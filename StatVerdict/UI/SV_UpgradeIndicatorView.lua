local addonName, ns = ...
ns = ns or {}

local pendingRefresh = false
local pendingRefreshKind = "bags"
local pendingRefreshDelay = 0.35
local scanFrame
local BAG_REFRESH_DELAY = 0.20
local FULL_REFRESH_DELAY = 0.15
local MIN_BAG_REFRESH_INTERVAL = 0.25
local MIN_FULL_REFRESH_INTERVAL = 0.50
local NUM_CONTAINER_SCAN_FRAMES = NUM_TOTAL_BAG_FRAMES or NUM_CONTAINER_FRAMES or 13
local lastBagRefreshAt = 0
local lastFullRefreshAt = 0
local clearDecisionCacheOnNextScan = false
local debugLines = nil -- Disabled debug logging for production
local activeIndicators = {}
local indicatorSources = {}
local bagRefreshCounter = 1

local function DebugLine(line)
    if not debugLines then return end
    debugLines[#debugLines + 1] = tostring(line or "")
end

local function ShowIndicatorDebugFallback(lines)
    if type(lines) ~= "table" then return end
    local frame = ns.StatVerdictIndicatorDebugFrame
    if not frame then
        frame = CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictIndicatorDebugFrame") or "StatVerdictIndicatorDebugFrame", UIParent, "BackdropTemplate")
        frame:SetSize(680, 520)
        frame:SetPoint("CENTER")
        frame:SetFrameStrata("DIALOG")
        frame:SetMovable(true)
        frame:EnableMouse(true)
        frame:RegisterForDrag("LeftButton")
        frame:SetScript("OnDragStart", frame.StartMoving)
        frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
        frame:Hide()
        frame:SetBackdrop({
            bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
            edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
            tile = true,
            tileSize = 32,
            edgeSize = 32,
            insets = { left = 8, right = 8, top = 8, bottom = 8 },
        })

        local close = CreateFrame("Button", nil, frame, "UIPanelCloseButton")
        close:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -2, -2)

        local title = frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
        title:SetPoint("TOP", frame, "TOP", 0, -12)
        title:SetText("StatVerdict Indicator Debug")

        local scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
        scroll:SetPoint("TOPLEFT", frame, "TOPLEFT", 18, -42)
        scroll:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", -32, 18)

        local edit = CreateFrame("EditBox", nil, scroll)
        edit:SetMultiLine(true)
        edit:SetAutoFocus(false)
        edit:SetFontObject(ChatFontNormal)
        edit:SetWidth(610)
        edit:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
        scroll:SetScrollChild(edit)
        frame.editBox = edit
        ns.StatVerdictIndicatorDebugFrame = frame
    end

    frame.editBox:SetText(table.concat(lines, "\n"))
    frame.editBox:HighlightText(0, 0)
    frame:Show()
end

-- /svdebug retired from public builds (kept as quiet no-op for old macros).
SLASH_STATVERDICTDEBUG1 = "/svdebug"
SlashCmdList["STATVERDICTDEBUG"] = function()
    if not ns.STATVERDICT_DEV_TOOLS then return end
    if debugLines and #debugLines > 0 then
        ShowIndicatorDebugFallback(debugLines)
    else
        print("|cffffd76a[StatVerdict]|r No debug data available")
    end
end

local function LinkName(itemLink)
    if not itemLink then return "nil" end
    return tostring(itemLink):match("%[(.-)%]") or tostring(itemLink)
end

local function SafeCall(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, result = pcall(fn, ...)
    if ok then return result end
    return nil
end

local function LooksLikeItemLink(value)
    return type(value) == "string" and (value:find("|Hitem:", 1, true) or value:find("^item:%d+"))
end

local function IsFrameVisible(frame)
    if not frame then return false end
    if type(frame.IsVisible) == "function" then
        return frame:IsVisible()
    end
    if type(frame.IsShown) == "function" then
        return frame:IsShown()
    end
    return false
end

local GetIconAnchor

local function IsFrameInsideClip(frame, clipFrame)
    if not clipFrame then return true end
    local ok, result = pcall(function()
        if type(clipFrame.IsVisible) == "function" and not clipFrame:IsVisible() then
            return false
        end
        if type(frame.GetTop) ~= "function" or type(frame.GetBottom) ~= "function"
            or type(clipFrame.GetTop) ~= "function" or type(clipFrame.GetBottom) ~= "function" then
            return true
        end
        local top = frame:GetTop()
        local bottom = frame:GetBottom()
        local clipTop = clipFrame:GetTop()
        local clipBottom = clipFrame:GetBottom()
        if not top or not bottom or not clipTop or not clipBottom then
            return true
        end
        return bottom <= (clipTop + 2) and top >= (clipBottom - 2)
    end)
    if not ok then return true end
    return result and true or false
end

-- Indicators must never steal bag-slot clicks. Prefer Texture/FontString regions
-- (no mouse). Keep any leftover Frame overlays click-through and in parent strata.
local function EnsureClickThrough(overlay)
    if not overlay then return end
    if type(overlay.EnableMouse) ~= "function" then
        return
    end
    overlay:EnableMouse(false)
    if type(overlay.SetMouseClickEnabled) == "function" then
        overlay:SetMouseClickEnabled(false)
    end
    if type(overlay.SetMouseMotionEnabled) == "function" then
        overlay:SetMouseMotionEnabled(false)
    end
    if type(overlay.SetPropagateMouseClicks) == "function" then
        overlay:SetPropagateMouseClicks(true)
    end
    if type(overlay.SetPropagateMouseMotion) == "function" then
        overlay:SetPropagateMouseMotion(true)
    end
end

local function RepositionIndicator(frame, indicator)
    if not frame or not indicator then return end
    local anchor = GetIconAnchor(frame) or frame
    indicator:ClearAllPoints()
    local kind = indicator.svIndicatorKind
    if kind == "main_spec" or kind == "off_spec" or kind == "both_specs" then
        -- FontString anchored by CENTER on TOPRIGHT, shifted left so the
        -- trailing letter of the MS/OS badge only barely overhangs the icon.
        indicator:SetPoint("CENTER", anchor, "TOPRIGHT", -9, -6)
    else
        indicator:SetPoint("TOPLEFT", anchor, "TOPLEFT", -3, 3)
    end
    EnsureClickThrough(indicator)
    -- Frame overlays only: stay in parent strata / modest level bump.
    if type(indicator.EnableMouse) == "function"
        and type(frame.GetFrameLevel) == "function"
        and type(indicator.SetFrameLevel) == "function" then
        local ok, level = pcall(frame.GetFrameLevel, frame)
        if ok and tonumber(level) then
            indicator:SetFrameLevel(tonumber(level) + 5)
        end
    end
end

local function GetQuestItemLinkFromButton(button)
    if not button or type(button.GetID) ~= "function" or type(GetQuestItemLink) ~= "function" then
        return nil
    end
    local id = button:GetID()
    if not id or id <= 0 then return nil end
    local name = type(button.GetName) == "function" and button:GetName() or ""
    local itemType = button.type
    if itemType ~= "choice" and itemType ~= "reward" then
        if type(name) == "string" and name:find("Choice", 1, true) then
            itemType = "choice"
        elseif type(name) == "string" and name:find("Reward", 1, true) then
            itemType = "reward"
        end
    end
    if itemType == "choice" or itemType == "reward" then
        return SafeCall(GetQuestItemLink, itemType, id)
    end
    return nil
end

local function GetFrameItemLink(frame)
    if not IsFrameVisible(frame) then
        return nil
    end

    local link = nil
    if type(frame.GetItemLink) == "function" then
        link = SafeCall(frame.GetItemLink, frame)
        if LooksLikeItemLink(link) then return link end
    end
    if type(frame.GetItemLocation) == "function" and C_Item and C_Item.GetItemLink then
        local location = SafeCall(frame.GetItemLocation, frame)
        if location then
            link = SafeCall(C_Item.GetItemLink, location)
            if LooksLikeItemLink(link) then return link end
        end
    end
    if C_Container and C_Container.GetContainerItemLink then
        local bagID = type(frame.GetBagID) == "function" and SafeCall(frame.GetBagID, frame) or frame.bagID
        local slotID = type(frame.GetID) == "function" and SafeCall(frame.GetID, frame) or frame.slotID
        if bagID ~= nil and slotID ~= nil then
            link = SafeCall(C_Container.GetContainerItemLink, bagID, slotID)
            if LooksLikeItemLink(link) then return link end
        end
    end
    link = frame.itemLink or frame.link or frame.hyperlink
    if LooksLikeItemLink(link) then return link end
    link = GetQuestItemLinkFromButton(frame)
    if LooksLikeItemLink(link) then return link end
    return nil
end

local function IsBagItemFrame(frame)
    if not frame then return false end
    if type(frame.GetBagID) == "function" and SafeCall(frame.GetBagID, frame) ~= nil then
        return true
    end
    if frame.bagID ~= nil or frame.BagID ~= nil then
        return true
    end
    local name = type(frame.GetName) == "function" and frame:GetName() or nil
    return type(name) == "string" and (name:find("ContainerFrame", 1, true) or name:find("Bag", 1, true)) and true or false
end

local EQUIPPED_SLOT_NAMES = {
    CharacterHeadSlot = true,
    CharacterNeckSlot = true,
    CharacterShoulderSlot = true,
    CharacterBackSlot = true,
    CharacterChestSlot = true,
    CharacterShirtSlot = true,
    CharacterTabardSlot = true,
    CharacterWristSlot = true,
    CharacterHandsSlot = true,
    CharacterWaistSlot = true,
    CharacterLegsSlot = true,
    CharacterFeetSlot = true,
    CharacterFinger0Slot = true,
    CharacterFinger1Slot = true,
    CharacterTrinket0Slot = true,
    CharacterTrinket1Slot = true,
    CharacterMainHandSlot = true,
    CharacterSecondaryHandSlot = true,
    InspectHeadSlot = true,
    InspectNeckSlot = true,
    InspectShoulderSlot = true,
    InspectBackSlot = true,
    InspectChestSlot = true,
    InspectShirtSlot = true,
    InspectTabardSlot = true,
    InspectWristSlot = true,
    InspectHandsSlot = true,
    InspectWaistSlot = true,
    InspectLegsSlot = true,
    InspectFeetSlot = true,
    InspectFinger0Slot = true,
    InspectFinger1Slot = true,
    InspectTrinket0Slot = true,
    InspectTrinket1Slot = true,
    InspectMainHandSlot = true,
    InspectSecondaryHandSlot = true,
}

local function IsEquippedPaperDollItemFrame(frame)
    if not frame then return false end
    local name = type(frame.GetName) == "function" and frame:GetName() or nil
    if type(name) == "string" then
        if EQUIPPED_SLOT_NAMES[name] then return true end
        if (name:match("^Character.+Slot$") or name:match("^Inspect.+Slot$")) and not IsBagItemFrame(frame) then
            return true
        end
    end

    -- Retail character/inspect paper-doll slots can also be anonymous item buttons
    -- parented somewhere under PaperDollItemsFrame. Those represent already equipped
    -- items, so StatVerdict should not draw bag-style upgrade/value indicators there.
    local parent = type(frame.GetParent) == "function" and frame:GetParent() or nil
    local depth = 0
    while parent and depth < 8 do
        local parentName = type(parent.GetName) == "function" and parent:GetName() or nil
        if parentName == "PaperDollItemsFrame" or parentName == "InspectPaperDollItemsFrame" then
            return true
        end
        parent = type(parent.GetParent) == "function" and parent:GetParent() or nil
        depth = depth + 1
    end
    return false
end

GetIconAnchor = function(frame)
    if not frame then return nil end
    local candidates = {
        frame.Icon,
        frame.icon,
        frame.IconTexture,
        frame.iconTexture,
        frame.texture,
        frame.Texture,
    }
    for _, candidate in ipairs(candidates) do
        if candidate and type(candidate.GetObjectType) == "function" and type(candidate.IsShown) == "function" then
            return candidate
        end
    end
    local name = type(frame.GetName) == "function" and frame:GetName() or nil
    if type(name) == "string" then
        for _, suffix in ipairs({ "Icon", "IconTexture", "IconQuestTexture", "NormalTexture" }) do
            local candidate = _G[name .. suffix]
            if candidate and type(candidate.GetObjectType) == "function" then
                return candidate
            end
        end
    end
    return frame
end

local function HideAllIndicators()
    for indicator in pairs(activeIndicators) do
        if indicator and type(indicator.Hide) == "function" then
            indicator:Hide()
        end
    end
end

local function GetIndicatorMode(indicator, owner)
    if not indicator then return "none" end
    local parent = type(indicator.GetParent) == "function" and indicator:GetParent() or nil
    if parent == owner then
        return "child"
    end
    if parent == UIParent then
        return "floating-ui-parent"
    end
    return "other-parent"
end

local function GetFrameName(frame)
    if not frame then return "(nil)" end
    if type(frame.GetName) == "function" then
        return frame:GetName() or "(unnamed)"
    end
    return "(unnamed)"
end

local function DebugIndicatorState(frame, itemLink, state)
    if not debugLines then return end
    local indicator = frame and frame.StatVerdictUpgradeIndicator
    local parent = indicator and type(indicator.GetParent) == "function" and indicator:GetParent() or nil
    local textureObject = indicator
    if indicator and indicator.texture then
        textureObject = indicator.texture
    end
    local texturePath = textureObject and type(textureObject.GetTexture) == "function" and textureObject:GetTexture() or nil
    DebugLine(string.format(
        "Indicator mode=%s owner=%s indicatorParent=%s item=%s kind=%s shown=%s texture=%s",
        tostring(GetIndicatorMode(indicator, frame)),
        tostring(GetFrameName(frame)),
        tostring(GetFrameName(parent)),
        tostring(LinkName(itemLink)),
        tostring(state and state.kind or "none"),
        tostring(indicator and type(indicator.IsShown) == "function" and indicator:IsShown() or false),
        tostring(texturePath or "-")
    ))
end

function ns.HideUpgradeIndicators()
    HideAllIndicators()
end

local function HookIndicatorOwner(frame)
    if not frame or frame.StatVerdictIndicatorHooks or type(frame.HookScript) ~= "function" then
        return
    end
    frame.StatVerdictIndicatorHooks = true
    frame:HookScript("OnHide", function()
        if frame.StatVerdictUpgradeIndicator then frame.StatVerdictUpgradeIndicator:Hide() end
        if frame.StatVerdictSpecValueIndicator then frame.StatVerdictSpecValueIndicator:Hide() end
    end)
    -- Do not refresh on every bag-button OnShow — that storms the UI when bags open.
    -- Container UpdateItems / BAG_UPDATE already schedule a coalesced refresh.
end

local UPGRADE_ARROW_TEXTURE = "Interface\\AddOns\\StatVerdict\\Textures\\UpgradeArrow"
-- Above bag icon art / borders (same OVERLAY layer, higher sublevel).
local INDICATOR_DRAW_SUBLEVEL = 7

-- Textures / FontStrings never receive mouse. Avoid Frame wrappers on bag slots
-- so corner badges cannot steal clicks from the item button.
local function EnsureIndicator(frame)
    if frame.StatVerdictUpgradeIndicator then
        return frame.StatVerdictUpgradeIndicator
    end
    local texture = frame:CreateTexture(nil, "OVERLAY", nil, INDICATOR_DRAW_SUBLEVEL)
    texture:SetSize(18, 18)
    texture:SetTexture(UPGRADE_ARROW_TEXTURE)
    if texture.SetDrawLayer then
        texture:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
    end
    texture:Hide()
    frame.StatVerdictUpgradeIndicator = texture
    activeIndicators[texture] = true
    HookIndicatorOwner(frame)
    return texture
end

local function ApplyUpgradeLook(overlay)
    if not overlay then return end
    if overlay.SetTexture then
        overlay:SetSize(18, 18)
        overlay:SetTexture(UPGRADE_ARROW_TEXTURE)
        overlay:SetVertexColor(1, 1, 1, 1)
        if overlay.SetDrawLayer then
            overlay:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
        end
        overlay:Show()
    elseif overlay.texture then
        overlay:SetSize(18, 18)
        overlay.texture:SetTexture(UPGRADE_ARROW_TEXTURE)
        overlay.texture:SetVertexColor(1, 1, 1, 1)
        if overlay.texture.SetDrawLayer then
            overlay.texture:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
        end
        overlay.texture:Show()
    end
end

local function EnsureSpecValueIndicator(frame)
    if frame.StatVerdictSpecValueIndicator then
        return frame.StatVerdictSpecValueIndicator
    end
    local text = frame:CreateFontString(nil, "OVERLAY")
    if type(text.SetDrawLayer) == "function" then
        text:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
    end
    if type(text.SetFont) == "function" then
        text:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", 13, "OUTLINE")
    end
    text:SetText("|cff00ff00OS|r")
    text:Hide()
    frame.StatVerdictSpecValueIndicator = text
    activeIndicators[text] = true
    HookIndicatorOwner(frame)
    return text
end

local function SetLetterBadgeFont(overlay, kind)
    local text = overlay
    if overlay and overlay.text then
        text = overlay.text
    end
    if not (text and text.SetFont) then return end
    local file, _, flags = text:GetFont()
    file = file or STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
    text:SetFont(file, 13, flags or "OUTLINE")
end

local function HideFrameIndicators(frame)
    if frame.StatVerdictUpgradeIndicator then
        frame.StatVerdictUpgradeIndicator.svIndicatorKind = nil
        frame.StatVerdictUpgradeIndicator:Hide()
    end
    if frame.StatVerdictSpecValueIndicator then
        frame.StatVerdictSpecValueIndicator.svIndicatorKind = nil
        frame.StatVerdictSpecValueIndicator:Hide()
    end
end

local function SetIndicator(frame, state, options)
    if not state then
        if options and options.nativeUpgradeIcon and frame and frame.UpgradeIcon and type(frame.UpgradeIcon.SetShown) == "function" then
            frame.UpgradeIcon:SetShown(false)
        end
        HideFrameIndicators(frame)
        return
    end

    local showUpgrade = state.kind == "upgrade"
    local specRole = state.specRole
    local specLabel = state.specLabel
    if not specRole and (state.kind == "main_spec" or state.kind == "off_spec" or state.kind == "both_specs") then
        specRole = state.kind
        specLabel = state.label or state.text
    end

    -- Upgrade arrow (top-left). Always use StatVerdict's texture so draw-layer
    -- stays above bag icon art (Blizzard UpgradeIcon often sits behind the icon).
    if showUpgrade then
        if options and options.nativeUpgradeIcon and frame.UpgradeIcon and type(frame.UpgradeIcon.SetShown) == "function" then
            -- Keep native hidden; custom arrow is the stable path.
            frame.UpgradeIcon:SetShown(false)
        end
        local overlay = EnsureIndicator(frame)
        overlay.svIndicatorKind = state.kind
        ApplyUpgradeLook(overlay)
        RepositionIndicator(frame, overlay)
        overlay:Show()
    else
        if frame.StatVerdictUpgradeIndicator then
            frame.StatVerdictUpgradeIndicator.svIndicatorKind = nil
            frame.StatVerdictUpgradeIndicator:Hide()
        end
        if options and options.nativeUpgradeIcon and frame.UpgradeIcon and type(frame.UpgradeIcon.SetShown) == "function" then
            frame.UpgradeIcon:SetShown(false)
        end
    end

    -- Green letter badges (top-right): MS / OS.
    local letter = nil
    local letterKind = nil
    if specRole then
        letter = specLabel or (specRole == "off_spec" and "OS" or (specRole == "both_specs" and "M/O" or "MS"))
        letterKind = specRole
    end

    if letter then
        local value = EnsureSpecValueIndicator(frame)
        value.svIndicatorKind = letterKind
        SetLetterBadgeFont(value, letterKind)
        value:SetText("|cff00ff00" .. tostring(letter) .. "|r")
        RepositionIndicator(frame, value)
        value:Show()
    elseif frame.StatVerdictSpecValueIndicator then
        frame.StatVerdictSpecValueIndicator.svIndicatorKind = nil
        frame.StatVerdictSpecValueIndicator:Hide()
    end
end

local function HookBagButtonApprove(button)
    if not button or button.StatVerdictApproveHooked or type(button.HookScript) ~= "function" then
        return
    end
    button.StatVerdictApproveHooked = true
    button:HookScript("PreClick", function(self, mouseButton)
        if mouseButton ~= "RightButton" and mouseButton ~= "LeftButton" then
            return
        end
        if not IsAltKeyDown or not IsAltKeyDown() then
            return
        end
        if InCombatLockdown and InCombatLockdown() then
            return
        end

        local preferSecondary = (mouseButton == "LeftButton")
        if preferSecondary then
            local secondaryContext = nil
            if ns.GetTooltipEvaluationContexts then
                _, secondaryContext = ns.GetTooltipEvaluationContexts()
            end
            if not secondaryContext then
                return
            end
        end

        local itemLink = nil
        local bagID = type(self.GetBagID) == "function" and SafeCall(self.GetBagID, self) or nil
        if bagID == nil and type(self.GetParent) == "function" then
            local parent = self:GetParent()
            bagID = parent and type(parent.GetID) == "function" and SafeCall(parent.GetID, parent) or nil
        end
        local slotID = SafeCall(self.GetID, self)
        if bagID ~= nil and slotID ~= nil and C_Container and C_Container.GetContainerItemInfo then
            local itemInfo = SafeCall(C_Container.GetContainerItemInfo, bagID, slotID)
            if type(itemInfo) == "table" then
                itemLink = itemInfo.hyperlink
            end
        end
        itemLink = itemLink or GetFrameItemLink(self)
        if not itemLink or not ns.TryApproveItemLink then
            return
        end
        ns.TryApproveItemLink(itemLink, nil, preferSecondary)
    end)
end

local function UpdateItemButton(frame, itemLink, options)
    if not frame then return false end
    if options and options.source == "bags" then
        HookBagButtonApprove(frame)
    end
    if IsEquippedPaperDollItemFrame(frame) then
        HideFrameIndicators(frame)
        return false
    end
    local hasExplicitItemLink = itemLink ~= nil
    local frameUsable = IsFrameVisible(frame)
        or (hasExplicitItemLink and type(frame.IsShown) == "function" and frame:IsShown())
    if not frameUsable then
        HideFrameIndicators(frame)
        return false
    end
    if options and options.clipFrame and not IsFrameInsideClip(frame, options.clipFrame) then
        HideFrameIndicators(frame)
        return false
    end
    itemLink = itemLink or GetFrameItemLink(frame)
    if itemLink then
        local isBag = IsBagItemFrame(frame) or (options and options.source == "bags")
        local stateOptions = options
        if isBag and (not options or options.source ~= "bags") then
            stateOptions = {
                source = "bags",
                nativeUpgradeIcon = options and options.nativeUpgradeIcon,
                allowValueIndicator = options and options.allowValueIndicator,
            }
        end
        local state = ns.GetUpgradeIndicatorItemState and ns.GetUpgradeIndicatorItemState(itemLink, stateOptions) or nil
        SetIndicator(frame, state, options)
        DebugIndicatorState(frame, itemLink, state)
        if debugLines then
            local name = type(frame.GetName) == "function" and frame:GetName() or nil
            local parent = type(frame.GetParent) == "function" and frame:GetParent() or nil
            local parentName = parent and type(parent.GetName) == "function" and parent:GetName() or nil
            local width = type(frame.GetWidth) == "function" and frame:GetWidth() or 0
            local height = type(frame.GetHeight) == "function" and frame:GetHeight() or 0
            DebugLine(string.format(
                "%s parent=%s size=%.0fx%.0f item=%s indicator=%s",
                tostring(name or "(unnamed)"),
                tostring(parentName or "(unnamed)"),
                tonumber(width) or 0,
                tonumber(height) or 0,
                LinkName(itemLink),
                tostring(state and state.kind or "none")
            ))
        end
        return true
    end
    HideFrameIndicators(frame)
    return false
end

function ns.UpdateUpgradeIndicatorFrame(frame, itemLink, options)
    return UpdateItemButton(frame, itemLink, options)
end

function ns.RegisterUpgradeIndicatorSource(name, scanner)
    if type(name) ~= "string" or name == "" or type(scanner) ~= "function" then
        return
    end
    indicatorSources[name] = scanner
end

local function ScanRegisteredSources()
    local total = 0
    local sourceCount = 0
    for name, scanner in pairs(indicatorSources) do
        sourceCount = sourceCount + 1
        local ok, count = pcall(scanner)
        count = ok and tonumber(count) or 0
        total = total + count
        if debugLines then
            DebugLine(string.format("Source %s: withLinks=%d", tostring(name), count))
        end
    end
    if debugLines then
        DebugLine(string.format("ScanRegisteredSources: Found %d sources, total links=%d", sourceCount, total))
    end
    return total
end

local function ScanNamedButtonSeries(prefix, maxIndex)
    local count = 0
    local seen = 0
    for index = 1, maxIndex do
        local button = _G[prefix .. index]
        if button and IsFrameVisible(button) then
            seen = seen + 1
            if UpdateItemButton(button, nil, { allowValueIndicator = true, nativeUpgradeIcon = true, source = "bags" }) then
                count = count + 1
            end
        end
    end
    if debugLines and seen > 0 then
        DebugLine(string.format("Named series %s*: visible=%d withLinks=%d", prefix, seen, count))
    end
    return count
end

local function UpdateBagItemButton(button)
    if not button or button.isExtended then return false end
    HookBagButtonApprove(button)
    local itemLink = nil
    if C_Container and C_Container.GetContainerItemInfo and type(button.GetID) == "function" then
        local bagID = type(button.GetBagID) == "function" and SafeCall(button.GetBagID, button) or nil
        if bagID == nil and type(button.GetParent) == "function" then
            local parent = button:GetParent()
            bagID = parent and type(parent.GetID) == "function" and SafeCall(parent.GetID, parent) or nil
        end
        local slotID = SafeCall(button.GetID, button)
        if bagID ~= nil and slotID ~= nil then
            local itemInfo = SafeCall(C_Container.GetContainerItemInfo, bagID, slotID)
            if type(itemInfo) == "table" then
                itemLink = itemInfo.hyperlink
                if not itemInfo.stackCount then
                    itemLink = nil
                end
            end
        end
    end
    itemLink = itemLink or GetFrameItemLink(button)
    if not itemLink then
        if button.UpgradeIcon and type(button.UpgradeIcon.SetShown) == "function" then
            button.UpgradeIcon:SetShown(false)
        end
        HideFrameIndicators(button)
        button.StatVerdictLastCheckedRefresh = nil
        button.StatVerdictLastCheckedItemLink = nil
        return false
    end
    -- Always refresh when cache is invalidated to prevent stale state
    if clearDecisionCacheOnNextScan then
        button.StatVerdictLastCheckedRefresh = nil
        button.StatVerdictLastCheckedItemLink = nil
    elseif button.StatVerdictLastCheckedRefresh == bagRefreshCounter and button.StatVerdictLastCheckedItemLink == itemLink then
        return true
    end
    button.StatVerdictLastCheckedRefresh = bagRefreshCounter
    button.StatVerdictLastCheckedItemLink = itemLink
    return UpdateItemButton(button, itemLink, { allowValueIndicator = true, nativeUpgradeIcon = true, source = "bags" })
end

local function UpdateContainerFrameUpgradeIcons(container)
    if not container or not IsFrameVisible(container) then return 0 end
    if debugLines then
        DebugLine(string.format("Bag update: %s", tostring(GetFrameName(container))))
    end
    local count = 0
    if type(container.EnumerateValidItems) == "function" then
        for _, itemButton in container:EnumerateValidItems() do
            if UpdateBagItemButton(itemButton) then
                count = count + 1
            end
        end
        return count
    end

    local prefix = type(container.GetName) == "function" and container:GetName() or nil
    local size = tonumber(container.size) or 0
    if prefix and size > 0 then
        for index = 1, size do
            if UpdateBagItemButton(_G[prefix .. "Item" .. index]) then
                count = count + 1
            end
        end
    end
    return count
end

local function ScanBagButtons()
    local count = 0
    bagRefreshCounter = bagRefreshCounter + 1
    if _G.ContainerFrameCombinedBags and IsFrameVisible(_G.ContainerFrameCombinedBags) then
        count = count + UpdateContainerFrameUpgradeIcons(_G.ContainerFrameCombinedBags)
    end
    for frameIndex = 1, NUM_CONTAINER_SCAN_FRAMES do
        local container = _G["ContainerFrame" .. frameIndex]
        if container and IsFrameVisible(container) then
            count = count + UpdateContainerFrameUpgradeIcons(container)
        end
    end
    if count == 0 then
        count = count + ScanNamedButtonSeries("ContainerFrameCombinedBagsItem", 220)
        count = count + ScanNamedButtonSeries("ContainerFrameCombinedBagsItemButton", 220)
        for frameIndex = 1, NUM_CONTAINER_SCAN_FRAMES do
            count = count + ScanNamedButtonSeries("ContainerFrame" .. frameIndex .. "Item", 80)
        end
    end
    return count
end

local function AnyKnownContainerVisible()
    if IsFrameVisible(_G.ContainerFrameCombinedBags) then
        return true
    end
    for index = 1, NUM_CONTAINER_SCAN_FRAMES do
        if IsFrameVisible(_G["ContainerFrame" .. index]) then
            return true
        end
    end
    return false
end

local function ScanVisibleItemFrames(kind)
    kind = kind or "bags"
    -- Full scans wipe everything first. Bag-only updates each visible slot in place
    -- (empty slots clear themselves) so we avoid a hide/show storm on every BAG_UPDATE.
    if kind == "full" then
        HideAllIndicators()
    end
    if clearDecisionCacheOnNextScan and ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
        clearDecisionCacheOnNextScan = false
    end

    local bagCount = 0
    if AnyKnownContainerVisible() then
        bagCount = ScanBagButtons()
    elseif kind == "bags" then
        HideAllIndicators()
    end

    local sourceCount = 0
    -- Only scan external sources during full refresh to prevent performance issues
    if kind == "full" then
        sourceCount = ScanRegisteredSources()
    end

    if debugLines then
        DebugLine(string.format("Summary: kind=%s bagLinks=%d sourceLinks=%d globalGenericScan=disabled pawnStyleBags=enabled", tostring(kind), bagCount, sourceCount))
    end
end

local function UpgradeRefreshNow(kind)
    if debugLines then
        DebugLine(string.format("UpgradeRefreshNow: Called with kind=%s", tostring(kind)))
    end
    if InCombatLockdown and InCombatLockdown() then
        if debugLines then
            DebugLine("UpgradeRefreshNow: Blocked - In combat")
        end
        return
    end
    local now = GetTime and GetTime() or 0
    if kind == "full" then
        if now > 0 and (now - lastFullRefreshAt) < MIN_FULL_REFRESH_INTERVAL then
            if debugLines then
                DebugLine("UpgradeRefreshNow: Blocked - Full refresh throttled")
            end
            return
        end
        lastFullRefreshAt = now
    else
        if now > 0 and (now - lastBagRefreshAt) < MIN_BAG_REFRESH_INTERVAL then
            if debugLines then
                DebugLine("UpgradeRefreshNow: Blocked - Bag refresh throttled")
            end
            return
        end
        lastBagRefreshAt = now
    end
    if debugLines then
        DebugLine(string.format("UpgradeRefreshNow: Proceeding with scan kind=%s", tostring(kind)))
    end
    ScanVisibleItemFrames(kind)
end

function ns.RefreshUpgradeIndicators(kind)
    if debugLines then
        DebugLine(string.format("ns.RefreshUpgradeIndicators: Called with kind=%s", tostring(kind)))
    end
    kind = kind == "full" and "full" or "bags"
    if pendingRefresh then
        if debugLines then
            DebugLine(string.format("ns.RefreshUpgradeIndicators: Blocked - Pending refresh exists (kind=%s)", tostring(kind)))
        end
        if kind == "full" then
            pendingRefreshKind = "full"
            pendingRefreshDelay = math.min(pendingRefreshDelay or FULL_REFRESH_DELAY, FULL_REFRESH_DELAY)
        end
        return
    end
    pendingRefresh = true
    pendingRefreshKind = kind
    pendingRefreshDelay = kind == "full" and FULL_REFRESH_DELAY or BAG_REFRESH_DELAY
    if debugLines then
        DebugLine(string.format("ns.RefreshUpgradeIndicators: Scheduling UpgradeRefreshNow in %s seconds for kind=%s", tostring(pendingRefreshDelay), tostring(pendingRefreshKind)))
    end
    C_Timer.After(pendingRefreshDelay, function()
        if debugLines then
            DebugLine(string.format("ns.RefreshUpgradeIndicators: Timer fired, calling UpgradeRefreshNow with kind=%s", tostring(pendingRefreshKind)))
        end
        local refreshKind = pendingRefreshKind or "bags"
        pendingRefresh = false
        pendingRefreshKind = "bags"
        UpgradeRefreshNow(refreshKind)
    end)
end

function ns.ForceUpgradeIndicatorRefreshNow(kind)
    clearDecisionCacheOnNextScan = true
    if ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
    end
    pendingRefresh = false
    pendingRefreshKind = "bags"
    lastBagRefreshAt = 0
    lastFullRefreshAt = 0
    UpgradeRefreshNow(kind == "bags" and "bags" or "full")
end

function ns.InvalidateUpgradeIndicatorDecisionCache()
    clearDecisionCacheOnNextScan = true
end

local function ScheduleRefresh(kind)
    ns.RefreshUpgradeIndicators(kind or "bags")
end

local hookedShowFrames = {}

local function HookFrameShow(frame)
    if not frame or hookedShowFrames[frame] or type(frame.HookScript) ~= "function" then
        return
    end
    hookedShowFrames[frame] = true
    frame:HookScript("OnShow", ScheduleRefresh)
    frame:HookScript("OnHide", HideAllIndicators)
end

local function HookKnownContainerShows()
    HookFrameShow(_G.ContainerFrameCombinedBags)
    for index = 1, NUM_CONTAINER_SCAN_FRAMES do
        HookFrameShow(_G["ContainerFrame" .. index])
    end
end

scanFrame = CreateFrame("Frame")
local function RegisterEventSafe(eventName)
    local ok = pcall(scanFrame.RegisterEvent, scanFrame, eventName)
    return ok
end

RegisterEventSafe("PLAYER_LOGIN")
RegisterEventSafe("PLAYER_EQUIPMENT_CHANGED")
RegisterEventSafe("BAG_UPDATE_DELAYED")
RegisterEventSafe("BAG_NEW_ITEMS_UPDATED")
RegisterEventSafe("QUEST_DETAIL")
RegisterEventSafe("QUEST_PROGRESS")
RegisterEventSafe("QUEST_COMPLETE")
RegisterEventSafe("QUEST_FINISHED")
RegisterEventSafe("PLAYER_REGEN_ENABLED")
RegisterEventSafe("GET_ITEM_INFO_RECEIVED")
scanFrame:SetScript("OnEvent", function(_, event)
    HookKnownContainerShows()
    if event == "PLAYER_EQUIPMENT_CHANGED"
        or event == "PLAYER_SPECIALIZATION_CHANGED"
        or event == "PLAYER_TALENT_UPDATE"
        or event == "TRAIT_CONFIG_UPDATED"
        or event == "TRAIT_SUB_TREE_CHANGED" then
        clearDecisionCacheOnNextScan = true
        bagRefreshCounter = bagRefreshCounter + 1 -- Force refresh of bag items
        -- Use delayed full refresh to prevent performance spikes
        C_Timer.After(0.5, function()
            ScheduleRefresh("full")
        end)
        return
    end
    if event == "PLAYER_LOGIN" or event == "GET_ITEM_INFO_RECEIVED"
        or event == "QUEST_DETAIL" or event == "QUEST_PROGRESS" or event == "QUEST_COMPLETE" or event == "QUEST_FINISHED"
    then
        ScheduleRefresh("full")
        return
    end
    ScheduleRefresh("bags")
end)

if hooksecurefunc then
    -- Coalesce all container paint hooks into one throttled ScheduleRefresh.
    -- Per-UpdateItems timers used to stack and re-evaluate every slot repeatedly.
    if ContainerFrameMixin and type(ContainerFrameMixin.UpdateItems) == "function" then
        hooksecurefunc(ContainerFrameMixin, "UpdateItems", function()
            ScheduleRefresh("bags")
        end)
    end
    if _G.ContainerFrameCombinedBags and type(_G.ContainerFrameCombinedBags.UpdateItems) == "function" then
        hooksecurefunc(_G.ContainerFrameCombinedBags, "UpdateItems", function()
            ScheduleRefresh("bags")
        end)
    end
    for index = 1, NUM_CONTAINER_SCAN_FRAMES do
        local container = _G["ContainerFrame" .. index]
        if container and type(container.UpdateItems) == "function" then
            hooksecurefunc(container, "UpdateItems", function()
                ScheduleRefresh("bags")
            end)
        end
    end
    if type(ContainerFrame_Update) == "function" then
        hooksecurefunc("ContainerFrame_Update", function() ScheduleRefresh("bags") end)
    end
    if type(ContainerFrame_UpdateItems) == "function" then
        hooksecurefunc("ContainerFrame_UpdateItems", function() ScheduleRefresh("bags") end)
    end
    for _, functionName in ipairs({ "ToggleAllBags", "OpenAllBags", "CloseAllBags", "ToggleBag", "OpenBag", "CloseBag", "ToggleBackpack", "OpenBackpack", "CloseBackpack" }) do
        if type(_G[functionName]) == "function" then
            hooksecurefunc(functionName, function()
                HookKnownContainerShows()
                ScheduleRefresh("bags")
            end)
        end
    end
end

if C_Timer then
    C_Timer.After(0.50, function()
        HookKnownContainerShows()
        ScheduleRefresh("full")
    end)
end
