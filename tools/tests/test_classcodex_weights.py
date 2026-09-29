from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.classcodex_weights import (
    SCALE_FACTOR_TIMEOUT_SECONDS,
    build_all_weights,
    build_weight_context,
    parse_scale_factors,
    scale_metric_for_role,
)
from tools.live_benchmark_engine import SPEC_BY_KEY
from tools.tests.test_simc_stat_engine import sim_option_lines

FIXTURE = Path(__file__).parent / "fixtures" / "simc_scale_factor_report.json"


def scale_report(metric: str = "dps", **by_abbrev: float) -> dict:
    """A json2 report in the shape SimC really writes (see the fixture README)."""
    values = {"Crit": 65.3, "Haste": 49.2, "Mastery": 45.5, "Vers": 34.5}
    values.update(by_abbrev)
    return {"sim": {"players": [{"name": "sv_0001", "scale_factors": dict(values), "scale_factors_all": {metric: dict(values)}}]}}


class ParseScaleFactorsTests(unittest.TestCase):
    def test_parses_the_fixture_into_canonical_stat_names(self) -> None:
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))
        weights = parse_scale_factors(report)
        self.assertEqual(
            {"critical_strike": 0.653, "haste": 0.492, "mastery": 0.455, "versatility": 0.345},
            weights["sv_0001"],
        )

    def test_reads_the_requested_metric(self) -> None:
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))
        weights = parse_scale_factors(report, "hps")
        self.assertEqual(0.0, weights["sv_0001"]["critical_strike"])

    def test_ignores_non_secondary_stats(self) -> None:
        weights = parse_scale_factors(scale_report(Str=2.1, Agi=0.0))
        self.assertEqual({"critical_strike", "haste", "mastery", "versatility"}, set(weights["sv_0001"]))

    def test_raises_a_clear_error_when_scale_factors_are_absent(self) -> None:
        report = {"sim": {"players": [{"name": "sv_0001", "collected_data": {}}]}}
        with self.assertRaisesRegex(ValueError, "scale_factors_all"):
            parse_scale_factors(report)

    def test_raises_when_the_requested_metric_is_absent(self) -> None:
        with self.assertRaisesRegex(ValueError, "hps"):
            parse_scale_factors(scale_report("dps"), "hps")

    def test_raises_when_a_secondary_stat_is_missing(self) -> None:
        report = scale_report()
        del report["sim"]["players"][0]["scale_factors_all"]["dps"]["Vers"]
        with self.assertRaisesRegex(ValueError, "versatility"):
            parse_scale_factors(report)


class ScaleMetricForRoleTests(unittest.TestCase):
    def test_healers_use_hps_everyone_else_dps(self) -> None:
        self.assertEqual("hps", scale_metric_for_role("healer"))
        self.assertEqual("dps", scale_metric_for_role("dps"))
        self.assertEqual("dps", scale_metric_for_role("tank"))


GEAR = [{"itemId": 1, "slot": "Head", "ilvl": 330}]
TALENTS = {"all": {"raid": [{"export": "X", "recommended": True}]}}


class BuildWeightContextTests(unittest.TestCase):
    def test_returns_normalized_weights_from_a_scale_factor_run(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        with patch("tools.classcodex_weights.run_simc", return_value=({}, scale_report())):
            weights = build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc"))
        self.assertAlmostEqual(1.0, weights["critical_strike"])
        self.assertLess(weights["versatility"], weights["critical_strike"])

    def test_runs_simc_with_real_scale_factor_settings(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        with patch("tools.classcodex_weights.run_simc", return_value=({}, scale_report())) as mock_run:
            build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc"))
        profile_text = mock_run.call_args.args[1]
        header = sim_option_lines(profile_text)
        self.assertIn("calculate_scale_factors=1", header)
        self.assertIn("iterations=10000", header)
        self.assertIn("target_error=0.1", header)
        self.assertIn("max_time=300", header)
        self.assertIn("scale_only=crit_rating,haste_rating,mastery_rating,versatility_rating", header)
        self.assertEqual(SCALE_FACTOR_TIMEOUT_SECONDS, mock_run.call_args.kwargs["timeout_seconds"])
        self.assertGreaterEqual(mock_run.call_args.kwargs["threads"], 1)

    def test_healers_are_weighted_by_hps(self) -> None:
        spec = SPEC_BY_KEY["PRIEST_HOLY"]
        report = scale_report("hps", Crit=10.0, Haste=20.0, Mastery=5.0, Vers=8.0)
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            weights = build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc"))
        self.assertAlmostEqual(1.0, weights["haste"])

    def test_a_healer_report_without_hps_is_skipped(self) -> None:
        spec = SPEC_BY_KEY["PRIEST_HOLY"]
        with patch("tools.classcodex_weights.run_simc", return_value=({}, scale_report("dps"))):
            self.assertIsNone(build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc")))

    def test_returns_none_when_any_weight_is_negative(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        with patch("tools.classcodex_weights.run_simc", return_value=({}, scale_report(Vers=-0.4))):
            self.assertIsNone(build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc")))

    def test_returns_none_when_no_weight_is_positive(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        report = scale_report(Crit=0.0, Haste=0.0, Mastery=0.0, Vers=0.0)
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            self.assertIsNone(build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc")))

    def test_returns_none_without_a_talent_export(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        self.assertIsNone(build_weight_context(spec, GEAR, {}, "all", "raid", Path("simc")))

    def test_returns_none_when_gear_list_is_empty(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        self.assertIsNone(build_weight_context(spec, [], TALENTS, "all", "raid", Path("simc")))

    def test_returns_none_when_simc_raises(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        with patch("tools.classcodex_weights.run_simc", side_effect=RuntimeError("boom")):
            self.assertIsNone(build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc")))

    def test_returns_none_when_scaling_data_is_missing_for_the_actor(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        report = {"sim": {"players": []}}
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            self.assertIsNone(build_weight_context(spec, GEAR, TALENTS, "all", "raid", Path("simc")))


class BuildAllWeightsTests(unittest.TestCase):
    def test_builds_one_profile_per_spec_with_a_context_per_goal_and_hero_talent(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"mplus": [{"itemId": 1, "slot": "Head", "ilvl": 330}], "raid": [{"itemId": 2, "slot": "Head", "ilvl": 330}]}}, "source": "ugg"},
                "talents": {"value": {"all": {"mplus": [{"export": "M", "recommended": True}], "raid": [{"export": "R", "recommended": True}]}}, "source": "ugg"},
            }
        }
        with patch("tools.classcodex_weights.run_simc", return_value=({}, scale_report())):
            data = build_all_weights(specs, Path("simc"), goals=("MYTHIC_PLUS", "RAID"))

        # Same key casing and nesting as the targets file:
        # profiles[specKey].goals[goal].heroTalents[heroTalentKey].
        profile = data["profiles"]["DEATHKNIGHT_FROST"]
        self.assertEqual("DEATHKNIGHT_FROST", profile["specKey"])
        weights = profile["goals"]["MYTHIC_PLUS"]["heroTalents"]["all"]
        self.assertAlmostEqual(1.0, weights["critical_strike"])
        self.assertNotIn("PVP", profile["goals"])  # no PVP data anywhere in this fixture

    def test_skips_a_spec_key_not_in_the_catalog(self) -> None:
        specs = {"NOTASPEC_madeup": {"gear": {"value": {}, "source": "ugg"}}}
        data = build_all_weights(specs, Path("simc"))
        self.assertEqual({}, data["profiles"])


if __name__ == "__main__":
    unittest.main()
