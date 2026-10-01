import json
import unittest
from pathlib import Path

from tools.item_sources import DEFAULT_OUT, DEFAULT_POOL, build_sources, render_lua, source_kind


class SourceKindTests(unittest.TestCase):
    def test_dungeons_and_known_raids_are_labelled_the_rest_are_not(self) -> None:
        self.assertEqual("D", source_kind({"kind": "dungeon", "instance": "Kings' Rest"}))
        self.assertEqual("R", source_kind({"kind": "raid", "instance": "The Voidspire"}))
        # The journal lists world bosses and delves among the raids: it does not say which they are.
        self.assertEqual("", source_kind({"kind": "raid", "instance": "Midnight"}))
        self.assertEqual("", source_kind({"kind": "raid", "instance": "Sporefall"}))


class BuildSourcesTests(unittest.TestCase):
    pool = {"items": {
        "1": {"sources": [{"instance": "Kings' Rest", "encounter": "Dazar", "kind": "dungeon"},
                          {"instance": "Kings' Rest", "encounter": "Dazar", "kind": "dungeon"}]},
        "2": {"sources": [{"instance": "The Voidspire", "encounter": "Vorasius", "kind": "raid"},
                          {"instance": "Murder Row", "encounter": "Zaen", "kind": "dungeon"}]},
        "3": {"sources": []},
        "4": {"sources": [{"instance": "", "encounter": "x", "kind": "dungeon"}]},
    }}

    def test_a_repeated_source_counts_once_and_empty_ones_are_left_out(self) -> None:
        self.assertEqual({1: [["Kings' Rest", "Dazar", "D"]],
                          2: [["The Voidspire", "Vorasius", "R"], ["Murder Row", "Zaen", "D"]]},
                         build_sources(self.pool))

    def test_the_lua_is_a_plain_table_keyed_by_item_id(self) -> None:
        text = render_lua(build_sources(self.pool))
        self.assertIn('[1]={{"Kings\' Rest","Dazar","D"}}', text)
        self.assertIn('[2]={{"The Voidspire","Vorasius","R"},{"Murder Row","Zaen","D"}}', text)
        self.assertTrue(text.startswith("local addonName, ns = ...\n"))


class CommittedFileTests(unittest.TestCase):
    def test_the_committed_file_is_exactly_what_the_generator_writes(self) -> None:
        """No hand edits: the data file is the generator's output for the committed pool."""
        pool = json.loads(Path(DEFAULT_POOL).read_text(encoding="utf-8"))
        self.assertEqual(render_lua(build_sources(pool)), Path(DEFAULT_OUT).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
