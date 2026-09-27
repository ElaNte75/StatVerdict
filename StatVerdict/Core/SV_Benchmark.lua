local addonName, ns = ...

-- Benchmark level = which key-level difficulty bracket the Mythic+ data is built from,
-- based on players' highest key this season (agreed with the user 2026-09-27). Data
-- cohorts are LOW / MID / HIGH directly; players see Low / Mid / High.
local LEVELS = {
    {
        key = "LOW", label = "Low", meaning = "Players with a highest key of 9 or lower", hint = "Lower keys",
        about = "Built from 100 Mythic+ players this season whose highest key was 9 or lower. Your stat targets and Popular Gear come from the gear they actually wore in their runs, so this matches players at your own pace if you are still working up to higher keys. For players mostly running lower keys.",
    },
    {
        key = "MID", label = "Mid", meaning = "Players with a highest key between 10 and 15", hint = "Recommended",
        about = "Built from 100 Mythic+ players this season whose highest key was between 10 and 15. Your stat targets and Popular Gear come from the gear they actually wore in their runs: the range most active Mythic+ players are in. The best fit for most players, and the default.",
    },
    {
        key = "HIGH", label = "High", meaning = "Players with a highest key of 16 or higher", hint = "Push keys",
        about = "Built from 100 Mythic+ players this season whose highest key was 16 or higher. Your stat targets and Popular Gear come from the gear they actually wore in their runs: the bar for players pushing high keys. For a demanding, competitive build.",
    },
}
local DEFAULT_LEVEL = "MID"

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

-- The Benchmark level only matters while the Main Spec build or a configured Off Spec
-- build uses the Mythic+ goal. The button and the drawer are locked otherwise.
function ns.IsBenchmarkRelevant()
    local selection = ns.GetSavedStatAuditSelection and ns.GetSavedStatAuditSelection() or nil
    if type(selection) ~= "table" then return true end
    if selection.goalMode == "MYTHIC_PLUS" then return true end
    return selection.secondaryEnabled == true and selection.secondaryGoalMode == "MYTHIC_PLUS"
end

-- True when a benchmark's numbers should carry a "less stable" warning: the sample is
-- below twice the minimum, or the confidence is not high.
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
