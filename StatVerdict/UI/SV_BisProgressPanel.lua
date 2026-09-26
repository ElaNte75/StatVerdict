local addonName, ns = ...

local Panel = {}
ns.StatVerdictBisProgressPanel = Panel

local MAX_ROWS = 16
local TIER_COLOR = {
    S = "|cffff8000",
    A = "|cffa335ee",
    B = "|cff0070dd",
    C = "|cff1eff00",
    D = "|cff9d9d9d",
}

local pendingItemLoads = {}
local refreshFrame = nil
local lastRefreshFrame = nil
local lastRefreshProfile = nil

local function Offset(key)
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function Register(key, label, region, options)
    if ns.RegisterDevLayoutRegion then ns.RegisterDevLayoutRegion(key, label, region, options) end
end

local function SafeNumber(value)
    if value == nil then return nil end
    return tonumber(value)
end

local function RequestItemLoad(itemID)
    itemID = SafeNumber(itemID)
    if not itemID then return end
    pendingItemLoads[itemID] = true
    if C_Item and type(C_Item.RequestLoadItemDataByID) == "function" then
        pcall(C_Item.RequestLoadItemDataByID, itemID)
    end
end

local function GetBonusIDs(entry)
    if type(entry) ~= "table" then return nil end
    local item = entry.item
    local bonuses = nil
    if type(item) == "table" and type(item.bonus_ids) == "table" then
        bonuses = item.bonus_ids
    elseif type(entry.bonus_ids) == "table" then
        bonuses = entry.bonus_ids
    end
    if type(bonuses) ~= "table" or #bonuses == 0 then return nil end
    local out = {}
    for _, bonus in ipairs(bonuses) do
        local n = SafeNumber(bonus)
        if n then out[#out + 1] = n end
    end
    return #out > 0 and out or nil
end

local function BuildItemLink(itemID, bonusIDs)
    itemID = SafeNumber(itemID)
    if not itemID then return nil end
    -- Match Tools/SV_BISResolver.lua: bonuses must sit after linkLevel + 3 empty fields
    -- (spec, modifiersMask, itemContext) or rarity/ilvl tooltips stay on the base item.
    if type(bonusIDs) ~= "table" or #bonusIDs == 0 then
        return "item:" .. tostring(itemID)
    end
    local level = 90
    if type(UnitLevel) == "function" then
        local unitLevel = SafeNumber(UnitLevel("player"))
        if unitLevel and unitLevel > 0 then
            level = unitLevel
        end
    end
    return ("item:%d::::::::%d::::%d:%s"):format(itemID, level, #bonusIDs, table.concat(bonusIDs, ":"))
end

local function GetEntryItemID(entry)
    if type(entry) ~= "table" then return nil end
    local item = entry.item
    if type(item) == "table" then
        return SafeNumber(item.item_id)
    end
    return SafeNumber(entry.item_id)
end

local function GetEntryStaticName(entry)
    if type(entry) ~= "table" then return nil end
    local item = entry.item
    if type(item) == "table" and type(item.name) == "string" and item.name ~= "" then
        return item.name
    end
    if type(entry.name) == "string" and entry.name ~= "" then
        return entry.name
    end
    return nil
end

local function GetItemInfoByLinkOrID(itemLink, itemID)
    if C_Item and type(C_Item.GetItemInfo) == "function" then
        if itemLink then
            local ok, name, link, quality = pcall(C_Item.GetItemInfo, itemLink)
            if ok and name then return name, link or itemLink, quality end
        end
        if itemID then
            local ok, name, link, quality = pcall(C_Item.GetItemInfo, itemID)
            if ok and name then return name, link, quality end
        end
    end
    if type(GetItemInfo) == "function" then
        if itemLink then
            local name, link, quality = GetItemInfo(itemLink)
            if name then return name, link or itemLink, quality end
        end
        if itemID then
            local name, link, quality = GetItemInfo(itemID)
            if name then return name, link, quality end
        end
    end
    return nil, itemLink, nil
end

local function GetQualityHex(quality)
    quality = SafeNumber(quality)
    if quality ~= nil and type(GetItemQualityColor) == "function" then
        local _, _, _, hex = GetItemQualityColor(quality)
        if type(hex) == "string" and hex ~= "" then
            if hex:sub(1, 2) == "|c" then
                return hex
            end
            return "|c" .. hex
        end
    end
    return "|cffdbdbdb"
end

local function GetLinkItemLevel(itemLink)
    if not itemLink then return nil end
    if ns.GetItemLevel then
        local level = SafeNumber(ns.GetItemLevel(itemLink))
        if level then return level end
    end
    if C_Item and type(C_Item.GetDetailedItemLevelInfo) == "function" then
        local ok, level = pcall(C_Item.GetDetailedItemLevelInfo, itemLink)
        if ok then return SafeNumber(level) end
    end
    if type(GetDetailedItemLevelInfo) == "function" then
        local ok, level = pcall(GetDetailedItemLevelInfo, itemLink)
        if ok then return SafeNumber(level) end
    end
    return nil
end

local function ResolveDisplayItem(entry)
    local itemID = GetEntryItemID(entry)
    local bonusIDs = GetBonusIDs(entry)
    local itemLink = BuildItemLink(itemID, bonusIDs)
    local name, resolvedLink, quality = GetItemInfoByLinkOrID(itemLink, itemID)
    if not name then
        RequestItemLoad(itemID)
        name = GetEntryStaticName(entry)
    end
    if not name or name == "" then
        name = itemID and ("item:" .. tostring(itemID)) or "Unknown item"
    end
    local displayLink = resolvedLink or itemLink
    local itemLevel = GetLinkItemLevel(displayLink)
    return {
        itemID = itemID,
        name = name,
        link = displayLink,
        quality = quality,
        itemLevel = itemLevel,
        bonusIDs = bonusIDs,
    }
end

local function ScanOwnedItemLevels()
    local equippedCounts, bagCounts = {}, {}
    local equippedLevels, bagLevels = {}, {}

    local function note(mapCounts, mapLevels, itemID, itemLink)
        itemID = SafeNumber(itemID)
        if not itemID then return end
        mapCounts[itemID] = (mapCounts[itemID] or 0) + 1
        local level = GetLinkItemLevel(itemLink)
        if level then
            local previous = mapLevels[itemID]
            if not previous or level > previous then
                mapLevels[itemID] = level
            end
        end
    end

    if type(GetInventoryItemLink) == "function" then
        for slot = 1, 19 do
            local link = GetInventoryItemLink("player", slot)
            if link then
                local itemID = SafeNumber(link:match("item:(%d+)"))
                    or (type(GetInventoryItemID) == "function" and SafeNumber(GetInventoryItemID("player", slot)))
                note(equippedCounts, equippedLevels, itemID, link)
            end
        end
    end

    if C_Container and type(C_Container.GetContainerNumSlots) == "function" then
        for bag = 0, 5 do
            local slots = SafeNumber(C_Container.GetContainerNumSlots(bag)) or 0
            for slot = 1, slots do
                local link = nil
                if type(C_Container.GetContainerItemLink) == "function" then
                    link = C_Container.GetContainerItemLink(bag, slot)
                end
                local itemID = nil
                if link then
                    itemID = SafeNumber(link:match("item:(%d+)"))
                elseif type(C_Container.GetContainerItemID) == "function" then
                    itemID = SafeNumber(C_Container.GetContainerItemID(bag, slot))
                end
                if itemID then
                    note(bagCounts, bagLevels, itemID, link)
                end
            end
        end
    end

    return equippedCounts, bagCounts, equippedLevels, bagLevels
end

local function HideTooltip(row)
    if GameTooltip and GameTooltip:IsOwned(row) then
        GameTooltip:Hide()
    end
end

local function ShowItemTooltip(row)
    if not row or not row.itemLink then return end
    if not GameTooltip then return end
    GameTooltip:SetOwner(row, "ANCHOR_RIGHT")
    GameTooltip:SetHyperlink(row.itemLink)
    GameTooltip:Show()
end

local function EnsureRowMouse(row)
    if row.StatVerdictMouseReady then return end
    row.StatVerdictMouseReady = true
    row:EnableMouse(true)
    row:SetScript("OnEnter", function(self)
        ShowItemTooltip(self)
    end)
    row:SetScript("OnLeave", function(self)
        HideTooltip(self)
    end)
end

local function SetRowOwnership(row, state)
    if state == "equipped" then
        row.status:SetText("|cff20e060E|r")
    elseif state == "bag" then
        row.status:SetText("|cffffcc20B|r")
    else
        row.status:SetText("|cff777777-|r")
    end
end

local function SetRowOwnedLevel(row, ownedLevel)
    if ownedLevel and ownedLevel > 0 then
        row.ownedIlvl:SetText(tostring(ownedLevel))
        row.ownedIlvl:SetTextColor(0.40, 0.80, 1.00)
    else
        row.ownedIlvl:SetText("-")
        row.ownedIlvl:SetTextColor(0.45, 0.45, 0.45)
    end
end

local function SetRowItemVisual(row, display)
    EnsureRowMouse(row)
    row.itemLink = display.link
    row.itemID = display.itemID

    -- Name only, rarity-colored. Target/max ilvl lives in the tooltip via bonus IDs.
    local coloredName = GetQualityHex(display.quality) .. tostring(display.name or "Unknown item") .. "|r"
    row.name:SetText(coloredName)
    row.name:SetTextColor(1, 1, 1)
end

local function OwnershipState(itemID, occurrence, equippedCounts, bagCounts)
    if not itemID then return "missing" end
    local equippedCount = equippedCounts[itemID] or 0
    local bagCount = bagCounts[itemID] or 0
    if occurrence <= equippedCount then
        return "equipped"
    end
    if occurrence <= (equippedCount + bagCount) then
        return "bag"
    end
    return "missing"
end

local ROW_LAYOUT_VERSION = 10
-- Title chip sits near TOP (-12). List content starts below it; AdvDev can nudge further.
local CONTENT_TOP_BASE = -50

local function EnsureContentHost(card)
    if not card then return nil end
    local host = card.contentHost
    if host then
        if ns.UnregisterDevLayoutBorderEditOnly then
            ns.UnregisterDevLayoutBorderEditOnly(host, 0, 0, 0, 0)
        end
        if host.SetBackdrop then
            host:SetBackdrop(nil)
        end
        return host
    end

    host = CreateFrame("Frame", nil, card)
    host:EnableMouse(false)
    host:SetPoint("TOPLEFT", card, "TOPLEFT", 0, CONTENT_TOP_BASE)
    host:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", 0, 0)

    for index, row in ipairs(card.rows or {}) do
        row:SetParent(host)
        row:ClearAllPoints()
        row:SetPoint("TOPLEFT", host, "TOPLEFT", 10, -((index - 1) * 21))
    end
    if card.summary then
        card.summary:SetParent(host)
        card.summary:ClearAllPoints()
        card.summary:SetPoint("BOTTOMLEFT", host, "BOTTOMLEFT", 12, 12)
    end

    card.contentHost = host
    return host
end

local function LayoutContentHost(card)
    local host = EnsureContentHost(card)
    if not host then return end

    -- Content host is not an AdvDev target — orphan cyan boxes over the list.
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("bisTrinkets.content")
    end
    if ns.UnregisterDevLayoutBorderEditOnly then
        ns.UnregisterDevLayoutBorderEditOnly(host, 0, 0, 0, 0)
    elseif host.SetBackdropBorderColor then
        host:SetBackdropBorderColor(0, 0, 0, 0)
    end

    host:ClearAllPoints()
    host:SetPoint("TOPLEFT", card, "TOPLEFT", 0, CONTENT_TOP_BASE)
    host:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", 0, 0)
    host:Show()
    if host.SetBackdrop then
        host:SetBackdrop(nil)
    end

    for index, row in ipairs(card.rows or {}) do
        row:ClearAllPoints()
        row:SetPoint("TOPLEFT", host, "TOPLEFT", 10, -((index - 1) * 21))
    end
    if card.summary then
        card.summary:ClearAllPoints()
        card.summary:SetPoint("BOTTOMLEFT", host, "BOTTOMLEFT", 12, 12)
    end
end

-- Row columns: status | slotLabel | ownedIlvl/dash | item name
-- Equal padding on both sides of the owned-ilvl / "-".
-- BiS keeps the ideal gap; Ranked Trinkets use a slightly tighter one.
local GAP_AROUND_DASH_BIS = 16
local GAP_AROUND_DASH_TRINKETS = 10
local OWNED_COL_MIN = 12
local SLOT_COL_MIN = 36

local function GapsForMode(showTrinkets)
    local gap = showTrinkets and GAP_AROUND_DASH_TRINKETS or GAP_AROUND_DASH_BIS
    return gap, gap
end

local function EnsurePanel(frame)
    if frame.bisProgressCard and frame.bisProgressCard.layoutVersion == ROW_LAYOUT_VERSION then
        return frame.bisProgressCard
    end
    if frame.bisProgressCard then
        frame.bisProgressCard:Hide()
        frame.bisProgressCard = nil
    end

    local card = CreateFrame("Frame", nil, frame, "BackdropTemplate")
    card.layoutVersion = ROW_LAYOUT_VERSION
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
    card.title:SetText(ns.GetReferenceWording and ns.GetReferenceWording().base or "Best in Slot")
    card.title:SetTextColor(1.0, 0.82, 0.0)

    card.titleHit = CreateFrame("Frame", nil, card)
    card.titleHit:EnableMouse(false)
    card.titleHit:SetPoint("TOPLEFT", card.title, "TOPLEFT", -2, 2)
    card.titleHit:SetSize(110, 16)

    local contentHost = CreateFrame("Frame", nil, card)
    contentHost:EnableMouse(false)
    contentHost:SetPoint("TOPLEFT", card, "TOPLEFT", 0, CONTENT_TOP_BASE)
    contentHost:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", 0, 0)
    card.contentHost = contentHost

    card.summary = contentHost:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.summary:SetPoint("BOTTOMLEFT", contentHost, "BOTTOMLEFT", 12, 12)
    card.summary:SetText((ns.GetReferenceWording and ns.GetReferenceWording().progress or "BiS Progress") .. ": -")

    card.rows = {}
    for index = 1, MAX_ROWS do
        local row = CreateFrame("Frame", nil, contentHost)
        row:SetPoint("TOPLEFT", contentHost, "TOPLEFT", 10, -((index - 1) * 21))
        row:SetSize(326, 20)

        -- E / B / -
        row.status = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        row.status:SetPoint("LEFT", row, "LEFT", 0, 0)
        row.status:SetWidth(16)
        row.status:SetJustifyH("LEFT")

        -- Helm / Hands / #1 A ...
        row.slot = row:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        row.slot:SetPoint("LEFT", row.status, "RIGHT", 2, 0)
        row.slot:SetWidth(SLOT_COL_MIN)
        row.slot:SetJustifyH("LEFT")
        row.slot:SetTextColor(0.72, 0.72, 0.72)

        -- Owned item level, or "-" if missing
        row.ownedIlvl = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        row.ownedIlvl:SetPoint("LEFT", row.slot, "RIGHT", GAP_AROUND_DASH_BIS, 0)
        row.ownedIlvl:SetWidth(OWNED_COL_MIN)
        row.ownedIlvl:SetJustifyH("LEFT")
        row.ownedIlvl:SetText("-")
        row.ownedIlvl:SetTextColor(0.45, 0.45, 0.45)

        -- Item name (rarity color)
        row.name = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        row.name:SetPoint("LEFT", row.ownedIlvl, "RIGHT", GAP_AROUND_DASH_BIS, 0)
        row.name:SetPoint("RIGHT", row, "RIGHT", -4, 0)
        row.name:SetJustifyH("LEFT")
        row.name:SetWordWrap(false)

        EnsureRowMouse(row)
        card.rows[index] = row
    end

    frame.bisProgressCard = card
    return card
end

function Panel.Apply(frame)
    local card = EnsurePanel(frame)
    local cardX = Offset("bis.card")
    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    local showTrinkets = mode == "trinkets"
    local widthKey = showTrinkets and "trinkets.width" or "bis.width"
    local cardWidth
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelWidth then
        cardWidth = ns.StatVerdictDashboardLayout.GetRightPanelWidth(frame)
    else
        cardWidth = SafeNumber(card.preferredWidth) or ((showTrinkets and 300 or 360) + SizeDelta(widthKey))
    end
    if cardWidth < 220 then cardWidth = 220 end
    if cardWidth > 720 then cardWidth = 720 end
    local panelX = 770 + cardX
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelX then
        panelX = ns.StatVerdictDashboardLayout.GetRightPanelX(frame)
    end

    local cardKey = showTrinkets and "trinkets.card" or "bis.card"
    local cardLabel = showTrinkets and "Ranked Trinkets drawer" or "Best in Slot drawer"
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad(cardKey)
        or { top = 0, bottom = 0, left = 0, right = 0 }
    local visibleWidth = math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0))
    card:SetWidth(visibleWidth)
    -- Same top/bottom band as Setup and Stat Progress (ignore legacy vertical group nudge).
    local extra = 0
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelExtraGap then
        extra = ns.StatVerdictDashboardLayout.GetRightPanelExtraGap()
    end
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard and frame.statProgressCard then
        ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, extra, 0, cardPad)
    elseif ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorOuterCard then
        ns.StatVerdictDashboardLayout.AnchorOuterCard(card, frame, panelX, cardPad)
    else
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", panelX, -34)
        card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", panelX, 14)
    end
    -- Whole card is the AdvDev target: Move X (shared dock) + Size W + Padding.
    if ns.ApplyRightDrawerCardDev then
        local baseW
        if showTrinkets then
            baseW = SafeNumber(card.trinketsPreferredWidth) or SafeNumber(card.preferredWidth) or 300
        else
            baseW = SafeNumber(card.bisPreferredWidth) or SafeNumber(card.preferredWidth) or 360
        end
        ns.ApplyRightDrawerCardDev(card, cardKey, cardLabel, widthKey, baseW)
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion(showTrinkets and "bis.card" or "trinkets.card")
    end

    LayoutContentHost(card)

    for _, row in ipairs(card.rows or {}) do
        row:SetWidth(math.max(80, visibleWidth - 20))
    end

    -- Outer pad owns Size W — retire the legacy width strip and left-edge Y strip.
    if frame.devBisWidthRegion then
        frame.devBisWidthRegion:Hide()
    end
    if frame.devBisTrinketsGroupRegion then
        frame.devBisTrinketsGroupRegion:Hide()
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("bisTrinkets.width")
        ns.UnregisterDevLayoutRegion("bisTrinkets.group")
        ns.UnregisterDevLayoutRegion("bisTrinkets.content")
        ns.UnregisterDevLayoutRegion("bis.width")
        ns.UnregisterDevLayoutRegion("trinkets.width")
    end
    if card.titleHit then
        card.titleHit:Hide()
        if ns.UnregisterDevLayoutRegion then
            ns.UnregisterDevLayoutRegion("bis.titleHit")
            ns.UnregisterDevLayoutRegion("trinkets.titleHit")
        end
    end
end

function Panel.GetPreferredWidth(frame)
    local card = frame and frame.bisProgressCard
    if not card then return nil end
    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    if mode == "trinkets" then
        return SafeNumber(card.trinketsPreferredWidth) or SafeNumber(card.preferredWidth)
    end
    if mode == "bis" then
        return SafeNumber(card.bisPreferredWidth) or SafeNumber(card.preferredWidth)
    end
    return SafeNumber(card.preferredWidth)
end

local function MeasureAndApplyAutoWidth(frame, card, showTrinkets)
    local gapSlotToOwned, gapOwnedToName = GapsForMode(showTrinkets)
    local maxSlotW, maxOwnedW, maxNameW = 0, 0, 0
    for _, row in ipairs(card.rows or {}) do
        if row:IsShown() then
            if row.slot and row.slot.GetStringWidth then
                local w = row.slot:GetStringWidth() or 0
                if w > maxSlotW then maxSlotW = w end
            end
            if row.ownedIlvl and row.ownedIlvl.GetStringWidth then
                local w = row.ownedIlvl:GetStringWidth() or 0
                if w > maxOwnedW then maxOwnedW = w end
            end
            if row.name and row.name.GetStringWidth then
                local w = row.name:GetStringWidth() or 0
                if w > maxNameW then maxNameW = w end
            end
        end
    end
    if maxSlotW < SLOT_COL_MIN then maxSlotW = SLOT_COL_MIN end
    if maxOwnedW < OWNED_COL_MIN then maxOwnedW = OWNED_COL_MIN end
    maxSlotW = math.ceil(maxSlotW)
    maxOwnedW = math.ceil(maxOwnedW)

    for _, row in ipairs(card.rows or {}) do
        row.slot:SetWidth(maxSlotW)
        row.ownedIlvl:SetWidth(maxOwnedW)
        row.ownedIlvl:ClearAllPoints()
        row.ownedIlvl:SetPoint("LEFT", row.slot, "RIGHT", gapSlotToOwned, 0)
        row.name:ClearAllPoints()
        row.name:SetPoint("LEFT", row.ownedIlvl, "RIGHT", gapOwnedToName, 0)
        row.name:SetPoint("RIGHT", row, "RIGHT", -4, 0)
    end

    -- status(16)+gap(2)+slot+gap+owned+gap+name+padding
    local preferred = math.ceil(16 + 2 + maxSlotW + gapSlotToOwned + maxOwnedW + gapOwnedToName + maxNameW + 24)
    if preferred < 240 then preferred = 240 end
    if preferred > 720 then preferred = 720 end
    card.preferredWidth = preferred
    if showTrinkets then
        card.trinketsPreferredWidth = preferred
    else
        card.bisPreferredWidth = preferred
    end

    local widthKey = showTrinkets and "trinkets.width" or "bis.width"
    local delta = SizeDelta(widthKey)
    -- Migrate once from the old shared key if this mode has no own delta yet.
    if delta == 0 then
        delta = SizeDelta("bisTrinkets.width")
    end
    local finalW = preferred + delta
    if finalW < 220 then finalW = 220 end
    if finalW > 720 then finalW = 720 end

    -- Padding is a visual inset: the card renders narrower but finalW stays
    -- the logical width used for frame sizing.
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad(showTrinkets and "trinkets.card" or "bis.card")
        or { top = 0, bottom = 0, left = 0, right = 0 }
    local visibleW = math.max(120, finalW - (cardPad.left or 0) - (cardPad.right or 0))

    card:SetWidth(visibleW)
    for _, row in ipairs(card.rows or {}) do
        row:SetWidth(math.max(80, visibleW - 20))
    end

    -- Always resize main frame to the right panel's actual width (not a stale/shrunk delta).
    if frame and ns.StatVerdictDashboardLayout then
        local usedRows = frame.StatVerdictUsedRows or 4
        local layoutToken = (showTrinkets and "trinkets:" or "bis:") .. tostring(preferred) .. ":" .. tostring(finalW)
        if card.lastLayoutPreferredWidth ~= layoutToken then
            card.lastLayoutPreferredWidth = layoutToken
            if ns.StatVerdictDashboardLayout.Apply then
                ns.StatVerdictDashboardLayout.Apply(frame, usedRows, frame.StatVerdictLayoutControls)
            end
        end
        if ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
            ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
        end
    end
end

local function CacheBisProgress(profile)
    ns.StatVerdictProgressCache = ns.StatVerdictProgressCache or {}
    local generated = type(profile) == "table" and profile.generatedContext or nil
    local bis = type(generated) == "table" and generated.bis or nil
    local slots = type(bis) == "table" and bis.slots or nil
    if type(slots) ~= "table" then
        ns.StatVerdictProgressCache.bis = nil
        return
    end

    local equippedCounts, bagCounts = ScanOwnedItemLevels()
    local seenRequired = {}
    local owned, total = 0, 0
    for index = 1, #slots do
        local entry = slots[index]
        if entry then
            local display = ResolveDisplayItem(entry)
            local occurrence = 1
            if display.itemID then
                seenRequired[display.itemID] = (seenRequired[display.itemID] or 0) + 1
                occurrence = seenRequired[display.itemID]
            end
            total = total + 1
            local state = OwnershipState(display.itemID, occurrence, equippedCounts, bagCounts)
            if state ~= "missing" then
                owned = owned + 1
            end
        end
    end
    ns.StatVerdictProgressCache.bis = {
        owned = owned,
        total = total,
    }
end

function Panel.UpdateProgressCache(profile)
    CacheBisProgress(profile)
end

function Panel.Refresh(frame, profile)
    local card = EnsurePanel(frame)
    lastRefreshFrame = frame
    if not profile and ns.GetActivePanelContext then
        local context = ns.GetActivePanelContext()
        profile = context and context.profile or nil
    end
    lastRefreshProfile = profile
    CacheBisProgress(profile)

    local mode = ns.GetRightPanelMode and ns.GetRightPanelMode() or nil
    if mode ~= "bis" and mode ~= "trinkets" then
        card:Hide()
        if ns.HideMsOsViewTabs then
            ns.HideMsOsViewTabs(card)
        end
        return
    end
    local showTrinkets = mode == "trinkets"
    local showBis = mode == "bis"
    if not showBis and not showTrinkets then
        card:Hide()
        return
    end
    card:Show()

    -- Unified title chip replaces gold FontString + separate Main/Off Spec toggle.
    if card.title then
        card.title:Hide()
        card.title:SetText("")
    end
    if card.titleHit then
        card.titleHit:Hide()
    end

    local generated = type(profile) == "table" and profile.generatedContext or nil
    local equippedCounts, bagCounts, equippedLevels, bagLevels = ScanOwnedItemLevels()

    if showTrinkets then
        local trinkets = type(generated) == "table" and generated.trinkets or nil
        local shown = 0
        local owned = 0
        for index, row in ipairs(card.rows) do
            local entry = type(trinkets) == "table" and trinkets[index] or nil
            if entry then
                shown = shown + 1
                local display = ResolveDisplayItem(entry)
                local state = OwnershipState(display.itemID, 1, equippedCounts, bagCounts)
                if state ~= "missing" then owned = owned + 1 end

                local tier = tostring(entry.tier or "-")
                local tierColor = TIER_COLOR[tier] or "|cff9d9d9d"
                row.slot:SetText(tierColor .. "#" .. tostring(index) .. " " .. tier .. "|r")

                local ownedLevel = nil
                if state == "equipped" then
                    ownedLevel = display.itemID and equippedLevels[display.itemID] or nil
                elseif state == "bag" then
                    ownedLevel = display.itemID and bagLevels[display.itemID] or nil
                end

                SetRowOwnership(row, state)
                SetRowOwnedLevel(row, ownedLevel)
                SetRowItemVisual(row, display)
                row:Show()
            else
                row.itemLink = nil
                row:Hide()
            end
        end
        card.summary:SetText(string.format("Trinkets: %d ranked · Owned %d/%d", shown, owned, shown))
        card.summary:SetTextColor(1.00, 0.82, 0.20)
        MeasureAndApplyAutoWidth(frame, card, true)
        if ns.PlaceMsOsTitleChip then
            ns.PlaceMsOsTitleChip(card, "trinkets", "trinkets")
        elseif ns.PlaceMsOsViewTabs then
            ns.PlaceMsOsViewTabs(card, card, 0, "trinkets")
        end
        return
    end

    local bis = type(generated) == "table" and generated.bis or nil
    local slots = type(bis) == "table" and bis.slots or nil
    local seenRequired = {}
    local owned, total = 0, 0

    for index, row in ipairs(card.rows) do
        local entry = type(slots) == "table" and slots[index] or nil
        if entry then
            local display = ResolveDisplayItem(entry)
            local occurrence = 1
            if display.itemID then
                seenRequired[display.itemID] = (seenRequired[display.itemID] or 0) + 1
                occurrence = seenRequired[display.itemID]
            end

            local state = OwnershipState(display.itemID, occurrence, equippedCounts, bagCounts)
            total = total + 1
            if state ~= "missing" then owned = owned + 1 end

            local ownedLevel = nil
            if state == "equipped" then
                ownedLevel = display.itemID and equippedLevels[display.itemID] or nil
            elseif state == "bag" then
                ownedLevel = display.itemID and bagLevels[display.itemID] or nil
            end

            row.slot:SetText(tostring(entry.slot or "-"))
            SetRowOwnership(row, state)
            SetRowOwnedLevel(row, ownedLevel)
            SetRowItemVisual(row, display)
            row:Show()
        else
            row.itemLink = nil
            row:Hide()
        end
    end

    local wording = ns.GetReferenceWording and ns.GetReferenceWording() or nil
    card.summary:SetText(string.format(
        "%s: %d/%d%s",
        wording and wording.progress or "BiS Progress",
        owned,
        total,
        wording and wording.progressSuffix or ""
    ))
    if total > 0 and owned >= total then
        card.summary:SetTextColor(0.20, 1.00, 0.35)
    else
        card.summary:SetTextColor(1.00, 0.82, 0.20)
    end
    MeasureAndApplyAutoWidth(frame, card, false)
    if ns.PlaceMsOsTitleChip then
        ns.PlaceMsOsTitleChip(card, "bis", "bis")
    elseif ns.PlaceMsOsViewTabs then
        ns.PlaceMsOsViewTabs(card, card, 0, "bis")
    end
end

if not refreshFrame then
    refreshFrame = CreateFrame("Frame")
    refreshFrame:RegisterEvent("GET_ITEM_INFO_RECEIVED")
    refreshFrame:SetScript("OnEvent", function(_, event, itemID)
        if event ~= "GET_ITEM_INFO_RECEIVED" then return end
        itemID = SafeNumber(itemID)
        if not itemID or not pendingItemLoads[itemID] then return end
        pendingItemLoads[itemID] = nil
        if lastRefreshFrame and lastRefreshProfile and Panel.Refresh then
            Panel.Refresh(lastRefreshFrame, lastRefreshProfile)
        elseif ns.RequestStatAuditRefresh then
            ns.RequestStatAuditRefresh()
        end
    end)
end
