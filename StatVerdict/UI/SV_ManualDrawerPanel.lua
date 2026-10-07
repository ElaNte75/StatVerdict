local addonName, ns = ...

local Panel = {}
ns.StatVerdictManualDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local SCROLL_TOP = -40  -- under the title chip (12 + 24 high), with a little air
local SIZE_ROW_HEIGHT = 34 -- the text size slider at the bottom of the card: its name and value, the slider under them
local SIZE_ROW_BOTTOM = 12
local CLOSE_BUTTON_ROOM = 78 -- a floating panel has its Close button at the bottom right: the slider stops before it
local SCROLL_BOTTOM_PAD = SIZE_ROW_BOTTOM + SIZE_ROW_HEIGHT + 8

-- How far above the card's bottom the text stops: the slider is there.
local function ScrollBottomPad(card)
    return SCROLL_BOTTOM_PAD
end

-- The Manual's own text size, in percent: 100% is the size it always had. Remembered; only the Manual uses it.
local TEXT_SCALE_MIN, TEXT_SCALE_MAX, TEXT_SCALE_STEP = 100, 200, 25

function ns.GetManualTextScalePercent()
    local db = _G.StatVerdictDB
    local percent = type(db) == "table" and tonumber(db.manualTextScale) or 100
    return math.max(TEXT_SCALE_MIN, math.min(TEXT_SCALE_MAX, percent))
end

local function TextScale()
    return ns.GetManualTextScalePercent() / 100
end

-- Puts a text in its base size times the scale (the base size is the one the font object gave it).
local function ApplyTextScale(fontString, scale)
    if not fontString.svBaseSize then
        local font, size, flags = fontString:GetFont()
        fontString.svBaseFont, fontString.svBaseSize, fontString.svBaseFlags = font, tonumber(size) or 12, flags
    end
    if fontString.svBaseFont then
        fontString:SetFont(fontString.svBaseFont, fontString.svBaseSize * scale, fontString.svBaseFlags)
    end
end
local SCROLL_SIDE_PAD = 10
local SCROLLBAR_WIDTH = 18

local function Offset(key)
    if ns.GetLayoutOffset then return ns.GetLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetLayoutSizeDelta then return ns.GetLayoutSizeDelta(key) end
    return 0
end

local MANUAL_LINES = {
    { title = true, text = "Manual" },
    { text = "StatVerdict compares gear against a virtual loadout — a saved picture of the gear you want to play, not necessarily what you are wearing right now." },
    { text = "Verdict Points are deterministic heuristic points. They are not simulated DPS, healing, survival, or a percentage performance gain." },
    { gap = true },
    { title = true, text = "Stat Progress bars" },
    { text = "Each row in Stat Progress shows one tracked stat for your build: how much you have now versus the target for your chosen goal (Mythic+, Raid, or PvP)." },
    { text = "The vertical line on the bar is 100% of that target. Fill to the left of the line is progress toward the goal. Fill past the line is surplus — how far you are over target." },
    { text = "The percentage on the bar is your progress (for example 87.0%). When you are over target it shows as a plus percent (for example +12.0%). Wider bars also show current / target numbers, and the amount you are short or over." },
    { gap = true },
    { title = true, text = "Weights (live modifiers)" },
    { text = "The Weight column is StatVerdict's live modifier for that secondary — how much one point is worth right now relative to your other secondaries and how far you are from target." },
    { text = "Weights start from your profile priorities, then adjust automatically: stats you are still missing get more weight; stats you have already met (or pushed past a soft cap) get less." },
    { text = "Upgrade scoring still treats item level and your primary stat (Strength / Agility / Intellect) as fixed top anchors. Secondaries then redistribute inside a capped budget with live pressure — when a top secondary needs a boost, weight is taken from the lowest priority first (#4, then #3), without zeroing lower stats." },
    { text = "Tiny primary gaps (a few points) can still lose to clearly better top-two secondaries on a near-equal item level piece. Large primary or item-level drops never get that exception." },
    { text = "Trinkets are scored differently: a goal-specific reference tier/rank can add reference value (from the guides' tier list). StatVerdict does not calculate proc or on-use performance itself." },
    { text = "Rings and necks often have no primary — their top secondary gets an extra boost to stand in for that missing Strength / Agility / Intellect." },
    { gap = true },
    { title = true, text = "How the virtual loadout works" },
    { text = "If you are currently playing the same specialization StatVerdict is evaluating, your worn gear is the truth. The loadout updates automatically when you swap items." },
    { text = "For another specialization, Approve can fill its virtual gear baseline without equipping the items. Trustworthy live weights still require one capture while that specialization is active; until then StatVerdict shows that stats are not captured and produces no verdict." },
    { gap = true },
    { title = true, text = "Approve (bags)" },
    { text = "Approve saves an item into a specialization's virtual loadout so future comparisons use that baseline — the gear you intend to play — instead of whatever you happen to be wearing." },
    { text = "Alt + Right-Click on a bag item — approve into the Main Spec loadout. Clicking an already saved item removes it again (the slot reverts to your worn gear)." },
    { text = "Alt + Left-Click on a bag item — same toggle for the Off Spec loadout (when an Off Spec is set)." },
    { text = "When you switch specialization, the pieces you marked for that spec are put on (only those in your bags; every other slot keeps what you wear). It never happens in combat, and a line in the chat says what was put on." },
    { gap = true },
    { title = true, text = "Panels" },
    { text = "Best in Slot — the best-in-slot items for the active build (Mythic+, Raid or PvP), with your progress." },
    { text = "Hover a Best in Slot item to see it at its recommended item level, with the recommended gems and enchant." },
    { text = "Options chooses what that hover shows. Best in Slot tooltip: our compact tooltip; under it, Gems and enchants adds the recommended gems and enchant. Best in Slot: game tooltip: the game's own item tooltip. Only one of the two tooltips can be on: ticking one turns the other off. With both unticked, hovering shows nothing. The trinket list works the same way: Ranked Trinkets tooltip is our compact tooltip (name, level, stats), and under it Trinket effect adds the trinket's effect; or Ranked Trinkets: game tooltip." },
    { text = "The Best in Slot and Ranked Trinkets tooltips end with Where to find: the dungeon or raid and the boss the item drops from, when the game's Adventure Journal lists it. An item the journal does not list (crafted, vendor, PvP, the Great Vault, the Catalyst or an event) says Other source, with no item level of its own claimed." },
    { text = "Ranked Trinkets — ranked trinket list for the active build." },
    { text = "Options — yes / no choices: Upgrade Arrow and MS / OS Labels on bag items, Stat Ranks on tooltips, the Best in Slot and Ranked Trinkets tooltips, and the window's own: Always on top, Compact Mode and Auto-hide the left side and Window size (see Window and Compact Mode below). Hover a choice to see what it does." },
    { text = "Guide — the stat priorities, Best in Slot lists and stat targets are copied from the guides, unchanged. Pick Auto (the default: the tier follows your own stats and moves up when you cover about 90% of it) or one fixed tier: Tier 1, Tier 2 or Tier 3 (the most demanding). Main Spec and Off Spec each keep their own choice: with an Off Spec set up, click the checkbox in front of a spec's name in the main window to look at that spec (this changes the view only, never your game spec). The tier in use is shown in the title bar; Best in Slot and trinkets follow it." },
    { text = "On Best in Slot and Ranked Trinkets, click the title chip to switch Main Spec / Off Spec. Both panels share that selection." },
    { text = "Only one side panel can be open at a time." },
    { text = "This Manual has its own Text size slider at the bottom (100% to 200%): the text and the window get bigger together, and the Manual remembers the size you chose. It does not change the size of the StatVerdict window." },
    { gap = true },
    { title = true, text = "Window and Compact Mode" },
    { text = "Options → Always on top keeps this window in front of everything. Off (the default), it is in front while you work in it and steps behind as soon as you click anywhere else (another add-on, the chat, a game window or the world); click it to bring it back." },
    { text = "Options → Window size is a slider from 100% down to 75% (it starts at 85%). It makes the whole window, and the panels that belong to it, smaller, in the normal window and in Compact Mode, and each remembers its own size. The size is applied when you let go of the slider." },
    { text = "Options → Compact Mode makes the window smaller: one stat table at a time, with Guide, Best in Slot, Ranked Trinkets and Options in a row under the table. With an Off Spec set, Show Off Spec / Show Main Spec under the dropdowns switches the table. The heading of the build in view (Main Spec Build or Off Spec Build) is gold, the other white." },
    { text = "In Compact Mode the panels open as windows of their own, titled StatVerdict Guide, StatVerdict Options and so on. Drag one by its title or an empty spot, close it with Close at its bottom right; the next one opens where you left it. The Manual opens from the Manual button next to Close in Options." },
    { text = "Options → Auto-hide the left side (part of Compact Mode) folds the Main Spec / Off Spec builds behind a thin strip at the window's left edge, and the window gets narrower. Move the mouse onto the strip to show the builds over the table; they fold away again when the mouse leaves (not while a menu is open). The table's title then ends with a small (Main Spec) or (Off Spec)." },
    { gap = true },
    { title = true, text = "Item tooltips" },
    { text = "The verdict on an item's tooltip names its build, Main Spec or Off Spec. The Main Spec comes first; the Off Spec shows when the item is an upgrade for it alone." },
    { text = "Stat Ranks: every secondary stat on an item tooltip shows its place in the guide's order for the build in view (for example +73 Critical Strike #1 MS). Stats the guide calls roughly equal share a number. Switch it off in Options." },
    { text = "Hold Alt over an item to see the other build for as long as you hold it: the ranks and the whole verdict (with an Off Spec set). A gold line says when the other build gains from the item too. Over an item in your bags Alt is the marking key instead (Alt-Left-Click / Alt-Right-Click), so it changes nothing there." },
    { text = "Hold Ctrl over an item the Catalyst can turn into your Best in Slot set piece to preview that piece at the same item level. Shift is the game's own comparison." },
    { text = "A StatVerdict Warning on a tooltip means the Catalyst would turn that piece (the one you wear, or one in your bags or at a vendor that is no upgrade as it is) into your Best in Slot set piece, and the points that gain is worth over what you wear in that slot." },
    { text = "Marks on the character sheet: BIS on a piece you wear that is already Best in Slot, CAT on a piece the Catalyst would turn into your Best in Slot set piece. Switch them off in Options (Marks on the character sheet)." },
    { gap = true },
    { title = true, text = "Bag markers" },
    { text = "MS / OS membership labels appear only on bag items. Upgrade arrows can also appear on quest rewards, merchants, and the Adventure Guide." },
    { text = "Green arrow — upgrade vs your comparison baseline." },
    { text = "MS / OS — item is already saved in your Main / Off Spec virtual loadout." },
    { text = "Options → Upgrade Arrow on bag items and MS / OS Labels on bag items control the bag arrows and labels. It does not disable quest, merchant, or Adventure Guide upgrade arrows." },
    { gap = true },
    { title = true, text = "Limits and data" },
    { text = "StatVerdict models item level, primary and secondary stats, actual gem stats, physical weapon DPS, tank armor/stamina, and validated goal-specific references." },
    { text = "It does not model encounter mechanics, execution, most procs/on-use effects, embellishment power, tertiary value, set-bonus magnitude, or upgrade-currency cost." },
    { text = "Bundled profile data has freshness and quality checks. After about two months without an update it counts as out of date, and if it is also incomplete or mismatched to your goal, StatVerdict shows an unavailable state instead of guessing: update StatVerdict to the latest version to get new data." },
}

local function EnsureCard(frame)
    if frame.manualDrawerCard then return frame.manualDrawerCard end

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
    card:EnableMouse(true)

    -- The title: the chip every tab shares (full width of the card, text centred).
    card.title = ns.PlaceTabTitleChip(card, "Manual").label

    local scrollName = "StatVerdictManualScroll"
    local scroll = CreateFrame("ScrollFrame", scrollName, card, "UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, SCROLL_TOP)
    scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -(SCROLL_SIDE_PAD + SCROLLBAR_WIDTH), ScrollBottomPad(card))
    scroll:EnableMouse(true)

    local child = CreateFrame("Frame", nil, scroll)
    child:SetSize(100, 100)
    scroll:SetScrollChild(child)

    card.scroll = scroll
    card.scrollChild = child
    card.lines = {}

    if type(scroll.EnableMouseWheel) == "function" then
        scroll:EnableMouseWheel(true)
    end
    scroll:SetScript("OnMouseWheel", function(self, delta)
        local current = self:GetVerticalScroll() or 0
        local maxScroll = 0
        if self.GetVerticalScrollRange then
            maxScroll = self:GetVerticalScrollRange() or 0
        end
        local nextScroll = current - (delta * 28)
        if nextScroll < 0 then nextScroll = 0 end
        if nextScroll > maxScroll then nextScroll = maxScroll end
        self:SetVerticalScroll(nextScroll)
    end)

    -- The Manual's own text size: the text and the window grow together; applied when the mouse lets go of the slider.
    card.sizeRow = ns.CreateStepSlider(card, {
        label = "Text size",
        tip = "Makes the Manual's text, and its window, bigger: from 100% up to 200%. It is remembered, and only the Manual uses it.",
        min = TEXT_SCALE_MIN, max = TEXT_SCALE_MAX, step = TEXT_SCALE_STEP,
        get = function() return ns.GetManualTextScalePercent() end,
        commit = function(value)
            _G.StatVerdictDB = _G.StatVerdictDB or {}
            _G.StatVerdictDB.manualTextScale = value
            if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
        end,
    })

    frame.manualDrawerCard = card
    return card
end

local function LayoutManualContent(card, contentWidth)
    local child = card.scrollChild
    local scale = TextScale()
    local y = -4 * scale
    local lineIndex = 0
    local textWidth = math.max(60, contentWidth - 8)

    for _, entry in ipairs(MANUAL_LINES) do
        if entry.gap then
            y = y - 10 * scale
        elseif entry.text and not entry.title then
            lineIndex = lineIndex + 1
            local fs = card.lines[lineIndex]
            if not fs then
                fs = child:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
                card.lines[lineIndex] = fs
            end
            fs:ClearAllPoints()
            fs:SetPoint("TOPLEFT", child, "TOPLEFT", 2, y)
            fs:SetWidth(textWidth)
            fs:SetJustifyH("LEFT")
            fs:SetWordWrap(true)
            fs:SetNonSpaceWrap(true)
            fs:SetTextColor(0.78, 0.78, 0.78)
            ApplyTextScale(fs, scale)
            fs:SetText(entry.text)
            fs:Show()
            local height = fs:GetStringHeight() or 12
            if height < 12 * scale then height = 12 * scale end
            y = y - (height + 5 * scale)
        elseif entry.title and entry.text and entry.text ~= "Manual" then
            lineIndex = lineIndex + 1
            local fs = card.lines[lineIndex]
            if not fs then
                fs = child:CreateFontString(nil, "OVERLAY", "GameFontNormal")
                card.lines[lineIndex] = fs
            end
            fs:ClearAllPoints()
            fs:SetPoint("TOPLEFT", child, "TOPLEFT", 2, y)
            fs:SetWidth(textWidth)
            fs:SetJustifyH("LEFT")
            fs:SetTextColor(1.0, 0.82, 0.0)
            ApplyTextScale(fs, scale)
            fs:SetText(entry.text)
            fs:Show()
            y = y - 18 * scale
        end
    end
    for i = lineIndex + 1, #(card.lines) do
        card.lines[i]:Hide()
    end

    local contentHeight = math.max(40, -y + 8 * scale)
    child:SetSize(contentWidth, contentHeight)
    return contentHeight
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "manual"
end

-- Its own width times the text size (the text and the window grow together), never wider than most of the screen.
function Panel.GetPreferredWidth(frame)
    local width = (DRAWER_PREFERRED_WIDTH + SizeDelta("manual.width")) * TextScale()
    local screenWidth = UIParent and UIParent.GetWidth and tonumber(UIParent:GetWidth()) or 1920
    return math.min(width, screenWidth * 0.8)
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.manualDrawerCard then frame.manualDrawerCard:Hide() end
        return
    end

    local card = EnsureCard(frame)
    local layout = ns.StatVerdictDashboardLayout
    local cardX = Offset("manual.card")
    local cardWidth = Panel.GetPreferredWidth(frame)
    if layout and layout.GetRightPanelWidth then
        cardWidth = layout.GetRightPanelWidth(frame) or cardWidth
    end
    -- A window of its own grows in height with the text size too (as far as the screen allows).
    if layout and layout.IsCompact and layout.IsCompact() and layout.GetFloatingPanelHeight then
        local screenHeight = UIParent and UIParent.GetHeight and tonumber(UIParent:GetHeight()) or 1080
        card.svFloatingHeight = math.min(layout.GetFloatingPanelHeight() * TextScale(), screenHeight * 0.85)
    else
        card.svFloatingHeight = nil
    end
    local panelX = 770 + cardX
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelX then
        panelX = ns.StatVerdictDashboardLayout.GetRightPanelX(frame)
    end

    card.preferredWidth = cardWidth
    local extra = 0
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelExtraGap then
        extra = ns.StatVerdictDashboardLayout.GetRightPanelExtraGap()
    end
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad("manual.card")
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
    -- Whole card: Move X (shared dock) + Size W + Padding.
    if ns.ApplyRightDrawerCard then
        ns.ApplyRightDrawerCard(card, "manual.card", "Manual drawer", "manual.width", DRAWER_PREFERRED_WIDTH)
    end
    
    -- Outer pad owns Size W — retire the legacy right-edge width strip.

    ns.PlaceTabTitleChip(card, "Manual")

    card.scroll:ClearAllPoints()
    card.scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, SCROLL_TOP)
    card.scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -(SCROLL_SIDE_PAD + SCROLLBAR_WIDTH), ScrollBottomPad(card))
    card.scroll:Show()

    -- The text size slider, bottom left; a floating panel keeps clear of its Close button at the bottom right.
    local sizeRow = card.sizeRow
    local innerWidth = math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0))
    local rowWidth = math.max(100, innerWidth - 2 * SCROLL_SIDE_PAD - ((card.svFloating and CLOSE_BUTTON_ROOM) or 0))
    sizeRow:ClearAllPoints()
    sizeRow:SetPoint("BOTTOMLEFT", card, "BOTTOMLEFT", SCROLL_SIDE_PAD, SIZE_ROW_BOTTOM)
    sizeRow:SetSize(rowWidth, SIZE_ROW_HEIGHT)
    sizeRow:SetFrameLevel((card:GetFrameLevel() or 1) + 6)
    sizeRow.label:ClearAllPoints()
    sizeRow.label:SetPoint("TOPLEFT", sizeRow, "TOPLEFT", 0, 0)
    sizeRow.value:ClearAllPoints()
    sizeRow.value:SetPoint("TOPRIGHT", sizeRow, "TOPRIGHT", 0, 0)
    sizeRow.slider:ClearAllPoints()
    sizeRow.slider:SetPoint("TOPLEFT", sizeRow, "TOPLEFT", 0, -16)
    sizeRow.slider:SetPoint("TOPRIGHT", sizeRow, "TOPRIGHT", 0, -16)
    ns.PlaceStepSliderTicks(sizeRow.slider, rowWidth)
    sizeRow:SyncValue()
    sizeRow:Show()

    local contentWidth = math.max(80, cardWidth - SCROLL_SIDE_PAD * 2 - SCROLLBAR_WIDTH - 4)
    LayoutManualContent(card, contentWidth)
    card.scroll:SetVerticalScroll(0)
    if card.scroll.UpdateScrollChildRect then
        card.scroll:UpdateScrollChildRect()
    end

    local scrollBar = card.scroll.ScrollBar
    if type(scrollBar) ~= "table" then
        scrollBar = nil
        if type(card.scroll.GetName) == "function" then
            local ok, name = pcall(card.scroll.GetName, card.scroll)
            if ok and type(name) == "string" then scrollBar = _G[name .. "ScrollBar"] end
        end
    end
    local range = card.scroll.GetVerticalScrollRange and tonumber(card.scroll:GetVerticalScrollRange()) or 0
    local needScroll = range > 1
    if scrollBar then
        if needScroll then
            scrollBar:Show()
        else
            scrollBar:Hide()
        end
    end
    local rightPad = needScroll and (SCROLL_SIDE_PAD + SCROLLBAR_WIDTH) or SCROLL_SIDE_PAD
    card.scroll:ClearAllPoints()
    card.scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, SCROLL_TOP)
    card.scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -rightPad, ScrollBottomPad(card))
    if not needScroll and card.scroll.SetVerticalScroll then
        card.scroll:SetVerticalScroll(0)
    end

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
