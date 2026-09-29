local addonName, ns = ...

-- Benchmark level = which group of top players the Mythic+ data is built from.
-- Data cohorts are TOP_25 / TOP_100 / TOP_200; players see Elite / Standard / Broad.
local LEVELS = {
    {
        key = "ELITE", label = "Elite", meaning = "Gear of the top 25 players", hint = "Strictest",
        about = "Built from the top 25 Mythic+ players this season. Your stat targets and Popular Gear come from the gear they actually wore in their runs, so this is the strictest bar to measure against. A small group means the numbers can shift more between updates. For pushing for the very top.",
    },
    {
        key = "STANDARD", label = "Standard", meaning = "Gear of the top 100 players", hint = "Recommended",
        about = "Built from the top 100 Mythic+ players this season. Your stat targets and Popular Gear come from the gear they actually wore in their runs: a demanding but realistic bar, from a group large enough for steady numbers. The best fit for most players, and the default.",
    },
    {
        key = "BROAD", label = "Broad", meaning = "Gear of the top 200 players", hint = "Steadiest",
        about = "Built from the top 200 Mythic+ players this season. Your stat targets and Popular Gear come from the gear they actually wore in their runs. The larger group gives the steadiest numbers and a slightly gentler bar than Elite. For a safe, typical build.",
    },
}
local DEFAULT_LEVEL = "STANDARD"

local BY_KEY = {}
for _, level in ipairs(LEVELS) do
    BY_KEY[level.key] = level
end

function ns.GetBenchmarkLevels()
    return LEVELS
end

function ns.GetBenchmarkLevelInfo(key)
    return BY_KEY[key] or BY_KEY[DEFAULT_LEVEL]
end

function ns.GetBenchmarkLevel()
    local db = _G.StatVerdictDB
    local key = type(db) == "table" and db.benchmarkLevel or nil
    if BY_KEY[key] then return key end
    return DEFAULT_LEVEL
end

function ns.SetBenchmarkLevel(key)
    if not BY_KEY[key] then return false end
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    _G.StatVerdictDB.benchmarkLevel = key
    if ns.ProfileRepository and ns.ProfileRepository.RefreshProviderView then
        ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")
    end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
end

-- The Benchmark levels (top 25/100/200 players) were built from Raider.IO, which is
-- gone: Mythic+ now uses the same curated ClassCodex data as Raid and PvP, so there is
-- nothing left to choose. The button and the drawer stay in the addon but are locked.
function ns.IsBenchmarkRelevant()
    return false
end

-- True when a benchmark's numbers should carry a "less stable" warning: the sample is
-- below twice the minimum (Elite always is) or the confidence is not high.
function ns.IsBenchmarkSampleSmall(bench)
    if type(bench) ~= "table" then return true end
    local sample = tonumber(bench.sampleSize) or 0
    local minimum = tonumber(bench.minimumSample) or 0
    return tostring(bench.confidence) ~= "high" or sample < (2 * minimum)
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
