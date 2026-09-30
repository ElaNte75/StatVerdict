local addonName, ns = ...

local function Colors()
    return ns.Colors
end

local function AddLine(tooltip, text, r, g, b)
    if tooltip and text then
        tooltip:AddLine(text, r, g, b, true)
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
        AddLine(tooltip, specLine)
    end
    if referenceInfo and referenceInfo.bis then
        local wording = ns.GetReferenceWording and ns.GetReferenceWording(context.profile and context.profile.goal) or nil
        local tag = wording and wording.tag or "BIS"
        AddLine(tooltip, c.white .. "Reference: " .. "|cff00ccff(" .. tag .. ")|r" .. c.reset, 1, 1, 1)
    elseif referenceInfo and referenceInfo.catalystPath then
        AddLine(tooltip, c.white .. "Reference: " .. "|cff00ccffGood if converted to the set piece with the Catalyst|r" .. c.reset, 1, 1, 1)
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
    if selected.setComparison and (selected.equippedMainLink or selected.equippedOffLink) then
        AddLine(tooltip, c.white .. (ruleBlocked and ("Would replace " .. baselineLabel .. " set:") or ("Better than " .. baselineLabel .. " set:")) .. c.reset, 1, 1, 1)
        local mainName = GetColoredItemName(selected.equippedMainLink) or GetItemNameFromLink(selected.equippedMainLink) or "Main Hand"
        local offName = GetColoredItemName(selected.equippedOffLink) or GetItemNameFromLink(selected.equippedOffLink) or "Off Hand"
        AddLine(tooltip, c.white .. "Main Hand: " .. c.reset .. mainName, 1, 1, 1)
        AddLine(tooltip, c.white .. "Off Hand: " .. c.reset .. offName, 1, 1, 1)
    else
        AddLine(tooltip, c.white .. (ruleBlocked and ("Would replace " .. baselineLabel .. ":") or ("Better than " .. baselineLabel .. ":")) .. c.reset, 1, 1, 1)
        AddLine(tooltip, targetName, 1, 1, 1)
    end
    if verdictScoreText then
        local signedValue = verdictScore
        local valueColor = signedValue >= 0 and c.green or c.red
        local verdictLabel = ruleBlocked and "Raw Verdict Points: " or "Verdict Points: "
        local verdictLine = c.white .. verdictLabel .. valueColor .. verdictScoreText
        AddLine(tooltip, verdictLine .. c.reset, 1, 1, 1)
    end
    AddLine(tooltip, "|cff9d9d9dHeuristic comparison; not simulated DPS or healing.|r", 0.62, 0.62, 0.62)
    local provenance = ns.ProfileRepository
        and ns.ProfileRepository.GetDataProvenance
        and ns.ProfileRepository.GetDataProvenance(context.profile and context.profile.goal)
    if provenance and provenance.scrape then
        AddLine(tooltip, "|cff9d9d9dProfile source: " .. tostring(provenance.sourceName or "bundled data")
            .. " · " .. tostring(provenance.scrape) .. "|r", 0.62, 0.62, 0.62)
    end
    if selected.ruleReason then
        AddLine(tooltip, c.yellow .. "Reason: " .. selected.ruleReason .. c.reset, 1, 0.85, 0.2)
    end

    if showApproveHint and not ruleBlocked then
        local specName = context.specName or (context.profile and context.profile.specName) or "this build"
        if isSecondary then
            AddLine(tooltip, "|cffffd200Alt-Left-Click to save for " .. tostring(specName) .. " (Off Spec)|r", 1, 0.82, 0)
        else
            AddLine(tooltip, "|cffffd200Alt-Right-Click to save for " .. tostring(specName) .. "|r", 1, 0.82, 0)
        end
    end

    tooltip:Show()
end

function ns.RenderTooltipLoadoutMembership(tooltip, context)
    if not tooltip or not context then
        return
    end
    local specName = context.specName or (context.profile and context.profile.specName) or "this build"
    local c = Colors()
    tooltip:AddLine(" ")
    AddLine(tooltip, "|cffff8000StatVerdict|r", 1, 0.5, 0)
    local specLine = BuildSpecLine(context)
    if specLine then
        AddLine(tooltip, specLine)
    end
    AddLine(tooltip, c.green .. "Saved in " .. tostring(specName) .. " loadout" .. c.reset, 0.2, 1, 0.2)
    tooltip:Show()
end
