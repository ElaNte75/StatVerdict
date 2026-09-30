"""The mechanism that decides what is an upgrade, judged by its own rules (not by any data set):
item level wins (except on jewelry), Measured uses the size of the measured weights, Guide keeps
the guide's order. Runs the real scoring with the real generated data."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as verdict
from tools.tests.test_addon_lua import LuaRuntime

SLOTS = list(verdict.SLOTS)
STATES = {
    "undergeared": {"crit": 400, "haste": 500, "mastery": 500, "versatility": 60},
    "mid": {"crit": 900, "haste": 1000, "mastery": 1000, "versatility": 100},
    "well geared": {"crit": 1150, "haste": 1250, "mastery": 1300, "versatility": 150},
}
STATS = ("mastery_rating", "haste_rating", "crit_rating", "versatility_rating")
PAIRS = [(a, b) for i, a in enumerate(STATS) for b in STATS[i + 1:]]


def base_item(slot: str) -> dict:
    if slot in ("neck", "finger1", "finger2"):
        return {"name": slot, "ilevel": 246, "agility": 0, "crit_rating": 70, "haste_rating": 80,
                "mastery_rating": 90}
    return {"name": slot, "ilevel": 246, "agility": 110, "crit_rating": 60, "haste_rating": 70, "mastery_rating": 80}


def candidate(slot: str, ilvl: int, pair: tuple[str, str]) -> dict:
    """The same item at another item level (every stat grows about 1.3% per level), its secondaries
    all in two stats."""
    scale = 1 + 0.013 * (ilvl - 246)
    b = base_item(slot)
    total = (b["crit_rating"] + b["haste_rating"] + b["mastery_rating"]) * scale
    item = {"name": "C", "ilevel": ilvl, "agility": b["agility"] * scale}
    for key in pair:
        item[key] = total / 2
    return item


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ScoringMechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = verdict.load_addon()

    def comparison(self, mode: str, state: str, slot: str, item: dict):
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES[state], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", mode)
        equipped = lua.table()
        for gear_slot, (slot_id, _) in verdict.SLOTS.items():
            link = f"item:{gear_slot}:246"
            verdict.register_item(lua, link, 1, base_item(gear_slot), gear_slot)
            equipped[slot_id] = link
        lua.globals().EQUIPPED = equipped
        verdict.register_item(lua, "item:c:1", 1, item, slot)
        ns.ClearUpgradeIndicatorDecisionCache()
        return ns.BuildComparison("item:c:1", profile).selected

    def test_clearly_more_item_level_is_always_an_upgrade_on_armor(self) -> None:
        for mode in ("GUIDE", "MEASURED"):
            for state in STATES:
                for gap in (6, 10, 20):
                    for pair in PAIRS:
                        selected = self.comparison(mode, state, "chest", candidate("chest", 246 + gap, pair))
                        self.assertTrue(selected.isUpgrade and selected.deltaScore > 0, (mode, state, gap, pair))

    def test_small_steps_are_left_to_the_stats(self) -> None:
        # +5 item levels is not forced: a split that loses value (all Versatility) is not an upgrade.
        worst = candidate("chest", 251, ("versatility_rating", "versatility_rating"))
        self.assertFalse(self.comparison("GUIDE", "mid", "chest", worst).isUpgrade)

    def test_jewelry_is_the_exception(self) -> None:
        # Necks carry no primary stat: +10 item levels with the worst split is not forced up.
        worst = candidate("neck", 256, ("versatility_rating", "versatility_rating"))
        self.assertFalse(self.comparison("GUIDE", "mid", "neck", worst).isUpgrade)

    def test_less_item_level_is_still_held_back(self) -> None:
        best = candidate("chest", 236, ("mastery_rating", "haste_rating"))
        self.assertFalse(self.comparison("GUIDE", "mid", "chest", best).isUpgrade)

    def test_measured_uses_the_size_of_the_measured_weights(self) -> None:
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "MEASURED")
        weights = {str(k): float(profile.secondaryWeights[k]) for k in profile.secondaryWeights.keys()}
        shares = {k: ns.GetScoringSecondaryWeights(profile, k)[0] for k in weights}
        self.assertAlmostEqual(6.0, sum(shares.values()))
        total = sum(weights.values())
        for key, weight in weights.items():
            self.assertAlmostEqual(6.0 * weight / total, shares[key], places=6, msg=key)

    def test_guide_keeps_the_rank_shares_of_the_guide_order(self) -> None:
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", "GUIDE")
        self.assertIsNone(profile.secondaryWeights)
        order = [str(profile.secondaryOrder[i]) for i in range(1, 5)]
        # The guide has a Mastery = Haste tie tier, so those two share the average of ranks 1 and 2.
        expected = {order[0]: 2.1, order[1]: 2.1, order[2]: 1.2, order[3]: 0.6}
        self.assertEqual(order[:2], ["ITEM_MOD_MASTERY_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT"])
        for key, share in expected.items():
            self.assertAlmostEqual(share, ns.GetScoringSecondaryWeights(profile, key)[0], msg=key)

    def test_a_buff_does_not_move_the_ratings_until_gear_or_spec_changes(self) -> None:
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        before = ns.GetCurrentStatRating("ITEM_MOD_HASTE_RATING_SHORT")
        # A flask appears: the game reports more Haste, but no gear or spec event happened.
        lua.execute("local old = GetCombatRating; GetCombatRating = function(id) return old(id) + (id == 18 and 500 or 0) end")
        self.assertEqual(before, ns.GetCurrentStatRating("ITEM_MOD_HASTE_RATING_SHORT"))
        ns.InvalidateCurrentStatRatings()  # what an equipment/spec/talent event does
        self.assertEqual(before + 500, ns.GetCurrentStatRating("ITEM_MOD_HASTE_RATING_SHORT"))

    def test_stat_progress_reads_both_weights_from_the_scoring(self) -> None:
        # `a and f()` keeps only the first value of f(); that once left the Weight column at "-".
        import re
        from pathlib import Path
        source = Path("StatVerdict/UI/SV_StatAudit.lua").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"scoringBase, scoringLive\s*=\s*ns\.GetScoringSecondaryWeights\s+and", source))
        self.assertEqual(2, source.count("scoringBase, scoringLive = ns.GetScoringSecondaryWeights("))

    # --- the live weights (how far each stat is from its target) ---

    def targets(self, profile) -> dict:
        rows = profile.auditTargets.rows
        return {str(rows[i].key): float(rows[i].target) for i in range(1, len(rows) + 1)}

    def live(self, mode: str, fraction_of_target) -> tuple:
        """(profile, {stat: live weight}) when the character holds `fraction_of_target[stat]` of each target."""
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", mode)
        targets = self.targets(profile)
        ratings = {}
        for name, key in (("crit", "ITEM_MOD_CRIT_RATING_SHORT"), ("haste", "ITEM_MOD_HASTE_RATING_SHORT"),
                          ("mastery", "ITEM_MOD_MASTERY_RATING_SHORT"), ("versatility", "ITEM_MOD_VERSATILITY")):
            ratings[name] = targets[key] * fraction_of_target(key)
        verdict.set_character(lua, ratings, 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", mode)
        keys = [str(profile.secondaryOrder[i]) for i in range(1, 5)]
        return profile, {k: ns.GetScoringSecondaryWeights(profile, k) for k in keys}

    def test_live_weights_always_add_up_to_the_budget(self) -> None:
        for mode in ("GUIDE", "MEASURED"):
            for fraction in (0.0, 0.4, 1.0, 2.5):
                _, weights = self.live(mode, lambda key: fraction)
                self.assertAlmostEqual(6.0, sum(live for _, live in weights.values()), places=6, msg=(mode, fraction))

    def test_the_last_stat_is_not_drained_when_everything_is_missing(self) -> None:
        # Every stat 60% short: nobody is drained to a floor; each keeps at least 80% of its share.
        for mode in ("GUIDE", "MEASURED"):
            _, weights = self.live(mode, lambda key: 0.4)
            for key, (base, live) in weights.items():
                self.assertGreater(live, 0.8 * base, (mode, key))

    def test_equal_shares_and_equal_needs_give_equal_weights(self) -> None:
        profile, weights = self.live("GUIDE", lambda key: 0.5)
        groups = profile.equalGroups
        self.assertIsNotNone(groups)  # the Totemic guide has a tie tier
        order = [str(profile.secondaryOrder[i]) for i in range(1, 5)]
        for group in groups.values():
            keys = [order[int(position) - 1] for position in group.values()]
            for key in keys[1:]:
                self.assertAlmostEqual(weights[keys[0]][1], weights[key][1], places=9)

    def test_a_bigger_deficit_and_a_surplus_move_a_weight_the_right_way(self) -> None:
        _, near = self.live("MEASURED", lambda key: 0.9)
        _, far = self.live("MEASURED", lambda key: 0.9 if key != "ITEM_MOD_HASTE_RATING_SHORT" else 0.3)
        _, over = self.live("MEASURED", lambda key: 0.9 if key != "ITEM_MOD_HASTE_RATING_SHORT" else 1.8)
        haste = "ITEM_MOD_HASTE_RATING_SHORT"
        self.assertGreater(far[haste][1], near[haste][1])
        self.assertLess(over[haste][1], near[haste][1])


if __name__ == "__main__":
    unittest.main()
