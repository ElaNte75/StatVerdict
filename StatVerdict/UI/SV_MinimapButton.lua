local addonName, ns = ...

-- Minimap button + retail Addon Compartment ("addon bag") opener.
-- No LibDBIcon embed — lightweight custom button.

local CUSTOM_ICON = "Interface\\AddOns\\StatVerdict\\Media\\StatVerdictIcon.tga"
local FALLBACK_ICON = "Interface\\Icons\\Ability_Mage_BrainFreeze"
-- Prefer custom Media icon when present; otherwise use a stock icon (Media file optional).
local ICON_TEXTURE = FALLBACK_ICON
local BUTTON_SIZE = 31
local DEFAULT_ANGLE = 220

local button

local function ResolveIconTexture()
    if type(GetFileIDFromPath) == "function" then
        local id = GetFileIDFromPath(CUSTOM_ICON)
        if id and id > 0 then
            return CUSTOM_ICON
        end
    end
    return FALLBACK_ICON
end
local function EnsureMinimapDB()
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    local db = _G.StatVerdictDB
    if type(db.minimap) ~= "table" then
        db.minimap = { hide = false, angle = DEFAULT_ANGLE }
    end
    if db.minimap.angle == nil then
        db.minimap.angle = DEFAULT_ANGLE
    end
    return db.minimap
end

local function UpdateButtonPosition()
    if not button or not Minimap then return end
    local db = EnsureMinimapDB()
    local angle = math.rad(tonumber(db.angle) or DEFAULT_ANGLE)
    local radius = (Minimap:GetWidth() / 2) + 5
    button:ClearAllPoints()
    button:SetPoint("CENTER", Minimap, "CENTER", math.cos(angle) * radius, math.sin(angle) * radius)
end

local function SetButtonShown(shown)
    local db = EnsureMinimapDB()
    db.hide = not shown
    if not button then return end
    if shown then
        button:Show()
        UpdateButtonPosition()
    else
        button:Hide()
    end
end

local function ToggleFromClick()
    if ns.ToggleStatAudit then
        ns.ToggleStatAudit()
    end
end

local function ShowButtonTooltip(owner)
    if not GameTooltip then return end
    GameTooltip:SetOwner(owner, "ANCHOR_LEFT")
    GameTooltip:AddLine("StatVerdict", 1.0, 0.82, 0.0)
    if ns.VERSION then
        GameTooltip:AddLine(tostring(ns.VERSION), 0.72, 0.74, 0.78)
    end
    GameTooltip:AddLine("Left-click: open / close", 1, 1, 1)
    GameTooltip:AddLine("Right-click: hide minimap icon", 0.8, 0.8, 0.8)
    GameTooltip:AddLine("Drag: move around minimap", 0.8, 0.8, 0.8)
    GameTooltip:AddLine("Also available in the Addon Compartment bag.", 0.65, 0.75, 0.85)
    GameTooltip:Show()
end

local function EnsureButton()
    if button then return button end
    if not Minimap then return nil end
    ICON_TEXTURE = ResolveIconTexture()

    button = CreateFrame("Button", ns.UIName and ns.UIName("StatVerdictMinimapButton") or "StatVerdictMinimapButton", Minimap)
    button:SetSize(BUTTON_SIZE, BUTTON_SIZE)
    button:SetFrameStrata("MEDIUM")
    button:SetFrameLevel((Minimap:GetFrameLevel() or 1) + 8)
    button:RegisterForClicks("AnyUp")
    button:RegisterForDrag("LeftButton")
    button:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")

    local overlay = button:CreateTexture(nil, "OVERLAY")
    overlay:SetSize(53, 53)
    overlay:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
    overlay:SetPoint("TOPLEFT", button, "TOPLEFT", 0, 0)

    local icon = button:CreateTexture(nil, "BACKGROUND")
    icon:SetSize(20, 20)
    icon:SetTexture(ICON_TEXTURE)
    icon:SetPoint("CENTER", button, "CENTER", 0, 0)
    button.icon = icon

    button:SetScript("OnEnter", function(self)
        ShowButtonTooltip(self)
    end)
    button:SetScript("OnLeave", function()
        if GameTooltip then GameTooltip:Hide() end
    end)

    button:SetScript("OnClick", function(_, mouseButton)
        if mouseButton == "RightButton" then
            SetButtonShown(false)
            print("|cffff8000StatVerdict:|r Minimap icon hidden. Use the Addon Compartment bag or /sva to open. Re-show with /sv minimap.")
            return
        end
        ToggleFromClick()
    end)

    button:SetScript("OnDragStart", function(self)
        self:SetScript("OnUpdate", function(btn)
            local mx, my = Minimap:GetCenter()
            local cx, cy = GetCursorPosition()
            local scale = Minimap:GetEffectiveScale() or 1
            cx, cy = cx / scale, cy / scale
            local angle = math.deg(math.atan2(cy - my, cx - mx))
            local db = EnsureMinimapDB()
            db.angle = angle
            UpdateButtonPosition()
        end)
    end)
    button:SetScript("OnDragStop", function(self)
        self:SetScript("OnUpdate", nil)
    end)

    UpdateButtonPosition()
    if EnsureMinimapDB().hide then
        button:Hide()
    else
        button:Show()
    end
    return button
end

local function RegisterAddonCompartment()
    -- Prefer TOC AddonCompartmentFunc registration; skip manual duplicate.
    if ns._svCompartmentRegistered then
        return
    end
    if not AddonCompartmentFrame or not AddonCompartmentFrame.RegisterAddon then
        return
    end
    -- TOC already registers when AddonCompartmentFunc is present; only fall back if needed.
    if C_AddOns and C_AddOns.GetAddOnMetadata then
        local tocFunc = C_AddOns.GetAddOnMetadata(addonName, "AddonCompartmentFunc")
        if tocFunc and tocFunc ~= "" then
            ns._svCompartmentRegistered = true
            return
        end
    end
    ns._svCompartmentRegistered = true
    AddonCompartmentFrame:RegisterAddon({
        text = "StatVerdict",
        icon = ICON_TEXTURE,
        notCheckable = true,
        func = function(_, menuInputData)
            local buttonName = type(menuInputData) == "table" and menuInputData.buttonName or menuInputData
            if buttonName == "RightButton" then
                return
            end
            ToggleFromClick()
        end,
        funcOnEnter = function(menuButton)
            ShowButtonTooltip(menuButton)
        end,
        funcOnLeave = function()
            if GameTooltip then GameTooltip:Hide() end
        end,
    })
end

-- TOC / global hooks for Addon Compartment metadata registration.
local function OnCompartmentClick(_, buttonName)
    if buttonName == "RightButton" then
        return
    end
    ToggleFromClick()
end

local function OnCompartmentEnter(_, menuButtonFrame)
    ShowButtonTooltip(menuButtonFrame)
end

local function OnCompartmentLeave()
    if GameTooltip then GameTooltip:Hide() end
end

function StatVerdict_OnAddonCompartmentClick(_, buttonName)
    OnCompartmentClick(_, buttonName)
end
function StatVerdict_OnAddonCompartmentEnter(_, menuButtonFrame)
    OnCompartmentEnter(_, menuButtonFrame)
end
function StatVerdict_OnAddonCompartmentLeave()
    OnCompartmentLeave()
end

local loader = CreateFrame("Frame")
loader:RegisterEvent("PLAYER_LOGIN")
loader:SetScript("OnEvent", function(self)
    EnsureMinimapDB()
    EnsureButton()
    RegisterAddonCompartment()
    self:UnregisterEvent("PLAYER_LOGIN")
end)

function ns.HandleMinimapSlash(msg)
    msg = tostring(msg or ""):lower():match("^%s*(.-)%s*$") or ""
    if msg == "minimap" or msg == "icon" then
        SetButtonShown(true)
        print("|cffff8000StatVerdict:|r Minimap icon shown.")
        return true
    end
    return false
end
