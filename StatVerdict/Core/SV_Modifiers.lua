local addonName, ns = ...

-- Global scoring model.
-- Profiles define stat priority/order. This file defines how StatVerdict values those priorities.
-- Keep this generic for all classes/specs; use explicit profile.modifierOverrides only for real exceptions.

ns.GlobalStatVerdictModifiers = {
    pointBudget = 10,
    itemLevel = {
        heroTalentUnlockLevel = 80,
        preExpansionTargetItemLevel = 70,
        campaignTargetItemLevel = 200,
        levelingTargetItemLevel = 70,
        soloTargetItemLevel = 276,
        maxLevelWeight = 1.20,
    },
    dynamicTarget = {
        enabled = true,
        maxPositiveGap = 0.60,
        maxNegativeGap = 0.20,
        -- Tiered behavior:
        -- A: primary + top 2 secondary
        -- B: remaining secondary
        -- C: minor/extra stats
        tierABoost = 0.30,
        tierBBoost = 0.18,
        tierCBoost = 0.10,
        tierAPenalty = 0.20,
        tierBPenalty = 0.65,
        tierCPenalty = 0.80,
        tierAFloor = 0.92,
        tierBFloor = 0.45,
        tierCFloor = 0.25,
        topSecondaryLimit = 2,
    },
    primary = 4.00,
    secondary = { 4.00, 3.00, 2.00, 1.00 },
    fallbackSecondary = 1.00,
    socket = {
        primarySecondaryRatingPerSocket = 16,
        secondarySecondaryRatingPerSocket = 7,
        maxPrismaticSocketsPerItem = 3,
    },
    extras = {
        ITEM_MOD_STAMINA_SHORT = 1.00,
        STATVERDICT_ARMOR = 2.00,
        ITEM_MOD_AVOIDANCE_RATING_SHORT = 0.50,
        ITEM_MOD_LIFESTEAL = 0.50,
        ITEM_MOD_SPEED = 0.50,
        ITEM_MOD_SPEED_SHORT = 0.50,
        STATVERDICT_MAIN_HAND_DPS = 6.00,
        STATVERDICT_OFF_HAND_DPS = 2.00,
    },
    jewelry = {
        enabled = true,
        topSecondaryAsPrimary = 0.90,
        secondSecondaryAsPrimary = 0.78,
        thirdSecondaryAsPrimary = 0.68,
        otherSecondaryBoost = 1.05,
    },
    roleExtras = {
        TANK = {
            ITEM_MOD_STAMINA_SHORT = 2.00,
            STATVERDICT_ARMOR = 3.00,
        },
    },
    softCap = {
        nearRatio = 0.90,
        nearPenalty = 0.85,
        overPenalty = 0.55,
    },
    delta = {
        -- Calibration layer for stat swaps.
        -- Gaining a lower-priority stat should not fully cancel losing a higher-priority stat.
        gain = {
            primary = 0.85,
            secondary = { 1.00, 0.90, 0.80, 0.70 },
            fallbackSecondary = 0.65,
        },
        loss = {
            primary = 1.05,
            secondary = { 1.50, 1.30, 1.15, 1.00 },
            fallbackSecondary = 1.00,
        },
    },
    percent = {
        -- Display layer now reports Item Value %, not pseudo-DPS %.
        -- Formula: weighted delta / equipped weighted score * 100.
        maxDisplayPercent = 99.99,
    },
}

local function GetPlayerLevel()
    if type(UnitLevel) ~= "function" then return nil end
    return tonumber(UnitLevel("player"))
end

local function GetMaxLevel()
    if type(GetMaxPlayerLevel) == "function" then
        local level = tonumber(GetMaxPlayerLevel())
        if level and level > 0 then return level end
    end
    if type(GetMaxLevelForPlayerExpansion) == "function" then
        local level = tonumber(GetMaxLevelForPlayerExpansion())
        if level and level > 0 then return level end
    end
    return 90
end

local function IsLevelingCharacter()
    local level = GetPlayerLevel()
    if not level then return false end
    local maxLevel = GetMaxLevel()
    return maxLevel and level < maxLevel
end

local function GetRawItemLevelWeight()
    local model = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.itemLevel or nil
    local base = tonumber(model and model.maxLevelWeight) or 1.20
    -- Below max level: modest extra weight on item level; cancelled at max.
    if IsLevelingCharacter() then
        return base * 1.25
    end
    return base
end


local TARGET_ROWS_BY_PROFILE = {
    DRUID_BALANCE = {
        -- Wowhead Balance priority. BiS-total numeric targets remain intentionally unset until
        -- the full slot-by-slot item stat audit is entered. Do not use generic 31k/14k values.
        { key = "ITEM_MOD_INTELLECT_SHORT", priority = 1 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", priority = 2 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", priority = 3 },
        { key = "ITEM_MOD_VERSATILITY", priority = 4 },
    },
    DRUID_BALANCE_ELUNES_CHOSEN = {
        { key = "ITEM_MOD_INTELLECT_SHORT", priority = 1 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", priority = 2 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", priority = 4 },
        { key = "ITEM_MOD_VERSATILITY", priority = 5 },
    },
    DRUID_FERAL = {
        -- Wowhead Feral Druid of the Claw priority. Numeric targets are pending verified BiS totals.
        { key = "ITEM_MOD_AGILITY_SHORT", priority = 1 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", priority = 2 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", priority = 4 },
        { key = "ITEM_MOD_VERSATILITY", priority = 5 },
    },
    DRUID_FERAL_WILDSTALKER = {
        { key = "ITEM_MOD_AGILITY_SHORT", priority = 1 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", priority = 2 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", priority = 3 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", priority = 4 },
        { key = "ITEM_MOD_VERSATILITY", priority = 5 },
    },
    DRUID_GUARDIAN = {
        -- Guardian top-cohort medians (non-normalized, Armory-derived).
        { key = "ITEM_MOD_AGILITY_SHORT", target = 1862, priority = 1 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 1126, priority = 2 },
        { key = "ITEM_MOD_VERSATILITY", target = 618, priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 410, priority = 4 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 381, priority = 5 },
        { key = "ITEM_MOD_STAMINA_SHORT", target = 23939, priority = 6 },
        { key = "STATVERDICT_ARMOR", target = 917, priority = 7 },
    },
    DRUID_RESTORATION = {
        -- Wowhead Restoration priority. Numeric targets are pending verified BiS totals.
        { key = "ITEM_MOD_INTELLECT_SHORT", priority = 1 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", priority = 2 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", priority = 3 },
        { key = "ITEM_MOD_VERSATILITY", priority = 4 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", priority = 5 },
    },
    PALADIN_HOLY = {
        { key = "ITEM_MOD_INTELLECT_SHORT", target = 31500, priority = 1 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 14100, priority = 2 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 12400, priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 9200, priority = 4 },
        { key = "ITEM_MOD_VERSATILITY", target = 5600, priority = 5 },
    },
    PALADIN_PROTECTION = {
        { key = "STATVERDICT_MAIN_HAND_DPS", target = 11800, priority = 1 },
        { key = "ITEM_MOD_STRENGTH_SHORT", target = 31500, priority = 2 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 12400, priority = 3 },
        { key = "ITEM_MOD_VERSATILITY", target = 9200, priority = 4 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 7600, priority = 5 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 5600, priority = 6 },
        { key = "ITEM_MOD_STAMINA_SHORT", target = 68000, priority = 7 },
        { key = "STATVERDICT_ARMOR", target = 18000, priority = 8 },
    },
    PALADIN_RETRIBUTION = {
        { key = "STATVERDICT_MAIN_HAND_DPS", target = 11800, priority = 1 },
        { key = "ITEM_MOD_STRENGTH_SHORT", target = 31500, priority = 2 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 14100, priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 9200, priority = 4 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 7600, priority = 5 },
        { key = "ITEM_MOD_VERSATILITY", target = 5600, priority = 6 },
    },
    SHAMAN_ELEMENTAL = {
        { key = "ITEM_MOD_INTELLECT_SHORT", target = 31500, priority = 1 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 14100, priority = 2 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 12400, priority = 3 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 9200, priority = 4 },
        { key = "ITEM_MOD_VERSATILITY", target = 5600, priority = 5 },
    },
    SHAMAN_ENHANCEMENT = {
        { key = "STATVERDICT_MAIN_HAND_DPS", target = 11800, priority = 1 },
        { key = "STATVERDICT_OFF_HAND_DPS", target = 11800, priority = 2 },
        { key = "ITEM_MOD_AGILITY_SHORT", target = 31500, priority = 3 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 14100, priority = 4 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 12400, priority = 5 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 9200, priority = 6 },
        { key = "ITEM_MOD_VERSATILITY", target = 5600, priority = 7 },
    },
    SHAMAN_RESTORATION = {
        { key = "ITEM_MOD_INTELLECT_SHORT", target = 31500, priority = 1 },
        { key = "ITEM_MOD_CRIT_RATING_SHORT", target = 12400, priority = 2 },
        { key = "ITEM_MOD_MASTERY_RATING_SHORT", target = 9200, priority = 3 },
        { key = "ITEM_MOD_VERSATILITY", target = 7600, priority = 4 },
        { key = "ITEM_MOD_HASTE_RATING_SHORT", target = 5600, priority = 5 },
    },
}

local TARGET_PROFILE_ALIASES = {
    DRUID_BALANCE_KEEPER_OF_THE_GROVE = "DRUID_BALANCE",
    DRUID_BALANCE_ELUNES_CHOSEN = "DRUID_BALANCE_ELUNES_CHOSEN",
    DRUID_FERAL_DOTC = "DRUID_FERAL",
    DRUID_FERAL_WILDSTALKER = "DRUID_FERAL_WILDSTALKER",
    DRUID_GUARDIAN_DOTC = "DRUID_GUARDIAN",
    DRUID_GUARDIAN_ELUNES_CHOSEN = "DRUID_GUARDIAN",
    DRUID_RESTORATION_KEEPER_OF_THE_GROVE = "DRUID_RESTORATION",
    DRUID_RESTORATION_WILDSTALKER = "DRUID_RESTORATION",
}

local TARGET_PROFILE_ID_BY_SPEC_ID = {
    [102] = "DRUID_BALANCE",
    [103] = "DRUID_FERAL",
    [104] = "DRUID_GUARDIAN",
    [105] = "DRUID_RESTORATION",
    [65] = "PALADIN_HOLY",
    [66] = "PALADIN_PROTECTION",
    [70] = "PALADIN_RETRIBUTION",
    [262] = "SHAMAN_ELEMENTAL",
    [263] = "SHAMAN_ENHANCEMENT",
    [264] = "SHAMAN_RESTORATION",
}

local PRIMARY_STAT_INDEX_BY_KEY = {
    ITEM_MOD_STRENGTH_SHORT = 1,
    ITEM_MOD_AGILITY_SHORT = 2,
    ITEM_MOD_STAMINA_SHORT = 3,
    ITEM_MOD_INTELLECT_SHORT = 4,
}

local RATING_ID_BY_TARGET_KEY = {
    ITEM_MOD_CRIT_RATING_SHORT = function()
        return CR_CRIT_MELEE or CR_CRIT_SPELL or CR_CRIT_RANGED
    end,
    ITEM_MOD_HASTE_RATING_SHORT = function()
        return CR_HASTE_MELEE or CR_HASTE_SPELL or CR_HASTE_RANGED or CR_HASTE
    end,
    ITEM_MOD_MASTERY_RATING_SHORT = function()
        return CR_MASTERY
    end,
    ITEM_MOD_VERSATILITY = function()
        return CR_VERSATILITY_DAMAGE_DONE or CR_VERSATILITY_DAMAGE_TAKEN
    end,
    ITEM_MOD_AVOIDANCE_RATING_SHORT = function()
        return CR_AVOIDANCE
    end,
    ITEM_MOD_LIFESTEAL = function()
        return CR_LIFESTEAL
    end,
    ITEM_MOD_SPEED = function()
        return CR_SPEED
    end,
    ITEM_MOD_SPEED_SHORT = function()
        return CR_SPEED
    end,
}

local function Clamp(value, minimum, maximum)
    if value < minimum then
        return minimum
    elseif value > maximum then
        return maximum
    end
    return value
end

local function SafePlainNumber(value)
    local sanitizer = ns.SanitizeStatVerdictNumber
    if type(sanitizer) == "function" then
        return sanitizer(value)
    end
    local ok, plain = pcall(function()
        local n = tonumber(value)
        if n == nil then return nil end
        return n + 0
    end)
    if ok and type(plain) == "number" then
        return plain
    end
    return nil
end

local function IsInCombat()
    return type(InCombatLockdown) == "function" and InCombatLockdown()
end

local function ResolveTargetProfileID(profile)
    if type(profile) ~= "table" then
        return nil
    end

    local profileID = profile.id
    if type(profileID) == "string" then
        profileID = TARGET_PROFILE_ALIASES[profileID] or profileID
        if TARGET_ROWS_BY_PROFILE[profileID] then
            return profileID
        end
    end

    local specID = profile.specID
    local resolvedID = specID and TARGET_PROFILE_ID_BY_SPEC_ID[specID]
    if resolvedID and TARGET_ROWS_BY_PROFILE[resolvedID] then
        return resolvedID
    end

    return nil
end

function ns.GetStatVerdictTargetRows(profile)
    if type(profile) == "table" and type(profile.auditTargets) == "table" and type(profile.auditTargets.rows) == "table" then
        return profile.auditTargets.rows, (type(profile.id) == "string" and profile.id or "PROFILE_AUDIT_TARGETS")
    end
    local profileID = ResolveTargetProfileID(profile)
    return profileID and TARGET_ROWS_BY_PROFILE[profileID] or nil, profileID
end

local function GetTargetRow(profile, statKey)
    local rows = ns.GetStatVerdictTargetRows and ns.GetStatVerdictTargetRows(profile) or nil
    if type(rows) ~= "table" then
        return nil
    end
    for _, row in ipairs(rows) do
        if row.key == statKey then
            return row
        end
    end
    return nil
end

function ns.GetStatSoftCap(profile, statKey)
    if type(profile) ~= "table" or not statKey then
        return nil
    end
    local capInfo = profile.caps and profile.caps[statKey]
    local softCap = capInfo and tonumber(capInfo.soft)
    if softCap and softCap > 0 then
        return softCap
    end
    return nil
end

local function GetCurrentPrimaryStat(statKey)
    local cached = IsInCombat() and ns.GetCachedAuditStatValue and ns.GetCachedAuditStatValue(statKey) or nil
    if cached ~= nil then return cached end
    local statIndex = PRIMARY_STAT_INDEX_BY_KEY[statKey]
    if not statIndex or type(UnitStat) ~= "function" or IsInCombat() then
        return nil
    end
    local ok, base, effective = pcall(UnitStat, "player", statIndex)
    if not ok then return nil end
    return SafePlainNumber(effective) or SafePlainNumber(base)
end

local function GetCurrentRatingStat(statKey)
    local cached = ns.GetCachedCurrentStatRating and ns.GetCachedCurrentStatRating(statKey) or nil
    if IsInCombat() then return cached end
    if type(GetCombatRating) ~= "function" then
        return cached
    end
    local getter = RATING_ID_BY_TARGET_KEY[statKey]
    local ratingID = getter and getter()
    if not ratingID then
        return cached
    end
    local ok, value = pcall(GetCombatRating, ratingID)
    if not ok then return cached end
    return SafePlainNumber(value) or cached
end

local function GetCurrentWeaponDPS(isOffHand)
    if type(UnitDamage) ~= "function" or type(UnitAttackSpeed) ~= "function" then
        return nil
    end

    if IsInCombat() then return nil end
    local okDamage, mainLow, mainHigh, offLow, offHigh = pcall(UnitDamage, "player")
    if not okDamage then return nil end
    local okSpeed, mainSpeed, offSpeed = pcall(UnitAttackSpeed, "player")
    if not okSpeed then return nil end
    local low, high, speed
    if isOffHand then
        low, high, speed = tonumber(offLow), tonumber(offHigh), tonumber(offSpeed)
    else
        low, high, speed = tonumber(mainLow), tonumber(mainHigh), tonumber(mainSpeed)
    end
    if low and high and speed and speed > 0 then
        return ((low + high) / 2) / speed
    end
    return nil
end

local function GetCurrentTargetStatValue(statKey, profile)
    local snapshotValue = ns.GetSnapshotStatValue and ns.GetSnapshotStatValue(profile, statKey) or nil
    if snapshotValue ~= nil then
        return snapshotValue
    end
    if statKey == "STATVERDICT_MAIN_HAND_DPS" then
        return GetCurrentWeaponDPS(false)
    elseif statKey == "STATVERDICT_OFF_HAND_DPS" then
        return GetCurrentWeaponDPS(true)
    elseif statKey == "STATVERDICT_ARMOR" then
        local cached = IsInCombat() and ns.GetCachedAuditStatValue and ns.GetCachedAuditStatValue(statKey) or nil
        if cached ~= nil then return cached end
        if type(UnitArmor) == "function" and not IsInCombat() then
            local ok, base, effective = pcall(UnitArmor, "player")
            if ok then return SafePlainNumber(effective) or SafePlainNumber(base) end
        end
        return nil
    end
    local value = GetCurrentPrimaryStat(statKey) or GetCurrentRatingStat(statKey)
    return SafePlainNumber(value)
end

local function HasHigherPriorityGaps(profile, priority)
    if not priority then
        return false
    end
    local rows = ns.GetStatVerdictTargetRows and ns.GetStatVerdictTargetRows(profile) or nil
    if type(rows) ~= "table" then
        return false
    end
    for _, row in ipairs(rows) do
        if row.priority and row.priority < priority then
            local current = SafePlainNumber(GetCurrentTargetStatValue(row.key, profile))
            local target = SafePlainNumber(row.target)
            if current and target and target > 0 and (current / target) < ns.GlobalStatVerdictModifiers.dynamicTarget.lowPriorityThrottleRatio then
                return true
            end
        end
    end
    return false
end

local function GetTargetGapUrgency(baseWeight, row)
    if not baseWeight or not row then
        return 0
    end

    local target = SafePlainNumber(row.target)
    local current = SafePlainNumber(GetCurrentTargetStatValue(row.key, profile))
    if not target or target <= 0 or not current then
        return 0
    end

    local gapRatio = math.max(0, (target - current) / target)
    local priority = tonumber(row.priority) or 99
    local priorityPressure = 1 / math.max(priority, 1)
    return gapRatio * math.max(baseWeight, 0) * (0.70 + priorityPressure)
end

local function GetProfileMaxGapUrgency(profile)
    local rows = ns.GetStatVerdictTargetRows and ns.GetStatVerdictTargetRows(profile) or nil
    if type(rows) ~= "table" then
        return 0
    end

    local maxUrgency = 0
    for _, row in ipairs(rows) do
        local baseWeight = ns.GetStatWeight and ns.GetStatWeight(profile, row.key) or nil
        if baseWeight and baseWeight > 0 then
            maxUrgency = math.max(maxUrgency, GetTargetGapUrgency(baseWeight, row))
        end
    end
    return maxUrgency
end


local GetSecondaryRankForDelta

local JEWELRY_EQUIP_LOCATIONS = {
    INVTYPE_NECK = true,
    INVTYPE_FINGER = true,
}

function ns.GetSlotContextAdjustedWeight(profile, statKey, baseWeight, equipLocation)
    baseWeight = tonumber(baseWeight)
    if not baseWeight or baseWeight == 0 then
        return baseWeight or 0
    end

    local model = ns.GlobalStatVerdictModifiers
    local jewelry = model and model.jewelry
    if not jewelry or not jewelry.enabled or not JEWELRY_EQUIP_LOCATIONS[equipLocation] then
        return baseWeight
    end

    local rank = GetSecondaryRankForDelta(profile, statKey)
    if not rank then
        return baseWeight
    end

    local primary = tonumber(model.primary) or 1
    if rank == 1 then
        return math.max(baseWeight, primary * (tonumber(jewelry.topSecondaryAsPrimary) or 0.90))
    elseif rank == 2 then
        return math.max(baseWeight, primary * (tonumber(jewelry.secondSecondaryAsPrimary) or 0.78))
    elseif rank == 3 then
        return math.max(baseWeight, primary * (tonumber(jewelry.thirdSecondaryAsPrimary) or 0.68))
    end

    return baseWeight * (tonumber(jewelry.otherSecondaryBoost) or 1.05)
end

local function GetDynamicBudgetAllocation(profile)
    local config = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.dynamicTarget
    if not config or not config.enabled then
        return nil
    end

    if type(profile) ~= "table" then
        return nil
    end

    local targetRows = ns.GetStatVerdictTargetRows and ns.GetStatVerdictTargetRows(profile) or nil
    local targetByKey = {}
    if type(targetRows) == "table" then
        for _, row in ipairs(targetRows) do
            if row and row.key then
                targetByKey[row.key] = row
            end
        end
    end

    local function ResolveBaseWeight(statKey)
        local base = ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil
        base = tonumber(base) or 0
        if base > 0 then
            return base
        end
        local row = targetByKey[statKey]
        local rowBase = tonumber(row and row.baseModifier) or 0
        if rowBase > 0 then
            return rowBase
        end
        local overrideBase = tonumber(profile and profile.modifierOverrides and profile.modifierOverrides[statKey]) or 0
        if overrideBase > 0 then
            return overrideBase
        end
        return 0
    end

    local activeKeys = {}
    local seen = {}
    local function addKey(statKey)
        if not statKey or seen[statKey] then return end
        local base = ResolveBaseWeight(statKey)
        if base <= 0 then return end
        seen[statKey] = true
        activeKeys[#activeKeys + 1] = statKey
    end

    addKey(profile.primaryStat)
    if type(profile.secondaryOrder) == "table" then
        for _, statKey in ipairs(profile.secondaryOrder) do
            addKey(statKey)
        end
    end
    if type(profile.extraWeights) == "table" then
        for statKey, weight in pairs(profile.extraWeights) do
            if (tonumber(weight) or 0) > 0 then
                addKey(statKey)
            end
        end
    end
    local roleExtras = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.roleExtras and profile.role and ns.GlobalStatVerdictModifiers.roleExtras[profile.role]
    if type(roleExtras) == "table" then
        for statKey, weight in pairs(roleExtras) do
            if (tonumber(weight) or 0) > 0 then
                addKey(statKey)
            end
        end
    end
    for statKey in pairs(targetByKey) do
        addKey(statKey)
    end

    if #activeKeys == 0 then
        return nil
    end

    local totalBase = 0
    local totalScore = 0
    local scored = {}

    local function getTier(statKey, row)
        if statKey == profile.primaryStat then
            return "A"
        end
        local p = tonumber(row and row.priority) or 99
        if p >= 2 and p <= (1 + (tonumber(config.topSecondaryLimit) or 2)) then
            return "A"
        end
        local t = string.upper(tostring(row and row.type or ""))
        if t == "SECONDARY" then
            return "B"
        end
        return "C"
    end

    for _, statKey in ipairs(activeKeys) do
        local base = ResolveBaseWeight(statKey)
        if base > 0 then
            local effectiveBase = ns.GetSoftCapAdjustedWeight and ns.GetSoftCapAdjustedWeight(profile, statKey, base) or base
            effectiveBase = tonumber(effectiveBase) or base

            local row = targetByKey[statKey]
            local target = SafePlainNumber(row and row.target) or 0
            local current = SafePlainNumber(GetCurrentTargetStatValue(statKey, profile))
            local gapRatio = 0
            if target > 0 and current then
                gapRatio = (target - current) / target
            end

            local tier = getTier(statKey, row)
            local boostMax = (tier == "A" and (tonumber(config.tierABoost) or 0.30))
                or (tier == "B" and (tonumber(config.tierBBoost) or 0.18))
                or (tonumber(config.tierCBoost) or 0.10)
            local penaltyMax = (tier == "A" and (tonumber(config.tierAPenalty) or 0.20))
                or (tier == "B" and (tonumber(config.tierBPenalty) or 0.65))
                or (tonumber(config.tierCPenalty) or 0.80)
            local floorRatio = (tier == "A" and (tonumber(config.tierAFloor) or 0.92))
                or (tier == "B" and (tonumber(config.tierBFloor) or 0.45))
                or (tonumber(config.tierCFloor) or 0.25)
            local score = effectiveBase

            -- Objective: close deficits on high-tier stats first.
            if gapRatio > 0 then
                local deficitPressure = Clamp(gapRatio / (config.maxPositiveGap or 0.60), 0, 1)
                score = effectiveBase * (1 + (boostMax * deficitPressure))
            elseif gapRatio < 0 then
                local overPressure = Clamp(math.abs(gapRatio) / (config.maxNegativeGap or 0.30), 0, 1)
                local basePenalty = penaltyMax * overPressure
                local extraPenalty = 0
                if overPressure > 0.65 then
                    extraPenalty = (overPressure - 0.65) / 0.35 * (penaltyMax * 0.35)
                end
                local totalPenalty = Clamp(basePenalty + extraPenalty, 0, penaltyMax + (penaltyMax * 0.35))
                score = effectiveBase * (1 - totalPenalty)
            else
                score = effectiveBase
            end

            -- Tier floors keep top-priority stats from collapsing.
            local floorValue = effectiveBase * floorRatio
            score = math.max(score, floorValue, 0.10)
            -- Keep live reallocation on the full normalized budget (raw base),
            -- not on already-penalized subtotal, so live sum remains consistent.
            totalBase = totalBase + base
            totalScore = totalScore + score
            scored[statKey] = {
                base = effectiveBase,
                baseRaw = base,
                score = score,
                tier = tier,
            }
        end
    end

    if totalBase <= 0 or totalScore <= 0 then
        return nil
    end

    local allocation = {}
    local tierCBudget = 0
    local nonCTotalBase = 0
    local nonCTotalScore = 0

    for key, info in pairs(scored) do
        if info.tier == "C" then
            -- Preserve minor penalties directly so they do not get washed out by global normalization.
            allocation[key] = info.score
            tierCBudget = tierCBudget + info.score
        else
            nonCTotalBase = nonCTotalBase + info.baseRaw
            nonCTotalScore = nonCTotalScore + info.score
        end
    end

    local remainingBudget = totalBase - tierCBudget
    if remainingBudget < 0 then
        remainingBudget = 0
    end

    local nonCScale = 1
    if nonCTotalScore > 0 then
        nonCScale = remainingBudget / nonCTotalScore
    end

    for key, info in pairs(scored) do
        if info.tier ~= "C" then
            allocation[key] = info.score * nonCScale
        end
    end

    return allocation
end

function ns.GetDynamicStatWeight(profile, statKey, baseWeight)
    baseWeight = tonumber(baseWeight)
    if not baseWeight or baseWeight == 0 then
        return baseWeight or 0
    end

    local allocation = GetDynamicBudgetAllocation(profile)
    if type(allocation) ~= "table" or allocation[statKey] == nil then
        return baseWeight
    end

    local baseAllocation = ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil
    baseAllocation = tonumber(baseAllocation)
    if not baseAllocation or baseAllocation <= 0 then
        -- Profile-driven rows may not exist in core stat table; use current baseWeight as anchor.
        baseAllocation = baseWeight
    end

    local adjusted = baseWeight * (allocation[statKey] / baseAllocation)
    if statKey == profile.primaryStat and adjusted < baseWeight then
        return baseWeight
    end
    return adjusted
end


local function GetTargetSecondaryRank(profile, statKey)
    local rows = ns.GetStatVerdictTargetRows and ns.GetStatVerdictTargetRows(profile) or nil
    if type(rows) ~= "table" then return nil end

    local ordered = {}
    for index, row in ipairs(rows) do
        if row and string.upper(tostring(row.type or "")) == "SECONDARY" and row.key then
            ordered[#ordered + 1] = {
                key = row.key,
                priority = tonumber(row.priority) or index,
                index = index,
            }
        end
    end
    table.sort(ordered, function(a, b)
        if a.priority == b.priority then return a.index < b.index end
        return a.priority < b.priority
    end)
    for index, row in ipairs(ordered) do
        if row.key == statKey then return index end
    end
    return nil
end

local function GetSecondaryRank(profile, statKey)
    local targetRank = GetTargetSecondaryRank(profile, statKey)
    if targetRank then return targetRank end
    if type(profile) ~= "table" or type(profile.secondaryOrder) ~= "table" then
        return nil
    end

    for index, key in ipairs(profile.secondaryOrder) do
        if key == statKey then
            return index
        end
    end

    return nil
end

local function GetEqualGroupTopRank(profile, rank)
    if not rank or type(profile) ~= "table" or type(profile.equalGroups) ~= "table" then
        return rank
    end

    for _, group in ipairs(profile.equalGroups) do
        local matched = false
        local topRank = rank
        for _, groupRank in ipairs(group) do
            if groupRank == rank then
                matched = true
            end
            if type(groupRank) == "number" and groupRank < topRank then
                topRank = groupRank
            end
        end
        if matched then
            return topRank
        end
    end

    return rank
end

local function GetRawDefaultStatWeight(profile, statKey)
    if not profile or not statKey then
        return nil
    end

    local model = ns.GlobalStatVerdictModifiers

    if statKey == "STATVERDICT_ITEM_LEVEL" then
        return GetRawItemLevelWeight()
    end

    if statKey == profile.primaryStat then
        return model.primary
    end

    local rank = GetSecondaryRank(profile, statKey)
    if rank then
        rank = GetEqualGroupTopRank(profile, rank)
        return model.secondary[rank] or model.fallbackSecondary
    end

    local roleExtras = model.roleExtras and profile and profile.role and model.roleExtras[profile.role]
    if roleExtras and roleExtras[statKey] ~= nil then
        return tonumber(roleExtras[statKey]) or 0
    end
    local explicitExtra = type(profile.extraWeights) == "table" and profile.extraWeights[statKey] ~= nil
    local targetExtra = GetTargetRow(profile, statKey) ~= nil
    if model.extras and model.extras[statKey] ~= nil and (explicitExtra or targetExtra) then
        return tonumber(model.extras[statKey]) or 0
    end

    return nil
end

local function IsBudgetedProfileStat(profile, statKey)
    if not profile or not statKey then
        return false
    end

    -- Item level is a synthetic stat, but it still consumes the same point budget.
    if statKey == "STATVERDICT_ITEM_LEVEL" then
        return true
    end

    -- Always budget the profile's primary stat.
    if profile.primaryStat and statKey == profile.primaryStat then
        return true
    end

    -- Always budget secondary stats that are explicitly ordered for the spec.
    if type(profile.secondaryOrder) == "table" then
        for _, orderedKey in ipairs(profile.secondaryOrder) do
            if orderedKey == statKey then
                return true
            end
        end
    end

    -- Budget any explicit profile extra weight that is positive.
    if type(profile.extraWeights) == "table" and profile.extraWeights[statKey] ~= nil then
        local v = tonumber(profile.extraWeights[statKey]) or 0
        if v > 0 then
            return true
        end
    end

    -- Role-specific extras, such as tank armor, are part of the same budget too.
    local roleExtras = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.roleExtras and profile.role and ns.GlobalStatVerdictModifiers.roleExtras[profile.role]
    if type(roleExtras) == "table" and roleExtras[statKey] ~= nil then
        return true
    end

    if type(profile.modifierOverrides) == "table" and profile.modifierOverrides[statKey] ~= nil then
        return true
    end

    return false
end

local function AddBudgetRawTotal(profile, statKey, included, state)
    if not statKey or included[statKey] then
        return
    end
    if not IsBudgetedProfileStat(profile, statKey) then
        return
    end

    local raw = tonumber(GetRawDefaultStatWeight(profile, statKey)) or 0
    if raw <= 0 then
        return
    end

    included[statKey] = true
    state.rawTotal = state.rawTotal + raw
end

local function GetProfileBudgetScale(profile)
    if type(profile) ~= "table" then
        return 1
    end
    local included = {}
    local state = { rawTotal = 0 }

    -- Synthetic item level participates in the same budget as profile stats.
    AddBudgetRawTotal(profile, "STATVERDICT_ITEM_LEVEL", included, state)

    -- Always start from canonical profile definition.
    AddBudgetRawTotal(profile, profile.primaryStat, included, state)
    if type(profile.secondaryOrder) == "table" then
        for _, statKey in ipairs(profile.secondaryOrder) do
            AddBudgetRawTotal(profile, statKey, included, state)
        end
    end

    -- Include rows if present (deduped by key).
    local rows = ns.GetStatVerdictTargetRows and ns.GetStatVerdictTargetRows(profile) or nil
    if type(rows) == "table" then
        for _, row in ipairs(rows) do
            AddBudgetRawTotal(profile, row.key, included, state)
        end
    end

    -- Include explicit extras configured on profile.
    if type(profile.extraWeights) == "table" then
        for statKey, weight in pairs(profile.extraWeights) do
            if (tonumber(weight) or 0) > 0 then
                AddBudgetRawTotal(profile, statKey, included, state)
            end
        end
    end

    -- Include stamina only when explicitly relevant for the profile.
    if included["ITEM_MOD_STAMINA_SHORT"] == nil then
        if profile.primaryStat == "ITEM_MOD_STAMINA_SHORT" then
            AddBudgetRawTotal(profile, "ITEM_MOD_STAMINA_SHORT", included, state)
        elseif type(profile.extraWeights) == "table" and (tonumber(profile.extraWeights["ITEM_MOD_STAMINA_SHORT"]) or 0) > 0 then
            AddBudgetRawTotal(profile, "ITEM_MOD_STAMINA_SHORT", included, state)
        end
    end

    -- Role-specific extras, such as tank armor, are part of the same budget pool.
    local roleExtras = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.roleExtras and profile and profile.role and ns.GlobalStatVerdictModifiers.roleExtras[profile.role]
    if type(roleExtras) == "table" then
        for statKey in pairs(roleExtras) do
            AddBudgetRawTotal(profile, statKey, included, state)
        end
    end

    if type(profile) == "table" and type(profile.modifierOverrides) == "table" then
        for statKey in pairs(profile.modifierOverrides) do
            AddBudgetRawTotal(profile, statKey, included, state)
        end
    end

    local budget = tonumber(ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.pointBudget) or 20
    if state.rawTotal <= 0 then
        return 1
    end

    return budget / state.rawTotal
end

local function GetBudgetedDefaultStatWeight(profile, statKey)
    local raw = GetRawDefaultStatWeight(profile, statKey)
    if raw == nil then
        return nil
    end

    if IsBudgetedProfileStat(profile, statKey) then
        return raw * GetProfileBudgetScale(profile)
    end

    return raw
end

local function GetExtraWeight(profile, statKey)
    if statKey == "STATVERDICT_MAIN_HAND_DPS" or statKey == "STATVERDICT_OFF_HAND_DPS" then
        if not GetTargetRow(profile, statKey) then
            return nil
        end
    end

    return GetBudgetedDefaultStatWeight(profile, statKey)
end



GetSecondaryRankForDelta = function(profile, statKey)
    return GetEqualGroupTopRank(profile, GetSecondaryRank(profile, statKey))
end

local function GetDeltaPriorityMultiplier(profile, statKey, delta)
    local model = ns.GlobalStatVerdictModifiers
    local deltaModel = model and model.delta
    if not deltaModel or not statKey or not delta or delta == 0 then
        return 1
    end

    local profileTable = type(profile) == "table" and profile or nil
    local hasGeneratedPriority = GetTargetSecondaryRank(profileTable, statKey) ~= nil
    local overrides = not hasGeneratedPriority and (delta > 0 and profileTable and profileTable.deltaGainMultipliers or profileTable and profileTable.deltaLossMultipliers) or nil
    if type(overrides) == "table" and overrides[statKey] ~= nil then
        local override = tonumber(overrides[statKey]) or 1
        if profileTable and statKey == profileTable.primaryStat and delta > 0 and override < 1 then
            return 1
        end
        return override
    end

    local direction = delta > 0 and deltaModel.gain or deltaModel.loss
    if type(direction) ~= "table" then
        return 1
    end

    if profileTable and statKey == profileTable.primaryStat then
        local primaryMultiplier = tonumber(direction.primary) or 1
        if delta > 0 and primaryMultiplier < 1 then
            return 1
        end
        return primaryMultiplier
    end

    local rank = GetSecondaryRankForDelta(profileTable, statKey)
    if rank and type(direction.secondary) == "table" then
        return tonumber(direction.secondary[rank]) or tonumber(direction.fallbackSecondary) or 1
    end

    return 1
end

function ns.GetDefaultStatWeight(profile, statKey)
    return GetBudgetedDefaultStatWeight(profile, statKey)
end


function ns.GetStatWeight(profile, statKey)
    if not profile or not statKey then
        return nil
    end

    if type(profile.modifierOverrides) == "table" and profile.modifierOverrides[statKey] ~= nil then
        return tonumber(profile.modifierOverrides[statKey]) or 0
    end

    return ns.GetDefaultStatWeight(profile, statKey)
end

function ns.GetSoftCapAdjustedWeight(profile, statKey, baseWeight)
    if not profile or not statKey or not baseWeight then
        return baseWeight or 0
    end
    if statKey == profile.primaryStat then
        return baseWeight
    end

    local capInfo = profile.caps and profile.caps[statKey]
    local softCap = capInfo and tonumber(capInfo.soft)
    if not softCap or softCap <= 0 then
        return baseWeight
    end

    local current = SafePlainNumber((ns.GetSnapshotStatValue and ns.GetSnapshotStatValue(profile, statKey)) or (ns.GetCurrentStatRating and ns.GetCurrentStatRating(statKey) or nil))
    if not current then
        return baseWeight
    end

    local model = ns.GlobalStatVerdictModifiers.softCap
    if current >= softCap then
        return baseWeight * model.overPenalty
    end
    if current >= (softCap * model.nearRatio) then
        return baseWeight * model.nearPenalty
    end

    return baseWeight
end


function ns.GetDeltaAdjustedStatWeight(profile, statKey, delta, baseWeight, equipLocation)
    local weight = baseWeight or (ns.GetStatWeight and ns.GetStatWeight(profile, statKey)) or 0
    if not weight or weight == 0 then
        return 0
    end

    weight = ns.GetSlotContextAdjustedWeight and ns.GetSlotContextAdjustedWeight(profile, statKey, weight, equipLocation) or weight
    weight = ns.GetDynamicStatWeight and ns.GetDynamicStatWeight(profile, statKey, weight) or weight
    return weight * GetDeltaPriorityMultiplier(profile, statKey, delta)
end
