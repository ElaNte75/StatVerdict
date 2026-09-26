local addonName, ns = ...

local Panel = {}
ns.StatVerdictBenchmarkDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 280
local MARGIN = 14
local ROW_HEIGHT = 56
local ROW_STEP = 62
local ROWS_TOP = -96
local INFO_ROW_STEP = 18

local GOLD = { 1.0, 0.82, 0.0 }
local GREY = { 0.72, 0.72, 0.72 }
local WHITE = { 1.0, 1.0, 1.0 }
local ORANGE = { 1.0, 0.5, 0.0 }
local GREEN = { 0.20, 1.00, 0.35 }
local LINE = { 0.72, 0.74, 0.78, 0.30 }

local function Offset(key)
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function ActiveBenchmark()
    local context = ns.GetActivePanelContext and ns.GetActivePanelContext() or nil
    local profile = context and context.profile or nil
    local generated = type(profile) == "table" and profile.generatedContext or nil
    return type(generated) == "table" and generated.benchmark or nil
end

local function ActiveGoalIsMythicPlus()
    local goal = ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode() or "MYTHIC_PLUS"
    return goal == "MYTHIC_PLUS"
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

local function EnsureLevelRow(card, index, level)
    card.levelRows = card.levelRows or {}
    if card.levelRows[index] then return card.levelRows[index] end

    local row = CreateFrame("Button", nil, card, "BackdropTemplate")
    row.key = level.key
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
    row.label:SetPoint("TOPLEFT", row, "TOPLEFT", 42, -11)
    row.label:SetText(level.label)

    row.hint = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.hint:SetPoint("TOPRIGHT", row, "TOPRIGHT", -12, -13)
    row.hint:SetJustifyH("RIGHT")
    row.hint:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.hint:SetText(level.hint or "")

    row.meaning = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetPoint("TOPLEFT", row.label, "BOTTOMLEFT", 0, -5)
    row.meaning:SetJustifyH("LEFT")
    row.meaning:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.meaning:SetText(level.meaning)

    row:SetScript("OnEnter", function(self)
        self.hovered = true
        PaintRow(self, ns.GetBenchmarkLevel() == self.key, true)
    end)
    row:SetScript("OnLeave", function(self)
        self.hovered = false
        PaintRow(self, ns.GetBenchmarkLevel() == self.key, false)
    end)
    row:SetScript("OnClick", function()
        ns.SetBenchmarkLevel(level.key)
        Panel.Sync(card)
    end)

    card.levelRows[index] = row
    return row
end

local INFO_LABELS = { "Sample", "Data from" }

local function EnsureCard(frame)
    if frame.benchmarkDrawerCard then return frame.benchmarkDrawerCard end

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
    card.title:SetText("Benchmark Level")
    card.title:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    AddLine(card, -36)

    card.intro = AddText(card, "GameFontHighlightSmall", -48)
    card.intro:SetTextColor(GREY[1], GREY[2], GREY[3])
    card.intro:SetText("Choose which players your Mythic+ targets and popular gear are based on.")

    for index, level in ipairs(ns.GetBenchmarkLevels()) do
        local row = EnsureLevelRow(card, index, level)
        local y = ROWS_TOP - ((index - 1) * ROW_STEP)
        row:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
        row:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
    end

    local infoTop = ROWS_TOP - (#ns.GetBenchmarkLevels() * ROW_STEP) - 6
    AddLine(card, infoTop)

    card.infoTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.infoTitle:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, infoTop - 14)
    card.infoTitle:SetText("Current data")
    card.infoTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    card.dataRows = {}
    for index, label in ipairs(INFO_LABELS) do
        local y = infoTop - 40 - ((index - 1) * INFO_ROW_STEP)
        local row = {}
        row.label = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        row.label:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
        row.label:SetTextColor(GREY[1], GREY[2], GREY[3])
        row.label:SetText(label)
        row.value = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        row.value:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
        row.value:SetJustifyH("RIGHT")
        card.dataRows[index] = row
    end

    card.note = AddText(card, "GameFontHighlightSmall", infoTop - 40)
    local warningY = infoTop - 40 - (#INFO_LABELS * INFO_ROW_STEP) - 4
    card.warning = AddText(card, "GameFontHighlightSmall", warningY)
    card.warning:SetTextColor(ORANGE[1], ORANGE[2], ORANGE[3])

    -- A short plain-language description of the selected level sits below the data,
    -- leaving room for a two-line warning above it.
    card.about = AddText(card, "GameFontHighlightSmall", warningY - 34)
    card.about:SetTextColor(0.85, 0.85, 0.85)

    frame.benchmarkDrawerCard = card
    return card
end

function Panel.Sync(card)
    if not card then return end

    local selected = ns.GetBenchmarkLevel()
    for _, row in ipairs(card.levelRows or {}) do
        row.check:SetChecked(row.key == selected)
        PaintRow(row, row.key == selected, row.hovered == true)
    end
    card.about:SetText(ns.GetBenchmarkLevelInfo(selected).about or "")

    local mythicPlus = ActiveGoalIsMythicPlus()
    local bench = mythicPlus and ActiveBenchmark() or nil
    local provenance = ns.ProfileRepository and ns.ProfileRepository.GetDataProvenance
        and ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS") or nil

    for _, row in ipairs(card.dataRows or {}) do
        row.label:SetShown(bench ~= nil)
        row.value:SetShown(bench ~= nil)
    end

    if bench then
        card.note:SetText("")
        local confidence = tostring(bench.confidence or "unknown")
        card.dataRows[1].value:SetText(string.format(
            "%d players · %s confidence",
            tonumber(bench.sampleSize) or 0,
            confidence:sub(1, 1):upper() .. confidence:sub(2)
        ))
        if confidence == "high" then
            card.dataRows[1].value:SetTextColor(GREEN[1], GREEN[2], GREEN[3])
        else
            card.dataRows[1].value:SetTextColor(ORANGE[1], ORANGE[2], ORANGE[3])
        end
        card.dataRows[2].value:SetText(tostring(provenance and provenance.scrape or "unknown"))
        card.dataRows[2].value:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
        if ns.IsBenchmarkSampleSmall(bench) then
            card.warning:SetText("Smaller sample: results can be less stable.")
        else
            card.warning:SetText("")
        end
        return
    end

    card.warning:SetText("")
    if not mythicPlus then
        card.note:SetTextColor(GREY[1], GREY[2], GREY[3])
        card.note:SetText("The build you are viewing does not use Mythic+. This level applies to your other Mythic+ build.")
    elseif provenance and provenance.available == false then
        card.note:SetTextColor(ORANGE[1], ORANGE[2], ORANGE[3])
        card.note:SetText("Benchmark data is out of date. Update StatVerdict to get fresh Mythic+ data.")
    else
        card.note:SetTextColor(ORANGE[1], ORANGE[2], ORANGE[3])
        card.note:SetText("No data for this build at this level.")
    end
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "benchmark"
end

function Panel.SetOpen(open)
    if open then
        if ns.SetRightPanelMode then ns.SetRightPanelMode("benchmark") end
    elseif Panel.IsOpen() and ns.SetRightPanelMode then
        ns.SetRightPanelMode(nil)
    end
end

function Panel.Toggle()
    if ns.ToggleRightPanelMode then ns.ToggleRightPanelMode("benchmark") end
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
        if frame.benchmarkDrawerCard then frame.benchmarkDrawerCard:Hide() end
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
        ns.ApplyRightDrawerCardDev(card, "benchmark.card", "Benchmark drawer", "benchmark.width", DRAWER_PREFERRED_WIDTH)
    end

    Panel.Sync(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
