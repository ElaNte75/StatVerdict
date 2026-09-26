# Benchmark: live Mythic+ data in the addon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the addon use the live GitHub-generated benchmark data for Mythic+ (through a small compacted file and a new Benchmark panel with Elite/Standard/Broad levels), while Raid/PvP keep the old data and the interface look does not change.

**Architecture:** A Python compaction step turns the six large raw benchmark files into one small Lua file (`SV_MythicPlusBenchmarks.lua`) whose per-level context has exactly the shape the old Mythic+ context had, so scoring, the item-boost code and the panels keep working. `ProfileRepository` reads that file for the Mythic+ goal at the level the player chose; every other goal reads the old file. A new drawer panel replaces the Summary panel and stores the chosen level.

**Tech Stack:** Python 3.12+ (`unittest`), WoW Lua 5.1 addon code, GitHub Actions YAML, optional dev-only Python package `lupa` (runs the addon's Lua in tests; tests skip if it is not installed).

**Spec:** `docs/superpowers/specs/2026-09-26-benchmark-mythicplus-data-design.md`

## Global Constraints

- The interface style and window size do not change; the window still opens with all right-side panels closed.
- Raid and PvP keep reading `SV_ProfileData.lua` exactly as today.
- Levels: ELITE = data cohort `TOP_25`, STANDARD = `TOP_100` (default), BROAD = `TOP_200`. Player-facing names are Elite / Standard / Broad with the meaning lines "Gear of the top 25 players", "Gear of the top 100 players", "Gear of the top 200 players".
- Mythic+ wording: "Popular" replaces "BiS"; Raid/PvP keep "BiS" / "Best in Slot".
- Boost constants in `Core/SV_ItemReferenceBonuses.lua` are NOT changed: `BIS_BONUS = 8`, trinket tiers S 95 / A 65 / B 35 / C 14 / D 0, `MAX_RANK_BONUS = 5`.
- Compacted addon file: under 5 MB (`MAX_FILE_BYTES = 5 * 1024 * 1024`); runtime freshness: `generatedAt` within 30 days; quality checks unchanged (at least 10 slots, average item level at least 250, at least 2 stat targets).
- Trinket tiers from pooled usage share: S at 40% or more, A at 20%, B at 8%, C at 3%; below 3% is not listed. These are the initial values and are reviewed with the user in Task 5 before they are locked.
- Removal rule (user's): superseded things are deleted completely, with leftovers; risky deletions are done in two steps (unplug, user verifies in game, then delete).
- User-facing explanations to the user are in simple Greek, no code (CLAUDE.md). Code, comments, commit messages stay in English.
- Do NOT stage or commit the user's pre-existing uncommitted work: `.gitignore`, `StatVerdict/scripts/ship.ps1`, `tools/README.md`, `tools/wowhead_proof.py`, `tools/data/wowhead_proof_resto.json`, the deleted `StatVerdict/Media/StatVerdictIcon.png` and `StatVerdict/_check_profiles.py`. Always `git add` explicit paths. `tools/data/wowhead_proof_resto.json` contains real player names and must never be committed.
- Run Python tests from the repository root: `python -m unittest discover -s tools/tests -v`.

## Review Focus

Inputs and conditions the spec implies but no obvious task test covers; each has its test in the task named at the end of the line.

1. A Demon Hunter Devourer profile whose live `primaryStat` says agility although its median primary stats show intellect: the compacted profile must use the measured primary stat (Task 3).
2. A hero tree with `insufficient` status (Devourer `HERO_126`): no row for it, the spec-wide priority row still exists (Task 3).
3. A spec that has data at Standard but not at Elite: the profile exists with only the levels that are valid; the addon shows "unavailable" for the missing level instead of another level's data (Task 4, Task 9).
4. Off Spec / unknown hero tree (no `heroSubTreeID` on the context): the addon must fall back to the spec-wide priority row, not to a mismatching hero row (Task 9).
5. The same ring or trinket item appearing in both slots' lists must not be counted twice or listed twice (Task 1, Task 2).
6. Stale data (`generatedAt` older than 30 days) must fail closed (Task 9).
7. A trinket or popular item that is NOT in the list must get no boost, and the boost must follow the level the player selected (Task 9).

---

## File structure

Create:
- `tools/addon_benchmarks.py` — pure compaction functions + CLI (one responsibility: raw benchmark databases → addon data → Lua file).
- `tools/tests/addon_fixtures.py` — synthetic raw-database builder shared by the Python and Lua tests.
- `tools/tests/test_addon_benchmarks.py` — Python tests for the compaction.
- `tools/tests/test_addon_lua.py` — lupa tests: every `.toc` file compiles; repository, hero priority, level switch, freshness, boosts.
- `StatVerdict/Core/SV_Benchmark.lua` — levels, saved choice, wording helper.
- `StatVerdict/UI/SV_BenchmarkDrawerPanel.lua` — the Benchmark drawer.
- `StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua` — generated output (committed by the workflow).
- `tools/data/live/SV_LiveBenchmarkData_{DPS1,DPS2,DPS3,DPS4,Tank,Healer}.json` — the raw files, moved here.

Modify: `StatVerdict/StatVerdict.toc`, `StatVerdict/Core/SV_ProfileRepository.lua`, `StatVerdict/Core/SV_EvaluationContext.lua`, `StatVerdict/Core/SV_SpecSnapshot.lua`, `StatVerdict/UI/SV_RightPanelMode.lua`, `StatVerdict/UI/SV_DashboardLayout.lua`, `StatVerdict/UI/SV_SettingsPanel.lua`, `StatVerdict/UI/SV_BisProgressPanel.lua`, `StatVerdict/UI/SV_Render.lua`, `StatVerdict/UI/SV_ManualDrawerPanel.lua`, `StatVerdict/STORE.md`, `StatVerdict/VERDICT_MODEL.md`, `tools/live_benchmark_engine.py` (defaults only), `.github/workflows/weekly-benchmarks.yml`, `.github/workflows/benchmark-retry.yml`, `tools/README.md` (edited, left uncommitted, see constraints).

Delete: the six `StatVerdict/Data/Generated/SV_LiveBenchmarkData_*.lua` files and (moved) the six `.json` files from the addon folder.

---

## Phase 1 — Data

### Task 1: Popular slot selection

**Files:**
- Create: `tools/addon_benchmarks.py`
- Create: `tools/tests/addon_fixtures.py`
- Create: `tools/tests/test_addon_benchmarks.py`

**Interfaces:**
- Consumes: raw `gearCohorts.<TOP_n>.popularItems` (dict slot key → list of item dicts with `itemId`, `name`, `count`, `usagePercent`, `variants[{bonusIds, count, itemLevel}]`).
- Produces: `SLOT_ORDER`, `pick_popular_slots(popular_items: dict) -> list[dict]`, internal `_pool(popular_items, keys) -> list[dict]`, `_top_variant(item) -> dict | None`. Each slot dict: `{"slot": str, "item": {"item_id": int, "name": str, "bonus_ids": list[int]}, "usagePercent": float}`.

- [ ] **Step 1: Write the fixtures file**

`tools/tests/addon_fixtures.py`:

```python
"""Synthetic raw benchmark data shared by the addon compaction and Lua tests."""

from __future__ import annotations

from typing import Any

SLOT_KEYS = ("HEAD", "HANDS", "NECK", "WAIST", "SHOULDER", "LEGS", "BACK", "FEET", "CHEST", "WRIST", "MAIN_HAND")


def make_item(item_id: int, name: str, count: int, percent: float, bonus: list[int]) -> dict[str, Any]:
    return {
        "itemId": item_id,
        "name": name,
        "count": count,
        "usagePercent": percent,
        "confidence95LowerPercent": 0.0,
        "observedBisCandidate": False,
        "variants": [
            {"itemLevel": 330.0, "bonusIds": list(bonus), "gemIds": [], "enchantIds": [], "tier": None, "count": count},
        ],
    }


def make_popular_items() -> dict[str, list[dict[str, Any]]]:
    popular: dict[str, list[dict[str, Any]]] = {}
    for index, key in enumerate(SLOT_KEYS):
        base = 1000 + index * 10
        popular[key] = [
            make_item(base, f"{key} favourite", 60, 60.0, [100 + index]),
            make_item(base + 1, f"{key} second", 20, 20.0, [200 + index]),
        ]
    # Rings: item 1901 is worn by 60 in slot 1 and 10 in slot 2 (pooled 70),
    # item 1902 by 20 and 55 (pooled 75) -> 1902 ranks first, 1901 second.
    popular["FINGER_1"] = [make_item(1901, "Ring A", 60, 60.0, [301]), make_item(1902, "Ring B", 20, 20.0, [302])]
    popular["FINGER_2"] = [make_item(1902, "Ring B", 55, 55.0, [302]), make_item(1901, "Ring A", 10, 10.0, [301])]
    # Trinkets pooled: Alpha 50, Gamma 45, Beta 35, Tiny 1 (below the 3% floor).
    popular["TRINKET_1"] = [make_item(5001, "Trinket Alpha", 50, 50.0, [401]), make_item(5002, "Trinket Beta", 25, 25.0, [402])]
    popular["TRINKET_2"] = [
        make_item(5003, "Trinket Gamma", 45, 45.0, [403]),
        make_item(5002, "Trinket Beta", 10, 10.0, [402]),
        make_item(5004, "Trinket Tiny", 1, 1.0, [404]),
    ]
    return popular


def make_stat_cohort(
    sample: int,
    crit: float,
    haste: float,
    mastery: float,
    versatility: float,
    primaries: tuple[float, float, float] = (2400.0, 500.0, 300.0),
    average_item_level: float = 326.9,
    status: str = "ok",
    minimum: int = 25,
) -> dict[str, Any]:
    strength, agility, intellect = primaries
    return {
        "status": status,
        "requestedSize": sample,
        "rankCeiling": sample,
        "sampleSize": sample,
        "minimumSample": minimum,
        "completeness": 1.0,
        "confidence": "high",
        "averageItemLevel": average_item_level,
        "meanItemLevel": average_item_level,
        "statTargets": {
            "method": "median_simc_reconstructed_loadout",
            "stats": {
                "strength": strength,
                "agility": agility,
                "intellect": intellect,
                "stamina": 70000.0,
                "crit": crit,
                "haste": haste,
                "mastery": mastery,
                "versatility": versatility,
            },
        },
    }


def make_gear_cohort(sample: int, status: str = "ok") -> dict[str, Any]:
    return {
        "status": status,
        "rankCeiling": sample,
        "sampleSize": sample,
        "minimumSample": 25,
        "popularItems": make_popular_items(),
    }


def make_profile(spec_key_class: str = "death-knight", primary: str = "strength") -> dict[str, Any]:
    cohorts = {
        "TOP_25": make_stat_cohort(25, 1300, 950, 700, 450),
        "TOP_100": make_stat_cohort(100, 1140, 900, 680, 430),
        "TOP_200": make_stat_cohort(200, 1100, 880, 690, 420),
    }
    gear = {"TOP_25": make_gear_cohort(25), "TOP_100": make_gear_cohort(100), "TOP_200": make_gear_cohort(200)}
    hero_31 = {
        "id": 31,
        "name": "Hero Talent 31",
        "status": "ok",
        "fallback": "spec",
        "cohorts": {
            "TOP_25": make_stat_cohort(25, 600, 1000, 900, 590, minimum=10),
            "TOP_100": make_stat_cohort(100, 600, 1000, 900, 590),
            "TOP_200": make_stat_cohort(200, 600, 1000, 900, 590, minimum=50),
        },
    }
    hero_33 = {
        "id": 33,
        "name": "Hero Talent 33",
        "status": "ok",
        "fallback": "spec",
        "cohorts": {
            "TOP_25": make_stat_cohort(25, 1300, 400, 1000, 700, minimum=10),
            "TOP_100": make_stat_cohort(100, 1300, 400, 1000, 700),
            "TOP_200": make_stat_cohort(200, 1300, 400, 1000, 700, minimum=50),
        },
    }
    hero_bad = {
        "id": 35,
        "name": "Hero Talent 35",
        "status": "insufficient",
        "fallback": "spec",
        "cohorts": {"TOP_100": make_stat_cohort(3, 1, 1, 1, 1, status="insufficient")},
    }
    return {
        "status": "ok",
        "class": spec_key_class,
        "spec": "Blood",
        "role": "tank",
        "primaryStat": primary,
        "cohorts": cohorts,
        "gearCohorts": gear,
        "heroTalentTrees": {"HERO_31": hero_31, "HERO_33": hero_33, "HERO_35": hero_bad},
    }


def make_raw_database(generated_at: str, profiles: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": 5,
        "generatedAt": generated_at,
        "source": {"season": "season-mn-2", "regions": ["eu", "us"], "aggregation": "median"},
        "profiles": profiles if profiles is not None else {"DEATHKNIGHT_BLOOD": make_profile()},
        "externalSimulations": {"status": "unavailable"},
    }
```

- [ ] **Step 2: Write the failing tests**

`tools/tests/test_addon_benchmarks.py`:

```python
from __future__ import annotations

import unittest

from tools.addon_benchmarks import pick_popular_slots
from tools.tests.addon_fixtures import make_item, make_popular_items


class PickPopularSlotsTests(unittest.TestCase):
    def test_single_slot_takes_top_item_and_its_most_used_variant(self) -> None:
        popular = {
            "HEAD": [
                {
                    **make_item(1, "Helm", 60, 60.0, [1]),
                    "variants": [
                        {"itemLevel": 320.0, "bonusIds": [7], "count": 10},
                        {"itemLevel": 330.0, "bonusIds": [8, 9], "count": 50},
                    ],
                },
                make_item(2, "Other Helm", 20, 20.0, [2]),
            ]
        }
        slots = pick_popular_slots(popular)
        self.assertEqual(1, len(slots))
        self.assertEqual("Helm", slots[0]["slot"])
        self.assertEqual({"item_id": 1, "name": "Helm", "bonus_ids": [8, 9]}, slots[0]["item"])
        self.assertEqual(60.0, slots[0]["usagePercent"])

    def test_rings_pool_both_slots_and_stay_distinct(self) -> None:
        slots = pick_popular_slots(make_popular_items())
        rings = [s for s in slots if s["slot"] == "Ring"]
        self.assertEqual([1902, 1901], [s["item"]["item_id"] for s in rings])
        self.assertEqual([75.0, 70.0], [s["usagePercent"] for s in rings])

    def test_trinket_slots_are_two_distinct_items(self) -> None:
        slots = pick_popular_slots(make_popular_items())
        trinkets = [s for s in slots if s["slot"] == "Trinket"]
        self.assertEqual([5001, 5003], [s["item"]["item_id"] for s in trinkets])

    def test_missing_slot_is_skipped_and_order_follows_the_panel(self) -> None:
        slots = pick_popular_slots(make_popular_items())
        labels = [s["slot"] for s in slots]
        self.assertNotIn("Off Hand", labels)
        self.assertEqual(
            ["Helm", "Hands", "Neck", "Waist", "Shoulders", "Legs", "Cloak", "Feet", "Chest",
             "Ring", "Ring", "Trinket", "Bracers", "Trinket", "Main Hand"],
            labels,
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: FAIL / ERROR `ModuleNotFoundError: No module named 'tools.addon_benchmarks'`.

- [ ] **Step 4: Write the minimal implementation**

`tools/addon_benchmarks.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/addon_benchmarks.py tools/tests/addon_fixtures.py tools/tests/test_addon_benchmarks.py
git commit -m "feat: pick the most popular item per slot for the addon benchmark file"
```

### Task 2: Trinket ranking and tiers

**Files:**
- Modify: `tools/addon_benchmarks.py`
- Modify: `tools/tests/test_addon_benchmarks.py`

**Interfaces:**
- Consumes: `_pool`, `_item_fields` from Task 1.
- Produces: `TIER_THRESHOLDS`, `TRINKET_LIMIT`, `rank_trinkets(popular_items) -> list[dict]` with dicts `{"item_id", "name", "bonus_ids", "tier", "usagePercent"}` ordered by usage, highest first.

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_addon_benchmarks.py` (add `rank_trinkets` to the import line: `from tools.addon_benchmarks import pick_popular_slots, rank_trinkets`), before the `if __name__` block:

```python
class RankTrinketsTests(unittest.TestCase):
    def test_pooled_usage_orders_and_assigns_tiers(self) -> None:
        ranked = rank_trinkets(make_popular_items())
        self.assertEqual([5001, 5003, 5002], [t["item_id"] for t in ranked])
        self.assertEqual(["S", "S", "A"], [t["tier"] for t in ranked])
        self.assertEqual([50.0, 45.0, 35.0], [t["usagePercent"] for t in ranked])

    def test_below_three_percent_is_not_listed(self) -> None:
        ranked = rank_trinkets(make_popular_items())
        self.assertNotIn(5004, [t["item_id"] for t in ranked])

    def test_tier_boundaries(self) -> None:
        popular = {
            "TRINKET_1": [
                make_item(1, "s", 40, 40.0, [1]),
                make_item(2, "a", 20, 20.0, [1]),
                make_item(3, "b", 8, 8.0, [1]),
                make_item(4, "c", 3, 3.0, [1]),
                make_item(5, "none", 2, 2.99, [1]),
            ]
        }
        ranked = rank_trinkets(popular)
        self.assertEqual(["S", "A", "B", "C"], [t["tier"] for t in ranked])

    def test_same_item_in_both_slots_is_listed_once(self) -> None:
        popular = {
            "TRINKET_1": [make_item(9, "x", 30, 30.0, [1])],
            "TRINKET_2": [make_item(9, "x", 20, 20.0, [1])],
        }
        ranked = rank_trinkets(popular)
        self.assertEqual(1, len(ranked))
        self.assertEqual(50.0, ranked[0]["usagePercent"])
        self.assertEqual("S", ranked[0]["tier"])

    def test_list_is_capped_at_the_panel_row_count(self) -> None:
        popular = {"TRINKET_1": [make_item(i, f"t{i}", 5, 5.0, [1]) for i in range(1, 30)]}
        self.assertEqual(16, len(rank_trinkets(popular)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: ImportError for `rank_trinkets`.

- [ ] **Step 3: Implement**

Add to `tools/addon_benchmarks.py` after `SLOT_ORDER`:

```python
# (tier, minimum pooled usage percent). Initial values; reviewed with the user
# against real data before they are locked (plan Task 5).
TIER_THRESHOLDS: tuple[tuple[str, float], ...] = (("S", 40.0), ("A", 20.0), ("B", 8.0), ("C", 3.0))
TRINKET_LIMIT = 16  # rows in the addon's Ranked Trinkets panel
```

and at the end of the file:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/addon_benchmarks.py tools/tests/test_addon_benchmarks.py
git commit -m "feat: rank trinkets by pooled usage with S-C tiers for the addon benchmark file"
```

### Task 3: Stat targets, priority profiles and measured primary stat

**Files:**
- Modify: `tools/addon_benchmarks.py`
- Modify: `tools/tests/test_addon_benchmarks.py`

**Interfaces:**
- Consumes: `LEVELS` from Task 1.
- Produces: `TARGET_KEYS`, `PRIORITY_KEYS`, `TIE_RATIO`, `MIN_SLOTS`, `MIN_ITEM_LEVEL`, `valid_cohort(cohort) -> bool`, `secondary_stats(cohort, key_map) -> dict[str, float]`, `order_and_tiers(stats) -> tuple[list[str], list[list[str]]]`, `build_priority_profiles(profile, cohort_key, spec_cohort) -> list[dict]`, `measured_primary_stat(cohort, fallback) -> str`.

- [ ] **Step 1: Write the failing tests**

Add imports (`build_priority_profiles, measured_primary_stat, order_and_tiers, secondary_stats, valid_cohort, TARGET_KEYS`) and `from tools.tests.addon_fixtures import make_profile, make_stat_cohort` and append:

```python
class TargetsAndPriorityTests(unittest.TestCase):
    def test_secondary_stats_are_renamed_for_the_addon(self) -> None:
        cohort = make_stat_cohort(100, 1140, 900, 680, 430)
        self.assertEqual(
            {"critical_strike": 1140.0, "haste": 900.0, "mastery": 680.0, "versatility": 430.0},
            secondary_stats(cohort, TARGET_KEYS),
        )

    def test_order_and_tiers_group_stats_within_five_percent(self) -> None:
        order, tiers = order_and_tiers({"haste": 1000.0, "mastery": 900.0, "critical-strike": 600.0, "versatility": 590.0})
        self.assertEqual(["haste", "mastery", "critical-strike", "versatility"], order)
        self.assertEqual([["haste"], ["mastery"], ["critical-strike", "versatility"]], tiers)

    def test_priority_rows_per_valid_hero_tree_plus_spec_wide_row(self) -> None:
        profile = make_profile()
        rows = build_priority_profiles(profile, "TOP_100", profile["cohorts"]["TOP_100"])
        self.assertEqual([31, 33, None], [r.get("heroSubTreeID") for r in rows])
        self.assertEqual(["haste", "mastery", "critical-strike", "versatility"], rows[0]["order"])
        self.assertEqual(["critical-strike", "mastery", "versatility", "haste"], rows[1]["order"])
        self.assertEqual(["critical-strike", "haste", "mastery", "versatility"], rows[2]["order"])
        self.assertTrue(all(r["context"] == "Mythic+" for r in rows))

    def test_insufficient_hero_tree_gets_no_row(self) -> None:
        profile = make_profile()
        rows = build_priority_profiles(profile, "TOP_100", profile["cohorts"]["TOP_100"])
        self.assertNotIn(35, [r.get("heroSubTreeID") for r in rows])

    def test_valid_cohort_needs_ok_status_and_minimum_sample(self) -> None:
        self.assertTrue(valid_cohort(make_stat_cohort(100, 1, 1, 1, 1)))
        self.assertFalse(valid_cohort(make_stat_cohort(100, 1, 1, 1, 1, status="insufficient")))
        self.assertFalse(valid_cohort(make_stat_cohort(20, 1, 1, 1, 1, minimum=25)))
        self.assertFalse(valid_cohort(None))

    def test_primary_stat_is_measured_not_trusted(self) -> None:
        # Devourer Demon Hunter is an Intellect spec but the raw label says agility.
        cohort = make_stat_cohort(100, 1, 1, 1, 1, primaries=(300.0, 500.0, 2400.0))
        self.assertEqual("intellect", measured_primary_stat(cohort, "agility"))
        empty = make_stat_cohort(100, 1, 1, 1, 1, primaries=(0.0, 0.0, 0.0))
        self.assertEqual("agility", measured_primary_stat(empty, "agility"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: ImportError for the new names.

- [ ] **Step 3: Implement**

Add after `TRINKET_LIMIT`:

```python
MIN_SLOTS = 10  # same as the addon's MIN_CONTEXT_ITEMS
MIN_ITEM_LEVEL = 250.0  # same as the addon's MIN_VALID_MAX_LEVEL_TARGET_ILVL
TIE_RATIO = 0.05  # a stat within 5% of the previous one shares its priority tier
# Live database key -> key used in the addon's statTargets / priority rows.
TARGET_KEYS = {"crit": "critical_strike", "haste": "haste", "mastery": "mastery", "versatility": "versatility"}
PRIORITY_KEYS = {"crit": "critical-strike", "haste": "haste", "mastery": "mastery", "versatility": "versatility"}
PRIMARY_KEYS = ("strength", "agility", "intellect")
```

and at the end of the file:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/addon_benchmarks.py tools/tests/test_addon_benchmarks.py
git commit -m "feat: derive stat targets, hero priority rows and measured primary stat for the addon"
```

### Task 4: Context assembly, addon data, Lua writer, CLI and report

**Files:**
- Modify: `tools/addon_benchmarks.py`
- Modify: `tools/tests/test_addon_benchmarks.py`

**Interfaces:**
- Consumes: everything from Tasks 1-3; `to_lua` from `tools/live_benchmark_engine.py`.
- Produces: `build_level_context(profile, cohort_key) -> dict | None`, `build_profile(spec_key, profile) -> dict | None`, `build_addon_data(databases: list[dict]) -> dict`, `render_lua(data) -> str`, `write_addon_file(data, path) -> int` (returns byte size, raises `ValueError` over `MAX_FILE_BYTES`), `build_report(data) -> str`, `load_databases(directory) -> list[dict]`, `main(argv=None) -> int`.
- Output data shape (the contract the addon reads):
  `{"schemaVersion": 1, "generatedAt": "<oldest raw generatedAt>", "source": {...}, "profiles": {specKey: {"specKey", "classToken", "primaryStat", "levels": {"ELITE"|"STANDARD"|"BROAD": context}}}}` where `context = {"targets": {...}, "bis": {"label": "Popular", "slots": [...]}, "trinkets": [...], "priorityProfiles": [...], "benchmark": {...}}`.

- [ ] **Step 1: Write the failing tests**

Add imports (`MAX_FILE_BYTES, build_addon_data, build_level_context, build_profile, build_report, render_lua, write_addon_file`) plus `import tempfile`, `from pathlib import Path`, `from tools.tests.addon_fixtures import make_gear_cohort, make_raw_database` and append:

```python
class AssemblyTests(unittest.TestCase):
    def test_level_context_has_the_shape_the_addon_reads(self) -> None:
        profile = make_profile()
        context = build_level_context(profile, "TOP_100")
        targets = context["targets"]
        self.assertEqual("MYTHIC_PLUS", targets["sourceGoal"])
        self.assertEqual(326.9, targets["averageItemLevel"])
        self.assertEqual(15, targets["itemCount"])
        self.assertEqual(
            {"critical_strike": 1140.0, "haste": 900.0, "mastery": 680.0, "versatility": 430.0},
            targets["statTargets"]["stats"],
        )
        self.assertEqual("Popular", context["bis"]["label"])
        self.assertEqual(15, len(context["bis"]["slots"]))
        self.assertEqual(["S", "S", "A"], [t["tier"] for t in context["trinkets"]])
        self.assertEqual(
            {"level": "STANDARD", "cohort": "TOP_100", "sampleSize": 100, "minimumSample": 25,
             "confidence": "high", "completeness": 1.0},
            context["benchmark"],
        )

    def test_invalid_cohort_gives_no_context(self) -> None:
        profile = make_profile()
        profile["cohorts"]["TOP_25"]["status"] = "insufficient"
        self.assertIsNone(build_level_context(profile, "TOP_25"))
        self.assertIsNotNone(build_level_context(profile, "TOP_100"))

    def test_too_few_slots_or_low_item_level_gives_no_context(self) -> None:
        profile = make_profile()
        profile["gearCohorts"]["TOP_100"]["popularItems"] = {"HEAD": make_gear_cohort(100)["popularItems"]["HEAD"]}
        self.assertIsNone(build_level_context(profile, "TOP_100"))
        profile = make_profile()
        profile["cohorts"]["TOP_100"]["averageItemLevel"] = 200.0
        self.assertIsNone(build_level_context(profile, "TOP_100"))

    def test_profile_keeps_only_valid_levels_and_measured_primary(self) -> None:
        profile = make_profile(spec_key_class="demon-hunter", primary="agility")
        for cohort in profile["cohorts"].values():
            cohort["statTargets"]["stats"].update({"strength": 300.0, "agility": 500.0, "intellect": 2400.0})
        profile["cohorts"]["TOP_25"]["status"] = "insufficient"
        built = build_profile("DEMONHUNTER_DEVOURER", profile)
        self.assertEqual("DEMONHUNTER", built["classToken"])
        self.assertEqual("intellect", built["primaryStat"])
        self.assertEqual(["BROAD", "STANDARD"], sorted(built["levels"]))

    def test_profile_that_is_not_ok_is_left_out(self) -> None:
        profile = make_profile()
        profile["status"] = "failed"
        self.assertIsNone(build_profile("DEATHKNIGHT_BLOOD", profile))

    def test_addon_data_uses_the_oldest_generated_at(self) -> None:
        older = make_raw_database("2026-09-01T00:00:00Z")
        newer = make_raw_database("2026-09-20T00:00:00Z", {"MAGE_FIRE": make_profile("mage", "intellect")})
        data = build_addon_data([newer, older])
        self.assertEqual("2026-09-01T00:00:00Z", data["generatedAt"])
        self.assertEqual(1, data["schemaVersion"])
        self.assertEqual(["DEATHKNIGHT_BLOOD", "MAGE_FIRE"], sorted(data["profiles"]))
        self.assertEqual("season-mn-2", data["source"]["season"])

    def test_lua_output_and_size_gate(self) -> None:
        data = build_addon_data([make_raw_database("2026-09-26T00:00:00Z")])
        text = render_lua(data)
        self.assertTrue(text.startswith("local addonName, ns = ...\n"))
        self.assertIn("ns.MythicPlusBenchmarks = {", text)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out" / "SV_MythicPlusBenchmarks.lua"
            size = write_addon_file(data, path)
            self.assertEqual(size, path.stat().st_size)
            self.assertLess(size, MAX_FILE_BYTES)
        oversized = {"schemaVersion": 1, "generatedAt": "x", "source": {}, "profiles": {"a": "x" * (MAX_FILE_BYTES + 1)}}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_addon_file(oversized, Path(tmp) / "big.lua")
            self.assertFalse((Path(tmp) / "big.lua").exists())

    def test_report_lists_each_spec(self) -> None:
        data = build_addon_data([make_raw_database("2026-09-26T00:00:00Z")])
        report = build_report(data)
        self.assertIn("DEATHKNIGHT_BLOOD", report)
        self.assertIn("STANDARD", report)
        self.assertIn("tiers S:2 A:1 B:0 C:0", report)
        self.assertIn("clear favourites (>=40%): 15/15", report)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tools.tests.test_addon_benchmarks -v`
Expected: ImportError for the new names.

- [ ] **Step 3: Implement**

Add near the top of `tools/addon_benchmarks.py` (after `from typing import Any`):

```python
import argparse
import json
import sys
from pathlib import Path

try:
    from tools.live_benchmark_engine import to_lua
except ModuleNotFoundError:
    # Run as "python tools/addon_benchmarks.py": sys.path[0] is tools/, not the repo root.
    from live_benchmark_engine import to_lua
```

Add `MAX_FILE_BYTES = 5 * 1024 * 1024` after `MIN_ITEM_LEVEL`. At the end of the file add:

```python
def _class_token(value: Any) -> str:
    return "".join(ch for ch in str(value).upper() if ch.isalpha())


def build_level_context(profile: dict[str, Any], cohort_key: str) -> dict[str, Any] | None:
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
    level = next(name for name, key in LEVELS.items() if key == cohort_key)
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
        "priorityProfiles": build_priority_profiles(profile, cohort_key, cohort),
        "benchmark": {
            "level": level,
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
    levels: dict[str, Any] = {}
    for level, cohort_key in LEVELS.items():
        context = build_level_context(profile, cohort_key)
        if context:
            levels[level] = context
    if not levels:
        return None
    reference_key = LEVELS["STANDARD"] if "STANDARD" in levels else LEVELS[sorted(levels)[0]]
    reference = (profile.get("cohorts") or {}).get(reference_key)
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
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return size


def build_report(data: dict[str, Any]) -> str:
    """Per-spec numbers used to review tier thresholds and slot favourites."""
    lines = [f"generatedAt {data['generatedAt']}, {len(data['profiles'])} specs"]
    for spec_key in sorted(data["profiles"]):
        profile = data["profiles"][spec_key]
        for level in ("ELITE", "STANDARD", "BROAD"):
            context = profile["levels"].get(level)
            if not context:
                lines.append(f"{spec_key} {level}: no data")
                continue
            slots = context["bis"]["slots"]
            favourites = sum(1 for s in slots if s["usagePercent"] >= 40.0)
            counts = {tier: 0 for tier, _ in TIER_THRESHOLDS}
            for trinket in context["trinkets"]:
                counts[trinket["tier"]] += 1
            tiers = " ".join(f"{tier}:{counts[tier]}" for tier, _ in TIER_THRESHOLDS)
            bench = context["benchmark"]
            lines.append(
                f"{spec_key} {level}: sample {bench['sampleSize']} ({bench['confidence']}), "
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
```

The test for `test_report_lists_each_spec` expects `clear favourites (>=40%): 15/15`: the fixture gives every slot a 60% favourite or, for pooled rings/trinkets, 70+/50+, so all 15 slots are >= 40%. If that assertion fails on the trinket second slot (Gamma 45%) recheck the fixture, not the threshold.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s tools/tests -v`
Expected: all tests PASS (existing engine tests included).

- [ ] **Step 5: Commit**

```bash
git add tools/addon_benchmarks.py tools/tests/test_addon_benchmarks.py
git commit -m "feat: build the compact Mythic+ addon file with size gate, report and CLI"
```

### Task 5: Run on real data, review thresholds with the user, write the real file

**Files:**
- Create (generated): `StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua`

**Interfaces:**
- Consumes: the six raw files (still in `StatVerdict/Data/Generated/` at this point).
- Produces: the committed addon data file; a report the user reviews.

- [ ] **Step 1: Print the review report from the real raw files**

Run: `python tools/addon_benchmarks.py --inputs StatVerdict/Data/Generated --report > "$TEMP/benchmark_report.txt"` (in PowerShell use `$env:TEMP`), then read the file.
Expected: a line per spec and level, 40 specs x 3 levels, no traceback.

- [ ] **Step 2: Check the numbers**

From the report, compute and note: how many spec/level lines say "no data"; the spread of "clear favourites"; how many specs have zero S-tier trinkets or more than 3 S-tier trinkets; the specs where the measured primary differs from the raw label (for these, run a one-off Python check printing `profile["primaryStat"]` for the raw file and the report's value; expect Devourer to change from agility to intellect).

- [ ] **Step 3: Review with the user (STOP)**

Explain to the user in simple Greek, no code: how many slots have a clear favourite, whether the tier limits (S 40 / A 20 / B 8 / C 3) look sensible on real data, and what changed for Devourer. Propose new limits only if the numbers show a problem (for example most specs with no S trinket). Wait for the user's decision. Do not continue until they agree; if they change limits, update `TIER_THRESHOLDS`, update the tier-boundary test in Task 2 and rerun `python -m unittest discover -s tools/tests -v`.

- [ ] **Step 4: Write the real file**

Run: `python tools/addon_benchmarks.py --inputs StatVerdict/Data/Generated`
Expected: `Wrote StatVerdict\Data\Generated\SV_MythicPlusBenchmarks.lua (<5 MB, 40 specs)`.

- [ ] **Step 5: Commit**

```bash
git add StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua tools/addon_benchmarks.py tools/tests/test_addon_benchmarks.py
git commit -m "data: first compact Mythic+ benchmark file for the addon"
```

### Task 6: Move raw files out of the addon folder and update the workflows

**Files:**
- Move: six `StatVerdict/Data/Generated/SV_LiveBenchmarkData_*.json` -> `tools/data/live/`
- Delete: six `StatVerdict/Data/Generated/SV_LiveBenchmarkData_*.lua`
- Modify: `tools/live_benchmark_engine.py:1717-1718`, `.github/workflows/weekly-benchmarks.yml`, `.github/workflows/benchmark-retry.yml`, `tools/README.md`

**Interfaces:**
- Consumes: `python tools/addon_benchmarks.py --inputs tools/data/live --out StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua` (Task 4 CLI defaults).
- Produces: workflows that keep raw JSON in `tools/data/live/`, never commit raw `.lua`, and regenerate + commit the compact file.

- [ ] **Step 1: Move and delete**

```bash
mkdir -p tools/data/live
for role in DPS1 DPS2 DPS3 DPS4 Tank Healer; do
  git mv "StatVerdict/Data/Generated/SV_LiveBenchmarkData_${role}.json" "tools/data/live/SV_LiveBenchmarkData_${role}.json"
  git rm -q "StatVerdict/Data/Generated/SV_LiveBenchmarkData_${role}.lua"
done
python tools/addon_benchmarks.py
```

Expected: the last command prints `Wrote ... 40 specs` (default `--inputs tools/data/live`); `git status --short` shows six renames, six deletions and no file over 1 MB left in `StatVerdict/Data/Generated` except `SV_ProfileData.*`.

- [ ] **Step 2: Engine defaults**

In `tools/live_benchmark_engine.py` lines 1717-1718 replace the two defaults:

```python
    parser.add_argument("--json-out", type=Path, default=Path("tools/data/live/SV_LiveBenchmarkData.json"))
    parser.add_argument("--lua-out", type=Path, default=Path("tools/data/live/SV_LiveBenchmarkData.lua"))
```

Also change `tools/README.md` line 120 to `--validate-only tools/data/live/SV_LiveBenchmarkData_Tank.json`, and add under "## Automation" a short paragraph: raw data lives in `tools/data/live/` and is never shipped; `python tools/addon_benchmarks.py` turns it into `StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua`, the only benchmark file the addon loads. Do not `git add tools/README.md` (user's pending edits).

- [ ] **Step 3: Weekly workflow, merge job**

In `.github/workflows/weekly-benchmarks.yml`, replace the two steps "Recombine the 4 healer groups..." and "Place the DPS/Tank files..." and the commit step with:

```yaml
      - name: Recombine the 4 healer groups into one Healer file
        env:
          COHORTS: ${{ inputs.cohorts || '25,100,200' }}
        run: |
          python tools/live_benchmark_engine.py \
            --cohorts "$COHORTS" \
            --merge-inputs "partials/partial-healer-1.json,partials/partial-healer-2.json,partials/partial-healer-3.json,partials/partial-healer-4.json" \
            --json-out tools/data/live/SV_LiveBenchmarkData_Healer.json \
            --lua-out /tmp/healer-raw.lua

      - name: Place the DPS/Tank files under their final names
        shell: bash
        run: |
          declare -A rename=(
            [dps-1]=DPS1 [dps-2]=DPS2 [dps-3]=DPS3 [dps-4]=DPS4 [tank]=Tank
          )
          for group in "${!rename[@]}"; do
            label="${rename[$group]}"
            cp "partials/partial-${group}.json" "tools/data/live/SV_LiveBenchmarkData_${label}.json"
          done

      - name: Build the addon's Mythic+ file
        run: python tools/addon_benchmarks.py --inputs tools/data/live --out StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua

      - name: Commit validated update
        shell: bash
        run: |
          if [ -z "$(git status --porcelain -- StatVerdict/Data/Generated tools/data/live tools/data/benchmark_retry_queue.json)" ]; then
            echo "No benchmark changes."
            exit 0
          fi
          git config user.name "StatVerdict Benchmark Bot"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add tools/data/live/SV_LiveBenchmarkData_*.json
          git add StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua
          git add tools/data/benchmark_retry_queue.json
          git commit -m "data: refresh live benchmarks"
          # main can move while this job runs (a code push, or another
          # instance of this workflow). Only the generated data files
          # changed here, so rebasing onto the latest main is safe -
          # retry a few times instead of losing a successful run's result.
          for attempt in 1 2 3 4 5; do
            if git push; then
              exit 0
            fi
            echo "Push rejected (attempt $attempt/5), rebasing onto latest main and retrying..."
            git fetch origin main
            git rebase origin/main
          done
          echo "::error::Could not push benchmark update after 5 attempts."
          exit 1
```

Also update the comment block above "Validate full spec coverage" so it says the per-role files are kept in `tools/data/live/` (outside the addon folder) and only the compact file goes into the addon.

- [ ] **Step 4: Retry workflow**

In `.github/workflows/benchmark-retry.yml`: (a) in the "Route each retried spec back" step replace `StatVerdict/Data/Generated/SV_LiveBenchmarkData_*.json` with `tools/data/live/SV_LiveBenchmarkData_*.json` in the `for target in` loop and in the final `--merge-inputs "$(ls ...)"` line; (b) in the loop replace `lua="${target%.json}.lua"` and `--lua-out "$lua"` with `--lua-out /tmp/retry-fold.lua` (delete the `lua=` line); (c) add after that step:

```yaml
      - name: Build the addon's Mythic+ file
        if: steps.queue.outputs.pending == 'true'
        run: python tools/addon_benchmarks.py --inputs tools/data/live --out StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua
```

(d) in "Commit retried update" replace the status path list with `StatVerdict/Data/Generated tools/data/live tools/data/benchmark_retry_queue.json` and the two `git add ...SV_LiveBenchmarkData_*` lines with:

```bash
          git add tools/data/live/SV_LiveBenchmarkData_*.json
          git add StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua
```

- [ ] **Step 5: Verify the YAML and the tests**

Run: `python -c "import yaml,sys; [yaml.safe_load(open(p, encoding='utf-8')) for p in ('.github/workflows/weekly-benchmarks.yml','.github/workflows/benchmark-retry.yml')]; print('yaml ok')"` (if `yaml` is missing run `pip install pyyaml` first) and `python -m unittest discover -s tools/tests -v`.
Expected: `yaml ok`, all tests PASS. Then `grep -rn "Data/Generated/SV_LiveBenchmark" .github tools *.md` must print nothing.

- [ ] **Step 6: Commit and push, then dispatch one real run**

```bash
git add tools/data/live tools/live_benchmark_engine.py .github/workflows/weekly-benchmarks.yml .github/workflows/benchmark-retry.yml StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua
git commit -m "Move raw benchmark data out of the addon folder; workflows build the compact Mythic+ file"
git push
gh workflow run weekly-benchmarks.yml
```

Tell the user (Greek, simple) that a full run takes about 23 minutes; when it finishes, check `gh run list --workflow=weekly-benchmarks.yml --limit 1` shows success and that the bot commit touched only `tools/data/live/*.json` and `SV_MythicPlusBenchmarks.lua`. If it fails, read the failing step's log with `gh run view --log-failed`, fix, and rerun before continuing to Phase 2 (the addon work does not depend on this run because the compact file already exists from Task 5).

---

## Phase 2 — Addon

### Task 7: Lua test harness (lupa) and syntax check

**Files:**
- Create: `tools/tests/test_addon_lua.py`

**Interfaces:**
- Produces: helpers in `tools/tests/test_addon_lua.py` reused by later tasks: `toc_lua_files()`, `new_runtime()`, `load_addon_file(lua, ns, relative_path)`, `write_data_file(path, generated_at)`.

- [ ] **Step 1: Install the dev-only dependency**

Run: `pip install lupa`
Expected: installs. If no wheel exists for this Python version and the build fails, tell the user, continue without it (the Lua tests skip), and treat every later "run the Lua tests" step as "review the Lua by reading it carefully" plus the user's in-game checklist.

- [ ] **Step 2: Write the harness and the syntax test**

`tools/tests/test_addon_lua.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.addon_benchmarks import build_addon_data, render_lua
from tools.tests.addon_fixtures import make_profile, make_raw_database

try:
    from lupa import LuaRuntime
except ImportError:  # optional dev dependency: pip install lupa
    LuaRuntime = None

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "StatVerdict"


def toc_lua_files() -> list[Path]:
    files = []
    for line in (ADDON / "StatVerdict.toc").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("##"):
            files.append(ADDON / line.replace("\\", "/"))
    return files


def new_runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("time = os.time")  # WoW provides time()
    return lua


def load_addon_file(lua, ns, relative_path: str) -> None:
    loader = lua.eval("function(path) local f, err = loadfile(path) if not f then error(err) end return f end")
    loader(str(ADDON / relative_path))("StatVerdict", ns)


def write_data_file(path: Path, generated_at: str, profiles: dict | None = None) -> None:
    data = build_addon_data([make_raw_database(generated_at, profiles)])
    path.write_text(render_lua(data), encoding="utf-8")


def now_stamp(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AddonLuaSyntaxTests(unittest.TestCase):
    def test_every_toc_file_compiles(self) -> None:
        lua = new_runtime()
        check = lua.eval("function(src, name) local f, err = load(src, name) if not f then return err end return nil end")
        for path in toc_lua_files():
            self.assertTrue(path.exists(), f"{path} is listed in the .toc but missing")
            error = check(path.read_text(encoding="utf-8-sig"), "@" + path.name)
            self.assertIsNone(error, f"{path.name}: {error}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run**

Run: `python -m unittest tools.tests.test_addon_lua -v`
Expected: `test_every_toc_file_compiles` PASS (or skipped if lupa is missing). If a pre-existing addon file fails to compile, that is a real finding: report it to the user, do not silently fix unrelated files.

- [ ] **Step 4: Commit**

```bash
git add tools/tests/test_addon_lua.py
git commit -m "test: compile every addon Lua file from the .toc with lupa"
```

### Task 8: Benchmark levels core file and wording helper

**Files:**
- Create: `StatVerdict/Core/SV_Benchmark.lua`
- Modify: `StatVerdict/StatVerdict.toc`
- Modify: `tools/tests/test_addon_lua.py`

**Interfaces:**
- Produces (all on `ns`): `GetBenchmarkLevels() -> {key,label,meaning}[]`, `GetBenchmarkLevelInfo(key) -> table`, `GetBenchmarkLevel() -> "ELITE"|"STANDARD"|"BROAD"`, `SetBenchmarkLevel(key) -> boolean`, `GetReferenceWording(goal?) -> {popular, button, base, main, off, progress, progressSuffix, tag, manual}`.

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_addon_lua.py` before the `if __name__` block:

```python
@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class BenchmarkCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_Benchmark.lua")

    def test_default_level_is_standard(self) -> None:
        self.assertEqual("STANDARD", self.ns.GetBenchmarkLevel())

    def test_set_level_is_saved_and_unknown_is_rejected(self) -> None:
        self.assertTrue(self.ns.SetBenchmarkLevel("ELITE"))
        self.assertEqual("ELITE", self.ns.GetBenchmarkLevel())
        self.assertEqual("ELITE", self.lua.globals().StatVerdictDB.benchmarkLevel)
        self.assertFalse(self.ns.SetBenchmarkLevel("TOP_25"))
        self.assertEqual("ELITE", self.ns.GetBenchmarkLevel())

    def test_garbage_saved_value_falls_back_to_default(self) -> None:
        self.lua.globals().StatVerdictDB.benchmarkLevel = "nonsense"
        self.assertEqual("STANDARD", self.ns.GetBenchmarkLevel())

    def test_level_names_and_meaning_lines(self) -> None:
        levels = self.ns.GetBenchmarkLevels()
        self.assertEqual(["Elite", "Standard", "Broad"], [levels[i].label for i in (1, 2, 3)])
        self.assertEqual("Gear of the top 25 players", levels[1].meaning)

    def test_wording_is_popular_for_mythic_plus_and_bis_otherwise(self) -> None:
        mplus = self.ns.GetReferenceWording("MYTHIC_PLUS")
        self.assertEqual("Popular Gear", mplus.button)
        self.assertEqual("Main Spec Popular Gear", mplus.main)
        self.assertEqual("Popular Progress", mplus.progress)
        self.assertEqual(" · Standard", mplus.progressSuffix)
        self.assertEqual("Popular", mplus.tag)
        raid = self.ns.GetReferenceWording("RAID")
        self.assertEqual("Best in Slot", raid.button)
        self.assertEqual("BiS Progress", raid.progress)
        self.assertEqual("", raid.progressSuffix)
        self.assertEqual("BIS", raid.tag)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tools.tests.test_addon_lua.BenchmarkCoreTests -v`
Expected: FAIL/ERROR (`Core/SV_Benchmark.lua` does not exist).

- [ ] **Step 3: Write the file**

`StatVerdict/Core/SV_Benchmark.lua`:

```lua
local addonName, ns = ...

-- Benchmark level = which group of top players the Mythic+ data is built from.
-- Data cohorts are TOP_25 / TOP_100 / TOP_200; players see Elite / Standard / Broad.
local LEVELS = {
    { key = "ELITE", label = "Elite", meaning = "Gear of the top 25 players" },
    { key = "STANDARD", label = "Standard", meaning = "Gear of the top 100 players" },
    { key = "BROAD", label = "Broad", meaning = "Gear of the top 200 players" },
}
local DEFAULT_LEVEL = "STANDARD"

local BY_KEY = {}
for _, level in ipairs(LEVELS) do
    BY_KEY[level.key] = level
end

function ns.GetBenchmarkLevels()
    return LEVELS
end

function ns.GetBenchmarkLevelInfo(key)
    return BY_KEY[key] or BY_KEY[DEFAULT_LEVEL]
end

function ns.GetBenchmarkLevel()
    local db = _G.StatVerdictDB
    local key = type(db) == "table" and db.benchmarkLevel or nil
    if BY_KEY[key] then return key end
    return DEFAULT_LEVEL
end

function ns.SetBenchmarkLevel(key)
    if not BY_KEY[key] then return false end
    _G.StatVerdictDB = _G.StatVerdictDB or {}
    _G.StatVerdictDB.benchmarkLevel = key
    if ns.ProfileRepository and ns.ProfileRepository.RefreshProviderView then
        ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")
    end
    if ns.RequestStatAuditRefresh then ns.RequestStatAuditRefresh() end
    if ns.RefreshUpgradeIndicators then ns.RefreshUpgradeIndicators() end
    return true
end

-- Mythic+ lists are "most popular among top players", not curated Best in Slot,
-- so they are labelled honestly. Raid/PvP keep the curated BiS wording.
function ns.GetReferenceWording(goal)
    goal = goal or (ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode()) or "MYTHIC_PLUS"
    if goal == "MYTHIC_PLUS" then
        local level = ns.GetBenchmarkLevelInfo(ns.GetBenchmarkLevel())
        return {
            popular = true,
            button = "Popular Gear",
            base = "Popular Gear",
            main = "Main Spec Popular Gear",
            off = "Off Spec Popular Gear",
            progress = "Popular Progress",
            progressSuffix = " · " .. level.label,
            tag = "Popular",
        }
    end
    return {
        popular = false,
        button = "Best in Slot",
        base = "Best in Slot",
        main = "Main Spec Best in Slot",
        off = "Off Spec Best in Slot",
        progress = "BiS Progress",
        progressSuffix = "",
        tag = "BIS",
    }
end
```

- [ ] **Step 4: Register in the .toc**

In `StatVerdict/StatVerdict.toc` add `Core/SV_Benchmark.lua` on the line right after `Core/SV_Constants.lua` (it must load before `Core/SV_ProfileRepository.lua`).

- [ ] **Step 5: Run to verify pass**

Run: `python -m unittest tools.tests.test_addon_lua -v`
Expected: PASS (syntax test + 5 benchmark core tests).

- [ ] **Step 6: Commit**

```bash
git add StatVerdict/Core/SV_Benchmark.lua StatVerdict/StatVerdict.toc tools/tests/test_addon_lua.py
git commit -m "feat: benchmark levels, saved choice and Popular/BiS wording helper"
```

### Task 9: ProfileRepository reads the new Mythic+ file; hero tree priority by id

**Files:**
- Modify: `StatVerdict/Core/SV_ProfileRepository.lua`
- Modify: `StatVerdict/Core/SV_EvaluationContext.lua`
- Modify: `StatVerdict/Core/SV_SpecSnapshot.lua`
- Modify: `StatVerdict/StatVerdict.toc`
- Modify: `tools/tests/test_addon_lua.py`

**Interfaces:**
- Consumes: `ns.MythicPlusBenchmarks` (Task 4 output shape), `ns.GetBenchmarkLevel` (Task 8).
- Produces: `Repository.GetContext(specKey, goal)` returns the level context for `MYTHIC_PLUS`; `Repository.GetPriority(specKey, goal, heroTalentName, heroSubTreeID)`; `Repository.GetDataProvenance(goal)`; `ns.GetSnapshotHeroSubTreeID(profileOrContext)`; `context.heroSubTreeID` on the evaluation context.

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_addon_lua.py`:

```python
@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class RepositoryTests(unittest.TestCase):
    def build_runtime(self, generated_at: str | None = None, level: str | None = None, profiles: dict | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data_path = Path(self.tmp.name) / "SV_MythicPlusBenchmarks.lua"
        write_data_file(data_path, generated_at or now_stamp(), profiles)
        lua = new_runtime()
        ns = lua.table()
        db = lua.table()
        if level:
            db.benchmarkLevel = level
        lua.globals().StatVerdictDB = db
        lua.eval("function(path, ns) local f = assert(loadfile(path)) f('StatVerdict', ns) end")(str(data_path), ns)
        for relative in ("Core/SV_Benchmark.lua", "Core/SV_ProfileRepository.lua", "Core/SV_ItemReferenceBonuses.lua"):
            load_addon_file(lua, ns, relative)
        ns.GetStatVerdictSpecIDByKey = lua.eval("function(key) return 250 end")
        ns.GetStatVerdictRoleBySpecID = lua.eval("function(id) return 'TANK' end")
        return lua, ns

    def context(self, lua, **extra):
        table = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS", role="TANK", specID=250, classFile="DEATHKNIGHT")
        for key, value in extra.items():
            table[key] = value
        return table

    def targets(self, profile) -> dict:
        rows = profile.auditTargets.rows
        return {rows[i].key: rows[i].target for i in range(1, len(rows) + 1)}

    def test_mythic_plus_profile_is_built_from_the_live_file(self) -> None:
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertFalse(profile.invalidGeneratedContext)
        self.assertEqual("ITEM_MOD_STRENGTH_SHORT", profile.primaryStat)
        self.assertEqual(1140.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])

    def test_level_choice_changes_the_targets(self) -> None:
        lua, ns = self.build_runtime(level="ELITE")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(1300.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])

    def test_hero_tree_id_selects_its_priority_and_unknown_uses_spec_wide(self) -> None:
        lua, ns = self.build_runtime()
        hero = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=31))
        self.assertEqual("ITEM_MOD_HASTE_RATING_SHORT", hero.secondaryOrder[1])
        self.assertEqual("ITEM_MOD_MASTERY_RATING_SHORT", hero.secondaryOrder[2])
        other = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=33))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", other.secondaryOrder[1])
        unknown = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(["ITEM_MOD_CRIT_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT"],
                         [unknown.secondaryOrder[1], unknown.secondaryOrder[2]])
        mismatch = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=99))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", mismatch.secondaryOrder[1])

    def test_missing_level_shows_no_data_instead_of_another_level(self) -> None:
        profile = make_profile()
        profile["cohorts"]["TOP_25"]["status"] = "insufficient"
        lua, ns = self.build_runtime(level="ELITE", profiles={"DEATHKNIGHT_BLOOD": profile})
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))
        lua, ns = self.build_runtime(profiles={"DEATHKNIGHT_BLOOD": profile})
        self.assertIsNotNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))

    def test_stale_data_fails_closed(self) -> None:
        lua, ns = self.build_runtime(generated_at=now_stamp(days_ago=40))
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))

    def test_raid_still_reads_the_old_file_only(self) -> None:
        lua, ns = self.build_runtime()
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal="RAID")))

    def test_provider_view_lists_specs_from_the_live_file(self) -> None:
        lua, ns = self.build_runtime()
        provider = ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")
        self.assertIsNotNone(provider["DEATHKNIGHT"][250].default)

    def test_provenance_uses_the_live_file_for_mythic_plus(self) -> None:
        lua, ns = self.build_runtime()
        info = ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS")
        self.assertTrue(info.available)
        self.assertEqual("StatVerdict live benchmarks · Standard", info.sourceName)
        self.assertEqual(now_stamp()[:10], info.scrape)

    def test_popular_items_and_trinkets_keep_their_boosts(self) -> None:
        lua, ns = self.build_runtime()
        profile = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        helm = ns.GetItemReferenceInfo("item:1000", profile)
        self.assertEqual(8, helm.bonus)
        self.assertIsNotNone(helm.bis)
        # The two most popular trinkets are also in the popular-slot list, so they get
        # the +8 list bonus on top of their tier bonus (same as the old BiS data did).
        alpha = ns.GetItemReferenceInfo("item:5001", profile)
        self.assertEqual("S", alpha.trinket.tier)
        self.assertEqual(108, alpha.bonus)  # list 8 + tier 95 + rank bonus 5
        gamma = ns.GetItemReferenceInfo("item:5003", profile)
        self.assertEqual(107, gamma.bonus)  # list 8 + tier 95 + rank bonus 4
        beta = ns.GetItemReferenceInfo("item:5002", profile)
        self.assertEqual("A", beta.trinket.tier)
        self.assertEqual(70, beta.bonus)  # tier 65 + rank bonus 5 (not in the popular-slot list)
        self.assertIsNone(ns.GetItemReferenceInfo("item:1001", profile))  # second most popular helm: not listed
        self.assertIsNone(ns.GetItemReferenceInfo("item:5004", profile))  # below the 3% floor
        self.assertIsNone(ns.GetItemReferenceInfo("item:999999", profile))

    def test_boost_follows_the_selected_level(self) -> None:
        lua, ns = self.build_runtime(level="BROAD")
        profile = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1000", profile).bonus)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tools.tests.test_addon_lua.RepositoryTests -v`
Expected: FAIL (the repository still reads only `ns.GeneratedProfileData`).

- [ ] **Step 3: Repository — read path**

In `StatVerdict/Core/SV_ProfileRepository.lua`:

(a) After `local function GetRoot()` block (ends at the `return root` / `end` following it, currently line ~92) add:

```lua
local MYTHIC_PLUS_SCHEMA_VERSION = 1

-- Mythic+ data comes from the live benchmark file (tools/addon_benchmarks.py),
-- one context per benchmark level. Other goals still use the bundled root.
local function GetMythicPlusRoot()
    local root = ns.MythicPlusBenchmarks
    if type(root) ~= "table" or root.schemaVersion ~= MYTHIC_PLUS_SCHEMA_VERSION then
        return nil
    end
    if not IsRecentDate(root.generatedAt, MAX_GENERATED_AGE_DAYS) then
        return nil
    end
    return root
end

local function GetGoalRoot(goal)
    if goal == "MYTHIC_PLUS" then return GetMythicPlusRoot() end
    return GetRoot()
end
```

(b) Replace `local function GetContext(specKey, goal)` with:

```lua
local function GetContext(specKey, goal)
    if goal == "MYTHIC_PLUS" then
        local root = GetMythicPlusRoot()
        local profiles = root and root.profiles
        local profile = type(profiles) == "table" and profiles[specKey] or nil
        if type(profile) ~= "table" or type(profile.levels) ~= "table" then return nil, nil end
        local level = ns.GetBenchmarkLevel and ns.GetBenchmarkLevel() or "STANDARD"
        local context = profile.levels[level]
        return type(context) == "table" and context or nil, profile
    end
    local root = GetRoot()
    local profiles = root and root.profiles
    local profile = type(profiles) == "table" and profiles[specKey] or nil
    local contexts = type(profile) == "table" and profile.contexts or nil
    if type(contexts) ~= "table" then return nil, profile end
    local context = contexts[goal]
    return type(context) == "table" and context or nil, profile
end
```

(c) Replace `function Repository.GetDataProvenance()` with:

```lua
function Repository.GetDataProvenance(goal)
    if goal == "MYTHIC_PLUS" then
        local root = ns.MythicPlusBenchmarks
        local level = ns.GetBenchmarkLevelInfo and ns.GetBenchmarkLevelInfo(ns.GetBenchmarkLevel()) or nil
        local generatedAt = type(root) == "table" and root.generatedAt or nil
        return {
            available = GetMythicPlusRoot() ~= nil,
            generatedAt = generatedAt,
            scrape = type(generatedAt) == "string" and generatedAt:sub(1, 10) or nil,
            sourceName = "StatVerdict live benchmarks" .. (level and (" · " .. level.label) or ""),
        }
    end
    local root = ns.GeneratedProfileData
    local source = type(root) == "table" and root.source or nil
    return {
        available = GetRoot() ~= nil,
        generatedAt = type(root) == "table" and root.generatedAt or nil,
        scrape = type(source) == "table" and source.scrape or nil,
        sourceName = type(source) == "table" and source.name or nil,
    }
end
```

(d) In `Repository.BuildProviderView(goal)` replace `local root = GetRoot()` with `local root = GetGoalRoot(goal)`.

(e) In `BuildRuntimeProfile` the `source = "generated_classcodex"` and `providerLabel` stay for now (cleanup task renames the source string).

- [ ] **Step 4: Repository — hero tree priority by id**

(a) Replace `local function PriorityScore(row, heroTalentName, contextName)` with:

```lua
local function PriorityScore(row, heroTalentName, contextName, heroSubTreeID)
    if type(row) ~= "table" then return -1 end
    local score = 0
    local wantedHero = NormalizeToken(heroTalentName)
    local rowHero = NormalizeToken(row.heroTalent)
    if heroSubTreeID and row.heroSubTreeID ~= nil then
        if tonumber(row.heroSubTreeID) == tonumber(heroSubTreeID) then
            score = score + 4
        end
    elseif row.heroSubTreeID == nil and wantedHero ~= "" and rowHero == wantedHero then
        score = score + 4
    elseif row.heroSubTreeID == nil and (rowHero == "" or rowHero == "all") then
        score = score + 1
    end
```

keep the remaining lines of the function (the `wantedContext` block and `return score`) unchanged. A row that carries a `heroSubTreeID` different from the wanted one scores 0 + context, so the spec-wide row (score 1 + context) beats it; with no wanted id a hero row also scores 0 (`heroSubTreeID` is nil so the first `if` is skipped, and the `elseif`s require `row.heroSubTreeID == nil`).

(b) Change `function Repository.GetPriority(specKey, goal, heroTalentName)` to `function Repository.GetPriority(specKey, goal, heroTalentName, heroSubTreeID)` and its call `PriorityScore(row, heroTalentName, contextName)` to `PriorityScore(row, heroTalentName, contextName, heroSubTreeID)`.

(c) In `BuildRuntimeProfile` replace

```lua
    local priority = Repository.GetPriority(specKey, goal, heroTalentName)
```

with

```lua
    local heroSubTreeID = context.heroSubTreeID
        or (ns.GetSnapshotHeroSubTreeID and ns.GetSnapshotHeroSubTreeID(context))
    local priority = Repository.GetPriority(specKey, goal, heroTalentName, heroSubTreeID)
```

- [ ] **Step 5: Hero tree id plumbing**

In `StatVerdict/Core/SV_EvaluationContext.lua` add before `local function BuildCurrentContext()`:

```lua
local function GetCurrentHeroSubTreeID()
    local heroSpecID
    if C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpec then
        heroSpecID = SafeCall(C_ClassTalents.GetActiveHeroTalentSpec)
    end
    if not heroSpecID and C_ClassTalents and C_ClassTalents.GetActiveHeroTalentSpecID then
        heroSpecID = SafeCall(C_ClassTalents.GetActiveHeroTalentSpecID)
    end
    return tonumber(heroSpecID)
end
```

and add `heroSubTreeID = GetCurrentHeroSubTreeID(),` in the returned table right after the `heroTalentName = GetCurrentHeroTalentName(),` line.

In `StatVerdict/Core/SV_SpecSnapshot.lua` add right after `function ns.GetSnapshotHeroTalentName(profile) ... end`:

```lua
function ns.GetSnapshotHeroSubTreeID(profile)
    local snapshot = GetSnapshot(profile)
    local id = snapshot and tonumber(snapshot.heroSubTreeID)
    if id and id > 0 then return id end
    return nil
end
```

- [ ] **Step 6: Register the data file in the .toc**

In `StatVerdict/StatVerdict.toc` add `Data/Generated/SV_MythicPlusBenchmarks.lua` right after `Data/Generated/SV_ProfileData.lua`.

- [ ] **Step 7: Run to verify pass**

Run: `python -m unittest discover -s tools/tests -v`
Expected: all PASS, including the nine `RepositoryTests` and the syntax test for the edited files. If a repository test fails on a missing stub (a global the code calls), add the stub to `build_runtime` rather than changing addon behaviour, unless the failure shows a real bug.

- [ ] **Step 8: Commit**

```bash
git add StatVerdict/Core/SV_ProfileRepository.lua StatVerdict/Core/SV_EvaluationContext.lua StatVerdict/Core/SV_SpecSnapshot.lua StatVerdict/StatVerdict.toc tools/tests/test_addon_lua.py
git commit -m "feat: Mythic+ profiles come from the live benchmark file, hero priority by tree id"
```

### Task 10: Benchmark drawer replaces Summary (unplugged)

**Files:**
- Create: `StatVerdict/UI/SV_BenchmarkDrawerPanel.lua`
- Modify: `StatVerdict/UI/SV_RightPanelMode.lua`
- Modify: `StatVerdict/UI/SV_DashboardLayout.lua`
- Modify: `StatVerdict/UI/SV_SettingsPanel.lua`
- Modify: `StatVerdict/StatVerdict.toc`

**Interfaces:**
- Consumes: `ns.GetBenchmarkLevels`, `ns.GetBenchmarkLevel`, `ns.SetBenchmarkLevel` (Task 8); the active profile's `generatedContext.benchmark` (Task 4); `ns.GetActivePanelContext`.
- Produces: right-panel mode `"benchmark"`; `ns.StatVerdictBenchmarkDrawerPanel` with `IsOpen/SetOpen/Toggle/GetPreferredWidth/Apply` (same contract as the Options drawer); the `summary` mode no longer exists.

- [ ] **Step 1: Create the drawer**

`StatVerdict/UI/SV_BenchmarkDrawerPanel.lua`:

```lua
local addonName, ns = ...

local Panel = {}
ns.StatVerdictBenchmarkDrawerPanel = Panel

local DRAWER_PREFERRED_WIDTH = 280
local LEVEL_STEP = 50
local CHECK_LABEL_FONT_SIZE = 11

local function Offset(key)
    if ns.GetDevLayoutOffset then return ns.GetDevLayoutOffset(key) end
    return 0, 0
end

local function SizeDelta(key)
    if ns.GetDevLayoutSizeDelta then return ns.GetDevLayoutSizeDelta(key) end
    return 0
end

local function ActiveBenchmark()
    local context = ns.GetActivePanelContext and ns.GetActivePanelContext() or nil
    local profile = context and context.profile or nil
    local generated = type(profile) == "table" and profile.generatedContext or nil
    return type(generated) == "table" and generated.benchmark or nil
end

local function IsMythicPlus()
    local goal = ns.GetStatAuditGoalMode and ns.GetStatAuditGoalMode() or "MYTHIC_PLUS"
    return goal == "MYTHIC_PLUS"
end

local function SyncCard(card)
    if not card then return end
    local mythicPlus = IsMythicPlus()
    local selected = ns.GetBenchmarkLevel()
    for _, row in ipairs(card.levelRows or {}) do
        row.check:SetChecked(row.key == selected)
        if mythicPlus then
            row.check:Enable()
            row.check:SetAlpha(1)
        else
            row.check:Disable()
            row.check:SetAlpha(0.5)
        end
    end

    local bench = mythicPlus and ActiveBenchmark() or nil
    if not mythicPlus then
        card.info:SetText("This choice applies to Mythic+ only. Raid and PvP use their own bundled data.")
        card.info:SetTextColor(0.72, 0.72, 0.72)
        card.warning:SetText("")
        return
    end
    if not bench then
        card.info:SetText("No data for this build at this level.")
        card.info:SetTextColor(1.0, 0.5, 0.0)
        card.warning:SetText("")
        return
    end
    local provenance = ns.ProfileRepository and ns.ProfileRepository.GetDataProvenance
        and ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS") or nil
    card.info:SetText(string.format(
        "Sample: %d players · Confidence: %s\nData from: %s",
        tonumber(bench.sampleSize) or 0,
        tostring(bench.confidence or "unknown"),
        tostring(provenance and provenance.scrape or "unknown")
    ))
    card.info:SetTextColor(0.85, 0.85, 0.85)
    if tostring(bench.confidence) ~= "high" then
        card.warning:SetText("Smaller sample: results can be less stable.")
    else
        card.warning:SetText("")
    end
end

local function EnsureLevelRow(card, index, level)
    card.levelRows = card.levelRows or {}
    local row = card.levelRows[index]
    if row then return row end
    row = { key = level.key }
    row.check = CreateFrame("CheckButton", nil, card, "UICheckButtonTemplate")
    row.check:SetSize(22, 22)
    if row.check.Text then
        row.check.Text:SetText(level.label)
        row.check.Text:SetTextColor(1, 1, 1)
        local font, _, flags = row.check.Text:GetFont()
        if font then row.check.Text:SetFont(font, CHECK_LABEL_FONT_SIZE, flags) end
    end
    row.meaning = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.meaning:SetTextColor(0.72, 0.72, 0.72)
    row.meaning:SetJustifyH("LEFT")
    row.meaning:SetText(level.meaning)
    row.check:SetScript("OnClick", function()
        ns.SetBenchmarkLevel(level.key)
        SyncCard(card)
    end)
    card.levelRows[index] = row
    return row
end

local function EnsureCard(frame)
    if frame.benchmarkDrawerCard then return frame.benchmarkDrawerCard end

    local card = CreateFrame("Frame", nil, frame, "BackdropTemplate")
    card:SetFrameLevel(math.max(1, frame:GetFrameLevel() - 1))
    card:SetBackdrop({
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border",
        tile = true,
        tileSize = 16,
        edgeSize = 12,
        insets = { left = 3, right = 3, top = 3, bottom = 3 },
    })
    card:SetBackdropColor(0.018, 0.022, 0.030, 0.96)
    card:SetBackdropBorderColor(0.72, 0.74, 0.78, 0.86)

    card.title = card:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    card.title:SetPoint("TOPLEFT", card, "TOPLEFT", 12, -12)
    card.title:SetText("Benchmark Level")
    card.title:SetTextColor(1.0, 0.82, 0.0)

    card.intro = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.intro:SetPoint("TOPLEFT", card, "TOPLEFT", 12, -36)
    card.intro:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, -36)
    card.intro:SetJustifyH("LEFT")
    card.intro:SetWordWrap(true)
    card.intro:SetTextColor(0.72, 0.72, 0.72)
    card.intro:SetText("Choose which players your Mythic+ targets and popular gear are based on.")

    for index, level in ipairs(ns.GetBenchmarkLevels()) do
        local row = EnsureLevelRow(card, index, level)
        local top = -84 - ((index - 1) * LEVEL_STEP)
        row.check:SetPoint("TOPLEFT", card, "TOPLEFT", 10, top)
        row.meaning:SetPoint("TOPLEFT", card, "TOPLEFT", 40, top - 24)
        row.meaning:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, top - 24)
    end

    local infoTop = -84 - (#ns.GetBenchmarkLevels() * LEVEL_STEP) - 8
    card.info = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.info:SetPoint("TOPLEFT", card, "TOPLEFT", 12, infoTop)
    card.info:SetPoint("TOPRIGHT", card, "TOPRIGHT", -12, infoTop)
    card.info:SetJustifyH("LEFT")
    card.info:SetWordWrap(true)

    card.warning = card:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    card.warning:SetPoint("TOPLEFT", card.info, "BOTTOMLEFT", 0, -8)
    card.warning:SetPoint("TOPRIGHT", card.info, "BOTTOMRIGHT", 0, -8)
    card.warning:SetJustifyH("LEFT")
    card.warning:SetWordWrap(true)
    card.warning:SetTextColor(1.0, 0.5, 0.0)

    frame.benchmarkDrawerCard = card
    return card
end

function Panel.IsOpen()
    return ns.GetRightPanelMode and ns.GetRightPanelMode() == "benchmark"
end

function Panel.SetOpen(open)
    if open then
        if ns.SetRightPanelMode then ns.SetRightPanelMode("benchmark") end
    elseif Panel.IsOpen() and ns.SetRightPanelMode then
        ns.SetRightPanelMode(nil)
    end
end

function Panel.Toggle()
    if ns.ToggleRightPanelMode then ns.ToggleRightPanelMode("benchmark") end
end

function Panel.GetPreferredWidth(frame)
    local width = DRAWER_PREFERRED_WIDTH + SizeDelta("benchmark.width")
    if width < 200 then width = 200 end
    if width > 520 then width = 520 end
    return width
end

function Panel.Apply(frame)
    if not frame then return end
    if not Panel.IsOpen() then
        if frame.benchmarkDrawerCard then frame.benchmarkDrawerCard:Hide() end
        if ns.UnregisterDevLayoutRegion then ns.UnregisterDevLayoutRegion("benchmark.card") end
        return
    end

    local card = EnsureCard(frame)
    local cardX = Offset("benchmark.card")
    local cardWidth = Panel.GetPreferredWidth(frame)
    local panelX = 770 + cardX
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelX then
        panelX = ns.StatVerdictDashboardLayout.GetRightPanelX(frame)
    end

    card.preferredWidth = cardWidth
    local extra = 0
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.GetRightPanelExtraGap then
        extra = ns.StatVerdictDashboardLayout.GetRightPanelExtraGap()
    end
    local cardPad = ns.GetRightDrawerCardPad and ns.GetRightDrawerCardPad("benchmark.card")
        or { top = 0, bottom = 0, left = 0, right = 0 }
    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard and frame.statProgressCard then
        ns.StatVerdictDashboardLayout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, extra, 0, cardPad)
    elseif ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.AnchorOuterCard then
        ns.StatVerdictDashboardLayout.AnchorOuterCard(card, frame, panelX, cardPad)
    else
        card:ClearAllPoints()
        card:SetPoint("TOPLEFT", frame, "TOPLEFT", panelX, -34)
        card:SetPoint("BOTTOMLEFT", frame, "BOTTOMLEFT", panelX, 14)
    end
    card:SetWidth(math.max(120, cardWidth - (cardPad.left or 0) - (cardPad.right or 0)))
    card:Show()
    if ns.ApplyRightDrawerCardDev then
        ns.ApplyRightDrawerCardDev(card, "benchmark.card", "Benchmark drawer", "benchmark.width", DRAWER_PREFERRED_WIDTH)
    end

    SyncCard(card)

    if ns.StatVerdictDashboardLayout and ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel then
        ns.StatVerdictDashboardLayout.SyncFrameWidthToRightPanel(frame)
    end
end
```

- [ ] **Step 2: Right panel mode**

In `StatVerdict/UI/SV_RightPanelMode.lua`:
1. Header comment: replace `"summary"` with `"benchmark"` in the `Modes:` line.
2. `VALID`: replace `summary = true,` with `benchmark = true,`.
3. `ns.GetRightPanelMode`: replace the block `if db.showSummaryPanel == true then return "summary" end` with `if db.showBenchmarkPanel == true then return "benchmark" end`.
4. `ns.SetRightPanelMode`: replace `db.showSummaryPanel = (mode == "summary")` with `db.showBenchmarkPanel = (mode == "benchmark")`.
5. `PANEL_TITLES`: delete the whole `summary = { ... },` entry.
6. `ResolvePanelKind`: change the final `return "summary"` to `return "bis"`.
7. Replace `TitleForPanel` body's `PANEL_TITLES[ResolvePanelKind(panelKind)]` and the width-measure `PANEL_TITLES[kind]` (two places) by a shared helper defined just above `ResolvePanelKind`:

```lua
-- The Best in Slot panel reads "Popular Gear" for Mythic+ (see ns.GetReferenceWording).
local function PanelTitles(panelKind)
    if panelKind == "bis" and ns.GetReferenceWording then
        local wording = ns.GetReferenceWording()
        return { base = wording.base, MAIN = wording.main, OFF = wording.off }
    end
    return PANEL_TITLES[panelKind]
end
```

   and use `PanelTitles(ResolvePanelKind(panelKind))` / `PanelTitles(kind)` in those two reads. `ResolvePanelKind` keeps testing `PANEL_TITLES[panelKind]` for validity.
8. `HideInactiveTitleHandles`: change `local prefixes = { "summary", "bis", "trinkets", "bisTrinkets" }` to `{ "bis", "trinkets", "bisTrinkets" }`.
9. In `ns.PlaceMsOsTitleChip`: delete the `if layoutPrefix == "summary" then label = "Summary title (Main/Off Spec)" elseif` branch so the chain starts with `if layoutPrefix == "bis" then`, and update the comments that say `"summary" | "bis" | "trinkets"` / `summary.* / bis.* / trinkets.*` to drop `summary`.
10. The tooltip line 397 text "Click to switch Main Spec / Off Spec for Summary, BiS, and Ranked Trinkets." becomes "Click to switch Main Spec / Off Spec for Popular Gear / Best in Slot and Ranked Trinkets."

- [ ] **Step 3: Dashboard layout**

In `StatVerdict/UI/SV_DashboardLayout.lua`:
1. `Layout.GetRightPanelWidth`: replace the whole `if mode == "summary" then ... end` block with:

```lua
    if mode == "benchmark" then
        if ns.StatVerdictBenchmarkDrawerPanel and ns.StatVerdictBenchmarkDrawerPanel.GetPreferredWidth then
            return ns.StatVerdictBenchmarkDrawerPanel.GetPreferredWidth(frame)
        end
        return Clamp(280 + SizeDelta("benchmark.width"), 200, 520)
    end
```

2. `SharedRightDockX`: in the key list replace `"summary.card"` with `"benchmark.card"`.
3. `Layout.SyncFrameWidthToRightPanel`: replace `elseif mode == "summary" then card = frame.characterSummaryDrawerCard` with `elseif mode == "benchmark" then card = frame.benchmarkDrawerCard`.
4. `Layout.Apply`: replace `local showSummary = mode == "summary"` with `local showBenchmark = mode == "benchmark"`; in `HideAllRightDrawers` replace the four Summary lines (`characterSummaryDrawerCard`, `devSummaryDrawerWidthRegion`, `devSummaryDrawerMoveGrip`, and the `if not showSummary and ... ClearDevTargets` block) with:

```lua
        if frame.benchmarkDrawerCard then frame.benchmarkDrawerCard:Hide() end
        if ns.UnregisterDevLayoutRegion and not showBenchmark then
            ns.UnregisterDevLayoutRegion("benchmark.card")
        end
```

   replace the dispatch branch `elseif showSummary and ns.StatVerdictCharacterSummaryDrawerPanel then ... Apply(frame, profile)` (the whole branch including the profile lookup) with:

```lua
    elseif showBenchmark and ns.StatVerdictBenchmarkDrawerPanel then
        ns.StatVerdictBenchmarkDrawerPanel.Apply(frame)
```

   and in the final `else` branch replace the `StatVerdictCharacterSummaryDrawerPanel.Apply(frame)` call with `if ns.StatVerdictBenchmarkDrawerPanel and ns.StatVerdictBenchmarkDrawerPanel.Apply then ns.StatVerdictBenchmarkDrawerPanel.Apply(frame) end`.

- [ ] **Step 4: Settings panel button**

In `StatVerdict/UI/SV_SettingsPanel.lua` replace the Summary entry of `PANEL_TOGGLE_BUTTONS` with:

```lua
    {
        mode = "benchmark",
        field = "benchmarkDrawerButton",
        label = "Benchmark",
        -- Layout key kept from the Summary button this replaced, so saved
        -- button positions carry over (the button appears where Summary was).
        layoutKey = "setup.summaryButton",
        defaultY = -374,
    },
```

and in `PositionPanelToggleButtons` replace `button.label:SetText(spec.label)` with:

```lua
        local label = spec.label
        if spec.mode == "bis" and ns.GetReferenceWording then
            label = ns.GetReferenceWording().button
        end
        button.label:SetText(label)
```

- [ ] **Step 5: .toc — add the drawer, unplug Summary**

In `StatVerdict/StatVerdict.toc`: add `UI/SV_BenchmarkDrawerPanel.lua` on the line after `UI/SV_OptionsDrawerPanel.lua`, and remove the line `UI/SV_CharacterSummaryDrawerPanel.lua`. The file itself stays on disk until the cleanup task. Every remaining reference to `ns.StatVerdictCharacterSummaryDrawerPanel` is guarded (`... and ns.StatVerdictCharacterSummaryDrawerPanel ...`); verify with `grep -rn "StatVerdictCharacterSummaryDrawerPanel" StatVerdict/Core StatVerdict/UI StatVerdict/StatVerdict.lua` and confirm every hit is inside a nil-guard or inside the unplugged file itself.

- [ ] **Step 6: Tests**

Add to `tools/tests/test_addon_lua.py`:

```python
@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class PanelModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")

    def test_benchmark_is_a_valid_mode_and_summary_is_not(self) -> None:
        self.ns.SetRightPanelMode("benchmark")
        self.assertEqual("benchmark", self.ns.GetRightPanelMode())
        self.ns.SetRightPanelMode("summary")
        self.assertIsNone(self.ns.GetRightPanelMode())

    def test_window_opens_with_every_panel_closed(self) -> None:
        self.assertIsNone(self.ns.GetRightPanelMode())

    def test_toc_lists_benchmark_drawer_and_not_summary(self) -> None:
        names = [path.name for path in toc_lua_files()]
        self.assertIn("SV_BenchmarkDrawerPanel.lua", names)
        self.assertNotIn("SV_CharacterSummaryDrawerPanel.lua", names)
```

`SV_RightPanelMode.lua` uses WoW frame APIs only inside functions, so loading it at file scope must work with an empty `ns`; if the load fails on a missing global, add the smallest stub to `setUp` (for example `self.lua.execute("CreateFrame = function() return {} end")`) and note it.

Run: `python -m unittest discover -s tools/tests -v`
Expected: all PASS (the syntax test now also compiles the new drawer and the edited files).

- [ ] **Step 7: Commit**

```bash
git add StatVerdict/UI/SV_BenchmarkDrawerPanel.lua StatVerdict/UI/SV_RightPanelMode.lua StatVerdict/UI/SV_DashboardLayout.lua StatVerdict/UI/SV_SettingsPanel.lua StatVerdict/StatVerdict.toc tools/tests/test_addon_lua.py
git commit -m "feat: Benchmark drawer replaces the Summary panel (Summary unplugged)"
```

### Task 11: Popular wording in panels, tooltip, manual and store text

**Files:**
- Modify: `StatVerdict/UI/SV_BisProgressPanel.lua` (lines ~413, 429, 807)
- Modify: `StatVerdict/UI/SV_Render.lua` (lines ~89-110, 147-154)
- Modify: `StatVerdict/UI/SV_ManualDrawerPanel.lua` (lines 41, 54, 57, 58)
- Modify: `StatVerdict/STORE.md`
- Modify: `StatVerdict/VERDICT_MODEL.md`

**Interfaces:**
- Consumes: `ns.GetReferenceWording(goal)` (Task 8); `Repository.GetDataProvenance(goal)` (Task 9).

- [ ] **Step 1: Progress line in the panel**

In `StatVerdict/UI/SV_BisProgressPanel.lua`:
- line ~413: `card.title:SetText("Best in Slot")` -> `card.title:SetText(ns.GetReferenceWording and ns.GetReferenceWording().base or "Best in Slot")`.
- line ~429: `card.summary:SetText("BiS Progress: -")` -> `card.summary:SetText((ns.GetReferenceWording and ns.GetReferenceWording().progress or "BiS Progress") .. ": -")`.
- line ~807: replace `card.summary:SetText(string.format("BiS Progress: %d/%d", owned, total))` with:

```lua
    local wording = ns.GetReferenceWording and ns.GetReferenceWording() or nil
    card.summary:SetText(string.format(
        "%s: %d/%d%s",
        wording and wording.progress or "BiS Progress",
        owned,
        total,
        wording and wording.progressSuffix or ""
    ))
```

- [ ] **Step 2: Tooltip tag and provenance line**

In `StatVerdict/UI/SV_Render.lua`:
- replace `AddLine(tooltip, c.white .. "Reference: " .. "|cff00ccff(BIS)|r" .. c.reset, 1, 1, 1)` with:

```lua
        local wording = ns.GetReferenceWording and ns.GetReferenceWording(context.profile and context.profile.goal) or nil
        local tag = wording and wording.tag or "BIS"
        AddLine(tooltip, c.white .. "Reference: " .. "|cff00ccff(" .. tag .. ")|r" .. c.reset, 1, 1, 1)
```

- replace `and ns.ProfileRepository.GetDataProvenance()` (the call inside the `local provenance = ...` expression) with `and ns.ProfileRepository.GetDataProvenance(context.profile and context.profile.goal)`.

- [ ] **Step 3: Manual text**

In `StatVerdict/UI/SV_ManualDrawerPanel.lua` replace these four entries (keep the surrounding entries):
- line 41 -> `{ text = "Trinkets are scored differently: a goal-specific reference tier/rank can add reference value (for Mythic+ it comes from how many top players wear the trinket). StatVerdict does not calculate proc or on-use performance itself." },`
- line 54 -> `{ text = "Popular Gear (Best in Slot for Raid and PvP) — Mythic+ shows the items most top players wear, with your progress for the active build." },`
- line 57 -> `{ text = "Benchmark — choose which group of top players Mythic+ targets and popular gear are based on: Elite (top 25), Standard (top 100) or Broad (top 200)." },`
- line 58 -> `{ text = "On Popular Gear / Best in Slot and Ranked Trinkets, click the title chip to switch Main Spec / Off Spec. Both panels share that selection." },`

- [ ] **Step 4: Store and model documents**

In `StatVerdict/STORE.md`: line 34 -> `- Tracks **Popular Gear** progress (Mythic+, from live top-player data) and **Best in Slot** progress (Raid, PvP)`; line 99 -> `4. Popular Gear / Best in Slot panel`; add a bullet after line 34: `- **Benchmark** levels (Elite / Standard / Broad) choose how strict the Mythic+ comparison group is`. In `StatVerdict/VERDICT_MODEL.md` under "Signals" replace the bullet starting `- **BiS and trinket references**` with:

```
- **Popular and trinket references** (Mythic+: live data, "Popular"; Raid and PvP:
  bundled curated "BiS") are hints from goal-specific profile data. Mythic+
  popularity is the share of top players wearing an item at the chosen Benchmark
  level. They may only affect a verdict when that data passes the profile quality
  and freshness checks.
```

- [ ] **Step 5: Verify and commit**

Run: `python -m unittest discover -s tools/tests -v` (syntax check of the edited Lua) and `grep -rn "BiS Progress\|(BIS)" StatVerdict/UI StatVerdict/Core` — remaining hits must only be the Raid/PvP fallback strings inside `SV_Benchmark.lua` and the fallbacks in the expressions above.

```bash
git add StatVerdict/UI/SV_BisProgressPanel.lua StatVerdict/UI/SV_Render.lua StatVerdict/UI/SV_ManualDrawerPanel.lua StatVerdict/STORE.md StatVerdict/VERDICT_MODEL.md
git commit -m "Label Mythic+ reference lists Popular instead of BiS; update manual and store text"
```

### Task 12: Hand over for in-game verification

**Files:** none changed.

- [ ] **Step 1: Full test run**

Run: `python -m unittest discover -s tools/tests -v`
Expected: all PASS (Lua tests skipped only if lupa is missing; say so to the user if that is the case).

- [ ] **Step 2: Push**

```bash
git push
```

Inform the user (update only, per CLAUDE.md).

- [ ] **Step 3: Give the user the in-game checklist (Greek, simple, no code)**

1. Copy the addon folder to the game (or run `ship.ps1` the usual way) and `/reload`. The window opens with all right-side panels closed, same look as before.
2. Panels list: the first button (where Summary was) says **Benchmark**; the "Best in Slot" button says **Popular Gear** on Mythic+ and switches back to **Best in Slot** on Raid or PvP.
3. Open Benchmark: three choices Elite / Standard / Broad with the meaning lines; Standard is ticked; sample size, confidence and date are shown; switching to Elite changes the stat targets in the main window and the Popular list.
4. Popular Gear panel shows "Popular Progress: x/15 · Standard"; hovering an item from the list shows "Reference: (Popular)" and a higher verdict than an identical item outside the list; hovering a listed trinket shows its tier.
5. Raid and PvP still show the old data and "BiS" wording; on those goals the Benchmark drawer says the choice is Mythic+ only.
6. For a Mythic+ build check the priority order changes with your hero talent tree. If it never changes, tell me: run `/dump C_ClassTalents.GetActiveHeroTalentSpec()` and send the number, so I can compare it with the numbers in the data.
7. A Demon Hunter Devourer build shows Intellect as its primary stat on Mythic+.
8. Any Lua error popup or a spec that says "no data" unexpectedly: send a screenshot.

Wait for the user's verdict before Task 13.

### Task 13: Cleanup (after the user confirms the game check)

**Files:**
- Delete: `StatVerdict/UI/SV_CharacterSummaryDrawerPanel.lua`
- Modify: `StatVerdict/UI/SV_StatProgressPanel.lua`, `StatVerdict/UI/SV_LayoutOffsets.lua`, `StatVerdict/UI/SV_BisProgressPanel.lua`, `StatVerdict/UI/SV_StatAudit.lua`, `StatVerdict/Core/SV_ProfileRepository.lua`, `IMPROVEMENTS.md`

- [ ] **Step 1: Delete the Summary panel and everything only it used**

Run `git rm StatVerdict/UI/SV_CharacterSummaryDrawerPanel.lua`. Then, one grep at a time, remove what nothing else uses (each removal followed by `python -m unittest discover -s tools/tests -v`):
- `grep -rn "StatVerdictCharacterSummaryDrawerPanel" StatVerdict` — delete the guarded call sites in `SV_StatProgressPanel.lua` (~1533) and `SV_DashboardLayout.lua`.
- `grep -rn "showSummaryPanel\|summary\.\|Character Summary" StatVerdict --include=*.lua` — remove the hidden in-window summary card (`EnsureSummaryCard`, `frame.summaryTitle`, `SetCardVisible(summaryCard, false)`, `stats.summary.*` layout registrations) from `SV_StatProgressPanel.lua`, and the `stats.summary.*` / `summary.*` keys from `SV_LayoutOffsets.lua` (31 entries) only if `grep` shows nothing else reads them. Keep `setup.summaryButton` (the Benchmark button reuses that key so saved positions survive) and add a one-line comment there that the key name is historical.
- `grep -rn "StatVerdictProgressCache" StatVerdict` — delete the `bis` cache producer (`CacheBisProgress` and `Panel.UpdateProgressCache` if unused) and the `MAIN`/`OFF` cache writers in `SV_StatAudit.lua` if the greps show no remaining readers.

- [ ] **Step 2: Other leftovers named in earlier work**

- `SV_StatAudit.lua` ~3218: remove the dead `liveOverride` / `LIVE_CLASSCODEX` debug branch (`grep -rn "liveOverride" StatVerdict` must show no writer first).
- `SV_ProfileRepository.lua`: rename the profile `source = "generated_classcodex"` and `BuildAuditTargets` `source = "generated_classcodex"` to `"generated"` after `grep -rn "generated_classcodex" StatVerdict` shows no reader depends on the string.
- `IMPROVEMENTS.md`: delete the file if all its items are implemented (the pipeline memory says they are); otherwise tell the user which remain.

- [ ] **Step 3: Old Mythic+ slice of `SV_ProfileData` (decide with the user)**

Ask the user (simple Greek): the old file still contains a Mythic+ section that the game no longer reads. Removing it needs changes to `StatVerdict/scripts/extract_bridge_export.py`, `ship.ps1` and `StatVerdict/tests/test_profile_validation.py`, because they currently require it. Recommend doing it now if the user agrees; if they prefer, leave it as a separate task. Do it only after their yes.

- [ ] **Step 4: Verify and commit**

Run: `python -m unittest discover -s tools/tests -v`; then ask the user to `/reload` in game once more (Benchmark drawer, Popular Gear, Raid/PvP).

```bash
git add -A StatVerdict IMPROVEMENTS.md
git status --short
```

Before committing, read `git status --short` and unstage anything on the constraints' do-not-commit list (`git restore --staged <path>`), then:

```bash
git commit -m "Remove the Summary panel and other leftovers replaced by Benchmark"
git push
```

- [ ] **Step 5: Update memory**

Update `statverdict-pipeline-state-and-todo.md`: addon consumption is built (compact file, Benchmark levels, Popular wording), Devourer primary stat is measured for Mythic+, remaining to-do items (CurseForge publish action, Raid/PvP live data, Builder.lua Devourer for Raid/PvP, upload-artifact bump).

---

## Self-review

**Spec coverage:** decisions 1-8 -> Tasks 8-11 (M+/Raid split, look unchanged, same shape, Popular naming, Benchmark replaces Summary, level names, panels closed at start in Task 10 tests, removal rule in Task 13); data side (raw files out, compaction, size gate, hero rows, tiers, absent cohorts) -> Tasks 1-6; boosts -> Task 9 tests; verification -> Tasks 7, 9, 12; phases -> Tasks 1-6 / 7-11 / 12 / 13.
**Placeholders:** none; every code step carries code; the two decision points (thresholds, old Mythic+ slice) are explicit user checkpoints, not gaps.
**Consistency:** `pick_popular_slots`/`rank_trinkets`/`build_level_context` names and the data shape match between Tasks 1-4, the fixtures, and the Lua tests (item ids 1000/5001/5002/5003, levels ELITE/STANDARD/BROAD, `benchmark` table, `heroSubTreeID`); `ns.GetReferenceWording`, `ns.GetBenchmarkLevel`, `GetDataProvenance(goal)` are defined in Tasks 8-9 before use in Tasks 10-11.
