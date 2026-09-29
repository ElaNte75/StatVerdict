from __future__ import annotations

import unittest

from tools.classcodex_targets_cli import render_lua


class RenderLuaTests(unittest.TestCase):
    def test_wraps_the_data_as_ns_class_codex_targets(self) -> None:
        rendered = render_lua({"schemaVersion": 1, "profiles": {}})
        self.assertIn("ns.ClassCodexTargets = ", rendered)
        self.assertIn("Do not edit manually", rendered)


if __name__ == "__main__":
    unittest.main()
