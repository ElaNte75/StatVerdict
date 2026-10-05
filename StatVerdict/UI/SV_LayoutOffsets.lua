local addonName, ns = ...

-- Public layout offsets: seed tuned defaults and expose read/write helpers.
-- The layout every new install starts from: the owner's tuned window (taller, wider, buttons placed). Since layout seed 2.
-- Do not edit by hand; it was copied from the owner's saved layout (without the lock flags of the old layout dev tools).
local DEFAULT_DASHBOARD_OFFSETS = {
["bis.card.pad"] = {
["bottom"] = 5,
["left"] = 0,
["right"] = 0,
["top"] = 5,
},
["bis.title"] = {
["x"] = -10,
["y"] = 0,
},
["bis.title.height"] = {
["height"] = -4,
},
["bis.title.pad"] = {
["bottom"] = 0,
["left"] = 5,
["right"] = 5,
["top"] = 0,
},
["bis.title.width"] = {
["width"] = 163,
},
["bisTrinkets.content"] = {
["x"] = 0,
["y"] = 10,
},
["bisTrinkets.content.pad"] = {
["bottom"] = 0,
["left"] = 0,
["right"] = 0,
["top"] = 0,
},
["dashboard.width"] = {
["width"] = -16,
},
["manual.card.pad"] = {
["bottom"] = 5,
["left"] = 0,
["right"] = 0,
["top"] = 5,
},
["options.card.pad"] = {
["bottom"] = 5,
["left"] = 0,
["right"] = 0,
["top"] = 5,
},
["right.card"] = {
["x"] = -5,
["y"] = 0,
},
["screen.1"] = {
["x"] = 2,
["y"] = 40,
},
["screen.1.msStats"] = {
["x"] = 1,
["y"] = -3,
},
["screen.1.msStats.average"] = {
["x"] = 18,
["y"] = -4,
},
["screen.1.msStats.average.height"] = {
["height"] = 0,
},
["screen.1.msStats.average.width"] = {
["width"] = 125,
},
["screen.1.msStats.width"] = {
["width"] = -2,
},
["screen.1.width"] = {
["width"] = -127,
},
["screen.2"] = {
["x"] = 2,
["y"] = 41,
},
["screen.2.box.1"] = {
["x"] = 1,
["y"] = -1,
},
["screen.2.box.1.height"] = {
["height"] = -17,
},
["screen.2.box.1.width"] = {
["width"] = -2,
},
["screen.2.osStats.average"] = {
["x"] = 18,
["y"] = -5,
},
["screen.2.osStats.average.width"] = {
["width"] = 125,
},
["screen.2.width"] = {
["width"] = -127,
},
["setup.bisButton"] = {
["_abs"] = false,
["x"] = -2,
["y"] = 68,
},
["setup.bisButton.width"] = {
["width"] = -32,
},
["setup.buildDropdown"] = {
["_abs"] = false,
["x"] = 0,
["y"] = 17,
},
["setup.buildDropdown.width"] = {
["width"] = -53,
},
["setup.card"] = {
["x"] = 0,
["y"] = 0,
},
["setup.height"] = {
["height"] = 50,
},
["setup.mainDropdown"] = {
["_abs"] = false,
["x"] = 0,
["y"] = 38,
},
["setup.mainDropdown.width"] = {
["width"] = -53,
},
["setup.mainTitle"] = {
["_abs"] = false,
["x"] = 2,
["y"] = 0,
},
["setup.manualButton"] = {
["_abs"] = false,
["x"] = -2,
["y"] = 91,
},
["setup.manualButton.width"] = {
["width"] = -32,
},
["setup.offDropdown"] = {
["_abs"] = false,
["x"] = 0,
["y"] = 69,
},
["setup.offDropdown.width"] = {
["width"] = -52,
},
["setup.offGoalDropdown"] = {
["_abs"] = false,
["x"] = 0,
["y"] = 48,
},
["setup.offGoalDropdown.width"] = {
["width"] = -52,
},
["setup.offTitle"] = {
["_abs"] = false,
["x"] = 2,
["y"] = 53,
},
["setup.optionsButton"] = {
["_abs"] = false,
["x"] = -2,
["y"] = 93,
},
["setup.optionsButton.width"] = {
["width"] = -32,
},
["setup.optionsTitle"] = {
["_abs"] = false,
["x"] = 2,
["y"] = 90,
},
["setup.pad"] = {
["bottom"] = 5,
["left"] = 5,
["right"] = 0,
["top"] = 5,
},
["setup.summaryButton"] = {
["_abs"] = false,
["x"] = -2,
["y"] = 153,
},
["setup.summaryButton.width"] = {
["width"] = -32,
},
["setup.trinketsButton"] = {
["_abs"] = false,
["x"] = -2,
["y"] = 67,
},
["setup.trinketsButton.width"] = {
["width"] = -32,
},
["setup.width"] = {
["width"] = -61,
},
["stats.average"] = {
["x"] = 110,
["y"] = 201,
},
["stats.average.width"] = {
["width"] = -3,
},
["stats.card"] = {
["x"] = 0,
["y"] = 0,
},
["stats.cardTitle"] = {
["x"] = 676,
["y"] = 147,
},
["stats.column.current"] = {
["x"] = 1,
["y"] = 0,
},
["stats.column.liveModifier"] = {
["x"] = -112,
["y"] = -11,
},
["stats.column.liveModifier.width"] = {
["width"] = -18,
},
["stats.column.priority"] = {
["x"] = -12,
["y"] = -11,
},
["stats.column.priority.width"] = {
["width"] = -10,
},
["stats.column.progress"] = {
["x"] = -106,
["y"] = -11,
},
["stats.column.stat"] = {
["x"] = -27,
["y"] = -11,
},
["stats.column.stat.width"] = {
["width"] = -66,
},
["stats.column.target"] = {
["x"] = 83,
["y"] = 0,
},
["stats.headerText.current"] = {
["x"] = 11,
["y"] = 0,
},
["stats.headerText.priority"] = {
["x"] = 2,
["y"] = 0,
},
["stats.headerText.stat"] = {
["x"] = -4,
["y"] = 0,
},
["stats.height"] = {
["height"] = 50,
},
["stats.mainContent"] = {
["x"] = 692,
["y"] = -214,
},
["stats.offContent"] = {
["x"] = -218,
["y"] = 495,
},
["stats.offContent.height"] = {
["height"] = -20,
},
["stats.offContent.width"] = {
["width"] = -142,
},
["stats.offSpecTitle"] = {
["x"] = 0,
["y"] = 45,
},
["stats.offSpecTitle.width"] = {
["width"] = -115,
},
["stats.pad"] = {
["bottom"] = 5,
["left"] = 5,
["right"] = 0,
["top"] = 5,
},
["stats.specTitle"] = {
["x"] = -1,
["y"] = 26,
},
["stats.specTitle.width"] = {
["width"] = -115,
},
["stats.table.width"] = {
["width"] = 20,
},
["stats.width"] = {
["width"] = -106,
},
["summary.attributes"] = {
["x"] = 5,
["y"] = -2,
},
["summary.attributes.width"] = {
["width"] = 0,
},
["summary.attributesTitle"] = {
["x"] = 5,
["y"] = -3,
},
["summary.attributesTitle.width"] = {
["width"] = 0,
},
["summary.card.pad"] = {
["bottom"] = 5,
["left"] = 0,
["right"] = 0,
["top"] = 5,
},
["summary.enhancements"] = {
["x"] = 5,
["y"] = -1,
},
["summary.enhancements.width"] = {
["width"] = 0,
},
["summary.enhancementsTitle"] = {
["x"] = 5,
["y"] = -2,
},
["summary.enhancementsTitle.width"] = {
["width"] = 0,
},
["summary.itemLevel"] = {
["x"] = 5,
["y"] = 0,
},
["summary.itemLevel.width"] = {
["width"] = 0,
},
["summary.svTitle"] = {
["x"] = 5,
["y"] = -3,
},
["summary.svTitle.width"] = {
["width"] = 0,
},
["summary.svValues"] = {
["x"] = 5,
["y"] = -1,
},
["summary.svValues.width"] = {
["width"] = 0,
},
["summary.title"] = {
["x"] = 0,
["y"] = 0,
},
["summary.title.height"] = {
["height"] = -4,
},
["summary.title.width"] = {
["width"] = -9,
},
["summary.width"] = {
["width"] = -97,
},
["trinkets.card.pad"] = {
["bottom"] = 5,
["left"] = 0,
["right"] = 0,
["top"] = 5,
},
["trinkets.title"] = {
["x"] = -10,
["y"] = 0,
},
["trinkets.title.height"] = {
["height"] = -4,
},
["trinkets.title.pad"] = {
["bottom"] = 0,
["left"] = 5,
["right"] = 5,
["top"] = 0,
},
["trinkets.title.width"] = {
["width"] = 69,
},
}

-- The window's own layout (title, menus, buttons, border) the add-on was tuned on; copied from the owner's saved layout.
local DEFAULT_STAT_AUDIT_LAYOUT = {
    applyBtnX = -92,
    applyBtnY = 15,
    aspectLabelFontSize = 11,
    autoHeroToggleX = 170,
    autoHeroToggleY = -74,
    avgProgressFontSize = 12,
    avgProgressX = 14,
    avgProgressY = 20,
    borderAlpha = 0.35,
    buttonHeight = 22,
    buttonWidth = 80,
    defaultBtnX = -10,
    defaultBtnY = 15,
    dropdownScale = 1,
    dropdownWidth = 108,
    editBtnX = -95,
    editBtnY = 15,
    extraHeight = 0,
    frameExtraHeight = 0,
    frameWidth = 732,
    goalDropdownScale = 1,
    goalDropdownWidth = 112,
    goalDropdownX = -260,
    goalDropdownY = -55,
    goalLabelX = -325,
    goalLabelY = -40,
    offspecToggleFontSize = 15,
    offspecToggleX = 18,
    offspecToggleY = -75,
    primaryDropdownScale = 1,
    primaryDropdownWidth = 130,
    primaryDropdownX = -129,
    primaryDropdownY = -55,
    primaryLabelX = -175,
    primaryLabelY = -40,
    sampleLineFontSize = 11,
    sampleLineX = 221,
    sampleLineY = 21,
    secondaryDropdownScale = 1,
    secondaryDropdownWidth = 130,
    secondaryDropdownX = 3,
    secondaryDropdownY = -55,
    secondaryLabelX = -53,
    secondaryLabelY = -40,
    secondaryTitleX = 18,
    secondaryTitleY = -40,
    titleFontSize = 12,
    titleWidth = 674,
    titleX = 18,
    titleY = -25,
    width = 688,
    x = 23,
    y = -112,
}

local DEFAULT_SPEC_TITLE_FONT_SIZE = 13

-- Saved entries of the removed layout dev tools and of their one-time fixes. Nothing reads them any more.
local LEFTOVER_DEV_KEYS = {
    "advancedDevelopmentMode", "devDashboardHidden", "devDashboardHiddenUndo", "devDashboardOffsetsUndo",
    "devLayoutPadPosition", "devDashboardLayoutSchemaVersion", "devDashboardOffsetsRestoredFromBackup",
    "layoutWeightsKeysMoved", "devFlushDockFrames12Fix", "devAbsoluteStackFrames12Fix", "devBisWidthAutoFix",
    "devSingleGutterBetweenCardsFix", "devStatsCardDockFix", "devUniformPanelGutterFix", "devScreen2FromOffTable",
}

local function CopyRecoveredOffsets(target)
    if type(target) ~= "table" then return end
    for key, value in pairs(DEFAULT_DASHBOARD_OFFSETS) do
        if type(value) == "table" then
            target[key] = {}
            for field, fieldValue in pairs(value) do
                target[key][field] = fieldValue
            end
        end
    end
end

function ns.EnsureLayoutDB()
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    _G.StatVerdictDB.devDashboardOffsets = _G.StatVerdictDB.devDashboardOffsets or {}
    -- Layout seed 2 (once, for everyone): every player gets the layout the add-on was tuned on. The add-on has no setting that
    -- changes these sizes and positions (only the old layout dev tools did, which are gone), so nothing a player chose is lost. The window position,
    -- the saved builds and every other setting are not touched.
    if _G.StatVerdictDB.layoutSeedVersion ~= 2 then
        _G.StatVerdictDB.devDashboardOffsets = {}
        CopyRecoveredOffsets(_G.StatVerdictDB.devDashboardOffsets)
        _G.StatVerdictDB.statAuditLayout = {}
        for key, value in pairs(DEFAULT_STAT_AUDIT_LAYOUT) do
            _G.StatVerdictDB.statAuditLayout[key] = value
        end
        _G.StatVerdictDB.specTitleFontSize = DEFAULT_SPEC_TITLE_FONT_SIZE
        for _, key in ipairs(LEFTOVER_DEV_KEYS) do
            _G.StatVerdictDB[key] = nil
        end
        _G.StatVerdictDB.layoutSeedVersion = 2
    end
    return _G.StatVerdictDB.devDashboardOffsets
end

local function EnsureDB()
    return ns.EnsureLayoutDB()
end

function ns.GetLayoutOffset(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then return 0, 0 end
    return tonumber(value.x) or 0, tonumber(value.y) or 0
end

function ns.GetLayoutSizeDelta(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then return 0 end
    return tonumber(value.width) or 0
end

function ns.GetLayoutHeightDelta(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then return 0 end
    return tonumber(value.height) or 0
end

function ns.GetLayoutPadding(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then
        return { top = 0, bottom = 0, left = 0, right = 0 }
    end
    return {
        top = tonumber(value.top) or 0,
        bottom = tonumber(value.bottom) or 0,
        left = tonumber(value.left) or 0,
        right = tonumber(value.right) or 0,
    }
end

function ns.WriteLayoutOffset(key, x, y, extras)
    if type(key) ~= "string" then return end
    local db = EnsureDB()
    local entry = db[key]
    if type(entry) ~= "table" then
        entry = {}
        db[key] = entry
    end
    entry.x = tonumber(x) or 0
    entry.y = tonumber(y) or 0
    if type(extras) == "table" then
        for k, v in pairs(extras) do
            entry[k] = v
        end
    end
end

function ns.GetLayoutOffsetAbs(key)
    local value = EnsureDB()[key]
    return type(value) == "table" and value._abs == true
end

-- Sets the border colour of a panel (nil colour: leave it).
function ns.SetBorderColor(region, r, g, b, a)
    if region and region.SetBackdropBorderColor and r ~= nil then
        region:SetBackdropBorderColor(r, g, b, a)
    end
end
