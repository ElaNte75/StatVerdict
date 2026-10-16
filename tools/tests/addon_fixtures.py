"""Synthetic ClassCodex data shared by the addon Lua tests."""

from __future__ import annotations

from typing import Any

# --- ClassCodex data (the shape tools/classcodex_targets_cli.py writes into StatVerdict/Data/Generated) ---

CLASSCODEX_SLOTS = (
    "Head", "Neck", "Shoulders", "Back", "Chest", "Wrist", "Hands", "Waist",
    "Legs", "Feet", "Finger 1", "Finger 2", "Trinket 1", "Trinket 2", "Main Hand",
)
PRIORITY_CONTEXT = {"OVERALL": "Overall", "MYTHIC_PLUS": "Mythic+", "RAID": "Raid", "PVP": "PvP"}


def make_hero_context(
    goal: str,
    hero: str,
    stats: tuple[float, float, float, float],
    order: list[str],
    average_item_level: float | None = 337.9,
    helm_id: int = 1000,
    tiers: list[list[str]] | None = None,
) -> dict[str, Any]:
    """One ClassCodex spec/goal/hero-talent context. Items: helm = helm_id,
    other slots 1001.., trinkets 5001 (Trinket 1) and 5003 (Trinket 2); the
    trinket tier list ranks 5001 S, 5003 S, 5002 A. No targets.levels:
    tests add them with add_tier_targets."""
    crit, haste, mastery, versatility = stats
    slots = []
    for index, slot in enumerate(CLASSCODEX_SLOTS):
        item_id = {"Head": helm_id, "Trinket 1": 5001, "Trinket 2": 5003}.get(slot, 1000 + index)
        slots.append({"slot": slot, "item": {"item_id": item_id, "bonus_ids": [6652, 100 + index]}})
    targets: dict[str, Any] = {
        "itemCount": len(slots),
        "itemLevelSlots": len(slots) if average_item_level is not None else 0,
        "sourceGoal": goal,
        "statTargets": {
            "context": goal,
            "source": "ClassCodex BiS + SimulationCraft",
            "stats": {"critical_strike": crit, "haste": haste, "mastery": mastery, "versatility": versatility},
        },
        "targetMetadata": {"lowItemReplacements": 0, "unresolvedLowItems": 0},
    }
    if average_item_level is not None:
        targets["averageItemLevel"] = average_item_level
    return {
        "targets": targets,
        "bis": {"label": "ClassCodex BiS", "slots": slots},
        "trinkets": [
            {"item_id": 5001, "bonus_ids": [401], "tier": "S"},
            {"item_id": 5003, "bonus_ids": [403], "tier": "S"},
            {"item_id": 5002, "bonus_ids": [402], "tier": "A"},
        ],
        "priorityProfiles": [
            {"context": PRIORITY_CONTEXT[goal], "heroTalent": hero, "order": list(order), "tiers": tiers or []},
        ],
    }


TIER_LEVEL_ITEM_LEVEL = {"hero": 321.0, "champion": 308.0}
TIER_LEVEL_OF_BIN = {"top50": "hero", "top80": "champion"}


def make_tier_targets(**bins: tuple[float | None, float | None, float | None, float | None]) -> dict[str, Any]:
    """The stat targets of the tiers, per bin ("top20" = Tier 3 at Myth 6/6,
    "top50" = Tier 2 at Hero 6/6, "top80" = Tier 1 at Champion 6/6) as
    (crit, haste, mastery, versatility) ratings. A None value leaves that stat
    out of the bin."""
    names = ("critical_strike", "haste", "mastery", "versatility")
    return {
        bin_key: {name: value for name, value in zip(names, values) if value is not None}
        for bin_key, values in bins.items()
    }


def add_tier_targets(targets: dict[str, Any], spec_key: str, goal: str, hero: str,
                     tier_targets: dict[str, Any]) -> dict[str, Any]:
    """Puts make_tier_targets on one spec/goal/hero context of a make_classcodex_targets
    result: Tier 3 replaces statTargets, Tiers 2 and 1 become targets.levels."""
    data = targets["profiles"][spec_key]["goals"][goal]["heroTalents"][hero]["targets"]
    for bin_key, stats in tier_targets.items():
        level = TIER_LEVEL_OF_BIN.get(bin_key)
        if level is None:
            data["statTargets"]["stats"] = stats
        else:
            data.setdefault("levels", {})[level] = {
                "statTargets": {"stats": stats}, "averageItemLevel": TIER_LEVEL_ITEM_LEVEL[level],
            }
    return targets


def make_classcodex_targets(build_id: str, profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    """Blood DK: M+ sanlayn + deathbringer, Raid sanlayn, PvP sanlayn (no item level,
    like real PvP data). Brewmaster: M+ master-of-harmony only."""
    if profiles is None:
        blood_order = ["haste", "critical_strike", "mastery", "versatility"]
        profiles = {
            "DEATHKNIGHT_BLOOD": {
                "specKey": "DEATHKNIGHT_BLOOD",
                "classToken": "DEATHKNIGHT",
                "primaryStat": "strength",
                "goals": {
                    "OVERALL": {"heroTalents": {
                        "sanlayn": make_hero_context("OVERALL", "sanlayn", (1140, 900, 680, 430), blood_order),
                    }},
                    "MYTHIC_PLUS": {"heroTalents": {
                        "sanlayn": make_hero_context("MYTHIC_PLUS", "sanlayn", (1140, 900, 680, 430), blood_order),
                        "deathbringer": make_hero_context(
                            "MYTHIC_PLUS", "deathbringer", (1300, 400, 1000, 700),
                            ["critical_strike", "mastery", "versatility", "haste"], helm_id=1500),
                    }},
                    "RAID": {"heroTalents": {
                        "sanlayn": make_hero_context("RAID", "sanlayn", (1200, 950, 600, 400), blood_order),
                    }},
                    "PVP": {"heroTalents": {
                        "sanlayn": make_hero_context(
                            "PVP", "sanlayn", (600, 700, 500, 800),
                            ["versatility", "haste", "critical_strike", "mastery"], average_item_level=None),
                    }},
                },
            },
            "MONK_BREWMASTER": {
                "specKey": "MONK_BREWMASTER",
                "classToken": "MONK",
                "primaryStat": "agility",
                "goals": {
                    "MYTHIC_PLUS": {"heroTalents": {
                        "master-of-harmony": make_hero_context(
                            "MYTHIC_PLUS", "master-of-harmony", (900, 800, 700, 1000),
                            ["versatility", "critical_strike", "haste", "mastery"]),
                    }},
                },
            },
        }
    return {"schemaVersion": 1, "buildId": build_id, "publishedAt": "", "profiles": profiles}
