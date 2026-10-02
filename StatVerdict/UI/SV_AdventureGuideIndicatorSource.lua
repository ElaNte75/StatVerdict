local addonName, ns = ...
ns = ns or {}

-- Adventure Guide indicators: soft, local updates only.
-- Never call RefreshUpgradeIndicators("full") from here — that arrow wipe
-- wipe + GET_ITEM_INFO_RECEIVED feedback loop is what made loot rows flicker
-- and steal clicks.

local sourceFrame = CreateFrame("Frame")
local hookedFrames = {}
local journalLinkByItemID = {}
local pendingSoftRefresh = false
local softRefreshQueued = false
local lastSoftRefreshAt = 0
local MIN_SOFT_REFRESH_INTERVAL = 0.75
local requestedItemIDs = {}

-- "/sv ag" switches the Adventure Guide marks off (and on again): a way to tell whether the marks are what
-- makes the Adventure Guide misbehave. Saved in StatVerdictDB.adventureGuideMarksOff.
function ns.IsAdventureGuideMarksEnabled()
    return not (StatVerdictDB and StatVerdictDB.adventureGuideMarksOff)
end

local function LooksLikeItemLink(value)
    return type(value) == "string" and (value:find("|Hitem:", 1, true) or value:find("^item:%d+"))
end

local function GetItemIDFromLink(itemLink)
    if type(itemLink) ~= "string" then return nil end
    local id = itemLink:match("item:(%d+)")
    return id and tonumber(id) or nil
end

local function WalkFrames(root, visitor, depth)
    if not root or type(root.GetChildren) ~= "function" then return end
    depth = depth or 0
    if depth > 8 then return end
    local children = { root:GetChildren() }
    for _, child in ipairs(children) do
        visitor(child, depth + 1)
        WalkFrames(child, visitor, depth + 1)
    end
end

local function GetSafeDirectItemLink(frame)
    if not frame then return nil end
    for _, key in ipairs({ "itemLink", "link", "hyperlink", "itemHyperlink" }) do
        local value = frame[key]
        if LooksLikeItemLink(value) then return value end
    end
    return nil
end

local function CacheLinkForItemID(itemID, link)
    if itemID and LooksLikeItemLink(link) and link:find("|Hitem:", 1, true) then
        journalLinkByItemID[itemID] = link
    end
end

local function RequestItemLink(itemID)
    if not itemID or requestedItemIDs[itemID] then
        return
    end
    requestedItemIDs[itemID] = true
    if C_Item and C_Item.RequestLoadItemDataByID then
        pcall(C_Item.RequestLoadItemDataByID, itemID)
    end
end

local function GetAdventureLootItemLink(frame)
    if not frame then return nil end

    local direct = GetSafeDirectItemLink(frame)
    if direct and direct:find("|Hitem:", 1, true) then
        local itemID = GetItemIDFromLink(direct) or tonumber(frame.itemID or frame.itemId)
        CacheLinkForItemID(itemID, direct)
        return direct
    end

    local itemID = tonumber(frame.itemID or frame.itemId)
    if not itemID or itemID <= 0 then
        return nil
    end

    if journalLinkByItemID[itemID] then
        return journalLinkByItemID[itemID]
    end

    -- Only read cached item data. Never call GetItemInfo on a cold ID here:
    -- that requests the item and fires GET_ITEM_INFO_RECEIVED → refresh storm.
    local cached = C_Item and C_Item.IsItemDataCachedByID and C_Item.IsItemDataCachedByID(itemID)
    if cached and C_Item.GetItemInfo then
        local link = select(2, C_Item.GetItemInfo(itemID))
        if LooksLikeItemLink(link) and link:find("|Hitem:", 1, true) then
            CacheLinkForItemID(itemID, link)
            return link
        end
    end

    RequestItemLink(itemID)
    return nil
end

local function IsAdventureLootButton(frame)
    if not frame or type(frame.GetObjectType) ~= "function" or frame:GetObjectType() ~= "Button" then
        return false
    end
    local itemID = tonumber(frame.itemID or frame.itemId)
    if not itemID or itemID < 10000 then
        return false
    end
    local width = type(frame.GetWidth) == "function" and frame:GetWidth() or 0
    local height = type(frame.GetHeight) == "function" and frame:GetHeight() or 0
    -- Slightly looser than before: 12.1 loot rows vary a bit by UI scale.
    return width >= 220 and width <= 420 and height >= 36 and height <= 90
end

local function ScanAdventureGuide()
    if not ns.IsAdventureGuideMarksEnabled() then
        return 0
    end
    local root = _G.EncounterJournal
    if not root or type(root.IsShown) ~= "function" or not root:IsShown() then
        return 0
    end
    if not ns.UpdateUpgradeIndicatorFrame then
        return 0
    end

    local count = 0
    WalkFrames(root, function(frame)
        if not IsAdventureLootButton(frame) then return end
        local link = GetAdventureLootItemLink(frame)
        if link and link:find("|Hitem:", 1, true) then
            if ns.UpdateUpgradeIndicatorFrame(frame, link) then
                count = count + 1
            end
        else
            -- Clear stale arrow on recycled rows without a global wipe.
            ns.UpdateUpgradeIndicatorFrame(frame, "")
        end
    end)
    return count
end

local function SoftRefreshNow()
    local journal = _G.EncounterJournal
    if not (journal and type(journal.IsShown) == "function" and journal:IsShown()) then
        return
    end
    lastSoftRefreshAt = GetTime and GetTime() or 0
    ScanAdventureGuide()
end

-- Coalesced AG-only refresh. Does not wipe bags / other sources.
local function SoftRefreshSoon()
    if not ns.IsAdventureGuideMarksEnabled() then
        return
    end
    local journal = _G.EncounterJournal
    if not (journal and type(journal.IsShown) == "function" and journal:IsShown()) then
        return
    end

    softRefreshQueued = true
    if pendingSoftRefresh then
        return
    end
    pendingSoftRefresh = true

    local now = GetTime and GetTime() or 0
    local delay = 0.35
    if now > 0 and (now - lastSoftRefreshAt) < MIN_SOFT_REFRESH_INTERVAL then
        delay = MIN_SOFT_REFRESH_INTERVAL - (now - lastSoftRefreshAt) + 0.05
    end

    if C_Timer and C_Timer.After then
        C_Timer.After(delay, function()
            pendingSoftRefresh = false
            local again = softRefreshQueued
            softRefreshQueued = false
            if again then
                SoftRefreshNow()
            end
            -- If more events arrived during the scan, schedule one trailing pass.
            if softRefreshQueued and not pendingSoftRefresh then
                SoftRefreshSoon()
            end
        end)
    else
        pendingSoftRefresh = false
        softRefreshQueued = false
        SoftRefreshNow()
    end
end

local function HookFrameShow(frame)
    if not frame or hookedFrames[frame] or type(frame.HookScript) ~= "function" then return end
    hookedFrames[frame] = true
    frame:HookScript("OnShow", SoftRefreshSoon)
end

local function HookScrollRefresh(frame)
    if not frame or hookedFrames[frame] or type(frame.HookScript) ~= "function" then return end
    hookedFrames[frame] = true
    if frame:HasScript("OnVerticalScroll") then
        frame:HookScript("OnVerticalScroll", SoftRefreshSoon)
    end
    if frame:HasScript("OnMouseWheel") then
        frame:HookScript("OnMouseWheel", SoftRefreshSoon)
    end
end

local function HookJournalHelpers()
    if not hooksecurefunc then return end

    if type(EncounterJournal_LootUpdate) == "function" and not sourceFrame.StatVerdictAdventureLootHooked then
        sourceFrame.StatVerdictAdventureLootHooked = true
        hooksecurefunc("EncounterJournal_LootUpdate", SoftRefreshSoon)
    end

    if type(EncounterJournal_SetTooltipWithCompare) == "function" and not sourceFrame.StatVerdictAdventureTooltipHooked then
        sourceFrame.StatVerdictAdventureTooltipHooked = true
        hooksecurefunc("EncounterJournal_SetTooltipWithCompare", function(_, itemLink)
            if LooksLikeItemLink(itemLink) then
                local itemID = GetItemIDFromLink(itemLink)
                CacheLinkForItemID(itemID, itemLink)
                -- Learning a real hyperlink: soft paint only, no full wipe.
                SoftRefreshSoon()
            end
        end)
    end
end

local function InitializeAdventureGuideSource()
    if sourceFrame.StatVerdictAdventureInitialized then
        HookJournalHelpers()
        HookFrameShow(_G.EncounterJournal)
        return
    end
    sourceFrame.StatVerdictAdventureInitialized = true

    if ns.RegisterUpgradeIndicatorSource then
        -- Still register for rare intentional full scans (login bags+world),
        -- but AG event path never triggers those full scans itself.
        ns.RegisterUpgradeIndicatorSource("AdventureGuide", ScanAdventureGuide)
    end
    HookFrameShow(_G.EncounterJournal)
    HookJournalHelpers()

    local journal = _G.EncounterJournal
    if journal then
        HookScrollRefresh(journal.encounter and journal.encounter.info and journal.encounter.info.LootContainer)
        HookScrollRefresh(journal.LootJournal)
        if journal.encounter and journal.encounter.info and journal.encounter.info.LootScroll then
            HookScrollRefresh(journal.encounter.info.LootScroll)
        end
    end

    SoftRefreshSoon()
end

sourceFrame:RegisterEvent("PLAYER_LOGIN")
sourceFrame:RegisterEvent("ADDON_LOADED")
sourceFrame:RegisterEvent("GET_ITEM_INFO_RECEIVED")
sourceFrame:SetScript("OnEvent", function(_, event, arg1)
    if event == "PLAYER_LOGIN" then
        InitializeAdventureGuideSource()
    elseif event == "ADDON_LOADED" and arg1 == "Blizzard_EncounterJournal" then
        InitializeAdventureGuideSource()
    elseif event == "GET_ITEM_INFO_RECEIVED" then
        if not ns.IsAdventureGuideMarksEnabled() then
            return
        end
        local journal = _G.EncounterJournal
        if not (journal and type(journal.IsShown) == "function" and journal:IsShown()) then
            return
        end
        local itemID = tonumber(arg1)
        if itemID and C_Item and C_Item.GetItemInfo then
            local link = select(2, C_Item.GetItemInfo(itemID))
            CacheLinkForItemID(itemID, link)
        end
        SoftRefreshSoon()
    end
end)

if C_AddOns and C_AddOns.IsAddOnLoaded and C_AddOns.IsAddOnLoaded("Blizzard_EncounterJournal") then
    InitializeAdventureGuideSource()
end
