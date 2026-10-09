local addonName, ns = ...

local Panel = {}
ns.StatVerdictOptionsDrawerPanel = Panel

-- The Options drawer: four dark group cards (the window, bag items and tooltips, Best in Slot, Ranked Trinkets), each under a
-- small gold heading with a thin rule. A choice is a row: its name, a short grey line under it where one helps, and a switch
-- on the right (gold when on). Hovering a row explains it. The list scrolls when it is taller than the panel.
local CHECKBOX_LABEL_FONT_SIZE = 11
local DESC_FONT_SIZE = 10
local ROW_HEIGHT = 24                      -- a row without a grey line
local ROW_HEIGHT_DESC = 36                 -- a row with one
local ROW_HEIGHT_SLIDER = 46               -- the name and the value above, the slider under them
local ROW_PAD = 10                         -- row edge > label, and switch > row edge
local CHILD_INDENT = 12                    -- a choice that belongs to the one above
local GROUP_PAD_BOTTOM = 6
local GROUP_HEADER_HEIGHT = 26             -- the heading and its rule
local GROUP_GAP = 8
local FIRST_ROW_TOP = -46                  -- under the title chip
local SWITCH_W, SWITCH_H = 28, 15
local SCROLLBAR_WIDTH = 18
local CONTENT_BOTTOM_PAD = 10              -- under the list in a docked panel
local FLOAT_MAX_HEIGHT = 500               -- a floating Options window is never higher than this; the list scrolls
local FLOAT_AIR = 8
local ROW_BACKDROP = { bgFile = "Interface\\Buttons\\WHITE8X8" }
local GROUP_BACKDROP = {
    bgFile = "Interface\\Buttons\\WHITE8X8",
    edgeFile = "Interface\\Buttons\\WHITE8X8",
    edgeSize = 1,
    insets = { left = 1, right = 1, top = 1, bottom = 1 },
}
local SWITCH_BACKDROP = {
    bgFile = "Interface\\Buttons\\WHITE8X8",
    edgeFile = "Interface\\Buttons\\WHITE8X8",
    edgeSize = 1,
    insets = { left = 1, right = 1, top = 1, bottom = 1 },
}
local GOLD = { 1.0, 0.82, 0.0 }
local GREY = { 0.55, 0.57, 0.62 }
local LOCKED_ALPHA = 0.45
local DRAWER_PREFERRED_WIDTH = 320
-- Left/right inner margin for the list (same as the Guide drawer MARGIN).
local CONTENT_MARGIN = 14
local TITLE_FONT_SIZE_DEFAULT = 15
local TITLE_FONT_SIZE_MIN = 11
local TITLE_FONT_SIZE_MAX = 24

local function Offset(key)
    if ns.GetLayoutOffset then return ns.GetLayoutOffset(key) end
    return 0, 0
end

local function Clamp(value, minValue, maxValue)
    value = tonumber(value) or 0
    if value < minValue then return minValue end
    if value > maxValue then return maxValue end
    return value
end

-- Quiet reader for saved title size (no Options UI). Both titles share this value.
function ns.GetSpecTitleFontSize()
    local db = _G.StatVerdictDB
    local size = db and tonumber(db.specTitleFontSize) or nil
    if size == nil then
        size = TITLE_FONT_SIZE_DEFAULT
    end
    return Clamp(size, TITLE_FONT_SIZE_MIN, TITLE_FONT_SIZE_MAX)
end

-- Unset counts as on, except for a choice that is off unless the player turns it on (default = false).
local function OptionFlagOn(key, default)
    local db = _G.StatVerdictDB
    if default == false then
        return type(db) == "table" and db[key] == true
    end
    return db == nil or db[key] ~= false
end

local function RefreshBagIndicatorsSoon()
    if ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
    elseif ns.InvalidateUpgradeIndicatorDecisionCache then
        ns.InvalidateUpgradeIndicatorDecisionCache()
    end
    if ns.ForceUpgradeIndicatorRefreshNow then
        ns.ForceUpgradeIndicatorRefreshNow("bags")
    elseif ns.RefreshUpgradeIndicators then
        ns.RefreshUpgradeIndicators("bags")
    elseif ns.RequestInventoryVerdictRefresh then
        ns.RequestInventoryVerdictRefresh("bags")
    end
end

-- The switch of a row: gold with the knob on the right when on, dark with the knob on the left when off.
local function PaintSwitch(row, on)
    local switch = row and row.switch
    if not switch then return end
    if on then
        switch:SetBackdropColor(0.45, 0.34, 0.0, 0.95)
        switch:SetBackdropBorderColor(GOLD[1], GOLD[2], GOLD[3], 0.95)
        switch.knob:SetColorTexture(GOLD[1], GOLD[2], GOLD[3], 1)
        switch.knob:ClearAllPoints()
        switch.knob:SetPoint("RIGHT", switch, "RIGHT", -2, 0)
    else
        switch:SetBackdropColor(0.09, 0.10, 0.13, 0.95)
        switch:SetBackdropBorderColor(0.30, 0.31, 0.36, 0.95)
        switch.knob:SetColorTexture(GREY[1], GREY[2], GREY[3], 1)
        switch.knob:ClearAllPoints()
        switch.knob:SetPoint("LEFT", switch, "LEFT", 2, 0)
    end
end

-- The name is white (grey while the choice is locked); a faint tint shows the row under the mouse; the switch shows the state.
local function PaintOptionRow(check)
    local row = check and check.svRow
    if not row then return end
    if row.hovered and not check.svLocked then
        row:SetBackdropColor(0.12, 0.13, 0.17, 0.85)
    else
        row:SetBackdropColor(0, 0, 0, 0)
    end
    if check.Text then
        if check.svLocked then
            check.Text:SetTextColor(GREY[1], GREY[2], GREY[3])
        else
            check.Text:SetTextColor(1, 1, 1)
        end
    end
    PaintSwitch(row, check.svSelected == true)
    row:SetAlpha(check.svLocked and LOCKED_ALPHA or 1)
end

local function ShowOptionTip(row, check)
    if not (check.svTip and GameTooltip and GameTooltip.SetOwner) then return end
    GameTooltip:SetOwner(row, "ANCHOR_RIGHT")
    GameTooltip:AddLine(check.svTipTitle or "", GOLD[1], GOLD[2], GOLD[3])
    GameTooltip:AddLine(check.svTip, 1, 1, 1, true)
    GameTooltip:Show()
end

local function HideOptionTip(row)
    if GameTooltip and GameTooltip.GetOwner and GameTooltip:GetOwner() == row then GameTooltip:Hide() end
end

local function EnsureSwitch(row)
    if row.switch then return row.switch end
    local switch = CreateFrame("Frame", nil, row, "BackdropTemplate")
    switch:SetSize(SWITCH_W, SWITCH_H)
    switch:SetBackdrop(SWITCH_BACKDROP)
    switch:EnableMouse(false)
    switch.knob = switch:CreateTexture(nil, "OVERLAY")
    switch.knob:SetSize(SWITCH_H - 4, SWITCH_H - 4)
    -- A round knob when the game can mask a texture; a small square otherwise.
    pcall(function()
        local mask = switch:CreateMaskTexture()
        mask:SetTexture("Interface\\CharacterFrame\\TempPortraitAlphaMask", "CLAMPTOBLACKADDITIVE", "CLAMPTOBLACKADDITIVE")
        mask:SetAllPoints(switch.knob)
        switch.knob:AddMaskTexture(mask)
    end)
    row.switch = switch
    return switch
end

-- One row: the choice's state lives in an invisible check button (the saved value, the name); the row draws it.
local function EnsureOptionRow(card, group, option)
    card.bagIndicatorChecks = card.bagIndicatorChecks or {}
    local check = card.bagIndicatorChecks[option.key]
    local row = check and check.svRow
    if not row then
        row = CreateFrame("Button", nil, group, "BackdropTemplate")
        row:SetBackdrop(ROW_BACKDROP)
        check = CreateFrame("CheckButton", nil, row)
        check:SetSize(1, 1)
        check:EnableMouse(false)
        check.optionKey = option.key
        check.Text = check:CreateFontString(nil, "OVERLAY")
        check.Text:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", CHECKBOX_LABEL_FONT_SIZE, "")
        check.Text:SetJustifyH("LEFT")
        check.Text:SetWordWrap(false)
        check.desc = row:CreateFontString(nil, "OVERLAY")
        check.desc:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", DESC_FONT_SIZE, "")
        check.desc:SetJustifyH("LEFT")
        check.desc:SetWordWrap(false)
        check.desc:SetTextColor(GREY[1], GREY[2], GREY[3])
        row.connector = row:CreateTexture(nil, "ARTWORK")
        row.connector:SetColorTexture(0.35, 0.30, 0.12, 0.8)
        row.connector:SetWidth(1)
        EnsureSwitch(row)
        row:SetScript("OnEnter", function(self)
            self.hovered = true
            PaintOptionRow(check)
            ShowOptionTip(self, check)
        end)
        row:SetScript("OnLeave", function(self)
            self.hovered = false
            PaintOptionRow(check)
            HideOptionTip(self)
        end)
        -- The whole row is the click target; the switch only shows the choice.
        row:SetScript("OnClick", function()
            if check.svLocked then return end
            check:SetChecked(not check.svSelected)
            local handler = check.scripts and check.scripts.OnClick or (check.GetScript and check:GetScript("OnClick"))
            if handler then handler(check) end
        end)
        check.svRow = row
        row.check = check
        card.bagIndicatorChecks[option.key] = check
    else
        row:SetParent(group)
    end
    check.svTip = option.tip
    check.svTipTitle = option.tipTitle or option.label
    check.Text:SetText(option.label)
    check.desc:SetText(option.desc or "")
    return check, row
end

-- Choices that are plain on / off switches: each is saved under its key. Some run something when changed.
-- Grouped by where they show: the bags, the item tooltips, the character info window.
local BAG_INDICATOR_OPTIONS = {
    { key = "showUpgradeArrow", label = "Upgrade Arrow on bag items",
      tip = "Shows a green arrow on the items in your bags that are an upgrade for you." },
    { key = "showMsOsLabels", label = "|cff00ff00MS|r / |cff00ff00OS|r Labels on bag items", tipTitle = "MS / OS Labels on bag items",
      tip = "Marks each upgrade arrow with MS (Main Spec) or OS (Off Spec), so you see which build gains from the item." },
    { key = "autoMark", label = "Auto mark worn pieces", desc = "What you wear marks itself",
      tip = "On: every piece you wear is saved for the spec you play, so it is put on again when you come back to that spec, and a piece you replace loses its mark. Alt-Click on an item in your bags saves it for the other build. Off: you save pieces yourself, Alt-Right-Click for the Main Spec and Alt-Left-Click for the Off Spec.",
      onChange = function() if ns.AutoMarkWornPieces then ns.AutoMarkWornPieces() end end },
}

local ITEM_TOOLTIP_OPTIONS = {
    { key = "showStatRanks", label = "Stat Ranks on tooltips", desc = "A stat's place in the guide",
      tip = "Shows where each secondary stat ranks in the guide for your build (for example #1 MS) on item tooltips. Hold Alt to see the other build." },
}

-- The pieces you wear, in the character info window (the game's own name for it).
local CHARACTER_INFO_OPTIONS = {
    { key = "showCharacterMarks", label = "Marks on worn pieces", desc = "BIS, CAT and the gold ring",
      tip = "Marks the pieces you wear in the character info window: BIS = it is in the Best in Slot list, CAT = the Catalyst would turn it into your Best in Slot set piece, a gold ring with two arrows = it is also in your other set.",
      onChange = function() if ns.RefreshCatalystMarks then ns.RefreshCatalystMarks() end end },
    { key = "showWornDownArrow", label = "Arrow on worn pieces", desc = "A better piece is in your bags",
      tip = "Puts a red arrow pointing down in the corner of a piece you wear in the character info window when a piece in your bags is better for the spec you play. The tooltip of the worn piece says which one.",
      onChange = function()
          if ns.ClearWornUpgradeCache then ns.ClearWornUpgradeCache() end
          if ns.RefreshCatalystMarks then ns.RefreshCatalystMarks() end
      end },
    { key = "showWornInfo", label = "Info on worn pieces", desc = "Explains the marks in the tooltip",
      tip = "On the tooltip of a piece you wear that has a mark, a short StatVerdict info says what the mark means (Best in Slot, the Catalyst, or also part of your other set)." },
}

-- The window's own behaviour (first in the list, as these are about the window).
local WINDOW_OPTIONS = {
    { key = "alwaysOnTop", label = "Always on top", default = false, desc = "Stays in front of everything",
      tip = "Keeps the StatVerdict window in front of everything. When off, it steps behind as soon as you click anywhere else, and comes back when you click it.",
      onChange = function() if ns.ApplyAlwaysOnTop then ns.ApplyAlwaysOnTop() end end },
    { key = "compactMode", label = "Compact Mode", default = false, desc = "A smaller window",
      tip = "A smaller window: one stat table at a time (switch with the Show Off Spec button under the dropdowns), with the panel buttons in a row under the table. The Manual opens from the button at the bottom of Options.",
      onChange = function()
          -- The window takes the size of the mode it is in now.
          if ns.ApplyWindowScale then ns.ApplyWindowScale() end
          if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
      end },
    { key = "autoHideLeft", label = "Auto-hide the left side", default = false, indent = true, requires = "compactMode",
      desc = "Folds the builds away",
      tip = "Part of Compact Mode (it is off and dimmed while Compact Mode is off): the Main Spec / Off Spec builds fold away behind a thin strip at the window's left edge, and the window gets narrower. Move the mouse onto the strip to show them over the table.",
      onChange = function() if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end end },
    -- Not a switch: a slider, in percent. Applied when the mouse lets go of it.
    { key = "windowScale", slider = true, label = "Window size", min = 75, max = 100, step = 5, default = 85,
      tip = "Makes the whole StatVerdict window, and the panels that belong to it, smaller: from 100% down to 75% (it starts at 85%). It works in the normal window and in Compact Mode, and each remembers its own size." },
}

-- What hovering a Best in Slot row shows.
-- Our tooltip and the game tooltip are always clickable: ticking one turns the
-- other off, unticking the ticked one leaves both off (no tooltip). The gems /
-- enchants block only exists inside our tooltip. showBisGemsEnchants is the
-- older single toggle's key, kept so saved choices survive.
local BIS_TOOLTIP_OPTIONS = {
    { key = "showBisTooltip", label = "Best in Slot tooltip",
      tip = "Hovering a Best in Slot item shows StatVerdict's own compact tooltip." },
    { key = "showBisGemsEnchants", label = "Gems and enchants", indent = true,
      tip = "Adds the recommended gems and enchants for that item to the tooltip." },
    { key = "bisUseGameTooltip", label = "Best in Slot: game tooltip", desc = "Instead of StatVerdict's own",
      tip = "Shows the game's own item tooltip, instead of StatVerdict's, when you hover a Best in Slot item. Ticking this turns StatVerdict's tooltip off." },
}
-- The same three choices for the Ranked Trinkets list. The
-- effect line is a child of our tooltip (only exists inside it), like gems / enchants.
local TRINKET_TOOLTIP_OPTIONS = {
    { key = "showTrinketTooltip", label = "Ranked Trinkets tooltip",
      tip = "Hovering a trinket in the Ranked Trinkets list shows StatVerdict's own compact tooltip." },
    { key = "showTrinketEffect", label = "Trinket effect", indent = true,
      tip = "Adds the trinket's effect text to the tooltip." },
    { key = "trinketUseGameTooltip", label = "Ranked Trinkets: game tooltip", desc = "Instead of StatVerdict's own",
      tip = "Shows the game's own item tooltip, instead of StatVerdict's, when you hover a trinket. Ticking this turns StatVerdict's tooltip off." },
}

-- The size slider: the name on the left, the value in gold on the right, the slider under them (ns.CreateStepSlider).
-- The window changes size when the mouse lets go (not while it is dragged: the slider sits in the window it resizes).
local function EnsureSliderRow(card, group, option)
    card.sliderRows = card.sliderRows or {}
    local row = card.sliderRows[option.key]
    if row then
        row:SetParent(group)
        return row
    end
    -- The normal window and Compact Mode each keep their own size.
    row = ns.CreateStepSlider(group, {
        label = option.label, tip = option.tip, min = option.min, max = option.max, step = option.step,
        get = function()
            return Clamp(ns.GetWindowScalePercent and ns.GetWindowScalePercent() or option.default, option.min, option.max)
        end,
        commit = function(value)
            _G.StatVerdictDB = _G.StatVerdictDB or {}
            _G.StatVerdictDB[ns.GetWindowScaleKey and ns.GetWindowScaleKey() or option.key] = value
            if ns.ApplyWindowScale then ns.ApplyWindowScale() end
        end,
    })
    card.sliderRows[option.key] = row
    return row
end

local function SyncSliders(card)
    for _, option in ipairs(WINDOW_OPTIONS) do
        local row = option.slider and card.sliderRows and card.sliderRows[option.key]
        if row then row:SyncValue() end
    end
end

-- checked, clickable for one Best in Slot option. Unset: ours and gems on, game off.
local function BisOptionState(key)
    local db = _G.StatVerdictDB
    local ours = OptionFlagOn("showBisTooltip")
    local game = (not ours) and type(db) == "table" and db.bisUseGameTooltip == true
    if key == "showBisTooltip" then return ours, true end
    if key == "showBisGemsEnchants" then return OptionFlagOn(key), ours end
    if key == "showTrinketTooltip" or key == "showTrinketEffect" or key == "trinketUseGameTooltip" then
        local trinketOurs = OptionFlagOn("showTrinketTooltip")
        if key == "showTrinketTooltip" then return trinketOurs, true end
        if key == "showTrinketEffect" then return OptionFlagOn(key), trinketOurs end
        return (not trinketOurs) and type(db) == "table" and db.trinketUseGameTooltip == true, true
    end
    return game, true
end

-- The tooltip option that a tick on key turns off.
local BIS_EXCLUSIVE_WITH = {
    showBisTooltip = "bisUseGameTooltip",
    bisUseGameTooltip = "showBisTooltip",
    showTrinketTooltip = "trinketUseGameTooltip",
    trinketUseGameTooltip = "showTrinketTooltip",
}

-- The choices that are plain switches (the window's and the bag items'): state, locked placeholder.
local SIMPLE_OPTION_LISTS = { BAG_INDICATOR_OPTIONS, ITEM_TOOLTIP_OPTIONS, CHARACTER_INFO_OPTIONS, WINDOW_OPTIONS }

local function SyncBagIndicatorOptionChecks(card)
    if not card or not card.bagIndicatorChecks then return end
    for _, list in ipairs(SIMPLE_OPTION_LISTS) do
        for _, option in ipairs(list) do
            local check = (not option.slider) and card.bagIndicatorChecks[option.key] or nil
            if check then
                -- A choice that belongs to another one (Auto-hide belongs to Compact Mode) is off and dimmed while that is off.
                -- Its own saved choice is kept and comes back when the other one is turned on again.
                local needed = option.requires and not OptionFlagOn(option.requires, false)
                check.svSelected = (not needed) and OptionFlagOn(option.key, option.default) or false
                check:SetChecked(check.svSelected)
                check.svLocked = option.locked == true or needed == true
                if check.svLocked then check:Disable() else check:Enable() end
                check:SetAlpha(check.svLocked and LOCKED_ALPHA or 1)
                PaintOptionRow(check)
            end
        end
    end
    -- Locked options are dimmed and not clickable; their saved value is kept.
    for _, list in ipairs({ BIS_TOOLTIP_OPTIONS, TRINKET_TOOLTIP_OPTIONS }) do
        for _, option in ipairs(list) do
            local check = card.bagIndicatorChecks[option.key]
            if check then
                local checked, active = BisOptionState(option.key)
                check.svSelected = checked and true or false
                check:SetChecked(checked)
                check.svLocked = not active
                if active then check:Enable() else check:Disable() end
                check:SetAlpha(active and 1 or LOCKED_ALPHA)
                PaintOptionRow(check)
            end
        end
    end
end

-- The groups, top to bottom.
local OPTION_SECTIONS = {
    { list = WINDOW_OPTIONS, simple = true, title = "WINDOW", field = "windowGroup" },
    { list = BAG_INDICATOR_OPTIONS, simple = true, bags = true, title = "BAG ITEMS", field = "bagGroup" },
    { list = ITEM_TOOLTIP_OPTIONS, simple = true, title = "ITEM TOOLTIPS", field = "itemTooltipGroup" },
    { list = CHARACTER_INFO_OPTIONS, simple = true, title = "CHARACTER INFO", field = "characterInfoGroup" },
    { list = BIS_TOOLTIP_OPTIONS, title = "BEST IN SLOT", field = "bisTooltipGroup" },
    { list = TRINKET_TOOLTIP_OPTIONS, title = "RANKED TRINKETS", field = "trinketTooltipGroup" },
}

local function RowHeight(option)
    if option.slider then return ROW_HEIGHT_SLIDER end
    return option.desc and ROW_HEIGHT_DESC or ROW_HEIGHT
end

-- Row tops (positive, down from the group's top), the group's height.
local function SectionLayout(list)
    local offsets, y = {}, GROUP_HEADER_HEIGHT
    for index, option in ipairs(list) do
        offsets[index] = y
        y = y + RowHeight(option)
    end
    return offsets, y + GROUP_PAD_BOTTOM
end

-- The height of the whole list: the groups and the gaps between them.
function Panel.GetContentHeight()
    local total = 0
    for index, section in ipairs(OPTION_SECTIONS) do
        local _, height = SectionLayout(section.list)
        total = total + height + (index > 1 and GROUP_GAP or 0)
    end
    return total
end

local function EnsureGroup(card, content, section)
    local group = card[section.field]
    if group then return group end
    group = CreateFrame("Frame", nil, content, "BackdropTemplate")
    group:SetBackdrop(GROUP_BACKDROP)
    group:SetBackdropColor(0.04, 0.05, 0.07, 0.92)
    group:SetBackdropBorderColor(0.14, 0.15, 0.18, 1)
    group:EnableMouse(false)
    group.heading = group:CreateFontString(nil, "OVERLAY")
    group.heading:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", 10, "")
    group.heading:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    group.heading:SetText(section.title)
    group.heading:SetPoint("TOPLEFT", group, "TOPLEFT", ROW_PAD, -9)
    group.rule = group:CreateTexture(nil, "ARTWORK")
    group.rule:SetColorTexture(0.35, 0.30, 0.12, 0.7)
    group.rule:SetHeight(1)
    group.rule:SetPoint("TOPLEFT", group, "TOPLEFT", ROW_PAD, -(GROUP_HEADER_HEIGHT - 6))
    group.rule:SetPoint("TOPRIGHT", group, "TOPRIGHT", -ROW_PAD, -(GROUP_HEADER_HEIGHT - 6))
    card[section.field] = group
    return group
end

-- The scroll bar of a scroll frame made from the game's template.
local function FindScrollBar(scroll)
    local bar = scroll.ScrollBar
    if type(bar) == "table" then return bar end
    if type(scroll.GetName) == "function" then
        local ok, name = pcall(scroll.GetName, scroll)
        if ok and type(name) == "string" then return _G[name .. "ScrollBar"] end
    end
    return nil
end

-- The panel's list scrolls: a scroll frame under the title chip, the groups inside it.
local function EnsureScroll(card)
    if card.scroll then return card.scroll, card.content end
    local scroll = CreateFrame("ScrollFrame", "StatVerdictOptionsScroll", card, "UIPanelScrollFrameTemplate")
    scroll:EnableMouse(true)
    local content = CreateFrame("Frame", nil, scroll)
    content:SetSize(100, 100)
    scroll:SetScrollChild(content)
    card.scroll, card.content = scroll, content
    return scroll, content
end

local function EnsureCard(frame)
    if frame.optionsDrawerCard then return frame.optionsDrawerCard end

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

    -- The title: the chip every tab shares (full width of the card, text centred).
    card.title = ns.PlaceTabTitleChip(card, "Options").label

    frame.optionsDrawerCard = card
    return card
end

-- Compact Mode: Options is a window of its own, and the Manual has no button in the compact row: a Manual button sits
-- left of the panel's Close button (bottom right). Opening the Manual replaces Options: there is never more than one
-- panel open.
local function ShowManualButton(card)
    if not card.manualButton then
        card.manualButton = ns.CreateFloatingButton(card, "Manual", function()
            if ns.SetRightPanelMode then ns.SetRightPanelMode("manual") end
        end)
    end
    local size = ns.StatVerdictDashboardLayout.FLOAT_BUTTON
    card.manualButton:ClearAllPoints()
    card.manualButton:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -(size.margin + size.width + size.gap), size.bottom)
    card.manualButton:SetFrameLevel((card:GetFrameLevel() or 1) + 6)
    card.manualButton:Show()
end

local function HideManualButton(card)
    if card.manualButton then card.manualButton:Hide() end
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "options"
end

function Panel.SetOpen(open)
    if open then
        if ns.SetRightPanelMode then ns.SetRightPanelMode("options") end
    else
        if Panel.IsOpen() and ns.SetRightPanelMode then
            ns.SetRightPanelMode(nil)
        end
    end
end

function Panel.Toggle()
    if ns.ToggleRightPanelMode then
        ns.ToggleRightPanelMode("options")
    end
end

function Panel.GetPreferredWidth(frame)
    -- The same width for everyone, docked or in a window of its own: the names, the grey lines and the switches need it.
    return DRAWER_PREFERRED_WIDTH
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.optionsDrawerCard then frame.optionsDrawerCard:Hide() end
        return
    end

    local card = EnsureCard(frame)
    local layout = ns.StatVerdictDashboardLayout
    local floating = layout and layout.IsCompact and layout.IsCompact() and layout.FLOAT_BUTTON ~= nil

    local cardX = Offset("options.card")
    local cardWidth = Panel.GetPreferredWidth(frame)
    local panelX = 770 + cardX
    if layout and layout.GetRightPanelX then
        panelX = layout.GetRightPanelX(frame)
    end

    card.preferredWidth = cardWidth
    -- A floating Options window is as high as its list needs, up to a limit; the list scrolls beyond that.
    local band = floating and layout.GetFloatingBand and layout.GetFloatingBand() or 0
    if floating then
        local need = -FIRST_ROW_TOP + Panel.GetContentHeight() + band + FLOAT_AIR
        card.svFloatingHeight = math.min(need, FLOAT_MAX_HEIGHT)
    else
        card.svFloatingHeight = nil
    end
    local extra = 0
    if layout and layout.GetRightPanelExtraGap then
        extra = layout.GetRightPanelExtraGap()
    end
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad("options.card")
        or { top = 0, bottom = 0, left = 0, right = 0 }
    if layout and layout.AnchorAfterPreviousCard and frame.statProgressCard then
        layout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, extra, 0, cardPad)
    elseif layout and layout.AnchorOuterCard then
        layout.AnchorOuterCard(card, frame, panelX, cardPad)
    else
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", panelX, -34)
        card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", panelX, 14)
    end
    local innerWidth = math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0))
    card:SetWidth(innerWidth)
    card:Show()
    -- Whole card: Move X (shared dock) + Size W + Padding.
    if ns.ApplyRightDrawerCard then
        ns.ApplyRightDrawerCard(card, "options.card", "Options drawer", "options.width", DRAWER_PREFERRED_WIDTH)
    end

    ns.PlaceTabTitleChip(card, "Options")

    -- The scrolling list: between the title chip and the bottom (the Manual / Close band of a floating panel).
    local cardHeight = tonumber(card.svFloatingHeight) or (card.GetHeight and tonumber(card:GetHeight())) or 380
    if cardHeight < 120 then cardHeight = 380 end
    local viewportHeight = cardHeight + FIRST_ROW_TOP - (floating and band or CONTENT_BOTTOM_PAD)
    local contentHeight = Panel.GetContentHeight()
    local needScroll = contentHeight > viewportHeight
    local scroll, content = EnsureScroll(card)
    local rightPad = CONTENT_MARGIN + (needScroll and SCROLLBAR_WIDTH or 0)
    scroll:ClearAllPoints()
    scroll:SetPoint("TOPLEFT", card, "TOPLEFT", CONTENT_MARGIN, FIRST_ROW_TOP)
    scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -rightPad, floating and band or CONTENT_BOTTOM_PAD)
    scroll:Show()
    local scrollBar = FindScrollBar(scroll)
    if scrollBar then scrollBar:SetShown(needScroll) end
    if not needScroll and scroll.SetVerticalScroll then scroll:SetVerticalScroll(0) end
    local contentWidth = math.max(160, innerWidth - CONTENT_MARGIN - rightPad)
    content:SetSize(contentWidth, math.max(contentHeight, 10))

    local top = 0
    for _, section in ipairs(OPTION_SECTIONS) do
        local group = EnsureGroup(card, content, section)
        local offsets, groupHeight = SectionLayout(section.list)
        group:ClearAllPoints()
        group:SetPoint("TOPLEFT", content, "TOPLEFT", 0, -top)
        group:SetSize(contentWidth, groupHeight)
        group:Show()

        for index, option in ipairs(section.list) do
            if option.slider then
                local sliderRow = EnsureSliderRow(card, group, option)
                sliderRow:ClearAllPoints()
                sliderRow:SetPoint("TOPLEFT", group, "TOPLEFT", 1, -offsets[index])
                sliderRow:SetPoint("TOPRIGHT", group, "TOPRIGHT", -1, -offsets[index])
                sliderRow:SetHeight(RowHeight(option))
                sliderRow:SetFrameLevel((group:GetFrameLevel() or 1) + 1)
                sliderRow:Show()
                sliderRow.label:ClearAllPoints()
                sliderRow.label:SetPoint("TOPLEFT", sliderRow, "TOPLEFT", ROW_PAD, -6)
                sliderRow.value:ClearAllPoints()
                sliderRow.value:SetPoint("TOPRIGHT", sliderRow, "TOPRIGHT", -ROW_PAD, -6)
                sliderRow.slider:ClearAllPoints()
                sliderRow.slider:SetPoint("TOPLEFT", sliderRow, "TOPLEFT", ROW_PAD, -26)
                sliderRow.slider:SetPoint("TOPRIGHT", sliderRow, "TOPRIGHT", -ROW_PAD, -26)
                sliderRow.slider:SetFrameLevel((sliderRow:GetFrameLevel() or 1) + 2)
                ns.PlaceStepSliderTicks(sliderRow.slider, math.max(40, contentWidth - 2 - 2 * ROW_PAD))
            else
            local check, row = EnsureOptionRow(card, group, option)
            local height = RowHeight(option)
            local indent = option.indent and CHILD_INDENT or 0
            row:ClearAllPoints()
            row:SetPoint("TOPLEFT", group, "TOPLEFT", 1, -offsets[index])
            row:SetPoint("TOPRIGHT", group, "TOPRIGHT", -1, -offsets[index])
            row:SetHeight(height)
            row:SetFrameLevel((group:GetFrameLevel() or 1) + 1)
            row:Show()
            -- Name (and the grey line under it) on the left, the switch on the right.
            local labelLeft = ROW_PAD + indent
            check:ClearAllPoints()
            check:SetPoint("TOPLEFT", row, "TOPLEFT", labelLeft, 0)
            local textWidth = math.max(40, contentWidth - labelLeft - ROW_PAD - SWITCH_W - 8)
            check.Text:ClearAllPoints()
            check.Text:SetPoint("TOPLEFT", row, "TOPLEFT", labelLeft, option.desc and -6 or -6)
            check.Text:SetWidth(textWidth)
            check.desc:ClearAllPoints()
            check.desc:SetPoint("TOPLEFT", row, "TOPLEFT", labelLeft, -21)
            check.desc:SetWidth(textWidth)
            check.desc:SetShown(option.desc ~= nil)
            row.switch:ClearAllPoints()
            row.switch:SetPoint("RIGHT", row, "RIGHT", -ROW_PAD, 0)
            row.switch:SetFrameLevel((row:GetFrameLevel() or 1) + 2)
            -- A choice that belongs to the one above hangs from a thin gold line.
            if option.indent then
                row.connector:ClearAllPoints()
                row.connector:SetPoint("TOPLEFT", row, "TOPLEFT", ROW_PAD, 0)
                row.connector:SetPoint("BOTTOMLEFT", row, "BOTTOMLEFT", ROW_PAD, 0)
                row.connector:Show()
            else
                row.connector:Hide()
            end
            check:SetScript("OnClick", function(self)
                if self.svLocked then
                    SyncBagIndicatorOptionChecks(card)
                    return
                end
                _G.StatVerdictDB = _G.StatVerdictDB or {}
                local on = self:GetChecked() and true or false
                _G.StatVerdictDB[option.key] = on
                if section.simple then
                    SyncBagIndicatorOptionChecks(card)
                    if section.bags then RefreshBagIndicatorsSoon() end
                    if option.onChange then option.onChange() end
                    SyncSliders(card)
                    return
                end
                local other = BIS_EXCLUSIVE_WITH[option.key]
                if on and other then _G.StatVerdictDB[other] = false end
                SyncBagIndicatorOptionChecks(card)
            end)
            end
        end
        top = top + groupHeight + GROUP_GAP
    end
    SyncBagIndicatorOptionChecks(card)
    SyncSliders(card)

    if floating then
        ShowManualButton(card)
        card:SetHeight(tonumber(card.svFloatingHeight) or cardHeight)
    else
        HideManualButton(card)
    end

    if layout and layout.SyncFrameWidthToRightPanel then
        layout.SyncFrameWidthToRightPanel(frame)
    end
end
