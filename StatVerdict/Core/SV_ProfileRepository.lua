local addonName, ns = ...

local Repository = {}
ns.ProfileRepository = Repository

local SCHEMA_VERSION = 1
local VALID_GOALS = {
    MYTHIC_PLUS = true,
    RAID = true,
    PVP = true,
}
local DEFAULT_GOAL = "MYTHIC_PLUS"
local MIN_VALID_MAX_LEVEL_TARGET_ILVL = 250
local STAT_KEY = {
    agility = "ITEM_MOD_AGILITY_SHORT",
    intellect = "ITEM_MOD_INTELLECT_SHORT",
    strength = "ITEM_MOD_STRENGTH_SHORT",
    stamina = "ITEM_MOD_STAMINA_SHORT",
    ["critical-strike"] = "ITEM_MOD_CRIT_RATING_SHORT",
    critical_strike = "ITEM_MOD_CRIT_RATING_SHORT",
    haste = "ITEM_MOD_HASTE_RATING_SHORT",
    mastery = "ITEM_MOD_MASTERY_RATING_SHORT",
    versatility = "ITEM_MOD_VERSATILITY",
    avoidance = "ITEM_MOD_AVOIDANCE_RATING_SHORT",
    leech = "ITEM_MOD_LIFESTEAL",
    speed = "ITEM_MOD_SPEED",
    armor = "STATVERDICT_ARMOR",
}
local STAT_LABEL = {
    ITEM_MOD_AGILITY_SHORT = "Agility",
    ITEM_MOD_INTELLECT_SHORT = "Intellect",
    ITEM_MOD_STRENGTH_SHORT = "Strength",
    ITEM_MOD_STAMINA_SHORT = "Stamina",
    ITEM_MOD_CRIT_RATING_SHORT = "Critical Strike",
    ITEM_MOD_HASTE_RATING_SHORT = "Haste",
    ITEM_MOD_MASTERY_RATING_SHORT = "Mastery",
    ITEM_MOD_VERSATILITY = "Versatility",
    ITEM_MOD_AVOIDANCE_RATING_SHORT = "Avoidance",
    ITEM_MOD_LIFESTEAL = "Leech",
    ITEM_MOD_SPEED = "Speed",
    STATVERDICT_ARMOR = "Armor",
}

local function NormalizeToken(value)
    if type(value) ~= "string" then return "" end
    return value:lower():gsub("[^%a%d]+", "")
end

local MAX_GENERATED_AGE_DAYS = 30
local MAX_SCRAPE_AGE_DAYS = 120
local MIN_CONTEXT_ITEMS = 10
local MAX_LOW_ITEM_RATIO = 0.25

local function ParseUtcDate(value)
    if type(value) ~= "string" or type(time) ~= "function" then return nil end
    local year, month, day, hour, minute, second =
        value:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)T?(%d?%d?):?(%d?%d?):?(%d?%d?)")
    if not year then
        year, month, day = value:match("^(%d%d%d%d)%-(%d%d)%-(%d%d)$")
    end
    if not year then return nil end
    return time({
        year = tonumber(year),
        month = tonumber(month),
        day = tonumber(day),
        hour = tonumber(hour) or 0,
        min = tonumber(minute) or 0,
        sec = tonumber(second) or 0,
    })
end

local function IsRecentDate(value, maxAgeDays)
    local timestamp = ParseUtcDate(value)
    if not timestamp or type(time) ~= "function" then return false end
    local age = time() - timestamp
    return age >= -86400 and age <= (maxAgeDays * 86400)
end

local function GetRoot()
    local root = ns.GeneratedProfileData
    if type(root) ~= "table" or root.schemaVersion ~= SCHEMA_VERSION then
        return nil
    end
    local source = type(root.source) == "table" and root.source or nil
    if not IsRecentDate(root.generatedAt, MAX_GENERATED_AGE_DAYS)
        or not IsRecentDate(source and source.scrape, MAX_SCRAPE_AGE_DAYS)
    then
        return nil
    end
    return root
end

local MYTHIC_PLUS_SCHEMA_VERSION = 1

-- Mythic+ data comes from the live benchmark file (tools/addon_benchmarks.py),
-- one context per benchmark level. Other goals still use the bundled root.
local function GetMythicPlusRoot()
    local root = ns.MythicPlusBenchmarks
    if type(root) ~= "table" or root.schemaVersion ~= MYTHIC_PLUS_SCHEMA_VERSION then
        return nil
    end
    if not IsRecentDate(root.generatedAt, MAX_GENERATED_AGE_DAYS) then
        return nil
    end
    return root
end

local function GetGoalRoot(goal)
    if goal == "MYTHIC_PLUS" then return GetMythicPlusRoot() end
    return GetRoot()
end

local function GetContext(specKey, goal)
    if goal == "MYTHIC_PLUS" then
        local root = GetMythicPlusRoot()
        local profiles = root and root.profiles
        local profile = type(profiles) == "table" and profiles[specKey] or nil
        if type(profile) ~= "table" or type(profile.levels) ~= "table" then return nil, nil end
        local level = ns.GetBenchmarkLevel and ns.GetBenchmarkLevel() or "MID"
        local context = profile.levels[level]
        return type(context) == "table" and context or nil, profile
    end
    local root = GetRoot()
    local profiles = root and root.profiles
    local profile = type(profiles) == "table" and profiles[specKey] or nil
    local contexts = type(profile) == "table" and profile.contexts or nil
    if type(contexts) ~= "table" then return nil, profile end
    local context = contexts[goal]
    return type(context) == "table" and context or nil, profile
end

local function CountPositiveTargets(statTargets)
    local values = type(statTargets) == "table" and statTargets.stats or nil
    local count = 0
    for _, value in pairs(type(values) == "table" and values or {}) do
        if tonumber(value) and tonumber(value) > 0 then count = count + 1 end
    end
    return count
end

local function ValidateGeneratedContext(context, goal)
    local targets = type(context) == "table" and context.targets or nil
    if type(targets) ~= "table" then return false, "Profile targets are missing." end
    if targets.sourceGoal ~= nil and targets.sourceGoal ~= goal then
        return false, "Profile targets belong to a different goal."
    end
    if CountPositiveTargets(targets.statTargets) < 2 then
        return false, "Profile has too few usable stat targets."
    end

    local bis = type(context) == "table" and context.bis or nil
    local bisSlots = type(bis) == "table" and bis.slots or nil
    if type(bisSlots) ~= "table" or #bisSlots < MIN_CONTEXT_ITEMS then
        return false, "Profile has too few goal-specific reference items."
    end

    local itemCount = tonumber(targets.itemCount) or 0
    if goal == "PVP" then
        -- PvP currently has priorities and BiS references, but no resolved Murlok
        -- gear totals. A non-zero count is the legacy cross-goal PvE fallback.
        if itemCount ~= 0 or tonumber(targets.averageItemLevel) ~= nil then
            return false, "PvP targets contain cross-goal resolved gear data."
        end
        return true
    end

    local averageItemLevel = tonumber(type(targets) == "table" and targets.averageItemLevel or nil)
    if averageItemLevel == nil or averageItemLevel < MIN_VALID_MAX_LEVEL_TARGET_ILVL then
        return false, "Generated target item level is not valid for a max-level profile."
    end
    if itemCount < MIN_CONTEXT_ITEMS then
        return false, "Resolved target set is incomplete."
    end
    local metadata = type(targets.targetMetadata) == "table" and targets.targetMetadata or {}
    local lowItems = tonumber(metadata.lowItemReplacements) or 0
    if itemCount > 0 and (lowItems / itemCount) > MAX_LOW_ITEM_RATIO then
        return false, "Resolved target set contains too many low-level replacements."
    end
    return true
end

function Repository.GetDataProvenance(goal)
    if goal == "MYTHIC_PLUS" then
        local root = ns.MythicPlusBenchmarks
        local level = ns.GetBenchmarkLevelInfo and ns.GetBenchmarkLevelInfo(ns.GetBenchmarkLevel()) or nil
        local generatedAt = type(root) == "table" and root.generatedAt or nil
        return {
            available = GetMythicPlusRoot() ~= nil,
            generatedAt = generatedAt,
            scrape = type(generatedAt) == "string" and generatedAt:sub(1, 10) or nil,
            sourceName = "StatVerdict live benchmarks" .. (level and (" · " .. level.label) or ""),
        }
    end
    local root = ns.GeneratedProfileData
    local source = type(root) == "table" and root.source or nil
    return {
        available = GetRoot() ~= nil,
        generatedAt = type(root) == "table" and root.generatedAt or nil,
        scrape = type(source) == "table" and source.scrape or nil,
        sourceName = type(source) == "table" and source.name or nil,
    }
end

local function PriorityScore(row, heroTalentName, contextName, heroSubTreeID)
    if type(row) ~= "table" then return -1 end
    local score = 0
    local wantedHero = NormalizeToken(heroTalentName)
    local rowHero = NormalizeToken(row.heroTalent)
    if heroSubTreeID and row.heroSubTreeID ~= nil then
        if tonumber(row.heroSubTreeID) == tonumber(heroSubTreeID) then
            score = score + 4
        end
    elseif row.heroSubTreeID == nil and wantedHero ~= "" and rowHero == wantedHero then
        score = score + 4
    elseif row.heroSubTreeID == nil and (rowHero == "" or rowHero == "all") then
        score = score + 1
    end

    local wantedContext = NormalizeToken(contextName)
    local rowContext = NormalizeToken(row.context)
    if wantedContext ~= "" and rowContext == wantedContext then
        score = score + 3
    elseif rowContext == "general" then
        score = score + 1
    end
    return score
end

function Repository.GetContext(specKey, goal)
    if not VALID_GOALS[goal] then return nil end
    return GetContext(specKey, goal)
end

function Repository.GetPriority(specKey, goal, heroTalentName, heroSubTreeID)
    local context = Repository.GetContext(specKey, goal)
    local rows = type(context) == "table" and context.priorityProfiles or nil
    if type(rows) ~= "table" then return nil end

    local contextName = "General"
    if goal == "MYTHIC_PLUS" then
        contextName = "Mythic+"
    elseif goal == "RAID" then
        contextName = "Raid"
    elseif goal == "PVP" then
        contextName = "PvP"
    end
    local best, bestScore
    for _, row in ipairs(rows) do
        local score = PriorityScore(row, heroTalentName, contextName, heroSubTreeID)
        if bestScore == nil or score > bestScore then
            best = row
            bestScore = score
        end
    end
    return best
end

local function BuildSecondaryOrder(priority)
    local order = {}
    for _, canonicalKey in ipairs(type(priority) == "table" and priority.order or {}) do
        local statKey = STAT_KEY[canonicalKey]
        if statKey then
            order[#order + 1] = statKey
        end
    end
    return order
end

local function BuildSecondaryOrderFromTargets(targets, fallbackPriority)
    local priorityOrder = BuildSecondaryOrder(fallbackPriority)
    if #priorityOrder > 0 then
        return priorityOrder
    end

    local statTargets = type(targets) == "table" and targets.statTargets or nil
    local targetValues = type(statTargets) == "table" and statTargets.stats or nil
    local ranked = {}

    if type(targetValues) == "table" then
        for canonicalKey, value in pairs(targetValues) do
            local statKey = STAT_KEY[canonicalKey]
            local target = tonumber(value)
            if statKey and target and target > 0 then
                ranked[#ranked + 1] = {
                    key = statKey,
                    target = target,
                }
            end
        end
    end

    if #ranked > 0 then
        table.sort(ranked, function(a, b)
            if a.target ~= b.target then
                return a.target > b.target
            end
            return tostring(a.key) < tostring(b.key)
        end)

        local order = {}
        for _, row in ipairs(ranked) do
            order[#order + 1] = row.key
        end
        return order
    end

    return {}
end

local function BuildEqualGroups(priority, secondaryOrder)
    local indexByKey = {}
    for index, statKey in ipairs(secondaryOrder) do
        indexByKey[statKey] = index
    end

    local groups = {}
    for _, tier in ipairs(type(priority) == "table" and priority.tiers or {}) do
        local group = {}
        for _, canonicalKey in ipairs(tier) do
            local index = indexByKey[STAT_KEY[canonicalKey]]
            if index then group[#group + 1] = index end
        end
        if #group > 1 then groups[#groups + 1] = group end
    end
    return groups
end

local function BuildAuditTargets(targets, primaryStat, secondaryOrder)
    local statTargets = type(targets) == "table" and targets.statTargets or nil
    local targetValues = type(statTargets) == "table" and statTargets.stats or nil
    local model = ns.GlobalStatVerdictModifiers or {}
    local secondaryWeights = type(model.secondary) == "table" and model.secondary or {}
    local rows = {}
    local seen = {}

    local function add(statKey, statType, priority, baseModifier)
        if not statKey or seen[statKey] then return end
        seen[statKey] = true
        local canonicalValue
        for canonicalKey, runtimeKey in pairs(STAT_KEY) do
            if runtimeKey == statKey then
                if type(targetValues) == "table" and targetValues[canonicalKey] ~= nil then
                    canonicalValue = tonumber(targetValues[canonicalKey])
                end
                if canonicalValue ~= nil then
                    break
                end
            end
        end
        if canonicalValue == nil then return end
        rows[#rows + 1] = {
            key = statKey,
            label = STAT_LABEL[statKey] or statKey,
            type = statType,
            target = canonicalValue,
            priority = priority,
            baseModifier = tonumber(baseModifier),
        }
    end

    for index, statKey in ipairs(secondaryOrder) do
        add(statKey, "Secondary", index, tonumber(secondaryWeights[index]) or tonumber(model.fallbackSecondary) or 1)
    end

    return {
        source = "generated_classcodex",
        averageItemLevel = type(targets) == "table" and targets.averageItemLevel or nil,
        rows = rows,
    }
end

function Repository.BuildRuntimeProfile(context)
    if type(context) ~= "table" then return nil end
    local specKey = context.specKey
        or (ns.GetStatVerdictSpecKeyBySpecID and ns.GetStatVerdictSpecKeyBySpecID(context.specID))
    if not specKey then return nil end

    local goal = context.goal
        or (ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode())
        or DEFAULT_GOAL
    if not VALID_GOALS[goal] then goal = DEFAULT_GOAL end

    local generatedContext, generatedProfile = GetContext(specKey, goal)
    if type(generatedContext) ~= "table" or type(generatedProfile) ~= "table" then
        return nil
    end
    local validGeneratedContext, invalidReason = ValidateGeneratedContext(generatedContext, goal)
    local invalidGeneratedContext = not validGeneratedContext

    local heroTalentName = context.heroTalentName
        or (ns.GetSnapshotHeroTalentName and ns.GetSnapshotHeroTalentName(context))
    local heroSubTreeID = context.heroSubTreeID
        or (ns.GetSnapshotHeroSubTreeID and ns.GetSnapshotHeroSubTreeID(context))
    local priority = Repository.GetPriority(specKey, goal, heroTalentName, heroSubTreeID)
    local secondaryOrder = BuildSecondaryOrderFromTargets(generatedContext.targets, priority)
    local primaryStat = STAT_KEY[generatedProfile.primaryStat]
    local role = context.role
        or (ns.GetStatVerdictRoleBySpecID and ns.GetStatVerdictRoleBySpecID(context.specID))
    local hiddenTrackedStats = {
        STATVERDICT_ITEM_LEVEL = true,
        [primaryStat] = true,
    }
    local extraWeights = {}
    if primaryStat ~= "ITEM_MOD_INTELLECT_SHORT" then
        hiddenTrackedStats.STATVERDICT_MAIN_HAND_DPS = true
        hiddenTrackedStats.STATVERDICT_OFF_HAND_DPS = true
        extraWeights.STATVERDICT_MAIN_HAND_DPS = 1
        extraWeights.STATVERDICT_OFF_HAND_DPS = 1
    end
    if role == "TANK" then
        hiddenTrackedStats.ITEM_MOD_STAMINA_SHORT = true
        hiddenTrackedStats.STATVERDICT_ARMOR = true
    end
    local profileID = table.concat({
        tostring(goal),
        tostring(specKey),
    }, "_")

    return {
        id = profileID,
        profileKey = profileID,
        goal = goal,
        specKey = specKey,
        class = generatedProfile.classToken or context.classFile,
        className = context.className,
        specID = context.specID,
        specName = context.specName
            or (ns.GetStatVerdictSpecNameByKey and ns.GetStatVerdictSpecNameByKey(specKey)),
        role = role,
        providerKey = "Generated",
        providerLabel = "StatVerdict",
        source = "generated_classcodex",
        primaryStat = primaryStat,
        secondaryOrder = secondaryOrder,
        hiddenTrackedStats = hiddenTrackedStats,
        equalGroups = BuildEqualGroups(priority, secondaryOrder),
        caps = {},
        extraWeights = extraWeights,
        auditTargets = invalidGeneratedContext and {
            source = "invalid_generated_context",
            averageItemLevel = nil,
            rows = {},
            invalidReason = invalidReason or "Generated profile data failed quality checks.",
        } or BuildAuditTargets(generatedContext.targets, primaryStat, secondaryOrder),
        generatedContext = invalidGeneratedContext and nil or generatedContext,
        invalidGeneratedContext = invalidGeneratedContext,
    }
end

function Repository.BuildProviderView(goal)
    local root = GetGoalRoot(goal)
    local provider = {}
    if not root then return provider end

    for specKey, generatedProfile in pairs(root.profiles or {}) do
        local specID = ns.GetStatVerdictSpecIDByKey and ns.GetStatVerdictSpecIDByKey(specKey)
        local classToken = generatedProfile.classToken
        if specID and classToken then
            local defaultContext = {
                specKey = specKey,
                specID = specID,
                classFile = classToken,
                specName = ns.GetStatVerdictSpecNameByKey and ns.GetStatVerdictSpecNameByKey(specKey),
                role = ns.GetStatVerdictRoleBySpecID and ns.GetStatVerdictRoleBySpecID(specID),
                goal = goal,
            }
            local defaultProfile = Repository.BuildRuntimeProfile(defaultContext)
            provider[classToken] = provider[classToken] or {}
            provider[classToken][specID] = {
                default = defaultProfile,
                hero = {},
            }
        end
    end
    return provider
end

function Repository.GetProviderView(goal)
    goal = VALID_GOALS[goal] and goal or DEFAULT_GOAL
    ns.ProfileProviders = ns.ProfileProviders or {}
    ns.ProfileProviders.GeneratedByGoal = ns.ProfileProviders.GeneratedByGoal or {}
    if type(ns.ProfileProviders.GeneratedByGoal[goal]) ~= "table" then
        ns.ProfileProviders.GeneratedByGoal[goal] = Repository.BuildProviderView(goal)
    end
    return ns.ProfileProviders.GeneratedByGoal[goal]
end

function Repository.RefreshProviderView(goal)
    goal = VALID_GOALS[goal] and goal or DEFAULT_GOAL
    ns.ProfileProviders = ns.ProfileProviders or {}
    ns.ProfileProviders.GeneratedByGoal = ns.ProfileProviders.GeneratedByGoal or {}
    ns.ProfileProviders.GeneratedByGoal[goal] = Repository.BuildProviderView(goal)
    ns.ProfileProviders.Generated = ns.ProfileProviders.GeneratedByGoal[goal]
    return ns.ProfileProviders.GeneratedByGoal[goal]
end
