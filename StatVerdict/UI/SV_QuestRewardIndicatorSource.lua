local addonName, ns = ...
ns = ns or {}

local sourceFrame = CreateFrame("Frame")
local hookedFrames = {}
local hookedScrollFrames = {}

local function DebugLine(line)
    if ns.AppendItemDebugLine then
        ns.AppendItemDebugLine(tostring(line or ""))
    end
    -- Disabled chat print to avoid spam
    -- else
    --     print("|cffffd76a[SV QuestRewards]|r " .. tostring(line or ""))
    -- end
end

local function SafeCall(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, result = pcall(fn, ...)
    if ok then return result end
    return nil
end

local function SafeCallAll(fn, ...)
    if type(fn) ~= "function" then return nil end
    local results = { pcall(fn, ...) }
    if results[1] then
        table.remove(results, 1)
        return unpack(results)
    end
    return nil
end

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

local function GetRewardButton(index)
    local rewardsFrame = (QuestInfoFrame and QuestInfoFrame.rewardsFrame) or _G.QuestInfoRewardsFrame
    if not rewardsFrame or type(QuestInfo_GetRewardButton) ~= "function" then
        return nil
    end
    return QuestInfo_GetRewardButton(rewardsFrame, index) or _G["QuestInfoRewardsFrameQuestInfoItem" .. tostring(index)]
end

local function GetSelectedQuestID()
    if C_QuestLog and type(C_QuestLog.GetSelectedQuest) == "function" then
        local questID = SafeCall(C_QuestLog.GetSelectedQuest)
        if tonumber(questID) and tonumber(questID) > 0 then
            return tonumber(questID)
        end
    end
    if type(GetQuestID) == "function" then
        local questID = SafeCall(GetQuestID)
        if tonumber(questID) and tonumber(questID) > 0 then
            return tonumber(questID)
        end
    end
    return nil
end

local function GetQuestRewardClipFrame()
    for _, frame in ipairs({
        _G.QuestMapDetailsScrollFrame,
        _G.QuestDetailScrollFrame,
        _G.QuestProgressScrollFrame,
        _G.QuestScrollFrame,
        _G.QuestRewardScrollFrame,
        _G.QuestInfoScrollFrame,
    }) do
        if IsFrameVisible(frame) then
            return frame
        end
    end
    return nil
end

local function GetQuestRewardLink(rewardType, index)
    if type(GetQuestItemLink) == "function" then
        local link = SafeCall(GetQuestItemLink, rewardType, index)
        if LooksLikeItemLink(link) then return link end
    end
    return nil
end

local function GetQuestLogItemID(rewardType, index, questID)
    if rewardType == "choice" and type(GetQuestLogChoiceInfo) == "function" then
        local _, _, _, _, _, itemID = SafeCallAll(GetQuestLogChoiceInfo, index, questID)
        if tonumber(itemID) then return tonumber(itemID) end
        _, _, _, _, _, itemID = SafeCallAll(GetQuestLogChoiceInfo, index)
        if tonumber(itemID) then return tonumber(itemID) end
    elseif rewardType == "reward" and type(GetQuestLogRewardInfo) == "function" then
        local _, _, _, _, _, itemID = SafeCallAll(GetQuestLogRewardInfo, index, questID)
        if tonumber(itemID) then return tonumber(itemID) end
        _, _, _, _, _, itemID = SafeCallAll(GetQuestLogRewardInfo, index)
        if tonumber(itemID) then return tonumber(itemID) end
    end
    return nil
end

local function GetQuestLogRewardLink(rewardType, index, questID)
    if type(GetQuestLogItemLink) == "function" then
        local link = SafeCall(GetQuestLogItemLink, rewardType, index, questID)
        if LooksLikeItemLink(link) then return link end
        link = SafeCall(GetQuestLogItemLink, rewardType, index)
        if LooksLikeItemLink(link) then return link end
    end
    local itemID = GetQuestLogItemID(rewardType, index, questID)
    if itemID then
        local _, link = C_Item and C_Item.GetItemInfo and SafeCallAll(C_Item.GetItemInfo, itemID)
        if LooksLikeItemLink(link) then return link end
        return "item:" .. tostring(itemID)
    end
    return nil
end

local function GetQuestLogChoiceCount(questID)
    if type(GetNumQuestLogChoices) ~= "function" then return 0 end
    return tonumber(SafeCall(GetNumQuestLogChoices, questID, false))
        or tonumber(SafeCall(GetNumQuestLogChoices, questID))
        or tonumber(SafeCall(GetNumQuestLogChoices))
        or 0
end

local function GetQuestLogRewardCount(questID)
    if type(GetNumQuestLogRewards) ~= "function" then return 0 end
    return tonumber(SafeCall(GetNumQuestLogRewards, questID))
        or tonumber(SafeCall(GetNumQuestLogRewards))
        or 0
end

local function IsQuestLogRewardMode()
    return IsFrameVisible(_G.QuestMapDetailsScrollFrame)
        or IsFrameVisible(_G.QuestScrollFrame)
        or (QuestInfoFrame and QuestInfoFrame.questLog and IsFrameVisible(_G.QuestInfoRewardsFrame))
end

local function ForEachQuestReward(callback)
    local rewardsFrame = _G.QuestInfoRewardsFrame
    local rewardPanel = _G.QuestFrameRewardPanel
    local questLogMode = IsQuestLogRewardMode()
    local visible = IsFrameVisible(rewardsFrame) or IsFrameVisible(rewardPanel) or questLogMode
    if not visible then
        return 0
    end

    local questID = questLogMode and GetSelectedQuestID() or nil
    local choiceCount
    local rewardCount
    if questLogMode and questID then
        choiceCount = GetQuestLogChoiceCount(questID)
        rewardCount = GetQuestLogRewardCount(questID)
    else
        choiceCount = tonumber(type(GetNumQuestChoices) == "function" and SafeCall(GetNumQuestChoices) or 0) or 0
        rewardCount = tonumber(type(GetNumQuestRewards) == "function" and SafeCall(GetNumQuestRewards) or 0) or 0
    end
    local count = 0

    for index = 1, choiceCount do
        local button = GetRewardButton(index)
        local link = questLogMode and GetQuestLogRewardLink("choice", index, questID) or GetQuestRewardLink("choice", index)
        if button and link then
            callback(button, link, "choice", index, index, questLogMode)
            count = count + 1
        end
    end

    for index = 1, rewardCount do
        local buttonIndex = choiceCount + index
        local button = GetRewardButton(buttonIndex)
        local link = questLogMode and GetQuestLogRewardLink("reward", index, questID) or GetQuestRewardLink("reward", index)
        if button and link then
            callback(button, link, "reward", index, buttonIndex, questLogMode)
            count = count + 1
        end
    end

    return count
end

local function ScanQuestRewards()
    if not ns.UpdateUpgradeIndicatorFrame then
        return 0
    end

    local count = 0
    local options = { clipFrame = GetQuestRewardClipFrame(), allowValueIndicator = true }
    DebugLine("ScanQuestRewards: Starting scan")
    ForEachQuestReward(function(button, link)
        local buttonName = button and type(button.GetName) == "function" and button:GetName() or "unknown"
        DebugLine("ScanQuestRewards: Processing button=" .. tostring(buttonName) .. " link=" .. tostring(link))
        if ns.UpdateUpgradeIndicatorFrame(button, link, options) then
            count = count + 1
            DebugLine("ScanQuestRewards: Successfully updated indicator for " .. tostring(buttonName))
        else
            DebugLine("ScanQuestRewards: Failed to update indicator for " .. tostring(buttonName))
        end
    end)
    DebugLine("ScanQuestRewards: Finished scan, count=" .. tostring(count))
    return count
end

local function RefreshSoon()
    if ns.RefreshUpgradeIndicators then
        ns.RefreshUpgradeIndicators("full")
    end
end

local function HookFrameShow(frame)
    if not frame or hookedFrames[frame] or type(frame.HookScript) ~= "function" then return end
    hookedFrames[frame] = true
    frame:HookScript("OnShow", RefreshSoon)
end

local function HookScrollFrame(frame)
    if not frame or hookedScrollFrames[frame] or type(frame.HookScript) ~= "function" then return end
    hookedScrollFrames[frame] = true
    frame:HookScript("OnVerticalScroll", RefreshSoon)
    frame:HookScript("OnMouseWheel", RefreshSoon)
    frame:HookScript("OnScrollRangeChanged", RefreshSoon)
    HookFrameShow(frame)
end

local function InitializeQuestRewardSource()
    DebugLine("InitializeQuestRewardSource: Starting initialization")
    if ns.RegisterUpgradeIndicatorSource then
        ns.RegisterUpgradeIndicatorSource("QuestRewards", ScanQuestRewards)
        DebugLine("InitializeQuestRewardSource: Registered QuestRewards source")
    else
        DebugLine("InitializeQuestRewardSource: ERROR - ns.RegisterUpgradeIndicatorSource not available")
    end
    HookFrameShow(_G.QuestInfoFrame)
    HookFrameShow(_G.QuestFrame)
    HookFrameShow(_G.QuestInfoRewardsFrame)
    HookFrameShow(_G.QuestFrameRewardPanel)
    HookFrameShow(QuestInfoFrame and QuestInfoFrame.rewardsFrame)
    HookFrameShow(_G.QuestMapDetailsScrollChildFrame)
    HookScrollFrame(_G.QuestMapDetailsScrollFrame)
    HookScrollFrame(_G.QuestDetailScrollFrame)
    HookScrollFrame(_G.QuestProgressScrollFrame)
    HookScrollFrame(_G.QuestScrollFrame)
    HookScrollFrame(_G.QuestRewardScrollFrame)
    HookScrollFrame(_G.QuestInfoScrollFrame)
    DebugLine("InitializeQuestRewardSource: Hooks installed")
    RefreshSoon()
    DebugLine("InitializeQuestRewardSource: Initialization complete")
end

sourceFrame:RegisterEvent("PLAYER_LOGIN")
sourceFrame:RegisterEvent("QUEST_DETAIL")
sourceFrame:RegisterEvent("QUEST_PROGRESS")
sourceFrame:RegisterEvent("QUEST_COMPLETE")
sourceFrame:RegisterEvent("QUEST_FINISHED")
sourceFrame:RegisterEvent("QUEST_LOG_UPDATE")
sourceFrame:SetScript("OnEvent", function(_, event)
    if event == "QUEST_FINISHED" then
        return
    end
    InitializeQuestRewardSource()
end)

if C_Timer then
    C_Timer.After(0.50, InitializeQuestRewardSource)
end
