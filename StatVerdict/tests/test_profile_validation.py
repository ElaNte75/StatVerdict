from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "extract_bridge_export.py"
SPEC = importlib.util.spec_from_file_location("extract_bridge_export", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def context(goal: str) -> dict:
    targets = {
        "sourceGoal": goal,
        "itemCount": 0 if goal == "PVP" else 16,
        "itemLevelSlots": 0 if goal == "PVP" else 16,
        "averageItemLevel": None if goal == "PVP" else 300,
        "targetMetadata": {"lowItemReplacements": 0, "unresolvedLowItems": 0},
        "statTargets": {
            "stats": {
                "haste": 800,
                "mastery": 700,
                "critical-strike": 600,
                "versatility": 500,
            }
        },
    }
    return {
        "targets": targets,
        "bis": {
            "label": goal,
            "slots": [{"slot": f"slot-{index}", "item": {"item_id": 1000 + index}} for index in range(16)],
        },
    }


def valid_database() -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    profiles = {}
    for index in range(MODULE.EXPECTED_PROFILE_COUNT):
        profiles[f"SPEC_{index:02d}"] = {
            "contexts": {
                "MYTHIC_PLUS": context("MYTHIC_PLUS"),
                "RAID": context("RAID"),
                "PVP": context("PVP"),
            }
        }
    return {
        "schemaVersion": 1,
        "generatedAt": now,
        "source": {
            "name": "fixture",
            "scrape": now,
            "resolveSummary": {"resolved": 100, "total": 100},
        },
        "profiles": profiles,
    }


class ProfileValidationTests(unittest.TestCase):
    def test_valid_goal_specific_database_passes(self) -> None:
        MODULE.validate_profile_data(valid_database())

    def test_cross_goal_pvp_totals_fail(self) -> None:
        database = valid_database()
        targets = database["profiles"]["SPEC_00"]["contexts"]["PVP"]["targets"]
        targets["itemCount"] = 16
        targets["averageItemLevel"] = 300
        with self.assertRaisesRegex(ValueError, "cross-goal"):
            MODULE.validate_profile_data(database)

    def test_goal_label_mismatch_fails(self) -> None:
        database = valid_database()
        database["profiles"]["SPEC_00"]["contexts"]["RAID"]["targets"]["sourceGoal"] = "MYTHIC_PLUS"
        with self.assertRaisesRegex(ValueError, "sourceGoal mismatch"):
            MODULE.validate_profile_data(database)

    def test_incomplete_or_low_level_set_fails(self) -> None:
        database = valid_database()
        targets = database["profiles"]["SPEC_00"]["contexts"]["RAID"]["targets"]
        targets["averageItemLevel"] = 180
        targets["itemCount"] = 8
        with self.assertRaisesRegex(ValueError, "implausible average item level"):
            MODULE.validate_profile_data(database)

    def test_stale_source_fails(self) -> None:
        database = valid_database()
        database["source"]["scrape"] = "2020-01-01"
        with self.assertRaisesRegex(ValueError, "exceeds"):
            MODULE.validate_profile_data(database)

    def test_unresolved_rate_fails(self) -> None:
        database = valid_database()
        database["source"]["resolveSummary"] = {"resolved": 90, "total": 100}
        with self.assertRaisesRegex(ValueError, "below 99%"):
            MODULE.validate_profile_data(database)

    def test_validation_does_not_mutate_input(self) -> None:
        database = valid_database()
        original = copy.deepcopy(database)
        MODULE.validate_profile_data(database)
        self.assertEqual(database, original)


if __name__ == "__main__":
    unittest.main()
