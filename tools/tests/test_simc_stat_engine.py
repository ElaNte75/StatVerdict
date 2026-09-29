from __future__ import annotations

import unittest

from tools.live_benchmark_engine import SPEC_BY_KEY
from tools.simc_stat_engine import parse_report, render_item, render_player, render_profiles


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


if __name__ == "__main__":
    unittest.main()
