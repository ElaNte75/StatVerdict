local addonName, ns = ...

local function StripText(text)
    if type(text) ~= "string" then return nil end
    text = text:gsub("|c%x%x%x%x%x%x%x%x", "")
    text = text:gsub("|r", "")
    return text
end

local function GetItemInfoSafe(itemLink)
    if not itemLink then
        return nil
    end
    return { C_Item.GetItemInfo(itemLink) }
end

local function GetItemInfoInstantSafe(itemLink)
    if not itemLink or type(C_Item) ~= "table" or type(C_Item.GetItemInfoInstant) ~= "function" then
        return nil
    end
    local ok, itemID, itemType, itemSubType, itemEquipLoc, icon, classID, subClassID = pcall(C_Item.GetItemInfoInstant, itemLink)
    if not ok then
        return nil
    end
    return itemID, itemType, itemSubType, itemEquipLoc, icon, classID, subClassID
end

local function ParseItemLevelText(text)
    text = StripText(text)
    if type(text) ~= "string" then return nil end

    local label = tostring(ITEM_LEVEL or "Item Level %d")
    label = label:gsub("%%d", "")
    label = label:gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", "")
    if label ~= "" and text:find(label, 1, true) then
        return tonumber(text:match("(%d+)"))
    end

    return tonumber(text:match("^Item Level%s+(%d+)"))
end

local function GetTooltipItemLevel(itemLink)
    if not itemLink then return nil end

    if type(C_TooltipInfo) == "table" and type(C_TooltipInfo.GetHyperlink) == "function" then
        local data = C_TooltipInfo.GetHyperlink(itemLink)
        if type(data) == "table" and type(data.lines) == "table" then
            for _, line in ipairs(data.lines) do
                local level = ParseItemLevelText(line and line.leftText)
                if level then return level end
            end
        end
    end

    return nil
end

function ns.GetItemEquipLocation(itemLink)
    local info = GetItemInfoSafe(itemLink)
    local equipLocation = info and info[9] or nil
    if equipLocation and equipLocation ~= "" then
        return equipLocation
    end
    local _, _, _, instantEquipLocation = GetItemInfoInstantSafe(itemLink)
    if instantEquipLocation and instantEquipLocation ~= "" then
        return instantEquipLocation
    end
    return nil
end

function ns.GetItemLevel(itemLink)
    if not itemLink then
        return nil
    end
    local tooltipLevel = GetTooltipItemLevel(itemLink)
    if tooltipLevel then
        return tooltipLevel
    end
    if C_Item.GetDetailedItemLevelInfo then
        local level = C_Item.GetDetailedItemLevelInfo(itemLink)
        if level then
            return level
        end
    end
    return select(4, C_Item.GetItemInfo(itemLink))
end

function ns.GetItemUpgradeInfo(itemLink)
    if not itemLink or type(C_Item) ~= "table" or type(C_Item.GetItemUpgradeInfo) ~= "function" then
        return nil
    end
    local ok, info = pcall(C_Item.GetItemUpgradeInfo, itemLink)
    return ok and type(info) == "table" and info or nil
end

function ns.GetItemID(itemLink)
    if not itemLink then return nil end
    local itemID = GetItemInfoInstantSafe(itemLink)
    if itemID then return tonumber(itemID) end
    local id = tostring(itemLink):match("item:(%d+)")
    return id and tonumber(id) or nil
end

function ns.GetItemQuality(itemLink)
    if not itemLink then return nil end
    if type(C_Item) == "table" and type(C_Item.GetItemInfo) == "function" then
        local quality = select(3, C_Item.GetItemInfo(itemLink))
        if quality ~= nil then return tonumber(quality) end
    elseif type(GetItemInfo) == "function" then
        local quality = select(3, GetItemInfo(itemLink))
        if quality ~= nil then return tonumber(quality) end
    end
    return nil
end
