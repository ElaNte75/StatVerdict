"""tools/item_check_verdict.py runs the addon's own comparison on an item-check result
(here a small made-up one) and lines it up against SimC's answer."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as verdict
from tools.tests.test_addon_lua import LuaRuntime

SLOTS = ["head", "neck", "shoulders", "back", "chest", "wrists", "hands", "waist", "legs", "feet",
         "finger1", "finger2", "trinket1", "trinket2", "main_hand", "off_hand"]


def sim(delta_pct: float) -> dict:
    return {"dps": {"mean": 100000 * (1 + delta_pct / 100)},
            "delta": {"abs": 1000 * delta_pct, "pct": delta_pct, "err95": 50.0}}


def result() -> dict:
    gear = {slot: {"name": slot, "ilevel": 246, "agility": 60, "haste_rating": 50, "mastery_rating": 50}
            for slot in SLOTS}
    better = {"name": "Better Neck", "ilevel": 272, "agility": 0, "haste_rating": 200, "mastery_rating": 200}
    worse = {"name": "Worse Neck", "ilevel": 200, "haste_rating": 20}
    return {
        "character": "Enhancement Shaman", "generated_at": "test",
        "baseline": {"stats": {"ratings": {"crit": 400, "haste": 600, "mastery": 700, "versatility": 100},
                               "agility": 1600}, "gear": gear},
        "rows": [
            {"slot": "neck", "replaced_slot": "neck", "name": "Better Neck", "item_id": 1, "ilevel": 272,
             "stats": "Haste 200", "gear": better, "replaced": "neck", "replaced_ilevel": 246, "st": sim(2.0),
             "simulable": True},
            {"slot": "neck", "replaced_slot": "neck", "name": "Worse Neck", "item_id": 2, "ilevel": 200,
             "stats": "Haste 20", "gear": worse, "replaced": "neck", "replaced_ilevel": 246, "st": sim(-2.0),
             "simulable": True},
            {"slot": "trinket", "name": "On-use", "item_id": 3, "ilevel": 272, "stats": "Agi 100",
             "simulable": False, "gear": better, "replaced_slot": "trinket1", "st": sim(0.3)},
        ],
    }


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ReplayTests(unittest.TestCase):
    def test_addon_answers_are_lined_up_with_simc(self) -> None:
        replayed = verdict.replay(result(), goals=("MYTHIC_PLUS",), modes=("GUIDE",))
        run = replayed["runs"]["MYTHIC_PLUS/GUIDE"]
        by_name = {r["row"]["name"]: r for r in run["rows"]}
        self.assertEqual("upgrade", by_name["Better Neck"]["addon"]["verdict"])
        self.assertEqual("not an upgrade", by_name["Worse Neck"]["addon"]["verdict"])
        self.assertEqual("unreliable", by_name["On-use"]["simc"])
        self.assertGreater(by_name["Better Neck"]["addon"]["points"], 0)
        self.assertTrue(by_name["Better Neck"]["addon"]["breakdown"])
        text = verdict.render(result(), replayed)
        self.assertIn("OK: both say upgrade", text)
        self.assertIn("OK: both say not an upgrade", text)

    def test_classification(self) -> None:
        self.assertEqual("MISSED: SimC says upgrade, addon does not", verdict.classify("upgrade", "not an upgrade"))
        self.assertTrue(verdict.classify("same", "upgrade").startswith("WRONG"))
        self.assertEqual("not compared", verdict.classify("unreliable", "upgrade"))

    def test_spearman(self) -> None:
        self.assertAlmostEqual(1.0, verdict.spearman([(1, 10), (2, 20), (3, 30)]))
        self.assertAlmostEqual(-1.0, verdict.spearman([(1, 30), (2, 20), (3, 10)]))
        self.assertIsNone(verdict.spearman([(1, 1)]))


if __name__ == "__main__":
    unittest.main()
