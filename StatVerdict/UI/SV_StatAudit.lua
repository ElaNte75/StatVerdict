local addonName, ns = ...
ns = ns or {}

-- Static audit target data lives in Core/SV_AuditTargets.lua.
local COLOR_TITLE_GOLD = { 1.00, 0.82, 0.00 }      -- classic WoW gold
local COLOR_SOFT_YELLOW = { 0.92, 0.82, 0.45 }     -- softer yellow for table text

local function SafeNumber(value)
    local sanitizer = ns.SanitizeStatVerdictNumber
    if type(sanitizer) == "function" then
        return sanitizer(value)
    end
    local ok, plain = pcall(function()
        local converted = tonumber(value)
        if converted == nil then return nil end
        if converted ~= converted then return nil end
        return converted + 0
    end)
    if ok and type(plain) == "number" then return plain end
    return nil
end

local GetSavedSelection
local SaveSelection
local GetEffectiveGoalMode
local RequestInventoryVerdictRefresh
local GetCustomBucket
local GOAL_LEVELING
local GOAL_OVERALL
local GOAL_MYTHIC_PLUS
local GOAL_RAID
local GOAL_PVP
local DEFAULT_MAX_LEVEL_GOAL

local function FormatNumber(value, decimals)
    value = SafeNumber(value)
    if not value then return "-" end
    if decimals and decimals > 0 then return string.format("%." .. decimals .. "f", value) end
    return string.format("%d", math.floor(value + 0.5))
end

local function FormatDiff(value)
    value = SafeNumber(value)
    if not value then return "-" end
    local rounded = math.floor(math.abs(value) + 0.5)
    if value > 0 then return "+" .. rounded end
    if value < 0 then return "-" .. rounded end
    return "0"
end

local function FormatProgress(current, target)
    current = SafeNumber(current)
    target = SafeNumber(target)
    if not current or not target or target <= 0 then return "-" end
    local ratio = math.max(0, current / target)
    if ratio > 1 then
        local over = (ratio - 1) * 100
        return string.format("+%.1f%%", over)
    end
    return string.format("%.1f%%", ratio * 100)
end

local function SafeStringWidth(fs, text)
    if not fs or type(fs.GetStringWidth) ~= "function" then return 0 end
    local old = fs:GetText() or ""
    fs:SetText(text or "")
    local w = fs:GetStringWidth() or 0
    fs:SetText(old)
    return w
end

local function GetClassColor(context)
    local classFile = context and context.classFile
    local classColor = classFile and RAID_CLASS_COLORS and RAID_CLASS_COLORS[classFile]
    if classColor then
        return classColor.r or 1, classColor.g or 0.49, classColor.b or 0.04
    end
    return 1, 0.49, 0.04
end

local function GetBaseModifier(profile, statKey)
    if ns.GetStatAuditBaseModifier then return ns.GetStatAuditBaseModifier(profile, statKey) end
    return nil
end

local function GetLiveModifier(profile, statKey, baseModifier, softCapOverride, currentValue)
    if ns.GetStatAuditLiveModifier then return ns.GetStatAuditLiveModifier(profile, statKey, baseModifier, softCapOverride, currentValue) end
    return nil
end

local function CopyRows(rows)
    local copy = {}
    if type(rows) ~= "table" then return copy end
    for index, row in ipairs(rows) do
        copy[index] = {
            key = row.key,
            label = row.label,
            type = row.type,
            target = SafeNumber(row.target),
            targetPercent = SafeNumber(row.targetPercent),
            targetRating = SafeNumber(row.targetRating),
            softCap = SafeNumber(row.softCap),
            baseModifier = SafeNumber(row.baseModifier),
            priority = row.priority or index,
            valueMode = row.valueMode,
            unboundedTarget = row.unboundedTarget and true or false,
        }
    end
    table.sort(copy, function(a, b) return (a.priority or 999) < (b.priority or 999) end)
    return copy
end

local function GetItemLevelAuditTarget()
    local model = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.itemLevel or nil
    if ns.StatAuditIsPlayerBelowHeroTalentLevel and ns.StatAuditIsPlayerBelowHeroTalentLevel() then
        return SafeNumber(model and model.preExpansionTargetItemLevel) or SafeNumber(model and model.levelingTargetItemLevel) or 70
    end
    if ns.StatAuditIsPlayerBelowMaxLevel and ns.StatAuditIsPlayerBelowMaxLevel() then
        return SafeNumber(model and model.campaignTargetItemLevel) or 220
    end
    return SafeNumber(model and model.soloTargetItemLevel) or 276
end

local function GetItemLevelAuditTargetTooltip(targetValue)
    local model = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.itemLevel or nil
    if ns.StatAuditIsPlayerBelowHeroTalentLevel and ns.StatAuditIsPlayerBelowHeroTalentLevel() then
        local target = SafeNumber(targetValue) or SafeNumber(model and model.preExpansionTargetItemLevel) or SafeNumber(model and model.levelingTargetItemLevel) or 70
        return "Pre-Midnight leveling milestone", string.format("Target %d is a practical item-level milestone before reaching level 80 and unlocking hero talents.", target)
    end
    if ns.StatAuditIsPlayerBelowMaxLevel and ns.StatAuditIsPlayerBelowMaxLevel() then
        local target = SafeNumber(targetValue) or SafeNumber(model and model.campaignTargetItemLevel) or 220
        return "Campaign leveling milestone", string.format("Target %d is the Midnight Season 1 Heroic Dungeon queue milestone to aim for while finishing the leveling campaign.", target)
    end
    local target = SafeNumber(targetValue) or SafeNumber(model and model.soloTargetItemLevel) or 276
    local goalMode = (GetEffectiveGoalMode and GetEffectiveGoalMode(GetSavedSelection and GetSavedSelection() or nil)) or DEFAULT_MAX_LEVEL_GOAL
    if goalMode == GOAL_MYTHIC_PLUS then
        return "Mythic+ item-level target", string.format("Target %d uses the validated bundled Mythic+ set when available; otherwise it is a configured fallback milestone.", target)
    end
    if goalMode == GOAL_RAID then
        return "Raid item-level target", string.format("Target %d uses the validated bundled Raid set when available; otherwise it is a configured fallback milestone.", target)
    end
    if goalMode == GOAL_PVP then
        return "PvP item-level milestone", string.format("Target %d is a configured milestone; StatVerdict does not currently derive PvP item level from the Murlok reference list.", target)
    end
    return "Item-level target", string.format("Target %d is the current validated target or configured fallback milestone.", target)
end

local function RoundModifier(value)
    value = SafeNumber(value)
    if not value then return nil end
    return math.floor((value * 100) + 0.5) / 100
end

local function NormalizeRowBaseModifierBudget(rows)
    if type(rows) ~= "table" then return rows end
    local budget = SafeNumber(ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.pointBudget) or 10
    local total, roundedTotal = 0, 0
    local largestIndex, largestValue = nil, 0

    for index, row in ipairs(rows) do
        local base = SafeNumber(row and row.baseModifier)
        if base and base > 0 then
            total = total + base
            if base > largestValue then
                largestValue = base
                largestIndex = index
            end
        end
    end

    if total <= 0 then return rows end
    local scale = budget / total

    for _, row in ipairs(rows) do
        local base = SafeNumber(row and row.baseModifier)
        if base and base > 0 then
            row.baseModifier = RoundModifier(base * scale)
            roundedTotal = roundedTotal + (row.baseModifier or 0)
        end
    end

    if largestIndex then
        local diff = RoundModifier(budget - roundedTotal)
        if diff and math.abs(diff) >= 0.01 then
            rows[largestIndex].baseModifier = RoundModifier((rows[largestIndex].baseModifier or 0) + diff)
        end
    end

    return rows
end

local function AssignLiveTiers(rows)
    if type(rows) ~= "table" then return rows end
    local secondaryRank = 0
    for _, row in ipairs(rows) do
        local rowType = string.upper(tostring(row and row.type or ""))
        if rowType == "ITEM" or rowType == "GEAR" or rowType == "PRIMARY" or row.key == "STATVERDICT_ITEM_LEVEL" then
            row.liveTier = 1
        elseif rowType == "SECONDARY" then
            secondaryRank = secondaryRank + 1
            row.secondaryRank = secondaryRank
            row.liveTier = secondaryRank <= 2 and 2 or 3
        elseif rowType == "MINOR" then
            row.liveTier = 4
        else
            row.liveTier = 4
        end
    end
    return rows
end

local function FinalizeAuditRows(rows, target)
    if target and target.noNormalizeBaseModifierBudget then
        return AssignLiveTiers(rows)
    end
    return AssignLiveTiers(NormalizeRowBaseModifierBudget(rows))
end

local function PrepareAuditRows(rows, target)
    rows = CopyRows(rows)
    return FinalizeAuditRows(rows or {}, target)
end

local function ResolveAuditProfileID(context, profile)
    if ns.ResolveStatAuditProfileID then return ns.ResolveStatAuditProfileID(context, profile) end
    return nil
end

-- Static spec/class metadata lives in Core/SV_SpecMeta.lua.

local function GetAuditTarget(context, profile)
    local generated = type(profile) == "table" and profile.auditTargets or nil
    if type(generated) ~= "table" or type(generated.rows) ~= "table" then
        return nil
    end

    return {
        source = generated.source or "generated_profile",
        rows = generated.rows,
        itemLevelTarget = SafeNumber(generated.averageItemLevel),
    }
end

function ns.GetStatVerdictItemLevelTarget(profile, context)
    context = context or {}
    if type(profile) == "table" then
        context.profile = context.profile or profile
        context.specID = context.specID or profile.specID
    end
    local target = GetAuditTarget(context, profile)
    return SafeNumber(target and target.itemLevelTarget) or GetItemLevelAuditTarget()
end

function ns.GetStatVerdictItemLevelWeightScale(profile)
    local target = ns.GetStatVerdictItemLevelTarget and ns.GetStatVerdictItemLevelTarget(profile) or nil
    local current = ns.GetCurrentAuditStatValue and ns.GetCurrentAuditStatValue("STATVERDICT_ITEM_LEVEL") or nil
    if not current or not target or target <= 0 then return 1 end

    local progress = current / target
    local isLeveling = ns.StatAuditIsPlayerBelowMaxLevel and ns.StatAuditIsPlayerBelowMaxLevel()
    if isLeveling then
        if progress < 0.50 then return 1.60 end
        if progress < 0.75 then return 1.35 end
        if progress < 0.90 then return 1.15 end
        if progress >= 1.00 then return 0.70 end
        return 1.00
    end

    if progress < 0.90 then return 1.20 end
    if progress < 0.97 then return 1.08 end
    if progress < 1.00 then return 1.06 end
    if progress < 1.05 then return 0.70 end
    return 0.45
end

function ns.GetStatAuditTargetPointTotal(context, profile)
    local target = GetAuditTarget(context, profile)
    local rows = PrepareAuditRows(target and target.rows, target)
    local profileID = ResolveAuditProfileID(context, profile)
    local customBucket = GetCustomBucket(profileID)
    local total = 0
    for _, row in ipairs(rows or {}) do
        local targetValue = SafeNumber(row.target)
        if customBucket and customBucket.targets and customBucket.targets[row.key] then
            targetValue = SafeNumber(customBucket.targets[row.key]) or targetValue
        end
        if row.unboundedTarget then targetValue = nil end
        local baseModifier = SafeNumber(row.baseModifier)
        if baseModifier == nil then
            baseModifier = GetBaseModifier(profile, row.key)
        end
        if customBucket and customBucket.baseModifiers then
            local customBase = SafeNumber(customBucket.baseModifiers[row.key])
            if customBase then baseModifier = customBase end
        end
        if targetValue and targetValue > 0 and baseModifier and baseModifier > 0 then
            total = total + (targetValue * baseModifier)
        end
    end
    if total > 0 then return total end
    return nil
end

local function CreateSeparator(parent, x)
    local texture = parent:CreateTexture(nil, "ARTWORK")
    texture:SetColorTexture(0.9, 0.78, 0.28, 0.35)
    texture:SetPoint("TOPLEFT", parent, "TOPLEFT", x, -78)
    texture:SetPoint("BOTTOMLEFT", parent, "BOTTOMLEFT", x, 22)
    texture:SetWidth(1)
    return texture
end

local function CreateText(parent, x, y, width, justify, fontObject)
    local text = parent:CreateFontString(nil, "OVERLAY", fontObject or "GameFontNormalSmall")
    text:SetPoint("TOPLEFT", parent, "TOPLEFT", x, y)
    text:SetWidth(width)
    text:SetJustifyH(justify or "LEFT")
    text:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
    return text
end

local AuditFrame
local LastLiveModifiersByKey = {}
local AuditInteractionBlocker
local DebugInteractionBlocker
local ShowAuditInteractionBlocker
local HideAuditInteractionBlocker
local function GetLiveCacheKey(profileID, statKey)
    return tostring(profileID or "UNKNOWN") .. "::" .. tostring(statKey or "UNKNOWN")
end

function ns.GetCachedStatAuditLiveModifier(profileID, statKey)
    local value = LastLiveModifiersByKey[GetLiveCacheKey(profileID, statKey)]
    value = SafeNumber(value)
    if value then return value end
    return nil
end

-- Warm the live-Weight cache for a profile (Stat Progress Weight column).
-- Generated-profile upgrade scoring uses target-driven anchors instead; this cache
-- remains available for UI and non-generated profile paths.
function ns.EnsureCachedStatAuditLiveModifiers(profile)
    if type(profile) ~= "table" then return false end
    local profileID = ResolveAuditProfileID(nil, profile)
    if not profileID then return false end

    local target = GetAuditTarget(nil, profile)
    local rows = PrepareAuditRows(target and target.rows, target)
    if type(rows) ~= "table" or #rows == 0 then return false end
    if not ns.NormalizeStatAuditLiveWeights then return false end

    local customBucket = GetCustomBucket and GetCustomBucket(profileID) or nil

    local function getCurrentValue(statKey)
        if ns.GetSnapshotStatValue then
            local snap = ns.GetSnapshotStatValue(profile, statKey)
            if snap ~= nil then return snap end
        end
        return ns.GetCurrentAuditStatValue and ns.GetCurrentAuditStatValue(statKey) or nil
    end

    local function getRatingValue(statKey)
        if ns.GetSnapshotStatValue then
            local snap = ns.GetSnapshotStatValue(profile, statKey)
            if snap ~= nil then return snap end
        end
        return ns.GetCurrentAuditRatingValue and ns.GetCurrentAuditRatingValue(statKey) or nil
    end

    local normalized = ns.NormalizeStatAuditLiveWeights({
        rows = rows,
        maxDataRows = #rows,
        profile = profile,
        target = target,
        customBucket = customBucket,
        getCurrentValue = getCurrentValue,
        getRatingValue = getRatingValue,
        isSecondaryKey = ns.IsAuditSecondaryStatKey,
    }) or {}

    local wrote = false
    for statKey, liveModifier in pairs(normalized) do
        local value = SafeNumber(liveModifier)
        if value then
            LastLiveModifiersByKey[GetLiveCacheKey(profileID, statKey)] = value
            wrote = true
        end
    end
    return wrote
end

local function EnsureAuditInteractionBlocker()
    if AuditInteractionBlocker then return AuditInteractionBlocker end
    local blocker = CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictAuditInteractionBlocker") or "StatVerdictAuditInteractionBlocker", UIParent, "BackdropTemplate")
    blocker:Hide()
    blocker:SetFrameStrata("FULLSCREEN_DIALOG")
    blocker:SetFrameLevel(2000)
    blocker:EnableMouse(true)
    blocker:RegisterForDrag("LeftButton")
    blocker:SetScript("OnDragStart", function() end)
    blocker:SetScript("OnMouseDown", function() end)
    blocker:SetScript("OnMouseUp", function() end)
    blocker:SetScript("OnHide", function(self) self:ClearAllPoints() end)
    AuditInteractionBlocker = blocker
    return blocker
end

local function EnsureDebugInteractionBlocker()
    if DebugInteractionBlocker then return DebugInteractionBlocker end
    local blocker = CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictDebugInteractionBlocker") or "StatVerdictDebugInteractionBlocker", UIParent, "BackdropTemplate")
    blocker:Hide()
    blocker:SetFrameStrata("FULLSCREEN_DIALOG")
    blocker:SetFrameLevel(2000)
    blocker:EnableMouse(true)
    blocker:RegisterForDrag("LeftButton")
    blocker:SetScript("OnDragStart", function() end)
    blocker:SetScript("OnMouseDown", function() end)
    blocker:SetScript("OnMouseUp", function() end)
    blocker:SetScript("OnHide", function(self) self:ClearAllPoints() end)
    DebugInteractionBlocker = blocker
    return blocker
end

ShowAuditInteractionBlocker = function()
    if not AuditFrame or not AuditFrame:IsShown() then return end
    local blocker = EnsureAuditInteractionBlocker()
    blocker:ClearAllPoints()
    blocker:SetParent(AuditFrame)
    blocker:SetAllPoints(AuditFrame)
    blocker:Show()
    if ns.DebugOverrideFrame and ns.DebugOverrideFrame.IsShown and ns.DebugOverrideFrame:IsShown() then
        local dblock = EnsureDebugInteractionBlocker()
        dblock:ClearAllPoints()
        dblock:SetParent(ns.DebugOverrideFrame)
        dblock:SetAllPoints(ns.DebugOverrideFrame)
        dblock:Show()
    end
end

HideAuditInteractionBlocker = function()
    if AuditInteractionBlocker and AuditInteractionBlocker:IsShown() then
        AuditInteractionBlocker:Hide()
        AuditInteractionBlocker:SetParent(UIParent)
    end
    if DebugInteractionBlocker and DebugInteractionBlocker:IsShown() then
        DebugInteractionBlocker:Hide()
        DebugInteractionBlocker:SetParent(UIParent)
    end
end

local UpdateFrame
local LayoutControllerFrame
local PrimaryAspectDropdown
local SecondaryAspectDropdown
local OffGoalDropdown
local VisibilityDropdown
local SecondaryEnabledCheckbox
local BisEnabledCheckbox
local TrinketEnabledCheckbox
local MainViewCheckbox
local OffViewCheckbox
local EditButton
local DefaultButton
local GoalDropdown
-- Static hero option metadata lives in Core/SV_SpecMeta.lua.
local HEADER_TOOLTIP_TEXT = {
    current = "Current ratings from equipped gear for the active spec, or captured snapshot stats for an Off Spec.",
    target = "Validated bundled profile targets for the selected goal. Unavailable data is not silently replaced by another goal.",
    diff = "Difference = Current - Target.",
    progress = "Progress toward target. Above 100% means over target.",
    softCap = "Soft cap threshold. Above this value, value gain is reduced.",
    baseModifier = "Base stat weight before dynamic adjustments.",
    liveModifier = "Dynamic stat weight after target and soft-cap logic."
}
local LastDropdownClassFile
local LastDropdownSpecID
local LastDropdownSelectionSignature
local LAYOUT_CONST = {
    MAX_VISIBLE_ROWS = 12,
    ROW_HEIGHT = 20,
    GRID_TOP_Y = -94,
    GRID_LEFT_X = 14,
    GRID_WIDTH = 710,
    SEPARATOR_TOP_Y = -78,
    HEADER_Y_OFFSET = 16,
    ROW_START_OFFSET = -6,
    GRID_CARD_INSET_X = 10,
    GRID_CARD_INSET_TOP = 12,
    GRID_CARD_INSET_BOTTOM = 16,
    GRID_CARD_EXTRA_BOTTOM_DEFAULT = 14,
    GRID_MIN_WIDTH = 640,
    GRID_MAX_WIDTH = 710,
    GRID_MIN_X = 8,
    GRID_MAX_X = 40,
    GRID_MIN_Y = -130,
    GRID_MAX_Y = -80,
    GRID_EXTRA_HEIGHT_MIN = 0,
    GRID_EXTRA_HEIGHT_MAX = 140,
    FRAME_WIDTH_DEFAULT = 760,
    FRAME_WIDTH_MIN = 700,
    FRAME_WIDTH_MAX = 1200,
    FRAME_EXTRA_HEIGHT_DEFAULT = 0,
    FRAME_EXTRA_HEIGHT_MIN = -40,
    FRAME_EXTRA_HEIGHT_MAX = 260,
    TITLE_X_DEFAULT = 18,
    TITLE_Y_DEFAULT = -36,
    TITLE_X_MIN = 8,
    TITLE_X_MAX = 120,
    TITLE_Y_MIN = -90,
    TITLE_Y_MAX = -18,
    TITLE_WIDTH_DEFAULT = 710,
    TITLE_WIDTH_MIN = 360,
    TITLE_WIDTH_MAX = 1080,
    TITLE_FONT_SIZE_DEFAULT = 15,
    TITLE_FONT_SIZE_MIN = 11,
    TITLE_FONT_SIZE_MAX = 24,
    ASPECT_LABEL_FONT_SIZE_DEFAULT = 12,
    ASPECT_LABEL_FONT_SIZE_MIN = 10,
    ASPECT_LABEL_FONT_SIZE_MAX = 20,
    DROPDOWN_WIDTH_DEFAULT = 118,
    DROPDOWN_WIDTH_MIN = 80,
    DROPDOWN_WIDTH_MAX = 220,
    DROPDOWN_SCALE_DEFAULT = 1.00,
    DROPDOWN_SCALE_MIN = 0.80,
    DROPDOWN_SCALE_MAX = 1.40,
    GOAL_LABEL_X_DEFAULT = -394,
    GOAL_LABEL_Y_DEFAULT = -38,
    GOAL_DROPDOWN_X_DEFAULT = -342,
    GOAL_DROPDOWN_Y_DEFAULT = -42,
    PRIMARY_LABEL_X_DEFAULT = -250,
    PRIMARY_LABEL_Y_DEFAULT = -38,
    PRIMARY_DROPDOWN_X_DEFAULT = -184,
    PRIMARY_DROPDOWN_Y_DEFAULT = -42,
    SECONDARY_LABEL_X_DEFAULT = -106,
    SECONDARY_LABEL_Y_DEFAULT = -38,
    SECONDARY_DROPDOWN_X_DEFAULT = -42,
    SECONDARY_DROPDOWN_Y_DEFAULT = -42,
    SECONDARY_TITLE_X_DEFAULT = 18,
    SECONDARY_TITLE_Y_DEFAULT = -58,
    OFFSPEC_TOGGLE_X_DEFAULT = 18,
    OFFSPEC_TOGGLE_Y_DEFAULT = -56,
    AUTO_HERO_TOGGLE_X_DEFAULT = 170,
    AUTO_HERO_TOGGLE_Y_DEFAULT = -56,
    OFFSPEC_TOGGLE_FONT_SIZE_DEFAULT = 12,
    OFFSPEC_TOGGLE_FONT_SIZE_MIN = 10,
    OFFSPEC_TOGGLE_FONT_SIZE_MAX = 20,
    BORDER_ALPHA_DEFAULT = 0.95,
    BORDER_ALPHA_MIN = 0.10,
    BORDER_ALPHA_MAX = 1.00,
    AVG_PROGRESS_X_DEFAULT = 22,
    AVG_PROGRESS_Y_DEFAULT = 34,
    SAMPLE_LINE_X_DEFAULT = 360,
    SAMPLE_LINE_Y_DEFAULT = 34,
    SAMPLE_LINE_FONT_SIZE_DEFAULT = 11,
    BUTTON_EDIT_X_DEFAULT = -182,
    BUTTON_EDIT_Y_DEFAULT = 18,
    BUTTON_DEFAULT_X_DEFAULT = -94,
    BUTTON_DEFAULT_Y_DEFAULT = 18,
    BUTTON_WIDTH_DEFAULT = 80,
    BUTTON_HEIGHT_DEFAULT = 22,
}

local LAYOUT_FIELD_RULES = {
    { key = "x", default = LAYOUT_CONST.GRID_LEFT_X, min = LAYOUT_CONST.GRID_MIN_X, max = LAYOUT_CONST.GRID_MAX_X, clamp = true },
    { key = "y", default = LAYOUT_CONST.GRID_TOP_Y, min = LAYOUT_CONST.GRID_MIN_Y, max = LAYOUT_CONST.GRID_MAX_Y, clamp = true },
    { key = "width", default = LAYOUT_CONST.GRID_WIDTH, min = LAYOUT_CONST.GRID_MIN_WIDTH, max = LAYOUT_CONST.GRID_MAX_WIDTH, clamp = true },
    { key = "extraHeight", default = LAYOUT_CONST.GRID_CARD_EXTRA_BOTTOM_DEFAULT, min = LAYOUT_CONST.GRID_EXTRA_HEIGHT_MIN, max = LAYOUT_CONST.GRID_EXTRA_HEIGHT_MAX, clamp = true },
    { key = "frameWidth", default = LAYOUT_CONST.FRAME_WIDTH_DEFAULT, min = LAYOUT_CONST.FRAME_WIDTH_MIN, max = LAYOUT_CONST.FRAME_WIDTH_MAX, clamp = true },
    { key = "frameExtraHeight", default = LAYOUT_CONST.FRAME_EXTRA_HEIGHT_DEFAULT, min = LAYOUT_CONST.FRAME_EXTRA_HEIGHT_MIN, max = LAYOUT_CONST.FRAME_EXTRA_HEIGHT_MAX, clamp = true },
    { key = "titleX", default = LAYOUT_CONST.TITLE_X_DEFAULT, min = LAYOUT_CONST.TITLE_X_MIN, max = LAYOUT_CONST.TITLE_X_MAX, clamp = true },
    { key = "titleY", default = LAYOUT_CONST.TITLE_Y_DEFAULT, min = LAYOUT_CONST.TITLE_Y_MIN, max = LAYOUT_CONST.TITLE_Y_MAX, clamp = true },
    { key = "titleWidth", default = LAYOUT_CONST.TITLE_WIDTH_DEFAULT, min = LAYOUT_CONST.TITLE_WIDTH_MIN, max = LAYOUT_CONST.TITLE_WIDTH_MAX, clamp = true },
    { key = "titleFontSize", default = LAYOUT_CONST.TITLE_FONT_SIZE_DEFAULT, min = LAYOUT_CONST.TITLE_FONT_SIZE_MIN, max = LAYOUT_CONST.TITLE_FONT_SIZE_MAX, clamp = true },
    { key = "aspectLabelFontSize", default = LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_DEFAULT, min = LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_MIN, max = LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_MAX, clamp = true },
    { key = "dropdownWidth", default = LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT, min = LAYOUT_CONST.DROPDOWN_WIDTH_MIN, max = LAYOUT_CONST.DROPDOWN_WIDTH_MAX, clamp = true },
    { key = "dropdownScale", default = LAYOUT_CONST.DROPDOWN_SCALE_DEFAULT, min = LAYOUT_CONST.DROPDOWN_SCALE_MIN, max = LAYOUT_CONST.DROPDOWN_SCALE_MAX, clamp = true },
    { key = "goalLabelX", default = LAYOUT_CONST.GOAL_LABEL_X_DEFAULT, clamp = false },
    { key = "goalLabelY", default = LAYOUT_CONST.GOAL_LABEL_Y_DEFAULT, clamp = false },
    { key = "goalDropdownX", default = LAYOUT_CONST.GOAL_DROPDOWN_X_DEFAULT, clamp = false },
    { key = "goalDropdownY", default = LAYOUT_CONST.GOAL_DROPDOWN_Y_DEFAULT, clamp = false },
    { key = "primaryLabelX", default = LAYOUT_CONST.PRIMARY_LABEL_X_DEFAULT, clamp = false },
    { key = "primaryLabelY", default = LAYOUT_CONST.PRIMARY_LABEL_Y_DEFAULT, clamp = false },
    { key = "primaryDropdownX", default = LAYOUT_CONST.PRIMARY_DROPDOWN_X_DEFAULT, clamp = false },
    { key = "primaryDropdownY", default = LAYOUT_CONST.PRIMARY_DROPDOWN_Y_DEFAULT, clamp = false },
    { key = "secondaryLabelX", default = LAYOUT_CONST.SECONDARY_LABEL_X_DEFAULT, clamp = false },
    { key = "secondaryLabelY", default = LAYOUT_CONST.SECONDARY_LABEL_Y_DEFAULT, clamp = false },
    { key = "secondaryDropdownX", default = LAYOUT_CONST.SECONDARY_DROPDOWN_X_DEFAULT, clamp = false },
    { key = "secondaryDropdownY", default = LAYOUT_CONST.SECONDARY_DROPDOWN_Y_DEFAULT, clamp = false },
    { key = "secondaryTitleX", default = LAYOUT_CONST.SECONDARY_TITLE_X_DEFAULT, clamp = false },
    { key = "secondaryTitleY", default = LAYOUT_CONST.SECONDARY_TITLE_Y_DEFAULT, clamp = false },
    { key = "offspecToggleX", default = LAYOUT_CONST.OFFSPEC_TOGGLE_X_DEFAULT, clamp = false },
    { key = "offspecToggleY", default = LAYOUT_CONST.OFFSPEC_TOGGLE_Y_DEFAULT, clamp = false },
    { key = "autoHeroToggleX", default = LAYOUT_CONST.AUTO_HERO_TOGGLE_X_DEFAULT, clamp = false },
    { key = "autoHeroToggleY", default = LAYOUT_CONST.AUTO_HERO_TOGGLE_Y_DEFAULT, clamp = false },
    { key = "offspecToggleFontSize", default = LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_DEFAULT, min = LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_MIN, max = LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_MAX, clamp = true },
    { key = "borderAlpha", default = LAYOUT_CONST.BORDER_ALPHA_DEFAULT, min = LAYOUT_CONST.BORDER_ALPHA_MIN, max = LAYOUT_CONST.BORDER_ALPHA_MAX, clamp = true },
    { key = "avgProgressX", default = LAYOUT_CONST.AVG_PROGRESS_X_DEFAULT, clamp = false },
    { key = "avgProgressY", default = LAYOUT_CONST.AVG_PROGRESS_Y_DEFAULT, clamp = false },
    { key = "avgProgressFontSize", default = 12, min = 8, max = 24, clamp = true },
    { key = "sampleLineX", default = 360, clamp = false },
    { key = "sampleLineY", default = 34, clamp = false },
    { key = "sampleLineFontSize", default = 11, min = 8, max = 24, clamp = true },
    { key = "editBtnX", default = LAYOUT_CONST.BUTTON_EDIT_X_DEFAULT, clamp = false },
    { key = "editBtnY", default = LAYOUT_CONST.BUTTON_EDIT_Y_DEFAULT, clamp = false },
    { key = "defaultBtnX", default = LAYOUT_CONST.BUTTON_DEFAULT_X_DEFAULT, clamp = false },
    { key = "defaultBtnY", default = LAYOUT_CONST.BUTTON_DEFAULT_Y_DEFAULT, clamp = false },
    { key = "buttonWidth", default = LAYOUT_CONST.BUTTON_WIDTH_DEFAULT, min = 56, max = 140, clamp = true },
    { key = "buttonHeight", default = LAYOUT_CONST.BUTTON_HEIGHT_DEFAULT, min = 18, max = 34, clamp = true },
}

local LAYOUT_CONTROL_DEFS = {
    { section = "Frame / Card", x = 10, y = -36 },
    { key = "frameWidth", label = "Frame Width", min = LAYOUT_CONST.FRAME_WIDTH_MIN, max = LAYOUT_CONST.FRAME_WIDTH_MAX, step = 4, x = 10, y = -58, default = LAYOUT_CONST.FRAME_WIDTH_DEFAULT },
    { key = "frameExtraHeight", label = "Frame Height", min = LAYOUT_CONST.FRAME_EXTRA_HEIGHT_MIN, max = LAYOUT_CONST.FRAME_EXTRA_HEIGHT_MAX, step = 2, x = 10, y = -82, default = LAYOUT_CONST.FRAME_EXTRA_HEIGHT_DEFAULT },
    { key = "x", label = "Card X", min = LAYOUT_CONST.GRID_MIN_X, max = LAYOUT_CONST.GRID_MAX_X, step = 1, x = 10, y = -106, default = LAYOUT_CONST.GRID_LEFT_X },
    { key = "y", label = "Card Y", min = LAYOUT_CONST.GRID_MIN_Y, max = LAYOUT_CONST.GRID_MAX_Y, step = 1, x = 10, y = -130, default = LAYOUT_CONST.GRID_TOP_Y },
    { key = "width", label = "Card Width", min = LAYOUT_CONST.GRID_MIN_WIDTH, max = LAYOUT_CONST.GRID_MAX_WIDTH, step = 2, x = 10, y = -154, default = LAYOUT_CONST.GRID_WIDTH },
    { key = "extraHeight", label = "Card Extra H", min = LAYOUT_CONST.GRID_EXTRA_HEIGHT_MIN, max = LAYOUT_CONST.GRID_EXTRA_HEIGHT_MAX, step = 1, x = 10, y = -178, default = LAYOUT_CONST.GRID_CARD_EXTRA_BOTTOM_DEFAULT },
    { key = "borderAlpha", label = "Border Alpha", min = LAYOUT_CONST.BORDER_ALPHA_MIN, max = LAYOUT_CONST.BORDER_ALPHA_MAX, step = 0.05, x = 10, y = -202, default = LAYOUT_CONST.BORDER_ALPHA_DEFAULT, decimals = 2 },

    { section = "Titles / Labels", x = 10, y = -236 },
    { key = "titleX", label = "Title X", min = LAYOUT_CONST.TITLE_X_MIN, max = LAYOUT_CONST.TITLE_X_MAX, step = 1, x = 10, y = -258, default = LAYOUT_CONST.TITLE_X_DEFAULT },
    { key = "titleY", label = "Title Y", min = LAYOUT_CONST.TITLE_Y_MIN, max = LAYOUT_CONST.TITLE_Y_MAX, step = 1, x = 10, y = -282, default = LAYOUT_CONST.TITLE_Y_DEFAULT },
    { key = "titleFontSize", label = "Title Font", min = LAYOUT_CONST.TITLE_FONT_SIZE_MIN, max = LAYOUT_CONST.TITLE_FONT_SIZE_MAX, step = 1, x = 10, y = -306, default = LAYOUT_CONST.TITLE_FONT_SIZE_DEFAULT },
    { key = "secondaryTitleX", label = "OffSpec X", min = LAYOUT_CONST.TITLE_X_MIN, max = LAYOUT_CONST.TITLE_X_MAX, step = 1, x = 10, y = -330, default = LAYOUT_CONST.SECONDARY_TITLE_X_DEFAULT },
    { key = "secondaryTitleY", label = "OffSpec Y", min = LAYOUT_CONST.TITLE_Y_MIN - 50, max = LAYOUT_CONST.TITLE_Y_MAX, step = 1, x = 10, y = -354, default = LAYOUT_CONST.SECONDARY_TITLE_Y_DEFAULT },
    { key = "aspectLabelFontSize", label = "Label Font", min = LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_MIN, max = LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_MAX, step = 1, x = 10, y = -378, default = LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_DEFAULT },

    { section = "Goal / Spec Dropdowns", x = 300, y = -36 },
    { key = "dropdownWidth", label = "Dropdown W", min = LAYOUT_CONST.DROPDOWN_WIDTH_MIN, max = LAYOUT_CONST.DROPDOWN_WIDTH_MAX, step = 2, x = 300, y = -58, default = LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT },
    { key = "dropdownScale", label = "Dropdown H", min = LAYOUT_CONST.DROPDOWN_SCALE_MIN, max = LAYOUT_CONST.DROPDOWN_SCALE_MAX, step = 0.05, x = 300, y = -82, default = LAYOUT_CONST.DROPDOWN_SCALE_DEFAULT, decimals = 2 },

    { section = "Goal Position", x = 300, y = -116 },
    { key = "goalLabelX", label = "GoalLbl X", min = -520, max = -20, step = 1, x = 300, y = -138, default = LAYOUT_CONST.GOAL_LABEL_X_DEFAULT },
    { key = "goalLabelY", label = "GoalLbl Y", min = -120, max = -8, step = 1, x = 300, y = -162, default = LAYOUT_CONST.GOAL_LABEL_Y_DEFAULT },
    { key = "goalDropdownX", label = "GoalBox X", min = -520, max = -10, step = 1, x = 300, y = -186, default = LAYOUT_CONST.GOAL_DROPDOWN_X_DEFAULT },
    { key = "goalDropdownY", label = "GoalBox Y", min = -130, max = -10, step = 1, x = 300, y = -210, default = LAYOUT_CONST.GOAL_DROPDOWN_Y_DEFAULT },

    { section = "Main Spec Position", x = 300, y = -244 },
    { key = "primaryLabelX", label = "MainLbl X", min = -520, max = -20, step = 1, x = 300, y = -266, default = LAYOUT_CONST.PRIMARY_LABEL_X_DEFAULT },
    { key = "primaryLabelY", label = "MainLbl Y", min = -120, max = -8, step = 1, x = 300, y = -290, default = LAYOUT_CONST.PRIMARY_LABEL_Y_DEFAULT },
    { key = "primaryDropdownX", label = "MainBox X", min = -520, max = -10, step = 1, x = 300, y = -314, default = LAYOUT_CONST.PRIMARY_DROPDOWN_X_DEFAULT },
    { key = "primaryDropdownY", label = "MainBox Y", min = -130, max = -10, step = 1, x = 300, y = -338, default = LAYOUT_CONST.PRIMARY_DROPDOWN_Y_DEFAULT },

    { section = "Off Spec Position", x = 300, y = -372 },
    { key = "secondaryLabelX", label = "OffLbl X", min = -260, max = 0, step = 1, x = 300, y = -394, default = LAYOUT_CONST.SECONDARY_LABEL_X_DEFAULT },
    { key = "secondaryLabelY", label = "OffLbl Y", min = -120, max = -8, step = 1, x = 300, y = -418, default = LAYOUT_CONST.SECONDARY_LABEL_Y_DEFAULT },
    { key = "secondaryDropdownX", label = "OffBox X", min = -260, max = 20, step = 1, x = 300, y = -442, default = LAYOUT_CONST.SECONDARY_DROPDOWN_X_DEFAULT },
    { key = "secondaryDropdownY", label = "OffBox Y", min = -130, max = -10, step = 1, x = 300, y = -466, default = LAYOUT_CONST.SECONDARY_DROPDOWN_Y_DEFAULT },

    { section = "Checkboxes", x = 300, y = -500 },
    { key = "offspecToggleX", label = "OffTgl X", min = -420, max = 20, step = 1, x = 300, y = -522, default = LAYOUT_CONST.OFFSPEC_TOGGLE_X_DEFAULT },
    { key = "offspecToggleY", label = "OffTgl Y", min = -130, max = -10, step = 1, x = 300, y = -546, default = LAYOUT_CONST.OFFSPEC_TOGGLE_Y_DEFAULT },
    { key = "autoHeroToggleX", label = "AutoHero X", min = -420, max = 220, step = 1, x = 300, y = -570, default = LAYOUT_CONST.AUTO_HERO_TOGGLE_X_DEFAULT },
    { key = "autoHeroToggleY", label = "AutoHero Y", min = -130, max = -10, step = 1, x = 300, y = -594, default = LAYOUT_CONST.AUTO_HERO_TOGGLE_Y_DEFAULT },
    { key = "offspecToggleFontSize", label = "Toggles Font", min = LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_MIN, max = LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_MAX, step = 1, x = 300, y = -618, default = LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_DEFAULT },

    { section = "Footer / Buttons", x = 300, y = -652 },
    { key = "avgProgressX", label = "Avg X", min = 0, max = 560, step = 1, x = 300, y = -674, default = LAYOUT_CONST.AVG_PROGRESS_X_DEFAULT },
    { key = "avgProgressY", label = "Avg Y", min = 8, max = 90, step = 1, x = 300, y = -698, default = LAYOUT_CONST.AVG_PROGRESS_Y_DEFAULT },
    { key = "avgProgressFontSize", label = "Avg Font", min = 8, max = 24, step = 1, x = 300, y = -722, default = 12 },
    { key = "sampleLineX", label = "Sample X", min = 0, max = 650, step = 1, x = 300, y = -746, default = LAYOUT_CONST.SAMPLE_LINE_X_DEFAULT },
    { key = "sampleLineY", label = "Sample Y", min = 8, max = 90, step = 1, x = 300, y = -770, default = LAYOUT_CONST.SAMPLE_LINE_Y_DEFAULT },
    { key = "sampleLineFontSize", label = "Sample Font", min = 8, max = 24, step = 1, x = 300, y = -794, default = LAYOUT_CONST.SAMPLE_LINE_FONT_SIZE_DEFAULT },
    { key = "editBtnX", label = "Edit X", min = -340, max = -40, step = 1, x = 300, y = -818, default = LAYOUT_CONST.BUTTON_EDIT_X_DEFAULT },
    { key = "editBtnY", label = "Edit Y", min = 4, max = 60, step = 1, x = 300, y = -842, default = LAYOUT_CONST.BUTTON_EDIT_Y_DEFAULT },
    { key = "defaultBtnX", label = "Default X", min = -260, max = -10, step = 1, x = 300, y = -866, default = LAYOUT_CONST.BUTTON_DEFAULT_X_DEFAULT },
    { key = "defaultBtnY", label = "Default Y", min = 4, max = 60, step = 1, x = 300, y = -890, default = LAYOUT_CONST.BUTTON_DEFAULT_Y_DEFAULT },
    { key = "buttonWidth", label = "Btn Width", min = 56, max = 140, step = 2, x = 300, y = -914, default = LAYOUT_CONST.BUTTON_WIDTH_DEFAULT },
    { key = "buttonHeight", label = "Btn Height", min = 18, max = 34, step = 1, x = 300, y = -938, default = LAYOUT_CONST.BUTTON_HEIGHT_DEFAULT },
}

local Clamp

local function NormalizeLayoutFields(source, target)
    source = source or {}
    target = target or {}
    for _, rule in ipairs(LAYOUT_FIELD_RULES) do
        local value = tonumber(source[rule.key])
        if value == nil then
            value = tonumber(target[rule.key])
        end
        if value == nil then
            value = rule.default
        end
        if rule.clamp then
            value = Clamp(value, rule.min, rule.max)
        end
        target[rule.key] = value
    end
    return target
end

Clamp = function(value, minValue, maxValue)
    if value < minValue then return minValue end
    if value > maxValue then return maxValue end
    return value
end

local GetCharacterKey

local function EnsureSavedDB()
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    _G.StatVerdictDB.statAuditLayout = _G.StatVerdictDB.statAuditLayout or {}
    _G.StatVerdictDB.statAuditSelection = _G.StatVerdictDB.statAuditSelection or {}
    _G.StatVerdictDB.statAuditCustom = _G.StatVerdictDB.statAuditCustom or {}
    _G.StatVerdictDB.statAuditLayoutByCharacter = _G.StatVerdictDB.statAuditLayoutByCharacter or {}
    _G.StatVerdictDB.statAuditSelectionByCharacter = _G.StatVerdictDB.statAuditSelectionByCharacter or {}
    _G.StatVerdictDB.statAuditCustomByCharacter = _G.StatVerdictDB.statAuditCustomByCharacter or {}
    _G.StatVerdictDB.statAuditWindowPosByCharacter = _G.StatVerdictDB.statAuditWindowPosByCharacter or {}
    _G.StatVerdictDB.statAuditDebugOverride = _G.StatVerdictDB.statAuditDebugOverride or {}
    return _G.StatVerdictDB
end

local function SaveWindowPosition(frame)
    if not frame then return end
    local db = EnsureSavedDB()
    local key = GetCharacterKey()
    local left, top = frame:GetLeft(), frame:GetTop()
    if not left or not top then return end
    db.statAuditWindowPosByCharacter[key] = { mode = "TOPLEFT", x = left, y = top }
    local dashboardMoveX = 0
    if ns.GetDevLayoutOffset then
        dashboardMoveX = select(1, ns.GetDevLayoutOffset("dashboard.move")) or 0
    end
    frame.devTopLeftBase = { x = left - dashboardMoveX, y = top }
    frame.svUserWindowPos = { x = left, y = top }
end

local function LoadWindowPosition()
    local db = EnsureSavedDB()
    local key = GetCharacterKey()
    return db.statAuditWindowPosByCharacter and db.statAuditWindowPosByCharacter[key] or nil
end

local function SyncDevTopLeftBase(frame, left, top)
    if not frame then return end
    local dashboardMoveX = 0
    if ns.GetDevLayoutOffset then
        dashboardMoveX = select(1, ns.GetDevLayoutOffset("dashboard.move")) or 0
    end
    frame.devTopLeftBase = { x = (left or 0) - dashboardMoveX, y = top or 0 }
end

-- Apply the user's remembered spot (or center on first launch). Does not write SavedVariables.
local function ApplyUserWindowPosition(frame)
    if not frame or not UIParent then return end
    local saved = LoadWindowPosition()
    frame:ClearAllPoints()
    if saved and saved.mode == "TOPLEFT" then
        local x, y = tonumber(saved.x) or 0, tonumber(saved.y) or 0
        frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", x, y)
        frame.svUserWindowPos = { x = x, y = y }
        SyncDevTopLeftBase(frame, x, y)
    elseif saved and saved.mode == "CENTER" then
        frame:SetPoint("CENTER", UIParent, "CENTER", tonumber(saved.ox) or 0, tonumber(saved.oy) or 0)
        local left, top = frame:GetLeft(), frame:GetTop()
        if left and top then
            frame.svUserWindowPos = { x = left, y = top }
            SyncDevTopLeftBase(frame, left, top)
        else
            frame.devTopLeftBase = {
                x = tonumber(saved.ox) or 0,
                y = tonumber(saved.oy) or 0,
                point = "CENTER",
            }
        end
    else
        -- First launch: center. Position is saved only after the user moves or closes.
        frame:SetPoint("CENTER")
        frame.svUserWindowPos = nil
        frame.devTopLeftBase = { x = 0, y = 0, point = "CENTER" }
    end
end

-- Keep the full frame (including open right panels) on screen by shifting left if needed.
-- Does not overwrite the remembered user position unless persistUserPos is true.
local function FitWindowOnScreen(frame, persistUserPos)
    if not frame or not UIParent then return end
    local pw = UIParent:GetWidth() or 0
    local ph = UIParent:GetHeight() or 0
    local fw = frame:GetWidth() or 0
    local fh = frame:GetHeight() or 0
    if pw <= 0 or ph <= 0 or fw <= 0 or fh <= 0 then return end

    local left = frame:GetLeft()
    local top = frame:GetTop()
    local bottom = frame:GetBottom()
    if not left or not top then return end

    local margin = 16
    local right = left + fw
    if right > pw - margin then
        left = left - (right - (pw - margin))
    end
    if left < margin then
        left = margin
    end
    if top > ph - margin then
        top = ph - margin
    end
    if bottom and (bottom < margin) then
        top = margin + fh
    end

    frame:ClearAllPoints()
    frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", left, top)
    SyncDevTopLeftBase(frame, left, top)
    if persistUserPos then
        SaveWindowPosition(frame)
    end
end

local function EnsureWindowOnScreen(frame)
    FitWindowOnScreen(frame, false)
end

local function ClampWindowToScreen(frame)
    FitWindowOnScreen(frame, false)
end

-- Re-apply remembered user spot after panel width changes, then fit if overflowing.
function ns.ReapplyStatAuditWindowLayout(frame)
    frame = frame or AuditFrame
    if not frame then return end
    local user = frame.svUserWindowPos
    if not user then
        local saved = LoadWindowPosition()
        if saved and saved.mode == "TOPLEFT" then
            user = { x = tonumber(saved.x) or 0, y = tonumber(saved.y) or 0 }
            frame.svUserWindowPos = user
        end
    end
    if user and user.x ~= nil and user.y ~= nil then
        frame:ClearAllPoints()
        frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", user.x, user.y)
        SyncDevTopLeftBase(frame, user.x, user.y)
    end
    FitWindowOnScreen(frame, false)
end

GetCharacterKey = function()
    local name, realm = nil, nil
    if type(UnitFullName) == "function" then
        name, realm = UnitFullName("player")
    end
    if not name and type(UnitName) == "function" then
        name = UnitName("player")
    end
    if not realm and type(GetRealmName) == "function" then
        realm = GetRealmName()
    end
    name = name or "Unknown"
    realm = realm or "UnknownRealm"
    return tostring(realm) .. ":" .. tostring(name)
end

GetCustomBucket = function(profileID)
    if type(profileID) ~= "string" or profileID == "" then return nil end
    local db = EnsureSavedDB()
    local key = GetCharacterKey()
    db.statAuditCustomByCharacter[key] = db.statAuditCustomByCharacter[key] or {}
    local bucket = db.statAuditCustomByCharacter[key]
    -- one-time migration from old global custom table
    if not bucket[profileID] and type(db.statAuditCustom[profileID]) == "table" then
        bucket[profileID] = db.statAuditCustom[profileID]
    end
    bucket[profileID] = bucket[profileID] or { targets = {}, softCaps = {}, baseModifiers = {} }
    return bucket[profileID]
end

local function HasCustomProfile(profileID)
    local bucket = GetCustomBucket(profileID)
    if not bucket then return false end
    return next(bucket.targets or {}) ~= nil or next(bucket.softCaps or {}) ~= nil or next(bucket.baseModifiers or {}) ~= nil
end

local ACTIVE_SPEC_SENTINEL = "ACTIVE_SPECIALIZATION"
local LOOT_SPEC_SENTINEL = "LOOT_SPECIALIZATION"
GOAL_LEVELING = "LEVELING"
GOAL_OVERALL = "OVERALL"
GOAL_MYTHIC_PLUS = "MYTHIC_PLUS"
GOAL_RAID = "RAID"
GOAL_PVP = "PVP"
DEFAULT_MAX_LEVEL_GOAL = GOAL_MYTHIC_PLUS

local GOAL_OPTIONS = {
    { key = GOAL_MYTHIC_PLUS, label = "Mythic+" },
    { key = GOAL_RAID, label = "Raid" },
    { key = GOAL_PVP, label = "PvP" },
}

local GOAL_LABEL_BY_KEY = {
    [GOAL_LEVELING] = "Leveling",
    [GOAL_MYTHIC_PLUS] = "Mythic+",
    [GOAL_RAID] = "Raid",
    [GOAL_PVP] = "PvP",
}

local function GetGoalDisplayLabel(goalMode)
    goalMode = tostring(goalMode or "")
    if goalMode == "SOLO" then goalMode = GOAL_MYTHIC_PLUS end
    return GOAL_LABEL_BY_KEY[goalMode] or goalMode
end

local function FormatViewDropdownText(label, active)
    label = tostring(label or "Select")
    return label
end

local function BuildDropdownSelectionSignature(selection)
    if type(selection) ~= "table" then return "" end
    return table.concat({
        tostring(selection.primarySpecID or ""),
        tostring(selection.secondarySpecID or ""),
        tostring(selection.goalMode or ""),
        tostring(selection.secondaryGoalMode or ""),
        tostring(selection.secondaryEnabled and 1 or 0),
        tostring(selection.activeView or "MAIN"),
    }, ":")
end

local function NormalizeGoalMode(goalMode)
    goalMode = tostring(goalMode or "")
    if goalMode == "SOLO" then return GOAL_MYTHIC_PLUS end
    if goalMode == "OVERALL" then return GOAL_MYTHIC_PLUS end
    if goalMode == "MYTHIC_PLUS" then return GOAL_MYTHIC_PLUS end
    if goalMode == "RAID" then return GOAL_RAID end
    if goalMode == "PVP" then return GOAL_PVP end
    if goalMode == GOAL_LEVELING
        or goalMode == GOAL_MYTHIC_PLUS
        or goalMode == GOAL_RAID
        or goalMode == GOAL_PVP then
        return goalMode
    end
    return DEFAULT_MAX_LEVEL_GOAL
end

local function NormalizeOptionalGoalMode(goalMode)
    if goalMode == nil then return nil end
    goalMode = tostring(goalMode or "")
    if goalMode == "" or goalMode == "CHOOSE_OFF_SPEC" or goalMode == "NONE" then return nil end
    return NormalizeGoalMode(goalMode)
end

local function NormalizeRequiredGoalMode(goalMode)
    return NormalizeOptionalGoalMode(goalMode)
end

GetSavedSelection = function()
    local db = EnsureSavedDB()
    local key = GetCharacterKey()
    db.statAuditSelectionByCharacter[key] = db.statAuditSelectionByCharacter[key] or {}
    local s = db.statAuditSelectionByCharacter[key]
    -- one-time migration from old global selection
    if next(s) == nil and type(db.statAuditSelection) == "table" and next(db.statAuditSelection) ~= nil then
        for k, v in pairs(db.statAuditSelection) do
            if k ~= "secondaryEnabled" and k ~= "autoDetectHeroTalent" then
                s[k] = v
            end
        end
    end
    if s.secondaryGoalMode ~= nil then
        s.secondaryGoalMode = NormalizeOptionalGoalMode(s.secondaryGoalMode)
    end
    s.autoDetectHeroTalent = false
    s.goalMode = NormalizeRequiredGoalMode(s.goalMode)
    -- One-time migration: old Overall / Leveling selections map to Mythic+.
    if s.goalMode == GOAL_OVERALL or s.goalMode == "OVERALL" or s.goalMode == GOAL_LEVELING or s.goalMode == "LEVELING" then
        s.goalMode = DEFAULT_MAX_LEVEL_GOAL
    end
    if s.secondaryGoalMode == GOAL_OVERALL or s.secondaryGoalMode == "OVERALL" or s.secondaryGoalMode == GOAL_LEVELING or s.secondaryGoalMode == "LEVELING" then
        s.secondaryGoalMode = nil
        s.secondarySpecID = nil
        s.activeView = "MAIN"
    end
    if s.primarySpecID ~= nil and s.primarySpecID ~= ACTIVE_SPEC_SENTINEL and s.primarySpecID ~= LOOT_SPEC_SENTINEL then s.primarySpecID = tonumber(s.primarySpecID) end
    if s.secondarySpecID ~= nil and s.secondarySpecID ~= ACTIVE_SPEC_SENTINEL and s.secondarySpecID ~= LOOT_SPEC_SENTINEL then s.secondarySpecID = tonumber(s.secondarySpecID) end
    -- Off Spec is fully on only when both Profile and specialization are chosen.
    s.secondaryEnabled = (s.secondaryGoalMode ~= nil) and (s.secondarySpecID ~= nil) or false
    if not s.secondaryEnabled then s.activeView = "MAIN" end
    if s.activeView ~= "OFF" then s.activeView = "MAIN" end
    db.statAuditSelectionByCharacter[key] = s
    return s
end

ns.StatAuditIsPlayerBelowHeroTalentLevel = function()
    if type(UnitLevel) ~= "function" then return false end
    local level = tonumber(UnitLevel("player"))
    local model = ns.GlobalStatVerdictModifiers and ns.GlobalStatVerdictModifiers.itemLevel or nil
    local heroTalentUnlockLevel = SafeNumber(model and model.heroTalentUnlockLevel) or 80
    return level and level > 0 and level < heroTalentUnlockLevel
end

ns.StatAuditIsPlayerBelowMaxLevel = function()
    if type(UnitLevel) ~= "function" then return false end
    local level = tonumber(UnitLevel("player"))
    if not level or level <= 0 then return false end
    local maxLevel = nil
    if type(GetMaxPlayerLevel) == "function" then
        maxLevel = tonumber(GetMaxPlayerLevel())
    end
    if (not maxLevel or maxLevel <= 0) and type(GetMaxLevelForPlayerExpansion) == "function" then
        maxLevel = tonumber(GetMaxLevelForPlayerExpansion())
    end
    if not maxLevel or maxLevel <= 0 then maxLevel = 90 end
    return level < maxLevel
end

GetEffectiveGoalMode = function(selection)
    if type(selection) == "table" and selection.activeView == "OFF" and selection.secondaryEnabled then
        return NormalizeOptionalGoalMode(selection.secondaryGoalMode)
    end
    return NormalizeRequiredGoalMode(selection and selection.goalMode)
end

function ns.GetStatAuditGoalMode()
    return GetEffectiveGoalMode(GetSavedSelection())
end

SaveSelection = function(selection)
    local db = EnsureSavedDB()
    local key = GetCharacterKey()
    db.statAuditSelectionByCharacter[key] = db.statAuditSelectionByCharacter[key] or {}
    local secondaryEnabled = (selection.secondaryGoalMode ~= nil) and (selection.secondarySpecID ~= nil) or false
    selection.secondaryEnabled = secondaryEnabled
    if not secondaryEnabled and selection.activeView == "OFF" then
        selection.activeView = "MAIN"
    end
    db.statAuditSelectionByCharacter[key].secondaryEnabled = secondaryEnabled
    db.statAuditSelectionByCharacter[key].autoDetectHeroTalent = false
    db.statAuditSelectionByCharacter[key].primarySpecID = selection.primarySpecID
    db.statAuditSelectionByCharacter[key].secondarySpecID = selection.secondarySpecID
    db.statAuditSelectionByCharacter[key].activeView = (selection.activeView == "OFF") and "OFF" or "MAIN"
    db.statAuditSelectionByCharacter[key].goalMode = NormalizeRequiredGoalMode(selection.goalMode)
    db.statAuditSelectionByCharacter[key].secondaryGoalMode = NormalizeOptionalGoalMode(selection.secondaryGoalMode)
end

local function SetSetupCheckboxTextColor(control, active)
    if not (control and control.Text) then return end
    if active then
        control.Text:SetTextColor(1.0, 1.0, 1.0)
    else
        control.Text:SetTextColor(0.55, 0.55, 0.55)
    end
end

local function ApplyToggleLabelColors(selection)
    local db = EnsureSavedDB()
    if AuditFrame and AuditFrame.goalLabel then
        AuditFrame.goalLabel:SetTextColor(0.90, 0.90, 0.90)
    end
    if AuditFrame and AuditFrame.offGoalLabel then
        local active = selection and selection.secondaryGoalMode ~= nil
        AuditFrame.offGoalLabel:SetTextColor(active and 0.90 or 0.55, active and 0.90 or 0.55, active and 0.90 or 0.55)
    end
    if VisibilityDropdown then
        local active = db.showBisPanel ~= false or db.showTrinketPanel == true
        if active then
            -- leave label style at default
        end
    end
end

function ns.SetStatAuditActiveView(view)
    local selection = GetSavedSelection()
    if view == "OFF" then
        if not selection.secondaryEnabled or not selection.secondarySpecID then
            return false
        end
        selection.activeView = "OFF"
    else
        selection.activeView = "MAIN"
    end
    SaveSelection(selection)
    RequestInventoryVerdictRefresh()
    if UpdateFrame and AuditFrame and AuditFrame:IsShown() then
        UpdateFrame()
    end
    return true
end

function ns.GetSavedStatAuditSelection()
    return GetSavedSelection()
end

function ns.GetStatAuditActiveView()
    local selection = GetSavedSelection()
    return selection and selection.activeView or "MAIN"
end

-- Shared context for Summary / BiS / Ranked Trinkets (follows MS/OS panel view).
function ns.GetActivePanelContext()
    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    local selection = GetSavedSelection()
    local view = (selection and selection.activeView == "OFF") and "OFF" or "MAIN"
    if view == "OFF" then
        if not (selection and selection.secondaryEnabled and secondaryContext and secondaryContext.profile) then
            view = "MAIN"
            if selection then
                selection.activeView = "MAIN"
                SaveSelection(selection)
            end
        else
            return secondaryContext, "OFF"
        end
    end
    return primaryContext, "MAIN"
end

local function GetHeroOptionsForSpec(goalMode, classFile, specID)
    local provider = ns.ProfileRepository and ns.ProfileRepository.GetProviderView and ns.ProfileRepository.GetProviderView(goalMode)
        or (ns.ProfileProviders and ns.ProfileProviders.Generated)
    local classProfiles = provider and classFile and provider[classFile]
    local specProfiles = classProfiles and classProfiles[specID]
    local opts = {}
    if specProfiles and type(specProfiles.hero) == "table" then
        for heroName in pairs(specProfiles.hero) do
            if type(heroName) == "string" and heroName ~= "" then
                opts[#opts + 1] = heroName
            end
        end
    end
    local staticHeroOptions = ns.GetStatVerdictHeroOptionsBySpecID and ns.GetStatVerdictHeroOptionsBySpecID(specID) or nil
    if #opts == 0 and type(staticHeroOptions) == "table" then
        for _, heroName in ipairs(staticHeroOptions) do
            if type(heroName) == "string" and heroName ~= "" then
                opts[#opts + 1] = heroName
            end
        end
    end
    table.sort(opts)
    return opts
end

local function GetActiveSpecID()
    if type(GetSpecialization) == "function" and type(GetSpecializationInfo) == "function" then
        local specIndex = GetSpecialization()
        if specIndex then
            local specID = select(1, GetSpecializationInfo(specIndex))
            specID = tonumber(specID)
            if specID and specID > 0 then return specID end
        end
    end
    return nil
end

local function GetLootSpecIDFallbackCurrent()
    if type(GetLootSpecialization) == "function" then
        local lootSpecID = tonumber(GetLootSpecialization())
        if lootSpecID and lootSpecID > 0 then return lootSpecID end
    end
    return GetActiveSpecID()
end

local function ResolveSelectedSpecID(specSelection)
    if specSelection == ACTIVE_SPEC_SENTINEL then return GetActiveSpecID() end
    if specSelection == LOOT_SPEC_SENTINEL then return GetLootSpecIDFallbackCurrent() end
    return tonumber(specSelection)
end

local function GetSpecOptionsForClass(classFile)
    local options = {}
    local provider = ns.ProfileProviders and ns.ProfileProviders.Generated
    local classProfiles = provider and provider[classFile]
    if type(classProfiles) ~= "table" then return options end
    for specID, specProfiles in pairs(classProfiles) do
        if type(specID) == "number" and type(specProfiles) == "table" and type(specProfiles.default) == "table" then
            options[#options + 1] = {
                specID = specID,
                specName = specProfiles.default.specName or ("Spec " .. tostring(specID)),
            }
        end
    end
    table.sort(options, function(a, b) return (a.specName or "") < (b.specName or "") end)
    return options
end

local function NormalizeDebugKeyPart(value)
    value = tostring(value or "")
    value = string.gsub(value, "[^%w]+", "_")
    value = string.gsub(value, "_+", "_")
    value = string.gsub(value, "^_+", "")
    value = string.gsub(value, "_+$", "")
    return string.upper(value)
end

local function BuildExpectedProfileDebugKey(context)
    if type(context) ~= "table" then return "NO_EXPECTED_KEY" end
    local specKey = context.specKey
        or context.specKeyOverride
        or (ns.GetStatVerdictSpecKeyBySpecID and ns.GetStatVerdictSpecKeyBySpecID(context.specID))
        or "NO_SPEC"
    local parts = {
        NormalizeDebugKeyPart(context.goal or "NO_GOAL"),
        NormalizeDebugKeyPart(specKey),
    }
    return table.concat(parts, "_")
end

local function BuildContextForSpec(baseContext, specID, selection, goalMode)
    local providerLabel = (baseContext and baseContext.providerLabel) or "StatVerdict"
    local classFile = baseContext and baseContext.classFile
    local className = baseContext and baseContext.className
    local goal = NormalizeOptionalGoalMode(goalMode)
    local specNameFallback = (baseContext and baseContext.specName) or "Spec"
    local function incomplete(reason)
        return {
            providerKey = "Generated",
            providerLabel = providerLabel,
            classFile = classFile,
            className = className,
            specID = specID,
            specName = specNameFallback,
            goal = goal,
            profile = nil,
            incompleteBuildReason = reason,
            source = "incomplete_manual_spec_context",
        }
    end
    if not goal then
        return incomplete("Choose a profile and spec to build this view.")
    end
    local provider = ns.ProfileRepository and ns.ProfileRepository.GetProviderView and ns.ProfileRepository.GetProviderView(goal)
        or (ns.ProfileProviders and ns.ProfileProviders.Generated)
    local classProfiles = provider and classFile and provider[classFile]
    local specProfiles = classProfiles and classProfiles[specID]
    local profile = specProfiles and specProfiles.default or nil
    if not profile then return incomplete("No generated profile exists for this profile/spec combination.") end
    specNameFallback = profile.specName or specNameFallback

    return {
        providerKey = "Generated",
        providerLabel = providerLabel,
        classFile = classFile,
        className = className,
        specID = specID,
        specName = profile.specName or (baseContext and baseContext.specName) or "Spec",
        role = profile.role or (baseContext and baseContext.role),
        goal = goal,
        profile = profile,
        source = "manual_spec_context",
    }
end

local function GetDebugOverrideState()
    local db = EnsureSavedDB()
    db.statAuditDebugOverride = db.statAuditDebugOverride or {}
    return db.statAuditDebugOverride
end

local function SaveDebugOverrideState(state)
    local db = EnsureSavedDB()
    db.statAuditDebugOverride = db.statAuditDebugOverride or {}
    for k, v in pairs(state or {}) do
        db.statAuditDebugOverride[k] = v
    end
end
ns.GetDebugOverrideState = GetDebugOverrideState
ns.SaveDebugOverrideState = SaveDebugOverrideState

local function BuildDebugBaseContext(state)
    if type(state) ~= "table" or not state.enabled then return nil end
    local classFile = tostring(state.classFile or "")
    local specID = tonumber(state.specID)
    local specKey = tostring(state.specKey or "")
    if classFile == "" or (not specID and specKey == "") then return nil end
    local providerKey = "Generated"
    local providerLabel = "StatVerdict"
    local provider = ns.ProfileProviders and ns.ProfileProviders[providerKey]
    local classProfiles = provider and provider[classFile]
    local specProfiles = classProfiles and specID and classProfiles[specID] or nil
    local defaultProfile = specProfiles and specProfiles.default
    local className = (defaultProfile and defaultProfile.className) or (LOCALIZED_CLASS_NAMES_MALE and LOCALIZED_CLASS_NAMES_MALE[classFile]) or classFile
    local specName = (defaultProfile and defaultProfile.specName) or (ns.GetStatVerdictSpecNameByKey and ns.GetStatVerdictSpecNameByKey(specKey)) or ("Spec " .. tostring(specID or specKey))
    return {
        providerKey = providerKey,
        providerLabel = providerLabel,
        classFile = classFile,
        className = className,
        specID = specID,
        specName = specName,
        role = defaultProfile and defaultProfile.role or nil,
        profile = defaultProfile or {},
        specKeyOverride = (specKey ~= "" and specKey) or nil,
        source = "debug_override",
    }
end

local function GetBaseContextForAudit()
    -- Debug class/spec override is developer-only (AdvDev TOC).
    if ns.STATVERDICT_DEV_TOOLS then
        local debugState = GetDebugOverrideState()
        local debugCtx = BuildDebugBaseContext(debugState)
        if debugCtx then return debugCtx end
    end
    return ns.GetEvaluationContext and ns.GetEvaluationContext() or nil
end

function ns.GetTooltipEvaluationContexts()
    local baseContext = GetBaseContextForAudit()
    if not baseContext or not baseContext.profile then
        return nil, nil
    end
    if baseContext.source == "debug_override" then
        return baseContext, nil
    end

    local selection = GetSavedSelection()
    local primarySpecID = ResolveSelectedSpecID(selection.primarySpecID) or (baseContext and baseContext.specID)
    local primaryContext = primarySpecID and BuildContextForSpec(baseContext, primarySpecID, selection, selection.goalMode) or nil

    local secondaryContext = nil
    local secondarySpecID = ResolveSelectedSpecID(selection.secondarySpecID)
    local primaryGoal = NormalizeOptionalGoalMode(selection.goalMode)
    local secondaryGoal = NormalizeOptionalGoalMode(selection.secondaryGoalMode)
    local duplicateBuild = primarySpecID and secondarySpecID and primarySpecID == secondarySpecID and primaryGoal == secondaryGoal
    if selection.secondaryEnabled and secondarySpecID and not duplicateBuild then
        secondaryContext = BuildContextForSpec(baseContext, secondarySpecID, selection, selection.secondaryGoalMode)
    end
    SaveSelection(selection)
    return primaryContext, secondaryContext
end

local function LoadSavedLayout()
    local db = EnsureSavedDB()
    db.statAuditLayout = db.statAuditLayout or {}
    local saved = db.statAuditLayout
    -- one-time migration from per-character layout to global layout
    if next(saved) == nil and type(db.statAuditLayoutByCharacter) == "table" then
        local currentKey = GetCharacterKey()
        local currentLayout = db.statAuditLayoutByCharacter[currentKey]
        if type(currentLayout) == "table" and next(currentLayout) ~= nil then
            for k, v in pairs(currentLayout) do saved[k] = v end
        else
            -- fallback: pick first non-empty character layout
            for _, v in pairs(db.statAuditLayoutByCharacter) do
                if type(v) == "table" and next(v) ~= nil then
                    for kk, vv in pairs(v) do saved[kk] = vv end
                    break
                end
            end
        end
    end
    return NormalizeLayoutFields(saved, {})
end

local function SaveLayout(layout)
    local db = EnsureSavedDB()
    db.statAuditLayout = db.statAuditLayout or {}
    local normalized = NormalizeLayoutFields(layout or {}, db.statAuditLayout)
    for _, rule in ipairs(LAYOUT_FIELD_RULES) do
        db.statAuditLayout[rule.key] = normalized[rule.key]
    end
end

local function LayoutTitleAndSelectors(frame, layout)
    local titleFontSize = (ns.GetSpecTitleFontSize and ns.GetSpecTitleFontSize())
        or layout.titleFontSize
        or LAYOUT_CONST.TITLE_FONT_SIZE_DEFAULT
    if frame.subtitle then
        frame.subtitle:ClearAllPoints()
        frame.subtitle:SetPoint("TOPLEFT", frame, "TOPLEFT", layout.titleX, layout.titleY)
        frame.subtitle:SetWidth(layout.titleWidth)
        local currentFont, _, fontFlags = frame.subtitle:GetFont()
        if currentFont then frame.subtitle:SetFont(currentFont, titleFontSize, fontFlags) end
        frame.subtitle.StatVerdictTitleBaseSize = titleFontSize
    end
    if frame.secondarySubtitle then
        frame.secondarySubtitle:ClearAllPoints()
        frame.secondarySubtitle:SetPoint("TOPLEFT", frame, "TOPLEFT", layout.secondaryTitleX, layout.secondaryTitleY)
        frame.secondarySubtitle:SetWidth(layout.titleWidth)
        local currentFont, _, fontFlags = frame.secondarySubtitle:GetFont()
        if currentFont then frame.secondarySubtitle:SetFont(currentFont, titleFontSize, fontFlags) end
        frame.secondarySubtitle.StatVerdictTitleBaseSize = titleFontSize
    end
    local profileTagFontSize = math.max(8, titleFontSize - 2)
    if frame.profileTagMain then
        local f, _, fl = frame.profileTagMain:GetFont()
        if f then frame.profileTagMain:SetFont(f, profileTagFontSize, fl) end
    end
    if frame.profileTagSecondary then
        local f, _, fl = frame.profileTagSecondary:GetFont()
        if f then frame.profileTagSecondary:SetFont(f, profileTagFontSize, fl) end
    end
    if frame.primaryLabel then
        frame.primaryLabel:ClearAllPoints()
        frame.primaryLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", layout.primaryLabelX, layout.primaryLabelY)
        local f, _, fl = frame.primaryLabel:GetFont()
        if f then frame.primaryLabel:SetFont(f, layout.aspectLabelFontSize, fl) end
    end
    if frame.secondaryLabel then
        frame.secondaryLabel:ClearAllPoints()
        frame.secondaryLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", layout.secondaryLabelX, layout.secondaryLabelY)
        local f, _, fl = frame.secondaryLabel:GetFont()
        if f then frame.secondaryLabel:SetFont(f, layout.aspectLabelFontSize, fl) end
    end
    if frame.goalLabel then
        frame.goalLabel:ClearAllPoints()
        frame.goalLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", layout.goalLabelX, layout.goalLabelY)
        local f, _, fl = frame.goalLabel:GetFont()
        if f then frame.goalLabel:SetFont(f, layout.aspectLabelFontSize, fl) end
    end
    if frame.offGoalLabel then
        frame.offGoalLabel:ClearAllPoints()
        frame.offGoalLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", layout.goalLabelX, layout.goalLabelY - 104)
        local f, _, fl = frame.offGoalLabel:GetFont()
        if f then frame.offGoalLabel:SetFont(f, layout.aspectLabelFontSize, fl) end
    end
    local function LayoutChipDropdown(dropdown, point, relative, relPoint, x, y, width)
        if not dropdown then return end
        dropdown:ClearAllPoints()
        dropdown:SetPoint(point, relative, relPoint, x, y)
        dropdown:SetWidth(width)
        dropdown:SetScale(1)
    end
    if PrimaryAspectDropdown then
        LayoutChipDropdown(PrimaryAspectDropdown, "TOPRIGHT", frame, "TOPRIGHT", layout.primaryDropdownX, layout.primaryDropdownY, layout.dropdownWidth)
    end
    if SecondaryAspectDropdown then
        LayoutChipDropdown(SecondaryAspectDropdown, "TOPRIGHT", frame, "TOPRIGHT", layout.secondaryDropdownX, layout.secondaryDropdownY, layout.dropdownWidth)
    end
    if GoalDropdown then
        LayoutChipDropdown(GoalDropdown, "TOPRIGHT", frame, "TOPRIGHT", layout.goalDropdownX, layout.goalDropdownY, layout.dropdownWidth)
    end
    if OffGoalDropdown then
        LayoutChipDropdown(OffGoalDropdown, "TOPRIGHT", frame, "TOPRIGHT", layout.goalDropdownX, layout.goalDropdownY - 104, layout.dropdownWidth)
    end
    if VisibilityDropdown then
        LayoutChipDropdown(VisibilityDropdown, "TOPLEFT", frame, "TOPLEFT", layout.offspecToggleX, layout.offspecToggleY, layout.dropdownWidth)
        VisibilityDropdown:Hide()
    end
    if frame.avgProgressText then
        -- Owned by MS stats (StatProgressPanel). Do not re-anchor to the main frame.
        local f, _, fl = frame.avgProgressText:GetFont()
        if f then frame.avgProgressText:SetFont(f, layout.avgProgressFontSize, fl) end
    end
    if frame.profileLine then
        frame.profileLine:ClearAllPoints()
        frame.profileLine:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", layout.sampleLineX, layout.sampleLineY)
        local f, _, fl = frame.profileLine:GetFont()
        if f then frame.profileLine:SetFont(f, layout.sampleLineFontSize, fl) end
    end
    if EditButton then
        EditButton:ClearAllPoints()
        EditButton:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", layout.editBtnX, layout.editBtnY)
        EditButton:SetSize(layout.buttonWidth, layout.buttonHeight)
    end
    if DefaultButton then
        DefaultButton:ClearAllPoints()
        DefaultButton:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", layout.defaultBtnX, layout.defaultBtnY)
        DefaultButton:SetSize(layout.buttonWidth, layout.buttonHeight)
    end
end

local function LayoutGridCard(frame, layout, gridBottomY)
    if not frame.gridCard then return end
    frame.gridCard:ClearAllPoints()
    frame.gridCard:SetPoint("TOPLEFT", frame, "TOPLEFT", layout.x - LAYOUT_CONST.GRID_CARD_INSET_X, layout.y + LAYOUT_CONST.HEADER_Y_OFFSET + LAYOUT_CONST.GRID_CARD_INSET_TOP)
    frame.gridCard:SetPoint("TOPRIGHT", frame, "TOPLEFT", layout.x + layout.width + LAYOUT_CONST.GRID_CARD_INSET_X, layout.y + LAYOUT_CONST.HEADER_Y_OFFSET + LAYOUT_CONST.GRID_CARD_INSET_TOP)
    frame.gridCard:SetPoint("BOTTOMLEFT", frame, "TOPLEFT", layout.x - LAYOUT_CONST.GRID_CARD_INSET_X, gridBottomY - LAYOUT_CONST.GRID_CARD_INSET_BOTTOM - layout.extraHeight)
    frame.gridCard:SetBackdropBorderColor(1, 1, 1, layout.borderAlpha)
end

local function LayoutHeadersAndGrid(frame, layout, lineCount, gridBottomY)
    for _, column in ipairs(frame.columns or {}) do
        local header = frame.headers and frame.headers[column.key]
        if header then
            header:ClearAllPoints()
            header:SetPoint("TOPLEFT", frame, "TOPLEFT", layout.x + (column.relX or 0), layout.y + LAYOUT_CONST.HEADER_Y_OFFSET)
            header:SetWidth(column.width)
        end
    end
    for _, separator in ipairs(frame.separators or {}) do
        separator:ClearAllPoints()
        local x = layout.x + (separator.relX or 0)
        separator:SetPoint("TOPLEFT", frame, "TOPLEFT", x, layout.y + LAYOUT_CONST.HEADER_Y_OFFSET)
        separator:SetPoint("BOTTOMLEFT", frame, "TOPLEFT", x, gridBottomY)
    end
    for lineIndex, line in ipairs(frame.horizontalLines or {}) do
        if lineIndex <= lineCount then
            line:Show()
            line:ClearAllPoints()
            line:SetPoint("TOPLEFT", frame, "TOPLEFT", layout.x, layout.y - ((lineIndex - 1) * LAYOUT_CONST.ROW_HEIGHT))
            line:SetWidth(layout.width)
            line:SetHeight(1)
        else
            line:Hide()
        end
    end
end

local function LayoutRows(frame, layout, visibleRows)
    for rowIndex, row in ipairs(frame.rows or {}) do
        local show = rowIndex <= visibleRows
        for key, cell in pairs(row) do
            if show then
                local column = frame.columnByKey and frame.columnByKey[key]
                if column then
                    cell:ClearAllPoints()
                    cell:SetPoint("TOPLEFT", frame, "TOPLEFT", layout.x + (column.relX or 0), layout.y + LAYOUT_CONST.ROW_START_OFFSET - ((rowIndex - 1) * LAYOUT_CONST.ROW_HEIGHT))
                    cell:SetWidth(column.width)
                end
                cell:Show()
            else
                cell:Hide()
            end
        end
    end
end

local function ApplyDynamicLayout(frame, usedRows)
    if not frame then return end
    frame.StatVerdictUsedRows = usedRows
    frame.StatVerdictLayoutControls = {
        goal = GoalDropdown,
        offGoal = OffGoalDropdown,
        primary = PrimaryAspectDropdown,
        secondary = SecondaryAspectDropdown,
        visibility = VisibilityDropdown,
    }
    if ns.StatVerdictDashboardLayout then
        ns.StatVerdictDashboardLayout.Apply(frame, usedRows, frame.StatVerdictLayoutControls)
        return
    end
    frame.gridLayout = NormalizeLayoutFields(frame.gridLayout or LoadSavedLayout(), frame.gridLayout or {})
    local layout = frame.gridLayout
    local visibleRows = math.max(1, math.min(LAYOUT_CONST.MAX_VISIBLE_ROWS, usedRows or 1))
    local lineCount = visibleRows + 1
    local gridBottomY = layout.y - ((lineCount - 1) * LAYOUT_CONST.ROW_HEIGHT)
    local frameHeight = (170 + (visibleRows * LAYOUT_CONST.ROW_HEIGHT)) + layout.frameExtraHeight
    frame:SetWidth(layout.frameWidth)
    frame:SetHeight(frameHeight)
    LayoutTitleAndSelectors(frame, layout)
    LayoutGridCard(frame, layout, gridBottomY)
    LayoutHeadersAndGrid(frame, layout, lineCount, gridBottomY)
    LayoutRows(frame, layout, visibleRows)
end

local function EnsureFrame()
    if AuditFrame then return AuditFrame end
    local frame = CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictStatAuditFrame") or "StatVerdictStatAuditFrame", UIParent, "BackdropTemplate")
    if ns.ApplyStatVerdictWindowChrome then
        ns.ApplyStatVerdictWindowChrome(frame, {
            close = true,
            title = "StatVerdict",
            version = ns.VERSION,
        })
    else
        frame:SetBackdrop({
            bgFile = "Interface\\Buttons\\WHITE8X8",
            edgeFile = "Interface\\Buttons\\WHITE8X8",
            edgeSize = 1,
            insets = { left = 1, right = 1, top = 1, bottom = 1 },
        })
        frame:SetBackdropColor(0.055, 0.062, 0.078, 0.97)
        frame:SetBackdropBorderColor(0.48, 0.50, 0.54, 0.92)
        frame.title = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
        frame.title:SetPoint("TOPLEFT", frame, "TOPLEFT", 12, -8)
        frame.title:SetText("StatVerdict")
        frame.title:SetTextColor(COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
    end
    if frame.title then
        frame.title:SetText("StatVerdict")
        frame.title:SetTextColor(COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
        frame.title:Show()
    end
    frame:SetSize(LAYOUT_CONST.FRAME_WIDTH_DEFAULT, 370)
    ApplyUserWindowPosition(frame)
    FitWindowOnScreen(frame, false)
    frame:SetMovable(true)
    frame:EnableMouse(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", frame.StartMoving)
    frame:SetScript("OnDragStop", function(self)
        self:StopMovingOrSizing()
        SaveWindowPosition(self)
    end)
    frame:Hide()

    -- Esc / combat CloseAllWindows / X all end up here.
    -- After combat the window stays closed until the user opens it again.
    frame:HookScript("OnHide", function(self)
        SaveWindowPosition(self)
        self.svWantShown = false
    end)

    -- Esc closes the window.
    if type(UISpecialFrames) == "table" then
        local already = false
        for i = 1, #UISpecialFrames do
            if UISpecialFrames[i] == "StatVerdictStatAuditFrame" then
                already = true
                break
            end
        end
        if not already then
            UISpecialFrames[#UISpecialFrames + 1] = "StatVerdictStatAuditFrame"
        end
    end

    frame.subtitle = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightLarge")
    frame.subtitle:SetPoint("TOPLEFT", frame, "TOPLEFT", LAYOUT_CONST.TITLE_X_DEFAULT, LAYOUT_CONST.TITLE_Y_DEFAULT)
    frame.subtitle:SetWidth(LAYOUT_CONST.TITLE_WIDTH_DEFAULT)
    frame.subtitle:SetJustifyH("LEFT")
    frame.subtitle:SetWordWrap(false)
    if frame.subtitle.SetNonSpaceWrap then
        frame.subtitle:SetNonSpaceWrap(false)
    end
    frame.subtitle:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
    frame.subtitle:EnableMouse(false)
    frame.subtitle:SetScript("OnEnter", nil)
    frame.subtitle:SetScript("OnLeave", nil)
    frame.subtitle:SetScript("OnMouseUp", nil)

    frame.profileTagMain = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.profileTagMain:SetJustifyH("LEFT")
    frame.profileTagMain:SetTextColor(0.40, 0.78, 1.00)

    frame.profileLine = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.profileLine:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", 360, 34)
    frame.profileLine:SetWidth(380)
    frame.profileLine:SetJustifyH("LEFT")
    frame.profileLine:SetTextColor(COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
    frame.profileLine:EnableMouse(true)
    frame.profileLine:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_TOPLEFT")
        GameTooltip:SetText("Data Source", 1, 0.82, 0.0)
        GameTooltip:AddLine("Generated from ClassCodex profile data.", 0.92, 0.82, 0.45, true)
        GameTooltip:Show()
    end)
    frame.profileLine:SetScript("OnLeave", function() GameTooltip:Hide() end)
    frame.profileLine:SetScript("OnMouseUp", function(_, button)
        if button ~= "LeftButton" then return end
        local url = "ClassCodex"
        if type(ChatEdit_ChooseBoxForSend) == "function" and type(ChatEdit_ActivateChat) == "function" then
            local eb = ChatEdit_ChooseBoxForSend()
            ChatEdit_ActivateChat(eb)
            if eb and type(eb.SetText) == "function" then
                eb:SetText(url)
                if type(eb.HighlightText) == "function" then
                    eb:HighlightText()
                end
            end
        else
            print(url)
        end
    end)
    frame.profileLine:Hide()

    frame.goalLabel = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.goalLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.GOAL_LABEL_X_DEFAULT, LAYOUT_CONST.GOAL_LABEL_Y_DEFAULT)
    frame.goalLabel:SetText("Goal")
    frame.goalLabel:SetTextColor(0.9, 0.9, 0.9)

    frame.primaryLabel = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.primaryLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.PRIMARY_LABEL_X_DEFAULT, LAYOUT_CONST.PRIMARY_LABEL_Y_DEFAULT)
    frame.primaryLabel:SetText("Main Spec")
    frame.primaryLabel:SetTextColor(0.9, 0.9, 0.9)

    frame.offGoalLabel = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.offGoalLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.GOAL_LABEL_X_DEFAULT, -190)
    frame.offGoalLabel:SetText("Off-Spec Profile")
    frame.offGoalLabel:SetTextColor(0.55, 0.55, 0.55)

    frame.secondaryLabel = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.secondaryLabel:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.SECONDARY_LABEL_X_DEFAULT, LAYOUT_CONST.SECONDARY_LABEL_Y_DEFAULT)
    frame.secondaryLabel:SetText("Off Spec")
    frame.secondaryLabel:SetTextColor(0.55, 0.55, 0.55)

    GoalDropdown = ns.CreateChipDropdown(frame, "StatVerdictGoalDropdown")
    GoalDropdown:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.GOAL_DROPDOWN_X_DEFAULT, LAYOUT_CONST.GOAL_DROPDOWN_Y_DEFAULT)
    GoalDropdown:SetWidth(LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT)

    PrimaryAspectDropdown = ns.CreateChipDropdown(frame, "StatVerdictPrimaryAspectDropdown")
    PrimaryAspectDropdown:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.PRIMARY_DROPDOWN_X_DEFAULT, LAYOUT_CONST.PRIMARY_DROPDOWN_Y_DEFAULT)
    PrimaryAspectDropdown:SetWidth(LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT)

    OffGoalDropdown = ns.CreateChipDropdown(frame, "StatVerdictOffGoalDropdown")
    OffGoalDropdown:SetWidth(LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT)

    SecondaryAspectDropdown = ns.CreateChipDropdown(frame, "StatVerdictSecondaryAspectDropdown")
    SecondaryAspectDropdown:SetPoint("TOPRIGHT", frame, "TOPRIGHT", LAYOUT_CONST.SECONDARY_DROPDOWN_X_DEFAULT, LAYOUT_CONST.SECONDARY_DROPDOWN_Y_DEFAULT)
    SecondaryAspectDropdown:SetWidth(LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT)

    VisibilityDropdown = ns.CreateChipDropdown(frame, "StatVerdictVisibilityDropdown")
    VisibilityDropdown:SetWidth(LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT)
    VisibilityDropdown:Hide()

    frame.secondarySubtitle = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightLarge")
    frame.secondarySubtitle:SetPoint("TOPLEFT", frame, "TOPLEFT", LAYOUT_CONST.SECONDARY_TITLE_X_DEFAULT, LAYOUT_CONST.SECONDARY_TITLE_Y_DEFAULT)
    frame.secondarySubtitle:SetWidth(LAYOUT_CONST.TITLE_WIDTH_DEFAULT)
    frame.secondarySubtitle:SetJustifyH("LEFT")
    frame.secondarySubtitle:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
    frame.secondarySubtitle:Hide()

    frame.profileTagSecondary = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    frame.profileTagSecondary:SetJustifyH("LEFT")
    frame.profileTagSecondary:SetTextColor(0.40, 0.78, 1.00)
    frame.profileTagSecondary:Hide()

    frame.avgProgressText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    frame.avgProgressText:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", LAYOUT_CONST.AVG_PROGRESS_X_DEFAULT, LAYOUT_CONST.AVG_PROGRESS_Y_DEFAULT)
    frame.avgProgressText:SetTextColor(0.40, 0.78, 1.00)
    frame.avgProgressText:SetText("Average Progress: -")
    frame.avgProgressText:EnableMouse(true)
    frame.avgProgressText:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_TOPLEFT")
        GameTooltip:SetText("Average Progress", 1, 0.82, 0.0)
        GameTooltip:AddLine("Mean capped progress across active stats.", 0.92, 0.82, 0.45, true)
        GameTooltip:AddLine("Each stat contributes up to 100%.", 0.92, 0.82, 0.45, true)
        GameTooltip:Show()
    end)
    frame.avgProgressText:SetScript("OnLeave", function()
        GameTooltip:Hide()
    end)

    frame.offAvgProgressText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    frame.offAvgProgressText:SetTextColor(0.40, 0.78, 1.00)
    frame.offAvgProgressText:SetText("Average Progress: -")
    frame.offAvgProgressText:Hide()
    frame.offAvgProgressText:EnableMouse(true)
    frame.offAvgProgressText:SetScript("OnEnter", function(self)
        GameTooltip:SetOwner(self, "ANCHOR_TOPLEFT")
        GameTooltip:SetText("Off Spec Average Progress", 1, 0.82, 0.0)
        GameTooltip:AddLine("Mean capped progress across Off Spec active stats.", 0.92, 0.82, 0.45, true)
        GameTooltip:AddLine("Each stat contributes up to 100%.", 0.92, 0.82, 0.45, true)
        GameTooltip:Show()
    end)
    frame.offAvgProgressText:SetScript("OnLeave", function()
        GameTooltip:Hide()
    end)

    frame.profileKeyDebugText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    frame.profileKeyDebugText:SetTextColor(0.75, 0.78, 0.82)
    frame.profileKeyDebugText:SetJustifyH("LEFT")
    frame.profileKeyDebugText:SetText("")
    frame.profileKeyDebugText:Hide()

    frame.expectedProfileKeyDebugText = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    frame.expectedProfileKeyDebugText:SetTextColor(0.92, 0.92, 0.92)
    frame.expectedProfileKeyDebugText:SetJustifyH("LEFT")
    frame.expectedProfileKeyDebugText:SetText("")
    frame.expectedProfileKeyDebugText:Hide()


    EditButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    EditButton:SetSize(LAYOUT_CONST.BUTTON_WIDTH_DEFAULT, LAYOUT_CONST.BUTTON_HEIGHT_DEFAULT)
    EditButton:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", LAYOUT_CONST.BUTTON_EDIT_X_DEFAULT, LAYOUT_CONST.BUTTON_EDIT_Y_DEFAULT)
    EditButton:SetText("Edit")
    EditButton:Hide()

    DefaultButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    DefaultButton:SetSize(LAYOUT_CONST.BUTTON_WIDTH_DEFAULT, LAYOUT_CONST.BUTTON_HEIGHT_DEFAULT)
    DefaultButton:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", LAYOUT_CONST.BUTTON_DEFAULT_X_DEFAULT, LAYOUT_CONST.BUTTON_DEFAULT_Y_DEFAULT)
    DefaultButton:SetText("Default")
    DefaultButton:Disable()
    DefaultButton:Hide()

    frame.gridCard = CreateFrame("Frame", nil, frame, "BackdropTemplate")
    frame.gridCard:SetFrameStrata(frame:GetFrameStrata())
    frame.gridCard:SetFrameLevel(math.max(1, frame:GetFrameLevel() - 1))
    frame.gridCard:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 14,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    frame.gridCard:SetBackdropColor(0.02, 0.03, 0.05, 0.36)
    frame.gridCard:SetBackdropBorderColor(1, 1, 1, 0.95)

    frame.headers, frame.rows, frame.separators = {}, {}, {}
    local columns = ns.StatVerdictStatProgressPanel
        and ns.StatVerdictStatProgressPanel.GetColumns(252)
        or {
            { key = "priority", label = "#", x = 262, relX = 10, width = 22, justify = "RIGHT" },
            { key = "stat", label = "Stat", x = 294, relX = 42, width = 122, justify = "LEFT" },
            { key = "current", label = "Current", x = 426, relX = 174, width = 70, justify = "RIGHT" },
            { key = "target", label = "Target", x = 506, relX = 254, width = 70, justify = "RIGHT" },
            { key = "progress", label = "Progress", x = 586, relX = 334, width = 92, justify = "CENTER" },
            { key = "liveModifier", label = "Weight", x = 688, relX = 436, width = 58, justify = "RIGHT" },
        }
    frame.columns = columns
    frame.columnByKey = {}
    for _, column in ipairs(columns) do
        column.relX = column.relX or (column.x - 252)
        frame.columnByKey[column.key] = column
    end
    for _, column in ipairs(columns) do
        frame.headers[column.key] = CreateText(frame, column.x, -78, column.width, "CENTER", "GameFontNormalSmall")
        frame.headers[column.key]:SetText(column.label)
        frame.headers[column.key]:SetDrawLayer("OVERLAY", 2)
        if HEADER_TOOLTIP_TEXT[column.key] then
            frame.headers[column.key]:SetTextColor(COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
            frame.headers[column.key]:EnableMouse(true)
            frame.headers[column.key]:SetScript("OnEnter", function(self)
                GameTooltip:SetOwner(self, "ANCHOR_TOP")
                GameTooltip:SetText(column.label, COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
                GameTooltip:AddLine(HEADER_TOOLTIP_TEXT[column.key], 0.92, 0.82, 0.45, true)
                GameTooltip:Show()
            end)
            frame.headers[column.key]:SetScript("OnLeave", function()
                GameTooltip:Hide()
            end)
        else
            frame.headers[column.key]:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
        end
    end
    frame.horizontalLines = {}
    for lineIndex = 1, (LAYOUT_CONST.MAX_VISIBLE_ROWS + 1) do
        local line = frame:CreateTexture(nil, "ARTWORK")
        line:SetColorTexture(0.9, 0.78, 0.28, lineIndex == 1 and 0.30 or 0.16)
        line:SetPoint("TOPLEFT", frame, "TOPLEFT", LAYOUT_CONST.GRID_LEFT_X, LAYOUT_CONST.GRID_TOP_Y - ((lineIndex - 1) * LAYOUT_CONST.ROW_HEIGHT))
        line:SetWidth(LAYOUT_CONST.GRID_WIDTH)
        line:SetHeight(1)
        frame.horizontalLines[#frame.horizontalLines + 1] = line
    end
    for rowIndex = 1, LAYOUT_CONST.MAX_VISIBLE_ROWS do
        frame.rows[rowIndex] = {}
        local y = -100 - ((rowIndex - 1) * LAYOUT_CONST.ROW_HEIGHT)
        for _, column in ipairs(columns) do
            frame.rows[rowIndex][column.key] = CreateText(frame, column.x, y, column.width, column.justify, "GameFontHighlightSmall")
            frame.rows[rowIndex][column.key]:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
            frame.rows[rowIndex][column.key]:SetDrawLayer("OVERLAY", 2)
        end
    end
    if ns.StatVerdictStatProgressPanel then
        ns.StatVerdictStatProgressPanel.EnsureProgressBars(frame, LAYOUT_CONST.MAX_VISIBLE_ROWS)
        ns.StatVerdictStatProgressPanel.EnsureOffProgressBars(frame, LAYOUT_CONST.MAX_VISIBLE_ROWS)
    end

    -- Off Spec duplicate of the same column/row widgets (hidden until Off Spec is selected).
    frame.offHeaders, frame.offRows = {}, {}
    for _, column in ipairs(columns) do
        frame.offHeaders[column.key] = CreateText(frame, column.x, -78, column.width, "CENTER", "GameFontNormalSmall")
        frame.offHeaders[column.key]:SetText(column.label)
        frame.offHeaders[column.key]:SetDrawLayer("OVERLAY", 2)
        if HEADER_TOOLTIP_TEXT[column.key] then
            frame.offHeaders[column.key]:SetTextColor(COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
        else
            frame.offHeaders[column.key]:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
        end
        frame.offHeaders[column.key]:Hide()
    end
    for rowIndex = 1, LAYOUT_CONST.MAX_VISIBLE_ROWS do
        frame.offRows[rowIndex] = {}
        local y = -100 - ((rowIndex - 1) * LAYOUT_CONST.ROW_HEIGHT)
        for _, column in ipairs(columns) do
            frame.offRows[rowIndex][column.key] = CreateText(frame, column.x, y, column.width, column.justify, "GameFontHighlightSmall")
            frame.offRows[rowIndex][column.key]:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
            frame.offRows[rowIndex][column.key]:SetDrawLayer("OVERLAY", 2)
            frame.offRows[rowIndex][column.key]:Hide()
        end
    end
    frame.svOffSpecVisible = false
    frame.svOffSpecUsedRows = 0

    frame.inlineEditors = {}
    frame.editMode = false
    frame.editDirty = false
    frame.pendingEdits = {}

    local function EnsureInlineEditor(rowIndex, key, anchorCell)
        frame.inlineEditors[rowIndex] = frame.inlineEditors[rowIndex] or {}
        if frame.inlineEditors[rowIndex][key] then return frame.inlineEditors[rowIndex][key] end
        local eb = CreateFrame("EditBox", nil, frame)
        eb:SetAutoFocus(false)
        eb:SetNumeric(false)
        eb:SetHeight(12)
        eb:SetFontObject("GameFontHighlightSmall")
        eb:SetTextInsets(0, 0, 0, 0)
        eb:SetJustifyH("CENTER")
        eb:SetJustifyV("MIDDLE")
        eb:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
        eb:SetScript("OnEnterPressed", function(self) self:ClearFocus() end)
        eb:EnableMouse(true)
        eb:SetFrameStrata("DIALOG")
        eb:SetFrameLevel(frame:GetFrameLevel() + 30)
        eb:SetTextColor(1, 1, 1)
        eb:SetCursorPosition(0)
        eb:Hide()
        frame.inlineEditors[rowIndex][key] = eb
        return eb
    end

    local function HideAllInlineEditors()
        for _, rowEditors in pairs(frame.inlineEditors) do
            for _, eb in pairs(rowEditors) do
                eb:Hide()
            end
        end
    end

    local function RecalcEditState()
        local rowsData = frame.currentRenderedData or {}
        local pending = frame.pendingEdits or {}
        local dirty = false
        for _, item in ipairs(rowsData) do
            local p = pending[item.key]
            if p then dirty = true end
        end
        frame.editDirty = dirty
        if frame.editMode then
            EditButton:SetText("Apply")
        else
            EditButton:SetText("Edit")
        end
    end

    local function RefreshInlineEditors()
        HideAllInlineEditors()
        if not frame.editMode then return end
        local rowsData = frame.currentRenderedData or {}
        local pending = frame.pendingEdits or {}
        for _, item in ipairs(rowsData) do
            local row = frame.rows[item.rowIndex]
            if row then
                local p = pending[item.key] or {}
                local tgt = (p.target ~= nil) and p.target or item.targetValue
                local cap = (p.softCap ~= nil) and p.softCap or item.softCapValue
                local base = (p.base ~= nil) and p.base or item.baseValue

                local ebTarget = EnsureInlineEditor(item.rowIndex, "target", row.target)
                local ebSoft = EnsureInlineEditor(item.rowIndex, "softCap", row.softCap)
                local ebBase = EnsureInlineEditor(item.rowIndex, "baseModifier", row.baseModifier)

                ebTarget:ClearAllPoints()
                ebTarget:SetWidth(math.max(24, (row.target:GetWidth() or 64) - 6))
                ebTarget:SetPoint("CENTER", row.target, "CENTER", 0, 0)
                ebSoft:ClearAllPoints()
                ebSoft:SetWidth(math.max(24, (row.softCap:GetWidth() or 64) - 6))
                ebSoft:SetPoint("CENTER", row.softCap, "CENTER", 0, 0)
                ebBase:ClearAllPoints()
                ebBase:SetWidth(math.max(22, (row.baseModifier:GetWidth() or 52) - 6))
                ebBase:SetPoint("CENTER", row.baseModifier, "CENTER", 0, 0)

                ebTarget:SetText(tgt and tostring(math.floor(tgt + 0.5)) or "")
                ebSoft:SetText(cap and tostring(math.floor(cap + 0.5)) or "")
                ebBase:SetText(base and string.format("%.2f", base) or "")
                ebTarget:SetTextColor(1, 1, 1)
                ebSoft:SetTextColor(1, 1, 1)
                ebBase:SetTextColor(1, 1, 1)

                ebTarget:SetScript("OnTextChanged", function(self)
                    frame.pendingEdits[item.key] = frame.pendingEdits[item.key] or {}
                    frame.pendingEdits[item.key].target = SafeNumber(self:GetText())
                    RecalcEditState()
                end)
                ebSoft:SetScript("OnTextChanged", function(self)
                    frame.pendingEdits[item.key] = frame.pendingEdits[item.key] or {}
                    frame.pendingEdits[item.key].softCap = SafeNumber(self:GetText())
                    RecalcEditState()
                end)
                ebBase:SetScript("OnTextChanged", function(self)
                    frame.pendingEdits[item.key] = frame.pendingEdits[item.key] or {}
                    frame.pendingEdits[item.key].base = SafeNumber(self:GetText())
                    RecalcEditState()
                end)

                if item.unboundedTarget then ebTarget:Hide() else ebTarget:Show() end
                ebSoft:Show()
                ebBase:Show()
            end
        end
        RecalcEditState()
    end
    frame.RefreshInlineEditors = RefreshInlineEditors
    frame.HideInlineEditors = HideAllInlineEditors

    EditButton:SetScript("OnClick", function()
        if not frame.editMode then
            frame.editMode = true
            frame.pendingEdits = {}
            EditButton:SetText("Apply")
            if UpdateFrame then UpdateFrame() end
        else
            local profileID = frame.currentProfileID
            if profileID then
                local bucket = GetCustomBucket(profileID)
                local rowsData = frame.currentRenderedData or {}
                local pending = frame.pendingEdits or {}
                for _, item in ipairs(rowsData) do
                    local p = pending[item.key]
                    if p then
                        if p.target ~= nil then bucket.targets[item.key] = p.target end
                        if p.softCap ~= nil then bucket.softCaps[item.key] = p.softCap end
                        if p.base ~= nil then bucket.baseModifiers[item.key] = p.base end
                    end
                end
            end
            frame.editMode = false
            frame.pendingEdits = {}
            frame.editDirty = false
            HideAllInlineEditors()
            EditButton:SetText("Edit")
            if UpdateFrame then UpdateFrame() end
            RequestInventoryVerdictRefresh()
        end
    end)

    DefaultButton:SetScript("OnClick", function()
        local profileID = frame.currentProfileID
        if not profileID then return end
        local key = GetCharacterKey()
        local db = EnsureSavedDB()
        db.statAuditCustomByCharacter[key] = db.statAuditCustomByCharacter[key] or {}
        db.statAuditCustomByCharacter[key][profileID] = { targets = {}, softCaps = {}, baseModifiers = {} }
        frame.pendingEdits = {}
        frame.editDirty = false
        if UpdateFrame then UpdateFrame() end
        RequestInventoryVerdictRefresh()
    end)
    frame.gridLayout = LoadSavedLayout()
    ApplyDynamicLayout(frame, 1)
    AuditFrame = frame
    return frame
end

local function BuildAspectLabel(specName, heroName)
    if heroName and heroName ~= "" then
        return tostring(specName) .. " / " .. tostring(heroName)
    end
    return tostring(specName)
end

local inventoryRefreshGeneration = 0

RequestInventoryVerdictRefresh = function(kind)
    inventoryRefreshGeneration = inventoryRefreshGeneration + 1
    local generation = inventoryRefreshGeneration
    local refreshKind = kind == "bags" and "bags" or "full"

    local function doRefresh()
        if generation ~= inventoryRefreshGeneration then return end
        if ns.ClearUpgradeIndicatorDecisionCache then
            ns.ClearUpgradeIndicatorDecisionCache()
        end
        if ns.RefreshUpgradeIndicators then
            ns.RefreshUpgradeIndicators(refreshKind)
        end
    end

    doRefresh()

    if C_Timer and C_Timer.After then
        -- Dropdown changes can happen while bag buttons are not yet repainted.
        -- Run a few light delayed passes so MS/OS/upgrade indicators update
        -- without requiring the user to close and reopen the bags.
        C_Timer.After(0.15, doRefresh)
        C_Timer.After(0.35, doRefresh)
        C_Timer.After(0.75, doRefresh)
    end
end

function ns.RequestInventoryVerdictRefresh(kind)
    RequestInventoryVerdictRefresh(kind)
end

local function RefreshProfileDropdown(dropdown, selectionField, placeholderText, _unusedLocked, labelControl, onChange)
    if not dropdown then return end
    local selection = GetSavedSelection()
    local rawGoal = selection and selection[selectionField] or nil
    local currentGoal = rawGoal and NormalizeGoalMode(rawGoal) or nil
    local textValue = GOAL_LABEL_BY_KEY[currentGoal] or placeholderText or "Choose Profile"

    local options = {}
    options[#options + 1] = {
        text = placeholderText or "Choose Profile",
        checked = not currentGoal,
        func = function()
            selection[selectionField] = nil
            SaveSelection(selection)
            if onChange then onChange(selection) end
            RequestInventoryVerdictRefresh("full")
            if UpdateFrame then UpdateFrame() end
        end,
    }
    for _, option in ipairs(GOAL_OPTIONS) do
        options[#options + 1] = {
            text = option.label,
            checked = currentGoal == option.key,
            func = function()
                selection[selectionField] = option.key
                if selectionField == "goalMode" then
                    if selection.primarySpecID == nil or selection.primarySpecID == ACTIVE_SPEC_SENTINEL then
                        local currentSpecID = GetActiveSpecID and GetActiveSpecID() or nil
                        if currentSpecID then
                            selection.primarySpecID = currentSpecID
                        end
                    end
                    if selection.secondaryGoalMode and selection.secondaryGoalMode == option.key then
                        selection.secondaryGoalMode = nil
                        selection.secondarySpecID = nil
                        selection.secondaryEnabled = false
                        selection.activeView = "MAIN"
                    end
                end
                SaveSelection(selection)
                if onChange then onChange(selection) end
                RequestInventoryVerdictRefresh()
                if UpdateFrame then UpdateFrame() end
            end,
        }
    end

    if dropdown.SetOptions then dropdown:SetOptions(options) end
    if dropdown.SetText then dropdown:SetText(textValue) end
    if labelControl then labelControl:SetTextColor(0.90, 0.90, 0.90) end
end

local function RefreshGoalDropdown()
    local selection = GetSavedSelection()
    RefreshProfileDropdown(GoalDropdown, "goalMode", "Choose Profile", nil, AuditFrame and AuditFrame.goalLabel, function()
        if ns.ProfileRepository and ns.ProfileRepository.RefreshProviderView then
            ns.ProfileRepository.RefreshProviderView(selection.goalMode or DEFAULT_MAX_LEVEL_GOAL)
        end
    end)
end

-- True when candidate Off Spec + Off Profile would be the same build as Main Spec.
local function WouldDuplicateMainBuild(selection, candidateSpecID)
    candidateSpecID = tonumber(candidateSpecID)
    if not candidateSpecID or candidateSpecID <= 0 then return false end
    local resolvedMain = ResolveSelectedSpecID(selection and selection.primarySpecID) or GetActiveSpecID()
    if not resolvedMain or candidateSpecID ~= resolvedMain then return false end
    local primaryGoal = NormalizeOptionalGoalMode(selection and selection.goalMode)
    local secondaryGoal = NormalizeOptionalGoalMode(selection and selection.secondaryGoalMode)
    return primaryGoal ~= nil and secondaryGoal ~= nil and primaryGoal == secondaryGoal
end

-- Like Main Spec profile pick: prefer the currently played spec, unless it duplicates Main.
local function AutoAssignOffSpecFromActivePlay(selection)
    if not selection or not selection.secondaryGoalMode then
        return
    end
    local activeSpecID = GetActiveSpecID()
    if not activeSpecID then
        return
    end
    if WouldDuplicateMainBuild(selection, activeSpecID) then
        -- Same build as Main — leave Choose Off-Spec for a manual pick.
        if selection.secondarySpecID and WouldDuplicateMainBuild(selection, selection.secondarySpecID) then
            selection.secondarySpecID = nil
        end
        if not selection.secondarySpecID then
            selection.activeView = "MAIN"
        end
        return
    end
    selection.secondarySpecID = activeSpecID
    selection.activeView = "OFF"
end

local function ClearOffSpecSelection(selection)
    if not selection then return end
    selection.secondaryGoalMode = nil
    selection.secondarySpecID = nil
    selection.secondaryEnabled = false
    selection.activeView = "MAIN"
end

local function RefreshOffGoalDropdown()
    if not OffGoalDropdown then return end
    local selection = GetSavedSelection()
    local currentGoal = selection and NormalizeOptionalGoalMode(selection.secondaryGoalMode) or nil
    local hasProfile = currentGoal ~= nil
    local textValue = hasProfile and (GOAL_LABEL_BY_KEY[currentGoal] or "Off Spec Profile") or "Choose Profile"

    local options = {}
    -- When a profile is active, first action is Disable (restores Choose Profile).
    options[#options + 1] = {
        text = hasProfile and "Disable" or "Choose Profile",
        checked = not hasProfile,
        func = function()
            ClearOffSpecSelection(selection)
            SaveSelection(selection)
            if ns.ProfileRepository and ns.ProfileRepository.RefreshProviderView then
                ns.ProfileRepository.RefreshProviderView(selection.goalMode or DEFAULT_MAX_LEVEL_GOAL)
            end
            RequestInventoryVerdictRefresh("full")
            if UpdateFrame then UpdateFrame() end
        end,
    }
    for _, option in ipairs(GOAL_OPTIONS) do
        options[#options + 1] = {
            text = option.label,
            checked = currentGoal == option.key,
            func = function()
                selection.secondaryGoalMode = option.key
                -- Auto-pick currently played spec unless it duplicates Main Spec.
                AutoAssignOffSpecFromActivePlay(selection)
                SaveSelection(selection)
                if ns.ProfileRepository and ns.ProfileRepository.RefreshProviderView then
                    ns.ProfileRepository.RefreshProviderView(selection.secondaryGoalMode or selection.goalMode or DEFAULT_MAX_LEVEL_GOAL)
                end
                RequestInventoryVerdictRefresh()
                if UpdateFrame then UpdateFrame() end
            end,
        }
    end

    if OffGoalDropdown.SetOptions then OffGoalDropdown:SetOptions(options) end
    if OffGoalDropdown.SetText then OffGoalDropdown:SetText(textValue) end
    if AuditFrame and AuditFrame.offGoalLabel then
        AuditFrame.offGoalLabel:SetTextColor(hasProfile and 0.90 or 0.55, hasProfile and 0.90 or 0.55, hasProfile and 0.90 or 0.55)
    end
end

local function RefreshVisibilityDropdown()
    if not VisibilityDropdown then return end
    -- Replaced by Panels toggle buttons (Best in Slot / Ranked Trinkets / Options / Manual).
    VisibilityDropdown:Hide()
end

local function RefreshAspectDropdowns(context)
    if not PrimaryAspectDropdown or not SecondaryAspectDropdown then return end
    RefreshGoalDropdown()
    RefreshOffGoalDropdown()
    RefreshVisibilityDropdown()
    local classFile = context and context.classFile
    if not classFile then return end

    local options = GetSpecOptionsForClass(classFile)
    local selection = GetSavedSelection()
    local currentSpecID = context and context.specID or nil

    if not selection.primarySpecID then selection.primarySpecID = ACTIVE_SPEC_SENTINEL end
    if selection.secondaryGoalMode ~= nil then
        selection.secondaryGoalMode = NormalizeOptionalGoalMode(selection.secondaryGoalMode)
    end
    selection.secondaryEnabled = (selection.secondaryGoalMode ~= nil) and (selection.secondarySpecID ~= nil) or false

    if selection.primarySpecID ~= ACTIVE_SPEC_SENTINEL and selection.primarySpecID ~= LOOT_SPEC_SENTINEL then
        local primaryExists = false
        for _, opt in ipairs(options) do
            if opt.specID == selection.primarySpecID then primaryExists = true break end
        end
        if not primaryExists then selection.primarySpecID = currentSpecID or ACTIVE_SPEC_SENTINEL end
    end

    if selection.secondarySpecID and selection.secondarySpecID ~= ACTIVE_SPEC_SENTINEL and selection.secondarySpecID ~= LOOT_SPEC_SENTINEL then
        local exists = false
        for _, opt in ipairs(options) do
            if opt.specID == selection.secondarySpecID then exists = true break end
        end
        if not exists then selection.secondarySpecID = nil end
    end

    local resolvedPrimary = ResolveSelectedSpecID(selection.primarySpecID) or currentSpecID
    local resolvedSecondary = ResolveSelectedSpecID(selection.secondarySpecID)
    local primaryGoal = NormalizeOptionalGoalMode(selection.goalMode)
    local secondaryGoal = NormalizeOptionalGoalMode(selection.secondaryGoalMode)
    if selection.secondaryEnabled and resolvedPrimary and resolvedSecondary and resolvedPrimary == resolvedSecondary and primaryGoal == secondaryGoal then
        selection.secondarySpecID = nil
        selection.secondaryEnabled = false
        selection.activeView = "MAIN"
    end
    SaveSelection(selection)

    local primaryOptions = {
        {
            text = "Auto (Active Spec)",
            checked = (selection.primarySpecID == ACTIVE_SPEC_SENTINEL),
            func = function()
                selection.primarySpecID = ACTIVE_SPEC_SENTINEL
                selection.activeView = "MAIN"
                SaveSelection(selection)
                RefreshAspectDropdowns(context)
                RequestInventoryVerdictRefresh()
                if UpdateFrame then UpdateFrame() end
            end,
        },
        {
            text = "Loot Specialization",
            checked = (selection.primarySpecID == LOOT_SPEC_SENTINEL),
            func = function()
                selection.primarySpecID = LOOT_SPEC_SENTINEL
                selection.activeView = "MAIN"
                SaveSelection(selection)
                RefreshAspectDropdowns(context)
                RequestInventoryVerdictRefresh()
                if UpdateFrame then UpdateFrame() end
            end,
        },
    }
    for _, opt in ipairs(options) do
        primaryOptions[#primaryOptions + 1] = {
            text = opt.specName,
            checked = (selection.primarySpecID == opt.specID),
            func = function()
                selection.primarySpecID = opt.specID
                selection.activeView = "MAIN"
                SaveSelection(selection)
                RefreshAspectDropdowns(context)
                RequestInventoryVerdictRefresh()
                if UpdateFrame then UpdateFrame() end
            end,
        }
    end
    if PrimaryAspectDropdown.SetOptions then PrimaryAspectDropdown:SetOptions(primaryOptions) end

    -- Flow: Off-Spec Profile first (Disable lives there) → then Choose Off-Spec / auto active play.
    local hasOffProfile = selection.secondaryGoalMode ~= nil
    local hasOffSpec = selection.secondarySpecID ~= nil
    local secondaryOptions = {}
    if hasOffProfile then
        if not hasOffSpec then
            secondaryOptions[#secondaryOptions + 1] = {
                text = "Choose Off-Spec",
                checked = true,
                func = function() end,
            }
        end
        for _, opt in ipairs(options) do
            local resolvedMain = ResolveSelectedSpecID(selection.primarySpecID) or currentSpecID
            local duplicateMainBuild = opt.specID == resolvedMain
                and NormalizeOptionalGoalMode(selection.secondaryGoalMode) == NormalizeOptionalGoalMode(selection.goalMode)
            if not duplicateMainBuild then
                secondaryOptions[#secondaryOptions + 1] = {
                    text = opt.specName,
                    checked = (selection.secondarySpecID == opt.specID),
                    func = function()
                        selection.secondarySpecID = opt.specID
                        selection.secondaryEnabled = selection.secondaryGoalMode ~= nil
                        if selection.secondaryEnabled then
                            selection.activeView = "OFF"
                        end
                        SaveSelection(selection)
                        RefreshAspectDropdowns(context)
                        RequestInventoryVerdictRefresh()
                        if UpdateFrame then UpdateFrame() end
                    end,
                }
            end
        end
        if SecondaryAspectDropdown.SetEnabled then SecondaryAspectDropdown:SetEnabled(true) end
    else
        secondaryOptions[#secondaryOptions + 1] = {
            text = "Choose Off-Spec",
            checked = true,
            func = function() end,
        }
        if SecondaryAspectDropdown.SetEnabled then SecondaryAspectDropdown:SetEnabled(false) end
    end
    if SecondaryAspectDropdown.SetOptions then SecondaryAspectDropdown:SetOptions(secondaryOptions) end

    local mainViewActive = selection.activeView ~= "OFF"
    local offViewActive = selection.secondaryEnabled and selection.activeView == "OFF"
    if selection.primarySpecID == ACTIVE_SPEC_SENTINEL then
        if PrimaryAspectDropdown.SetText then PrimaryAspectDropdown:SetText(FormatViewDropdownText("Auto (Active Spec)", mainViewActive)) end
    elseif selection.primarySpecID == LOOT_SPEC_SENTINEL then
        if PrimaryAspectDropdown.SetText then PrimaryAspectDropdown:SetText(FormatViewDropdownText("Loot Specialization", mainViewActive)) end
    else
        local label = nil
        for _, opt in ipairs(options) do
            if opt.specID == selection.primarySpecID then label = opt.specName break end
        end
        if PrimaryAspectDropdown.SetText then PrimaryAspectDropdown:SetText(FormatViewDropdownText(label or "Select", mainViewActive)) end
    end

    if hasOffSpec then
        local label = nil
        for _, opt in ipairs(options) do
            if opt.specID == selection.secondarySpecID then label = opt.specName break end
        end
        if SecondaryAspectDropdown.SetText then SecondaryAspectDropdown:SetText(FormatViewDropdownText(label or "Select Off-Spec", offViewActive)) end
    else
        if SecondaryAspectDropdown.SetText then SecondaryAspectDropdown:SetText(FormatViewDropdownText("Choose Off-Spec", false)) end
    end

    if not selection.secondaryEnabled then
        selection.activeView = "MAIN"
        SaveSelection(selection)
    end

    ApplyToggleLabelColors(selection)
    if MainViewCheckbox then MainViewCheckbox:Hide() end
    if OffViewCheckbox then OffViewCheckbox:Hide() end

    LastDropdownClassFile = classFile
    LastDropdownSpecID = context and context.specID or nil
    LastDropdownSelectionSignature = BuildDropdownSelectionSignature(selection)
end

local function SetRow(frame, rowIndex, values, rowsStore, bars)
    local rows = rowsStore or frame.rows
    local row = rows and rows[rowIndex]
    if not row then return end
    for _, column in ipairs(frame.columns) do
        local cell = row[column.key]
        if cell then
            cell:SetText(values and values[column.key] or "")
            cell:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3])
            local columnTooltip = values and values.cellTooltips and values.cellTooltips[column.key] or nil
            if columnTooltip and columnTooltip.title and columnTooltip.body then
                cell:EnableMouse(true)
                cell:SetScript("OnEnter", function(self)
                    GameTooltip:SetOwner(self, "ANCHOR_TOP")
                    GameTooltip:SetText(columnTooltip.title, 1, 0.82, 0.0)
                    GameTooltip:AddLine(columnTooltip.body, 0.92, 0.82, 0.45, true)
                    GameTooltip:Show()
                end)
                cell:SetScript("OnLeave", function() GameTooltip:Hide() end)
            else
                cell:SetScript("OnEnter", nil)
                cell:SetScript("OnLeave", nil)
                cell:EnableMouse(false)
            end
            if column.key == "target" then
                if values and values.targetTooltipTitle and values.targetTooltipBody then
                    cell:EnableMouse(true)
                    cell:SetScript("OnEnter", function(self)
                        GameTooltip:SetOwner(self, "ANCHOR_TOP")
                        GameTooltip:SetText(values.targetTooltipTitle, 1, 0.82, 0.0)
                        GameTooltip:AddLine(values.targetTooltipBody, 0.92, 0.82, 0.45, true)
                        GameTooltip:Show()
                    end)
                    cell:SetScript("OnLeave", function() GameTooltip:Hide() end)
                elseif not columnTooltip then
                    cell:SetScript("OnEnter", nil)
                    cell:SetScript("OnLeave", nil)
                    cell:EnableMouse(false)
                end
            end
        end
    end
    if values and values.stat and values.stat ~= "" and not values.isTotal and row.stat then
        row.stat:SetText(" " .. tostring(values.stat))
    end
    if values and values.type and values.type ~= "" and not values.isTotal and row.type then
        row.type:SetText(" " .. tostring(values.type))
    end
    if values and values.isTotal then
        if row.stat then row.stat:SetTextColor(0.0, 1.0, 0.65) end
        if row.type then row.type:SetTextColor(0.0, 1.0, 0.65) end
    end
    if values and values.colors then
        for key, color in pairs(values.colors) do
            if row[key] and type(color) == "table" then
                row[key]:SetTextColor(color[1] or COLOR_SOFT_YELLOW[1], color[2] or COLOR_SOFT_YELLOW[2], color[3] or COLOR_SOFT_YELLOW[3])
            end
        end
    end
    if values and values.targetTooltipTitle and values.targetTooltipBody and row.target then
        row.target:SetTextColor(COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3])
    end
    if values and values.liveTrend and row.liveModifier then
        if values.liveTrend == "up" then row.liveModifier:SetTextColor(0.2, 1.0, 0.2)
        elseif values.liveTrend == "down" then row.liveModifier:SetTextColor(1.0, 0.25, 0.25)
        else row.liveModifier:SetTextColor(COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]) end
    end
    if ns.StatVerdictStatProgressPanel then
        ns.StatVerdictStatProgressPanel.SetProgress(
            frame,
            rowIndex,
            values and values.progress,
            values and values.currentValue,
            values and values.targetValue,
            bars,
            rows
        )
    end
end

local function EnsureIncompleteBuildText(frame)
    if frame.incompleteBuildText then return frame.incompleteBuildText end
    local text = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    text:SetJustifyH("LEFT")
    text:SetJustifyV("TOP")
    text:SetTextColor(0.92, 0.82, 0.45)
    frame.incompleteBuildText = text
    return text
end

local function EnsureMissingSnapshotButtons(frame)
    if frame.missingSnapshotOK and frame.missingSnapshotRespec then
        return frame.missingSnapshotOK, frame.missingSnapshotRespec
    end
    local ok = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    ok:SetSize(72, 22)
    ok:SetText("OK")
    ok:Hide()

    local respec = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    respec:SetSize(92, 22)
    respec:SetText("Respec")
    respec:Hide()

    frame.missingSnapshotOK = ok
    frame.missingSnapshotRespec = respec
    return ok, respec
end

local function SetStatProgressTableVisible(frame, visible)
    if frame.statProgressTableCard then
        if visible then frame.statProgressTableCard:Show() else frame.statProgressTableCard:Hide() end
    end
    if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.SetSummaryVisible then
        ns.StatVerdictStatProgressPanel.SetSummaryVisible(frame, visible)
    end
    for _, header in pairs(frame.headers or {}) do
        if visible then header:Show() else header:Hide() end
    end
    for _, row in ipairs(frame.rows or {}) do
        for _, cell in pairs(row) do
            if not visible then cell:Hide() end
        end
    end
    for _, bar in ipairs(frame.statProgressBars or {}) do
        if not visible then bar:Hide() end
    end
end

local function HideOffSpecEmptyHint(frame)
    if not frame then return end
    if frame.offSpecEmptyHint then
        frame.offSpecEmptyHint:Hide()
    end
    local function HideEmptyOn(card)
        if not card then return end
        if card.emptyTitle then card.emptyTitle:Hide() end
        if card.emptyBody then card.emptyBody:Hide() end
    end
    HideEmptyOn(frame.offStatProgressTableCard)
    HideEmptyOn(frame.svOffStatContentHost)
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("stats.offSpecHint")
    end
end

local function HideOffSpecTable(frame)
    if not frame then return end
    frame.svOffSpecVisible = false
    frame.svOffSpecUsedRows = 0
    frame.svOffSpecMissingMessage = false
    -- Keep the Off Spec card in the locked slot; StatProgressPanel fills empty-hint content.
    if frame.secondarySubtitle then
        frame.secondarySubtitle:SetText("Off Spec")
        frame.secondarySubtitle:SetTextColor(0.85, 0.85, 0.88)
        frame.secondarySubtitle:Show()
    end
    if frame.offAvgProgressText then
        frame.offAvgProgressText:SetText("")
        frame.offAvgProgressText:Hide()
    end
    for _, header in pairs(frame.offHeaders or {}) do
        header:Hide()
    end
    for _, row in ipairs(frame.offRows or {}) do
        for _, cell in pairs(row) do
            cell:SetText("")
            cell:Hide()
        end
    end
    for _, bar in ipairs(frame.offStatProgressBars or {}) do
        bar:Hide()
        bar.svHasProgress = false
    end
    if frame.offMissingSnapshotText then
        frame.offMissingSnapshotText:Hide()
    end
    if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end
    if frame.offMissingSnapshotRespec then frame.offMissingSnapshotRespec:Hide() end
    HideOffSpecEmptyHint(frame)
    if ns.UnregisterDevLayoutRegion then
        ns.UnregisterDevLayoutRegion("stats.offAverage")
        ns.UnregisterDevLayoutRegion("stats.offSpecHint")
    end
end

local function HideMissingSnapshotButtons(frame)
    if frame.missingSnapshotOK then frame.missingSnapshotOK:Hide() end
    if frame.missingSnapshotRespec then frame.missingSnapshotRespec:Hide() end
end

local function ShowIncompleteBuildMessage(frame, message)
    frame.svSuppressOffSpecHint = false
    frame.svMainSpecEmptyHint = true
    frame.svMainSpecMissingMessage = false
    HideOffSpecEmptyHint(frame)
    ApplyDynamicLayout(frame, 1)
    -- Keep both fixed screens visible; Main shows the empty/setup hint inside.
    SetStatProgressTableVisible(frame, true)
    HideMissingSnapshotButtons(frame)
    if frame.avgProgressText then
        frame.avgProgressText:SetText("")
        frame.avgProgressText:Hide()
    end
    if ns.StatVerdictBisProgressPanel then
        ns.StatVerdictBisProgressPanel.Refresh(frame, nil)
    end
    if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.RefreshSummary then
        ns.StatVerdictStatProgressPanel.RefreshSummary(frame, nil, nil)
    end
    -- Legacy floating text — hide; content lives inside the Main Spec screen.
    if frame.incompleteBuildText then
        frame.incompleteBuildText:SetText("")
        frame.incompleteBuildText:Hide()
    end
    HideOffSpecTable(frame)
end

local function FormatMissingSnapshotMessage(specName)
    specName = tostring(specName or "this spec")
    return string.format(
        "No virtual loadout for %s yet.\n\n"
            .. "StatVerdict needs a live capture of that build's gear and stats.\n"
            .. "Use Respec to switch to %s once — then this panel works normally.",
        specName,
        specName
    )
end

local function EnsureMainSpecMissingSnapshotUI(frame)
    local host = frame.svMainStatContentHost or frame.statProgressTableCard
    if not host then return nil end
    if frame.mainMissingSnapshotText then
        if frame.mainMissingSnapshotOK then frame.mainMissingSnapshotOK:Hide() end
        if frame.mainMissingSnapshotText.GetParent and frame.mainMissingSnapshotText:GetParent() ~= host then
            frame.mainMissingSnapshotText:SetParent(host)
        end
        if frame.mainMissingSnapshotRespec and frame.mainMissingSnapshotRespec.GetParent
            and frame.mainMissingSnapshotRespec:GetParent() ~= host then
            frame.mainMissingSnapshotRespec:SetParent(host)
        end
        return frame.mainMissingSnapshotText, frame.mainMissingSnapshotRespec
    end

    local text = host:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    text:SetJustifyH("LEFT")
    text:SetJustifyV("TOP")
    text:SetTextColor(0.92, 0.82, 0.45)
    if text.SetWordWrap then text:SetWordWrap(true) end
    if text.SetNonSpaceWrap then text:SetNonSpaceWrap(true) end
    text:Hide()
    frame.mainMissingSnapshotText = text

    local respec = CreateFrame("Button", nil, host, "UIPanelButtonTemplate")
    respec:SetSize(92, 22)
    respec:SetText("Respec")
    respec:Hide()
    frame.mainMissingSnapshotRespec = respec

    return text, respec
end

function ns.LayoutMainSpecMissingSnapshotUI(frame)
    if not frame or frame.svMainSpecMissingMessage ~= true then return end
    local card = frame.svMainStatContentHost or frame.statProgressTableCard
    local text = frame.mainMissingSnapshotText
    local respec = frame.mainMissingSnapshotRespec
    if not card or not text or not respec then return end
    if frame.mainMissingSnapshotOK then frame.mainMissingSnapshotOK:Hide() end

    -- Fit message + Respec inside the content host — never grow or shift the frame.
    local pad = 16
    local btnH = 22
    local gap = 12
    respec:ClearAllPoints()
    respec:SetPoint("BOTTOMLEFT", card, "BOTTOMLEFT", pad, pad)
    respec:Show()

    local width = math.max(160, (card:GetWidth() or 400) - (pad * 2))
    text:ClearAllPoints()
    text:SetPoint("TOPLEFT", card, "TOPLEFT", pad, -pad)
    text:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -pad, pad + btnH + gap)
    text:SetWidth(width)
    if text.SetWordWrap then text:SetWordWrap(true) end
    text:Show()
end

local function HideMainSpecMissingSnapshotUI(frame)
    if not frame then return end
    frame.svMainSpecMissingMessage = false
    frame.svMainSpecEmptyHint = false
    if frame.mainMissingSnapshotText then frame.mainMissingSnapshotText:Hide() end
    if frame.mainMissingSnapshotOK then frame.mainMissingSnapshotOK:Hide() end
    if frame.mainMissingSnapshotRespec then frame.mainMissingSnapshotRespec:Hide() end
    -- Legacy floating message path.
    if frame.incompleteBuildText then
        frame.incompleteBuildText:SetText("")
        frame.incompleteBuildText:Hide()
    end
    HideMissingSnapshotButtons(frame)
end

local function ShowMissingSnapshotMessage(frame, profile, context, profileKey)
    -- Keep Off Spec empty-hint available when OS is not configured.
    frame.svSuppressOffSpecHint = false
    frame.svMainSpecEmptyHint = false
    frame.svMainSpecMissingMessage = true

    -- Hide Main Spec table contents; keep the card for the message (same pattern as Off Spec).
    SetStatProgressTableVisible(frame, true)
    for _, header in pairs(frame.headers or {}) do
        header:Hide()
    end
    for _, row in ipairs(frame.rows or {}) do
        for _, cell in pairs(row) do
            if cell and cell.SetText then cell:SetText("") end
            if cell and cell.Hide then cell:Hide() end
        end
    end
    for _, bar in ipairs(frame.statProgressBars or {}) do
        bar:Hide()
        bar.svHasProgress = false
    end
    if frame.avgProgressText then
        frame.avgProgressText:SetText("")
        frame.avgProgressText:Hide()
    end
    if ns.StatVerdictBisProgressPanel then
        ns.StatVerdictBisProgressPanel.Refresh(frame, nil)
    end
    if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.RefreshSummary then
        ns.StatVerdictStatProgressPanel.RefreshSummary(frame, nil, nil)
    end

    -- Hide legacy floating incomplete text if present.
    if frame.incompleteBuildText then
        frame.incompleteBuildText:SetText("")
        frame.incompleteBuildText:Hide()
    end
    HideMissingSnapshotButtons(frame)

    if not frame.statProgressTableCard then
        -- Ensure card exists via a light layout pass.
        ApplyDynamicLayout(frame, 1)
    end

    local specName = (context and context.specName) or (profile and profile.specName) or "this spec"
    local text, respec = EnsureMainSpecMissingSnapshotUI(frame)
    if not text then
        -- Fallback: old floating message if the card is somehow missing.
        local legacy = EnsureIncompleteBuildText(frame)
        local anchor = frame.statProgressCard or frame
        legacy:ClearAllPoints()
        legacy:SetPoint("TOPLEFT", anchor, "TOPLEFT", 18, -88)
        legacy:SetWidth(math.max(180, (anchor:GetWidth() or 520) - 36))
        legacy:SetText(FormatMissingSnapshotMessage(specName))
        legacy:Show()
        return
    end

    text:SetText(FormatMissingSnapshotMessage(specName))
    respec:SetScript("OnClick", function()
        local success, reason = nil, nil
        if ns.SwitchToStatVerdictSnapshotSpec then
            success, reason = ns.SwitchToStatVerdictSnapshotSpec(profile)
        else
            success, reason = false, "Snapshot spec switch is not available."
        end
        if not success and DEFAULT_CHAT_FRAME then
            DEFAULT_CHAT_FRAME:AddMessage("|cffff8000StatVerdict:|r " .. tostring(reason or "Unable to switch specialization."))
        end
    end)
end

local function EnsureOffSpecMissingSnapshotUI(frame)
    local host = frame.svOffStatContentHost or frame.offStatProgressTableCard
    if not host then return nil end
    if frame.offMissingSnapshotText then
        if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end
        if frame.offMissingSnapshotText.GetParent and frame.offMissingSnapshotText:GetParent() ~= host then
            frame.offMissingSnapshotText:SetParent(host)
        end
        if frame.offMissingSnapshotRespec and frame.offMissingSnapshotRespec.GetParent
            and frame.offMissingSnapshotRespec:GetParent() ~= host then
            frame.offMissingSnapshotRespec:SetParent(host)
        end
        return frame.offMissingSnapshotText, frame.offMissingSnapshotRespec
    end

    local text = host:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    text:SetJustifyH("LEFT")
    text:SetJustifyV("TOP")
    text:SetTextColor(0.92, 0.82, 0.45)
    if text.SetWordWrap then text:SetWordWrap(true) end
    if text.SetNonSpaceWrap then text:SetNonSpaceWrap(true) end
    text:Hide()
    frame.offMissingSnapshotText = text

    local respec = CreateFrame("Button", nil, host, "UIPanelButtonTemplate")
    respec:SetSize(92, 22)
    respec:SetText("Respec")
    respec:Hide()
    frame.offMissingSnapshotRespec = respec

    return text, respec
end

-- Re-run after layout sizes the Off Spec content host so the message + button fit.
function ns.LayoutOffSpecMissingSnapshotUI(frame)
    if not frame or frame.svOffSpecMissingMessage ~= true then return end
    local card = frame.svOffStatContentHost or frame.offStatProgressTableCard
    local text = frame.offMissingSnapshotText
    local respec = frame.offMissingSnapshotRespec
    if not card or not text or not respec then return end
    if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end

    -- Fit message + Respec inside the content host — never grow or shift the frame.
    local pad = 16
    local btnH = 22
    local gap = 12
    respec:ClearAllPoints()
    respec:SetPoint("BOTTOMLEFT", card, "BOTTOMLEFT", pad, pad)
    respec:Show()

    local width = math.max(160, (card:GetWidth() or 400) - (pad * 2))
    text:ClearAllPoints()
    text:SetPoint("TOPLEFT", card, "TOPLEFT", pad, -pad)
    text:SetPoint("BOTTOMRIGHT", card, "BOTTOMRIGHT", -pad, pad + btnH + gap)
    text:SetWidth(width)
    if text.SetWordWrap then text:SetWordWrap(true) end
    text:Show()
end

local function ShowOffSpecMissingSnapshotMessage(frame, profile, context, profileKey)
    HideOffSpecEmptyHint(frame)
    frame.svSuppressOffSpecHint = false
    frame.svOffSpecVisible = true
    frame.svOffSpecMissingMessage = true
    frame.svOffSpecUsedRows = 0

    for _, header in pairs(frame.offHeaders or {}) do
        header:Hide()
    end
    for _, row in ipairs(frame.offRows or {}) do
        for _, cell in pairs(row) do
            cell:SetText("")
            cell:Hide()
        end
    end
    for _, bar in ipairs(frame.offStatProgressBars or {}) do
        bar:Hide()
        bar.svHasProgress = false
    end
    if frame.offAvgProgressText then
        frame.offAvgProgressText:SetText("")
        frame.offAvgProgressText:Hide()
    end

    if frame.secondarySubtitle then
        local titleSpec = (context and context.specName) or (profile and profile.specName) or "Unknown Spec"
        local titleClass = (context and context.className) or (profile and profile.className) or "Unknown Class"
        frame.secondarySubtitle:SetText(titleSpec .. " " .. titleClass)
        frame.secondarySubtitle:SetTextColor(GetClassColor(context))
        frame.secondarySubtitle:Show()
    end

    if not frame.offStatProgressTableCard then
        local parent = frame.statProgressCard or frame
        frame.offStatProgressTableCard = CreateFrame("Frame", nil, parent, "BackdropTemplate")
        frame.offStatProgressTableCard:SetBackdrop({
            bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
            edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
            tile = true,
            tileSize = 16,
            edgeSize = 12,
            insets = { left = 3, right = 3, top = 3, bottom = 3 },
        })
        frame.offStatProgressTableCard:SetBackdropColor(0.018, 0.022, 0.030, 0.72)
        frame.offStatProgressTableCard:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.72)
    end

    local card = frame.offStatProgressTableCard
    card:Show()

    local specName = (context and context.specName) or (profile and profile.specName) or "this spec"
    local text, respec = EnsureOffSpecMissingSnapshotUI(frame)
    if not text then return end

    text:SetText(FormatMissingSnapshotMessage(specName))
    respec:SetScript("OnClick", function()
        local success, reason = nil, nil
        if ns.SwitchToStatVerdictSnapshotSpec then
            success, reason = ns.SwitchToStatVerdictSnapshotSpec(profile)
        else
            success, reason = false, "Snapshot spec switch is not available."
        end
        if not success and DEFAULT_CHAT_FRAME then
            DEFAULT_CHAT_FRAME:AddMessage("|cffff8000StatVerdict:|r " .. tostring(reason or "Unable to switch specialization."))
        end
    end)
    ns.LayoutOffSpecMissingSnapshotUI(frame)
end

local function HideIncompleteBuildMessage(frame)
    HideMainSpecMissingSnapshotUI(frame)
    frame.svMainSpecEmptyHint = false
    frame.svSuppressOffSpecHint = false
    if frame.incompleteBuildText then
        frame.incompleteBuildText:SetText("")
        frame.incompleteBuildText:Hide()
    end
    if frame.avgProgressText then frame.avgProgressText:Show() end
end

local function BuildSpecDisplayTitle(context, profile)
    local specName = (context and context.specName) or (profile and profile.specName) or "Unknown Spec"
    local className = (context and context.className) or (profile and profile.className) or "Unknown Class"
    local heroName = nil

    if ns.GetSnapshotHeroTalentName then
        heroName = ns.GetSnapshotHeroTalentName(profile)
    end
    if (not heroName or heroName == "") and context then
        heroName = context.heroTalentName
    end

    local title = specName .. " " .. className
    if type(heroName) == "string" and heroName ~= "" then
        title = title .. " / " .. heroName
    end
    return title
end

local function FillOffSpecProgressTable(frame, selection, secondaryContext)
    if not frame then return end
    if not (selection and selection.secondaryEnabled and secondaryContext and secondaryContext.profile) then
        HideOffSpecTable(frame)
        ns.StatVerdictProgressCache = ns.StatVerdictProgressCache or {}
        ns.StatVerdictProgressCache.OFF = nil
        return
    end

    local offContext = secondaryContext
    local offProfile = offContext.profile
    local offTarget = GetAuditTarget(offContext, offProfile)
    local offRowsData = PrepareAuditRows(offTarget and offTarget.rows, offTarget)
    local offProfileID = ResolveAuditProfileID(offContext, offProfile)
    local offCustom = GetCustomBucket(offProfileID)

    if frame.secondarySubtitle then
        frame.secondarySubtitle:SetText(BuildSpecDisplayTitle(offContext, offProfile))
        frame.secondarySubtitle:SetTextColor(GetClassColor(offContext))
        frame.secondarySubtitle:Show()
        if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.FitOffSpecTitle then
            ns.StatVerdictStatProgressPanel.FitOffSpecTitle(frame)
        end
    end

    for index = 1, #(frame.offRows or {}) do
        SetRow(frame, index, nil, frame.offRows, frame.offStatProgressBars)
    end

    if ns.IsSnapshotMissingForProfile and ns.IsSnapshotMissingForProfile(offProfile) then
        ShowOffSpecMissingSnapshotMessage(frame, offProfile, offContext, offProfileID)
        return
    end

    if not offRowsData or #offRowsData == 0 then
        if frame.offMissingSnapshotText then frame.offMissingSnapshotText:Hide() end
        if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end
        if frame.offMissingSnapshotRespec then frame.offMissingSnapshotRespec:Hide() end
        frame.svOffSpecVisible = true
        frame.svOffSpecUsedRows = 1
        for _, header in pairs(frame.offHeaders or {}) do header:Show() end
        SetRow(frame, 1, {
            priority = "-",
            stat = "No Off Spec target data",
            current = "-",
            target = "-",
            progress = "-",
            liveModifier = "-",
        }, frame.offRows, frame.offStatProgressBars)
        return
    end

    if frame.offMissingSnapshotText then frame.offMissingSnapshotText:Hide() end
    if frame.offMissingSnapshotOK then frame.offMissingSnapshotOK:Hide() end
    if frame.offMissingSnapshotRespec then frame.offMissingSnapshotRespec:Hide() end
    frame.svOffSpecMissingMessage = false

    local maxDataRows = math.min(#offRowsData, LAYOUT_CONST.MAX_VISIBLE_ROWS - 1)
    local progressSum, progressCount = 0, 0

    local function renderOff()
        local inShapeshiftGrace = ns.IsAuditShapeshiftGraceActive and ns.IsAuditShapeshiftGraceActive()
        local lockLiveToBaseline = (ns.IsAuditDruidNonCasterForm and ns.IsAuditDruidNonCasterForm()) or inShapeshiftGrace
        local normalizedAuditLiveByKey = {}
        if not lockLiveToBaseline and ns.NormalizeStatAuditLiveWeights then
            normalizedAuditLiveByKey = ns.NormalizeStatAuditLiveWeights({
                rows = offRowsData,
                maxDataRows = maxDataRows,
                profile = offProfile,
                target = offTarget,
                customBucket = offCustom,
                getCurrentValue = ns.GetCurrentAuditStatValue,
                getRatingValue = ns.GetCurrentAuditRatingValue,
                isSecondaryKey = ns.IsAuditSecondaryStatKey,
            }) or {}
        end

        for index = 1, maxDataRows do
            local row = offRowsData[index]
            if offCustom and offCustom.targets and offCustom.targets[row.key] then
                row.target = SafeNumber(offCustom.targets[row.key]) or row.target
            end
            local current = ns.GetCurrentAuditStatValue and ns.GetCurrentAuditStatValue(row.key) or nil
            local targetValue = SafeNumber(row.target)
            if row.unboundedTarget then targetValue = nil end
            local isSecondary = ns.IsAuditSecondaryStatKey and ns.IsAuditSecondaryStatKey(row.key)
            local calcCurrent = current
            local calcTarget = targetValue
            if isSecondary and row.valueMode == "percent" then
                calcCurrent = ns.GetCurrentAuditRatingValue and ns.GetCurrentAuditRatingValue(row.key) or nil
                calcTarget = SafeNumber(row.targetRating) or SafeNumber(row.target)
                current = calcCurrent
                targetValue = calcTarget
            end
            local softCap = SafeNumber(row.softCap)
            if softCap == nil then
                softCap = ns.GetStatSoftCap and ns.GetStatSoftCap(offProfile, row.key) or nil
            end
            local baseModifier = SafeNumber(row.baseModifier)
            if baseModifier == nil then
                baseModifier = GetBaseModifier(offProfile, row.key)
            end
            local liveModifier = GetLiveModifier(offProfile, row.key, baseModifier, softCap, calcCurrent)
            local ratioToTarget = nil
            if calcCurrent and calcTarget and calcTarget > 0 then
                ratioToTarget = calcCurrent / calcTarget
            end
            if baseModifier and ratioToTarget and not lockLiveToBaseline then
                liveModifier = baseModifier * ns.StatAuditGetTieredLiveScale(row, ratioToTarget, calcCurrent, softCap)
            end
            if normalizedAuditLiveByKey[row.key] then
                liveModifier = normalizedAuditLiveByKey[row.key]
            end
            if ns.ApplyStatAuditPrimaryFloor then
                liveModifier = ns.ApplyStatAuditPrimaryFloor(row, baseModifier, liveModifier)
            end
            if row.unboundedTarget and baseModifier then
                liveModifier = baseModifier
            end
            local liveTrend = "same"
            if liveModifier and baseModifier then
                if liveModifier > baseModifier + 0.0005 then liveTrend = "up"
                elseif liveModifier < baseModifier - 0.0005 then liveTrend = "down" end
            end

            local progressText = "-"
            local progressColor = { COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3] }
            if calcCurrent and calcTarget and calcTarget > 0 then
                local ratio = calcCurrent / calcTarget
                if ratio < 0 then ratio = 0 end
                if ratio > 1 then ratio = 1 end
                progressSum = progressSum + ratio
                progressCount = progressCount + 1
                progressText = string.format("%.0f%%", ratio * 100)
                if ratio >= 1 then
                    progressColor = { 0.2, 1.0, 0.2 }
                elseif ratio >= 0.85 then
                    progressColor = { 1.0, 0.86, 0.2 }
                else
                    progressColor = { 1.0, 0.25, 0.25 }
                end
            elseif row.unboundedTarget then
                progressText = "^"
            end

            SetRow(frame, index, {
                priority = tostring(row.priority or index),
                stat = row.label or (ns.StatNames and ns.StatNames[row.key]) or row.key or "-",
                current = calcCurrent and string.format("%.0f", calcCurrent) or "-",
                target = calcTarget and string.format("%.0f", calcTarget) or (row.unboundedTarget and "^" or "-"),
                progress = progressText,
                liveModifier = liveModifier and string.format("%.2f", liveModifier) or "-",
                liveTrend = liveTrend,
                currentValue = current,
                targetValue = targetValue,
                colors = {
                    progress = progressColor,
                },
            }, frame.offRows, frame.offStatProgressBars)
        end
    end

    if ns.WithStatVerdictSnapshotProfile then
        ns.WithStatVerdictSnapshotProfile(offProfile, renderOff)
    else
        renderOff()
    end

    -- Restore Main Spec snapshot binding after Off Spec fill.
    if ns.SetStatVerdictSnapshotProfile then
        local mainProfile = nil
        if ns.GetTooltipEvaluationContexts then
            local primary = ns.GetTooltipEvaluationContexts()
            mainProfile = primary and primary.profile or nil
        end
        ns.SetStatVerdictSnapshotProfile(mainProfile)
    end

    frame.svOffSpecVisible = true
    frame.svOffSpecUsedRows = maxDataRows
    for _, header in pairs(frame.offHeaders or {}) do
        header:Show()
    end
    for index = 1, maxDataRows do
        local row = frame.offRows[index]
        if row then
            for _, cell in pairs(row) do
                cell:Show()
            end
        end
    end

    ns.StatVerdictProgressCache = ns.StatVerdictProgressCache or {}
    local avgPct = nil
    local avgLabel = "-"
    if progressCount > 0 then
        avgPct = (progressSum / progressCount) * 100
        avgLabel = string.format("%.1f%%", avgPct)
    end
    ns.StatVerdictProgressCache.OFF = {
        avgPct = avgPct,
        label = avgLabel,
    }

    if frame.offAvgProgressText then
        local avgColor = { 1.0, 0.86, 0.2 }
        if avgPct then
            if avgPct >= 95 then
                avgColor = { 0.2, 1.0, 0.2 }
            elseif avgPct >= 85 then
                avgColor = { 1.0, 0.86, 0.2 }
            else
                avgColor = { 1.0, 0.25, 0.25 }
            end
        end
        frame.offAvgProgressText:SetText("Average Progress: " .. avgLabel)
        frame.offAvgProgressText:SetTextColor(avgColor[1], avgColor[2], avgColor[3])
        frame.offAvgProgressText:Show()
    end
end

UpdateFrame = function()
    local frame = EnsureFrame()
    local context = ns.GetEvaluationContext and ns.GetEvaluationContext() or nil
    local dropdownSelection = GetSavedSelection()
    if ns.ProfileRepository and ns.ProfileRepository.RefreshProviderView then
        ns.ProfileRepository.RefreshProviderView(GetEffectiveGoalMode(dropdownSelection) or DEFAULT_MAX_LEVEL_GOAL)
    end
    local dropdownSignature = BuildDropdownSelectionSignature(dropdownSelection)
    if context and (
        LastDropdownClassFile ~= context.classFile
        or LastDropdownSpecID ~= context.specID
        or LastDropdownSelectionSignature ~= dropdownSignature
    ) then
        RefreshAspectDropdowns(context)
    end

    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end

    local selection = GetSavedSelection()
    RefreshGoalDropdown()
    if not selection.secondaryEnabled and selection.activeView == "OFF" then
        selection.activeView = "MAIN"
        SaveSelection(selection)
    end

    -- Dual tables: Main always shows primary; Off Spec table is filled separately below.
    -- activeView no longer swaps the Main Spec table.
    if primaryContext and primaryContext.profile then
        context = primaryContext
    elseif primaryContext then
        context = primaryContext
    end
    frame.currentProviderKey = context and context.providerKey or nil
    frame.currentClassFile = context and context.classFile or nil
    frame.currentActiveSpecID = context and context.specID or nil

    if MainViewCheckbox then MainViewCheckbox:Hide() end
    if OffViewCheckbox then OffViewCheckbox:Hide() end

    local titleContext = (primaryContext and primaryContext.profile) and primaryContext or context
    local profile = context and context.profile or nil
    if ns.SetStatVerdictSnapshotProfile then
        ns.SetStatVerdictSnapshotProfile(profile)
    end
    local incompleteReason = context and context.incompleteBuildReason or nil
    local target = GetAuditTarget(context, profile)
    local rows = PrepareAuditRows(target and target.rows, target)
    local profileID = ResolveAuditProfileID(context, profile)
    local customBucket = GetCustomBucket(profileID)
    frame.currentProfileID = profileID
    frame.currentRowsForEdit = rows
    local showProfileKeyDebug = ns.StatVerdictDevShowProfileKeyDebug and ns.StatVerdictDevShowProfileKeyDebug()
    local expectedProfileKey = BuildExpectedProfileDebugKey(context)
    if frame.expectedProfileKeyDebugText then
        if showProfileKeyDebug then
            frame.expectedProfileKeyDebugText:SetText("Expected key: " .. tostring(expectedProfileKey or "NO_EXPECTED_KEY"))
            frame.expectedProfileKeyDebugText:Show()
        else
            frame.expectedProfileKeyDebugText:SetText("")
            frame.expectedProfileKeyDebugText:Hide()
        end
    end
    if frame.profileKeyDebugText then
        if showProfileKeyDebug then
            local profileKey = tostring((profile and (profile.profileKey or profile.id)) or profileID or "NO_PROFILE_KEY")
            local matchText = (profileKey == expectedProfileKey) and "MATCH" or "MISMATCH"
            local invalid = profile and profile.invalidGeneratedContext and " | INVALID_CONTEXT" or ""
            local sourceText = ""
            if profile and type(profile.generatedContext) == "table" then
                sourceText = " | STATIC_GENERATED"
            end
            frame.profileKeyDebugText:SetText("Loaded key: " .. profileKey .. " | " .. matchText .. invalid .. sourceText)
            frame.profileKeyDebugText:Show()
        else
            frame.profileKeyDebugText:SetText("")
            frame.profileKeyDebugText:Hide()
        end
    end
    local specName = (titleContext and titleContext.specName) or (profile and profile.specName) or "Unknown Spec"
    local className = (titleContext and titleContext.className) or (profile and profile.className) or "Unknown Class"
    local subtitle = BuildSpecDisplayTitle(titleContext or context, profile)
    frame.subtitle:SetText(subtitle)
    frame.subtitle:SetTextColor(GetClassColor(context))
    if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.FitSpecTitle then
        ns.StatVerdictStatProgressPanel.FitSpecTitle(frame)
    end
    if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.SetModeBadge then
        ns.StatVerdictStatProgressPanel.SetModeBadge(frame, GetGoalDisplayLabel(context and context.goal))
    end
    if incompleteReason or not profile then
        ShowIncompleteBuildMessage(frame, incompleteReason or "Choose a profile and spec to build this view.")
        return
    end
    if ns.IsSnapshotMissingForProfile and ns.IsSnapshotMissingForProfile(profile) then
        ShowMissingSnapshotMessage(frame, profile, context, profileID)
        -- Still render Off Spec normally when it is configured (do not wipe it).
        FillOffSpecProgressTable(frame, selection, secondaryContext)
        local offRows = math.max(1, tonumber(frame.svOffSpecUsedRows) or 1)
        ApplyDynamicLayout(frame, math.max(1, tonumber(frame.svOffSpecUsedRows) or 1))
        if ns.LayoutMainSpecMissingSnapshotUI then
            ns.LayoutMainSpecMissingSnapshotUI(frame)
        end
        if frame.svOffSpecMissingMessage and ns.LayoutOffSpecMissingSnapshotUI then
            ns.LayoutOffSpecMissingSnapshotUI(frame)
        end
        return
    end
    if frame.dismissedMissingSnapshotKey == profileID then
        frame.dismissedMissingSnapshotKey = nil
    end
    HideIncompleteBuildMessage(frame)
    if frame.primaryLabel then
        frame.primaryLabel:SetTextColor(1.0, 1.0, 1.0)
    end
    if frame.secondaryLabel then
        if selection.secondaryEnabled then
            frame.secondaryLabel:SetTextColor(1.0, 1.0, 1.0)
        else
            frame.secondaryLabel:SetTextColor(0.55, 0.55, 0.55)
        end
    end
    local secondarySubtitleText = nil
    if frame.profileTagMain then
        frame.profileTagMain:SetText("")
        frame.profileTagMain:Hide()
    end
    if frame.profileLine then
        frame.profileLine:SetText("")
        frame.profileLine:Hide()
    end
    if DefaultButton then
        if HasCustomProfile(profileID) then DefaultButton:Enable() else DefaultButton:Disable() end
    end
    if frame.secondarySubtitle then
        -- Text is set later when Off Spec table is filled; hide until then.
        frame.secondarySubtitle:Hide()
    end
    for index = 1, #frame.rows do SetRow(frame, index, nil) end
    if #rows == 0 then
        HideOffSpecTable(frame)
        ApplyDynamicLayout(frame, 1)
        SetStatProgressTableVisible(frame, true)
        SetRow(frame, 1, { priority = "-", stat = "No profile target data", current = "-", target = "-", progress = "-", liveModifier = "-" })
        local panelProfile = profile
        if ns.GetActivePanelContext then
            local panelContext = ns.GetActivePanelContext()
            if panelContext and panelContext.profile then
                panelProfile = panelContext.profile
            end
        end
        if ns.StatVerdictBisProgressPanel then
            ns.StatVerdictBisProgressPanel.Refresh(frame, panelProfile)
        end
        if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.RefreshSummary then
            ns.StatVerdictStatProgressPanel.RefreshSummary(frame, panelProfile, target)
        end
        return
    end

    local totalCurrent, totalTarget = 0, 0
    local hasCurrent, hasTarget = false, false
    local baseSum, liveSum, baseCount, liveCount = 0, 0, 0, 0
    local progressSum, progressCount = 0, 0
    frame.currentRenderedData = {}

    local maxDataRows = math.min(#rows, LAYOUT_CONST.MAX_VISIBLE_ROWS - 1)
    local inShapeshiftGrace = ns.IsAuditShapeshiftGraceActive and ns.IsAuditShapeshiftGraceActive()
    local lockLiveToBaseline = (ns.IsAuditDruidNonCasterForm and ns.IsAuditDruidNonCasterForm()) or inShapeshiftGrace
    local normalizedAuditLiveByKey = {}
    if not lockLiveToBaseline and ns.NormalizeStatAuditLiveWeights then
        normalizedAuditLiveByKey = ns.NormalizeStatAuditLiveWeights({
            rows = rows,
            maxDataRows = maxDataRows,
            profile = profile,
            target = target,
            customBucket = customBucket,
            getCurrentValue = ns.GetCurrentAuditStatValue,
            getRatingValue = ns.GetCurrentAuditRatingValue,
            isSecondaryKey = ns.IsAuditSecondaryStatKey,
        }) or {}
    end
    for index = 1, maxDataRows do
        local row = rows[index]
        if customBucket and customBucket.targets and customBucket.targets[row.key] then
            row.target = SafeNumber(customBucket.targets[row.key]) or row.target
        end
        local current = ns.GetCurrentAuditStatValue and ns.GetCurrentAuditStatValue(row.key) or nil
        local targetValue = SafeNumber(row.target)
        if row.unboundedTarget then targetValue = nil end
        local isSecondary = ns.IsAuditSecondaryStatKey and ns.IsAuditSecondaryStatKey(row.key)
        local calcCurrent = current
        local calcTarget = targetValue
        if isSecondary and row.valueMode == "percent" then
            calcCurrent = ns.GetCurrentAuditRatingValue and ns.GetCurrentAuditRatingValue(row.key) or nil
            calcTarget = SafeNumber(row.targetRating) or SafeNumber(row.target)
            current = calcCurrent
            targetValue = calcTarget
        end
        local softCap = SafeNumber(row.softCap)
        if softCap == nil then
            softCap = ns.GetStatSoftCap and ns.GetStatSoftCap(profile, row.key) or nil
        end
        if customBucket and customBucket.softCaps then
            local customCap = SafeNumber(customBucket.softCaps[row.key])
            if customCap then softCap = customCap end
        end
        local diff = calcCurrent and calcTarget and (calcCurrent - calcTarget) or nil
        local baseModifier = SafeNumber(row.baseModifier)
        if baseModifier == nil then
            baseModifier = GetBaseModifier(profile, row.key)
        end
        if customBucket and customBucket.baseModifiers then
            local customBase = SafeNumber(customBucket.baseModifiers[row.key])
            if customBase then baseModifier = customBase end
        end
        local cacheKey = GetLiveCacheKey(profileID, row.key)
        local liveModifier = nil
        if lockLiveToBaseline and LastLiveModifiersByKey[cacheKey] then
            liveModifier = LastLiveModifiersByKey[cacheKey]
        else
            liveModifier = GetLiveModifier(profile, row.key, baseModifier, softCap, calcCurrent)
        end
        local rowTypeUpper = string.upper(tostring(row.type or ""))
        local ratioToTarget = nil
        if calcCurrent and calcTarget and calcTarget > 0 then
            ratioToTarget = calcCurrent / calcTarget
        end
        if baseModifier and ratioToTarget and not lockLiveToBaseline then
            liveModifier = baseModifier * ns.StatAuditGetTieredLiveScale(row, ratioToTarget, calcCurrent, softCap)
        end
        if normalizedAuditLiveByKey[row.key] then
            liveModifier = normalizedAuditLiveByKey[row.key]
        end
        if ns.ApplyStatAuditPrimaryFloor then
            liveModifier = ns.ApplyStatAuditPrimaryFloor(row, baseModifier, liveModifier)
        end
        if row.unboundedTarget and baseModifier then
            liveModifier = baseModifier
        end
        local decimals = (row.key == "STATVERDICT_MAIN_HAND_DPS" or row.key == "STATVERDICT_OFF_HAND_DPS") and 2 or 0
        local liveTrend = "same"
        if liveModifier and baseModifier then
            if liveModifier > baseModifier + 0.0005 then liveTrend = "up"
            elseif liveModifier < baseModifier - 0.0005 then liveTrend = "down" end
        end
        if calcCurrent then totalCurrent = totalCurrent + calcCurrent; hasCurrent = true end
        if calcTarget then totalTarget = totalTarget + calcTarget; hasTarget = true end
        if baseModifier then baseSum = baseSum + baseModifier; baseCount = baseCount + 1 end
        if liveModifier then liveSum = liveSum + liveModifier; liveCount = liveCount + 1 end
        if calcCurrent and calcTarget and calcTarget > 0 then
            local ratio = calcCurrent / calcTarget
            if ratio < 0 then ratio = 0 end
            if ratio > 1 then ratio = 1 end
            progressSum = progressSum + ratio
            progressCount = progressCount + 1
        end
        local diffColor = {COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]}
        if diff and calcTarget and calcTarget > 0 then
            local diffRatio = math.abs(diff) / calcTarget
            if diffRatio <= 0.05 then
                diffColor = {0.2, 1.0, 0.2}
            elseif diffRatio <= 0.15 then
                diffColor = {COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]}
            else
                diffColor = {1.0, 0.25, 0.25}
            end
        end
        local progressColor = {COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]}
        if calcCurrent and calcTarget and calcTarget > 0 then
            local pct = (calcCurrent / calcTarget) * 100
            if pct >= 100 then
                progressColor = {0.2, 1.0, 0.2}
            elseif pct >= 95 and pct < 100 then
                progressColor = {0.2, 1.0, 0.2}
            elseif pct >= 85 and pct < 95 then
                progressColor = {COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]}
            else
                progressColor = {1.0, 0.25, 0.25}
            end
        end
        local diffText = FormatDiff(diff)
        local progressText = FormatProgress(calcCurrent, calcTarget)
        local targetTooltipTitle, targetTooltipBody = nil, nil
        local targetText = FormatNumber(targetValue, decimals)
        if row.key == "STATVERDICT_ITEM_LEVEL" and targetValue and targetValue > 0 then
            targetTooltipTitle, targetTooltipBody = GetItemLevelAuditTargetTooltip(targetValue)
        elseif row.unboundedTarget then
            targetTooltipTitle = "No Fixed Primary Target"
            targetTooltipBody = "Higher primary stat is always beneficial. This row is excluded from Average Progress."
        end
        local displayCurrent = ""
        local displayTarget = ""
        local displaySoftCap = FormatNumber(softCap, decimals)
        local displayDiff = diffText
        local displayProgress = progressText
        local cellTooltips = nil
        if row.unboundedTarget then
            displayTarget = "^"
            displayDiff = "-"
            displayProgress = "-"
            if cellTooltips then
                cellTooltips.target = nil
                cellTooltips.diff = nil
            end
        end
        SetRow(frame, index, {
            priority = tostring(row.priority or index),
            stat = row.label or (ns.StatNames and ns.StatNames[row.key]) or row.key or "-",
            type = row.type or "-",
            current = displayCurrent,
            target = displayTarget,
            softCap = displaySoftCap,
            diff = displayDiff,
            progress = displayProgress,
            baseModifier = baseModifier and string.format("%.2f", baseModifier) or "-",
            liveModifier = liveModifier and string.format("%.2f", liveModifier) or "-",
            liveTrend = liveTrend,
            targetTooltipTitle = targetTooltipTitle,
            targetTooltipBody = targetTooltipBody,
            currentValue = current,
            targetValue = targetValue,
            cellTooltips = cellTooltips,
            colors = {
                current = {COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]},
                target = row.unboundedTarget and {COLOR_TITLE_GOLD[1], COLOR_TITLE_GOLD[2], COLOR_TITLE_GOLD[3]} or {0.2, 1.0, 0.2},
                diff = diffColor,
                progress = progressColor,
                baseModifier = {COLOR_SOFT_YELLOW[1], COLOR_SOFT_YELLOW[2], COLOR_SOFT_YELLOW[3]},
            },
        })
        frame.currentRenderedData[#frame.currentRenderedData + 1] = {
            rowIndex = index,
            key = row.key,
            targetValue = targetValue,
            currentValue = current,
            softCapValue = softCap,
            baseValue = baseModifier,
            unboundedTarget = row.unboundedTarget and true or false,
        }
        if frame.editMode and frame.rows[index] then
            frame.rows[index].target:SetText(row.unboundedTarget and "^" or "")
            frame.rows[index].softCap:SetText("")
            frame.rows[index].baseModifier:SetText("")
        end
        if liveModifier and not lockLiveToBaseline then
            LastLiveModifiersByKey[cacheKey] = liveModifier
        end
    end

    SetStatProgressTableVisible(frame, true)
    local panelProfile = profile
    if ns.GetActivePanelContext then
        local panelContext = ns.GetActivePanelContext()
        if panelContext and panelContext.profile then
            panelProfile = panelContext.profile
        end
    end
    if ns.StatVerdictBisProgressPanel then
        ns.StatVerdictBisProgressPanel.Refresh(frame, panelProfile)
    end
    if ns.StatVerdictStatProgressPanel and ns.StatVerdictStatProgressPanel.RefreshSummary then
        ns.StatVerdictStatProgressPanel.RefreshSummary(frame, panelProfile, target)
    end
    if frame.avgProgressText then
        local avgProgressText = "-"
        local avgColor = {1.0, 0.86, 0.2}
        local avgPct = nil
        if progressCount > 0 then
            avgPct = (progressSum / progressCount) * 100
            avgProgressText = string.format("%.1f%%", avgPct)
        end
        if avgPct then
            if avgPct >= 100 then
                avgColor = {0.2, 1.0, 0.2}
            elseif avgPct >= 95 and avgPct < 100 then
                avgColor = {0.2, 1.0, 0.2}
            elseif avgPct >= 85 and avgPct < 95 then
                avgColor = {1.0, 0.86, 0.2}
            else
                avgColor = {1.0, 0.25, 0.25}
            end
        end
        frame.avgProgressText:SetText("Average Progress: " .. avgProgressText)
        frame.avgProgressText:SetTextColor(avgColor[1], avgColor[2], avgColor[3])
        ns.StatVerdictProgressCache = ns.StatVerdictProgressCache or {}
        ns.StatVerdictProgressCache.MAIN = {
            avgPct = avgPct,
            label = avgProgressText,
        }
    end

    -- Second identical table for Off Spec (hidden entirely when none selected).
    FillOffSpecProgressTable(frame, selection, secondaryContext)

    ApplyDynamicLayout(frame, maxDataRows)
    if frame.svMainSpecMissingMessage and ns.LayoutMainSpecMissingSnapshotUI then
        ns.LayoutMainSpecMissingSnapshotUI(frame)
    end
    if frame.svOffSpecMissingMessage and ns.LayoutOffSpecMissingSnapshotUI then
        ns.LayoutOffSpecMissingSnapshotUI(frame)
    end
	if frame.RefreshInlineEditors then
	    frame.RefreshInlineEditors()
	end
end

function ns.RequestStatAuditRefresh()
    if UpdateFrame and AuditFrame and AuditFrame:IsShown() then
        UpdateFrame()
    end
    RequestInventoryVerdictRefresh()
end

function ns.CloseStatAudit()
    local frame = AuditFrame or EnsureFrame()
    if not frame then return end
    frame.svWantShown = false
    if frame:IsShown() then
        frame:Hide()
    else
        SaveWindowPosition(frame)
    end
end

function ns.OpenStatAudit()
    local frame = EnsureFrame()
    frame.svWantShown = true
    ApplyUserWindowPosition(frame)
    UpdateFrame()
    frame:Show()
    FitWindowOnScreen(frame, false)
end

function ns.ToggleStatAudit()
    local frame = EnsureFrame()
    if frame:IsShown() then
        ns.CloseStatAudit()
        return
    end
    ns.OpenStatAudit()
end

-- Global for keybind / compartment TOC hooks.
function StatVerdict_ToggleStatAudit()
    if ns.ToggleStatAudit then
        ns.ToggleStatAudit()
    end
end

BINDING_HEADER_STATVERDICT = "StatVerdict"
BINDING_NAME_STATVERDICT_TOGGLE = "Toggle StatVerdict window"

local function ApplyLayoutController()
    if not LayoutControllerFrame or not AuditFrame then return end
    AuditFrame.gridLayout = AuditFrame.gridLayout or {}
    NormalizeLayoutFields(LayoutControllerFrame.layout or AuditFrame.gridLayout, AuditFrame.gridLayout)
    SaveLayout(AuditFrame.gridLayout)
    if UpdateFrame and AuditFrame:IsShown() then
        UpdateFrame()
    elseif AuditFrame then
        ApplyDynamicLayout(AuditFrame, 1)
    end
end

local function CreateStepControl(parent, opts)
    local row = CreateFrame("Frame", nil, parent)
    row:SetSize(270, 24)
    row:SetPoint("TOPLEFT", parent, "TOPLEFT", opts.x or 10, opts.y)

    if opts.section then
        row.label = row:CreateFontString(nil, "OVERLAY", "GameFontNormal")
        row.label:SetPoint("LEFT", row, "LEFT", 0, 0)
        row.label:SetText(opts.section)
        row.label:SetTextColor(1.0, 0.82, 0.0)
        row.Refresh = function() end
        return row
    end

    row.label = row:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    row.label:SetPoint("LEFT", row, "LEFT", 0, 0)
    row.label:SetText(opts.label)

    row.value = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.value:SetPoint("LEFT", row, "LEFT", 146, 0)
    row.value:SetWidth(64)
    row.value:SetJustifyH("RIGHT")

    local btnMinus = CreateFrame("Button", nil, row, "UIPanelButtonTemplate")
    btnMinus:SetSize(24, 20)
    btnMinus:SetPoint("RIGHT", row, "RIGHT", -30, 0)
    btnMinus:SetText("-")

    local btnPlus = CreateFrame("Button", nil, row, "UIPanelButtonTemplate")
    btnPlus:SetSize(24, 20)
    btnPlus:SetPoint("RIGHT", row, "RIGHT", 0, 0)
    btnPlus:SetText("+")

    local function refreshValueText()
        local v = parent.layout[opts.key]
        if opts.decimals and opts.decimals > 0 then
            row.value:SetText(string.format("%." .. opts.decimals .. "f", v))
        else
            row.value:SetText(tostring(math.floor(v + 0.5)))
        end
    end

    local function step(delta)
        local curr = tonumber(parent.layout[opts.key]) or opts.default
        local nextValue = Clamp(curr + (delta * opts.step), opts.min, opts.max)
        parent.layout[opts.key] = nextValue
        refreshValueText()
        ApplyLayoutController()
    end

    btnMinus:SetScript("OnClick", function() step(-1) end)
    btnPlus:SetScript("OnClick", function() step(1) end)

    row.Refresh = refreshValueText
    refreshValueText()
    return row
end

local function RefreshLayoutController()
    if not LayoutControllerFrame or not AuditFrame then return end
    local live = AuditFrame.gridLayout or LoadSavedLayout()
    LayoutControllerFrame.layout = {
        x = live.x or LAYOUT_CONST.GRID_LEFT_X,
        y = live.y or LAYOUT_CONST.GRID_TOP_Y,
        width = live.width or LAYOUT_CONST.GRID_WIDTH,
        extraHeight = live.extraHeight or LAYOUT_CONST.GRID_CARD_EXTRA_BOTTOM_DEFAULT,
        frameWidth = live.frameWidth or LAYOUT_CONST.FRAME_WIDTH_DEFAULT,
        frameExtraHeight = live.frameExtraHeight or LAYOUT_CONST.FRAME_EXTRA_HEIGHT_DEFAULT,
        titleX = live.titleX or LAYOUT_CONST.TITLE_X_DEFAULT,
        titleY = live.titleY or LAYOUT_CONST.TITLE_Y_DEFAULT,
        titleWidth = live.titleWidth or LAYOUT_CONST.TITLE_WIDTH_DEFAULT,
        titleFontSize = live.titleFontSize or LAYOUT_CONST.TITLE_FONT_SIZE_DEFAULT,
        aspectLabelFontSize = live.aspectLabelFontSize or LAYOUT_CONST.ASPECT_LABEL_FONT_SIZE_DEFAULT,
        dropdownWidth = live.dropdownWidth or live.primaryDropdownWidth or live.goalDropdownWidth or live.secondaryDropdownWidth or LAYOUT_CONST.DROPDOWN_WIDTH_DEFAULT,
        dropdownScale = live.dropdownScale or live.primaryDropdownScale or live.goalDropdownScale or live.secondaryDropdownScale or LAYOUT_CONST.DROPDOWN_SCALE_DEFAULT,
        goalLabelX = live.goalLabelX or LAYOUT_CONST.GOAL_LABEL_X_DEFAULT,
        goalLabelY = live.goalLabelY or LAYOUT_CONST.GOAL_LABEL_Y_DEFAULT,
        goalDropdownX = live.goalDropdownX or LAYOUT_CONST.GOAL_DROPDOWN_X_DEFAULT,
        goalDropdownY = live.goalDropdownY or LAYOUT_CONST.GOAL_DROPDOWN_Y_DEFAULT,
        primaryLabelX = live.primaryLabelX or LAYOUT_CONST.PRIMARY_LABEL_X_DEFAULT,
        primaryLabelY = live.primaryLabelY or LAYOUT_CONST.PRIMARY_LABEL_Y_DEFAULT,
        primaryDropdownX = live.primaryDropdownX or LAYOUT_CONST.PRIMARY_DROPDOWN_X_DEFAULT,
        primaryDropdownY = live.primaryDropdownY or LAYOUT_CONST.PRIMARY_DROPDOWN_Y_DEFAULT,
        secondaryLabelX = live.secondaryLabelX or LAYOUT_CONST.SECONDARY_LABEL_X_DEFAULT,
        secondaryLabelY = live.secondaryLabelY or LAYOUT_CONST.SECONDARY_LABEL_Y_DEFAULT,
        secondaryDropdownX = live.secondaryDropdownX or LAYOUT_CONST.SECONDARY_DROPDOWN_X_DEFAULT,
        secondaryDropdownY = live.secondaryDropdownY or LAYOUT_CONST.SECONDARY_DROPDOWN_Y_DEFAULT,
        secondaryTitleX = live.secondaryTitleX or LAYOUT_CONST.SECONDARY_TITLE_X_DEFAULT,
        secondaryTitleY = live.secondaryTitleY or LAYOUT_CONST.SECONDARY_TITLE_Y_DEFAULT,
        offspecToggleX = live.offspecToggleX or LAYOUT_CONST.OFFSPEC_TOGGLE_X_DEFAULT,
        offspecToggleY = live.offspecToggleY or LAYOUT_CONST.OFFSPEC_TOGGLE_Y_DEFAULT,
        autoHeroToggleX = live.autoHeroToggleX or LAYOUT_CONST.AUTO_HERO_TOGGLE_X_DEFAULT,
        autoHeroToggleY = live.autoHeroToggleY or LAYOUT_CONST.AUTO_HERO_TOGGLE_Y_DEFAULT,
        offspecToggleFontSize = live.offspecToggleFontSize or LAYOUT_CONST.OFFSPEC_TOGGLE_FONT_SIZE_DEFAULT,
        borderAlpha = live.borderAlpha or LAYOUT_CONST.BORDER_ALPHA_DEFAULT,
        avgProgressX = live.avgProgressX or LAYOUT_CONST.AVG_PROGRESS_X_DEFAULT,
        avgProgressY = live.avgProgressY or LAYOUT_CONST.AVG_PROGRESS_Y_DEFAULT,
        avgProgressFontSize = live.avgProgressFontSize or 12,
        sampleLineX = live.sampleLineX or LAYOUT_CONST.SAMPLE_LINE_X_DEFAULT,
        sampleLineY = live.sampleLineY or LAYOUT_CONST.SAMPLE_LINE_Y_DEFAULT,
        sampleLineFontSize = live.sampleLineFontSize or LAYOUT_CONST.SAMPLE_LINE_FONT_SIZE_DEFAULT,
        editBtnX = live.editBtnX or LAYOUT_CONST.BUTTON_EDIT_X_DEFAULT,
        editBtnY = live.editBtnY or LAYOUT_CONST.BUTTON_EDIT_Y_DEFAULT,
        defaultBtnX = live.defaultBtnX or LAYOUT_CONST.BUTTON_DEFAULT_X_DEFAULT,
        defaultBtnY = live.defaultBtnY or LAYOUT_CONST.BUTTON_DEFAULT_Y_DEFAULT,
        buttonWidth = live.buttonWidth or LAYOUT_CONST.BUTTON_WIDTH_DEFAULT,
        buttonHeight = live.buttonHeight or LAYOUT_CONST.BUTTON_HEIGHT_DEFAULT,
    }
    for _, control in ipairs(LayoutControllerFrame.controls or {}) do
        if control.Refresh then control:Refresh() end
    end
end

local function EnsureLayoutController()
    if LayoutControllerFrame then return LayoutControllerFrame end
    local panel = CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictLayoutControllerFrame") or "StatVerdictLayoutControllerFrame", UIParent, "BasicFrameTemplateWithInset")
    panel:SetSize(590, 1000)
    panel:SetPoint("CENTER", UIParent, "CENTER", 390, 0)
    panel:SetMovable(true)
    panel:EnableMouse(true)
    panel:RegisterForDrag("LeftButton")
    panel:SetScript("OnDragStart", panel.StartMoving)
    panel:SetScript("OnDragStop", panel.StopMovingOrSizing)
    panel:Hide()

    panel.title = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    panel.title:SetPoint("TOP", panel, "TOP", 0, -8)
    panel.title:SetText("SV Layout Controller")
    panel.layout = LoadSavedLayout()
    panel.controls = {}

    for _, def in ipairs(LAYOUT_CONTROL_DEFS) do
        panel.controls[#panel.controls + 1] = CreateStepControl(panel, def)
    end

    panel.note = panel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    panel.note:SetPoint("TOPLEFT", panel, "TOPLEFT", 12, -966)
    panel.note:SetWidth(560)
    panel.note:SetJustifyH("LEFT")
    panel.note:SetText("/sva preview\n/svlayout toggle")

    LayoutControllerFrame = panel
    return panel
end

function ns.ToggleStatAuditLayoutController()
    local panel = EnsureLayoutController()
    EnsureFrame()
    if panel:IsShown() then
        panel:Hide()
        if UpdateFrame then UpdateFrame() end
        return
    end
    RefreshLayoutController()
    panel:Show()
    if UpdateFrame then UpdateFrame() end
end

function ns.DebugSortedClassFiles()
    local names, seen = {}, {}
    local provider = ns.ProfileProviders and ns.ProfileProviders.Generated
    if type(provider) == "table" then
        for classFile, _ in pairs(provider) do
            if type(classFile) == "string" and not seen[classFile] then
                seen[classFile] = true
                names[#names + 1] = classFile
            end
        end
    end
    table.sort(names)
    return names
end

function ns.DebugSpecOptionsForClass(classFile)
    local out = {}
    for _, opt in ipairs(GetSpecOptionsForClass(classFile)) do
        local key = ns.GetStatVerdictSpecKeyBySpecID and ns.GetStatVerdictSpecKeyBySpecID(opt.specID) or nil
        out[#out + 1] = { specID = opt.specID, specName = opt.specName, specKey = key }
    end
    table.sort(out, function(a, b) return tostring(a.specName or "") < tostring(b.specName or "") end)
    return out
end

function ns.DebugHeroOptionsForSpec(classFile, specID, specKey)
    local staticHeroOptions = ns.GetStatVerdictHeroOptionsBySpecID and ns.GetStatVerdictHeroOptionsBySpecID(specID) or nil
    if type(specID) == "number" and type(staticHeroOptions) == "table" then
        local out = {}
        for _, hero in ipairs(staticHeroOptions) do
            out[#out + 1] = tostring(hero)
        end
        return out
    end

    return GetHeroOptionsForSpec("Generated", classFile, specID)
end

function ns.RefreshDebugOverrideFrame(frame)
    frame = frame or DebugOverrideFrame
    if not frame then return end
    local state = GetDebugOverrideState()
    local classFile = state.classFile
    local specID = tonumber(state.specID)
    local specKey = state.specKey
    state.heroTalentName = nil

    frame.enable:SetChecked(state.enabled and true or false)

    UIDropDownMenu_Initialize(frame.classDrop, function(_, level)
        local info = UIDropDownMenu_CreateInfo()
        for _, cf in ipairs(ns.DebugSortedClassFiles()) do
            info.text = (LOCALIZED_CLASS_NAMES_MALE and LOCALIZED_CLASS_NAMES_MALE[cf]) or cf
            info.func = function()
                state.classFile = cf
                local opts = ns.DebugSpecOptionsForClass(cf)
                state.specID = (opts[1] and opts[1].specID) or nil
                state.specKey = (opts[1] and opts[1].specKey) or nil
                SaveDebugOverrideState(state)
                ns.RefreshDebugOverrideFrame(frame)
                if UpdateFrame and AuditFrame and AuditFrame:IsShown() then UpdateFrame() end
            end
            info.checked = (classFile == cf)
            UIDropDownMenu_AddButton(info, level)
        end
    end)
    UIDropDownMenu_SetText(frame.classDrop, ((LOCALIZED_CLASS_NAMES_MALE and LOCALIZED_CLASS_NAMES_MALE[classFile]) or classFile or "Select"))

    UIDropDownMenu_Initialize(frame.specDrop, function(_, level)
        local info = UIDropDownMenu_CreateInfo()
        for _, opt in ipairs(ns.DebugSpecOptionsForClass(classFile)) do
            info.text = opt.specName
            info.func = function()
                state.specID = opt.specID
                state.specKey = opt.specKey
                SaveDebugOverrideState(state)
                ns.RefreshDebugOverrideFrame(frame)
                if UpdateFrame and AuditFrame and AuditFrame:IsShown() then UpdateFrame() end
            end
            info.checked = (specID == opt.specID and (state.specKey == opt.specKey or (not state.specKey and not opt.specKey)))
            UIDropDownMenu_AddButton(info, level)
        end
    end)
    local specText = "Select"
    for _, opt in ipairs(ns.DebugSpecOptionsForClass(classFile)) do
        if specID == opt.specID and (state.specKey == opt.specKey or (not state.specKey and not opt.specKey)) then
            specText = opt.specName
            break
        end
    end
    UIDropDownMenu_SetText(frame.specDrop, specText)

    if frame.heroDrop then
        UIDropDownMenu_SetText(frame.heroDrop, "")
        UIDropDownMenu_DisableDropDown(frame.heroDrop)
        frame.heroDrop:Hide()
    end
end

ns.EventFrame = ns.EventFrame or CreateFrame("Frame")
ns.EventFrame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
ns.EventFrame:RegisterEvent("PLAYER_SPECIALIZATION_CHANGED")
ns.EventFrame:RegisterEvent("PLAYER_LOOT_SPEC_UPDATED")
ns.EventFrame:RegisterEvent("PLAYER_ENTERING_WORLD")
ns.EventFrame:RegisterEvent("UPDATE_SHAPESHIFT_FORM")
ns.EventFrame:RegisterEvent("UNIT_STATS")
ns.EventFrame:RegisterEvent("COMBAT_RATING_UPDATE")
ns.EventFrame:SetScript("OnEvent", function(_, event, unit)
    if event == "UNIT_STATS" and unit ~= "player" then return end
    if event == "PLAYER_ENTERING_WORLD" or event == "PLAYER_SPECIALIZATION_CHANGED" or event == "PLAYER_LOOT_SPEC_UPDATED" then
        if RequestInventoryVerdictRefresh then
            RequestInventoryVerdictRefresh()
        end
    end
    if event == "UPDATE_SHAPESHIFT_FORM" then
        if ns.MarkAuditShapeshiftChanged then
            ns.MarkAuditShapeshiftChanged()
        end
    end
    if AuditFrame and AuditFrame:IsShown() and UpdateFrame then UpdateFrame() end
end)

SLASH_STATVERDICTAUDIT1 = "/sva"
SlashCmdList.STATVERDICTAUDIT = function() ns.ToggleStatAudit() end

-- Legacy /svlayout controller retired (Dashboard + LayoutOffsets own placement).
SLASH_STATVERDICTLAYOUT1 = "/svlayout"
SlashCmdList.STATVERDICTLAYOUT = function()
    if ns.STATVERDICT_DEV_TOOLS then
        print("|cffff8000StatVerdict:|r /svlayout is retired. Use /svmove for AdvDev layout editing.")
    end
end


















