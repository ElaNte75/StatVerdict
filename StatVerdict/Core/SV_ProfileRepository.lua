local addonName, ns = ...

local Repository = {}
ns.ProfileRepository = Repository

local VALID_GOALS = {
    MYTHIC_PLUS = true,
    RAID = true,
    PVP = true,
}
local DEFAULT_GOAL = "MYTHIC_PLUS"

-- The secondary priority, weights and stat targets are exactly what the
-- ClassCodex addon shows: its guide priority list (rank weights) and its u.gg
-- stat targets (targets.guideTargets, bin below). Players read these guides,
-- so the addon must not contradict them. A stat the guide has no target for
-- uses our own SimC total of the best-in-slot gear (targets.statTargets).
-- Older saved variables (weightMode, gearLevel) are ignored.

-- Which u.gg bin of the guide targets is shown (the ClassCodex addon's default
-- is the top 20%). StatVerdictDB.statTargetBin overrides it.
local DEFAULT_STAT_TARGET_BIN = "top20"
local VALID_STAT_TARGET_BINS = {
    top20 = true,
    top50 = true,
    top80 = true,
}
Repository.DEFAULT_STAT_TARGET_BIN = DEFAULT_STAT_TARGET_BIN

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
local MIN_CONTEXT_ITEMS = 10
local MAX_LOW_ITEM_RATIO = 0.25

-- Seconds to add to time(fields) so fields written in UTC give the real UTC
-- timestamp: time() reads a date table as LOCAL time. Both sides are read as
-- standard time (isdst = false), so daylight saving cancels out. 0 when WoW's
-- date() is missing (then the error is at most the client's UTC offset, <= 14h,
-- which the 30-day freshness window and its 1-day future tolerance absorb).
local function GetUtcCorrection(localStamp)
    if type(date) ~= "function" then return 0 end
    local ok, utc = pcall(date, "!*t", localStamp)
    if not ok or type(utc) ~= "table" then return 0 end
    utc.isdst = false
    local okTime, asLocal = pcall(time, utc)
    if not okTime or type(asLocal) ~= "number" then return 0 end
    return localStamp - asLocal
end

-- ClassCodex buildIds start with the UTC build time: "20260929064954-6702fd4-878715d1".
local function ParseBuildTime(buildId)
    if type(buildId) ~= "string" or type(time) ~= "function" then return nil end
    local year, month, day, hour, minute, second =
        buildId:match("^(%d%d%d%d)(%d%d)(%d%d)(%d%d)(%d%d)(%d%d)")
    if not year then return nil end
    local localStamp = time({
        year = tonumber(year),
        month = tonumber(month),
        day = tonumber(day),
        hour = tonumber(hour),
        min = tonumber(minute),
        sec = tonumber(second),
        isdst = false,
    })
    if type(localStamp) ~= "number" then return nil end
    return localStamp + GetUtcCorrection(localStamp)
end
Repository.ParseBuildTime = ParseBuildTime

local function IsRecentBuild(buildId, maxAgeDays)
    local timestamp = ParseBuildTime(buildId)
    if not timestamp then return false end
    local age = time() - timestamp
    return age >= -86400 and age <= (maxAgeDays * 86400)
end

-- All goals (Mythic+, Raid, PvP) come from the ClassCodex targets file
-- (tools/classcodex_targets_cli.py): profiles[specKey].goals[goal].heroTalents[heroKey].
-- Stale or missing data fails closed: every lookup below returns nil.
local function GetTargetsRoot()
    local root = ns.ClassCodexTargets
    if type(root) ~= "table" or type(root.profiles) ~= "table" then return nil end
    if not IsRecentBuild(root.buildId, MAX_GENERATED_AGE_DAYS) then return nil end
    return root
end

local function GetSpecProfile(specKey)
    local root = GetTargetsRoot()
    local profile = root and specKey and root.profiles[specKey] or nil
    return type(profile) == "table" and profile or nil
end

local function GetHeroTalents(specKey, goal)
    if not VALID_GOALS[goal] then return nil, nil end
    local profile = GetSpecProfile(specKey)
    local goals = profile and profile.goals
    local goalRoot = type(goals) == "table" and goals[goal] or nil
    local heroTalents = type(goalRoot) == "table" and goalRoot.heroTalents or nil
    return type(heroTalents) == "table" and heroTalents or nil, profile
end

local function GetContext(specKey, goal, heroKey)
    if not heroKey then return nil, nil end
    local heroTalents, profile = GetHeroTalents(specKey, goal)
    local context = heroTalents and heroTalents[heroKey] or nil
    if type(context) ~= "table" then return nil, nil end
    return context, profile
end

-- Player hero tree -> ClassCodex key ("sanlayn", "master-of-harmony").
-- 1. The hero subtree ID (SV_SpecMeta table): language-independent, so it is
--    tried first. A known ID decides on its own: if this spec/goal has no data
--    for that tree the answer is nil, never a name match or a guess.
-- 2. The hero tree name ("San'layn"): only English names match, since the game
--    gives names in the client language. Only a name that matches one of this
--    spec/goal's keys counts: an unknown hero tree gives nil (no data), never
--    another tree's data.
-- 3. A MISSING name (below hero-talent level, or a snapshot without hero info)
--    gives the first key in sorted order plus a second return value true, so
--    callers can flag the profile as a guess.
local function ResolveHeroKey(specKey, goal, heroTalentName, heroSubTreeID)
    local wanted = NormalizeToken(heroTalentName)
    local heroTalents = GetHeroTalents(specKey, goal)
    if not heroTalents then return nil end
    local idKey = ns.GetStatVerdictHeroKeyBySubTreeID and ns.GetStatVerdictHeroKeyBySubTreeID(heroSubTreeID)
    if idKey then
        if type(heroTalents[idKey]) == "table" then return idKey end
        return nil
    end
    if wanted == "" then
        local first
        for heroKey in pairs(heroTalents) do
            if type(heroKey) == "string" and (first == nil or heroKey < first) then first = heroKey end
        end
        if first then return first, true end
        return nil
    end
    for heroKey in pairs(heroTalents) do
        if NormalizeToken(heroKey) == wanted then return heroKey end
    end
    -- Best-matching name: exactly one key containing the other ("shadopan" / "theshadopan").
    local match
    for heroKey in pairs(heroTalents) do
        local normalized = NormalizeToken(heroKey)
        if normalized ~= "" and (normalized:find(wanted, 1, true) or wanted:find(normalized, 1, true)) then
            if match then return nil end -- ambiguous: no data rather than a guess
            match = heroKey
        end
    end
    return match
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
    if CountPositiveTargets(targets.statTargets) < 2 then
        return false, "Profile has too few usable stat targets."
    end

    local bis = type(context) == "table" and context.bis or nil
    local bisSlots = type(bis) == "table" and bis.slots or nil
    if type(bisSlots) ~= "table" or #bisSlots < MIN_CONTEXT_ITEMS then
        return false, "Profile has too few goal-specific reference items."
    end

    local itemCount = tonumber(targets.itemCount) or 0
    local averageItemLevel = tonumber(targets.averageItemLevel)
    -- ClassCodex PvP gear carries no item level, so PvP targets have none.
    local itemLevelOptional = goal == "PVP" and targets.averageItemLevel == nil
    if not itemLevelOptional and (averageItemLevel == nil or averageItemLevel < MIN_VALID_MAX_LEVEL_TARGET_ILVL) then
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

Repository.ValidateGeneratedContext = ValidateGeneratedContext

function Repository.GetDataProvenance(goal)
    if not VALID_GOALS[goal] then return { available = false } end
    local root = ns.ClassCodexTargets
    local buildId = type(root) == "table" and root.buildId or nil
    local year, month, day
    if type(buildId) == "string" then
        year, month, day = buildId:match("^(%d%d%d%d)(%d%d)(%d%d)")
    end
    return {
        available = GetTargetsRoot() ~= nil,
        buildId = buildId,
        scrape = year and (year .. "-" .. month .. "-" .. day) or nil,
        sourceName = "StatVerdict data",
    }
end

function Repository.GetContext(specKey, goal, heroKey)
    local context = GetContext(specKey, goal, heroKey)
    return context
end

function Repository.ResolveHeroKey(specKey, goal, heroTalentName, heroSubTreeID)
    return ResolveHeroKey(specKey, goal, heroTalentName, heroSubTreeID)
end

-- Each ClassCodex hero context carries its own priority row.
local function GetPriority(context)
    local rows = type(context) == "table" and context.priorityProfiles or nil
    local priority = type(rows) == "table" and rows[1] or nil
    return type(priority) == "table" and priority or nil
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

function Repository.GetStatTargetBin()
    local db = _G.StatVerdictDB
    local bin = type(db) == "table" and db.statTargetBin or nil
    if type(bin) == "string" and VALID_STAT_TARGET_BINS[bin] then return bin end
    return DEFAULT_STAT_TARGET_BIN
end

-- Positive stat targets of one data table (canonical keys) keyed by runtime
-- stat key; nil when none is usable.
local function CollectTargetValues(values)
    if type(values) ~= "table" then return nil end
    local result, count = {}, 0
    for canonicalKey, value in pairs(values) do
        local statKey = STAT_KEY[canonicalKey]
        local target = tonumber(value)
        if statKey and target and target > 0 then
            result[statKey] = target
            count = count + 1
        end
    end
    return count > 0 and result or nil
end

-- The stat targets shown, keyed by runtime stat key, whether the guide
-- (ClassCodex / u.gg) has no targets for this build in the chosen bin, and the
-- item level those targets belong to. The guide's bin is read; our own targets
-- (the SimC totals of the best-in-slot gear) fill the gaps, or stand in for a
-- build the guide has no targets for.
local function SelectTargetValues(targets, bin)
    local statTargets = type(targets) == "table" and targets.statTargets or nil
    local own = CollectTargetValues(type(statTargets) == "table" and statTargets.stats or nil) or {}
    local averageItemLevel = type(targets) == "table" and targets.averageItemLevel or nil
    local guideRoot = type(targets) == "table" and targets.guideTargets or nil
    local guide = CollectTargetValues(type(guideRoot) == "table" and guideRoot[bin] or nil)
    local guideMissing = guide == nil
    if guideMissing then return own, guideMissing, averageItemLevel end

    local selected = {}
    for statKey, value in pairs(own) do selected[statKey] = value end
    for statKey, value in pairs(guide) do selected[statKey] = value end
    return selected, guideMissing, averageItemLevel
end

-- Saves the guide target bin (Guide drawer: Tier 1/2/3) and drops the cached
-- provider views. false (nothing saved) for an unknown bin.
function Repository.SetStatTargetBin(bin)
    if type(bin) ~= "string" or not VALID_STAT_TARGET_BINS[bin] then return false end
    _G.StatVerdictDB = type(_G.StatVerdictDB) == "table" and _G.StatVerdictDB or {}
    _G.StatVerdictDB.statTargetBin = bin
    Repository.InvalidateProviderViews()
    return true
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

-- targetValues: the targets shown, keyed by runtime stat key, and
-- averageItemLevel the item level they belong to (SelectTargetValues).
local function BuildAuditTargets(averageItemLevel, targetValues, secondaryOrder, equalGroups)
    -- The weight shown per stat is the very one the verdict scoring uses: its fixed share
    -- of the secondary budget (by rank in the guide's order, ties share their average), see SV_Scoring.
    local shares = ns.GetSecondaryBaseShares and ns.GetSecondaryBaseShares(secondaryOrder, equalGroups) or {}
    local rows = {}
    local seen = {}

    local function add(statKey, statType, priority, baseModifier)
        if not statKey or seen[statKey] then return end
        seen[statKey] = true
        -- A secondary stat always keeps its row: a stat with no target (e.g.
        -- Versatility when neither the guide nor the best gear carries any) shows
        -- with target 0, which every consumer already treats as "no target".
        local target = targetValues[statKey] or 0
        rows[#rows + 1] = {
            key = statKey,
            label = STAT_LABEL[statKey] or statKey,
            type = statType,
            target = target,
            priority = priority,
            baseModifier = tonumber(baseModifier),
        }
    end

    for index, statKey in ipairs(secondaryOrder) do
        add(statKey, "Secondary", index, shares[statKey] or 1)
    end

    return {
        source = "generated_classcodex",
        averageItemLevel = averageItemLevel,
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

    local heroTalentName = context.heroTalentName
        or (ns.GetSnapshotHeroTalentName and ns.GetSnapshotHeroTalentName(context))
    local heroSubTreeID = context.heroSubTreeID
        or (ns.GetSnapshotHeroSubTreeID and ns.GetSnapshotHeroSubTreeID(context))
    local heroKey, heroKeyGuessed = ResolveHeroKey(specKey, goal, heroTalentName, heroSubTreeID)
    local generatedContext, generatedProfile = GetContext(specKey, goal, heroKey)
    if type(generatedContext) ~= "table" or type(generatedProfile) ~= "table" then
        return nil
    end
    local validGeneratedContext, invalidReason = ValidateGeneratedContext(generatedContext, goal)
    local invalidGeneratedContext = not validGeneratedContext

    local priority = GetPriority(generatedContext)
    local secondaryOrder = BuildSecondaryOrderFromTargets(generatedContext.targets, priority)
    local equalGroups = BuildEqualGroups(priority, secondaryOrder)
    local statTargetBin = Repository.GetStatTargetBin()
    local targetValues, guideTargetsMissing, targetItemLevel =
        SelectTargetValues(generatedContext.targets, statTargetBin)
    local primaryStat = STAT_KEY[generatedProfile.primaryStat]
    if not primaryStat then return nil end
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
        heroKey = heroKey,
        heroKeyGuessed = heroKeyGuessed == true,
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
        equalGroups = equalGroups,
        caps = {},
        extraWeights = extraWeights,
        auditTargets = invalidGeneratedContext and {
            source = "invalid_generated_context",
            averageItemLevel = nil,
            rows = {},
            invalidReason = invalidReason or "Generated profile data failed quality checks.",
        } or BuildAuditTargets(targetItemLevel, targetValues, secondaryOrder, equalGroups),
        statTargetBin = statTargetBin,
        guideTargetsMissing = guideTargetsMissing,
        generatedContext = invalidGeneratedContext and nil or generatedContext,
        invalidGeneratedContext = invalidGeneratedContext,
    }
end

function Repository.BuildProviderView(goal)
    local root = VALID_GOALS[goal] and GetTargetsRoot() or nil
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

-- The provider view builds a profile for every spec (40), so it is cached per
-- goal and rebuilt only when something it is built from changes: the loaded
-- data files, their freshness, the scoring model, the guide target bin, or the
-- hero tree a spec snapshot records (each spec's default profile follows it). Nothing else
-- feeds BuildRuntimeProfile here: the goal is fixed per view and spec
-- ID/name/role come from the static SV_SpecMeta tables.
local providerViewSignature = {}
local signatureContext = {}

local function BuildProviderViewSignature(goal)
    local root = VALID_GOALS[goal] and GetTargetsRoot() or nil
    local parts = {
        goal,
        tostring(ns.ClassCodexTargets),
        tostring(type(ns.ClassCodexTargets) == "table" and ns.ClassCodexTargets.buildId or nil),
        tostring(root ~= nil),
        tostring(ns.GlobalStatVerdictModifiers),
        Repository.GetStatTargetBin(),
    }
    if root then
        for specKey in pairs(root.profiles or {}) do
            local specID = ns.GetStatVerdictSpecIDByKey and ns.GetStatVerdictSpecIDByKey(specKey)
            signatureContext.specKey = specKey
            signatureContext.specID = specID
            local heroName = ns.GetSnapshotHeroTalentName and ns.GetSnapshotHeroTalentName(signatureContext)
            local heroID = ns.GetSnapshotHeroSubTreeID and ns.GetSnapshotHeroSubTreeID(signatureContext)
            parts[#parts + 1] = tostring(specKey) .. "=" .. tostring(heroID) .. ":" .. tostring(heroName)
        end
    end
    return table.concat(parts, "|")
end

function Repository.InvalidateProviderViews()
    for goal in pairs(providerViewSignature) do
        providerViewSignature[goal] = nil
    end
end

function Repository.GetProviderView(goal)
    goal = VALID_GOALS[goal] and goal or DEFAULT_GOAL
    ns.ProfileProviders = ns.ProfileProviders or {}
    ns.ProfileProviders.GeneratedByGoal = ns.ProfileProviders.GeneratedByGoal or {}
    local signature = BuildProviderViewSignature(goal)
    if type(ns.ProfileProviders.GeneratedByGoal[goal]) ~= "table" or providerViewSignature[goal] ~= signature then
        ns.ProfileProviders.GeneratedByGoal[goal] = Repository.BuildProviderView(goal)
        providerViewSignature[goal] = signature
    end
    return ns.ProfileProviders.GeneratedByGoal[goal]
end

-- Makes the goal's view the active one (ns.ProfileProviders.Generated);
-- rebuilds it only when its inputs changed (see above).
function Repository.RefreshProviderView(goal)
    local view = Repository.GetProviderView(goal)
    ns.ProfileProviders.Generated = view
    return view
end
