local addonName, ns = ...
ns = ns or {}

-- Diminishing returns of the secondary stats for the verdict scoring.
--
-- A rating point is not worth the same everywhere: the game converts rating to a raw percent
-- and takes an increasing cut off each bracket of raw percent (none up to 30%, then 10%, 20%,
-- 30%, 40%, 50%). The scoring judges a swap by the stats you have now, so an item is worth
-- what the swap really adds AFTER these cuts: the change in the effective stat between
-- "now" and "after the swap", not a straight count of rating.
--
-- The conversion factors come from the vendored table in Data/Generated/SV_StatDR.lua
-- (ns.StatDR); the brackets below mirror it (a test keeps them in step).

-- { width in raw percent, share taken off inside it }
local BRACKETS = {
    { 30, 0 },
    { 10, 0.1 },
    { 10, 0.2 },
    { 10, 0.3 },
    { 20, 0.4 },
    { 120, 0.5 },
}

local STAT_NAME = {
    ITEM_MOD_CRIT_RATING_SHORT = "crit",
    ITEM_MOD_HASTE_RATING_SHORT = "haste",
    ITEM_MOD_MASTERY_RATING_SHORT = "mastery",
    ITEM_MOD_VERSATILITY = "versatility",
}
local CRIT_BASE = 5
local PROBE_RATING = 100 -- far below the first cut, where a rating point is worth its full value

local function SafeNumber(value)
    value = tonumber(value)
    if value and value == value then return value end
    return nil
end

-- Effective percent (after the cuts) for a raw percent.
local function EffectivePercent(raw)
    if raw <= 0 then return 0 end
    local effective, from = 0, 0
    for _, bracket in ipairs(BRACKETS) do
        local width, cut = bracket[1], bracket[2]
        if raw < from + width then
            return effective + (raw - from) * (1 - cut)
        end
        effective = effective + width * (1 - cut)
        from = from + width
    end
    return effective
end
ns.DiminishingReturnsEffectivePercent = EffectivePercent

-- Rating needed for 1% (mastery: for 1 mastery point) at this level, read from the vendored
-- table through its own TargetPercent at a rating too low to be cut. Mastery converts exactly
-- like crit in that table (a test keeps this true), which spares the spec coefficient.
local function RatingPerPercent(statName, level)
    local statDR = ns.StatDR
    if type(statDR) ~= "table" or type(statDR.TargetPercent) ~= "function" then return nil end
    local probe = statName == "mastery" and "crit" or statName
    local ok, percent = pcall(statDR.TargetPercent, probe, level, PROBE_RATING)
    percent = ok and SafeNumber(percent) or nil
    if not percent then return nil end
    if probe == "crit" then percent = percent - CRIT_BASE end
    if percent <= 0 then return nil end
    return PROBE_RATING / percent
end

-- The change in a secondary stat, counted in "rating that is worth its full value", when the
-- character's rating goes from `current` to `current + delta`. Equal to delta while the
-- character stays below the first cut. Unknown current rating or level: delta unchanged.
function ns.GetEffectiveRatingDelta(statKey, current, delta)
    local statName = STAT_NAME[statKey]
    delta = SafeNumber(delta)
    current = SafeNumber(current)
    if not statName or not delta or delta == 0 or not current then return delta end
    if current < 0 then current = 0 end
    local level = SafeNumber(type(UnitLevel) == "function" and UnitLevel("player")) or 90
    local k = RatingPerPercent(statName, level)
    if not k then return delta end
    local after = math.max(0, current + delta)
    return k * (EffectivePercent(after / k) - EffectivePercent(current / k))
end
