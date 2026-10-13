"""Room to grow on the upgrade track: two pieces the stats cannot tell apart are not equal for the player, the one that can
still be raised wins. It never overrules a real difference. Real scoring, real generated data."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as verdict
from tools.tests.test_addon_lua import LuaRuntime
from tools.tests.test_scoring_mechanism import STATES, base_item


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class UpgradePotentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()

    def judge(self, mastery_change, candidate_top=None, equipped_top=None):
        """The chest the bags hold, with its mastery changed by `mastery_change` against the worn one (item level 246);
        *_top: the item level the piece can reach on its upgrade track (nil: not on one)."""
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "GUIDE")
        equipped = lua.table()
        for gear_slot, (slot_id, _) in verdict.SLOTS.items():
            link = f"item:{gear_slot}:246"
            verdict.register_item(lua, link, 1, base_item(gear_slot), gear_slot)
            equipped[slot_id] = link
        lua.globals().EQUIPPED = equipped
        item = dict(base_item("chest"))
        item["name"] = "C"
        item["mastery_rating"] += mastery_change
        verdict.register_item(lua, "item:c:1", 1, item, "chest")
        lua.execute("UPG = {}")
        if candidate_top:
            lua.execute(f'UPG["item:c:1"] = {{ maxItemLevel = {candidate_top} }}')
        if equipped_top:
            lua.execute(f'UPG["item:chest:246"] = {{ maxItemLevel = {equipped_top} }}')
        lua.execute("C_Item.GetItemUpgradeInfo = function(link) return UPG[link] end")
        ns.ClearUpgradeIndicatorDecisionCache()
        return ns.BuildComparison("item:c:1", profile).selected

    def test_equal_stats_without_room_are_no_upgrade(self):
        self.assertFalse(self.judge(0).isUpgrade)

    def test_equal_stats_with_room_to_grow_are_an_upgrade(self):
        selected = self.judge(0, candidate_top=259)
        self.assertTrue(selected.isUpgrade)
        self.assertTrue(selected.potentialLift)
        self.assertGreater(selected.deltaScore, 0)   # the verdict stays a small positive number
        self.assertEqual(0, selected.rawDeltaScore)  # the stats themselves are equal

    def test_slightly_worse_stats_with_room_are_still_an_upgrade(self):
        self.assertTrue(self.judge(-1, candidate_top=259).isUpgrade)

    def test_a_real_loss_is_never_overruled(self):
        self.assertFalse(self.judge(-5, candidate_top=259).isUpgrade)

    def test_both_with_the_same_room_changes_nothing(self):
        self.assertFalse(self.judge(0, candidate_top=259, equipped_top=259).isUpgrade)

    def test_the_worn_piece_with_more_room_is_not_a_reason_to_refuse_a_real_upgrade(self):
        selected = self.judge(8, candidate_top=None, equipped_top=259)
        self.assertTrue(selected.isUpgrade)
        self.assertIsNone(selected.potentialLift)

    def test_the_worn_piece_with_more_room_does_not_make_an_equal_piece_an_upgrade(self):
        self.assertFalse(self.judge(0, candidate_top=None, equipped_top=259).isUpgrade)

    def test_the_push_is_small_and_capped(self):
        # 3 levels of room are worth 0.3%: not enough to lift a piece that is 0.425% worse.
        self.assertFalse(self.judge(-3, candidate_top=249).isUpgrade)
        # A huge room is capped at 1.5%: 0.425% worse is lifted, 2.8% worse (-20 mastery) is not.
        self.assertTrue(self.judge(-3, candidate_top=346).isUpgrade)
        self.assertFalse(self.judge(-20, candidate_top=346).isUpgrade)
