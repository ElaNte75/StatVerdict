from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.classcodex_targets import (
    GOAL_CONTEXT_KEY,
    select_context,
    build_simc_items,
    average_item_level,
    select_talent_export,
    build_trinkets,
    build_priority_row,
    build_target_context,
)
from tools.live_benchmark_engine import SPEC_BY_KEY


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


class SelectTalentExportTests(unittest.TestCase):
    def test_prefers_the_entry_marked_recommended(self) -> None:
        talents = {
            "deathbringer": {
                "mplus": [
                    {"export": "AAA", "label": "DW Frostbane"},
                    {"export": "BBB", "label": "DW Breath", "recommended": True},
                ]
            }
        }
        self.assertEqual("BBB", select_talent_export(talents, "deathbringer", "mplus"))

    def test_falls_back_to_the_first_entry_when_none_is_recommended(self) -> None:
        talents = {"deathbringer": {"raid": [{"export": "CCC", "label": "Raid"}]}}
        self.assertEqual("CCC", select_talent_export(talents, "deathbringer", "raid"))

    def test_returns_none_when_the_context_has_no_entries(self) -> None:
        talents = {"deathbringer": {"all": []}}
        self.assertIsNone(select_talent_export(talents, "deathbringer", "pvp"))


class BuildTrinketsAndPriorityTests(unittest.TestCase):
    def test_build_trinkets_passes_through_tier_and_bonus_ids(self) -> None:
        trinkets = {"all": {"raid": [{"itemId": 270175, "bonusIDs": [13848], "tier": "S"}]}}
        result = build_trinkets(trinkets, "all", "raid")
        self.assertEqual([{"item_id": 270175, "bonus_ids": [13848], "tier": "S"}], result)

    def test_build_trinkets_defaults_missing_bonus_ids_to_empty_list(self) -> None:
        trinkets = {"all": {"all": [{"itemId": 1, "tier": "A"}]}}
        result = build_trinkets(trinkets, "all", "pvp")
        self.assertEqual([{"item_id": 1, "bonus_ids": [], "tier": "A"}], result)

    def test_build_priority_row_converts_tier_groups_to_order_and_tiers(self) -> None:
        stat_priority = {
            "deathbringer": {"mplus": {"secondary": [["crit"], ["haste", "mastery"], ["versatility"]]}}
        }
        row = build_priority_row(stat_priority, "deathbringer", "mplus", "Mythic+", "deathbringer")
        self.assertEqual(
            {
                "context": "Mythic+",
                "heroTalent": "deathbringer",
                "order": ["crit", "haste", "mastery", "versatility"],
                "tiers": [["haste", "mastery"]],
            },
            row,
        )

    def test_build_priority_row_returns_none_when_no_secondary_list(self) -> None:
        stat_priority = {"deathbringer": {"raid": {}}}
        self.assertIsNone(build_priority_row(stat_priority, "deathbringer", "raid", "Raid", "deathbringer"))

    def test_build_priority_row_drops_non_string_group_elements(self) -> None:
        stat_priority = {
            "deathbringer": {"mplus": {"secondary": [["crit", 123], ["haste"]]}}
        }
        row = build_priority_row(stat_priority, "deathbringer", "mplus", "Mythic+", "deathbringer")
        # Non-string element (123) should be dropped from both order and tiers
        self.assertEqual(
            {
                "context": "Mythic+",
                "heroTalent": "deathbringer",
                "order": ["crit", "haste"],
                "tiers": [],  # First group only has 1 valid string, so not a tie
            },
            row,
        )


class BuildTargetContextTests(unittest.TestCase):
    def test_reconstructs_targets_and_bis_from_gear_and_a_simc_run(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [
            {"itemId": 271474, "slot": "Head", "bonusIDs": [1], "ilvl": 334},
            {"itemId": 268265, "slot": "Neck", "bonusIDs": [2], "ilvl": 344},
        ]
        talents = {"all": {"mplus": [{"export": "TALENTSTRING", "recommended": True}]}}
        reconstructed = {
            "ratings": {"crit": 501.0, "haste": 602.0, "mastery": 703.0, "versatility": 804.0},
        }
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})) as mock_run:
            context = build_target_context(spec, "MYTHIC_PLUS", gear, talents, "all", "mplus")

        self.assertEqual(
            {"critical_strike": 501.0, "haste": 602.0, "mastery": 703.0, "versatility": 804.0},
            context["targets"]["statTargets"]["stats"],
        )
        self.assertEqual(2, context["targets"]["itemCount"])
        self.assertEqual(339.0, context["targets"]["averageItemLevel"])
        self.assertEqual("MYTHIC_PLUS", context["targets"]["sourceGoal"])
        self.assertEqual(
            [
                {"slot": "Head", "item": {"item_id": 271474, "bonus_ids": [1]}},
                {"slot": "Neck", "item": {"item_id": 268265, "bonus_ids": [2]}},
            ],
            context["bis"]["slots"],
        )
        mock_run.assert_called_once()

    def test_returns_none_when_no_talent_export_is_available(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 300}]
        self.assertIsNone(build_target_context(spec, "PVP", gear, {}, "all", "pvp"))

    def test_returns_none_when_gear_list_is_empty(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        self.assertIsNone(build_target_context(spec, "RAID", [], talents, "all", "raid"))

    def test_returns_none_when_simc_raises(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 300}]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        with patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError("boom")):
            self.assertIsNone(build_target_context(spec, "RAID", gear, talents, "all", "raid"))

    def test_returns_none_when_fewer_than_two_usable_stats(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 300}]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        reconstructed = {"ratings": {"crit": 501.0}}
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})):
            self.assertIsNone(build_target_context(spec, "RAID", gear, talents, "all", "raid"))


if __name__ == "__main__":
    unittest.main()
