local addonName, ns = ...

local Panel = {}
ns.StatVerdictOptionsDrawerPanel = Panel

-- Match setup checkbox look (SettingsPanel), slightly larger for readability.
local DROPDOWN_LABEL_FONT_SIZE = 10
local DROPDOWN_SCALE = 0.92
local CHECKBOX_LABEL_FONT_SIZE = 11
local BAG_CHECK_LABEL_GAP = 5
local BAG_CHECK_STEP = 24
local DRAWER_PREFERRED_WIDTH = 280
local TITLE_FONT_SIZE_DEFAULT = 15
local TITLE_FONT_SIZE_MIN = 11
local TITLE_FONT_SIZE_MAX = 24

local function Offset(key)
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function HeightDelta(key)
    if ns.GetDevLayoutHeightDelta then return ns.GetDevLayoutHeightDelta(key) end
    return 0
end

local function Padding(key)
    if ns.GetDevLayoutPadding then return ns.GetDevLayoutPadding(key) end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

local function Register(key, label, region, options)
    if ns.RegisterDevLayoutRegion then ns.RegisterDevLayoutRegion(key, label, region, options) end
end

local function Clamp(value, minValue, maxValue)
    value = tonumber(value) or 0
    if value < minValue then return minValue end
    if value > maxValue then return maxValue end
    return value
end

-- Place a Features text title with AdvDev Move / Size / Padding (hit region tracks glyphs).
local function PlaceFeaturesTitle(card, fontString, layoutKey, label, defaultX, defaultY)
    if not (card and fontString and layoutKey) then return end
    local ox, oy = Offset(layoutKey)
    local pad = Padding(layoutKey .. ".pad")
    fontString:ClearAllPoints()
    fontString:SetPoint(
        "TOPLEFT",
        card,
        "TOPLEFT",
        defaultX + (ox or 0) + (pad.left or 0),
        defaultY + (oy or 0) - (pad.top or 0)
    )
    fontString:Show()

    local baseW = 80
    local baseH = 18
    if fontString.GetStringWidth then
        baseW = math.max(40, (fontString:GetStringWidth() or 0) + 8)
    end
    if fontString.GetStringHeight then
        baseH = math.max(14, (fontString:GetStringHeight() or 0) + 4)
    end
    local logicalW = baseW + SizeDelta(layoutKey .. ".width")
    local logicalH = baseH + HeightDelta(layoutKey .. ".height")
    if logicalW < 24 then logicalW = 24 end
    if logicalH < 12 then logicalH = 12 end

    local hit = nil
    if ns.EnsureDevLayoutTextHitRegion then
        hit = ns.EnsureDevLayoutTextHitRegion(card, layoutKey, fontString, {
            padding = 2,
            minWidth = 24,
            minHeight = 12,
        })
    end
    if hit and hit.SetSize then
        local visW = math.max(16, logicalW - (pad.left or 0) - (pad.right or 0))
        local visH = math.max(10, logicalH - (pad.top or 0) - (pad.bottom or 0))
        hit:SetSize(visW, visH)
    end
    if ns.RegisterDevLayoutOuterSpec then
        ns.RegisterDevLayoutOuterSpec(layoutKey, {
            label = label,
            moveKey = layoutKey,
            widthKey = layoutKey .. ".width",
            heightKey = layoutKey .. ".height",
            padKey = layoutKey .. ".pad",
            baseW = baseW,
            baseH = baseH,
            sharedFrameHeight = false,
            lockKey = layoutKey .. ".locked",
        })
    end
    if hit then
        Register(layoutKey, label, hit, {
            axis = "xy",
            padding = 0,
            group = "controls",
            protect = true,
            exactHit = true,
            alwaysCapture = true,
        })
    end
end

-- Checkbox group: tight AdvDev box around the marker toggles only.
local function PlaceBagChecksBlock(card, block, layoutKey, label, defaultX, defaultY, baseW, baseH)
    if not (card and block and layoutKey) then return end
    local ox, oy = Offset(layoutKey)
    local pad = Padding(layoutKey .. ".pad")
    local logicalW = baseW + SizeDelta(layoutKey .. ".width")
    local logicalH = baseH + HeightDelta(layoutKey .. ".height")
    -- Cap runaway saved heights from older orphan AdvDev boxes.
    if logicalW < 80 then logicalW = 80 end
    if logicalH < baseH then logicalH = baseH end
    if logicalH > baseH + 80 then logicalH = baseH + 80 end
    if logicalW > 420 then logicalW = 420 end
    local visW = math.max(40, logicalW - (pad.left or 0) - (pad.right or 0))
    local visH = math.max(20, logicalH - (pad.top or 0) - (pad.bottom or 0))
    block:ClearAllPoints()
    block:SetPoint(
        "TOPLEFT",
        card,
        "TOPLEFT",
        defaultX + (ox or 0) + (pad.left or 0),
        defaultY + (oy or 0) - (pad.top or 0)
    )
    block:SetSize(visW, visH)
    block:Show()
    if block.SetBackdrop then
        if ns.UnregisterDevLayoutBorderEditOnly then
            ns.UnregisterDevLayoutBorderEditOnly(block, 0, 0, 0, 0)
        end
        if block.SetBackdropBorderColor then
            block:SetBackdropBorderColor(0, 0, 0, 0)
        end
        if block.SetBackdropColor then
            block:SetBackdropColor(0, 0, 0, 0)
        end
    end
    if ns.RegisterDevLayoutOuterSpec then
        ns.RegisterDevLayoutOuterSpec(layoutKey, {
            label = label,
            moveKey = layoutKey,
            widthKey = layoutKey .. ".width",
            heightKey = layoutKey .. ".height",
            padKey = layoutKey .. ".pad",
            baseW = baseW,
            baseH = baseH,
            sharedFrameHeight = false,
            lockKey = layoutKey .. ".locked",
        })
    end
    Register(layoutKey, label, block, {
        axis = "xy",
        padding = 0,
        group = "controls",
        protect = true,
        exactHit = true,
        alwaysCapture = true,
    })
end

-- Quiet reader for saved title size (no Features UI). Both titles share this value.
function ns.GetSpecTitleFontSize()
    local db = _G.StatVerdictDB
    local size = db and tonumber(db.specTitleFontSize) or nil
    if size == nil then
        size = TITLE_FONT_SIZE_DEFAULT
    end
    return Clamp(size, TITLE_FONT_SIZE_MIN, TITLE_FONT_SIZE_MAX)
end

local function OptionFlagOn(key)
    local db = _G.StatVerdictDB
    return db == nil or db[key] ~= false
end

local function RefreshBagIndicatorsSoon()
    if ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
    elseif ns.InvalidateUpgradeIndicatorDecisionCache then
        ns.InvalidateUpgradeIndicatorDecisionCache()
    end
    if ns.ForceUpgradeIndicatorRefreshNow then
        ns.ForceUpgradeIndicatorRefreshNow("bags")
    elseif ns.RefreshUpgradeIndicators then
        ns.RefreshUpgradeIndicators("bags")
    elseif ns.RequestInventoryVerdictRefresh then
        ns.RequestInventoryVerdictRefresh("bags")
    end
end

local function ApplyCheckboxLabelFont(control)
    if not (control and control.Text and control.Text.GetFont and control.Text.SetFont) then return end
    local font, _, flags = control.Text:GetFont()
    if font then control.Text:SetFont(font, CHECKBOX_LABEL_FONT_SIZE, flags) end
end

local function ApplyBagCheckLabelGap(control)
    local text = control and control.Text
    if not (text and text.ClearAllPoints and text.SetPoint) then return end
    text:ClearAllPoints()
    text:SetPoint("LEFT", control, "RIGHT", BAG_CHECK_LABEL_GAP, 1)
    text:SetJustifyH("LEFT")
end

local function ClearAccentWordLabel(control)
    if not control then return end
    if control.svAccent then control.svAccent:Hide() end
    if control.svRest then control.svRest:Hide() end
    if control.Text then control.Text:Show() end
end

-- Future Safe / Approve toggles land in this list too.
-- No master "Enable All" — each marker is toggled manually.
local BAG_INDICATOR_OPTIONS = {
    { key = "showUpgradeArrow", label = "Upgrade Arrow" },
    { key = "showMsOsLabels", label = "|cff00ff00MS|r / |cff00ff00OS|r Labels" },
}

local function EnsureOptionCheckbox(card, option, parent)
    local optionKey = option.key
    card.bagIndicatorChecks = card.bagIndicatorChecks or {}
    local check = card.bagIndicatorChecks[optionKey]
    parent = parent or card
    if not check then
        check = CreateFrame("CheckButton", nil, parent, "UICheckButtonTemplate")
        check:SetSize(22, 22)
        check:SetScale(1.0)
        check.optionKey = optionKey
        card.bagIndicatorChecks[optionKey] = check
    else
        check:SetParent(parent)
        check:SetSize(22, 22)
        check:SetScale(1.0)
    end

    ClearAccentWordLabel(check)
    if check.Text then
        check.Text:Show()
        check.Text:SetText(option.label)
        check.Text:SetTextColor(1, 1, 1)
        ApplyCheckboxLabelFont(check)
        ApplyBagCheckLabelGap(check)
    end
    return check
end

local function SyncBagIndicatorOptionChecks(card)
    if not card or not card.bagIndicatorChecks then return end
    for _, option in ipairs(BAG_INDICATOR_OPTIONS) do
        local check = card.bagIndicatorChecks[option.key]
        if check then
            check:SetChecked(OptionFlagOn(option.key))
            check:Enable()
            check:SetAlpha(1)
        end
    end
    -- Legacy Enable All checkbox removed from UI.
    local legacy = card.bagIndicatorChecks.showBagIndicators
    if legacy then
        legacy:Hide()
        legacy:SetScript("OnClick", nil)
    end
end

local function HideLegacyTitleFontUi(card)
    if not card then return end
    if card.displayTitle then card.displayTitle:Hide() end
    if card.titleFontLabel then card.titleFontLabel:Hide() end
    if card.titleFontHint then card.titleFontHint:Hide() end
    if card.titleFontValue then card.titleFontValue:Hide() end
    if card.titleFontMinus then card.titleFontMinus:Hide() end
    if card.titleFontPlus then card.titleFontPlus:Hide() end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("options.displayTitle")
        ns.UnregisterDevLayoutRegion("options.titleFont")
        ns.UnregisterDevLayoutRegion("options.showBagIndicators")
    end
end

local function EnsureBagChecksBlock(card)
    local block = card.bagChecksBlock
    if block then return block end
    block = CreateFrame("Frame", nil, card, "BackdropTemplate")
    block:EnableMouse(false)
    block:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 8,
        insets = { left = 2, right = 2, top = 2, bottom = 2 },
    })
    block:SetBackdropColor(0, 0, 0, 0)
    block:SetBackdropBorderColor(0, 0, 0, 0)
    card.bagChecksBlock = block
    return block
end

local function UnregisterFeaturesInnerDev()
    if not ns.UnregisterDevLayoutRegion then return end
    ns.UnregisterDevLayoutRegion("options.title")
    ns.UnregisterDevLayoutRegion("options.bagMarkersTitle")
    ns.UnregisterDevLayoutRegion("options.bagChecks")
    ns.UnregisterDevLayoutRegion("options.showBagIndicators")
    for _, option in ipairs(BAG_INDICATOR_OPTIONS) do
        ns.UnregisterDevLayoutRegion("options." .. option.key)
    end
end

local function EnsureCard(frame)
    if frame.optionsDrawerCard then
        HideLegacyTitleFontUi(frame.optionsDrawerCard)
        return frame.optionsDrawerCard
    end

    local card = CreateFrame("Frame", nil, frame, "BackdropTemplate")
    card:SetFrameLevel(math.max(1, frame:GetFrameLevel() - 1))
    card:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    card:SetBackdropColor(0.018, 0.022, 0.030, 0.96)
    card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)

    card.title = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.title:SetPoint("TOPLEFT", card, "TOPLEFT", 12, -12)
    card.title:SetText("Features")
    card.title:SetTextColor(1.0, 0.82, 0.0)

    card.bagMarkersTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.bagMarkersTitle:SetText("Bag Markers")
    card.bagMarkersTitle:SetTextColor(1.0, 0.82, 0.0)

    card.hint = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.hint:SetTextColor(0.72, 0.72, 0.72)
    card.hint:SetJustifyH("LEFT")
    card.hint:SetWordWrap(true)
    card.hint:Hide()

    frame.optionsDrawerCard = card
    return card
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "options"
end

function Panel.SetOpen(open)
    if open then
        if ns.SetRightPanelMode then ns.SetRightPanelMode("options") end
    else
        if Panel.IsOpen() and ns.SetRightPanelMode then
            ns.SetRightPanelMode(nil)
        end
    end
end

function Panel.Toggle()
    if ns.ToggleRightPanelMode then
        ns.ToggleRightPanelMode("options")
    end
end

function Panel.GetPreferredWidth(frame)
    -- Single source of truth: base + SizeDelta (never cache a width that already includes delta).
    local width = DRAWER_PREFERRED_WIDTH + SizeDelta("options.width")
    if width < 200 then width = 200 end
    if width > 520 then width = 520 end
    return width
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.optionsDrawerCard then frame.optionsDrawerCard:Hide() end
        if frame.devOptionsWidthRegion then frame.devOptionsWidthRegion:Hide() end
        if ns.UnregisterDevLayoutRegion then ns.UnregisterDevLayoutRegion("options.card") end
        UnregisterFeaturesInnerDev()
        return
    end

    local card = EnsureCard(frame)
    HideLegacyTitleFontUi(card)

    local cardX = Offset("options.card")
    local cardWidth = Panel.GetPreferredWidth(frame)
    local panelX = 770 + cardX
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelX then
        panelX = ns.StatVerdictDashboardLayout.GetRightPanelX(frame)
    end

    card.preferredWidth = cardWidth
    local extra = 0
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelExtraGap then
        extra = ns.StatVerdictDashboardLayout.GetRightPanelExtraGap()
    end
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad("options.card")
        or { top = 0, bottom = 0, left = 0, right = 0 }
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard and frame.statProgressCard then
        ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, extra, 0, cardPad)
    elseif ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorOuterCard then
        ns.StatVerdictDashboardLayout.AnchorOuterCard(card, frame, panelX, cardPad)
    else
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", panelX, -34)
        card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", panelX, 14)
    end
    card:SetWidth(math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0)))
    card:Show()
    -- Whole card is the AdvDev target: Move X (shared dock) + Size W + Padding.
    if ns.ApplyRightDrawerCardDev then
        ns.ApplyRightDrawerCardDev(card, "options.card", "Features drawer", "options.width", DRAWER_PREFERRED_WIDTH)
    end

    -- Outer pad owns Size W — retire the legacy right-edge width strip.
    if frame.devOptionsWidthRegion then
        frame.devOptionsWidthRegion:Hide()
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("options.width")
    end

    PlaceFeaturesTitle(card, card.title, "options.title", "Features title", 12, -12)
    PlaceFeaturesTitle(card, card.bagMarkersTitle, "options.bagMarkersTitle", "Bag Markers title", 12, -40)

    -- Hint about quest / Adventure Guide removed — bags-only is already the behavior.
    if card.hint then
        card.hint:Hide()
        card.hint:SetText("")
    end

    local block = EnsureBagChecksBlock(card)
    local count = #BAG_INDICATOR_OPTIONS
    local blockBaseW = math.max(160, math.min(220, cardWidth - 24))
    local blockBaseH = math.max(BAG_CHECK_STEP, count * BAG_CHECK_STEP)
    -- Migrate older per-checkbox XY into the group once, if the group was never nudged.
    do
        local bx, by = Offset("options.bagChecks")
        if (not bx or bx == 0) and (not by or by == 0) and ns.GetDevLayoutOffset and ns.WriteDevLayoutOffset then
            local legacyX, legacyY = ns.GetDevLayoutOffset("options.showUpgradeArrow")
            if (not legacyX or legacyX == 0) and (not legacyY or legacyY == 0) then
                legacyX, legacyY = ns.GetDevLayoutOffset("options.showBagIndicators")
            end
            if (legacyX and legacyX ~= 0) or (legacyY and legacyY ~= 0) then
                ns.WriteDevLayoutOffset("options.bagChecks", legacyX or 0, legacyY or 0)
            end
        end
    end
    PlaceBagChecksBlock(card, block, "options.bagChecks", "Bag marker checkboxes", 12, -70, blockBaseW, blockBaseH)

    -- Per-checkbox AdvDev keys retired — the group owns Move / Size / Padding.
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("options.showBagIndicators")
        for _, option in ipairs(BAG_INDICATOR_OPTIONS) do
            ns.UnregisterDevLayoutRegion("options." .. option.key)
        end
    end

    for index, option in ipairs(BAG_INDICATOR_OPTIONS) do
        local check = EnsureOptionCheckbox(card, option, block)
        check:ClearAllPoints()
        check:SetPoint("TOPLEFT", block, "TOPLEFT", 0, -((index - 1) * BAG_CHECK_STEP))
        check:SetFrameLevel((block:GetFrameLevel() or 1) + 6)
        check:Show()
        check:SetScript("OnClick", function(self)
            _G.StatVerdictDB = _G.StatVerdictDB or {}
            _G.StatVerdictDB[option.key] = self:GetChecked() and true or false
            SyncBagIndicatorOptionChecks(card)
            RefreshBagIndicatorsSoon()
        end)
    end
    SyncBagIndicatorOptionChecks(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end

function ns.IsOptionsDrawerOpen()
    return Panel.IsOpen()
end

function ns.SetOptionsDrawerOpen(open)
    Panel.SetOpen(open)
end

function ns.ToggleOptionsDrawer()
    Panel.Toggle()
end
