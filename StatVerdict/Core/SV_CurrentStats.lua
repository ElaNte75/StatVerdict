local addonName, ns = ...

local STAT_INDEX_BY_KEY = {
    ITEM_MOD_STRENGTH_SHORT = 1,
    ITEM_MOD_AGILITY_SHORT = 2,
    ITEM_MOD_STAMINA_SHORT = 3,
    ITEM_MOD_INTELLECT_SHORT = 4,
}

local RATING_ID_BY_KEY = {
    ITEM_MOD_CRIT_RATING_SHORT = function() return CR_CRIT_MELEE or CR_CRIT_SPELL or CR_CRIT_RANGED end,
    ITEM_MOD_HASTE_RATING_SHORT = function() return CR_HASTE_MELEE or CR_HASTE_SPELL or CR_HASTE_RANGED or CR_HASTE end,
    ITEM_MOD_MASTERY_RATING_SHORT = function() return CR_MASTERY end,
    ITEM_MOD_VERSATILITY = function() return CR_VERSATILITY_DAMAGE_DONE or CR_VERSATILITY_DAMAGE_TAKEN end,
    ITEM_MOD_AVOIDANCE_RATING_SHORT = function() return CR_AVOIDANCE end,
    ITEM_MOD_LIFESTEAL = function() return CR_LIFESTEAL end,
    ITEM_MOD_SPEED = function() return CR_SPEED end,
}

local SHAPESHIFT_GRACE_SECONDS = 0.35
local lastKnownCasterStamina = nil
local lastKnownCasterArmor = nil
local lastShapeshiftChangeAt = 0

local EQUIPPED_GEAR_STAT_SLOTS = {
    1, 2, 3, 5, 6, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17,
}

local GetStableStaminaValue
local GetArmorValue
local GetStableArmorValue

local function SafeNumber(value)
    if type(ns.SanitizeStatVerdictNumber) == "function" then
        return ns.SanitizeStatVerdictNumber(value)
    end
    value = tonumber(value)
    if not value then return nil end
    if type(issecretvalue) == "function" and issecretvalue(value) then
        return nil
    end
    -- Protect NaN check with pcall to avoid taint errors in combat
    local ok, isNotNaN = pcall(function() return value == value end)
    if ok and isNotNaN then return value end
    return nil
end

local function GetUnitStatValue(statKey)
    local statIndex = STAT_INDEX_BY_KEY[statKey]
    if not statIndex or type(UnitStat) ~= "function" then return nil end
    local base, effective = UnitStat("player", statIndex)
    return SafeNumber(effective) or SafeNumber(base)
end

function ns.GetLiveCharacterSheetStatValue(statKey)
    if statKey == "STATVERDICT_ITEM_LEVEL" then
        if type(GetAverageItemLevel) == "function" then
            local _, equipped = GetAverageItemLevel()
            return SafeNumber(equipped)
        end
        return nil
    end
    if statKey == "STATVERDICT_ARMOR" then return GetStableArmorValue(GetArmorValue()) end
    local unitValue = GetUnitStatValue(statKey)
    if statKey == "ITEM_MOD_STAMINA_SHORT" then
        unitValue = GetStableStaminaValue(unitValue)
    end
    if unitValue ~= nil then return unitValue end
    if type(GetCombatRating) == "function" then
        local getter = RATING_ID_BY_KEY[statKey]
        local ratingID = getter and getter()
        if ratingID then return SafeNumber(GetCombatRating(ratingID)) end
    end
    return nil
end

function ns.GetCurrentCharacterSheetStatValue(statKey)
    local snapshotValue = ns.GetActiveSnapshotDisplayStatValue and ns.GetActiveSnapshotDisplayStatValue(statKey) or nil
    if snapshotValue ~= nil then return snapshotValue end
    return ns.GetLiveCharacterSheetStatValue(statKey)
end

local function GetEquippedGearStatValue(statKey)
    if not statKey or type(GetInventoryItemLink) ~= "function" then return nil end
    if type(C_Item) ~= "table" or type(C_Item.GetItemStats) ~= "function" then return nil end

    local total = 0
    local found = false
    for _, slotID in ipairs(EQUIPPED_GEAR_STAT_SLOTS) do
        local itemLink = GetInventoryItemLink("player", slotID)
        if itemLink then
            local stats = C_Item.GetItemStats(itemLink)
            local amount = type(stats) == "table" and SafeNumber(stats[statKey]) or nil
            if amount then
                total = total + amount
                found = true
            end
            if type(C_Item.GetItemNumSockets) == "function" and type(C_Item.GetItemGem) == "function" then
                local socketCount = SafeNumber(C_Item.GetItemNumSockets(itemLink)) or 0
                for socketIndex = 1, socketCount do
                    local _, gemLink = C_Item.GetItemGem(itemLink, socketIndex)
                    local gemStats = gemLink and C_Item.GetItemStats(gemLink) or nil
                    local gemAmount = type(gemStats) == "table" and SafeNumber(gemStats[statKey]) or nil
                    if gemAmount then
                        total = total + gemAmount
                        found = true
                    end
                end
            end
        end
    end
    if found then return total end
    return nil
end

local function IsDruidCasterForm()
    if type(UnitClass) ~= "function" then return false end
    local _, classFile = UnitClass("player")
    if classFile ~= "DRUID" then return false end
    local formIndex = (type(GetShapeshiftForm) == "function") and (GetShapeshiftForm() or 0) or 0
    return formIndex == 0
end

function ns.IsAuditDruidNonCasterForm()
    if type(UnitClass) ~= "function" then return false end
    local _, classFile = UnitClass("player")
    if classFile ~= "DRUID" then return false end
    return not IsDruidCasterForm()
end

GetStableStaminaValue = function(rawStamina)
    local value = SafeNumber(rawStamina)
    if not value then return nil end
    local classFile = nil
    if type(UnitClass) == "function" then
        _, classFile = UnitClass("player")
    end
    if classFile ~= "DRUID" then
        return value
    end
    local now = (type(GetTime) == "function") and GetTime() or 0
    if IsDruidCasterForm() then
        if ns.IsAuditShapeshiftGraceActive() and lastKnownCasterStamina then
            return lastKnownCasterStamina
        end
        lastKnownCasterStamina = value
        return value
    end
    return lastKnownCasterStamina or value
end

GetArmorValue = function()
    if type(UnitArmor) ~= "function" then return nil end
    local base, effective = UnitArmor("player")
    return SafeNumber(effective) or SafeNumber(base)
end

GetStableArmorValue = function(rawArmor)
    local value = SafeNumber(rawArmor)
    if not value then return nil end
    if type(UnitClass) ~= "function" then return value end
    local _, classFile = UnitClass("player")
    if classFile ~= "DRUID" then
        return value
    end
    if IsDruidCasterForm() then
        if ns.IsAuditShapeshiftGraceActive() and lastKnownCasterArmor then
            return lastKnownCasterArmor
        end
        lastKnownCasterArmor = value
        return value
    end
    return lastKnownCasterArmor or value
end

function ns.GetCurrentAuditRatingValue(statKey)
    local snapshotValue = ns.GetActiveSnapshotStatValue and ns.GetActiveSnapshotStatValue(statKey) or nil
    if snapshotValue ~= nil then return snapshotValue end
    if type(GetCombatRating) ~= "function" then return nil end
    local getter = RATING_ID_BY_KEY[statKey]
    local ratingID = getter and getter()
    if not ratingID then return nil end
    return SafeNumber(GetCombatRating(ratingID))
end

function ns.IsAuditSecondaryStatKey(statKey)
    return RATING_ID_BY_KEY[statKey] ~= nil
end

local function GetWeaponDPS(isOffHand)
    if type(UnitDamage) ~= "function" or type(UnitAttackSpeed) ~= "function" then return nil end
    local mainLow, mainHigh, offLow, offHigh = UnitDamage("player")
    local mainSpeed, offSpeed = UnitAttackSpeed("player")
    local low, high, speed
    if isOffHand then
        low, high, speed = SafeNumber(offLow), SafeNumber(offHigh), SafeNumber(offSpeed)
    else
        low, high, speed = SafeNumber(mainLow), SafeNumber(mainHigh), SafeNumber(mainSpeed)
    end
    if low and high and speed and speed > 0 then return ((low + high) / 2) / speed end
    return nil
end

function ns.GetCurrentAuditStatValue(statKey)
    local snapshotValue = ns.GetActiveSnapshotStatValue and ns.GetActiveSnapshotStatValue(statKey) or nil
    if snapshotValue ~= nil then return snapshotValue end
    if statKey == "STATVERDICT_ITEM_LEVEL" then
        if type(GetAverageItemLevel) == "function" then
            local _, equipped = GetAverageItemLevel()
            return SafeNumber(equipped)
        end
        return nil
    end
    if statKey == "STATVERDICT_MAIN_HAND_DPS" then return GetWeaponDPS(false) end
    if statKey == "STATVERDICT_OFF_HAND_DPS" then return GetWeaponDPS(true) end
    if statKey == "STATVERDICT_ARMOR" then return GetStableArmorValue(GetArmorValue()) end
    if STAT_INDEX_BY_KEY[statKey] then
        return GetEquippedGearStatValue(statKey) or GetUnitStatValue(statKey)
    end
    local unitVal = GetUnitStatValue(statKey)
    if statKey == "ITEM_MOD_STAMINA_SHORT" then
        unitVal = GetStableStaminaValue(unitVal)
    end
    return unitVal or ns.GetCurrentAuditRatingValue(statKey)
end

function ns.MarkAuditShapeshiftChanged()
    lastShapeshiftChangeAt = (type(GetTime) == "function") and GetTime() or 0
end

function ns.IsAuditShapeshiftGraceActive()
    local now = (type(GetTime) == "function") and GetTime() or 0
    return (now - (lastShapeshiftChangeAt or 0)) < SHAPESHIFT_GRACE_SECONDS
end
