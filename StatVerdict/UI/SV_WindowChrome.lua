local addonName, ns = ...

-- Custom outer chrome for the main StatVerdict window (replaces BasicFrameTemplate).

local TITLE_BAR_H = 30
local TITLE_FONT_SIZE = 15
local VERSION_FONT_SIZE = 11

-- ns.RELEASE_DATE ("2026-10-03") as "3 Oct 2026"; English month names, so the text never depends on the game language.
local MONTHS = { "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" }
function ns.FormatReleaseDate()
    local year, month, day = tostring(ns.RELEASE_DATE or ""):match("^(%d+)-(%d+)-(%d+)$")
    month = tonumber(month)
    if not (year and MONTHS[month or 0]) then return nil end
    return tonumber(day) .. " " .. MONTHS[month] .. " " .. year
end

-- Options > Window > Window size: the whole window, and the side panels that are part of it, scale together.
local SCALE_MIN, SCALE_MAX, SCALE_DEFAULT = 75, 100, 85 -- percent: a smaller window, never one too small to read

-- The normal window and Compact Mode each remember their own size. Until the player picks one for Compact Mode it keeps
-- the size the normal window has, so switching mode does not make the window jump.
function ns.GetWindowScaleKey()
    local db = _G.StatVerdictDB
    if type(db) == "table" and db.compactMode == true then return "windowScaleCompact" end
    return "windowScale"
end

function ns.GetWindowScalePercent()
    local db = _G.StatVerdictDB
    local percent = SCALE_DEFAULT
    if type(db) == "table" then
        percent = tonumber(db[ns.GetWindowScaleKey()]) or tonumber(db.windowScale) or SCALE_DEFAULT
    end
    return math.max(SCALE_MIN, math.min(SCALE_MAX, percent))
end

function ns.GetWindowScale()
    return ns.GetWindowScalePercent() / 100
end

-- Gives the window the saved size and keeps its top left corner (and the saved spot of the side panels) where it was on the
-- screen. Returns the factor the positions were multiplied by and the new top left, or nil when nothing changed.
function ns.ChangeWindowScale(frame)
    if not (frame and frame.SetScale) then return nil end
    local new = ns.GetWindowScale()
    local old = tonumber(frame.GetScale and frame:GetScale()) or 1
    if math.abs(old - new) < 0.001 then return nil end
    local left = frame.GetLeft and tonumber(frame:GetLeft())
    local top = frame.GetTop and tonumber(frame:GetTop())
    frame:SetScale(new)
    local ratio = old / new
    local newLeft, newTop
    if left and top then
        newLeft, newTop = left * ratio, top * ratio
        frame:ClearAllPoints()
        frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", newLeft, newTop)
    end
    local db = _G.StatVerdictDB
    local spot = type(db) == "table" and db.floatingPanelPos or nil
    if type(spot) == "table" and tonumber(spot.x) and tonumber(spot.y) then
        spot.x, spot.y = spot.x * ratio, spot.y * ratio
    end
    return ratio, newLeft, newTop
end

-- Options > Window > Always on top (off unless the player turns it on).
-- On: the window always sits in front of the add-ons and the game's own windows.
-- Off: it is in front while the player works in it, and steps behind everything as soon as the player clicks anywhere else
-- (another add-on, the chat, a game window, the world); a click on it brings it forward again.
local FRONT_STRATA, BACK_STRATA = "HIGH", "BACKGROUND"
local layered -- the window the layer rules are applied to

function ns.AlwaysOnTopEnabled()
    local db = _G.StatVerdictDB
    return type(db) == "table" and db.alwaysOnTop == true
end

-- The window and the panels that are windows of their own (Compact Mode) always share one layer.
local function SetStrata(frame, strata)
    frame:SetFrameStrata(strata)
    if ns.SyncFloatingPanelStrata then ns.SyncFloatingPanelStrata(frame, strata) end
end

local function SetLayer(frame, front)
    frame.svInFront = front
    SetStrata(frame, front and FRONT_STRATA or BACK_STRATA)
    if front and frame.Raise then frame:Raise() end
end

-- Is the mouse over the window, or over anything that belongs to it (a panel window of its own, its menus, its blocker)?
-- The second value is the panel window it is over, so that one can be brought in front of the main window.
local function MouseIsOverOurWindow(frame)
    local foci
    if type(GetMouseFoci) == "function" then
        foci = GetMouseFoci()
    elseif type(GetMouseFocus) == "function" then
        foci = { GetMouseFocus() }
    end
    for _, focus in ipairs(foci or {}) do
        local current = focus
        while current do
            if current == frame then return true, nil end
            if current.svWindow == frame then return true, current end
            if current.svOwnedWindow then return true, nil end
            current = current.GetParent and current:GetParent() or nil
        end
    end
    return false, nil
end

local function OnAnyMouseDown()
    local frame = layered
    if not frame or ns.AlwaysOnTopEnabled() or not frame:IsShown() then return end
    local over, panel = MouseIsOverOurWindow(frame)
    if over ~= frame.svInFront then SetLayer(frame, over) end
    -- A click on a panel window of its own brings that panel to the front, not the main window over it.
    if over and panel and panel.Raise then panel:Raise() end
end

-- frame: the main window the first time; later calls (the option changed) may leave it out.
function ns.ApplyAlwaysOnTop(frame)
    if frame and frame.SetFrameStrata and layered ~= frame then
        layered = frame
        frame:HookScript("OnShow", function(self)
            if not ns.AlwaysOnTopEnabled() then SetLayer(self, true) end
        end)
        local watcher = CreateFrame("Frame")
        watcher:SetScript("OnEvent", OnAnyMouseDown)
        pcall(watcher.RegisterEvent, watcher, "GLOBAL_MOUSE_DOWN")
    end
    frame = frame or layered
    if not (frame and frame.SetFrameStrata) then return end
    if ns.AlwaysOnTopEnabled() then
        frame.svInFront = true
        SetStrata(frame, FRONT_STRATA)
    else
        SetLayer(frame, true)
    end
    if frame.SetToplevel then frame:SetToplevel(true) end
end
-- The narrowest window whose title bar still holds the title, the version, the tier label and the close button.
function ns.GetTitleBarMinWidth(frame)
    local function width(fontString)
        return fontString and fontString.GetStringWidth and tonumber(fontString:GetStringWidth()) or 0
    end
    if not frame then return 0 end
    return 12 + width(frame.title) + 8 + width(frame.versionLabel) + 10 + width(frame.tierLabel) + 10 + 22 + 6
end

local EDGE = 1
local PAD = 6

local BG = { 0.055, 0.062, 0.078, 0.97 }
local TITLE_BG = { 0.090, 0.098, 0.118, 0.98 }
local OUTER_BORDER = { 0.48, 0.50, 0.54, 0.92 }
local INNER_BORDER = { 0.30, 0.32, 0.36, 0.70 }
local INNER_FILL = { 0.035, 0.040, 0.052, 0.40 }
local GOLD = { 1.00, 0.82, 0.00 }
local VERSION_COLOR = { 0.72, 0.74, 0.78 }
local CLOSE_IDLE = { 0.10, 0.10, 0.12, 0.92 }
local CLOSE_HOVER = { 0.16, 0.16, 0.18, 0.95 }
local CLOSE_BORDER = { 0.40, 0.40, 0.42, 0.92 }

local function PaintClose(button, state)
    if not button then return end
    if state == "hover" then
        button:SetBackdropColor(CLOSE_HOVER[1], CLOSE_HOVER[2], CLOSE_HOVER[3], CLOSE_HOVER[4])
        button:SetBackdropBorderColor(0.55, 0.55, 0.58, 0.95)
    elseif state == "pushed" then
        button:SetBackdropColor(0.06, 0.06, 0.07, 0.95)
        button:SetBackdropBorderColor(0.28, 0.28, 0.30, 0.95)
    else
        button:SetBackdropColor(CLOSE_IDLE[1], CLOSE_IDLE[2], CLOSE_IDLE[3], CLOSE_IDLE[4])
        button:SetBackdropBorderColor(CLOSE_BORDER[1], CLOSE_BORDER[2], CLOSE_BORDER[3], CLOSE_BORDER[4])
    end
end

--- Apply StatVerdict chrome to a plain BackdropTemplate frame.
--- Returns the title-bar frame (for drag / title anchoring).
function ns.ApplyStatVerdictWindowChrome(frame, options)
    if not frame then return nil end
    options = type(options) == "table" and options or {}

    frame:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Buttons\\WHITE8X8",
        edgeSize = EDGE,
        insets = { left = EDGE, right = EDGE, top = EDGE, bottom = EDGE },
    })
    frame:SetBackdropColor(BG[1], BG[2], BG[3], BG[4])
    frame:SetBackdropBorderColor(OUTER_BORDER[1], OUTER_BORDER[2], OUTER_BORDER[3], OUTER_BORDER[4])

    -- Soft outer rim (1px outside the hard edge) for a slightly richer silhouette.
    if not frame.svChromeRim then
        frame.svChromeRim = frame:CreateTexture(nil, "BACKGROUND", nil, -7)
    end
    frame.svChromeRim:ClearAllPoints()
    frame.svChromeRim:SetPoint("TOPLEFT", frame, "TOPLEFT", -2, 2)
    frame.svChromeRim:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", 2, -2)
    frame.svChromeRim:SetColorTexture(0, 0, 0, 0.45)

    local titleBar = frame.svTitleBar
    if not titleBar then
        titleBar = CreateFrame("Frame", nil, frame)
        frame.svTitleBar = titleBar
    end
    titleBar:ClearAllPoints()
    titleBar:SetPoint("TOPLEFT", frame, "TOPLEFT", EDGE, -EDGE)
    titleBar:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -EDGE, -EDGE)
    titleBar:SetHeight(TITLE_BAR_H)
    titleBar:EnableMouse(false)
    titleBar:SetFrameLevel((frame:GetFrameLevel() or 1) + 5)

    if not titleBar.bg then
        titleBar.bg = titleBar:CreateTexture(nil, "BACKGROUND")
    end
    titleBar.bg:SetAllPoints(titleBar)
    titleBar.bg:SetColorTexture(TITLE_BG[1], TITLE_BG[2], TITLE_BG[3], TITLE_BG[4])

    -- No gold accent line — kept the chrome clean under the close button.

    -- Inner content well (non-interactive).
    local well = frame.svInnerWell
    if not well then
        well = CreateFrame("Frame", nil, frame, "BackdropTemplate")
        frame.svInnerWell = well
    end
    well:EnableMouse(false)
    well:SetFrameLevel(math.max(1, (frame:GetFrameLevel() or 1)))
    well:ClearAllPoints()
    well:SetPoint("TOPLEFT", frame, "TOPLEFT", PAD, -(TITLE_BAR_H + EDGE + 2))
    well:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", -PAD, PAD)
    well:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Buttons\\WHITE8X8",
        edgeSize = 1,
        insets = { left = 0, right = 0, top = 0, bottom = 0 },
    })
    well:SetBackdropColor(INNER_FILL[1], INNER_FILL[2], INNER_FILL[3], INNER_FILL[4])
    well:SetBackdropBorderColor(INNER_BORDER[1], INNER_BORDER[2], INNER_BORDER[3], INNER_BORDER[4])

    -- Hide leftover accent from older builds.
    if frame.svTitleAccent then
        frame.svTitleAccent:Hide()
        frame.svTitleAccent:SetTexture(nil)
    end

    if options.close ~= false then
        local close = frame.CloseButton
        if not close then
            close = CreateFrame("Button", nil, frame, "BackdropTemplate")
            frame.CloseButton = close
            close:SetSize(22, 22)
            close:SetBackdrop({
                bgFile = "Interface\\Buttons\\WHITE8X8",
                edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
                tile = false,
                edgeSize = 10,
                insets = { left = 2, right = 2, top = 2, bottom = 2 },
            })
            close.label = close:CreateFontString(nil, "OVERLAY")
            local font = STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
            close.label:SetFont(font, 12, "")
            close.label:SetPoint("CENTER", close, "CENTER", 0, 0)
            close.label:SetText("x")
            close.label:SetTextColor(0.85, 0.85, 0.85)
            PaintClose(close, "normal")
            close:SetScript("OnEnter", function(self)
                PaintClose(self, "hover")
                self.label:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
            end)
            close:SetScript("OnLeave", function(self)
                PaintClose(self, "normal")
                self.label:SetTextColor(0.85, 0.85, 0.85)
            end)
            close:SetScript("OnMouseDown", function(self) PaintClose(self, "pushed") end)
            close:SetScript("OnMouseUp", function(self)
                if self:IsMouseOver() then PaintClose(self, "hover") else PaintClose(self, "normal") end
            end)
            close:SetScript("OnClick", function()
                if ns.CloseStatAudit then
                    ns.CloseStatAudit()
                else
                    frame:Hide()
                end
            end)
        end
        close:ClearAllPoints()
        close:SetPoint("TOPRIGHT", frame, "TOPRIGHT", -6, -4)
        close:SetFrameLevel((frame:GetFrameLevel() or 1) + 20)
        close:Show()
    end

    -- Window title + version on the title bar (above chrome layers).
    local font = STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
    if not frame.title then
        frame.title = titleBar:CreateFontString(nil, "OVERLAY")
    end
    frame.title:SetFont(font, TITLE_FONT_SIZE, "")
    frame.title:ClearAllPoints()
    frame.title:SetPoint("LEFT", titleBar, "LEFT", 12, 0)
    frame.title:SetJustifyH("LEFT")
    frame.title:SetText(options.title or "StatVerdict")
    frame.title:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    frame.title:Show()

    local versionText = tostring(options.version or ns.VERSION or "")
    if not frame.versionLabel then
        frame.versionLabel = titleBar:CreateFontString(nil, "OVERLAY")
    end
    frame.versionLabel:SetFont(font, VERSION_FONT_SIZE, "")
    frame.versionLabel:ClearAllPoints()
    frame.versionLabel:SetPoint("LEFT", frame.title, "RIGHT", 8, 0)

    -- The tier in use ("Auto · Tier 2") sits at the right end of the title bar.
    if not frame.tierLabel then
        frame.tierLabel = titleBar:CreateFontString(nil, "OVERLAY")
    end
    frame.tierLabel:SetFont(font, VERSION_FONT_SIZE, "")
    frame.tierLabel:ClearAllPoints()
    if frame.CloseButton then
        frame.tierLabel:SetPoint("RIGHT", frame.CloseButton, "LEFT", -10, 0)
    else
        frame.tierLabel:SetPoint("RIGHT", titleBar, "RIGHT", -12, 0)
    end
    frame.tierLabel:SetJustifyH("RIGHT")
    frame.tierLabel:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    frame.tierLabel:SetText("")
    frame.versionLabel:SetPoint("RIGHT", frame.tierLabel, "LEFT", -8, 0)
    frame.versionLabel:SetJustifyH("LEFT")
    frame.versionLabel:SetText(versionText ~= "" and ("v" .. versionText) or "")
    frame.versionLabel:SetTextColor(VERSION_COLOR[1], VERSION_COLOR[2], VERSION_COLOR[3])
    frame.versionLabel:Show()

    -- The mouse over the title or the version shows when the add-on was last updated. The title bar takes no mouse
    -- (the window drags by its own frame), so this only watches where the mouse is.
    if not frame.svUpdateWatcher then
        local watcher = CreateFrame("Frame", nil, frame)
        frame.svUpdateWatcher = watcher
        local elapsed, showing = 0, false
        local function hide()
            if showing and GameTooltip and GameTooltip:GetOwner() == titleBar then GameTooltip:Hide() end
            showing = false
        end
        watcher:SetScript("OnUpdate", function(_, dt)
            elapsed = elapsed + dt
            if elapsed < 0.1 then return end
            elapsed = 0
            local over = (frame.title and frame.title:IsMouseOver()) or (frame.versionLabel and frame.versionLabel:IsMouseOver())
            if over and not showing then
                if not GameTooltip or GameTooltip:IsShown() then return end
                local text = ns.FormatReleaseDate and ns.FormatReleaseDate() or nil
                if not text then return end
                GameTooltip:SetOwner(titleBar, "ANCHOR_BOTTOM")
                GameTooltip:AddLine("StatVerdict v" .. tostring(ns.VERSION or ""), GOLD[1], GOLD[2], GOLD[3])
                GameTooltip:AddLine("Last update: " .. text, 1, 1, 1)
                GameTooltip:Show()
                showing = true
            elseif not over then
                hide()
            end
        end)
        watcher:SetScript("OnHide", hide)
    end

    frame.svChromeTitleBarHeight = TITLE_BAR_H
    return titleBar
end
