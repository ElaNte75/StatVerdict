local addonName, ns = ...

ns.ADDON_NAME = addonName
ns.VERSION = "1.0.7"
ns.ACTIVE_PROVIDER = "StatVerdict"

local frame = CreateFrame("Frame")
ns.Frame = frame

frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
frame:RegisterEvent("PLAYER_SPECIALIZATION_CHANGED")
frame:RegisterEvent("BAG_UPDATE_DELAYED")
frame:RegisterEvent("PLAYER_TALENT_UPDATE")
frame:RegisterEvent("ACTIVE_TALENT_GROUP_CHANGED")
frame:RegisterEvent("TRAIT_CONFIG_UPDATED")
frame:RegisterEvent("TRAIT_SUB_TREE_CHANGED")

frame:SetScript("OnEvent", function()
    if ns.RefreshUpgradeIndicators then
        ns.RefreshUpgradeIndicators()
    end
end)

local function PrintSV(message)
    print("|cffff8000StatVerdict:|r " .. tostring(message or ""))
end

local function ResolveApproveContext(preferSecondary)
    local primaryContext, secondaryContext = nil, nil
    if ns.GetTooltipEvaluationContexts then
        primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
    end
    if preferSecondary then
        return secondaryContext or primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)
    end
    return primaryContext or (ns.GetEvaluationContext and ns.GetEvaluationContext() or nil)
end

local function ResolveApproveTarget(arg)
    local itemLink, context, slotID = nil, nil, nil
    if ns.GetRememberedTooltipVerdictContext then
        itemLink, context, slotID = ns.GetRememberedTooltipVerdictContext()
    end

    local preferSecondary = false
    if type(arg) == "string" and arg ~= "" then
        local pasted = arg:match("(|Hitem:.-|h.-|h)") or arg:match("(item:%d+[^%s]*)")
        if pasted then
            itemLink = pasted
        elseif arg:lower() == "secondary" or arg:lower() == "os" then
            preferSecondary = true
        end
    end

    context = ResolveApproveContext(preferSecondary) or context
    return itemLink, context, slotID
end

function ns.TryApproveItemLink(itemLink, slotID, preferSecondary)
    if type(itemLink) ~= "string" or itemLink == "" then
        return false
    end
    local context = ResolveApproveContext(preferSecondary)
    local profile = context and context.profile or nil
    if not profile then
        if preferSecondary then
            PrintSV("No off-spec build selected to save into.")
        else
            PrintSV("No evaluation profile available for approve.")
        end
        return false
    end
    if not ns.ApproveItemIntoVirtualLoadout then
        PrintSV("Approve is not available.")
        return false
    end

    -- Toggle: Alt-clicking an item already saved in this spec's loadout removes
    -- it again (slot reverts to the currently worn piece).
    if ns.IsItemInEquipmentSnapshot and ns.RemoveItemFromVirtualLoadout
        and ns.IsItemInEquipmentSnapshot(profile, itemLink) then
        local removed, removeMessage = ns.RemoveItemFromVirtualLoadout(itemLink, profile)
        PrintSV(removeMessage or (removed and "Removed." or "Remove failed."))
        return removed and true or false
    end

    -- Prefer remembered slot when the remembered item matches this link.
    -- Do not override the MS/OS target chosen by the click (preferSecondary).
    local rememberedLink, rememberedContext, rememberedSlot = nil, nil, nil
    if ns.GetRememberedTooltipVerdictContext then
        rememberedLink, rememberedContext, rememberedSlot = ns.GetRememberedTooltipVerdictContext()
    end
    if not slotID and rememberedLink and rememberedSlot then
        local sameID = tostring(itemLink):match("item:(%d+)") == tostring(rememberedLink):match("item:(%d+)")
        if sameID then
            slotID = rememberedSlot
        end
    end

    local ok, message = ns.ApproveItemIntoVirtualLoadout(itemLink, profile, slotID)
    PrintSV(message or (ok and "Saved." or "Approve failed."))
    return ok and true or false
end

local function ApproveFromCommand(arg)
    local itemLink, context, slotID = ResolveApproveTarget(arg)
    if not itemLink then
        PrintSV("Hover an upgrade, then Alt-Right-Click it (or use /sv approve).")
        return
    end
    ns.TryApproveItemLink(itemLink, slotID, arg and (arg:lower() == "secondary" or arg:lower() == "os"))
end

local function TryApproveFromTooltipClick(tooltip, button)
    if not IsAltKeyDown or not IsAltKeyDown() then return end
    if button ~= "RightButton" and button ~= "LeftButton" then return end
    if not tooltip or not tooltip:IsShown() then return end

    local preferSecondary = (button == "LeftButton")
    if preferSecondary then
        local _, secondaryContext = nil, nil
        if ns.GetTooltipEvaluationContexts then
            _, secondaryContext = ns.GetTooltipEvaluationContexts()
        end
        if not secondaryContext then
            return
        end
    end

    local itemLink, context, slotID = nil, nil, nil
    if ns.GetRememberedTooltipVerdictContext then
        itemLink, context, slotID = ns.GetRememberedTooltipVerdictContext()
    end
    if not itemLink then
        if type(tooltip.GetItem) == "function" then
            local _, link = tooltip:GetItem()
            itemLink = link
        end
    end
    if not itemLink then
        return
    end
    ns.TryApproveItemLink(itemLink, slotID, preferSecondary)
end

if GameTooltip then
    GameTooltip:HookScript("OnMouseDown", function(self, button)
        TryApproveFromTooltipClick(self, button)
    end)
end
if ItemRefTooltip then
    ItemRefTooltip:HookScript("OnMouseDown", function(self, button)
        TryApproveFromTooltipClick(self, button)
    end)
end

local function HandleSlash(msg)
    local cmd, arg = msg:match("^(%S*)%s*(.-)$")
    cmd = string.lower(cmd or "")

    if ns.HandleMinimapSlash and ns.HandleMinimapSlash(cmd) then
        return
    end

    if cmd == "approve" then
        ApproveFromCommand(arg)
    elseif cmd == "help" or cmd == "" then
        PrintSV("Available commands:")
        print("  Alt-Right-Click an upgrade in bags to save it into Main Spec")
        print("  Alt-Left-Click an upgrade in bags to save it into Off Spec (when enabled)")
        print("  /sv approve - Save the hovered upgrade into Main Spec")
        print("  /sv approve secondary - Save into Off Spec when dual-build is enabled")
        print("  /sv minimap - Show the minimap icon")
        print("  /sv help - Show this help message")
        print("  /sva - Open / close the StatVerdict window")
        if ns.STATVERDICT_DEV_TOOLS then
            print("  /svdev - Advanced Development tools")
            print("  /svmove - Layout editor")
            print("  /svbis - Best in Slot resolver")
        end
    else
        PrintSV("Unknown command: " .. cmd)
        print("Use /sv help for available commands")
    end
end

SLASH_STATVERDICT1 = "/sv"
SlashCmdList["STATVERDICT"] = HandleSlash

-- Hidden, not in /sv help: /svweights guide|measured|blend (see SV_ProfileRepository).
SLASH_STATVERDICTWEIGHTS1 = "/svweights"
SlashCmdList["STATVERDICTWEIGHTS"] = function(msg)
    if ns.HandleWeightModeSlash then ns.HandleWeightModeSlash(msg) end
end
