from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.classcodex_weights_cli import MAX_FILE_BYTES, render_lua, write_addon_file


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


if __name__ == "__main__":
    unittest.main()
