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

function ns.IsItemInEquipmentSnapshot(profile, itemLink)
    if not GetItemIDFromLink(itemLink) then return false end
    local snapshot = GetSnapshot(profile)
    local links = snapshot and snapshot.equipment
    if type(links) ~= "table" then return false end
    for slotID, equippedLink in pairs(links) do
        if SnapshotLinksMatch(itemLink, equippedLink) then
            return true, SafeNumber(slotID), equippedLink
        end
    end
    return false
end



function ns.GetEquipmentSnapshotItemRole(itemLink)
    if not GetItemIDFromLink(itemLink) then return nil end
    local db = EnsureDB()
    local snapshots = db and db.bySpecID
    if type(snapshots) ~= "table" then return nil end

    local function containsSnapshot(snapshot)
        local links = snapshot and snapshot.equipment
        if type(links) ~= "table" then return false end
        for _, equippedLink in pairs(links) do
            if SnapshotLinksMatch(itemLink, equippedLink) then
                return true
            end
        end
        return false
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

-- Approve an item into a spec's virtual loadout without requiring equip or respec.
-- Works for any class/spec. slotID is optional; when omitted, comparison selects the best target slot.
function ns.ApproveItemIntoVirtualLoadout(itemLink, profile, slotID)
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
function ns.RemoveItemFromVirtualLoadout(itemLink, profile)
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
    for slotKey, savedLink in pairs(equipment) do
        if type(savedLink) == "string" and SnapshotLinksMatch(itemLink, savedLink) then
            removedSlot = SafeNumber(slotKey)
            local worn = type(GetInventoryItemLink) == "function"
                and GetInventoryItemLink("player", removedSlot) or nil
            equipment[slotKey] = worn
            break
        end
    end
    if not removedSlot then
        return false, "This item is not saved in that loadout."
    end

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
            if type(prevLink) == "string" and prevLink ~= "" and ItemLinkInPlayerBags(prevLink) then
                local wornLink = equipment[slotKey]
                if not wornLink or not SnapshotLinksMatch(wornLink, prevLink) then
                    equipment[slotKey] = prevLink
                    preservedApprove = true
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
        lastApprovedSlot = previous and previous.lastApprovedSlot or nil,
        lastApprovedLink = previous and previous.lastApprovedLink or nil,
    }

    return db.bySpecID[specKey]
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
end

local function ScheduleCapture()
    if IsInCombat() then return end
    captureScheduleToken = captureScheduleToken + 1
    local token = captureScheduleToken
    for index, delay in ipairs(CAPTURE_DELAYS) do
        C_Timer.After(delay, function()
            if token ~= captureScheduleToken or IsInCombat() then return end
            ns.CaptureActiveSpecSnapshot()
            RequestRefresh()
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
    ScheduleCapture()
end)
