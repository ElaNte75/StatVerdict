local addonName, ns = ...

local Builder = {}
ns.Builder = Builder

local PRIMARY_BY_SPEC = {
    DEATHKNIGHT_BLOOD = "strength", DEATHKNIGHT_FROST = "strength", DEATHKNIGHT_UNHOLY = "strength",
    DEMONHUNTER_HAVOC = "agility", DEMONHUNTER_VENGEANCE = "agility", DEMONHUNTER_DEVOURER = "agility",
    DRUID_BALANCE = "intellect", DRUID_FERAL = "agility", DRUID_GUARDIAN = "agility", DRUID_RESTORATION = "intellect",
    EVOKER_DEVASTATION = "intellect", EVOKER_PRESERVATION = "intellect", EVOKER_AUGMENTATION = "intellect",
    HUNTER_BEAST_MASTERY = "agility", HUNTER_MARKSMANSHIP = "agility", HUNTER_SURVIVAL = "agility",
    MAGE_ARCANE = "intellect", MAGE_FIRE = "intellect", MAGE_FROST = "intellect",
    MONK_BREWMASTER = "agility", MONK_MISTWEAVER = "intellect", MONK_WINDWALKER = "agility",
    PALADIN_HOLY = "intellect", PALADIN_PROTECTION = "strength", PALADIN_RETRIBUTION = "strength",
    PRIEST_DISCIPLINE = "intellect", PRIEST_HOLY = "intellect", PRIEST_SHADOW = "intellect",
    ROGUE_ASSASSINATION = "agility", ROGUE_OUTLAW = "agility", ROGUE_SUBTLETY = "agility",
    SHAMAN_ELEMENTAL = "intellect", SHAMAN_ENHANCEMENT = "agility", SHAMAN_RESTORATION = "intellect",
    WARLOCK_AFFLICTION = "intellect", WARLOCK_DEMONOLOGY = "intellect", WARLOCK_DESTRUCTION = "intellect",
    WARRIOR_ARMS = "strength", WARRIOR_FURY = "strength", WARRIOR_PROTECTION = "strength",
}

local STAT_LABEL_TO_KEY = {
    ["critical strike"] = "critical-strike",
    ["crit"] = "critical-strike",
    ["haste"] = "haste",
    ["mastery"] = "mastery",
    ["versatility"] = "versatility",
    ["agility"] = "agility",
    ["intellect"] = "intellect",
    ["strength"] = "strength",
    ["stamina"] = "stamina",
}

local ARCHON_KEY_TO_CANON = {
    crit = "critical_strike",
    haste = "haste",
    mastery = "mastery",
    versatility = "versatility",
    critical_strike = "critical_strike",
    ["critical-strike"] = "critical_strike",
}

local function SpecKeyFromSlug(classToken, slug)
    local normalized = tostring(slug or ""):upper():gsub("%-", "_")
    return tostring(classToken or "") .. "_" .. normalized
end

local function NormalizeStatToken(label)
    if type(label) ~= "string" then
        return nil
    end
    local key = STAT_LABEL_TO_KEY[label:lower()]
    return key
end

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

local function FindGearSet(specData, wantedLabels)
    if type(specData) ~= "table" or type(specData.bisGear) ~= "table" then
        return nil
    end
    for _, wanted in ipairs(wantedLabels) do
        local wantedLower = wanted:lower()
        for _, gearSet in ipairs(specData.bisGear) do
            local label = tostring(gearSet and gearSet.label or ""):lower()
            if label == wantedLower then
                return gearSet
            end
        end
    end
    return specData.bisGear[1]
end

local function BuildPriorityProfiles(guideSpec)
    local out = {}
    local priorities = type(guideSpec) == "table" and guideSpec.priorities or nil
    if type(priorities) ~= "table" then
        return out
    end
    for _, row in ipairs(priorities) do
        if type(row) == "table" and type(row.stats) == "table" then
            local order = {}
            local tiers = {}
            for _, tier in ipairs(row.stats) do
                local tierKeys = {}
                if type(tier) == "table" then
                    for _, label in ipairs(tier) do
                        local key = NormalizeStatToken(label)
                        if key then
                            order[#order + 1] = key
                            tierKeys[#tierKeys + 1] = key
                        end
                    end
                end
                if #tierKeys > 0 then
                    tiers[#tiers + 1] = tierKeys
                end
            end
            if #order > 0 then
                out[#out + 1] = {
                    heroTalent = row.heroTalent or "All",
                    context = row.context or "General",
                    order = order,
                    tiers = tiers,
                }
            end
        end
    end
    return out
end

local function BuildBisFromSet(gearSet)
    if type(gearSet) ~= "table" or type(gearSet.slots) ~= "table" then
        return { label = "Unknown", slots = {} }
    end
    local slots = {}
    for _, slotInfo in ipairs(gearSet.slots) do
        local item = type(slotInfo) == "table" and slotInfo.item or nil
        if type(item) == "table" then
            local itemID = tonumber(item.itemId or item.itemID or item.id)
            if itemID then
                slots[#slots + 1] = {
                    slot = slotInfo.slot,
                    source = slotInfo.source or "",
                    item = {
                        item_id = itemID,
                        name = item.name or "",
                        bonus_ids = CopyArray(item.bonusIDs or item.bonus_ids or item.bonuses),
                    },
                }
            end
        end
    end
    return {
        label = gearSet.label or "Unknown",
        slots = slots,
    }
end

local function BuildPvpBis(murlokSpec)
    local slots = {}
    local gear = type(murlokSpec) == "table" and murlokSpec.bisGear or nil
    if type(gear) ~= "table" then
        return { label = "PvP", slots = slots }
    end
    for slotName, list in pairs(gear) do
        local first = type(list) == "table" and list[1] or nil
        local itemID = type(first) == "table" and tonumber(first.itemId or first.itemID) or nil
        if itemID then
            slots[#slots + 1] = {
                slot = slotName,
                source = "",
                item = { item_id = itemID },
            }
        end
    end
    return { label = "PvP", slots = slots }
end

local function BuildTrinkets(gearSpec, goal)
    local out = {}
    local list = type(gearSpec) == "table" and gearSpec.trinkets or nil
    if type(list) ~= "table" then
        return out
    end
    local want = goal == "RAID" and "raid" or (goal == "PVP" and "pvp" or "dungeon")
    for _, row in ipairs(list) do
        if type(row) == "table" then
            local contexts = row.contexts
            local ok = type(contexts) ~= "table"
            if type(contexts) == "table" then
                for _, ctx in ipairs(contexts) do
                    local c = tostring(ctx):lower()
                    if c == want or (want == "dungeon" and (c == "mythic+" or c == "m+")) then
                        ok = true
                        break
                    end
                end
            end
            if ok then
                out[#out + 1] = {
                    item_id = tonumber(row.itemId or row.itemID),
                    name = row.name or "",
                    source = row.source or "",
                    tier = row.tier,
                    contexts = CopyArray(row.contexts),
                    bonus_ids = CopyArray(row.bonusIDs or row.bonus_ids),
                }
            end
        end
    end
    return out
end

local function BuildCrafting(craftSpec, goal)
    local key = goal == "RAID" and "raid" or (goal == "PVP" and "pvp" or "mythicPlus")
    local block = type(craftSpec) == "table" and craftSpec[key] or nil
    if type(block) ~= "table" then
        return { context = key, crafts = {}, embellishments = {} }
    end
    local function mapList(list)
        local out = {}
        for _, row in ipairs(list or {}) do
            if type(row) == "table" then
                out[#out + 1] = {
                    item_id = tonumber(row.itemId or row.itemID),
                    name = row.name or "",
                    recipe_id = tonumber(row.recipeId or row.recipe_id),
                    popular = row.popular and true or nil,
                    bonus_ids = CopyArray(row.bonusIDs or row.bonus_ids),
                }
            end
        end
        return out
    end
    return {
        context = key,
        crafts = mapList(block.crafts),
        embellishments = mapList(block.embellishments),
    }
end

local function BuildStatTargets(archonSpec, murlokSpec, goal)
    if goal == "PVP" then
        local stats = {}
        local order = {}
        local list = type(murlokSpec) == "table" and murlokSpec.statPriority or nil
        if type(list) == "table" then
            for _, row in ipairs(list) do
                local canon = ARCHON_KEY_TO_CANON[tostring(row.key or ""):lower()]
                local rating = tonumber(row.rating)
                if canon and rating then
                    stats[canon] = rating
                    order[#order + 1] = canon
                end
            end
        end
        return {
            context = "PvP",
            source = "ClassCodex",
            stats = stats,
            order = order,
        }
    end

    local ctxName = goal == "RAID" and "Raid" or "Mythic+"
    local block = type(archonSpec) == "table" and archonSpec[ctxName] or nil
    local targets = type(block) == "table" and block.targets or nil
    local stats = {}
    if type(targets) == "table" then
        for key, value in pairs(targets) do
            local canon = ARCHON_KEY_TO_CANON[tostring(key):lower()]
            local n = tonumber(value)
            if canon and n then
                stats[canon] = n
            end
        end
    end
    return {
        context = ctxName,
        source = "ClassCodex",
        stats = stats,
    }
end

local function IndexResolved(entries)
    local by = {}
    for _, entry in ipairs(entries or {}) do
        if entry and entry.resolved then
            local classToken = entry.classToken
            local specKey = entry.specKey
            local label = tostring(entry.label or "")
            by[classToken] = by[classToken] or {}
            by[classToken][specKey] = by[classToken][specKey] or {}
            by[classToken][specKey][label] = by[classToken][specKey][label] or {}
            local bucket = by[classToken][specKey][label]
            bucket[#bucket + 1] = entry
        end
    end
    return by
end

local function SumResolvedForLabels(index, classToken, slug, labels)
    local classBucket = index[classToken] and index[classToken][slug]
    if not classBucket then
        return nil, 0, 0, 0
    end
    local chosen
    for _, label in ipairs(labels) do
        if classBucket[label] then
            chosen = classBucket[label]
            break
        end
    end
    if not chosen then
        return nil, 0, 0, 0
    end

    local stats = {}
    local ilvlSum, ilvlCount, itemCount = 0, 0, 0
    local lowReplacements = 0
    for _, entry in ipairs(chosen) do
        itemCount = itemCount + 1
        local ilvl = tonumber(entry.itemLevel)
        if ilvl and ilvl > 0 then
            ilvlSum = ilvlSum + ilvl
            ilvlCount = ilvlCount + 1
            if ilvl < 180 then
                lowReplacements = lowReplacements + 1
            end
        end
        if type(entry.stats) == "table" then
            for k, v in pairs(entry.stats) do
                stats[k] = (stats[k] or 0) + (tonumber(v) or 0)
            end
        end
    end
    local average = ilvlCount > 0 and (ilvlSum / ilvlCount) or nil
    return {
        averageItemLevel = average,
        itemCount = itemCount,
        itemLevelSlots = ilvlCount,
        stats = stats,
        targetMetadata = {
            lowItemReplacements = lowReplacements,
            unresolvedLowItems = 0,
        },
    }, itemCount, ilvlCount, lowReplacements
end

local function BuildContext(goal, guideSpec, icySpec, wowSpec, craftSpec, archonSpec, murlokSpec, resolvedIndex, classToken, slug)
    local labels
    if goal == "MYTHIC_PLUS" then
        labels = { "Mythic+", "Overall" }
    elseif goal == "RAID" then
        labels = { "Raid", "Overall" }
    else
        labels = { "PvP", "Overall" }
    end

    local gearSet
    if goal == "PVP" then
        gearSet = nil
    else
        gearSet = FindGearSet(icySpec, labels) or FindGearSet(wowSpec, labels)
    end

    local bis
    if goal == "PVP" then
        bis = BuildPvpBis(murlokSpec)
    else
        bis = BuildBisFromSet(gearSet)
        if goal == "MYTHIC_PLUS" then
            bis.label = "Mythic+"
        elseif goal == "RAID" then
            bis.label = "Raid"
        end
    end

    -- Murlok PvP recommendations are not part of the PvE resolver index.
    -- Never manufacture PvP gear totals from an arbitrary PvE set.
    local resolvedTargets = nil
    if goal ~= "PVP" then
        resolvedTargets = SumResolvedForLabels(resolvedIndex, classToken, slug, labels)
    end
    local targets = resolvedTargets or {
        averageItemLevel = nil,
        itemCount = 0,
        itemLevelSlots = 0,
        stats = {},
        targetMetadata = { lowItemReplacements = 0, unresolvedLowItems = 0 },
    }
    targets.statTargets = BuildStatTargets(archonSpec, murlokSpec, goal)
    targets.sourceGoal = goal
    targets.targetMetadata = targets.targetMetadata or {
        lowItemReplacements = 0,
        unresolvedLowItems = 0,
    }

    return {
        priorityProfiles = BuildPriorityProfiles(guideSpec),
        bis = bis,
        trinkets = BuildTrinkets(wowSpec or icySpec, goal),
        crafting = BuildCrafting(craftSpec, goal),
        targets = targets,
        targetMetadata = targets.targetMetadata,
    }
end

function Builder.Build(resolvedEntries, summary)
    local profiles = {}
    local guideRoot = _G.ClassCodexData or {}
    local icyRoot = _G.ClassCodexIcyVeinsData or {}
    local wowRoot = _G.ClassCodexGearData or {}
    local craftRoot = _G.ClassCodexCraftingData or {}
    local archonRoot = _G.ClassCodexArchonStats or {}
    local murlokRoot = _G.ClassCodexMurlokPvp or {}
    local resolvedIndex = IndexResolved(resolvedEntries)

    local classSeen = {}
    for classToken, classData in pairs(guideRoot) do
        classSeen[classToken] = true
        if type(classData) == "table" then
            for slug, guideSpec in pairs(classData) do
                local specKey = SpecKeyFromSlug(classToken, slug)
                local primary = PRIMARY_BY_SPEC[specKey]
                if primary then
                    profiles[specKey] = {
                        classToken = classToken,
                        specKey = specKey,
                        specSlug = tostring(slug),
                        primaryStat = primary,
                        contexts = {
                            MYTHIC_PLUS = BuildContext(
                                "MYTHIC_PLUS", guideSpec,
                                icyRoot[classToken] and icyRoot[classToken][slug],
                                wowRoot[classToken] and wowRoot[classToken][slug],
                                craftRoot[classToken] and craftRoot[classToken][slug],
                                archonRoot[classToken] and archonRoot[classToken][slug],
                                murlokRoot[classToken] and murlokRoot[classToken][slug],
                                resolvedIndex, classToken, slug
                            ),
                            RAID = BuildContext(
                                "RAID", guideSpec,
                                icyRoot[classToken] and icyRoot[classToken][slug],
                                wowRoot[classToken] and wowRoot[classToken][slug],
                                craftRoot[classToken] and craftRoot[classToken][slug],
                                archonRoot[classToken] and archonRoot[classToken][slug],
                                murlokRoot[classToken] and murlokRoot[classToken][slug],
                                resolvedIndex, classToken, slug
                            ),
                            PVP = BuildContext(
                                "PVP", guideSpec,
                                icyRoot[classToken] and icyRoot[classToken][slug],
                                wowRoot[classToken] and wowRoot[classToken][slug],
                                craftRoot[classToken] and craftRoot[classToken][slug],
                                archonRoot[classToken] and archonRoot[classToken][slug],
                                murlokRoot[classToken] and murlokRoot[classToken][slug],
                                resolvedIndex, classToken, slug
                            ),
                        },
                    }
                end
            end
        end
    end

    -- Include specs that exist only in gear tables (e.g. missing guide rows).
    for classToken, classData in pairs(icyRoot) do
        if type(classData) == "table" then
            for slug, _ in pairs(classData) do
                local specKey = SpecKeyFromSlug(classToken, slug)
                if not profiles[specKey] and PRIMARY_BY_SPEC[specKey] then
                    local guideSpec = guideRoot[classToken] and guideRoot[classToken][slug] or {}
                    profiles[specKey] = {
                        classToken = classToken,
                        specKey = specKey,
                        specSlug = tostring(slug),
                        primaryStat = PRIMARY_BY_SPEC[specKey],
                        contexts = {
                            MYTHIC_PLUS = BuildContext("MYTHIC_PLUS", guideSpec,
                                icyRoot[classToken] and icyRoot[classToken][slug],
                                wowRoot[classToken] and wowRoot[classToken][slug],
                                craftRoot[classToken] and craftRoot[classToken][slug],
                                archonRoot[classToken] and archonRoot[classToken][slug],
                                murlokRoot[classToken] and murlokRoot[classToken][slug],
                                resolvedIndex, classToken, slug),
                            RAID = BuildContext("RAID", guideSpec,
                                icyRoot[classToken] and icyRoot[classToken][slug],
                                wowRoot[classToken] and wowRoot[classToken][slug],
                                craftRoot[classToken] and craftRoot[classToken][slug],
                                archonRoot[classToken] and archonRoot[classToken][slug],
                                murlokRoot[classToken] and murlokRoot[classToken][slug],
                                resolvedIndex, classToken, slug),
                            PVP = BuildContext("PVP", guideSpec,
                                icyRoot[classToken] and icyRoot[classToken][slug],
                                wowRoot[classToken] and wowRoot[classToken][slug],
                                craftRoot[classToken] and craftRoot[classToken][slug],
                                archonRoot[classToken] and archonRoot[classToken][slug],
                                murlokRoot[classToken] and murlokRoot[classToken][slug],
                                resolvedIndex, classToken, slug),
                        },
                    }
                end
            end
        end
    end

    local profileCount = 0
    for _ in pairs(profiles) do
        profileCount = profileCount + 1
    end

    return {
        schemaVersion = 1,
        generatedAt = date("!%Y-%m-%dT%H:%M:%SZ"),
        source = {
            name = "ClassCodex",
            version = (_G.C_AddOns and C_AddOns.GetAddOnMetadata and C_AddOns.GetAddOnMetadata("ClassCodex", "Version")) or nil,
            resolverRun = date("!%Y-%m-%dT%H:%M:%SZ"),
            scrape = _G.ClassCodex_LastScrape,
            resolveSummary = summary,
            profileCount = profileCount,
        },
        profiles = profiles,
    }
end
