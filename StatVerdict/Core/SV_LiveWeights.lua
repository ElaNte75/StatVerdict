local addonName, ns = ...
ns = ns or {}

local function SafeNumber(value)
    value = tonumber(value)
    if value and value == value then return value end
    return nil
end

local function IsPrimaryRow(row)
    return string.upper(tostring(row and row.type or "")) == "PRIMARY"
end

function ns.GetStatAuditBaseModifier(profile, statKey)
    if ns.GetStatWeight then
        return SafeNumber(ns.GetStatWeight(profile, statKey))
    end
    return nil
end

function ns.GetStatAuditLiveModifier(profile, statKey, baseModifier, softCapOverride, currentValue)
    if not baseModifier then return nil end
    local adjusted = baseModifier
    if ns.GetSoftCapAdjustedWeight then
        adjusted = SafeNumber(ns.GetSoftCapAdjustedWeight(profile, statKey, adjusted)) or adjusted
    end
    if softCapOverride and currentValue and softCapOverride > 0 and currentValue > softCapOverride then
        local overRatio = (currentValue - softCapOverride) / softCapOverride
        local damp = 1 - math.min(0.75, overRatio * 0.8)
        if damp < 0.25 then damp = 0.25 end
        adjusted = adjusted * damp
    end
    if ns.GetDynamicStatWeight then
        adjusted = SafeNumber(ns.GetDynamicStatWeight(profile, statKey, adjusted)) or adjusted
    end
    return adjusted
end

function ns.ApplyStatAuditPrimaryFloor(row, baseModifier, liveModifier)
    if not IsPrimaryRow(row) then return liveModifier end
    baseModifier = SafeNumber(baseModifier)
    liveModifier = SafeNumber(liveModifier)
    if baseModifier and liveModifier and liveModifier < baseModifier then
        return baseModifier
    end
    return liveModifier
end

function ns.StatAuditGetLiveTier(row)
    if row and row.liveTier then return row.liveTier end
    local rowType = string.upper(tostring(row and row.type or ""))
    if rowType == "PRIMARY" then return 1 end
    if rowType == "ITEM" then return 1 end
    if rowType == "MINOR" then return 4 end
    if rowType == "SECONDARY" then
        local secondaryRank = SafeNumber(row and row.secondaryRank) or 99
        if secondaryRank <= 2 then return 2 end
        return 3
    end
    return 4
end

function ns.StatAuditGetTieredLiveScale(row, ratioToTarget, currentValue, softCap)
    if not ratioToTarget then return 1.0 end
    local tier = ns.StatAuditGetLiveTier(row)
    if ratioToTarget < 0 then ratioToTarget = 0 end
    currentValue = SafeNumber(currentValue)
    softCap = SafeNumber(softCap)

    if tier == 1 then
        if row and row.key == "STATVERDICT_ITEM_LEVEL" then
            if ratioToTarget < 0.90 then return 1.20 end
            if ratioToTarget < 0.97 then return 1.08 end
            if ratioToTarget < 1.00 then return 1.06 end
            if ratioToTarget < 1.05 then return 0.70 end
            return 0.45
        end
        if ratioToTarget < 1.00 then
            local gap = math.min(1.0, 1.00 - ratioToTarget)
            return 1.00 + (gap * 0.40)
        end
        return 1.00
    end

    if tier == 2 then
        if ratioToTarget < 0.60 then return 1.45 end
        if ratioToTarget < 0.85 then return 1.25 end
        if ratioToTarget < 1.00 then return 1.08 end
        if ratioToTarget > 2.00 then return 0.45 end
        if ratioToTarget > 1.50 then return 0.60 end
        if ratioToTarget > 1.20 then return 0.78 end
        if currentValue and softCap and softCap > 0 and currentValue > softCap then
            local overSoft = (currentValue - softCap) / softCap
            if overSoft > 0.30 then return 0.62 end
            if overSoft > 0.15 then return 0.75 end
            return 0.88
        end
        return 1.00
    end

    if tier == 3 then
        if ratioToTarget < 0.60 then return 1.20 end
        if ratioToTarget < 0.85 then return 1.10 end
        if ratioToTarget < 1.00 then return 1.03 end
        if ratioToTarget > 2.00 then return 0.35 end
        if ratioToTarget > 1.50 then return 0.50 end
        if ratioToTarget > 1.20 then return 0.68 end
        if currentValue and softCap and softCap > 0 and currentValue > softCap then
            local overSoft = (currentValue - softCap) / softCap
            if overSoft > 0.30 then return 0.50 end
            if overSoft > 0.15 then return 0.65 end
            return 0.82
        end
        return 1.00
    end

    if ratioToTarget < 1.00 then return 1.00 end
    if ratioToTarget > 1.50 then return 0.45 end
    if ratioToTarget > 1.20 then return 0.60 end
    if ratioToTarget > 1.05 then return 0.78 end
    return 0.90
end

local function ResolveBaseModifier(args, row)
    local baseModifier = SafeNumber(row and row.baseModifier)
    if baseModifier == nil then
        baseModifier = ns.GetStatAuditBaseModifier(args.profile, row.key)
    end
    local customBucket = args.customBucket
    if customBucket and customBucket.baseModifiers then
        local customBase = SafeNumber(customBucket.baseModifiers[row.key])
        if customBase then baseModifier = customBase end
    end
    return baseModifier
end

local function ResolveSoftCap(args, row)
    local softCap = SafeNumber(row and row.softCap)
    if softCap == nil then
        softCap = ns.GetStatSoftCap and ns.GetStatSoftCap(args.profile, row.key) or nil
    end
    local customBucket = args.customBucket
    if customBucket and customBucket.softCaps then
        local customCap = SafeNumber(customBucket.softCaps[row.key])
        if customCap then softCap = customCap end
    end
    return softCap
end

local function ApplyCustomTarget(customBucket, row)
    if customBucket and customBucket.targets and customBucket.targets[row.key] then
        row.target = SafeNumber(customBucket.targets[row.key]) or row.target
    end
end

function ns.NormalizeStatAuditLiveWeights(args)
    args = args or {}
    local rows = args.rows or {}
    local maxDataRows = args.maxDataRows or #rows
    local getCurrentValue = args.getCurrentValue
    local getRatingValue = args.getRatingValue
    local isSecondaryKey = args.isSecondaryKey
    if type(getCurrentValue) ~= "function" then return {} end

    local normalizedAuditLiveByKey = {}
    local rawLiveByKey, baseLiveByKey, baseLiveTotal, rawLiveTotal = {}, {}, 0, 0
    local liveMetaByKey = {}
    local itemLevelHasTarget = false
    local itemLevelBelowTarget = false

    for index = 1, maxDataRows do
        local row = rows[index]
        if row and row.key then
            ApplyCustomTarget(args.customBucket, row)
            local current = getCurrentValue(row.key)
            local targetValue = SafeNumber(row.target)
            local calcCurrent = current
            local calcTarget = targetValue
            if isSecondaryKey and isSecondaryKey(row.key) and row.valueMode == "percent" then
                calcCurrent = getRatingValue and getRatingValue(row.key) or calcCurrent
                calcTarget = SafeNumber(row.targetRating) or SafeNumber(row.target)
            end
            local softCap = ResolveSoftCap(args, row)
            local baseModifier = ResolveBaseModifier(args, row)
            if baseModifier then
                local liveModifier = ns.GetStatAuditLiveModifier(args.profile, row.key, baseModifier, softCap, calcCurrent)
                local ratioToTarget = nil
                if calcCurrent and calcTarget and calcTarget > 0 then
                    ratioToTarget = calcCurrent / calcTarget
                end
                if row.key == "STATVERDICT_ITEM_LEVEL" and calcTarget and calcTarget > 0 then
                    itemLevelHasTarget = true
                    if calcCurrent and calcCurrent < calcTarget then
                        itemLevelBelowTarget = true
                    end
                end
                if ratioToTarget then
                    liveModifier = baseModifier * ns.StatAuditGetTieredLiveScale(row, ratioToTarget, calcCurrent, softCap)
                end
                liveModifier = SafeNumber(liveModifier) or baseModifier
                liveModifier = ns.ApplyStatAuditPrimaryFloor(row, baseModifier, liveModifier)
                baseLiveTotal = baseLiveTotal + baseModifier
                rawLiveTotal = rawLiveTotal + liveModifier
                rawLiveByKey[row.key] = liveModifier
                baseLiveByKey[row.key] = baseModifier
                liveMetaByKey[row.key] = {
                    tier = ns.StatAuditGetLiveTier(row),
                    priority = SafeNumber(row.priority) or index,
                    ratio = ratioToTarget,
                }
            end
        end
    end

    if baseLiveTotal <= 0 or rawLiveTotal <= 0 then return normalizedAuditLiveByKey end

    local fixedTotal, fixedRawTotal = 0, 0
    if not itemLevelHasTarget and rawLiveByKey.STATVERDICT_ITEM_LEVEL and baseLiveByKey.STATVERDICT_ITEM_LEVEL then
        fixedTotal = baseLiveByKey.STATVERDICT_ITEM_LEVEL
        fixedRawTotal = rawLiveByKey.STATVERDICT_ITEM_LEVEL
        normalizedAuditLiveByKey.STATVERDICT_ITEM_LEVEL = fixedTotal
    end
    local variableBaseTotal = baseLiveTotal - fixedTotal
    local variableRawTotal = rawLiveTotal - fixedRawTotal
    local scale = 1
    if variableBaseTotal > 0 and variableRawTotal > 0 then
        scale = variableBaseTotal / variableRawTotal
    elseif rawLiveTotal > 0 then
        scale = baseLiveTotal / rawLiveTotal
    end
    for key, rawLive in pairs(rawLiveByKey) do
        if normalizedAuditLiveByKey[key] == nil then
            normalizedAuditLiveByKey[key] = rawLive * scale
        end
    end

    local function protectDeficitFloor(protectedKey)
        local protectedBase = baseLiveByKey[protectedKey]
        local protectedLive = normalizedAuditLiveByKey[protectedKey]
        if not protectedBase or not protectedLive or protectedLive >= protectedBase then return end

        local debt = protectedBase - protectedLive
        normalizedAuditLiveByKey[protectedKey] = protectedBase
        local function takeFrom(statKey)
            if debt <= 0 or statKey == protectedKey then return end
            local value = normalizedAuditLiveByKey[statKey]
            if not value or value <= 0 then return end
            local room = math.max(0, value - 0.05)
            if room <= 0 then return end
            local taken = math.min(debt, room)
            normalizedAuditLiveByKey[statKey] = value - taken
            debt = debt - taken
        end
        local donors = {}
        for _, row in ipairs(rows) do
            if row and row.key and row.key ~= protectedKey then
                local meta = liveMetaByKey[row.key] or {}
                donors[#donors + 1] = {
                    key = row.key,
                    tier = SafeNumber(meta.tier) or SafeNumber(row.liveTier) or 4,
                    priority = SafeNumber(meta.priority) or SafeNumber(row.priority) or 999,
                    over = math.max(0, (SafeNumber(meta.ratio) or 0) - 1),
                }
            end
        end
        table.sort(donors, function(a, b)
            if a.key == "ITEM_MOD_SPEED" and b.key ~= "ITEM_MOD_SPEED" then return true end
            if b.key == "ITEM_MOD_SPEED" and a.key ~= "ITEM_MOD_SPEED" then return false end
            if math.abs((a.over or 0) - (b.over or 0)) > 0.05 then return (a.over or 0) > (b.over or 0) end
            if (a.tier or 4) ~= (b.tier or 4) then return (a.tier or 4) > (b.tier or 4) end
            return (a.priority or 999) > (b.priority or 999)
        end)
        for _, donor in ipairs(donors) do
            takeFrom(donor.key)
            if debt <= 0 then break end
        end
        if debt > 0 then
            for _, donor in ipairs(donors) do
                if donor.tier ~= 1 then
                    takeFrom(donor.key)
                    if debt <= 0 then break end
                end
            end
        end
    end

    if itemLevelHasTarget and itemLevelBelowTarget then
        protectDeficitFloor("STATVERDICT_ITEM_LEVEL")
    end
    local topSecondaryKey = nil
    for _, row in ipairs(rows) do
        if row and row.key and string.upper(tostring(row.type or "")) == "SECONDARY" then
            topSecondaryKey = row.key
            break
        end
    end
    for _, row in ipairs(rows) do
        if row and row.key and row.key ~= "STATVERDICT_ITEM_LEVEL" then
            local meta = liveMetaByKey[row.key] or {}
            local ratio = SafeNumber(meta.ratio)
            local tier = SafeNumber(meta.tier) or SafeNumber(row.liveTier) or 4
            -- Keep primary / tier-1 and the #1 secondary from going below base while still behind target.
            -- Otherwise normalize can paint Crit (top secondary at ~74%) as a red "penalty".
            if IsPrimaryRow(row) or (tier == 1 and ratio and ratio < 1) then
                protectDeficitFloor(row.key)
            elseif topSecondaryKey and row.key == topSecondaryKey and ratio and ratio < 1 then
                protectDeficitFloor(row.key)
            end
        end
    end

    -- Once two secondary stats have both met their targets, live demand may reduce
    -- their value but must not reverse the source priority shown in the audit table.
    local previousOverSecondary = nil
    local reclaimed = 0
    for _, row in ipairs(rows) do
        local key = row and row.key
        local meta = key and liveMetaByKey[key] or nil
        local isSecondary = string.upper(tostring(row and row.type or "")) == "SECONDARY"
        local ratio = SafeNumber(meta and meta.ratio)
        if isSecondary and ratio and ratio >= 1 and normalizedAuditLiveByKey[key] and baseLiveByKey[key] then
            if previousOverSecondary then
                local previousLive = normalizedAuditLiveByKey[previousOverSecondary]
                local previousBase = baseLiveByKey[previousOverSecondary]
                local currentBase = baseLiveByKey[key]
                if previousLive and previousBase and previousBase > 0 and currentBase then
                    local maximum = previousLive * (currentBase / previousBase)
                    if normalizedAuditLiveByKey[key] > maximum then
                        reclaimed = reclaimed + (normalizedAuditLiveByKey[key] - maximum)
                        normalizedAuditLiveByKey[key] = maximum
                    end
                end
            end
            previousOverSecondary = key
        elseif isSecondary then
            previousOverSecondary = nil
        end
    end

    if reclaimed > 0 then
        for _, row in ipairs(rows) do
            local key = row and row.key
            local meta = key and liveMetaByKey[key] or nil
            local ratio = SafeNumber(meta and meta.ratio)
            if key and normalizedAuditLiveByKey[key] and ratio and ratio < 1 then
                normalizedAuditLiveByKey[key] = normalizedAuditLiveByKey[key] + reclaimed
                reclaimed = 0
                break
            end
        end
    end

    return normalizedAuditLiveByKey
end
