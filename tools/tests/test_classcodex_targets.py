from __future__ import annotations

import unittest

from tools.classcodex_targets import GOAL_CONTEXT_KEY, select_context, build_simc_items, average_item_level


class SelectContextTests(unittest.TestCase):
    def test_returns_the_exact_goal_context_when_present(self) -> None:
        nested = {"deathbringer": {"mplus": ["A"], "all": ["B"]}}
        result = select_context(nested, "deathbringer", GOAL_CONTEXT_KEY["MYTHIC_PLUS"])
        self.assertEqual(["A"], result)

    def test_falls_back_to_all_when_the_goal_context_is_missing(self) -> None:
        nested = {"deathbringer": {"all": ["B"]}}
        result = select_context(nested, "deathbringer", GOAL_CONTEXT_KEY["PVP"])
        self.assertEqual(["B"], result)

    def test_returns_none_when_neither_the_goal_context_nor_all_exists(self) -> None:
        nested = {"deathbringer": {"raid": ["C"]}}
        result = select_context(nested, "deathbringer", GOAL_CONTEXT_KEY["PVP"])
        self.assertIsNone(result)

    def test_returns_none_for_an_unknown_hero_talent_key(self) -> None:
        nested = {"deathbringer": {"all": ["B"]}}
        result = select_context(nested, "sanlayn", GOAL_CONTEXT_KEY["MYTHIC_PLUS"])
        self.assertIsNone(result)


class BuildSimcItemsTests(unittest.TestCase):
    def test_converts_slot_names_and_carries_ilvl_and_bonus_ids(self) -> None:
        gear = [
            {"itemId": 271474, "slot": "Head", "bonusIDs": [13695, 13692], "ilvl": 334},
            {"itemId": 268265, "slot": "Neck", "bonusIDs": [6652, 13668]},
        ]
        items = build_simc_items(gear)
        self.assertEqual(
            {"itemId": 271474, "itemLevel": 334, "bonusIds": [13695, 13692]},
            items["HEAD"],
        )
        self.assertEqual({"itemId": 268265, "bonusIds": [6652, 13668]}, items["NECK"])
        self.assertNotIn("itemLevel", items["NECK"])

    def test_skips_entries_with_unknown_slot_names(self) -> None:
        gear = [{"itemId": 1, "slot": "Relic", "bonusIDs": []}]
        self.assertEqual({}, build_simc_items(gear))

    def test_average_item_level_ignores_entries_without_ilvl(self) -> None:
        gear = [
            {"itemId": 1, "slot": "Head", "ilvl": 330},
            {"itemId": 2, "slot": "Neck", "ilvl": 340},
            {"itemId": 3, "slot": "Waist"},
        ]
        self.assertEqual(335.0, average_item_level(gear))

    def test_average_item_level_is_none_when_nothing_has_ilvl(self) -> None:
        self.assertIsNone(average_item_level([{"itemId": 1, "slot": "Head"}]))


if __name__ == "__main__":
    unittest.main()
