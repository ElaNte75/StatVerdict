from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.classcodex_weights import build_all_weights, build_weight_context, parse_scale_factors
from tools.live_benchmark_engine import SPEC_BY_KEY

FIXTURE = Path(__file__).parent / "fixtures" / "simc_scale_factor_report.json"


class ParseScaleFactorsTests(unittest.TestCase):
    def test_parses_the_documented_shape_fixture(self) -> None:
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))
        weights = parse_scale_factors(report)
        self.assertTrue(weights, "expected at least one actor's weights")
        for actor_weights in weights.values():
            for stat in ("crit", "haste", "mastery", "versatility"):
                self.assertIn(stat, actor_weights)
                self.assertIsInstance(actor_weights[stat], float)

    def test_raises_a_clear_error_when_scaling_data_is_absent(self) -> None:
        report = {"sim": {"players": [{"name": "sv_0001", "collected_data": {}}]}}
        with self.assertRaisesRegex(ValueError, "scaling"):
            parse_scale_factors(report)


class BuildWeightContextTests(unittest.TestCase):
    def test_returns_normalized_weights_from_a_scale_factor_run(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 330}]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        report = {"sim": {"players": [{"name": "sv_0001", "scaling": {"dps": {
            "crit_rating": 65.3, "haste_rating": 49.2, "mastery_rating": 45.5, "versatility_rating": 34.5,
        }}}]}}
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            weights = build_weight_context(spec, gear, talents, "all", "raid", Path("simc"))
        self.assertAlmostEqual(1.0, weights["crit"])
        self.assertLess(weights["versatility"], weights["crit"])

    def test_returns_none_without_a_talent_export(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 330}]
        self.assertIsNone(build_weight_context(spec, gear, {}, "all", "raid", Path("simc")))

    def test_returns_none_when_gear_list_is_empty(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        self.assertIsNone(build_weight_context(spec, [], talents, "all", "raid", Path("simc")))

    def test_returns_none_when_simc_raises(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 330}]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        with patch("tools.classcodex_weights.run_simc", side_effect=RuntimeError("boom")):
            self.assertIsNone(build_weight_context(spec, gear, talents, "all", "raid", Path("simc")))

    def test_returns_none_when_scaling_data_is_missing_for_the_actor(self) -> None:
        spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
        gear = [{"itemId": 1, "slot": "Head", "ilvl": 330}]
        talents = {"all": {"raid": [{"export": "X", "recommended": True}]}}
        report = {"sim": {"players": []}}
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            self.assertIsNone(build_weight_context(spec, gear, talents, "all", "raid", Path("simc")))


class BuildAllWeightsTests(unittest.TestCase):
    def test_builds_one_profile_per_spec_with_a_context_per_goal_and_hero_talent(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"mplus": [{"itemId": 1, "slot": "Head", "ilvl": 330}], "raid": [{"itemId": 2, "slot": "Head", "ilvl": 330}]}}, "source": "ugg"},
                "talents": {"value": {"all": {"mplus": [{"export": "M", "recommended": True}], "raid": [{"export": "R", "recommended": True}]}}, "source": "ugg"},
            }
        }
        report = {"sim": {"players": [{"name": "sv_0001", "scaling": {"dps": {
            "crit_rating": 65.3, "haste_rating": 49.2, "mastery_rating": 45.5, "versatility_rating": 34.5,
        }}}]}}
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            data = build_all_weights(specs, Path("simc"), goals=("MYTHIC_PLUS", "RAID"))

        weights = data["profiles"]["DEATHKNIGHT_frost"]["MYTHIC_PLUS"]["all"]
        self.assertAlmostEqual(1.0, weights["crit"])
        self.assertNotIn("PVP", data["profiles"]["DEATHKNIGHT_frost"])  # no PVP data anywhere in this fixture

    def test_skips_a_spec_key_not_in_the_catalog(self) -> None:
        specs = {"NOTASPEC_madeup": {"gear": {"value": {}, "source": "ugg"}}}
        data = build_all_weights(specs, Path("simc"))
        self.assertEqual({}, data["profiles"])


if __name__ == "__main__":
    unittest.main()
