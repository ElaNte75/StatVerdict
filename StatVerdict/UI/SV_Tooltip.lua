local addonName, ns = ...

local PREFIX = "StatVerdict"

-- The Catalyst preview (see below, at the stat ranks): true while the tooltip is being filled with the set piece, and
-- the tooltip -> item link it was showing before the swap. The set piece is not an item the player owns, so nothing
-- about saving it is offered while it shows.
local catalystPreviewing = false
local previewOf = setmetatable({}, { __mode = "k" })
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

-- Alt is held, not switched: while it is down the tooltip shows the other build, and letting go brings the first
-- one back. Over an item in the bags Alt is the marking key (Alt-click), so it changes nothing there.
-- tooltipInBags is worked out once per tooltip, in ProcessTooltip.
local tooltipInBags = false

local function OtherBuildHeld(hasOff)
    return hasOff and not tooltipInBags and IsAltKeyDown and IsAltKeyDown() and true or false
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
        -- The game's comparison tooltip (the piece worn, next to the one under the mouse) names no link, only the item
        -- id: the link is the one worn in a slot with that id.
        local name = type(tooltip.GetName) == "function" and tooltip:GetName() or nil
        local itemID = data and tonumber(data.id) or nil
        if itemID and type(name) == "string" and name:find("ShoppingTooltip", 1, true) and type(GetInventoryItemLink) == "function" then
            for slot = 1, 19 do
                local worn = GetInventoryItemLink("player", slot)
                if type(worn) == "string" and tonumber(worn:match("item:(%d+)")) == itemID then
                    return worn
                end
            end
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
        -- Pictures set into the text (the MS / OS label of a stat rank) carry the addon's own folder name in their
        -- path: that is not the verdict.
        if type(text) == "string" and string.find((text:gsub("|T.-|t", "")), PREFIX, 1, true) then
            return true
        end
    end

    return false
end

-- guid: the game's serial number of the bag piece under the mouse (tells two copies of one item apart), or nil.
local function ItemInContextLoadout(itemLink, context, guid)
    local profile = context and context.profile or nil
    if not itemLink or not profile or not ns.IsItemInEquipmentSnapshot then
        return false
    end
    local ok, contains = pcall(ns.IsItemInEquipmentSnapshot, profile, itemLink, guid)
    return ok and contains and true or false
end

-- The serial number of the piece in the bag slot a tooltip belongs to.
local function BagPieceGUID(owner)
    if type(owner) ~= "table" or not ns.GetBagItemGUID then return nil end
    local bagID = type(owner.GetBagID) == "function" and select(2, pcall(owner.GetBagID, owner)) or nil
    if bagID == nil and type(owner.GetParent) == "function" then
        local parent = owner:GetParent()
        bagID = parent and type(parent.GetID) == "function" and select(2, pcall(parent.GetID, parent)) or nil
    end
    local slotID = type(owner.GetID) == "function" and select(2, pcall(owner.GetID, owner)) or nil
    if tonumber(bagID) == nil or tonumber(slotID) == nil then return nil end
    local ok, guid = pcall(ns.GetBagItemGUID, tonumber(bagID), tonumber(slotID))
    return ok and guid or nil
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

-- Does the item upgrade this build? The same test the verdict block applies, without drawing anything.
local function IsUpgradeFor(itemLink, context)
    local profile = type(context) == "table" and context.profile or nil
    if type(profile) ~= "table" or profile.invalidGeneratedContext or not ns.BuildComparison then
        return false
    end
    local function check()
        local comparison = ns.BuildComparison(itemLink, profile)
        local selected = comparison and not comparison.missingOffhand and comparison.selected or nil
        return selected ~= nil and selected.isUpgrade == true
            and (tonumber(selected.deltaScore or selected.rawDeltaScore) or 0) > 0
    end
    local ok, result = pcall(function()
        if ns.WithStatVerdictSnapshotProfile then
            return ns.WithStatVerdictSnapshotProfile(profile, check)
        end
        return check()
    end)
    return ok and result == true
end

-- Is the tooltip the one of a piece the player wears, on the character sheet (not the inspect window)?
local function IsWornPieceTooltip(owner)
    if type(owner) ~= "table" or type(owner.GetName) ~= "function" then return false end
    local name = owner:GetName()
    return type(name) == "string" and name:match("^Character.+Slot$") ~= nil
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

    -- A piece the player wears is not compared with anything: it only explains its marks (Options > Info on worn pieces).
    if IsWornPieceTooltip(owner) then
        local db = _G.StatVerdictDB
        local wornSlot = nil
        if type(owner.GetID) == "function" then
            local okID, slotID = pcall(owner.GetID, owner)
            wornSlot = okID and tonumber(slotID) or nil
        end
        local drewInfo = false
        if not (type(db) == "table" and db.showWornInfo == false) and ns.RenderTooltipWornInfo then
            local primary = ns.GetTooltipEvaluationContexts and ns.GetTooltipEvaluationContexts() or nil
            local wornGUID = wornSlot and ns.GetWornItemGUID and ns.GetWornItemGUID(wornSlot) or nil
            local warning = wornSlot and ns.GetBagUpgradesForWornSlots and ns.GetBagUpgradesForWornSlots()[wornSlot] or nil
            local okInfo, drew = pcall(ns.RenderTooltipWornInfo, tooltip, itemLink, primary, wornGUID,
                warning ~= nil and not warning.ignored)
            drewInfo = okInfo and drew and true or false
        end
        -- A better piece in the bags (its own option: Options > Character info > Arrow on worn pieces).
        if wornSlot and ns.RenderTooltipWornBagUpgrade then
            pcall(ns.RenderTooltipWornBagUpgrade, tooltip, wornSlot, drewInfo)
        end
        return
    end

    local fromBags = (not catalystPreviewing) and tooltipInBags
    local bagGUID = fromBags and BagPieceGUID(owner) or nil   -- this very piece (two copies of an item are told apart)

    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    primaryContext = primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)

    local renderedDataUnavailable = false
    local catalystOnlyDrawn = false  -- the Main Spec drew only the Catalyst block: the Off Spec may still have a verdict
    local membershipDrawn = false    -- "Saved in ... loadout" was drawn: nothing else is said about the item
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
                local clickName = ns.MarkClickLabel and ns.MarkClickLabel(isSecondary) or (isSecondary and "Alt-Left-Click" or "Alt-Right-Click")
                if isSecondary then
                    tooltip:AddLine("|cffffd200" .. clickName .. " to save this item for " .. specName .. " (Off Spec)|r", 1, 0.82, 0, true)
                else
                    tooltip:AddLine("|cffffd200" .. clickName .. " to save this item for " .. specName .. "|r", 1, 0.82, 0, true)
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
        if fromBags and ItemInContextLoadout(itemLink, context, bagGUID) then
            ns.RememberTooltipVerdictContext(itemLink, context, nil)
            if ns.RenderTooltipLoadoutMembership then
                -- One line for both builds: when the other one holds the item as well it says "both loadouts".
                local otherContext = nil
                local candidate = (context == primaryContext) and secondaryContext or primaryContext
                if candidate and candidate ~= context and ItemInContextLoadout(itemLink, candidate, bagGUID) then
                    otherContext = candidate
                end
                ns.RenderTooltipLoadoutMembership(tooltip, context, otherContext, isSecondary)
                membershipDrawn = true
                return true
            end
        end

        -- Not an upgrade as it is, or the piece the player wears: the Main Spec still gets told when the Catalyst would
        -- make the item Best in Slot (and better than what is in the slot). Not for the Off Spec.
        local function catalystOnly(worn)
            if isSecondary or catalystPreviewing or not ns.RenderTooltipCatalystOnly then return false end
            catalystOnlyDrawn = ns.RenderTooltipCatalystOnly(tooltip, context, itemLink, worn) and true or false
            return catalystOnlyDrawn
        end

        local function buildAndRender()
            local comparison = ns.BuildComparison(itemLink, profile)
            if not comparison then
                return catalystOnly(true)
            end
            if comparison.missingOffhand then
                local rendered = RenderMissingOffhandNotice(tooltip, context)
                if rendered and fromBags then
                    ns.RememberTooltipVerdictContext(itemLink, context, comparison)
                end
                return rendered
            end
            if not comparison.selected then
                return catalystOnly(false)
            end

            if ns.RenderTooltipVerdict then
                ns.RenderTooltipVerdict(tooltip, context, comparison, isSecondary, fromBags)
                local rendered = TooltipAlreadyHasStatVerdict(tooltip)
                if not rendered then
                    rendered = catalystOnly(false)
                end
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

    -- Which build the verdict is for: the Main Spec first, whatever the window shows. Alt switches to the Off Spec, but
    -- only when an Off Spec is set: without one there is nothing to switch to. The stat ranks follow the same rule.
    local hasOff = secondaryContext ~= nil and secondaryContext ~= primaryContext
        and type(secondaryContext) == "table" and secondaryContext.profile ~= nil
    local altHeld = OtherBuildHeld(hasOff)
    local showOff = altHeld
    local firstContext, firstIsSecondary, otherContext = primaryContext, false, secondaryContext
    if showOff then
        firstContext, firstIsSecondary, otherContext = secondaryContext, true, primaryContext
    end

    -- A piece in the bags that is saved in a build's loadout needs no comparison: the mark on it already says so (it was
    -- saved when worn, or by hand). One StatVerdict line names the build, or both; nothing else is worked out.
    if fromBags and ns.RenderTooltipLoadoutMembership then
        local inFirst = ItemInContextLoadout(itemLink, firstContext, bagGUID)
        local inOther = otherContext and otherContext ~= firstContext and ItemInContextLoadout(itemLink, otherContext, bagGUID) or false
        if inFirst and inOther then
            -- Saved in both builds: one line, nothing is compared.
            local shownIsSecondary = (firstContext == secondaryContext) and (secondaryContext ~= primaryContext)
            ns.RememberTooltipVerdictContext(itemLink, firstContext, nil)
            ns.RenderTooltipLoadoutMembership(tooltip, firstContext, otherContext, shownIsSecondary)
            return
        elseif inFirst or inOther then
            -- Saved in one build only: the other build is still judged (is the piece better than what that build wears?),
            -- then one line says where it is saved.
            local markedContext = inFirst and firstContext or otherContext
            local unmarkedContext = inFirst and otherContext or firstContext
            local markedIsSecondary = (markedContext == secondaryContext) and (secondaryContext ~= primaryContext)
            local verdictDrawn = false
            if unmarkedContext and unmarkedContext ~= markedContext then
                verdictDrawn = renderContext(unmarkedContext, not markedIsSecondary) and true or false
            end
            -- Under a verdict: one plain line ("Also saved in ..."); alone: the usual StatVerdict block.
            ns.RenderTooltipLoadoutMembership(tooltip, markedContext, nil, markedIsSecondary, verdictDrawn)
            return
        end
    end

    if renderContext(firstContext, firstIsSecondary) then
        if membershipDrawn then
            return
        end
        if catalystOnlyDrawn then
            if otherContext and otherContext ~= firstContext then
                renderContext(otherContext, not firstIsSecondary)
            end
            return
        end
        -- One gold line (important, not a side hint) when the other build gains from this item too, so it is not missed.
        -- (Not while Alt is held: the Off Spec view needs no word about the Main Spec, it was just seen.)
        if hasOff and not altHeld and not catalystPreviewing and IsUpgradeFor(itemLink, otherContext) then
            tooltip:AddLine("|cffffd200Also an upgrade for Off Spec|r", 1, 0.82, 0)
            -- In the bags the tooltip cannot be switched (Alt marks there), so say how to mark the other build.
            if fromBags then
                tooltip:AddLine("|cff999999" .. (ns.MarkClickLabel and ns.MarkClickLabel(true) or "Alt-Left-Click") .. ": save in loadout|r", 0.6, 0.6, 0.6)
            else
                tooltip:AddLine("|cff999999Hold Alt to see Off Spec|r", 0.6, 0.6, 0.6)
            end
            tooltip:Show()
        end
        return
    end
    if otherContext and otherContext ~= firstContext then
        renderContext(otherContext, not firstIsSecondary)
    end
end

-- Stat ranks: every secondary stat on an item tooltip gets its place in the guide's order for the build
-- shown in the window ("+73 Critical Strike #1 MS"). Stats the guide calls roughly equal carry the same number.
-- The build is the one selected in the window (MS or OS, in gold, after the number so it
-- stands apart from a green stat line); holding Alt shows the other one. Switched off with Options > Stat Ranks (StatVerdictDB.showStatRanks).
-- Holding Ctrl over an item the Catalyst can turn into the Best in Slot set piece swaps the tooltip for that piece (same
-- item level, its own stats and verdict); Ctrl up puts the item back. (Alt is the stat ranks' key: it shows the other
-- build.) The flag only stops the swapped tooltip from being swapped again.
local RANK_COLOR = "|cffffd100"  -- the game's tooltip gold (Item Level, Vendor, Auction), not the addon's orange
-- MS / OS are small gold pictures (StatRankMS / StatRankOS in Textures), because tooltip text cannot change
-- its size inside a line. Size: height 8, width 16 (the pictures are 2:1).
local LABEL_PATH = "|TInterface\\AddOns\\StatVerdict\\Textures\\StatRank"
local LABEL_SIZE = ":8:16|t"

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

    local primary, secondary = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primary, secondary = ns.GetTooltipEvaluationContexts()
    end
    primary = primary or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)
    local hasOff = secondary and secondary.profile and true or false
    local showOff = OtherBuildHeld(hasOff)  -- Alt held: the other build
    local context = showOff and secondary or primary
    local specLabel = showOff and "OS" or "MS"
    local profile = context and context.profile or nil
    if type(profile) ~= "table" or profile.invalidGeneratedContext or not ns.GetSecondaryDisplayRanks then
        return
    end

    local stats = {}
    for statKey, entry in pairs(ns.GetSecondaryDisplayRanks(profile.secondaryOrder, profile.equalGroups)) do
        local name = _G[statKey]
        if type(name) == "string" and name ~= "" then
            stats[#stats + 1] = {
                name = name,
                suffix = " " .. RANK_COLOR .. "#" .. entry.rank .. "|r " .. LABEL_PATH .. specLabel .. LABEL_SIZE,
            }
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
            and not text:find(RANK_COLOR, 1, true) then
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

-- The item string that shows the Best in Slot set piece an item the Catalyst can convert would become, with the
-- item's own item level and bonus ids; nil when Ctrl is not held or the item has no Catalyst path. Second value: the
-- item string of the tooltip as it was.
local function CatalystPreviewLink(tooltip)
    if catalystPreviewing then return nil end
    if not (IsControlKeyDown and IsControlKeyDown()) then return nil end
    if InCombatLockdown and InCombatLockdown() then return nil end
    if tooltip ~= _G.GameTooltip or type(tooltip.SetHyperlink) ~= "function" then return nil end
    local itemLink = GetTooltipItemLink(tooltip)
    local itemString = type(itemLink) == "string" and itemLink:match("(item:[%-%d:]+)") or nil
    if not itemString or not ns.GetItemReferenceInfo or not ns.GetTooltipEvaluationContexts then return nil end
    local primary = ns.GetTooltipEvaluationContexts()
    local profile = primary and primary.profile or nil
    local info = profile and ns.GetItemReferenceInfo(itemString, profile) or nil
    local targetID = info and info.catalystPath and tonumber(info.catalystPath.targetItemID) or nil
    local previewString = targetID and ns.CatalystTargetItemString and ns.CatalystTargetItemString(itemString, targetID) or nil
    if not previewString then return nil end
    return previewString, itemString
end

-- Alt and Ctrl: redraw the tooltip that is open when one goes down or up. Alt (held): the other build.
-- Ctrl: an item the Catalyst can convert shows the set piece, and Ctrl up puts the item itself back. (Shift is the
-- game's own item comparison.)
local modifierWatcher = CreateFrame and CreateFrame("Frame") or nil
if modifierWatcher then
    modifierWatcher:RegisterEvent("MODIFIER_STATE_CHANGED")
    modifierWatcher:SetScript("OnEvent", function(_, _, key, down)
        local isAlt = key == "LALT" or key == "RALT"
        local isCtrl = key == "LCTRL" or key == "RCTRL"
        if not (isAlt or isCtrl) then return end
        local tip = _G.GameTooltip
        if not (tip and tip:IsShown()) then return end
        local original = previewOf[tip]
        if isAlt then
            -- Down shows the other build, up brings the first one back. Not over a bag item (Alt is the marking key
            -- there) and not while the set piece shows.
            if original or tooltipInBags or (InCombatLockdown and InCombatLockdown()) then return end
            if type(tip.RefreshData) == "function" then
                pcall(tip.RefreshData, tip)
            end
        elseif original then
            -- The set piece is showing: Ctrl up brings the item back; Alt changes nothing there.
            if isCtrl and not (IsControlKeyDown and IsControlKeyDown()) then
                previewOf[tip] = nil
                pcall(tip.SetHyperlink, tip, original)
            end
        elseif type(tip.RefreshData) == "function" then
            pcall(tip.RefreshData, tip)
        end
    end)
end

function ns.ProcessTooltip(tooltip)
    if not catalystPreviewing then
        tooltipInBags = ns.IsTooltipFromPlayerBags and ns.IsTooltipFromPlayerBags(tooltip) or false
    end
    local previewLink, original = CatalystPreviewLink(tooltip)
    if previewLink then
        catalystPreviewing = true
        local ok = pcall(tooltip.SetHyperlink, tooltip, previewLink)
        catalystPreviewing = false
        if ok then
            previewOf[tooltip] = original  -- the swapped tooltip was filled by this same function, one level down
            return
        end
    elseif not catalystPreviewing then
        previewOf[tooltip] = nil  -- a fresh tooltip
    end
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
