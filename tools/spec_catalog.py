"""The 40 StatVerdict specializations: addon spec key, class/spec names,
role and primary stat. Shared by the ClassCodex pipelines and the SimC engine."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spec:
    key: str
    class_name: str
    spec_name: str
    role: str
    primary: str


SPECS = (
    Spec("DEATHKNIGHT_BLOOD", "death-knight", "Blood", "tank", "strength"),
    Spec("DEATHKNIGHT_FROST", "death-knight", "Frost", "dps", "strength"),
    Spec("DEATHKNIGHT_UNHOLY", "death-knight", "Unholy", "dps", "strength"),
    Spec("DEMONHUNTER_DEVOURER", "demon-hunter", "Devourer", "dps", "intellect"),
    Spec("DEMONHUNTER_HAVOC", "demon-hunter", "Havoc", "dps", "agility"),
    Spec("DEMONHUNTER_VENGEANCE", "demon-hunter", "Vengeance", "tank", "agility"),
    Spec("DRUID_BALANCE", "druid", "Balance", "dps", "intellect"),
    Spec("DRUID_FERAL", "druid", "Feral", "dps", "agility"),
    Spec("DRUID_GUARDIAN", "druid", "Guardian", "tank", "agility"),
    Spec("DRUID_RESTORATION", "druid", "Restoration", "healer", "intellect"),
    Spec("EVOKER_AUGMENTATION", "evoker", "Augmentation", "dps", "intellect"),
    Spec("EVOKER_DEVASTATION", "evoker", "Devastation", "dps", "intellect"),
    Spec("EVOKER_PRESERVATION", "evoker", "Preservation", "healer", "intellect"),
    Spec("HUNTER_BEAST_MASTERY", "hunter", "Beast Mastery", "dps", "agility"),
    Spec("HUNTER_MARKSMANSHIP", "hunter", "Marksmanship", "dps", "agility"),
    Spec("HUNTER_SURVIVAL", "hunter", "Survival", "dps", "agility"),
    Spec("MAGE_ARCANE", "mage", "Arcane", "dps", "intellect"),
    Spec("MAGE_FIRE", "mage", "Fire", "dps", "intellect"),
    Spec("MAGE_FROST", "mage", "Frost", "dps", "intellect"),
    Spec("MONK_BREWMASTER", "monk", "Brewmaster", "tank", "agility"),
    Spec("MONK_MISTWEAVER", "monk", "Mistweaver", "healer", "intellect"),
    Spec("MONK_WINDWALKER", "monk", "Windwalker", "dps", "agility"),
    Spec("PALADIN_HOLY", "paladin", "Holy", "healer", "intellect"),
    Spec("PALADIN_PROTECTION", "paladin", "Protection", "tank", "strength"),
    Spec("PALADIN_RETRIBUTION", "paladin", "Retribution", "dps", "strength"),
    Spec("PRIEST_DISCIPLINE", "priest", "Discipline", "healer", "intellect"),
    Spec("PRIEST_HOLY", "priest", "Holy", "healer", "intellect"),
    Spec("PRIEST_SHADOW", "priest", "Shadow", "dps", "intellect"),
    Spec("ROGUE_ASSASSINATION", "rogue", "Assassination", "dps", "agility"),
    Spec("ROGUE_OUTLAW", "rogue", "Outlaw", "dps", "agility"),
    Spec("ROGUE_SUBTLETY", "rogue", "Subtlety", "dps", "agility"),
    Spec("SHAMAN_ELEMENTAL", "shaman", "Elemental", "dps", "intellect"),
    Spec("SHAMAN_ENHANCEMENT", "shaman", "Enhancement", "dps", "agility"),
    Spec("SHAMAN_RESTORATION", "shaman", "Restoration", "healer", "intellect"),
    Spec("WARLOCK_AFFLICTION", "warlock", "Affliction", "dps", "intellect"),
    Spec("WARLOCK_DEMONOLOGY", "warlock", "Demonology", "dps", "intellect"),
    Spec("WARLOCK_DESTRUCTION", "warlock", "Destruction", "dps", "intellect"),
    Spec("WARRIOR_ARMS", "warrior", "Arms", "dps", "strength"),
    Spec("WARRIOR_FURY", "warrior", "Fury", "dps", "strength"),
    Spec("WARRIOR_PROTECTION", "warrior", "Protection", "tank", "strength"),
)
SPEC_BY_KEY = {spec.key: spec for spec in SPECS}
