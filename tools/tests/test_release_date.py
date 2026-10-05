"""The window shows the day the add-on was last updated, as '3 Oct 2026'."""
import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ReleaseDateTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_WindowChrome.lua")

    def test_the_date_is_written_with_an_english_month(self):
        self.ns.RELEASE_DATE = "2026-10-03"
        self.assertEqual("3 Oct 2026", self.ns.FormatReleaseDate())
        self.ns.RELEASE_DATE = "2027-01-15"
        self.assertEqual("15 Jan 2027", self.ns.FormatReleaseDate())

    def test_a_missing_or_broken_date_shows_nothing(self):
        self.ns.RELEASE_DATE = None
        self.assertIsNone(self.ns.FormatReleaseDate())
        self.ns.RELEASE_DATE = "soon"
        self.assertIsNone(self.ns.FormatReleaseDate())
        self.ns.RELEASE_DATE = "2026-13-01"
        self.assertIsNone(self.ns.FormatReleaseDate())


if __name__ == "__main__":
    unittest.main()
