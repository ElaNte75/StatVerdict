"""A small simulated game world for the loadout tests: worn pieces, bags, serial numbers, spec changes, a clock and the
game's events. The real add-on files (SV_SpecSnapshot.lua, SV_UpgradeIndicatorLogic.lua) run on top of it; only the scoring
(BuildComparison) and the selection of the two builds are stand-ins."""
from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime

WORLD = r"""
clock, SPEC, COMBAT = 1000, 251, false
INVSLOT_MAINHAND, INVSLOT_OFFHAND = 16, 17
DEFAULT_CHAT_FRAME = { AddMessage = function() end }
worn, wornGUID = {}, {}            -- slot -> link ; slot -> serial
bagItems = {}                      -- bag slot (1..30) -> { link =, guid = }
cursor = nil
pendingEvents = false
frames, timers, timerSeq = {}, {}, 0
errors = {}

GetTime = function() return clock end
InCombatLockdown = function() return COMBAT end
GetSpecialization = function() return 1 end
GetSpecializationInfo = function() return SPEC end
GetSpecializationInfoByID = function(id) return id, "Spec" .. id end
UnitGUID = function() return "Player-1-ME" end
GetInventoryItemLink = function(unit, slot) return worn[slot] end
CursorHasItem = function() return cursor ~= nil end
ClearCursor = function()
    if cursor then
        for i = 1, 30 do if not bagItems[i] then bagItems[i] = cursor cursor = nil pendingEvents = true break end end
    end
end

C_Container = {
    GetContainerNumSlots = function(b) if b == 0 then return 30 end return 0 end,
    GetContainerItemLink = function(b, s) local it = bagItems[s] return it and it.link or nil end,
    PickupContainerItem = function(b, s)
        if cursor then return end
        if bagItems[s] then cursor = bagItems[s]; bagItems[s] = nil end
    end,
}
ItemLocation = {
    CreateFromEquipmentSlot = function(_, slot) return { eq = slot } end,
    CreateFromBagAndSlot = function(_, b, s) return { bag = b, slot = s } end,
}
local function swapIntoSlot(it, slot)
    local oldLink, oldGUID = worn[slot], wornGUID[slot]
    worn[slot], wornGUID[slot] = it.link, it.guid
    pendingEvents = true
    if oldLink then return { link = oldLink, guid = oldGUID } end
    return nil
end
C_Item = {
    EquipItemByName = function(link, slot)
        if COMBAT then return end
        for i = 1, 30 do
            local it = bagItems[i]
            if it and it.link == link then
                bagItems[i] = swapIntoSlot(it, slot)
                return
            end
        end
    end,
    GetItemGUID = function(location)
        if location.eq then return wornGUID[location.eq] end
        local it = bagItems[location.slot]
        return it and it.guid or nil
    end,
    GetItemCount = function(id)
        local n = 0
        for i = 1, 30 do local it = bagItems[i] if it and tonumber(it.link:match("item:(%d+)")) == id then n = n + 1 end end
        for s, l in pairs(worn) do if tonumber(l:match("item:(%d+)")) == id then n = n + 1 end end
        return n
    end,
    IsEquippableItem = function() return true end,
}
EquipCursorItem = function(slot)
    if COMBAT or not cursor then return end
    local old = swapIntoSlot(cursor, slot)
    cursor = old
end
CreateFrame = function()
    local f = { scripts = {}, events = {} }
    f.RegisterEvent = function(self, event) self.events[event] = true end
    f.SetScript = function(self, name, fn) self.scripts[name] = fn end
    frames[#frames + 1] = f
    return f
end
C_Timer = { After = function(d, fn) timerSeq = timerSeq + 1 timers[#timers + 1] = { at = clock + d, fn = fn, seq = timerSeq } end }

function fireEvent(event)
    for _, f in ipairs(frames) do
        local h = f.scripts.OnEvent
        if h and f.events[event] then local ok, err = pcall(h, f, event) if not ok then errors[#errors + 1] = tostring(err) end end
    end
end
function flushEvents()
    local guard = 0
    while pendingEvents and guard < 20 do
        pendingEvents = false
        fireEvent("PLAYER_EQUIPMENT_CHANGED"); fireEvent("BAG_UPDATE_DELAYED")
        guard = guard + 1
    end
end
function advance(dt)
    local target = clock + dt
    flushEvents()
    while true do
        local bi
        for i, t in ipairs(timers) do
            if t.at <= target and (not bi or t.at < timers[bi].at or (t.at == timers[bi].at and t.seq < timers[bi].seq)) then bi = i end
        end
        if not bi then break end
        local t = table.remove(timers, bi)
        if t.at > clock then clock = t.at end
        local ok, err = pcall(t.fn)
        if not ok then errors[#errors + 1] = tostring(err) end
        flushEvents()
    end
    clock = target
end
function changeSpec(id)
    SPEC = id
    fireEvent("PLAYER_SPECIALIZATION_CHANGED")
end

StatVerdictDB = { specSnapshots = { version = 1, revision = 0, bySpecID = {} } }
"""

# items: id -> { slot type, score for spec 251, score for spec 250 }
STUBS = r"""
ITEMS = {}      -- id -> { kind = "ring"|"neck"|"head"|"trinket", s251 =, s250 = }
local function idOf(link) return tonumber(link:match("item:(%d+)")) end
local function slotsOf(kind)
    if kind == "ring" then return { 11, 12 } elseif kind == "neck" then return { 2 } elseif kind == "head" then return { 1 }
    elseif kind == "trinket" then return { 13, 14 } end
    return {}
end
ns.GetComparableSlots = function(link) local it = ITEMS[idOf(link)] return it and slotsOf(it.kind) or {} end
ns.IsItemCompatibleWithSlot = function() return true end
ns.GetItemEquipLocation = function() return "INVTYPE_FINGER" end
ns.GetSavedStatAuditSelection = function() return { primarySpecID = 251, secondaryEnabled = true, secondarySpecID = 250 } end
ns.GetTooltipEvaluationContexts = function()
    return { specID = 251, profile = { specID = 251, id = "ms" } }, { specID = 250, profile = { specID = 250, id = "os" } }
end
local function score(link, specID)
    local it = ITEMS[idOf(link)]
    return it and it["s" .. specID] or 0
end
ns.BuildComparison = function(link, profile)
    local it = ITEMS[idOf(link)]
    if not it then return nil end
    local best
    for _, slot in ipairs(slotsOf(it.kind)) do
        local eq
        if ns.ShouldUseEquipmentSnapshot(profile) then eq = ns.GetSnapshotEquippedLink(profile, slot)
        else eq = (ns.GetPlayedLoadoutOverlay and ns.GetPlayedLoadoutOverlay(profile, slot)) or worn[slot] end
        local cur = eq and score(eq, profile.specID) or 0
        local delta = score(link, profile.specID) - cur
        if eq and idOf(eq) == idOf(link) then delta = 0 end
        if not best or cur < best.cur then best = { slot = slot, cur = cur, delta = delta } end
    end
    return { selected = { slotID = best.slot, deltaScore = best.delta, isUpgrade = best.delta > 0 }, comparisons = {} }
end
"""


class World:
    def __init__(self, items, characterGUID="Player-1-ME", played=251):
        self.lua = new_runtime()
        self.lua.execute(WORLD)
        self.lua.execute(f"SPEC = {played}")
        self.lua.execute("ns = {}")
        self.ns = self.lua.eval("ns")
        # The stubs need ns and the real snapshot file first (BuildComparison reads its functions at call time).
        load_addon_file(self.lua, self.ns, "Core/SV_SpecSnapshot.lua")
        self.lua.execute(STUBS)
        for item_id, (kind, s251, s250) in items.items():
            self.lua.execute(f'ITEMS[{item_id}] = {{ kind = "{kind}", s251 = {s251}, s250 = {s250} }}')
        load_addon_file(self.lua, self.ns, "Core/SV_UpgradeIndicatorLogic.lua")
        self.serial = 0
        self.links = {}

    # ---- building the world
    def link(self, item_id, level=0):
        return f"|Hitem:{item_id}::{level}|h[Item{item_id}]|h"

    def new_guid(self):
        self.serial += 1
        return f"Item-1-0-{self.serial:08d}"

    def wear(self, slot, item_id, guid=None):
        guid = guid or self.new_guid()
        self.lua.execute(f'worn[{slot}] = "{self.link(item_id)}"; wornGUID[{slot}] = "{guid}"')
        return guid

    def bag(self, item_id, guid=None, level=0):
        guid = guid or self.new_guid()
        self.lua.execute(f'for i = 1, 30 do if not bagItems[i] then bagItems[i] = {{ link = "{self.link(item_id, level)}", guid = "{guid}" }} break end end')
        return guid

    def snapshot(self, spec, **fields):
        """Install a saved loadout. fields: equipment/marked {slot: item_id}, markedGUID {slot: guid}, manualSlots {slot: true|guid}."""
        parts = [f'specID = {spec}', 'revision = 1', 'characterGUID = "Player-1-ME"', 'stats = { STATVERDICT_ITEM_LEVEL = 280 }']
        for key in ("equipment", "marked"):
            if key in fields:
                body = ", ".join(f'["{s}"] = "{self.link(i)}"' for s, i in fields[key].items())
                parts.append(f"{key} = {{ {body} }}")
        for key in ("markedGUID", "manualSlots"):
            if key in fields:
                body = ", ".join((f'["{s}"] = true' if v is True else f'["{s}"] = "{v}"') for s, v in fields[key].items())
                parts.append(f"{key} = {{ {body} }}")
        if fields.get("seeded", True):
            parts.append("autoMarkSeeded = true")
        self.lua.execute(f'StatVerdictDB.specSnapshots.bySpecID["{spec}"] = {{ {", ".join(parts)} }}')

    # ---- what happens in the game
    def advance(self, seconds):
        self.lua.execute(f"advance({seconds})")

    def settle(self, seconds=30):
        self.advance(seconds)

    def change_spec(self, spec):
        self.lua.execute(f"changeSpec({spec})")

    def login(self):
        self.lua.execute('fireEvent("PLAYER_ENTERING_WORLD")')

    def set_combat(self, on):
        self.lua.execute(f"COMBAT = {'true' if on else 'false'}")
        if not on:
            self.lua.execute('fireEvent("PLAYER_REGEN_ENABLED")')

    def put_on(self, bag_slot, slot):
        """The player drags a bag piece onto a slot."""
        self.lua.execute(f"""
        local it = bagItems[{bag_slot}]
        if it and not COMBAT then
            local oldLink, oldGUID = worn[{slot}], wornGUID[{slot}]
            worn[{slot}], wornGUID[{slot}] = it.link, it.guid
            bagItems[{bag_slot}] = oldLink and {{ link = oldLink, guid = oldGUID }} or nil
            pendingEvents = true
        end""")

    def take_off(self, slot):
        self.lua.execute(f"""
        if worn[{slot}] and not COMBAT then
            for i = 1, 30 do if not bagItems[i] then
                bagItems[i] = {{ link = worn[{slot}], guid = wornGUID[{slot}] }}
                worn[{slot}], wornGUID[{slot}] = nil, nil
                pendingEvents = true
                break end end
        end""")

    # ---- looking
    def worn_ids(self):
        out = {}
        for slot in range(1, 18):
            link = self.lua.eval(f"worn[{slot}]")
            if link:
                out[slot] = (int(str(link).split("item:")[1].split(":")[0]), str(self.lua.eval(f"wornGUID[{slot}]")))
        return out

    def bag_ids(self):
        out = []
        for i in range(1, 31):
            link = self.lua.eval(f"bagItems[{i}] and bagItems[{i}].link")
            if link:
                out.append((i, int(str(link).split("item:")[1].split(":")[0]), str(self.lua.eval(f"bagItems[{i}].guid"))))
        return out

    def indicator(self, bag_slot):
        """The state the bag marker shows for this bag slot: (kind, specRole) or None."""
        r = self.lua.eval(f"""
        (function()
            local it = bagItems[{bag_slot}]
            if not it then return "" end
            local s = ns.GetUpgradeIndicatorItemState(it.link, {{ source = "bags", itemGUID = it.guid }})
            if not s then return "none" end
            return tostring(s.kind) .. "/" .. tostring(s.specRole)
        end)()""")
        return str(r)

    def marked_guid(self, spec, slot):
        v = self.lua.eval(f'(StatVerdictDB.specSnapshots.bySpecID["{spec}"] or {{}}).markedGUID and StatVerdictDB.specSnapshots.bySpecID["{spec}"].markedGUID["{slot}"]')
        return str(v) if v else None

    def errors(self):
        return [str(self.lua.eval(f"errors[{i}]")) for i in range(1, int(self.lua.eval("#errors")) + 1)]

    def dump(self):
        """The whole saved loadout state as text (to compare two moments)."""
        return str(self.lua.eval("""
        (function()
            local keys = {}
            local function ser(v, indent)
                if type(v) ~= "table" then return tostring(v) end
                local ks = {}
                for k in pairs(v) do ks[#ks + 1] = tostring(k) end
                table.sort(ks)
                local out = {}
                for _, k in ipairs(ks) do
                    local val = v[k]
                    if val == nil then val = v[tonumber(k)] end
                    if k ~= "revision" and k ~= "capturedAt" then out[#out + 1] = k .. "=" .. ser(val) end
                end
                return "{" .. table.concat(out, ",") .. "}"
            end
            return ser(StatVerdictDB.specSnapshots.bySpecID)
        end)()"""))
