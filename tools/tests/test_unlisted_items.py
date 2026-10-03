"""Items the guide lists without bonus ids (about 70 trinkets): the same item's ids from another list, else the
6/6 id of the shown tier's track, never anything for PvP."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as v


class UnlistedItemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = v.load_addon()
        cls.repo = cls.ns.ProfileRepository

    def entries(self):
        """Every trinket entry of the real data: (item id, bonus ids or None, goal)."""
        root = self.ns.ClassCodexTargets
        out = []
        for spec in root.profiles.keys():
            for goal in root.profiles[spec].goals.keys():
                for hero in root.profiles[spec].goals[goal].heroTalents.keys():
                    trinkets = root.profiles[spec].goals[goal].heroTalents[hero].trinkets
                    for i in range(1, len(trinkets or {}) + 1):
                        entry = trinkets[i]
                        ids = entry.bonus_ids
                        out.append((int(entry.item_id), [int(ids[k]) for k in range(1, len(ids) + 1)] if ids and len(ids) else None, str(goal)))
        return out

    def test_an_item_listed_with_ids_elsewhere_borrows_them(self) -> None:
        entries = self.entries()
        with_ids = {item for item, ids, goal in entries if ids and goal != "PVP"}
        without = {item for item, ids, goal in entries if not ids}
        borrowable = sorted(with_ids & without)
        self.assertTrue(borrowable, "the real data has trinkets listed with and without ids")
        for item in borrowable[:10]:
            ids = self.repo.GetKnownBonusIDs(item)
            self.assertIsNotNone(ids, item)
            self.assertGreater(len(ids), 0, item)

    def test_an_unknown_item_borrows_nothing(self) -> None:
        self.assertIsNone(self.repo.GetKnownBonusIDs(1))
        self.assertIsNone(self.repo.GetKnownBonusIDs(None))

    def test_the_borrowed_ids_are_a_copy(self) -> None:
        item = next(item for item, ids, goal in self.entries() if ids and goal != "PVP")
        first = self.repo.GetKnownBonusIDs(item)
        first[1] = 999999
        self.assertNotEqual(999999, self.repo.GetKnownBonusIDs(item)[1])

    def set_tier(self, bin_name: str, goal: str = "MYTHIC_PLUS") -> None:
        lua = self.lua
        lua.globals().SV_TEST_BIN = bin_name
        lua.globals().SV_TEST_GOAL = goal
        self.repo.GetEffectiveStatTargetBin = lua.eval("function() return SV_TEST_BIN end")
        self.ns.GetStatAuditGoalMode = lua.eval("function() return SV_TEST_GOAL end")

    def test_the_shown_tier_picks_the_track_and_its_top_id(self) -> None:
        self.ns.ClassCodexTargets.trackTop = self.lua.table_from({"myth": 111, "hero": 222, "champion": 333})
        for bin_name, track, top in (("top20", "myth", 111), ("top50", "hero", 222), ("top80", "champion", 333)):
            self.set_tier(bin_name)
            self.assertEqual(track, self.repo.GetActiveTrack(), bin_name)
            self.assertEqual(top, self.repo.GetTrackTopBonusID(), bin_name)

    def test_pvp_has_no_track(self) -> None:
        self.ns.ClassCodexTargets.trackTop = self.lua.table_from({"myth": 111, "hero": 222, "champion": 333})
        self.set_tier("top80", goal="PVP")
        self.assertIsNone(self.repo.GetActiveTrack())
        self.assertIsNone(self.repo.GetTrackTopBonusID())

    def test_data_without_top_ids_gives_none(self) -> None:
        self.ns.ClassCodexTargets.trackTop = None
        self.set_tier("top50")
        self.assertIsNone(self.repo.GetTrackTopBonusID())


if __name__ == "__main__":
    unittest.main()
