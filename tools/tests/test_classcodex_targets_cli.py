from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import classcodex_targets_cli
from tools.classcodex_fetch import FetchResult
from tools.classcodex_targets_cli import render_lua


class RenderLuaTests(unittest.TestCase):
    def test_wraps_the_data_as_ns_class_codex_targets(self) -> None:
        rendered = render_lua({"schemaVersion": 1, "profiles": {}})
        self.assertIn("ns.ClassCodexTargets = ", rendered)
        self.assertIn("Do not edit manually", rendered)


def spec_fields(export: str) -> dict:
    return {
        "gear": {"value": {"all": {"raid": [{"itemId": 1, "slot": "Head", "ilvl": 300}]}}},
        "talents": {"value": {"all": {"raid": [{"export": export}]}}},
    }


SPECS = {"DEATHKNIGHT_frost": spec_fields("DK"), "PALADIN_holy": spec_fields("HPAL")}
GOOD = ({"sv_0001": {"ratings": {"crit": 1.0, "haste": 2.0}}}, {})


def fake_run_simc(_binary, profile_text, **_kwargs):
    if 'paladin="' in profile_text:
        raise RuntimeError("Player sv_0001 is using an unsupported spec")
    return GOOD


class WowheadFallbackCliTests(unittest.TestCase):
    def test_an_unreachable_wowhead_only_skips_the_affected_combos(self) -> None:
        fetched = FetchResult(build_id="b1", published_at="2026-09-29", sources={})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), redirect_stdout(io.StringIO()), \
                patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched), \
                patch("tools.classcodex_targets_cli.build", return_value=SPECS), \
                patch("tools.classcodex_targets.run_simc", side_effect=fake_run_simc), \
                patch("tools.classcodex_targets_cli.reconstruct_loadout", side_effect=OSError("network down")) as wowhead:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            code = classcodex_targets_cli.main(["--simc-bin", "simc", "--out", str(out)])
            self.assertTrue(out.exists())
        self.assertEqual(0, code)
        wowhead.assert_called_once()  # only for the spec SimC cannot initialise
        self.assertIn("PALADIN_HOLY/RAID/all: wowhead fallback failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
