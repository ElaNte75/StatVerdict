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

# (tier, minimum pooled usage percent). Initial values; reviewed with the user
# against real data before they are locked (plan Task 5).
TIER_THRESHOLDS: tuple[tuple[str, float], ...] = (("S", 40.0), ("A", 20.0), ("B", 8.0), ("C", 3.0))
TRINKET_LIMIT = 16  # rows in the addon's Ranked Trinkets panel
MIN_SLOTS = 10  # same as the addon's MIN_CONTEXT_ITEMS
MIN_ITEM_LEVEL = 250.0  # same as the addon's MIN_VALID_MAX_LEVEL_TARGET_ILVL
TIE_RATIO = 0.05  # a stat within 5% of the previous one shares its priority tier
# Live database key -> key used in the addon's statTargets / priority rows.
TARGET_KEYS = {"crit": "critical_strike", "haste": "haste", "mastery": "mastery", "versatility": "versatility"}
PRIORITY_KEYS = {"crit": "critical-strike", "haste": "haste", "mastery": "mastery", "versatility": "versatility"}
PRIMARY_KEYS = ("strength", "agility", "intellect")


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


def _tier_for(percent: float) -> str | None:
    for tier, floor in TIER_THRESHOLDS:
        if percent >= floor:
            return tier
    return None


def rank_trinkets(popular_items: dict[str, Any]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for entry in _pool(popular_items, ("TRINKET_1", "TRINKET_2")):
        percent = round(entry["percent"], 2)
        tier = _tier_for(percent)
        if tier is None:
            continue
        ranked.append({**_item_fields(entry["item"]), "tier": tier, "usagePercent": percent})
        if len(ranked) == TRINKET_LIMIT:
            break
    return ranked


def valid_cohort(cohort: Any) -> bool:
    if not isinstance(cohort, dict) or cohort.get("status") != "ok":
        return False
    minimum = int(cohort.get("minimumSample") or 0)
    return minimum > 0 and int(cohort.get("sampleSize") or 0) >= minimum


def secondary_stats(cohort: dict[str, Any] | None, key_map: dict[str, str]) -> dict[str, float]:
    raw = ((cohort or {}).get("statTargets") or {}).get("stats") or {}
    stats: dict[str, float] = {}
    for source_key, target_key in key_map.items():
        value = raw.get(source_key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            stats[target_key] = float(value)
    return stats


def order_and_tiers(stats: dict[str, float]) -> tuple[list[str], list[list[str]]]:
    ranked = sorted(((k, v) for k, v in stats.items() if v > 0), key=lambda kv: (-kv[1], kv[0]))
    order = [key for key, _ in ranked]
    tiers: list[list[str]] = []
    previous: float | None = None
    for key, value in ranked:
        if previous is not None and value >= previous * (1.0 - TIE_RATIO):
            tiers[-1].append(key)
        else:
            tiers.append([key])
        previous = value
    return order, tiers


def _priority_row(cohort: dict[str, Any], hero_tree_id: int | None) -> dict[str, Any] | None:
    order, tiers = order_and_tiers(secondary_stats(cohort, PRIORITY_KEYS))
    if not order:
        return None
    row: dict[str, Any] = {"context": "Mythic+", "order": order, "tiers": tiers}
    if hero_tree_id is not None:
        row["heroSubTreeID"] = hero_tree_id
    return row


def build_priority_profiles(
    profile: dict[str, Any], cohort_key: str, spec_cohort: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tree in (profile.get("heroTalentTrees") or {}).values():
        tree_id = tree.get("id")
        cohort = (tree.get("cohorts") or {}).get(cohort_key)
        if not isinstance(tree_id, int) or not valid_cohort(cohort):
            continue
        row = _priority_row(cohort, tree_id)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["heroSubTreeID"])
    general = _priority_row(spec_cohort, None)
    if general:
        rows.append(general)
    return rows


def measured_primary_stat(cohort: dict[str, Any] | None, fallback: str) -> str:
    raw = ((cohort or {}).get("statTargets") or {}).get("stats") or {}
    best = max(PRIMARY_KEYS, key=lambda key: float(raw.get(key) or 0.0))
    return best if float(raw.get(best) or 0.0) > 0 else fallback
