local addonName, ns = ...

-- Custom outer chrome for the main StatVerdict window (replaces BasicFrameTemplate).

local TITLE_BAR_H = 30
local TITLE_FONT_SIZE = 15
local VERSION_FONT_SIZE = 11
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
    if frame.CloseButton then
        frame.versionLabel:SetPoint("RIGHT", frame.CloseButton, "LEFT", -10, 0)
    else
        frame.versionLabel:SetPoint("RIGHT", titleBar, "RIGHT", -12, 0)
    end
    frame.versionLabel:SetJustifyH("LEFT")
    frame.versionLabel:SetText(versionText ~= "" and versionText or "")
    frame.versionLabel:SetTextColor(VERSION_COLOR[1], VERSION_COLOR[2], VERSION_COLOR[3])
    frame.versionLabel:Show()

    frame.svChromeTitleBarHeight = TITLE_BAR_H
    return titleBar
end
