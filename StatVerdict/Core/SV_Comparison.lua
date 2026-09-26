local addonName, ns = ...

local function SafeNumber(value)
    local ok, num = pcall(tonumber, value)
    if ok and num then return num end
    return nil
end

function ns.GetComparableSlots(itemLink)
    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    if not equipLocation or equipLocation == "" then
        return nil
    end
    if ns.MultiSlotByEquipLocation[equipLocation] then
        return ns.MultiSlotByEquipLocation[equipLocation]
    end
    local slot = ns.InventorySlotByEquipLocation[equipLocation]
    if slot then
        return { slot }
    end
    return nil
end

local function GetComparableSlots(itemLink)
    return ns.GetComparableSlots(itemLink)
end

local function GetEquippedLink(slotID)
    if not slotID then
        return nil
    end
    return GetInventoryItemLink("player", slotID)
end

-- Virtual loadout is the only baseline for off-spec comparisons.
-- Active-spec comparisons use currently equipped gear (also mirrored into the virtual loadout on capture).
local function GetCompatibleEquippedLink(slotID, profile)
    local itemLink = nil
    local useSnapshot = ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile)
    if useSnapshot then
        itemLink = ns.GetSnapshotEquippedLink and ns.GetSnapshotEquippedLink(profile, slotID) or nil
    else
        itemLink = GetEquippedLink(slotID)
    end
    if itemLink and ns.IsItemCompatibleWithSlot and not ns.IsItemCompatibleWithSlot(itemLink, profile, slotID) then
        return nil
    end
    return itemLink
end

local function GetMaxDisplayPercent()
    return ns.GlobalStatVerdictModifiers
        and ns.GlobalStatVerdictModifiers.percent
        and tonumber(ns.GlobalStatVerdictModifiers.percent.maxDisplayPercent)
        or 99.99
end

local TWO_HAND_EQUIP_LOCATIONS = {
    INVTYPE_2HWEAPON = true,
    INVTYPE_RANGED = true,
    INVTYPE_RANGEDRIGHT = true,
}

local ONE_HAND_EQUIP_LOCATIONS = {
    INVTYPE_WEAPON = true,
    INVTYPE_WEAPONMAINHAND = true,
}

local function IsTwoHandEquipLocation(equipLocation)
    return equipLocation and TWO_HAND_EQUIP_LOCATIONS[equipLocation] or false
end

local function IsOneHandMainEquipLocation(equipLocation)
    return equipLocation and ONE_HAND_EQUIP_LOCATIONS[equipLocation] or false
end

local function ContainsSlot(slots, targetSlot)
    for _, slotID in ipairs(slots) do
        if slotID == targetSlot then
            return true
        end
    end
    return false
end

local function GetItemString(itemLink)
    if type(itemLink) ~= "string" then return nil end
    return itemLink:match("|H(item:[^|]+)|h") or itemLink:match("(item:%d[^|%s]*)")
end

local function IsSameComparableItem(candidateLink, equippedLink)
    if not candidateLink or not equippedLink then
        return false
    end

    local candidateID = ns.GetItemID and ns.GetItemID(candidateLink) or nil
    local equippedID = ns.GetItemID and ns.GetItemID(equippedLink) or nil
    if candidateID and equippedID and candidateID ~= equippedID then
        return false
    end

    -- The full item string carries bonuses, gems, enchants and crafted
    -- modifiers. Matching only item ID, ilvl and four secondaries incorrectly
    -- collapses materially different copies into the equipped item.
    local candidateItemString = GetItemString(candidateLink)
    local equippedItemString = GetItemString(equippedLink)
    return candidateItemString ~= nil and candidateItemString == equippedItemString
end

function ns.BuildComparison(itemLink, profile)
    if not itemLink or not profile then
        return nil
    end
    if profile.invalidGeneratedContext then
        return nil
    end
    if ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile) then
        if ns.HasEquipmentSnapshot and not ns.HasEquipmentSnapshot(profile) then
            return nil
        end
        if ns.HasSnapshotStats and not ns.HasSnapshotStats(profile) then
            return nil
        end
    end

    local eligibility = ns.EvaluateItemEligibility and ns.EvaluateItemEligibility(itemLink, profile) or { allowed = true }
    if not eligibility.allowed then
        return nil
    end

    local slots = GetComparableSlots(itemLink)
    if not slots or #slots == 0 then
        return nil
    end
    if ns.RestrictComparableSlotsByRules then
        slots = ns.RestrictComparableSlotsByRules(itemLink, slots, profile) or slots
    end

    local candidateScore = ns.GetItemProfileScore(itemLink, profile) or 0
    local candidateEquipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    local candidateCanUseOffhand = ContainsSlot(slots, INVSLOT_OFFHAND)
    local equippedMainLink = GetCompatibleEquippedLink(INVSLOT_MAINHAND, profile)
    local equippedOffLink = GetCompatibleEquippedLink(INVSLOT_OFFHAND, profile)
    local equippedMainEquipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(equippedMainLink) or nil

    if IsOneHandMainEquipLocation(candidateEquipLocation)
        and IsTwoHandEquipLocation(equippedMainEquipLocation)
        and not equippedOffLink
        and not candidateCanUseOffhand
    then
        return {
            itemLink = itemLink,
            candidateScore = candidateScore,
            comparisons = {},
            selected = nil,
            isUpgrade = false,
            missingOffhand = true,
            equippedMainLink = equippedMainLink,
        }
    end

    local comparisons = {}
    local bestUpgrade = nil
    local weakestEquipped = nil
    local emptySlotUpgrade = nil

    if IsTwoHandEquipLocation(candidateEquipLocation) and not candidateCanUseOffhand and equippedMainLink and equippedOffLink and not IsTwoHandEquipLocation(equippedMainEquipLocation) then
        local equippedMainScore = ns.GetItemProfileScore(equippedMainLink, profile, INVSLOT_MAINHAND) or 0
        local equippedOffScore = ns.GetItemProfileScore(equippedOffLink, profile, INVSLOT_OFFHAND) or 0
        local equippedSetScore = equippedMainScore + equippedOffScore
        local candidateSlotScore = ns.GetItemProfileScore(itemLink, profile, INVSLOT_MAINHAND) or candidateScore
        local delta, deltaRows = nil, nil
        if ns.GetWeightedDeltaScoreForEquippedSet then
            delta, deltaRows = ns.GetWeightedDeltaScoreForEquippedSet(itemLink, {
                { link = equippedMainLink, slotID = INVSLOT_MAINHAND },
                { link = equippedOffLink, slotID = INVSLOT_OFFHAND },
            }, profile, INVSLOT_MAINHAND)
        end
        delta = delta or (candidateSlotScore - equippedSetScore)
        equippedSetScore = candidateSlotScore - delta
        local rawPercent = ns.GetUpgradePercent(delta, equippedSetScore, profile, itemLink, equippedMainLink) or 0
        local comparison = {
            slotID = INVSLOT_MAINHAND,
            slotLabel = "Main Hand + Off Hand",
            equippedLink = equippedMainLink,
            equippedMainLink = equippedMainLink,
            equippedOffLink = equippedOffLink,
            equippedScore = equippedSetScore,
            candidateScore = candidateSlotScore,
            deltaScore = delta,
            rawDeltaScore = delta,
            rawPercent = rawPercent,
            rawIsUpgrade = delta > 0,
            percent = rawPercent,
            isUpgrade = delta > 0,
            deltaRows = deltaRows,
            setComparison = true,
        }
        comparisons[#comparisons + 1] = comparison
        weakestEquipped = comparison
        if delta > 0 then
            bestUpgrade = comparison
        end
    end

    for _, slotID in ipairs(slots) do
        if IsTwoHandEquipLocation(candidateEquipLocation) and not candidateCanUseOffhand and slotID == INVSLOT_MAINHAND and equippedMainLink and equippedOffLink and not IsTwoHandEquipLocation(equippedMainEquipLocation) then
            -- Already compared the candidate 2H against the equipped mainhand+offhand set.
        else
        local equippedLink = GetCompatibleEquippedLink(slotID, profile)
        local candidateSlotScore = ns.GetItemProfileScore(itemLink, profile, slotID) or candidateScore
        if equippedLink and IsSameComparableItem(itemLink, equippedLink) then
            -- The same item at the same effective level is already represented by the profile snapshot/equipped slot.
        elseif equippedLink then
            local equippedScore = ns.GetItemProfileScore(equippedLink, profile, slotID)
            if equippedScore then
                local delta, deltaRows = ns.GetWeightedDeltaScore(itemLink, equippedLink, profile, slotID)
                delta = delta or 0
                local effectiveDelta = delta
                local rawPercent = ns.GetUpgradePercent(delta, equippedScore, profile, itemLink, equippedLink) or 0
                if delta > 0 and equippedScore == 0 then
                    rawPercent = GetMaxDisplayPercent()
                end
                local comparison = {
                    slotID = slotID,
                    slotLabel = ns.SlotLabels[slotID] or tostring(slotID),
                    equippedLink = equippedLink,
                    equippedScore = equippedScore,
                    candidateScore = candidateSlotScore,
                    deltaScore = effectiveDelta,
                    rawDeltaScore = delta,
                    rawPercent = rawPercent,
                    rawIsUpgrade = delta > 0,
                    percent = rawPercent,
                    isUpgrade = effectiveDelta > 0,
                    deltaRows = deltaRows,
                }
                comparisons[#comparisons + 1] = comparison

                if not weakestEquipped or equippedScore < weakestEquipped.equippedScore then
                    weakestEquipped = comparison
                end
                if effectiveDelta > 0 and (not bestUpgrade or effectiveDelta > bestUpgrade.deltaScore) then
                    bestUpgrade = comparison
                end
            end
        elseif candidateSlotScore then
            local delta, deltaRows = ns.GetWeightedDeltaScore(itemLink, nil, profile, slotID)
            delta = delta or candidateSlotScore
            local maxPercent = GetMaxDisplayPercent()
            local comparison = {
                slotID = slotID,
                slotLabel = ns.SlotLabels[slotID] or tostring(slotID),
                equippedLink = nil,
                equippedScore = 0,
                candidateScore = candidateSlotScore,
                deltaScore = delta,
                rawDeltaScore = delta,
                rawPercent = maxPercent,
                rawIsUpgrade = true,
                percent = maxPercent,
                isUpgrade = true,
                emptySlot = true,
                deltaRows = deltaRows,
            }
            comparisons[#comparisons + 1] = comparison

            if not weakestEquipped then
                weakestEquipped = comparison
            end
            if not emptySlotUpgrade then
                emptySlotUpgrade = comparison
            end
            if not bestUpgrade or delta > bestUpgrade.deltaScore then
                bestUpgrade = comparison
            end
        end
        end
    end

    if #comparisons == 0 then
        return nil
    end

    local selected = emptySlotUpgrade or bestUpgrade or weakestEquipped or comparisons[1]
    selected.deltaRows = selected.deltaRows or ns.GetDeltaRows(itemLink, selected.equippedLink, profile, selected.slotID)

    local result = {
        itemLink = itemLink,
        candidateScore = candidateScore,
        comparisons = comparisons,
        selected = selected,
        isUpgrade = selected and selected.isUpgrade or false,
    }
    if ns.ApplyComparisonRules then
        result = ns.ApplyComparisonRules(itemLink, profile, result) or result
    end
    return result
end
