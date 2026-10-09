local addonName, ns = ...
ns = ns or {}

local cache = {}
local stateCache = {}

local function ContextKey(context)
    if type(context) ~= "table" then return "none" end
    local profile = context.profile or {}
    local snapshotRevision = ns.GetEquipmentSnapshotRevision and ns.GetEquipmentSnapshotRevision(profile) or ""
    return table.concat({
        tostring(context.classFile or ""),
        tostring(context.specID or ""),
        tostring(context.specName or ""),
        tostring(profile.id or ""),
        tostring(snapshotRevision),
    }, "|")
end

local function EvaluateForContext(itemLink, context)
    local profile = context and context.profile or nil
    if not itemLink or not profile or not ns.BuildComparison then
        return nil
    end
    local key = tostring(itemLink) .. "::" .. ContextKey(context)
    local cached = cache[key]
    if cached ~= nil then
        return cached
    end
    local comparison = ns.BuildComparison(itemLink, profile)
    local selected = comparison and comparison.selected or nil
    local verdictScore = selected and tonumber(selected.deltaScore or selected.rawDeltaScore) or nil
    local result = selected and selected.isUpgrade and verdictScore and verdictScore > 0 or false
    cache[key] = result
    return result
end

local function SnapshotContainsItem(itemLink, context, guid)
    local profile = context and context.profile or nil
    if not profile or not ns.IsItemInEquipmentSnapshot then
        return false
    end
    local ok, contains = pcall(ns.IsItemInEquipmentSnapshot, profile, itemLink, guid)
    return ok and contains and true or false
end

local wornUpgradeCache = nil

function ns.ClearWornUpgradeCache()
    wornUpgradeCache = nil
end

function ns.ClearUpgradeIndicatorDecisionCache()
    cache = {}
    stateCache = {}
    wornUpgradeCache = nil
end

-- For every slot the player wears something in: the best piece in the bags that beats it for the spec that is played,
-- { [slotID] = { link = the bag piece, gain = points } }. The comparison is the tooltip's own (the bag piece is named by
-- the slot it would replace). Worked out once and kept until the gear or the bags change; nothing in combat.
function ns.GetBagUpgradesForWornSlots()
    if wornUpgradeCache then return wornUpgradeCache end
    local optionDb = _G.StatVerdictDB
    if type(optionDb) == "table" and optionDb.showWornDownArrow == false then return {} end   -- Options: switched off
    if InCombatLockdown and InCombatLockdown() then return {} end
    if not (ns.GetTooltipEvaluationContexts and ns.ShouldUseEquipmentSnapshot and ns.BuildComparison and C_Container) then
        return {}
    end
    local result = {}
    local primary, secondary = ns.GetTooltipEvaluationContexts()
    local played = nil
    for _, context in ipairs({ primary or false, secondary or false }) do
        if context and context.profile and not ns.ShouldUseEquipmentSnapshot(context.profile) then
            played = context
            break
        end
    end
    if not played then
        wornUpgradeCache = result
        return result
    end

    local bagIDs = { 0, 1, 2, 3, 4, 5 }
    if Enum and Enum.BagIndex then
        local bi = Enum.BagIndex
        bagIDs = { bi.Backpack or 0, bi.Bag_1 or 1, bi.Bag_2 or 2, bi.Bag_3 or 3, bi.Bag_4 or 4, bi.ReagentBag or 5 }
    end
    local isEquippable = (C_Item and C_Item.IsEquippableItem) or IsEquippableItem
    if ns.BeginContextScan then ns.BeginContextScan() end
    pcall(function()
        local seen = {}
        for _, bagID in ipairs(bagIDs) do
            for slot = 1, (tonumber(C_Container.GetContainerNumSlots(bagID)) or 0) do
                local link = C_Container.GetContainerItemLink(bagID, slot)
                if link and not seen[link] and (type(isEquippable) ~= "function" or isEquippable(link)) then
                    seen[link] = true
                    local ok, comparison = pcall(function()
                        if ns.WithStatVerdictSnapshotProfile then
                            return ns.WithStatVerdictSnapshotProfile(played.profile, function() return ns.BuildComparison(link, played.profile) end)
                        end
                        return ns.BuildComparison(link, played.profile)
                    end)
                    local selected = ok and comparison and not comparison.missingOffhand and comparison.selected or nil
                    local gain = selected and tonumber(selected.deltaScore or selected.rawDeltaScore) or nil
                    local slotID = selected and tonumber(selected.slotID) or nil
                    if selected and selected.isUpgrade and gain and gain > 0 and slotID then
                        local best = result[slotID]
                        if not best or gain > best.gain then result[slotID] = { link = link, gain = gain } end
                    end
                end
            end
        end
    end)
    if ns.EndContextScan then ns.EndContextScan() end
    -- Each entry knows its worn piece and whether the player chose to ignore this very warning (same worn piece, same
    -- better piece in the bags).
    local db = _G.StatVerdictDB
    local ignoredList = type(db) == "table" and type(db.ignoredWornWarnings) == "table" and db.ignoredWornWarnings or {}
    for slotID, entry in pairs(result) do
        entry.slot = slotID
        entry.key = tostring(played.specID or "") .. ":" .. tostring(ns.GetWornItemGUID and ns.GetWornItemGUID(slotID) or "")
        entry.ignored = ignoredList[entry.key] == entry.link
    end
    wornUpgradeCache = result
    return result
end

-- A warning that was ignored is forgotten as soon as its worn piece is not worn any more: putting the piece back on later is
-- a new decision.
local WORN_SLOTS_FOR_PRUNE = { 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 }
function ns.PruneIgnoredWornWarnings()
    local db = _G.StatVerdictDB
    local list = type(db) == "table" and db.ignoredWornWarnings or nil
    if type(list) ~= "table" or not ns.GetWornItemGUID then return end
    local worn = {}
    for _, slotID in ipairs(WORN_SLOTS_FOR_PRUNE) do
        local guid = ns.GetWornItemGUID(slotID)
        if guid then worn[guid] = true end
    end
    for key in pairs(list) do
        local guid = tostring(key):match(":(.*)$")
        if not (guid and worn[guid]) then list[key] = nil end
    end
end

-- "I know, it is my choice": the warning of this slot stays away while the worn piece and the better piece in the bags stay
-- the same. Returns true when there was a warning to ignore.
function ns.IgnoreWornWarning(slotID)
    local entry = ns.GetBagUpgradesForWornSlots()[tonumber(slotID)]
    if not entry then return false end
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    local db = _G.StatVerdictDB
    db.ignoredWornWarnings = type(db.ignoredWornWarnings) == "table" and db.ignoredWornWarnings or {}
    db.ignoredWornWarnings[entry.key] = entry.link
    wornUpgradeCache = nil
    return true
end

local function RoleState(role)
    if role == "main_spec" then
        return { kind = "main_spec", label = "MS", text = "MS", specRole = "main_spec", specLabel = "MS" }
    elseif role == "off_spec" then
        return { kind = "off_spec", label = "OS", text = "OS", specRole = "off_spec", specLabel = "OS" }
    elseif role == "both_specs" then
        -- In both loadouts: the bag shows both marks, MS at the top right and OS below it.
        return { kind = "both_specs", label = "MS/OS", text = "MS/OS", specRole = "both_specs", specLabel = "MS/OS" }
    end
    return nil
end

local function ContextHasSnapshotItem(itemLink, context, guid)
    return SnapshotContainsItem(itemLink, context, guid)
end

local function FlagOn(key)
    local db = _G.StatVerdictDB
    return db == nil or db[key] ~= false
end

-- Bag Markers settings (Arrow / MS-OS) apply ONLY to bags.
-- No master Enable All — each toggle is independent.
local function FilterBagIndicatorState(state)
    if not state then
        return nil
    end

    local kind = state.kind
    if kind == "upgrade" then
        if not FlagOn("showUpgradeArrow") then
            return nil
        end
        if state.specRole and not FlagOn("showMsOsLabels") then
            return { kind = "upgrade", label = "UP", text = nil }
        end
        return state
    end

    if kind == "main_spec" or kind == "off_spec" or kind == "both_specs" then
        if not FlagOn("showMsOsLabels") then
            return nil
        end
        return state
    end

    return state
end

-- Outside bags (quest, Adventure Guide, merchants, …): always show upgrade arrow
-- when the item is an upgrade, ignoring Bag Markers toggles. MS/OS stay bags-only.
local function FilterNonBagIndicatorState(state)
    if not state or state.kind ~= "upgrade" then
        return nil
    end
    return { kind = "upgrade", label = "UP", text = nil }
end

-- guid: the game's serial number of this very piece (bags only; nil elsewhere). It tells two copies of the same item apart.
local function ComputeRawIndicatorState(itemLink, guid)
    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    primaryContext = primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)

    local role = nil
    if ns.GetEquipmentSnapshotItemRole then
        local ok, resolvedRole = pcall(ns.GetEquipmentSnapshotItemRole, itemLink, guid)
        if ok then role = resolvedRole end
    end

    local primaryContains = ContextHasSnapshotItem(itemLink, primaryContext, guid)
    local secondaryContains = secondaryContext and secondaryContext ~= primaryContext and ContextHasSnapshotItem(itemLink, secondaryContext, guid) or false

    if not role and primaryContains and secondaryContains then
        role = "both_specs"
    elseif not role and primaryContains then
        role = "main_spec"
    elseif not role and secondaryContains then
        role = "off_spec"
    end

    local isUpgrade = false
    if primaryContext and not primaryContains and EvaluateForContext(itemLink, primaryContext) then
        isUpgrade = true
    elseif secondaryContext and secondaryContext ~= primaryContext and not secondaryContains and EvaluateForContext(itemLink, secondaryContext) then
        isUpgrade = true
    end

    local state = nil
    -- Saved in one build and an upgrade for the other: the arrow stays, with the letter of the build that holds it.
    if role and (primaryContains or secondaryContains) and not isUpgrade then
        state = RoleState(role)
    elseif isUpgrade then
        state = { kind = "upgrade", label = "UP", text = nil }
        local roleInfo = RoleState(role)
        if roleInfo then
            state.specRole = roleInfo.specRole
            state.specLabel = roleInfo.specLabel
        end
    else
        state = RoleState(role)
    end

    return state
end

function ns.GetUpgradeIndicatorItemState(itemLink, options)
    if type(itemLink) ~= "string" or itemLink == "" then
        return nil
    end

    local forBags = options and (options.source == "bags" or options.applyBagMarkerFilters)
    -- Detect bag frames even when caller forgot source= (legacy bag scan paths).
    if not forBags and options and options.isBag then
        forBags = true
    end

    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    primaryContext = primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)

    local itemGUID = forBags and options and options.itemGUID or nil
    local stateKey = table.concat({
        itemLink,
        tostring(itemGUID or ""),
        ContextKey(primaryContext),
        ContextKey(secondaryContext),
        forBags and "bags" or "world",
        forBags and tostring(FlagOn("showUpgradeArrow")) or "1",
        forBags and tostring(FlagOn("showMsOsLabels")) or "0",
    }, "::")
    if stateCache[stateKey] ~= nil then
        return stateCache[stateKey] or nil
    end

    local state = ComputeRawIndicatorState(itemLink, itemGUID)
    if forBags then
        state = FilterBagIndicatorState(state)
    else
        state = FilterNonBagIndicatorState(state)
    end

    stateCache[stateKey] = state or false
    return state
end
