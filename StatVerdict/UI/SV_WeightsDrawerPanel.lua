local addonName, ns = ...

local Panel = {}
ns.StatVerdictWeightsDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local MARGIN = 14

-- The Auto and tier rows use this look.
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

-- Two blocks of premium rows. First the spec the choice is for: Main Spec or Off Spec
-- (a radio pair, the build the whole window shows; it changes the view only, never
-- the game's spec). Then, for that spec, Auto and the stat target tiers, least to most
-- demanding (a radio group: exactly one is ticked, shown gold, never two), each with its
-- name, a hint on the right and a short meaning under the name. The whole row is the click
-- target. Auto's meaning line tells where the character stands. Each spec keeps its own
-- choice.
local SPEC_ROW_HEIGHT = 24
local SPEC_ROW_STEP = 26
local SPEC_TITLE_Y = -76
local SPEC_ROWS_TOP = -92
local ROW_COUNT = 4
local ROW_HEIGHT = 38
local ROW_STEP = 42
local TITLE_Y = -152
local ROWS_TOP = -170
local INTRO_HEIGHT = 2 * 10 + 2
local STATUS_SPACING = 2
-- Nothing may move when the tier or the status changes: the status line gets the
-- room of its longest text (two lines) for good; an empty status just leaves space.
local STATUS_HEIGHT = 2 * 10 + 1 * STATUS_SPACING

-- The spec key of the build the drawer shows (nil before a build exists).
local function ActiveSpecKey()
    local profile = ActiveProfile()
    return type(profile) == "table" and profile.specKey or nil
end

local function SelectedChoice()
    return ns.GetTargetChoice(ActiveSpecKey()).selected
end

-- "Blood Death Knight" for a build's profile.
local function SpecName(profile)
    if type(profile) ~= "table" then return nil end
    local parts = {}
    if profile.specName and profile.specName ~= "" then parts[#parts + 1] = tostring(profile.specName) end
    if profile.className and profile.className ~= "" then parts[#parts + 1] = tostring(profile.className) end
    return #parts > 0 and table.concat(parts, " ") or nil
end

-- The Main Spec / Off Spec builds: { main = name, off = name or nil, view = "MAIN" | "OFF" }.
local function SpecChoice()
    local primary, secondary
    if ns.GetTooltipEvaluationContexts then primary, secondary = ns.GetTooltipEvaluationContexts() end
    local offReady = type(secondary) == "table" and type(secondary.profile) == "table"
    local view = ns.GetStatAuditActiveView and ns.GetStatAuditActiveView() or "MAIN"
    if view ~= "OFF" or not offReady then view = "MAIN" end
    return {
        main = SpecName(type(primary) == "table" and primary.profile or nil),
        off = offReady and SpecName(secondary.profile) or nil,
        offReady = offReady,
        view = view,
    }
end

local function EnsureSpecRow(card, index, view, label)
    card.specRows = card.specRows or {}
    if card.specRows[index] then return card.specRows[index] end

    local row = CreateFrame("Button", nil, card, "BackdropTemplate")
    row.view = view
    row:SetHeight(SPEC_ROW_HEIGHT)
    row:SetBackdrop(ROW_BACKDROP)

    row.check = CreateFrame("CheckButton", nil, row, "UICheckButtonTemplate")
    row.check:SetSize(20, 20)
    row.check:SetPoint("LEFT", row, "LEFT", 6, 0)
    row.check:EnableMouse(false)
    if row.check.Text then row.check.Text:Hide() end

    row.label = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.label:SetPoint("LEFT", row.check, "RIGHT", 4, 0)
    row.label:SetText(label)

    row.hint = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.hint:SetPoint("RIGHT", row, "RIGHT", -10, 0)
    row.hint:SetJustifyH("RIGHT")
    row.hint:SetTextColor(GREY[1], GREY[2], GREY[3])

    row:SetScript("OnEnter", function(self)
        self.hovered = true
        PaintRow(self, self.selected == true, not self.disabled)
    end)
    row:SetScript("OnLeave", function(self)
        self.hovered = false
        PaintRow(self, self.selected == true, false)
    end)
    row:SetScript("OnClick", function(self)
        if self.disabled then return end
        if ns.SetStatAuditActiveView then ns.SetStatAuditActiveView(self.view) end
        if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
        Panel.Sync(card)
    end)

    card.specRows[index] = row
    return row
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
    row.label:SetPoint("TOPLEFT", row, "TOPLEFT", 42, -6)

    row.hint = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.hint:SetPoint("TOPRIGHT", row, "TOPRIGHT", -12, -8)
    row.hint:SetJustifyH("RIGHT")
    row.hint:SetTextColor(GREY[1], GREY[2], GREY[3])

    row.meaning = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetPoint("TOPLEFT", row.label, "BOTTOMLEFT", 0, -3)
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
        ns.GetTargetChoice(ActiveSpecKey()).set(row.key)
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

    card.specTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    card.specTitle:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, SPEC_TITLE_Y)
    card.specTitle:SetJustifyH("LEFT")
    card.specTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    card.specTitle:SetText("Spec")

    for index, info in ipairs({ { "MAIN", "Main Spec" }, { "OFF", "Off Spec" } }) do
        local row = EnsureSpecRow(card, index, info[1], info[2])
        local y = SPEC_ROWS_TOP - ((index - 1) * SPEC_ROW_STEP)
        row:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
        row:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
    end

    card.binTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    card.binTitle:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, TITLE_Y)
    card.binTitle:SetJustifyH("LEFT")
    card.binTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    local lastRow
    for index = 1, ROW_COUNT do
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

    -- Which build is shown: the radio pair of Main Spec / Off Spec.
    local specs = SpecChoice()
    for _, row in ipairs(card.specRows or {}) do
        local isOff = row.view == "OFF"
        local name = specs.main
        if isOff then name = specs.off end
        row.disabled = isOff and not specs.offReady
        row.selected = (not row.disabled) and specs.view == row.view
        row.hint:SetText(name or (isOff and "Not set up" or ""))
        row.check:SetChecked(row.selected)
        PaintRow(row, row.selected, row.hovered == true and not row.disabled)
        row:SetAlpha(row.disabled and 0.45 or 1)
    end

    local choice = ns.GetTargetChoice(ActiveSpecKey())
    card.binTitle:SetText(choice.title)
    for index, row in ipairs(card.binRows or {}) do
        local info = choice.options[index] or {}
        row.key = info.key
        row.label:SetText(info.label or "")
        row.hint:SetText(info.hint or "")
        local meaning = info.meaning or ""
        if info.auto then meaning = ns.GetAutoTierSummary(ActiveProfile()) or meaning end
        row.meaning:SetText(meaning)
        local checked = info.key ~= nil and info.key == choice.selected
        row.check:SetChecked(checked)
        PaintRow(row, checked, row.hovered == true)
    end

    -- The status: a build without guide targets (orange), and the one-off notice
    -- after Auto moved the character up a tier (gold).
    local lines = {}
    if MissingGuideTargets() then
        lines[#lines + 1] = "No guide targets for this build: our own are used."
    end
    local notice = choice.selected == "auto" and ns.GetAutoTierNotice(ActiveProfile()) or nil
    if notice then lines[#lines + 1] = notice end
    card.noticeShown = notice ~= nil
    if MissingGuideTargets() then
        card.status:SetTextColor(ORANGE[1], ORANGE[2], ORANGE[3])
    else
        card.status:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    end
    card.status:SetText(table.concat(lines, "\n"))
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
        local closed = frame.weightsDrawerCard
        if closed then
            -- The move-up notice was seen: it goes when the drawer closes.
            if closed.noticeShown then
                local repository = ns.ProfileRepository
                if repository and repository.ClearAutoNotice then repository.ClearAutoNotice() end
                closed.noticeShown = false
            end
            closed:Hide()
        end
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
