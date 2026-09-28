"""Builds per-goal, per-spec, per-hero-talent BiS stat targets from the
already-merged ClassCodex data (tools/classcodex_build.py) by reconstructing
paper-doll stats through SimulationCraft (tools/simc_stat_engine.py) — the
same engine already proven on Raider.IO run gear.

See docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline-spec.md
for the full design and the real data shapes this module relies on.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from tools.simc_stat_engine import render_profiles, run_simc
    from tools.live_benchmark_engine import SPEC_BY_KEY
except ModuleNotFoundError:
    from simc_stat_engine import render_profiles, run_simc
    from live_benchmark_engine import SPEC_BY_KEY

CLASSCODEX_SLOT_TO_SIMC: dict[str, str] = {
    "Head": "HEAD",
    "Neck": "NECK",
    "Shoulders": "SHOULDER",
    "Back": "BACK",
    "Chest": "CHEST",
    "Wrist": "WRIST",
    "Hands": "HANDS",
    "Waist": "WAIST",
    "Legs": "LEGS",
    "Feet": "FEET",
    "Finger 1": "FINGER_1",
    "Finger 2": "FINGER_2",
    "Trinket 1": "TRINKET_1",
    "Trinket 2": "TRINKET_2",
    "Main Hand": "MAIN_HAND",
    "Off Hand": "OFF_HAND",
}

GOAL_CONTEXT_KEY: dict[str, str] = {
    "MYTHIC_PLUS": "mplus",
    "RAID": "raid",
    "PVP": "pvp",
}

FALLBACK_CONTEXT_KEY = "all"


def select_context(nested: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> Any | None:
    """nested is a ClassCodex `{heroTalentKey: {contextKey: value}}` field
    (gear, talents, trinkets or statPriority's `.value`). Returns the exact
    goal context if present, else the `"all"` fallback, else None."""
    if not isinstance(nested, dict):
        return None
    by_context = nested.get(hero_talent_key)
    if not isinstance(by_context, dict):
        return None
    if context_key in by_context:
        return by_context[context_key]
    return by_context.get(FALLBACK_CONTEXT_KEY)


def build_simc_items(gear_list: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Converts a ClassCodex gear list into a SimC items dict keyed by WoW API
    slot tokens (as defined in CLASSCODEX_SLOT_TO_SIMC). Each item carries its
    itemId, optional itemLevel (ilvl), and optional bonusIds (camelCase bonusIDs).
    Skips entries with unknown slots or missing itemIds."""
    items: dict[str, dict[str, Any]] = {}
    for entry in gear_list or []:
        if not isinstance(entry, dict):
            continue
        simc_slot = CLASSCODEX_SLOT_TO_SIMC.get(str(entry.get("slot") or ""))
        item_id = entry.get("itemId")
        if simc_slot is None or not isinstance(item_id, (int, float)):
            continue
        item: dict[str, Any] = {"itemId": int(item_id)}
        ilvl = entry.get("ilvl")
        if isinstance(ilvl, (int, float)):
            item["itemLevel"] = ilvl
        bonus_ids = entry.get("bonusIDs")
        if isinstance(bonus_ids, list):
            item["bonusIds"] = [int(v) for v in bonus_ids if isinstance(v, (int, float))]
        items[simc_slot] = item
    return items


def average_item_level(gear_list: list[dict[str, Any]] | None) -> float | None:
    """Calculates the average item level from a gear list, ignoring entries
    without an ilvl field. Returns None if no entries have an ilvl."""
    levels = [
        float(entry["ilvl"])
        for entry in (gear_list or [])
        if isinstance(entry, dict) and isinstance(entry.get("ilvl"), (int, float))
    ]
    if not levels:
        return None
    return sum(levels) / len(levels)


def select_talent_export(talents_value: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> str | None:
    """Selects a talent export string for a goal/hero-talent combo. Returns the
    export string marked as recommended if present, else the export string of the
    first entry, or None if no valid entry exists."""
    entries = select_context(talents_value, hero_talent_key, context_key)
    if not isinstance(entries, list) or not entries:
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("recommended") is True:
            export = entry.get("export")
            if isinstance(export, str) and export:
                return export
    first = entries[0]
    export = first.get("export") if isinstance(first, dict) else None
    return export if isinstance(export, str) and export else None


def build_trinkets(trinkets_value: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> list[dict[str, Any]]:
    """Converts a ClassCodex trinket list (tiered S/A/B/C/D) into the addon's
    expected shape. Returns a list of dicts with item_id, bonus_ids, and tier."""
    entries = select_context(trinkets_value, hero_talent_key, context_key)
    if not isinstance(entries, list):
        return []
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("itemId"), (int, float)):
            continue
        tier = entry.get("tier")
        if not isinstance(tier, str) or not tier:
            continue
        bonus_ids = entry.get("bonusIDs")
        result.append(
            {
                "item_id": int(entry["itemId"]),
                "bonus_ids": [int(v) for v in bonus_ids if isinstance(v, (int, float))] if isinstance(bonus_ids, list) else [],
                "tier": tier,
            }
        )
    return result


def build_priority_row(
    stat_priority_value: dict[str, Any] | None,
    hero_talent_key: str,
    context_key: str,
    context_label: str,
    hero_talent_name: str,
) -> dict[str, Any] | None:
    """Converts ClassCodex's stat-priority tier-groups into an order/tiers row
    matching what the WoW addon's SV_ProfileRepository.lua validates. Returns
    a dict with context, heroTalent, order, and tiers, or None if no secondary list."""
    context = select_context(stat_priority_value, hero_talent_key, context_key)
    tiers = context.get("secondary") if isinstance(context, dict) else None
    if not isinstance(tiers, list) or not tiers:
        return None
    order: list[str] = []
    tie_groups: list[list[str]] = []
    for group in tiers:
        if not isinstance(group, list) or not group:
            continue
        # Validate each element is a non-empty string before adding
        valid_entries = [entry for entry in group if isinstance(entry, str) and entry]
        if not valid_entries:
            continue
        order.extend(valid_entries)
        if len(valid_entries) > 1:
            tie_groups.append(valid_entries)
    if not order:
        return None
    return {
        "context": context_label,
        "heroTalent": hero_talent_name,
        "order": order,
        "tiers": tie_groups,
    }


SIMC_TO_CANONICAL_STAT = {
    "crit": "critical_strike",
    "haste": "haste",
    "mastery": "mastery",
    "versatility": "versatility",
}


def build_target_context(
    spec: Any,
    goal: str,
    gear_list: list[dict[str, Any]] | None,
    talents_value: dict[str, Any] | None,
    hero_talent_key: str,
    context_key: str,
    simc_binary: Path = Path("simc"),
) -> dict[str, Any] | None:
    """Reconstructs the `targets`/`bis` half of a ClassCodex per-goal profile
    by running the BiS gear loadout for one spec/goal/hero-talent through
    SimulationCraft. Returns None if there is no gear, no talent export, or
    the SimC run fails or yields fewer than two usable secondary stats."""
    items = build_simc_items(gear_list)
    if not items:
        return None
    talent_loadout = select_talent_export(talents_value, hero_talent_key, context_key)
    if not talent_loadout:
        return None

    record = {"race": "human", "runTalentLoadout": talent_loadout, "items": items, "level": 90}
    profile_text, actor_map = render_profiles(spec, [record])
    try:
        stats_by_actor, _report = run_simc(simc_binary, profile_text)
    except Exception:  # noqa: BLE001 - fail closed; caller skips this combo
        return None
    actor_name = next(iter(actor_map))
    reconstructed = stats_by_actor.get(actor_name)
    if not reconstructed:
        return None
    ratings = reconstructed.get("ratings", {})
    stats = {
        canonical: float(ratings[raw])
        for raw, canonical in SIMC_TO_CANONICAL_STAT.items()
        if isinstance(ratings.get(raw), (int, float))
    }
    if len(stats) < 2:
        return None

    average_ilvl = average_item_level(gear_list)
    bis_slots = [
        {"slot": entry["slot"], "item": {"item_id": int(entry["itemId"]), **({"bonus_ids": [int(v) for v in entry["bonusIDs"] if isinstance(v, (int, float))]} if isinstance(entry.get("bonusIDs"), list) else {})}}
        for entry in (gear_list or [])
        if isinstance(entry, dict) and isinstance(entry.get("itemId"), (int, float)) and entry.get("slot") in CLASSCODEX_SLOT_TO_SIMC
    ]

    return {
        "targets": {
            "averageItemLevel": average_ilvl,
            "itemCount": len(items),
            "itemLevelSlots": len(items),
            "statTargets": {"context": goal, "source": "ClassCodex BiS + SimulationCraft", "stats": stats},
            "targetMetadata": {"lowItemReplacements": 0, "unresolvedLowItems": 0},
            "sourceGoal": goal,
        },
        "bis": {"label": "ClassCodex BiS", "slots": bis_slots},
    }


CONTEXT_LABEL = {"mplus": "Mythic+", "raid": "Raid", "pvp": "PvP", "all": "General"}


def _classcodex_key_to_catalog_key(spec_key: str) -> str:
    class_folder, _, spec_token = spec_key.partition("_")
    return f"{class_folder}_{spec_token.upper().replace('-', '_')}"


def _hero_talent_keys(gear_value: dict[str, Any] | None, talents_value: dict[str, Any] | None) -> set[str]:
    keys: set[str] = set()
    if isinstance(gear_value, dict):
        keys.update(gear_value.keys())
    if isinstance(talents_value, dict):
        keys.update(talents_value.keys())
    return keys


def build_all(
    specs: dict[str, dict[str, Any]],
    simc_binary: Path,
    goals: tuple[str, ...] = ("MYTHIC_PLUS", "RAID", "PVP"),
) -> dict[str, Any]:
    """Loops over every ClassCodex spec/goal/hero-talent combo, reconstructing
    stat targets via SimC for each, and assembles the full per-spec document.
    Skips spec keys not in the SPEC_BY_KEY catalog and goals with no usable
    hero-talent context anywhere."""
    profiles: dict[str, Any] = {}
    for spec_key, fields in specs.items():
        catalog_key = _classcodex_key_to_catalog_key(spec_key)
        spec = SPEC_BY_KEY.get(catalog_key)
        if spec is None:
            continue

        gear_value = (fields.get("gear") or {}).get("value")
        talents_value = (fields.get("talents") or {}).get("value")
        trinkets_value = (fields.get("trinkets") or {}).get("value")
        stat_priority_value = (fields.get("statPriority") or {}).get("value")

        goals_out: dict[str, Any] = {}
        for goal in goals:
            context_key = GOAL_CONTEXT_KEY[goal]
            hero_talents_out: dict[str, Any] = {}
            for hero_talent_key in _hero_talent_keys(gear_value, talents_value):
                gear_list = select_context(gear_value, hero_talent_key, context_key)
                if not isinstance(gear_list, list) or not gear_list:
                    continue
                target_context = build_target_context(
                    spec, goal, gear_list, talents_value, hero_talent_key, context_key, simc_binary
                )
                if target_context is None:
                    continue
                target_context["trinkets"] = build_trinkets(trinkets_value, hero_talent_key, context_key)
                row = build_priority_row(
                    stat_priority_value,
                    hero_talent_key,
                    context_key,
                    CONTEXT_LABEL[context_key],
                    hero_talent_key,
                )
                target_context["priorityProfiles"] = [row] if row else []
                hero_talents_out[hero_talent_key] = target_context
            if hero_talents_out:
                goals_out[goal] = {"heroTalents": hero_talents_out}

        if goals_out:
            profiles[spec_key] = {
                "specKey": spec_key,
                "classToken": spec_key.split("_", 1)[0],
                "primaryStat": spec.primary,
                "goals": goals_out,
            }

    return {"profiles": profiles}
