local addonName, ns = ...

-- Stat weight modes the player picks in the Weights drawer. The mode itself is kept
-- and applied by the profile repository (StatVerdictDB.weightMode); this file only
-- holds the wording shown to the player and refreshes the views after a change.
local MODES = {
    {
        key = "GUIDE", label = "Guide", meaning = "ClassCodex: Icy Veins / u.gg", hint = "Recommended",
        about = "Priority and stat targets exactly as in ClassCodex (Icy Veins / u.gg). Recommended.",
    },
    {
        key = "MEASURED", label = "Measured", meaning = "Our BiS targets and simulations", hint = "",
        about = "Our own: targets from best-in-slot gear with recommended gems and enchants, weights from simulations.",
    },
    {
        key = "BLEND", label = "Blend", meaning = "Average of guide and ours", hint = "",
        about = "Average of both.",
    },
}
local DEFAULT_MODE = "GUIDE"

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
