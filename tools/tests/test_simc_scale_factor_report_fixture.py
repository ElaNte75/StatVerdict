# tools/tests/test_simc_scale_factor_report_fixture.py
from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "simc_scale_factor_report.json"


class ScaleFactorFixtureShapeTests(unittest.TestCase):
    def test_fixture_exists_and_is_valid_json(self) -> None:
        self.assertTrue(FIXTURE.exists(), f"missing {FIXTURE} -- see Task 8's ruling in the plan/ledger")
        report = json.loads(FIXTURE.read_text(encoding="utf-8"))
        sim = report.get("sim", report)
        players = sim.get("players") or sim.get("player") or []
        self.assertTrue(players, "fixture has no player entries")
        # This assertion documents the real key this plan's parser (Task 9)
        # must read scale factors from -- update it (and Task 9's parser) to
        # match whatever key a real captured report actually uses, once one
        # is available (this fixture is documented knowledge, not a live
        # capture -- see simc_scale_factor_report.README.md).
        self.assertIn("scaling", players[0])


if __name__ == "__main__":
    unittest.main()
