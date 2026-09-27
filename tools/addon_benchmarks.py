#!/usr/bin/env python3
"""Compact the live benchmark databases into the small Mythic+ file the addon loads.

The raw databases (tools/data/live/SV_LiveBenchmarkData_*.json) hold every
cohort, hero tree, variant and evidence run id. The addon needs only the
stat targets, the popular item per slot, ranked trinkets and stat priority.
This module writes exactly that, in the shape the addon's old Mythic+
context had, so scoring and the panels do not change.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from tools.live_benchmark_engine import to_lua
except ModuleNotFoundError:
    # Run as "python tools/addon_benchmarks.py": sys.path[0] is tools/, not the repo root.
    from live_benchmark_engine import to_lua

SCHEMA_VERSION = 1
GOAL = "MYTHIC_PLUS"
BRACKETS = ("LOW", "MID", "HIGH")
SAMPLE_SIZES = (20, 50, 100)

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
OFF_HAND_MIN_SHARE = 50.0  # percent of players that must wear an off hand for the row to be listed
MIN_SLOTS = 10  # same as the addon's MIN_CONTEXT_ITEMS
MIN_ITEM_LEVEL = 250.0  # same as the addon's MIN_VALID_MAX_LEVEL_TARGET_ILVL
MAX_FILE_BYTES = 5 * 1024 * 1024
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


def _off_hand_is_plausible(popular_items: dict[str, Any]) -> bool:
    """List an Off Hand only when it can go with the listed Main Hand.

    Two-handed weapons block the off hand, so a popular staff next to a rarely used
    off hand is an impossible pair. The raw data has no weapon pairs, so this uses
    usage shares: at least half of the players wear an off hand, and the top main hand
    plus the off hands add up to more than 100%, which proves they overlap (the top
    main hand is a one-hander). Otherwise the row is left out.
    """
    off_share = sum(float(i.get("usagePercent") or 0.0) for i in popular_items.get("OFF_HAND") or [])
    if off_share < OFF_HAND_MIN_SHARE:
        return False
    top_main = max((float(i.get("usagePercent") or 0.0) for i in popular_items.get("MAIN_HAND") or []), default=0.0)
    return top_main + off_share > 100.0


def pick_popular_slots(popular_items: dict[str, Any]) -> list[dict[str, Any]]:
    off_hand_ok = _off_hand_is_plausible(popular_items)
    ranked_cache: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    used: dict[str, int] = {}
    slots: list[dict[str, Any]] = []
    for label, keys in SLOT_ORDER:
        if label == "Off Hand" and not off_hand_ok:
            continue
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
    profile: dict[str, Any], bracket: str, inner_cohort_key: str, spec_cohort: dict[str, Any]
) -> list[dict[str, Any]]:
    """inner_cohort_key is the hero tree's OWN cohort naming (still "TOP_{size}" -
    aggregate_hero_trees in live_benchmark_engine.py is unchanged by the bracket work), not
    the outer "{bracket}_{size}" key. heroTalentTrees holds every bracket's trees under
    "{bracket}:{treeKey}", so this filters to the ones belonging to `bracket` first."""
    rows: list[dict[str, Any]] = []
    prefix = f"{bracket}:"
    for tree_key, tree in (profile.get("heroTalentTrees") or {}).items():
        if not tree_key.startswith(prefix):
            continue
        tree_id = tree.get("id")
        cohort = (tree.get("cohorts") or {}).get(inner_cohort_key)
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


def _class_token(value: Any) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalpha())


def build_level_context(profile: dict[str, Any], bracket: str, cohort_key: str) -> dict[str, Any] | None:
    cohort = (profile.get("cohorts") or {}).get(cohort_key)
    gear = (profile.get("gearCohorts") or {}).get(cohort_key)
    if not valid_cohort(cohort) or not isinstance(gear, dict) or gear.get("status") != "ok":
        return None
    popular = gear.get("popularItems") or {}
    slots = pick_popular_slots(popular)
    average = cohort.get("averageItemLevel")
    stats = secondary_stats(cohort, TARGET_KEYS)
    if len(slots) < MIN_SLOTS or not isinstance(average, (int, float)) or average < MIN_ITEM_LEVEL or len(stats) < 2:
        return None
    # A hero tree's own cohorts are still keyed TOP_{size} (see build_priority_profiles).
    size_text = cohort_key.rsplit("_", 1)[1]
    return {
        "targets": {
            "averageItemLevel": float(average),
            "itemCount": len(slots),
            "itemLevelSlots": len(slots),
            "statTargets": {"context": "Mythic+", "source": "StatVerdict live benchmarks", "stats": stats},
            "targetMetadata": {"lowItemReplacements": 0, "unresolvedLowItems": 0},
            "sourceGoal": GOAL,
        },
        "bis": {"label": "Popular", "slots": slots},
        "trinkets": rank_trinkets(popular),
        "priorityProfiles": build_priority_profiles(profile, bracket, f"TOP_{size_text}", cohort),
        "benchmark": {
            "level": bracket,
            "cohort": cohort_key,
            "sampleSize": int(cohort.get("sampleSize") or 0),
            "minimumSample": int(cohort.get("minimumSample") or 0),
            "confidence": cohort.get("confidence") or "unknown",
            "completeness": float(cohort.get("completeness") or 0.0),
        },
    }


def build_profile(spec_key: str, profile: dict[str, Any]) -> dict[str, Any] | None:
    if profile.get("status") != "ok":
        return None
    levels: dict[str, dict[str, Any]] = {}
    for bracket in BRACKETS:
        for size in SAMPLE_SIZES:
            cohort_key = f"{bracket}_{size}"
            context = build_level_context(profile, bracket, cohort_key)
            if context:
                levels.setdefault(bracket, {})[str(size)] = context
    if not levels:
        return None
    cohorts = profile.get("cohorts") or {}
    reference_key = next(
        (f"{b}_100" for b in ("HIGH", "MID", "LOW") if valid_cohort(cohorts.get(f"{b}_100"))),
        None,
    )
    reference = cohorts.get(reference_key) if reference_key else None
    return {
        "specKey": spec_key,
        "classToken": _class_token(profile.get("class")),
        "primaryStat": measured_primary_stat(reference, str(profile.get("primaryStat") or "")),
        "levels": levels,
    }


def build_addon_data(databases: list[dict[str, Any]]) -> dict[str, Any]:
    if not databases:
        raise ValueError("at least one raw benchmark database is required")
    stamps = [str(db["generatedAt"]) for db in databases if db.get("generatedAt")]
    if not stamps:
        raise ValueError("no raw benchmark database carries generatedAt")
    profiles: dict[str, Any] = {}
    for database in databases:
        for spec_key, profile in (database.get("profiles") or {}).items():
            built = build_profile(spec_key, profile)
            if built:
                profiles[spec_key] = built
    raw_source = databases[0].get("source") or {}
    source = {"name": "StatVerdict live benchmarks"}
    for key in ("season", "regions", "aggregation"):
        if raw_source.get(key) is not None:
            source[key] = raw_source[key]
    return {"schemaVersion": SCHEMA_VERSION, "generatedAt": min(stamps), "source": source, "profiles": profiles}


def render_lua(data: dict[str, Any]) -> str:
    return (
        "local addonName, ns = ...\n\n"
        "-- Generated by tools/addon_benchmarks.py from the live benchmark files. Do not edit manually.\n"
        "ns.MythicPlusBenchmarks = " + to_lua(data) + "\n"
    )


def write_addon_file(data: dict[str, Any], path: Path) -> int:
    text = render_lua(data)
    size = len(text.encode("utf-8"))
    if size > MAX_FILE_BYTES:
        raise ValueError(f"addon benchmark file is {size} bytes, over the {MAX_FILE_BYTES} byte limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Write bytes so Windows keeps LF line endings and the size gate stays exact.
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)
    return size


def build_report(data: dict[str, Any]) -> str:
    """Per-spec numbers used to review tier thresholds and slot favourites."""
    lines = [f"generatedAt {data['generatedAt']}, {len(data['profiles'])} specs"]
    for spec_key in sorted(data["profiles"]):
        profile = data["profiles"][spec_key]
        for bracket in BRACKETS:
            for size in SAMPLE_SIZES:
                label = f"{bracket}_{size}"
                context = profile["levels"].get(bracket, {}).get(str(size))
                if not context:
                    lines.append(f"{spec_key} {label}: no data")
                    continue
                slots = context["bis"]["slots"]
                favourites = sum(1 for s in slots if s["usagePercent"] >= 40.0)
                counts = {tier: 0 for tier, _ in TIER_THRESHOLDS}
                for trinket in context["trinkets"]:
                    counts[trinket["tier"]] += 1
                tiers = " ".join(f"{tier}:{counts[tier]}" for tier, _ in TIER_THRESHOLDS)
                bench = context["benchmark"]
                lines.append(
                    f"{spec_key} {label}: sample {bench['sampleSize']} ({bench['confidence']}), "
                    f"primary {profile['primaryStat']}, slots {len(slots)}, "
                    f"clear favourites (>=40%): {favourites}/{len(slots)}, tiers {tiers}"
                )
    return "\n".join(lines)


def load_databases(directory: Path) -> list[dict[str, Any]]:
    paths = sorted(directory.glob("SV_LiveBenchmarkData_*.json"))
    if not paths:
        raise FileNotFoundError(f"no SV_LiveBenchmarkData_*.json files in {directory}")
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path("tools/data/live"))
    parser.add_argument("--out", type=Path, default=Path("StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua"))
    parser.add_argument("--report", action="store_true", help="print the per-spec review report and write nothing")
    args = parser.parse_args(argv)

    data = build_addon_data(load_databases(args.inputs))
    if args.report:
        print(build_report(data))
        return 0
    if not data["profiles"]:
        print("No specialization produced usable data; refusing to write the addon file.", file=sys.stderr)
        return 1
    size = write_addon_file(data, args.out)
    print(f"Wrote {args.out} ({size} bytes, {len(data['profiles'])} specs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
