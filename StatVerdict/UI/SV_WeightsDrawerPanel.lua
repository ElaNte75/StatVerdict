local addonName, ns = ...

local Panel = {}
ns.StatVerdictWeightsDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local MARGIN = 14

-- The tier rows use this look.
local ROW_BACKDROP = {
    bgFile = "Interface\\Buttons\\WHITE8X8",
    edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
    tile = false,
    edgeSize = 12,
    insets = { left = 3, right = 3, top = 3, bottom = 3 },
}

local GOLD = { 1.0, 0.82, 0.0 }
local GREY = { 0.72, 0.72, 0.72 }
local WHITE = { 1.0, 1.0, 1.0 }
local ORANGE = { 1.0, 0.5, 0.0 }
local LINE = { 0.72, 0.74, 0.78, 0.30 }

-- Layout keys are "weights.*"; positions saved under the old "benchmark.*" names are moved in EnsureLayoutDB.
local function Offset(key)
    if ns.GetLayoutOffset then return ns.GetLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetLayoutSizeDelta then return ns.GetLayoutSizeDelta(key) end
    return 0
end

local function ActiveProfile()
    local context = ns.GetActivePanelContext and ns.GetActivePanelContext() or nil
    return context and context.profile or nil
end

-- A build the guide has no stat targets for shows our own (the stat totals of
-- the best-in-slot gear), which the status line says.
local function MissingGuideTargets()
    local profile = ActiveProfile()
    return type(profile) == "table" and profile.guideTargetsMissing == true
end

local function PaintRow(row, selected, hovered)
    row:SetBackdropColor(selected and 0.16 or 0.05, selected and 0.13 or 0.06, selected and 0.03 or 0.08, 0.92)
    if selected then
        row:SetBackdropBorderColor(GOLD[1], GOLD[2], GOLD[3], 0.95)
        row.label:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    else
        if hovered then
            row:SetBackdropBorderColor(0.62, 0.64, 0.70, 0.90)
        else
            row:SetBackdropBorderColor(0.32, 0.34, 0.40, 0.85)
        end
        row.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
    end
end

local function AddLine(card, y)
    local line = card:CreateTexture(nil, "ARTWORK")
    line:SetColorTexture(LINE[1], LINE[2], LINE[3], LINE[4])
    line:SetHeight(1)
    line:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
    line:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
    return line
end

local function AddText(card, template, y, justify)
    local text = card:CreateFontString(nil, "OVERLAY", template)
    text:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
    text:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
    text:SetJustifyH(justify or "LEFT")
    text:SetWordWrap(true)
    return text
end

-- The stat target tiers: three premium rows, least to most demanding (a radio
-- group: exactly one is ticked, shown gold), each with its name, a hint on the
-- right and a short meaning under the name. The whole row is the click target.
local ROW_HEIGHT = 50
local ROW_STEP = 56
local TITLE_Y = -78
local ROWS_TOP = -96
local INTRO_HEIGHT = 2 * 10 + 2
local STATUS_SPACING = 2
-- Nothing may move when the tier or the status changes: the status line gets the
-- room of its longest text (two lines) for good; an empty status just leaves space.
local STATUS_HEIGHT = 2 * 10 + 1 * STATUS_SPACING

local function SelectedChoice()
    return ns.GetTargetChoice().selected
end

local function EnsureTierRow(card, index)
    card.binRows = card.binRows or {}
    if card.binRows[index] then return card.binRows[index] end

    local row = CreateFrame("Button", nil, card, "BackdropTemplate")
    row:SetHeight(ROW_HEIGHT)
    row:SetBackdrop(ROW_BACKDROP)

    -- Only shows the tick; the whole row is the click target.
    row.check = CreateFrame("CheckButton", nil, row, "UICheckButtonTemplate")
    row.check:SetSize(24, 24)
    row.check:SetPoint("LEFT", row, "LEFT", 8, 0)
    row.check:EnableMouse(false)
    if row.check.Text then row.check.Text:Hide() end

    row.label = row:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    row.label:SetPoint("TOPLEFT", row, "TOPLEFT", 42, -9)

    row.hint = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.hint:SetPoint("TOPRIGHT", row, "TOPRIGHT", -12, -11)
    row.hint:SetJustifyH("RIGHT")
    row.hint:SetTextColor(GREY[1], GREY[2], GREY[3])

    row.meaning = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetPoint("TOPLEFT", row.label, "BOTTOMLEFT", 0, -4)
    row.meaning:SetJustifyH("LEFT")
    row.meaning:SetTextColor(GREY[1], GREY[2], GREY[3])

    row:SetScript("OnEnter", function(self)
        self.hovered = true
        PaintRow(self, SelectedChoice() == self.key, true)
    end)
    row:SetScript("OnLeave", function(self)
        self.hovered = false
        PaintRow(self, SelectedChoice() == self.key, false)
    end)
    row:SetScript("OnClick", function()
        ns.GetTargetChoice().set(row.key)
        Panel.Sync(card)
    end)

    card.binRows[index] = row
    return row
end

local function EnsureCard(frame)
    if frame.weightsDrawerCard then return frame.weightsDrawerCard end
    local guide = ns.GetGuideInfo()

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
    card.title:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, -14)
    card.title:SetText(guide.title)
    card.title:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    AddLine(card, -36)

    card.intro = AddText(card, "GameFontHighlightSmall", -46)
    card.intro:SetHeight(INTRO_HEIGHT)
    card.intro:SetJustifyV("TOP")
    card.intro:SetTextColor(GREY[1], GREY[2], GREY[3])
    card.intro:SetText(guide.intro)

    card.binTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    card.binTitle:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, TITLE_Y)
    card.binTitle:SetJustifyH("LEFT")
    card.binTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    local lastRow
    for index = 1, 3 do
        local row = EnsureTierRow(card, index)
        local y = ROWS_TOP - ((index - 1) * ROW_STEP)
        row:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
        row:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
        lastRow = row
    end

    card.status = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.status:SetPoint("TOPLEFT", lastRow, "BOTTOMLEFT", 0, -8)
    card.status:SetPoint("TOPRIGHT", lastRow, "BOTTOMRIGHT", 0, -8)
    card.status:SetHeight(STATUS_HEIGHT)
    card.status:SetJustifyH("LEFT")
    card.status:SetJustifyV("TOP")
    card.status:SetWordWrap(true)
    card.status:SetSpacing(STATUS_SPACING)

    frame.weightsDrawerCard = card
    return card
end

function Panel.Sync(card)
    if not card then return end

    local choice = ns.GetTargetChoice()
    card.binTitle:SetText(choice.title)
    for index, row in ipairs(card.binRows or {}) do
        local info = choice.options[index] or {}
        row.key = info.key
        row.label:SetText(info.label or "")
        row.hint:SetText(info.hint or "")
        row.meaning:SetText(info.meaning or "")
        local checked = info.key ~= nil and info.key == choice.selected
        row.check:SetChecked(checked)
        PaintRow(row, checked, row.hovered == true)
    end

    local status = ""
    if MissingGuideTargets() then
        status = "No guide targets for this build: our own are used."
    end
    card.status:SetTextColor(ORANGE[1], ORANGE[2], ORANGE[3])
    card.status:SetText(status)
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "weights"
end

function Panel.SetOpen(open)
    if open then
        if ns.SetRightPanelMode then ns.SetRightPanelMode("weights") end
    elseif Panel.IsOpen() and ns.SetRightPanelMode then
        ns.SetRightPanelMode(nil)
    end
end

function Panel.Toggle()
    if ns.ToggleRightPanelMode then ns.ToggleRightPanelMode("weights") end
end

-- The drawer copies the padding of the Features drawer, so its outline sits exactly
-- like the other drawers; a padding set on this drawer itself wins.
function Panel.GetCardPad()
    local function pad(key)
        return ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad(key)
            or { top = 0, bottom = 0, left = 0, right = 0 }
    end
    local own = pad("weights.card")
    if (own.top or 0) ~= 0 or (own.bottom or 0) ~= 0 or (own.left or 0) ~= 0 or (own.right or 0) ~= 0 then
        return own
    end
    return pad("options.card")
end

function Panel.GetPreferredWidth(frame)
    local width = DRAWER_PREFERRED_WIDTH + SizeDelta("weights.width")
    if width < 200 then width = 200 end
    if width > 520 then width = 520 end
    return width
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.weightsDrawerCard then frame.weightsDrawerCard:Hide() end
        return
    end

    local card = EnsureCard(frame)
    local cardX = Offset("weights.card")
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
    local cardPad = Panel.GetCardPad()
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard and frame.statProgressCard then
        ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, extra, 0, cardPad)
    elseif ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorOuterCard then
        ns.StatVerdictDashboardLayout.AnchorOuterCard(card, frame, panelX, cardPad)
    else
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", panelX, -34)
        card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", panelX, 14)
    end
    local innerWidth = math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0))
    card:SetWidth(innerWidth)
    card:Show()
    if ns.ApplyRightDrawerCard then
        ns.ApplyRightDrawerCard(card, "weights.card", "Guide drawer", "weights.width", DRAWER_PREFERRED_WIDTH)
    end

    Panel.Sync(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
