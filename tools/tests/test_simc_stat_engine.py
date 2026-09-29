from __future__ import annotations

import unittest
from pathlib import Path

from tools.live_benchmark_engine import SPEC_BY_KEY
from tools.simc_stat_engine import (
    parse_report,
    render_item,
    render_player,
    render_profiles,
    run_simc_with_recovery,
)


def sim_option_lines(profile_text: str) -> list[str]:
    """The global sim-option lines of a rendered profile, i.e. everything
    before the first actor declaration (`deathknight="sv_0001"`)."""
    lines = []
    for line in profile_text.splitlines():
        if '="' in line:
            break
        if line:
            lines.append(line)
    return lines


class SimulationCraftStatEngineTests(unittest.TestCase):
    def test_render_item_preserves_exact_variant(self) -> None:
        line = render_item(
            "HEAD",
            {
                "itemId": 271474,
                "itemLevel": 321,
                "bonusIds": [13695, 13692],
                "gemIds": [240894],
                "enchantIds": [7991],
            },
        )
        self.assertEqual(
            "head=,id=271474,ilevel=321,bonus_id=13695/13692,"
            "gem_id=240894,enchant_id=7991",
            line,
        )

    def test_render_blood_profile_includes_run_talents_and_role(self) -> None:
        profile = render_player(
            actor_name="sv_0001",
            class_name="death-knight",
            spec_name="Blood",
            role="tank",
            race="Night Elf",
            talent_loadout="CoPAAAA",
            items={"HEAD": {"itemId": 271474, "itemLevel": 321}},
        )
        self.assertIn('deathknight="sv_0001"', profile)
        self.assertIn("race=night_elf", profile)
        self.assertIn("spec=blood", profile)
        self.assertIn("talents=CoPAAAA", profile)
        self.assertIn("role=tank", profile)

    def test_render_profiles_defaults_are_the_paper_doll_settings(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        record = {"runTalentLoadout": "X", "items": {"HEAD": {"itemId": 1}}}
        text, _actors = render_profiles(spec, [record])
        header = sim_option_lines(text)
        self.assertEqual(
            [
                "iterations=1",
                "max_time=1",
                "fixed_time=1",
                "calculate_scale_factors=0",
                "report_details=0",
                "allow_experimental_specializations=1",
            ],
            header,
        )

    def test_render_profiles_accepts_scale_factor_settings(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        record = {"runTalentLoadout": "X", "items": {"HEAD": {"itemId": 1}}}
        text, _actors = render_profiles(
            spec,
            [record],
            iterations=10000,
            max_time=300,
            calculate_scale_factors=True,
            scale_only=("crit_rating", "haste_rating"),
            target_error=0.1,
        )
        header = sim_option_lines(text)
        self.assertIn("iterations=10000", header)
        self.assertIn("max_time=300", header)
        self.assertIn("calculate_scale_factors=1", header)
        self.assertIn("scale_only=crit_rating,haste_rating", header)
        self.assertIn("target_error=0.1", header)

    def test_parse_json2_paper_doll_stats(self) -> None:
        report = {
            "sim": {
                "players": [
                    {
                        "name": "sv_0001",
                        "collected_data": {
                            "buffed_stats": {
                                "attribute": {"strength": 4200, "stamina": 22000},
                                "resources": {"health": 1500000},
                                "stats": {
                                    "crit_rating": 501,
                                    "crit_pct": 0.12,
                                    "haste_rating": 602,
                                    "haste_pct": 0.15,
                                    "mastery_rating": 703,
                                    "mastery_pct": 0.34,
                                    "versatility_rating": 804,
                                    "versatility_pct": 0.10,
                                    "armor": 18000,
                                },
                            }
                        },
                    }
                ]
            }
        }
        parsed = parse_report(report)["sv_0001"]
        self.assertEqual(602, parsed["ratings"]["haste"])
        self.assertEqual(0.34, parsed["percentages"]["mastery"])
        self.assertEqual(1500000, parsed["health"])


class StatSheetOnlyTests(unittest.TestCase):
    def test_default_actions_line_only_when_requested(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        record = {"runTalentLoadout": "X", "items": {"HEAD": {"itemId": 1}}}
        plain, _ = render_profiles(spec, [record])
        sheet, _ = render_profiles(spec, [record], stat_sheet_only=True)
        self.assertNotIn("default_actions=0", plain)
        self.assertIn("default_actions=0", sheet.splitlines())
        # It belongs to the player block, not the global sim options.
        self.assertNotIn("default_actions=0", sim_option_lines(sheet))

    def test_render_player_still_requires_talents_by_default(self) -> None:
        with self.assertRaises(ValueError):
            render_player(actor_name="a", class_name="mage", spec_name="Fire", role="dps", race="human",
                          talent_loadout="", items={})

    def test_render_player_omits_the_talents_line_when_talents_are_optional(self) -> None:
        text = render_player(actor_name="a", class_name="mage", spec_name="Fire", role="dps", race="human",
                             talent_loadout="", items={}, talents_optional=True)
        self.assertNotIn("talents=", text)
        # A given loadout is still rendered.
        text = render_player(actor_name="a", class_name="mage", spec_name="Fire", role="dps", race="human",
                             talent_loadout="T", items={}, talents_optional=True)
        self.assertIn("talents=T", text)

    def test_render_profiles_passes_talents_optional_through(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        text, _ = render_profiles(spec, [{"items": {"HEAD": {"itemId": 1}}}], talents_optional=True)
        self.assertNotIn("talents=", text)


WEAPON_ITEMS = {"HEAD": {"itemId": 1}, "MAIN_HAND": {"itemId": 2}, "OFF_HAND": {"itemId": 3}}
OFFHAND_2H_ERROR = "Player sv_0001 has an Off-Hand weapon equipped with a 2h weapon"
BOTH_WEAPONS_ERROR = "Player sv_0001 has both a 1-hand and 2-hand weapon equipped at once"
GOOD_STATS = {"sv_0001": {"ratings": {"crit": 1.0, "haste": 2.0}}}


class FakeSimc:
    """Records the profile of every call and raises/returns in order."""

    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.profiles: list[str] = []
        self.kwargs: list[dict] = []

    def __call__(self, _binary, profile_text, **kwargs):
        self.profiles.append(profile_text)
        self.kwargs.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RunSimcWithRecoveryTests(unittest.TestCase):
    spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]

    def record(self) -> dict:
        return {"race": "human", "runTalentLoadout": "X", "items": dict(WEAPON_ITEMS), "level": 90}

    def run_with(self, fake: FakeSimc):
        return run_simc_with_recovery(
            Path("simc"), self.spec, self.record(),
            render_kwargs={"stat_sheet_only": True}, run_kwargs={"timeout_seconds": 5}, run_simc_fn=fake,
        )

    def test_no_recovery_when_the_first_run_succeeds(self) -> None:
        fake = FakeSimc((GOOD_STATS, {"r": 1}))
        stats, report, recovery, actor = self.run_with(fake)
        self.assertEqual(GOOD_STATS, stats)
        self.assertEqual({"r": 1}, report)
        self.assertEqual([], recovery)
        self.assertEqual("sv_0001", actor)
        self.assertIn("off_hand=", fake.profiles[0])
        self.assertIn("default_actions=0", fake.profiles[0])
        self.assertEqual({"timeout_seconds": 5}, fake.kwargs[0])

    def test_drops_the_off_hand_on_a_two_hander_conflict(self) -> None:
        fake = FakeSimc(RuntimeError(OFFHAND_2H_ERROR), (GOOD_STATS, {}))
        _stats, _report, recovery, _actor = self.run_with(fake)
        self.assertEqual(["dropped OFF_HAND"], recovery)
        self.assertNotIn("off_hand=", fake.profiles[1])
        self.assertIn("main_hand=", fake.profiles[1])

    def test_then_drops_the_main_hand_when_the_conflict_persists(self) -> None:
        fake = FakeSimc(RuntimeError(BOTH_WEAPONS_ERROR), RuntimeError(BOTH_WEAPONS_ERROR), (GOOD_STATS, {}))
        _stats, _report, recovery, _actor = self.run_with(fake)
        self.assertEqual(["dropped OFF_HAND", "dropped MAIN_HAND"], recovery)
        self.assertNotIn("off_hand=", fake.profiles[2])
        self.assertNotIn("main_hand=", fake.profiles[2])
        self.assertIn("head=", fake.profiles[2])

    def test_never_more_than_two_retries(self) -> None:
        fake = FakeSimc(*(RuntimeError(BOTH_WEAPONS_ERROR) for _ in range(4)))
        with self.assertRaisesRegex(RuntimeError, "1-hand and 2-hand"):
            self.run_with(fake)
        self.assertEqual(3, len(fake.profiles))

    def test_other_errors_are_not_retried(self) -> None:
        fake = FakeSimc(RuntimeError("could not find spell data"), (GOOD_STATS, {}))
        with self.assertRaisesRegex(RuntimeError, "spell data"):
            self.run_with(fake)
        self.assertEqual(1, len(fake.profiles))

    def test_a_different_error_after_a_weapon_retry_is_raised(self) -> None:
        fake = FakeSimc(RuntimeError(OFFHAND_2H_ERROR), RuntimeError("boom"))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            self.run_with(fake)
        self.assertEqual(2, len(fake.profiles))

    def test_the_callers_record_is_not_mutated(self) -> None:
        record = self.record()
        fake = FakeSimc(RuntimeError(OFFHAND_2H_ERROR), (GOOD_STATS, {}))
        run_simc_with_recovery(Path("simc"), self.spec, record, render_kwargs={}, run_kwargs={}, run_simc_fn=fake)
        self.assertIn("OFF_HAND", record["items"])


if __name__ == "__main__":
    unittest.main()
