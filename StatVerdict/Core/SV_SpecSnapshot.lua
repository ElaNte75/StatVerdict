local addonName, ns = ...

local SNAPSHOT_VERSION = 1

local EQUIPMENT_SLOTS = {
    1, 2, 3, 5, 6, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17,
}

local STAT_KEYS = {
    "STATVERDICT_ITEM_LEVEL",
    "ITEM_MOD_STRENGTH_SHORT",
    "ITEM_MOD_AGILITY_SHORT",
    "ITEM_MOD_STAMINA_SHORT",
    "ITEM_MOD_INTELLECT_SHORT",
    "ITEM_MOD_CRIT_RATING_SHORT",
    "ITEM_MOD_HASTE_RATING_SHORT",
    "ITEM_MOD_MASTERY_RATING_SHORT",
    "ITEM_MOD_VERSATILITY",
    "ITEM_MOD_AVOIDANCE_RATING_SHORT",
    "ITEM_MOD_LIFESTEAL",
    "ITEM_MOD_SPEED",
    "ITEM_MOD_SPEED_SHORT",
    "STATVERDICT_ARMOR",
    "STATVERDICT_MAIN_HAND_DPS",
    "STATVERDICT_OFF_HAND_DPS",
}

local activeProfile = nil
local captureScheduleToken = 0

local CAPTURE_DELAYS = { 0.25, 1.00, 2.00 }

local function SafeNumber(value)
    local sanitizer = ns.SanitizeStatVerdictNumber
    if type(sanitizer) == "function" then
        return sanitizer(value)
    end
    local ok, plain = pcall(function()
        local converted = tonumber(value)
        if converted == nil then return nil end
        if converted ~= converted then return nil end
        return converted + 0
    end)
    if ok and type(plain) == "number" then return plain end
    return nil
end

local function IsInCombat()
    return type(InCombatLockdown) == "function" and InCombatLockdown()
end

-- Saved loadouts are shared by every character of the account (keyed by spec), so each one remembers which
-- character made it. Only that character can say whether its items are gone.
local function CurrentCharacterGUID()
    if type(UnitGUID) ~= "function" then return nil end
    local ok, guid = pcall(UnitGUID, "player")
    if ok and type(guid) == "string" and not (issecretvalue and issecretvalue(guid)) then return guid end
    return nil
end

local function EnsureDB()
    StatVerdictDB = StatVerdictDB or {}
    StatVerdictDB.specSnapshots = StatVerdictDB.specSnapshots or {}
    StatVerdictDB.specSnapshots.version = SNAPSHOT_VERSION
    StatVerdictDB.specSnapshots.revision = SafeNumber(StatVerdictDB.specSnapshots.revision) or 0
    StatVerdictDB.specSnapshots.bySpecID = StatVerdictDB.specSnapshots.bySpecID or {}
    return StatVerdictDB.specSnapshots
end

local function GetActiveSpecID()
    if type(GetSpecialization) ~= "function" or type(GetSpecializationInfo) ~= "function" then
        return nil
    end
    local specIndex = GetSpecialization()
    if not specIndex then return nil end
    return SafeNumber((select(1, GetSpecializationInfo(specIndex))))
end


local function GetActiveHeroSubTreeID()
    local function safeCall(func, ...)
        if type(func) ~= "function" then return nil end
        local ok, a = pcall(func, ...)
        if ok then return a end
        return nil
    end
    local subTreeID
    if C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpec then
        subTreeID = SafeNumber(safeCall(C_ClassTalents.GetActiveHeroTalentSpec))
    end
    if not subTreeID and C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpecID then
        subTreeID = SafeNumber(safeCall(C_ClassTalents.GetActiveHeroTalentSpecID))
    end
    return subTreeID
end

local function GetActiveHeroTalentName()
    if type(ns.GetCurrentHeroTalentName) == "function" then
        local ok, name = pcall(ns.GetCurrentHeroTalentName)
        if ok and type(name) == "string" and name ~= "" then
            return name
        end
    end

    local function safeCall(func, ...)
        if type(func) ~= "function" then return nil end
        local ok, a = pcall(func, ...)
        if ok then return a end
        return nil
    end
    local function heroName(info)
        if type(info) == "table" then
            return info.name
                or info.subTreeName
                or info.heroTalentName
                or info.heroTalentSpecName
                or info.heroSpecName
                or info.displayName
        end
        return type(info) == "string" and info or nil
    end
    local function subTreeName(configID, subTreeID)
        if not configID or not subTreeID then return nil end
        if C_Traits and type(C_Traits.GetSubTreeInfo) == "function" then
            local name = heroName(safeCall(C_Traits.GetSubTreeInfo, configID, subTreeID))
            if type(name) == "string" and name ~= "" then
                return name
            end
        end
        return nil
    end

    local subTreeID
    if C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpec then
        subTreeID = SafeNumber(safeCall(C_ClassTalents.GetActiveHeroTalentSpec))
    end
    if not subTreeID and C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpecID then
        subTreeID = SafeNumber(safeCall(C_ClassTalents.GetActiveHeroTalentSpecID))
    end
    if not subTreeID or subTreeID == 0 then return nil end

    local configID = C_ClassTalents and C_ClassTalents.GetActiveConfigID and SafeNumber(safeCall(C_ClassTalents.GetActiveConfigID)) or nil
    local name = subTreeName(configID, subTreeID)
    if name then return name end

    if C_ClassTalents and C_ClassTalents.GetHeroTalentSpecInfo then
        name = heroName(safeCall(C_ClassTalents.GetHeroTalentSpecInfo, subTreeID))
        if name then return name end
    end

    local specID = GetActiveSpecID()
    if specID and C_ClassTalents and C_ClassTalents.GetHeroTalentSpecsForClassSpec then
        local specs = safeCall(C_ClassTalents.GetHeroTalentSpecsForClassSpec, specID)
        local function inspectCandidate(candidate)
            local candidateID = SafeNumber(candidate)
            if type(candidate) == "table" then
                candidateID = SafeNumber(candidate.subTreeID or candidate.subTreeId or candidate.ID or candidate.id or candidate.heroSpecID or candidate.heroSpecId)
                if candidateID == subTreeID then
                    local candidateName = heroName(candidate)
                    if candidateName then return candidateName end
                end
            end
            if candidateID == subTreeID then
                return subTreeName(configID, candidateID)
            end
            return nil
        end
        if type(specs) == "table" then
            for _, candidate in ipairs(specs) do
                name = inspectCandidate(candidate)
                if name then return name end
            end
            for _, candidate in pairs(specs) do
                name = inspectCandidate(candidate)
                if name then return name end
            end
        else
            name = inspectCandidate(specs)
            if name then return name end
        end
    end

    if C_Traits and C_Traits.GetDefinitionInfo then
        name = heroName(safeCall(C_Traits.GetDefinitionInfo, subTreeID))
        if name then return name end
    end
    return nil
end

local function GetProfileSpecID(profile)
    return SafeNumber(type(profile) == "table" and profile.specID or nil)
end

local function GetSnapshot(profile)
    local specID = GetProfileSpecID(profile)
    if not specID then return nil end
    local db = EnsureDB()
    return db.bySpecID[tostring(specID)]
end

function ns.SetStatVerdictSnapshotProfile(profile)
    activeProfile = profile
end

function ns.WithStatVerdictSnapshotProfile(profile, callback)
    if type(callback) ~= "function" then return nil end
    local previousProfile = activeProfile
    activeProfile = profile
    local results = { pcall(callback) }
    activeProfile = previousProfile
    if not results[1] then
        error(results[2], 2)
    end
    return select(2, unpack(results))
end

function ns.ShouldUseEquipmentSnapshot(profile)
    local specID = GetProfileSpecID(profile)
    local activeSpecID = GetActiveSpecID()
    return specID ~= nil and activeSpecID ~= nil and specID ~= activeSpecID
end

function ns.HasEquipmentSnapshot(profile)
    return GetSnapshot(profile) ~= nil
end

function ns.HasSnapshotStats(profile)
    local snapshot = GetSnapshot(profile)
    local stats = snapshot and snapshot.stats
    return type(stats) == "table" and next(stats) ~= nil
end

function ns.GetSnapshotEquippedLink(profile, slotID)
    if not ns.ShouldUseEquipmentSnapshot(profile) then
        return nil
    end
    local snapshot = GetSnapshot(profile)
    local links = snapshot and snapshot.equipment
    return links and links[tostring(slotID)] or nil
end

function ns.GetEquipmentSnapshotRevision(profile)
    local db = EnsureDB()
    local snapshot = type(profile) == "table" and GetSnapshot(profile) or nil
    return SafeNumber(snapshot and snapshot.revision) or SafeNumber(db.revision) or 0
end

local function GetItemIDFromLink(itemLink)
    if type(itemLink) ~= "string" then return nil end
    return SafeNumber(itemLink:match("item:(%d+)"))
end

local function GetItemLevelFromLink(itemLink)
    if type(itemLink) ~= "string" then return nil end
    local getter = C_Item and C_Item.GetDetailedItemLevelInfo or GetDetailedItemLevelInfo
    if type(getter) ~= "function" then return nil end
    local ok, level = pcall(getter, itemLink)
    return ok and SafeNumber(level) or nil
end

local function SnapshotLinksMatch(candidateLink, snapshotLink)
    local candidateID = GetItemIDFromLink(candidateLink)
    local snapshotID = GetItemIDFromLink(snapshotLink)
    if not candidateID or not snapshotID or candidateID ~= snapshotID then
        return false
    end

    local candidateLevel = GetItemLevelFromLink(candidateLink)
    local snapshotLevel = GetItemLevelFromLink(snapshotLink)
    if candidateLevel and snapshotLevel then
        return candidateLevel == snapshotLevel
    end

    return true
end

-- True when a matching copy still sits in player bags (not currently equipped).
local function ItemLinkInPlayerBags(itemLink)
    if not GetItemIDFromLink(itemLink) then return false end
    if type(C_Container) ~= "table" then return false end
    local getSlots = C_Container.GetContainerNumSlots
    local getLink = C_Container.GetContainerItemLink
    if type(getSlots) ~= "function" or type(getLink) ~= "function" then
        return false
    end
    local bagIDs = { 0, 1, 2, 3, 4, 5 }
    if Enum and Enum.BagIndex then
        local bi = Enum.BagIndex
        bagIDs = {
            bi.Backpack or 0,
            bi.Bag_1 or 1,
            bi.Bag_2 or 2,
            bi.Bag_3 or 3,
            bi.Bag_4 or 4,
            bi.ReagentBag or 5,
        }
    end
    for _, bagID in ipairs(bagIDs) do
        local slots = tonumber(getSlots(bagID)) or 0
        for slot = 1, slots do
            local link = getLink(bagID, slot)
            if link and SnapshotLinksMatch(itemLink, link) then
                return true
            end
        end
    end
    return false
end

-- The game gives every physical item its own serial number (item GUID). A mark remembers it, so the right copy is
-- found again whatever its name, level, gems or slot are. Everything here is read-only and protected.
local function BagIDList()
    local ids = { 0, 1, 2, 3, 4, 5 }
    if Enum and Enum.BagIndex then
        local bi = Enum.BagIndex
        ids = { bi.Backpack or 0, bi.Bag_1 or 1, bi.Bag_2 or 2, bi.Bag_3 or 3, bi.Bag_4 or 4, bi.ReagentBag or 5 }
    end
    return ids
end

local function GUIDFromLocation(location)
    if not (location and C_Item and C_Item.GetItemGUID) then return nil end
    local ok, guid = pcall(C_Item.GetItemGUID, location)
    if ok and type(guid) == "string" and guid ~= "" and not (issecretvalue and issecretvalue(guid)) then return guid end
    return nil
end

function ns.GetBagItemGUID(bagID, slot)
    if not (ItemLocation and ItemLocation.CreateFromBagAndSlot) then return nil end
    return GUIDFromLocation(ItemLocation:CreateFromBagAndSlot(bagID, slot))
end

local function WornGUID(slotID)
    if not (ItemLocation and ItemLocation.CreateFromEquipmentSlot) then return nil end
    return GUIDFromLocation(ItemLocation:CreateFromEquipmentSlot(slotID))
end

-- Where a serial number sits in the bags: bag, slot, and how many bag items share the same item id (copies).
local function FindBagLocationByGUID(guid)
    if type(guid) ~= "string" or not (C_Container and C_Container.GetContainerNumSlots and C_Container.GetContainerItemLink) then
        return nil
    end
    local foundBag, foundSlot, foundID = nil, nil, nil
    local items = {}
    for _, bagID in ipairs(BagIDList()) do
        for slot = 1, (tonumber(C_Container.GetContainerNumSlots(bagID)) or 0) do
            local link = C_Container.GetContainerItemLink(bagID, slot)
            if link then
                local id = GetItemIDFromLink(link)
                items[#items + 1] = id
                if not foundBag and ns.GetBagItemGUID(bagID, slot) == guid then
                    foundBag, foundSlot, foundID = bagID, slot, id
                end
            end
        end
    end
    if not foundBag then return nil end
    local copies = 0
    for _, id in ipairs(items) do if id == foundID then copies = copies + 1 end end
    return foundBag, foundSlot, copies
end

function ns.GetWornItemGUID(slotID)
    return WornGUID(slotID)
end

-- Put the bag piece with this serial number on, into this slot. A single copy goes by the item (as the put-on after a spec
-- change does); with several copies in the bags the exact one is picked up and put on.
function ns.EquipBagPieceByGUID(guid, targetSlot)
    if IsInCombat() then return false, "in combat" end
    local bagID, bagSlot, copies = FindBagLocationByGUID(guid)
    if not bagID then return false, "not found in bags" end
    local link = C_Container.GetContainerItemLink(bagID, bagSlot)
    local equipItem = (type(C_Item) == "table" and C_Item.EquipItemByName) or EquipItemByName
    if (copies or 1) <= 1 and type(equipItem) == "function" and link then
        return pcall(equipItem, link, targetSlot)
    end
    local pickup = C_Container.PickupContainerItem
    if type(pickup) ~= "function" or type(EquipCursorItem) ~= "function" or (CursorHasItem and CursorHasItem()) then
        return false, "cursor is busy or the pick-up function is missing"
    end
    local ok, err = pcall(pickup, bagID, bagSlot)
    if ok then ok, err = pcall(EquipCursorItem, targetSlot) end
    if CursorHasItem and CursorHasItem() and ClearCursor then ClearCursor() end
    return ok, err
end

-- Put the piece of this bag slot on, straight into the given slot: it is picked up and dropped on the slot, the way the
-- player would drag it. The piece it replaces ends up on the cursor (the caller lets go of it a moment later).
function ns.EquipBagSlotInto(bagID, bagSlot, targetSlot)
    if IsInCombat() then return false end
    if CursorHasItem and CursorHasItem() then return false end
    local pickup = C_Container and C_Container.PickupContainerItem
    if type(pickup) ~= "function" or type(EquipCursorItem) ~= "function" then return false end
    local ok = pcall(pickup, bagID, bagSlot)
    if not ok then return false end
    local ok2 = pcall(EquipCursorItem, targetSlot)
    return ok2 and true or false
end

-- Is this very piece marked in the loadout? With a serial number the answer is exact; a mark made before serial
-- numbers existed (no serial stored for its slot) is still recognised by item, as before.
function ns.IsPieceMarkedInLoadout(profile, itemLink, guid)
    local snapshot = GetSnapshot(profile)
    local markedGUID = snapshot and type(snapshot.markedGUID) == "table" and snapshot.markedGUID or nil
    if guid and markedGUID then
        for _, stored in pairs(markedGUID) do
            if stored == guid then return true end
        end
        local links = snapshot and type(snapshot.equipment) == "table" and snapshot.equipment or {}
        for slotKey, savedLink in pairs(links) do
            if markedGUID[slotKey] and type(savedLink) == "string" and SnapshotLinksMatch(itemLink, savedLink) then
                return false   -- the same item, but another copy of it is the marked one
            end
        end
    end
    return ns.IsItemInEquipmentSnapshot(profile, itemLink) and true or false
end

-- Does this loadout hold this piece? With a serial number (guid) the marked copy is recognised exactly, even after an
-- upgrade changed its level; a slot that remembers another copy's serial number does not count for this one. Slots without
-- a serial number (worn pieces, marks made before serial numbers) match by item, as before.
local function SnapshotHoldsPiece(snapshot, itemLink, guid)
    local links = snapshot and snapshot.equipment
    if type(links) ~= "table" then return false end
    local stored = type(snapshot.markedGUID) == "table" and snapshot.markedGUID or nil
    if guid and stored then
        for slotKey, storedGUID in pairs(stored) do
            if storedGUID == guid and links[slotKey] then return true, SafeNumber(slotKey), links[slotKey] end
        end
    end
    for slotKey, equippedLink in pairs(links) do
        if SnapshotLinksMatch(itemLink, equippedLink) then
            local slotGUID = stored and stored[slotKey] or nil
            if not (guid and slotGUID and slotGUID ~= guid) then
                return true, SafeNumber(slotKey), equippedLink
            end
        end
    end
    return false
end

function ns.IsItemInEquipmentSnapshot(profile, itemLink, guid)
    if not GetItemIDFromLink(itemLink) then return false end
    local snapshot = GetSnapshot(profile)
    if not snapshot then return false end
    return SnapshotHoldsPiece(snapshot, itemLink, guid)
end



function ns.GetEquipmentSnapshotItemRole(itemLink, guid)
    if not GetItemIDFromLink(itemLink) then return nil end
    local db = EnsureDB()
    local snapshots = db and db.bySpecID
    if type(snapshots) ~= "table" then return nil end

    local function containsSnapshot(snapshot)
        return (SnapshotHoldsPiece(snapshot, itemLink, guid)) and true or false
    end

    local selection = ns.GetSavedStatAuditSelection and ns.GetSavedStatAuditSelection() or nil
    local activeSpecID = GetActiveSpecID()
    local primarySpecID = nil
    if type(selection) == "table" and type(selection.primarySpecID) == "number" then
        primarySpecID = selection.primarySpecID
    end
    primarySpecID = primarySpecID or activeSpecID

    local secondaryEnabled = type(selection) == "table" and selection.secondaryEnabled == true
    local secondarySpecID = nil
    if secondaryEnabled and type(selection) == "table" and type(selection.secondarySpecID) == "number" then
        secondarySpecID = selection.secondarySpecID
    end

    local inPrimary = false
    local inSecondary = false
    local primaryMatchedID = nil
    local secondaryMatchedID = nil

    if primarySpecID then
        local snapshot = snapshots[tostring(primarySpecID)]
        if containsSnapshot(snapshot) then
            inPrimary = true
            primaryMatchedID = primarySpecID
        end
    end

    if secondarySpecID and secondarySpecID ~= primarySpecID then
        local snapshot = snapshots[tostring(secondarySpecID)]
        if containsSnapshot(snapshot) then
            inSecondary = true
            secondaryMatchedID = secondarySpecID
        end
    end

    if inPrimary and inSecondary then
        return "both_specs", primaryMatchedID, secondaryMatchedID
    elseif inPrimary then
        return "main_spec", primaryMatchedID
    elseif inSecondary then
        return "off_spec", secondaryMatchedID
    end

    return nil
end

function ns.GetSnapshotStatValue(profile, statKey)
    if not ns.ShouldUseEquipmentSnapshot(profile) then
        return nil
    end
    local snapshot = GetSnapshot(profile)
    local stats = snapshot and snapshot.stats
    return stats and SafeNumber(stats[statKey]) or nil
end

function ns.GetActiveSnapshotStatValue(statKey)
    return ns.GetSnapshotStatValue(activeProfile, statKey)
end

function ns.GetSnapshotHeroTalentName(profile)
    local snapshot = GetSnapshot(profile)
    local name = snapshot and snapshot.heroTalentName
    if type(name) == "string" and name ~= "" then
        return name
    end
    return nil
end

function ns.GetSnapshotHeroSubTreeID(profile)
    local snapshot = GetSnapshot(profile)
    local id = snapshot and tonumber(snapshot.heroSubTreeID)
    if id and id > 0 then return id end
    return nil
end

function ns.IsSnapshotMissingForProfile(profile)
    return profile ~= nil and ns.ShouldUseEquipmentSnapshot(profile) and not ns.HasEquipmentSnapshot(profile)
end

function ns.SwitchToStatVerdictSnapshotSpec(profile)
    local targetSpecID = GetProfileSpecID(profile)
    if not targetSpecID then return false, "No target spec." end
    if type(InCombatLockdown) == "function" and InCombatLockdown() then
        return false, "Cannot switch specialization in combat."
    end
    if type(GetNumSpecializations) ~= "function" or type(GetSpecializationInfo) ~= "function" then
        return false, "Specialization API is not available."
    end

    local targetIndex = nil
    for index = 1, GetNumSpecializations() do
        local specID = SafeNumber((select(1, GetSpecializationInfo(index))))
        if specID == targetSpecID then
            targetIndex = index
            break
        end
    end
    if not targetIndex then return false, "Target specialization is not available." end

    local ok, err
    if type(SetSpecialization) == "function" then
        ok, err = pcall(SetSpecialization, targetIndex)
    elseif type(C_SpecializationInfo) == "table" and type(C_SpecializationInfo.SetSpecialization) == "function" then
        ok, err = pcall(C_SpecializationInfo.SetSpecialization, targetIndex)
    else
        return false, "Specialization switch API is not available."
    end
    if not ok then
        return false, tostring(err or "Unable to switch specialization.")
    end
    return true
end

local function EnsureVirtualLoadout(specID)
    specID = SafeNumber(specID)
    if not specID then return nil end
    local db = EnsureDB()
    local key = tostring(specID)
    local snapshot = db.bySpecID[key]
    if type(snapshot) ~= "table" then
        local revision = (SafeNumber(db.revision) or 0) + 1
        db.revision = revision
        snapshot = {
            specID = specID,
            revision = revision,
            capturedAt = type(time) == "function" and time() or nil,
            equipment = {},
            stats = {},
            displayStats = {},
            source = "virtual_loadout",
            characterGUID = CurrentCharacterGUID(),
        }
        db.bySpecID[key] = snapshot
    end
    snapshot.equipment = type(snapshot.equipment) == "table" and snapshot.equipment or {}
    return snapshot, db
end

local TWO_HAND_EQUIP_LOCATIONS = {
    INVTYPE_2HWEAPON = true,
    INVTYPE_RANGED = true,
    INVTYPE_RANGEDRIGHT = true,
}

-- Shared cache-clear + UI refresh after any virtual-loadout mutation.
local function NotifyVirtualLoadoutChanged()
    if ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
    end
    if ns.InvalidateUpgradeIndicatorDecisionCache then
        ns.InvalidateUpgradeIndicatorDecisionCache()
    end
    if ns.ForceUpgradeIndicatorRefreshNow then
        ns.ForceUpgradeIndicatorRefreshNow("full")
    elseif ns.RequestInventoryVerdictRefresh then
        ns.RequestInventoryVerdictRefresh("full")
    elseif ns.RefreshUpgradeIndicators then
        ns.RefreshUpgradeIndicators("full")
    end
    if ns.RequestStatAuditRefresh then
        ns.RequestStatAuditRefresh()
    end
    if ns.RefreshOpenItemTooltipsAfterLoadoutChange then
        ns.RefreshOpenItemTooltipsAfterLoadoutChange()
    end
    -- Keep tooltip usable: briefly re-show membership on next ProcessTooltip after hide.
    if C_Timer and C_Timer.After then
        C_Timer.After(0.05, function()
            if ns.ForceUpgradeIndicatorRefreshNow then
                ns.ForceUpgradeIndicatorRefreshNow("bags")
            end
        end)
    end
end

-- Two slots that take the same kind of piece: rings, trinkets, and one-hand weapons (main and off hand).
local EQUIP_PAIRS = { [11] = { 11, 12 }, [12] = { 11, 12 }, [13] = { 13, 14 }, [14] = { 13, 14 }, [16] = { 16, 17 }, [17] = { 16, 17 } }

local function FitsBothSlots(link, pair)
    if pair[1] ~= 16 then return true end  -- any ring or trinket fits both of its slots
    local slots = ns.GetComparableSlots and ns.GetComparableSlots(link) or nil
    if type(slots) ~= "table" then return false end
    local has = {}
    for _, slot in ipairs(slots) do has[tonumber(slot)] = true end
    return (has[16] and has[17]) and true or false
end

-- Approve an item into a spec's virtual loadout without requiring equip or respec.
-- Works for any class/spec. slotID is optional; when omitted, comparison selects the best target slot.
function ns.ApproveItemIntoVirtualLoadout(itemLink, profile, slotID, itemGUID)
    if type(itemLink) ~= "string" or itemLink == "" then
        return false, "No item to approve."
    end
    local specID = GetProfileSpecID(profile)
    if not specID then
        return false, "No target specialization."
    end

    -- Ensure a virtual loadout exists first so comparison can resolve slots against it.
    local snapshot, db = EnsureVirtualLoadout(specID)
    if not snapshot or not db then
        return false, "Unable to create virtual loadout."
    end

    local comparison = nil
    local targetSlot = SafeNumber(slotID)
    if not targetSlot and ns.BuildComparison then
        comparison = ns.BuildComparison(itemLink, profile)
        targetSlot = comparison and comparison.selected and SafeNumber(comparison.selected.slotID) or nil
    end
    if not targetSlot and ns.GetComparableSlots then
        local slots = ns.GetComparableSlots(itemLink)
        targetSlot = slots and SafeNumber(slots[1]) or nil
    end
    if not targetSlot then
        return false, "Could not resolve a gear slot for this item."
    end

    -- Two slots take this kind of piece (rings, trinkets, one-hand weapons): the comparison names the weaker worn piece,
    -- which can be the same slot for two pieces marked one after the other, and the second would push the first out. A
    -- slot that already holds a marked piece is kept: the new one goes to the other slot of the pair, if that holds none.
    local pair = EQUIP_PAIRS[targetSlot]
    if pair and FitsBothSlots(itemLink, pair) and type(snapshot.marked) == "table"
        and snapshot.marked[tostring(targetSlot)] ~= nil then
        local other = (pair[1] == targetSlot) and pair[2] or pair[1]
        if snapshot.marked[tostring(other)] == nil then targetSlot = other end
    end

    if ns.IsItemCompatibleWithSlot and not ns.IsItemCompatibleWithSlot(itemLink, profile, targetSlot) then
        return false, "Item is not compatible with this specialization slot."
    end

    if ns.BuildComparison then
        comparison = comparison or ns.BuildComparison(itemLink, profile)
        for _, entry in ipairs(comparison and comparison.comparisons or {}) do
            if SafeNumber(entry and entry.slotID) == targetSlot and entry.ruleBlocked then
                return false, entry.ruleReason or "This replacement is blocked by an equipment rule."
            end
        end
    end

    local previous = snapshot.equipment[tostring(targetSlot)]
    snapshot.equipment[tostring(targetSlot)] = itemLink

    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    if equipLocation and TWO_HAND_EQUIP_LOCATIONS[equipLocation] and targetSlot == INVSLOT_MAINHAND then
        snapshot.equipment[tostring(INVSLOT_OFFHAND)] = nil
    end

    local revision = (SafeNumber(db.revision) or 0) + 1
    db.revision = revision
    snapshot.revision = revision
    snapshot.capturedAt = type(time) == "function" and time() or snapshot.capturedAt
    snapshot.source = "approve"
    snapshot.lastApprovedSlot = targetSlot
    snapshot.lastApprovedLink = itemLink
    -- Marked by the player: these are the pieces put on when this spec is switched to.
    snapshot.marked = type(snapshot.marked) == "table" and snapshot.marked or {}
    snapshot.marked[tostring(targetSlot)] = itemLink
    -- The serial number of the marked piece (nil when the game did not give one: the mark then works by item, as before).
    snapshot.markedGUID = type(snapshot.markedGUID) == "table" and snapshot.markedGUID or {}
    snapshot.markedGUID[tostring(targetSlot)] = type(itemGUID) == "string" and itemGUID or nil
    -- A hand mark: Auto mark leaves this slot alone until the piece is worn or the mark is removed.
    snapshot.manualSlots = type(snapshot.manualSlots) == "table" and snapshot.manualSlots or {}
    -- For the spec that is played, the lock remembers the piece worn in the slot now: when another piece is worn there later,
    -- the lock lets go. For another spec it is a plain lock (its gear is not worn now).
    local lockValue = true
    if GetActiveSpecID() == specID and type(GetInventoryItemLink) == "function" then
        lockValue = WornGUID(targetSlot) or true
    end
    snapshot.manualSlots[tostring(targetSlot)] = lockValue
    if equipLocation and TWO_HAND_EQUIP_LOCATIONS[equipLocation] and targetSlot == INVSLOT_MAINHAND then
        snapshot.marked[tostring(INVSLOT_OFFHAND)] = nil
        snapshot.markedGUID[tostring(INVSLOT_OFFHAND)] = nil
        snapshot.manualSlots[tostring(INVSLOT_OFFHAND)] = nil
    end

    NotifyVirtualLoadoutChanged()

    local slotLabel = ns.SlotLabels and ns.SlotLabels[targetSlot] or ("Slot " .. tostring(targetSlot))
    local specName = (type(profile) == "table" and profile.specName) or tostring(specID)
    local replaced = previous and previous ~= itemLink
    local message = replaced
        and ("Saved to " .. tostring(specName) .. " (" .. slotLabel .. ", replaced).")
        or ("Saved to " .. tostring(specName) .. " (" .. slotLabel .. ").")
    return true, message, targetSlot, previous
end

-- Toggle counterpart of Approve: Alt-clicking an item that is already saved in
-- the spec's virtual loadout removes it again. The slot falls back to whatever
-- the character currently wears there, so the loadout returns to its pre-approve
-- state without having to equip/unequip anything.
function ns.RemoveItemFromVirtualLoadout(itemLink, profile, itemGUID)
    if type(itemLink) ~= "string" or itemLink == "" then
        return false, "No item to remove."
    end
    local specID = GetProfileSpecID(profile)
    if not specID then
        return false, "No target specialization."
    end

    local db = EnsureDB()
    local snapshot = db.bySpecID and db.bySpecID[tostring(specID)] or nil
    local equipment = snapshot and type(snapshot.equipment) == "table" and snapshot.equipment or nil
    if not equipment then
        return false, "This item is not saved in that loadout."
    end

    local removedSlot = nil
    local storedGUIDs = type(snapshot.markedGUID) == "table" and snapshot.markedGUID or {}
    -- With a serial number, the slot that holds exactly this piece is the one to clear.
    local function clearSlot(slotKey)
        removedSlot = SafeNumber(slotKey)
        local worn = type(GetInventoryItemLink) == "function"
            and GetInventoryItemLink("player", removedSlot) or nil
        equipment[slotKey] = worn
    end
    if type(itemGUID) == "string" then
        for slotKey, stored in pairs(storedGUIDs) do
            if stored == itemGUID and equipment[slotKey] ~= nil then clearSlot(slotKey) break end
        end
    end
    if not removedSlot then
        for slotKey, savedLink in pairs(equipment) do
            -- A slot that remembers another copy's serial number belongs to that copy, not to this piece.
            local otherCopy = type(itemGUID) == "string" and storedGUIDs[slotKey] ~= nil and storedGUIDs[slotKey] ~= itemGUID
            if not otherCopy and type(savedLink) == "string" and SnapshotLinksMatch(itemLink, savedLink) then
                clearSlot(slotKey)
                break
            end
        end
    end
    if not removedSlot then
        return false, "This item is not saved in that loadout."
    end
    if type(snapshot.marked) == "table" then snapshot.marked[tostring(removedSlot)] = nil end
    if type(snapshot.markedGUID) == "table" then snapshot.markedGUID[tostring(removedSlot)] = nil end
    if type(snapshot.manualSlots) == "table" then snapshot.manualSlots[tostring(removedSlot)] = nil end

    -- Approving a two-hander clears the off-hand slot; removing it restores the
    -- worn off-hand so the loadout matches the character again.
    if removedSlot == INVSLOT_MAINHAND and equipment[tostring(INVSLOT_OFFHAND)] == nil
        and type(GetInventoryItemLink) == "function" then
        equipment[tostring(INVSLOT_OFFHAND)] = GetInventoryItemLink("player", INVSLOT_OFFHAND)
    end

    local revision = (SafeNumber(db.revision) or 0) + 1
    db.revision = revision
    snapshot.revision = revision
    snapshot.capturedAt = type(time) == "function" and time() or snapshot.capturedAt
    if snapshot.lastApprovedLink and SnapshotLinksMatch(itemLink, snapshot.lastApprovedLink) then
        snapshot.lastApprovedLink = nil
        snapshot.lastApprovedSlot = nil
    end

    NotifyVirtualLoadoutChanged()

    local slotLabel = ns.SlotLabels and ns.SlotLabels[removedSlot] or ("Slot " .. tostring(removedSlot))
    local specName = (type(profile) == "table" and profile.specName) or tostring(specID)
    return true, "Removed from " .. tostring(specName) .. " (" .. slotLabel .. ").", removedSlot
end

local function SameValueMap(a, b)
    for key, value in pairs(a) do
        if b[key] ~= value then return false end
    end
    for key in pairs(b) do
        if a[key] == nil then return false end
    end
    return true
end

function ns.CaptureActiveSpecSnapshot()
    if IsInCombat() then return nil end
    if ns.UpdateCurrentStatsCache then ns.UpdateCurrentStatsCache() end
    local specID = GetActiveSpecID()
    if not specID then return nil end

    local db = EnsureDB()
    local specKey = tostring(specID)
    local previous = db.bySpecID and db.bySpecID[specKey] or nil
    local previousEquipment = previous and type(previous.equipment) == "table" and previous.equipment or nil

    local equipment = {}
    if type(GetInventoryItemLink) == "function" then
        for _, slotID in ipairs(EQUIPMENT_SLOTS) do
            local link = GetInventoryItemLink("player", slotID)
            if link then
                equipment[tostring(slotID)] = link
            end
        end
    end

    -- Preserve virtual-loadout pieces that were Approved from bags and are still
    -- sitting in bags. A full worn-only replace was wiping MS/OS membership and
    -- flipping those items back to D/S after the next capture refresh.
    local preservedApprove = false
    if previousEquipment then
        for slotKey, prevLink in pairs(previousEquipment) do
            if type(prevLink) == "string" and prevLink ~= "" then
                local wornLink = equipment[slotKey]
                -- A piece with a stored serial number is recognised by it; others by item, as before.
                local storedGUID = previous and type(previous.markedGUID) == "table" and previous.markedGUID[slotKey] or nil
                local wornMatches
                if storedGUID then
                    wornMatches = WornGUID(tonumber(slotKey)) == storedGUID
                else
                    wornMatches = wornLink and SnapshotLinksMatch(wornLink, prevLink)
                end
                if not wornMatches then
                    local inBags
                    if storedGUID then
                        inBags = FindBagLocationByGUID(storedGUID) ~= nil
                    else
                        inBags = ItemLinkInPlayerBags(prevLink)
                    end
                    if inBags then
                        equipment[slotKey] = prevLink
                        preservedApprove = true
                    end
                end
            end
        end
    end

    local stats = {}
    local displayStats = {}
    if ns.GetCurrentAuditStatValue then
        local previousProfile = activeProfile
        activeProfile = nil
        for _, statKey in ipairs(STAT_KEYS) do
            local value = SafeNumber(ns.GetCurrentAuditStatValue(statKey))
            if value then
                stats[statKey] = value
            end
            local displayValue = ns.GetLiveCharacterSheetStatValue and SafeNumber(ns.GetLiveCharacterSheetStatValue(statKey)) or nil
            if displayValue then
                displayStats[statKey] = displayValue
            end
        end
        activeProfile = previousProfile
    end

    -- Nothing changed since the last capture (same worn pieces, same stats, same hero talents): keep it as it is. A new
    -- revision would make every screen re-evaluate every item for nothing.
    if previous and previousEquipment and previous.characterGUID == CurrentCharacterGUID()
        and previous.heroSubTreeID == (GetActiveHeroSubTreeID and GetActiveHeroSubTreeID() or nil)
        and SameValueMap(equipment, previousEquipment)
        and SameValueMap(stats, type(previous.stats) == "table" and previous.stats or {})
        and SameValueMap(displayStats, type(previous.displayStats) == "table" and previous.displayStats or {}) then
        return previous
    end

    local revision = (SafeNumber(db.revision) or 0) + 1
    db.revision = revision
    local source = "active_capture"
    if preservedApprove and previous and previous.source == "approve" then
        source = "approve"
    elseif preservedApprove then
        source = "active_capture_merged"
    end
    db.bySpecID[specKey] = {
        specID = specID,
        revision = revision,
        capturedAt = type(time) == "function" and time() or nil,
        heroTalentName = GetActiveHeroTalentName(),
        heroSubTreeID = GetActiveHeroSubTreeID and GetActiveHeroSubTreeID() or nil,
        equipment = equipment,
        stats = stats,
        displayStats = displayStats,
        source = source,
        characterGUID = CurrentCharacterGUID(),
        lastApprovedSlot = previous and previous.lastApprovedSlot or nil,
        lastApprovedLink = previous and previous.lastApprovedLink or nil,
        marked = previous and previous.marked or nil,
        markedGUID = previous and previous.markedGUID or nil,
        manualSlots = previous and previous.manualSlots or nil,
    }

    return db.bySpecID[specKey]
end

-- Vanished gear. A saved loadout is a picture, so an item that is sold, disenchanted, deleted or
-- otherwise gone would stay in it for ever and every later comparison would use it. When an item of
-- a saved loadout is no longer owned (worn, in the bags, the bank or the warband bank), it leaves the
-- loadout, and its slot falls back to what is worn there now. What is worn always has priority;
-- what the player puts in the bags stays their own choice (Approve).
--
-- Safety: an item counts as gone only when it is missing in two checks at least
-- VANISH_CONFIRM_SECONDS apart (a trade, a bank move or a loading screen never removes anything),
-- and the check is by item id, so a second copy of the same item keeps it. The active spec is not
-- touched: its picture is rebuilt from the worn gear on every capture. An item bought back from a
-- vendor within RESTORE_WINDOW_SECONDS goes back where it was, if the slot was not changed since.
local VANISH_CONFIRM_SECONDS = 3
local RESTORE_WINDOW_SECONDS = 600
local missingSince = {}      -- itemID -> time it was first found missing
local recentlyRemoved = {}   -- { itemID, specKey, slotKey, link, fallback, at }

local function Now()
    if type(GetTime) == "function" then return GetTime() end
    return type(time) == "function" and time() or 0
end

-- Unknown means present: nothing is removed on a guess.
local function PlayerOwnsItem(itemID)
    local getter = (type(C_Item) == "table" and C_Item.GetItemCount) or GetItemCount
    if type(getter) ~= "function" then return true end
    local ok, count = pcall(getter, itemID, true, false, true, true)
    count = ok and SafeNumber(count) or nil
    if count == nil then return true end
    return count > 0
end

local function SpecNameByID(specID)
    if type(GetSpecializationInfoByID) == "function" then
        local ok, _, name = pcall(GetSpecializationInfoByID, tonumber(specID))
        if ok and type(name) == "string" and name ~= "" then return name end
    end
    return "spec " .. tostring(specID)
end

local function SayLoadoutChange(text)
    if DEFAULT_CHAT_FRAME and DEFAULT_CHAT_FRAME.AddMessage then
        DEFAULT_CHAT_FRAME:AddMessage("|cffff8000StatVerdict:|r " .. text)
    end
end

local function BumpSnapshotRevision(db, snapshot)
    local revision = (SafeNumber(db.revision) or 0) + 1
    db.revision = revision
    snapshot.revision = revision
    snapshot.capturedAt = type(time) == "function" and time() or snapshot.capturedAt
end

-- Runs one check. Returns how many items it removed or restored, and whether some are still
-- waiting for their second look (the caller checks again later).
function ns.PruneVanishedLoadoutItems()
    if IsInCombat() then return 0, false end
    local activeSpecID = GetActiveSpecID()
    if not activeSpecID then return 0, false end
    local db = EnsureDB()
    local activeKey = tostring(activeSpecID)
    local myGUID = CurrentCharacterGUID()
    if not myGUID then return 0, false end
    local now = Now()
    local changed, pending = 0, false

    for specKey, snapshot in pairs(db.bySpecID) do
        local equipment = type(snapshot) == "table" and snapshot.equipment or nil
        -- Only this character's own loadouts: the bags here say nothing about another character's gear, and a
        -- loadout saved before the character was recorded is never touched.
        if specKey ~= activeKey and type(equipment) == "table" and snapshot.characterGUID == myGUID then
            -- The table is only changed after the walk over it (adding a key while walking is not allowed).
            local gone = {}
            for slotKey, link in pairs(equipment) do
                local itemID = GetItemIDFromLink(link)
                if itemID then
                    if PlayerOwnsItem(itemID) then
                        missingSince[itemID] = nil
                    elseif not missingSince[itemID] then
                        missingSince[itemID] = now
                        pending = true
                    elseif now - missingSince[itemID] >= VANISH_CONFIRM_SECONDS then
                        gone[#gone + 1] = { slotKey = slotKey, link = link, itemID = itemID }
                    else
                        pending = true
                    end
                end
            end
            local removedHere = #gone > 0
            for _, entry in ipairs(gone) do
                local slotID = SafeNumber(entry.slotKey)
                local worn = slotID and type(GetInventoryItemLink) == "function"
                    and GetInventoryItemLink("player", slotID) or nil
                equipment[entry.slotKey] = worn
                -- Removing a two-hander gives the off-hand slot back to what is worn there.
                if slotID == INVSLOT_MAINHAND and equipment[tostring(INVSLOT_OFFHAND)] == nil
                    and type(GetInventoryItemLink) == "function" then
                    equipment[tostring(INVSLOT_OFFHAND)] = GetInventoryItemLink("player", INVSLOT_OFFHAND)
                end
                if type(snapshot.marked) == "table" then snapshot.marked[entry.slotKey] = nil end
                if type(snapshot.markedGUID) == "table" then snapshot.markedGUID[entry.slotKey] = nil end
                if type(snapshot.manualSlots) == "table" then snapshot.manualSlots[entry.slotKey] = nil end
                if snapshot.lastApprovedLink and GetItemIDFromLink(snapshot.lastApprovedLink) == entry.itemID then
                    snapshot.lastApprovedLink, snapshot.lastApprovedSlot = nil, nil
                end
                recentlyRemoved[#recentlyRemoved + 1] = {
                    itemID = entry.itemID, specKey = specKey, slotKey = entry.slotKey,
                    link = entry.link, fallback = worn, at = now,
                }
                missingSince[entry.itemID] = nil
                changed = changed + 1
                SayLoadoutChange(tostring(entry.link) .. " is gone and was removed from the "
                    .. SpecNameByID(specKey) .. " loadout.")
            end
            if removedHere then BumpSnapshotRevision(db, snapshot) end
        end
    end

    -- Bought back (or found again) shortly after it was removed: it returns to its slot, unless the
    -- slot was changed in the meantime.
    for index = #recentlyRemoved, 1, -1 do
        local entry = recentlyRemoved[index]
        if now - entry.at > RESTORE_WINDOW_SECONDS then
            table.remove(recentlyRemoved, index)
        elseif PlayerOwnsItem(entry.itemID) then
            local snapshot = db.bySpecID[entry.specKey]
            local equipment = snapshot and snapshot.equipment
            if type(equipment) == "table" and equipment[entry.slotKey] == entry.fallback then
                equipment[entry.slotKey] = entry.link
                BumpSnapshotRevision(db, snapshot)
                changed = changed + 1
                SayLoadoutChange(tostring(entry.link) .. " is back and was put back into the "
                    .. SpecNameByID(entry.specKey) .. " loadout.")
            end
            table.remove(recentlyRemoved, index)
        end
    end

    if changed > 0 then NotifyVirtualLoadoutChanged() end
    return changed, pending
end

local pruneToken = 0
local function SchedulePrune(delay)
    if type(C_Timer) ~= "table" or type(C_Timer.After) ~= "function" then return end
    pruneToken = pruneToken + 1
    local token = pruneToken
    C_Timer.After(delay, function()
        if token ~= pruneToken then return end
        local _, pending = ns.PruneVanishedLoadoutItems()
        if pending then
            -- The second look: items first found missing are checked again once the delay has passed.
            SchedulePrune(VANISH_CONFIRM_SECONDS + 0.5)
        end
    end)
end

local function RequestRefresh()
    if ns.InvalidateUpgradeIndicatorDecisionCache then
        ns.InvalidateUpgradeIndicatorDecisionCache()
    elseif ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
    end
    if ns.RequestInventoryVerdictRefresh then
        ns.RequestInventoryVerdictRefresh()
    elseif ns.RefreshUpgradeIndicators then
        ns.RefreshUpgradeIndicators()
    end
    if ns.RequestStatAuditRefresh then
        ns.RequestStatAuditRefresh()
    end
    -- The marks on the character sheet follow the loadouts: they are redrawn after the loadouts changed (the sheet's own
    -- redraw, half a second after an equipment change, can come before the marks are updated).
    if ns.RefreshCatalystMarks and type(C_Timer) == "table" and C_Timer.After then
        C_Timer.After(0.1, ns.RefreshCatalystMarks)
    end
end

-- Switching spec puts on the pieces the player marked for the new spec (Alt-click) and that are in the bags.
-- Every other slot keeps what is worn. Only after a real spec change, never in combat, never at login.
-- The game is busy for a moment after a spec change and may ignore a piece put on too early, so the pass runs again
-- twice later: a piece already worn is skipped, so a pass that finds nothing left to do changes nothing.
local EQUIP_AFTER_SPEC_DELAYS = { 1.25, 2.5, 4 }
local lastSpecID = nil
-- Auto mark ignores gear changes for a few seconds after a spec change: the game still shows the old spec's gear until the
-- marked pieces of the new spec are put on (EQUIP_AFTER_SPEC_DELAYS), and that must not be taken for the new spec's own.
local AUTO_MARK_QUIET_SECONDS = 7
local lastSpecChangeAt = nil

-- Which slot a marked piece is put on. For a pair of slots the slot number saved at marking time means little (the
-- same two rings can sit the other way round in the other spec), so the piece goes where the worn item is NOT
-- part of this loadout: the pieces the loadout keeps (marked or not) stay on. nil: nothing to do (the piece is already
-- worn, or both worn pieces belong to the loadout). `claimed`: slots already filled during this pass.
local function ChooseEquipSlot(slotID, link, equipment, claimed, guid, markedGUID)
    local pair = EQUIP_PAIRS[slotID]
    if not pair or not FitsBothSlots(link, pair) then return slotID end
    markedGUID = type(markedGUID) == "table" and markedGUID or {}
    -- A worn piece belongs to the loadout when it is the marked copy (serial number) of one of the pair's slots, or,
    -- for a slot without a serial number, the same item as the loadout holds there.
    local function belongs(worn, wornSlot)
        local wornGUID = WornGUID(wornSlot)
        for _, slot in ipairs(pair) do
            local stored = markedGUID[tostring(slot)]
            if stored then
                if wornGUID == stored then return true end
            else
                local kept = equipment[tostring(slot)]
                if type(kept) == "string" and SnapshotLinksMatch(worn, kept) then return true end
            end
        end
        return false
    end
    local get = type(GetInventoryItemLink) == "function" and GetInventoryItemLink or function() return nil end
    for _, slot in ipairs(pair) do
        local worn = get("player", slot)
        if guid then
            if worn and WornGUID(slot) == guid then return nil end
        elseif worn and SnapshotLinksMatch(worn, link) then
            return nil
        end
    end
    local candidates = {}
    for _, slot in ipairs(pair) do
        if not claimed[slot] then
            local worn = get("player", slot)
            if not worn or not belongs(worn, slot) then candidates[#candidates + 1] = slot end
        end
    end
    if #candidates == 0 then return nil end
    for _, slot in ipairs(candidates) do
        if slot == slotID then return slot end
    end
    return candidates[1]
end

function ns.EquipMarkedLoadoutItems()
    if IsInCombat() then return 0 end
    local specID = GetActiveSpecID()
    if not specID then return 0 end
    local snapshot = EnsureDB().bySpecID[tostring(specID)]
    local marked = type(snapshot) == "table" and snapshot.marked or nil
    local equipment = type(snapshot) == "table" and snapshot.equipment or nil
    local equipItem = (type(C_Item) == "table" and C_Item.EquipItemByName) or EquipItemByName
    if type(marked) ~= "table" or type(equipment) ~= "table" or type(equipItem) ~= "function" then return 0 end

    local slots = {}
    for slotKey in pairs(marked) do
        local slotID = SafeNumber(slotKey)
        if slotID then slots[#slots + 1] = slotID end
    end
    table.sort(slots)  -- the main hand before the off hand
    local equipped = 0
    local claimed = {}
    local markedGUID = type(snapshot.markedGUID) == "table" and snapshot.markedGUID or {}
    for _, slotID in ipairs(slots) do
        local key = tostring(slotID)
        local link = marked[key]
        local guid = markedGUID[key]
        local target = nil
        local bagID, bagSlot, copies
        if type(link) ~= "string" then
            -- nothing usable is marked here
        elseif guid then
            -- The mark knows its piece by serial number: that is all that counts (no second list to agree with).
            bagID, bagSlot, copies = FindBagLocationByGUID(guid)
            if bagID then
                target = ChooseEquipSlot(slotID, link, equipment, claimed, guid, markedGUID)
            end
        elseif type(equipment[key]) == "string" and SnapshotLinksMatch(equipment[key], link) and ItemLinkInPlayerBags(link) then
            target = ChooseEquipSlot(slotID, link, equipment, claimed)
        end
        local worn = target and type(GetInventoryItemLink) == "function" and GetInventoryItemLink("player", target) or nil
        local alreadyWorn = target and (guid and WornGUID(target) == guid or (not guid and worn and SnapshotLinksMatch(worn, link)))
        if target and not alreadyWorn then
            claimed[target] = true
            local ok, err
            if guid and copies and copies > 1 then
                -- Several copies of this item in the bags: the name cannot say which one, so the exact one is picked up.
                local pickup = C_Container and C_Container.PickupContainerItem
                if type(pickup) == "function" and type(EquipCursorItem) == "function"
                    and not (CursorHasItem and CursorHasItem()) then
                    ok, err = pcall(pickup, bagID, bagSlot)
                    if ok then ok, err = pcall(EquipCursorItem, target) end
                    if CursorHasItem and CursorHasItem() and ClearCursor then ClearCursor() end
                else
                    ok, err = false, "cursor is busy or the pick-up function is missing"
                end
            else
                ok, err = pcall(equipItem, link, target)
            end
            if ok then
                equipped = equipped + 1
                SayLoadoutChange(link .. " was put on from the " .. SpecNameByID(specID) .. " loadout.")
            end
        end
    end
    return equipped
end

local function NoteSpecChange()
    local specID = GetActiveSpecID()
    if not specID then return end
    local changed = lastSpecID ~= nil and lastSpecID ~= specID
    lastSpecID = specID
    if changed then lastSpecChangeAt = Now() end
    if changed and type(C_Timer) == "table" and type(C_Timer.After) == "function" then
        for _, delay in ipairs(EQUIP_AFTER_SPEC_DELAYS) do
            C_Timer.After(delay, function()
                if GetActiveSpecID() == specID then ns.EquipMarkedLoadoutItems() end
            end)
        end
        -- Once the quiet time is over, take what is worn as the new spec's marks.
        C_Timer.After(AUTO_MARK_QUIET_SECONDS + 0.5, function()
            if GetActiveSpecID() == specID and not IsInCombat() then
                ns.CaptureActiveSpecSnapshot()
                ns.AutoMarkWornPieces()
                RequestRefresh()
            end
        end)
    end
end

-- Auto mark: whatever is worn in the spec that is played becomes that spec's marked piece, so it is put on again whenever
-- the spec is switched back to, and a replaced piece loses its mark. A mark the player made by hand (Alt-click) stays until
-- the player wears that piece or removes the mark. Switched off by the "Auto mark" option (StatVerdictDB.autoMark = false).
local function AutoMarkEnabled()
    return not (type(StatVerdictDB) == "table" and StatVerdictDB.autoMark == false)
end

function ns.IsAutoMarkOn()
    return AutoMarkEnabled()
end

-- The click that saves a piece in the bags, as the tooltips and help name it: one Alt-Click with Auto mark on (it saves the
-- build that is not played), Alt-Left-Click (Off Spec) / Alt-Right-Click (Main Spec) with Auto mark off.
function ns.MarkClickLabel(isSecondary)
    if AutoMarkEnabled() then return "Alt-Click" end
    return isSecondary and "Alt-Left-Click" or "Alt-Right-Click"
end

function ns.AutoMarkWornPieces()
    if IsInCombat() or not AutoMarkEnabled() then return 0 end
    local specID = GetActiveSpecID()
    if not specID then return 0 end
    if lastSpecID ~= nil and lastSpecID ~= specID then return 0 end
    if lastSpecChangeAt and Now() - lastSpecChangeAt < AUTO_MARK_QUIET_SECONDS then return 0 end
    local db = EnsureDB()
    local snapshot = db.bySpecID[tostring(specID)]
    if type(snapshot) ~= "table" or type(snapshot.equipment) ~= "table" then return 0 end
    if type(GetInventoryItemLink) ~= "function" then return 0 end

    snapshot.marked = type(snapshot.marked) == "table" and snapshot.marked or {}
    snapshot.markedGUID = type(snapshot.markedGUID) == "table" and snapshot.markedGUID or {}
    if type(snapshot.manualSlots) ~= "table" then
        -- Marks made before Auto mark existed: a marked piece that sits in the bags and is not worn is the player's own
        -- choice (kept as a hand mark); worn pieces are ordinary marks.
        snapshot.manualSlots = {}
        for slotKey, markLink in pairs(snapshot.marked) do
            if type(markLink) == "string" then
                local storedGUID = snapshot.markedGUID[slotKey]
                local wornLink = GetInventoryItemLink("player", tonumber(slotKey))
                local isWorn
                if storedGUID then
                    isWorn = WornGUID(tonumber(slotKey)) == storedGUID
                else
                    isWorn = wornLink and SnapshotLinksMatch(wornLink, markLink)
                end
                if not isWorn and ItemLinkInPlayerBags(markLink) then
                    snapshot.manualSlots[slotKey] = WornGUID(tonumber(slotKey)) or true
                end
            end
        end
    end

    local changed = 0
    for _, slotID in ipairs(EQUIPMENT_SLOTS) do
        local key = tostring(slotID)
        local wornLink = GetInventoryItemLink("player", slotID)
        local wornGUID = WornGUID(slotID)
        if wornLink and wornGUID then
            local storedGUID = snapshot.markedGUID[key]
            local lock = snapshot.manualSlots[key]
            if lock then
                local markLink = snapshot.marked[key]
                if storedGUID == wornGUID
                    or (not storedGUID and type(markLink) == "string" and SnapshotLinksMatch(wornLink, markLink)) then
                    snapshot.manualSlots[key] = nil   -- the hand-marked piece is worn now: an ordinary mark again
                    lock = nil
                elseif type(lock) == "string" and lock ~= wornGUID then
                    -- Another piece is worn here than when the hand mark was made: the player moved on. The worn piece
                    -- takes the slot's mark, and the piece marked by hand loses it for this spec.
                    snapshot.manualSlots[key] = nil
                    lock = nil
                end
            end
            if not lock and storedGUID ~= wornGUID then
                snapshot.marked[key] = wornLink
                snapshot.markedGUID[key] = wornGUID
                changed = changed + 1
            end
        end
    end

    -- A two-hander in the main hand leaves no off-hand piece to put on.
    local mainLink = GetInventoryItemLink("player", INVSLOT_MAINHAND)
    local mainLocation = mainLink and ns.GetItemEquipLocation and ns.GetItemEquipLocation(mainLink) or nil
    local offKey = tostring(INVSLOT_OFFHAND)
    if mainLocation and TWO_HAND_EQUIP_LOCATIONS[mainLocation] and not snapshot.manualSlots[offKey]
        and snapshot.marked[offKey] ~= nil then
        snapshot.marked[offKey] = nil
        snapshot.markedGUID[offKey] = nil
        changed = changed + 1
    end

    -- The revision change is enough: the screens refresh through the capture pass that called this (no extra full refresh).
    if changed > 0 then
        BumpSnapshotRevision(db, snapshot)
    end
    return changed
end

local function ScheduleCapture()
    if IsInCombat() then return end
    captureScheduleToken = captureScheduleToken + 1
    local token = captureScheduleToken
    for index, delay in ipairs(CAPTURE_DELAYS) do
        C_Timer.After(delay, function()
            if token ~= captureScheduleToken or IsInCombat() then return end
            local activeSpecID = GetActiveSpecID()
            local db = EnsureDB()
            local before = activeSpecID and db.bySpecID[tostring(activeSpecID)]
            local revisionBefore = before and before.revision
            local tableBefore = before
            ns.CaptureActiveSpecSnapshot()
            ns.AutoMarkWornPieces()
            local after = activeSpecID and db.bySpecID[tostring(activeSpecID)]
            -- Refresh the screens only when the loadout really changed (several captures follow every event).
            if after ~= tableBefore or (after and after.revision ~= revisionBefore) then
                RequestRefresh()
            end
        end)
    end
end

local function RegisterEventSafe(frame, event)
    if not frame or not event then return end
    pcall(frame.RegisterEvent, frame, event)
end

local frame = CreateFrame("Frame")
RegisterEventSafe(frame, "PLAYER_ENTERING_WORLD")
RegisterEventSafe(frame, "PLAYER_SPECIALIZATION_CHANGED")
RegisterEventSafe(frame, "ACTIVE_PLAYER_SPECIALIZATION_CHANGED")
RegisterEventSafe(frame, "PLAYER_LOGIN")
RegisterEventSafe(frame, "PLAYER_LEVEL_UP")
RegisterEventSafe(frame, "PLAYER_EQUIPMENT_CHANGED")
RegisterEventSafe(frame, "PLAYER_TALENT_UPDATE")
RegisterEventSafe(frame, "ACTIVE_TALENT_GROUP_CHANGED")
RegisterEventSafe(frame, "TRAIT_CONFIG_UPDATED")
RegisterEventSafe(frame, "TRAIT_SUB_TREE_CHANGED")
frame:SetScript("OnEvent", function(_, event, unit)
    if event == "UNIT_STATS" and unit ~= "player" then
        return
    end
    if event == "PLAYER_SPECIALIZATION_CHANGED" or event == "ACTIVE_PLAYER_SPECIALIZATION_CHANGED"
        or event == "PLAYER_ENTERING_WORLD" or event == "PLAYER_LOGIN" then
        NoteSpecChange()
    end
    ScheduleCapture()
end)

-- A separate frame: the capture frame above reacts to every one of its events with a new capture.
local pruneFrame = CreateFrame("Frame")
RegisterEventSafe(pruneFrame, "BAG_UPDATE_DELAYED")
RegisterEventSafe(pruneFrame, "PLAYER_ENTERING_WORLD")
pruneFrame:SetScript("OnEvent", function(_, event)
    -- After a loading screen the bags and banks need a moment to be known.
    SchedulePrune(event == "PLAYER_ENTERING_WORLD" and 15 or 1)
end)
