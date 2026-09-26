local addonName, ns = ...

-- Chip-style dropdown: same visual language as panel toggle chips,
-- but opens a list instead of toggling a side panel.

local LABEL_FONT_SIZE = 10
local ROW_HEIGHT = 22
local MENU_PAD = 4
local MAX_VISIBLE_ROWS = 12

local WHITE = { 0.82, 0.82, 0.82 }
local GOLD = { 0.95, 0.78, 0.20 }

local openDropdown = nil
local catcher = nil

local function PaintChip(button, state)
    if not button then return end
    if state == "pushed" then
        button:SetBackdropColor(0.06, 0.06, 0.07, 0.95)
        button:SetBackdropBorderColor(0.28, 0.28, 0.30, 0.95)
    elseif state == "hover" then
        button:SetBackdropColor(0.14, 0.14, 0.16, 0.95)
        button:SetBackdropBorderColor(0.48, 0.48, 0.50, 0.95)
    else
        button:SetBackdropColor(0.10, 0.10, 0.12, 0.92)
        button:SetBackdropBorderColor(0.38, 0.38, 0.40, 0.92)
    end
end

local function PaintMenuRow(button, state, selected)
    if not button then return end
    if state == "hover" or state == "pushed" then
        button:SetBackdropColor(0.18, 0.18, 0.20, 0.95)
        button:SetBackdropBorderColor(0.45, 0.45, 0.48, 0.6)
    elseif selected then
        button:SetBackdropColor(0.14, 0.14, 0.16, 0.95)
        button:SetBackdropBorderColor(0.40, 0.40, 0.42, 0.5)
    else
        button:SetBackdropColor(0.08, 0.08, 0.09, 0.0)
        button:SetBackdropBorderColor(0, 0, 0, 0)
    end
end

local function CloseChipDropdown(dropdown)
    if not dropdown then return end
    if dropdown.menu then dropdown.menu:Hide() end
    if openDropdown == dropdown then
        openDropdown = nil
    end
    if catcher then catcher:Hide() end
end

local function CloseOpenChipDropdown()
    if openDropdown then
        CloseChipDropdown(openDropdown)
    end
end

local function EnsureCatcher()
    if catcher then return catcher end
    catcher = CreateFrame("Button", ns.UIName and ns.UIName("StatVerdictChipDropdownCatcher") or "StatVerdictChipDropdownCatcher", UIParent)
    catcher:SetAllPoints(UIParent)
    catcher:SetFrameStrata("FULLSCREEN_DIALOG")
    catcher:SetFrameLevel(90)
    catcher:EnableMouse(true)
    catcher:Hide()
    catcher:SetScript("OnClick", function()
        CloseOpenChipDropdown()
    end)
    return catcher
end

local function EnsureMenuButton(menu, index)
    local button = menu.buttons[index]
    if button then return button end
    button = CreateFrame("Button", nil, menu, "BackdropTemplate")
    button:SetHeight(ROW_HEIGHT)
    button:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Buttons\\WHITE8X8",
        edgeSize = 1,
        insets = { left = 0, right = 0, top = 0, bottom = 0 },
    })
    button.label = button:CreateFontString(nil, "OVERLAY")
    local font = STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
    button.label:SetFont(font, LABEL_FONT_SIZE, "")
    button.label:SetJustifyH("LEFT")
    button.label:SetPoint("LEFT", button, "LEFT", 8, 0)
    button.label:SetPoint("RIGHT", button, "RIGHT", -8, 0)
    button.check = button:CreateFontString(nil, "OVERLAY")
    button.check:SetFont(font, LABEL_FONT_SIZE, "")
    button.check:SetPoint("RIGHT", button, "RIGHT", -6, 0)
    button.check:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
    button.check:SetText("")
    menu.buttons[index] = button
    return button
end

local function OpenChipDropdown(dropdown)
    if not dropdown or not dropdown.menu then return end
    CloseOpenChipDropdown()

    local options = dropdown.options or {}
    local menu = dropdown.menu
    local width = math.max(dropdown:GetWidth() or 170, 120)
    local count = #options
    if count <= 0 then return end

    local visible = math.min(count, MAX_VISIBLE_ROWS)
    local height = MENU_PAD * 2 + visible * ROW_HEIGHT
    menu:SetSize(width, height)
    menu:ClearAllPoints()
    menu:SetPoint("TOPLEFT", dropdown, "BOTTOMLEFT", 0, -2)
    menu:SetFrameStrata("FULLSCREEN_DIALOG")
    menu:SetFrameLevel(100)

    for index = 1, math.max(count, #(menu.buttons)) do
        local button = EnsureMenuButton(menu, index)
        local option = options[index]
        if option then
            button:ClearAllPoints()
            button:SetPoint("TOPLEFT", menu, "TOPLEFT", MENU_PAD, -MENU_PAD - ((index - 1) * ROW_HEIGHT))
            button:SetPoint("RIGHT", menu, "RIGHT", -MENU_PAD, 0)
            button.label:SetText(tostring(option.text or ""))
            if option.checked then
                button.label:SetTextColor(GOLD[1], GOLD[2], GOLD[3])
                button.check:SetText("•")
            else
                button.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
                button.check:SetText("")
            end
            PaintMenuRow(button, "normal", option.checked and true or false)
            button:SetScript("OnEnter", function(self)
                PaintMenuRow(self, "hover", option.checked and true or false)
            end)
            button:SetScript("OnLeave", function(self)
                PaintMenuRow(self, "normal", option.checked and true or false)
            end)
            button:SetScript("OnClick", function()
                CloseChipDropdown(dropdown)
                if type(option.func) == "function" then
                    option.func()
                end
            end)
            button:Show()
        else
            button:Hide()
        end
    end

    local c = EnsureCatcher()
    c:SetFrameLevel(menu:GetFrameLevel() - 1)
    c:Show()
    menu:Show()
    openDropdown = dropdown
end

function ns.CreateChipDropdown(parent, name)
    local root = CreateFrame("Frame", name, parent)
    root:SetSize(170, 26)
    root.svIsChipDropdown = true
    root.options = {}

    local chip = CreateFrame("Button", nil, root, "BackdropTemplate")
    chip:SetAllPoints(root)
    chip.shadow = chip:CreateTexture(nil, "BACKGROUND")
    chip.shadow:SetPoint("TOPLEFT", 2, -2)
    chip.shadow:SetPoint("BOTTOMRIGHT", 3, -3)
    chip.shadow:SetColorTexture(0, 0, 0, 0.45)
    chip:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = false,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    PaintChip(chip, "normal")

    local font = STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
    chip.label = chip:CreateFontString(nil, "OVERLAY")
    chip.label:SetFont(font, LABEL_FONT_SIZE, "")
    chip.label:SetJustifyH("LEFT")
    chip.label:SetJustifyV("MIDDLE")
    chip.label:SetWordWrap(false)
    if chip.label.SetMaxLines then
        chip.label:SetMaxLines(1)
    end
    chip.label:SetNonSpaceWrap(false)
    chip.label:SetPoint("LEFT", chip, "LEFT", 8, 0)
    chip.label:SetPoint("RIGHT", chip, "RIGHT", -18, 0)
    chip.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
    chip.label:SetText("")

    chip.caret = chip:CreateFontString(nil, "OVERLAY")
    chip.caret:SetFont(font, LABEL_FONT_SIZE, "")
    chip.caret:SetPoint("RIGHT", chip, "RIGHT", -7, 0)
    chip.caret:SetTextColor(0.65, 0.65, 0.65)
    chip.caret:SetText("v")

    chip:SetScript("OnEnter", function(self) PaintChip(self, "hover") end)
    chip:SetScript("OnLeave", function(self) PaintChip(self, "normal") end)
    chip:SetScript("OnMouseDown", function(self) PaintChip(self, "pushed") end)
    chip:SetScript("OnMouseUp", function(self)
        if self:IsMouseOver() then PaintChip(self, "hover") else PaintChip(self, "normal") end
    end)
    chip:SetScript("OnClick", function()
        if root.svEnabled == false then return end
        if root.menu and root.menu:IsShown() then
            CloseChipDropdown(root)
        else
            OpenChipDropdown(root)
        end
    end)

    local menu = CreateFrame("Frame", nil, UIParent, "BackdropTemplate")
    menu:SetBackdrop({
        bgFile = "Interface\\Buttons\\WHITE8X8",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = false,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    menu:SetBackdropColor(0.08, 0.08, 0.09, 0.97)
    menu:SetBackdropBorderColor(0.38, 0.38, 0.40, 0.95)
    menu:EnableMouse(true)
    menu:Hide()
    menu.buttons = {}

    root.chip = chip
    root.menu = menu

    function root:SetText(text)
        self.chip.label:SetText(tostring(text or ""))
    end

    function root:GetText()
        return self.chip.label:GetText()
    end

    function root:SetOptions(options)
        self.options = type(options) == "table" and options or {}
        if self.menu and self.menu:IsShown() then
            OpenChipDropdown(self)
        end
    end

    function root:SetEnabled(enabled)
        self.svEnabled = enabled ~= false
        if self.svEnabled then
            self.chip:Enable()
            self.chip:SetAlpha(1)
            if self.chip.label then
                self.chip.label:SetTextColor(WHITE[1], WHITE[2], WHITE[3])
            end
            if self.chip.caret then
                self.chip.caret:SetTextColor(0.65, 0.65, 0.65)
            end
        else
            CloseChipDropdown(self)
            self.chip:Disable()
            self.chip:SetAlpha(0.45)
            if self.chip.label then
                self.chip.label:SetTextColor(0.55, 0.55, 0.55)
            end
            if self.chip.caret then
                self.chip.caret:SetTextColor(0.40, 0.40, 0.40)
            end
            PaintChip(self.chip, "normal")
        end
    end

    function root:IsEnabled()
        return self.svEnabled ~= false
    end

    function root:Close()
        CloseChipDropdown(self)
    end

    root.svEnabled = true

    root:HookScript("OnHide", function(self)
        CloseChipDropdown(self)
    end)

    return root
end

function ns.IsChipDropdown(frame)
    return type(frame) == "table" and frame.svIsChipDropdown == true
end

function ns.CloseAllChipDropdowns()
    CloseOpenChipDropdown()
end
