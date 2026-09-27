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
    # The Broad group's favourite helm differs, so tests can tell the levels apart.
    gear["TOP_200"]["popularItems"]["HEAD"][0] = make_item(1500, "HEAD broad favourite", 60, 60.0, [150])
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


BRACKET_STATS: dict[str, tuple[float, float, float, float]] = {
    "LOW": (1300.0, 950.0, 700.0, 450.0),
    "MID": (1140.0, 900.0, 680.0, 430.0),
    "HIGH": (1100.0, 880.0, 690.0, 420.0),
}
BRACKET_SAMPLE_SIZES: tuple[int, ...] = (20, 50, 100)
_MINIMUM_BY_SIZE = {20: 5, 50: 13, 100: 25}


def make_bracket_profile(spec_key_class: str = "death-knight", primary: str = "strength") -> dict[str, Any]:
    """Same shape as make_profile, but keyed LOW/MID/HIGH x 20/50/100 (see BRACKET_CEILINGS
    and SAMPLE_SIZES in tools/live_benchmark_engine.py) instead of TOP_25/TOP_100/TOP_200.
    Kept separate from make_profile so tools/tests/test_addon_lua.py (out of scope for this
    plan - it exercises the still-unchanged ELITE/STANDARD/BROAD Lua selector) is untouched."""
    cohorts: dict[str, Any] = {}
    gear: dict[str, Any] = {}
    for bracket, (crit, haste, mastery, versatility) in BRACKET_STATS.items():
        for size in BRACKET_SAMPLE_SIZES:
            key = f"{bracket}_{size}"
            cohorts[key] = make_stat_cohort(size, crit, haste, mastery, versatility, minimum=_MINIMUM_BY_SIZE[size])
            gear[key] = make_gear_cohort(size)
    # HIGH's favourite helm differs, so tests can tell brackets apart.
    for size in BRACKET_SAMPLE_SIZES:
        gear[f"HIGH_{size}"]["popularItems"]["HEAD"][0] = make_item(1500, "HEAD high-bracket favourite", 60, 60.0, [150])

    def hero_tree_cohorts(crit: float, haste: float, mastery: float, versatility: float) -> dict[str, Any]:
        # A hero tree's own "cohorts" sub-dict is built by aggregate_hero_trees, which is
        # unchanged by the bracket work and still names its slices TOP_{size} - only the
        # OUTER heroTalentTrees dict key carries the bracket prefix (see build_profile).
        return {
            f"TOP_{size}": make_stat_cohort(size, crit, haste, mastery, versatility, minimum=_MINIMUM_BY_SIZE[size])
            for size in BRACKET_SAMPLE_SIZES
        }

    # HERO_31's crit/haste are swapped for MID (relative to LOW/HIGH), on purpose: it makes
    # the stat PRIORITY ORDER itself differ by bracket, so a test that reads the wrong
    # bracket's hero tree gets a visibly wrong order, not just a leaked/duplicated row.
    hero_31_stats = {"LOW": (600, 1000, 900, 590), "MID": (1000, 600, 900, 590), "HIGH": (600, 1000, 900, 590)}

    hero_trees: dict[str, Any] = {}
    for bracket in BRACKET_STATS:
        hero_trees[f"{bracket}:HERO_31"] = {
            "id": 31, "name": "Hero Talent 31", "status": "ok", "fallback": "spec",
            "cohorts": hero_tree_cohorts(*hero_31_stats[bracket]),
        }
        hero_trees[f"{bracket}:HERO_33"] = {
            "id": 33, "name": "Hero Talent 33", "status": "ok", "fallback": "spec",
            "cohorts": hero_tree_cohorts(1300, 400, 1000, 700),
        }
        hero_trees[f"{bracket}:HERO_35"] = {
            "id": 35, "name": "Hero Talent 35", "status": "insufficient", "fallback": "spec",
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
        "heroTalentTrees": hero_trees,
    }


def make_bracket_raw_database(
    generated_at: str, profiles: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "schemaVersion": 5,
        "generatedAt": generated_at,
        "source": {"season": "season-mn-2", "regions": ["eu", "us"], "aggregation": "median"},
        "profiles": profiles if profiles is not None else {"DEATHKNIGHT_BLOOD": make_bracket_profile()},
        "externalSimulations": {"status": "unavailable"},
    }


def make_raw_database(generated_at: str, profiles: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": 5,
        "generatedAt": generated_at,
        "source": {"season": "season-mn-2", "regions": ["eu", "us"], "aggregation": "median"},
        "profiles": profiles if profiles is not None else {"DEATHKNIGHT_BLOOD": make_profile()},
        "externalSimulations": {"status": "unavailable"},
    }
