local addonName, ns = ...
ns = ns or {}

local sourceFrame = CreateFrame("Frame")
local hooked = false
local pendingRefresh = false
local lastRefreshAt = 0
local MIN_REFRESH_INTERVAL = 0.30
local MERCHANT_ITEM_BUTTONS = 12
local BUYBACK_ITEM_BUTTONS = 12

local function LooksLikeItemLink(value)
    return type(value) == "string" and (value:find("|Hitem:", 1, true) or value:find("^item:%d+"))
end

local function IsFrameVisible(frame)
    if not frame then return false end
    if type(frame.IsVisible) == "function" then
        return frame:IsVisible()
    end
    if type(frame.IsShown) == "function" then
        return frame:IsShown()
    end
    return false
end

local function MerchantShown()
    return IsFrameVisible(_G.MerchantFrame)
end

local function GetMerchantLink(index)
    if type(GetMerchantItemLink) == "function" then
        local ok, link = pcall(GetMerchantItemLink, index)
        if ok and LooksLikeItemLink(link) then
            return link
        end
    end
    return nil
end

local function GetBuybackLink(index)
    if type(GetBuybackItemLink) == "function" then
        local ok, link = pcall(GetBuybackItemLink, index)
        if ok and LooksLikeItemLink(link) then
            return link
        end
    end
    return nil
end

local function ScanMerchantButtons()
    if not MerchantShown() or not ns.UpdateUpgradeIndicatorFrame then
        return 0
    end

    local count = 0
    local options = { source = "merchant" }

    -- MerchantFrame page: MerchantItem1ItemButton … MerchantItem12ItemButton
    local pageOffset = 0
    if type(MerchantFrame) == "table" and tonumber(MerchantFrame.page) then
        pageOffset = (tonumber(MerchantFrame.page) - 1) * MERCHANT_ITEM_BUTTONS
    end

    local buybackMode = MerchantFrame and MerchantFrame.selectedTab == 2
    if buybackMode then
        local numBuyback = type(GetNumBuybackItems) == "function" and tonumber(GetNumBuybackItems()) or BUYBACK_ITEM_BUTTONS
        for index = 1, math.min(BUYBACK_ITEM_BUTTONS, numBuyback or BUYBACK_ITEM_BUTTONS) do
            local button = _G["MerchantItem" .. index .. "ItemButton"]
            local link = GetBuybackLink(index)
            if button then
                if link then
                    if ns.UpdateUpgradeIndicatorFrame(button, link, options) then
                        count = count + 1
                    end
                else
                    ns.UpdateUpgradeIndicatorFrame(button, "", options)
                end
            end
        end
        return count
    end

    local numItems = type(GetMerchantNumItems) == "function" and tonumber(GetMerchantNumItems()) or 0
    for slot = 1, MERCHANT_ITEM_BUTTONS do
        local button = _G["MerchantItem" .. slot .. "ItemButton"]
        local index = pageOffset + slot
        local link = (numItems > 0 and index <= numItems) and GetMerchantLink(index) or nil
        if button then
            if link then
                if ns.UpdateUpgradeIndicatorFrame(button, link, options) then
                    count = count + 1
                end
            else
                ns.UpdateUpgradeIndicatorFrame(button, "", options)
            end
        end
    end
    return count
end

local function RefreshSoon()
    if not MerchantShown() then
        return
    end
    if pendingRefresh then
        return
    end
    pendingRefresh = true
    local now = GetTime and GetTime() or 0
    local delay = 0.15
    if now > 0 and (now - lastRefreshAt) < MIN_REFRESH_INTERVAL then
        delay = MIN_REFRESH_INTERVAL - (now - lastRefreshAt) + 0.05
    end
    if C_Timer and C_Timer.After then
        C_Timer.After(delay, function()
            pendingRefresh = false
            if not MerchantShown() then
                return
            end
            lastRefreshAt = GetTime and GetTime() or 0
            ScanMerchantButtons()
        end)
    else
        pendingRefresh = false
        ScanMerchantButtons()
    end
end

local function HookMerchant()
    if hooked then return end
    hooked = true

    if ns.RegisterUpgradeIndicatorSource then
        ns.RegisterUpgradeIndicatorSource("Merchant", ScanMerchantButtons)
    end

    if _G.MerchantFrame and type(_G.MerchantFrame.HookScript) == "function" then
        _G.MerchantFrame:HookScript("OnShow", RefreshSoon)
        _G.MerchantFrame:HookScript("OnHide", function()
            if ns.HideUpgradeIndicators then
                -- Do not wipe bags/quest; only merchant buttons are cleared next scan.
            end
        end)
    end

    if hooksecurefunc then
        if type(MerchantFrame_Update) == "function" then
            hooksecurefunc("MerchantFrame_Update", RefreshSoon)
        end
        if type(MerchantFrame_UpdateMerchantInfo) == "function" then
            hooksecurefunc("MerchantFrame_UpdateMerchantInfo", RefreshSoon)
        end
        if type(MerchantFrame_UpdateBuybackInfo) == "function" then
            hooksecurefunc("MerchantFrame_UpdateBuybackInfo", RefreshSoon)
        end
    end
end

sourceFrame:RegisterEvent("PLAYER_LOGIN")
sourceFrame:RegisterEvent("MERCHANT_SHOW")
sourceFrame:RegisterEvent("MERCHANT_UPDATE")
sourceFrame:RegisterEvent("MERCHANT_CLOSED")
sourceFrame:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGIN" then
        HookMerchant()
        return
    end
    HookMerchant()
    if event == "MERCHANT_CLOSED" then
        return
    end
    RefreshSoon()
end)

if C_Timer and C_Timer.After then
    C_Timer.After(0.5, HookMerchant)
end
