"""Loads the whole addon in a fake WoW for the scoring and tooltip tests.

The real Lua 5.1 runs through lupa, with the real generated guide data; tests put items and a character into it and ask
the addon's own functions (ns.BuildComparison and the rest) for the answer. Nothing here is a copy of the scoring: if
the addon changes, the answer changes. Development tool, not part of the addon.
"""
from __future__ import annotations

from typing import Any

from tools.tests.test_addon_lua import FRAME_STUB, compile_lua_file, new_runtime, toc_lua_files
from tools.tests.test_addon_integration import PIN_TIME_TO_BUILD, WOW_GLOBALS_STUB

# slot name -> (inventory slot id, equip location)
SLOTS = {
    "head": (1, "INVTYPE_HEAD"), "neck": (2, "INVTYPE_NECK"), "shoulders": (3, "INVTYPE_SHOULDER"),
    "shoulder": (3, "INVTYPE_SHOULDER"), "back": (15, "INVTYPE_CLOAK"), "chest": (5, "INVTYPE_CHEST"),
    "wrists": (9, "INVTYPE_WRIST"), "wrist": (9, "INVTYPE_WRIST"), "hands": (10, "INVTYPE_HAND"),
    "waist": (6, "INVTYPE_WAIST"), "legs": (7, "INVTYPE_LEGS"), "feet": (8, "INVTYPE_FEET"),
    "finger1": (11, "INVTYPE_FINGER"), "finger2": (12, "INVTYPE_FINGER"),
    "trinket1": (13, "INVTYPE_TRINKET"), "trinket2": (14, "INVTYPE_TRINKET"),
    "main_hand": (16, "INVTYPE_WEAPON"), "off_hand": (17, "INVTYPE_WEAPON"),
}
JEWELRY_OR_CLOAK = {"neck", "back", "finger1", "finger2", "trinket1", "trinket2"}
STAT_KEYS = {
    "agility": "ITEM_MOD_AGILITY_SHORT",
    "strength": "ITEM_MOD_STRENGTH_SHORT",
    "intellect": "ITEM_MOD_INTELLECT_SHORT",
    "stamina": "ITEM_MOD_STAMINA_SHORT",
    "crit_rating": "ITEM_MOD_CRIT_RATING_SHORT",
    "haste_rating": "ITEM_MOD_HASTE_RATING_SHORT",
    "mastery_rating": "ITEM_MOD_MASTERY_RATING_SHORT",
    "versatility_rating": "ITEM_MOD_VERSATILITY",
}
COMBAT_RATING = {"crit": 9, "haste": 18, "mastery": 26, "versatility": 29}  # CR_* ids the addon may ask for

CHARACTER = {"classFile": "SHAMAN", "className": "Shaman", "specKey": "SHAMAN_ENHANCEMENT", "specID": 263,
             "role": "DAMAGER", "heroTalentName": "Totemic"}

INVSLOT_LUA = """
INVSLOT_HEAD, INVSLOT_NECK, INVSLOT_SHOULDER, INVSLOT_BODY, INVSLOT_CHEST = 1, 2, 3, 4, 5
INVSLOT_WAIST, INVSLOT_LEGS, INVSLOT_FEET, INVSLOT_WRIST, INVSLOT_HAND = 6, 7, 8, 9, 10
INVSLOT_FINGER1, INVSLOT_FINGER2, INVSLOT_TRINKET1, INVSLOT_TRINKET2 = 11, 12, 13, 14
INVSLOT_BACK, INVSLOT_MAINHAND, INVSLOT_OFFHAND, INVSLOT_RANGED, INVSLOT_TABARD = 15, 16, 17, 18, 19
"""

ITEM_API_LUA = """
ITEMS = {}
local function info(link) return ITEMS[link] end
GetItemInfo = function(link)
    local i = info(link); if not i then return nil end
    return i.name, link, 4, i.ilvl, 80, "Armor", i.subclass, 1, i.equipLoc, 0, 0, i.classID, i.subID
end
GetItemInfoInstant = function(link)
    local i = info(link); if not i then return nil end
    return i.id, "Armor", i.subclass, i.equipLoc, 0, i.classID, i.subID
end
GetDetailedItemLevelInfo = function(link) local i = info(link); return i and i.ilvl or nil end
GetItemStats = function(link) local i = info(link); return i and i.stats or nil end
GetInventoryItemLink = function(unit, slot) return EQUIPPED and EQUIPPED[slot] or nil end
C_Item = setmetatable({
    GetItemStats = function(link) local i = info(link); return i and i.stats or nil end,
    GetItemInfo = function(link) return GetItemInfo(link) end,
    GetItemInfoInstant = function(link) return GetItemInfoInstant(link) end,
    GetDetailedItemLevelInfo = function(link) return GetDetailedItemLevelInfo(link) end,
    GetItemNumSockets = function() return 0 end,
}, {__index = function() return function() return nil end end})
"""


def lua_pairs(table) -> dict:
    return {key: table[key] for key in table.keys()} if table is not None else {}


def lua_list(table) -> list:
    return [table[i] for i in range(1, len(table) + 1)] if table is not None else []


def load_addon():
    """The whole addon (toc order) with the real generated data, in a fake WoW."""
    lua = new_runtime()
    lua.execute(FRAME_STUB)
    lua.execute(WOW_GLOBALS_STUB)
    # Real numbers, not stubs: the addon builds its slot tables from these while loading.
    lua.execute(INVSLOT_LUA)
    lua.globals().StatVerdictDB = lua.table()
    ns = lua.table()
    lua.globals().SV_TEST_NS = ns
    for path in toc_lua_files():
        compile_lua_file(lua, path)("StatVerdict", ns)
    lua.execute("setmetatable(_G, nil)")
    lua.eval("function(src, buildId, parse) assert(loadstring(src))(buildId, parse) end")(
        PIN_TIME_TO_BUILD, ns.ClassCodexTargets.buildId, ns.ProfileRepository.ParseBuildTime)
    lua.execute(ITEM_API_LUA)
    return lua, ns


def item_stats(raw: dict[str, Any]) -> dict[str, float]:
    return {lua_key: float(raw[key]) for key, lua_key in STAT_KEYS.items() if isinstance(raw.get(key), (int, float))}


def register_item(lua, link: str, item_id: int, raw: dict[str, Any], slot: str) -> None:
    _, equip_loc = SLOTS[slot]
    stats = lua.table_from(item_stats(raw))
    sub_id = 0 if slot in JEWELRY_OR_CLOAK else 3  # 3 = mail, the Shaman armor type
    subclass = "Miscellaneous" if slot in JEWELRY_OR_CLOAK else "Mail"
    lua.globals().ITEMS[link] = lua.table(
        id=item_id, name=str(raw.get("name") or f"item {item_id}"), ilvl=float(raw.get("ilevel") or 0),
        equipLoc=equip_loc, stats=stats, classID=4, subID=sub_id, subclass=subclass)


def set_character(lua, ratings: dict[str, float], agility: float) -> None:
    """The WoW APIs that say who is playing and how many rating points they have now."""
    crit, haste = ratings.get("crit", 0), ratings.get("haste", 0)
    mastery, vers = ratings.get("mastery", 0), ratings.get("versatility", 0)
    lua.execute(f"""
    -- The game defines these rating ids; without them the addon cannot read the character's
    -- ratings and its live weights stay neutral.
    CR_CRIT_MELEE, CR_HASTE_MELEE, CR_MASTERY, CR_VERSATILITY_DAMAGE_DONE = 9, 18, 26, 29
    UnitClass = function() return "Shaman", "SHAMAN", 7 end
    UnitLevel = function() return 90 end
    UnitName = function() return "Tester" end
    GetSpecialization = function() return 2 end
    GetSpecializationInfo = function() return 263, "Enhancement", "", 0, "DAMAGER", "AGILITY" end
    GetCombatRating = function(id)
        if id == 9 then return {crit} end
        if id == 18 then return {haste} end
        if id == 26 then return {mastery} end
        if id == 29 then return {vers} end
        return 0
    end
    UnitStat = function() return {agility}, {agility}, 0, 0 end
    """)
    # The addon reads ratings at gear/spec changes only; a new character is such a change.
    lua.execute("if SV_TEST_NS and SV_TEST_NS.InvalidateCurrentStatRatings then SV_TEST_NS.InvalidateCurrentStatRatings() end")


def build_profile(lua, ns, goal: str, mode: str):
    ns.ProfileRepository.InvalidateProviderViews()
    context = lua.table(**CHARACTER)
    context.goal = goal
    return ns.ProfileRepository.BuildRuntimeProfile(context)
