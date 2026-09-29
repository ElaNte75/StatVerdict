from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from pathlib import Path

from tools.classcodex_targets import (
    GOAL_CONTEXT_KEY,
    ComboSkipped,
    reconstruct_target_context,
    talent_export_from_entries,
    talent_exports_from_entries,
    select_context,
    select_goal_context,
    build_simc_items,
    average_item_level,
    select_talent_export,
    build_trinkets,
    build_priority_row,
    build_target_context,
    build_all,
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


class SelectGoalContextTests(unittest.TestCase):
    def test_exact_first_choice_key_wins_over_fallback_keys(self) -> None:
        nested = {"deathbringer": {"mplus": ["M"], "aoe": ["A"], "all": ["X"]}}
        self.assertEqual(["M"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_mythic_plus_falls_back_to_aoe_when_mplus_is_absent(self) -> None:
        nested = {"deathbringer": {"aoe": ["A"], "single-target": ["S"], "all": ["X"]}}
        self.assertEqual(["A"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_raid_falls_back_to_single_target_when_raid_is_absent(self) -> None:
        nested = {"deathbringer": {"aoe": ["A"], "single-target": ["S"], "all": ["X"]}}
        self.assertEqual(["S"], select_goal_context(nested, "deathbringer", "RAID"))

    def test_all_is_the_last_resort_context(self) -> None:
        nested = {"deathbringer": {"pvp": ["P"], "all": ["X"]}}
        self.assertEqual(["X"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))
        self.assertEqual(["X"], select_goal_context(nested, "deathbringer", "RAID"))

    def test_pvp_never_uses_aoe_or_single_target(self) -> None:
        nested = {"deathbringer": {"aoe": ["A"], "single-target": ["S"]}}
        self.assertIsNone(select_goal_context(nested, "deathbringer", "PVP"))

    def test_falls_back_to_the_all_hero_key_when_the_hero_has_no_match(self) -> None:
        # Real ClassCodex layout: Mythic+ gear only exists under hero "all",
        # the specific hero keys only carry PvP gear.
        nested = {"all": {"mplus": ["ALL-M"]}, "deathbringer": {"pvp": ["DB-P"]}}
        self.assertEqual(["ALL-M"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))
        self.assertEqual(["DB-P"], select_goal_context(nested, "deathbringer", "PVP"))

    def test_a_hero_specific_all_context_beats_the_all_hero(self) -> None:
        nested = {"all": {"mplus": ["ALL-M"]}, "deathbringer": {"all": ["DB-X"]}}
        self.assertEqual(["DB-X"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_empty_values_are_skipped_so_the_chain_keeps_looking(self) -> None:
        nested = {"deathbringer": {"mplus": [], "aoe": ["A"]}}
        self.assertEqual(["A"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_returns_none_when_nothing_matches(self) -> None:
        self.assertIsNone(select_goal_context({"deathbringer": {"pvp": ["P"]}}, "deathbringer", "RAID"))
        self.assertIsNone(select_goal_context(None, "deathbringer", "RAID"))


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


class TalentExportsFromEntriesTests(unittest.TestCase):
    def test_recommended_first_then_the_rest_in_order_without_duplicates(self) -> None:
        entries = [
            {"export": "A"},
            {"export": "B", "recommended": True},
            {"export": "A"},
            {"label": "no export"},
            "junk",
            {"export": "C"},
        ]
        self.assertEqual(["B", "A", "C"], talent_exports_from_entries(entries))
        self.assertEqual("B", talent_export_from_entries(entries))

    def test_empty_or_invalid_input(self) -> None:
        self.assertEqual([], talent_exports_from_entries(None))
        self.assertEqual([], talent_exports_from_entries([]))
        self.assertIsNone(talent_export_from_entries([]))


TALENT_ERROR = "Selected node 82241 entry 103320 is not available to player's spec"
GOOD = ({"sv_0001": {"ratings": {"crit": 1.0, "haste": 2.0}}}, {})


class TalentFallbackTests(unittest.TestCase):
    spec = SPEC_BY_KEY["DRUID_RESTORATION"]
    gear = [{"itemId": 1, "slot": "Head", "ilvl": 300}]

    def run_targets(self, side_effect, exports):
        with patch("tools.classcodex_targets.run_simc", side_effect=side_effect) as mock_run, \
                redirect_stderr(io.StringIO()):
            context = reconstruct_target_context(self.spec, "RAID", self.gear, exports)
        return context, [call.args[1] for call in mock_run.call_args_list]

    def test_tries_the_next_export_when_simc_rejects_the_talents(self) -> None:
        context, profiles = self.run_targets([RuntimeError(TALENT_ERROR), GOOD], ["A", "B"])
        self.assertIn("talents=A", profiles[0])
        self.assertIn("talents=B", profiles[1])
        self.assertEqual(["talent export 2"], context["targets"]["targetMetadata"]["recovery"])

    def test_runs_without_talents_when_every_export_is_rejected(self) -> None:
        context, profiles = self.run_targets([RuntimeError(TALENT_ERROR), RuntimeError(TALENT_ERROR), GOOD], ["A", "B"])
        self.assertEqual(3, len(profiles))
        self.assertNotIn("talents=", profiles[2])
        self.assertEqual(["talents ignored"], context["targets"]["targetMetadata"]["recovery"])

    def test_a_non_talent_error_is_not_retried(self) -> None:
        with patch("tools.classcodex_targets.run_simc", side_effect=[RuntimeError("boom"), GOOD]) as mock_run, \
                redirect_stderr(io.StringIO()), self.assertRaises(ComboSkipped):
            reconstruct_target_context(self.spec, "RAID", self.gear, ["A", "B"])
        self.assertEqual(1, mock_run.call_count)

    def test_the_run_without_talents_failing_skips_the_combo(self) -> None:
        with self.assertRaisesRegex(ComboSkipped, "SimC run failed"):
            self.run_targets([RuntimeError(TALENT_ERROR)] * 3, ["A", "B"])

    def test_build_all_hands_every_export_to_the_fallback(self) -> None:
        specs = {
            "DRUID_restoration": {
                "gear": {"value": {"all": {"raid": self.gear}}},
                "talents": {"value": {"keeper-of-the-grove": {"raid": [{"export": "A"}, {"export": "B"}]}}},
            }
        }
        with patch("tools.classcodex_targets.run_simc", side_effect=[RuntimeError(TALENT_ERROR), GOOD]), \
                redirect_stderr(io.StringIO()):
            data = build_all(specs, Path("simc"), goals=("RAID",))
        context = data["profiles"]["DRUID_RESTORATION"]["goals"]["RAID"]["heroTalents"]["keeper-of-the-grove"]
        self.assertEqual(["talent export 2"], context["targets"]["targetMetadata"]["recovery"])


class TargetRecoveryTests(unittest.TestCase):
    spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
    gear = [
        {"itemId": 1, "slot": "Head", "ilvl": 300},
        {"itemId": 2, "slot": "Main Hand", "ilvl": 300},
        {"itemId": 3, "slot": "Off Hand", "ilvl": 300},
    ]

    def test_runs_a_stat_sheet_only_profile_without_recovery_metadata(self) -> None:
        with patch("tools.classcodex_targets.run_simc", return_value=GOOD) as mock_run:
            context = reconstruct_target_context(self.spec, "RAID", self.gear, "X")
        self.assertIn("default_actions=0", mock_run.call_args.args[1].splitlines())
        self.assertNotIn("recovery", context["targets"]["targetMetadata"])

    def test_weapon_recovery_is_recorded_and_bis_keeps_every_slot(self) -> None:
        error = RuntimeError("Player sv_0001 has an Off-Hand weapon equipped with a 2h weapon")
        with patch("tools.classcodex_targets.run_simc", side_effect=[error, GOOD]) as mock_run:
            context = reconstruct_target_context(self.spec, "RAID", self.gear, "X")
        self.assertNotIn("off_hand=", mock_run.call_args.args[1])
        self.assertEqual(["dropped OFF_HAND"], context["targets"]["targetMetadata"]["recovery"])
        self.assertEqual(["Head", "Main Hand", "Off Hand"], [slot["slot"] for slot in context["bis"]["slots"]])
        self.assertEqual(3, context["targets"]["itemCount"])


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
                # ClassCodex's raw "crit" is normalized to the addon's canonical key.
                "order": ["critical_strike", "haste", "mastery", "versatility"],
                "tiers": [["haste", "mastery"]],
            },
            row,
        )

    def test_build_priority_row_normalizes_tiers_and_drops_unknown_or_repeated_tokens(self) -> None:
        stat_priority = {
            "deathbringer": {"mplus": {"secondary": [["Crit", "vers"], ["leech"], ["crit", "mastery"]]}}
        }
        row = build_priority_row(stat_priority, "deathbringer", "mplus", "Mythic+", "deathbringer")
        self.assertEqual(["critical_strike", "versatility", "mastery"], row["order"])
        self.assertEqual([["critical_strike", "versatility"]], row["tiers"])

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
                "order": ["critical_strike", "haste"],
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

    def test_gear_without_any_ilvl_still_builds_with_a_null_average_item_level(self) -> None:
        # Real ClassCodex PvP gear lists carry no "ilvl" at all; that is not a
        # failure, the average is simply unknown.
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [{"itemId": 1, "slot": "Head", "bonusIDs": [1]}, {"itemId": 2, "slot": "Neck"}]
        talents = {"all": {"pvp": [{"export": "PVPSTRING"}]}}
        reconstructed = {"ratings": {"crit": 501.0, "haste": 602.0, "mastery": 703.0, "versatility": 804.0}}
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})):
            context = build_target_context(spec, "PVP", gear, talents, "all", "pvp")
        self.assertIsNotNone(context)
        self.assertIsNone(context["targets"]["averageItemLevel"])
        self.assertEqual(2, context["targets"]["itemCount"])

    def test_item_level_slots_counts_only_entries_that_have_an_ilvl(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [
            {"itemId": 1, "slot": "Head", "ilvl": 330},
            {"itemId": 2, "slot": "Neck", "ilvl": 340},
            {"itemId": 3, "slot": "Waist"},
        ]
        talents = {"all": {"mplus": [{"export": "X"}]}}
        reconstructed = {"ratings": {"crit": 1.0, "haste": 2.0}}
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})):
            context = build_target_context(spec, "MYTHIC_PLUS", gear, talents, "all", "mplus")
        self.assertEqual(3, context["targets"]["itemCount"])
        self.assertEqual(2, context["targets"]["itemLevelSlots"])
        self.assertEqual(335.0, context["targets"]["averageItemLevel"])

    def test_duplicate_slots_resolve_the_same_way_everywhere(self) -> None:
        # Two entries for one slot: the last one wins for the simulated SimC
        # items, the BiS list, the item count and the item level alike.
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [
            {"itemId": 1, "slot": "Head", "ilvl": 300},
            {"itemId": 2, "slot": "Neck", "ilvl": 340},
            {"itemId": 9, "slot": "Head", "ilvl": 360},
        ]
        talents = {"all": {"mplus": [{"export": "X"}]}}
        reconstructed = {"ratings": {"crit": 1.0, "haste": 2.0}}
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})) as mock_run:
            context = build_target_context(spec, "MYTHIC_PLUS", gear, talents, "all", "mplus")
        profile_text = mock_run.call_args.args[1]
        self.assertIn("head=,id=9,", profile_text)
        self.assertNotIn("id=1,", profile_text)
        self.assertEqual([9, 2], [slot["item"]["item_id"] for slot in context["bis"]["slots"]])
        self.assertEqual(2, context["targets"]["itemCount"])
        self.assertEqual(350.0, context["targets"]["averageItemLevel"])

    def test_zero_valued_stats_do_not_count_toward_the_two_stat_minimum(self) -> None:
        # Mirrors the addon's CountPositiveTargets: only values > 0 count.
        spec = SPEC_BY_KEY["DEATHKNIGHT_BLOOD"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 300}]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        reconstructed = {"ratings": {"crit": 501.0, "haste": 0.0, "mastery": 0, "versatility": -1.0}}
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})):
            self.assertIsNone(build_target_context(spec, "RAID", gear, talents, "all", "raid"))

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


class BuildAllTests(unittest.TestCase):
    def test_builds_one_profile_per_spec_with_a_context_per_goal_and_hero_talent(self) -> None:
        specs = {
            "DEATHKNIGHT_blood": {
                "gear": {"value": {"all": {"mplus": [{"itemId": 1, "slot": "Head", "ilvl": 330}], "raid": [{"itemId": 2, "slot": "Head", "ilvl": 330}]}}, "source": "ugg"},
                "talents": {"value": {"all": {"mplus": [{"export": "M", "recommended": True}], "raid": [{"export": "R", "recommended": True}]}}, "source": "ugg"},
                "trinkets": {"value": {"all": {"mplus": [{"itemId": 9, "tier": "S"}]}}, "source": "ugg"},
                "statPriority": {"value": {"all": {"mplus": {"secondary": [["crit"], ["haste"]]}}}, "source": "ugg"},
            }
        }
        reconstructed = {"ratings": {"crit": 500.0, "haste": 500.0, "mastery": 500.0, "versatility": 500.0}}
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})):
            data = build_all(specs, Path("simc"), goals=("MYTHIC_PLUS", "RAID"))

        # Keyed by the addon's own (uppercase) spec key, not ClassCodex's raw casing.
        self.assertEqual(["DEATHKNIGHT_BLOOD"], list(data["profiles"]))
        profile = data["profiles"]["DEATHKNIGHT_BLOOD"]
        self.assertEqual("DEATHKNIGHT_BLOOD", profile["specKey"])
        self.assertEqual("DEATHKNIGHT", profile["classToken"])
        mplus_context = profile["goals"]["MYTHIC_PLUS"]["heroTalents"]["all"]
        self.assertIn("targets", mplus_context)
        self.assertEqual([{"item_id": 9, "bonus_ids": [], "tier": "S"}], mplus_context["trinkets"])
        self.assertEqual(1, len(mplus_context["priorityProfiles"]))
        self.assertNotIn("PVP", profile["goals"])  # no PVP data anywhere in this fixture

    def test_skips_a_spec_key_not_in_the_catalog(self) -> None:
        specs = {"NOTASPEC_madeup": {"gear": {"value": {}, "source": "ugg"}}}
        data = build_all(specs, Path("simc"))
        self.assertEqual({}, data["profiles"])


if __name__ == "__main__":
    unittest.main()
