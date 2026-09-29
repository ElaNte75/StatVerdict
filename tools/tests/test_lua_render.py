from __future__ import annotations

import unittest

from tools.classcodex_lua_sandbox import run_addon_namespace
from tools.lua_render import to_lua, to_lua_compact

try:
    import lupa  # noqa: F401
except ImportError:  # optional dev dependency
    lupa = None

SAMPLE = {
    "buildId": "20260929-x",
    "end": {"and": 1, "master-of-harmony": [1, 2, 3], "top20": {"critical_strike": 1225.5}},
    "name": 'quote " and \ backslash and ünïcode',
    "flags": [True, False],
    "empty": {},
    "nested": [{"a": 1}, {"b": [4, 5]}],
    "9lives": 3,
}


@unittest.skipIf(lupa is None, "lupa not installed")
class CompactLuaRenderTests(unittest.TestCase):
    def load(self, text: str):
        return run_addon_namespace("local _, ns = ...\nns.Data = " + text, "compact.lua", "StatVerdict")["Data"]

    @staticmethod
    def normalise(value):
        if isinstance(value, dict) and value and all(isinstance(k, int) for k in value):
            return [CompactLuaRenderTests.normalise(value[k]) for k in sorted(value)]
        if isinstance(value, dict):
            return {k: CompactLuaRenderTests.normalise(v) for k, v in value.items()}
        if isinstance(value, list):
            return [CompactLuaRenderTests.normalise(v) for v in value]
        return value

    def test_compact_output_loads_to_the_same_data_as_the_readable_output(self) -> None:
        self.assertEqual(self.normalise(self.load(to_lua(SAMPLE))), self.normalise(self.load(to_lua_compact(SAMPLE))))

    def test_keywords_and_odd_keys_are_bracketed_and_names_are_bare(self) -> None:
        text = to_lua_compact(SAMPLE)
        self.assertIn('["end"]=', text)
        self.assertIn('["master-of-harmony"]=', text)
        self.assertIn('["9lives"]=', text)
        self.assertIn("top20=", text)

    def test_integer_keys_stay_numbers_in_lua(self) -> None:
        # trackSwap = {hero = {[12854] = 12846}}: the addon looks bonus ids up by number.
        data = {"hero": {12854: 12846, 13848: 12846}}
        text = to_lua_compact(data)
        self.assertIn("[12854]=12846", text)
        self.assertEqual(data, self.load(text))

    def test_compact_is_smaller_and_has_no_newlines(self) -> None:
        self.assertNotIn("\n", to_lua_compact(SAMPLE))
        self.assertLess(len(to_lua_compact(SAMPLE)), len(to_lua(SAMPLE)))


if __name__ == "__main__":
    unittest.main()
