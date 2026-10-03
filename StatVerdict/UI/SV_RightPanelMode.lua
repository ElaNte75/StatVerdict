local addonName, ns = ...

-- Single source of truth for the right-side drawer.
-- Modes: "bis" | "trinkets" | "weights" | "options" | "manual" | nil (all closed).
-- Exactly one may be open at a time.

local VALID = {
    bis = true,
    trinkets = true,
    weights = true,
    options = true,
    manual = true,
}

function ns.GetRightPanelMode()
    local db = _G.StatVerdictDB
    if type(db) ~= "table" then
        return nil
    end
    if db.showManualPanel == true then
        return "manual"
    end
    if db.showOptionsPanel == true then
        return "options"
    end
    if db.showWeightsPanel == true then
        return "weights"
    end
    if db.showTrinketPanel == true then
        return "trinkets"
    end
    -- Explicit open only — first launch keeps all right panels closed.
    if db.showBisPanel == true then
        return "bis"
    end
    return nil
end

function ns.SetRightPanelMode(mode)
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    local db = _G.StatVerdictDB
    if not VALID[mode] then
        mode = nil
    end
    db.showBisPanel = (mode == "bis")
    db.showTrinketPanel = (mode == "trinkets")
    db.showWeightsPanel = (mode == "weights")
    db.showOptionsPanel = (mode == "options")
    db.showManualPanel = (mode == "manual")
    if ns.RequestStatAuditRefresh then
        ns.RequestStatAuditRefresh()
    end
end

function ns.ToggleRightPanelMode(mode)
    if ns.GetRightPanelMode() == mode then
        ns.SetRightPanelMode(nil)
    else
        ns.SetRightPanelMode(mode)
    end
end

local TAB_YELLOW = { 1.0, 0.82, 0.0 }
local TAB_WHITE = { 0.92, 0.82, 0.20 }
local LABEL_FONT_SIZE = 11
local DEFAULT_TOGGLE_HEIGHT = 24
local CHIP_MIN_WIDTH = 140
local CHIP_MIN_HEIGHT = 18
local CHIP_MAX_HEIGHT = 48
local CHIP_SIDE_MARGIN = 12   -- the gap between a title chip and the card's left and right edge
local CHIP_TOP = -12          -- from the card's top edge

-- Unified title chip labels (qualifier first — natural English).
-- Click cycles Main Spec ↔ Off Spec; the text inside the same button updates.
local PANEL_TITLES = {
    bis = {
        base = "Best in Slot",
        MAIN = "Main Spec Best in Slot",
        OFF = "Off Spec Best in Slot",
    },
    trinkets = {
        base = "Ranked Trinkets",
        MAIN = "Main Spec Ranked Trinkets",
        OFF = "Off Spec Ranked Trinkets",
    },
}

local function IsOffSpecConfigured()
    local selection = ns.GetSavedStatAuditSelection and ns.GetSavedStatAuditSelection() or nil
    return selection
        and selection.secondaryEnabled == true
        and type(selection.secondarySpecID) == "number"
        and selection.secondarySpecID > 0
end

local function ResolveActiveView()
    local view = ns.GetStatAuditActiveView and ns.GetStatAuditActiveView() or "MAIN"
    if view == "OFF" and not IsOffSpecConfigured() then
        view = "MAIN"
    end
    return view
end

-- The Best in Slot panel wording comes from ns.GetReferenceWording.
local function PanelTitles(panelKind)
    if panelKind == "bis" and ns.GetReferenceWording then
        local wording = ns.GetReferenceWording()
        return { base = wording.base, MAIN = wording.main, OFF = wording.off }
    end
    return PANEL_TITLES[panelKind]
end

local function ResolvePanelKind(panelKind)
    if PANEL_TITLES[panelKind] then
        return panelKind
    end
    return "bis"
end

-- Each panel keeps its own AdvDev keys: bis.* / trinkets.*
local function LayoutKeyForPanel(panelKind)
    return ResolvePanelKind(panelKind)
end

local function TitleForPanel(panelKind, view, _osReady)
    local titles = PanelTitles(ResolvePanelKind(panelKind))
    -- Always "Main Spec …" / "Off Spec …" — never the bare panel name.
    if view == "OFF" then
        return titles.OFF
    end
    return titles.MAIN
end

local function HideLegacyPanelTitle(parent)
    if not parent then return end
    if parent.title and parent.title.Hide then
        parent.title:Hide()
        if parent.title.SetText then
            parent.title:SetText("")
        end
    end
    if parent.titleRegion and parent.titleRegion.Hide then
        parent.titleRegion:Hide()
    end
    if parent.titleHit and parent.titleHit.Hide then
        parent.titleHit:Hide()
    end
end

local function PaintSpecToggleButton(button, state)
    if not button then return end
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

local function FirstNonZeroOffset(...)
    for i = 1, select("#", ...) do
        local key = select(i, ...)
        if key and ns.GetLayoutOffset then
            local x, y = ns.GetLayoutOffset(key)
            if (x and x ~= 0) or (y and y ~= 0) then
                return x or 0, y or 0
            end
        end
    end
    return 0, 0
end

local function HeightDeltaForKey(key)
    if not key then return 0 end
    if ns.GetLayoutHeightDelta then
        return ns.GetLayoutHeightDelta(key) or 0
    end
    local db = _G.StatVerdictDB and _G.StatVerdictDB.devDashboardOffsets
    local value = db and db[key]
    if type(value) == "table" then
        return tonumber(value.height) or 0
    end
    return 0
end

local function FirstNonZeroHeightDelta(...)
    for i = 1, select("#", ...) do
        local d = HeightDeltaForKey(select(i, ...))
        if d ~= 0 then return d end
    end
    return 0
end

-- Every tab's title is one chip as wide as its card, CHIP_SIDE_MARGIN from each edge, text centred.
-- Height of the chip (the width comes from the two anchors).
local function ApplyChipHeight(button, layoutPrefix)
    local height = DEFAULT_TOGGLE_HEIGHT
    if layoutPrefix == "bis" or layoutPrefix == "trinkets" then
        height = height + FirstNonZeroHeightDelta(
            layoutPrefix .. ".title.height",
            "bisTrinkets.title.height"
        )
    end
    if height < CHIP_MIN_HEIGHT then height = CHIP_MIN_HEIGHT end
    if height > CHIP_MAX_HEIGHT then height = CHIP_MAX_HEIGHT end
    button:SetHeight(height)
end

-- The look every title chip shares: shadow, dark rounded backdrop, centred gold label.
local function StyleTitleChip(chip, labelText)
    chip.shadow = chip:CreateTexture(nil, "BACKGROUND")
    chip.shadow:SetPoint("TOPLEFT", 2, -2)
    chip.shadow:SetPoint("BOTTOMRIGHT", 3, -3)
    chip.shadow:SetColorTexture(0, 0, 0, 0.45)

    chip:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = false,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    PaintSpecToggleButton(chip, "normal")

    chip.label = chip:CreateFontString(nil, "OVERLAY")
    chip.label:SetPoint("CENTER", chip, "CENTER", 0, 0)
    chip.label:SetJustifyH("CENTER")
    chip.label:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", LABEL_FONT_SIZE, "")
    chip.label:SetTextColor(TAB_YELLOW[1], TAB_YELLOW[2], TAB_YELLOW[3])
    chip.label:SetText(labelText or "")
end

-- Places a chip across the top of its card.
local function PlaceChipAcrossCard(chip, card, yOffset)
    chip:ClearAllPoints()
    chip:SetPoint("TOPLEFT", card, "TOPLEFT", CHIP_SIDE_MARGIN, CHIP_TOP + (yOffset or 0))
    chip:SetPoint("TOPRIGHT", card, "TOPRIGHT", -CHIP_SIDE_MARGIN, CHIP_TOP + (yOffset or 0))
end

-- The title chip of a tab without a Main / Off Spec switch (Guide, Features, Manual): the same chip as Best in
-- Slot and Ranked Trinkets, but not a button. Returns the chip; chip.label is the title text.
function ns.PlaceTabTitleChip(card, text)
    if not card then return nil end
    local chip = card.svTabTitleChip
    if not chip then
        chip = CreateFrame("Frame", nil, card, "BackdropTemplate")
        chip:EnableMouse(false)
        StyleTitleChip(chip, text)
        card.svTabTitleChip = chip
    end
    chip.label:SetText(text or "")
    PlaceChipAcrossCard(chip, card, 0)
    chip:SetHeight(DEFAULT_TOGGLE_HEIGHT)
    chip:SetFrameLevel((card:GetFrameLevel() or 1) + 6)
    chip:Show()
    return chip
end

-- Unified title chip of Best in Slot and Ranked Trinkets: also the Main Spec / Off Spec switch.
function ns.EnsureMsOsViewTabs(parent)
    if not parent then return nil end

    local button = parent.svViewToggle
    if button and button.svDrawerStyle ~= 3 then
        button:Hide()
        button:SetParent(nil)
        parent.svViewToggle = nil
        button = nil
    end

    if not button then
        button = CreateFrame("Button", nil, parent, "BackdropTemplate")
        button.svDrawerStyle = 3
        button:SetSize(CHIP_MIN_WIDTH, DEFAULT_TOGGLE_HEIGHT)
        StyleTitleChip(button, "Main Spec Best in Slot")
        parent.svViewToggle = button
    end

    return parent.svViewToggle
end

function ns.SyncMsOsViewTabs(parent)
    if not parent then return end
    local toggle = ns.EnsureMsOsViewTabs(parent)
    local panelKind = ResolvePanelKind(toggle.svPanelKind or parent.svTitlePanelKind or "bis")
    local view = ResolveActiveView()
    local osReady = IsOffSpecConfigured()

    if view == "OFF" and not osReady and ns.SetStatAuditActiveView then
        ns.SetStatAuditActiveView("MAIN")
        view = "MAIN"
    end

    toggle.svPanelKind = panelKind
    parent.svTitlePanelKind = panelKind
    toggle.label:SetText(TitleForPanel(panelKind, view, osReady))
    toggle:Enable()
    toggle:SetAlpha(1)
    toggle:Show()
    PaintSpecToggleButton(toggle, "normal")

    if osReady then
        toggle.label:SetTextColor(TAB_YELLOW[1], TAB_YELLOW[2], TAB_YELLOW[3])
        toggle:SetScript("OnClick", function()
            local current = ResolveActiveView()
            if ns.SetStatAuditActiveView then
                ns.SetStatAuditActiveView(current == "OFF" and "MAIN" or "OFF")
            end
        end)
        toggle:SetScript("OnEnter", function(self)
            PaintSpecToggleButton(self, "hover")
            if GameTooltip then
                GameTooltip:SetOwner(self, "ANCHOR_TOP")
                GameTooltip:SetText("Spec view", TAB_YELLOW[1], TAB_YELLOW[2], TAB_YELLOW[3])
                GameTooltip:AddLine("Click to switch Main Spec / Off Spec for Best in Slot and Ranked Trinkets.", 0.85, 0.85, 0.85, true)
                GameTooltip:Show()
            end
        end)
        toggle:SetScript("OnLeave", function(self)
            PaintSpecToggleButton(self, "normal")
            if GameTooltip then GameTooltip:Hide() end
        end)
        toggle:SetScript("OnMouseDown", function(self)
            PaintSpecToggleButton(self, "pushed")
        end)
        toggle:SetScript("OnMouseUp", function(self)
            if self:IsMouseOver() then
                PaintSpecToggleButton(self, "hover")
            else
                PaintSpecToggleButton(self, "normal")
            end
        end)
    else
        -- No Off Spec configured — show base panel title, non-interactive.
        toggle.label:SetTextColor(TAB_WHITE[1], TAB_WHITE[2], TAB_WHITE[3])
        toggle:SetScript("OnClick", nil)
        toggle:SetScript("OnEnter", function(self)
            PaintSpecToggleButton(self, "normal")
        end)
        toggle:SetScript("OnLeave", function(self)
            PaintSpecToggleButton(self, "normal")
            if GameTooltip then GameTooltip:Hide() end
        end)
        toggle:SetScript("OnMouseDown", nil)
        toggle:SetScript("OnMouseUp", nil)
    end
end

-- Place the unified title chip at the panel title position (replaces FontString title).
-- panelKind: "bis" | "trinkets" — each has independent AdvDev settings.
function ns.PlaceMsOsTitleChip(parent, _layoutPrefixIgnored, panelKind)
    if not parent then return end
    panelKind = ResolvePanelKind(panelKind or _layoutPrefixIgnored)
    local layoutPrefix = LayoutKeyForPanel(panelKind)

    HideLegacyPanelTitle(parent)

    local toggle = ns.EnsureMsOsViewTabs(parent)
    toggle.svPanelKind = panelKind
    parent.svTitlePanelKind = panelKind
    parent.svTitleLayoutPrefix = layoutPrefix

    local _, y = FirstNonZeroOffset(
        layoutPrefix .. ".title",
        layoutPrefix .. ".viewToggle",
        layoutPrefix .. ".msTab",
        -- One-time migration from the old shared BiS/Trinkets key.
        (layoutPrefix == "bis" or layoutPrefix == "trinkets") and "bisTrinkets.title" or nil,
        (layoutPrefix == "bis" or layoutPrefix == "trinkets") and "bisTrinkets.viewToggle" or nil
    )

    ns.SyncMsOsViewTabs(parent)
    ApplyChipHeight(toggle, layoutPrefix)
    PlaceChipAcrossCard(toggle, parent, y)
    toggle:SetFrameLevel((parent:GetFrameLevel() or 1) + 8)
end

-- Compat: older call sites passed (parent, anchor, gap, prefix).
function ns.PlaceMsOsViewTabs(parent, _anchorFrame, _gap, layoutPrefix)
    ns.PlaceMsOsTitleChip(parent, layoutPrefix, layoutPrefix)
end

function ns.HideMsOsViewTabs(parent)
    if not parent then return end
    if parent.svViewToggle then parent.svViewToggle:Hide() end
    if parent.svViewToggleHint then parent.svViewToggleHint:Hide() end
end

-- Visual inset padding of a right-side drawer card (does not change its
-- logical footprint or the shared dock position).
function ns.GetRightDrawerCardPad(key)
    if ns.GetLayoutPadding then
        return ns.GetLayoutPadding(key .. ".pad")
    end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

-- Shared AdvDev wiring for a right-side drawer card: same model as Panel 1/2.
-- Whole card is selectable (alwaysCapture), white outline in AdvDev, outer pad
-- for Move X + Size W + Padding.
function ns.ApplyRightDrawerCard(card, key, label, widthKey, baseW)
    if not card then return end
    if card.SetBackdrop then
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
    end
    -- Drawer chrome border is always visible (not AdvDev-only).
    if ns.SetBorderColor then
        ns.SetBorderColor(card, 0.72, 0.74, 0.78, 0.86)
    elseif card.SetBackdropBorderColor then
        card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
    end
    -- The whole-card region replaces the legacy shared "right.card" strip.
end
