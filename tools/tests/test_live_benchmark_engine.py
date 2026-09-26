from __future__ import annotations

import copy
import unittest

from tools.live_benchmark_engine import (
    SCHEMA_VERSION,
    SPECS,
    aggregate_cohort,
    aggregate_hero_trees,
    compare_hero_trees,
    parse_active_hero_talent,
    parse_character_stats,
    parse_equipment,
    validate_database,
)


def record(index: int, item_level: float = 320) -> dict:
    return {
        "name": f"Player{index}",
        "realm": "test-realm",
        "region": "eu",
        "score": 4000 - index,
        "itemLevel": item_level,
        "stats": {
            "strength": 2000 + index,
            "agility": 2000 + index,
            "intellect": 2000 + index,
            "stamina": 10000 + index,
            "crit": 500 + index,
            "haste": 600 + index,
            "mastery": 700 + index,
            "versatility": 800 + index,
        },
        "items": {
            "HEAD": {"itemId": 100, "name": "Test Helm", "itemLevel": item_level},
            "TRINKET_1": {"itemId": 200, "name": "Test Trinket", "itemLevel": item_level},
        },
    }


class BenchmarkEngineTests(unittest.TestCase):
    def test_catalog_has_forty_unique_specs(self) -> None:
        self.assertEqual(40, len(SPECS))
        self.assertEqual(40, len({spec.key for spec in SPECS}))

    def test_parse_character_sheet_ratings(self) -> None:
        raw = {
            "strength": {"base": 100, "effective": 120},
            "agility": {"base": 10, "effective": 10},
            "intellect": {"base": 20, "effective": 20},
            "stamina": {"base": 900, "effective": 950},
            "melee_crit": {"rating_bonus": 12.1, "rating_normalized": 501, "value": 17.1},
            "spell_crit": {"rating_bonus": 12.1, "rating_normalized": 501, "value": 17.1},
            "melee_haste": {"rating_bonus": 9.4, "rating_normalized": 602, "value": 9.4},
            "mastery": {"rating_bonus": 20.2, "rating_normalized": 703, "value": 38.0},
            "versatility": 804.0,
        }
        parsed = parse_character_stats(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(120, parsed["strength"])
        self.assertEqual(501, parsed["crit"])
        self.assertEqual(804, parsed["versatility"])

    def test_parse_authoritative_equipment(self) -> None:
        average, items = parse_equipment(
            {
                "equipped_items": [
                    {
                        "item": {"id": 123},
                        "slot": {"type": "HEAD"},
                        "name": "Verified Helm",
                        "level": {"value": 320},
                    },
                    {
                        "item": {"id": 456},
                        "slot": {"type": "CHEST"},
                        "name": {"en_US": "Verified Chest"},
                        "level": {"value": 322},
                    },
                ]
            }
        )
        self.assertEqual(321, average)
        self.assertEqual("Verified Helm", items["HEAD"]["name"])
        self.assertEqual("Verified Chest", items["CHEST"]["name"])

    def test_parse_active_hero_talent(self) -> None:
        tree, reason = parse_active_hero_talent(
            {
                "active_specialization": {"id": 250, "name": "Blood"},
                "active_hero_talent_tree": {"id": 31, "name": "San'layn"},
            },
            "Blood",
        )
        self.assertIsNone(reason)
        self.assertEqual(
            {"key": "HERO_31", "id": 31, "name": "San'layn"},
            tree,
        )

    def test_parse_active_hero_talent_from_active_loadout(self) -> None:
        tree, reason = parse_active_hero_talent(
            {
                "active_specialization": {"id": 250, "name": "Blood"},
                "specializations": [
                    {
                        "specialization": {"id": 250, "name": "Blood"},
                        "loadouts": [
                            {
                                "is_active": True,
                                "selected_hero_talent_tree": {"id": 32, "name": "Deathbringer"},
                            }
                        ],
                    }
                ],
            },
            "Blood",
        )
        self.assertIsNone(reason)
        self.assertEqual("Deathbringer", tree["name"])

    def test_cohort_uses_median_and_rejects_ilvl_outlier(self) -> None:
        records = [record(index) for index in range(10)]
        records.append(record(99, item_level=100))
        cohort = aggregate_cohort(records, 10)
        self.assertEqual(10, cohort["sampleSize"])
        self.assertEqual(320, cohort["averageItemLevel"])
        self.assertEqual(604.5, cohort["statTargets"]["stats"]["haste"])
        self.assertEqual(100.0, cohort["popularItems"]["HEAD"][0]["usagePercent"])

    def test_database_validation_requires_all_specs(self) -> None:
        cohort = aggregate_cohort([record(index) for index in range(3)], 3)
        database = {
            "schemaVersion": SCHEMA_VERSION,
            "profiles": {
                spec.key: {
                    "status": "ok",
                    "cohorts": {"TOP_3": copy.deepcopy(cohort)},
                    "heroTalentTrees": {},
                }
                for spec in SPECS
            },
        }
        validate_database(database, 3)
        del database["profiles"][SPECS[0].key]
        with self.assertRaisesRegex(ValueError, "expected 40 profiles"):
            validate_database(database, 3)

    def test_rare_spec_is_flagged_insufficient_without_failing_the_run(self) -> None:
        full = aggregate_cohort([record(index) for index in range(3)], 3)
        sparse = aggregate_cohort([record(0)], 3)
        empty = aggregate_cohort([], 3)
        self.assertEqual("ok", full["status"])
        self.assertEqual("insufficient", sparse["status"])
        self.assertEqual("insufficient", empty["status"])
        profiles = {
            spec.key: {
                "status": "ok",
                "cohorts": {"TOP_3": copy.deepcopy(full)},
                "heroTalentTrees": {},
            }
            for spec in SPECS
        }
        profiles[SPECS[0].key] = {
            "status": "insufficient",
            "cohorts": {"TOP_3": sparse},
            "heroTalentTrees": {},
        }
        profiles[SPECS[1].key] = {
            "status": "insufficient",
            "cohorts": {"TOP_3": empty},
            "heroTalentTrees": {},
        }
        database = {"schemaVersion": SCHEMA_VERSION, "profiles": profiles}
        validate_database(database, 3, max_insufficient_specs=2)
        with self.assertRaisesRegex(ValueError, "2 specs lack a complete TOP_3"):
            validate_database(database, 3, max_insufficient_specs=1)
        profiles[SPECS[0].key]["status"] = "ok"
        with self.assertRaisesRegex(ValueError, "profile status does not match"):
            validate_database(database, 3, max_insufficient_specs=2)

    def test_hero_tree_cohorts_and_comparison(self) -> None:
        records = []
        for index in range(6):
            row = record(index)
            row["heroTalent"] = {
                "key": "HERO_31" if index < 3 else "HERO_32",
                "id": 31 if index < 3 else 32,
                "name": "San'layn" if index < 3 else "Deathbringer",
            }
            row["stats"]["haste"] = 900 + index if index < 3 else 300 + index
            row["stats"]["crit"] = 300 + index if index < 3 else 900 + index
            records.append(row)

        trees = aggregate_hero_trees(records, (3,))
        self.assertEqual("ok", trees["HERO_31"]["status"])
        self.assertEqual("spec", trees["HERO_31"]["fallback"])
        analysis = compare_hero_trees(trees, 3)
        self.assertEqual("ok", analysis["status"])
        self.assertGreater(analysis["statRanges"]["haste"]["relativeRangePercent"], 100)

    def test_hero_tree_analysis_fails_closed_with_one_complete_tree(self) -> None:
        records = [record(index) for index in range(3)]
        for row in records:
            row["heroTalent"] = {"key": "HERO_31", "id": 31, "name": "San'layn"}
        analysis = compare_hero_trees(aggregate_hero_trees(records, (3,)), 3)
        self.assertEqual("insufficient", analysis["status"])


if __name__ == "__main__":
    unittest.main()
