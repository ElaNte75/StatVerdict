local addonName, ns = ...

local Panel = {}
ns.StatVerdictStatProgressPanel = Panel

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

local function EnsureScreenBadge(screen, text)
    if not screen then return end
    if not screen.screenIndexBadge then
        screen.screenIndexBadge = screen:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        screen.screenIndexBadge:SetPoint("BOTTOMRIGHT", screen, "BOTTOMRIGHT", -6, 4)
        screen.screenIndexBadge:SetJustifyH("RIGHT")
        screen.screenIndexBadge:SetTextColor(0.85, 0.78, 0.35)
    end
    screen.screenIndexBadge:SetText(text or "")
    if ns.RegisterDevLayoutEditOnly then
        ns.RegisterDevLayoutEditOnly(screen.screenIndexBadge)
    end
    if not (ns.IsDevLayoutEditActive and ns.IsDevLayoutEditActive()) then
        screen.screenIndexBadge:Hide()
    end
end

local function ApplyDevOnlyBorder(region, r, g, b, a)
    if not (region and region.SetBackdropBorderColor) then return end
    r = r or 0.72
    g = g or 0.74
    b = b or 0.78
    a = a or 0.86
    if ns.RegisterDevLayoutBorderEditOnly then
        ns.RegisterDevLayoutBorderEditOnly(region, r, g, b, a)
    elseif ns.IsDevLayoutEditActive and ns.IsDevLayoutEditActive() then
        region:SetBackdropBorderColor(r, g, b, a)
    else
        region:SetBackdropBorderColor(0, 0, 0, 0)
    end
end

local function ApplyDevOnlyBadge(fontString, text)
    if not fontString then return end
    if text then fontString:SetText(text) end
    if ns.RegisterDevLayoutEditOnly then
        ns.RegisterDevLayoutEditOnly(fontString)
    end
    if not (ns.IsDevLayoutEditActive and ns.IsDevLayoutEditActive()) then
        fontString:Hide()
    end
end

-- OS card textbox (box 1): child of Screen 2. Screen 2 is child of Panel 2.
local function EnsureOSCardTextbox(frame, screen)
    if not (frame and screen) then return nil end
    local box = frame.svOSCardTextbox1
    if not box then
        box = CreateFrame("Frame", nil, screen, "BackdropTemplate")
        box:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 8,
            insets = { left = 0, right = 0, top = 2, bottom = 2 },
        })
        box:SetBackdropColor(0.018, 0.022, 0.030, 0.85)
        box:SetBackdropBorderColor(0, 0, 0, 0)
        box.boxBadge = box:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        box.boxBadge:SetPoint("BOTTOMRIGHT", box, "BOTTOMRIGHT", -6, 4)
        box.boxBadge:SetJustifyH("RIGHT")
        box.boxBadge:SetTextColor(0.85, 0.78, 0.35)
        box.boxBadge:SetText("box 1")
        frame.svOSCardTextbox1 = box
    end
    if box.GetParent and box:GetParent() ~= screen then
        box:SetParent(screen)
    end
    box:SetFrameLevel(math.max(4, (screen:GetFrameLevel() or 1) + 2))
    -- Border only while AdvDev edit mode is on.
    ApplyDevOnlyBorder(box, 0.72, 0.74, 0.78, 0.86)
    if box.boxBadge then
        ApplyDevOnlyBadge(box.boxBadge, "box 1")
    end
    return box
end

local function Clamp(value, minValue, maxValue)
    value = tonumber(value) or 0
    if value < minValue then return minValue end
    if value > maxValue then return maxValue end
    return value
end

local function SetFontSize(fontString, size)
    if not fontString then return end
    local file, _, flags = fontString:GetFont()
    if file then fontString:SetFont(file, size, flags) end
end

local SPEC_TITLE_FONT_MIN = 10
local SPEC_TITLE_FONT_FALLBACK = 15

local function GetTitleFontSize()
    if ns.GetSpecTitleFontSize then
        return ns.GetSpecTitleFontSize()
    end
    return SPEC_TITLE_FONT_FALLBACK
end

function Panel.FitTitleText(fontString, preferredSize)
    local fs = fontString
    if not fs then return end
    fs:SetWordWrap(false)
    if fs.SetNonSpaceWrap then
        fs:SetNonSpaceWrap(false)
    end
    local maxWidth = fs:GetWidth() or 0
    if maxWidth < 40 then return end

    local file, _, flags = fs:GetFont()
    if not file then return end
    local baseSize = tonumber(preferredSize) or GetTitleFontSize()
    if baseSize < SPEC_TITLE_FONT_MIN then baseSize = SPEC_TITLE_FONT_MIN end
    fs.StatVerdictTitleBaseSize = baseSize

    for size = baseSize, SPEC_TITLE_FONT_MIN, -1 do
        fs:SetFont(file, size, flags)
        local textWidth = fs:GetStringWidth() or 0
        if textWidth <= (maxWidth - 2) then
            return
        end
    end
    fs:SetFont(file, SPEC_TITLE_FONT_MIN, flags)
end

function Panel.FitSpecTitle(frame)
    local size = GetTitleFontSize()
    Panel.FitTitleText(frame and frame.subtitle, size)
end

function Panel.FitOffSpecTitle(frame)
    local size = GetTitleFontSize()
    Panel.FitTitleText(frame and frame.secondarySubtitle, size)
end

local function EnsureTitleBox(frame, storeKey)
    if not frame then return nil end
    frame._svTitleBoxes = frame._svTitleBoxes or {}
    local box = frame._svTitleBoxes[storeKey]
    if not box then
        box = CreateFrame("Frame", nil, frame)
        box:EnableMouse(false)
        frame._svTitleBoxes[storeKey] = box
    end
    return box
end

-- MS stats: child of Screen 1. Holds headers / columns / progress bars / # grid.
local function EnsureMSStatsBox(frame, screen)
    if not (frame and screen) then return nil end
    local box = frame.svMainStatContentHost
    -- Need BackdropTemplate for edit-only border (old plain hosts get replaced once).
    if box and not box.SetBackdrop then
        box:Hide()
        if box.SetParent then box:SetParent(nil) end
        frame.svMainStatContentHost = nil
        box = nil
    end
    if not box then
        box = CreateFrame("Frame", nil, screen, "BackdropTemplate")
        box:EnableMouse(false)
        frame.svMainStatContentHost = box
    end
    if box.GetParent and box:GetParent() ~= screen then
        box:SetParent(screen)
    end
    if box.SetClipsChildren then
        box:SetClipsChildren(false)
    end
    box:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 8,
        insets = { left = 0, right = 0, top = 2, bottom = 2 },
    })
    box:SetBackdropColor(0, 0, 0, 0)
    box:SetFrameLevel(math.max(4, (screen:GetFrameLevel() or 1) + 2))
    ApplyDevOnlyBorder(box, 0.72, 0.74, 0.78, 0.86)
    if not box.boxBadge then
        box.boxBadge = box:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        box.boxBadge:SetPoint("BOTTOMRIGHT", box, "BOTTOMRIGHT", -6, 4)
        box.boxBadge:SetJustifyH("RIGHT")
        box.boxBadge:SetTextColor(0.85, 0.78, 0.35)
    end
    ApplyDevOnlyBadge(box.boxBadge, "ms stats")
    return box
end

-- OS stats: child of Screen 2. Holds Off Spec headers / columns / bars.
local function EnsureOSStatsBox(frame, screen)
    if not (frame and screen) then return nil end
    local box = frame.svOffStatContentHost
    if box and not box.SetBackdrop then
        box:Hide()
        if box.SetParent then box:SetParent(nil) end
        frame.svOffStatContentHost = nil
        box = nil
    end
    if not box then
        box = CreateFrame("Frame", nil, screen, "BackdropTemplate")
        box:EnableMouse(false)
        frame.svOffStatContentHost = box
    end
    if box.GetParent and box:GetParent() ~= screen then
        box:SetParent(screen)
    end
    if box.SetClipsChildren then
        box:SetClipsChildren(false)
    end
    box:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 8,
        insets = { left = 0, right = 0, top = 2, bottom = 2 },
    })
    box:SetBackdropColor(0, 0, 0, 0)
    box:SetFrameLevel(math.max(4, (screen:GetFrameLevel() or 1) + 2))
    ApplyDevOnlyBorder(box, 0.72, 0.74, 0.78, 0.86)
    if not box.boxBadge then
        box.boxBadge = box:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        box.boxBadge:SetPoint("BOTTOMRIGHT", box, "BOTTOMRIGHT", -6, 4)
        box.boxBadge:SetJustifyH("RIGHT")
        box.boxBadge:SetTextColor(0.85, 0.78, 0.35)
    end
    ApplyDevOnlyBadge(box.boxBadge, "os stats")
    return box
end

-- Empty-state copy drawn *inside* the fixed Off Spec card (same size as stats).
local function EnsureOffSpecEmptyHintContent(card)
    if not card then return nil end
    if card.emptyTitle then return card end

    card.emptyTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.emptyTitle:SetJustifyH("LEFT")
    card.emptyTitle:SetTextColor(1.0, 0.82, 0.0)
    card.emptyTitle:SetText("Your Off Spec lives here")

    card.emptyBody = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.emptyBody:SetJustifyH("LEFT")
    card.emptyBody:SetJustifyV("TOP")
    card.emptyBody:SetTextColor(0.78, 0.78, 0.80)
    if card.emptyBody.SetWordWrap then card.emptyBody:SetWordWrap(true) end
    card.emptyBody:SetText(
        "Pick an Off Spec and Profile from the controls above.\n\n"
            .. "When Off Spec is set, this space becomes a full progress table for that build — "
            .. "weights, targets, and how close you are — right under Main Spec.\n\n"
            .. "Until then, this panel waits quietly for your second specialization."
    )
    return card
end

local function EnsureMainSpecEmptyHintContent(card)
    if not card then return nil end
    if card.emptyTitle then return card end

    card.emptyTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.emptyTitle:SetJustifyH("LEFT")
    card.emptyTitle:SetTextColor(1.0, 0.82, 0.0)
    card.emptyTitle:SetText("Your Main Spec lives here")

    card.emptyBody = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.emptyBody:SetJustifyH("LEFT")
    card.emptyBody:SetJustifyV("TOP")
    card.emptyBody:SetTextColor(0.78, 0.78, 0.80)
    if card.emptyBody.SetWordWrap then card.emptyBody:SetWordWrap(true) end
    card.emptyBody:SetText(
        "Pick a Main Spec and Profile from the controls on the left.\n\n"
            .. "When Main Spec is set, this space shows that build's progress table — "
            .. "weights, targets, and how close you are.\n\n"
            .. "Until then, this screen stays ready for your primary specialization."
    )
    return card
end

local function LayoutEmptyHintContent(card)
    if not card or not card.emptyTitle or not card.emptyBody then return end
    local pad = 14
    card.emptyTitle:ClearAllPoints()
    card.emptyTitle:SetPoint("TOPLEFT", card, "TOPLEFT", pad, -pad)
    card.emptyTitle:SetPoint("TOPRIGHT", card, "TOPRIGHT", -pad, -pad)
    card.emptyTitle:Show()

    card.emptyBody:ClearAllPoints()
    card.emptyBody:SetPoint("TOPLEFT", card.emptyTitle, "BOTTOMLEFT", 0, -10)
    card.emptyBody:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -pad, pad)
    card.emptyBody:Show()
end

local function LayoutOffSpecEmptyHintContent(card)
    LayoutEmptyHintContent(card)
end

local function HideEmptyHintContent(card)
    if not card then return end
    if card.emptyTitle then card.emptyTitle:Hide() end
    if card.emptyBody then card.emptyBody:Hide() end
end

local function HideOffSpecEmptyHintContent(card)
    HideEmptyHintContent(card)
end

-- Legacy separate hint card from older builds — always suppress.
local function EnsureOffSpecEmptyHint(frame)
    if frame and frame.offSpecEmptyHint then
        frame.offSpecEmptyHint:Hide()
    end
    return nil
end

local function GetProgressBarWidth()
    return Clamp(220 + SizeDelta("stats.column.progress.width"), 60, 900)
end

local function EnsureBorder(frame, owner, prefix)
    if frame[prefix] then return frame[prefix] end
    local border = {}
    border.top = owner:CreateTexture(nil, "BORDER")
    border.bottom = owner:CreateTexture(nil, "BORDER")
    border.left = owner:CreateTexture(nil, "BORDER")
    border.right = owner:CreateTexture(nil, "BORDER")
    for _, texture in pairs(border) do
        texture:SetColorTexture(1, 1, 1, 0.22)
    end
    frame[prefix] = border
    return border
end

local function PositionBorder(border, owner)
    border.top:ClearAllPoints()
    border.top:SetPoint("TOPLEFT", owner, "TOPLEFT", 0, 0)
    border.top:SetPoint("TOPRIGHT", owner, "TOPRIGHT", 0, 0)
    border.top:SetHeight(1)

    border.bottom:ClearAllPoints()
    border.bottom:SetPoint("BOTTOMLEFT", owner, "BOTTOMLEFT", 0, 0)
    border.bottom:SetPoint("BOTTOMRIGHT", owner, "BOTTOMRIGHT", 0, 0)
    border.bottom:SetHeight(1)

    border.left:ClearAllPoints()
    border.left:SetPoint("TOPLEFT", owner, "TOPLEFT", 0, 0)
    border.left:SetPoint("BOTTOMLEFT", owner, "BOTTOMLEFT", 0, 0)
    border.left:SetWidth(1)

    border.right:ClearAllPoints()
    border.right:SetPoint("TOPRIGHT", owner, "TOPRIGHT", 0, 0)
    border.right:SetPoint("BOTTOMRIGHT", owner, "BOTTOMRIGHT", 0, 0)
    border.right:SetWidth(1)
end

local COLUMNS = {
    { key = "priority", label = "#", relX = 10, width = 22, justify = "RIGHT" },
    { key = "stat", label = "Stat", relX = 42, width = 150, justify = "LEFT" },
    { key = "current", label = "", relX = 0, width = 1, justify = "RIGHT" },
    { key = "target", label = "", relX = 0, width = 1, justify = "RIGHT" },
    { key = "progress", label = "Progress", relX = 206, width = 220, justify = "CENTER" },
    { key = "liveModifier", label = "Weight", relX = 436, width = 58, justify = "RIGHT" },
}

local UpdateBarVisual

function Panel.GetColumns(gridX)
    local columns = {}
    for _, source in ipairs(COLUMNS) do
        local column = {}
        for key, value in pairs(source) do column[key] = value end
        column.x = gridX + source.relX
        columns[#columns + 1] = column
    end
    return columns
end

local function EnsureCard(frame)
    if frame.statProgressCard then return frame.statProgressCard end

    local card = CreateFrame("Frame", nil, frame, "BackdropTemplate")
    card:SetFrameLevel(math.max(1, frame:GetFrameLevel() - 1))
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
    if card.SetClipsChildren then
        card:SetClipsChildren(false)
    end

    -- "Stat Progress" title retired — Panel 2 needs no card label.

    -- Corner index so we can say "Frame 2" unambiguously.
    card.frameIndexBadge = card:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    card.frameIndexBadge:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -8, 6)
    card.frameIndexBadge:SetJustifyH("RIGHT")
    card.frameIndexBadge:SetTextColor(0.85, 0.78, 0.35)
    card.frameIndexBadge:SetText("Panel 2")
    card.frameIndexBadge:Hide()

    frame.statProgressCard = card
    return card
end

local function EnsureSummaryCard(frame)
    if frame.statSummaryCard then return frame.statSummaryCard end

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

    card.itemLabelY = -18
    card.itemCurrentY = -18
    card.primaryLabelY = -36
    card.primaryCurrentY = -36
    card.bisLabelY = -54
    card.bisCurrentY = -54

    frame.summaryTitle = frame.summaryTitle or frame:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    frame.summaryTitle:SetText("Character Summary")
    frame.summaryTitle:SetWidth(150)
    frame.summaryTitle:SetJustifyH("LEFT")
    frame.summaryTitle:SetTextColor(1.0, 0.82, 0.0)

    card.itemLabel = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.itemLabel:SetPoint("TOPLEFT", card, "TOPLEFT", 12, card.itemLabelY)
    card.itemLabel:SetWidth(92)
    card.itemLabel:SetJustifyH("LEFT")
    card.itemLabel:SetText("Item Level")
    card.itemLabel:SetTextColor(0.92, 0.82, 0.45)

    card.itemCurrent = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.itemCurrent:SetPoint("TOPLEFT", card, "TOPLEFT", 170, card.itemCurrentY)
    card.itemCurrent:SetWidth(46)
    card.itemCurrent:SetJustifyH("RIGHT")
    card.itemCurrent:SetTextColor(1, 1, 1)

    card.itemSlash = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.itemSlash:SetPoint("TOPLEFT", card, "TOPLEFT", 232, card.itemCurrentY)
    card.itemSlash:SetWidth(10)
    card.itemSlash:SetJustifyH("CENTER")
    card.itemSlash:SetTextColor(1, 1, 1)
    card.itemSlash:SetText("/")

    card.itemTarget = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.itemTarget:SetPoint("TOPLEFT", card, "TOPLEFT", 242, card.itemCurrentY)
    card.itemTarget:SetWidth(46)
    card.itemTarget:SetJustifyH("LEFT")
    card.itemTarget:SetTextColor(0.2, 1.0, 0.2)

    card.itemDiff = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.itemDiff:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, card.itemCurrentY)
    card.itemDiff:SetWidth(46)
    card.itemDiff:SetJustifyH("LEFT")
    card.itemDiff:SetTextColor(1, 1, 1)

    card.primaryLabel = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.primaryLabel:SetPoint("TOPLEFT", card, "TOPLEFT", 12, card.primaryLabelY)
    card.primaryLabel:SetWidth(92)
    card.primaryLabel:SetJustifyH("LEFT")
    card.primaryLabel:SetText("Primary Stat")
    card.primaryLabel:SetTextColor(0.92, 0.82, 0.45)

    card.primaryCurrent = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.primaryCurrent:SetPoint("TOPLEFT", card, "TOPLEFT", 170, card.primaryCurrentY)
    card.primaryCurrent:SetWidth(50)
    card.primaryCurrent:SetJustifyH("RIGHT")
    card.primaryCurrent:SetTextColor(1, 1, 1)

    card.bisLabel = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.bisLabel:SetPoint("TOPLEFT", card, "TOPLEFT", 12, card.bisLabelY)
    card.bisLabel:SetWidth(92)
    card.bisLabel:SetJustifyH("LEFT")
    card.bisLabel:SetText("Best in Slot")
    card.bisLabel:SetTextColor(0.92, 0.82, 0.45)

    card.bisOwned = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.bisOwned:SetPoint("TOPLEFT", card, "TOPLEFT", 170, card.bisCurrentY)
    card.bisOwned:SetWidth(28)
    card.bisOwned:SetJustifyH("RIGHT")
    card.bisOwned:SetTextColor(1, 1, 1)

    card.bisSlash = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.bisSlash:SetPoint("TOPLEFT", card, "TOPLEFT", 202, card.bisCurrentY)
    card.bisSlash:SetWidth(10)
    card.bisSlash:SetJustifyH("CENTER")
    card.bisSlash:SetTextColor(1, 1, 1)
    card.bisSlash:SetText("/")

    card.bisTotal = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.bisTotal:SetPoint("TOPLEFT", card, "TOPLEFT", 216, card.bisCurrentY)
    card.bisTotal:SetWidth(28)
    card.bisTotal:SetJustifyH("LEFT")
    card.bisTotal:SetTextColor(1, 1, 1)

    frame.statSummaryCard = card
    return card
end

local function SetCardVisible(card, visible)
    if not card then return end
    if visible then card:Show() else card:Hide() end
end

local function CreateProgressBar(parent)
    local bar = CreateFrame("StatusBar", nil, parent)
    bar:SetStatusBarTexture("Interface\\Buttons\\WHITE8X8")
    bar:SetMinMaxValues(0, 100)
    bar:SetValue(0)
    bar:SetStatusBarColor(0.18, 0.70, 0.28, 0.45)
    bar:SetFrameLevel(math.max(1, parent:GetFrameLevel() + 1))
    local bg = bar:CreateTexture(nil, "BACKGROUND")
    bg:SetAllPoints()
    bg:SetColorTexture(0.02, 0.02, 0.02, 0.94)
    bar.text = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    bar.text:SetPoint("CENTER")
    bar.text:SetTextColor(1, 1, 1)
    bar.percentText = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    bar.percentText:SetJustifyH("CENTER")
    bar.percentText:SetJustifyV("MIDDLE")
    bar.percentText:SetHeight(12)
    bar.percentText:SetTextColor(1, 1, 1)
    bar.currentText = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    bar.currentText:SetJustifyH("RIGHT")
    bar.currentText:SetJustifyV("MIDDLE")
    bar.currentText:SetHeight(12)
    bar.currentText:SetTextColor(1, 1, 1)
    bar.slashText = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    bar.slashText:SetJustifyH("CENTER")
    bar.slashText:SetJustifyV("MIDDLE")
    bar.slashText:SetHeight(12)
    bar.slashText:SetTextColor(1, 1, 1)
    bar.targetText = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    bar.targetText:SetJustifyH("LEFT")
    bar.targetText:SetJustifyV("MIDDLE")
    bar.targetText:SetHeight(12)
    bar.targetText:SetTextColor(1, 1, 1)
    bar.deltaText = bar:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    bar.deltaText:SetJustifyH("RIGHT")
    bar.deltaText:SetJustifyV("MIDDLE")
    bar.deltaText:SetHeight(12)
    bar.deltaText:SetTextColor(1, 1, 1)
    bar.targetMarker = bar:CreateTexture(nil, "OVERLAY")
    bar.targetMarker:SetColorTexture(0.66, 0.66, 0.66, 0.95)
    bar.targetMarker:SetSize(2, 12)
    EnsureBorder(bar, bar, "svBorder")
    bar:Hide()
    return bar
end

function Panel.EnsureProgressBars(frame, count)
    frame.statProgressBars = frame.statProgressBars or {}
    for index = 1, count do
        if not frame.statProgressBars[index] then
            frame.statProgressBars[index] = CreateProgressBar(frame)
        end
    end
end

function Panel.EnsureOffProgressBars(frame, count)
    frame.offStatProgressBars = frame.offStatProgressBars or {}
    for index = 1, count do
        if not frame.offStatProgressBars[index] then
            frame.offStatProgressBars[index] = CreateProgressBar(frame)
        end
    end
end

function Panel.Apply(frame, gridX, gridTopY, visibleRows, rowHeight)
    local card = EnsureCard(frame)
    if card and card.SetClipsChildren then
        card:SetClipsChildren(false)
    end
    if not card.frameIndexBadge then
        card.frameIndexBadge = card:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        card.frameIndexBadge:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -8, 6)
        card.frameIndexBadge:SetJustifyH("RIGHT")
        card.frameIndexBadge:SetTextColor(0.85, 0.78, 0.35)
    end
    card.frameIndexBadge:SetText("Panel 2")
    ApplyDevOnlyBadge(card.frameIndexBadge, "Panel 2")
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
    local summaryCard = EnsureSummaryCard(frame)
    local _, cardY = Offset("stats.card")
    local tableX, tableY = Offset("stats.table")
    local progressX, progressY = Offset("stats.column.progress")
    local progressWidth = GetProgressBarWidth()
    local cardWidth = 516 + SizeDelta("stats.width")
    if cardWidth < 220 then cardWidth = 220 end
    if cardWidth > 1200 then cardWidth = 1200 end
    card:SetWidth(cardWidth)
    -- Move / size / padding from AdvDev Stat Progress controls.
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorStatsCard then
        ns.StatVerdictDashboardLayout.AnchorStatsCard(card, frame)
    elseif ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard and frame.settingsCard then
        ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard(card, frame.settingsCard, frame, 0, cardY)
    else
        local cardLeft = (tonumber(gridX) or 252) - 6
        if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetStatsCardPlacedLeft then
            cardLeft = ns.StatVerdictDashboardLayout.GetStatsCardPlacedLeft(frame)
        end
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", cardLeft, -34 + cardY)
        card:SetSize(cardWidth, 360)
    end

    -- Whole Stat Progress card: click empty space inside to select. One border turns yellow when selected.
    if frame._svDevStripRegions and frame._svDevStripRegions["stats.card"] then
        frame._svDevStripRegions["stats.card"]:Hide()
    end
    if frame._svDevRimRegions and frame._svDevRimRegions["stats.card"] then
        for _, edge in pairs(frame._svDevRimRegions["stats.card"]) do
            if edge and edge.Hide then edge:Hide() end
        end
    end
    -- Panel chrome border is always visible (not AdvDev-only).
    if ns.UnregisterDevLayoutBorderEditOnly then
        ns.UnregisterDevLayoutBorderEditOnly(card, 0.72, 0.74, 0.78, 0.86)
    elseif card.SetBackdropBorderColor then
        card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
    end

    -- "Stat Progress" title removed — hide leftovers from older builds.
    if card.title then
        card.title:Hide()
        card.title:SetText("")
    end
    if frame._svTitleBoxes and frame._svTitleBoxes["stats.cardTitle"] then
        frame._svTitleBoxes["stats.cardTitle"]:Hide()
    end

    -- Size/move are pad-only now — no floating width/height nubs on this card.
    if frame.devStatsWidthRegion then
        frame.devStatsWidthRegion:Hide()
    end

    -- Character Summary moved to the right-side Summary drawer.
    SetCardVisible(summaryCard, false)
    if frame.summaryTitle then frame.summaryTitle:Hide() end
    if frame.devSummaryWidthRegion then frame.devSummaryWidthRegion:Hide() end
    if frame.devSummaryHeightRegion then frame.devSummaryHeightRegion:Hide() end

    if frame.subtitle then
        local x, y = Offset("stats.specTitle")
        local titlePad = Padding("stats.specTitle.pad")
        -- Width comes only from Size W (outer pad). Do not clamp by X —
        -- that made left/right move look like shrink/grow.
        local titleWidth = 490 + SizeDelta("stats.specTitle.width")
        if titleWidth < 80 then titleWidth = 80 end
        if titleWidth > 900 then titleWidth = 900 end
        local titleH = 18 + HeightDelta("stats.specTitle.height")
        if titleH < 12 then titleH = 12 end
        -- Padding = visual inset: the logical footprint (Size W/H) stays intact.
        local titleVisW = math.max(20, titleWidth - (titlePad.left or 0) - (titlePad.right or 0))
        local titleVisH = math.max(10, titleH - (titlePad.top or 0) - (titlePad.bottom or 0))

        -- Independent of Screen 1: parented to Panel 2 only.
        local titleBox = EnsureTitleBox(frame, "stats.specTitle")
        if titleBox.GetParent and titleBox:GetParent() ~= card then
            titleBox:SetParent(card)
        end
        if frame.subtitle.GetParent and frame.subtitle:GetParent() ~= card then
            frame.subtitle:SetParent(card)
        end
        titleBox:ClearAllPoints()
        titleBox:SetPoint(
            "TOPLEFT",
            card,
            "TOPLEFT",
            12 + x + (titlePad.left or 0),
            -34 + y - (titlePad.top or 0)
        )
        titleBox:SetSize(titleVisW, titleVisH)
        titleBox:SetFrameLevel((card:GetFrameLevel() or 1) + 6)
        titleBox:Show()

        frame.subtitle:ClearAllPoints()
        frame.subtitle:SetPoint("LEFT", titleBox, "LEFT", 0, 0)
        frame.subtitle:SetWidth(titleVisW)
        frame.subtitle:SetJustifyH("LEFT")
        frame.subtitle:SetWordWrap(false)
        if frame.subtitle.SetNonSpaceWrap then
            frame.subtitle:SetNonSpaceWrap(false)
        end
        Panel.FitSpecTitle(frame)

        -- Outer pad owns Size W — hide legacy width nub.
        if frame.devSpecTitleWidthRegion then frame.devSpecTitleWidthRegion:Hide() end
    end
    if frame.secondarySubtitle then
        frame.secondarySubtitle:SetJustifyH("LEFT")
        frame.secondarySubtitle:SetWordWrap(false)
        if frame.secondarySubtitle.SetNonSpaceWrap then
            frame.secondarySubtitle:SetNonSpaceWrap(false)
        end
    end
    if frame.expectedProfileKeyDebugText then
        local titleX, titleY = Offset("stats.specTitle")
        frame.expectedProfileKeyDebugText:ClearAllPoints()
        frame.expectedProfileKeyDebugText:SetPoint("TOPLEFT", card, "TOPLEFT", 12 + titleX, -56 + titleY)
        frame.expectedProfileKeyDebugText:SetWidth(math.max(180, cardWidth - 24 - titleX))
    end

    if not frame.statProgressTableCard then
        frame.statProgressTableCard = CreateFrame("Frame", nil, card, "BackdropTemplate")
    end
    local mainScreen = frame.statProgressTableCard
    if mainScreen.GetParent and mainScreen:GetParent() ~= card then
        mainScreen:SetParent(card)
    end
    mainScreen:SetFrameLevel(math.max(2, (card:GetFrameLevel() or 1) + 2))
    if mainScreen.SetClipsChildren then
        mainScreen:SetClipsChildren(false)
    end
    if mainScreen.SetBackdrop then
        mainScreen:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 8,
            insets = { left = 0, right = 0, top = 2, bottom = 2 },
        })
        mainScreen:SetBackdropColor(0.018, 0.022, 0.030, 0.72)
        -- Screen chrome is part of the product look (always visible).
        mainScreen:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
        if ns.UnregisterDevLayoutBorderEditOnly then
            ns.UnregisterDevLayoutBorderEditOnly(mainScreen, 0.72, 0.74, 0.78, 0.86)
        end
    end

    -- Screen 1: child of Panel 2. Move/Size/Pad via AdvDev. Lock binds layout to Panel 2.
    local screenPad = { top = 0, bottom = 0, left = 0, right = 0 }
    if ns.GetDevLayoutPadding then
        screenPad = ns.GetDevLayoutPadding("screen.1.pad")
    end
    local screenX, screenY = Offset("screen.1")
    local screenW = 512 + SizeDelta("screen.1.width")
    local screenH = 160 + HeightDelta("screen.1.height")
    if screenW < 120 then screenW = 120 end
    if screenW > 900 then screenW = 900 end
    if screenH < 40 then screenH = 40 end
    if screenH > 600 then screenH = 600 end
    -- Padding = visual inset: Size W/H is the logical footprint, the visible
    -- box shrinks inward and neighbors are laid out on the logical size.
    local visualW = math.max(40, screenW - (screenPad.left or 0) - (screenPad.right or 0))
    local visualH = math.max(30, screenH - (screenPad.top or 0) - (screenPad.bottom or 0))
    local screenLeft = 6 + (tonumber(screenX) or 0) + (screenPad.left or 0)
    local screenTop = -70 + (tonumber(screenY) or 0) - (screenPad.top or 0)
    mainScreen:ClearAllPoints()
    mainScreen:SetPoint("TOPLEFT", card, "TOPLEFT", screenLeft, screenTop)
    mainScreen:SetSize(visualW, visualH)
    mainScreen:Show()

    -- MS stats: child of Screen 1. Headers / columns / bars live inside this box.
    local mainHost = EnsureMSStatsBox(frame, mainScreen)
    local msKey = "screen.1.msStats"
    local msX, msY = Offset(msKey)
    local msPad = Padding(msKey .. ".pad")
    local msBaseW = math.max(80, visualW - 8)
    local msBaseH = math.max(40, visualH - 8)
    local mainHostW = msBaseW + SizeDelta(msKey .. ".width")
    local mainHostH = msBaseH + HeightDelta(msKey .. ".height")
    if mainHostW < 80 then mainHostW = 80 end
    if mainHostW > 900 then mainHostW = 900 end
    if mainHostH < 40 then mainHostH = 40 end
    if mainHostH > 600 then mainHostH = 600 end
    -- Padding = visual inset within the logical footprint.
    local mainHostVisW = math.max(40, mainHostW - (msPad.left or 0) - (msPad.right or 0))
    local mainHostVisH = math.max(30, mainHostH - (msPad.top or 0) - (msPad.bottom or 0))
    mainHost:ClearAllPoints()
    mainHost:SetPoint(
        "TOPLEFT",
        mainScreen,
        "TOPLEFT",
        4 + (tonumber(msX) or 0) + (msPad.left or 0),
        -4 + (tonumber(msY) or 0) - (msPad.top or 0)
    )
    mainHost:SetSize(mainHostVisW, mainHostVisH)
    mainHost:Show()
    -- Drop the old independent Panel-2 content host key.

    local tableH = mainHostVisH
    local fixedRows = math.max(1, math.floor((tableH - 34) / rowHeight))
    if fixedRows > 12 then fixedRows = 12 end
    frame.svFixedSlotRows = fixedRows
    frame.svStatScreenHeight = tableH

    -- Edit-only: "screen 1" badge (Lock/Unlock is on the AdvDev pad only).
    EnsureScreenBadge(mainScreen, "screen 1")


    -- Average Progress: child of MS stats (moves with Screen 1 → MS stats).
    if frame.avgProgressText then
        local avgKey = "screen.1.msStats.average"
        local x, y = Offset(avgKey)
        local avgPad = Padding(avgKey .. ".pad")
        local avgBox = EnsureTitleBox(frame, avgKey)
        if avgBox.GetParent and avgBox:GetParent() ~= mainHost then
            avgBox:SetParent(mainHost)
        end
        if frame.avgProgressText.GetParent and frame.avgProgressText:GetParent() ~= avgBox then
            frame.avgProgressText:SetParent(avgBox)
        end
        local avgW = 160 + SizeDelta(avgKey .. ".width")
        local avgH = 16 + HeightDelta(avgKey .. ".height")
        if avgW < 80 then avgW = 80 end
        if avgH < 12 then avgH = 12 end
        -- Padding = visual inset (bottom-anchored: bottom pad lifts the box).
        local avgVisW = math.max(20, avgW - (avgPad.left or 0) - (avgPad.right or 0))
        local avgVisH = math.max(10, avgH - (avgPad.top or 0) - (avgPad.bottom or 0))
        avgBox:ClearAllPoints()
        avgBox:SetPoint(
            "BOTTOMLEFT",
            mainHost,
            "BOTTOMLEFT",
            8 + (tonumber(x) or 0) + (avgPad.left or 0),
            8 + (tonumber(y) or 0) + (avgPad.bottom or 0)
        )
        avgBox:SetSize(avgVisW, avgVisH)
        avgBox:SetFrameLevel((mainHost:GetFrameLevel() or 1) + 8)
        frame.avgProgressText:ClearAllPoints()
        frame.avgProgressText:SetPoint("LEFT", avgBox, "LEFT", 0, 0)
        frame.avgProgressText:SetWidth(avgVisW)
        if frame.svMainSpecMissingMessage == true or frame.svMainSpecEmptyHint == true then
            avgBox:Hide()
            frame.avgProgressText:Hide()
            if frame._svTitleBoxes and frame._svTitleBoxes["stats.average"] then
                frame._svTitleBoxes["stats.average"]:Hide()
            end
        else
            avgBox:Show()
            frame.avgProgressText:Show()
            if frame._svTitleBoxes and frame._svTitleBoxes["stats.average"] then
                frame._svTitleBoxes["stats.average"]:Hide()
            end
        end
    end

    local showMainRows = math.min(math.max(1, tonumber(visibleRows) or 1), fixedRows)
    local mainMissing = frame.svMainSpecMissingMessage == true
    local mainEmpty = (not mainMissing) and (frame.svMainSpecEmptyHint == true)

    if frame.profileKeyDebugText then
        -- Independent of Screen 1 — do not hitch debug text to the screen frame.
        local dbgX, dbgY = Offset("stats.profileKeyDebug")
        frame.profileKeyDebugText:ClearAllPoints()
        frame.profileKeyDebugText:SetPoint("TOPLEFT", card, "TOPLEFT", 8 + dbgX, -52 + dbgY)
        frame.profileKeyDebugText:SetWidth(math.max(180, visualW))
    end

    for index, bar in ipairs(frame.statProgressBars or {}) do
        if bar.GetParent and bar:GetParent() ~= mainHost then
            bar:SetParent(mainHost)
        end
        if (not mainMissing) and (not mainEmpty) and index <= showMainRows then
            bar:ClearAllPoints()
            bar:SetPoint(
                "TOPLEFT",
                mainHost,
                "TOPLEFT",
                6 + progressX + 206,
                progressY - 21 - ((index - 1) * rowHeight)
            )
            bar:SetSize(progressWidth, 12)
            bar.svWidth = progressWidth
            if bar.border then
                for _, line in ipairs(bar.border) do
                    line:Hide()
                end
            end
            PositionBorder(bar.svBorder, bar)
            if UpdateBarVisual and bar.svHasProgress then
                UpdateBarVisual(bar)
            end
            bar:Show()
        else
            bar:Hide()
        end
    end

    if mainMissing and ns.LayoutMainSpecMissingSnapshotUI then
        HideEmptyHintContent(mainHost)
        ns.LayoutMainSpecMissingSnapshotUI(frame)
    elseif mainEmpty then
        EnsureMainSpecEmptyHintContent(mainHost)
        LayoutEmptyHintContent(mainHost)
    else
        HideEmptyHintContent(mainHost)
        -- Also clear any leftover empty copy that was parented to Screen 1.
        HideEmptyHintContent(mainScreen)
    end

    -- Screen 2 (Off Spec table): child of Panel 2, fully independent of Screen 1.
    local showOff = frame.svOffSpecVisible == true
    local missingMsg = frame.svOffSpecMissingMessage == true
    local showEmptyHint = (not showOff) and (not frame.svSuppressOffSpecHint)
    -- Defaults match the old stacked layout when Screen 1 is at its own defaults.
    local OFF_TITLE_DEFAULT_X = 10
    local OFF_TITLE_DEFAULT_Y = -242
    local OFF_SCREEN_DEFAULT_X = 6
    local OFF_SCREEN_DEFAULT_Y = -262

    local screen2Pad = Padding("screen.2.pad")
    local screen2X, screen2Y = Offset("screen.2")
    local offW = 512 + SizeDelta("screen.2.width")
    local offH = 160 + HeightDelta("screen.2.height")
    if offW < 120 then offW = 120 end
    if offW > 900 then offW = 900 end
    if offH < 40 then offH = 40 end
    if offH > 600 then offH = 600 end
    local offLeft = OFF_SCREEN_DEFAULT_X + (tonumber(screen2X) or 0) + (screen2Pad.left or 0)
    local offTop = OFF_SCREEN_DEFAULT_Y + (tonumber(screen2Y) or 0) - (screen2Pad.top or 0)
    -- Padding = visual inset: the logical footprint (offW/offH) stays intact.
    local offVisW = math.max(40, offW - (screen2Pad.left or 0) - (screen2Pad.right or 0))
    local offVisH = math.max(30, offH - (screen2Pad.top or 0) - (screen2Pad.bottom or 0))

    if not frame.offStatProgressTableCard then
        frame.offStatProgressTableCard = CreateFrame("Frame", nil, card, "BackdropTemplate")
        frame.offStatProgressTableCard:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 8,
            insets = { left = 0, right = 0, top = 2, bottom = 2 },
        })
        frame.offStatProgressTableCard:SetBackdropColor(0.018, 0.022, 0.030, 0.72)
        frame.offStatProgressTableCard:SetBackdropBorderColor(0, 0, 0, 0)
    end
    local offScreen = frame.offStatProgressTableCard
    if offScreen.GetParent and offScreen:GetParent() ~= card then
        offScreen:SetParent(card)
    end
    offScreen:SetFrameLevel(math.max(2, (card:GetFrameLevel() or 1) + 2))
    if offScreen.SetClipsChildren then
        offScreen:SetClipsChildren(false)
    end
    if offScreen.SetBackdrop then
        offScreen:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 8,
            insets = { left = 0, right = 0, top = 2, bottom = 2 },
        })
        offScreen:SetBackdropColor(0.018, 0.022, 0.030, 0.72)
        -- Screen chrome is part of the product look (always visible).
        offScreen:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)
        if ns.UnregisterDevLayoutBorderEditOnly then
            ns.UnregisterDevLayoutBorderEditOnly(offScreen, 0.72, 0.74, 0.78, 0.86)
        end
    end

    EnsureOffSpecEmptyHint(frame)
    if frame._svDevStripRegions and frame._svDevStripRegions["stats.offTable"] then
        frame._svDevStripRegions["stats.offTable"]:Hide()
    end

    -- Off Spec title: independent AdvDev target on Panel 2.
    if frame.secondarySubtitle then
        local titleX, titleY = Offset("stats.offSpecTitle")
        local titlePad = Padding("stats.offSpecTitle.pad")
        local offTitleWidth = 490 + SizeDelta("stats.offSpecTitle.width")
        if offTitleWidth < 80 then offTitleWidth = 80 end
        if offTitleWidth > 900 then offTitleWidth = 900 end
        local offTitleH = 18 + HeightDelta("stats.offSpecTitle.height")
        if offTitleH < 12 then offTitleH = 12 end

        local offTitleBox = EnsureTitleBox(frame, "stats.offSpecTitle")
        if offTitleBox.GetParent and offTitleBox:GetParent() ~= card then
            offTitleBox:SetParent(card)
        end
        if frame.secondarySubtitle.GetParent and frame.secondarySubtitle:GetParent() ~= card then
            frame.secondarySubtitle:SetParent(card)
        end
        local offTitleVisW = math.max(20, offTitleWidth - (titlePad.left or 0) - (titlePad.right or 0))
        local offTitleVisH = math.max(10, offTitleH - (titlePad.top or 0) - (titlePad.bottom or 0))
        offTitleBox:ClearAllPoints()
        offTitleBox:SetPoint(
            "TOPLEFT",
            card,
            "TOPLEFT",
            OFF_TITLE_DEFAULT_X + titleX + (titlePad.left or 0),
            OFF_TITLE_DEFAULT_Y + titleY - (titlePad.top or 0)
        )
        offTitleBox:SetSize(offTitleVisW, offTitleVisH)
        offTitleBox:SetFrameLevel((card:GetFrameLevel() or 1) + 6)
        offTitleBox:Show()

        if not showOff then
            local cur = frame.secondarySubtitle:GetText() or ""
            if cur == "" then
                frame.secondarySubtitle:SetText("Off Spec")
                frame.secondarySubtitle:SetTextColor(0.85, 0.85, 0.88)
            end
        end
        frame.secondarySubtitle:ClearAllPoints()
        frame.secondarySubtitle:SetPoint("LEFT", offTitleBox, "LEFT", 0, 0)
        frame.secondarySubtitle:SetWidth(math.max(20, offTitleWidth - (titlePad.left or 0) - (titlePad.right or 0)))
        frame.secondarySubtitle:Show()
        Panel.FitOffSpecTitle(frame)


        if frame.devOffSpecTitleWidthRegion then frame.devOffSpecTitleWidthRegion:Hide() end
    end

    offScreen:ClearAllPoints()
    offScreen:SetPoint("TOPLEFT", card, "TOPLEFT", offLeft, offTop)
    offScreen:SetSize(offVisW, offVisH)
    offScreen:Show()

    EnsureScreenBadge(offScreen, "screen 2")

    -- OS stats: child of Screen 2 (mirrors MS stats under Screen 1).
    local offHost = EnsureOSStatsBox(frame, offScreen)
    local osKey = "screen.2.osStats"
    local osX, osY = Offset(osKey)
    local osPad = Padding(osKey .. ".pad")
    local osBaseW = math.max(80, offVisW - 8)
    local osBaseH = math.max(40, offVisH - 8)
    local offHostW = osBaseW + SizeDelta(osKey .. ".width")
    local offHostH = osBaseH + HeightDelta(osKey .. ".height")
    if offHostW < 80 then offHostW = 80 end
    if offHostW > 900 then offHostW = 900 end
    if offHostH < 40 then offHostH = 40 end
    if offHostH > 600 then offHostH = 600 end
    -- Padding = visual inset within the logical footprint.
    local offHostVisW = math.max(40, offHostW - (osPad.left or 0) - (osPad.right or 0))
    local offHostVisH = math.max(30, offHostH - (osPad.top or 0) - (osPad.bottom or 0))
    offHost:ClearAllPoints()
    offHost:SetPoint(
        "TOPLEFT",
        offScreen,
        "TOPLEFT",
        4 + (tonumber(osX) or 0) + (osPad.left or 0),
        -4 + (tonumber(osY) or 0) - (osPad.top or 0)
    )
    offHost:SetSize(offHostVisW, offHostVisH)

    -- When empty-hint box 1 fills Screen 2, hide OS stats so it does not float beside it.
    if showEmptyHint then
        offHost:Hide()
    else
        offHost:Show()
    end

    -- Off Spec Average Progress: child of OS stats.
    if frame.offAvgProgressText then
        if showOff and not missingMsg and not showEmptyHint then
            local avgKey = "screen.2.osStats.average"
            local avgX, avgY = Offset(avgKey)
            local avgPad = Padding(avgKey .. ".pad")
            local offAvgBox = EnsureTitleBox(frame, avgKey)
            if offAvgBox.GetParent and offAvgBox:GetParent() ~= offHost then
                offAvgBox:SetParent(offHost)
            end
            if frame.offAvgProgressText.GetParent and frame.offAvgProgressText:GetParent() ~= offAvgBox then
                frame.offAvgProgressText:SetParent(offAvgBox)
            end
            local avgW = 160 + SizeDelta(avgKey .. ".width")
            local avgH = 16 + HeightDelta(avgKey .. ".height")
            if avgW < 80 then avgW = 80 end
            if avgH < 12 then avgH = 12 end
            -- Padding = visual inset (bottom-anchored: bottom pad lifts the box).
            local avgVisW = math.max(20, avgW - (avgPad.left or 0) - (avgPad.right or 0))
            local avgVisH = math.max(10, avgH - (avgPad.top or 0) - (avgPad.bottom or 0))
            offAvgBox:ClearAllPoints()
            offAvgBox:SetPoint(
                "BOTTOMLEFT",
                offHost,
                "BOTTOMLEFT",
                8 + (tonumber(avgX) or 0) + (avgPad.left or 0),
                8 + (tonumber(avgY) or 0) + (avgPad.bottom or 0)
            )
            offAvgBox:SetSize(avgVisW, avgVisH)
            offAvgBox:SetFrameLevel((offHost:GetFrameLevel() or 1) + 8)
            frame.offAvgProgressText:ClearAllPoints()
            frame.offAvgProgressText:SetPoint("LEFT", offAvgBox, "LEFT", 0, 0)
            frame.offAvgProgressText:SetWidth(avgVisW)
            offAvgBox:Show()
            frame.offAvgProgressText:Show()
            if frame._svTitleBoxes and frame._svTitleBoxes["stats.offAverage"] then
                frame._svTitleBoxes["stats.offAverage"]:Hide()
            end
        else
            if frame._svTitleBoxes and frame._svTitleBoxes["screen.2.osStats.average"] then
                frame._svTitleBoxes["screen.2.osStats.average"]:Hide()
            end
            if frame._svTitleBoxes and frame._svTitleBoxes["stats.offAverage"] then
                frame._svTitleBoxes["stats.offAverage"]:Hide()
            end
            frame.offAvgProgressText:Hide()
        end
    end

    local offFixedRows = math.max(1, math.floor((offHostVisH - 34) / rowHeight))
    if offFixedRows > 12 then offFixedRows = 12 end
    frame.svOffFixedSlotRows = offFixedRows
    local offShowRows = math.min(tonumber(frame.svOffSpecUsedRows) or visibleRows, offFixedRows)
    for index, bar in ipairs(frame.offStatProgressBars or {}) do
        if bar.GetParent and bar:GetParent() ~= offHost then
            bar:SetParent(offHost)
        end
        if showOff and (not missingMsg) and index <= offShowRows then
            bar:ClearAllPoints()
            bar:SetPoint(
                "TOPLEFT",
                offHost,
                "TOPLEFT",
                6 + progressX + 206,
                progressY - 21 - ((index - 1) * rowHeight)
            )
            bar:SetSize(progressWidth, 12)
            bar.svWidth = progressWidth
            if bar.border then
                for _, line in ipairs(bar.border) do
                    line:Hide()
                end
            end
            PositionBorder(bar.svBorder, bar)
            if UpdateBarVisual and bar.svHasProgress then
                UpdateBarVisual(bar)
            end
            bar:Show()
        else
            bar:Hide()
        end
    end

    if showOff and missingMsg then
        HideOffSpecEmptyHintContent(offHost)
        HideOffSpecEmptyHintContent(offScreen)
        if frame.svOSCardTextbox1 then
            HideOffSpecEmptyHintContent(frame.svOSCardTextbox1)
            frame.svOSCardTextbox1:Hide()
        end
        if ns.LayoutOffSpecMissingSnapshotUI then
            ns.LayoutOffSpecMissingSnapshotUI(frame)
        end
    elseif showEmptyHint then
        if frame.offMissingSnapshotText then frame.offMissingSnapshotText:Hide() end
        if frame.offMissingSnapshotRespec then frame.offMissingSnapshotRespec:Hide() end
        if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end
        -- Empty OS copy lives in box 1, child of Screen 2 (Screen 2 is child of Panel 2).
        HideOffSpecEmptyHintContent(offHost)
        HideOffSpecEmptyHintContent(offScreen)
        local osBox = EnsureOSCardTextbox(frame, offScreen)
        local boxX, boxY = Offset("screen.2.box.1")
        local boxPad = Padding("screen.2.box.1.pad")
        local boxW = (offVisW - 8) + SizeDelta("screen.2.box.1.width")
        local boxH = (offVisH - 8) + HeightDelta("screen.2.box.1.height")
        if boxW < 80 then boxW = 80 end
        if boxH < 40 then boxH = 40 end
        -- Padding = visual inset within the logical footprint.
        boxW = math.max(40, boxW - (boxPad.left or 0) - (boxPad.right or 0))
        boxH = math.max(30, boxH - (boxPad.top or 0) - (boxPad.bottom or 0))
        osBox:ClearAllPoints()
        osBox:SetPoint(
            "TOPLEFT",
            offScreen,
            "TOPLEFT",
            4 + (tonumber(boxX) or 0) + (boxPad.left or 0),
            -4 + (tonumber(boxY) or 0) - (boxPad.top or 0)
        )
        osBox:SetSize(boxW, boxH)
        osBox:Show()
        EnsureOffSpecEmptyHintContent(osBox)
        LayoutOffSpecEmptyHintContent(osBox)
    else
        HideOffSpecEmptyHintContent(offHost)
        HideOffSpecEmptyHintContent(offScreen)
        if frame.svOSCardTextbox1 then
            HideOffSpecEmptyHintContent(frame.svOSCardTextbox1)
            frame.svOSCardTextbox1:Hide()
        end
        if not missingMsg then
            if frame.offMissingSnapshotText then frame.offMissingSnapshotText:Hide() end
            if frame.offMissingSnapshotRespec then frame.offMissingSnapshotRespec:Hide() end
            if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end
        end
    end
end

function Panel.RefreshSummary(frame, profile, target)
    -- Bottom Character Summary card is retired; the Summary drawer that
    -- replaced it was itself replaced by the Weights drawer (formerly Benchmark) and removed.
    if frame and frame.statSummaryCard then frame.statSummaryCard:Hide() end
    if frame and frame.summaryTitle then frame.summaryTitle:Hide() end
end

function Panel.SetSummaryVisible(frame, visible)
    -- Always hidden in the old bottom slot.
    local card = frame and frame.statSummaryCard or nil
    SetCardVisible(card, false)
    if frame and frame.summaryTitle then
        frame.summaryTitle:Hide()
    end
end

local function FormatRaw(value)
    value = tonumber(value)
    if not value then return "-" end
    return tostring(math.floor(value + 0.5))
end

UpdateBarVisual = function(bar)
    if not bar then return end
    local currentValue = tonumber(bar.svCurrentValue)
    local targetValue = tonumber(bar.svTargetValue)
    local ratio = (currentValue and targetValue and targetValue > 0) and (currentValue / targetValue) or nil
    local hasCurrentWithoutTarget = currentValue and currentValue > 0 and not (targetValue and targetValue > 0)
    local currentTextValue = currentValue and FormatRaw(currentValue) or ""
    local targetTextValue = (targetValue and targetValue > 0) and FormatRaw(targetValue) or ""
    local diffTextValue = ""
    if ratio and currentValue and targetValue then
        if ratio >= 1 then
            diffTextValue = "+" .. FormatRaw(currentValue - targetValue)
        else
            diffTextValue = "-" .. FormatRaw(targetValue - currentValue)
        end
    elseif hasCurrentWithoutTarget then
        diffTextValue = "+" .. FormatRaw(currentValue)
    end

    local longestDigits = math.max(string.len(currentTextValue), string.len(targetTextValue), string.len(diffTextValue))
    local markerRatio = 0.74
    local targetFillPct = markerRatio * 100
    local overFillPct = 100 - targetFillPct
    local fillPct = 0
    if ratio then
        if ratio <= 1 then
            fillPct = ratio * targetFillPct
        else
            fillPct = targetFillPct + math.min(overFillPct, ((ratio - 1) / 0.25) * overFillPct)
        end
    elseif hasCurrentWithoutTarget then
        fillPct = 100
    end
    if fillPct < 0 then fillPct = 0 end
    if fillPct > 100 then fillPct = 100 end
    bar:SetValue(fillPct)

    local width = tonumber(bar.svWidth) or GetProgressBarWidth()
    local markerX = width * markerRatio
    if bar.targetMarker then
        bar.targetMarker:ClearAllPoints()
        bar.targetMarker:SetPoint("CENTER", bar, "LEFT", markerX, 0)
        bar.targetMarker:SetColorTexture(0.66, 0.66, 0.66, 0.95)
        bar.targetMarker:Show()
    end

    bar.text:SetText("")
    bar.text:SetTextColor(1, 1, 1)

    local fontSize = (width < 165 or longestDigits >= 5) and 9 or 10
    local currentWidth = (longestDigits >= 4) and 38 or (width < 185 and 30 or 36)
    local slashWidth = 8
    local targetWidth = (longestDigits >= 4) and 40 or (width < 185 and 30 or 34)
    local pairWidth = currentWidth + slashWidth + targetWidth + 2
    local pairRight = markerX - 4
    local pairLeft = pairRight - pairWidth
    local showPair = width >= 220 and pairLeft >= 56
    local percentLeft = 2
    local percentRight = showPair and (pairLeft - 4) or (markerX - 8)
    local percentWidth = math.max(36, percentRight - percentLeft)
    local percentCenter = percentLeft + (percentWidth / 2)

    if bar.percentText then
        bar.percentText:ClearAllPoints()
        SetFontSize(bar.percentText, fontSize)
        bar.percentText:SetPoint("CENTER", bar, "LEFT", percentCenter, 0)
        bar.percentText:SetWidth(percentWidth)
        bar.percentText:SetHeight(12)
        if ratio and targetValue and targetValue > 0 then
            if ratio > 1 then
                bar.percentText:SetText(string.format("+%.1f%%", (ratio - 1) * 100))
            else
                bar.percentText:SetText(string.format("%.1f%%", ratio * 100))
            end
        else
            bar.percentText:SetText("-")
        end
        bar.percentText:SetTextColor(1, 1, 1)
        bar.percentText:Show()
    end

    local slashX = pairLeft + currentWidth + (slashWidth / 2)
    if bar.currentText then
        bar.currentText:ClearAllPoints()
        SetFontSize(bar.currentText, fontSize)
        if showPair then
            bar.currentText:SetPoint("RIGHT", bar, "LEFT", slashX - 3, 0)
            bar.currentText:SetWidth(currentWidth)
            bar.currentText:SetHeight(12)
            bar.currentText:SetText(currentTextValue)
            bar.currentText:SetTextColor(1, 1, 1)
            bar.currentText:Show()
        else
            bar.currentText:SetText("")
            bar.currentText:Hide()
        end
    end
    if bar.slashText then
        bar.slashText:ClearAllPoints()
        SetFontSize(bar.slashText, fontSize)
        if showPair then
            bar.slashText:SetPoint("CENTER", bar, "LEFT", slashX, 0)
            bar.slashText:SetWidth(slashWidth)
            bar.slashText:SetHeight(12)
            bar.slashText:SetText((currentValue and targetValue and targetValue > 0) and "/" or "")
            bar.slashText:SetTextColor(1, 1, 1)
            bar.slashText:Show()
        else
            bar.slashText:SetText("")
            bar.slashText:Hide()
        end
    end
    if bar.targetText then
        bar.targetText:ClearAllPoints()
        SetFontSize(bar.targetText, fontSize)
        if showPair then
            bar.targetText:SetPoint("LEFT", bar, "LEFT", slashX + 3, 0)
            bar.targetText:SetWidth(targetWidth)
            bar.targetText:SetHeight(12)
            bar.targetText:SetText(targetTextValue)
            bar.targetText:SetTextColor(1, 1, 1)
            bar.targetText:Show()
        else
            bar.targetText:SetText("")
            bar.targetText:Hide()
        end
    end

    if bar.deltaText then
        bar.deltaText:ClearAllPoints()
        SetFontSize(bar.deltaText, fontSize)
        bar.deltaText:SetPoint("RIGHT", bar, "RIGHT", -2, 0)
        bar.deltaText:SetWidth(math.max((longestDigits >= 4) and 44 or 28, width - markerX - 4))
        bar.deltaText:SetHeight(12)
        bar.deltaText:SetJustifyH("RIGHT")
        bar.deltaText:SetTextColor(1, 1, 1)
        if diffTextValue ~= "" then
            bar.deltaText:SetText(diffTextValue)
            bar.deltaText:Show()
        else
            bar.deltaText:SetText("")
            bar.deltaText:Hide()
        end
    end

    if (ratio and ratio >= 1) or hasCurrentWithoutTarget then
        bar:SetStatusBarColor(0.08, 0.52, 0.18, 0.82)
    elseif ratio and ratio >= 0.90 then
        bar:SetStatusBarColor(0.62, 0.48, 0.08, 0.82)
    else
        bar:SetStatusBarColor(0.48, 0.09, 0.09, 0.82)
    end
end
function Panel.SetProgress(frame, rowIndex, progressText, currentValue, targetValue, bars, rowsStore)
    local barList = bars or frame.statProgressBars
    local bar = barList and barList[rowIndex]
    if not bar then return end
    local rows = rowsStore or frame.rows
    if rows and rows[rowIndex] and rows[rowIndex].progress then
        rows[rowIndex].progress:SetText("")
    end
    bar.svHasProgress = true
    bar.svProgressText = progressText
    bar.svCurrentValue = currentValue
    bar.svTargetValue = targetValue
    UpdateBarVisual(bar)
end

