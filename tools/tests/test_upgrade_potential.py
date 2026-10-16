"""Room to grow on the upgrade track: two pieces the stats cannot tell apart are not equal for the player, the one that can
still be raised wins. It never overrules a real difference. Real scoring, real generated data."""
from __future__ import annotations

import unittest

from tools import addon_harness as verdict
from tools.tests.test_addon_lua import LuaRuntime
from tools.tests.test_scoring_mechanism import STATES, base_item


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class UpgradePotentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()

    def judge(self, mastery_change, candidate_top=None, equipped_top=None, myth_targets=None):
        """The chest the bags hold, with its mastery changed by `mastery_change` against the worn one (item level 246);
        *_top: the item level the piece can reach on its upgrade track (nil: not on one)."""
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "GUIDE")
        if myth_targets is not None:
            # The shown tier's targets are all the character already has (a surplus); the Myth ones are `myth_targets` times higher.
            rows = lua.table()
            for index in range(1, len(profile.auditTargets.rows) + 1):
                row = profile.auditTargets.rows[index]
                rows[index] = lua.table(key=row.key, label=row.label, type=row.type, priority=row.priority,
                                        baseModifier=row.baseModifier, target=1)
            myth_rows = lua.table()
            for index in range(1, len(profile.auditTargets.rows) + 1):
                row = profile.auditTargets.rows[index]
                myth_rows[index] = lua.table(key=row.key, label=row.label, type=row.type, priority=row.priority,
                                             baseModifier=row.baseModifier, target=myth_targets)
            profile.auditTargets = lua.table(rows=rows, source="test")
            profile.mythAuditTargets = lua.table(rows=myth_rows, source="test")
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

    def test_a_piece_with_room_on_a_higher_track_is_judged_against_the_myth_targets(self):
        # The shown tier's targets are met many times over (surplus: the extra mastery counts less); the Myth
        # targets are far above the character, so the extra mastery is fully needed. Without room to grow the
        # shown tier's targets decide.
        with_room = self.judge(10, candidate_top=346, equipped_top=300, myth_targets=100000)
        without_room = self.judge(10, candidate_top=None, equipped_top=300, myth_targets=100000)
        self.assertGreater(with_room.rawDeltaScore, without_room.rawDeltaScore)

    def test_a_piece_that_is_not_on_a_higher_track_keeps_the_shown_targets(self):
        same_track = self.judge(10, candidate_top=300, equipped_top=300, myth_targets=100000)
        none = self.judge(10, candidate_top=None, equipped_top=300, myth_targets=100000)
        self.assertEqual(none.rawDeltaScore, same_track.rawDeltaScore)

    def test_without_myth_targets_a_piece_with_room_is_judged_as_before(self):
        # The shown tier is Myth itself: the profile carries no separate Myth targets.
        with_room = self.judge(10, candidate_top=346, equipped_top=300)
        without_room = self.judge(10, candidate_top=None, equipped_top=300)
        self.assertEqual(without_room.rawDeltaScore, with_room.rawDeltaScore)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class JewelryTopStatTests(unittest.TestCase):
    """Rings and necks all lack a primary stat, so the guide's first secondary gets no stand-in boost there: it is
    worth about what its place in the order says. Trinkets (which may give a primary) keep the boost."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()

    def score(self, slot, stat, amount):
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "GUIDE")
        item = {"name": "X", "ilevel": 246, "agility": 0, stat: amount}
        link = f"item:{slot}:{stat}:{amount}"
        verdict.register_item(lua, link, 1, item, slot)
        score = ns.GetItemProfileScore(link, profile, verdict.SLOTS[slot][0])
        return score[0] if isinstance(score, tuple) else score

    def worth(self, slot, stat):
        """The points one rating point of `stat` is worth in `slot`."""
        return (self.score(slot, stat, 100) - self.score(slot, stat, 0)) / 100

    def test_the_first_secondary_of_the_order_is_not_boosted_on_a_neck_or_a_ring(self):
        for slot in ("neck", "finger1"):
            scores = {stat: self.worth(slot, stat) for stat in ("crit_rating", "haste_rating", "mastery_rating")}
            self.assertLess(max(scores.values()) / min(scores.values()), 1.6, (slot, scores))

    def test_a_trinket_keeps_the_boost(self):
        scores = {stat: self.worth("trinket1", stat) for stat in ("crit_rating", "haste_rating", "mastery_rating")}
        self.assertGreater(max(scores.values()) / min(scores.values()), 1.6, scores)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class UpgradeCeilingTests(unittest.TestCase):
    """The game says a piece's rank (Hero 1/6) but not the item level it reaches at 6/6: that comes from our own track data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()

    def ceiling(self, level, upgrade):
        lua, ns = self.lua, self.ns
        item = {"name": "X", "ilevel": level, "crit_rating": 10}
        verdict.register_item(lua, "item:ring:1", 1, item, "finger1")
        lua.execute(f"UPG = {{ ['item:ring:1'] = {upgrade} }}; C_Item.GetItemUpgradeInfo = function(l) return UPG[l] end")
        return ns.GetItemUpgradeCeiling("item:ring:1")

    def test_the_rank_and_level_tell_the_track(self):
        self.assertEqual(321, self.ceiling(305, "{ currentLevel = 1, maxLevel = 6, trackString = 'Hero' }"))
        self.assertEqual(308, self.ceiling(292, "{ currentLevel = 1, maxLevel = 6, trackString = 'Champion' }"))
        self.assertEqual(334, self.ceiling(318, "{ currentLevel = 1, maxLevel = 6 }"))  # no track name: the level at that rank says Myth
        self.assertEqual(308, self.ceiling(305, "{ currentLevel = 5, maxLevel = 6 }"))  # Champion 5/6 shares its level with Hero 1/6

    def test_the_track_name_is_the_fallback(self):
        self.assertEqual(321, self.ceiling(250, "{ currentLevel = 1, maxLevel = 6, trackString = 'Hero' }"))

    def test_a_client_that_gives_the_top_is_believed(self):
        self.assertEqual(340, self.ceiling(305, "{ currentLevel = 1, maxLevel = 6, maxItemLevel = 340 }"))

    def test_a_piece_on_no_track_has_none(self):
        self.assertIsNone(self.ceiling(305, "nil"))
        self.assertIsNone(self.ceiling(250, "{ currentLevel = 1, maxLevel = 6 }"))
