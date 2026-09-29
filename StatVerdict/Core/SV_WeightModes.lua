local addonName, ns = ...

-- Stat weight modes the player picks in the Weights drawer. The mode itself is kept
-- and applied by the profile repository (StatVerdictDB.weightMode); this file only
-- holds the wording shown to the player and refreshes the views after a change.
local MODES = {
    {
        key = "GUIDE", label = "Guide", meaning = "ClassCodex: Icy Veins / u.gg", hint = "Recommended",
        about = "Priority and stat targets exactly as in ClassCodex (Icy Veins / u.gg); weights follow that priority. Recommended.",
    },
    {
        key = "MEASURED", label = "Measured", meaning = "Our BiS targets and simulations", hint = "",
        about = "Our own: priority and weights from simulations, stat targets from best-in-slot gear with recommended gems and enchants.",
    },
    {
        key = "BLEND", label = "Blend", meaning = "Average of guide and ours", hint = "",
        about = "Guide priority; weights and stat targets are the average of the guide's and ours.",
    },
}
local DEFAULT_MODE = "GUIDE"

-- Which ClassCodex (u.gg) stat target level Guide and Blend use, as the
-- ClassCodex addon offers it. Kept by the repository (StatVerdictDB.statTargetBin).
local STAT_TARGET_BINS = {
    { key = "top20", label = "Top 20%" },
    { key = "top50", label = "Top 50%" },
    { key = "top80", label = "Top 80%" },
}
local DEFAULT_STAT_TARGET_BIN = "top20"

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
