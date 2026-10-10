local addonName, ns = ...
ns = ns or {}

-- One shared, trailing debounce for every arrow refresh (bags and all other sources):
-- requests only mark work as pending, one timer runs it, nothing is dropped, and a
-- refresh asked for in combat waits until combat ends.
local pendingKind = nil
local timerActive = false
local waitingForCombatEnd = false
local scanFrame
local REFRESH_DELAY = 0.20
local ITEM_INFO_DELAY = 0.60
local MIN_REFRESH_INTERVAL = 0.30
local NUM_CONTAINER_SCAN_FRAMES = NUM_TOTAL_BAG_FRAMES or NUM_CONTAINER_FRAMES or 13
local lastRefreshAt = 0
local clearDecisionCacheOnNextScan = false
local indicatorSources = {}
local bagRefreshCounter = 1

local function SafeCall(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, result = pcall(fn, ...)
    if ok then return result end
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

local GetIconAnchor

local function IsFrameInsideClip(frame, clipFrame)
    if not clipFrame then return true end
    local ok, result = pcall(function()
        if type(clipFrame.IsVisible) == "function" and not clipFrame:IsVisible() then
            return false
        end
        if type(frame.GetTop) ~= "function" or type(frame.GetBottom) ~= "function"
            or type(clipFrame.GetTop) ~= "function" or type(clipFrame.GetBottom) ~= "function" then
            return true
        end
        local top = frame:GetTop()
        local bottom = frame:GetBottom()
        local clipTop = clipFrame:GetTop()
        local clipBottom = clipFrame:GetBottom()
        if not top or not bottom or not clipTop or not clipBottom then
            return true
        end
        return bottom <= (clipTop + 2) and top >= (clipBottom - 2)
    end)
    if not ok then return true end
    return result and true or false
end

-- Indicators must never steal bag-slot clicks. Prefer Texture/FontString regions
-- (no mouse). Keep any leftover Frame overlays click-through and in parent strata.
local function EnsureClickThrough(overlay)
    if not overlay then return end
    if type(overlay.EnableMouse) ~= "function" then
        return
    end
    overlay:EnableMouse(false)
    if type(overlay.SetMouseClickEnabled) == "function" then
        overlay:SetMouseClickEnabled(false)
    end
    if type(overlay.SetMouseMotionEnabled) == "function" then
        overlay:SetMouseMotionEnabled(false)
    end
    if type(overlay.SetPropagateMouseClicks) == "function" then
        overlay:SetPropagateMouseClicks(true)
    end
    if type(overlay.SetPropagateMouseMotion) == "function" then
        overlay:SetPropagateMouseMotion(true)
    end
end

local function RepositionIndicator(frame, indicator)
    if not frame or not indicator then return end
    local anchor = GetIconAnchor(frame) or frame
    indicator:ClearAllPoints()
    local kind = indicator.svIndicatorKind
    if kind == "main_spec" or kind == "off_spec" or kind == "both_specs" then
        -- FontString anchored by CENTER on TOPRIGHT, shifted left so the
        -- trailing letter of the MS/OS badge only barely overhangs the icon.
        indicator:SetPoint("CENTER", anchor, "TOPRIGHT", -9, -6)
    else
        indicator:SetPoint("TOPLEFT", anchor, "TOPLEFT", -3, 3)
    end
    EnsureClickThrough(indicator)
    -- Frame overlays only: stay in parent strata / modest level bump.
    if type(indicator.EnableMouse) == "function"
        and type(frame.GetFrameLevel) == "function"
        and type(indicator.SetFrameLevel) == "function" then
        local ok, level = pcall(frame.GetFrameLevel, frame)
        if ok and tonumber(level) then
            indicator:SetFrameLevel(tonumber(level) + 5)
        end
    end
end

local function GetQuestItemLinkFromButton(button)
    if not button or type(button.GetID) ~= "function" or type(GetQuestItemLink) ~= "function" then
        return nil
    end
    local id = button:GetID()
    if not id or id <= 0 then return nil end
    local name = type(button.GetName) == "function" and button:GetName() or ""
    local itemType = button.type
    if itemType ~= "choice" and itemType ~= "reward" then
        if type(name) == "string" and name:find("Choice", 1, true) then
            itemType = "choice"
        elseif type(name) == "string" and name:find("Reward", 1, true) then
            itemType = "reward"
        end
    end
    if itemType == "choice" or itemType == "reward" then
        return SafeCall(GetQuestItemLink, itemType, id)
    end
    return nil
end

local function GetFrameItemLink(frame)
    if not IsFrameVisible(frame) then
        return nil
    end

    local link = nil
    if type(frame.GetItemLink) == "function" then
        link = SafeCall(frame.GetItemLink, frame)
        if LooksLikeItemLink(link) then return link end
    end
    if type(frame.GetItemLocation) == "function" and C_Item and C_Item.GetItemLink then
        local location = SafeCall(frame.GetItemLocation, frame)
        if location then
            link = SafeCall(C_Item.GetItemLink, location)
            if LooksLikeItemLink(link) then return link end
        end
    end
    if C_Container and C_Container.GetContainerItemLink then
        local bagID = type(frame.GetBagID) == "function" and SafeCall(frame.GetBagID, frame) or frame.bagID
        local slotID = type(frame.GetID) == "function" and SafeCall(frame.GetID, frame) or frame.slotID
        if bagID ~= nil and slotID ~= nil then
            link = SafeCall(C_Container.GetContainerItemLink, bagID, slotID)
            if LooksLikeItemLink(link) then return link end
        end
    end
    link = frame.itemLink or frame.link or frame.hyperlink
    if LooksLikeItemLink(link) then return link end
    link = GetQuestItemLinkFromButton(frame)
    if LooksLikeItemLink(link) then return link end
    return nil
end

local function IsBagItemFrame(frame)
    if not frame then return false end
    if type(frame.GetBagID) == "function" and SafeCall(frame.GetBagID, frame) ~= nil then
        return true
    end
    if frame.bagID ~= nil or frame.BagID ~= nil then
        return true
    end
    local name = type(frame.GetName) == "function" and frame:GetName() or nil
    return type(name) == "string" and (name:find("ContainerFrame", 1, true) or name:find("Bag", 1, true)) and true or false
end

local EQUIPPED_SLOT_NAMES = {
    CharacterHeadSlot = true,
    CharacterNeckSlot = true,
    CharacterShoulderSlot = true,
    CharacterBackSlot = true,
    CharacterChestSlot = true,
    CharacterShirtSlot = true,
    CharacterTabardSlot = true,
    CharacterWristSlot = true,
    CharacterHandsSlot = true,
    CharacterWaistSlot = true,
    CharacterLegsSlot = true,
    CharacterFeetSlot = true,
    CharacterFinger0Slot = true,
    CharacterFinger1Slot = true,
    CharacterTrinket0Slot = true,
    CharacterTrinket1Slot = true,
    CharacterMainHandSlot = true,
    CharacterSecondaryHandSlot = true,
    InspectHeadSlot = true,
    InspectNeckSlot = true,
    InspectShoulderSlot = true,
    InspectBackSlot = true,
    InspectChestSlot = true,
    InspectShirtSlot = true,
    InspectTabardSlot = true,
    InspectWristSlot = true,
    InspectHandsSlot = true,
    InspectWaistSlot = true,
    InspectLegsSlot = true,
    InspectFeetSlot = true,
    InspectFinger0Slot = true,
    InspectFinger1Slot = true,
    InspectTrinket0Slot = true,
    InspectTrinket1Slot = true,
    InspectMainHandSlot = true,
    InspectSecondaryHandSlot = true,
}

local function IsEquippedPaperDollItemFrame(frame)
    if not frame then return false end
    local name = type(frame.GetName) == "function" and frame:GetName() or nil
    if type(name) == "string" then
        if EQUIPPED_SLOT_NAMES[name] then return true end
        if (name:match("^Character.+Slot$") or name:match("^Inspect.+Slot$")) and not IsBagItemFrame(frame) then
            return true
        end
    end

    -- Retail character/inspect paper-doll slots can also be anonymous item buttons
    -- parented somewhere under PaperDollItemsFrame. Those represent already equipped
    -- items, so StatVerdict should not draw bag-style upgrade/value indicators there.
    local parent = type(frame.GetParent) == "function" and frame:GetParent() or nil
    local depth = 0
    while parent and depth < 8 do
        local parentName = type(parent.GetName) == "function" and parent:GetName() or nil
        if parentName == "PaperDollItemsFrame" or parentName == "InspectPaperDollItemsFrame" then
            return true
        end
        parent = type(parent.GetParent) == "function" and parent:GetParent() or nil
        depth = depth + 1
    end
    return false
end

GetIconAnchor = function(frame)
    if not frame then return nil end
    local candidates = {
        frame.Icon,
        frame.icon,
        frame.IconTexture,
        frame.iconTexture,
        frame.texture,
        frame.Texture,
    }
    for _, candidate in ipairs(candidates) do
        if candidate and type(candidate.GetObjectType) == "function" and type(candidate.IsShown) == "function" then
            return candidate
        end
    end
    local name = type(frame.GetName) == "function" and frame:GetName() or nil
    if type(name) == "string" then
        for _, suffix in ipairs({ "Icon", "IconTexture", "IconQuestTexture", "NormalTexture" }) do
            local candidate = _G[name .. suffix]
            if candidate and type(candidate.GetObjectType) == "function" then
                return candidate
            end
        end
    end
    return frame
end

local function HookIndicatorOwner(frame)
    if not frame or frame.StatVerdictIndicatorHooks or type(frame.HookScript) ~= "function" then
        return
    end
    frame.StatVerdictIndicatorHooks = true
    frame:HookScript("OnHide", function()
        if frame.StatVerdictUpgradeIndicator then frame.StatVerdictUpgradeIndicator:Hide() end
        if frame.StatVerdictSpecValueIndicator then frame.StatVerdictSpecValueIndicator:Hide() end
        if frame.StatVerdictOffSpecIndicator then frame.StatVerdictOffSpecIndicator:Hide() end
        if frame.StatVerdictBagRing then frame.StatVerdictBagRing:Hide() end
        -- The marks are hidden now, so the slot is no longer "already painted": the next scan must paint it again
        -- (otherwise a closed and reopened bag keeps its marks hidden for ever).
        frame.StatVerdictLastCheckedRefresh = nil
        frame.StatVerdictLastCheckedItemLink = nil
        frame.StatVerdictLastCheckedGUID = nil
    end)
    -- Do not refresh on every bag-button OnShow — that storms the UI when bags open.
    -- Container UpdateItems / BAG_UPDATE already schedule a coalesced refresh.
end

local UPGRADE_ARROW_TEXTURE = "Interface\\AddOns\\StatVerdict\\Textures\\UpgradeArrow"
-- Above bag icon art / borders (same OVERLAY layer, higher sublevel).
local INDICATOR_DRAW_SUBLEVEL = 7

-- The gold ring with two arrows (a picture): "this piece is in both builds' loadouts". Used on the character sheet and in
-- the bags. (The file is called SharedRing2: the first drawing, SharedRing, was dropped.)
local SHARED_TEXTURE = "Interface\\AddOns\\StatVerdict\\Textures\\SharedRing2"
-- The same ring with thicker, brighter strokes, for the bags (it has to stand out next to the green MS / OS letters).
local SHARED_TEXTURE_BAG = "Interface\\AddOns\\StatVerdict\\Textures\\SharedRingBold"

-- Textures / FontStrings never receive mouse. Avoid Frame wrappers on bag slots
-- so corner badges cannot steal clicks from the item button.
local function EnsureIndicator(frame)
    if frame.StatVerdictUpgradeIndicator then
        return frame.StatVerdictUpgradeIndicator
    end
    local texture = frame:CreateTexture(nil, "OVERLAY", nil, INDICATOR_DRAW_SUBLEVEL)
    texture:SetSize(18, 18)
    texture:SetTexture(UPGRADE_ARROW_TEXTURE)
    if texture.SetDrawLayer then
        texture:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
    end
    texture:Hide()
    frame.StatVerdictUpgradeIndicator = texture
    HookIndicatorOwner(frame)
    return texture
end

local function ApplyUpgradeLook(overlay)
    if not overlay then return end
    if overlay.SetTexture then
        overlay:SetSize(18, 18)
        overlay:SetTexture(UPGRADE_ARROW_TEXTURE)
        overlay:SetVertexColor(1, 1, 1, 1)
        if overlay.SetDrawLayer then
            overlay:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
        end
        overlay:Show()
    elseif overlay.texture then
        overlay:SetSize(18, 18)
        overlay.texture:SetTexture(UPGRADE_ARROW_TEXTURE)
        overlay.texture:SetVertexColor(1, 1, 1, 1)
        if overlay.texture.SetDrawLayer then
            overlay.texture:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
        end
        overlay.texture:Show()
    end
end

local function EnsureSpecValueIndicator(frame, field)
    field = field or "StatVerdictSpecValueIndicator"
    if frame[field] then
        return frame[field]
    end
    local text = frame:CreateFontString(nil, "OVERLAY")
    if type(text.SetDrawLayer) == "function" then
        text:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL)
    end
    if type(text.SetFont) == "function" then
        text:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", 13, "OUTLINE")
    end
    text:SetText("|cff00ff00OS|r")
    text:Hide()
    frame[field] = text
    HookIndicatorOwner(frame)
    return text
end

local function SetLetterBadgeFont(overlay, kind, size)
    local text = overlay
    if overlay and overlay.text then
        text = overlay.text
    end
    if not (text and text.SetFont) then return end
    local file, _, flags = text:GetFont()
    file = file or STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF"
    text:SetFont(file, size or 13, flags or "OUTLINE")
end

local function HideFrameIndicators(frame)
    if frame.StatVerdictUpgradeIndicator then
        frame.StatVerdictUpgradeIndicator.svIndicatorKind = nil
        frame.StatVerdictUpgradeIndicator:Hide()
    end
    if frame.StatVerdictSpecValueIndicator then
        frame.StatVerdictSpecValueIndicator.svIndicatorKind = nil
        frame.StatVerdictSpecValueIndicator:Hide()
    end
    if frame.StatVerdictOffSpecIndicator then
        frame.StatVerdictOffSpecIndicator.svIndicatorKind = nil
        frame.StatVerdictOffSpecIndicator:Hide()
    end
    if frame.StatVerdictBagRing then frame.StatVerdictBagRing:Hide() end
end

-- A piece in both loadouts: the same gold ring as on the character sheet, in the top right corner (no MS / OS letters).
local function SetBagRing(frame, shown)
    local ring = frame.StatVerdictBagRing
    if not ring then
        if not shown then return end
        ring = frame:CreateTexture(nil, "OVERLAY")
        if type(ring.SetDrawLayer) == "function" then ring:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL) end
        ring:SetTexture(SHARED_TEXTURE_BAG)
        ring:SetSize(22, 22)
        frame.StatVerdictBagRing = ring
        HookIndicatorOwner(frame)
    end
    if not shown then
        ring:Hide()
        return
    end
    ring:ClearAllPoints()
    ring:SetPoint("CENTER", GetIconAnchor(frame) or frame, "TOPRIGHT", -10, -9)
    ring:Show()
end

-- One green MS / OS / M/O badge: shown when `shown`, else hidden.
local function SetSpecLetter(frame, field, shown, letter, kind, small)
    local text = frame[field]
    if not shown then
        if text then
            text.svIndicatorKind = nil
            text:Hide()
        end
        return
    end
    text = EnsureSpecValueIndicator(frame, field)
    text.svIndicatorKind = kind
    SetLetterBadgeFont(text, kind, small and 11 or 13)
    text:SetText("|cff00ff00" .. letter .. "|r")
    RepositionIndicator(frame, text)
    text:Show()
end

local function SetIndicator(frame, state, options)
    if not state then
        if options and options.nativeUpgradeIcon and frame and frame.UpgradeIcon and type(frame.UpgradeIcon.SetShown) == "function" then
            frame.UpgradeIcon:SetShown(false)
        end
        HideFrameIndicators(frame)
        return
    end

    local showUpgrade = state.kind == "upgrade"
    local specRole = state.specRole
    local specLabel = state.specLabel
    if not specRole and (state.kind == "main_spec" or state.kind == "off_spec" or state.kind == "both_specs") then
        specRole = state.kind
        specLabel = state.label or state.text
    end

    -- Upgrade arrow (top-left). Always use StatVerdict's texture so draw-layer
    -- stays above bag icon art (Blizzard UpgradeIcon often sits behind the icon).
    if showUpgrade then
        if options and options.nativeUpgradeIcon and frame.UpgradeIcon and type(frame.UpgradeIcon.SetShown) == "function" then
            -- Keep native hidden; custom arrow is the stable path.
            frame.UpgradeIcon:SetShown(false)
        end
        local overlay = EnsureIndicator(frame)
        overlay.svIndicatorKind = state.kind
        ApplyUpgradeLook(overlay)
        RepositionIndicator(frame, overlay)
        overlay:Show()
    else
        if frame.StatVerdictUpgradeIndicator then
            frame.StatVerdictUpgradeIndicator.svIndicatorKind = nil
            frame.StatVerdictUpgradeIndicator:Hide()
        end
        if options and options.nativeUpgradeIcon and frame.UpgradeIcon and type(frame.UpgradeIcon.SetShown) == "function" then
            frame.UpgradeIcon:SetShown(false)
        end
    end

    -- Green letter badge at the top right: MS or OS; an item in both loadouts shows the gold ring instead (no letters).
    local both = specRole == "both_specs"
    SetSpecLetter(frame, "StatVerdictSpecValueIndicator", specRole == "main_spec", "MS", "main_spec", false)
    SetSpecLetter(frame, "StatVerdictOffSpecIndicator", specRole == "off_spec", "OS", "off_spec", false)
    SetBagRing(frame, both)
end

-- Right-click (no modifier key) on a ring, trinket or one-hand weapon in the bags: the game puts the piece in the first of the
-- two slots, which is not always the piece the tooltip says it beats. Before the click we note which worn piece the
-- comparison names (for the spec that is played); after the game has put the piece on, if it replaced another piece, that
-- piece goes back on in place of the named one. The result is the same whichever slot each piece sits in.
local smartEquipPending = nil
local SMART_EQUIP_WINDOW = 2.5

local function BagAndSlotOfButton(button)
    local bagID = type(button.GetBagID) == "function" and SafeCall(button.GetBagID, button) or nil
    if bagID == nil and type(button.GetParent) == "function" then
        local parent = button:GetParent()
        bagID = parent and type(parent.GetID) == "function" and SafeCall(parent.GetID, parent) or nil
    end
    local slotID = type(button.GetID) == "function" and SafeCall(button.GetID, button) or nil
    return bagID, slotID
end

local function PrepareSmartEquip(button)
    smartEquipPending = nil
    if InCombatLockdown and InCombatLockdown() then return end
    if not (ns.GetBagItemGUID and ns.GetWornItemGUID and ns.BuildComparison and ns.GetComparableSlots
        and ns.ShouldUseEquipmentSnapshot and ns.GetTooltipEvaluationContexts and C_Container) then
        return
    end
    local bagID, bagSlot = BagAndSlotOfButton(button)
    if bagID == nil or bagSlot == nil then return end
    local info = SafeCall(C_Container.GetContainerItemInfo, bagID, bagSlot)
    local itemLink = type(info) == "table" and info.hyperlink or nil
    if not itemLink then return end
    local slots = ns.GetComparableSlots(itemLink)
    if type(slots) ~= "table" or #slots ~= 2 then return end
    local itemGUID = ns.GetBagItemGUID(bagID, bagSlot)
    if not itemGUID then return end

    local primary, secondary = ns.GetTooltipEvaluationContexts()
    local played = nil
    for _, context in ipairs({ primary or false, secondary or false }) do
        if context and context.profile and not ns.ShouldUseEquipmentSnapshot(context.profile) then
            played = context
            break
        end
    end
    if not played then return end

    local comparison = ns.BuildComparison(itemLink, played.profile)
    local selected = comparison and comparison.selected
    local targetSlot = selected and tonumber(selected.slotID) or nil
    if not targetSlot or (targetSlot ~= slots[1] and targetSlot ~= slots[2]) then return end

    local pairGUIDs = {}
    for _, slot in ipairs(slots) do
        local guid = ns.GetWornItemGUID(slot)
        if guid then pairGUIDs[#pairGUIDs + 1] = guid end
    end
    local targetGUID = ns.GetWornItemGUID(targetSlot)
    if #pairGUIDs < 2 or not targetGUID then return end   -- an empty slot: the game fills it, nothing to correct

    smartEquipPending = {
        time = GetTime and GetTime() or 0,
        slots = { slots[1], slots[2] },
        itemGUID = itemGUID,
        targetGUID = targetGUID,
        pairGUIDs = pairGUIDs,
    }
    -- Straight onto the slot the comparison names: one change, nothing else moves. The piece is then on the cursor (locked
    -- in its bag slot), so the game's own right-click that follows has nothing left to put on.
    if ns.EquipBagSlotInto then
        smartEquipPending.direct = ns.EquipBagSlotInto(bagID, bagSlot, targetSlot)
    end
end

local smartEquipToken = 0
local smartEquipFrame = CreateFrame("Frame")
smartEquipFrame:RegisterEvent("PLAYER_EQUIPMENT_CHANGED")
smartEquipFrame:SetScript("OnEvent", function()
    local pending = smartEquipPending
    if not pending then return end
    if (GetTime and GetTime() or 0) - pending.time > SMART_EQUIP_WINDOW then
        smartEquipPending = nil
        return
    end
    -- One change makes several events: act once, a moment after the last.
    smartEquipToken = smartEquipToken + 1
    local token = smartEquipToken
    C_Timer.After(0.35, function()
        if token ~= smartEquipToken then return end
        local p = smartEquipPending
        smartEquipPending = nil
        if not p or (InCombatLockdown and InCombatLockdown()) then return end
        -- Whatever is still on the cursor (the replaced piece) goes back to the bags.
        if CursorHasItem and CursorHasItem() and ClearCursor then ClearCursor() end
        local newSlot, targetSlot = nil, nil
        for _, slot in ipairs(p.slots) do
            local guid = ns.GetWornItemGUID(slot)
            if guid == p.itemGUID then newSlot = slot elseif guid == p.targetGUID then targetSlot = slot end
        end
        if not newSlot or not targetSlot then return end   -- not put on, or the named piece was the one replaced: all good
        -- The game replaced the other piece: it goes back on, in place of the one the comparison named.
        local replaced = nil
        for _, guid in ipairs(p.pairGUIDs) do
            if guid ~= p.targetGUID and guid ~= p.itemGUID then replaced = guid end
        end
        if replaced then
            -- Two steps, so that every piece ends up where it was and the new one takes the place of the named one: the
            -- piece the game replaced goes back where it was (the new one passes through the bags), then the new one is put
            -- on in the place of the named piece.
            local ok, err = ns.EquipBagPieceByGUID(replaced, newSlot)
            if ok then
                C_Timer.After(0.4, function()
                    if InCombatLockdown and InCombatLockdown() then return end
                    local ok2, err2 = ns.EquipBagPieceByGUID(p.itemGUID, targetSlot)
                end)
            end
        end
    end)
end)

local function HookBagButtonApprove(button)
    if not button or button.StatVerdictApproveHooked or type(button.HookScript) ~= "function" then
        return
    end
    button.StatVerdictApproveHooked = true
    button:HookScript("PreClick", function(self, mouseButton)
        if mouseButton ~= "RightButton" and mouseButton ~= "LeftButton" then
            return
        end
        -- A plain right-click (no Alt, Shift or Ctrl) puts a bag piece on: note what the comparison says it replaces.
        if mouseButton == "RightButton" and not (IsAltKeyDown and IsAltKeyDown())
            and not (IsShiftKeyDown and IsShiftKeyDown()) and not (IsControlKeyDown and IsControlKeyDown()) then
            pcall(PrepareSmartEquip, self)
            return
        end
        if not IsAltKeyDown or not IsAltKeyDown() then
            return
        end
        if InCombatLockdown and InCombatLockdown() then
            return
        end

        local preferSecondary = (mouseButton == "LeftButton")
        local primaryContext, secondaryContext = nil, nil
        if ns.GetTooltipEvaluationContexts then
            primaryContext, secondaryContext = ns.GetTooltipEvaluationContexts()
        end
        if ns.IsAutoMarkOn and ns.IsAutoMarkOn() then
            -- Auto mark on: what you wear marks itself, so one Alt-Click (either button) saves the piece for the build that
            -- is not played. With one build only, or a spec that is neither build, there is nothing to save it for.
            if not secondaryContext or not ns.ShouldUseEquipmentSnapshot then
                return
            end
            local primaryPlayed = primaryContext and not ns.ShouldUseEquipmentSnapshot(primaryContext.profile)
            local secondaryPlayed = not ns.ShouldUseEquipmentSnapshot(secondaryContext.profile)
            if primaryPlayed then
                preferSecondary = true
            elseif secondaryPlayed then
                preferSecondary = false
            else
                return
            end
        elseif preferSecondary and not secondaryContext then
            return
        end

        local itemLink = nil
        local bagID = type(self.GetBagID) == "function" and SafeCall(self.GetBagID, self) or nil
        if bagID == nil and type(self.GetParent) == "function" then
            local parent = self:GetParent()
            bagID = parent and type(parent.GetID) == "function" and SafeCall(parent.GetID, parent) or nil
        end
        local slotID = SafeCall(self.GetID, self)
        if bagID ~= nil and slotID ~= nil and C_Container and C_Container.GetContainerItemInfo then
            local itemInfo = SafeCall(C_Container.GetContainerItemInfo, bagID, slotID)
            if type(itemInfo) == "table" then
                itemLink = itemInfo.hyperlink
            end
        end
        itemLink = itemLink or GetFrameItemLink(self)
        if not itemLink or not ns.TryApproveItemLink then
            return
        end
        -- The game's serial number of this very piece, so the mark follows this copy and no other.
        local itemGUID = nil
        if bagID ~= nil and slotID ~= nil and ns.GetBagItemGUID then
            itemGUID = SafeCall(ns.GetBagItemGUID, bagID, slotID)
        end
        ns.TryApproveItemLink(itemLink, nil, preferSecondary, itemGUID, ns.IsAutoMarkOn and ns.IsAutoMarkOn() or false)
    end)
end

local function UpdateItemButton(frame, itemLink, options)
    if not frame then return false end
    if options and options.source == "bags" then
        HookBagButtonApprove(frame)
    end
    if IsEquippedPaperDollItemFrame(frame) then
        HideFrameIndicators(frame)
        return false
    end
    local hasExplicitItemLink = itemLink ~= nil
    local frameUsable = IsFrameVisible(frame)
        or (hasExplicitItemLink and type(frame.IsShown) == "function" and frame:IsShown())
    if not frameUsable then
        HideFrameIndicators(frame)
        return false
    end
    if options and options.clipFrame and not IsFrameInsideClip(frame, options.clipFrame) then
        HideFrameIndicators(frame)
        return false
    end
    itemLink = itemLink or GetFrameItemLink(frame)
    if itemLink then
        local isBag = IsBagItemFrame(frame) or (options and options.source == "bags")
        local stateOptions = options
        if isBag and (not options or options.source ~= "bags") then
            stateOptions = {
                source = "bags",
                nativeUpgradeIcon = options and options.nativeUpgradeIcon,
                allowValueIndicator = options and options.allowValueIndicator,
            }
        end
        local state = ns.GetUpgradeIndicatorItemState and ns.GetUpgradeIndicatorItemState(itemLink, stateOptions) or nil
        SetIndicator(frame, state, options)
        return true
    end
    HideFrameIndicators(frame)
    return false
end

function ns.UpdateUpgradeIndicatorFrame(frame, itemLink, options)
    return UpdateItemButton(frame, itemLink, options)
end

function ns.RegisterUpgradeIndicatorSource(name, scanner)
    if type(name) ~= "string" or name == "" or type(scanner) ~= "function" then
        return
    end
    indicatorSources[name] = scanner
end

local function ScanRegisteredSources()
    local total = 0
    local sourceCount = 0
    for name, scanner in pairs(indicatorSources) do
        sourceCount = sourceCount + 1
        local ok, count = pcall(scanner)
        count = ok and tonumber(count) or 0
        total = total + count
    end
    return total
end

local function ScanNamedButtonSeries(prefix, maxIndex)
    local count = 0
    local seen = 0
    for index = 1, maxIndex do
        local button = _G[prefix .. index]
        if button and IsFrameVisible(button) then
            seen = seen + 1
            if UpdateItemButton(button, nil, { allowValueIndicator = true, nativeUpgradeIcon = true, source = "bags" }) then
                count = count + 1
            end
        end
    end
    return count
end

local function UpdateBagItemButton(button)
    if not button or button.isExtended then return false end
    HookBagButtonApprove(button)
    local itemLink = nil
    local itemGUID = nil   -- the game's serial number of the piece in this slot (tells two copies of one item apart)
    if C_Container and C_Container.GetContainerItemInfo and type(button.GetID) == "function" then
        local bagID = type(button.GetBagID) == "function" and SafeCall(button.GetBagID, button) or nil
        if bagID == nil and type(button.GetParent) == "function" then
            local parent = button:GetParent()
            bagID = parent and type(parent.GetID) == "function" and SafeCall(parent.GetID, parent) or nil
        end
        local slotID = SafeCall(button.GetID, button)
        if bagID ~= nil and slotID ~= nil then
            local itemInfo = SafeCall(C_Container.GetContainerItemInfo, bagID, slotID)
            if type(itemInfo) == "table" then
                itemLink = itemInfo.hyperlink
                if not itemInfo.stackCount then
                    itemLink = nil
                end
                if itemLink and ns.GetBagItemGUID then
                    itemGUID = SafeCall(ns.GetBagItemGUID, bagID, slotID)
                end
            end
        end
    end
    itemLink = itemLink or GetFrameItemLink(button)
    if not itemLink then
        if button.UpgradeIcon and type(button.UpgradeIcon.SetShown) == "function" then
            button.UpgradeIcon:SetShown(false)
        end
        HideFrameIndicators(button)
        button.StatVerdictLastCheckedRefresh = nil
        button.StatVerdictLastCheckedItemLink = nil
        return false
    end
    -- Always refresh when cache is invalidated to prevent stale state
    if clearDecisionCacheOnNextScan then
        button.StatVerdictLastCheckedRefresh = nil
        button.StatVerdictLastCheckedItemLink = nil
    elseif button.StatVerdictLastCheckedRefresh == bagRefreshCounter and button.StatVerdictLastCheckedItemLink == itemLink
        and button.StatVerdictLastCheckedGUID == itemGUID then
        return true
    end
    -- The slot counts as checked only once it was really painted: a button that was not visible yet (the bag opened very
    -- fast) must be tried again on the next pass, not skipped for ever.
    local painted = UpdateItemButton(button, itemLink, { allowValueIndicator = true, nativeUpgradeIcon = true, source = "bags", itemGUID = itemGUID })
    if painted then
        button.StatVerdictLastCheckedRefresh = bagRefreshCounter
        button.StatVerdictLastCheckedItemLink = itemLink
        button.StatVerdictLastCheckedGUID = itemGUID
    else
        button.StatVerdictLastCheckedRefresh = nil
        button.StatVerdictLastCheckedItemLink = nil
        button.StatVerdictLastCheckedGUID = nil
    end
    return painted
end

local function UpdateContainerFrameUpgradeIcons(container)
    if not container or not IsFrameVisible(container) then return 0 end
    local count = 0
    if type(container.EnumerateValidItems) == "function" then
        for _, itemButton in container:EnumerateValidItems() do
            if UpdateBagItemButton(itemButton) then
                count = count + 1
            end
        end
        return count
    end

    local prefix = type(container.GetName) == "function" and container:GetName() or nil
    local size = tonumber(container.size) or 0
    if prefix and size > 0 then
        for index = 1, size do
            if UpdateBagItemButton(_G[prefix .. "Item" .. index]) then
                count = count + 1
            end
        end
    end
    return count
end

local function ScanBagButtons()
    local count = 0
    if _G.ContainerFrameCombinedBags and IsFrameVisible(_G.ContainerFrameCombinedBags) then
        count = count + UpdateContainerFrameUpgradeIcons(_G.ContainerFrameCombinedBags)
    end
    for frameIndex = 1, NUM_CONTAINER_SCAN_FRAMES do
        local container = _G["ContainerFrame" .. frameIndex]
        if container and IsFrameVisible(container) then
            count = count + UpdateContainerFrameUpgradeIcons(container)
        end
    end
    if count == 0 then
        count = count + ScanNamedButtonSeries("ContainerFrameCombinedBagsItem", 220)
        count = count + ScanNamedButtonSeries("ContainerFrameCombinedBagsItemButton", 220)
        for frameIndex = 1, NUM_CONTAINER_SCAN_FRAMES do
            count = count + ScanNamedButtonSeries("ContainerFrame" .. frameIndex .. "Item", 80)
        end
    end
    return count
end

local function AnyKnownContainerVisible()
    if IsFrameVisible(_G.ContainerFrameCombinedBags) then
        return true
    end
    for index = 1, NUM_CONTAINER_SCAN_FRAMES do
        if IsFrameVisible(_G["ContainerFrame" .. index]) then
            return true
        end
    end
    return false
end

local function ScanVisibleItemFrames(kind)
    -- Arrows are updated in place (each slot sets or clears its own arrow); nothing is
    -- wiped first, so arrows never blink. Hidden windows hide their own arrows.
    if clearDecisionCacheOnNextScan and ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
        clearDecisionCacheOnNextScan = false
        -- Every slot remembers the item it last showed; after a change (an Alt-click save, a swap, a
        -- new spec) that memory is stale, so this scan must repaint every slot.
        bagRefreshCounter = bagRefreshCounter + 1
    end

    -- The whole scan shares one set of evaluation contexts instead of rebuilding them per item.
    ns.BeginContextScan()
    local ok, err = pcall(function()
        if AnyKnownContainerVisible() then
            ScanBagButtons()
        end

        if kind == "full" then
            ScanRegisteredSources()
        end
    end)
    ns.EndContextScan()
    if not ok then error(err, 0) end
end

local function RunPendingRefresh()
    timerActive = false
    if InCombatLockdown and InCombatLockdown() then
        waitingForCombatEnd = true
        return
    end
    local kind = pendingKind or "bags"
    pendingKind = nil
    lastRefreshAt = GetTime and GetTime() or 0
    ScanVisibleItemFrames(kind)
end

function ns.RefreshUpgradeIndicators(kind, delay)
    if kind == "full" or pendingKind == nil then
        pendingKind = kind == "full" and "full" or (pendingKind or "bags")
    end
    if timerActive then
        return
    end
    timerActive = true
    delay = delay or REFRESH_DELAY
    local now = GetTime and GetTime() or 0
    local sinceLast = now - lastRefreshAt
    if now > 0 and sinceLast < MIN_REFRESH_INTERVAL then
        delay = math.max(delay, MIN_REFRESH_INTERVAL - sinceLast)
    end
    C_Timer.After(delay, RunPendingRefresh)
end

function ns.ForceUpgradeIndicatorRefreshNow(kind)
    clearDecisionCacheOnNextScan = true
    if ns.ClearUpgradeIndicatorDecisionCache then
        ns.ClearUpgradeIndicatorDecisionCache()
    end
    pendingKind = nil
    lastRefreshAt = GetTime and GetTime() or 0
    if InCombatLockdown and InCombatLockdown() then
        waitingForCombatEnd = true
        pendingKind = kind == "bags" and "bags" or "full"
        return
    end
    ScanVisibleItemFrames(kind == "bags" and "bags" or "full")
end

function ns.InvalidateUpgradeIndicatorDecisionCache()
    clearDecisionCacheOnNextScan = true
end

local function ScheduleRefresh(kind)
    ns.RefreshUpgradeIndicators(kind == "full" and "full" or "bags")
end

local hookedShowFrames = {}

local function HookFrameShow(frame)
    if not frame or hookedShowFrames[frame] or type(frame.HookScript) ~= "function" then
        return
    end
    hookedShowFrames[frame] = true
    frame:HookScript("OnShow", function()
        ScheduleRefresh("bags")
        -- Paint the marks at once when a bag opens (the scheduled pass above stays as the safety net), so they do not
        -- appear a moment after the items. Never in combat; a failure here must not disturb the bag.
        if not (InCombatLockdown and InCombatLockdown()) then
            pcall(ScanVisibleItemFrames, "bags")
        end
    end)
end

local function HookKnownContainerShows()
    HookFrameShow(_G.ContainerFrameCombinedBags)
    for index = 1, NUM_CONTAINER_SCAN_FRAMES do
        HookFrameShow(_G["ContainerFrame" .. index])
    end
end

-- One gold mark, in the middle of a piece the player wears, on the character sheet (the inspect window is not touched):
--   the letters BIS = the piece is in the Best in Slot list; CAT = the Catalyst would turn it into the Best in Slot set
--   piece (so it says Best in Slot as well); a thin gold ring with two arrows (a picture, Textures/SharedRing2) = the piece is
--   in both builds' loadouts. Both facts at once: the letters inside the ring. No dark fill behind either.
--   Everything is protected: a failure here must never break the character sheet.

local RING_SIZE = 31              -- the ring around the letters; the ring alone is the same size
local LETTERS_SIZE_IN_RING = 10   -- the letters fit inside the ring
local LETTERS_SIZE_ALONE = 12
local WORN_MARK_SLOTS = {
    "CharacterHeadSlot", "CharacterNeckSlot", "CharacterShoulderSlot", "CharacterBackSlot", "CharacterChestSlot",
    "CharacterWristSlot", "CharacterHandsSlot", "CharacterWaistSlot", "CharacterLegsSlot", "CharacterFeetSlot",
    "CharacterFinger0Slot", "CharacterFinger1Slot", "CharacterTrinket0Slot", "CharacterTrinket1Slot",
    "CharacterMainHandSlot", "CharacterSecondaryHandSlot",
}

local function EnsureWornMark(frame, field, size, text, point, x, y)
    local mark = frame[field]
    if not mark then
        mark = frame:CreateFontString(nil, "OVERLAY")
        if type(mark.SetDrawLayer) == "function" then mark:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL) end
        mark:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", size, "OUTLINE")
        mark:SetText(text)
        mark:SetPoint(point, GetIconAnchor(frame) or frame, point, x, y)
        frame[field] = mark
    end
    return mark
end

local function SetSharedMark(frame, shown)
    local mark = frame.StatVerdictSharedMark
    if not mark then
        if not shown then return end
        mark = frame:CreateTexture(nil, "OVERLAY")
        -- (the game accepts draw sublevels from -8 to 7 only: one more is an error)
        if type(mark.SetDrawLayer) == "function" then mark:SetDrawLayer("OVERLAY", INDICATOR_DRAW_SUBLEVEL) end
        frame.StatVerdictSharedMark = mark
    end
    mark:SetTexture(SHARED_TEXTURE)
    if not shown then
        mark:Hide()
        return
    end
    mark:ClearAllPoints()
    mark:SetSize(RING_SIZE, RING_SIZE)
    mark:SetPoint("CENTER", GetIconAnchor(frame) or frame, "CENTER", 0, 0)
    mark:Show()
end

-- The letters get smaller when they sit inside the ring. The CAT letters (bold) are the same size as BIS but have a thick
-- outline: they say something has to be done (the Catalyst turns the piece into Best in Slot), so they must be seen at once.
local CAT_SIZE_ALONE = LETTERS_SIZE_ALONE       -- the same size as BIS: it must stay inside the ring
local CAT_SIZE_IN_RING = LETTERS_SIZE_IN_RING
local function SetLettersSize(mark, inRing, bold)
    if type(mark.SetFont) ~= "function" then return end
    local size = inRing and LETTERS_SIZE_IN_RING or LETTERS_SIZE_ALONE
    if bold then size = inRing and CAT_SIZE_IN_RING or CAT_SIZE_ALONE end
    mark:SetFont(STANDARD_TEXT_FONT or "Fonts\\FRIZQT__.TTF", size, bold and "THICKOUTLINE" or "OUTLINE")
end

-- The red arrow pointing down in the corner of a worn piece: a better piece for the spec that is played is in the bags.
-- (The bags' own green arrow, turned over and made red: no new picture.)
-- A click on the arrow says "I know, it is my choice": the warning of that slot goes away (see ns.IgnoreWornWarning).
local function SetWornDownArrow(frame, entry)
    local button = frame.StatVerdictWornDownArrow
    if not button then
        if not entry then return end
        button = CreateFrame("Button", nil, frame)
        button:SetSize(20, 20)
        button:SetFrameLevel((frame:GetFrameLevel() or 1) + 6)
        button.arrow = button:CreateTexture(nil, "OVERLAY")
        button.arrow:SetAllPoints(button)
        button.arrow:SetTexture(UPGRADE_ARROW_TEXTURE)
        if type(button.arrow.SetRotation) == "function" then button.arrow:SetRotation(math.pi) end
        -- The bags' arrow is green: red on top of green would be dark. Take its colour away first, then paint it red.
        if type(button.arrow.SetDesaturated) == "function" then button.arrow:SetDesaturated(true) end
        button.arrow:SetVertexColor(1, 0, 0, 1)
        -- A second, identical arrow laid on top makes the red twice as strong.
        button.arrow2 = button:CreateTexture(nil, "OVERLAY", nil, 2)
        button.arrow2:SetAllPoints(button)
        button.arrow2:SetTexture(UPGRADE_ARROW_TEXTURE)
        if type(button.arrow2.SetRotation) == "function" then button.arrow2:SetRotation(math.pi) end
        if type(button.arrow2.SetDesaturated) == "function" then button.arrow2:SetDesaturated(true) end
        button.arrow2:SetVertexColor(1, 0, 0, 1)
        button:SetScript("OnClick", function(self)
            if ns.IgnoreWornWarning and ns.IgnoreWornWarning(self.svSlot) then
                if ns.RefreshCatalystMarks then ns.RefreshCatalystMarks() end
            end
        end)
        button:SetScript("OnEnter", function(self)
            GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
            -- Only what it is and what the click does: the piece itself is named on the worn piece's own tooltip.
            GameTooltip:AddLine("Better in your bags", 1, 1, 1)
            GameTooltip:AddLine("Click the arrow to ignore this: it is your choice.", 0.6, 0.6, 0.6)
            GameTooltip:Show()
        end)
        button:SetScript("OnLeave", function() GameTooltip:Hide() end)
        frame.StatVerdictWornDownArrow = button
    end
    if not entry then
        button:Hide()
        return
    end
    button.svSlot = frame:GetID()
    button.svEntry = entry
    button:ClearAllPoints()
    button:SetPoint("CENTER", GetIconAnchor(frame) or frame, "TOPRIGHT", -8, -8)
    button:Show()
end

-- info: ns.GetWornPieceInfo(link) of the piece, or nil.
local function SetWornMarks(frame, info, tag)
    if not frame then return end
    local gain = info and not info.bis and info.gain or nil
    local inRing = (info and info.shared) and true or false
    if gain then
        local mark = EnsureWornMark(frame, "StatVerdictCatalystMark", LETTERS_SIZE_ALONE, "|cffffd200CAT|r", "CENTER", 0, 0)
        SetLettersSize(mark, inRing, true)
        mark:Show()
        -- The same word once more, a pixel to the right: the strokes of the letters get thicker (the font has no bold).
        local twin = EnsureWornMark(frame, "StatVerdictCatalystMarkBold", LETTERS_SIZE_ALONE, "|cffffd200CAT|r", "CENTER", 1, 0)
        SetLettersSize(twin, inRing, true)
        twin:Show()
    else
        if frame.StatVerdictCatalystMark then frame.StatVerdictCatalystMark:Hide() end
        if frame.StatVerdictCatalystMarkBold then frame.StatVerdictCatalystMarkBold:Hide() end
    end
    if info and info.bis then
        local mark = EnsureWornMark(frame, "StatVerdictBisMark", LETTERS_SIZE_ALONE, "", "CENTER", 0, 0)
        mark:SetText("|cffffd200" .. tostring(tag or "BIS") .. "|r")
        SetLettersSize(mark, inRing)
        mark:Show()
    elseif frame.StatVerdictBisMark then
        frame.StatVerdictBisMark:Hide()
    end
    SetSharedMark(frame, inRing)
end

local function RefreshCatalystMarks()
    -- The marks live on the character sheet only: while it is closed there is nothing to draw (the sheet's OnShow asks again).
    local sheet = _G.PaperDollFrame
    if sheet and not IsFrameVisible(sheet) then return true end
    local ok = pcall(function()
        if not (ns.GetTooltipEvaluationContexts and ns.GetWornPieceInfo and GetInventoryItemLink) then return end
        local context = ns.GetTooltipEvaluationContexts()
        local profile = type(context) == "table" and context.profile or nil
        -- Options > Marks on the character sheet: off means no marks at all (saved choice, on when never set).
        local db = _G.StatVerdictDB
        if type(db) == "table" and db.showCharacterMarks == false then profile = nil end
        local wording = ns.GetReferenceWording and ns.GetReferenceWording(profile and profile.goal) or nil
        -- The red arrow has its own option (on when never set); a better piece in the bags, per slot.
        local arrowOn = not (type(db) == "table" and db.showWornDownArrow == false)
        local betterInBags = arrowOn and ns.GetBagUpgradesForWornSlots and ns.GetBagUpgradesForWornSlots() or nil
        for _, name in ipairs(WORN_MARK_SLOTS) do
            local frame = _G[name]
            if frame and type(frame.GetID) == "function" then
                -- Each slot on its own: a problem with one piece must not stop the marks of the others.
                pcall(function()
                    local info = nil
                    if profile and IsFrameVisible(frame) then
                        local link = GetInventoryItemLink("player", frame:GetID())
                        local wornGUID = link and ns.GetWornItemGUID and ns.GetWornItemGUID(frame:GetID()) or nil
                        info = link and ns.GetWornPieceInfo(link, wornGUID) or nil
                    end
                    local entry = betterInBags and IsFrameVisible(frame) and betterInBags[frame:GetID()] or nil
                    if entry and entry.ignored then entry = nil end
                    -- While the arrow warns about the piece, the "also in the other set" ring is not shown on it.
                    if entry and info and info.shared then
                        local copy = {}
                        for key, value in pairs(info) do copy[key] = value end
                        copy.shared = nil
                        info = (copy.bis or copy.gain) and copy or nil
                    end
                    SetWornMarks(frame, info, wording and wording.tag)
                    SetWornDownArrow(frame, entry)
                end)
            end
        end
    end)
    return ok
end
ns.RefreshCatalystMarks = RefreshCatalystMarks

-- Events come in bursts (bag changes, item data): every one asked for its own redraw, 15-30 ms each. One redraw answers
-- the whole burst; it happens after the last request of the burst was made, so it sees what is true then.
local catalystMarksPending = false
local function RequestCatalystMarks(delay)
    if catalystMarksPending then return end
    catalystMarksPending = true
    C_Timer.After(delay or 0.2, function()
        catalystMarksPending = false
        RefreshCatalystMarks()
    end)
end
ns.RequestCatalystMarks = RequestCatalystMarks

local catalystMarkHooked = false
local function HookCatalystMarks()
    if catalystMarkHooked then return end
    local sheet = _G.PaperDollFrame
    if sheet and type(sheet.HookScript) == "function" then
        catalystMarkHooked = true
        sheet:HookScript("OnShow", function() RequestCatalystMarks(0.2) end)
    end
end

scanFrame = CreateFrame("Frame")
local function RegisterEventSafe(eventName)
    local ok = pcall(scanFrame.RegisterEvent, scanFrame, eventName)
    return ok
end

RegisterEventSafe("PLAYER_LOGIN")
RegisterEventSafe("PLAYER_EQUIPMENT_CHANGED")
RegisterEventSafe("BAG_UPDATE_DELAYED")
RegisterEventSafe("BAG_NEW_ITEMS_UPDATED")
RegisterEventSafe("PLAYER_REGEN_ENABLED")
RegisterEventSafe("GET_ITEM_INFO_RECEIVED")
local function AnyArrowWindowVisible()
    if AnyKnownContainerVisible() then
        return true
    end
    for _, name in ipairs({ "MerchantFrame", "QuestFrame", "QuestInfoFrame", "EncounterJournal" }) do
        local skip = name == "EncounterJournal" and ns.IsAdventureGuideMarksEnabled and not ns.IsAdventureGuideMarksEnabled()
        if not skip and IsFrameVisible(_G[name]) then
            return true
        end
    end
    return false
end

scanFrame:SetScript("OnEvent", function(_, event)
    HookKnownContainerShows()
    HookCatalystMarks()
    -- The gear or the bags changed: what the bags hold against the worn pieces has to be worked out again.
    if event == "PLAYER_EQUIPMENT_CHANGED" and ns.PruneIgnoredWornWarnings then
        ns.PruneIgnoredWornWarnings()
    end
    if (event == "PLAYER_EQUIPMENT_CHANGED" or event == "BAG_UPDATE_DELAYED") and ns.ClearWornUpgradeCache then
        ns.ClearWornUpgradeCache()
    end
    if (event == "PLAYER_EQUIPMENT_CHANGED" or event == "GET_ITEM_INFO_RECEIVED" or event == "BAG_UPDATE_DELAYED")
        and IsFrameVisible(_G.PaperDollFrame) then
        RequestCatalystMarks(0.5)
    end
    if event == "PLAYER_REGEN_ENABLED" then
        if waitingForCombatEnd then
            waitingForCombatEnd = false
            ScheduleRefresh(pendingKind == "full" and "full" or "bags")
        end
        return
    end
    if event == "GET_ITEM_INFO_RECEIVED" then
        -- Item data arrives in bursts; only care while a window with arrows is open,
        -- and answer a whole burst with one late refresh.
        if AnyArrowWindowVisible() then
            clearDecisionCacheOnNextScan = true
            bagRefreshCounter = bagRefreshCounter + 1
            ns.RefreshUpgradeIndicators("full", ITEM_INFO_DELAY)
        end
        return
    end
    if event == "PLAYER_EQUIPMENT_CHANGED" then
        clearDecisionCacheOnNextScan = true
        bagRefreshCounter = bagRefreshCounter + 1
        ns.RefreshUpgradeIndicators("full", 0.5)
        return
    end
    if event == "PLAYER_LOGIN" then
        ScheduleRefresh("full")
        return
    end
    ScheduleRefresh("bags")
end)

if hooksecurefunc then
    -- Coalesce all container paint hooks into one throttled ScheduleRefresh.
    -- Per-UpdateItems timers used to stack and re-evaluate every slot repeatedly.
    if ContainerFrameMixin and type(ContainerFrameMixin.UpdateItems) == "function" then
        hooksecurefunc(ContainerFrameMixin, "UpdateItems", function()
            ScheduleRefresh("bags")
        end)
    end
    if _G.ContainerFrameCombinedBags and type(_G.ContainerFrameCombinedBags.UpdateItems) == "function" then
        hooksecurefunc(_G.ContainerFrameCombinedBags, "UpdateItems", function()
            ScheduleRefresh("bags")
        end)
    end
    for index = 1, NUM_CONTAINER_SCAN_FRAMES do
        local container = _G["ContainerFrame" .. index]
        if container and type(container.UpdateItems) == "function" then
            hooksecurefunc(container, "UpdateItems", function()
                ScheduleRefresh("bags")
            end)
        end
    end
    if type(ContainerFrame_Update) == "function" then
        hooksecurefunc("ContainerFrame_Update", function() ScheduleRefresh("bags") end)
    end
    if type(ContainerFrame_UpdateItems) == "function" then
        hooksecurefunc("ContainerFrame_UpdateItems", function() ScheduleRefresh("bags") end)
    end
    for _, functionName in ipairs({ "ToggleAllBags", "OpenAllBags", "CloseAllBags", "ToggleBag", "OpenBag", "CloseBag", "ToggleBackpack", "OpenBackpack", "CloseBackpack" }) do
        if type(_G[functionName]) == "function" then
            hooksecurefunc(functionName, function()
                HookKnownContainerShows()
                ScheduleRefresh("bags")
            end)
        end
    end
end

if C_Timer then
    C_Timer.After(0.50, function()
        HookKnownContainerShows()
        ScheduleRefresh("full")
    end)
end
