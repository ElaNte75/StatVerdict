from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from pathlib import Path

from tools.classcodex_targets import (
    GOAL_CONTEXT_KEY,
    ComboSkipped,
    LoadoutUpgrades,
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
    guide_targets_for,
    format_rating_sanity,
    select_loadout_upgrades,
)
from tools.spec_catalog import SPEC_BY_KEY


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


UNSUPPORTED_ERRORS = (
    "Player sv_0001 is using an unsupported spec",
    "Player sv_0001 role (hybrid) or spec isn't supported yet",
)


def wowhead_loadout(totals: dict, failures: list | None = None) -> dict:
    return {"slotCount": 1, "resolvedSlots": 1, "totals": totals, "slots": {}, "failures": failures or []}


class WowheadFallbackTests(unittest.TestCase):
    spec = SPEC_BY_KEY["PALADIN_HOLY"]
    gear = [{"itemId": 1, "slot": "Head", "ilvl": 300, "bonusIDs": [7]}]

    def run_fallback(self, simc_effect, wowhead):
        with patch("tools.classcodex_targets.run_simc", side_effect=simc_effect), redirect_stderr(io.StringIO()):
            return reconstruct_target_context(self.spec, "RAID", self.gear, "X", wowhead_reconstruct=wowhead)

    def test_uses_wowhead_gear_totals_when_simc_does_not_support_the_spec(self) -> None:
        for message in UNSUPPORTED_ERRORS:
            calls = []

            def fake_wowhead(items, *, primary):
                calls.append((items, primary))
                return wowhead_loadout({"crit": 900, "haste": 1200, "mastery": 0, "intellect": 5000, "stamina": 1})

            context = self.run_fallback(RuntimeError(message), fake_wowhead)
            self.assertEqual([({"HEAD": {"itemId": 1, "itemLevel": 300, "bonusIds": [7]}}, "intellect")], calls)
            stat_targets = context["targets"]["statTargets"]
            self.assertEqual({"critical_strike": 900.0, "haste": 1200.0, "mastery": 0.0}, stat_targets["stats"])
            self.assertEqual(
                "ClassCodex BiS + Wowhead gear totals (no SimC support for this spec)", stat_targets["source"]
            )
            self.assertEqual(["wowhead fallback"], context["targets"]["targetMetadata"]["recovery"])
            self.assertEqual([{"slot": "Head", "item": {"item_id": 1, "bonus_ids": [7]}}], context["bis"]["slots"])

    def test_never_runs_when_simc_succeeds(self) -> None:
        def forbidden(*_args, **_kwargs):
            raise AssertionError("wowhead fallback must not run")

        context = self.run_fallback([GOOD], forbidden)
        self.assertEqual("ClassCodex BiS + SimulationCraft", context["targets"]["statTargets"]["source"])

    def test_any_simc_failure_after_recovery_uses_the_fallback(self) -> None:
        def fake_wowhead(items, *, primary):
            return wowhead_loadout({"crit": 900, "haste": 1200, "mastery": 0, "intellect": 5000})

        context = self.run_fallback(RuntimeError("could not find spell data"), fake_wowhead)
        self.assertEqual(["wowhead fallback"], context["targets"]["targetMetadata"]["recovery"])

    def test_without_an_injected_reconstructor_the_combo_is_skipped_as_before(self) -> None:
        with patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError(UNSUPPORTED_ERRORS[0])), \
                redirect_stderr(io.StringIO()), self.assertRaisesRegex(ComboSkipped, "SimC run failed"):
            reconstruct_target_context(self.spec, "RAID", self.gear, "X")

    def test_any_wowhead_failure_skips_the_combo(self) -> None:
        def raising(*_args, **_kwargs):
            raise OSError("network down")

        def partial(*_args, **_kwargs):
            return wowhead_loadout({"crit": 900, "haste": 1200}, failures=[{"slot": "HEAD"}])

        for wowhead in (raising, partial):
            with self.assertRaises(ComboSkipped) as caught:
                self.run_fallback(RuntimeError(UNSUPPORTED_ERRORS[0]), wowhead)
            self.assertEqual("wowhead fallback failed", caught.exception.reason)

    def test_fewer_than_two_positive_secondaries_skips(self) -> None:
        def one_stat(*_args, **_kwargs):
            return wowhead_loadout({"crit": 900, "haste": 0, "intellect": 5000})

        with self.assertRaisesRegex(ComboSkipped, "fewer than 2 usable secondary stats"):
            self.run_fallback(RuntimeError(UNSUPPORTED_ERRORS[0]), one_stat)

    def test_build_all_passes_the_reconstructor_through(self) -> None:
        specs = {
            "PALADIN_holy": {
                "gear": {"value": {"all": {"raid": self.gear}}},
                "talents": {"value": {"all": {"raid": [{"export": "X"}]}}},
            }
        }

        def fake_wowhead(items, *, primary):
            return wowhead_loadout({"crit": 900, "versatility": 700})

        with patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError(UNSUPPORTED_ERRORS[1])), \
                redirect_stderr(io.StringIO()):
            data = build_all(specs, Path("simc"), goals=("RAID",), wowhead_reconstruct=fake_wowhead)
        context = data["profiles"]["PALADIN_HOLY"]["goals"]["RAID"]["heroTalents"]["all"]
        self.assertEqual(["wowhead fallback"], context["targets"]["targetMetadata"]["recovery"])


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


ENCHANTS = {
    "all": {
        "all": {
            "Head": [{"id": 7991, "pop": 36.8}, {"id": 8017, "itemId": 243981, "spellId": 1236001, "pop": 46.7}],
            "Main Hand": [{"id": 3368, "spellId": 53344, "pop": 63.2}],
            "Relic": [{"id": 1, "pop": 99}],
        },
        "pvp": {"Head": [{"id": 243981, "pop": 33.3}]},
    }
}
GEMS = {
    "all": {
        "all": [
            {"primary": 240983, "pop": 9.5, "secondary": [240892]},
            {"primary": 240983, "pop": 12.6, "secondary": [240908, 240910]},
        ],
        "pvp": [{"pop": 50, "secondary": [240900]}],
    }
}
UPGRADE_GEAR = [
    {"itemId": 1, "slot": "Head", "ilvl": 300, "bonusIDs": [7]},
    {"itemId": 2, "slot": "Neck", "ilvl": 300},
    {"itemId": 3, "slot": "Trinket 1", "ilvl": 300},
    {"itemId": 4, "slot": "Main Hand", "ilvl": 300},
]


class LoadoutUpgradeTests(unittest.TestCase):
    def test_picks_the_most_popular_enchant_per_slot_and_gem_set(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "deathbringer", "RAID")
        self.assertEqual(
            {
                "HEAD": {"id": 8017, "item_id": 243981, "spell_id": 1236001},
                "MAIN_HAND": {"id": 3368, "spell_id": 53344},
            },
            upgrades.enchants,
        )
        # Primary gem first, then the secondary ones.
        self.assertEqual([240983, 240908, 240910], upgrades.gems)

    def test_the_goal_context_wins_over_all(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "deathbringer", "PVP")
        # The PvP list's bare id is the scroll's item id: it is translated to the real enchant
        # the PvE list knows for that scroll.
        self.assertEqual({"HEAD": {"id": 8017, "item_id": 243981, "spell_id": 1236001}}, upgrades.enchants)
        self.assertEqual([240900], upgrades.gems)

    def test_missing_data_gives_no_upgrades(self) -> None:
        upgrades = select_loadout_upgrades(None, None, "all", "RAID")
        self.assertEqual({}, upgrades.enchants)
        self.assertEqual([], upgrades.gems)

    def test_build_simc_items_adds_enchants_and_gems_except_on_trinkets(self) -> None:
        items = build_simc_items(UPGRADE_GEAR, select_loadout_upgrades(ENCHANTS, GEMS, "all", "RAID"))
        self.assertEqual([8017], items["HEAD"]["enchantIds"])
        self.assertEqual([240983, 240908, 240910], items["HEAD"]["gemIds"])
        self.assertEqual([240983, 240908, 240910], items["NECK"]["gemIds"])
        self.assertNotIn("enchantIds", items["NECK"])
        self.assertNotIn("gemIds", items["TRINKET_1"])
        self.assertEqual([3368], items["MAIN_HAND"]["enchantIds"])


class TargetUpgradeTests(unittest.TestCase):
    spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]

    def run_targets(self, side_effect):
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "all", "RAID")
        with patch("tools.classcodex_targets.run_simc", side_effect=side_effect) as mock_run, \
                redirect_stderr(io.StringIO()):
            context = reconstruct_target_context(self.spec, "RAID", UPGRADE_GEAR, "X", upgrades=upgrades)
        return context, [call.args[1] for call in mock_run.call_args_list]

    def test_the_simulated_loadout_and_bis_slots_carry_the_same_gems_and_enchants(self) -> None:
        context, profiles = self.run_targets([GOOD])
        self.assertIn("head=,id=1,ilevel=300,bonus_id=7,gem_id=240983/240908/240910,enchant_id=8017", profiles[0])
        metadata = context["targets"]["targetMetadata"]
        self.assertEqual(2, metadata["enchantCount"])
        self.assertEqual(3, metadata["gemCount"])
        self.assertNotIn("recovery", metadata)
        self.assertEqual(
            [
                {
                    "slot": "Head",
                    "item": {
                        "item_id": 1,
                        "bonus_ids": [7],
                        "gem_ids": [240983, 240908, 240910],
                        "enchant": {"id": 8017, "item_id": 243981, "spell_id": 1236001},
                    },
                },
                {"slot": "Neck", "item": {"item_id": 2, "gem_ids": [240983, 240908, 240910]}},
                {"slot": "Trinket 1", "item": {"item_id": 3}},
                {
                    "slot": "Main Hand",
                    "item": {
                        "item_id": 4,
                        "gem_ids": [240983, 240908, 240910],
                        "enchant": {"id": 3368, "spell_id": 53344},
                    },
                },
            ],
            context["bis"]["slots"],
        )

    def test_dropped_gems_are_left_out_of_the_metadata_and_bis_slots(self) -> None:
        context, profiles = self.run_targets([RuntimeError("invalid gem_id 240983"), GOOD])
        self.assertNotIn("gem_id=", profiles[1])
        metadata = context["targets"]["targetMetadata"]
        self.assertEqual(["gems dropped"], metadata["recovery"])
        self.assertEqual(0, metadata["gemCount"])
        self.assertEqual(2, metadata["enchantCount"])
        for slot in context["bis"]["slots"]:
            self.assertNotIn("gem_ids", slot["item"])
        self.assertEqual({"id": 8017, "item_id": 243981, "spell_id": 1236001}, context["bis"]["slots"][0]["item"]["enchant"])

    def test_dropped_enchants_are_left_out_too(self) -> None:
        errors = [RuntimeError("invalid gem_id"), RuntimeError("unknown enchant_id"), GOOD]
        context, _profiles = self.run_targets(errors)
        metadata = context["targets"]["targetMetadata"]
        self.assertEqual(["gems dropped", "enchants dropped"], metadata["recovery"])
        self.assertEqual(0, metadata["enchantCount"])
        for slot in context["bis"]["slots"]:
            self.assertNotIn("enchant", slot["item"])

    def test_build_all_uses_the_specs_enchants_and_gems(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": UPGRADE_GEAR}}},
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
                "enchants": {"value": ENCHANTS, "source": "ugg"},
                "gems": {"value": GEMS, "source": "ugg"},
            }
        }
        with patch("tools.classcodex_targets.run_simc", return_value=GOOD) as mock_run:
            data = build_all(specs, Path("simc"), goals=("RAID",))
        self.assertIn("enchant_id=8017", mock_run.call_args.args[1])
        metadata = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["deathbringer"]["targets"][
            "targetMetadata"
        ]
        self.assertEqual(2, metadata["enchantCount"])


class RatingSanityReportTests(unittest.TestCase):
    def test_reports_our_summed_rating_against_ugg_top50(self) -> None:
        data = {
            "profiles": {
                "DEATHKNIGHT_FROST": {
                    "goals": {
                        "RAID": {
                            "heroTalents": {
                                "deathbringer": {
                                    "targets": {
                                        "statTargets": {"stats": {"critical_strike": 1500.0, "haste": 1500.0}},
                                        "guideTargets": {"top50": {"critical_strike": 2000.0, "haste": 2000.0}},
                                    }
                                },
                                "rider": {"targets": {"statTargets": {"stats": {"haste": 100.0}}}},
                            }
                        }
                    }
                }
            }
        }
        report = format_rating_sanity(data)
        self.assertIn("DEATHKNIGHT_FROST/RAID/deathbringer: ours 3000 vs u.gg top50 4000 (ratio 0.75)", report)
        self.assertIn("DEATHKNIGHT_FROST/RAID/rider: ours 100 vs u.gg top50 n/a", report)
        self.assertIn("median ratio 0.75 over 1 context(s)", report)


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

    def test_guide_targets_follow_goal_and_hero_with_all_hero_fallback(self) -> None:
        stat_targets = {
            "deathbringer": {"mplus": {"top50": {"crit": 1358, "haste": 682}}},
            "all": {
                "mplus": {"top50": {"crit": 1}},
                "raid": {
                    "top20": {"haste": 788, "mastery": 1180, "versatility": 181, "crit": 1413},
                    "top50": {"crit": 1300},
                    "top80": {"crit": 1200, "leech": 5},
                },
            },
        }
        self.assertEqual(
            {"top50": {"critical_strike": 1358.0, "haste": 682.0}},
            guide_targets_for(stat_targets, "deathbringer", "MYTHIC_PLUS"),
        )
        raid = guide_targets_for(stat_targets, "deathbringer", "RAID")
        self.assertEqual(
            {"critical_strike": 1413.0, "haste": 788.0, "mastery": 1180.0, "versatility": 181.0}, raid["top20"]
        )
        self.assertEqual({"critical_strike": 1200.0}, raid["top80"])
        self.assertIsNone(guide_targets_for(stat_targets, "deathbringer", "PVP"))
        self.assertIsNone(guide_targets_for(None, "deathbringer", "RAID"))

    def test_build_all_adds_guide_targets_even_after_a_recovered_run(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": TargetRecoveryTests.gear}}},
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
                "statTargets": {"value": {"all": {"raid": {"top50": {"crit": 1300, "mastery": 900}}}}},
            }
        }
        error = RuntimeError("Player sv_0001 has an Off-Hand weapon equipped with a 2h weapon")
        with patch("tools.classcodex_targets.run_simc", side_effect=[error, GOOD]):
            data = build_all(specs, Path("simc"), goals=("RAID", "PVP"))
        targets = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["deathbringer"]["targets"]
        self.assertEqual(["dropped OFF_HAND"], targets["targetMetadata"]["recovery"])
        self.assertEqual({"top50": {"critical_strike": 1300.0, "mastery": 900.0}}, targets["guideTargets"])

    def test_guide_targets_are_omitted_when_ugg_has_none(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": TargetRecoveryTests.gear}}},
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
            }
        }
        with patch("tools.classcodex_targets.run_simc", return_value=GOOD):
            data = build_all(specs, Path("simc"), goals=("RAID",))
        targets = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["deathbringer"]["targets"]
        self.assertNotIn("guideTargets", targets)

    def test_skips_a_spec_key_not_in_the_catalog(self) -> None:
        specs = {"NOTASPEC_madeup": {"gear": {"value": {}, "source": "ugg"}}}
        data = build_all(specs, Path("simc"))
        self.assertEqual({}, data["profiles"])


class PvpEnchantScrollTests(unittest.TestCase):
    ENCHANTS = {
        "all": {
            "all": {"Head": [{"id": 7961, "itemId": 243981, "spellId": 1236100, "pop": 50}]},
            "pvp": {
                "Head": [{"id": 243981, "pop": 60}],
                "Chest": [{"id": 999999, "pop": 60}],
            },
        }
    }

    def test_a_bare_pvp_scroll_id_becomes_the_real_enchant(self) -> None:
        from tools.classcodex_targets import select_loadout_upgrades

        upgrades = select_loadout_upgrades(self.ENCHANTS, None, "hero", "PVP")
        head = upgrades.enchants["HEAD"]
        self.assertEqual({"id": 7961, "item_id": 243981, "spell_id": 1236100}, head)

    def test_an_unknown_bare_scroll_id_is_kept_for_display_but_never_simulated(self) -> None:
        upgrades = select_loadout_upgrades(self.ENCHANTS, None, "hero", "PVP")
        self.assertEqual({"item_id": 999999}, upgrades.enchants["CHEST"])
        items = build_simc_items([{"itemId": 5, "slot": "Chest"}], upgrades)
        self.assertNotIn("enchantIds", items["CHEST"])


# Real shapes (2026-09-29): Icy Veins' enchant ids are scroll item ids, its
# weapon runes are {id = spellId, spellId}; u.gg's PvE entries carry the real
# enchant id, the scroll's itemId and the spellId.
ICY_ENCHANTS = {
    "all": {
        "all": {
            "Head": [{"id": 244007}],
            "Shoulders": [{"id": 243962}],
            "Chest": [{"id": 777777}],
            "Main Hand": [{"id": 53344, "spellId": 53344}],
            "Off Hand": [{"id": 62158, "spellId": 62158}],
        }
    }
}
LOOKUP = {
    "byItem": {244007: {"id": 8017, "item_id": 244007, "spell_id": 1236084}},
    "bySpell": {
        1236084: {"id": 8017, "item_id": 244007, "spell_id": 1236084},
        1236062: {"id": 7973, "item_id": 243963, "spell_id": 1236062},
        53344: {"id": 3368, "spell_id": 53344},
    },
    # db_gamedata recipes inverted: scroll item -> enchant spell.
    "recipeSpellByItem": {244007: 1236084, 243962: 1236062},
}


class IcyVeinsEnchantTranslationTests(unittest.TestCase):
    def test_scroll_ids_and_rune_spells_become_real_enchants(self) -> None:
        upgrades = select_loadout_upgrades(ICY_ENCHANTS, None, "deathbringer", "RAID", LOOKUP)
        self.assertEqual({"id": 8017, "item_id": 244007, "spell_id": 1236084}, upgrades.enchants["HEAD"])
        # Not a u.gg itemId, but the recipe names its spell, which u.gg knows.
        self.assertEqual({"id": 7973, "item_id": 243962, "spell_id": 1236062}, upgrades.enchants["SHOULDER"])
        self.assertEqual({"id": 3368, "spell_id": 53344}, upgrades.enchants["MAIN_HAND"])

    def test_untranslatable_enchants_keep_only_their_item_or_spell_id(self) -> None:
        upgrades = select_loadout_upgrades(ICY_ENCHANTS, None, "deathbringer", "RAID", LOOKUP)
        self.assertEqual({"item_id": 777777}, upgrades.enchants["CHEST"])
        self.assertEqual({"spell_id": 62158}, upgrades.enchants["OFF_HAND"])
        gear = [
            {"itemId": 1, "slot": "Chest", "bonusIDs": [13848]},
            {"itemId": 2, "slot": "Off Hand", "bonusIDs": [13848]},
            {"itemId": 3, "slot": "Head", "bonusIDs": [13848]},
        ]
        items = build_simc_items(gear, upgrades)
        self.assertNotIn("enchantIds", items["CHEST"])
        self.assertNotIn("enchantIds", items["OFF_HAND"])
        self.assertEqual([8017], items["HEAD"]["enchantIds"])
        with patch("tools.classcodex_targets.run_simc", return_value=GOOD) as mock_run, redirect_stderr(io.StringIO()):
            context = reconstruct_target_context(SPEC_BY_KEY["DEATHKNIGHT_FROST"], "RAID", gear, "X", upgrades=upgrades)
        profile = mock_run.call_args.args[1]
        self.assertNotIn("777777", profile)
        self.assertNotIn("62158", profile)
        slots = {slot["slot"]: slot["item"] for slot in context["bis"]["slots"]}
        self.assertEqual({"item_id": 777777}, slots["Chest"]["enchant"])
        self.assertEqual({"spell_id": 62158}, slots["Off Hand"]["enchant"])
        self.assertEqual(8017, slots["Head"]["enchant"]["id"])
        self.assertEqual(1, context["targets"]["targetMetadata"]["enchantCount"])

    def test_icy_veins_single_gem_set_primary_first(self) -> None:
        gems = {"all": {"all": [{"primary": 240967, "secondary": [240908, 240898]}]}}
        self.assertEqual([240967, 240908, 240898], select_loadout_upgrades(None, gems, "hero", "RAID").gems)

    def test_build_all_passes_the_builds_enchant_lookup(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": [{"itemId": 1, "slot": "Head", "ilvl": 300}]}}},
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
                "enchants": {"value": ICY_ENCHANTS, "source": "icyveins"},
                "enchantLookup": {"value": LOOKUP, "source": "ugg+gamedata"},
            }
        }
        with patch("tools.classcodex_targets.run_simc", return_value=GOOD) as mock_run:
            build_all(specs, Path("simc"), goals=("RAID",))
        self.assertIn("enchant_id=8017", mock_run.call_args.args[1])


class NoAlternativesTests(unittest.TestCase):
    """Owner decision 2026-09-29: only the single best gem/enchant is kept."""

    def test_upgrades_carry_only_the_best_choice(self) -> None:
        self.assertEqual(("enchants", "gems"), LoadoutUpgrades._fields)

    def test_bis_slots_never_carry_alternatives(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "all", "RAID")
        with patch("tools.classcodex_targets.run_simc", return_value=GOOD), redirect_stderr(io.StringIO()):
            context = reconstruct_target_context(
                SPEC_BY_KEY["DEATHKNIGHT_FROST"], "RAID", UPGRADE_GEAR, "X", upgrades=upgrades
            )
        for slot in context["bis"]["slots"]:
            self.assertNotIn("gem_alt_id", slot["item"])
            self.assertNotIn("enchant_alt", slot["item"])


if __name__ == "__main__":
    unittest.main()


class AnnotatedPriorityEntryTests(unittest.TestCase):
    def test_icy_veins_stat_notes_keep_the_stat(self) -> None:
        from tools.classcodex_targets import priority_row_from_context

        row = priority_row_from_context(
            {"secondary": [[{"stat": "versatility", "note": "to 24%"}], ["mastery"], ["haste"], ["crit"]]}, "PvP", "hero"
        )
        self.assertEqual(["versatility", "mastery", "haste", "critical_strike"], row["order"])
