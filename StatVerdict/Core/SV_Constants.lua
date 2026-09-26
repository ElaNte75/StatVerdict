local addonName, ns = ...

-- Public folder = "StatVerdict". Development folder = "StatVerdict_Dev".
-- Both can be installed at once; Dev uses distinct global UI names / slash cmds when needed.
ns.ADDON_FOLDER = addonName
ns.IS_DEV_BUILD = (addonName == "StatVerdict_Dev")
ns.UI_PREFIX = ns.IS_DEV_BUILD and "StatVerdictDev" or "StatVerdict"

function ns.UIName(name)
    name = tostring(name or "")
    if name == "" then
        return ns.UI_PREFIX
    end
    if string.sub(name, 1, 11) == "StatVerdict" then
        if ns.IS_DEV_BUILD then
            return "StatVerdictDev" .. string.sub(name, 12)
        end
        return name
    end
    return ns.UI_PREFIX .. name
end

function ns.IsPublicStatVerdictLoaded()
    if not ns.IS_DEV_BUILD then
        return true
    end
    if C_AddOns and C_AddOns.IsAddOnLoaded then
        local ok, loaded = pcall(C_AddOns.IsAddOnLoaded, "StatVerdict")
        return ok and loaded and true or false
    end
    return false
end

-- Midnight (12.0+) secret values: combat APIs may return numbers that cannot be
-- compared or used in arithmetic while addon execution is tainted. Convert to a
-- plain number when accessible; otherwise return nil so callers can fall back.
function ns.SanitizeStatVerdictNumber(value)
    if value == nil then
        return nil
    end
    if type(issecretvalue) == "function" and issecretvalue(value) then
        if type(canaccessvalue) ~= "function" or not canaccessvalue(value) then
            return nil
        end
    end
    local ok, plain = pcall(function()
        local n = tonumber(value)
        if n == nil then return nil end
        if n ~= n then return nil end
        return n + 0
    end)
    if not ok or type(plain) ~= "number" then
        return nil
    end
    if type(issecretvalue) == "function" and issecretvalue(plain) then
        if type(canaccessvalue) ~= "function" or not canaccessvalue(plain) then
            return nil
        end
    end
    return plain
end

ns.Colors = {
    green = "|cff00ff00",
    red = "|cffff4040",
    yellow = "|cffffd76a",
    white = "|cffffffff",
    reset = "|r",
}

ns.StatNames = {
    STATVERDICT_ITEM_LEVEL = "Item Level",
    ITEM_MOD_AGILITY_SHORT = "Agility",
    ITEM_MOD_INTELLECT_SHORT = "Intellect",
    ITEM_MOD_STRENGTH_SHORT = "Strength",
    ITEM_MOD_STAMINA_SHORT = "Stamina",
    ITEM_MOD_CRIT_RATING_SHORT = "Critical Strike",
    ITEM_MOD_HASTE_RATING_SHORT = "Haste",
    ITEM_MOD_MASTERY_RATING_SHORT = "Mastery",
    ITEM_MOD_VERSATILITY = "Versatility",
    ITEM_MOD_LIFESTEAL = "Leech",
    ITEM_MOD_AVOIDANCE_RATING_SHORT = "Avoidance",
    ITEM_MOD_SPEED = "Speed",
    ITEM_MOD_SPEED_SHORT = "Speed",
    STATVERDICT_ARMOR = "Armor",
    STATVERDICT_MAIN_HAND_DPS = "Main Hand DPS",
    STATVERDICT_OFF_HAND_DPS = "Off Hand DPS",
    STATVERDICT_PRISMATIC_SOCKET = "Empty Prismatic Socket",
}

ns.InventorySlotByEquipLocation = {
    INVTYPE_HEAD = INVSLOT_HEAD,
    INVTYPE_NECK = INVSLOT_NECK,
    INVTYPE_SHOULDER = INVSLOT_SHOULDER,
    INVTYPE_CHEST = INVSLOT_CHEST,
    INVTYPE_ROBE = INVSLOT_CHEST,
    INVTYPE_WAIST = INVSLOT_WAIST,
    INVTYPE_LEGS = INVSLOT_LEGS,
    INVTYPE_FEET = INVSLOT_FEET,
    INVTYPE_WRIST = INVSLOT_WRIST,
    INVTYPE_HAND = INVSLOT_HAND,
    INVTYPE_FINGER = INVSLOT_FINGER1,
    INVTYPE_TRINKET = INVSLOT_TRINKET1,
    INVTYPE_CLOAK = INVSLOT_BACK,
    INVTYPE_WEAPON = INVSLOT_MAINHAND,
    INVTYPE_SHIELD = INVSLOT_OFFHAND,
    INVTYPE_2HWEAPON = INVSLOT_MAINHAND,
    INVTYPE_WEAPONMAINHAND = INVSLOT_MAINHAND,
    INVTYPE_WEAPONOFFHAND = INVSLOT_OFFHAND,
    INVTYPE_HOLDABLE = INVSLOT_OFFHAND,
    INVTYPE_RANGED = INVSLOT_MAINHAND,
    INVTYPE_RANGEDRIGHT = INVSLOT_MAINHAND,
}

ns.MultiSlotByEquipLocation = {
    INVTYPE_FINGER = { INVSLOT_FINGER1, INVSLOT_FINGER2 },
    INVTYPE_TRINKET = { INVSLOT_TRINKET1, INVSLOT_TRINKET2 },
}

ns.SlotLabels = {
    [INVSLOT_HEAD] = "Head",
    [INVSLOT_NECK] = "Neck",
    [INVSLOT_SHOULDER] = "Shoulder",
    [INVSLOT_CHEST] = "Chest",
    [INVSLOT_WAIST] = "Waist",
    [INVSLOT_LEGS] = "Legs",
    [INVSLOT_FEET] = "Feet",
    [INVSLOT_WRIST] = "Wrist",
    [INVSLOT_HAND] = "Hands",
    [INVSLOT_FINGER1] = "Ring 1",
    [INVSLOT_FINGER2] = "Ring 2",
    [INVSLOT_TRINKET1] = "Trinket 1",
    [INVSLOT_TRINKET2] = "Trinket 2",
    [INVSLOT_BACK] = "Back",
    [INVSLOT_MAINHAND] = "Main Hand",
    [INVSLOT_OFFHAND] = "Off Hand",
}

