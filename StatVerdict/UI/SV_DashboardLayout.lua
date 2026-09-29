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
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end


local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function Clamp(value, minValue, maxValue)
    value = tonumber(value) or 0
    if value < minValue then return minValue end
    if value > maxValue then return maxValue end
    return value
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
    if ns.GetDevLayoutHeightDelta then
        height = height + (ns.GetDevLayoutHeightDelta("stats.table.height") or 0)
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
        return Clamp(baseWidth + delta, 200, 520)
    end
    if mode == "weights" then
        if ns.StatVerdictWeightsDrawerPanel and ns.StatVerdictWeightsDrawerPanel.GetPreferredWidth then
            return ns.StatVerdictWeightsDrawerPanel.GetPreferredWidth(frame)
        end
        return Clamp(300 + SizeDelta("benchmark.width"), 200, 520)
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
    for _, key in ipairs({ "benchmark.card", "options.card", "manual.card", "bis.card" }) do
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

function Layout.GetSetupCardWidth(frame)
    return Clamp(SETUP_CARD_BASE_WIDTH + SizeDelta("setup.width"), 80, 700)
end

-- Right edge of Panel 1's logical span (Size W only). Panel 2 starts here.
-- Padding is a visual inset inside the footprint; it never moves neighbors.
function Layout.GetSetupCardRight(frame)
    return Layout.GetSetupCardLeft() + Layout.GetSetupCardWidth(frame)
end

function Layout.GetSetupCardPad()
    if ns.GetDevLayoutPadding then
        return ns.GetDevLayoutPadding("setup.pad")
    end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

function Layout.GetSetupCardHeight(frame)
    local base = 360
    local delta = 0
    if ns.GetDevLayoutHeightDelta then
        delta = ns.GetDevLayoutHeightDelta("setup.height") or 0
    end
    return Clamp(base + delta, 120, 1200)
end

-- Panel 1: Size W/H is the logical footprint (used for layout/neighbors).
-- Padding insets the visible card inside that footprint on each side.
function Layout.AnchorSetupCard(card, frame)
    if not card or not frame then return end
    local pad = Layout.GetSetupCardPad()
    local cardX, cardY = Offset("setup.card")
    cardY = tonumber(cardY) or 0
    local left = Layout.GetSetupCardLeft() + (pad.left or 0)
    local width = math.max(40, Layout.GetSetupCardWidth(frame) - (pad.left or 0) - (pad.right or 0))
    local height = math.max(40, Layout.GetSetupCardHeight(frame) - (pad.top or 0) - (pad.bottom or 0))
    local top = -(WELL_TOP) + cardY - (pad.top or 0)
    card:ClearAllPoints()
    card:SetPoint("TOPLEFT", frame, "TOPLEFT", left, top)
    card:SetSize(width, height)
end

function Layout.GetStatsCardWidth(frame)
    return Clamp(STATS_CARD_BASE_WIDTH + SizeDelta("stats.width"), 220, 1200)
end

-- Panel 2 starts after Panel 1's occupied span (includes Panel 1 push pads).
function Layout.GetStatsCardLeft(frame)
    return Layout.GetSetupCardRight(frame)
end

function Layout.GetStatsCardPad()
    if ns.GetDevLayoutPadding then
        return ns.GetDevLayoutPadding("stats.pad")
    end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

function Layout.GetStatsCardPlacedLeft(frame)
    local cardX = select(1, Offset("stats.card"))
    return Layout.GetStatsCardLeft(frame) + (tonumber(cardX) or 0)
end

function Layout.GetStatsCardHeight(frame)
    local base = 360
    local delta = 0
    if ns.GetDevLayoutHeightDelta then
        delta = ns.GetDevLayoutHeightDelta("stats.height") or 0
    end
    return Clamp(base + delta, 120, 1200)
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

function Layout.GetRightPanelX(frame)
    -- Logical right of Panel 2 (Size W only; padding is a visual inset).
    local statsRight = Layout.GetStatsCardPlacedLeft(frame)
        + Layout.GetStatsCardWidth(frame)
    local base = statsRight + Layout.GetPanelGutter()
    -- Dock may be negative so the drawer can move left past the default gutter.
    local dock = SharedRightDockX()
    return base + (tonumber(dock) or 0)
end

-- Extra gap past the normal gutter for AdvDev right-dock nudge.
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
    if showRightPanel then
        local rightPanelX = Layout.GetRightPanelX(frame)
        local rightPanelWidth = Layout.GetRightPanelWidth(frame)
        return Clamp(rightPanelX + rightPanelWidth + edge, MIN_FRAME_WIDTH, MAX_FRAME_WIDTH)
    end
    -- Frame width follows the logical footprint (Size W); padding never grows it.
    local statsLeft = Layout.GetStatsCardPlacedLeft(frame)
    local statsCardWidth = Layout.GetStatsCardWidth(frame)
    return Clamp(
        statsLeft + statsCardWidth + edge,
        MIN_FRAME_WIDTH,
        MAX_FRAME_WIDTH
    )
end

local function ComputeFrameHeight(frame)
    -- Main frame height = tallest panel Size H. Padding pushes panels; it does not shrink Size H.
    local setupH = Layout.GetSetupCardHeight(frame)
    local statsH = Layout.GetStatsCardHeight(frame)
    local inner = math.max(setupH, statsH)
    return Clamp(WELL_TOP + inner + WELL_PAD, 200, 1400)
end

function Layout.SyncFrameWidthToRightPanel(frame)
    if not frame then return end
    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    if not mode then
        -- No right drawer: shrink to Stat Progress only.
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
    local showRightPanel = mode ~= nil
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
        if frame.devBisWidthRegion then frame.devBisWidthRegion:Hide() end
        if frame.devBisTrinketsGroupRegion then frame.devBisTrinketsGroupRegion:Hide() end
        if frame.optionsDrawerCard then frame.optionsDrawerCard:Hide() end
        if frame.devOptionsWidthRegion then frame.devOptionsWidthRegion:Hide() end
        if frame.manualDrawerCard then frame.manualDrawerCard:Hide() end
        if frame.devManualWidthRegion then frame.devManualWidthRegion:Hide() end
        if frame.weightsDrawerCard then frame.weightsDrawerCard:Hide() end
        -- Drop orphan AdvDev targets from inactive drawers so cyan ghosts cannot linger.
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
        if frame.devBisWidthRegion then frame.devBisWidthRegion:Show() end
        if frame.devBisTrinketsGroupRegion then frame.devBisTrinketsGroupRegion:Show() end
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

    -- One AdvDev box per column (header + values share width & XY).
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

            -- Outer AdvDev pad: Move XY + Size W (legacy width nubs removed).
            local colBaseW = math.max(16, tonumber(column.width) or 16)
            local colKey = "stats.column." .. key
            local widthKey = colKey .. ".width"

            -- Title letters: cyan hit around the text; Move X only on the outer pad.
            local header = frame.headers and frame.headers[key]
            if header and ns.EnsureDevLayoutTextHitRegion then
                local stringW = 0
                if header.GetStringWidth then
                    stringW = tonumber(header:GetStringWidth()) or 0
                end
                local textKey = "stats.headerText." .. key
                local textHit = ns.EnsureDevLayoutTextHitRegion(frame, textKey, header, {
                    minWidth = math.max(8, math.min(colW - 2, stringW + 4)),
                    minHeight = 12,
                    padding = 1,
                    justify = "CENTER",
                })
            end

            -- Drop legacy orange width nubs — Size W lives on the outer pad now.
            if frame._svDevWidthHandles and frame._svDevWidthHandles[widthKey] then
                frame._svDevWidthHandles[widthKey]:Hide()
            end
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

    if not frame.devStatTableWidthRegion then
        frame.devStatTableWidthRegion = CreateFrame("Frame", nil, frame)
        frame.devStatTableWidthRegion:EnableMouse(false)
    end
    if ns.EnsureDevLayoutWidthHandle and tableAnchor then
        frame.devStatTableWidthRegion = ns.EnsureDevLayoutWidthHandle(frame, "stats.table.width", tableAnchor, {
            width = 10,
            height = 28,
            gap = 2,
        })
    else
        frame.devStatTableWidthRegion:ClearAllPoints()
        frame.devStatTableWidthRegion:SetPoint("TOPLEFT", frame, "TOPLEFT", tableBaseX + gridWidth + 2, tableBaseY + 8)
        frame.devStatTableWidthRegion:SetSize(10, 28)
        frame.devStatTableWidthRegion:Show()
    end

    local tableHeightHandle
    if ns.EnsureDevLayoutHeightHandle and tableAnchor then
        tableHeightHandle = ns.EnsureDevLayoutHeightHandle(frame, "stats.table.height", tableAnchor, {
            width = 28,
            height = 10,
            gap = 2,
        })
    end
    if tableHeightHandle then
        frame.devStatTableHeightRegion = tableHeightHandle
    end

    -- Legacy stats.table grips replaced by Screen 1 / Screen 2. Do not mass-strip
    -- stats.* — titles, columns, and screens must keep their move frames.
    if frame.devStatTableMoveGrip then frame.devStatTableMoveGrip:Hide() end
    if frame.devStatTableWidthRegion then frame.devStatTableWidthRegion:Hide() end
    if frame.devStatTableHeightRegion then frame.devStatTableHeightRegion:Hide() end
    if frame.devStatTableRegion then frame.devStatTableRegion:Hide() end
    if frame.devSpecTitleWidthRegion then frame.devSpecTitleWidthRegion:Hide() end
    if frame.devOffSpecTitleWidthRegion then frame.devOffSpecTitleWidthRegion:Hide() end
    if frame._svDevStripRegions and frame._svDevStripRegions["stats.offTable"] then
        frame._svDevStripRegions["stats.offTable"]:Hide()
    end

    -- Main frame size/move AdvDev targets removed: window size follows Frames 1+2.
    if frame.devDashboardMoveRegion then frame.devDashboardMoveRegion:Hide() end
    if frame.devDashboardWidthRegion then frame.devDashboardWidthRegion:Hide() end
    if frame.devPanelGutterRegion then frame.devPanelGutterRegion:Hide() end
    -- Panel 1 children keep their own AdvDev targets (titles / dropdowns / drawer buttons).
    if frame.devSetupWidthRegion then frame.devSetupWidthRegion:Hide() end
    if frame.devSetupHeightRegion then frame.devSetupHeightRegion:Hide() end
    if frame.statVerdictSetupResizeRegions then
        for _, region in pairs(frame.statVerdictSetupResizeRegions) do
            if region and region.Hide then region:Hide() end
        end
    end
    if frame._svDevWidthHandles then
        for _, handle in pairs(frame._svDevWidthHandles) do
            if handle and handle.Hide then handle:Hide() end
        end
    end
    if frame._svDevHeightHandles then
        for _, handle in pairs(frame._svDevHeightHandles) do
            if handle and handle.Hide then handle:Hide() end
        end
    end
    -- Keep Average Progress / header text hit boxes selectable — do not mass-hide them.
end
