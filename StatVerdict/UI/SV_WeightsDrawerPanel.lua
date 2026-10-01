local addonName, ns = ...

local Panel = {}
ns.StatVerdictWeightsDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local MARGIN = 14
local ROWS_TOP = -72

-- The stat target cards use this look.
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

-- Choice group under the guide text: title, three small cards in one row, least to
-- most demanding (a radio group: exactly one is ticked), then the selected card's
-- explanation under them (two lines). The cards are the guide's stat target tier
-- (ns.GetTargetChoice). Never dimmed.
local DESCRIPTION_SPACING = 4
local SEPARATOR_GAP = 8           -- status line > separator
local BIN_GROUP_GAP = 16          -- separator > group
local BIN_CHIP_TOP = -22          -- title (10px) + 12px
local BIN_CHIP_HEIGHT = 26
local BIN_CHIP_GAP = 8            -- between the cards
local BIN_CHIP_CHECK = 20
local BIN_NOTE_GAP = 8            -- cards > explanation
local BIN_NOTE_HEIGHT = 2 * 10 + DESCRIPTION_SPACING + 2
local BIN_BOTTOM_MARGIN = 4
local BIN_NOTE_TOP = BIN_CHIP_TOP - BIN_CHIP_HEIGHT - BIN_NOTE_GAP
local BIN_GROUP_HEIGHT = -BIN_NOTE_TOP + BIN_NOTE_HEIGHT + BIN_BOTTOM_MARGIN
-- Nothing may move when the card or the status changes, so the guide text and
-- the status line get the room of their longest text for good (the guide text:
-- four lines; a status: two lines); a shorter or empty text just leaves space
-- under it.
local STATUS_SPACING = 2
local ABOUT_HEIGHT = 4 * 10 + 3 * DESCRIPTION_SPACING
local STATUS_HEIGHT = 2 * 10 + 1 * STATUS_SPACING

-- The key of the card ticked now.
local function SelectedChoice()
    return ns.GetTargetChoice().selected
end

-- Three equal cards filling the given width, with even gaps between them.
local function LayoutBinChips(card, width)
    local chipWidth = (width - 2 * BIN_CHIP_GAP) / 3
    for index, chip in ipairs(card.binRows or {}) do
        chip:ClearAllPoints()
        chip:SetSize(chipWidth, BIN_CHIP_HEIGHT)
        chip:SetPoint("TOPLEFT", card.binGroup, "TOPLEFT", (index - 1) * (chipWidth + BIN_CHIP_GAP), BIN_CHIP_TOP)
    end
end

local function EnsureBinGroup(card, above)
    local group = CreateFrame("Frame", nil, card)
    group:SetPoint("TOPLEFT", above, "BOTTOMLEFT", 0, -BIN_GROUP_GAP)
    group:SetPoint("TOPRIGHT", above, "BOTTOMRIGHT", 0, -BIN_GROUP_GAP)
    group:SetHeight(BIN_GROUP_HEIGHT)
    card.binGroup = group

    card.binTitle = group:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    card.binTitle:SetPoint("TOPLEFT", group, "TOPLEFT", 0, 0)
    card.binTitle:SetJustifyH("LEFT")
    card.binTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    card.binNote = group:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.binNote:SetPoint("TOPLEFT", group, "TOPLEFT", 0, BIN_NOTE_TOP)
    card.binNote:SetPoint("TOPRIGHT", group, "TOPRIGHT", 0, BIN_NOTE_TOP)
    card.binNote:SetHeight(BIN_NOTE_HEIGHT)
    card.binNote:SetJustifyH("LEFT")
    card.binNote:SetJustifyV("TOP")
    card.binNote:SetWordWrap(true)
    card.binNote:SetSpacing(DESCRIPTION_SPACING)
    card.binNote:SetTextColor(0.85, 0.85, 0.85)

    -- Keys, labels and the title are filled in by Panel.Sync.
    card.binRows = {}
    for index = 1, 3 do
        local option = CreateFrame("Button", nil, group, "BackdropTemplate")
        option:SetBackdrop(ROW_BACKDROP)

        -- The whole card is the click target; the tick only shows the choice.
        option.check = CreateFrame("CheckButton", nil, option, "UICheckButtonTemplate")
        option.check:SetSize(BIN_CHIP_CHECK, BIN_CHIP_CHECK)
        option.check:SetPoint("LEFT", option, "LEFT", 4, 0)
        option.check:EnableMouse(false)
        if option.check.Text then option.check.Text:Hide() end

        option.label = option:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        option.label:SetPoint("LEFT", option.check, "RIGHT", 1, 0)

        option:SetScript("OnEnter", function(self)
            self.hovered = true
            PaintRow(self, SelectedChoice() == self.key, true)
        end)
        option:SetScript("OnLeave", function(self)
            self.hovered = false
            PaintRow(self, SelectedChoice() == self.key, false)
        end)
        option:SetScript("OnClick", function()
            ns.GetTargetChoice().set(option.key)
            Panel.Sync(card)
        end)
        card.binRows[index] = option
    end
    return group  -- the cards are sized to the drawer width in Panel.Apply
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
    card.intro:SetTextColor(GREY[1], GREY[2], GREY[3])
    card.intro:SetText(guide.intro)

    -- Everything below hangs from the element above it: the guide's sources >
    -- status line (empty when all is well) > separator > stat target group (with the
    -- card's explanation). Each block has a fixed height, so nothing moves on a click.
    card.about = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.about:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, ROWS_TOP)
    card.about:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, ROWS_TOP)
    card.about:SetHeight(ABOUT_HEIGHT)
    card.about:SetJustifyH("LEFT")
    card.about:SetJustifyV("TOP")
    card.about:SetWordWrap(true)
    card.about:SetSpacing(DESCRIPTION_SPACING)
    card.about:SetTextColor(0.85, 0.85, 0.85)
    card.about:SetText(guide.about)

    card.status = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.status:SetPoint("TOPLEFT", card.about, "BOTTOMLEFT", 0, -4)
    card.status:SetPoint("TOPRIGHT", card.about, "BOTTOMRIGHT", 0, -4)
    card.status:SetHeight(STATUS_HEIGHT)
    card.status:SetJustifyH("LEFT")
    card.status:SetJustifyV("TOP")
    card.status:SetWordWrap(true)
    card.status:SetSpacing(STATUS_SPACING)

    card.separator = card:CreateTexture(nil, "ARTWORK")
    card.separator:SetColorTexture(LINE[1], LINE[2], LINE[3], LINE[4])
    card.separator:SetHeight(1)
    card.separator:SetPoint("TOPLEFT", card.status, "BOTTOMLEFT", 0, -SEPARATOR_GAP)
    card.separator:SetPoint("TOPRIGHT", card.status, "BOTTOMRIGHT", 0, -SEPARATOR_GAP)

    EnsureBinGroup(card, card.separator)

    frame.weightsDrawerCard = card
    return card
end

function Panel.Sync(card)
    if not card then return end

    local choice = ns.GetTargetChoice()
    card.binTitle:SetText(choice.title)
    local binAbout = ""
    for index, option in ipairs(card.binRows or {}) do
        local info = choice.options[index] or {}
        option.key = info.key
        option.label:SetText(info.label or "")
        local checked = info.key ~= nil and info.key == choice.selected
        option.check:SetChecked(checked)
        if checked then binAbout = info.about or "" end
        PaintRow(option, checked, option.hovered == true)
    end
    card.binNote:SetText(binAbout)

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
    if card.binChipsWidth ~= innerWidth then
        card.binChipsWidth = innerWidth
        LayoutBinChips(card, innerWidth - 2 * MARGIN)
    end
    card:Show()
    if ns.ApplyRightDrawerCard then
        ns.ApplyRightDrawerCard(card, "weights.card", "Guide drawer", "weights.width", DRAWER_PREFERRED_WIDTH)
    end

    Panel.Sync(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
