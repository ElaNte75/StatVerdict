local addonName, ns = ...

local function Colors()
    return ns.Colors
end

-- Lines do not wrap: the tooltip grows a little instead, so short wording is the way to keep it narrow. Only long
-- prose (wrap = true) may fold.
local function AddLine(tooltip, text, r, g, b, wrap)
    if tooltip and text then
        tooltip:AddLine(text, r, g, b, wrap == true)
    end
end

local function GetItemNameFromLink(itemLink)
    if type(itemLink) ~= "string" then
        return nil
    end
    local name = itemLink:match("%[(.-)%]")
    if name and name ~= "" then
        return name
    end
    return nil
end

local function GetColoredItemName(itemLink)
    if not itemLink then
        return nil
    end
    local itemName, _, itemQuality = C_Item.GetItemInfo(itemLink)
    itemName = itemName or GetItemNameFromLink(itemLink)
    if not itemName then
        return nil
    end
    local colorPrefix
    if itemQuality then
        local _, _, _, hex = GetItemQualityColor(itemQuality)
        if hex and hex ~= "" then
            colorPrefix = "|c" .. hex
        end
    end
    return (colorPrefix or "|cffffffff") .. itemName .. "|r"
end

local function FormatVerdictScore(value)
    if value == nil then
        return nil
    end
    if value > 0 then
        return string.format("+%.1f", value)
    end
    if value < 0 then
        return string.format("%.1f", value)
    end
    return "0.0"
end

local function GetClassColorPrefix(context)
    local classFile = context and context.classFile
    if classFile and RAID_CLASS_COLORS and RAID_CLASS_COLORS[classFile] then
        return RAID_CLASS_COLORS[classFile].colorStr and ("|c" .. RAID_CLASS_COLORS[classFile].colorStr) or "|cffffffff"
    end
    return "|cffffffff"
end

local function BuildSpecLine(context)
    if not context then
        return nil
    end
    local label = context.specName or "Current Spec"
    if context.heroTalentName and context.heroTalentName ~= "" then
        label = label .. " - " .. context.heroTalentName
    end
    return GetClassColorPrefix(context) .. label .. "|r"
end

local TRINKET_TIER_COLOR = {
    S = "|cffff8000",
    A = "|cffa335ee",
    B = "|cff0070dd",
    C = "|cff1eff00",
    D = "|cff9d9d9d",
}

-- The upgrade-track bonus id (from the data root's trackRanks) that gives an item level; when several tracks reach it,
-- the one at the wanted rank first. nil when no track of the season has that level.
local function TrackBonusForLevel(level, wantedRank)
    local root = ns.ClassCodexTargets
    local ranks = type(root) == "table" and root.trackRanks or nil
    if type(ranks) ~= "table" or not level then return nil end
    local found = nil
    for _, track in ipairs({ "champion", "hero", "myth" }) do
        for rank, entry in pairs(type(ranks[track]) == "table" and ranks[track] or {}) do
            if type(entry) == "table" and tonumber(entry[2]) == level then
                if tonumber(rank) == wantedRank then return tonumber(entry[1]) end
                found = found or tonumber(entry[1])
            end
        end
    end
    return found
end

-- The item string of the Best in Slot set piece an item the Catalyst can convert becomes, at the item's own item
-- level. The item's bonus ids do not carry over (the game reads the set piece at its base level), so the set piece
-- gets the upgrade-track bonus id that gives the item's level. nil when the item has no item string or no track
-- reaches its level; second value: the item's own item string.
function ns.CatalystTargetItemString(itemLink, targetItemID)
    local itemString = type(itemLink) == "string" and itemLink:match("(item:[%-%d:]+)") or nil
    targetItemID = tonumber(targetItemID)
    if not itemString or not targetItemID then return nil end
    local level = tonumber(ns.GetItemLevel and ns.GetItemLevel(itemString))
    local info = ns.GetItemUpgradeInfo and ns.GetItemUpgradeInfo(itemString) or nil
    local bonusID = TrackBonusForLevel(level, info and tonumber(info.currentLevel) or nil)
    if not bonusID then return nil end
    local linkLevel = type(UnitLevel) == "function" and tonumber(UnitLevel("player")) or 90
    return ("item:%d::::::::%d::::1:%d"):format(targetItemID, linkLevel, bonusID), itemString
end

function ns.RenderTooltipVerdict(tooltip, context, comparison, isSecondary, showApproveHint)
    if not tooltip or not context or not comparison or not comparison.selected then
        return
    end

    local selected = comparison.selected
    local referenceInfo = ns.GetItemReferenceInfo and ns.GetItemReferenceInfo(comparison.itemLink, context.profile) or nil
    local upgradeInfo = ns.GetItemUpgradeInfo and ns.GetItemUpgradeInfo(comparison.itemLink) or nil

    local verdictScore = selected.deltaScore or selected.rawDeltaScore or 0
    local ruleBlocked = selected.ruleBlocked == true
    if (not selected.isUpgrade or verdictScore <= 0) and not ruleBlocked then
        return
    end

    local c = Colors()
    local targetName = GetColoredItemName(selected.equippedLink) or GetItemNameFromLink(selected.equippedLink) or selected.slotLabel or "equipped item"
    local verdictScoreText = FormatVerdictScore(verdictScore)
    tooltip:AddLine(" ")
    AddLine(tooltip, ruleBlocked and "|cffff8000StatVerdict Warning|r" or "|cffff8000StatVerdict Result|r", 1, 0.5, 0)

    local specLine = BuildSpecLine(context)
    if specLine then
        -- Which of the two builds this is, in the gold of the save hints.
        AddLine(tooltip, "|cffffd200" .. (isSecondary and "Off Spec" or "Main Spec") .. "|r " .. specLine)
    end
    if referenceInfo and referenceInfo.bis then
        local wording = ns.GetReferenceWording and ns.GetReferenceWording(context.profile and context.profile.goal) or nil
        local tag = wording and wording.tag or "BIS"
        AddLine(tooltip, c.white .. "Reference: " .. "|cff00ccff(" .. tag .. ")|r" .. c.reset, 1, 1, 1)
    end
    if referenceInfo and referenceInfo.trinket then
        local trinket = referenceInfo.trinket
        local tier = tostring(trinket.tier or "")
        local tierColor = TRINKET_TIER_COLOR[tier] or c.white
        local rankText = trinket.rank and (" #" .. tostring(trinket.rank)) or ""
        AddLine(tooltip, c.white .. "Trinket Tier: " .. tierColor .. "(" .. tier .. rankText .. ")|r" .. c.reset, 1, 1, 1)
    end
    if type(upgradeInfo) == "table" and (tonumber(upgradeInfo.maxItemLevel) or 0) > 0 then
        local track = type(upgradeInfo.trackString) == "string" and upgradeInfo.trackString or "Upgrade Track"
        local currentLevel = tonumber(upgradeInfo.currentLevel)
        local maxLevel = tonumber(upgradeInfo.maxLevel)
        local rankText = currentLevel and maxLevel and (" " .. tostring(currentLevel) .. "/" .. tostring(maxLevel)) or ""
        AddLine(tooltip, c.white .. track .. rankText .. ": up to item level " .. tostring(upgradeInfo.maxItemLevel) .. c.reset, 1, 1, 1)
    end

    local usesSnapshot = context.profile
        and ns.ShouldUseEquipmentSnapshot
        and ns.ShouldUseEquipmentSnapshot(context.profile)
    local baselineLabel = usesSnapshot and "virtual loadout" or "equipped"
    -- The verdict points close the "Better than ..." line, so there is no separate points line.
    local pointsText = ""
    if verdictScoreText then
        local valueColor = verdictScore >= 0 and c.green or c.red
        pointsText = " " .. valueColor .. verdictScoreText .. (ruleBlocked and " raw" or "") .. c.reset
    end
    if selected.setComparison and (selected.equippedMainLink or selected.equippedOffLink) then
        AddLine(tooltip, c.white .. (ruleBlocked and ("Would replace " .. baselineLabel .. " set:") or ("Better than " .. baselineLabel .. " set:")) .. c.reset .. pointsText, 1, 1, 1)
        local mainName = GetColoredItemName(selected.equippedMainLink) or GetItemNameFromLink(selected.equippedMainLink) or "Main Hand"
        local offName = GetColoredItemName(selected.equippedOffLink) or GetItemNameFromLink(selected.equippedOffLink) or "Off Hand"
        AddLine(tooltip, c.white .. "Main Hand: " .. c.reset .. mainName, 1, 1, 1)
        AddLine(tooltip, c.white .. "Off Hand: " .. c.reset .. offName, 1, 1, 1)
    else
        -- One line: what it beats (the item itself, not the word loadout), then the points.
        AddLine(tooltip, c.white .. (ruleBlocked and "Would replace " or "Better than ") .. c.reset .. targetName .. c.white .. " :" .. c.reset .. pointsText, 1, 1, 1)
    end
    if selected.ruleReason then
        AddLine(tooltip, c.yellow .. "Reason: " .. selected.ruleReason .. c.reset, 1, 0.85, 0.2, true)
    end

    -- An item the Catalyst can turn into the Best in Slot set piece: whether that piece, judged with its real
    -- stats at this item level, comes out better than the item as it is, and the way to see it.
    if referenceInfo and referenceInfo.catalystPath and not ruleBlocked then
        local convertedScore = nil
        local targetLink = ns.CatalystTargetItemString and ns.CatalystTargetItemString(comparison.itemLink, referenceInfo.catalystPath.targetItemID)
        local converted = targetLink and ns.BuildComparison and ns.BuildComparison(targetLink, context.profile) or nil
        local convertedSelected = converted and converted.selected or nil
        if convertedSelected then
            convertedScore = convertedSelected.deltaScore or convertedSelected.rawDeltaScore
        end
        if convertedScore ~= nil then
            if convertedScore > verdictScore then
                -- The set piece is the guide's Best in Slot piece for this slot: that is what it becomes.
                local wording = ns.GetReferenceWording and ns.GetReferenceWording(context.profile and context.profile.goal) or nil
                local base = wording and wording.base or "Best in Slot"
                AddLine(tooltip, "|cff00ccff" .. base .. " after the Catalyst|r", 0, 0.8, 1)
            else
                AddLine(tooltip, "|cff999999Not better after the Catalyst|r", 0.6, 0.6, 0.6)
            end
        end
        if targetLink then
            AddLine(tooltip, "|cff999999Hold Ctrl to preview|r", 0.6, 0.6, 0.6)
        end
    end

    -- Last line: which click saves the item (the spec is already named above).
    -- (With Auto mark on there is nothing to save for the spec that is played: it marks itself when you wear the piece.)
    local playedSpec = ns.IsAutoMarkOn and ns.IsAutoMarkOn() and ns.ShouldUseEquipmentSnapshot
        and context and context.profile and not ns.ShouldUseEquipmentSnapshot(context.profile)
    if showApproveHint and not ruleBlocked and not playedSpec then
        local clickName = ns.MarkClickLabel and ns.MarkClickLabel(isSecondary) or (isSecondary and "Alt-Left-Click" or "Alt-Right-Click")
        AddLine(tooltip, "|cff999999" .. clickName .. ": save in loadout|r", 0.6, 0.6, 0.6)
    end

    tooltip:Show()
end

-- An item that is no upgrade as it is (or the very piece the player wears) but that the Catalyst turns into the Best in
-- Slot set piece, better than what sits in that slot: say so, and nothing else (no verdict, no other build). Draws
-- nothing and returns false when there is no such path, no set piece at the item's level, or it would not be better.
-- What the Catalyst would gain: the points of the Best in Slot set piece (at the item's own item level) over what sits in
-- that slot; nil when the item has no Catalyst path, no set piece can be built, or it would not be better.
function ns.GetCatalystGain(context, itemLink)
    if not context or not context.profile or not itemLink then return nil end
    local referenceInfo = ns.GetItemReferenceInfo and ns.GetItemReferenceInfo(itemLink, context.profile) or nil
    local path = referenceInfo and referenceInfo.catalystPath or nil
    if not path then return nil end
    local targetLink = ns.CatalystTargetItemString and ns.CatalystTargetItemString(itemLink, path.targetItemID)
    local converted = targetLink and ns.BuildComparison and ns.BuildComparison(targetLink, context.profile) or nil
    local selected = converted and converted.selected or nil
    local score = selected and (selected.deltaScore or selected.rawDeltaScore) or nil
    if not score or score <= 0 then return nil end
    return score
end

-- What is worth saying about a piece the player WEARS (character sheet): { bis = it is in the Best in Slot list,
-- gain = the points the Catalyst would add when it would turn the piece into the Best in Slot set piece (a piece that is
-- already Best in Slot has none), shared = it is in both builds' loadouts, otherLabel = "Main Spec" / "Off Spec": the
-- build that is not the one being played }. nil when there is nothing to say.
-- guid: the game's serial number of the worn piece (so the loadouts are asked about this very piece), or nil.
function ns.GetWornPieceInfo(itemLink, guid)
    if type(itemLink) ~= "string" or not ns.GetTooltipEvaluationContexts then return nil end
    local primary, secondary = ns.GetTooltipEvaluationContexts()
    local profile = type(primary) == "table" and primary.profile or nil
    if type(profile) ~= "table" then return nil end
    local function evaluate()
        local info = ns.GetItemReferenceInfo and ns.GetItemReferenceInfo(itemLink, profile) or nil
        local result = { bis = (info and info.bis) and true or false }
        if not result.bis and ns.GetCatalystGain then result.gain = ns.GetCatalystGain(primary, itemLink) end
        local other = type(secondary) == "table" and secondary ~= primary and secondary.profile or nil
        if other and ns.IsItemInEquipmentSnapshot
            and ns.IsItemInEquipmentSnapshot(profile, itemLink, guid) and ns.IsItemInEquipmentSnapshot(other, itemLink, guid) then
            result.shared = true
            -- The main spec is the one being played when its loadout is not a snapshot of another spec.
            local mainIsPlayed = not (ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile))
            result.otherLabel = mainIsPlayed and "Off Spec" or "Main Spec"
        elseif other then
            -- In one build's loadout only (the one that is played, since it is worn): say which. Information only.
            local otherContext = secondary
            local primaryPlayed = not (ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile))
            local playedContext = nil
            if primaryPlayed then
                playedContext = primary
            elseif ns.ShouldUseEquipmentSnapshot and not ns.ShouldUseEquipmentSnapshot(other) then
                playedContext = otherContext
            end
            if playedContext and playedContext.profile and ns.IsItemInEquipmentSnapshot
                and ns.IsItemInEquipmentSnapshot(playedContext.profile, itemLink, guid) then
                result.single = { label = (playedContext == primary) and "MS" or "OS", context = playedContext }
            end
        end
        return result
    end
    local result = ns.WithStatVerdictSnapshotProfile and ns.WithStatVerdictSnapshotProfile(profile, evaluate) or evaluate()
    if result and (result.bis or result.gain or result.shared or result.single) then return result end
    return nil
end

-- The tooltip of a piece the player wears: no verdict (it is worn), only what the marks on the character sheet mean,
-- and only for a piece that has a mark. Returns true when it drew something.
function ns.RenderTooltipWornInfo(tooltip, itemLink, primaryContext, guid, hideShared)
    if not tooltip then return false end
    local info = ns.GetWornPieceInfo(itemLink, guid)
    -- While the red arrow warns about the piece, "also part of your other set" is not said either (the ring is hidden too).
    if info and hideShared and info.shared then
        local copy = {}
        for key, value in pairs(info) do copy[key] = value end
        copy.shared = nil
        info = (copy.bis or copy.gain) and copy or nil
    end
    if not info then return false end
    local c = Colors()
    local wording = ns.GetReferenceWording and ns.GetReferenceWording(primaryContext and primaryContext.profile and primaryContext.profile.goal) or nil
    local base = wording and wording.base or "Best in Slot"
    tooltip:AddLine(" ")
    AddLine(tooltip, info.gain and "|cffff8000StatVerdict Warning|r" or "|cffff8000StatVerdict info|r", 1, 0.5, 0)
    if info.bis then
        -- Best in Slot is light blue, as everywhere in the add-on.
        AddLine(tooltip, "|cff00ccffThis item is " .. base .. "|r", 0, 0.8, 1)
    end
    if info.gain then
        local scoreText = FormatVerdictScore(info.gain)
        AddLine(tooltip, "|cff00ccffCatalyst it: " .. base .. "|r" .. (scoreText and (" " .. c.green .. scoreText .. c.reset) or ""), 0, 0.8, 1)
        AddLine(tooltip, "|cff999999Hold Ctrl to preview|r", 0.6, 0.6, 0.6)
    end
    if info.shared then
        -- The build is always MS or OS in green: the same letters, in the same colour, as on the bag items.
        local label = (info.otherLabel == "Off Spec") and "OS" or "MS"
        AddLine(tooltip, "|cffffd200Also part of your |r|cff00ff00" .. label .. "|r|cffffd200 set|r", 1, 0.82, 0)
    elseif info.single then
        -- Belongs to one build only: which one (MS / OS in green, the spec in its class colour).
        local specContext = info.single.context
        local specName = specContext and (specContext.specName or (specContext.profile and specContext.profile.specName)) or nil
        local named = specName and (" " .. GetClassColorPrefix(specContext) .. tostring(specName) .. c.reset) or ""
        AddLine(tooltip, "|cffffd200Part of your |r|cff00ff00" .. info.single.label .. "|r" .. named .. "|cffffd200 set|r", 1, 0.82, 0)
    end
    tooltip:Show()
    return true
end

-- On the tooltip of a piece the player wears: when a piece in the bags beats it for the spec that is played, say which one
-- (the red arrow on the character sheet says the same). drewInfo: the worn-piece info block is already there (no new title).
function ns.RenderTooltipWornBagUpgrade(tooltip, slotID, drewInfo)
    if not tooltip or not tonumber(slotID) then return false end
    local db = _G.StatVerdictDB
    if type(db) == "table" and db.showWornDownArrow == false then return false end
    local map = ns.GetBagUpgradesForWornSlots and ns.GetBagUpgradesForWornSlots() or nil
    local entry = map and map[tonumber(slotID)]
    if not entry or entry.ignored then return false end
    if not drewInfo then
        tooltip:AddLine(" ")
        AddLine(tooltip, "|cffff8000StatVerdict info|r", 1, 0.5, 0)
    end
    -- Two short white lines (a long one makes the whole tooltip wider): what it is, then the piece and its points.
    local scoreText = FormatVerdictScore(entry.gain)
    local c = Colors()
    AddLine(tooltip, "Better in your bags:", 1, 1, 1)
    -- The points are green, as everywhere else ("Better than ...: +153.2").
    AddLine(tooltip, tostring(entry.link) .. (scoreText and (" : " .. c.green .. scoreText .. c.reset) or ""), 1, 1, 1)
    AddLine(tooltip, "|cff999999Click the arrow to ignore this: it is your choice.|r", 0.6, 0.6, 0.6)
    tooltip:Show()
    return true
end

function ns.RenderTooltipCatalystOnly(tooltip, context, itemLink, worn)
    if not tooltip then return false end
    local score = ns.GetCatalystGain(context, itemLink)
    if not score then return false end

    local c = Colors()
    local wording = ns.GetReferenceWording and ns.GetReferenceWording(context.profile.goal) or nil
    local base = wording and wording.base or "Best in Slot"
    local scoreText = FormatVerdictScore(score)
    tooltip:AddLine(" ")
    AddLine(tooltip, "|cffff8000StatVerdict Warning|r", 1, 0.5, 0)
    local specLine = BuildSpecLine(context)
    if specLine then
        AddLine(tooltip, "|cffffd200Main Spec|r " .. specLine)
    end
    -- One short line: what to do, what it becomes, and the gain.
    AddLine(tooltip, "|cff00ccffCatalyst it: " .. base .. "|r" .. (scoreText and (" " .. c.green .. scoreText .. c.reset) or ""), 0, 0.8, 1)
    AddLine(tooltip, "|cff999999Hold Ctrl to preview|r", 0.6, 0.6, 0.6)
    tooltip:Show()
    return true
end

-- An item saved in a loadout: one line says where ("Saved in Frost loadout", or "Saved in both loadouts" when the
-- other build holds it too). otherContext: the other build's context when it holds the item as well; isSecondary: the
-- build is the Off Spec (the line then says "OS", else "MS", in gold, before the spec's name).
-- alsoLine: the line goes straight under a verdict block that is already on the tooltip (no gap, no second StatVerdict
-- title) and starts "Also saved in".
function ns.RenderTooltipLoadoutMembership(tooltip, context, otherContext, isSecondary, alsoLine)
    if not tooltip or not context then
        return
    end
    local specName = context.specName or (context.profile and context.profile.specName) or "this build"
    local c = Colors()
    if not alsoLine then
        tooltip:AddLine(" ")
        AddLine(tooltip, "|cffff8000StatVerdict|r", 1, 0.5, 0)
    end
    -- The spec's name has the class colour, so the eye goes to which build is meant; "MS and OS" is gold (no class has it).
    local where = otherContext and ("|cffffd200MS and OS|r" .. c.green .. " loadouts")
        or ("|cffffd200" .. (isSecondary and "OS" or "MS") .. "|r " .. GetClassColorPrefix(context) .. tostring(specName)
            .. c.reset .. c.green .. " loadout")
    AddLine(tooltip, c.green .. (alsoLine and "Also saved in " or "Saved in ") .. where .. c.reset, 0.2, 1, 0.2)
    tooltip:Show()
end
