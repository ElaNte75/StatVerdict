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
from tools.classcodex_targets_cli import render_lua


class RenderLuaTests(unittest.TestCase):
    def test_wraps_the_data_as_ns_class_codex_targets(self) -> None:
        rendered = render_lua({"schemaVersion": 1, "profiles": {}})
        self.assertIn("ns.ClassCodexTargets = ", rendered)
        self.assertIn("Do not edit manually", rendered)

    def test_guide_targets_and_bis_gems_enchants_round_trip_through_lua(self) -> None:
        context = {
            "targets": {
                "statTargets": {"context": "RAID", "source": "x", "stats": {"haste": 1.0, "mastery": 2.0}},
                "guideTargets": {"top20": {"critical_strike": 1413.0, "haste": 788.0}},
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
        self.assertEqual(1413.0, loaded["targets"]["guideTargets"]["top20"]["critical_strike"])
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
                patch("tools.classcodex_targets_cli.load_track_swap", return_value=None), \
                patch("tools.classcodex_targets.run_simc", side_effect=fake_run_simc), \
                patch("tools.classcodex_targets_cli.reconstruct_loadout", side_effect=OSError("network down")) as wowhead:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            code = classcodex_targets_cli.main(["--simc-bin", "simc", "--out", str(out), "--allow-missing-track-levels"])
            self.assertTrue(out.exists())
        self.assertEqual(0, code)
        wowhead.assert_called_once()  # only for the spec SimC cannot initialise
        self.assertIn("PALADIN_HOLY/RAID/all: wowhead fallback failed", stderr.getvalue())
        # The CI log carries the ours-vs-u.gg rating sanity check.
        self.assertIn("DEATHKNIGHT_FROST/RAID/all: ours 3 vs u.gg top50 n/a", stderr.getvalue())


class TrackSwapCliTests(unittest.TestCase):
    specs = {
        "DEATHKNIGHT_frost": {
            "gear": {"value": {"all": {"raid": [{"itemId": 1, "slot": "Head", "bonusIDs": [12854]}]}}},
            "talents": {"value": {"all": {"raid": [{"export": "DK"}]}}},
        }
    }

    def run_cli(self, track_swap):
        fetched = FetchResult(build_id="b1", published_at="2026-09-29", sources={})
        levels = {
            "sv_0001": {"ratings": {"crit": 0.9, "haste": 1.8}, "item_levels": {"head": 321.0}},
            "sv_0002": {"ratings": {"crit": 0.8, "haste": 1.6}, "item_levels": {"head": 308.0}},
        }
        runs = [GOOD, (levels, {})]
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), redirect_stdout(io.StringIO()), \
                patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched), \
                patch("tools.classcodex_targets_cli.build", return_value=self.specs), \
                patch("tools.classcodex_targets_cli.load_track_swap", return_value=track_swap) as loader, \
                patch("tools.classcodex_targets.run_simc", side_effect=lambda *_a, **_k: runs.pop(0)):
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            extra = ["--allow-missing-track-levels"] if track_swap is None else []
            code = classcodex_targets_cli.main(["--simc-bin", "simc", "--out", str(out), *extra])
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
                patch("tools.classcodex_targets.run_simc") as simc:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            out.write_text("OLD GOOD DATA", encoding="utf-8")
            code = classcodex_targets_cli.main(["--simc-bin", "simc", "--out", str(out)])
            kept = out.read_text(encoding="utf-8")
        self.assertEqual(1, code)
        self.assertEqual("OLD GOOD DATA", kept)
        simc.assert_not_called()  # it stops before the long SimC run
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
        self.assertEqual({"critical_strike": 0.9, "haste": 1.8}, targets["levels"]["hero"]["statTargets"]["stats"])
        self.assertEqual(308.0, targets["levels"]["champion"]["averageItemLevel"])
        self.assertIn("track swap hero: 1 id(s) mapped, 0 unmapped", log)

    def test_without_the_upgrade_tables_the_file_has_no_track_data(self) -> None:
        data, log = self.run_cli(None)
        self.assertNotIn("trackSwap", data)
        self.assertNotIn("trackItemLevels", data)
        self.assertIn("track swap: not available", log)


if __name__ == "__main__":
    unittest.main()
