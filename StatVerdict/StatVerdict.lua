local addonName, ns = ...

ns.VERSION = "2.1.41"
ns.RELEASE_DATE = "2026-10-05"  -- the day this version was last updated; shown when the mouse is over the title

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
    if ns.ResetContextScan then ns.ResetContextScan() end
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
        if not removed then PrintSV(removeMessage or "Remove failed.") end
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

    -- The marker on the item (MS / OS) is the answer; chat only says something when it did not work.
    local ok, message = ns.ApproveItemIntoVirtualLoadout(itemLink, profile, slotID)
    if not ok then PrintSV(message or "Approve failed.") end
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

-- /sv mouse: a diagnostic. For a few seconds it notes every change of the frame under the mouse and prints
-- the list at the end, so a report like "the tabs blink" shows which frame takes the mouse away.
local function FrameLabel(frame)
    local parts, current, depth = {}, frame, 0
    while current and depth < 4 do
        local ok, name = pcall(function() return current:GetName() end)
        if not (ok and type(name) == "string" and name ~= "") then
            local okType, objectType = pcall(function() return current:GetObjectType() end)
            name = okType and type(objectType) == "string" and objectType or "?"
        end
        parts[#parts + 1] = name
        local okParent, parent = pcall(function() return current:GetParent() end)
        current = okParent and parent or nil
        depth = depth + 1
    end
    return table.concat(parts, " < ")
end

function ns.WatchMouseFocus(seconds)
    if ns._svMouseWatch then
        PrintSV("Already watching.")
        return
    end
    local getFoci = type(GetMouseFoci) == "function" and GetMouseFoci or nil
    local getFocus = type(GetMouseFocus) == "function" and GetMouseFocus or nil
    if not (getFoci or getFocus) then
        PrintSV("This game version cannot report the frame under the mouse.")
        return
    end
    local watch = CreateFrame("Frame")
    ns._svMouseWatch = watch
    local elapsed, last, changes, counts, order = 0, nil, 0, {}, {}
    PrintSV("Watching the mouse for " .. tostring(seconds) .. " seconds. Move it over the tab that misbehaves.")
    watch:SetScript("OnUpdate", function(self, delta)
        elapsed = elapsed + delta
        local label
        local ok, foci = pcall(getFoci or getFocus)
        if ok then
            local top = getFoci and type(foci) == "table" and foci[1] or (not getFoci and foci) or nil
            label = top and FrameLabel(top) or "(nothing)"
        end
        if label and label ~= last then
            last = label
            changes = changes + 1
            if not counts[label] then counts[label] = 0; order[#order + 1] = label end
            counts[label] = counts[label] + 1
        end
        if elapsed >= seconds then
            self:SetScript("OnUpdate", nil)
            ns._svMouseWatch = nil
            PrintSV("Mouse focus changed " .. changes .. " times:")
            for _, name in ipairs(order) do
                print("  " .. counts[name] .. " x " .. name)
            end
        end
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
    elseif cmd == "mouse" then
        ns.WatchMouseFocus(8)
    elseif cmd == "ag" then
        StatVerdictDB = StatVerdictDB or {}
        StatVerdictDB.adventureGuideMarksOff = not StatVerdictDB.adventureGuideMarksOff or nil
        PrintSV("Adventure Guide marks are now " .. (StatVerdictDB.adventureGuideMarksOff and "OFF" or "ON")
            .. ". Type /reload to apply.")
    elseif cmd == "help" or cmd == "" then
        PrintSV("Available commands:")
        print("  Alt-Right-Click an upgrade in bags to save it into Main Spec")
        print("  Alt-Left-Click an upgrade in bags to save it into Off Spec (when enabled)")
        print("  /sv approve - Save the hovered upgrade into Main Spec")
        print("  /sv approve secondary - Save into Off Spec when dual-build is enabled")
        print("  /sv minimap - Show the minimap icon")
        print("  /sv ag - Switch the Adventure Guide marks off / on")
        print("  /sv mouse - For 8 seconds, list which frames sit under the mouse (for bug reports)")
        print("  /sv help - Show this help message")
        print("  /sva - Open / close the StatVerdict window")
    else
        PrintSV("Unknown command: " .. cmd)
        print("Use /sv help for available commands")
    end
end

SLASH_STATVERDICT1 = "/sv"
SlashCmdList["STATVERDICT"] = HandleSlash
