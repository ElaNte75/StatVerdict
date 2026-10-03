local addonName, ns = ...

local PREFIX = "StatVerdict"
local lastVerdictMemory = {
    itemLink = nil,
    context = nil,
    slotID = nil,
    at = nil,
}

function ns.RememberTooltipVerdictContext(itemLink, context, comparison)
    lastVerdictMemory.itemLink = itemLink
    lastVerdictMemory.context = context
    lastVerdictMemory.slotID = comparison and comparison.selected and comparison.selected.slotID or nil
    lastVerdictMemory.at = type(time) == "function" and time() or nil
end

function ns.GetRememberedTooltipVerdictContext()
    return lastVerdictMemory.itemLink, lastVerdictMemory.context, lastVerdictMemory.slotID
end

local function IsInternalStatVerdictTooltip(tooltip)
    if not tooltip or type(tooltip.GetName) ~= "function" then
        return false
    end
    local name = tooltip:GetName()
    return type(name) == "string" and string.find(name, "StatVerdict", 1, true) == 1
end

local function GetTooltipItemLink(tooltip)
    if not tooltip then
        return nil
    end

    if type(tooltip.GetItem) == "function" then
        local _, link = tooltip:GetItem()
        if link then
            return link
        end
    end

    if type(tooltip.GetTooltipData) == "function" then
        local data = tooltip:GetTooltipData()
        if data and data.hyperlink then
            return data.hyperlink
        end
    end

    return nil
end

local function FrameNameContains(frame, needle)
    if not frame or type(frame.GetName) ~= "function" then
        return false
    end
    local name = frame:GetName()
    return type(name) == "string" and string.find(name, needle, 1, true) ~= nil
end

local function IsBagItemFrame(frame)
    if not frame then
        return false
    end
    if type(frame.GetBagID) == "function" then
        local ok, bagID = pcall(frame.GetBagID, frame)
        if ok and bagID ~= nil then
            return true
        end
    end
    if FrameNameContains(frame, "ContainerFrame")
        or FrameNameContains(frame, "CombinedBags")
        or FrameNameContains(frame, "BagItem")
        or FrameNameContains(frame, "BagsBar") then
        return true
    end
    local parent = type(frame.GetParent) == "function" and frame:GetParent() or nil
    if parent and (
        FrameNameContains(parent, "ContainerFrame")
        or FrameNameContains(parent, "CombinedBags")
    ) then
        return true
    end
    return false
end

-- Approve / loadout-save actions only make sense for items you already own in bags.
function ns.IsTooltipFromPlayerBags(tooltip)
    if not tooltip then
        return false
    end

    if type(tooltip.GetOwner) == "function" then
        local owner = tooltip:GetOwner()
        if IsBagItemFrame(owner) then
            return true
        end
    end

    if type(GetMouseFoci) == "function" then
        local ok, foci = pcall(GetMouseFoci)
        if ok and type(foci) == "table" then
            for _, frame in ipairs(foci) do
                if IsBagItemFrame(frame) then
                    return true
                end
            end
        end
    elseif type(GetMouseFocus) == "function" then
        local ok, focus = pcall(GetMouseFocus)
        if ok and IsBagItemFrame(focus) then
            return true
        end
    end

    return false
end

local function TooltipAlreadyHasStatVerdict(tooltip)
    if not tooltip or not tooltip.GetName or not tooltip.NumLines then
        return false
    end

    local name = tooltip:GetName()
    if not name then
        return false
    end

    for i = 1, tooltip:NumLines() do
        local line = _G[name .. "TextLeft" .. i]
        local text = line and line:GetText()
        if type(text) == "string" and string.find(text, PREFIX, 1, true) then
            return true
        end
    end

    return false
end

local function ItemInContextLoadout(itemLink, context)
    local profile = context and context.profile or nil
    if not itemLink or not profile or not ns.IsItemInEquipmentSnapshot then
        return false
    end
    local ok, contains = pcall(ns.IsItemInEquipmentSnapshot, profile, itemLink)
    return ok and contains and true or false
end

local function RenderMissingOffhandNotice(tooltip, context)
    if not tooltip then return false end

    local specName = context and (context.specName or (context.profile and context.profile.specName)) or nil
    tooltip:AddLine(" ")
    tooltip:AddLine("|cffff8000StatVerdict:|r comparison incomplete", 1, 0.5, 0, true)
    if specName and specName ~= "" then
        tooltip:AddLine(tostring(specName), 1, 1, 1, true)
    end
    tooltip:AddLine("Requires an Off-Hand to compare with the equipped 2H weapon.", 1, 0.82, 0, true)
    tooltip:Show()
    return true
end

local function AddTooltipVerdict(tooltip)
    if IsInternalStatVerdictTooltip(tooltip) then
        return
    end
    -- Our own list rows (Ranked Trinkets) show the plain item: no verdict lines.
    local owner = tooltip and type(tooltip.GetOwner) == "function" and tooltip:GetOwner() or nil
    if type(owner) == "table" and owner.svNoVerdict == true then
        return
    end
    if not tooltip or TooltipAlreadyHasStatVerdict(tooltip) then
        return
    end

    local itemLink = GetTooltipItemLink(tooltip)
    if not itemLink then
        return
    end

    local fromBags = ns.IsTooltipFromPlayerBags and ns.IsTooltipFromPlayerBags(tooltip) or false

    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    primaryContext = primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)

    local renderedDataUnavailable = false
    local function renderContext(context, isSecondary)
        local profile = context and context.profile or nil
        if not profile then
            -- Provenance is per goal: this build's goal, else the selected one.
            local goal = (context and context.goal)
                or (ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode())
                or "MYTHIC_PLUS"
            local provenance = ns.ProfileRepository
                and ns.ProfileRepository.GetDataProvenance
                and ns.ProfileRepository.GetDataProvenance(goal)
            if provenance and provenance.available == false and not renderedDataUnavailable then
                renderedDataUnavailable = true
                tooltip:AddLine(" ")
                tooltip:AddLine("|cffff8000StatVerdict:|r profile data unavailable", 1, 0.5, 0, true)
                tooltip:AddLine("The bundled guide data is out of date or incomplete: update StatVerdict to the latest version.", 0.92, 0.82, 0.45, true)
                tooltip:AddLine("No gear verdict was produced.", 0.92, 0.82, 0.45, true)
                tooltip:Show()
                return true
            end
            return false
        end

        if profile.invalidGeneratedContext then
            tooltip:AddLine(" ")
            tooltip:AddLine("|cffff8000StatVerdict:|r profile quality check failed", 1, 0.5, 0, true)
            local reason = profile.auditTargets and profile.auditTargets.invalidReason
            tooltip:AddLine(tostring(reason or "This goal has no trustworthy profile data."), 0.92, 0.82, 0.45, true)
            tooltip:AddLine("No gear verdict was produced.", 0.92, 0.82, 0.45, true)
            tooltip:Show()
            return true
        end

        if ns.IsSnapshotMissingForProfile and ns.IsSnapshotMissingForProfile(profile) then
            if fromBags then
                ns.RememberTooltipVerdictContext(itemLink, context, nil)
                tooltip:AddLine(" ")
                tooltip:AddLine("|cffff8000StatVerdict:|r virtual loadout missing", 1, 0.82, 0.0, true)
                local specName = context.specName or profile.specName or "this spec"
                tooltip:AddLine("No saved gear list for " .. specName .. " yet.", 0.92, 0.82, 0.45, true)
                if isSecondary then
                    tooltip:AddLine("|cffffd200Alt-Left-Click to save this item for " .. specName .. " (Off Spec)|r", 1, 0.82, 0, true)
                else
                    tooltip:AddLine("|cffffd200Alt-Right-Click to save this item for " .. specName .. "|r", 1, 0.82, 0, true)
                end
                tooltip:Show()
                return true
            end
            -- Outside bags: do not prompt to save an item the player does not own yet.
            return false
        end

        if ns.ShouldUseEquipmentSnapshot
            and ns.ShouldUseEquipmentSnapshot(profile)
            and ns.HasSnapshotStats
            and not ns.HasSnapshotStats(profile)
        then
            tooltip:AddLine(" ")
            tooltip:AddLine("|cffff8000StatVerdict:|r Off Spec stats not captured", 1, 0.5, 0, true)
            tooltip:AddLine("Approve saved the gear baseline, but live weights require one capture while that spec is active.", 0.92, 0.82, 0.45, true)
            tooltip:AddLine("No gear verdict was produced.", 0.92, 0.82, 0.45, true)
            tooltip:Show()
            return true
        end

        -- Membership / save messaging only for owned bag items.
        if fromBags and ItemInContextLoadout(itemLink, context) then
            ns.RememberTooltipVerdictContext(itemLink, context, nil)
            if ns.RenderTooltipLoadoutMembership then
                ns.RenderTooltipLoadoutMembership(tooltip, context)
                return true
            end
        end

        local function buildAndRender()
            local comparison = ns.BuildComparison(itemLink, profile)
            if not comparison then
                return false
            end
            if comparison.missingOffhand then
                local rendered = RenderMissingOffhandNotice(tooltip, context)
                if rendered and fromBags then
                    ns.RememberTooltipVerdictContext(itemLink, context, comparison)
                end
                return rendered
            end
            if not comparison.selected then
                return false
            end

            if ns.RenderTooltipVerdict then
                ns.RenderTooltipVerdict(tooltip, context, comparison, isSecondary, fromBags)
                local rendered = TooltipAlreadyHasStatVerdict(tooltip)
                if rendered and fromBags then
                    ns.RememberTooltipVerdictContext(itemLink, context, comparison)
                end
                return rendered
            end
            return false
        end

        if ns.WithStatVerdictSnapshotProfile then
            return ns.WithStatVerdictSnapshotProfile(profile, buildAndRender)
        end
        return buildAndRender()
    end

    if renderContext(primaryContext, false) then
        return
    end
    if secondaryContext and secondaryContext ~= primaryContext then
        renderContext(secondaryContext, true)
    end
end

-- Stat ranks: every secondary stat on an item tooltip gets its place in the guide's order for the build
-- shown in the window ("+73 Critical Strike #1"). Stats the guide calls roughly equal share one number
-- and carry an "=" ("#2="). Switched off with Features > Stat Ranks (StatVerdictDB.showStatRanks).
local RANK_COLOR = "|cffffd100"

local function PlainText(text)
    return (text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""))
end

local function EscapePattern(text)
    return (text:gsub("[%^%$%(%)%%%.%[%]%*%+%-%?]", "%%%0"))
end

-- A whole stat line: a number and the stat's name, nothing else ("+73 Critical Strike"). The name is the game's
-- own word for the stat, so this works in every language and skips enchant and effect text.
local function IsStatLine(plain, name)
    local escaped = EscapePattern(name)
    local between = plain:match("^%s*[%+%-]?[%d%.,]+(.-)" .. escaped .. "%s*$")
    if between ~= nil then
        return #between <= 4 and not between:find("%d")
    end
    local after = plain:match("^%s*" .. escaped .. "(.-)[%+%-]?[%d%.,]+%s*$")
    return after ~= nil and #after <= 4 and not after:find("%d")
end

function ns.AddStatRanksToTooltip(tooltip)
    if not tooltip or type(tooltip.NumLines) ~= "function" or type(tooltip.GetName) ~= "function" then
        return
    end
    local db = _G.StatVerdictDB
    if type(db) == "table" and db.showStatRanks == false then
        return
    end
    if InCombatLockdown and InCombatLockdown() then
        return
    end
    local tooltipName = tooltip:GetName()
    if type(tooltipName) ~= "string" or tooltipName == "" or IsInternalStatVerdictTooltip(tooltip) then
        return
    end

    local context = ns.GetTooltipEvaluationContexts and (ns.GetTooltipEvaluationContexts()) or nil
    context = context or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)
    local profile = context and context.profile or nil
    if type(profile) ~= "table" or profile.invalidGeneratedContext or not ns.GetSecondaryDisplayRanks then
        return
    end

    local stats = {}
    for statKey, entry in pairs(ns.GetSecondaryDisplayRanks(profile.secondaryOrder, profile.equalGroups)) do
        local name = _G[statKey]
        if type(name) == "string" and name ~= "" then
            stats[#stats + 1] = { name = name, suffix = " " .. RANK_COLOR .. "#" .. entry.rank .. (entry.tied and "=" or "") .. "|r" }
        end
    end
    if #stats == 0 then
        return
    end

    local changed = false
    for index = 1, tooltip:NumLines() do
        local line = _G[tooltipName .. "TextLeft" .. index]
        local ok, text = pcall(function() return line and line:GetText() end)
        if ok and type(text) == "string" and not (issecretvalue and issecretvalue(text))
            and not text:find(RANK_COLOR .. "#", 1, true) then
            local plain = PlainText(text)
            -- The comparison block at the bottom ("If you replace this item...") lists changes, not stats.
            if type(ITEM_DELTA_DESCRIPTION) == "string" and plain:find(ITEM_DELTA_DESCRIPTION, 1, true) then
                break
            end
            for _, stat in ipairs(stats) do
                if IsStatLine(plain, stat.name) then
                    line:SetText(text .. stat.suffix)
                    changed = true
                    break
                end
            end
        end
    end
    if changed and tooltip.Show then
        tooltip:Show()
    end
end

function ns.ProcessTooltip(tooltip)
    pcall(ns.AddStatRanksToTooltip, tooltip)
    AddTooltipVerdict(tooltip)
end

function ns.RefreshOpenItemTooltipsAfterLoadoutChange()
    if GameTooltip and GameTooltip:IsShown() then
        GameTooltip:Hide()
    end
    if ItemRefTooltip and ItemRefTooltip:IsShown() then
        ItemRefTooltip:Hide()
    end
end

if TooltipDataProcessor and TooltipDataProcessor.AddTooltipPostCall and Enum and Enum.TooltipDataType and Enum.TooltipDataType.Item then
    TooltipDataProcessor.AddTooltipPostCall(Enum.TooltipDataType.Item, function(tooltip)
        ns.ProcessTooltip(tooltip)
    end)
else
    if GameTooltip and GameTooltip:HasScript("OnTooltipSetItem") then
        GameTooltip:HookScript("OnTooltipSetItem", ns.ProcessTooltip)
    end
    if ItemRefTooltip and ItemRefTooltip:HasScript("OnTooltipSetItem") then
        ItemRefTooltip:HookScript("OnTooltipSetItem", ns.ProcessTooltip)
    end
end
