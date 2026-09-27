local addonName, ns = ...

local Panel = {}
ns.StatVerdictBenchmarkDrawerPanel = Panel

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

local function ActiveBenchmark()
    local profile = ActiveProfile()
    local generated = type(profile) == "table" and profile.generatedContext or nil
    return type(generated) == "table" and generated.benchmark or nil
end

-- "Blood |cffc41f3bDeath Knight|r (Deathbringer) " (with a trailing space) for the %s in a
-- level's about text, so the description names the build it is actually describing. This
-- mirrors BuildSpecDisplayTitle in SV_StatAudit.lua (same three pieces, same fallback order),
-- which is how the main panel's "Blood Death Knight / Deathbringer" title is built - specName
-- and className must come from the CONTEXT, not context.profile (the runtime profile itself
-- only carries them reliably for the live-player path; the class-color addition is new here).
-- Empty string (not nil) when spec/class are unavailable, so the about text still reads
-- cleanly without it.
local function SpecDisplayPrefix()
    local context = ns.GetActivePanelContext and ns.GetActivePanelContext() or nil
    local profile = type(context) == "table" and context.profile or nil
    local specName = (type(context) == "table" and context.specName)
        or (type(profile) == "table" and profile.specName) or nil
    local className = (type(context) == "table" and context.className)
        or (type(profile) == "table" and profile.className) or nil
    if not (specName and className) then return "" end

    local classFile = type(context) == "table" and context.classFile or nil
    -- RAID_CLASS_COLORS[classFile].colorStr already carries the alpha byte (e.g.
    -- "ffc41f3b") - matching GetClassColorPrefix in SV_Render.lua, which is why the
    -- markup here is "|c" .. colorStr, not "|cff" .. colorStr (that doubled the alpha
    -- and broke the escape sequence, showing raw hex digits as text).
    local classColor = classFile and RAID_CLASS_COLORS and RAID_CLASS_COLORS[classFile]
    local coloredClassName = classColor and classColor.colorStr
        and ("|c" .. classColor.colorStr .. className .. "|r") or className

    local heroName = nil
    if ns.GetSnapshotHeroTalentName then
        heroName = ns.GetSnapshotHeroTalentName(profile)
    end
    if (not heroName or heroName == "") and type(context) == "table" then
        heroName = context.heroTalentName
    end

    local label = specName .. " " .. coloredClassName
    if type(heroName) == "string" and heroName ~= "" then
        label = label .. " (" .. heroName .. ")"
    end
    return label .. " "
end

-- Benchmark numbers of one level for the build on screen (from the bundled Mythic+ file).
local function LevelBenchmark(levelKey)
    local profile = ActiveProfile()
    local root = ns.MythicPlusBenchmarks
    local profiles = type(root) == "table" and root.profiles or nil
    local spec = type(profile) == "table" and type(profiles) == "table" and profiles[profile.specKey] or nil
    local levels = type(spec) == "table" and spec.levels or nil
    local context = type(levels) == "table" and levels[levelKey] or nil
    return type(context) == "table" and context.benchmark or nil
end

-- Second line of a level card: how reliable that level's data is (the update date sits to
-- its right, on its own right-aligned line - see row.date - the same way row.hint sits to
-- the right of row.label).
local function CardLine(level, bench)
    if type(bench) ~= "table" then return level.meaning end
    local confidence = tostring(bench.confidence or "unknown")
    local color = confidence == "high" and "|cff33ff59" or "|cffff8000"
    return color .. confidence:sub(1, 1):upper() .. confidence:sub(2) .. " confidence|r"
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
    row.label:SetPoint("TOPLEFT", row, "TOPLEFT", 42, -9)
    row.label:SetText(level.label)

    row.hint = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.hint:SetPoint("TOPRIGHT", row, "TOPRIGHT", -12, -11)
    row.hint:SetJustifyH("RIGHT")
    row.hint:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.hint:SetText(level.hint or "")

    row.meaning = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetPoint("TOPLEFT", row.label, "BOTTOMLEFT", 0, -4)
    row.meaning:SetJustifyH("LEFT")
    row.meaning:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.meaning:SetText(level.meaning)

    -- Right-aligned under row.hint, the same way row.hint sits right-aligned under the row.
    row.date = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.date:SetPoint("TOPRIGHT", row.hint, "BOTTOMRIGHT", 0, -4)
    row.date:SetJustifyH("RIGHT")
    row.date:SetTextColor(GREY[1], GREY[2], GREY[3])
    row.date:SetText("")

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

    card.intro = AddText(card, "GameFontHighlightSmall", -46)
    card.intro:SetTextColor(GREY[1], GREY[2], GREY[3])
    card.intro:SetText("Choose which players your Mythic+ targets and popular gear are based on.")

    for index, level in ipairs(ns.GetBenchmarkLevels()) do
        local row = EnsureLevelRow(card, index, level)
        local y = ROWS_TOP - ((index - 1) * ROW_STEP)
        row:SetPoint("TOPLEFT", card, "TOPLEFT", MARGIN, y)
        row:SetPoint("TOPRIGHT", card, "TOPRIGHT", -MARGIN, y)
    end

    -- Everything below hangs from the element above it, so nothing depends on a guessed
    -- card height: status line (empty when all is well) > separator > title > description.
    local rowsBottom = ROWS_TOP - ((#ns.GetBenchmarkLevels() - 1) * ROW_STEP) - ROW_HEIGHT
    card.status = AddText(card, "GameFontHighlightSmall", rowsBottom - 8)

    card.separator = card:CreateTexture(nil, "ARTWORK")
    card.separator:SetColorTexture(LINE[1], LINE[2], LINE[3], LINE[4])
    card.separator:SetHeight(1)
    card.separator:SetPoint("TOPLEFT", card.status, "BOTTOMLEFT", 0, -10)
    card.separator:SetPoint("TOPRIGHT", card.status, "BOTTOMRIGHT", 0, -10)

    card.aboutTitle = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.aboutTitle:SetPoint("TOPLEFT", card.separator, "BOTTOMLEFT", 0, -12)
    card.aboutTitle:SetPoint("TOPRIGHT", card.separator, "BOTTOMRIGHT", 0, -12)
    card.aboutTitle:SetJustifyH("LEFT")
    card.aboutTitle:SetTextColor(GOLD[1], GOLD[2], GOLD[3])

    card.about = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.about:SetPoint("TOPLEFT", card.aboutTitle, "BOTTOMLEFT", 0, -8)
    card.about:SetPoint("TOPRIGHT", card.aboutTitle, "BOTTOMRIGHT", 0, -8)
    card.about:SetJustifyH("LEFT")
    card.about:SetWordWrap(true)
    card.about:SetSpacing(4)
    card.about:SetTextColor(0.85, 0.85, 0.85)

    frame.benchmarkDrawerCard = card
    return card
end

function Panel.Sync(card)
    if not card then return end

    local mythicPlus = ActiveGoalIsMythicPlus()
    local provenance = ns.ProfileRepository and ns.ProfileRepository.GetDataProvenance
        and ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS") or nil
    local updated = provenance and provenance.scrape or nil

    local selected = ns.GetBenchmarkLevel()
    for _, row in ipairs(card.levelRows or {}) do
        row.check:SetChecked(row.key == selected)
        PaintRow(row, row.key == selected, row.hovered == true)
        local level = ns.GetBenchmarkLevelInfo(row.key)
        local bench = mythicPlus and LevelBenchmark(row.key) or nil
        row.meaning:SetText(CardLine(level, bench))
        row.date:SetText((type(bench) == "table" and updated) and tostring(updated) or "")
    end

    local info = ns.GetBenchmarkLevelInfo(selected)
    card.aboutTitle:SetText(info.label .. " benchmark")
    card.about:SetText((info.about or ""):format(SpecDisplayPrefix()))

    local bench = mythicPlus and ActiveBenchmark() or nil
    local status, color = "", ORANGE
    if not mythicPlus then
        status, color = "This view is not Mythic+. Your Mythic+ build uses this level.", GREY
    elseif provenance and provenance.available == false then
        status = "Benchmark data is out of date. Update StatVerdict."
    elseif not bench then
        status = "No data for this build at this level."
    elseif ns.IsBenchmarkSampleSmall(bench) then
        status = "Smaller sample: results can be less stable."
    end
    card.status:SetTextColor(color[1], color[2], color[3])
    card.status:SetText(status)
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
