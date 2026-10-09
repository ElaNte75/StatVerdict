local addonName, ns = ...

local Panel = {}
ns.StatVerdictManualDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local TITLE_CHIP_HEIGHT = 30   -- the Manual's title chip is taller than the other tabs' (its topic titles are longer)
local TITLE_FONT_SIZE = 15
local SCROLL_TOP = -48  -- under the title chip (12 + 30 high), with a little air
local SIZE_ROW_HEIGHT = 34 -- the text size slider at the bottom of the card: its name and value, the slider under them
local SIZE_ROW_BOTTOM = 12
local CLOSE_BUTTON_ROOM = 78 -- a floating panel has its Close button at the bottom right: the slider stops before it
local SCROLL_BOTTOM_PAD = SIZE_ROW_BOTTOM + SIZE_ROW_HEIGHT + 8

local DIVIDER_ROOM = 10  -- the thin line between the text and the text size slider

-- How far above the card's bottom the text stops: inside a topic the slider (and the line above it) is there; the list of
-- topics has no slider.
local function ScrollBottomPad(card)
    if card and card.manualSection == nil then return SIZE_ROW_BOTTOM end
    return SCROLL_BOTTOM_PAD + DIVIDER_ROOM
end

-- The Manual's own text size, in percent: 100% is the size it always had. Remembered; only the Manual uses it.
local TEXT_SCALE_MIN, TEXT_SCALE_MAX, TEXT_SCALE_STEP = 100, 175, 25

function ns.GetManualTextScalePercent()
    local db = _G.StatVerdictDB
    local percent = type(db) == "table" and tonumber(db.manualTextScale) or 100
    return math.max(TEXT_SCALE_MIN, math.min(TEXT_SCALE_MAX, percent))
end

-- The list of topics is always at 100%; the size the player chose is for the text inside a topic.
local function TextScale(card)
    if card and card.manualSection == nil then return 1 end
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
    { text = "A loadout is a saved picture of the pieces you play in one build. StatVerdict keeps one for your Main Spec and one for your Off Spec, so it can judge an item for either of them without you switching specialization." },
    { text = "For the specialization you are playing, the loadout follows what you wear: swap a piece and the loadout changes with it (see Marking pieces below). The comparison for that spec is with what you wear." },
    { text = "For the other specialization, the loadout is the gear it had when you last played it, plus the pieces you marked for it in your bags. Trustworthy live weights still require one capture while that specialization is active; until then StatVerdict shows that stats are not captured and produces no verdict." },
    { text = "Every piece in a loadout is remembered by the game's own serial number, a number each piece has for its whole life. So two copies of the same item (one with a gem, one without) are told apart, and a gem, an enchant or an upgrade does not make StatVerdict lose a piece. A mark made before this existed has no serial number: it still works, by item, and gets one when you mark it again." },
    { gap = true },
    { title = true, text = "Marking pieces" },
    { text = "A marked piece is one StatVerdict will put on when you switch to that build's specialization. A piece can be marked for the Main Spec, the Off Spec, or both. In your bags the mark shows in the top right corner of the item: MS, OS, or the gold ring with two arrows for both." },
    { text = "Auto mark (Options → Bag items, on by default). Every piece you wear is marked for the spec you play. When you wear a different piece in a slot, the old piece loses the mark for that spec (it keeps the other build's mark, if it had one), and the new one is marked. So you do not have to mark anything for the spec you play: wear it." },
    { text = "After you switch specialization, Auto mark waits about 7 seconds before it takes what you wear as the new spec's marks, because the game still shows the old spec's gear until the marked pieces of the new one are put on." },
    { text = "Alt-Click on an item in your bags (either mouse button) saves it for the build you are not playing. If the item is an upgrade for the build you play too, it is saved for both and shows the gold ring. Click it again to take it out. With one build only, or when you play a specialization that is neither of your builds, there is nothing to save it for." },
    { text = "A mark you make by hand with Alt-Click stays until you wear that piece, wear a different piece in that slot, or remove it. Auto mark does not change it before that." },
    { text = "When you switch specialization, the pieces marked for that spec are put on (only those in your bags; every other slot keeps what you wear), starting about a second after the switch. A ring, trinket or one-hand weapon takes the place of the worn one that is not marked for that spec, never one that is. It never happens in combat, and a line in the chat says what was put on." },
    { text = "Auto mark off (Options → Bag items): nothing marks itself. Alt-Right-Click on a bag item switches its Main Spec mark on or off, Alt-Left-Click its Off Spec mark (needs an Off Spec), one build at a time. The marks Auto mark made before you switched it off stay as they are and no longer follow what you wear: a piece you wear later is not marked, and when you come back to the spec, a marked piece in your bags can be put on in its place." },
    { gap = true },
    { title = true, text = "Wearing from the bags" },
    { text = "Right-click on a ring, trinket or one-hand weapon in your bags (no Alt, Shift or Ctrl): when both slots are taken, the game chooses by itself which worn piece to replace, and that is not always the one the tooltip says the new piece beats (\"Better than <piece>\")." },
    { text = "StatVerdict puts the new piece on the slot of the piece the tooltip names, in one step: the piece it replaces goes back to your bags and nothing else moves. For a moment the piece may sit on your mouse cursor; it is put down by itself. If that is not possible, StatVerdict puts things right afterwards. It never happens in combat." },
    { gap = true },
    { title = true, text = "Panels" },
    { text = "Best in Slot — the best-in-slot items for the active build (Mythic+, Raid or PvP), with your progress." },
    { text = "Hover a Best in Slot item to see it at its recommended item level, with the recommended gems and enchant." },
    { text = "Options chooses what that hover shows. Best in Slot tooltip: our compact tooltip; under it, Gems and enchants adds the recommended gems and enchant. Best in Slot: game tooltip: the game's own item tooltip. Only one of the two tooltips can be on: ticking one turns the other off. With both unticked, hovering shows nothing. The trinket list works the same way: Ranked Trinkets tooltip is our compact tooltip (name, level, stats), and under it Trinket effect adds the trinket's effect; or Ranked Trinkets: game tooltip." },
    { text = "The Best in Slot and Ranked Trinkets tooltips end with Where to find: the dungeon or raid and the boss the item drops from, when the game's Adventure Journal lists it. An item the journal does not list (crafted, vendor, PvP, the Great Vault, the Catalyst or an event) says Other source, with no item level of its own claimed." },
    { text = "Ranked Trinkets — ranked trinket list for the active build." },
    { text = "Options — yes / no choices, in groups: Window (Always on top, Compact Mode, Auto-hide the left side, Window size; see Window and Compact Mode below), Bag items (Upgrade Arrow, MS / OS Labels, Auto mark), Item tooltips (Stat Ranks), Character info (Marks on worn pieces, Arrow on worn pieces, Info on worn pieces), and the Best in Slot and Ranked Trinkets tooltips. Hover a choice to see what it does." },
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
    { text = "The verdict on an item's tooltip names its build, Main Spec or Off Spec, and what the item beats: \"Better than <item>: +points\". The Main Spec comes first; the Off Spec shows when the item is an upgrade for it alone." },
    { text = "When the other build gains from the item too, a gold line says so (Also an upgrade for Off Spec) and tells you how to see it: hold Alt (outside the bags), or Alt-Click to save it in the loadout (in the bags; Alt-Left-Click when Auto mark is off)." },
    { text = "An item in your bags that is saved in a loadout says so. Saved in both builds: one line, Saved in MS and OS loadouts, and nothing is compared. Saved in one build only: the other build is still judged (Better than <piece>: +points), and one plain line under it says Also saved in OS Blood loadout (MS or OS, then the spec in its class colour). Two copies of the same item are told apart: the line is about the copy under the mouse." },
    { text = "Stat Ranks: every secondary stat on an item tooltip shows its place in the guide's order for the build in view (for example +73 Critical Strike #1 MS). Stats the guide calls roughly equal share a number. Switch it off in Options." },
    { text = "Hold Alt over an item to see the other build for as long as you hold it: the ranks and the whole verdict (with an Off Spec set). A gold line says when the other build gains from the item too. Over an item in your bags Alt is the marking key instead (Alt-Click; Alt-Left-Click / Alt-Right-Click when Auto mark is off), so it changes nothing there." },
    { text = "Hold Ctrl over an item the Catalyst can turn into your Best in Slot set piece to preview that piece at the same item level. Shift is the game's own comparison." },
    { text = "A StatVerdict Warning on a tooltip means the Catalyst would turn that piece (the one you wear, or one in your bags or at a vendor that is no upgrade as it is) into your Best in Slot set piece, and the points that gain is worth over what you wear in that slot." },
    { gap = true },
    { title = true, text = "Character info" },
    { text = "In the character info window (C) a piece you wear can carry one gold mark in the middle of its icon: BIS = it is in the Best in Slot list. CAT = the Catalyst would turn it into your Best in Slot set piece (so it becomes Best in Slot as well). A thin gold ring with two arrows = the piece is also in your other set (Main Spec and Off Spec both use it); with BIS or CAT inside the ring when both are true. Switch the marks off in Options (Character info, Marks on worn pieces)." },
    { text = "The gold CAT is drawn with thicker letters than BIS: it is the one that asks you to do something." },
    { text = "A red arrow pointing down in the top right corner of a worn piece means a piece in your bags is better for the spec you play: you may have put on the wrong one. Its tooltip names the better piece and the points it gains. While the arrow shows, the gold ring (the piece is in both builds) is not shown on that piece. If wearing it is your choice, click the arrow: it goes away and the ring comes back, until you wear another piece or a different better piece turns up in the bags. Switch the arrow off in Options (Character info, Arrow on worn pieces)." },
    { text = "A piece you wear is never compared with the other build or with anything else; only the bags are looked at for the red arrow. If it has a mark, its tooltip has a short StatVerdict info that says what the mark means: This item is Best in Slot (light blue), Catalyst it: Best in Slot (when the Catalyst would make it Best in Slot, with the points it gains and Hold Ctrl to preview), Also part of your OS set (OS or MS in green, the other build), or, for a piece that belongs to one build only, Part of your MS Frost set (MS or OS in green, then the spec in its class colour). That last one is only information: there is no mark on the icon. Switch it off in Options (Character info, Info on worn pieces)." },
    { gap = true },
    { title = true, text = "Bag markers" },
    { text = "MS / OS membership labels appear only on bag items. Upgrade arrows can also appear on quest rewards, merchants, and the Adventure Guide." },
    { text = "Green arrow — upgrade vs your comparison baseline." },
    { text = "MS / OS — item is already saved in your Main / Off Spec virtual loadout (green letters, top right)." },
    { text = "Green arrow with MS or OS — the item is saved in one build and is an upgrade for the other: the arrow stays, with the letter of the build that holds it." },
    { text = "Gold ring with two arrows — item is saved in both loadouts; it replaces the letters. The same ring means the same thing in the character info window." },
    { text = "The marks appear as soon as you open your bags. Options → Upgrade Arrow on bag items and MS / OS Labels on bag items control the bag arrows and labels. It does not disable quest, merchant, or Adventure Guide upgrade arrows. How a piece gets marked is under Marking pieces." },
    { gap = true },
    { title = true, text = "Limits and data" },
    { text = "StatVerdict models item level, primary and secondary stats, actual gem stats, physical weapon DPS, tank armor/stamina, and validated goal-specific references." },
    { text = "It does not model encounter mechanics, execution, most procs/on-use effects, embellishment power, tertiary value, set-bonus magnitude, or upgrade-currency cost." },
    { text = "Bundled profile data has freshness and quality checks. After about two months without an update it counts as out of date, and if it is also incomplete or mismatched to your goal, StatVerdict shows an unavailable state instead of guessing: update StatVerdict to the latest version to get new data." },
}

-- The Manual is a list of topics: the Manual window shows only their titles; a click shows one topic's text, with its
-- title above and a small Back arrow to the list. The topics are the titled blocks of MANUAL_LINES; the lines before the
-- first block (under "Manual" itself) are the first topic, "Overview".
local function BuildSections()
    local sections, current = {}, nil
    for _, entry in ipairs(MANUAL_LINES) do
        if entry.title and entry.text then
            current = { title = (entry.text == "Manual") and "Overview" or entry.text, entries = {} }
            sections[#sections + 1] = current
        elseif current then
            current.entries[#current.entries + 1] = entry
        end
    end
    return sections
end

local sectionsCache = nil
local function Sections()
    if not sectionsCache then sectionsCache = BuildSections() end
    return sectionsCache
end

local Panel_Apply  -- forward: the topic buttons re-draw the panel

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
    card.topicButtons = {}
    card.svFrame = frame
    card.manualSection = nil  -- nil: the list of topics

    -- The small arrow on the left of the title, back to the list of topics (only while a topic is open).
    local back = CreateFrame("Button", nil, card)
    back:SetSize(54, 22)
    back:SetPoint("TOPLEFT", card, "TOPLEFT", 16, -16)
    back:SetFrameLevel((card:GetFrameLevel() or 1) + 8)
    back.icon = back:CreateTexture(nil, "ARTWORK")
    back.icon:SetTexture("Interface\\Buttons\\UI-SpellbookIcon-PrevPage-Up")
    back.icon:SetSize(22, 22)
    back.icon:SetPoint("LEFT", back, "LEFT", -4, 0)
    back.label = back:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    back.label:SetText("Back")
    back.label:SetPoint("LEFT", back.icon, "RIGHT", -3, 0)
    back:SetScript("OnEnter", function(self) self.label:SetTextColor(1, 0.82, 0) end)
    back:SetScript("OnLeave", function(self) self.label:SetTextColor(0.9, 0.9, 0.9) end)
    back:SetScript("OnClick", function() ns.StatVerdictManualDrawerPanel.ShowTopics(card.svFrame) end)
    back:Hide()
    card.backButton = back

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
        tip = "Makes the Manual's text, and its window, bigger: from 100% up to 175%. It is remembered, and only the Manual uses it.",
        min = TEXT_SCALE_MIN, max = TEXT_SCALE_MAX, step = TEXT_SCALE_STEP,
        get = function() return ns.GetManualTextScalePercent() end,
        commit = function(value)
            _G.StatVerdictDB = _G.StatVerdictDB or {}
            _G.StatVerdictDB.manualTextScale = value
            if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
        end,
    })

    -- A thin line above the slider: the text size is a setting, not part of the text.
    card.sizeDivider = card:CreateTexture(nil, "ARTWORK")
    card.sizeDivider:SetColorTexture(0.72, 0.74, 0.78, 0.35)
    card.sizeDivider:SetHeight(1)

    frame.manualDrawerCard = card
    return card
end

-- The list of topics: only their titles, each one a button.
local function LayoutTopics(card, contentWidth)
    local child = card.scrollChild
    local scale = TextScale(card)
    local y = -6 * scale
    local textWidth = math.max(60, contentWidth - 8)
    for index, section in ipairs(Sections()) do
        local button = card.topicButtons[index]
        if not button then
            button = CreateFrame("Button", nil, child)
            button.label = button:CreateFontString(nil, "OVERLAY", "GameFontNormal")
            button.label:SetPoint("LEFT", button, "LEFT", 4, 0)
            button.label:SetJustifyH("LEFT")
            button.label:SetTextColor(1.0, 0.82, 0.0)
            button:SetScript("OnEnter", function(self) self.label:SetTextColor(1, 1, 1) end)
            button:SetScript("OnLeave", function(self) self.label:SetTextColor(1.0, 0.82, 0.0) end)
            button.svIndex = index
            button:SetScript("OnClick", function(self) ns.StatVerdictManualDrawerPanel.OpenTopic(card.svFrame, self.svIndex) end)
            card.topicButtons[index] = button
        end
        button:ClearAllPoints()
        button:SetPoint("TOPLEFT", child, "TOPLEFT", 2, y)
        button:SetSize(textWidth, 22 * scale)
        button.label:SetWidth(textWidth - 8)
        ApplyTextScale(button.label, scale)
        button.label:SetText(section.title)
        button:Show()
        y = y - 26 * scale
    end
    for index = #Sections() + 1, #card.topicButtons do card.topicButtons[index]:Hide() end
    for _, line in ipairs(card.lines) do line:Hide() end
    local contentHeight = math.max(40, -y + 8 * scale)
    child:SetSize(contentWidth, contentHeight)
    return contentHeight
end

local function LayoutTopic(card, contentWidth, section)
    local child = card.scrollChild
    local scale = TextScale(card)
    local y = -4 * scale
    local lineIndex = 0
    local textWidth = math.max(60, contentWidth - 8)
    for _, button in ipairs(card.topicButtons) do button:Hide() end

    for _, entry in ipairs(section.entries) do
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
        end
    end
    for i = lineIndex + 1, #(card.lines) do
        card.lines[i]:Hide()
    end

    local contentHeight = math.max(40, -y + 8 * scale)
    child:SetSize(contentWidth, contentHeight)
    return contentHeight
end

local function LayoutManualContent(card, contentWidth)
    local section = card.manualSection and Sections()[card.manualSection] or nil
    if section then
        return LayoutTopic(card, contentWidth, section)
    end
    return LayoutTopics(card, contentWidth)
end

-- The list of topics.
function Panel.ShowTopics(frame)
    local card = frame and frame.manualDrawerCard
    if not card then return end
    card.manualSection = nil
    Panel_Apply(frame)
end

-- One topic (by its place in the list).
function Panel.OpenTopic(frame, index)
    local card = frame and frame.manualDrawerCard
    if not card or not Sections()[index] then return end
    card.manualSection = index
    Panel_Apply(frame)
end

function Panel.GetTopicTitles()
    local titles = {}
    for _, section in ipairs(Sections()) do titles[#titles + 1] = section.title end
    return titles
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "manual"
end

-- Its own width times the text size (the text and the window grow together), never wider than most of the screen.
function Panel.GetPreferredWidth(frame)
    local width = (DRAWER_PREFERRED_WIDTH + SizeDelta("manual.width")) * TextScale(frame and frame.manualDrawerCard)
    local screenWidth = UIParent and UIParent.GetWidth and tonumber(UIParent:GetWidth()) or 1920
    return math.min(width, screenWidth * 0.8)
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.manualDrawerCard then
            frame.manualDrawerCard:Hide()
            frame.manualDrawerCard.manualSection = nil  -- opened again, it starts at the list of topics
        end
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
        card.svFloatingHeight = math.min(layout.GetFloatingPanelHeight() * TextScale(card), screenHeight * 0.85)
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

    -- The title is the topic's, with the small Back arrow on its left; the list of topics is called Manual.
    local section = card.manualSection and Sections()[card.manualSection] or nil
    local chip = ns.PlaceTabTitleChip(card, section and section.title or "Manual")
    if type(chip) == "table" then
        chip:SetHeight(TITLE_CHIP_HEIGHT)
        local label = chip.label
        if type(label) == "table" and type(label.GetFont) == "function" and type(label.SetFont) == "function" then
            local file, _, flags = label:GetFont()
            if file then label:SetFont(file, TITLE_FONT_SIZE, flags) end
        end
    end
    if card.backButton then
        card.backButton:SetShown(section ~= nil)
    end

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
    sizeRow:SetShown(section ~= nil)
    if card.sizeDivider then
        card.sizeDivider:ClearAllPoints()
        card.sizeDivider:SetPoint("BOTTOMLEFT", card, "BOTTOMLEFT", SCROLL_SIDE_PAD, SIZE_ROW_BOTTOM + SIZE_ROW_HEIGHT + 5)
        card.sizeDivider:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -SCROLL_SIDE_PAD, SIZE_ROW_BOTTOM + SIZE_ROW_HEIGHT + 5)
        card.sizeDivider:SetShown(section ~= nil)
    end

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

Panel_Apply = Panel.Apply
