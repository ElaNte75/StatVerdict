local addonName, ns = ...

local Panel = {}
ns.StatVerdictBenchmarkDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 280
local LEVEL_STEP = 50
local CHECK_LABEL_FONT_SIZE = 11

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

local function IsMythicPlus()
    local goal = ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode() or "MYTHIC_PLUS"
    return goal == "MYTHIC_PLUS"
end

local function SyncCard(card)
    if not card then return end
    local mythicPlus = IsMythicPlus()
    local selected = ns.GetBenchmarkLevel()
    for _, row in ipairs(card.levelRows or {}) do
        row.check:SetChecked(row.key == selected)
        if mythicPlus then
            row.check:Enable()
            row.check:SetAlpha(1)
        else
            row.check:Disable()
            row.check:SetAlpha(0.5)
        end
    end

    local bench = mythicPlus and ActiveBenchmark() or nil
    if not mythicPlus then
        card.info:SetText("This choice applies to Mythic+ only. Raid and PvP use their own bundled data.")
        card.info:SetTextColor(0.72, 0.72, 0.72)
        card.warning:SetText("")
        return
    end
    if not bench then
        card.info:SetText("No data for this build at this level.")
        card.info:SetTextColor(1.0, 0.5, 0.0)
        card.warning:SetText("")
        return
    end
    local provenance = ns.ProfileRepository and ns.ProfileRepository.GetDataProvenance
        and ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS") or nil
    card.info:SetText(string.format(
        "Sample: %d players · Confidence: %s\nData from: %s",
        tonumber(bench.sampleSize) or 0,
        tostring(bench.confidence or "unknown"),
        tostring(provenance and provenance.scrape or "unknown")
    ))
    card.info:SetTextColor(0.85, 0.85, 0.85)
    if ns.IsBenchmarkSampleSmall(bench) then
        card.warning:SetText("Smaller sample: results can be less stable.")
    else
        card.warning:SetText("")
    end
end

local function EnsureLevelRow(card, index, level)
    card.levelRows = card.levelRows or {}
    local row = card.levelRows[index]
    if row then return row end
    row = { key = level.key }
    row.check = CreateFrame("CheckButton", nil, card, "UICheckButtonTemplate")
    row.check:SetSize(22, 22)
    if row.check.Text then
        row.check.Text:SetText(level.label)
        row.check.Text:SetTextColor(1, 1, 1)
        local font, _, flags = row.check.Text:GetFont()
        if font then row.check.Text:SetFont(font, CHECK_LABEL_FONT_SIZE, flags) end
    end
    row.meaning = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetTextColor(0.72, 0.72, 0.72)
    row.meaning:SetJustifyH("LEFT")
    row.meaning:SetText(level.meaning)
    row.check:SetScript("OnClick", function()
        ns.SetBenchmarkLevel(level.key)
        SyncCard(card)
    end)
    card.levelRows[index] = row
    return row
end

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
    card.title:SetPoint("TOPLEFT", card, "TOPLEFT", 12, -12)
    card.title:SetText("Benchmark Level")
    card.title:SetTextColor(1.0, 0.82, 0.0)

    card.intro = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.intro:SetPoint("TOPLEFT", card, "TOPLEFT", 12, -36)
    card.intro:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, -36)
    card.intro:SetJustifyH("LEFT")
    card.intro:SetWordWrap(true)
    card.intro:SetTextColor(0.72, 0.72, 0.72)
    card.intro:SetText("Choose which players your Mythic+ targets and popular gear are based on.")

    for index, level in ipairs(ns.GetBenchmarkLevels()) do
        local row = EnsureLevelRow(card, index, level)
        local top = -84 - ((index - 1) * LEVEL_STEP)
        row.check:SetPoint("TOPLEFT", card, "TOPLEFT", 10, top)
        row.meaning:SetPoint("TOPLEFT", card, "TOPLEFT", 40, top - 24)
        row.meaning:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, top - 24)
    end

    local infoTop = -84 - (#ns.GetBenchmarkLevels() * LEVEL_STEP) - 8
    card.info = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.info:SetPoint("TOPLEFT", card, "TOPLEFT", 12, infoTop)
    card.info:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, infoTop)
    card.info:SetJustifyH("LEFT")
    card.info:SetWordWrap(true)

    card.warning = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.warning:SetPoint("TOPLEFT", card.info, "BOTTOMLEFT", 0, -8)
    card.warning:SetPoint("TOPRIGHT", card.info, "BOTTOMRIGHT", 0, -8)
    card.warning:SetJustifyH("LEFT")
    card.warning:SetWordWrap(true)
    card.warning:SetTextColor(1.0, 0.5, 0.0)

    frame.benchmarkDrawerCard = card
    return card
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
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad("benchmark.card")
        or { top = 0, bottom = 0, left = 0, right = 0 }
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

    SyncCard(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
