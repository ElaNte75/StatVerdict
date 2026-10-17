local addonName, ns = ...

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
        -- The spec that is played: what is worn, or the piece marked for the slot that sits in the bags.
        itemLink = (ns.GetPlayedLoadoutOverlay and ns.GetPlayedLoadoutOverlay(profile, slotID)) or GetEquippedLink(slotID)
    end
    if itemLink and ns.IsItemCompatibleWithSlot and not ns.IsItemCompatibleWithSlot(itemLink, profile, slotID) then
        return nil
    end
    return itemLink
end

-- A piece counts as an upgrade only when it is worth at least this percent of the piece it replaces:
-- a gain of a few points is a sidegrade, not a reason to show an arrow.
local MIN_UPGRADE_PERCENT = 1.0

-- Clearly more item level (10 or more, outside jewelry and trinkets) is an upgrade whatever its size in points,
-- whether the Item Level Guard had to lift the verdict or the stats already gave a small positive one.
local function IsLiftedByItemLevel(deltaRows)
    if type(deltaRows) == "table" and deltaRows.itemLevelWin == true then
        return true
    end
    for _, row in ipairs(deltaRows or {}) do
        if type(row) == "table" and row.statKey == "STATVERDICT_ITEM_LEVEL_GUARD" and (tonumber(row.signedPoints) or 0) > 0 then
            return true
        end
    end
    return false
end

-- Room to grow: how many item levels a piece can still gain on its upgrade track (0 when it is at the top of its track,
-- or on none). Two pieces that are equal today are not equal for the player: the one with room can be raised.
local function UpgradeHeadroom(itemLink)
    if not itemLink or not ns.GetItemUpgradeCeiling or not ns.GetItemLevel then return 0 end
    local top = ns.GetItemUpgradeCeiling(itemLink)
    local level = tonumber(ns.GetItemLevel(itemLink))
    if not top or top <= 0 or not level then return 0 end
    return math.max(0, top - level)
end

-- A small push for the piece with more room to grow, only where today's stats leave it undecided: a gain below the
-- upgrade threshold, or a loss smaller than the push. Real differences are never overruled: it only turns an "almost"
-- into an upgrade. Returns the percent added (0 when it does not apply).
local POTENTIAL_PERCENT_PER_LEVEL = 0.10
local POTENTIAL_PERCENT_CAP = 1.50
local function PotentialPercent(candidateLink, equippedLink)
    local extra = UpgradeHeadroom(candidateLink) - UpgradeHeadroom(equippedLink)
    if extra <= 0 then return 0 end
    return math.min(POTENTIAL_PERCENT_CAP, extra * POTENTIAL_PERCENT_PER_LEVEL)
end

-- Prospect: a piece that can still grow and sits on a higher upgrade track than the worn one is judged against the
-- Myth 6/6 targets, the end goal, instead of the shown tier's: it must not lose points for passing a lower tier's target
-- it will need to pass anyway. The profile then carries the Myth targets (profile.mythAuditTargets); a copy that
-- uses them is made once per profile.
local function UpgradeCeiling(itemLink)
    return itemLink and ns.GetItemUpgradeCeiling and ns.GetItemUpgradeCeiling(itemLink) or nil
end

local function HasProspect(candidateLink, equippedLink)
    if UpgradeHeadroom(candidateLink) <= 0 then return false end
    local candidateTop = UpgradeCeiling(candidateLink)
    if not candidateTop then return false end
    local equippedTop = UpgradeCeiling(equippedLink) or tonumber(ns.GetItemLevel and ns.GetItemLevel(equippedLink)) or 0
    return candidateTop > equippedTop
end

local function ProspectProfile(profile, candidateLink, equippedLink)
    local mythTargets = type(profile) == "table" and profile.mythAuditTargets or nil
    if type(mythTargets) ~= "table" or not HasProspect(candidateLink, equippedLink) then return profile end
    if profile.mythView == nil or profile.mythViewSource ~= mythTargets then
        local view = {}
        for key, value in pairs(profile) do view[key] = value end
        view.auditTargets = mythTargets
        view.mythAuditTargets = nil
        profile.mythView, profile.mythViewSource = view, mythTargets
    end
    return profile.mythView
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

-- Weapons. The guide decides how a spec holds its weapons: its Best in Slot list has a weapon in the Off Hand slot (two
-- one-handers, "DUAL"; two-handers in both hands, "DUAL2H") or it has none (a two-hander, or a one-hander with a shield or
-- a held item, "SINGLE"). nil when the list or the item data is not there yet: nothing changes then.
local ONE_HAND_WEAPON_LOCATIONS = {
    INVTYPE_WEAPON = true,
    INVTYPE_WEAPONMAINHAND = true,
    INVTYPE_WEAPONOFFHAND = true,
}
local PAIR_MAX_WEAPONS = 8          -- the best pair is looked for among at most this many weapons of the bags
local PAIR_ITEM_LEVEL_SLACK = 10    -- a weapon counts for a pair from this far below the worn two-hander
-- The guide plays two weapons: a pair that is not far below the worn two-hander is what it asks for (two weapons attack
-- faster, and the off hand is used), so the pair is worth as much extra as a piece of the Best in Slot list. Weapons with
-- much worse stats still lose it.
local DUAL_WIELD_BONUS = 100

function ns.GetGuideWeaponSetup(profile)
    local context = type(profile) == "table" and profile.generatedContext or nil
    local slots = type(context) == "table" and type(context.bis) == "table" and context.bis.slots or nil
    if type(slots) ~= "table" or not ns.GetItemEquipLocation then return nil end
    local main, off = nil, nil
    for _, entry in ipairs(slots) do
        if type(entry) == "table" and type(entry.item) == "table" then
            if entry.slot == "Main Hand" then main = entry.item end
            if entry.slot == "Off Hand" then off = entry.item end
        end
    end
    if not main then return nil end
    if not off then return "SINGLE" end
    local location = ns.GetItemEquipLocation("item:" .. tostring(off.item_id))
    if not location or location == "" then return nil end
    if location == "INVTYPE_2HWEAPON" then return "DUAL2H" end
    if ONE_HAND_WEAPON_LOCATIONS[location] then return "DUAL" end
    return "SINGLE"
end

local function BagLinks()
    local links = {}
    if type(C_Container) ~= "table" or not C_Container.GetContainerNumSlots or not C_Container.GetContainerItemLink then
        return links
    end
    local bagIDs = { 0, 1, 2, 3, 4, 5 }
    if Enum and Enum.BagIndex then
        local bi = Enum.BagIndex
        bagIDs = { bi.Backpack or 0, bi.Bag_1 or 1, bi.Bag_2 or 2, bi.Bag_3 or 3, bi.Bag_4 or 4, bi.ReagentBag or 5 }
    end
    for _, bagID in ipairs(bagIDs) do
        for slot = 1, (tonumber(C_Container.GetContainerNumSlots(bagID)) or 0) do
            local link = C_Container.GetContainerItemLink(bagID, slot)
            if link then links[#links + 1] = link end
        end
    end
    return links
end

-- Can this one-hand weapon go in the main hand (or, with `offHand`, in the off hand) of the build?
local function WeaponFitsHand(link, profile, offHand)
    local location = ns.GetItemEquipLocation and ns.GetItemEquipLocation(link) or nil
    if offHand then
        if location ~= "INVTYPE_WEAPON" and location ~= "INVTYPE_WEAPONOFFHAND" then return false end
    elseif location ~= "INVTYPE_WEAPON" and location ~= "INVTYPE_WEAPONMAINHAND" then
        return false
    end
    local slotID = offHand and INVSLOT_OFFHAND or INVSLOT_MAINHAND
    return not ns.IsItemCompatibleWithSlot or ns.IsItemCompatibleWithSlot(link, profile, slotID)
end

-- The points two one-hand weapons (main hand, off hand) are worth over the two-hander that is worn: the verdict of that
-- two-hander over the pair, turned around, so that A over B is always the opposite of B over A.
local function PairDelta(profile, twoHandLink, mainLink, offLink)
    if not ns.GetWeightedDeltaScoreForEquippedSet then return nil end
    local delta, rows = ns.GetWeightedDeltaScoreForEquippedSet(twoHandLink, {
        { link = mainLink, slotID = INVSLOT_MAINHAND },
        { link = offLink, slotID = INVSLOT_OFFHAND },
    }, profile, INVSLOT_MAINHAND)
    if not delta then return nil end
    local turned = {}
    for _, row in ipairs(rows or {}) do
        turned[#turned + 1] = {
            statKey = row.statKey, statName = row.statName, amount = row.amount, points = row.points,
            signedPoints = -(tonumber(row.signedPoints) or 0), weight = row.weight, positive = not row.positive,
        }
    end
    return -delta, turned
end

-- The best pair is worked out once for the same weapons and the same worn two-hander, and kept for a couple of seconds: every
-- weapon of the bags asks for it when the bags are painted.
local PAIR_CACHE_SECONDS = 2
local pairCache = {}

-- Among the one-hand weapons of the bags (and `candidateLink` itself, which may be somewhere else: a vendor, a reward) the
-- best pair against the worn two-hander: { mainLink, offLink, delta, rows } or nil.
local function BestWeaponPair(profile, twoHandLink, candidateLink)
    local minimumLevel = (tonumber(ns.GetItemLevel and ns.GetItemLevel(twoHandLink)) or 0) - PAIR_ITEM_LEVEL_SLACK
    local weapons, skippedCandidate = {}, false
    for _, link in ipairs(BagLinks()) do
        if link == candidateLink and not skippedCandidate then
            skippedCandidate = true   -- the candidate's own place in the bags: it is added below, once
        else
            weapons[#weapons + 1] = link
        end
    end
    weapons[#weapons + 1] = candidateLink
    local usable = {}
    for _, link in ipairs(weapons) do
        local location = ns.GetItemEquipLocation and ns.GetItemEquipLocation(link) or nil
        local level = tonumber(ns.GetItemLevel and ns.GetItemLevel(link)) or 0
        if ONE_HAND_WEAPON_LOCATIONS[location] and level >= minimumLevel
            and (not ns.EvaluateItemEligibility or ns.EvaluateItemEligibility(link, profile).allowed) then
            usable[#usable + 1] = { link = link, level = level }
        end
    end
    table.sort(usable, function(a, b) return a.level > b.level end)
    while #usable > PAIR_MAX_WEAPONS do table.remove(usable) end
    local keyParts = { tostring(profile.id or profile.profileKey or ""), tostring(twoHandLink) }
    for _, entry in ipairs(usable) do keyParts[#keyParts + 1] = entry.link end
    local key = table.concat(keyParts, "|")
    local now = GetTime and GetTime() or 0
    local cached = pairCache[key]
    if cached and (now - cached.time) < PAIR_CACHE_SECONDS then return cached.best end
    local best = nil
    for i = 1, #usable - 1 do
        for j = i + 1, #usable do
            for _, order in ipairs({ { usable[i].link, usable[j].link }, { usable[j].link, usable[i].link } }) do
                if WeaponFitsHand(order[1], profile, false) and WeaponFitsHand(order[2], profile, true) then
                    local delta, rows = PairDelta(profile, twoHandLink, order[1], order[2])
                    if delta and (not best or delta > best.delta) then
                        best = { mainLink = order[1], offLink = order[2], delta = delta, rows = rows }
                    end
                end
            end
        end
    end
    pairCache = { [key] = { time = now, best = best } }
    return best
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

    -- The guide's weapon setup decides which weapons are worth a comparison at all.
    local weaponSetup = ns.GetGuideWeaponSetup(profile)
    local candidateIsOneHand = ONE_HAND_WEAPON_LOCATIONS[candidateEquipLocation] == true
    local wearsTwoHand = IsTwoHandEquipLocation(equippedMainEquipLocation) and not equippedOffLink
    if weaponSetup == "SINGLE" and candidateIsOneHand and wearsTwoHand then
        -- A two-hander build: a one-hander is never an upgrade over "an empty off hand".
        return { itemLink = itemLink, candidateScore = candidateScore, comparisons = {}, selected = nil, isUpgrade = false }
    end
    if weaponSetup == "DUAL" and IsTwoHandEquipLocation(candidateEquipLocation) and equippedMainLink and equippedOffLink
        and not IsTwoHandEquipLocation(equippedMainEquipLocation)
    then
        -- A dual wield build that wears two one-handers: a two-hander is not what its guide plays.
        return { itemLink = itemLink, candidateScore = candidateScore, comparisons = {}, selected = nil, isUpgrade = false }
    end
    if weaponSetup == "DUAL" and candidateIsOneHand and wearsTwoHand then
        -- A dual wield build that wears a two-hander: the weapons of the bags count as a pair against it, and only the two
        -- that make the best pair get the verdict.
        local pair = BestWeaponPair(profile, equippedMainLink, itemLink)
        if not pair or (pair.mainLink ~= itemLink and pair.offLink ~= itemLink) then
            return { itemLink = itemLink, candidateScore = candidateScore, comparisons = {}, selected = nil, isUpgrade = false }
        end
        local partner = (pair.mainLink == itemLink) and pair.offLink or pair.mainLink
        local equippedScore = ns.GetItemProfileScore(equippedMainLink, profile, INVSLOT_MAINHAND) or 0
        local pairDelta = pair.delta + DUAL_WIELD_BONUS
        local rows = pair.rows
        rows[#rows + 1] = {
            statKey = "STATVERDICT_REFERENCE_BONUS", statName = "Two weapons (guide)", amount = DUAL_WIELD_BONUS,
            points = DUAL_WIELD_BONUS, signedPoints = DUAL_WIELD_BONUS, weight = 1, positive = true,
        }
        local rawPercent = ns.GetUpgradePercent(pairDelta, equippedScore, profile, itemLink, equippedMainLink) or 0
        -- Each weapon of the pair knows its own hand: the marks, the right-click and the put-on after a spec change use it.
        local comparison = {
            slotID = (pair.mainLink == itemLink) and INVSLOT_MAINHAND or INVSLOT_OFFHAND,
            slotLabel = "Main Hand + Off Hand",
            equippedLink = equippedMainLink,
            equippedScore = equippedScore,
            candidateScore = equippedScore + pairDelta,
            deltaScore = pairDelta,
            rawDeltaScore = pairDelta,
            rawPercent = rawPercent,
            rawIsUpgrade = pairDelta > 0,
            percent = rawPercent,
            isUpgrade = pairDelta > 0 and rawPercent >= MIN_UPGRADE_PERCENT,
            deltaRows = rows,
            pairPartnerLink = partner,
        }
        local result = {
            itemLink = itemLink,
            candidateScore = candidateScore,
            comparisons = { comparison },
            selected = comparison,
            isUpgrade = comparison.isUpgrade,
        }
        if ns.ApplyComparisonRules then result = ns.ApplyComparisonRules(itemLink, profile, result) or result end
        return result
    end

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
            isUpgrade = delta > 0 and (rawPercent >= MIN_UPGRADE_PERCENT or IsLiftedByItemLevel(deltaRows)),
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
        local slotProfile = equippedLink and ProspectProfile(profile, itemLink, equippedLink) or profile
        local candidateSlotScore = ns.GetItemProfileScore(itemLink, slotProfile, slotID) or candidateScore
        if equippedLink and IsSameComparableItem(itemLink, equippedLink) then
            -- The same item at the same effective level is already represented by the profile snapshot/equipped slot.
        elseif equippedLink then
            local equippedScore = ns.GetItemProfileScore(equippedLink, slotProfile, slotID)
            if equippedScore then
                local delta, deltaRows = ns.GetWeightedDeltaScore(itemLink, equippedLink, slotProfile, slotID)
                delta = delta or 0
                local effectiveDelta = delta
                local rawPercent = ns.GetUpgradePercent(delta, equippedScore, slotProfile, itemLink, equippedLink) or 0
                if delta > 0 and equippedScore == 0 then
                    rawPercent = GetMaxDisplayPercent()
                end
                -- Not yet an upgrade by the stats, but close, and this piece can grow where the worn one cannot (as far):
                -- the room to grow tips it. The points then include the push, so the verdict stays a small positive.
                local potentialLift = false
                if rawPercent < MIN_UPGRADE_PERCENT and equippedScore ~= 0 then
                    local push = PotentialPercent(itemLink, equippedLink)
                    if push > 0 and rawPercent + push >= MIN_UPGRADE_PERCENT then
                        effectiveDelta = (rawPercent + push) / 100 * math.abs(equippedScore)
                        rawPercent = rawPercent + push
                        potentialLift = true
                    end
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
                    isUpgrade = effectiveDelta > 0 and (rawPercent >= MIN_UPGRADE_PERCENT or IsLiftedByItemLevel(deltaRows)),
                    potentialLift = potentialLift or nil,
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
