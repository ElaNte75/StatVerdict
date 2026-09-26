local addonName, ns = ...

local ARMOR_EQUIP_LOCATIONS = {
    INVTYPE_HEAD = true,
    INVTYPE_SHOULDER = true,
    INVTYPE_CHEST = true,
    INVTYPE_ROBE = true,
    INVTYPE_WAIST = true,
    INVTYPE_LEGS = true,
    INVTYPE_FEET = true,
    INVTYPE_WRIST = true,
    INVTYPE_HAND = true,
}

local ARMOR_PREFERENCE_BY_CLASS = {
    MAGE = LE_ITEM_ARMOR_CLOTH or 1,
    PRIEST = LE_ITEM_ARMOR_CLOTH or 1,
    WARLOCK = LE_ITEM_ARMOR_CLOTH or 1,
    DEMONHUNTER = LE_ITEM_ARMOR_LEATHER or 2,
    DRUID = LE_ITEM_ARMOR_LEATHER or 2,
    MONK = LE_ITEM_ARMOR_LEATHER or 2,
    ROGUE = LE_ITEM_ARMOR_LEATHER or 2,
    EVOKER = LE_ITEM_ARMOR_MAIL or 3,
    HUNTER = LE_ITEM_ARMOR_MAIL or 3,
    SHAMAN = LE_ITEM_ARMOR_MAIL or 3,
    DEATHKNIGHT = LE_ITEM_ARMOR_PLATE or 4,
    PALADIN = LE_ITEM_ARMOR_PLATE or 4,
    WARRIOR = LE_ITEM_ARMOR_PLATE or 4,
}

local OFFHAND_EQUIP_LOCATIONS = {
    INVTYPE_HOLDABLE = true,
    INVTYPE_SHIELD = true,
    INVTYPE_WEAPONOFFHAND = true,
}

local TWO_HAND_EQUIP_LOCATIONS = {
    INVTYPE_2HWEAPON = true,
    INVTYPE_RANGED = true,
    INVTYPE_RANGEDRIGHT = true,
}

local WEAPON_CLASS_ID = LE_ITEM_CLASS_WEAPON or 2
local ARMOR_CLASS_ID = LE_ITEM_CLASS_ARMOR or 4
local SHIELD_SUBCLASS_ID = LE_ITEM_ARMOR_SHIELD or 6

local PRIMARY_STAT_KEYS = {
    ITEM_MOD_STRENGTH_SHORT = true,
    ITEM_MOD_AGILITY_SHORT = true,
    ITEM_MOD_INTELLECT_SHORT = true,
}

local WEAPON_SUBCLASS_BY_CLASS = {
    DEATHKNIGHT = { [0] = true, [1] = true, [4] = true, [5] = true, [6] = true, [7] = true, [8] = true },
    DEMONHUNTER = { [0] = true, [7] = true, [9] = true, [13] = true, [15] = true },
    DRUID = { [4] = true, [5] = true, [6] = true, [10] = true, [13] = true, [15] = true },
    EVOKER = { [4] = true, [7] = true, [10] = true, [13] = true, [15] = true },
    HUNTER = { [0] = true, [1] = true, [2] = true, [3] = true, [6] = true, [7] = true, [8] = true, [10] = true, [13] = true, [15] = true, [18] = true },
    MAGE = { [7] = true, [10] = true, [15] = true, [19] = true },
    MONK = { [0] = true, [4] = true, [6] = true, [7] = true, [10] = true, [13] = true },
    PALADIN = { [0] = true, [1] = true, [4] = true, [5] = true, [6] = true, [7] = true, [8] = true },
    PRIEST = { [4] = true, [10] = true, [15] = true, [19] = true },
    ROGUE = { [2] = true, [3] = true, [4] = true, [7] = true, [13] = true, [15] = true, [18] = true },
    SHAMAN = { [0] = true, [1] = true, [4] = true, [5] = true, [10] = true, [13] = true, [15] = true },
    WARLOCK = { [7] = true, [10] = true, [15] = true, [19] = true },
    WARRIOR = { [0] = true, [1] = true, [2] = true, [3] = true, [4] = true, [5] = true, [6] = true, [7] = true, [8] = true, [10] = true, [13] = true, [15] = true, [18] = true },
}

local SHIELD_ALLOWED_BY_CLASS = {
    PALADIN = true,
    SHAMAN = true,
    WARRIOR = true,
}

local SHIELD_ALLOWED_BY_SPEC = {
    -- Paladin
    [65] = true,  -- Holy
    [66] = true,  -- Protection
    [70] = false, -- Retribution
    -- Warrior
    [71] = false, -- Arms
    [72] = false, -- Fury
    [73] = true,  -- Protection
    -- Shaman
    [262] = true,  -- Elemental
    [263] = false, -- Enhancement
    [264] = true,  -- Restoration
}

local OFFHAND_MODE_BY_SPEC = {
    -- Paladin
    [65] = "SHIELD",
    [66] = "SHIELD",
    [70] = "NONE",
    -- Warrior
    [71] = "NONE",
    [72] = "DUAL_WIELD",
    [73] = "SHIELD",
    -- Shaman
    [262] = "SHIELD",
    [263] = "DUAL_WIELD",
    [264] = "SHIELD",
}

local itemRuleMetadataCache = {}
local EQUIPMENT_SLOTS = {
    1, 2, 3, 5, 6, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17,
}
local TIER_ARMOR_SLOTS = {
    [1] = true,  -- Head
    [3] = true,  -- Shoulder
    [5] = true,  -- Chest
    [7] = true,  -- Legs
    [10] = true, -- Hands
}

local function StripText(text)
    if type(text) ~= "string" then return nil end
    text = text:gsub("|c%x%x%x%x%x%x%x%x", "")
    text = text:gsub("|r", "")
    return text
end

local function BoolResult(ok, reason)
    return {
        allowed = ok and true or false,
        reason = reason,
    }
end

local function GetEquippedLink(slotID, profile)
    if not slotID then return nil end
    local useSnapshot = ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile)
        and ns.HasEquipmentSnapshot and ns.HasEquipmentSnapshot(profile)
    if useSnapshot then
        return ns.GetSnapshotEquippedLink and ns.GetSnapshotEquippedLink(profile, slotID) or nil
    end
    return GetInventoryItemLink("player", slotID)
end

local function GetItemInfoInstantSafe(itemLink)
    if not itemLink or type(C_Item) ~= "table" or type(C_Item.GetItemInfoInstant) ~= "function" then
        return nil
    end
    local ok, itemID, itemType, itemSubType, equipLocation, icon, classID, subclassID = pcall(C_Item.GetItemInfoInstant, itemLink)
    if not ok then
        return nil
    end
    return itemID, itemType, itemSubType, equipLocation, icon, classID, subclassID
end

local function IsCosmeticOnlyItem(itemLink)
    if not itemLink then return false end
    local itemID = GetItemInfoInstantSafe(itemLink)
    local itemInfo = itemID or itemLink

    if type(C_Item) == "table" and type(C_Item.IsCosmeticItem) == "function" then
        local ok, result = pcall(C_Item.IsCosmeticItem, itemInfo)
        if ok and result == true then return true end
    elseif type(IsCosmeticItem) == "function" then
        local ok, result = pcall(IsCosmeticItem, itemInfo)
        if ok and result == true then return true end
    end

    if type(C_TooltipInfo) == "table" and type(C_TooltipInfo.GetHyperlink) == "function" then
        local ok, data = pcall(C_TooltipInfo.GetHyperlink, itemLink)
        local cosmeticLabel = StripText(ITEM_COSMETIC or "Cosmetic")
        cosmeticLabel = cosmeticLabel and cosmeticLabel:lower() or "cosmetic"
        if ok and type(data) == "table" and type(data.lines) == "table" then
            for _, line in ipairs(data.lines) do
                local text = StripText(line and line.leftText)
                if text and text:lower() == cosmeticLabel then
                    return true
                end
            end
        end
    end
    return false
end

local function GetProfileClass(profile)
    local classFile = type(profile) == "table" and profile.class or nil
    if type(classFile) ~= "string" or classFile == "" then
        if type(UnitClass) == "function" then
            _, classFile = UnitClass("player")
        end
    end
    return classFile
end

local function GetOffhandMode(profile)
    local specID = tonumber(profile and profile.specID)
    return specID and OFFHAND_MODE_BY_SPEC[specID] or nil
end

local function CanDualWieldTwoHanded(profile)
    return tonumber(profile and profile.specID) == 72
end

local function GetPreferredArmor(profile)
    local preferredArmor = tonumber(profile and profile.armorPreference)
    if preferredArmor then return preferredArmor end

    local classFile = GetProfileClass(profile)
    return classFile and ARMOR_PREFERENCE_BY_CLASS[classFile] or nil
end

local function IsPoorQualityItem(itemLink)
    local quality = ns.GetItemQuality and ns.GetItemQuality(itemLink) or nil
    if quality == nil then return false end
    return quality == (LE_ITEM_QUALITY_POOR or 0)
end

local function IsEquippableCandidate(itemLink)
    if type(C_Item) == "table" and type(C_Item.IsEquippableItem) == "function" then
        local ok = C_Item.IsEquippableItem(itemLink)
        return ok ~= false
    elseif type(IsEquippableItem) == "function" then
        local ok = IsEquippableItem(itemLink)
        return ok ~= false
    end
    return true
end

local function IsUsableArmorType(itemLink, profile)
    if not itemLink or type(profile) ~= "table" then return true end
    local itemID, _, _, equipLocation, _, classID, subclassID = GetItemInfoInstantSafe(itemLink)
    if not itemID then return true end
    if tonumber(classID) ~= ARMOR_CLASS_ID then return true end

    local classFile = GetProfileClass(profile)
    if equipLocation == "INVTYPE_SHIELD" or tonumber(subclassID) == SHIELD_SUBCLASS_ID then
        local specID = tonumber(profile and profile.specID)
        if specID and SHIELD_ALLOWED_BY_SPEC[specID] ~= nil then
            return SHIELD_ALLOWED_BY_SPEC[specID]
        end
        return classFile and SHIELD_ALLOWED_BY_CLASS[classFile] or false
    end

    if not ARMOR_EQUIP_LOCATIONS[equipLocation] then return true end

    local preferredArmor = GetPreferredArmor(profile)
    if not preferredArmor then return true end
    local itemArmor = tonumber(subclassID)
    if not itemArmor then return true end
    return itemArmor == preferredArmor
end

local function IsUsableWeaponType(itemLink, profile)
    if not itemLink or type(profile) ~= "table" then return true end
    local itemID, _, _, _, _, classID, subclassID = GetItemInfoInstantSafe(itemLink)
    if not itemID then return true end
    if tonumber(classID) ~= WEAPON_CLASS_ID then return true end

    local classFile = GetProfileClass(profile)
    local allowed = classFile and WEAPON_SUBCLASS_BY_CLASS[classFile] or nil
    if not allowed then return true end
    return allowed[tonumber(subclassID)] == true
end

local function IsWeaponPrimaryStatCompatible(itemLink, profile)
    if not itemLink or type(profile) ~= "table" then return true end
    local itemID, _, _, _, _, classID = GetItemInfoInstantSafe(itemLink)
    if not itemID or tonumber(classID) ~= WEAPON_CLASS_ID then return true end

    local desiredPrimary = profile.primaryStat
    if not PRIMARY_STAT_KEYS[desiredPrimary] then return true end

    local rawStats = nil
    if type(C_Item) == "table" and type(C_Item.GetItemStats) == "function" then
        local ok, stats = pcall(C_Item.GetItemStats, itemLink)
        if ok and type(stats) == "table" then
            rawStats = stats
        end
    elseif type(GetItemStats) == "function" then
        local ok, stats = pcall(GetItemStats, itemLink)
        if ok and type(stats) == "table" then
            rawStats = stats
        end
    end
    if not rawStats then return true end

    local hasPrimary = false
    for statKey in pairs(PRIMARY_STAT_KEYS) do
        local amount = tonumber(rawStats[statKey]) or 0
        if amount > 0 then
            hasPrimary = true
            if statKey == desiredPrimary then
                return true
            end
        end
    end

    -- Weapons without a primary stat remain valid; only an explicit mismatch is rejected.
    return not hasPrimary
end

local function IsBlockedByEquippedTwoHand(itemLink, profile)
    local candidateEquipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    if not OFFHAND_EQUIP_LOCATIONS[candidateEquipLocation] then
        return false
    end

    -- A shield-spec context is allowed to build its own one-hand + shield set
    -- even while another active spec currently has a two-handed weapon equipped.
    if GetOffhandMode(profile) == "SHIELD" then
        return false
    end

    local mainHandLink = GetEquippedLink(INVSLOT_MAINHAND, profile)
    local mainHandEquipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(mainHandLink) or nil
    return mainHandEquipLocation and TWO_HAND_EQUIP_LOCATIONS[mainHandEquipLocation] or false
end

local function IsUniqueEquippedItem(itemLink)
    if not itemLink then return false end

    if type(C_Item) == "table" and type(C_Item.GetItemUniquenessByID) == "function" then
        local ok, isUnique, _, limitCategoryCount, limitCategoryID = pcall(C_Item.GetItemUniquenessByID, itemLink)
        if ok and (isUnique == true or (tonumber(limitCategoryID) and tonumber(limitCategoryCount))) then
            return true
        end
    end
    if type(C_Item) == "table" and type(C_Item.GetItemUniqueness) == "function" then
        local ok, limitCategory, limitMax = pcall(C_Item.GetItemUniqueness, itemLink)
        if ok and ((tonumber(limitCategory) or 0) > 0 or (tonumber(limitMax) or 0) > 0) then
            return true
        end
    end

    return false
end

local function GetTooltipTextLines(itemLink)
    local lines = {}
    if not itemLink then return lines end

    if type(C_TooltipInfo) == "table" and type(C_TooltipInfo.GetHyperlink) == "function" then
        local ok, data = pcall(C_TooltipInfo.GetHyperlink, itemLink)
        if ok and type(data) == "table" and type(data.lines) == "table" then
            for _, line in ipairs(data.lines) do
                local text = StripText(line and line.leftText)
                if type(text) == "string" and text ~= "" then
                    lines[#lines + 1] = text
                end
            end
            return lines
        end
    end

    return lines
end

local function GetItemRuleMetadata(itemLink)
    if not itemLink then return { embellished = false } end
    local cached = itemRuleMetadataCache[itemLink]
    if cached then return cached end

    local metadata = {
        embellished = false,
        limitCategoryID = nil,
        limitCategoryName = nil,
        limitCategoryCount = nil,
        tierSetKey = nil,
    }
    local itemInfoLoaded = false
    local itemSetID = nil

    if type(C_Item) == "table" and type(C_Item.GetItemUniquenessByID) == "function" then
        local ok, _, categoryName, categoryCount, categoryID = pcall(C_Item.GetItemUniquenessByID, itemLink)
        if ok then
            metadata.limitCategoryID = tonumber(categoryID)
            metadata.limitCategoryName = type(categoryName) == "string" and categoryName or nil
            metadata.limitCategoryCount = tonumber(categoryCount)
        end
        local normalizedName = metadata.limitCategoryName and metadata.limitCategoryName:lower() or ""
        if normalizedName:find("embellish", 1, true) and metadata.limitCategoryCount == 2 then
            metadata.embellished = true
        end
    end

    if type(C_Item) == "table" and type(C_Item.GetItemInfo) == "function" then
        local results = { pcall(C_Item.GetItemInfo, itemLink) }
        itemInfoLoaded = results[1] == true and results[2] ~= nil
        local setID = results[1] and tonumber(results[17]) or nil
        if setID and setID > 0 then
            itemSetID = setID
        end
    end

    local setName, setSize = nil, nil
    local hasTwoPiece, hasFourPiece = false, false
    for _, rawText in ipairs(GetTooltipTextLines(itemLink)) do
        local text = rawText:gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", "")
        local lower = text:lower()
        if lower:find("embellish", 1, true) and lower:find("unique", 1, true) then
            metadata.embellished = true
        end

        local candidateName, _, candidateSize = text:match("^(.+)%s+%((%d+)%s*/%s*(%d+)%)$")
        if candidateName and tonumber(candidateSize) and tonumber(candidateSize) >= 4 then
            setName = candidateName
            setSize = tonumber(candidateSize)
        end
        if text:match("%(%s*2%s*%)") then
            hasTwoPiece = true
        end
        if text:match("%(%s*4%s*%)") then
            hasFourPiece = true
        end
    end

    if itemSetID and hasTwoPiece and hasFourPiece then
        metadata.tierSetKey = "set:" .. tostring(itemSetID)
    elseif setName and setSize and hasTwoPiece and hasFourPiece then
        metadata.tierSetKey = setName:lower()
    end

    local tierMetadataPending = itemSetID ~= nil and metadata.tierSetKey == nil
    if not tierMetadataPending and (itemInfoLoaded or metadata.limitCategoryID or metadata.tierSetKey or metadata.embellished) then
        itemRuleMetadataCache[itemLink] = metadata
    end
    return metadata
end

local function CountEquippedItemsMatching(profile, predicate)
    local count = 0
    for _, slotID in ipairs(EQUIPMENT_SLOTS) do
        local equippedLink = GetEquippedLink(slotID, profile)
        if equippedLink and predicate(GetItemRuleMetadata(equippedLink)) then
            count = count + 1
        end
    end
    return count
end

local function WouldExceedUniqueEquippedLimit(itemLink, comparisonEntry, profile)
    local candidateMetadata = GetItemRuleMetadata(itemLink)
    local categoryID = candidateMetadata.limitCategoryID
    local categoryCount = candidateMetadata.limitCategoryCount
    if not categoryID or not categoryCount or categoryCount <= 0 then return false end

    local equippedLink = comparisonEntry and comparisonEntry.equippedLink or nil
    local equippedMainLink = comparisonEntry and comparisonEntry.equippedMainLink or nil
    local equippedOffLink = comparisonEntry and comparisonEntry.equippedOffLink or nil
    if (equippedLink and GetItemRuleMetadata(equippedLink).limitCategoryID == categoryID)
        or (equippedMainLink and GetItemRuleMetadata(equippedMainLink).limitCategoryID == categoryID)
        or (equippedOffLink and GetItemRuleMetadata(equippedOffLink).limitCategoryID == categoryID)
    then
        return false
    end

    local equippedCount = CountEquippedItemsMatching(profile, function(metadata)
        return metadata.limitCategoryID == categoryID
    end)
    if equippedCount >= categoryCount then
        return true, candidateMetadata.limitCategoryName, categoryCount, candidateMetadata.embellished
    end
    return false
end

local function WouldBreakTierSet(itemLink, comparisonEntry, profile)
    local slotID = tonumber(comparisonEntry and comparisonEntry.slotID)
    if not slotID or not TIER_ARMOR_SLOTS[slotID] then return false end

    local equippedLink = comparisonEntry and comparisonEntry.equippedLink or nil
    if not equippedLink then return false end

    local equippedSetKey = GetItemRuleMetadata(equippedLink).tierSetKey
    if not equippedSetKey then return false end
    if GetItemRuleMetadata(itemLink).tierSetKey == equippedSetKey then return false end

    local equippedCount = 0
    for tierSlotID in pairs(TIER_ARMOR_SLOTS) do
        local tierLink = GetEquippedLink(tierSlotID, profile)
        if tierLink and GetItemRuleMetadata(tierLink).tierSetKey == equippedSetKey then
            equippedCount = equippedCount + 1
        end
    end
    local remainingCount = math.max(0, equippedCount - 1)
    return (equippedCount >= 4 and remainingCount < 4)
        or (equippedCount >= 2 and remainingCount < 2)
end

function ns.IsCosmeticOnlyItem(itemLink)
    return IsCosmeticOnlyItem(itemLink)
end

function ns.EvaluateItemEligibility(itemLink, profile)
    if not itemLink then
        return BoolResult(false, "missing_item")
    end
    if IsCosmeticOnlyItem(itemLink) then
        return BoolResult(false, "cosmetic_only")
    end
    if IsPoorQualityItem(itemLink) then
        return BoolResult(false, "poor_quality")
    end
    if not IsEquippableCandidate(itemLink) then
        return BoolResult(false, "not_equippable")
    end
    if not IsUsableArmorType(itemLink, profile) then
        return BoolResult(false, "wrong_armor_type")
    end
    if not IsUsableWeaponType(itemLink, profile) then
        return BoolResult(false, "wrong_weapon_type")
    end
    if not IsWeaponPrimaryStatCompatible(itemLink, profile) then
        return BoolResult(false, "wrong_primary_stat")
    end
    if IsBlockedByEquippedTwoHand(itemLink, profile) then
        return BoolResult(false, "blocked_by_equipped_two_hand")
    end
    return BoolResult(true, nil)
end

function ns.IsItemCompatibleWithSlot(itemLink, profile, slotID)
    if not itemLink then return true end
    if not IsWeaponPrimaryStatCompatible(itemLink, profile) then return false end
    local mode = GetOffhandMode(profile)
    if not mode then return true end

    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    if slotID == INVSLOT_MAINHAND then
        if mode == "SHIELD" and TWO_HAND_EQUIP_LOCATIONS[equipLocation] then
            return false
        end
        return true
    end
    if slotID ~= INVSLOT_OFFHAND then return true end
    if mode == "DUAL_WIELD" then
        return equipLocation == "INVTYPE_WEAPON"
            or equipLocation == "INVTYPE_WEAPONOFFHAND"
            or (equipLocation == "INVTYPE_2HWEAPON" and CanDualWieldTwoHanded(profile))
    end
    if mode == "SHIELD" then
        return equipLocation == "INVTYPE_SHIELD"
    end
    return false
end

function ns.RestrictComparableSlotsByRules(itemLink, slots, profile)
    if not itemLink or type(slots) ~= "table" then
        return slots
    end

    local adjustedSlots = slots
    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    local isDualWieldWeapon = equipLocation == "INVTYPE_WEAPON"
        or (equipLocation == "INVTYPE_2HWEAPON" and CanDualWieldTwoHanded(profile))
    if isDualWieldWeapon and GetOffhandMode(profile) == "DUAL_WIELD" then
        adjustedSlots = { INVSLOT_MAINHAND, INVSLOT_OFFHAND }
    end

    if #adjustedSlots <= 1 or not IsUniqueEquippedItem(itemLink) then
        return adjustedSlots
    end

    local candidateItemID = ns.GetItemID and ns.GetItemID(itemLink) or nil
    if not candidateItemID then
        return adjustedSlots
    end

    local matchingSlots = {}
    for _, slotID in ipairs(adjustedSlots) do
        local equippedLink = GetEquippedLink(slotID, profile)
        local compatible = not equippedLink or not ns.IsItemCompatibleWithSlot or ns.IsItemCompatibleWithSlot(equippedLink, profile, slotID)
        if equippedLink and compatible and ns.GetItemID and ns.GetItemID(equippedLink) == candidateItemID then
            matchingSlots[#matchingSlots + 1] = slotID
        end
    end

    if #matchingSlots > 0 then
        return matchingSlots
    end
    return adjustedSlots
end

function ns.ApplyComparisonRules(itemLink, profile, comparison)
    if type(comparison) ~= "table" or type(comparison.comparisons) ~= "table" then
        return comparison
    end

    for _, entry in ipairs(comparison.comparisons) do
        if entry and entry.isUpgrade then
            local exceedsUniqueLimit, categoryName, categoryCount, isEmbellished =
                WouldExceedUniqueEquippedLimit(itemLink, entry, profile)
            if exceedsUniqueLimit then
                entry.isUpgrade = false
                entry.ruleBlocked = true
                entry.embellishedLimitReached = isEmbellished == true
                local label = categoryName or (isEmbellished and "Embellished" or "Unique-equipped category")
                entry.ruleReason = tostring(label) .. " limit reached (" .. tostring(categoryCount) .. ")"
            elseif WouldBreakTierSet(itemLink, entry, profile) then
                entry.isUpgrade = false
                entry.ruleBlocked = true
                entry.breaksTierSet = true
                entry.ruleReason = "Would break an active 2-piece or 4-piece set bonus"
            end
        end
    end

    local bestAllowedUpgrade = nil
    for _, entry in ipairs(comparison.comparisons) do
        if entry and entry.isUpgrade
            and (not bestAllowedUpgrade or (tonumber(entry.deltaScore) or 0) > (tonumber(bestAllowedUpgrade.deltaScore) or 0))
        then
            bestAllowedUpgrade = entry
        end
    end

    if bestAllowedUpgrade then
        comparison.selected = bestAllowedUpgrade
    end
    comparison.isUpgrade = comparison.selected and comparison.selected.isUpgrade or false
    return comparison
end
