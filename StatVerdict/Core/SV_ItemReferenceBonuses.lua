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
    -- hero tree name the profile or its spec snapshot carries.
    local heroKey = type(profile) == "table" and profile.heroKey or nil
    if not heroKey and ns.ProfileRepository.ResolveHeroKey then
        local heroTalentName = type(profile) == "table" and profile.heroTalentName or nil
        heroTalentName = heroTalentName or (ns.GetSnapshotHeroTalentName and ns.GetSnapshotHeroTalentName(profile))
        heroKey = ns.ProfileRepository.ResolveHeroKey(specKey, goal, heroTalentName)
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
    local trinket = ResolveTrinketTier(heroDoc, itemID)
    if not bis and not trinket then return nil end

    return {
        itemID = itemID,
        goal = goal,
        bis = bis,
        trinket = trinket,
        bonus = (bis and bis.bonus or 0) + (trinket and trinket.bonus or 0),
    }
end

function ns.GetItemReferenceBonus(itemLink, profile)
    local info = ns.GetItemReferenceInfo(itemLink, profile)
    return info and tonumber(info.bonus) or 0, info
end
