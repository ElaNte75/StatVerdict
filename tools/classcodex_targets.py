"""Builds per-goal, per-spec, per-hero-talent BiS stat targets from the
already-merged ClassCodex data (tools/classcodex_build.py) by reconstructing
paper-doll stats through SimulationCraft (tools/simc_stat_engine.py) — the
same engine already proven on Raider.IO run gear.

See docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline-spec.md
for the full design and the real data shapes this module relies on.
"""
from __future__ import annotations

from typing import Any

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
        order.extend(group)
        if len(group) > 1:
            tie_groups.append(list(group))
    if not order:
        return None
    return {
        "context": context_label,
        "heroTalent": hero_talent_name,
        "order": order,
        "tiers": tie_groups,
    }
