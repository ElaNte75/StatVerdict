from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import classcodex_targets_cli
from tools.classcodex_fetch import FetchResult
from tools.classcodex_lua_sandbox import run_addon_namespace
from tools.classcodex_targets import load_spec_base_stats
from tools.classcodex_targets_cli import render_lua
from tools.tests.wowhead_fakes import fake_wowhead


class RenderLuaTests(unittest.TestCase):
    def test_wraps_the_data_as_ns_class_codex_targets(self) -> None:
        rendered = render_lua({"schemaVersion": 1, "profiles": {}})
        self.assertIn("ns.ClassCodexTargets = ", rendered)
        self.assertIn("Do not edit manually", rendered)

    def test_tier_levels_and_bis_gems_enchants_round_trip_through_lua(self) -> None:
        context = {
            "targets": {
                "statTargets": {"context": "RAID", "source": "x", "stats": {"haste": 1.0, "mastery": 2.0}},
                "levels": {"hero": {"statTargets": {"stats": {"critical_strike": 1413.0, "haste": 788.0}}}},
                "targetMetadata": {"gemCount": 1, "enchantCount": 1},
            },
            "bis": {
                "label": "ClassCodex BiS",
                "gems": {"primary": 240983, "secondary": 240908},
                "slots": [
                    {
                        "slot": "Head",
                        "item": {
                            "item_id": 1,
                            "bonus_ids": [7],
                            "enchant": {"id": 8017, "item_id": 243981, "spell_id": 1236001},
                        },
                    }
                ],
            },
        }
        data = {"profiles": {"DEATHKNIGHT_FROST": {"goals": {"RAID": {"heroTalents": {"all": context}}}}}}
        namespace = run_addon_namespace(render_lua(data), "t.lua", addon_name="StatVerdict")
        loaded = namespace["ClassCodexTargets"]["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["all"]
        self.assertEqual(1413.0, loaded["targets"]["levels"]["hero"]["statTargets"]["stats"]["critical_strike"])
        item = loaded["bis"]["slots"][0]["item"]
        self.assertEqual({"primary": 240983, "secondary": 240908}, loaded["bis"]["gems"])
        self.assertNotIn("gem_ids", item)
        self.assertEqual({"id": 8017, "item_id": 243981, "spell_id": 1236001}, item["enchant"])


def spec_fields(export: str) -> dict:
    return {
        "gear": {"value": {"all": {"raid": [{"itemId": 1, "slot": "Head", "ilvl": 300}]}}},
        "talents": {"value": {"all": {"raid": [{"export": export}]}}},
    }


SPECS = {"DEATHKNIGHT_frost": spec_fields("DK"), "PALADIN_holy": spec_fields("HPAL")}


class WowheadCliTests(unittest.TestCase):
    def test_an_unreachable_wowhead_skips_the_combos_and_the_run_is_reported(self) -> None:
        fetched = FetchResult(build_id="b1", published_at="2026-09-29", sources={})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), redirect_stdout(io.StringIO()),                 patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched),                 patch("tools.classcodex_targets_cli.build", return_value=SPECS),                 patch("tools.classcodex_targets_cli.load_track_swap", return_value=None),                 patch("tools.classcodex_targets_cli.reconstruct_loadout", side_effect=OSError("network down")):
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            code = classcodex_targets_cli.main(["--out", str(out), "--allow-missing-track-levels"])
            self.assertFalse(out.exists())  # nothing came out: the file is not written
        self.assertEqual(1, code)
        self.assertIn("PALADIN_HOLY/RAID/all: Wowhead lookup failed", stderr.getvalue())
        self.assertIn("Refusing to write", stderr.getvalue())

    def test_a_good_run_writes_the_file_and_the_log_carries_the_checks(self) -> None:
        fetched = FetchResult(build_id="20261014113733-abc-def", published_at="2026-10-14", sources={})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), redirect_stdout(io.StringIO()),                 patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched),                 patch("tools.classcodex_targets_cli.build", return_value=SPECS),                 patch("tools.classcodex_targets_cli.load_track_swap", return_value=None),                 patch("tools.classcodex_targets_cli.reconstruct_loadout", side_effect=fake_wowhead()):
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            report = Path(tmp) / "carry.txt"
            code = classcodex_targets_cli.main(["--out", str(out), "--allow-missing-track-levels", "--carry-report", str(report)])
            self.assertTrue(out.exists())
            self.assertIn("nothing needed", report.read_text(encoding="utf-8"))
        self.assertEqual(0, code)
        self.assertIn("Tier targets sanity", stderr.getvalue())
        self.assertIn("Carry-over", stderr.getvalue())


class TrackSwapCliTests(unittest.TestCase):
    specs = {
        "DEATHKNIGHT_frost": {
            "gear": {"value": {"all": {"raid": [{"itemId": 1, "slot": "Head", "bonusIDs": [12854]}]}}},
            "talents": {"value": {"all": {"raid": [{"export": "DK"}]}}},
        }
    }

    def run_cli(self, track_swap):
        fetched = FetchResult(build_id="b1", published_at="2026-09-29", sources={})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), redirect_stdout(io.StringIO()), \
                patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched), \
                patch("tools.classcodex_targets_cli.build", return_value=self.specs), \
                patch("tools.classcodex_targets_cli.load_track_swap", return_value=track_swap) as loader, \
                patch("tools.classcodex_targets_cli.reconstruct_loadout", side_effect=fake_wowhead()):
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            extra = ["--allow-missing-track-levels"] if track_swap is None else []
            code = classcodex_targets_cli.main(["--out", str(out), *extra])
            namespace = run_addon_namespace(out.read_text(encoding="utf-8"), "t.lua", addon_name="StatVerdict")
        self.assertEqual(0, code)
        loader.assert_called_once_with(self.specs)
        return namespace["ClassCodexTargets"], stderr.getvalue()

    def test_without_the_track_tables_nothing_is_written_and_the_old_file_stays(self) -> None:
        fetched = FetchResult(build_id="b1", published_at="2026-09-29", sources={})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), redirect_stdout(io.StringIO()), \
                patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched), \
                patch("tools.classcodex_targets_cli.build", return_value=self.specs), \
                patch("tools.classcodex_targets_cli.load_track_swap", return_value=None), \
                patch("tools.classcodex_targets_cli.reconstruct_loadout") as wowhead:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            out.write_text("OLD GOOD DATA", encoding="utf-8")
            code = classcodex_targets_cli.main(["--out", str(out)])
            kept = out.read_text(encoding="utf-8")
        self.assertEqual(1, code)
        self.assertEqual("OLD GOOD DATA", kept)
        wowhead.assert_not_called()  # it stops before the long lookup run
        self.assertIn("Refusing to write", stderr.getvalue())

    def test_the_file_root_carries_track_swap_and_item_levels(self) -> None:
        from tools.upgrade_tracks import TrackSwap

        swap = TrackSwap(
            {"hero": {12854: 12846}, "champion": {12854: 12838}},
            {"myth": 334, "hero": 321, "champion": 308},
            {"hero": [], "champion": []},
            {12854: "myth"},
            {"myth": 12854, "hero": 12846, "champion": 12838},
        )
        data, log = self.run_cli(swap)
        self.assertEqual({"hero": {12854: 12846}, "champion": {12854: 12838}}, data["trackSwap"])
        self.assertEqual({"myth": 334, "hero": 321, "champion": 308}, data["trackItemLevels"])
        self.assertEqual({"myth": 12854, "hero": 12846, "champion": 12838}, data["trackTop"])
        targets = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["all"]["targets"]
        base = load_spec_base_stats()["DEATHKNIGHT_FROST"]
        hero = targets["levels"]["hero"]["statTargets"]["stats"]
        self.assertEqual(100.0 + base["critical_strike"], hero["critical_strike"])  # the pieces' totals plus the base rating
        self.assertEqual(321.0, targets["levels"]["hero"]["averageItemLevel"])
        self.assertEqual(308.0, targets["levels"]["champion"]["averageItemLevel"])
        self.assertIn("track swap hero: 1 id(s) mapped, 0 unmapped", log)

    def test_without_the_upgrade_tables_the_file_has_no_track_data(self) -> None:
        data, log = self.run_cli(None)
        self.assertNotIn("trackSwap", data)
        self.assertNotIn("trackItemLevels", data)
        self.assertIn("track swap: not available", log)


if __name__ == "__main__":
    unittest.main()
