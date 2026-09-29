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
-- An item the Catalyst can turn into the BiS set piece counts as that piece.
local CATALYST_BONUS = BIS_BONUS

-- The slots the Catalyst can convert.
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

-- BiS item ids whose item data was requested from the game (set id unknown yet).
local pendingSetLoads = {}

local function NormalizeToken(value)
    if type(value) ~= "string" then return "" end
    return (value:lower():gsub("[^%a%d]+", ""))
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
    if not specKey then return nil, goal end
    -- BiS and trinket lists are per hero tree: use the profile's own tree
    -- (set by ProfileRepository.BuildRuntimeProfile), else resolve it from the
    -- hero subtree ID / hero tree name the profile or its spec snapshot carries.
    local heroKey = type(profile) == "table" and profile.heroKey or nil
    if not heroKey and ns.ProfileRepository.ResolveHeroKey then
        local heroTalentName = type(profile) == "table" and profile.heroTalentName or nil
        heroTalentName = heroTalentName or (ns.GetSnapshotHeroTalentName and ns.GetSnapshotHeroTalentName(profile))
        local heroSubTreeID = type(profile) == "table" and profile.heroSubTreeID or nil
        heroSubTreeID = heroSubTreeID or (ns.GetSnapshotHeroSubTreeID and ns.GetSnapshotHeroSubTreeID(profile))
        heroKey = ns.ProfileRepository.ResolveHeroKey(specKey, goal, heroTalentName, heroSubTreeID)
    end
    local context = heroKey and ns.ProfileRepository.GetContext(specKey, goal, heroKey) or nil
    return context, goal
end

local function GetItemID(itemLink)
    if ns.GetItemID then return ns.GetItemID(itemLink) end
    if not itemLink then return nil end
    local id = tostring(itemLink):match("item:(%d+)")
    return id and tonumber(id) or nil
end

local function FindBisEntry(reference, itemID)
    local slots = type(reference) == "table" and reference.slots or nil
    if type(slots) ~= "table" then return nil end
    for _, entry in ipairs(slots) do
        local item = type(entry) == "table" and entry.item or nil
        if itemID and type(item) == "table" and tonumber(item.item_id) == itemID then
            return entry
        end
    end
    return nil
end

local function ResolveBis(heroDoc, itemID)
    if type(heroDoc) ~= "table" then return nil end
    local reference = heroDoc.bis
    local entry = FindBisEntry(reference, itemID)
    if not entry then return nil end
    return {
        bonus = BIS_BONUS,
        slot = entry.slot,
        listLabel = type(reference) == "table" and reference.label or nil,
    }
end

local function HasUpgradeTrack(itemLink)
    if type(C_Item) == "table" and type(C_Item.GetItemUpgradeInfo) == "function" then
        local ok, info = pcall(C_Item.GetItemUpgradeInfo, itemLink)
        if ok and type(info) == "table" then return true end
    end
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

-- Is the item part of an item set (a tier set piece)? Asks the game: the item
-- set id is the 16th value C_Item.GetItemInfo returns. true / false when the
-- item data is loaded; nil (unknown) when it is not yet: the data is requested
-- and GET_ITEM_INFO_RECEIVED below refreshes the verdicts once it arrives.
local function IsSetPiece(itemID)
    if type(C_Item) ~= "table" or type(C_Item.GetItemInfo) ~= "function" then return nil end
    local ok, name, _, _, _, _, _, _, _, _, _, _, _, _, _, _, setID = pcall(C_Item.GetItemInfo, itemID)
    if ok and name ~= nil then
        pendingSetLoads[itemID] = nil
        return (tonumber(setID) or 0) > 0
    end
    if type(C_Item.RequestLoadItemDataByID) == "function" then
        pendingSetLoads[itemID] = true
        pcall(C_Item.RequestLoadItemDataByID, itemID)
    end
    return nil
end

local function ResolveCatalystPath(heroDoc, itemLink, itemID)
    if type(heroDoc) ~= "table" or not itemID or type(C_Item) ~= "table" then return nil end
    local equipLocation = ns.GetItemEquipLocation and ns.GetItemEquipLocation(itemLink) or nil
    if not CATALYST_EQUIP_LOCATIONS[equipLocation] then return nil end

    local entry = FindSameSlotBisEntry(heroDoc.bis, equipLocation)
    local targetItem = entry and type(entry.item) == "table" and entry.item or nil
    local targetItemID = tonumber(targetItem and targetItem.item_id or nil)
    if not targetItemID or targetItemID == itemID then return nil end
    if not HasUpgradeTrack(itemLink) then return nil end
    if IsSetPiece(targetItemID) ~= true then return nil end

    return {
        bonus = CATALYST_BONUS,
        slot = entry.slot,
        targetItemID = targetItemID,
    }
end

if type(CreateFrame) == "function" then
    local setDataFrame = CreateFrame("Frame")
    setDataFrame:RegisterEvent("GET_ITEM_INFO_RECEIVED")
    setDataFrame:SetScript("OnEvent", function(_, event, itemID)
        itemID = tonumber(itemID)
        if event ~= "GET_ITEM_INFO_RECEIVED" or not itemID or not pendingSetLoads[itemID] then return end
        pendingSetLoads[itemID] = nil
        -- Verdicts cached while the set piece was unknown are stale now.
        if ns.ClearUpgradeIndicatorDecisionCache then ns.ClearUpgradeIndicatorDecisionCache() end
        if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators("full") end
    end)
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
                if tonumber(entry.item_id) == itemID then
                    local rank = rankByTier[tier]
                    local rankBonus = math.max(0, MAX_RANK_BONUS - rank + 1)
                    return {
                        tier = tier,
                        rank = rank,
                        tierBonus = TRINKET_TIER_BONUS[tier],
                        rankBonus = rankBonus,
                        bonus = TRINKET_TIER_BONUS[tier] + rankBonus,
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

    local bis = ResolveBis(heroDoc, itemID)
    local catalystPath = (not bis) and ResolveCatalystPath(heroDoc, itemLink, itemID) or nil
    local trinket = ResolveTrinketTier(heroDoc, itemID)
    if not bis and not catalystPath and not trinket then return nil end

    return {
        itemID = itemID,
        goal = goal,
        bis = bis,
        catalystPath = catalystPath,
        trinket = trinket,
        bonus = (bis and bis.bonus or 0) + (catalystPath and catalystPath.bonus or 0) + (trinket and trinket.bonus or 0),
    }
end

function ns.GetItemReferenceBonus(itemLink, profile)
    local info = ns.GetItemReferenceInfo(itemLink, profile)
    return info and tonumber(info.bonus) or 0, info
end
