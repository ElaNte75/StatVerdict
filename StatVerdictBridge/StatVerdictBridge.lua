local addonName, ns = ...

StatVerdictBridgeDB = StatVerdictBridgeDB or {}

local frame
local statusText
local exportButton
local busy = false

local RELOAD_POPUP = "STATVERDICT_BRIDGE_RELOAD"

local function SetStatus(message)
    -- UI only — never spam chat (progress can fire dozens of times per export).
    if statusText then
        statusText:SetText(tostring(message or ""))
    end
end

local function EnsureReloadPopup()
    if StaticPopupDialogs and not StaticPopupDialogs[RELOAD_POPUP] then
        StaticPopupDialogs[RELOAD_POPUP] = {
            text = "Export ready. Reload UI now so SavedVariables are written to disk?\n\nAfter reload, run scripts\\ship.ps1 in the StatVerdict project.",
            button1 = RELOADUI or "Reload UI",
            button2 = CANCEL or "Cancel",
            OnAccept = function()
                if ReloadUI then
                    ReloadUI()
                end
            end,
            timeout = 0,
            whileDead = true,
            hideOnEscape = true,
            preferredIndex = 3,
        }
    end
end

local function SetBusy(isBusy)
    busy = isBusy and true or false
    if exportButton then
        if busy then
            exportButton:Disable()
            exportButton:SetText("Working...")
        else
            exportButton:Enable()
            exportButton:SetText("Export from ClassCodex")
        end
    end
end

local function FinishExport(profileData, summary)
    local export = ns.EncodeExportPayload(profileData)
    StatVerdictBridgeDB = {
        version = 1,
        ready = true,
        lastRun = date("!%Y-%m-%dT%H:%M:%SZ"),
        clientBuild = select(4, GetBuildInfo()),
        summary = summary,
        profileCount = profileData and profileData.source and profileData.source.profileCount or 0,
        export = export,
    }

    SetBusy(false)
    SetStatus(("Ready. %d profiles. Reload, then run ship.ps1"):format(StatVerdictBridgeDB.profileCount or 0))
    EnsureReloadPopup()
    if StaticPopup_Show then
        StaticPopup_Show(RELOAD_POPUP)
    end
end

local function StartExport()
    if busy or (ns.Resolver and ns.Resolver.IsRunning and ns.Resolver.IsRunning()) then
        SetStatus("Already running.")
        return
    end

    if not _G.ClassCodexGearData and not _G.ClassCodexIcyVeinsData and not _G.ClassCodexData then
        SetStatus("ClassCodex is not loaded. Enable it and /reload.")
        return
    end

    SetBusy(true)
    SetStatus("Resolving BiS items...")

    local ok = ns.Resolver.Start(function(msg)
        SetStatus(msg)
    end, function(entries, summary)
        SetStatus("Building profile database...")
        local okBuild, profileDataOrErr = pcall(function()
            return ns.Builder.Build(entries, summary)
        end)
        if not okBuild then
            SetBusy(false)
            SetStatus("Build failed: " .. tostring(profileDataOrErr))
            return
        end

        local okEncode, encodeErr = pcall(function()
            FinishExport(profileDataOrErr, summary)
        end)
        if not okEncode then
            SetBusy(false)
            SetStatus("Encode failed: " .. tostring(encodeErr))
        end
    end)

    if not ok then
        SetBusy(false)
    end
end

local function EnsureFrame()
    if frame then
        return frame
    end

    frame = CreateFrame("Frame", "StatVerdictBridgeFrame", UIParent, "BasicFrameTemplateWithInset")
    frame:SetSize(420, 180)
    frame:SetPoint("CENTER")
    frame:SetFrameStrata("DIALOG")
    frame:SetMovable(true)
    frame:EnableMouse(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", frame.StartMoving)
    frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
    frame:Hide()

    local title = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    title:SetPoint("TOP", 0, -6)
    title:SetText("StatVerdict Bridge")

    local hint = frame:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    hint:SetPoint("TOPLEFT", 16, -36)
    hint:SetPoint("TOPRIGHT", -16, -36)
    hint:SetJustifyH("LEFT")
    hint:SetText("1) Press Export\n2) Reload when asked\n3) Run scripts\\ship.ps1 on your PC")

    exportButton = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
    exportButton:SetSize(200, 28)
    exportButton:SetPoint("TOP", 0, -90)
    exportButton:SetText("Export from ClassCodex")
    exportButton:SetScript("OnClick", StartExport)

    statusText = frame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    statusText:SetPoint("BOTTOMLEFT", 16, 18)
    statusText:SetPoint("BOTTOMRIGHT", -16, 18)
    statusText:SetJustifyH("LEFT")
    statusText:SetText("Ready.")

    return frame
end

function ns.Toggle()
    local f = EnsureFrame()
    if f:IsShown() then
        f:Hide()
    else
        f:Show()
    end
end

SLASH_STATVERDICTBRIDGE1 = "/svbridge"
SLASH_STATVERDICTBRIDGE2 = "/svb"
SlashCmdList.STATVERDICTBRIDGE = function(msg)
    local cmd = string.lower((msg or ""):match("^%s*(%S*)") or "")
    if cmd == "export" or cmd == "run" then
        EnsureFrame():Show()
        StartExport()
    elseif cmd == "status" then
        local db = StatVerdictBridgeDB or {}
        SetStatus(("ready=%s lastRun=%s profiles=%s"):format(
            tostring(db.ready),
            tostring(db.lastRun or "never"),
            tostring(db.profileCount or 0)
        ))
    else
        ns.Toggle()
    end
end

local boot = CreateFrame("Frame")
boot:RegisterEvent("PLAYER_LOGIN")
boot:SetScript("OnEvent", function()
    local db = StatVerdictBridgeDB
    local f = EnsureFrame()
    if type(db) == "table" and db.ready and db.export and db.export.chunkCount then
        SetStatus(("Last export ready (%s profiles). Run ship.ps1"):format(tostring(db.profileCount or 0)))
    else
        SetStatus("Ready. Press Export from ClassCodex.")
    end
    -- Keep frame hidden on login; open with /svbridge when needed.
    f:Hide()
end)
