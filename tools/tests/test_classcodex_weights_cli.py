from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tools.classcodex_targets import SkipRecord
from tools.classcodex_weights_cli import (
    MAX_FILE_BYTES,
    filter_specs,
    main,
    merge_partials,
    parse_spec_filter,
    render_lua,
    write_addon_file,
    write_partial,
)
from tools.spec_catalog import SPEC_BY_KEY


class RenderLuaTests(unittest.TestCase):
    def test_wraps_the_data_as_ns_class_codex_weights(self) -> None:
        rendered = render_lua({"schemaVersion": 1, "profiles": {}})
        self.assertIn("ns.ClassCodexWeights = ", rendered)
        self.assertIn("Do not edit manually", rendered)


class WriteAddonFileTests(unittest.TestCase):
    def test_writes_the_file_within_the_two_megabyte_budget(self) -> None:
        data = {
            "schemaVersion": 1,
            "profiles": {
                "DEATHKNIGHT_FROST": {
                    "specKey": "DEATHKNIGHT_FROST",
                    "goals": {"MYTHIC_PLUS": {"heroTalents": {"deathbringer": {"critical_strike": 1.0}}}},
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out" / "SV_ClassCodexWeights.lua"
            size = write_addon_file(data, path)
            self.assertEqual(size, path.stat().st_size)
            self.assertLess(size, MAX_FILE_BYTES)

    def test_raises_and_does_not_write_when_over_the_size_budget(self) -> None:
        oversized = {"schemaVersion": 1, "profiles": {"a": "x" * (MAX_FILE_BYTES + 1)}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.lua"
            with self.assertRaises(ValueError):
                write_addon_file(oversized, path)
            self.assertFalse(path.exists())


def partial(build_id: str, spec_keys: list[str], skips: list[dict] | None = None) -> dict:
    return {
        "schemaVersion": 1,
        "buildId": build_id,
        "publishedAt": "2026-09-28",
        "profiles": {
            key: {"specKey": key, "goals": {"RAID": {"heroTalents": {"h": {"critical_strike": 1.0}}}}} for key in spec_keys
        },
        "skips": skips or [],
    }


class ShardingTests(unittest.TestCase):
    def test_parse_spec_filter_rejects_unknown_keys(self) -> None:
        self.assertEqual({"MAGE_FIRE", "MAGE_FROST"}, parse_spec_filter("MAGE_FIRE, MAGE_FROST"))
        self.assertIsNone(parse_spec_filter(None))
        with self.assertRaisesRegex(ValueError, "MAGE_FIREE"):
            parse_spec_filter("MAGE_FIREE")

    def test_filter_specs_keeps_the_shard_and_reports_missing_specs(self) -> None:
        specs = {"MAGE_fire": {}, "MAGE_frost": {}, "HUNTER_beast-mastery": {}}
        skips: list[SkipRecord] = []
        kept = filter_specs(specs, {"MAGE_FIRE", "HUNTER_BEAST_MASTERY", "PRIEST_HOLY"}, skips)
        self.assertEqual({"MAGE_fire", "HUNTER_beast-mastery"}, set(kept))
        self.assertEqual([SkipRecord("PRIEST_HOLY", None, None, "spec missing from ClassCodex data")], skips)

    def test_partials_round_trip_through_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a.json", Path(tmp) / "b.json"
            write_partial(partial("b1", ["MAGE_FIRE"]), [SkipRecord("MAGE_FIRE", "PVP", "h", "boom")], first)
            write_partial(partial("b1", ["MAGE_FROST"]), [], second)
            data, skips = merge_partials([first, second])
        self.assertEqual({"MAGE_FIRE", "MAGE_FROST"}, set(data["profiles"]))
        self.assertEqual("b1", data["buildId"])
        self.assertNotIn("skips", data)
        self.assertEqual([SkipRecord("MAGE_FIRE", "PVP", "h", "boom")], skips)

    def test_merge_refuses_overlapping_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a.json", Path(tmp) / "b.json"
            first.write_text(json.dumps(partial("b1", ["MAGE_FIRE"])), encoding="utf-8")
            second.write_text(json.dumps(partial("b1", ["MAGE_FIRE"])), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                merge_partials([first, second])

    def test_merge_refuses_shards_from_different_classcodex_builds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a.json", Path(tmp) / "b.json"
            first.write_text(json.dumps(partial("b1", ["MAGE_FIRE"])), encoding="utf-8")
            second.write_text(json.dumps(partial("b2", ["MAGE_FROST"])), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different ClassCodex builds"):
                merge_partials([first, second])

    def test_merge_mode_writes_the_addon_file_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shard = Path(tmp) / "a.json"
            shard.write_text(json.dumps(partial("b1", ["MAGE_FIRE"])), encoding="utf-8")
            out = Path(tmp) / "SV_ClassCodexWeights.lua"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = main(["--merge-inputs", str(shard), "--out", str(out)])
            self.assertEqual(0, code)
            self.assertIn('MAGE_FIRE={', out.read_text(encoding="utf-8"))

    def test_merge_mode_refuses_a_missing_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "SV_ClassCodexWeights.lua"
            with redirect_stderr(io.StringIO()):
                code = main(["--merge-inputs", str(Path(tmp) / "nope.json"), "--out", str(out)])
            self.assertEqual(1, code)
            self.assertFalse(out.exists())


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "classcodex-stat-weights.yml"


class WorkflowShardTests(unittest.TestCase):
    def test_shards_cover_every_spec_exactly_once_and_are_all_merged(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        groups = re.findall(r"- group: (\S+)", text)
        spec_lists = re.findall(r'^\s+specs: "([^"]+)"', text, flags=re.MULTILINE)
        self.assertEqual(len(groups), len(spec_lists))
        seen: list[str] = [key for specs in spec_lists for key in specs.split(",")]
        self.assertEqual(len(seen), len(set(seen)), "a spec is in more than one shard")
        self.assertEqual(set(SPEC_BY_KEY), set(seen), "shards must cover every spec")
        merge_line = re.search(r'--merge-inputs "([^"]+)"', text).group(1)
        self.assertEqual(
            {f"partials/partial-weights-{group}.json" for group in groups}, set(merge_line.split(","))
        )


if __name__ == "__main__":
    unittest.main()
