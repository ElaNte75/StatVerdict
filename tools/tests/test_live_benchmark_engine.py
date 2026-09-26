from __future__ import annotations

import copy
import unittest

from tools.live_benchmark_engine import (
    SPECS,
    aggregate_cohort,
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
            "melee_crit": {"rating": 501},
            "spell_crit": {"rating": 501},
            "melee_haste": {"rating": 602},
            "mastery": {"rating": 703},
            "versatility": 804,
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
            "schemaVersion": 1,
            "profiles": {
                spec.key: {"cohorts": {"TOP_3": copy.deepcopy(cohort)}}
                for spec in SPECS
            },
        }
        validate_database(database, 3)
        del database["profiles"][SPECS[0].key]
        with self.assertRaisesRegex(ValueError, "expected 40 profiles"):
            validate_database(database, 3)


if __name__ == "__main__":
    unittest.main()
