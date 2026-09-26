local addonName, ns = ...

-- Public layout offsets: seed tuned defaults and expose read/write helpers.
-- The AdvDev editor (SV_DevLayoutNudge.lua) loads only in the developer TOC.
local RESTORED_DEV_DASHBOARD_OFFSETS = {
["stats.summary.devSummaryItemDiffRegion"] = {
["y"] = 1,
["x"] = -3,
},
["setup.offDropdown"] = {
["y"] = 60,
["x"] = 0,
},
["setup.width"] = {
["width"] = -64,
},
["stats.summary.armor.value"] = {
["y"] = -9,
["x"] = -87,
},
["stats.column.progress.width"] = {
["width"] = -56,
},
["stats.column.stat"] = {
["y"] = 0,
["x"] = -20,
},
["stats.header.liveModifier"] = {
["y"] = 0,
["x"] = -171,
},
["stats.summary.stamina.value"] = {
["y"] = -5,
["x"] = -87,
},
["stats.summary.bis.owned"] = {
["y"] = -3,
["x"] = -69,
},
["setup.optionsTitle"] = {
["y"] = 93,
["x"] = 2,
},
["setup.buildDropdown.width"] = {
["width"] = -65,
},
["stats.table"] = {
["y"] = 0,
["x"] = 6,
},
["stats.header.priority"] = {
["y"] = 0,
["x"] = -8,
},
["setup.mainDropdown"] = {
["y"] = 32,
["x"] = 0,
},
["stats.summary.item.diff"] = {
["y"] = 3,
["x"] = -56,
},
["stats.table.width"] = {
["width"] = -178,
},
["stats.summary.item.target"] = {
["y"] = 0,
["x"] = -77,
},
["setup.offTitle"] = {
["y"] = 55,
["x"] = 4,
},
["setup.offHeroDropdown"] = {
["y"] = -14,
["x"] = -4,
},
["stats.summary.item.value"] = {
["y"] = 1,
["x"] = -88,
},
["stats.summary.bis.label"] = {
["y"] = 2,
["x"] = 18,
},
["stats.column.progress"] = {
["y"] = 0,
["x"] = -100,
},
["stats.column.priority"] = {
["y"] = 0,
["x"] = -15,
},
["setup.mainHeroDropdown"] = {
["y"] = -220,
["x"] = -9,
},
["setup.offDropdown.width"] = {
["width"] = -65,
},
["stats.summary.bis.total"] = {
["y"] = -3,
["x"] = -71,
},
["setup.offViewToggle"] = {
["y"] = 0,
["x"] = 11,
},
["setup.offHeroDropdown.width"] = {
["width"] = -68,
},
["setup.mainTitle"] = {
["y"] = -2,
["x"] = 4,
},
["stats.summary.card.height"] = {
["height"] = 19,
},
["dashboard.width"] = {
["width"] = -287,
},
["stats.column.liveModifier"] = {
["y"] = 0,
["x"] = -186,
},
["stats.summary.title"] = {
["y"] = 0,
["x"] = 3,
},
["setup.buildDropdown"] = {
["y"] = 14,
["x"] = 0,
},
["setup.visibility.width"] = {
["width"] = -65,
},
["stats.summary.devSummaryItemSlashRegion"] = {
["y"] = 5,
["x"] = -4,
},
["setup.visibility"] = {
["y"] = 72,
["x"] = 0,
},
["stats.summary.armor.label"] = {
["y"] = -9,
["x"] = 39,
},
["stats.summary.speed.value"] = {
["y"] = -5,
["x"] = -159,
},
["stats.summary.avoidance.value"] = {
["y"] = -1,
["x"] = -158,
},
["stats.summary.leech.value"] = {
["y"] = 1,
["x"] = -158,
},
["setup.card"] = {
["y"] = 0,
["x"] = 0,
},
["stats.summary.leech.label"] = {
["y"] = 1,
["x"] = -78,
},
["stats.summary.bis.slash"] = {
["y"] = -3,
["x"] = -69,
},
["stats.summary.speed.label"] = {
["y"] = -5,
["x"] = -78,
},
["setup.mainDropdown.width"] = {
["width"] = -66,
},
["stats.summary.avoidance.label"] = {
["y"] = -1,
["x"] = -78,
},
["bis.width"] = {
["width"] = 0,
},
["stats.summary.item.label"] = {
["y"] = 1,
["x"] = 39,
},
["stats.summary.stamina.label"] = {
["y"] = -5,
["x"] = 39,
},
["stats.summary.item.slash"] = {
["y"] = 0,
["x"] = -75,
},
["stats.summary.width"] = {
["width"] = -26,
},
["stats.summary.primary.value"] = {
["y"] = -1,
["x"] = -88,
},
["stats.summary.primary.current"] = {
["y"] = 4,
["x"] = -91,
},
["stats.summary.card"] = {
["y"] = 62,
["x"] = 6,
},
["stats.summary.bis.current"] = {
["y"] = 16,
["x"] = -70,
},
["stats.summary.devSummaryItemTargetRegion"] = {
["y"] = 1,
["x"] = -1,
},
["setup.offGoalDropdown"] = {
["y"] = 42,
["x"] = 0,
},
["bis.card"] = {
["y"] = 0,
["x"] = -200,
},
["stats.card"] = {
["y"] = 0,
["x"] = 0,
},
["stats.summary.item.current"] = {
["y"] = 0,
["x"] = -75,
},
["stats.summary.primary.label"] = {
["y"] = -1,
["x"] = 39,
},
["stats.header.stat"] = {
["y"] = 0,
["x"] = -57,
},
["setup.offGoalDropdown.width"] = {
["width"] = -65,
},
["stats.width"] = {
["width"] = -169,
},
["stats.header.progress"] = {
["y"] = 0,
["x"] = -101,
},
["setup.mainHeroDropdown.width"] = {
["width"] = -64,
},
}

local function TableHasEntries(value)
    if type(value) ~= "table" then return false end
    return next(value) ~= nil
end

local function CopyRecoveredOffsets(target)
    if type(target) ~= "table" then return end
    for key, value in pairs(RESTORED_DEV_DASHBOARD_OFFSETS) do
        if type(value) == "table" then
            target[key] = {}
            for field, fieldValue in pairs(value) do
                target[key][field] = fieldValue
            end
        end
    end
end

function ns.EnsureDevLayoutDB()
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    _G.StatVerdictDB.devDashboardOffsets = _G.StatVerdictDB.devDashboardOffsets or {}
    if not TableHasEntries(_G.StatVerdictDB.devDashboardOffsets) and _G.StatVerdictDB.devDashboardOffsetsRestoredFromBackup ~= true then
        CopyRecoveredOffsets(_G.StatVerdictDB.devDashboardOffsets)
        _G.StatVerdictDB.devDashboardOffsetsRestoredFromBackup = true
    end
    if _G.StatVerdictDB.devBisWidthAutoFix ~= true then
        local bisWidth = _G.StatVerdictDB.devDashboardOffsets["bis.width"]
        if type(bisWidth) == "table" and tonumber(bisWidth.width) and tonumber(bisWidth.width) < 0 then
            bisWidth.width = 0
        end
        local trinketsWidth = _G.StatVerdictDB.devDashboardOffsets["trinkets.width"]
        if type(trinketsWidth) == "table" and tonumber(trinketsWidth.width) and tonumber(trinketsWidth.width) < 0 then
            trinketsWidth.width = 0
        end
        _G.StatVerdictDB.devBisWidthAutoFix = true
    end
    if _G.StatVerdictDB.devStatsCardDockFix ~= true then
        local statsCard = _G.StatVerdictDB.devDashboardOffsets["stats.card"]
        if type(statsCard) == "table" then
            statsCard.x = 0
        end
        _G.StatVerdictDB.devStatsCardDockFix = true
    end
    if _G.StatVerdictDB.devSingleGutterBetweenCardsFix ~= true then
        local statsCard = _G.StatVerdictDB.devDashboardOffsets["stats.card"]
        if type(statsCard) == "table" then
            statsCard.x = 0
        end
        _G.StatVerdictDB.devSingleGutterBetweenCardsFix = true
    end
    if _G.StatVerdictDB.devAbsoluteStackFrames12Fix ~= true then
        local statsCard = _G.StatVerdictDB.devDashboardOffsets["stats.card"]
        if type(statsCard) == "table" then
            statsCard.x = 0
        end
        _G.StatVerdictDB.devAbsoluteStackFrames12Fix = true
    end
    if _G.StatVerdictDB.devUniformPanelGutterFix ~= true then
        for _, key in ipairs({ "setup.card", "stats.card" }) do
            local entry = _G.StatVerdictDB.devDashboardOffsets[key]
            if type(entry) == "table" then
                entry.y = 0
            end
        end
        _G.StatVerdictDB.devUniformPanelGutterFix = true
    end
    if _G.StatVerdictDB.devScreen2FromOffTable ~= true then
        local db = _G.StatVerdictDB.devDashboardOffsets
        local off = db["stats.offTable"]
        if type(db["screen.2"]) ~= "table" and type(off) == "table" then
            db["screen.2"] = { x = tonumber(off.x) or 0, y = tonumber(off.y) or 0 }
        end
        local offW = db["stats.offTable.width"]
        if type(db["screen.2.width"]) ~= "table" and type(offW) == "table" then
            db["screen.2.width"] = { width = tonumber(offW.width) or 0 }
        end
        local offH = db["stats.offTable.height"]
        if type(db["screen.2.height"]) ~= "table" and type(offH) == "table" then
            db["screen.2.height"] = { height = tonumber(offH.height) or 0 }
        end
        _G.StatVerdictDB.devScreen2FromOffTable = true
    end
    return _G.StatVerdictDB.devDashboardOffsets
end

local function EnsureDB()
    return ns.EnsureDevLayoutDB()
end

function ns.GetDevLayoutOffset(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then return 0, 0 end
    return tonumber(value.x) or 0, tonumber(value.y) or 0
end

function ns.GetDevLayoutSizeDelta(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then return 0 end
    return tonumber(value.width) or 0
end

function ns.GetDevLayoutHeightDelta(key)
    local value = EnsureDB()[key]
    if type(value) ~= "table" then return 0 end
    return tonumber(value.height) or 0
end

function ns.GetDevLayoutPadding(key)
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

function ns.WriteDevLayoutOffset(key, x, y, extras)
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

function ns.GetDevLayoutOffsetAbs(key)
    local value = EnsureDB()[key]
    return type(value) == "table" and value._abs == true
end

-- No-op stubs so product UI can call AdvDev helpers safely without the editor.
-- Critical: edit-only badges/borders must stay hidden when the editor is absent.
function ns.IsDevLayoutEditActive()
    return false
end

function ns.IsDevLayoutHidden(key)
    return false
end

function ns.IsDevLayoutScreenLocked(key)
    return true
end

function ns.RegisterDevLayoutRegion() end
function ns.UnregisterDevLayoutRegion() end
function ns.UnregisterDevLayoutRegionsByPrefix() end
function ns.UnregisterDevLayoutRegionsMatching() end
function ns.RegisterDevLayoutOuterSpec() end

function ns.RegisterDevLayoutEditOnly(region)
    if region and region.Hide then
        region:Hide()
    end
end

function ns.RegisterDevLayoutBorderEditOnly(region, r, g, b, a)
    if region and region.SetBackdropBorderColor then
        region:SetBackdropBorderColor(0, 0, 0, 0)
    end
end

function ns.UnregisterDevLayoutBorderEditOnly(region, r, g, b, a)
    if region and region.SetBackdropBorderColor and r ~= nil then
        region:SetBackdropBorderColor(r, g, b, a)
    end
end

function ns.EnsureDevLayoutStripRegion() return nil end
function ns.EnsureDevLayoutRimRegions() return nil end
function ns.EnsureDevLayoutGripRegion() return nil end
function ns.EnsureDevLayoutWidthHandle() return nil end
function ns.EnsureDevLayoutHeightHandle() return nil end
function ns.EnsureDevLayoutTextHitRegion() return nil end
function ns.EnsureDevLayoutLockButton() return nil end
function ns.ToggleDevLayoutScreenLock() end
function ns.RequestAdvancedDevelopmentModeLayoutRefresh() end

