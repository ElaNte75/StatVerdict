local addonName, ns = ...

local Layout = {}
ns.StatVerdictDashboardLayout = Layout

local GRID_X = 252
local GRID_TOP_Y = -112
local GRID_WIDTH = 500
local ROW_HEIGHT = 24
local BASE_FRAME_WIDTH = 1120
local MIN_FRAME_WIDTH = 360
local MAX_FRAME_WIDTH = 2600
local TABLE_HEADER_BAND = 34
local TABLE_CARD_TOP_NUDGE = 8
local OFF_TABLE_GAP = 12
local OFF_TITLE_BAND = 20
local FRAME_HEIGHT = 440
local PANEL_GUTTER_DEFAULT = 10
local PANEL_GUTTER_MIN = 4
local PANEL_GUTTER_MAX = 48
-- Legacy name kept as default; live value comes from GetPanelGutter().
local PANEL_GUTTER = PANEL_GUTTER_DEFAULT
local WELL_PAD = 6 -- must match SV_WindowChrome PAD
local TITLE_BAR_H = 30 -- must match SV_WindowChrome TITLE_BAR_H
local CHROME_EDGE = 1
local WELL_TOP = TITLE_BAR_H + CHROME_EDGE + 2 -- 33
local SETUP_CARD_BASE_WIDTH = 226
local STATS_CARD_INSET = 6 -- table origin inset inside Stat Progress card
local STATS_CARD_BASE_WIDTH = 516
local TABLE_TOP_FROM_CARD = -70 -- main title band inside Stat Progress card
-- Dual screens fit inside the outer card; row capacity follows screen height (not live data).
local FIXED_SLOT_ROWS = 5
local SCREEN_INSET_X = 6
local SCREEN_CONTENT_X = 6 -- content was historically at gridX while card sat at gridX-6
local SCREEN_BOTTOM_RESERVE = 28 -- Average Progress line under Main screen

local function Offset(key)
    if ns.GetLayoutOffset then return ns.GetLayoutOffset(key) end
    return 0, 0
end


local function SizeDelta(key)
    if ns.GetLayoutSizeDelta then return ns.GetLayoutSizeDelta(key) end
    return 0
end

local function Clamp(value, minValue, maxValue)
    value = tonumber(value) or 0
    if value < minValue then return minValue end
    if value > maxValue then return maxValue end
    return value
end

-- Compact Mode (Options > Window): one stat table at a time, the panel buttons in one row under it.
local COMPACT_ROW_GAP = 8
local COMPACT_BUTTON_ROW_H = 24
local COMPACT_ROW_INSET = 8 -- the button row stops this far from the card's edges
local COMPACT_STATS_BOTTOM_MARGIN = 10
local COMPACT_SETUP_FALLBACK_H = 242

function Layout.IsCompact()
    local db = _G.StatVerdictDB
    return type(db) == "table" and db.compactMode == true
end

-- True while an Off Spec is set up (a spec chosen): only then is there a second table to switch to.
function Layout.OffSpecReady()
    local selection = ns.GetSavedStatAuditSelection and ns.GetSavedStatAuditSelection() or nil
    return type(selection) == "table" and selection.secondaryEnabled == true
        and type(selection.secondarySpecID) == "number" and selection.secondarySpecID > 0
end

-- The table the compact window shows: "OFF" only while an Off Spec is set up and selected, else "MAIN"; nil when not compact.
function Layout.CompactView()
    if not Layout.IsCompact() then return nil end
    if Layout.OffSpecReady() and ns.GetStatAuditActiveView and ns.GetStatAuditActiveView() == "OFF" then
        return "OFF"
    end
    return "MAIN"
end

local function ColumnWidth(column)
    local base = tonumber(column and column.width) or 1
    if base <= 1 then return base end
    local key = column and column.key
    if not key then return base end
    local minW = math.min(12, base)
    return Clamp(base + SizeDelta("stats.column." .. key .. ".width"), minW, 900)
end

local function StatTableHeight(rowCount)
    local rows = math.max(1, tonumber(rowCount) or FIXED_SLOT_ROWS)
    local height = TABLE_HEADER_BAND + (rows * ROW_HEIGHT)
    if ns.GetLayoutHeightDelta then
        height = height + (ns.GetLayoutHeightDelta("stats.table.height") or 0)
    end
    if height < 40 then height = 40 end
    return height
end

local function IsEditableStatColumn(column)
    if not column or not column.key then return false end
    if column.key == "current" or column.key == "target" then return false end
    return (tonumber(column.width) or 0) >= 10
end

local function RightPanelWidth(showBis, showTrinkets, frame)
    local key = showTrinkets and "trinkets.width" or "bis.width"
    local preferred = nil
    if ns.StatVerdictBisProgressPanel and ns.StatVerdictBisProgressPanel.GetPreferredWidth then
        preferred = ns.StatVerdictBisProgressPanel.GetPreferredWidth(frame)
    end
    if not preferred and frame and frame.bisProgressCard then
        preferred = tonumber(frame.bisProgressCard.preferredWidth)
    end
    local baseWidth = preferred or (showBis and 360 or 300)
    local delta = SizeDelta(key)
    -- Migrate once from the old shared key if this mode has no own delta yet.
    if delta == 0 then
        delta = SizeDelta("bisTrinkets.width")
    end
    return Clamp(baseWidth + delta, 220, 720)
end

function Layout.GetRightPanelWidth(frame)
    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    if mode == "options" then
        -- Single source of truth: base + SizeDelta (same as the other drawers). Do not re-add delta
        -- on top of a cached preferredWidth — that blocked shrink and double-counted grow.
        if ns.StatVerdictOptionsDrawerPanel and ns.StatVerdictOptionsDrawerPanel.GetPreferredWidth then
            return ns.StatVerdictOptionsDrawerPanel.GetPreferredWidth(frame)
        end
        return Clamp(320 + SizeDelta("options.width"), 200, 520)
    end
    if mode == "manual" then
        local preferred = nil
        if ns.StatVerdictManualDrawerPanel and ns.StatVerdictManualDrawerPanel.GetPreferredWidth then
            preferred = ns.StatVerdictManualDrawerPanel.GetPreferredWidth(frame)
        end
        if not preferred and frame and frame.manualDrawerCard then
            preferred = tonumber(frame.manualDrawerCard.preferredWidth)
        end
        local baseWidth = preferred or 300
        local delta = SizeDelta("manual.width")
        if preferred and delta < 0 then delta = 0 end
        -- The Manual can be made bigger (its own text size slider), so it is allowed to be wide.
        return Clamp(baseWidth + delta, 200, 1100)
    end
    if mode == "weights" then
        if ns.StatVerdictWeightsDrawerPanel and ns.StatVerdictWeightsDrawerPanel.GetPreferredWidth then
            return ns.StatVerdictWeightsDrawerPanel.GetPreferredWidth(frame)
        end
        return Clamp(300 + SizeDelta("weights.width"), 200, 520)
    end
    local showTrinkets = mode == "trinkets"
    local showBis = mode == "bis"
    return RightPanelWidth(showBis, showTrinkets, frame)
end

local function SharedRightDockX()
    local x = select(1, Offset("right.card"))
    if x ~= 0 then return x end
    -- Migrate legacy per-drawer X so switching panels keeps the dock the user already set.
    local best, bestAbs = 0, 0
    for _, key in ipairs({ "weights.card", "options.card", "manual.card", "bis.card" }) do
        local v = select(1, Offset(key))
        local a = math.abs(tonumber(v) or 0)
        if a > bestAbs then
            bestAbs = a
            best = tonumber(v) or 0
        end
    end
    if best ~= 0 then
        _G.StatVerdictDB = _G.StatVerdictDB or {}
        _G.StatVerdictDB.devDashboardOffsets = _G.StatVerdictDB.devDashboardOffsets or {}
        _G.StatVerdictDB.devDashboardOffsets["right.card"] = { x = best, y = 0 }
    end
    return best
end

function Layout.GetPanelGutter()
    local delta = SizeDelta("panel.gutter")
    local gutter = PANEL_GUTTER_DEFAULT + delta
    if gutter < PANEL_GUTTER_MIN then gutter = PANEL_GUTTER_MIN end
    if gutter > PANEL_GUTTER_MAX then gutter = PANEL_GUTTER_MAX end
    return gutter
end

-- Frame offsets so every outer card shares the same top / bottom band.
function Layout.GetPanelTopOffset()
    return -(WELL_TOP + Layout.GetPanelGutter())
end

function Layout.GetPanelBottomInset()
    return WELL_PAD + Layout.GetPanelGutter()
end

-- Layout zero = content-well chrome line (same inset as top/bottom), NOT the absolute
-- outer window edge. Outer chrome is WELL_PAD/WELL_TOP; panels/screens stack from there.
-- Panel 1 box: [origin+moveX, …+W1]. Panel 2 box starts at Panel1Right.
local STACK_ORIGIN_X = WELL_PAD

-- Left edge of Panel 1 outer box (Move X only).
function Layout.GetSetupCardLeft()
    local setupX = select(1, Offset("setup.card"))
    return STACK_ORIGIN_X + (tonumber(setupX) or 0)
end

-- The left card's own width.
function Layout.GetSetupCardRealWidth()
    return Clamp(SETUP_CARD_BASE_WIDTH + SizeDelta("setup.width"), 80, 700)
end

-- Compact Mode with "Auto-hide the left side": the left card folds away behind a thin strip, and the window only
-- makes room for the strip.
local LEFT_STRIP_WIDTH = 22

function Layout.IsLeftAutoHidden()
    local db = _G.StatVerdictDB
    return Layout.IsCompact() and type(db) == "table" and db.autoHideLeft == true
end

-- The room the left column takes in the window: its card, or only the strip.
function Layout.GetSetupCardWidth(frame)
    if Layout.IsLeftAutoHidden() then return LEFT_STRIP_WIDTH end
    return Layout.GetSetupCardRealWidth()
end

-- Right edge of Panel 1's logical span (Size W only). Panel 2 starts here.
-- Padding is a visual inset inside the footprint; it never moves neighbors.
function Layout.GetSetupCardRight(frame)
    return Layout.GetSetupCardLeft() + Layout.GetSetupCardWidth(frame)
end

function Layout.GetSetupCardPad()
    if ns.GetLayoutPadding then
        return ns.GetLayoutPadding("setup.pad")
    end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

local function NormalSetupCardHeight()
    local base = 360
    local delta = 0
    if ns.GetLayoutHeightDelta then
        delta = ns.GetLayoutHeightDelta("setup.height") or 0
    end
    return Clamp(base + delta, 120, 1200)
end

-- In Compact Mode both cards are as high as the taller one needs, so their outlines line up like in the normal window.
function Layout.GetSetupCardHeight(frame)
    if Layout.IsCompact() then return Layout.GetCompactCardHeight() end
    return NormalSetupCardHeight()
end

-- Panel 1: Size W/H is the logical footprint (used for layout/neighbors).
-- Padding insets the visible card inside that footprint on each side.
function Layout.AnchorSetupCard(card, frame)
    if not card or not frame then return end
    local pad = Layout.GetSetupCardPad()
    local cardX, cardY = Offset("setup.card")
    cardY = tonumber(cardY) or 0
    local left = Layout.GetSetupCardLeft() + (pad.left or 0)
    local width = math.max(40, Layout.GetSetupCardRealWidth() - (pad.left or 0) - (pad.right or 0))
    local height = math.max(40, Layout.GetSetupCardHeight(frame) - (pad.top or 0) - (pad.bottom or 0))
    local top = -(WELL_TOP) + cardY - (pad.top or 0)
    card:ClearAllPoints()
    card:SetPoint("TOPLEFT", frame, "TOPLEFT", left, top)
    card:SetSize(width, height)
end

-- Where the strip of the folded-away left column goes: left, top (negative), width, height.
function Layout.GetLeftStripRect(frame)
    local pad = Layout.GetSetupCardPad()
    local _, cardY = Offset("setup.card")
    local left = Layout.GetSetupCardLeft() + (pad.left or 0)
    local width = math.max(10, LEFT_STRIP_WIDTH - (pad.left or 0) - (pad.right or 0))
    local height = math.max(40, Layout.GetSetupCardHeight(frame) - (pad.top or 0) - (pad.bottom or 0))
    return left, -(WELL_TOP) + (tonumber(cardY) or 0) - (pad.top or 0), width, height
end

-- The folded-away left column opens over the table, or folds away again.
function Layout.SetLeftOpen(frame, open)
    if not frame then return end
    frame.svLeftOpen = open == true
    local card = frame.settingsCard
    if not card then return end
    if frame.svLeftOpen then
        -- Above everything of the table (its bars and texts sit on higher levels of the window's own layer).
        card:SetFrameStrata("DIALOG")
        card:SetFrameLevel((frame:GetFrameLevel() or 1) + 30)
        card:Show()
    else
        card:Hide()
        card:SetFrameStrata(frame:GetFrameStrata() or "MEDIUM")
    end
end

function Layout.GetStatsCardWidth(frame)
    return Clamp(STATS_CARD_BASE_WIDTH + SizeDelta("stats.width"), 220, 1200)
end

-- Panel 2 starts after Panel 1's occupied span (includes Panel 1 push pads).
function Layout.GetStatsCardLeft(frame)
    return Layout.GetSetupCardRight(frame)
end

function Layout.GetStatsCardPad()
    if ns.GetLayoutPadding then
        return ns.GetLayoutPadding("stats.pad")
    end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

function Layout.GetStatsCardPlacedLeft(frame)
    local cardX = select(1, Offset("stats.card"))
    return Layout.GetStatsCardLeft(frame) + (tonumber(cardX) or 0)
end

local function NormalStatsCardHeight()
    local base = 360
    local delta = 0
    if ns.GetLayoutHeightDelta then
        delta = ns.GetLayoutHeightDelta("stats.height") or 0
    end
    return Clamp(base + delta, 120, 1200)
end

-- From the top of the stats card to the bottom of its one table (the table box as placed by its saved offset).
local function CompactTableBottom()
    local _, screenY = Offset("screen.1")
    local screenH = 160 + (ns.GetLayoutHeightDelta and ns.GetLayoutHeightDelta("screen.1.height") or 0)
    return 70 - (tonumber(screenY) or 0) + screenH
end

-- The stats card in Compact Mode: the one table and, inside the same outline, the row of panel buttons under it.
local function CompactStatsCardHeight()
    local pad = Layout.GetStatsCardPad()
    return (pad.top or 0) + CompactTableBottom() + COMPACT_ROW_GAP + COMPACT_BUTTON_ROW_H
        + COMPACT_STATS_BOTTOM_MARGIN + (pad.bottom or 0)
end

-- Both cards in Compact Mode: whichever needs more room (the left card holds the dropdowns and the view button).
function Layout.GetCompactCardHeight()
    local panel = ns.StatVerdictSettingsPanel
    local setupNeeds = (panel and panel.GetCompactHeight and panel.GetCompactHeight()) or COMPACT_SETUP_FALLBACK_H
    return Clamp(math.max(setupNeeds, CompactStatsCardHeight()), 120, 1200)
end

function Layout.GetStatsCardHeight(frame)
    if Layout.IsCompact() then return Layout.GetCompactCardHeight() end
    return NormalStatsCardHeight()
end

-- Where the compact button row goes: left, top (negative, from the window top), width, height. It sits inside the stats card.
function Layout.GetCompactButtonRow(frame)
    local pad = Layout.GetStatsCardPad()
    local left = Layout.GetStatsCardPlacedLeft(frame) + (pad.left or 0) + COMPACT_ROW_INSET
    local width = Layout.GetStatsCardWidth(frame) - (pad.left or 0) - (pad.right or 0) - 2 * COMPACT_ROW_INSET
    local top = -(WELL_TOP + (pad.top or 0) + CompactTableBottom() + COMPACT_ROW_GAP)
    return left, top, width, COMPACT_BUTTON_ROW_H
end

function Layout.GetGridX(frame)
    local pad = Layout.GetStatsCardPad()
    return Layout.GetStatsCardPlacedLeft(frame) + (pad.left or 0) + STATS_CARD_INSET
end

function Layout.GetGridTopY()
    local pad = Layout.GetStatsCardPad()
    local cardY = select(2, Offset("stats.card"))
    return -(WELL_TOP) + (tonumber(cardY) or 0) - (pad.top or 0) + TABLE_TOP_FROM_CARD
end

-- Panel 2: Size W/H is the logical footprint. Padding insets the visible card.
function Layout.AnchorStatsCard(card, frame)
    if not card or not frame then return end
    local pad = Layout.GetStatsCardPad()
    local cardX, cardY = Offset("stats.card")
    cardY = tonumber(cardY) or 0
    local left = Layout.GetStatsCardPlacedLeft(frame) + (pad.left or 0)
    local width = math.max(40, Layout.GetStatsCardWidth(frame) - (pad.left or 0) - (pad.right or 0))
    local height = math.max(40, Layout.GetStatsCardHeight(frame) - (pad.top or 0) - (pad.bottom or 0))
    local top = -(WELL_TOP) + cardY - (pad.top or 0)
    card:ClearAllPoints()
    card:SetPoint("TOPLEFT", frame, "TOPLEFT", left, top)
    card:SetSize(width, height)
end

local ZERO_PAD = { top = 0, bottom = 0, left = 0, right = 0 }

-- Anchor any outer column card to the shared top/bottom band.
-- pad (optional) is the card's own visual inset within its logical footprint.
function Layout.AnchorOuterCard(card, frame, left, pad)
    if not card or not frame then return end
    local g = Layout.GetPanelGutter()
    left = tonumber(left) or (WELL_PAD + g)
    pad = pad or ZERO_PAD
    card:ClearAllPoints()
    card:SetPoint("TOPLEFT", frame, "TOPLEFT", left + (pad.left or 0), Layout.GetPanelTopOffset() - (pad.top or 0))
    card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", left + (pad.left or 0), Layout.GetPanelBottomInset() + (pad.bottom or 0))
end

-- Dock this card to the previous card's right edge with exactly one gutter (no double left margin).
-- yOffset shifts the whole card (and its children) up/down without breaking the horizontal dock.
-- pad (optional) insets this card visually. The previous card may itself be
-- visually inset by its padding, so compensate back to its logical edges.
function Layout.AnchorAfterPreviousCard(card, previousCard, frame, extraGap, yOffset, pad)
    if not card or not frame then return end
    local g = Layout.GetPanelGutter() + (tonumber(extraGap) or 0)
    local y = tonumber(yOffset) or 0
    pad = pad or ZERO_PAD
    if previousCard and previousCard == frame.statProgressCard then
        if Layout.IsCompact() then
            -- Compact Mode: the side panel is its own window, free to move; the main window does not grow for it.
            Layout.AnchorFloatingPanel(card, frame)
            return
        end
        Layout.ReleaseFloatingPanel(card)
    end
    if previousCard then
        local prevPad = ZERO_PAD
        if previousCard == frame.statProgressCard then
            prevPad = Layout.GetStatsCardPad()
        end
        card:ClearAllPoints()
        card:SetPoint(
            "TOPLEFT", previousCard, "TOPRIGHT",
            g + (prevPad.right or 0) + (pad.left or 0),
            y + (prevPad.top or 0) - (pad.top or 0)
        )
        card:SetPoint(
            "BOTTOMLEFT", previousCard, "BOTTOMRIGHT",
            g + (prevPad.right or 0) + (pad.left or 0),
            y - (prevPad.bottom or 0) + (pad.bottom or 0)
        )
        return
    end
    Layout.AnchorOuterCard(card, frame, WELL_PAD + Layout.GetPanelGutter(), pad)
end

-- Floating side panels (Compact Mode) ---------------------------------------------------------------------------------
local FLOAT_GAP = 6
local FLOAT_FALLBACK_WIDTH = 320

-- The buttons at the bottom right of a floating panel: Close in the corner (every panel), Manual to its left (Options).
Layout.FLOAT_BUTTON = { width = 70, height = 24, margin = 14, bottom = 12, gap = 6 }

function ns.CreateFloatingButton(card, label, onClick)
    local size = Layout.FLOAT_BUTTON
    local button = CreateFrame("Button", nil, card, "BackdropTemplate")
    button:SetSize(size.width, size.height)
    button:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = false,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    button:SetBackdropColor(0.10, 0.10, 0.12, 0.92)
    button:SetBackdropBorderColor(0.38, 0.38, 0.40, 0.92)
    button.label = button:CreateFontString(nil, "OVERLAY")
    button.label:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", 11, "")
    button.label:SetPoint("CENTER", button, "CENTER", 0, 0)
    button.label:SetText(label)
    button.label:SetTextColor(0.82, 0.82, 0.82)
    button:SetScript("OnEnter", function(self) self:SetBackdropColor(0.14, 0.14, 0.16, 0.95) end)
    button:SetScript("OnLeave", function(self) self:SetBackdropColor(0.10, 0.10, 0.12, 0.92) end)
    button:SetScript("OnClick", onClick)
    return button
end

-- The room under the content of a floating panel for its Close button: the button, the distance from the bottom, some air.
function Layout.GetFloatingBand()
    local size = Layout.FLOAT_BUTTON
    return size.bottom + size.height + 8
end

-- Best in Slot and Ranked Trinkets: the title chip holds two lines in a window of its own (this much higher).
Layout.FLOAT_TITLE_EXTRA = 16

-- The panel's title in a window of its own, or its plain title when docked.
local function RefreshPanelTitle(card)
    local chip = card.svTabTitleChip
    if chip and chip.svBaseText and chip.label and ns.PanelTitleText then
        chip.label:SetText(ns.PanelTitleText(chip.svBaseText))
    end
end

-- As high as a docked panel in the normal window (the window's top and bottom bands left out).
function Layout.GetFloatingPanelHeight()
    local inner = math.max(NormalSetupCardHeight(), NormalStatsCardHeight())
    local windowHeight = WELL_TOP + inner + WELL_PAD
    return windowHeight - (WELL_TOP + Layout.GetPanelGutter()) - (WELL_PAD + Layout.GetPanelGutter())
end

local function ScreenSize()
    local width = UIParent and UIParent.GetWidth and tonumber(UIParent:GetWidth()) or 1920
    local height = UIParent and UIParent.GetHeight and tonumber(UIParent:GetHeight()) or 1080
    return width, height
end

-- The panel's units against the screen's: a window made smaller (Options > Window size) has bigger units.
local function RelativeScale(card)
    local own = card and card.GetEffectiveScale and tonumber(card:GetEffectiveScale())
    local screen = UIParent and UIParent.GetEffectiveScale and tonumber(UIParent:GetEffectiveScale())
    if own and screen and screen > 0 and own > 0 then return own / screen end
    return 1
end

-- Keeps a panel of this size (left, top) fully on the screen. scale: the panel's units against the screen's.
function Layout.ClampFloatingPosition(left, top, width, height, scale)
    local screenW, screenH = ScreenSize()
    scale = tonumber(scale) or 1
    if scale <= 0 then scale = 1 end
    screenW, screenH = screenW / scale, screenH / scale
    left = Clamp(left, 0, math.max(0, screenW - width))
    top = Clamp(top, math.min(height, screenH), screenH)
    return left, top
end

-- Where a panel opens when the player never moved one: beside the window (right, else left), level with its top.
local function DefaultFloatingPosition(frame, width, height, scale)
    local screenW = ScreenSize() / (tonumber(scale) or 1)
    local right, left, top = frame.GetRight and frame:GetRight(), frame.GetLeft and frame:GetLeft(), frame.GetTop and frame:GetTop()
    if not (tonumber(right) and tonumber(left) and tonumber(top)) then return 60, select(2, ScreenSize()) - 60 end
    local x = right + FLOAT_GAP
    if x + width > screenW then x = left - FLOAT_GAP - width end
    return x, top - (WELL_TOP + Layout.GetPanelGutter()) + WELL_TOP
end

local function SaveFloatingPosition(card)
    local left, top = card:GetLeft(), card:GetTop()
    if tonumber(left) and tonumber(top) then
        _G.StatVerdictDB = _G.StatVerdictDB or {}
        _G.StatVerdictDB.floatingPanelPos = { x = left, y = top }
    end
end

-- The drag, the close button: what makes a drawer card a window of its own. Made once per card.
local function EnsureFloatingChrome(card)
    if not card.svFloatingChrome then
        card.svFloatingChrome = true
        card:SetScript("OnDragStart", function(self) self:StartMoving() end)
        card:SetScript("OnDragStop", function(self)
            self:StopMovingOrSizing()
            SaveFloatingPosition(self)
        end)
        card.svCloseButton = ns.CreateFloatingButton(card, "Close", function()
            if ns.SetRightPanelMode then ns.SetRightPanelMode(nil) end
        end)
        card.svCloseButton:ClearAllPoints()
        card.svCloseButton:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -Layout.FLOAT_BUTTON.margin, Layout.FLOAT_BUTTON.bottom)
    end
    if not card.svFloating then
        card.svFloating = true
        card:SetMovable(true)
        card:SetClampedToScreen(true)
        card:EnableMouse(true)
        card:RegisterForDrag("LeftButton")
    end
    card.svCloseButton:SetFrameLevel((card:GetFrameLevel() or 1) + 20)
    card.svCloseButton:Show()
    -- The title chip of Best in Slot / Ranked Trinkets is a button: it hands a drag on to the window.
    local chip = card.svViewToggle
    if chip and not chip.svDragForwarded then
        chip.svDragForwarded = true
        chip:RegisterForDrag("LeftButton")
        chip:SetScript("OnDragStart", function() card:StartMoving() end)
        chip:SetScript("OnDragStop", function()
            card:StopMovingOrSizing()
            SaveFloatingPosition(card)
        end)
    end
end

-- The panel windows of the main window: they follow its layer (strata) and size, and go when it goes.
function ns.SyncFloatingPanelStrata(frame, strata)
    for _, card in ipairs(frame and frame.svFloatingCards or {}) do
        card:SetFrameStrata(strata)
    end
end

local function RegisterFloatingCard(frame, card)
    frame.svFloatingCards = frame.svFloatingCards or {}
    for _, known in ipairs(frame.svFloatingCards) do
        if known == card then return end
    end
    frame.svFloatingCards[#frame.svFloatingCards + 1] = card
    if not frame.svFloatingHideHooked then
        frame.svFloatingHideHooked = true
        -- The panel windows are not children of the main window any more, so they have to be sent away with it.
        frame:HookScript("OnHide", function(self)
            for _, panel in ipairs(self.svFloatingCards or {}) do
                if panel.svFloating then panel:Hide() end
            end
        end)
    end
end

-- The panel windows only show while the main window does.
function Layout.HideFloatingPanelsWithTheWindow(frame)
    if frame.IsShown and frame:IsShown() then return end
    for _, card in ipairs(frame.svFloatingCards or {}) do
        if card.svFloating then card:Hide() end
    end
end

function Layout.AnchorFloatingPanel(card, frame)
    if not (card and frame) then return end
    -- A window of its own: a child of the screen, not of the main window, and a top level one, so a click brings it (all of
    -- it) in front of the main window and the main window in front of it, like two windows of the game. It keeps the main
    -- window's layer and size.
    local newlyFloating = not card.svFloating
    if card.GetParent and card:GetParent() ~= UIParent then card:SetParent(UIParent) end
    card.svWindow = frame
    card:SetToplevel(true)
    card:SetScale(tonumber(frame.GetScale and frame:GetScale()) or 1)
    card:SetFrameStrata((frame.GetFrameStrata and frame:GetFrameStrata()) or "MEDIUM")
    RegisterFloatingCard(frame, card)
    local width = tonumber(card.preferredWidth) or tonumber(card.GetWidth and card:GetWidth()) or FLOAT_FALLBACK_WIDTH
    if width < 100 then width = FLOAT_FALLBACK_WIDTH end
    -- A panel that knows how high its content is (Best in Slot, Ranked Trinkets) says so; the rest are as high as a docked one.
    local height = tonumber(card.svFloatingHeight) or Layout.GetFloatingPanelHeight()
    local saved = _G.StatVerdictDB and _G.StatVerdictDB.floatingPanelPos
    local x, y
    if type(saved) == "table" and tonumber(saved.x) and tonumber(saved.y) then
        x, y = tonumber(saved.x), tonumber(saved.y)
    else
        x, y = DefaultFloatingPosition(frame, width, height, RelativeScale(card))
    end
    x, y = Layout.ClampFloatingPosition(x, y, width, height, RelativeScale(card))
    card:ClearAllPoints()
    card:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", x, y)
    card:SetHeight(height)
    EnsureFloatingChrome(card)
    RefreshPanelTitle(card)
    if newlyFloating and card.Raise then card:Raise() end  -- a panel that has just opened is in front
end

-- Back to a docked panel: no close button, no drag.
function Layout.ReleaseFloatingPanel(card)
    if not (card and card.svFloating) then return end
    card.svFloating = false
    card:SetMovable(false)
    card:RegisterForDrag()
    card:EnableMouse(false)
    if card.svCloseButton then card.svCloseButton:Hide() end
    -- Docked again: a part of the main window, as before.
    local window = card.svWindow
    if window then
        card:SetParent(window)
        card:SetToplevel(false)
        card:SetScale(1)
        card:SetFrameLevel(math.max(1, (window:GetFrameLevel() or 1) - 1))
    end
    RefreshPanelTitle(card)
end

function Layout.GetRightPanelX(frame)
    -- Logical right of Panel 2 (Size W only; padding is a visual inset).
    local statsRight = Layout.GetStatsCardPlacedLeft(frame)
        + Layout.GetStatsCardWidth(frame)
    local base = statsRight + Layout.GetPanelGutter()
    -- Dock may be negative so the drawer can move left past the default gutter.
    local dock = SharedRightDockX()
    return base + (tonumber(dock) or 0)
end

-- Extra gap past the normal gutter for the right dock.
-- Negative values pull the drawer left (closer to / over Panel 2).
function Layout.GetRightPanelExtraGap()
    return tonumber(SharedRightDockX()) or 0
end

-- Trailing space after the last panel inside the window chrome.
-- Slightly under the old full (gutter + well pad); half felt too tight.
function Layout.GetRightEdgeInset()
    local full = Layout.GetPanelGutter() + WELL_PAD
    local edge = math.floor(full * 0.75 + 0.5)
    if edge < 6 then edge = 6 end
    return edge
end

local function ComputeFrameWidth(frame, showRightPanel)
    local edge = Layout.GetRightEdgeInset()
    local titleRoom = (ns.GetTitleBarMinWidth and ns.GetTitleBarMinWidth(frame)) or 0
    if showRightPanel then
        local rightPanelX = Layout.GetRightPanelX(frame)
        local rightPanelWidth = Layout.GetRightPanelWidth(frame)
        return Clamp(math.max(rightPanelX + rightPanelWidth + edge, titleRoom), MIN_FRAME_WIDTH, MAX_FRAME_WIDTH)
    end
    -- Frame width follows the logical footprint (Size W); padding never grows it.
    local statsLeft = Layout.GetStatsCardPlacedLeft(frame)
    local statsCardWidth = Layout.GetStatsCardWidth(frame)
    return Clamp(
        math.max(statsLeft + statsCardWidth + edge, titleRoom),
        MIN_FRAME_WIDTH,
        MAX_FRAME_WIDTH
    )
end

local function ComputeFrameHeight(frame)
    -- Main frame height = tallest panel Size H. Padding pushes panels; it does not shrink Size H.
    local inner = math.max(NormalSetupCardHeight(), NormalStatsCardHeight())
    if Layout.IsCompact() then
        -- The two cards are short, the button row inside the stats card. A side panel floats free and never changes it.
        inner = Layout.GetCompactCardHeight()
    end
    return Clamp(WELL_TOP + inner + WELL_PAD, 200, 1400)
end

function Layout.SyncFrameWidthToRightPanel(frame)
    if not frame then return end
    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    if not mode or Layout.IsCompact() then
        -- No right drawer (or a floating one in Compact Mode): shrink to Stat Progress only.
        local width = ComputeFrameWidth(frame, false)
        if math.abs((frame:GetWidth() or 0) - width) >= 0.5 then
            frame:SetWidth(width)
        end
        if ns.ReapplyStatAuditWindowLayout then
            ns.ReapplyStatAuditWindowLayout(frame)
        end
        return
    end

    local card = frame.bisProgressCard
    if mode == "options" then
        card = frame.optionsDrawerCard
    elseif mode == "manual" then
        card = frame.manualDrawerCard
    elseif mode == "weights" then
        card = frame.weightsDrawerCard
    end
    local cardX = Layout.GetRightPanelX(frame)
    local cardW = nil
    if card and card:IsShown() then
        cardW = tonumber(card:GetWidth()) or tonumber(card.preferredWidth)
    end
    if not cardW or cardW < 50 then
        cardW = Layout.GetRightPanelWidth(frame)
    end
    local width = Clamp(cardX + cardW + Layout.GetRightEdgeInset(), MIN_FRAME_WIDTH, MAX_FRAME_WIDTH)
    if math.abs((frame:GetWidth() or 0) - width) >= 0.5 then
        frame:SetWidth(width)
    end
    if ns.ReapplyStatAuditWindowLayout then
        ns.ReapplyStatAuditWindowLayout(frame)
    end
end

function Layout.Apply(frame, usedRows, controls)
    local visibleRows = math.max(1, math.min(16, tonumber(usedRows) or 1))
    local gridOffsetX, gridOffsetY = Offset("stats.table")
    local gridWidth = GRID_WIDTH + SizeDelta("stats.table.width")
    if gridWidth < 140 then gridWidth = 140 end
    if gridWidth > 1200 then gridWidth = 1200 end
    local dashboardMoveX = Offset("dashboard.move")
    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    local showOptions = mode == "options"
    local showManual = mode == "manual"
    local showWeights = mode == "weights"
    local showTrinkets = mode == "trinkets"
    local showBis = mode == "bis"
    local showRightPanel = mode ~= nil and not Layout.IsCompact()
    local width = ComputeFrameWidth(frame, showRightPanel)
    local frameHeight = ComputeFrameHeight(frame)

    if not frame.devTopLeftBase then
        local left, top = frame:GetLeft(), frame:GetTop()
        if left and top then
            frame.devTopLeftBase = { x = left - dashboardMoveX, y = top }
        else
            local point, _, _, x, y = frame:GetPoint(1)
            frame.devTopLeftBase = {
                x = tonumber(x) or 0,
                y = tonumber(y) or 0,
                point = point or "CENTER",
            }
        end
    end
    frame:ClearAllPoints()
    local base = frame.devTopLeftBase
    if base and base.point == "CENTER" then
        frame:SetPoint("CENTER", UIParent, "CENTER", (tonumber(base.x) or 0) + dashboardMoveX, tonumber(base.y) or 0)
        local left, top = frame:GetLeft(), frame:GetTop()
        if left and top then
            frame.devTopLeftBase = { x = left - dashboardMoveX, y = top }
            frame:ClearAllPoints()
            frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", left, top)
        end
    else
        frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", (tonumber(base and base.x) or 0) + dashboardMoveX, tonumber(base and base.y) or 0)
    end
    frame:SetSize(width, frameHeight)
    if frame.SetClipsChildren then
        frame:SetClipsChildren(false)
    end
    if ns.ReapplyStatAuditWindowLayout then
        -- Keep the user's remembered spot; only nudge left if a right panel would clip.
        ns.ReapplyStatAuditWindowLayout(frame)
    end

    if ns.StatVerdictSettingsPanel then
        ns.StatVerdictSettingsPanel.Apply(frame, controls or {})
    end
    local gridX = Layout.GetGridX(frame)
    local gridTopY = Layout.GetGridTopY()
    local tableBaseX = gridX + gridOffsetX
    local tableBaseY = gridTopY + gridOffsetY
    if ns.StatVerdictStatProgressPanel then
        ns.StatVerdictStatProgressPanel.Apply(frame, gridX, gridTopY, visibleRows, ROW_HEIGHT)
    end

    local function HideAllRightDrawers()
        if frame.bisProgressCard then frame.bisProgressCard:Hide() end
        if frame.optionsDrawerCard then frame.optionsDrawerCard:Hide() end
        if frame.manualDrawerCard then frame.manualDrawerCard:Hide() end
        if frame.weightsDrawerCard then frame.weightsDrawerCard:Hide() end
            end

    HideAllRightDrawers()
    if showOptions and ns.StatVerdictOptionsDrawerPanel then
        ns.StatVerdictOptionsDrawerPanel.Apply(frame)
    elseif showManual and ns.StatVerdictManualDrawerPanel then
        ns.StatVerdictManualDrawerPanel.Apply(frame)
    elseif showWeights and ns.StatVerdictWeightsDrawerPanel then
        ns.StatVerdictWeightsDrawerPanel.Apply(frame)
    elseif (showBis or showTrinkets) and ns.StatVerdictBisProgressPanel then
        ns.StatVerdictBisProgressPanel.Apply(frame)
        if frame.bisProgressCard then frame.bisProgressCard:Show() end
    else
        if ns.StatVerdictOptionsDrawerPanel and ns.StatVerdictOptionsDrawerPanel.Apply then
            ns.StatVerdictOptionsDrawerPanel.Apply(frame)
        end
        if ns.StatVerdictManualDrawerPanel and ns.StatVerdictManualDrawerPanel.Apply then
            ns.StatVerdictManualDrawerPanel.Apply(frame)
        end
        if ns.StatVerdictWeightsDrawerPanel and ns.StatVerdictWeightsDrawerPanel.Apply then
            ns.StatVerdictWeightsDrawerPanel.Apply(frame)
        end
        Layout.SyncFrameWidthToRightPanel(frame)
    end

    -- Always re-sync after cards applied so Stats/Setup width growth never clips outside the frame.
    Layout.SyncFrameWidthToRightPanel(frame)
    local syncedHeight = ComputeFrameHeight(frame)
    if math.abs((frame:GetHeight() or 0) - syncedHeight) >= 0.5 then
        frame:SetHeight(syncedHeight)
    end

    if frame.gridCard then frame.gridCard:Hide() end
    if frame.profileLine then frame.profileLine:Hide() end
    if frame.profileTagMain then frame.profileTagMain:Hide() end
    if frame.profileTagSecondary then frame.profileTagSecondary:Hide() end
    if frame.secondarySubtitle then
        -- Title slot stays locked; StatProgressPanel owns visibility/text.
    end
    if frame.offAvgProgressText and frame.svOffSpecVisible ~= true then
        frame.offAvgProgressText:Hide()
    end
    if frame.offSpecEmptyHint then
        frame.offSpecEmptyHint:Hide()
    end

    -- Screen 1 → MS stats; Screen 2 → OS stats. Headers/columns/bars live inside those boxes.
    local mainScreen = frame.statProgressTableCard
    local offScreen = frame.offStatProgressTableCard
    local mainHost = frame.svMainStatContentHost or mainScreen
    local offHost = frame.svOffStatContentHost or offScreen
    local function PlaceOnHost(region, host, x, y)
        if not region or not host then return end
        if region.SetParent and region:GetParent() ~= host then
            region:SetParent(host)
        end
        region:ClearAllPoints()
        region:SetPoint("TOPLEFT", host, "TOPLEFT", x, y)
    end

    for _, column in ipairs(frame.columns or {}) do
        local header = frame.headers and frame.headers[column.key]
        if header then
            if frame.svMainSpecMissingMessage == true or not mainHost then
                header:Hide()
            else
                local colX, colY = Offset("stats.column." .. column.key)
                local textX, textY = Offset("stats.headerText." .. column.key)
                PlaceOnHost(
                    header,
                    mainHost,
                    SCREEN_CONTENT_X + colX + textX + (column.relX or 0),
                    colY + textY
                )
                header:SetWidth(ColumnWidth(column))
                header:Show()
            end
        end
    end

    for _, separator in ipairs(frame.separators or {}) do separator:Hide() end

    for lineIndex, line in ipairs(frame.horizontalLines or {}) do
        line:Hide()
    end

    local maxShowRows = math.min(visibleRows, FIXED_SLOT_ROWS)
    if frame.svFixedSlotRows then
        maxShowRows = math.min(visibleRows, tonumber(frame.svFixedSlotRows) or FIXED_SLOT_ROWS)
    elseif mainHost and mainHost.GetHeight then
        local h = tonumber(mainHost:GetHeight()) or 0
        if h >= 40 then
            maxShowRows = math.min(visibleRows, math.max(1, math.floor((h - TABLE_HEADER_BAND) / ROW_HEIGHT)))
        end
    end
    for rowIndex, row in ipairs(frame.rows or {}) do
        local shown = (frame.svMainSpecMissingMessage ~= true) and mainHost and rowIndex <= maxShowRows
        for key, cell in pairs(row) do
            if shown then
                local column = frame.columnByKey and frame.columnByKey[key]
                if column then
                    local colX, colY = Offset("stats.column." .. key)
                    PlaceOnHost(
                        cell,
                        mainHost,
                        SCREEN_CONTENT_X + colX + (column.relX or 0),
                        colY - 22 - ((rowIndex - 1) * ROW_HEIGHT)
                    )
                    cell:SetWidth(ColumnWidth(column))
                    cell:Show()
                end
            else
                cell:Hide()
            end
        end
    end

    -- Off Spec table: independent content host (not Screen 2).
    local offVisibleRows = math.min(
        math.max(1, tonumber(frame.svOffSpecUsedRows) or visibleRows),
        tonumber(frame.svOffFixedSlotRows) or tonumber(frame.svFixedSlotRows) or FIXED_SLOT_ROWS
    )
    if frame.svOffSpecVisible and frame.svOffSpecMissingMessage ~= true and offHost then
        for _, column in ipairs(frame.columns or {}) do
            local header = frame.offHeaders and frame.offHeaders[column.key]
            if header then
                local colX, colY = Offset("stats.column." .. column.key)
                local textX, textY = Offset("stats.headerText." .. column.key)
                PlaceOnHost(
                    header,
                    offHost,
                    SCREEN_CONTENT_X + colX + textX + (column.relX or 0),
                    colY + textY
                )
                header:SetWidth(ColumnWidth(column))
                header:Show()
            end
        end
        for rowIndex, row in ipairs(frame.offRows or {}) do
            local shown = rowIndex <= offVisibleRows
            for key, cell in pairs(row) do
                if shown then
                    local column = frame.columnByKey and frame.columnByKey[key]
                    if column then
                        local colX, colY = Offset("stats.column." .. key)
                        PlaceOnHost(
                            cell,
                            offHost,
                            SCREEN_CONTENT_X + colX + (column.relX or 0),
                            colY - 22 - ((rowIndex - 1) * ROW_HEIGHT)
                        )
                        cell:SetWidth(ColumnWidth(column))
                        cell:Show()
                    end
                else
                    cell:Hide()
                end
            end
        end
    else
        for _, header in pairs(frame.offHeaders or {}) do
            header:Hide()
        end
        for _, row in ipairs(frame.offRows or {}) do
            for _, cell in pairs(row) do
                cell:Hide()
            end
        end
    end

    if frame.avgProgressText then
        if frame.svMainSpecMissingMessage == true then
            frame.avgProgressText:Hide()
        else
            frame.avgProgressText:Show()
        end
    end

    -- One box per column (header + values share width & XY).
    -- Title letters use a separate exact-hit control (X only) inside that box.
    frame.devStatHeaderRegions = frame.devStatHeaderRegions or {}
    frame.devStatColumnRegions = frame.devStatColumnRegions or {}
    for _, column in ipairs(frame.columns or {}) do
        local key = column.key
        if not IsEditableStatColumn(column) then
            if frame.devStatColumnRegions[key] then
                frame.devStatColumnRegions[key]:Hide()
            end
            if frame.devStatHeaderRegions[key] then
                frame.devStatHeaderRegions[key]:Hide()
            end
        else
            local colX, colY = Offset("stats.column." .. key)
            local colW = math.max(16, ColumnWidth(column))
            local colH = 20 + math.max(24, math.min(visibleRows, FIXED_SLOT_ROWS) * ROW_HEIGHT)

            if frame.devStatHeaderRegions[key] then
                frame.devStatHeaderRegions[key]:Hide()
            end

            if not frame.devStatColumnRegions[key] then
                frame.devStatColumnRegions[key] = CreateFrame("Frame", nil, frame)
                frame.devStatColumnRegions[key]:EnableMouse(false)
            end
            local columnRegion = frame.devStatColumnRegions[key]
            local columnParent = mainHost or frame
            if columnRegion.GetParent and columnRegion:GetParent() ~= columnParent then
                columnRegion:SetParent(columnParent)
            end
            columnRegion:ClearAllPoints()
            columnRegion:SetPoint(
                "TOPLEFT",
                columnParent,
                "TOPLEFT",
                SCREEN_CONTENT_X + colX + (column.relX or 0),
                colY + 2
            )
            columnRegion:SetSize(colW, colH)
            columnRegion:Show()

            -- Outer pad: Move XY + Size W.
            local colBaseW = math.max(16, tonumber(column.width) or 16)
            local colKey = "stats.column." .. key
            local widthKey = colKey .. ".width"

            -- Drop legacy orange width nubs — Size W lives on the outer pad now.
            if key == "progress" then
                frame.devStatProgressWidthRegion = nil
            end
        end
    end

    local tableHeight = tonumber(frame.svStatScreenHeight) or StatTableHeight(FIXED_SLOT_ROWS)

    -- Prefer content host for legacy table grips; never overwrite Screen 1 size here.
    local tableAnchor = frame.svMainStatContentHost or frame.statProgressTableCard
    if tableAnchor and tableAnchor.IsShown and tableAnchor:IsShown() then
        if frame.devStatTableRegion then
            frame.devStatTableRegion:Hide()
        end
    else
        if not frame.devStatTableRegion then
            frame.devStatTableRegion = CreateFrame("Frame", nil, frame)
            frame.devStatTableRegion:EnableMouse(false)
        end
        frame.devStatTableRegion:ClearAllPoints()
        frame.devStatTableRegion:SetPoint("TOPLEFT", frame, "TOPLEFT", tableBaseX - 6, tableBaseY + 8)
        frame.devStatTableRegion:SetSize(gridWidth + 12, tableHeight)
        frame.devStatTableRegion:Show()
        tableAnchor = frame.devStatTableRegion
    end

    -- Move grip along the TOP edge of the inner table (above # / Stat / Progress headers).
    -- This stays clickable even when the big Stat Progress card is click-through.
    if not frame.devStatTableMoveGrip then
        frame.devStatTableMoveGrip = CreateFrame("Frame", nil, frame)
        frame.devStatTableMoveGrip:EnableMouse(false)
    end
    frame.devStatTableMoveGrip:ClearAllPoints()
    if tableAnchor then
        frame.devStatTableMoveGrip:SetPoint("BOTTOMLEFT", tableAnchor, "TOPLEFT", 0, 1)
        frame.devStatTableMoveGrip:SetPoint("BOTTOMRIGHT", tableAnchor, "TOPRIGHT", 0, 1)
    else
        frame.devStatTableMoveGrip:SetPoint("TOPLEFT", frame, "TOPLEFT", tableBaseX - 6, tableBaseY + 26)
        frame.devStatTableMoveGrip:SetWidth(gridWidth + 12)
    end
    frame.devStatTableMoveGrip:SetHeight(18)
    frame.devStatTableMoveGrip:Show()

    -- Legacy stats.table grips replaced by Screen 1 / Screen 2. Do not mass-strip
    -- stats.* — titles, columns, and screens must keep their move frames.
    if frame.devStatTableMoveGrip then frame.devStatTableMoveGrip:Hide() end
    if frame.devStatTableRegion then frame.devStatTableRegion:Hide() end

    -- Window size follows Frames 1+2.
        if frame.statVerdictSetupResizeRegions then
        for _, region in pairs(frame.statVerdictSetupResizeRegions) do
            if region and region.Hide then region:Hide() end
        end
    end
    -- Keep Average Progress / header text hit boxes selectable — do not mass-hide them.
    Layout.ApplyCompactViews(frame)
    Layout.HideFloatingPanelsWithTheWindow(frame)
end

local function HideRegion(region)
    if region and region.Hide then region:Hide() end
end

-- Puts a region where another one sits (same anchor, same offset).
local function PlaceWhere(region, model)
    if not (region and model and model.GetPoint) then return end
    local point, relativeTo, relativePoint, x, y = model:GetPoint(1)
    if not point then return end
    region:ClearAllPoints()
    region:SetPoint(point, relativeTo, relativePoint, x, y)
end

-- Compact Mode shows one table: the one selected. Run last, after the cards were laid out in their normal places. Without
-- Compact Mode nothing is done here, so the normal layout of the next pass is untouched.
-- While the left column is folded away its headings are not in sight, so a small "(Main Spec)" / "(Off Spec)" stands after the
-- table's title. It is a text of its own, in a small font, so it stays discreet whatever the title's size; the title gets
-- the room it takes.
local SPEC_TAG_FONT_SIZE = 9
local SPEC_TAG_GAP = 6

function Layout.UpdateSpecTag(frame, view)
    local tag = frame.svSpecTag
    if not (Layout.IsLeftAutoHidden() and view) then
        if tag then tag:Hide() end
        return
    end
    local title = view == "OFF" and frame.secondarySubtitle or frame.subtitle
    if not title then
        if tag then tag:Hide() end
        return
    end
    local parent = (title.GetParent and title:GetParent()) or frame
    if not tag then
        tag = parent:CreateFontString(nil, "OVERLAY")
        tag:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", SPEC_TAG_FONT_SIZE, "")
        tag:SetTextColor(0.90, 0.75, 0.20)
        frame.svSpecTag = tag
    elseif tag.GetParent and tag:GetParent() ~= parent then
        tag:SetParent(parent)
    end
    tag:SetText(view == "OFF" and "(Off Spec)" or "(Main Spec)")
    -- The title makes room for the tag, then the tag follows the end of the title's text.
    local room = (tonumber(tag:GetStringWidth()) or 0) + SPEC_TAG_GAP
    if title.SetWidth and title.GetWidth then
        title:SetWidth(math.max(80, (tonumber(title:GetWidth()) or 0) - room))
    end
    local panel = ns.StatVerdictStatProgressPanel
    if panel then
        if view == "OFF" and panel.FitOffSpecTitle then
            panel.FitOffSpecTitle(frame)
        elseif panel.FitSpecTitle then
            panel.FitSpecTitle(frame)
        end
    end
    tag:ClearAllPoints()
    tag:SetPoint("LEFT", title, "LEFT", (tonumber(title:GetStringWidth()) or 0) + SPEC_TAG_GAP, 0)
    tag:Show()
end

function Layout.ApplyCompactViews(frame)
    -- The Main Spec title is only ever shown once, when the window is made: what this file hid, it shows again first.
    if frame.svSubtitleHiddenByCompact then
        frame.svSubtitleHiddenByCompact = false
        if frame.subtitle and frame.subtitle.Show then frame.subtitle:Show() end
    end
    -- The folded-away left column: only its strip shows, and the card only while the mouse is on it.
    if Layout.IsLeftAutoHidden() then
        if frame.svLeftOpen then
            Layout.SetLeftOpen(frame, true)
        else
            HideRegion(frame.settingsCard)
        end
    else
        if frame.svLeftOpen and frame.settingsCard then
            frame.settingsCard:SetFrameStrata(frame:GetFrameStrata() or "MEDIUM")
        end
        frame.svLeftOpen = false
        HideRegion(frame.svLeftStrip)
        if frame.settingsCard and frame.settingsCard.Show then frame.settingsCard:Show() end
    end
    local view = Layout.CompactView()
    Layout.UpdateSpecTag(frame, view)
    if not view then return end
    local mainScreen, offScreen = frame.statProgressTableCard, frame.offStatProgressTableCard
    local boxes = frame._svTitleBoxes or {}
    local mainBox, offBox = boxes["stats.specTitle"], boxes["stats.offSpecTitle"]
    if view == "OFF" then
        HideRegion(mainScreen)
        HideRegion(mainBox)
        HideRegion(frame.subtitle)
        frame.svSubtitleHiddenByCompact = true
        if ns.HideSpecSelectButton then ns.HideSpecSelectButton("MAIN") end
        -- The Off Spec table and its title take the place of the Main Spec table and title.
        PlaceWhere(offScreen, mainScreen)
        if offScreen and mainScreen and offScreen.SetSize and mainScreen.GetWidth then
            offScreen:SetSize(mainScreen:GetWidth(), mainScreen:GetHeight())
        end
        PlaceWhere(offBox, mainBox)
        -- The table inside has its own saved offset and size per spec: use the Main Spec table's, so that the two views
        -- sit on exactly the same lines and nothing jumps when the view is switched.
        local mainHost, offHost = frame.svMainStatContentHost, frame.svOffStatContentHost
        if mainHost and offHost and mainHost.GetPoint then
            local point, _, relativePoint, x, y = mainHost:GetPoint(1)
            if point then
                offHost:ClearAllPoints()
                offHost:SetPoint(point, offScreen, relativePoint, x, y)
                if offHost.SetSize and mainHost.GetWidth then
                    offHost:SetSize(mainHost:GetWidth(), mainHost:GetHeight())
                end
            end
        end
    else
        HideRegion(offScreen)
        HideRegion(offBox)
        HideRegion(frame.secondarySubtitle)
        if frame.offAvgProgressText then frame.offAvgProgressText:Hide() end
        if ns.HideSpecSelectButton then ns.HideSpecSelectButton("OFF") end
    end
end
