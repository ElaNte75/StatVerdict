local addonName, ns = ...


-- Target-driven max-level scoring v2.
-- Item level and primary stat are fixed anchors. Only secondary stats redistribute
-- inside a small, capped budget so target pressure cannot overpower large ilvl/primary gaps.
--
-- Slot rules:
--   armor/weapons — primary + ilvl dominate; secondaries share one live budget
--   rings/neck    — primaryless transfer onto top secondary
--   trinkets      — BIS tier/rank first; secondaries heavily dampened (effect > stats)
-- How the guide's order becomes numbers: the guide gives only an order, so each place is worth a little less
-- than the one before (about 1.4 : 1.25 : 1.1 : 1). A stat the top place beats a lower one when it brings
-- about twice the amount, not when it brings any. Stats the guide calls equal share the average.
local TARGET_SECONDARY_BASE = { 1.40, 1.25, 1.10, 1.00 }
-- How the character's rating against a stat's target scales that stat's share (then all four are brought
-- back to the fixed budget in proportion, so nobody is drained first and equal shares stay equal).
--   Missing rating: counted in rating points, because it is pieces (not percent) that have to be found. A gap
--   of up to about a gem or an enchant (TARGET_NEED_SMALL_GAP) counts for nothing; it grows to the full boost
--   (TARGET_NEED_DEFICIT_MAX, +25%) at about several pieces (TARGET_NEED_FULL_GAP).
--   Priority: a stat only gets its boost as far as the stats above it in the guide's order have got to their
--   own targets (the gate), so the top of the order is filled first and, as it gets there, the stats below
--   take over. Stats in the same tie do not gate each other.
--   Rating over the target counts less, down to 0.75x at 60% or more over it.
local TARGET_NEED_DEFICIT_MAX = 0.25
local TARGET_NEED_SMALL_GAP = 60
local TARGET_NEED_FULL_GAP = 400
local TARGET_NEED_SURPLUS_RANGE = 0.60
local TARGET_NEED_SURPLUS_MIN = 0.75
local TARGET_SECONDARY_BUDGET = 6.00
local TARGET_ITEM_LEVEL_WEIGHT = 2.00
local PRIMARYLESS_TRANSFER = 0.50
-- Pieces that carry no primary stat (jewelry, and trinkets, which give the budget either as a primary stat
-- or as secondaries): the first secondary of the guide's order is scored as the primary stat, the others
-- keep their own weights. The rule belongs to the slot, so a swap is judged the same from both sides.
local PRIMARYLESS_EQUIP_LOCATIONS = {
    INVTYPE_FINGER = true,
    INVTYPE_NECK = true,
    INVTYPE_TRINKET = true,
}
-- Soft exception: tiny primary loss can still lose to strong #1+#2 secondaries.
local SOFT_PRIMARY_GAP = 5
local SOFT_PRIMARY_ILVL_SLACK = 3
local SOFT_PRIMARY_PENALTY_KEEP = 0.55
-- Trinkets are scored like jewelry (the list bonus, not damped stats, carries the effect); item level
-- counts a little more on them because the whole budget of a trinket scales with it.
local TRINKET_ITEM_LEVEL_SCALE = 1.15
local PRISMATIC_SOCKET_STAT_KEY = "STATVERDICT_PRISMATIC_SOCKET"

local SECONDARY_TARGET_KEY = {
    ITEM_MOD_CRIT_RATING_SHORT = true,
    ITEM_MOD_HASTE_RATING_SHORT = true,
    ITEM_MOD_MASTERY_RATING_SHORT = true,
    ITEM_MOD_VERSATILITY = true,
}

local function IsGeneratedTargetProfile(profile)
    return type(profile) == "table"
        and type(profile.secondaryOrder) == "table"
        and type(profile.auditTargets) == "table"
        and type(profile.auditTargets.rows) == "table"
end

local function GetTargetForStat(profile, statKey)
    if type(profile) ~= "table" or type(profile.auditTargets) ~= "table" then return nil end
    local rows = profile.auditTargets.rows
    if type(rows) ~= "table" then return nil end
    for _, row in ipairs(rows) do
        if type(row) == "table" and row.key == statKey then
            local target = tonumber(row.target)
            if target and target > 0 then return target end
        end
    end
    return nil
end

local function GetSecondaryRank(profile, statKey)
    if type(profile) ~= "table" or type(profile.secondaryOrder) ~= "table" then return nil end
    for index, key in ipairs(profile.secondaryOrder) do
        if key == statKey then return index end
    end
    return nil
end

local function GetMaxPrismaticSocketsPerItem()
    local socketModel = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.socket or nil
    local maxSockets = tonumber(socketModel and socketModel.maxPrismaticSocketsPerItem) or 3
    return math.max(0, math.floor(maxSockets))
end

local function GetSocketState(itemLink, rawStats)
    local maxSockets = GetMaxPrismaticSocketsPerItem()
    local socketCount = nil
    if type(C_Item) == "table" and type(C_Item.GetItemNumSockets) == "function" then
        local ok, count = pcall(C_Item.GetItemNumSockets, itemLink)
        if ok then socketCount = tonumber(count) end
    end
    local statSocketCount = tonumber(type(rawStats) == "table" and rawStats.EMPTY_SOCKET_PRISMATIC) or 0
    if socketCount == nil or (socketCount <= 0 and statSocketCount > 0) then
        socketCount = statSocketCount
    end
    socketCount = math.min(maxSockets, math.max(0, math.floor(socketCount)))

    local emptySockets = 0
    local gemStats = {}
    for index = 1, socketCount do
        local gemLink = nil
        if type(C_Item) == "table" and type(C_Item.GetItemGem) == "function" then
            local ok, _, link = pcall(C_Item.GetItemGem, itemLink, index)
            if ok then gemLink = link end
        end
        if gemLink then
            local ok, stats = pcall(C_Item.GetItemStats, gemLink)
            if ok and type(stats) == "table" then
                for statKey, amount in pairs(stats) do
                    local numericAmount = tonumber(amount)
                    if numericAmount then
                        gemStats[statKey] = (gemStats[statKey] or 0) + numericAmount
                    end
                end
            end
        else
            emptySockets = emptySockets + 1
        end
    end
    return emptySockets, gemStats
end

local function GetFixedPrimaryWeight(profile)
    local model = ns.GlobalStatVerdictModifiers or nil
    local weight = tonumber(model and model.primary) or 4.00
    if type(profile) == "table" and type(profile.modifierOverrides) == "table" and profile.primaryStat and profile.modifierOverrides[profile.primaryStat] ~= nil then
        weight = tonumber(profile.modifierOverrides[profile.primaryStat]) or weight
    end
    return weight
end

local function GetSecondaryBaseWeight(rank)
    return TARGET_SECONDARY_BASE[rank] or 0.50
end

-- While a swap is judged, the ratings the live weights read are the MIDDLE of the swap (the rating now
-- plus half of the change): judged from the other side the middle is the same, so the verdict of A over B
-- is exactly the opposite of B over A and two pieces can never both be better than each other.
local ratingOverride = nil

-- The rating of a stat the character has now (an off-spec profile: the saved snapshot's).
local function GetPlayerRatingForScoring(profile, statKey)
    if ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile) then
        return ns.GetSnapshotStatValue and ns.GetSnapshotStatValue(profile, statKey) or nil
    end
    return ns.GetCurrentStatRating and ns.GetCurrentStatRating(statKey) or nil
end

-- The rating the live weights read: the middle of the swap being judged, else the rating now.
local function GetCurrentRatingForScoring(profile, statKey)
    if ratingOverride and ratingOverride[statKey] ~= nil then
        return ratingOverride[statKey]
    end
    return GetPlayerRatingForScoring(profile, statKey)
end

local function BeginSwapRatings(profile, candidateStats, equippedStats)
    local mid = {}
    for statKey in pairs(SECONDARY_TARGET_KEY) do
        local current = GetPlayerRatingForScoring(profile, statKey)
        if type(current) == "number" then
            local delta = (tonumber(candidateStats[statKey]) or 0) - (tonumber(equippedStats[statKey]) or 0)
            mid[statKey] = current + delta / 2
        end
    end
    ratingOverride = mid
end

local function EndSwapRatings()
    ratingOverride = nil
end

local function GetTargetLiveMultiplier(profile, statKey, gate)
    local sanitizer = ns.SanitizeStatVerdictNumber
    local target = GetTargetForStat(profile, statKey)
    local current = GetCurrentRatingForScoring(profile, statKey)
    if type(sanitizer) == "function" then
        target = sanitizer(target)
        current = sanitizer(current)
    end
    -- Secret/inaccessible combat ratings fall back to a neutral multiplier.
    if not target or not current or target <= 0 then
        return 1.00
    end

    if current < target then
        local missing = target - current
        local fraction = (missing - TARGET_NEED_SMALL_GAP) / (TARGET_NEED_FULL_GAP - TARGET_NEED_SMALL_GAP)
        fraction = math.max(0, math.min(1, fraction))
        return 1 + TARGET_NEED_DEFICIT_MAX * fraction * (gate or 1)
    end
    local over = math.min(1, (current / target - 1) / TARGET_NEED_SURPLUS_RANGE)
    return 1 - (1 - TARGET_NEED_SURPLUS_MIN) * over
end

-- The fixed share of the secondary budget of each stat, in the profile's order: the guide gives an
-- order only, so rank places (TARGET_SECONDARY_BASE) scaled to TARGET_SECONDARY_BUDGET; stats the
-- guide calls roughly equal (equalGroups: lists of positions in the order) share the average of
-- their places.
-- Returns { [statKey] = share, ... } and the shares as a list in order.
function ns.GetSecondaryBaseShares(order, equalGroups)
    local bases, keys = {}, {}
    if type(order) ~= "table" then return {}, {} end
    local sumBase = 0
    for index, statKey in ipairs(order) do
        if SECONDARY_TARGET_KEY[statKey] then
            keys[#keys + 1] = { key = statKey, index = index }
            bases[index] = TARGET_SECONDARY_BASE[index] or 0.50
            sumBase = sumBase + bases[index]
        end
    end
    if type(equalGroups) == "table" then
        for _, group in ipairs(equalGroups) do
            local total, count = 0, 0
            for _, position in ipairs(group) do
                if bases[position] then total = total + bases[position]; count = count + 1 end
            end
            if count > 1 then
                local average = total / count
                for _, position in ipairs(group) do
                    if bases[position] then bases[position] = average end
                end
            end
        end
    end
    local byKey, list = {}, {}
    if sumBase <= 0 then return byKey, list end
    for _, entry in ipairs(keys) do
        local share = bases[entry.index] * (TARGET_SECONDARY_BUDGET / sumBase)
        byKey[entry.key] = share
        list[#list + 1] = share
    end
    return byKey, list
end

-- The place of each secondary stat in the guide's order, as shown on tooltips: { [statKey] = { rank, tied } }.
-- Stats the guide calls roughly equal (equalGroups) share the number of the highest place in their group.
function ns.GetSecondaryDisplayRanks(order, equalGroups)
    local ranks = {}
    if type(order) ~= "table" then return ranks end
    for index, statKey in ipairs(order) do
        if SECONDARY_TARGET_KEY[statKey] then
            ranks[statKey] = { rank = index, tied = false }
        end
    end
    if type(equalGroups) == "table" then
        for _, group in ipairs(equalGroups) do
            local top, members = nil, {}
            for _, position in ipairs(group) do
                local entry = ranks[order[position]]
                if entry then
                    members[#members + 1] = entry
                    if not top or position < top then top = position end
                end
            end
            if #members > 1 then
                for _, entry in ipairs(members) do
                    entry.rank = top
                    entry.tied = true
                end
            end
        end
    end
    return ranks
end

local function GetRawTargetSecondaryWeight(profile, statKey)
    local rank = GetSecondaryRank(profile, statKey)
    if not rank then return nil end

    local base = GetSecondaryBaseWeight(rank)
    local live = GetTargetLiveMultiplier(profile, statKey)
    return base * live
end

-- Live secondary budget: each stat's share scaled by how far the character is from its target,
-- then all brought back to the fixed budget in proportion.
local cachedSecondaryWeights = nil
local cachedSecondaryToken = nil

local function GetSecondaryCacheToken(profile)
    local id = tostring(profile and (profile.id or profile.profileKey) or "profile")
    local parts = { id }
    if type(profile.secondaryOrder) == "table" then
        for _, statKey in ipairs(profile.secondaryOrder) do
            local current = GetCurrentRatingForScoring(profile, statKey) or 0
            -- The target too: a new guide tier keeps the profile id.
            parts[#parts + 1] = tostring(statKey) .. "=" .. tostring(current)
                .. "/" .. tostring(GetTargetForStat(profile, statKey))
        end
    end
    if type(profile.equalGroups) == "table" then
        for _, group in ipairs(profile.equalGroups) do
            parts[#parts + 1] = "=" .. table.concat(group, ",")
        end
    end
    return table.concat(parts, "|")
end

local function BuildAllocatedSecondaryWeights(profile)
    local order = profile and profile.secondaryOrder
    if type(order) ~= "table" or #order == 0 then
        return {}
    end

    local keys, desired = {}, {}
    for _, statKey in ipairs(order) do
        if SECONDARY_TARGET_KEY[statKey] then keys[#keys + 1] = statKey end
    end
    local shareByKey = ns.GetSecondaryBaseShares(order, profile.equalGroups)
    if #keys == 0 or next(shareByKey) == nil then
        return {}
    end

    -- The progress (0 to 1) of every stat towards its target, for the gate.
    local progress = {}
    for i, statKey in ipairs(keys) do
        local target = GetTargetForStat(profile, statKey)
        local current = GetCurrentRatingForScoring(profile, statKey)
        if target and target > 0 and type(current) == "number" then
            progress[i] = math.max(0, math.min(1, current / target))
        end
    end

    local sumDesired = 0
    for i, statKey in ipairs(keys) do
        -- Gate: the least-finished stat among those the guide ranks strictly above this one.
        local gate = 1
        for j, otherKey in ipairs(keys) do
            if progress[j] and shareByKey[otherKey] > shareByKey[statKey] * (1 + 1e-9) then
                gate = math.min(gate, progress[j])
            end
        end
        desired[i] = shareByKey[statKey] * GetTargetLiveMultiplier(profile, statKey, gate)
        sumDesired = sumDesired + desired[i]
    end

    local weights = {}
    for i = 1, #keys do
        weights[i] = sumDesired > 0 and desired[i] * (TARGET_SECONDARY_BUDGET / sumDesired) or desired[i]
    end

    local byKey = {}
    for i, statKey in ipairs(keys) do
        byKey[statKey] = weights[i]
    end
    return byKey
end

local function GetAllocatedSecondaryWeight(profile, statKey)
    if not profile or not statKey or not SECONDARY_TARGET_KEY[statKey] then
        return nil
    end
    local token = GetSecondaryCacheToken(profile)
    if cachedSecondaryToken ~= token or type(cachedSecondaryWeights) ~= "table" then
        cachedSecondaryWeights = BuildAllocatedSecondaryWeights(profile)
        cachedSecondaryToken = token
    end
    return cachedSecondaryWeights[statKey]
end

local function GetPrimarylessTransferWeight(profile)
    return GetFixedPrimaryWeight(profile) * PRIMARYLESS_TRANSFER
end

local function GetTargetDrivenWeight(profile, statKey, equipLocation)
    if not IsGeneratedTargetProfile(profile) then return nil end

    if statKey == "STATVERDICT_ITEM_LEVEL" then
        local weight = TARGET_ITEM_LEVEL_WEIGHT
        if equipLocation == "INVTYPE_TRINKET" then
            weight = weight * TRINKET_ITEM_LEVEL_SCALE
        end
        return weight
    end

    if statKey == profile.primaryStat then
        return GetFixedPrimaryWeight(profile)
    end

    if SECONDARY_TARGET_KEY[statKey] then
        local weight = GetAllocatedSecondaryWeight(profile, statKey)
        if weight == nil then
            local raw = GetRawTargetSecondaryWeight(profile, statKey)
            if not raw then return ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil end
            weight = raw
        end
        if PRIMARYLESS_EQUIP_LOCATIONS[equipLocation] and GetSecondaryRank(profile, statKey) == 1 then
            weight = weight + GetPrimarylessTransferWeight(profile)
        end
        return weight
    end

    return ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil
end

-- The weight of one secondary stat as the verdict scoring really uses it: its fixed share
-- of the budget (base) and the live weight after the character's current stats (live).
-- nil for anything the target-driven scoring does not weigh this way.
function ns.GetScoringSecondaryWeights(profile, statKey)
    ratingOverride = nil  -- never read a half-finished swap's ratings here
    if not IsGeneratedTargetProfile(profile) or not SECONDARY_TARGET_KEY[statKey] then return nil end
    local shares = ns.GetSecondaryBaseShares(profile.secondaryOrder, profile.equalGroups)
    local base = shares[statKey]
    if base == nil then return nil end
    local live = GetAllocatedSecondaryWeight(profile, statKey)
    return base, live or base
end

function ns.GetTrackedProfileStats(profile)
    local keys = {
        [PRISMATIC_SOCKET_STAT_KEY] = true,
    }
    if type(profile) == "table" and type(profile.hiddenTrackedStats) == "table" then
        for statKey in pairs(profile.hiddenTrackedStats) do
            keys[statKey] = true
        end
    end
    if type(profile) == "table" and type(profile.secondaryOrder) == "table" then
        for _, statKey in ipairs(profile.secondaryOrder) do
            keys[statKey] = true
        end
    end
    return keys
end

local function ReadCurrentStatRating(statKey)
    if type(GetCombatRating) ~= "function" then
        return nil
    end

    local ratingID
    if statKey == "ITEM_MOD_CRIT_RATING_SHORT" then
        ratingID = CR_CRIT_MELEE or CR_CRIT_SPELL or CR_CRIT_RANGED
    elseif statKey == "ITEM_MOD_HASTE_RATING_SHORT" then
        ratingID = CR_HASTE_MELEE or CR_HASTE_SPELL or CR_HASTE_RANGED or CR_HASTE
    elseif statKey == "ITEM_MOD_MASTERY_RATING_SHORT" then
        ratingID = CR_MASTERY
    elseif statKey == "ITEM_MOD_VERSATILITY" then
        ratingID = CR_VERSATILITY_DAMAGE_DONE or CR_VERSATILITY_DAMAGE_TAKEN
    end

    if not ratingID then
        return nil
    end

    local ok, value = pcall(GetCombatRating, ratingID)
    if not ok then
        return nil
    end
    if type(ns.SanitizeStatVerdictNumber) == "function" then
        return ns.SanitizeStatVerdictNumber(value)
    end
    local converted = tonumber(value)
    if type(converted) ~= "number" then
        return nil
    end
    if type(issecretvalue) == "function" and issecretvalue(converted) then
        return nil
    end
    return converted
end

-- The rating the live weights work from is read when the gear, spec, talents or level change,
-- not on every buff. A flask, food or combat buff must not move the verdicts of the moment.
local ratingCache = {}

function ns.InvalidateCurrentStatRatings()
    ratingCache = {}
end

function ns.GetCurrentStatRating(statKey)
    local cached = ratingCache[statKey]
    if cached ~= nil then
        return cached
    end
    local value = ReadCurrentStatRating(statKey)
    if value ~= nil then
        ratingCache[statKey] = value
    end
    return value
end

local ratingEventFrame = CreateFrame and CreateFrame("Frame") or nil
if ratingEventFrame then
    for _, eventName in ipairs({
        "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "PLAYER_EQUIPMENT_CHANGED", "PLAYER_LEVEL_UP",
        "PLAYER_SPECIALIZATION_CHANGED", "PLAYER_TALENT_UPDATE", "ACTIVE_TALENT_GROUP_CHANGED",
        "TRAIT_CONFIG_UPDATED", "TRAIT_SUB_TREE_CHANGED",
    }) do
        pcall(ratingEventFrame.RegisterEvent, ratingEventFrame, eventName)
    end
    ratingEventFrame:SetScript("OnEvent", function()
        if ns.ResetContextScan then ns.ResetContextScan() end
        ns.InvalidateCurrentStatRatings()
        if C_Timer and C_Timer.After then
            -- Ratings settle shortly after a gear change; read them again then.
            C_Timer.After(0.3, ns.InvalidateCurrentStatRatings)
        end
    end)
end

local WEAPON_EQUIP_LOCATIONS = {
    INVTYPE_WEAPON = true,
    INVTYPE_2HWEAPON = true,
    INVTYPE_WEAPONMAINHAND = true,
    INVTYPE_WEAPONOFFHAND = true,
    INVTYPE_HOLDABLE = true,
    INVTYPE_RANGED = true,
    INVTYPE_RANGEDRIGHT = true,
}

local function GetWeaponDPSFromStats(rawStats)
    if type(rawStats) ~= "table" then
        return 0
    end

    return tonumber(rawStats.ITEM_MOD_DAMAGE_PER_SECOND_SHORT)
        or tonumber(rawStats.DAMAGE_PER_SECOND_SHORT)
        or tonumber(rawStats.ITEM_MOD_DPS_SHORT)
        or tonumber(rawStats.DPS)
        or 0
end

local function ShouldApplyWeaponStat(itemLink, statKey, slotID)
    if statKey ~= "STATVERDICT_MAIN_HAND_DPS" and statKey ~= "STATVERDICT_OFF_HAND_DPS" then
        return false
    end

    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    if not equipLocation or not WEAPON_EQUIP_LOCATIONS[equipLocation] then
        return false
    end

    if slotID == 16 then
        return statKey == "STATVERDICT_MAIN_HAND_DPS"
    elseif slotID == 17 then
        return statKey == "STATVERDICT_OFF_HAND_DPS"
    end

    if equipLocation == "INVTYPE_WEAPONOFFHAND" then
        return statKey == "STATVERDICT_OFF_HAND_DPS"
    end

    return statKey == "STATVERDICT_MAIN_HAND_DPS"
end

function ns.GetItemStatsForProfile(itemLink, profile, slotID)
    if not itemLink or not profile then
        return nil
    end
    local rawStats = C_Item.GetItemStats(itemLink)
    if type(rawStats) ~= "table" then
        rawStats = {}
    end
    local emptySockets, gemStats = GetSocketState(itemLink, rawStats)
    local tracked = ns.GetTrackedProfileStats(profile)
    local stats = {}
    for statKey in pairs(tracked) do
        if statKey == "STATVERDICT_ITEM_LEVEL" then
            local itemLevel = ns.GetItemLevel and ns.GetItemLevel(itemLink) or nil
            stats[statKey] = tonumber(itemLevel) or 0
        elseif statKey == "STATVERDICT_ARMOR" then
            stats[statKey] = tonumber(rawStats.RESISTANCE0_NAME) or tonumber(rawStats.ITEM_MOD_ARMOR_SHORT) or tonumber(rawStats.ARMOR) or 0
        elseif statKey == "STATVERDICT_MAIN_HAND_DPS" or statKey == "STATVERDICT_OFF_HAND_DPS" then
            if ShouldApplyWeaponStat(itemLink, statKey, slotID) then
                stats[statKey] = GetWeaponDPSFromStats(rawStats)
            else
                stats[statKey] = 0
            end
        elseif statKey == PRISMATIC_SOCKET_STAT_KEY then
            stats[statKey] = emptySockets
        else
            stats[statKey] = (tonumber(rawStats[statKey]) or 0) + (tonumber(gemStats[statKey]) or 0)
        end
    end
    return stats
end

local function GetAdjustedWeight(profile, statKey)
    local weight = ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil
    if not weight or weight == 0 then
        return nil
    end
    return ns.GetSoftCapAdjustedWeight and ns.GetSoftCapAdjustedWeight(profile, statKey, weight) or weight
end

local function RoundScoreWeight(weight)
    weight = tonumber(weight)
    if not weight then return nil end
    if weight >= 0 then
        return math.floor(weight * 100 + 0.5) / 100
    end
    return math.ceil(weight * 100 - 0.5) / 100
end

local function ScoreStatAmount(profile, statKey, amount, useSoftCap, equipLocation, itemStats)
    if not amount or amount == 0 then
        return 0
    end

    if statKey == PRISMATIC_SOCKET_STAT_KEY then
        -- Potential socket value is not immediate character power. Only actual
        -- gem stats are scored, so an empty socket cannot masquerade as filled.
        return 0
    end

    -- Generated ClassCodex profiles keep fixed item-level + primary anchors and only
    -- redistribute secondaries inside TARGET_SECONDARY_BUDGET (with capped live pressure).
    -- Stat Progress "Weight" rows are secondaries-only and can inflate far enough to
    -- overturn large ilvl/primary gaps — so they must not drive upgrade scoring here.
    local weight = nil
    if IsGeneratedTargetProfile(profile) then
        weight = GetTargetDrivenWeight(profile, statKey, equipLocation)
    end

    -- Non-generated profiles may use the Stat Progress live-Weight cache for secondaries.
    -- Never let that cache override item level or the profile primary (hidden #1 / #1.1).
    if weight == nil
        and useSoftCap
        and ns.ResolveStatAuditProfileID
        and ns.GetCachedStatAuditLiveModifier
        and statKey ~= "STATVERDICT_ITEM_LEVEL"
        and not (profile and profile.primaryStat and statKey == profile.primaryStat)
    then
        local profileID = ns.ResolveStatAuditProfileID(nil, profile)
        weight = profileID and ns.GetCachedStatAuditLiveModifier(profileID, statKey) or nil
        if weight ~= nil and ns.GetSlotContextAdjustedWeight then
            weight = ns.GetSlotContextAdjustedWeight(profile, statKey, weight, equipLocation)
        end
    end

    if weight == nil and statKey == "STATVERDICT_ITEM_LEVEL" then
        weight = ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil
        if useSoftCap and weight and ns.GetStatVerdictItemLevelWeightScale then
            weight = weight * (tonumber(ns.GetStatVerdictItemLevelWeightScale(profile)) or 1)
        end
    end

    if weight == nil then
        local targetDrivenWeight = GetTargetDrivenWeight(profile, statKey, equipLocation)
        if targetDrivenWeight ~= nil then
            weight = targetDrivenWeight
        elseif useSoftCap and ns.GetDeltaAdjustedStatWeight then
            weight = ns.GetDeltaAdjustedStatWeight(profile, statKey, amount, nil, equipLocation)
        else
            weight = useSoftCap and GetAdjustedWeight(profile, statKey)
                or (ns.GetStatWeight and ns.GetStatWeight(profile, statKey) or nil)
            if weight and ns.GetSlotContextAdjustedWeight then
                weight = ns.GetSlotContextAdjustedWeight(profile, statKey, weight, equipLocation)
            end
        end
    end

    if not weight or weight == 0 then
        return 0
    end
    weight = RoundScoreWeight(weight)
    return amount * weight
end

function ns.GetItemProfileScore(itemLink, profile, slotID)
    local stats = ns.GetItemStatsForProfile(itemLink, profile, slotID)
    if not stats then
        return nil
    end
    local total = 0
    local rows = {}
    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    for statKey, amount in pairs(stats) do
        local points = ScoreStatAmount(profile, statKey, amount, false, equipLocation, stats)
        if points ~= 0 then
            total = total + points
            rows[#rows + 1] = {
                statKey = statKey,
                statName = ns.StatNames[statKey] or statKey,
                amount = amount,
                points = points,
                weight = amount ~= 0 and (points / amount) or nil,
            }
        end
    end
    local referenceBonus = ns.GetItemReferenceBonus and ns.GetItemReferenceBonus(itemLink, profile) or 0
    if referenceBonus and referenceBonus ~= 0 then
        total = total + referenceBonus
        rows[#rows + 1] = {
            statKey = "STATVERDICT_REFERENCE_BONUS",
            statName = "Reference Bonus",
            amount = 1,
            points = referenceBonus,
            weight = referenceBonus,
        }
    end
    table.sort(rows, function(a, b)
        return math.abs(a.points) > math.abs(b.points)
    end)
    return total, rows, stats
end

-- Item level wins, in both directions: a piece with clearly more item level has more primary stat and
-- more of every secondary, so it is an upgrade whatever its split of secondaries, and a piece with
-- clearly less item level is never one. "Clearly" means 10 or more item levels; smaller steps are left to
-- the stats (a few item levels are worth less than a much better split of the secondaries).
-- Jewelry and trinkets are the exception: they carry no primary stat, so a lower item level with much
-- better stats can beat a higher one there. The two directions use the same number, so the verdict of
-- A over B stays the opposite of B over A.
local ITEM_LEVEL_WIN_FREE_GAP = 9
local NO_ITEM_LEVEL_WIN = {
    INVTYPE_NECK = true,
    INVTYPE_FINGER = true,
    INVTYPE_TRINKET = true,
}

-- The points a gap of item levels (beyond the free gap) is worth: 3 at 10 item levels, then 5 per item
-- level up to 20 and 8 above.
local function ItemLevelGapPoints(gap)
    local points = (math.min(gap, 10) - ITEM_LEVEL_WIN_FREE_GAP) * 3
    if gap > 10 then points = points + (math.min(gap, 20) - 10) * 5 end
    if gap > 20 then points = points + (gap - 20) * 8 end
    return points
end

local function ApplyItemLevelWinGuard(total, rows, candidateStats, equippedStats, profile, equipLocation)
    if not IsGeneratedTargetProfile(profile) then return total end
    if NO_ITEM_LEVEL_WIN[equipLocation] then return total end
    if type(candidateStats) ~= "table" or type(equippedStats) ~= "table" then return total end

    local candidateItemLevel = tonumber(candidateStats.STATVERDICT_ITEM_LEVEL) or 0
    local equippedItemLevel = tonumber(equippedStats.STATVERDICT_ITEM_LEVEL) or 0
    local gap = candidateItemLevel - equippedItemLevel
    if math.abs(gap) <= ITEM_LEVEL_WIN_FREE_GAP then return total end

    local points = ItemLevelGapPoints(math.abs(gap))
    local guarded
    if gap > 0 then
        -- Clearly more item level: an upgrade however small its points are (the comparison reads this mark; it
        -- would otherwise ask for 1% of the equipped score, which a clear item level win can fall short of).
        rows.itemLevelWin = true
        if total >= points then return total end
        guarded = points
    else
        if total <= -points then return total end
        guarded = -points
    end
    local change = guarded - total
    rows[#rows + 1] = {
        statKey = "STATVERDICT_ITEM_LEVEL_GUARD",
        statName = "Item Level Guard",
        amount = 1,
        points = math.abs(change),
        signedPoints = change,
        weight = change,
        positive = change > 0,
    }
    return guarded
end

-- Small primary deficit may lose to clearly better #1+#2 secondaries (sidegrades).
-- Large primary / ilvl gaps never get this forgiveness.
local function ApplySoftPrimaryGapForgiveness(total, rows, candidateStats, equippedStats, profile)
    if not IsGeneratedTargetProfile(profile) then return total end
    if type(candidateStats) ~= "table" or type(equippedStats) ~= "table" then return total end

    local primaryKey = profile.primaryStat
    if not primaryKey then return total end

    local primaryDelta = (tonumber(candidateStats[primaryKey]) or 0) - (tonumber(equippedStats[primaryKey]) or 0)
    if primaryDelta == 0 or math.abs(primaryDelta) > SOFT_PRIMARY_GAP then
        return total
    end

    local candidateItemLevel = tonumber(candidateStats.STATVERDICT_ITEM_LEVEL) or 0
    local equippedItemLevel = tonumber(equippedStats.STATVERDICT_ITEM_LEVEL) or 0
    if math.abs(candidateItemLevel - equippedItemLevel) > SOFT_PRIMARY_ILVL_SLACK then
        return total
    end

    -- Judged the same from both sides: the piece with the smaller primary is forgiven (+) when its top two
    -- secondaries make up for it, and the piece with the larger primary loses the same amount (-).
    local direction = primaryDelta < 0 and 1 or -1
    local primaryPoints = nil
    local topTwoPoints = 0
    for _, row in ipairs(rows) do
        if type(row) == "table" then
            if row.statKey == primaryKey then
                primaryPoints = (tonumber(row.signedPoints) or 0) * direction
            else
                local rank = GetSecondaryRank(profile, row.statKey)
                if rank and rank <= 2 then
                    topTwoPoints = topTwoPoints + (tonumber(row.signedPoints) or 0) * direction
                end
            end
        end
    end

    if not primaryPoints or primaryPoints >= 0 or topTwoPoints <= 0 then
        return total
    end

    local keptPenalty = (-primaryPoints) * SOFT_PRIMARY_PENALTY_KEEP
    if topTwoPoints < keptPenalty then
        return total
    end

    local forgiveness = (-primaryPoints) * (1 - SOFT_PRIMARY_PENALTY_KEEP) * direction
    if forgiveness == 0 then
        return total
    end

    rows[#rows + 1] = {
        statKey = "STATVERDICT_SOFT_PRIMARY_GAP",
        statName = "Soft Primary Gap",
        amount = math.abs(primaryDelta),
        points = math.abs(forgiveness),
        signedPoints = forgiveness,
        weight = forgiveness,
        positive = forgiveness > 0,
    }
    return total + forgiveness
end

function ns.GetWeightedDeltaScore(candidateLink, equippedLink, profile, slotID)
    local candidateStats = ns.GetItemStatsForProfile(candidateLink, profile, slotID)
    local equippedStats = equippedLink and ns.GetItemStatsForProfile(equippedLink, profile, slotID) or {}
    if not candidateStats or not equippedStats then
        return nil, {}
    end

    local tracked = ns.GetTrackedProfileStats(profile)
    local total = 0
    local rows = {}
    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(candidateLink) or nil

    BeginSwapRatings(profile, candidateStats, equippedStats)
    for statKey in pairs(tracked) do
        local delta = (candidateStats[statKey] or 0) - (equippedStats[statKey] or 0)
        if delta ~= 0 then
            -- What the swap really adds: rating loses value above the first cut, so a secondary
            -- stat is counted as the change in its effective value from now to after the swap.
            local scored = delta
            if SECONDARY_TARGET_KEY[statKey] and ns.GetEffectiveRatingDelta then
                scored = ns.GetEffectiveRatingDelta(statKey, GetPlayerRatingForScoring(profile, statKey), delta) or delta
            end
            local points = ScoreStatAmount(profile, statKey, scored, true, equipLocation, candidateStats)
            total = total + points
            rows[#rows + 1] = {
                statKey = statKey,
                statName = ns.StatNames[statKey] or statKey,
                amount = math.abs(delta),
                points = math.abs(points),
                signedPoints = points,
                weight = delta ~= 0 and (points / delta) or nil,
                positive = delta > 0,
            }
        end
    end
    EndSwapRatings()

    local candidateReferenceBonus = ns.GetItemReferenceBonus and ns.GetItemReferenceBonus(candidateLink, profile) or 0
    local equippedReferenceBonus = equippedLink and ns.GetItemReferenceBonus and ns.GetItemReferenceBonus(equippedLink, profile) or 0
    local referenceDelta = (candidateReferenceBonus or 0) - (equippedReferenceBonus or 0)
    if referenceDelta ~= 0 then
        total = total + referenceDelta
        rows[#rows + 1] = {
            statKey = "STATVERDICT_REFERENCE_BONUS",
            statName = "Reference Bonus",
            amount = math.abs(referenceDelta),
            points = math.abs(referenceDelta),
            signedPoints = referenceDelta,
            weight = 1,
            positive = referenceDelta > 0,
        }
    end

    total = ApplySoftPrimaryGapForgiveness(total, rows, candidateStats, equippedStats, profile)
    total = ApplyItemLevelWinGuard(total, rows, candidateStats, equippedStats, profile, equipLocation)

    table.sort(rows, function(a, b)
        return a.points > b.points
    end)

    return total, rows
end

function ns.GetWeightedDeltaScoreForEquippedSet(candidateLink, equippedItems, profile, candidateSlotID)
    local candidateStats = ns.GetItemStatsForProfile(candidateLink, profile, candidateSlotID)
    if not candidateStats or type(equippedItems) ~= "table" then
        return nil, {}
    end

    local tracked = ns.GetTrackedProfileStats(profile)
    local equippedStats = {}
    local itemLevelTotal, itemLevelCount = 0, 0
    local equippedReferenceBonus = 0
    for _, entry in ipairs(equippedItems) do
        local link = entry and entry.link
        local slotID = entry and entry.slotID
        local stats = link and ns.GetItemStatsForProfile(link, profile, slotID) or nil
        if type(stats) == "table" then
            for statKey in pairs(tracked) do
                if statKey == "STATVERDICT_ITEM_LEVEL" then
                    local itemLevel = tonumber(stats[statKey])
                    if itemLevel then
                        itemLevelTotal = itemLevelTotal + itemLevel
                        itemLevelCount = itemLevelCount + 1
                    end
                else
                    equippedStats[statKey] = (equippedStats[statKey] or 0) + (tonumber(stats[statKey]) or 0)
                end
            end
        end
        if link and ns.GetItemReferenceBonus then
            equippedReferenceBonus = equippedReferenceBonus + (ns.GetItemReferenceBonus(link, profile) or 0)
        end
    end
    if itemLevelCount > 0 then
        equippedStats.STATVERDICT_ITEM_LEVEL = itemLevelTotal / itemLevelCount
    end

    local total = 0
    local rows = {}
    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(candidateLink) or nil

    BeginSwapRatings(profile, candidateStats, equippedStats)
    for statKey in pairs(tracked) do
        local delta = (candidateStats[statKey] or 0) - (equippedStats[statKey] or 0)
        if delta ~= 0 then
            local scored = delta
            if SECONDARY_TARGET_KEY[statKey] and ns.GetEffectiveRatingDelta then
                scored = ns.GetEffectiveRatingDelta(statKey, GetPlayerRatingForScoring(profile, statKey), delta) or delta
            end
            local points = ScoreStatAmount(profile, statKey, scored, true, equipLocation, candidateStats)
            total = total + points
            rows[#rows + 1] = {
                statKey = statKey,
                statName = ns.StatNames[statKey] or statKey,
                amount = math.abs(delta),
                points = math.abs(points),
                signedPoints = points,
                weight = delta ~= 0 and (points / delta) or nil,
                positive = delta > 0,
            }
        end
    end
    EndSwapRatings()

    local candidateReferenceBonus = ns.GetItemReferenceBonus and ns.GetItemReferenceBonus(candidateLink, profile) or 0
    local referenceDelta = (candidateReferenceBonus or 0) - equippedReferenceBonus
    if referenceDelta ~= 0 then
        total = total + referenceDelta
        rows[#rows + 1] = {
            statKey = "STATVERDICT_REFERENCE_BONUS",
            statName = "Reference Bonus",
            amount = math.abs(referenceDelta),
            points = math.abs(referenceDelta),
            signedPoints = referenceDelta,
            weight = 1,
            positive = referenceDelta > 0,
        }
    end

    total = ApplySoftPrimaryGapForgiveness(total, rows, candidateStats, equippedStats, profile)
    total = ApplyItemLevelWinGuard(total, rows, candidateStats, equippedStats, profile, equipLocation)

    table.sort(rows, function(a, b)
        return a.points > b.points
    end)

    return total, rows, equippedStats
end

function ns.GetDeltaRows(candidateLink, equippedLink, profile, slotID)
    local _, rows = ns.GetWeightedDeltaScore(candidateLink, equippedLink, profile, slotID)
    return rows or {}
end

function ns.GetUpgradePercent(deltaScore, equippedScore, profile, candidateLink, equippedLink)
    if not deltaScore or not equippedScore then
        return nil
    end

    equippedScore = tonumber(equippedScore)
    if not equippedScore or equippedScore == 0 then
        return nil
    end

    local percent = (deltaScore / math.abs(equippedScore)) * 100
    local model = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.percent or nil
    local maxPercent = model and tonumber(model.maxDisplayPercent) or nil
    if maxPercent and percent > maxPercent then
        percent = maxPercent
    elseif maxPercent and percent < -maxPercent then
        percent = -maxPercent
    end

    return percent
end
