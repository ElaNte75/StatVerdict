# tools/tests/test_simc_scale_factor_report_fixture.py
from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "simc_scale_factor_report.json"


class ScaleFactorFixtureShapeTests(unittest.TestCase):
    def test_fixture_exists_and_is_valid_json(self) -> None:
        self.assertTrue(FIXTURE.exists(), f"missing {FIXTURE}")
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))
        players = report["sim"]["players"]
        self.assertTrue(players, "fixture has no player entries")

    def test_fixture_uses_the_shape_simc_source_writes(self) -> None:
        # Pinned to SimC's own report writer (engine/report/json/report_json.cpp
        # + util::stat_type_abbrev, midnight branch) -- see
        # simc_scale_factor_report.README.md. If a real captured report ever
        # disagrees, update this test, the fixture and parse_scale_factors together.
        player = json.loads(FIXTURE.read_text(encoding="utf-8"))["sim"]["players"][0]
        self.assertIn("scale_factors", player)
        self.assertIn("dps", player["scale_factors_all"])
        self.assertIn("hps", player["scale_factors_all"])
        for abbrev in ("Crit", "Haste", "Mastery", "Vers"):
            self.assertIn(abbrev, player["scale_factors_all"]["dps"])
        self.assertNotIn("scaling", player)  # the old, wrong guess


if __name__ == "__main__":
    unittest.main()
