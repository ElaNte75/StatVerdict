"""Diminishing returns in the verdict scoring: a rating point is worth less once the
character is past the first cut, and a swap is judged by what it really adds."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as verdict
from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class EffectiveRatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "Data/Generated/SV_StatDR.lua")
        load_addon_file(self.lua, self.ns, "Core/SV_DiminishingReturns.lua")
        self.lua.execute("UnitLevel = function() return 90 end")
        # rating per 1% at level 90 (the vendored table): crit 46, haste 44, versatility 54
        self.k = {"haste": 44.0, "crit": 46.0, "versatility": 54.0}
        self.keys = {"haste": "ITEM_MOD_HASTE_RATING_SHORT", "crit": "ITEM_MOD_CRIT_RATING_SHORT",
                     "versatility": "ITEM_MOD_VERSATILITY", "mastery": "ITEM_MOD_MASTERY_RATING_SHORT"}

    def effective(self, stat, current, delta):
        return self.ns.GetEffectiveRatingDelta(self.keys[stat], current, delta)

    def test_below_the_first_cut_a_rating_point_is_worth_its_full_value(self) -> None:
        for stat in self.keys:
            self.assertAlmostEqual(200.0, self.effective(stat, 500, 200), msg=stat)
            self.assertAlmostEqual(-150.0, self.effective(stat, 600, -150), msg=stat)

    def test_past_the_first_cut_a_rating_point_is_worth_less(self) -> None:
        low = self.effective("haste", 2000, 100)
        self.assertLess(low, 100.0)
        self.assertGreater(low, 60.0)
        # further up it is worth less again
        self.assertLess(self.effective("haste", 3500, 100), low)

    def test_it_matches_the_vendored_percent_curve(self) -> None:
        tp = self.ns.StatDR.TargetPercent
        for stat in ("haste", "crit", "versatility"):
            for current, delta in ((1000, 100), (1400, 200), (2100, 150), (2600, -300), (1250, 500)):
                expected = self.k[stat] * (tp(stat, 90, current + delta, "SHAMAN", "enhancement")
                                           - tp(stat, 90, current, "SHAMAN", "enhancement"))
                self.assertAlmostEqual(expected, self.effective(stat, current, delta), places=6,
                                       msg=(stat, current, delta))
        # mastery: the spec's coefficient (Enhancement 2.0) only scales the effect, not the cut
        expected = 46.0 * (tp("mastery", 90, 2300, "SHAMAN", "enhancement")
                           - tp("mastery", 90, 2000, "SHAMAN", "enhancement")) / 2.0
        self.assertAlmostEqual(expected, self.effective("mastery", 2000, 300), places=6)

    def test_a_swap_that_crosses_the_cut_is_partly_cut(self) -> None:
        crossing = self.effective("haste", 1250, 300)  # 1320 is where the cut starts
        self.assertLess(crossing, 300.0)
        self.assertGreater(crossing, self.effective("haste", 2000, 300))

    def test_losing_rating_above_the_cut_costs_less_than_its_face_value(self) -> None:
        self.assertGreater(self.effective("haste", 2500, -200), -200.0)

    def test_unknown_inputs_leave_the_amount_alone(self) -> None:
        self.assertEqual(120, self.ns.GetEffectiveRatingDelta("ITEM_MOD_AGILITY_SHORT", 2000, 120))
        self.assertEqual(120, self.ns.GetEffectiveRatingDelta(self.keys["haste"], None, 120))
        self.assertIsNone(self.ns.GetEffectiveRatingDelta(self.keys["haste"], 2000, None))
        self.assertEqual(0, self.ns.GetEffectiveRatingDelta(self.keys["haste"], 2000, 0))

    def test_brackets_mirror_the_vendored_curve(self) -> None:
        effective = self.ns.DiminishingReturnsEffectivePercent
        for raw in (5, 25, 30, 33, 45, 55, 80, 140):
            self.assertAlmostEqual(raw, self.ns.StatDR.RawPercentFor(effective(raw)), places=6, msg=raw)

    def test_mastery_converts_like_crit_in_the_vendored_table(self) -> None:
        tp = self.ns.StatDR.TargetPercent
        for level in (60, 80, 90):
            self.assertAlmostEqual((tp("mastery", level, 400, "SHAMAN", "enhancement") - 8) / 2.0,
                                   tp("crit", level, 400) - 5, places=6, msg=level)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ScoringUsesTheCutTests(unittest.TestCase):
    """The verdict points use the effective change, so the same item is worth less to a
    character that already has a lot of that stat."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()

    def points(self, haste_now: int, with_cut: bool) -> float:
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, {"crit": 900, "haste": haste_now, "mastery": 900, "versatility": 100}, 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "GUIDE")
        equipped = lua.table()
        for slot, (slot_id, _) in verdict.SLOTS.items():
            link = f"item:{slot}:246"
            verdict.register_item(lua, link, 1, {"name": slot, "ilevel": 246, "agility": 60}, slot)
            equipped[slot_id] = link
        lua.globals().EQUIPPED = equipped
        verdict.register_item(lua, "item:c:1", 1, {"name": "H", "ilevel": 246, "agility": 60, "haste_rating": 200}, "neck")
        original = ns.GetEffectiveRatingDelta
        if not with_cut:
            ns.GetEffectiveRatingDelta = lambda key, current, delta: delta
        try:
            ns.ClearUpgradeIndicatorDecisionCache()
            return float(ns.BuildComparison("item:c:1", profile).selected.deltaScore)
        finally:
            ns.GetEffectiveRatingDelta = original

    def test_no_difference_below_the_first_cut(self) -> None:
        self.assertAlmostEqual(self.points(600, False), self.points(600, True))

    def test_the_same_item_is_worth_less_far_above_the_first_cut(self) -> None:
        self.assertLess(self.points(2600, True), self.points(2600, False))


if __name__ == "__main__":
    unittest.main()
