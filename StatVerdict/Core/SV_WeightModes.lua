local addonName, ns = ...

-- The Guide drawer: where the addon's stat priorities, Best in Slot lists and
-- stat targets come from. Everything is a 1:1 copy of the guides, never tuned
-- or corrected; this file holds the wording shown to the player and the stat
-- target tier choice, which the profile repository keeps and applies
-- (StatVerdictDB.statTargetBin).
--
-- The one player-visible line allowed to name the data sources lives here (the
-- NoDataSourceNamesShownTests test lists this file as the one exception).
local GUIDE = {
    title = "Guide",
    intro = "All guide information comes from Icy Veins and u.gg.",
}

-- Which guide stat target level is used. Kept by the repository
-- (StatVerdictDB.statTargetBin): exactly one of Auto or one tier, never two. The
-- saved keys stay auto/top20/top50/top80; the player sees Auto, then a tier,
-- listed Tier 1 to Tier 3 (Tier 3 is the most demanding). Auto picks the tier
-- from the character's own stats (see the repository).
local STAT_TARGET_BINS = {
    { key = "auto", label = "Auto", hint = "Recommended", meaning = "Follows your stats", auto = true },
    { key = "top80", label = "Tier 1", hint = "Comfortable", meaning = "Targets most players reach" },
    { key = "top50", label = "Tier 2", hint = "Realistic", meaning = "The stats of a typical player" },
    { key = "top20", label = "Tier 3", hint = "Demanding", meaning = "The best-equipped players" },
}
local DEFAULT_STAT_TARGET_BIN = "auto"

function ns.GetGuideInfo()
    return GUIDE
end

function ns.GetStatTargetBins()
    return STAT_TARGET_BINS
end

function ns.GetStatTargetBin()
    local repository = ns.ProfileRepository
    if repository and repository.GetStatTargetBin then
        return repository.GetStatTargetBin()
    end
    return DEFAULT_STAT_TARGET_BIN
end

-- Saves the stat target tier through the repository (which drops its cached
-- views), then redraws the audit and the bag markers. false for an unknown tier.
function ns.SetStatTargetBin(key)
    local repository = ns.ProfileRepository
    if not (repository and repository.SetStatTargetBin) then return false end
    if not repository.SetStatTargetBin(key) then return false end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
end

-- What Auto says about the character (profile.autoInfo, set by the repository):
-- the line under "Auto" in the Guide drawer, the short label in the window title
-- bar, and the one-off notice after a move up. Fixed tiers say only their name.
local function Percent(progress)
    return math.max(0, math.min(99, math.floor((tonumber(progress) or 0) * 100)))
end

function ns.GetAutoTierSummary(profile)
    local info = type(profile) == "table" and profile.autoInfo or nil
    if type(info) ~= "table" then return nil end
    local level = tonumber(info.level) or 0
    if info.progress == nil then return "Follows your stats" end
    if level >= 3 then return "Tier 3 reached · top targets met" end
    if level <= 0 then return string.format("Getting started · %d%% to Tier 1", Percent(info.progress)) end
    return string.format("Tier %d reached · %d%% to Tier %d", level, Percent(info.progress), level + 1)
end

-- The tier named in the title bar: Auto's reached tier and how far to the next one, or the
-- fixed tier chosen.
function ns.GetTierTitleLabel(profile)
    if type(profile) ~= "table" then return nil end
    local info = profile.autoInfo
    if type(info) == "table" then
        local level = tonumber(info.level) or 0
        if info.progress == nil then return "Auto" end
        if level >= 3 then return "Auto · Tier 3 · top targets met" end
        if level <= 0 then return string.format("Auto · Starting · %d%% to Tier 1", Percent(info.progress)) end
        return string.format("Auto · Tier %d · %d%% to Tier %d", level, Percent(info.progress), level + 1)
    end
    for index, option in ipairs(STAT_TARGET_BINS) do
        if option.key == profile.statTargetBin and not option.auto then
            return option.label
        end
    end
    return nil
end

function ns.GetAutoTierNotice(profile)
    local repository = ns.ProfileRepository
    if not (repository and repository.GetAutoNotice) then return nil end
    local specKey = type(profile) == "table" and profile.specKey or nil
    local level = specKey and repository.GetAutoNotice(specKey) or nil
    if not level then return nil end
    return "You moved up to Tier " .. level .. "."
end

-- The cards under the guide text: Auto, then the guide's stat target tiers.
-- { title, options, selected, set(key) }.
function ns.GetTargetChoice()
    return {
        title = "Stat targets",
        options = STAT_TARGET_BINS,
        selected = ns.GetStatTargetBin(),
        set = ns.SetStatTargetBin,
    }
end

-- Every goal (Mythic+, Raid, PvP) reads the same curated Best in Slot lists.
function ns.GetReferenceWording(goal)
    return {
        popular = false,
        button = "Best in Slot",
        base = "Best in Slot",
        main = "Main Spec Best in Slot",
        off = "Off Spec Best in Slot",
        progress = "BiS Progress",
        progressSuffix = "",
        tag = "BIS",
    }
end
