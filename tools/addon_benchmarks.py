#!/usr/bin/env python3
"""Compact the live benchmark databases into the small Mythic+ file the addon loads.

The raw databases (tools/data/live/SV_LiveBenchmarkData_*.json) hold every
cohort, hero tree, variant and evidence run id. The addon needs only the
stat targets, the popular item per slot, ranked trinkets and stat priority.
This module writes exactly that, in the shape the addon's old Mythic+
context had, so scoring and the panels do not change.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
GOAL = "MYTHIC_PLUS"
LEVELS = {"ELITE": "TOP_25", "STANDARD": "TOP_100", "BROAD": "TOP_200"}

# Panel row order; a label that repeats (Ring, Trinket) takes the next-ranked item.
SLOT_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Helm", ("HEAD",)),
    ("Hands", ("HANDS",)),
    ("Neck", ("NECK",)),
    ("Waist", ("WAIST",)),
    ("Shoulders", ("SHOULDER",)),
    ("Legs", ("LEGS",)),
    ("Cloak", ("BACK",)),
    ("Feet", ("FEET",)),
    ("Chest", ("CHEST",)),
    ("Ring", ("FINGER_1", "FINGER_2")),
    ("Ring", ("FINGER_1", "FINGER_2")),
    ("Trinket", ("TRINKET_1", "TRINKET_2")),
    ("Bracers", ("WRIST",)),
    ("Trinket", ("TRINKET_1", "TRINKET_2")),
    ("Main Hand", ("MAIN_HAND",)),
    ("Off Hand", ("OFF_HAND",)),
)


def _top_variant(item: dict[str, Any]) -> dict[str, Any] | None:
    variants = item.get("variants") or []
    if not variants:
        return None
    return max(variants, key=lambda v: (int(v.get("count") or 0), float(v.get("itemLevel") or 0)))


def _pool(popular_items: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Merge the item lists of several slot keys; one entry per item id, most used first."""
    pooled: dict[int, dict[str, Any]] = {}
    for key in keys:
        for item in popular_items.get(key) or []:
            item_id = int(item["itemId"])
            count = int(item.get("count") or 0)
            percent = float(item.get("usagePercent") or 0.0)
            entry = pooled.get(item_id)
            if entry is None:
                pooled[item_id] = {"item": item, "count": count, "percent": percent}
                continue
            if count > int(entry["item"].get("count") or 0):
                entry["item"] = item
            entry["count"] += count
            entry["percent"] += percent
    return sorted(pooled.values(), key=lambda e: (-e["count"], int(e["item"]["itemId"])))


def _item_fields(item: dict[str, Any]) -> dict[str, Any]:
    variant = _top_variant(item) or {}
    return {
        "item_id": int(item["itemId"]),
        "name": item.get("name") or "",
        "bonus_ids": [int(v) for v in (variant.get("bonusIds") or [])],
    }


def pick_popular_slots(popular_items: dict[str, Any]) -> list[dict[str, Any]]:
    ranked_cache: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    used: dict[str, int] = {}
    slots: list[dict[str, Any]] = []
    for label, keys in SLOT_ORDER:
        if keys not in ranked_cache:
            ranked_cache[keys] = _pool(popular_items, keys)
        index = used.get(label, 0)
        used[label] = index + 1
        ranked = ranked_cache[keys]
        if index >= len(ranked):
            continue
        entry = ranked[index]
        slots.append(
            {"slot": label, "item": _item_fields(entry["item"]), "usagePercent": round(entry["percent"], 2)}
        )
    return slots
