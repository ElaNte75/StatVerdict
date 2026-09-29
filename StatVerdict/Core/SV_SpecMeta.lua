local addonName, ns = ...
ns = ns or {}

local SPEC_KEY_BY_SPEC_ID = {
    [250] = "DEATHKNIGHT_BLOOD", [251] = "DEATHKNIGHT_FROST", [252] = "DEATHKNIGHT_UNHOLY",
    [577] = "DEMONHUNTER_HAVOC", [581] = "DEMONHUNTER_VENGEANCE", [1480] = "DEMONHUNTER_DEVOURER",
    [102] = "DRUID_BALANCE", [103] = "DRUID_FERAL", [104] = "DRUID_GUARDIAN", [105] = "DRUID_RESTORATION",
    [1467] = "EVOKER_DEVASTATION", [1468] = "EVOKER_PRESERVATION", [1473] = "EVOKER_AUGMENTATION",
    [253] = "HUNTER_BEAST_MASTERY", [254] = "HUNTER_MARKSMANSHIP", [255] = "HUNTER_SURVIVAL",
    [62] = "MAGE_ARCANE", [63] = "MAGE_FIRE", [64] = "MAGE_FROST",
    [268] = "MONK_BREWMASTER", [270] = "MONK_MISTWEAVER", [269] = "MONK_WINDWALKER",
    [65] = "PALADIN_HOLY", [66] = "PALADIN_PROTECTION", [70] = "PALADIN_RETRIBUTION",
    [256] = "PRIEST_DISCIPLINE", [257] = "PRIEST_HOLY", [258] = "PRIEST_SHADOW",
    [259] = "ROGUE_ASSASSINATION", [260] = "ROGUE_OUTLAW", [261] = "ROGUE_SUBTLETY",
    [262] = "SHAMAN_ELEMENTAL", [263] = "SHAMAN_ENHANCEMENT", [264] = "SHAMAN_RESTORATION",
    [265] = "WARLOCK_AFFLICTION", [266] = "WARLOCK_DEMONOLOGY", [267] = "WARLOCK_DESTRUCTION",
    [71] = "WARRIOR_ARMS", [72] = "WARRIOR_FURY", [73] = "WARRIOR_PROTECTION",
}
local SPEC_ID_BY_KEY = {}
for specID, specKey in pairs(SPEC_KEY_BY_SPEC_ID) do
    SPEC_ID_BY_KEY[specKey] = specID
end
local ROLE_BY_SPEC_ID = {
    [250] = "TANK", [251] = "DAMAGER", [252] = "DAMAGER",
    [577] = "DAMAGER", [581] = "TANK", [1480] = "DAMAGER",
    [102] = "DAMAGER", [103] = "DAMAGER", [104] = "TANK", [105] = "HEALER",
    [1467] = "DAMAGER", [1468] = "HEALER", [1473] = "DAMAGER",
    [253] = "DAMAGER", [254] = "DAMAGER", [255] = "DAMAGER",
    [62] = "DAMAGER", [63] = "DAMAGER", [64] = "DAMAGER",
    [268] = "TANK", [269] = "DAMAGER", [270] = "HEALER",
    [65] = "HEALER", [66] = "TANK", [70] = "DAMAGER",
    [256] = "HEALER", [257] = "HEALER", [258] = "DAMAGER",
    [259] = "DAMAGER", [260] = "DAMAGER", [261] = "DAMAGER",
    [262] = "DAMAGER", [263] = "DAMAGER", [264] = "HEALER",
    [265] = "DAMAGER", [266] = "DAMAGER", [267] = "DAMAGER",
    [71] = "DAMAGER", [72] = "DAMAGER", [73] = "TANK",
}
local SPEC_NAME_BY_KEY = {
    DEATHKNIGHT_BLOOD = "Blood", DEATHKNIGHT_FROST = "Frost", DEATHKNIGHT_UNHOLY = "Unholy",
    DEMONHUNTER_HAVOC = "Havoc", DEMONHUNTER_VENGEANCE = "Vengeance", DEMONHUNTER_DEVOURER = "Devourer",
    DRUID_BALANCE = "Balance", DRUID_FERAL = "Feral", DRUID_GUARDIAN = "Guardian", DRUID_RESTORATION = "Restoration",
    EVOKER_DEVASTATION = "Devastation", EVOKER_PRESERVATION = "Preservation", EVOKER_AUGMENTATION = "Augmentation",
    HUNTER_BEAST_MASTERY = "Beast Mastery", HUNTER_MARKSMANSHIP = "Marksmanship", HUNTER_SURVIVAL = "Survival",
    MAGE_ARCANE = "Arcane", MAGE_FIRE = "Fire", MAGE_FROST = "Frost",
    MONK_BREWMASTER = "Brewmaster", MONK_MISTWEAVER = "Mistweaver", MONK_WINDWALKER = "Windwalker",
    PALADIN_HOLY = "Holy", PALADIN_PROTECTION = "Protection", PALADIN_RETRIBUTION = "Retribution",
    PRIEST_DISCIPLINE = "Discipline", PRIEST_HOLY = "Holy", PRIEST_SHADOW = "Shadow",
    ROGUE_ASSASSINATION = "Assassination", ROGUE_OUTLAW = "Outlaw", ROGUE_SUBTLETY = "Subtlety",
    SHAMAN_ELEMENTAL = "Elemental", SHAMAN_ENHANCEMENT = "Enhancement", SHAMAN_RESTORATION = "Restoration",
    WARLOCK_AFFLICTION = "Affliction", WARLOCK_DEMONOLOGY = "Demonology", WARLOCK_DESTRUCTION = "Destruction",
    WARRIOR_ARMS = "Arms", WARRIOR_FURY = "Fury", WARRIOR_PROTECTION = "Protection",
}

local HERO_OPTIONS_BY_SPEC_ID = {
    [250] = { "Deathbringer", "San'layn" },
    [251] = { "Deathbringer", "Rider of the Apocalypse" },
    [252] = { "San'layn", "Rider of the Apocalypse" },
    [577] = { "Aldrachi Reaver", "Fel-Scarred" },
    [581] = { "Aldrachi Reaver", "Annihilator" },
    [1480] = { "Annihilator", "Void-Scarred" },
    [102] = { "Keeper of the Grove", "Elune's Chosen" },
    [103] = { "Druid of the Claw", "Wildstalker" },
    [104] = { "Druid of the Claw", "Elune's Chosen" },
    [105] = { "Keeper of the Grove", "Wildstalker" },
    [1467] = { "Flameshaper", "Scalecommander" },
    [1468] = { "Flameshaper", "Chronowarden" },
    [1473] = { "Scalecommander", "Chronowarden" },
    [253] = { "Dark Ranger", "Pack Leader" },
    [254] = { "Dark Ranger", "Sentinel" },
    [255] = { "Pack Leader", "Sentinel" },
    [62] = { "Sunfury", "Spellslinger" },
    [63] = { "Sunfury", "Frostfire" },
    [64] = { "Spellslinger", "Frostfire" },
    [268] = { "Master of Harmony", "Shado-pan" },
    [269] = { "Conduit of the Celestials", "Shado-pan" },
    [270] = { "Conduit of the Celestials", "Master of Harmony" },
    [65] = { "Herald of the Sun", "Lightsmith" },
    [66] = { "Lightsmith", "Templar" },
    [70] = { "Herald of the Sun", "Templar" },
    [256] = { "Oracle", "Voidweaver" },
    [257] = { "Oracle", "Archon" },
    [258] = { "Archon", "Voidweaver" },
    [259] = { "Deathstalker", "Fatebound" },
    [260] = { "Fatebound", "Trickster" },
    [261] = { "Deathstalker", "Trickster" },
    [262] = { "Farseer", "Stormbringer" },
    [263] = { "Stormbringer", "Totemic" },
    [264] = { "Farseer", "Totemic" },
    [265] = { "Hellcaller", "Soul Harvester" },
    [266] = { "Diabolist", "Soul Harvester" },
    [267] = { "Diabolist", "Hellcaller" },
    [71] = { "Slayer", "Colossus" },
    [72] = { "Mountain Thane", "Slayer" },
    [73] = { "Colossus", "Mountain Thane" },
}

-- Hero tree subTreeID (C_ClassTalents.GetActiveHeroTalentSpec) -> ClassCodex hero
-- key. The game gives hero tree NAMES in the client language, so the ID is the
-- only language-independent way to find the player's hero tree. IDs are
-- Blizzard's TraitSubTree DB2 rows on each class talent tree (source: wago.tools
-- db2/TraitSubTree, build 12.x, checked 2026-09-29).
local HERO_KEY_BY_SUBTREE_ID = {
    [31] = "sanlayn", [32] = "rider-of-the-apocalypse", [33] = "deathbringer",
    [34] = "fel-scarred", [35] = "aldrachi-reaver", [124] = "annihilator", [126] = "void-scarred",
    [21] = "druid-of-the-claw", [22] = "wildstalker", [23] = "keeper-of-the-grove", [24] = "elunes-chosen",
    [36] = "scalecommander", [37] = "flameshaper", [38] = "chronowarden",
    [42] = "sentinel", [43] = "pack-leader", [44] = "dark-ranger",
    [39] = "sunfury", [40] = "spellslinger", [41] = "frostfire",
    [64] = "conduit-of-the-celestials", [65] = "shado-pan", [66] = "master-of-harmony",
    [48] = "templar", [49] = "lightsmith", [50] = "herald-of-the-sun",
    [18] = "voidweaver", [19] = "archon", [20] = "oracle",
    [51] = "trickster", [52] = "fatebound", [53] = "deathstalker",
    [54] = "totemic", [55] = "stormbringer", [56] = "farseer",
    [57] = "soul-harvester", [58] = "hellcaller", [59] = "diabolist",
    [60] = "slayer", [61] = "mountain-thane", [62] = "colossus",
}

function ns.GetStatVerdictHeroKeyBySubTreeID(subTreeID)
    return subTreeID and HERO_KEY_BY_SUBTREE_ID[tonumber(subTreeID)] or nil
end

function ns.GetStatVerdictHeroSubTreeIDs()
    local copy = {}
    for subTreeID, heroKey in pairs(HERO_KEY_BY_SUBTREE_ID) do copy[subTreeID] = heroKey end
    return copy
end

function ns.GetStatVerdictSpecKeyBySpecID(specID)
    return specID and SPEC_KEY_BY_SPEC_ID[specID] or nil
end

function ns.GetStatVerdictSpecIDByKey(specKey)
    return specKey and SPEC_ID_BY_KEY[specKey] or nil
end

function ns.GetStatVerdictRoleBySpecID(specID)
    return specID and ROLE_BY_SPEC_ID[specID] or nil
end

function ns.GetStatVerdictSpecNameByKey(specKey)
    return specKey and SPEC_NAME_BY_KEY[specKey] or nil
end

function ns.GetStatVerdictHeroOptionsBySpecID(specID)
    return specID and HERO_OPTIONS_BY_SPEC_ID[specID] or nil
end
