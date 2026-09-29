"""Per-track (Hero / Champion 6/6) Measured targets: the same BiS loadout
re-simulated with each item's upgrade-track bonus id swapped through
trackSwap (tools/upgrade_tracks.py)."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from tools.classcodex_targets import (
    build_all,
    format_coverage_report,
    reconstruct_target_context,
    select_loadout_upgrades,
)
from tools.spec_catalog import SPEC_BY_KEY
from tools.upgrade_tracks import TrackSwap

TRACK_SWAP = TrackSwap(
    swap={"hero": {12854: 12846, 13848: 12846}, "champion": {12854: 12838, 13848: 12838, 12846: 12838}},
    item_levels={"myth": 334, "hero": 321, "champion": 308},
    unmapped={"hero": [], "champion": []},
    track_of={12854: "myth", 13848: "myth", 12846: "hero"},
)

GEAR = [
    {"itemId": 1, "slot": "Head", "bonusIDs": [12854, 13847]},
    {"itemId": 2, "slot": "Neck", "bonusIDs": [8960]},
]

MYTH = {"sv_0001": {"ratings": {"crit": 100.0, "haste": 200.0}, "item_levels": {"head": 334.0, "neck": 300.0}}}
LEVELS = {
    "sv_0001": {"ratings": {"crit": 90.0, "haste": 180.0}, "item_levels": {"head": 321.0, "neck": 300.0}},
    "sv_0002": {"ratings": {"crit": 80.0, "haste": 160.0}, "item_levels": {"head": 308.0, "neck": 300.0}},
}
TALENT_ERROR = "Selected node 82241 entry 103320 is not available to player's spec"


def result(actors: dict) -> tuple[dict, dict]:
    return actors, {}


class TrackLevelTests(unittest.TestCase):
    spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]

    def run_targets(self, side_effect, gear=None, talents="X", track_swap=TRACK_SWAP, **kwargs):
        with patch("tools.classcodex_targets.run_simc", side_effect=side_effect) as mock_run, \
                redirect_stderr(io.StringIO()):
            context = reconstruct_target_context(
                self.spec, "RAID", gear or GEAR, talents, track_swap=track_swap, **kwargs
            )
        return context, [call.args[1] for call in mock_run.call_args_list]

    def test_hero_and_champion_are_simulated_together_with_swapped_track_ids(self) -> None:
        context, profiles = self.run_targets([result(MYTH), result(LEVELS)])
        self.assertEqual(2, len(profiles))
        self.assertIn("head=,id=1,bonus_id=12854/13847", profiles[0])
        hero_actor, champion_actor = profiles[1].split('deathknight="sv_0002"')
        self.assertIn("head=,id=1,bonus_id=12846/13847", hero_actor)
        self.assertIn("head=,id=1,bonus_id=12838/13847", champion_actor)
        self.assertIn("neck=,id=2,bonus_id=8960", champion_actor)
        self.assertIn("talents=X", champion_actor)
        self.assertIn("default_actions=0", champion_actor)
        targets = context["targets"]
        self.assertEqual(
            {
                "hero": {"statTargets": {"stats": {"critical_strike": 90.0, "haste": 180.0}}, "averageItemLevel": 310.5},
                "champion": {"statTargets": {"stats": {"critical_strike": 80.0, "haste": 160.0}}, "averageItemLevel": 304.0},
            },
            targets["levels"],
        )
        # Myth stays where it was; the BiS slots keep the Myth ids.
        self.assertEqual({"critical_strike": 100.0, "haste": 200.0}, targets["statTargets"]["stats"])
        self.assertEqual(317.0, targets["averageItemLevel"])
        self.assertEqual([12854, 13847], context["bis"]["slots"][0]["item"]["bonus_ids"])
        self.assertNotIn("swapMisses", targets["targetMetadata"])

    def test_without_a_track_swap_nothing_extra_runs(self) -> None:
        context, profiles = self.run_targets([result(MYTH)], track_swap=None)
        self.assertEqual(1, len(profiles))
        self.assertNotIn("levels", context["targets"])

    def test_the_level_run_repeats_the_myth_runs_recoveries(self) -> None:
        gear = GEAR + [
            {"itemId": 3, "slot": "Main Hand", "bonusIDs": [12854]},
            {"itemId": 4, "slot": "Off Hand", "bonusIDs": [12854]},
        ]
        upgrades = select_loadout_upgrades(
            None, {"all": {"all": [{"primary": 240983, "secondary": [240908]}]}}, "all", "RAID"
        )
        errors = [
            RuntimeError(TALENT_ERROR),
            RuntimeError("Player sv_0001 has an Off-Hand weapon equipped with a 2h weapon"),
            RuntimeError("invalid gem_id 240983"),
            result(MYTH),
            result(LEVELS),
        ]
        context, profiles = self.run_targets(errors, gear=gear, talents=["A", "B"], upgrades=upgrades)
        self.assertEqual(5, len(profiles))
        level_profile = profiles[4]
        self.assertIn("talents=B", level_profile)
        self.assertNotIn("talents=A", level_profile)
        self.assertNotIn("off_hand=", level_profile)
        self.assertNotIn("gem_id=", level_profile)
        self.assertIn("main_hand=,id=3,bonus_id=12846", level_profile)
        self.assertEqual({"hero", "champion"}, set(context["targets"]["levels"]))

    def test_talents_ignored_is_repeated_too(self) -> None:
        errors = [RuntimeError(TALENT_ERROR), result(MYTH), result(LEVELS)]
        _context, profiles = self.run_targets(errors, talents=["A"])
        self.assertNotIn("talents=", profiles[2])

    def test_a_failed_combined_run_retries_each_track_alone(self) -> None:
        hero_only = {"sv_0001": LEVELS["sv_0001"]}
        errors = [result(MYTH), RuntimeError("boom"), result(hero_only), RuntimeError("boom again")]
        context, profiles = self.run_targets(errors)
        self.assertEqual(4, len(profiles))
        self.assertIn("bonus_id=12846", profiles[2])
        self.assertIn("bonus_id=12838", profiles[3])
        self.assertEqual({"hero"}, set(context["targets"]["levels"]))

    def test_a_loadout_without_higher_track_ids_reuses_the_myth_run(self) -> None:
        gear = [{"itemId": 1, "slot": "Head", "bonusIDs": [12838]}, {"itemId": 2, "slot": "Neck"}]
        context, profiles = self.run_targets([result(MYTH)], gear=gear)
        self.assertEqual(1, len(profiles))
        same = {"statTargets": {"stats": {"critical_strike": 100.0, "haste": 200.0}}, "averageItemLevel": 317.0}
        self.assertEqual({"hero": same, "champion": same}, context["targets"]["levels"])

    def test_only_the_track_that_changes_is_simulated(self) -> None:
        gear = [{"itemId": 1, "slot": "Head", "bonusIDs": [12846]}]
        champion_only = {"sv_0001": LEVELS["sv_0002"]}
        context, profiles = self.run_targets([result(MYTH), result(champion_only)], gear=gear)
        self.assertEqual(2, len(profiles))
        self.assertIn("bonus_id=12838", profiles[1])
        self.assertNotIn("sv_0002", profiles[1])
        levels = context["targets"]["levels"]
        self.assertEqual({"critical_strike": 100.0, "haste": 200.0}, levels["hero"]["statTargets"]["stats"])
        self.assertEqual({"critical_strike": 80.0, "haste": 160.0}, levels["champion"]["statTargets"]["stats"])

    def test_a_swapped_item_drops_its_fixed_item_level(self) -> None:
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 334, "bonusIDs": [12854]}, {"itemId": 2, "slot": "Neck", "ilvl": 300}]
        _context, profiles = self.run_targets([result(MYTH), result(LEVELS)], gear=gear)
        self.assertIn("head=,id=1,ilevel=334,bonus_id=12854", profiles[0])
        self.assertIn("head=,id=1,bonus_id=12846", profiles[1])
        self.assertIn("neck=,id=2,ilevel=300", profiles[1])

    def test_an_unmapped_higher_track_id_stays_unswapped_and_is_counted(self) -> None:
        swap = TrackSwap(
            swap={"hero": {12854: 12846}, "champion": {12854: 12838}},
            item_levels={"myth": 334, "hero": 321, "champion": 308},
            unmapped={"hero": [12897], "champion": [12897]},
            track_of={12854: "myth", 12897: "myth"},
        )
        gear = GEAR + [{"itemId": 5, "slot": "Back", "bonusIDs": [12897]}]
        context, profiles = self.run_targets([result(MYTH), result(LEVELS)], gear=gear, track_swap=swap)
        self.assertIn("back=,id=5,bonus_id=12897", profiles[1])
        self.assertEqual(1, context["targets"]["targetMetadata"]["swapMisses"])
        self.assertEqual({"hero", "champion"}, set(context["targets"]["levels"]))

    def test_fewer_than_two_usable_stats_leaves_that_track_out(self) -> None:
        weak = {"sv_0001": {"ratings": {"crit": 90.0}}, "sv_0002": LEVELS["sv_0002"]}
        context, _profiles = self.run_targets([result(MYTH), result(weak)])
        self.assertEqual({"champion"}, set(context["targets"]["levels"]))

    def test_a_level_without_simc_item_levels_has_no_average(self) -> None:
        bare = {"sv_0001": {"ratings": {"crit": 1.0, "haste": 2.0}}, "sv_0002": {"ratings": {"crit": 1.0, "haste": 2.0}}}
        context, _profiles = self.run_targets([result(MYTH), result(bare)])
        self.assertNotIn("averageItemLevel", context["targets"]["levels"]["hero"])

    def test_the_wowhead_fallback_is_repeated_with_swapped_items(self) -> None:
        calls = []

        def fake_wowhead(items, *, primary):
            calls.append(items["HEAD"]["bonusIds"])
            return {"totals": {"crit": 900 - 10 * len(calls), "haste": 1200}, "slots": {}, "failures": []}

        with patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError("unsupported spec")), \
                redirect_stderr(io.StringIO()):
            context = reconstruct_target_context(
                SPEC_BY_KEY["PALADIN_HOLY"], "RAID", GEAR, "X",
                wowhead_reconstruct=fake_wowhead, track_swap=TRACK_SWAP,
            )
        self.assertEqual([[12854, 13847], [12846, 13847], [12838, 13847]], calls)
        levels = context["targets"]["levels"]
        self.assertEqual({"critical_strike": 880.0, "haste": 1200.0}, levels["hero"]["statTargets"]["stats"])
        self.assertEqual({"critical_strike": 870.0, "haste": 1200.0}, levels["champion"]["statTargets"]["stats"])


class TrackLevelBuildAllTests(unittest.TestCase):
    specs = {
        "DEATHKNIGHT_frost": {
            "gear": {"value": {"all": {"raid": GEAR}}, "source": "icyveins"},
            "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
        }
    }

    def build(self):
        with patch("tools.classcodex_targets.run_simc", side_effect=[result(MYTH), result(LEVELS)]), \
                redirect_stderr(io.StringIO()):
            return build_all(self.specs, Path("simc"), goals=("RAID",), track_swap=TRACK_SWAP)

    def test_build_all_passes_the_track_swap_through(self) -> None:
        data = self.build()
        targets = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["deathbringer"]["targets"]
        self.assertEqual({"hero", "champion"}, set(targets["levels"]))

    def test_the_coverage_report_shows_mapping_levels_and_contexts_with_levels(self) -> None:
        swap = TRACK_SWAP._replace(unmapped={"hero": [12897], "champion": [12897]})
        report = format_coverage_report(self.build(), swap)
        self.assertIn("track swap hero: 2 id(s) mapped, 1 unmapped (12897)", report)
        self.assertIn("track swap champion: 3 id(s) mapped, 1 unmapped (12897)", report)
        self.assertIn("6/6 item levels: myth 334, hero 321, champion 308", report)
        self.assertIn("contexts with levels: champion: 1, hero: 1 (of 1)", report)

    def test_the_coverage_report_says_when_there_is_no_track_swap(self) -> None:
        report = format_coverage_report({"profiles": {}})
        self.assertIn("track swap: not available", report)


if __name__ == "__main__":
    unittest.main()
