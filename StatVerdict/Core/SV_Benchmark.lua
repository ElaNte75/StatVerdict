local addonName, ns = ...

-- Benchmark level = which group of top players the Mythic+ data is built from.
-- Data cohorts are TOP_25 / TOP_100 / TOP_200; players see Elite / Standard / Broad.
local LEVELS = {
    { key = "ELITE", label = "Elite", meaning = "Gear of the top 25 players" },
    { key = "STANDARD", label = "Standard", meaning = "Gear of the top 100 players" },
    { key = "BROAD", label = "Broad", meaning = "Gear of the top 200 players" },
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

-- True when a benchmark's numbers should carry a "less stable" warning: the sample is
-- below twice the minimum (Elite always is) or the confidence is not high.
function ns.IsBenchmarkSampleSmall(bench)
    if type(bench) ~= "table" then return true end
    local sample = tonumber(bench.sampleSize) or 0
    local minimum = tonumber(bench.minimumSample) or 0
    return tostring(bench.confidence) ~= "high" or sample < (2 * minimum)
end

-- Mythic+ lists are "most popular among top players", not curated Best in Slot,
-- so they are labelled honestly. Raid/PvP keep the curated BiS wording.
function ns.GetReferenceWording(goal)
    goal = goal or (ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode()) or "MYTHIC_PLUS"
    if goal == "MYTHIC_PLUS" then
        local level = ns.GetBenchmarkLevelInfo(ns.GetBenchmarkLevel())
        return {
            popular = true,
            button = "Popular Gear",
            base = "Popular Gear",
            main = "Main Spec Popular Gear",
            off = "Off Spec Popular Gear",
            progress = "Popular Progress",
            progressSuffix = " · " .. level.label,
            tag = "Popular",
        }
    end
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
