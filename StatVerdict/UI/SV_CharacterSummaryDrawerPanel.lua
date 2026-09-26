local addonName, ns = ...

local Panel = {}
ns.StatVerdictCharacterSummaryDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 300
local ROW_HEIGHT = 18
local HEADER_HEIGHT = 18
local SCROLL_BOTTOM_PAD = 14
local SCROLL_SIDE_PAD = 10
local SCROLLBAR_WIDTH = 18
local LABEL_COLOR = { 0.92, 0.82, 0.45 }
local VALUE_COLOR = { 1, 1, 1 }
local HEADER_COLOR = { 1.0, 0.82, 0.0 }
local LABEL_VALUE_GAP = 6
local BLOCK_GAP = 8
-- Independent of card width: shrinking the drawer only crops empty space, not text.
local DEFAULT_BLOCK_WIDTH = 210

local function Offset(key)
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function HeightDelta(key)
    if ns.GetDevLayoutHeightDelta then return ns.GetDevLayoutHeightDelta(key) end
    return 0
end

local function Padding(key)
    if ns.GetDevLayoutPadding then return ns.GetDevLayoutPadding(key) end
    return { top = 0, bottom = 0, left = 0, right = 0 }
end

local function Register(key, label, region, options)
    if ns.RegisterDevLayoutRegion then ns.RegisterDevLayoutRegion(key, label, region, options) end
end

local function GlobalText(key, fallback)
    local text = _G[key]
    if type(text) == "string" and text ~= "" then return text end
    return fallback
end

local function EnsureProxy(card)
    if card.blizzardProxy then return card.blizzardProxy end
    local proxy = CreateFrame("Frame", nil, UIParent)
    proxy:Hide()
    proxy:SetSize(1, 1)
    proxy.Label = proxy:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    proxy.Value = proxy:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.blizzardProxy = proxy
    return proxy
end

local function ResetProxy(proxy)
    proxy.onEnterFunc = nil
    proxy.UpdateTooltip = nil
    proxy.tooltip = nil
    proxy.tooltip2 = nil
    proxy.tooltip3 = nil
    proxy.numericValue = nil
    proxy.spellCrit = nil
    proxy.speed = nil
    proxy.runSpeed = nil
    proxy.flightSpeed = nil
    proxy.swimSpeed = nil
    proxy.unit = nil
    if proxy.Label then proxy.Label:SetText("") end
    if proxy.Value then proxy.Value:SetText("") end
    proxy:Show()
end

local function CaptureProxy(proxy)
    return {
        kind = "stat",
        label = proxy.Label and proxy.Label:GetText() or "",
        value = proxy.Value and proxy.Value:GetText() or "",
        numericValue = proxy.numericValue,
        tooltip = proxy.tooltip,
        tooltip2 = proxy.tooltip2,
        tooltip3 = proxy.tooltip3,
        onEnterFunc = proxy.onEnterFunc,
        UpdateTooltip = proxy.UpdateTooltip,
        spellCrit = proxy.spellCrit,
        speed = proxy.speed,
        runSpeed = proxy.runSpeed,
        flightSpeed = proxy.flightSpeed,
        swimSpeed = proxy.swimSpeed,
        unit = proxy.unit,
    }
end

local function CategoryTitle(categoryFrameName)
    if CharacterStatsPane and categoryFrameName and CharacterStatsPane[categoryFrameName] then
        local cat = CharacterStatsPane[categoryFrameName]
        if cat.Title and cat.Title.GetText then
            local text = cat.Title:GetText()
            if type(text) == "string" and text ~= "" then
                return text
            end
        end
    end
    if categoryFrameName == "AttributesCategory" then
        return GlobalText("STAT_CATEGORY_ATTRIBUTES", "Attributes")
    end
    if categoryFrameName == "EnhancementsCategory" then
        return GlobalText("STAT_CATEGORY_ENHANCEMENTS", "Enhancements")
    end
    return categoryFrameName or "Stats"
end

local function SecureCall(func, ...)
    if type(func) ~= "function" then return end
    if type(securecallfunction) == "function" then
        return securecallfunction(func, ...)
    end
    return func(...)
end

local function ShouldShowStat(stat, spec, role)
    local showStat = true
    if showStat and stat.primary and spec and C_SpecializationInfo and C_SpecializationInfo.GetSpecializationInfo then
        local primaryStat = select(6, C_SpecializationInfo.GetSpecializationInfo(spec, false, false, nil, UnitSex("player")))
        if stat.primary ~= primaryStat then
            showStat = false
        end
    end
    if showStat and stat.roles then
        local foundRole = false
        for _, statRole in pairs(stat.roles) do
            if role == statRole then
                foundRole = true
                break
            end
        end
        showStat = foundRole
    end
    if showStat and stat.showFunc then
        local ok, result = pcall(function()
            return SecureCall(stat.showFunc)
        end)
        showStat = ok and result and true or false
    end
    return showStat
end

local function RunPaperDollUpdate(updateFunc, proxy)
    ResetProxy(proxy)
    SecureCall(updateFunc, proxy, "player")
end

local function KeepStatAfterUpdate(stat, proxy)
    return SecureCall(function()
        if not proxy:IsShown() then
            return false
        end
        if stat.hideAt ~= nil and stat.hideAt == proxy.numericValue then
            return false
        end
        return true
    end)
end

-- Returns structured sections (no Item Level category header).
local function CollectBlizzardSections(proxy)
    local sections = {
        itemLevel = nil,
        attributesTitle = nil,
        attributes = {},
        enhancementsTitle = nil,
        enhancements = {},
    }
    if type(PAPERDOLL_STATINFO) ~= "table" or type(PAPERDOLL_STATCATEGORIES) ~= "table" then
        return sections
    end

    local spec, role
    if C_SpecializationInfo and C_SpecializationInfo.GetSpecialization then
        spec = C_SpecializationInfo.GetSpecialization()
    end
    if spec and type(GetSpecializationRoleEnum) == "function" then
        role = GetSpecializationRoleEnum(spec)
    end

    local minLevel = tonumber(MIN_PLAYER_LEVEL_FOR_ITEM_LEVEL_DISPLAY) or 1
    local playerLevel = UnitLevel("player") or 1
    if playerLevel >= minLevel and type(PaperDollFrame_SetItemLevel) == "function" then
        RunPaperDollUpdate(PaperDollFrame_SetItemLevel, proxy)
        local itemEntry = CaptureProxy(proxy)
        itemEntry.isItemLevel = true
        sections.itemLevel = itemEntry
    end

    for catIndex = 1, #PAPERDOLL_STATCATEGORIES do
        local cat = PAPERDOLL_STATCATEGORIES[catIndex]
        local bucket = nil
        local titleKey = nil
        if cat.categoryFrame == "AttributesCategory" then
            bucket = sections.attributes
            titleKey = "attributesTitle"
        elseif cat.categoryFrame == "EnhancementsCategory" then
            bucket = sections.enhancements
            titleKey = "enhancementsTitle"
        end
        if bucket then
            for statIndex = 1, #(cat.stats or {}) do
                local stat = cat.stats[statIndex]
                local info = stat and PAPERDOLL_STATINFO[stat.stat] or nil
                if info and type(info.updateFunc) == "function" and ShouldShowStat(stat, spec, role) then
                    RunPaperDollUpdate(info.updateFunc, proxy)
                    if KeepStatAfterUpdate(stat, proxy) then
                        bucket[#bucket + 1] = CaptureProxy(proxy)
                    end
                end
            end
            if #bucket > 0 then
                sections[titleKey] = CategoryTitle(cat.categoryFrame)
            end
        end
    end

    return sections
end

local function FormatStatNumber(value)
    value = tonumber(value)
    if not value then return "-" end
    if math.abs(value - math.floor(value + 0.5)) < 0.05 then
        return string.format("%.0f", value)
    end
    return string.format("%.1f", value)
end

-- Map Blizzard character-sheet stat ids → snapshot displayStat keys.
local PAPERDOLL_TO_SNAPSHOT = {
    STRENGTH = "ITEM_MOD_STRENGTH_SHORT",
    AGILITY = "ITEM_MOD_AGILITY_SHORT",
    INTELLECT = "ITEM_MOD_INTELLECT_SHORT",
    STAMINA = "ITEM_MOD_STAMINA_SHORT",
    CRITCHANCE = "ITEM_MOD_CRIT_RATING_SHORT",
    HASTE = "ITEM_MOD_HASTE_RATING_SHORT",
    MASTERY = "ITEM_MOD_MASTERY_RATING_SHORT",
    VERSATILITY = "ITEM_MOD_VERSATILITY",
    LIFESTEAL = "ITEM_MOD_LIFESTEAL",
    AVOIDANCE = "ITEM_MOD_AVOIDANCE_RATING_SHORT",
    SPEED = "ITEM_MOD_SPEED",
    MOVESPEED = "ITEM_MOD_SPEED",
    ARMOR = "STATVERDICT_ARMOR",
}

local PAPERDOLL_LABEL_FALLBACK = {
    STRENGTH = "Strength",
    AGILITY = "Agility",
    INTELLECT = "Intellect",
    STAMINA = "Stamina",
    CRITCHANCE = "Critical Strike",
    HASTE = "Haste",
    MASTERY = "Mastery",
    VERSATILITY = "Versatility",
    LIFESTEAL = "Leech",
    AVOIDANCE = "Avoidance",
    SPEED = "Speed",
    MOVESPEED = "Speed",
    ARMOR = "Armor",
}

local function SnapshotStatLabel(statKey, paperStatId)
    if paperStatId then
        local globalKey = "STAT_" .. tostring(paperStatId)
        local fromGlobal = GlobalText(globalKey, nil)
        if fromGlobal and fromGlobal ~= globalKey then
            return fromGlobal
        end
        if PAPERDOLL_LABEL_FALLBACK[paperStatId] then
            return PAPERDOLL_LABEL_FALLBACK[paperStatId]
        end
    end
    if ns.StatNames and ns.StatNames[statKey] then
        return ns.StatNames[statKey]
    end
    return PAPERDOLL_LABEL_FALLBACK[tostring(statKey)] or tostring(statKey or "-")
end

local function ResolveProfileSpecIndex(profile)
    local specID = tonumber(profile and (profile.specID or profile.specId))
    if not specID then return nil end
    if type(GetNumSpecializations) ~= "function" or type(GetSpecializationInfo) ~= "function" then
        return nil
    end
    for index = 1, GetNumSpecializations() do
        local id = select(1, GetSpecializationInfo(index))
        if tonumber(id) == specID then
            return index
        end
    end
    return nil
end

local function ResolveSnapshotValue(stats, snapshotKey)
    if type(stats) ~= "table" or not snapshotKey then return nil end
    local value = tonumber(stats[snapshotKey])
    if value ~= nil then return value end
    -- Speed is stored under either key depending on capture path.
    if snapshotKey == "ITEM_MOD_SPEED" then
        return tonumber(stats.ITEM_MOD_SPEED_SHORT)
    end
    if snapshotKey == "ITEM_MOD_SPEED_SHORT" then
        return tonumber(stats.ITEM_MOD_SPEED)
    end
    return nil
end

local function AttachBlizzardTipMeta(entry, paperId, proxy)
    if type(entry) ~= "table" or not proxy then return entry end
    local updateFunc = nil
    if paperId and type(PAPERDOLL_STATINFO) == "table" then
        local info = PAPERDOLL_STATINFO[paperId]
        if info and type(info.updateFunc) == "function" then
            updateFunc = info.updateFunc
        end
    elseif entry.isItemLevel and type(PaperDollFrame_SetItemLevel) == "function" then
        updateFunc = PaperDollFrame_SetItemLevel
    end
    if type(updateFunc) ~= "function" then
        return entry
    end

    local savedLabel = entry.label
    local savedValue = entry.value
    local savedNumeric = entry.numericValue
    RunPaperDollUpdate(updateFunc, proxy)
    local tip = CaptureProxy(proxy)
    entry.tooltip = tip.tooltip
    entry.tooltip2 = tip.tooltip2
    entry.tooltip3 = tip.tooltip3
    entry.onEnterFunc = tip.onEnterFunc
    entry.UpdateTooltip = tip.UpdateTooltip
    entry.spellCrit = tip.spellCrit
    entry.speed = tip.speed
    entry.runSpeed = tip.runSpeed
    entry.flightSpeed = tip.flightSpeed
    entry.swimSpeed = tip.swimSpeed
    entry.unit = tip.unit or "player"
    -- Keep snapshot display numbers; only borrow Blizzard's official tip text.
    entry.label = savedLabel
    entry.value = savedValue
    entry.numericValue = savedNumeric
    return entry
end

-- Build Summary rows the same way Character Stats does for the selected profile's spec/role.
local function CollectSnapshotSectionsForProfile(profile, stats, proxy)
    local sections = {
        itemLevel = nil,
        attributesTitle = nil,
        attributes = {},
        enhancementsTitle = nil,
        enhancements = {},
        source = "snapshot",
    }
    if type(stats) ~= "table" then
        return sections
    end

    local ilvl = tonumber(stats.STATVERDICT_ITEM_LEVEL)
    if ilvl then
        sections.itemLevel = {
            kind = "stat",
            label = SnapshotStatLabel("STATVERDICT_ITEM_LEVEL"),
            value = FormatStatNumber(ilvl),
            numericValue = ilvl,
            isItemLevel = true,
        }
        AttachBlizzardTipMeta(sections.itemLevel, nil, proxy)
    end

    local specIndex = ResolveProfileSpecIndex(profile)
    local role = nil
    if specIndex and type(GetSpecializationRoleEnum) == "function" then
        role = GetSpecializationRoleEnum(specIndex)
    end

    if type(PAPERDOLL_STATCATEGORIES) ~= "table" then
        -- Fallback: core ratings only (never dump raw tertiary keys blindly).
        local core = {
            { key = "ITEM_MOD_STRENGTH_SHORT", paper = "STRENGTH" },
            { key = "ITEM_MOD_AGILITY_SHORT", paper = "AGILITY" },
            { key = "ITEM_MOD_INTELLECT_SHORT", paper = "INTELLECT" },
            { key = "ITEM_MOD_STAMINA_SHORT", paper = "STAMINA" },
            { key = "ITEM_MOD_CRIT_RATING_SHORT", paper = "CRITCHANCE" },
            { key = "ITEM_MOD_HASTE_RATING_SHORT", paper = "HASTE" },
            { key = "ITEM_MOD_MASTERY_RATING_SHORT", paper = "MASTERY" },
            { key = "ITEM_MOD_VERSATILITY", paper = "VERSATILITY" },
            { key = "STATVERDICT_ARMOR", paper = "ARMOR" },
        }
        for _, row in ipairs(core) do
            local value = ResolveSnapshotValue(stats, row.key)
            if value and value ~= 0 then
                local bucket = (row.paper == "CRITCHANCE"
                    or row.paper == "HASTE"
                    or row.paper == "MASTERY"
                    or row.paper == "VERSATILITY") and sections.enhancements or sections.attributes
                local entry = {
                    kind = "stat",
                    label = SnapshotStatLabel(row.key, row.paper),
                    value = FormatStatNumber(value),
                    numericValue = value,
                }
                AttachBlizzardTipMeta(entry, row.paper, proxy)
                bucket[#bucket + 1] = entry
            end
        end
        if #sections.attributes > 0 then
            sections.attributesTitle = GlobalText("STAT_CATEGORY_ATTRIBUTES", "Attributes")
        end
        if #sections.enhancements > 0 then
            sections.enhancementsTitle = GlobalText("STAT_CATEGORY_ENHANCEMENTS", "Enhancements")
        end
        return sections
    end

    local seenSnapshotKeys = {}
    for catIndex = 1, #PAPERDOLL_STATCATEGORIES do
        local cat = PAPERDOLL_STATCATEGORIES[catIndex]
        local bucket = nil
        local titleKey = nil
        if cat.categoryFrame == "AttributesCategory" then
            bucket = sections.attributes
            titleKey = "attributesTitle"
        elseif cat.categoryFrame == "EnhancementsCategory" then
            bucket = sections.enhancements
            titleKey = "enhancementsTitle"
        end
        if bucket then
            for statIndex = 1, #(cat.stats or {}) do
                local stat = cat.stats[statIndex]
                local paperId = stat and stat.stat or nil
                local snapshotKey = paperId and PAPERDOLL_TO_SNAPSHOT[paperId] or nil
                if snapshotKey and not seenSnapshotKeys[snapshotKey] and ShouldShowStat(stat, specIndex, role) then
                    local value = ResolveSnapshotValue(stats, snapshotKey)
                    local hideAt = stat.hideAt
                    local keep = value ~= nil
                    if keep and hideAt ~= nil and value == hideAt then
                        keep = false
                    end
                    -- Match character sheet: tertiary ratings with hideAt=0 stay hidden at zero.
                    if keep then
                        seenSnapshotKeys[snapshotKey] = true
                        local entry = {
                            kind = "stat",
                            label = SnapshotStatLabel(snapshotKey, paperId),
                            value = FormatStatNumber(value),
                            numericValue = value,
                        }
                        AttachBlizzardTipMeta(entry, paperId, proxy)
                        bucket[#bucket + 1] = entry
                    end
                end
            end
            if #bucket > 0 then
                sections[titleKey] = CategoryTitle(cat.categoryFrame)
            end
        end
    end

    return sections
end

-- Prefer saved snapshot for the selected MS/OS profile (not necessarily worn gear).
local function CollectSummarySections(proxy, profile)
    local stats = ns.GetProfileSnapshotDisplayStats and select(1, ns.GetProfileSnapshotDisplayStats(profile)) or nil
    if type(stats) == "table" and next(stats) then
        return CollectSnapshotSectionsForProfile(profile, stats, proxy)
    end

    -- Same-spec fallback: Blizzard sheet matches the worn (and auto-snapshotted) loadout.
    local useLive = true
    if profile and ns.ShouldUseEquipmentSnapshot and ns.ShouldUseEquipmentSnapshot(profile) then
        useLive = false
    end
    if useLive then
        local sections = CollectBlizzardSections(proxy)
        sections.source = "live"
        return sections
    end

    return {
        itemLevel = nil,
        attributesTitle = nil,
        attributes = {},
        enhancementsTitle = nil,
        enhancements = {
            {
                kind = "progress",
                label = "Snapshot:",
                value = "missing",
                valueR = { 1.0, 0.45, 0.25 },
                tipTitle = "Snapshot missing",
                tipBody = "Open that specialization once so StatVerdict can capture its gear snapshot.",
            },
        },
        source = "missing",
    }
end

local function FormatProgressPct(avgPct)
    if type(avgPct) ~= "number" then return "-" end
    return string.format("%.1f%%", avgPct)
end

local function ProgressColor(avgPct)
    if type(avgPct) ~= "number" then return 0.72, 0.72, 0.72 end
    if avgPct >= 95 then return 0.2, 1.0, 0.2 end
    if avgPct >= 85 then return 1.0, 0.86, 0.2 end
    return 1.0, 0.25, 0.25
end

local function CollectProgressRows(view)
    local rows = {}
    local cache = ns.StatVerdictProgressCache or {}
    view = (view == "OFF") and "OFF" or "MAIN"

    if view == "OFF" then
        local offPct = cache.OFF and cache.OFF.avgPct or nil
        local offR, offG, offB = ProgressColor(offPct)
        rows[#rows + 1] = {
            kind = "progress",
            label = "Off Spec Progress:",
            value = FormatProgressPct(offPct),
            valueR = { offR, offG, offB },
            tipTitle = "Off Spec Progress",
            tipBody = "Average progress toward your Off Spec stat targets (snapshot loadout).",
        }
    else
        local mainPct = cache.MAIN and cache.MAIN.avgPct or nil
        local mainR, mainG, mainB = ProgressColor(mainPct)
        rows[#rows + 1] = {
            kind = "progress",
            label = "Main Spec Progress:",
            value = FormatProgressPct(mainPct),
            valueR = { mainR, mainG, mainB },
            tipTitle = "Main Spec Progress",
            tipBody = "Average progress toward your Main Spec stat targets (snapshot loadout).",
        }
    end

    local bis = cache.bis
    if type(bis) == "table" and tonumber(bis.total) and bis.total > 0 then
        local owned = tonumber(bis.owned) or 0
        local total = tonumber(bis.total) or 0
        local ratio = total > 0 and (owned / total) * 100 or nil
        local bisR, bisG, bisB = ProgressColor(ratio)
        rows[#rows + 1] = {
            kind = "progress",
            label = "BiS Progress:",
            value = string.format("%d/%d", owned, total),
            valueR = { bisR, bisG, bisB },
            tipTitle = "Best in Slot Progress",
            tipBody = "How many BiS slots you already own (equipped or in bags) for the selected build.",
        }
    else
        rows[#rows + 1] = {
            kind = "progress",
            label = "BiS Progress:",
            value = "-",
            valueR = { 0.72, 0.72, 0.72 },
            tipTitle = "Best in Slot Progress",
            tipBody = "BiS ownership for the selected build. Updates when Stat Progress refreshes.",
        }
    end

    return rows
end

local function AttachBlizzardTooltip(row)
    row:EnableMouse(true)
    row:SetScript("OnEnter", function(self)
        SecureCall(function()
            if type(self.onEnterFunc) == "function" then
                self.onEnterFunc(self)
                return
            end
            if type(PaperDollStatTooltip) == "function" then
                PaperDollStatTooltip(self)
                if GameTooltip and GameTooltip:IsShown() then
                    return
                end
            end
            if not GameTooltip then return end
            if not (self.tooltip or self.tooltip2 or self.tooltip3) then return end
            GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
            GameTooltip:ClearLines()
            if self.tooltip then
                GameTooltip:SetText(tostring(self.tooltip), LABEL_COLOR[1], LABEL_COLOR[2], LABEL_COLOR[3])
            end
            if self.tooltip2 then
                GameTooltip:AddLine(tostring(self.tooltip2), 1, 1, 1, true)
            end
            if self.tooltip3 then
                GameTooltip:AddLine(tostring(self.tooltip3), 1, 1, 1, true)
            end
            GameTooltip:Show()
        end)
    end)
    row:SetScript("OnLeave", function(self)
        self.UpdateTooltip = nil
        if GameTooltip then GameTooltip:Hide() end
    end)
end

local function AttachSimpleTooltip(row, title, body)
    row:EnableMouse(true)
    row:SetScript("OnEnter", function(self)
        if not GameTooltip then return end
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:ClearLines()
        GameTooltip:SetText(tostring(title or ""), LABEL_COLOR[1], LABEL_COLOR[2], LABEL_COLOR[3])
        if type(body) == "string" and body ~= "" then
            GameTooltip:AddLine(body, 1, 1, 1, true)
        end
        GameTooltip:Show()
    end)
    row:SetScript("OnLeave", function()
        if GameTooltip then GameTooltip:Hide() end
    end)
end

local function EnsureCard(frame)
    if frame.characterSummaryDrawerCard then return frame.characterSummaryDrawerCard end

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
    card.title:SetText("Character Summary")
    card.title:SetTextColor(1.0, 0.82, 0.0)
    card.title:SetJustifyH("LEFT")

    -- Invisible hit/select region for AdvDev around the title text.
    card.titleRegion = CreateFrame("Frame", nil, card)
    card.titleRegion:EnableMouse(false)

    local scrollName = "StatVerdictSummaryScroll"
    local scroll = CreateFrame("ScrollFrame", scrollName, card, "UIPanelScrollFrameTemplate")
    scroll:EnableMouse(true)

    local child = CreateFrame("Frame", nil, scroll)
    child:SetSize(100, 100)
    scroll:SetScrollChild(child)

    card.scroll = scroll
    card.scrollChild = child
    card.blocks = {}

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

    frame.characterSummaryDrawerCard = card
    return card
end

local function EnsureBlock(card, key)
    card.blocks = card.blocks or {}
    local block = card.blocks[key]
    -- Need BackdropTemplate for the AdvDev white outline (old plain frames get replaced once).
    if block and not block.SetBackdrop then
        block:Hide()
        if block.SetParent then block:SetParent(nil) end
        card.blocks[key] = nil
        block = nil
    end
    if block then return block end
    block = CreateFrame("Frame", nil, card.scrollChild, "BackdropTemplate")
    block:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 8,
        insets = { left = 2, right = 2, top = 2, bottom = 2 },
    })
    block:SetBackdropColor(0, 0, 0, 0)
    block:SetBackdropBorderColor(0, 0, 0, 0)
    block.rows = {}
    block.header = block:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    block.header:SetJustifyH("LEFT")
    block.header:SetTextColor(HEADER_COLOR[1], HEADER_COLOR[2], HEADER_COLOR[3])
    block.header:Hide()
    card.blocks[key] = block
    return block
end

local function EnsureBlockRow(block, index)
    local row = block.rows[index]
    if row then return row end
    row = CreateFrame("Frame", nil, block)
    row:SetHeight(ROW_HEIGHT)
    row.label = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.label:SetJustifyH("LEFT")
    row.value = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.value:SetJustifyH("LEFT")
    block.rows[index] = row
    return row
end

local function ApplyStatRow(row, entry, rowWidth)
    row:SetWidth(rowWidth)
    row:SetHeight(ROW_HEIGHT)
    row.label:ClearAllPoints()
    row.value:ClearAllPoints()
    row.label:SetText(entry.label or "")
    row.label:SetTextColor(LABEL_COLOR[1], LABEL_COLOR[2], LABEL_COLOR[3])
    row.label:SetJustifyH("LEFT")
    row.value:SetText(entry.value or "-")
    row.value:SetJustifyH("RIGHT")

    -- Never wrap long labels like "Main Spec Progress" when tightening the value column.
    if row.label.SetWordWrap then row.label:SetWordWrap(false) end
    if row.label.SetNonSpaceWrap then row.label:SetNonSpaceWrap(false) end
    if row.value.SetWordWrap then row.value:SetWordWrap(false) end
    if row.value.SetNonSpaceWrap then row.value:SetNonSpaceWrap(false) end

    -- Value width follows the text (%, numbers), not a large fixed share of the row.
    local valueW = 36
    if row.value.GetStringWidth then
        valueW = math.max(28, (tonumber(row.value:GetStringWidth()) or 36) + 2)
    end
    if valueW > rowWidth * 0.55 then
        valueW = math.max(28, rowWidth * 0.55)
    end

    row.value:SetPoint("RIGHT", row, "RIGHT", 0, 0)
    row.value:SetWidth(valueW)
    row.label:SetPoint("LEFT", row, "LEFT", 0, 0)
    row.label:SetPoint("RIGHT", row.value, "LEFT", -LABEL_VALUE_GAP, 0)

    if entry.kind == "progress" then
        local r, g, b = 1, 1, 1
        if type(entry.valueR) == "table" then
            r, g, b = entry.valueR[1] or 1, entry.valueR[2] or 1, entry.valueR[3] or 1
        end
        row.value:SetTextColor(r, g, b)
        AttachSimpleTooltip(row, entry.tipTitle, entry.tipBody)
        return
    end

    row.value:SetTextColor(VALUE_COLOR[1], VALUE_COLOR[2], VALUE_COLOR[3])
    if entry.isItemLevel and type(GetItemLevelColor) == "function" then
        local r, g, b = GetItemLevelColor()
        if r then row.value:SetTextColor(r, g, b) end
    end

    row.tooltip = entry.tooltip
    row.tooltip2 = entry.tooltip2
    row.tooltip3 = entry.tooltip3
    row.onEnterFunc = entry.onEnterFunc
    row.UpdateTooltip = entry.UpdateTooltip
    row.spellCrit = entry.spellCrit
    row.speed = entry.speed
    row.runSpeed = entry.runSpeed
    row.flightSpeed = entry.flightSpeed
    row.swimSpeed = entry.swimSpeed
    row.unit = entry.unit or "player"
    row.numericValue = entry.numericValue
    AttachBlizzardTooltip(row)
end

local function BlockContentWidth(layoutKey, defaultWidth, maxWidth)
    local width = (tonumber(defaultWidth) or 200) + SizeDelta(layoutKey .. ".width")
    if width < 70 then width = 70 end
    if maxWidth and width > maxWidth then width = maxWidth end
    if width > 420 then width = 420 end
    return width
end

local function MaxVisibleBlockWidth(card)
    local cardW = (card and card.GetWidth and card:GetWidth()) or DRAWER_PREFERRED_WIDTH
    -- Keep AdvDev boxes inside the drawer; never spill past the scroll viewport.
    return math.max(80, cardW - SCROLL_SIDE_PAD * 2 - SCROLLBAR_WIDTH - 4)
end

local function HideWidthHandle(card, layoutKey)
    if not card or not card._svDevWidthHandles then return end
    local handle = card._svDevWidthHandles[layoutKey .. ".width"]
    if handle then handle:Hide() end
end

-- Place a Summary block with the shared AdvDev outer pad (Move / Size / Padding).
-- width/height are the logical footprint; padding insets the visible block.
-- Returns the logical height (footprint) used for stacking the next block.
local function PlaceBlock(card, block, layoutKey, label, baseX, baseY, width, height, baseW)
    -- Outer pad replaces the legacy width nubs.
    HideWidthHandle(card, layoutKey)
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion(layoutKey .. ".width")
    end
    if ns.IsDevLayoutHidden and ns.IsDevLayoutHidden(layoutKey) then
        block:Hide()
        return height
    end
    local ox, oy = Offset(layoutKey)
    local pad = Padding(layoutKey .. ".pad")
    local logicalH = height + HeightDelta(layoutKey .. ".height")
    if logicalH < 10 then logicalH = 10 end
    local visW = math.max(20, width - (pad.left or 0) - (pad.right or 0))
    local visH = math.max(10, logicalH - (pad.top or 0) - (pad.bottom or 0))
    block:ClearAllPoints()
    block:SetPoint(
        "TOPLEFT",
        card.scrollChild,
        "TOPLEFT",
        baseX + ox + (pad.left or 0),
        baseY + oy - (pad.top or 0)
    )
    block:SetSize(visW, visH)
    block:Show()
    if block.SetBackdrop then
        -- No AdvDev white rim on Summary blocks — cyan overlay alone is enough.
        if ns.UnregisterDevLayoutBorderEditOnly then
            ns.UnregisterDevLayoutBorderEditOnly(block, 0, 0, 0, 0)
        end
        block:SetBackdropBorderColor(0, 0, 0, 0)
        block:SetBackdropColor(0, 0, 0, 0)
    end
    if ns.RegisterDevLayoutOuterSpec then
        ns.RegisterDevLayoutOuterSpec(layoutKey, {
            label = label,
            moveKey = layoutKey,
            widthKey = layoutKey .. ".width",
            heightKey = layoutKey .. ".height",
            padKey = layoutKey .. ".pad",
            baseW = baseW or width,
            baseH = height,
            sharedFrameHeight = false,
            lockKey = layoutKey .. ".locked",
        })
    end
    Register(layoutKey, label, block, {
        axis = "xy",
        padding = 0,
        group = "controls",
        protect = true,
        exactHit = true,
        alwaysCapture = true,
    })
    return logicalH
end

local function FillTitleOnlyBlock(block, titleText, width)
    block.header:ClearAllPoints()
    block.header:SetPoint("TOPLEFT", block, "TOPLEFT", 0, 0)
    block.header:SetPoint("RIGHT", block, "RIGHT", 0, 0)
    block.header:SetText(titleText or "")
    if block.header.SetWordWrap then block.header:SetWordWrap(false) end
    if block.header.SetNonSpaceWrap then block.header:SetNonSpaceWrap(false) end
    block.header:Show()
    for _, row in ipairs(block.rows) do
        row:Hide()
    end
    return HEADER_HEIGHT
end

local function FillRowsBlock(block, entries, width)
    block.header:Hide()
    local y = 0
    local count = type(entries) == "table" and #entries or 0
    for index = 1, count do
        local row = EnsureBlockRow(block, index)
        row:ClearAllPoints()
        row:SetPoint("TOPLEFT", block, "TOPLEFT", 0, y)
        ApplyStatRow(row, entries[index], width)
        row:Show()
        y = y - ROW_HEIGHT
    end
    for index = count + 1, #(block.rows) do
        block.rows[index]:Hide()
    end
    return math.max(ROW_HEIGHT, count * ROW_HEIGHT)
end

local function LayoutContent(card, profile, view)
    local proxy = EnsureProxy(card)
    local sections = CollectSummarySections(proxy, profile)
    local progressRows = CollectProgressRows(view)

    local cursorY = -2
    local baseX = 2
    -- Fixed base width: card resize must not compress labels/values.
    local defaultBlockWidth = DEFAULT_BLOCK_WIDTH
    local maxBlockWidth = MaxVisibleBlockWidth(card)
    if defaultBlockWidth > maxBlockWidth then defaultBlockWidth = maxBlockWidth end
    local widest = defaultBlockWidth

    local function placeRows(blockKey, layoutKey, label, entries, gapAfter)
        local block = EnsureBlock(card, blockKey)
        if not entries or #entries == 0 then
            block:Hide()
            HideWidthHandle(card, layoutKey)
            return
        end
        local width = BlockContentWidth(layoutKey, defaultBlockWidth, maxBlockWidth)
        if width > widest then widest = width end
        local pad = Padding(layoutKey .. ".pad")
        local rowW = math.max(20, width - (pad.left or 0) - (pad.right or 0))
        local h = FillRowsBlock(block, entries, rowW)
        local logicalH = PlaceBlock(card, block, layoutKey, label, baseX, cursorY, width, h, defaultBlockWidth)
        cursorY = cursorY - (logicalH or h) - (gapAfter or BLOCK_GAP)
    end

    local function placeTitle(blockKey, layoutKey, label, titleText, gapAfter)
        local block = EnsureBlock(card, blockKey)
        if not titleText or titleText == "" then
            block:Hide()
            HideWidthHandle(card, layoutKey)
            return
        end
        local width = BlockContentWidth(layoutKey, defaultBlockWidth, maxBlockWidth)
        if width > widest then widest = width end
        local pad = Padding(layoutKey .. ".pad")
        local titleW = math.max(20, width - (pad.left or 0) - (pad.right or 0))
        local h = FillTitleOnlyBlock(block, titleText, titleW)
        local logicalH = PlaceBlock(card, block, layoutKey, label, baseX, cursorY, width, h, defaultBlockWidth)
        cursorY = cursorY - (logicalH or h) - (gapAfter or 2)
    end

    -- Item Level row only (no category title).
    if sections.itemLevel then
        placeRows("itemLevel", "summary.itemLevel", "Summary: Item Level", { sections.itemLevel }, BLOCK_GAP)
    else
        EnsureBlock(card, "itemLevel"):Hide()
    end

    placeTitle("attributesTitle", "summary.attributesTitle", "Summary: Attributes title", sections.attributesTitle, 2)
    placeRows("attributes", "summary.attributes", "Summary: Attributes values", sections.attributes, BLOCK_GAP)

    placeTitle("enhancementsTitle", "summary.enhancementsTitle", "Summary: Enhancements title", sections.enhancementsTitle, 2)
    placeRows("enhancements", "summary.enhancements", "Summary: Enhancements values", sections.enhancements, BLOCK_GAP)

    placeTitle("svTitle", "summary.svTitle", "Summary: StatVerdict title", "StatVerdict", 2)
    placeRows("svValues", "summary.svValues", "Summary: StatVerdict values", progressRows, 4)

    local contentHeight = math.max(40, -cursorY + 8)
    card.scrollChild:SetSize(widest + 12, contentHeight)
    return contentHeight
end

local function LayoutHeaderTexts(card)
    -- Unified title chip replaces gold FontString + separate Main/Off Spec toggle.
    if card.title then
        card.title:Hide()
        card.title:SetText("")
    end
    if card.titleRegion then
        card.titleRegion:Hide()
    end
    if ns.PlaceMsOsTitleChip then
        ns.PlaceMsOsTitleChip(card, "summary", "summary")
    elseif ns.PlaceMsOsViewTabs then
        ns.PlaceMsOsViewTabs(card, card, 0, "summary")
    end

    -- Identity line (name/race/class/level) removed — it forced the drawer too wide.
    if card.charName then
        card.charName:Hide()
        card.charName:SetText("")
    end
    if card.charNameRegion then
        card.charNameRegion:Hide()
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("summary.charName")
    end
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "summary"
end

function Panel.ClearDevTargets(frame)
    if frame then
        if frame.characterSummaryDrawerCard then frame.characterSummaryDrawerCard:Hide() end
        if frame.devSummaryDrawerWidthRegion then frame.devSummaryDrawerWidthRegion:Hide() end
        if frame.devSummaryDrawerMoveGrip then frame.devSummaryDrawerMoveGrip:Hide() end
        local card = frame.characterSummaryDrawerCard
        if card and card.blocks then
            for _, block in pairs(card.blocks) do
                if block then block:Hide() end
            end
        end
        if card and card.titleRegion then card.titleRegion:Hide() end
        if card and ns.HideMsOsViewTabs then
            ns.HideMsOsViewTabs(card)
        elseif card then
            if card.svMsTab then card.svMsTab:Hide() end
            if card.svOsTab then card.svOsTab:Hide() end
            if card.svViewToggle then card.svViewToggle:Hide() end
            if card.svViewToggleHint then card.svViewToggleHint:Hide() end
        end
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("summary.card")
    end
    if ns.UnregisterDevLayoutRegionsByPrefix then
        ns.UnregisterDevLayoutRegionsByPrefix("summary.")
    end
end

function Panel.GetPreferredWidth(frame)
    -- Always derive from SizeDelta — never cache preferredWidth here (that blocked shrinking).
    local width = DRAWER_PREFERRED_WIDTH + SizeDelta("summary.width")
    if width < 160 then width = 160 end
    if width > 520 then width = 520 end
    return width
end

local function GetScrollBar(scroll)
    if not scroll then return nil end
    if scroll.ScrollBar then return scroll.ScrollBar end
    local name = scroll.GetName and scroll:GetName() or nil
    if name and _G[name .. "ScrollBar"] then
        return _G[name .. "ScrollBar"]
    end
    return nil
end

local function UpdateSummaryScrollBar(card)
    local scroll = card and card.scroll
    if not scroll then return end
    local scrollBar = GetScrollBar(scroll)
    local range = 0
    if scroll.GetVerticalScrollRange then
        range = tonumber(scroll:GetVerticalScrollRange()) or 0
    end
    local needScroll = range > 1
    if scrollBar then
        if needScroll then
            scrollBar:Show()
        else
            scrollBar:Hide()
            if scroll.SetVerticalScroll then
                scroll:SetVerticalScroll(0)
            end
        end
    end
    return needScroll
end

local function LayoutSummaryScrollFrame(card)
    local _, titleY = Offset("summary.title")
    -- Title chip is ~24px tall at y=-12 → leave a bit more room than the old FontString.
    local scrollTop = -40 + math.min(0, titleY)
    if scrollTop > -32 then scrollTop = -32 end

    -- First pass: reserve scrollbar space so range measurement is accurate.
    card.scroll:ClearAllPoints()
    card.scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, scrollTop)
    card.scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -(SCROLL_SIDE_PAD + SCROLLBAR_WIDTH), SCROLL_BOTTOM_PAD)

    local needScroll = UpdateSummaryScrollBar(card)
    local rightPad = needScroll and (SCROLL_SIDE_PAD + SCROLLBAR_WIDTH) or SCROLL_SIDE_PAD
    card.scroll:ClearAllPoints()
    card.scroll:SetPoint("TOPLEFT", card, "TOPLEFT", SCROLL_SIDE_PAD, scrollTop)
    card.scroll:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -rightPad, SCROLL_BOTTOM_PAD)
    UpdateSummaryScrollBar(card)
end

function Panel.Refresh(frame, profile)
    if not frame or not Panel.IsOpen() then return end
    local card = EnsureCard(frame)
    local view = "MAIN"
    if ns.GetActivePanelContext then
        local context, activeView = ns.GetActivePanelContext()
        view = activeView or "MAIN"
        if not profile then
            profile = context and context.profile or nil
        end
    end
    card.svSummaryProfile = profile
    card.svSummaryView = view

    if ns.StatVerdictBisProgressPanel and ns.StatVerdictBisProgressPanel.UpdateProgressCache then
        ns.StatVerdictBisProgressPanel.UpdateProgressCache(profile)
    end
    LayoutHeaderTexts(card)

    -- Size scroll area first, then fill content, then show/hide scrollbar as needed.
    LayoutSummaryScrollFrame(card)
    LayoutContent(card, profile, view)
    LayoutSummaryScrollFrame(card)
end

function Panel.Apply(frame, profile)
    if not frame then return end
    if not Panel.IsOpen() then
        Panel.ClearDevTargets(frame)
        return
    end

    local card = EnsureCard(frame)
    local cardWidth = Panel.GetPreferredWidth(frame)
    local panelX = 770 + Offset("summary.card")
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelX then
        panelX = ns.StatVerdictDashboardLayout.GetRightPanelX(frame)
    end

    card.preferredWidth = cardWidth
    local extra = 0
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelExtraGap then
        extra = ns.StatVerdictDashboardLayout.GetRightPanelExtraGap()
    end
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad("summary.card")
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
    if ns.ApplyRightDrawerCardDev then
        ns.ApplyRightDrawerCardDev(card, "summary.card", "Character Summary drawer", "summary.width", DRAWER_PREFERRED_WIDTH)
    end

    -- Outer pad owns Size W — retire the legacy width strip and move grip.
    if frame.devSummaryDrawerWidthRegion then
        frame.devSummaryDrawerWidthRegion:Hide()
    end
    if frame.devSummaryDrawerMoveGrip then
        frame.devSummaryDrawerMoveGrip:Hide()
    end
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("summary.width")
    end

    Panel.Refresh(frame, profile)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
