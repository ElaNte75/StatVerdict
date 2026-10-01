local addonName, ns = ...

local Panel = {}
ns.StatVerdictManualDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local SCROLL_TOP = -34
local SCROLL_BOTTOM_PAD = 14
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
    { gap = true },
    { title = true, text = "Panels" },
    { text = "Best in Slot — the best-in-slot items for the active build (Mythic+, Raid or PvP), with your progress." },
    { text = "Hover a Best in Slot item to see it at its recommended item level, with the recommended gems and enchant." },
    { text = "Features → Best in Slot chooses what that hover shows. Best in Slot tooltip: our compact tooltip; under it, Gems and enchants adds the recommended gems and enchant. Use the game tooltip instead: the game's own item tooltip. Only one of the two tooltips can be on: ticking one turns the other off. With both unticked, hovering shows nothing. Features → Ranked Trinkets works the same way for the trinket list: Ranked Trinkets tooltip is our compact tooltip (name, level, stats), and under it Trinket effect adds the trinket's effect; or Use the game tooltip instead." },
    { text = "The Best in Slot and Ranked Trinkets tooltips end with Where to find: the dungeon or raid and the boss the item drops from, when the game's Adventure Journal lists it. Crafted items, the Great Vault and the Catalyst are not listed." },
    { text = "Ranked Trinkets — ranked trinket list for the active build." },
    { text = "Features — toggles for bag markers (Upgrade Arrow, MS/OS Labels)." },
    { text = "Guide — the stat priorities, Best in Slot lists and stat targets are copied from the guides, unchanged. Pick Auto (the default: the tier follows your own stats and moves up when you cover about 90% of it) or one fixed tier: Tier 1, Tier 2 or Tier 3 (the most demanding). The tier in use is shown in the title bar; Best in Slot and trinkets follow it." },
    { text = "On Best in Slot and Ranked Trinkets, click the title chip to switch Main Spec / Off Spec. Both panels share that selection." },
    { text = "Only one side panel can be open at a time." },
    { gap = true },
    { title = true, text = "Bag markers" },
    { text = "MS / OS membership labels appear only on bag items. Upgrade arrows can also appear on quest rewards, merchants, and the Adventure Guide." },
    { text = "Green arrow — upgrade vs your comparison baseline." },
    { text = "MS / OS — item is already saved in your Main / Off Spec virtual loadout." },
    { text = "Features → Bag Markers controls bag arrows and MS/OS labels. It does not disable quest, merchant, or Adventure Guide upgrade arrows." },
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

    card.title = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.title:SetPoint("TOPLEFT", card, "TOPLEFT", 12, -12)
    card.title:SetText("Manual")
    card.title:SetTextColor(1.0, 0.82, 0.0)

    local scrollName = "StatVerdictManualScroll"
    local scroll = CreateFrame("ScrollFrame", scrollName, card, "UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, SCROLL_TOP)
    scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -(SCROLL_SIDE_PAD + SCROLLBAR_WIDTH), SCROLL_BOTTOM_PAD)
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

    frame.manualDrawerCard = card
    return card
end

local function LayoutManualContent(card, contentWidth)
    local child = card.scrollChild
    local y = -4
    local lineIndex = 0
    local textWidth = math.max(60, contentWidth - 8)

    for _, entry in ipairs(MANUAL_LINES) do
        if entry.gap then
            y = y - 10
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
            fs:SetText(entry.text)
            fs:Show()
            local height = fs:GetStringHeight() or 12
            if height < 12 then height = 12 end
            y = y - (height + 5)
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
            fs:SetText(entry.text)
            fs:Show()
            y = y - 18
        end
    end
    for i = lineIndex + 1, #(card.lines) do
        card.lines[i]:Hide()
    end

    local contentHeight = math.max(40, -y + 8)
    child:SetSize(contentWidth, contentHeight)
    return contentHeight
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "manual"
end

function Panel.GetPreferredWidth(frame)
    local card = frame and frame.manualDrawerCard
    if card and tonumber(card.preferredWidth) then
        return tonumber(card.preferredWidth)
    end
    return DRAWER_PREFERRED_WIDTH + SizeDelta("manual.width")
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.manualDrawerCard then frame.manualDrawerCard:Hide() end
        return
    end

    local card = EnsureCard(frame)
    local cardX = Offset("manual.card")
    local cardWidth = DRAWER_PREFERRED_WIDTH + SizeDelta("manual.width")
    if cardWidth < 200 then cardWidth = 200 end
    if cardWidth > 520 then cardWidth = 520 end
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelWidth then
        cardWidth = ns.StatVerdictDashboardLayout.GetRightPanelWidth(frame) or cardWidth
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
    -- Whole card is the AdvDev target: Move X (shared dock) + Size W + Padding.
    if ns.ApplyRightDrawerCard then
        ns.ApplyRightDrawerCard(card, "manual.card", "Manual drawer", "manual.width", DRAWER_PREFERRED_WIDTH)
    end
    -- Manual body text is not AdvDev-editable — drop any leftover title/content ghosts.

    -- Outer pad owns Size W — retire the legacy right-edge width strip.

    local titleX, titleY = Offset("manual.title")
    card.title:ClearAllPoints()
    card.title:SetPoint("TOPLEFT", card, "TOPLEFT", 12 + titleX, -12 + titleY)

    card.scroll:ClearAllPoints()
    card.scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, SCROLL_TOP)
    card.scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -(SCROLL_SIDE_PAD + SCROLLBAR_WIDTH), SCROLL_BOTTOM_PAD)
    card.scroll:Show()

    local contentWidth = math.max(80, cardWidth - SCROLL_SIDE_PAD * 2 - SCROLLBAR_WIDTH - 4)
    LayoutManualContent(card, contentWidth)
    card.scroll:SetVerticalScroll(0)
    if card.scroll.UpdateScrollChildRect then
        card.scroll:UpdateScrollChildRect()
    end

    local scrollBar = card.scroll.ScrollBar or (card.scroll.GetName and _G[card.scroll:GetName() .. "ScrollBar"]) or nil
    local range = card.scroll.GetVerticalScrollRange and (card.scroll:GetVerticalScrollRange() or 0) or 0
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
    card.scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -rightPad, SCROLL_BOTTOM_PAD)
    if not needScroll and card.scroll.SetVerticalScroll then
        card.scroll:SetVerticalScroll(0)
    end

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
