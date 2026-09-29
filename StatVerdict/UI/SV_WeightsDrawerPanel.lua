local addonName, ns = ...

local Panel = {}
ns.StatVerdictWeightsDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 280
local MARGIN = 14
local ROW_HEIGHT = 50
local ROW_STEP = 56
local ROWS_TOP = -84

local GOLD = { 1.0, 0.82, 0.0 }
local GREY = { 0.72, 0.72, 0.72 }
local WHITE = { 1.0, 1.0, 1.0 }
local ORANGE = { 1.0, 0.5, 0.0 }
local LINE = { 0.72, 0.74, 0.78, 0.30 }

-- Layout keys keep the old "benchmark.*" names so saved drawer positions carry over.
local function Offset(key)
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function ActiveProfile()
    local context = ns.GetActivePanelContext and ns.GetActivePanelContext() or nil
    return context and context.profile or nil
end

-- Only MEASURED reads measured weights; a build without them falls back to the
-- guide order, which the status line says.
local function MissingMeasuredData(mode)
    if mode ~= "MEASURED" then return false end
    local profile = ActiveProfile()
    return type(profile) == "table" and profile.secondaryWeights == nil
end

-- GUIDE shows the guide stat targets; a build without them shows
-- our own, which the status line says.
local function MissingGuideTargets(mode)
    if mode ~= "GUIDE" then return false end
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

local function EnsureModeRow(card, index, mode)
    card.modeRows = card.modeRows or {}
    if card.modeRows[index] then return card.modeRows[index] end

    local row = CreateFrame("Button", nil, card, "BackdropTemplate")
    row.key = mode.key
    row:SetHeight(ROW_HEIGHT)
    row:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = false,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })

    -- Only shows the tick; the whole row is the click target.
    row.check = CreateFrame("CheckButton", nil, row, "UICheckButtonTemplate")
    row.check:SetSize(24, 24)
    row.check:SetPoint("LEFT", row, "LEFT", 8, 0)
    row.check:EnableMouse(false)
    if row.check.Text then row.check.Text:Hide() end

    row.label = row:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    row.label:SetPoint("TOPLEFT", row, "TOPLEFT", 42, -9)
    row.label:SetText(mode.label)

    row.hint = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.hint:SetPoint("TOPRIGHT", row, "TOPRIGHT", -12, -11)
    row.hint:SetJustifyH("RIGHT")
    row.hint:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.hint:SetText(mode.hint or "")

    row.meaning = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetPoint("TOPLEFT", row.label, "BOTTOMLEFT", 0, -4)
    row.meaning:SetJustifyH("LEFT")
    row.meaning:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.meaning:SetText(mode.meaning)

    row:SetScript("OnEnter", function(self)
        self.hovered = true
        PaintRow(self, ns.GetWeightMode() == self.key, true)
    end)
    row:SetScript("OnLeave", function(self)
        self.hovered = false
        PaintRow(self, ns.GetWeightMode() == self.key, false)
    end)
    row:SetScript("OnClick", function()
        ns.SetWeightMode(mode.key)
        Panel.Sync(card)
    end)

    card.modeRows[index] = row
    return row
end

-- "Stat targets" group: title, the three difficulties as check options side by
-- side, easy to hard (a radio group: exactly one is ticked), then the selected
-- difficulty's explanation under them (two lines). Only Guide uses the
-- difficulty: with Measured the options are dimmed and locked.
local DESCRIPTION_SPACING = 4
local BIN_NOTE_HEIGHT = 2 * 10 + DESCRIPTION_SPACING + 2
local BIN_GROUP_HEIGHT = 38 + 2 + BIN_NOTE_HEIGHT
local BIN_DIMMED_ALPHA = 0.45
local BIN_NOT_USED = "Not used with our own measurement."
local BIN_OPTION_TOP = -16
local BIN_OPTION_WIDTH = 80
local BIN_OPTION_STEP = 82
local BIN_OPTION_HEIGHT = 22

local function EnsureBinGroup(card, above)
    local group = CreateFrame("Frame", nil, card)
    group:SetPoint("TOPLEFT", above, "BOTTOMLEFT", 0, -10)
    group:SetPoint("TOPRIGHT", above, "BOTTOMRIGHT", 0, -10)
    group:SetHeight(BIN_GROUP_HEIGHT)
    card.binGroup = group

    card.binTitle = group:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    card.binTitle:SetPoint("TOPLEFT", group, "TOPLEFT", 0, 0)
    card.binTitle:SetJustifyH("LEFT")
    card.binTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    card.binTitle:SetText("Stat targets")

    card.binNote = group:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.binNote:SetPoint("TOPLEFT", group, "TOPLEFT", 0, BIN_OPTION_TOP - BIN_OPTION_HEIGHT - 2)
    card.binNote:SetPoint("TOPRIGHT", group, "TOPRIGHT", 0, BIN_OPTION_TOP - BIN_OPTION_HEIGHT - 2)
    card.binNote:SetHeight(BIN_NOTE_HEIGHT)
    card.binNote:SetJustifyH("LEFT")
    card.binNote:SetJustifyV("TOP")
    card.binNote:SetWordWrap(true)
    card.binNote:SetSpacing(DESCRIPTION_SPACING)
    card.binNote:SetTextColor(0.85, 0.85, 0.85)

    card.binRows = {}
    for index, bin in ipairs(ns.GetStatTargetBins()) do
        local option = CreateFrame("Button", nil, group)
        option.key = bin.key
        option:SetSize(BIN_OPTION_WIDTH, BIN_OPTION_HEIGHT)
        option:SetPoint("TOPLEFT", group, "TOPLEFT", (index - 1) * BIN_OPTION_STEP, BIN_OPTION_TOP)

        -- Same tick as the mode rows; the whole option is the click target.
        option.check = CreateFrame("CheckButton", nil, option, "UICheckButtonTemplate")
        option.check:SetSize(BIN_OPTION_HEIGHT, BIN_OPTION_HEIGHT)
        option.check:SetPoint("LEFT", option, "LEFT", -3, 0)
        option.check:EnableMouse(false)
        if option.check.Text then option.check.Text:Hide() end

        option.label = option:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        option.label:SetPoint("LEFT", option.check, "RIGHT", 1, 0)
        option.label:SetText(bin.label)

        option:SetScript("OnClick", function()
            if option.dimmed then return end
            ns.SetStatTargetBin(bin.key)
            Panel.Sync(card)
        end)
        card.binRows[index] = option
    end
    return group
end

local function EnsureCard(frame)
    if frame.weightsDrawerCard then return frame.weightsDrawerCard end

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
    card.title:SetText("Weights")
    card.title:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    AddLine(card, -36)

    card.intro = AddText(card, "GameFontHighlightSmall", -46)
    card.intro:SetTextColor(GREY[1], GREY[2], GREY[3])
    card.intro:SetText("Choose how stat priorities and targets are decided.")

    local lastRow
    for index, mode in ipairs(ns.GetWeightModes()) do
        local row = EnsureModeRow(card, index, mode)
        local y = ROWS_TOP - ((index - 1) * ROW_STEP)
        row:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
        row:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
        lastRow = row
    end

    -- Everything below hangs from the element above it, so nothing depends on a guessed
    -- card height: selected mode's description > status line (empty when all is well)
    -- > separator > stat target group (with the difficulty's explanation).
    card.about = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.about:SetPoint("TOPLEFT", lastRow, "BOTTOMLEFT", 0, -8)
    card.about:SetPoint("TOPRIGHT", lastRow, "BOTTOMRIGHT", 0, -8)
    card.about:SetJustifyH("LEFT")
    card.about:SetWordWrap(true)
    card.about:SetSpacing(DESCRIPTION_SPACING)
    card.about:SetTextColor(0.85, 0.85, 0.85)

    card.status = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.status:SetPoint("TOPLEFT", card.about, "BOTTOMLEFT", 0, -4)
    card.status:SetPoint("TOPRIGHT", card.about, "BOTTOMRIGHT", 0, -4)
    card.status:SetJustifyH("LEFT")
    card.status:SetWordWrap(true)

    card.separator = card:CreateTexture(nil, "ARTWORK")
    card.separator:SetColorTexture(LINE[1], LINE[2], LINE[3], LINE[4])
    card.separator:SetHeight(1)
    card.separator:SetPoint("TOPLEFT", card.status, "BOTTOMLEFT", 0, -10)
    card.separator:SetPoint("TOPRIGHT", card.status, "BOTTOMRIGHT", 0, -10)

    EnsureBinGroup(card, card.separator)

    frame.weightsDrawerCard = card
    return card
end

function Panel.Sync(card)
    if not card then return end

    local selected = ns.GetWeightMode()
    for _, row in ipairs(card.modeRows or {}) do
        row.check:SetChecked(row.key == selected)
        PaintRow(row, row.key == selected, row.hovered == true)
    end

    -- The difficulty only applies to Guide; the choice is kept for switching back.
    local bin = ns.GetStatTargetBin()
    local dimmed = selected ~= "GUIDE"
    local binAbout = ""
    for index, option in ipairs(card.binRows or {}) do
        local checked = option.key == bin
        option.check:SetChecked(checked)
        if checked then
            option.label:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
            binAbout = ns.GetStatTargetBins()[index].about or ""
        else
            option.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
        end
        option.dimmed = dimmed
        option:EnableMouse(not dimmed)
        option:SetAlpha(dimmed and BIN_DIMMED_ALPHA or 1)
    end
    card.binNote:SetText(dimmed and BIN_NOT_USED or binAbout)

    local info = ns.GetWeightModeInfo(selected)
    card.about:SetText(info.about or "")

    local status = ""
    if MissingMeasuredData(selected) then
        status = "No measured data for this build: the guide is used."
    elseif MissingGuideTargets(selected) then
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
    local own = pad("benchmark.card")
    if (own.top or 0) ~= 0 or (own.bottom or 0) ~= 0 or (own.left or 0) ~= 0 or (own.right or 0) ~= 0 then
        return own
    end
    return pad("options.card")
end

function Panel.GetPreferredWidth(frame)
    local width = DRAWER_PREFERRED_WIDTH + SizeDelta("benchmark.width")
    if width < 200 then width = 200 end
    if width > 520 then width = 520 end
    return width
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.weightsDrawerCard then frame.weightsDrawerCard:Hide() end
        if ns.UnregisterDevLayoutRegion then ns.UnregisterDevLayoutRegion("benchmark.card") end
        return
    end

    local card = EnsureCard(frame)
    local cardX = Offset("benchmark.card")
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
    card:SetWidth(math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0)))
    card:Show()
    if ns.ApplyRightDrawerCardDev then
        ns.ApplyRightDrawerCardDev(card, "benchmark.card", "Weights drawer", "benchmark.width", DRAWER_PREFERRED_WIDTH)
    end

    Panel.Sync(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
