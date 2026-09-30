local addonName, ns = ...

-- Stat weight modes the player picks in the Weights drawer. The mode itself is kept
-- and applied by the profile repository (StatVerdictDB.weightMode); this file only
-- holds the wording shown to the player and refreshes the views after a change.
local MODES = {
    {
        key = "GUIDE", label = "Guide", meaning = "From guides", hint = "Recommended",
        about = "Stat priority and stat targets taken straight from the guides. Recommended.",
    },
    {
        key = "MEASURED", label = "Measured", meaning = "Our own measurement", hint = "",
        about = "Our own simulation of your DPS: targets from best-in-slot gear with gems and enchants, and measured stat values. For tank specs it measures damage, not survivability.",
    },
}
local DEFAULT_MODE = "GUIDE"

-- Which guide stat target level Guide uses (Measured uses the gear level below).
-- Kept by the repository (StatVerdictDB.statTargetBin). The saved keys stay
-- top20/top50/top80; the player sees a tier, listed Tier 3 to Tier 1 (Tier 1 is
-- the most demanding).
local STAT_TARGET_BINS = {
    { key = "top80", label = "Tier 3", about = "Tier 3: stat targets that most players reach. A comfortable goal." },
    { key = "top50", label = "Tier 2", about = "Tier 2: the stats of a typical player. A solid, realistic goal." },
    { key = "top20", label = "Tier 1", about = "Tier 1: the stats the best-equipped players reach. The most demanding goal." },
}
local DEFAULT_STAT_TARGET_BIN = "top20"

-- Which gear level Measured uses (Guide ignores it): our own stat targets, and the
-- Best in Slot / trinket items shown at that upgrade track. Kept by the repository
-- (StatVerdictDB.gearLevel), listed easy to hard; Myth is the default.
local GEAR_LEVELS = {
    { key = "champion", label = "Champion", about = "Best in Slot, trinkets and targets at Champion-track gear. A comfortable goal." },
    { key = "hero", label = "Hero", about = "Best in Slot, trinkets and targets at Hero-track gear. A solid, realistic goal." },
    { key = "myth", label = "Myth", about = "Best in Slot, trinkets and targets at Myth-track gear. The most demanding goal." },
}
local DEFAULT_GEAR_LEVEL = "myth"

local BY_KEY = {}
for _, mode in ipairs(MODES) do
    BY_KEY[mode.key] = mode
end

function ns.GetWeightModes()
    return MODES
end

function ns.GetWeightModeInfo(key)
    return BY_KEY[key] or BY_KEY[DEFAULT_MODE]
end

function ns.GetWeightMode()
    local repository = ns.ProfileRepository
    if repository and repository.GetWeightMode then
        return repository.GetWeightMode()
    end
    return DEFAULT_MODE
end

-- Saves the mode through the repository (which drops its cached views), then
-- redraws the audit and the bag markers. false for an unknown mode.
function ns.SetWeightMode(key)
    local repository = ns.ProfileRepository
    if not BY_KEY[key] or not (repository and repository.SetWeightMode) then return false end
    if not repository.SetWeightMode(key) then return false end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
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

-- Same as SetWeightMode, for the stat target level. false for an unknown level.
function ns.SetStatTargetBin(key)
    local repository = ns.ProfileRepository
    if not (repository and repository.SetStatTargetBin) then return false end
    if not repository.SetStatTargetBin(key) then return false end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
end

function ns.GetGearLevels()
    return GEAR_LEVELS
end

function ns.GetGearLevel()
    local repository = ns.ProfileRepository
    if repository and repository.GetGearLevel then
        return repository.GetGearLevel()
    end
    return DEFAULT_GEAR_LEVEL
end

-- Same as SetWeightMode, for Measured's gear level. false for an unknown level.
function ns.SetGearLevel(key)
    local repository = ns.ProfileRepository
    if not (repository and repository.SetGearLevel) then return false end
    if not repository.SetGearLevel(key) then return false end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
end

-- The three cards under the mode rows mean a different, separately saved choice
-- per mode: Guide picks the guide's stat target tier, Measured our gear level.
-- { title, options, selected, set(key) } for the given mode.
function ns.GetTargetChoice(mode)
    if mode == "MEASURED" then
        return { title = "Gear level", options = GEAR_LEVELS, selected = ns.GetGearLevel(), set = ns.SetGearLevel }
    end
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
