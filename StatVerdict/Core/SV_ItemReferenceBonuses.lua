local addonName, ns = ...

local BIS_BONUS = 8
local TRINKET_TIER_BONUS = {
    -- Effect-first: tier gaps must outrun dampened secondary swings on trinkets.
    S = 95,
    A = 65,
    B = 35,
    C = 14,
    D = 0,
}
local MAX_RANK_BONUS = 5
local CATALYST_BONUS = BIS_BONUS

local CATALYST_EQUIP_LOCATIONS = {
    INVTYPE_HEAD = true,
    INVTYPE_SHOULDER = true,
    INVTYPE_CHEST = true,
    INVTYPE_ROBE = true,
    INVTYPE_HAND = true,
    INVTYPE_LEGS = true,
}

local BIS_SLOT_ALIASES_BY_EQUIP_LOCATION = {
    INVTYPE_HEAD = { "helm", "head" },
    INVTYPE_SHOULDER = { "shoulder", "shoulders" },
    INVTYPE_CHEST = { "chest" },
    INVTYPE_ROBE = { "chest", "robe" },
    INVTYPE_HAND = { "hands", "gloves" },
    INVTYPE_LEGS = { "legs" },
}

local function NormalizeToken(value)
    if type(value) ~= "string" then return "" end
    return value:lower():gsub("[^%a%d]+", "")
end

local function GetSpecKey(profile)
    if type(profile) ~= "table" then return nil end
    if type(profile.specKey) == "string" and profile.specKey ~= "" then
        return profile.specKey
    end
    if ns.GetStatVerdictSpecKeyBySpecID and profile.specID then
        local key = ns.GetStatVerdictSpecKeyBySpecID(profile.specID)
        if type(key) == "string" and key ~= "" then return key end
    end
    return nil
end

local function ResolveHeroDocument(profile)
    if not ns.ProfileRepository then return nil, nil end
    local goal = type(profile) == "table" and profile.goal or nil
    goal = goal or (ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode()) or "MYTHIC_PLUS"
    local specKey = GetSpecKey(profile)
    local context = specKey and ns.ProfileRepository.GetContext(specKey, goal) or nil
    return context, goal
end

local function GetItemID(itemLink)
    if ns.GetItemID then return ns.GetItemID(itemLink) end
    if not itemLink then return nil end
    local id = tostring(itemLink):match("item:(%d+)")
    return id and tonumber(id) or nil
end

local function GetItemEquipLocation(itemLink)
    return ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
end

local function HasUpgradeTrack(itemLink)
    if type(C_TooltipInfo) ~= "table" or type(C_TooltipInfo.GetHyperlink) ~= "function" then
        return false
    end
    local data = C_TooltipInfo.GetHyperlink(itemLink)
    if type(data) ~= "table" or type(data.lines) ~= "table" then return false end
    for _, line in ipairs(data.lines) do
        local text = line and line.leftText
        if type(text) == "string" then
            text = text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
            if text:find("^Upgrade Level:") then
                return true
            end
        end
    end
    return false
end

local function FindBisEntry(reference, itemID)
    local slots = type(reference) == "table" and reference.slots or nil
    if type(slots) ~= "table" then return nil end
    for _, entry in ipairs(slots) do
        local item = type(entry) == "table" and entry.item or nil
        if itemID and type(item) == "table" and tonumber(item.item_id or item.itemID) == itemID then
            return entry
        end
    end
    return nil
end

local function FindSameSlotBisEntry(reference, equipLocation)
    local slots = type(reference) == "table" and reference.slots or nil
    local aliases = BIS_SLOT_ALIASES_BY_EQUIP_LOCATION[equipLocation]
    if type(slots) ~= "table" or type(aliases) ~= "table" then return nil end

    local wanted = {}
    for _, alias in ipairs(aliases) do
        wanted[NormalizeToken(alias)] = true
    end

    for _, entry in ipairs(slots) do
        local slot = NormalizeToken(type(entry) == "table" and entry.slot or nil)
        if wanted[slot] then return entry end
    end
    return nil
end

local function IsCatalystSource(entry)
    local source = type(entry) == "table" and tostring(entry.source or "") or ""
    return source:lower():find("catalyst", 1, true) ~= nil
end

local function ResolveBis(heroDoc, goal, itemID)
    if type(heroDoc) ~= "table" then return nil end
    local reference = heroDoc.bis
    local entry = FindBisEntry(reference, itemID)
    if not entry then return nil end
    return {
        bonus = BIS_BONUS,
        slot = entry.slot,
        source = entry.source,
        listLabel = type(reference) == "table" and reference.label or nil,
    }
end

local function ResolveCatalystPath(heroDoc, itemLink, itemID)
    if type(heroDoc) ~= "table" or not itemID then return nil end
    local equipLocation = GetItemEquipLocation(itemLink)
    if not CATALYST_EQUIP_LOCATIONS[equipLocation] then return nil end
    if not HasUpgradeTrack(itemLink) then return nil end

    local reference = heroDoc.bis
    local entry = FindSameSlotBisEntry(reference, equipLocation)
    if not entry or not IsCatalystSource(entry) then return nil end

    local targetItem = type(entry.item) == "table" and entry.item or nil
    local targetItemID = tonumber(targetItem and (targetItem.item_id or targetItem.itemID) or nil)
    if not targetItemID or targetItemID == itemID then return nil end

    return {
        bonus = CATALYST_BONUS,
        slot = entry.slot,
        source = entry.source,
        targetItemID = targetItemID,
        targetName = targetItem.name,
        listLabel = type(reference) == "table" and reference.label or nil,
    }
end

local function ResolveTrinketTier(heroDoc, itemID)
    local entries = type(heroDoc) == "table" and heroDoc.trinkets or nil
    if type(entries) ~= "table" or not itemID then return nil end

    local rankByTier = {}
    for _, entry in ipairs(entries) do
        if type(entry) == "table" then
            local tier = tostring(entry.tier or ""):upper()
            if TRINKET_TIER_BONUS[tier] then
                rankByTier[tier] = (rankByTier[tier] or 0) + 1
                if tonumber(entry.item_id or entry.itemID) == itemID then
                    local rank = rankByTier[tier]
                    local rankBonus = math.max(0, MAX_RANK_BONUS - rank + 1)
                    return {
                        tier = tier,
                        rank = rank,
                        tierBonus = TRINKET_TIER_BONUS[tier],
                        rankBonus = rankBonus,
                        bonus = TRINKET_TIER_BONUS[tier] + rankBonus,
                        source = entry.source,
                    }
                end
            end
        end
    end
    return nil
end

function ns.GetItemReferenceInfo(itemLink, profile)
    local itemID = GetItemID(itemLink)
    if not itemID then return nil end

    local heroDoc, goal = ResolveHeroDocument(profile)
    if type(heroDoc) ~= "table" then return nil end

    local bis = ResolveBis(heroDoc, goal, itemID)
    local catalystPath = (not bis) and ResolveCatalystPath(heroDoc, itemLink, itemID) or nil
    local trinket = ResolveTrinketTier(heroDoc, itemID)
    if not bis and not catalystPath and not trinket then return nil end

    local total = (bis and bis.bonus or 0) + (catalystPath and catalystPath.bonus or 0) + (trinket and trinket.bonus or 0)
    return {
        itemID = itemID,
        goal = goal,
        bis = bis,
        catalystPath = catalystPath,
        trinket = trinket,
        bonus = total,
    }
end

function ns.GetItemReferenceBonus(itemLink, profile)
    local info = ns.GetItemReferenceInfo(itemLink, profile)
    return info and tonumber(info.bonus) or 0, info
end
