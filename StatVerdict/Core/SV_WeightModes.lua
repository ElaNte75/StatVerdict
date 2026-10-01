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
-- (StatVerdictDB.statTargetBin). The saved keys stay top20/top50/top80; the
-- player sees a tier, listed Tier 1 to Tier 3 (Tier 3 is the most demanding).
local STAT_TARGET_BINS = {
    { key = "top80", label = "Tier 1", hint = "Comfortable", meaning = "Targets most players reach" },
    { key = "top50", label = "Tier 2", hint = "Realistic", meaning = "The stats of a typical player" },
    { key = "top20", label = "Tier 3", hint = "Demanding", meaning = "The best-equipped players" },
}
local DEFAULT_STAT_TARGET_BIN = "top20"

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

-- The three cards under the guide text: the guide's stat target tier.
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
