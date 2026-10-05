local addonName, ns = ...

local Panel = {}
ns.StatVerdictSettingsPanel = Panel

-- Match dropdown label visual size (dropdowns are scaled 0.92 with font 10).
local DROPDOWN_LABEL_FONT_SIZE = 10
local DROPDOWN_SCALE = 0.92

local function Offset(key)
    if ns.GetLayoutOffset then return ns.GetLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetLayoutSizeDelta then return ns.GetLayoutSizeDelta(key) end
    return 0
end

local function HeightDelta(key)
    if ns.GetLayoutHeightDelta then return ns.GetLayoutHeightDelta(key) end
    return 0
end

local function Padding(key)
    if ns.GetLayoutPadding then return ns.GetLayoutPadding(key) end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end


-- TOPLEFT of child relative to TOPLEFT of parent (UI units).
-- Returns nil, nil if layout has not resolved yet (GetLeft/GetTop unavailable).
local function RelTopLeft(child, parent)
    if not (child and parent and child.GetLeft and parent.GetLeft and child.GetTop and parent.GetTop) then
        return nil, nil
    end
    local cl, ct = child:GetLeft(), child:GetTop()
    local pl, pt = parent:GetLeft(), parent:GetTop()
    if not (cl and ct and pl and pt) then return nil, nil end
    local cs = child:GetEffectiveScale() or 1
    local ps = parent:GetEffectiveScale() or 1
    if ps == 0 then ps = 1 end
    return (cl * cs - pl * ps) / ps, (ct * cs - pt * ps) / ps
end

-- Place a Panel 1 child: a child of Panel 1 (it moves with the panel), with its saved move / size / padding.
local function PlaceSetupChild(frame, card, region, spec)
    if not (frame and card and region and spec and spec.key) then return end
    local key = spec.key
    local defaultX = spec.defaultX or 0
    local defaultY = spec.defaultY or 0
    local baseW = spec.baseW or 100
    local baseH = spec.baseH or 26
    local pad = Padding(key .. ".pad")
    local dx, dy = Offset(key)

    -- An offset saved as absolute (older builds) is turned into one relative to the card, once.
    if ns.GetLayoutOffsetAbs and ns.GetLayoutOffsetAbs(key) and ns.WriteLayoutOffset then
        local cx, cy = RelTopLeft(card, frame)
        if cx ~= nil and cy ~= nil then
            ns.WriteLayoutOffset(key, (dx or 0) - cx - defaultX, (dy or 0) - cy - defaultY, { _abs = false })
            dx, dy = Offset(key)
        end
    end
    if region.GetParent and region:GetParent() ~= card then
        region:SetParent(card)
    end
    local w = baseW + SizeDelta(key .. ".width")
    local h = baseH + HeightDelta(key .. ".height")
    if w < (spec.minW or 20) then w = spec.minW or 20 end
    if h < (spec.minH or 10) then h = spec.minH or 10 end
    if spec.maxW and w > spec.maxW then w = spec.maxW end
    if spec.maxH and h > spec.maxH then h = spec.maxH end
    -- Padding is a visual inset: the logical footprint (w/h) stays intact.
    w = math.max(10, w - (pad.left or 0) - (pad.right or 0))
    h = math.max(10, h - (pad.top or 0) - (pad.bottom or 0))
    region:ClearAllPoints()
    region:SetPoint(
        "TOPLEFT",
        card,
        "TOPLEFT",
        defaultX + (dx or 0) + (pad.left or 0),
        defaultY + (dy or 0) - (pad.top or 0)
    )
    if region.SetSize then
        region:SetSize(w, h)
    else
        if region.SetWidth then region:SetWidth(w) end
        if region.SetHeight then region:SetHeight(h) end
    end

    region:SetFrameLevel((card:GetFrameLevel() or 1) + (spec.levelBoost or 6))
    region:Show()
end

local function EnsureTitleHost(card, storeKey, fontString, text)
    card._svTitleHosts = card._svTitleHosts or {}
    local host = card._svTitleHosts[storeKey]
    if not host then
        host = CreateFrame("Frame", nil, card)
        host:EnableMouse(false)
        card._svTitleHosts[storeKey] = host
    end
    if fontString then
        fontString:SetParent(host)
        fontString:ClearAllPoints()
        fontString:SetPoint("LEFT", host, "LEFT", 0, 0)
        if text then fontString:SetText(text) end
    end
    local tw = 80
    if fontString and fontString.GetStringWidth then
        tw = math.ceil((fontString:GetStringWidth() or 80) + 2)
    end
    if tw < 20 then tw = 20 end
    host:SetSize(tw, 16)
    return host, tw, 16
end

local function EnsureCard(frame)
    if frame.settingsCard then return frame.settingsCard end

    local card = CreateFrame("Frame", nil, frame, "BackdropTemplate")
    -- Above the window chrome fill so children (dropdowns/buttons) stay visible.
    card:SetFrameLevel(math.max(2, frame:GetFrameLevel() + 2))
    card:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 8,
        -- No L/R inset: adjacent frames must visually meet when stack gap = 0.
        insets = { left = 0, right = 0, top = 2, bottom = 2 },
    })
    card:SetBackdropColor(0.018, 0.022, 0.030, 0.96)
    card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)

    card.title = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.title:SetText("Main Spec Build")
    card.title:SetTextColor(1.0, 0.82, 0.0)

    card.offTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.offTitle:SetText("Off Spec Build")
    card.offTitle:SetTextColor(1.0, 0.82, 0.0)

    card.optionsTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.optionsTitle:SetText("Panels")
    card.optionsTitle:SetTextColor(1.0, 0.82, 0.0)

    -- Corner index so we can say "Frame 1" unambiguously.

    frame.settingsCard = card
    return card
end

local function HideLegacyBagMarkerControls(card)
    if not card then return end
    if card.bagMarkersTitle then card.bagMarkersTitle:Hide() end
    if card.bagMarkersHint then card.bagMarkersHint:Hide() end
    if card.bagIndicatorChecks then
        for _, check in pairs(card.bagIndicatorChecks) do
            if check and check.Hide then check:Hide() end
        end
    end
end

local GOLD = { 0.95, 0.78, 0.20 }
local WHITE = { 0.82, 0.82, 0.82 }

local function PaintDrawerToggleButton(button, state)
    if not button then return end
    -- Muted gray family closer to Blizzard dropdown chrome.
    if state == "pushed" then
        button:SetBackdropColor(0.06, 0.06, 0.07, 0.95)
        button:SetBackdropBorderColor(0.28, 0.28, 0.30, 0.95)
    elseif state == "hover" then
        button:SetBackdropColor(0.14, 0.14, 0.16, 0.95)
        button:SetBackdropBorderColor(0.48, 0.48, 0.50, 0.95)
    else
        button:SetBackdropColor(0.10, 0.10, 0.12, 0.92)
        button:SetBackdropBorderColor(0.38, 0.38, 0.40, 0.92)
    end
end

local function EnsureDrawerToggleButton(card, fieldName)
    local button = card[fieldName]
    if button and button.svDrawerStyle ~= 2 then
        button:Hide()
        button:SetParent(nil)
        card[fieldName] = nil
        button = nil
    end
    if not button then
        button = CreateFrame("Button", nil, card, "BackdropTemplate")
        button.svDrawerStyle = 2
        button:SetSize(170, 26)

        -- Soft drop shadow so the chip reads as a control, not flat text.
        button.shadow = button:CreateTexture(nil, "BACKGROUND")
        button.shadow:SetPoint("TOPLEFT", 2, -2)
        button.shadow:SetPoint("BOTTOMRIGHT", 3, -3)
        button.shadow:SetColorTexture(0, 0, 0, 0.45)

        button:SetBackdrop({
            bgFile = "Interface\\Buttons\\WHITE8X8",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = false,
            edgeSize = 12,
            insets = { left = 3, right = 3, top = 3, bottom = 3 },
        })
        PaintDrawerToggleButton(button, "normal")

        button.label = button:CreateFontString(nil, "OVERLAY")
        button.label:SetPoint("CENTER", button, "CENTER", 0, 0)
        button.label:SetJustifyH("CENTER")
        -- Same face/size as setup dropdown labels.
        local font = STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
        button.label:SetFont(font, DROPDOWN_LABEL_FONT_SIZE, "")
        button.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])

        button:SetScript("OnEnter", function(self)
            PaintDrawerToggleButton(self, "hover")
        end)
        button:SetScript("OnLeave", function(self)
            PaintDrawerToggleButton(self, "normal")
        end)
        button:SetScript("OnMouseDown", function(self)
            PaintDrawerToggleButton(self, "pushed")
        end)
        button:SetScript("OnMouseUp", function(self)
            if self:IsMouseOver() then
                PaintDrawerToggleButton(self, "hover")
            else
                PaintDrawerToggleButton(self, "normal")
            end
        end)
        card[fieldName] = button
    end
    return button
end

local PANEL_TOGGLE_BUTTONS = {
    {
        mode = "bis",
        field = "bisDrawerButton",
        label = "Best in Slot",
        layoutKey = "setup.bisButton",
        defaultY = -318,
    },
    {
        mode = "trinkets",
        field = "trinketsDrawerButton",
        label = "Ranked Trinkets",
        layoutKey = "setup.trinketsButton",
        defaultY = -346,
    },
    {
        mode = "weights",
        field = "weightsDrawerButton",
        label = "Guide",
        tooltip = "Whose guides the stat priorities, Best in Slot lists and stat targets are copied from, and the stat target tier.",
        -- Layout key kept from the Summary button (later Benchmark) this replaced,
        -- so saved button positions carry over.
        layoutKey = "setup.summaryButton",
        defaultY = -374,
    },
    {
        mode = "options",
        field = "optionsDrawerButton",
        label = "Options",
        layoutKey = "setup.optionsButton",
        defaultY = -410,  -- 8px further down than a plain step: Options and Manual are the addon's own, apart from the three guide buttons above
    },
    {
        mode = "manual",
        field = "manualDrawerButton",
        label = "Manual",
        layoutKey = "setup.manualButton",
        defaultY = -438,
    },
}

-- Label, colour and click of one panel button (Guide, Best in Slot, Ranked Trinkets, Options, Manual).
local function ConfigurePanelToggleButton(button, spec)
    local activeMode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    local active = activeMode == spec.mode
    local label = spec.label
    if spec.mode == "bis" and ns.GetReferenceWording then
        label = ns.GetReferenceWording().button
    end
    button.label:SetText(label)
    if active then
        button.label:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    else
        button.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
    end
    button:SetAlpha(1)
    button:SetScript("OnClick", function()
        if ns.ToggleRightPanelMode then
            ns.ToggleRightPanelMode(spec.mode)
        end
    end)
    button:SetScript("OnEnter", function(self)
        PaintDrawerToggleButton(self, "hover")
        if spec.tooltip and GameTooltip then
            GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
            GameTooltip:SetText(label, 1.0, 0.82, 0.0)
            GameTooltip:AddLine(spec.tooltip, 0.85, 0.85, 0.85, true)
            GameTooltip:Show()
        end
    end)
    button:SetScript("OnLeave", function(self)
        PaintDrawerToggleButton(self, "normal")
        if GameTooltip then GameTooltip:Hide() end
    end)
    button:SetScript("OnMouseDown", function(self)
        PaintDrawerToggleButton(self, "pushed")
    end)
    button:SetScript("OnMouseUp", function(self)
        if self:IsMouseOver() then
            PaintDrawerToggleButton(self, "hover")
        else
            PaintDrawerToggleButton(self, "normal")
        end
    end)
end

local function PositionPanelToggleButtons(frame, card)
    for _, spec in ipairs(PANEL_TOGGLE_BUTTONS) do
        local button = EnsureDrawerToggleButton(card, spec.field)
        ConfigurePanelToggleButton(button, spec)

        PlaceSetupChild(frame, card, button, {
            key = spec.layoutKey,
            label = spec.label,
            defaultX = 14,
            defaultY = spec.defaultY,
            baseW = 170,
            baseH = 26,
            minW = 80,
            maxW = 320,
            minH = 18,
            maxH = 48,
        })

        if frame.statVerdictSetupResizeRegions and frame.statVerdictSetupResizeRegions[spec.layoutKey .. ".width"] then
            frame.statVerdictSetupResizeRegions[spec.layoutKey .. ".width"]:Hide()
        end
    end
end

-- Compact Mode: the panel buttons that stay (Manual lives in Options), in one row under the table.
local COMPACT_BUTTON_MODES = { "weights", "bis", "trinkets", "options" }
local COMPACT_BUTTON_GAP = 6
local COMPACT_DROPDOWNS = {
    { key = "setup.buildDropdown", defaultY = -54 },
    { key = "setup.mainDropdown", defaultY = -104 },
    { key = "setup.offGoalDropdown", defaultY = -178 },
    { key = "setup.offDropdown", defaultY = -228 },
}
local COMPACT_TOGGLE_H = 24 -- the same height as the buttons of the row
local COMPACT_TOGGLE_GAP = 8
local COMPACT_BOTTOM_MARGIN = 10 -- between the view button and the card's bottom edge

-- How far down the card the lowest dropdown reaches (its bottom edge, from the card's top).
function Panel.GetCompactDropdownBottom()
    local bottom = 0
    for _, dropdown in ipairs(COMPACT_DROPDOWNS) do
        local _, dy = Offset(dropdown.key)
        local height = 26 + HeightDelta(dropdown.key .. ".height")
        bottom = math.max(bottom, -(dropdown.defaultY + (tonumber(dy) or 0)) + height)
    end
    return bottom
end

-- Height of the left card in Compact Mode: the dropdowns and the view button under them.
function Panel.GetCompactHeight()
    local pad = Padding("setup.pad")
    return (pad.top or 0) + Panel.GetCompactDropdownBottom() + COMPACT_TOGGLE_GAP + COMPACT_TOGGLE_H
        + COMPACT_BOTTOM_MARGIN + (pad.bottom or 0)
end

local function SpecForMode(mode)
    for _, spec in ipairs(PANEL_TOGGLE_BUTTONS) do
        if spec.mode == mode then return spec end
    end
    return nil
end

local function HideVerticalPanelControls(card)
    if card.optionsTitle then card.optionsTitle:Hide() end
    local host = card._svTitleHosts and card._svTitleHosts.optionsTitle
    if host then host:Hide() end
    for _, spec in ipairs(PANEL_TOGGLE_BUTTONS) do
        if card[spec.field] then card[spec.field]:Hide() end
    end
end

local function HideCompactControls(frame, card)
    for _, mode in ipairs(COMPACT_BUTTON_MODES) do
        local spec = SpecForMode(mode)
        local button = spec and frame["compact_" .. spec.field]
        if button then button:Hide() end
    end
    if card.compactViewButton then card.compactViewButton:Hide() end
end

local function PositionCompactButtons(frame)
    local layout = ns.StatVerdictDashboardLayout
    local left, top, width, height = layout.GetCompactButtonRow(frame)
    local count = #COMPACT_BUTTON_MODES
    local buttonWidth = math.floor((width - (count - 1) * COMPACT_BUTTON_GAP) / count)
    for index, mode in ipairs(COMPACT_BUTTON_MODES) do
        local spec = SpecForMode(mode)
        local button = EnsureDrawerToggleButton(frame, "compact_" .. spec.field)
        ConfigurePanelToggleButton(button, spec)
        button:ClearAllPoints()
        button:SetPoint("TOPLEFT", frame, "TOPLEFT", left + (index - 1) * (buttonWidth + COMPACT_BUTTON_GAP), top)
        button:SetSize(buttonWidth, height)
        button:SetFrameLevel((frame:GetFrameLevel() or 1) + 8)
        button:Show()
    end
end

-- Under the dropdowns: switches which table the compact window shows. Only while an Off Spec is set up.
local function PositionCompactViewButton(frame, card)
    local layout = ns.StatVerdictDashboardLayout
    local button = EnsureDrawerToggleButton(card, "compactViewButton")
    if not layout.OffSpecReady() then
        button:Hide()
        return
    end
    -- One line saying what a click does; the headings above the dropdowns show which spec is in view.
    local showingOff = layout.CompactView() == "OFF"
    button.label:SetText(showingOff and "Show Main Spec" or "Show Off Spec")
    button.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
    button:SetScript("OnClick", function()
        if ns.SetStatAuditActiveView then
            ns.SetStatAuditActiveView(layout.CompactView() == "OFF" and "MAIN" or "OFF")
        end
    end)
    button:SetScript("OnEnter", function(self)
        PaintDrawerToggleButton(self, "hover")
        if GameTooltip then
            GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
            GameTooltip:SetText("Spec view", 1.0, 0.82, 0.0)
            GameTooltip:AddLine("Switch the table between your Main Spec and your Off Spec. The heading of the spec in view is gold. Best in Slot and Ranked Trinkets follow it.", 0.85, 0.85, 0.85, true)
            GameTooltip:Show()
        end
    end)
    button:SetScript("OnLeave", function(self)
        PaintDrawerToggleButton(self, "normal")
        if GameTooltip then GameTooltip:Hide() end
    end)
    local cardWidth = 226 + SizeDelta("setup.width")
    -- On the same line as the row of panel buttons: the same top, the same height.
    local _, rowTop, _, rowHeight = layout.GetCompactButtonRow(frame)
    local cardLeft = layout.GetSetupCardLeft() + (Padding("setup.pad").left or 0)
    button:ClearAllPoints()
    button:SetPoint("TOPLEFT", frame, "TOPLEFT", cardLeft + 12, rowTop)
    button:SetSize(math.max(60, math.min(190, cardWidth - 24 - (Padding("setup.pad").left or 0))), rowHeight)
    button:SetFrameLevel((card:GetFrameLevel() or 1) + 6)
    button:Show()
end

-- The strip that stands for the folded-away left column: the mouse on it opens the column over the table.
local function PositionLeftStrip(frame, card)
    local layout = ns.StatVerdictDashboardLayout
    local strip = frame.svLeftStrip
    if not (layout and layout.IsLeftAutoHidden and layout.IsLeftAutoHidden()) then
        if strip then strip:Hide() end
        return
    end
    if not strip then
        strip = CreateFrame("Button", nil, frame, "BackdropTemplate")
        strip:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 8,
            insets = { left = 0, right = 0, top = 2, bottom = 2 },
        })
        strip:SetBackdropColor(0.018, 0.022, 0.030, 0.96)
        strip:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
        strip.label = strip:CreateFontString(nil, "OVERLAY")
        strip.label:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", 14, "")
        strip.label:SetPoint("CENTER", strip, "CENTER", 0, 0)
        strip.label:SetText(">>")
        strip.label:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
        strip:SetScript("OnEnter", function(self)
            layout.SetLeftOpen(frame, true)
            if GameTooltip then
                GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
                GameTooltip:SetText("Main Spec / Off Spec builds", 1.0, 0.82, 0.0)
                GameTooltip:AddLine("Shown while the mouse is here. Turn the folding off under Options.", 0.85, 0.85, 0.85, true)
                GameTooltip:Show()
            end
        end)
        strip:SetScript("OnLeave", function() if GameTooltip then GameTooltip:Hide() end end)
        -- The column folds away again shortly after the mouse leaves it (not while a dropdown menu is open).
        local away = 0
        strip:SetScript("OnUpdate", function(self, elapsed)
            if not frame.svLeftOpen then return end
            local over = self:IsMouseOver() or (frame.settingsCard and frame.settingsCard:IsMouseOver())
                or (ns.IsChipDropdownOpen and ns.IsChipDropdownOpen())
            if over then
                away = 0
            else
                away = away + (elapsed or 0)
                if away >= 0.35 then
                    away = 0
                    layout.SetLeftOpen(frame, false)
                end
            end
        end)
        frame.svLeftStrip = strip
    end
    local left, top, width, height = layout.GetLeftStripRect(frame)
    strip:ClearAllPoints()
    strip:SetPoint("TOPLEFT", frame, "TOPLEFT", left, top)
    strip:SetSize(width, height)
    strip:SetFrameLevel((frame:GetFrameLevel() or 1) + 8)
    strip:Show()
end

-- Compact Mode: the heading of the build in view is gold, the other white (they swap with the view). Otherwise both are gold.
local function PaintBuildHeadings(card)
    local layout = ns.StatVerdictDashboardLayout
    local view = layout and layout.CompactView and layout.CompactView() or nil
    local function paint(fontString, inView)
        if not fontString then return end
        if view == nil or inView then
            fontString:SetTextColor(1.0, 0.82, 0.0)
        else
            fontString:SetTextColor(1.0, 1.0, 1.0)
        end
    end
    paint(card.title, view ~= "OFF")
    paint(card.offTitle, view == "OFF")
end

function Panel.Apply(frame, controls)
    local card = EnsureCard(frame)
    -- Existing cards from older builds may still sit behind the window chrome.
    card:SetFrameLevel(math.max(2, frame:GetFrameLevel() + 2))
    if card.SetBackdrop then
        card:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 8,
            insets = { left = 0, right = 0, top = 2, bottom = 2 },
        })
        card:SetBackdropColor(0.018, 0.022, 0.030, 0.96)
        card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
    end
    local cardWidth = 226 + SizeDelta("setup.width")
    if cardWidth < 80 then cardWidth = 80 end
    if cardWidth > 700 then cardWidth = 700 end
    card:SetWidth(cardWidth)
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorSetupCard then
        ns.StatVerdictDashboardLayout.AnchorSetupCard(card, frame)
    elseif ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorOuterCard then
        local left = ns.StatVerdictDashboardLayout.GetSetupCardLeft and ns.StatVerdictDashboardLayout.GetSetupCardLeft() or 10
        ns.StatVerdictDashboardLayout.AnchorOuterCard(card, frame, left)
    else
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", 6, -33)
        card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 6, 6)
    end

    -- Whole card is the move target (Panel 1).
    -- Panel chrome border is always visible.
    if ns.SetBorderColor then
        ns.SetBorderColor(card, 0.72, 0.74, 0.78, 0.86)
    elseif card.SetBackdropBorderColor then
        card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
    end

    local goalLabel = frame.goalLabel
    local offGoalLabel = frame.offGoalLabel
    local primaryLabel = frame.primaryLabel
    local secondaryLabel = frame.secondaryLabel
    local goal = controls.goal
    local offGoal = controls.offGoal
    local primary = controls.primary
    local secondary = controls.secondary
    local visibility = controls.visibility

    if goalLabel then goalLabel:Hide() end
    if primaryLabel then primaryLabel:Hide() end
    if offGoalLabel then offGoalLabel:Hide() end
    if secondaryLabel then secondaryLabel:Hide() end

    if card.title then
        local host, tw, th = EnsureTitleHost(card, "mainTitle", card.title, "Main Spec Build")
        PlaceSetupChild(frame, card, host, {
            key = "setup.mainTitle",
            label = "Main Spec Build",
            defaultX = 12,
            defaultY = -12,
            baseW = tw,
            baseH = th,
            minW = 20,
            minH = 12,
            levelBoost = 5,
        })
    end

    if goal then
        if goal.SetScale then goal:SetScale(1) end
        PlaceSetupChild(frame, card, goal, {
            key = "setup.buildDropdown",
            label = "Build dropdown",
            defaultX = 12,
            defaultY = -54,
            baseW = 190,
            baseH = 26,
            minW = 60,
            maxW = 520,
            minH = 18,
            maxH = 48,
        })
    end

    if primary then
        if primary.SetScale then primary:SetScale(1) end
        PlaceSetupChild(frame, card, primary, {
            key = "setup.mainDropdown",
            label = "Main Spec dropdown",
            defaultX = 12,
            defaultY = -104,
            baseW = 190,
            baseH = 26,
            minW = 60,
            maxW = 520,
            minH = 18,
            maxH = 48,
        })
    end

    if card.offTitle then
        local host, tw, th = EnsureTitleHost(card, "offTitle", card.offTitle, "Off Spec Build")
        PlaceSetupChild(frame, card, host, {
            key = "setup.offTitle",
            label = "Off Spec Build",
            defaultX = 12,
            defaultY = -158,
            baseW = tw,
            baseH = th,
            minW = 20,
            minH = 12,
            levelBoost = 5,
        })
        card.offTitle:Show()
    end

    if offGoal then
        if offGoal.SetScale then offGoal:SetScale(1) end
        PlaceSetupChild(frame, card, offGoal, {
            key = "setup.offGoalDropdown",
            label = "Off-Spec Profile dropdown",
            defaultX = 12,
            defaultY = -178,
            baseW = 190,
            baseH = 26,
            minW = 60,
            maxW = 520,
            minH = 18,
            maxH = 48,
        })
    end

    if secondary then
        if secondary.SetScale then secondary:SetScale(1) end
        PlaceSetupChild(frame, card, secondary, {
            key = "setup.offDropdown",
            label = "Off Spec dropdown",
            defaultX = 12,
            defaultY = -228,
            baseW = 190,
            baseH = 26,
            minW = 60,
            maxW = 520,
            minH = 18,
            maxH = 48,
        })
    end

    local compact = ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.IsCompact and ns.StatVerdictDashboardLayout.IsCompact()
    if card.optionsTitle and not compact then
        card.optionsTitle:SetText("Panels")
        local host, tw, th = EnsureTitleHost(card, "optionsTitle", card.optionsTitle, "Panels")
        PlaceSetupChild(frame, card, host, {
            key = "setup.optionsTitle",
            label = "Panels",
            defaultX = 12,
            defaultY = -286,
            baseW = tw,
            baseH = th,
            minW = 20,
            minH = 12,
            levelBoost = 5,
        })
        card.optionsTitle:Show()
    end

    -- Visibility dropdown replaced by drawer toggle buttons below.
    if visibility then
        visibility:Hide()
    end

    PositionLeftStrip(frame, card)
    PaintBuildHeadings(card)
    HideLegacyBagMarkerControls(card)
    if compact then
        HideVerticalPanelControls(card)
        PositionCompactButtons(frame)
        PositionCompactViewButton(frame, card)
    else
        HideCompactControls(frame, card)
        PositionPanelToggleButtons(frame, card)
    end

    -- Main/Off view checkboxes retired: dual progress will be visible together later.
    if card.mainViewToggle then card.mainViewToggle:Hide() end
    if card.offViewToggle then card.offViewToggle:Hide() end
end
