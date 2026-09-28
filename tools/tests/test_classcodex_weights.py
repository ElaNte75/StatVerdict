from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.classcodex_weights import parse_scale_factors

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


if __name__ == "__main__":
    unittest.main()
