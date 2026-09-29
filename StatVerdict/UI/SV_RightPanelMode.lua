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
local CHIP_PAD_X = 18
local CHIP_MIN_WIDTH = 140
local CHIP_MAX_WIDTH = 360
local CHIP_MIN_HEIGHT = 18
local CHIP_MAX_HEIGHT = 48

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

local function TitleKindsForLayout(layoutPrefix)
    return { ResolvePanelKind(layoutPrefix) }
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
        if key and ns.GetDevLayoutOffset then
            local x, y = ns.GetDevLayoutOffset(key)
            if (x and x ~= 0) or (y and y ~= 0) then
                return x or 0, y or 0
            end
        end
    end
    return 0, 0
end

local function FirstNonZeroWidthDelta(...)
    for i = 1, select("#", ...) do
        local key = select(i, ...)
        if key and ns.GetDevLayoutSizeDelta then
            local d = ns.GetDevLayoutSizeDelta(key) or 0
            if d ~= 0 then return d end
        end
    end
    return 0
end

local function HeightDeltaForKey(key)
    if not key then return 0 end
    if ns.GetDevLayoutHeightDelta then
        return ns.GetDevLayoutHeightDelta(key) or 0
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

-- Width fits the longest label in this chip family (not the current text),
-- so Main/Off Spec and BiS/Trinkets switches do not resize the button.
local function MeasureStableTitleWidth(button, layoutPrefix)
    local label = button and button.label
    if not label or not label.SetText or not label.GetStringWidth then
        return CHIP_MIN_WIDTH
    end
    local saved = label.GetText and label:GetText() or nil
    local maxW = 0
    for _, kind in ipairs(TitleKindsForLayout(layoutPrefix)) do
        local titles = PanelTitles(kind)
        if titles then
            for _, key in ipairs({ "MAIN", "OFF" }) do
                label:SetText(titles[key])
                local w = label:GetStringWidth() or 0
                if w > maxW then maxW = w end
            end
        end
    end
    if saved ~= nil then
        label:SetText(saved)
    end
    return math.floor(maxW + CHIP_PAD_X)
end

local function ApplyChipSize(button, layoutPrefix)
    local baseWidth = MeasureStableTitleWidth(button, layoutPrefix)
    local width = baseWidth
    if layoutPrefix == "bis" or layoutPrefix == "trinkets" then
        width = width + FirstNonZeroWidthDelta(
            layoutPrefix .. ".title.width",
            layoutPrefix .. ".viewToggle.width",
            "bisTrinkets.title.width",
            "bisTrinkets.viewToggle.width"
        )
    else
        width = width + FirstNonZeroWidthDelta(
            layoutPrefix .. ".title.width",
            layoutPrefix .. ".viewToggle.width"
        )
    end
    if width < CHIP_MIN_WIDTH then width = CHIP_MIN_WIDTH end
    if width > CHIP_MAX_WIDTH then width = CHIP_MAX_WIDTH end

    local height = DEFAULT_TOGGLE_HEIGHT
    if layoutPrefix == "bis" or layoutPrefix == "trinkets" then
        height = height + FirstNonZeroHeightDelta(
            layoutPrefix .. ".title.height",
            "bisTrinkets.title.height"
        )
    else
        height = height + FirstNonZeroHeightDelta(layoutPrefix .. ".title.height")
    end
    if height < CHIP_MIN_HEIGHT then height = CHIP_MIN_HEIGHT end
    if height > CHIP_MAX_HEIGHT then height = CHIP_MAX_HEIGHT end

    -- Padding = visual inset: Size W/H is the logical footprint.
    local pad = { top = 0, bottom = 0, left = 0, right = 0 }
    if ns.GetDevLayoutPadding then
        pad = ns.GetDevLayoutPadding(layoutPrefix .. ".title.pad")
    end
    local visW = math.max(20, width - (pad.left or 0) - (pad.right or 0))
    local visH = math.max(12, height - (pad.top or 0) - (pad.bottom or 0))

    button:SetSize(visW, visH)
    return width, height, baseWidth, DEFAULT_TOGGLE_HEIGHT
end

local function HideInactiveTitleHandles(parent, activePrefix)
    if not parent then return end
    local prefixes = { "bis", "trinkets", "bisTrinkets" }
    if parent._svDevWidthHandles then
        for key, handle in pairs(parent._svDevWidthHandles) do
            if type(key) == "string" and handle and handle.Hide then
                local keep = false
                for _, prefix in ipairs(prefixes) do
                    if prefix == activePrefix and key == (prefix .. ".title.width") then
                        keep = true
                        break
                    end
                end
                if string.find(key, "title.width", 1, true) and not keep then
                    handle:Hide()
                end
            end
        end
    end
    if parent._svDevHeightHandles then
        for key, handle in pairs(parent._svDevHeightHandles) do
            if type(key) == "string" and handle and handle.Hide then
                local keep = key == (activePrefix .. ".title.height")
                if string.find(key, "title.height", 1, true) and not keep then
                    handle:Hide()
                end
            end
        end
    end
end

-- Unified title chip (replaces gold FontString + separate Main/Off Spec toggle).
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
        PaintSpecToggleButton(button, "normal")

        button.label = button:CreateFontString(nil, "OVERLAY")
        button.label:SetPoint("CENTER", button, "CENTER", 0, 0)
        button.label:SetJustifyH("CENTER")
        local font = STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
        button.label:SetFont(font, LABEL_FONT_SIZE, "")
        button.label:SetTextColor(TAB_YELLOW[1], TAB_YELLOW[2], TAB_YELLOW[3])
        button.label:SetText("Main Spec Best in Slot")

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

    local x, y = FirstNonZeroOffset(
        layoutPrefix .. ".title",
        layoutPrefix .. ".viewToggle",
        layoutPrefix .. ".msTab",
        -- One-time migration from the old shared BiS/Trinkets key.
        (layoutPrefix == "bis" or layoutPrefix == "trinkets") and "bisTrinkets.title" or nil,
        (layoutPrefix == "bis" or layoutPrefix == "trinkets") and "bisTrinkets.viewToggle" or nil
    )

    ns.SyncMsOsViewTabs(parent)
    local _, _, chipBaseW, chipBaseH = ApplyChipSize(toggle, layoutPrefix)

    local chipPad = { top = 0, bottom = 0, left = 0, right = 0 }
    if ns.GetDevLayoutPadding then
        chipPad = ns.GetDevLayoutPadding(layoutPrefix .. ".title.pad")
    end
    toggle:ClearAllPoints()
    toggle:SetPoint(
        "TOPLEFT",
        parent,
        "TOPLEFT",
        12 + x + (chipPad.left or 0),
        -12 + y - (chipPad.top or 0)
    )
    toggle:SetFrameLevel((parent:GetFrameLevel() or 1) + 8)

    HideInactiveTitleHandles(parent, layoutPrefix)

    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion(layoutPrefix .. ".msTab")
        ns.UnregisterDevLayoutRegion(layoutPrefix .. ".osTab")
        ns.UnregisterDevLayoutRegion(layoutPrefix .. ".viewToggle")
        ns.UnregisterDevLayoutRegion(layoutPrefix .. ".viewToggle.width")
        -- Drop shared key so it cannot steal hits from per-panel keys.
        ns.UnregisterDevLayoutRegion("bisTrinkets.title")
        ns.UnregisterDevLayoutRegion("bisTrinkets.title.width")
        ns.UnregisterDevLayoutRegion("bisTrinkets.title.height")
        -- On the shared BiS card, only the active mode's title is registered.
        if layoutPrefix == "bis" then
            ns.UnregisterDevLayoutRegion("trinkets.title")
            ns.UnregisterDevLayoutRegion("trinkets.title.width")
            ns.UnregisterDevLayoutRegion("trinkets.title.height")
        elseif layoutPrefix == "trinkets" then
            ns.UnregisterDevLayoutRegion("bis.title")
            ns.UnregisterDevLayoutRegion("bis.title.width")
            ns.UnregisterDevLayoutRegion("bis.title.height")
        end
    end
    local label = "Panel title"
    if layoutPrefix == "bis" then
        label = "Best in Slot title (Main/Off Spec)"
    elseif layoutPrefix == "trinkets" then
        label = "Ranked Trinkets title (Main/Off Spec)"
    end
    if ns.RegisterDevLayoutRegion then
        ns.RegisterDevLayoutRegion(layoutPrefix .. ".title", label, toggle, {
            axis = "xy",
            padding = 0,
            group = "controls",
            protect = true,
            exactHit = true,
            alwaysCapture = true,
        })
    end

    -- Outer pad (Move / Size / Padding) replaces the legacy width/height nubs.
    if ns.RegisterDevLayoutOuterSpec then
        ns.RegisterDevLayoutOuterSpec(layoutPrefix .. ".title", {
            label = label,
            moveKey = layoutPrefix .. ".title",
            widthKey = layoutPrefix .. ".title.width",
            heightKey = layoutPrefix .. ".title.height",
            padKey = layoutPrefix .. ".title.pad",
            baseW = chipBaseW,
            baseH = chipBaseH,
            sharedFrameHeight = false,
            lockKey = layoutPrefix .. ".title.locked",
        })
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion(layoutPrefix .. ".title.width")
        ns.UnregisterDevLayoutRegion(layoutPrefix .. ".title.height")
    end
    HideInactiveTitleHandles(parent, "__none__")
end

-- Compat: older call sites passed (parent, anchor, gap, prefix).
function ns.PlaceMsOsViewTabs(parent, _anchorFrame, _gap, layoutPrefix)
    ns.PlaceMsOsTitleChip(parent, layoutPrefix, layoutPrefix)
end

function ns.HideMsOsViewTabs(parent)
    if not parent then return end
    if parent.svViewToggle then parent.svViewToggle:Hide() end
    if parent.svViewToggleHint then parent.svViewToggleHint:Hide() end
    if parent._svDevWidthHandles then
        for key, handle in pairs(parent._svDevWidthHandles) do
            if type(key) == "string"
                and (string.find(key, "viewToggle.width", 1, true) or string.find(key, "title.width", 1, true))
                and handle and handle.Hide then
                handle:Hide()
            end
        end
    end
    if parent._svDevHeightHandles then
        for key, handle in pairs(parent._svDevHeightHandles) do
            if type(key) == "string"
                and string.find(key, "title.height", 1, true)
                and handle and handle.Hide then
                handle:Hide()
            end
        end
    end
end

-- Visual inset padding of a right-side drawer card (does not change its
-- logical footprint or the shared dock position).
function ns.GetRightDrawerCardPad(key)
    if ns.GetDevLayoutPadding then
        return ns.GetDevLayoutPadding(key .. ".pad")
    end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

-- Shared AdvDev wiring for a right-side drawer card: same model as Panel 1/2.
-- Whole card is selectable (alwaysCapture), white outline in AdvDev, outer pad
-- for Move X + Size W + Padding.
function ns.ApplyRightDrawerCardDev(card, key, label, widthKey, baseW)
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
    if ns.UnregisterDevLayoutBorderEditOnly then
        ns.UnregisterDevLayoutBorderEditOnly(card, 0.72, 0.74, 0.78, 0.86)
    elseif card.SetBackdropBorderColor then
        card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
    end
    if ns.RegisterDevLayoutOuterSpec then
        ns.RegisterDevLayoutOuterSpec(key, {
            label = label,
            moveKey = "right.card",
            moveAxis = "x",
            widthKey = widthKey,
            padKey = key .. ".pad",
            baseW = baseW,
            sharedFrameHeight = false,
            lockKey = key .. ".locked",
        })
    end
    if ns.RegisterDevLayoutRegion then
        ns.RegisterDevLayoutRegion(key, label, card, {
            axis = "x",
            padding = 0,
            group = "panels",
            protect = true,
            exactHit = true,
            alwaysCapture = true,
            nudgeKey = "right.card",
        })
    end
    -- The whole-card region replaces the legacy shared "right.card" strip.
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("right.card")
    end
end
