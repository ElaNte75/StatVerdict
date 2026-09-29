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

local function SnapshotContainsItem(itemLink, context)
    local profile = context and context.profile or nil
    if not profile or not ns.IsItemInEquipmentSnapshot then
        return false
    end
    local ok, contains = pcall(ns.IsItemInEquipmentSnapshot, profile, itemLink)
    return ok and contains and true or false
end

function ns.ClearUpgradeIndicatorDecisionCache()
    cache = {}
    stateCache = {}
end

local function RoleState(role)
    if role == "main_spec" then
        return { kind = "main_spec", label = "MS", text = "MS", specRole = "main_spec", specLabel = "MS" }
    elseif role == "off_spec" then
        return { kind = "off_spec", label = "OS", text = "OS", specRole = "off_spec", specLabel = "OS" }
    elseif role == "both_specs" then
        -- Keep the bag marker compact and familiar. A shared item is protected by
        -- the Main Spec label; the detailed membership remains available through
        -- snapshot/profile data, but the icon should stay visually simple.
        return { kind = "main_spec", label = "MS", text = "MS", specRole = "main_spec", specLabel = "MS" }
    end
    return nil
end

local function ContextHasSnapshotItem(itemLink, context)
    return SnapshotContainsItem(itemLink, context)
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

local function ComputeRawIndicatorState(itemLink)
    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    primaryContext = primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)

    local role = nil
    if ns.GetEquipmentSnapshotItemRole then
        local ok, resolvedRole = pcall(ns.GetEquipmentSnapshotItemRole, itemLink)
        if ok then role = resolvedRole end
    end

    local primaryContains = ContextHasSnapshotItem(itemLink, primaryContext)
    local secondaryContains = secondaryContext and secondaryContext ~= primaryContext and ContextHasSnapshotItem(itemLink, secondaryContext) or false

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
    if role and (primaryContains or secondaryContains) then
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

    local stateKey = table.concat({
        itemLink,
        ContextKey(primaryContext),
        ContextKey(secondaryContext),
        forBags and "bags" or "world",
        forBags and tostring(FlagOn("showUpgradeArrow")) or "1",
        forBags and tostring(FlagOn("showMsOsLabels")) or "0",
    }, "::")
    if stateCache[stateKey] ~= nil then
        return stateCache[stateKey] or nil
    end

    local state = ComputeRawIndicatorState(itemLink)
    if forBags then
        state = FilterBagIndicatorState(state)
    else
        state = FilterNonBagIndicatorState(state)
    end

    stateCache[stateKey] = state or false
    return state
end
