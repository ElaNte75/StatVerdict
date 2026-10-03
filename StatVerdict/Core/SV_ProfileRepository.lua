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
-- is the top 20%). StatVerdictDB.statTargetBin overrides it: exactly one of
--   auto   the tier follows the character's own stats (see ResolveAutoTier): the
--          default
--   top80 / top50 / top20   a fixed tier (Tier 1 / 2 / 3).
local DEFAULT_STAT_TARGET_BIN = "auto"
local VALID_STAT_TARGET_BINS = {
    auto = true,
    top20 = true,
    top50 = true,
    top80 = true,
}
Repository.DEFAULT_STAT_TARGET_BIN = DEFAULT_STAT_TARGET_BIN
-- The tiers from the easiest (Tier 1) to the most demanding (Tier 3).
local TIER_BINS = { "top80", "top50", "top20" }
-- Auto moves up to the next tier once the stats cover this much of the current
-- tier's targets, and back down only below the lower mark, so one piece of
-- gear swapped in or out never makes it flip back and forth.
local AUTO_UP_AT = 0.90
local AUTO_DOWN_BELOW = 0.80
local AUTO_MIN_RATING_SUM = 100  -- ratings that are not loaded yet read as 0: never judge on them

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

local MAX_GENERATED_AGE_DAYS = 60
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

-- The choice of one spec (Main Spec and Off Spec choose apart): the spec's own saved
-- choice, else the one saved before choices were per spec (statTargetBin), else Auto.
function Repository.GetStatTargetBin(specKey)
    local db = _G.StatVerdictDB
    if type(db) == "table" and specKey and type(db.specTargetBin) == "table" then
        local own = db.specTargetBin[specKey]
        if type(own) == "string" and VALID_STAT_TARGET_BINS[own] then return own end
    end
    local bin = type(db) == "table" and db.statTargetBin or nil
    if type(bin) == "string" and VALID_STAT_TARGET_BINS[bin] then return bin end
    return DEFAULT_STAT_TARGET_BIN
end

-- The upgrade track the Best in Slot / trinket items are shown at follows the
-- stat target tier: a comfortable target must not show gear only the best can
-- have. Tier 3 (top20) shows every item at the Myth 6/6 of its listing (an
-- extension rank or an older id lands on 6/6), Tier 2 at Hero 6/6, Tier 1 at
-- Champion 6/6, through the data root's trackSwap[track] (source bonus id -> that
-- track's 6/6 bonus id). A tier never raises an item above the track it is
-- listed on. PvP gear has no tracks and is never swapped. Old data has no swap:
-- the items then show as listed. Keys may be numbers or, as the generated file
-- writes them, strings.
local TRACK_OF_BIN = { top20 = "myth", top50 = "hero", top80 = "champion" }

-- The tier whose targets are shown for a spec: its fixed tier, or what Auto chose at the
-- spec's last profile build (Tier 3 until it chose). Without a spec: the one the Guide
-- shows now (the active Main / Off Spec view), else the last one built.
local effectiveBinBySpec = {}
local lastEffectiveBin = nil

function Repository.GetEffectiveStatTargetBin(specKey)
    if not specKey and ns.GetActivePanelContext then
        local context = ns.GetActivePanelContext()
        specKey = context and context.profile and context.profile.specKey or nil
    end
    local bin = Repository.GetStatTargetBin(specKey)
    if bin ~= "auto" then return bin end
    return (specKey and effectiveBinBySpec[specKey]) or lastEffectiveBin or "top20"
end

-- The upgrade track the shown tier stands for ("myth" | "hero" | "champion"); nil for PvP gear, which has none.
function Repository.GetActiveTrack()
    if ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode() == "PVP" then return nil end
    return TRACK_OF_BIN[Repository.GetEffectiveStatTargetBin()]
end

-- An item the guide lists without bonus ids (about 70 trinkets) is shown at base item level. The ids the guide
-- gives the same item in another list (another spec or goal; never PvP) are the best answer: the first list
-- found. Built once per data table.
local knownBonusIDs, knownBonusIDsRoot = nil, nil

local function EntryBonusList(entry)
    local item = type(entry) == "table" and entry.item or nil
    local ids = (type(item) == "table" and item.bonus_ids) or (type(entry) == "table" and entry.bonus_ids) or nil
    return type(ids) == "table" and #ids > 0 and ids or nil
end

local function EntryItemID(entry)
    local item = type(entry) == "table" and entry.item or nil
    return tonumber(type(item) == "table" and item.item_id or (type(entry) == "table" and entry.item_id) or nil)
end

local function BuildKnownBonusIDs(root)
    local index = {}
    local function note(entry)
        local itemID, ids = EntryItemID(entry), EntryBonusList(entry)
        if itemID and ids and not index[itemID] then
            local copy = {}
            for position, id in ipairs(ids) do copy[position] = id end
            index[itemID] = copy
        end
    end
    for _, profile in pairs(type(root) == "table" and root.profiles or {}) do
        for goal, goalData in pairs(type(profile) == "table" and profile.goals or {}) do
            if goal ~= "PVP" then
                for _, context in pairs(type(goalData) == "table" and goalData.heroTalents or {}) do
                    local bis = type(context) == "table" and context.bis or nil
                    for _, entry in pairs(type(bis) == "table" and bis.slots or {}) do note(entry) end
                    for _, entry in ipairs(type(context) == "table" and context.trinkets or {}) do note(entry) end
                end
            end
        end
    end
    return index
end

function Repository.GetKnownBonusIDs(itemID)
    local root = ns.ClassCodexTargets
    if knownBonusIDs == nil or knownBonusIDsRoot ~= root then
        knownBonusIDs, knownBonusIDsRoot = BuildKnownBonusIDs(root), root
    end
    local ids = knownBonusIDs[tonumber(itemID)]
    if not ids then return nil end
    local copy = {}  -- the caller may change its list; the index stays as built
    for position, id in ipairs(ids) do copy[position] = id end
    return copy
end

-- The 6/6 bonus id of the shown tier's track, from the data root (nil when the data has none).
function Repository.GetTrackTopBonusID()
    local track = Repository.GetActiveTrack()
    local root = ns.ClassCodexTargets
    local top = type(root) == "table" and root.trackTop or nil
    return track and type(top) == "table" and tonumber(top[track]) or nil
end

function Repository.GetActiveTrackSwap()
    if ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode() == "PVP" then return nil end
    local track = TRACK_OF_BIN[Repository.GetEffectiveStatTargetBin()]
    if not track then return nil end
    local root = ns.ClassCodexTargets
    local swaps = type(root) == "table" and root.trackSwap or nil
    local swap = type(swaps) == "table" and swaps[track] or nil
    return type(swap) == "table" and swap or nil
end

-- A copy of bonusIDs with every id in the active swap replaced by its value;
-- ids not in the swap stay. The same table when nothing is swapped.
function Repository.ApplyTrackSwap(bonusIDs)
    local swap = Repository.GetActiveTrackSwap()
    if not swap or type(bonusIDs) ~= "table" then return bonusIDs end
    local out = {}
    for index, bonusID in ipairs(bonusIDs) do
        local replacement = swap[bonusID]
        if replacement == nil then replacement = swap[tostring(bonusID)] end
        out[index] = tonumber(replacement) or bonusID
    end
    return out
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

-- Auto: the tier follows the character's own stats. The progress to a tier is
-- the average of each stat's progress to that tier's target (a stat past its
-- target counts as 100%), as in the main window's "Average Progress". `level` is the highest tier whose
-- targets are covered (0 to 3): it moves up at AUTO_UP_AT of the next tier and
-- back down only below AUTO_DOWN_BELOW of its own, and is remembered per spec
-- (StatVerdictDB.autoTier) so it does not flip back and forth. The targets and
-- Best in Slot shown are those of the next tier (the goal), Tier 3 at the top.
local AUTO_STATS = {
    "ITEM_MOD_CRIT_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT",
    "ITEM_MOD_MASTERY_RATING_SHORT", "ITEM_MOD_VERSATILITY",
}

local function ReadRating(specID, statKey)
    local pseudo = { specID = specID }
    if specID and ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(pseudo) then
        return ns.GetSnapshotStatValue and ns.GetSnapshotStatValue(pseudo, statKey) or nil
    end
    return ns.GetCurrentStatRating and ns.GetCurrentStatRating(statKey) or nil
end

-- The progress to a tier: the average of each stat's progress to its target, a stat past its
-- target counting as 100% -- the very number the main window shows as "Average Progress".
local function CoveredShare(targetValues, ratings)
    local sum, count = 0, 0
    for _, statKey in ipairs(AUTO_STATS) do
        local target = targetValues[statKey]
        if target and target > 0 then
            sum = sum + math.min(1, (ratings[statKey] or 0) / target)
            count = count + 1
        end
    end
    if count == 0 then return nil end
    return sum / count
end

-- The share of each tier's rating targets the stats cover: { [1] = Tier 1, [2] = Tier 2, [3] = Tier 3 }
-- and whether the stats are known (loaded). Shown for a fixed tier too: how far the next one is.
local function TierShares(targets, specID)
    local ratings, sum = {}, 0
    for _, statKey in ipairs(AUTO_STATS) do
        local value = tonumber(ReadRating(specID, statKey))
        ratings[statKey] = value
        sum = sum + (value or 0)
    end
    local shares = {}
    for tier, bin in ipairs(TIER_BINS) do
        local values = SelectTargetValues(targets, bin)
        shares[tier] = CoveredShare(values, ratings)
    end
    local known = sum >= AUTO_MIN_RATING_SUM and shares[1] ~= nil and shares[2] ~= nil and shares[3] ~= nil
    return shares, known
end

-- { level, shownTier, progress } for one spec; progress is the share of the shown
-- tier's targets covered, nil when the stats are not known yet (then the
-- remembered level stands).
local function ResolveAutoTier(specKey, shares, known)
    local db = _G.StatVerdictDB
    local remembered = type(db) == "table" and type(db.autoTier) == "table" and tonumber(db.autoTier[specKey]) or 0
    remembered = math.max(0, math.min(3, math.floor(remembered)))
    if not known then
        local shown = math.min(remembered + 1, 3)
        return { level = remembered, shownTier = shown, progress = nil }
    end
    local level = remembered
    while level < 3 and shares[level + 1] >= AUTO_UP_AT do level = level + 1 end
    while level > 0 and shares[level] < AUTO_DOWN_BELOW do level = level - 1 end
    if level ~= remembered and type(db) == "table" then
        db.autoTier = type(db.autoTier) == "table" and db.autoTier or {}
        db.autoTier[specKey] = level
        if level > remembered then
            db.autoNotice = { specKey = specKey, level = level }
        end
    end
    local shown = math.min(level + 1, 3)
    return { level = level, shownTier = shown, progress = shares[shown] }
end

-- The tier Auto moved the spec up to, for a one-off notice, or nil.
function Repository.GetAutoNotice(specKey)
    local db = _G.StatVerdictDB
    local notice = type(db) == "table" and db.autoNotice or nil
    if type(notice) == "table" and notice.specKey == specKey and tonumber(notice.level) then
        return math.floor(tonumber(notice.level))
    end
    return nil
end

function Repository.ClearAutoNotice()
    local db = _G.StatVerdictDB
    if type(db) == "table" then db.autoNotice = nil end
end

-- Saves the guide target bin (Guide drawer: Auto or Tier 1/2/3) and drops the cached
-- provider views. false (nothing saved) for an unknown bin.
function Repository.SetStatTargetBin(bin, specKey)
    if type(bin) ~= "string" or not VALID_STAT_TARGET_BINS[bin] then return false end
    _G.StatVerdictDB = type(_G.StatVerdictDB) == "table" and _G.StatVerdictDB or {}
    if specKey then
        local db = _G.StatVerdictDB
        db.specTargetBin = type(db.specTargetBin) == "table" and db.specTargetBin or {}
        db.specTargetBin[specKey] = bin
    else
        _G.StatVerdictDB.statTargetBin = bin
    end
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
    local statTargetBin = Repository.GetStatTargetBin(specKey)
    local effectiveBin, autoInfo = statTargetBin, nil
    local tierShares, sharesKnown = TierShares(generatedContext.targets, context.specID)
    if statTargetBin == "auto" then
        autoInfo = ResolveAutoTier(specKey, tierShares, sharesKnown)
        effectiveBin = TIER_BINS[autoInfo.shownTier]
    end
    effectiveBinBySpec[specKey] = effectiveBin
    lastEffectiveBin = effectiveBin
    local targetValues, guideTargetsMissing, targetItemLevel =
        SelectTargetValues(generatedContext.targets, effectiveBin)
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
        effectiveBin = effectiveBin,
        autoInfo = autoInfo,
        tierProgress = sharesKnown and tierShares or nil,
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
        Repository.GetStatTargetBin(),  -- the choice saved before choices were per spec
    }
    if root then
        for specKey in pairs(root.profiles or {}) do
            local specID = ns.GetStatVerdictSpecIDByKey and ns.GetStatVerdictSpecIDByKey(specKey)
            signatureContext.specKey = specKey
            signatureContext.specID = specID
            local heroName = ns.GetSnapshotHeroTalentName and ns.GetSnapshotHeroTalentName(signatureContext)
            local heroID = ns.GetSnapshotHeroSubTreeID and ns.GetSnapshotHeroSubTreeID(signatureContext)
            local bin = Repository.GetStatTargetBin(specKey)
            parts[#parts + 1] = tostring(specKey) .. "=" .. tostring(heroID) .. ":" .. tostring(heroName) .. ":" .. bin
            if bin == "auto" then
                -- Auto follows the stats: a new rating is a new input.
                local stamp = {}
                for _, statKey in ipairs(AUTO_STATS) do
                    stamp[#stamp + 1] = tostring(ReadRating(specID, statKey))
                end
                parts[#parts + 1] = table.concat(stamp, ",")
            end
        end
    end
    return table.concat(parts, "|")
end

function Repository.InvalidateProviderViews()
    for goal in pairs(providerViewSignature) do
        providerViewSignature[goal] = nil
    end
    if ns.ResetContextScan then ns.ResetContextScan() end
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
