local addonName, ns = ...

local Resolver = {}
ns.Resolver = Resolver

local MAX_PER_TICK = 25
local pendingQueue = {}
local pendingByKey = {}
local isRunning = false
local ticker = nil
local onComplete = nil
local onProgress = nil

local function CopyArray(values)
    local out = {}
    if type(values) ~= "table" then
        return out
    end
    for i = 1, #values do
        out[i] = values[i]
    end
    return out
end

local function Join(values, separator)
    local parts = {}
    if type(values) ~= "table" then
        return ""
    end
    for i = 1, #values do
        parts[#parts + 1] = tostring(values[i])
    end
    return table.concat(parts, separator or ":")
end

local function MakeItemKey(source, classToken, specKey, setLabel, slotName, itemID, bonusIDs)
    return table.concat({
        tostring(source or ""),
        tostring(classToken or ""),
        tostring(specKey or ""),
        tostring(setLabel or ""),
        tostring(slotName or ""),
        tostring(itemID or ""),
        Join(bonusIDs, "."),
    }, "|")
end

local function BuildItemString(itemID, bonusIDs)
    local id = tonumber(itemID)
    if not id then
        return nil
    end
    if type(bonusIDs) ~= "table" or #bonusIDs == 0 then
        return "item:" .. id
    end
    local level = 90
    if UnitLevel then
        local unitLevel = tonumber(UnitLevel("player"))
        if unitLevel and unitLevel > 0 then
            level = unitLevel
        end
    end
    return ("item:%d::::::::%d::::%d:%s"):format(id, level, #bonusIDs, Join(bonusIDs, ":"))
end

local function NormalizeStatKey(statKey)
    local key = tostring(statKey or "")
    if key:find("AGILITY") then return "agility" end
    if key:find("INTELLECT") then return "intellect" end
    if key:find("STRENGTH") then return "strength" end
    if key:find("STAMINA") then return "stamina" end
    if key:find("CRIT") then return "critical_strike" end
    if key:find("HASTE") then return "haste" end
    if key:find("MASTERY") then return "mastery" end
    if key:find("VERSATILITY") then return "versatility" end
    if key:find("AVOIDANCE") then return "avoidance" end
    if key:find("LEECH") then return "leech" end
    if key:find("SPEED") then return "speed" end
    if key:find("ARMOR") then return "armor" end
    return key
end

local function NormalizeStats(rawStats)
    local stats = {}
    if type(rawStats) ~= "table" then
        return stats
    end
    for key, amount in pairs(rawStats) do
        local normalized = NormalizeStatKey(key)
        local value = tonumber(amount)
        if normalized and value then
            stats[normalized] = (stats[normalized] or 0) + value
        end
    end
    return stats
end

local function ResolveEntry(entry)
    local itemString = entry.itemString
    if not itemString then
        entry.resolved = false
        entry.reason = "missing item string"
        return false
    end

    local itemName, itemLink, quality, itemLevel, _, _, _, _, equipLoc, icon, classID, subClassID
    if C_Item and C_Item.GetItemInfo then
        itemName, itemLink, quality, itemLevel, _, _, _, _, equipLoc, icon, classID, subClassID = C_Item.GetItemInfo(itemString)
    end

    if C_Item and C_Item.GetItemInfoInstant then
        local _, _, _, instantEquipLoc, instantIcon, instantClassID, instantSubClassID = C_Item.GetItemInfoInstant(entry.itemID)
        equipLoc = equipLoc or instantEquipLoc
        icon = icon or instantIcon
        classID = classID or instantClassID
        subClassID = subClassID or instantSubClassID
    end

    local detailedItemLevel
    if C_Item and C_Item.GetDetailedItemLevelInfo then
        detailedItemLevel = C_Item.GetDetailedItemLevelInfo(itemLink or itemString)
    end

    local rawStats
    if C_Item and C_Item.GetItemStats then
        rawStats = C_Item.GetItemStats(itemLink or itemString)
    end

    entry.itemNameResolved = itemName
    entry.itemLink = itemLink
    entry.quality = quality
    entry.itemLevel = detailedItemLevel or itemLevel
    entry.equipLoc = equipLoc
    entry.icon = icon
    entry.classID = classID
    entry.subClassID = subClassID
    entry.rawStats = rawStats
    entry.stats = NormalizeStats(rawStats)

    if itemLink and rawStats then
        entry.resolved = true
        entry.reason = nil
        return true
    end

    entry.resolved = false
    entry.reason = itemLink and "stats not available" or "item data not cached"
    return false
end

local function RequestItemData(entry)
    if C_Item and C_Item.RequestLoadItemDataByID and entry.itemID then
        pcall(C_Item.RequestLoadItemDataByID, entry.itemID)
    end
    if Item and Item.CreateFromItemLink and entry.itemString then
        local ok, item = pcall(Item.CreateFromItemLink, entry.itemString)
        if ok and item and item.ContinueOnItemLoad then
            item:ContinueOnItemLoad(function()
                ResolveEntry(entry)
            end)
        end
    end
end

local function AddEntry(entries, sourceName, classToken, specKey, setLabel, slotInfo)
    if type(slotInfo) ~= "table" or type(slotInfo.item) ~= "table" then
        return
    end
    local item = slotInfo.item
    local itemID = tonumber(item.itemId or item.itemID or item.id)
    if not itemID then
        return
    end
    local bonusIDs = CopyArray(item.bonusIDs or item.bonus_ids or item.bonuses)
    local itemString = BuildItemString(itemID, bonusIDs)
    local key = MakeItemKey(sourceName, classToken, specKey, setLabel, slotInfo.slot, itemID, bonusIDs)
    entries[#entries + 1] = {
        key = key,
        source = sourceName,
        classToken = classToken,
        specKey = specKey,
        label = setLabel,
        slot = slotInfo.slot,
        itemID = itemID,
        itemName = item.name,
        bonusIDs = bonusIDs,
        itemString = itemString,
        sourceText = slotInfo.source,
        resolved = false,
    }
end

local function ReadBISSource(entries, sourceName, sourceData)
    if type(sourceData) ~= "table" then
        return
    end
    for classToken, classData in pairs(sourceData) do
        if type(classData) == "table" then
            for specKey, specData in pairs(classData) do
                if type(specData) == "table" and type(specData.bisGear) == "table" then
                    for _, gearSet in ipairs(specData.bisGear) do
                        if type(gearSet) == "table" and type(gearSet.slots) == "table" then
                            local label = gearSet.label or "Unlabeled"
                            for _, slotInfo in ipairs(gearSet.slots) do
                                AddEntry(entries, sourceName, classToken, specKey, label, slotInfo)
                            end
                        end
                    end
                end
            end
        end
    end
end

local function BuildEntries()
    local entries = {}
    ReadBISSource(entries, "ClassCodexIcyVeins", _G.ClassCodexIcyVeinsData)
    ReadBISSource(entries, "ClassCodexWowhead", _G.ClassCodexGearData)
    return entries
end

local function CountResolved(entries)
    local total, resolved = 0, 0
    for _, entry in ipairs(entries or {}) do
        total = total + 1
        if entry.resolved then
            resolved = resolved + 1
        end
    end
    return total, resolved, total - resolved
end

local function FinishRun(entries)
    isRunning = false
    if ticker then
        ticker:Cancel()
        ticker = nil
    end
    local total, resolved, unresolved = CountResolved(entries)
    if onProgress then
        onProgress(("Resolve complete: %d / %d (%d unresolved)"):format(resolved, total, unresolved))
    end
    if onComplete then
        onComplete(entries, {
            total = total,
            resolved = resolved,
            unresolved = unresolved,
        })
    end
end

local function ProcessQueue(entries)
    if not isRunning then
        return
    end

    local processed = 0
    local remaining = {}
    for _, entry in ipairs(pendingQueue) do
        if processed < MAX_PER_TICK then
            processed = processed + 1
            if ResolveEntry(entry) then
                pendingByKey[entry.key] = nil
            else
                entry.resolveAttempts = (entry.resolveAttempts or 0) + 1
                if entry.resolveAttempts >= 8 then
                    pendingByKey[entry.key] = nil
                else
                    RequestItemData(entry)
                    remaining[#remaining + 1] = entry
                end
            end
        else
            remaining[#remaining + 1] = entry
        end
    end
    pendingQueue = remaining

    local total, resolved = CountResolved(entries)
    if onProgress and (resolved == total or resolved % 50 == 0 or #pendingQueue == 0) then
        onProgress(("Resolving items: %d / %d (%d pending)"):format(resolved, total, #pendingQueue))
    end

    if #pendingQueue == 0 then
        FinishRun(entries)
    end
end

function Resolver.IsRunning()
    return isRunning
end

function Resolver.Start(progressCb, completeCb)
    if isRunning then
        if progressCb then
            progressCb("Resolver already running.")
        end
        return false
    end

    if not _G.ClassCodexGearData and not _G.ClassCodexIcyVeinsData then
        if progressCb then
            progressCb("ClassCodex data is not loaded. Enable Class Codex and /reload.")
        end
        return false
    end

    onProgress = progressCb
    onComplete = completeCb

    local entries = BuildEntries()
    pendingQueue = {}
    pendingByKey = {}
    for _, entry in ipairs(entries) do
        pendingQueue[#pendingQueue + 1] = entry
        pendingByKey[entry.key] = entry
    end

    isRunning = true
    if onProgress then
        onProgress(("Resolver started: %d BIS entries."):format(#pendingQueue))
    end
    ProcessQueue(entries)
    if isRunning and not ticker then
        ticker = C_Timer.NewTicker(0.5, function()
            ProcessQueue(entries)
        end)
    end
    return true
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("ITEM_DATA_LOAD_RESULT")
frame:SetScript("OnEvent", function(_, _, itemID, success)
    if not success or not itemID then
        return
    end
    for key, entry in pairs(pendingByKey) do
        if entry.itemID == itemID and ResolveEntry(entry) then
            pendingByKey[key] = nil
        end
    end
end)
