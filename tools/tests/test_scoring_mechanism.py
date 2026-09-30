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
                for gap in (10, 14, 20):
                    for pair in PAIRS:
                        selected = self.comparison(mode, state, "chest", candidate("chest", 246 + gap, pair))
                        self.assertTrue(selected.isUpgrade and selected.deltaScore > 0, (mode, state, gap, pair))

    def test_small_steps_are_left_to_the_stats(self) -> None:
        # Up to +9 item levels is not forced: a split that loses value (all Versatility) is not an upgrade.
        for gap in (5, 9):
            worst = candidate("chest", 246 + gap, ("versatility_rating", "versatility_rating"))
            self.assertFalse(self.comparison("GUIDE", "mid", "chest", worst).isUpgrade, gap)

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
        # The guide has a Mastery = Haste tie tier, so those two share the average of ranks 1 and 2 (places are
        # worth 1.4 : 1.25 : 1.1 : 1 of the 6.00 budget).
        expected = {order[0]: 6 * 1.325 / 4.75, order[1]: 6 * 1.325 / 4.75, order[2]: 6 * 1.1 / 4.75, order[3]: 6 * 1.0 / 4.75}
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

    # --- two pieces are never both better than each other ---

    RATING_NAME = {"crit_rating": "crit", "haste_rating": "haste", "mastery_rating": "mastery",
                   "versatility_rating": "versatility"}

    def between(self, mode: str, ratings: dict, slot: str, worn: dict, other: dict) -> float:
        """The verdict points of `other` replacing `worn` in `slot`, for a character with `ratings`."""
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, ratings, 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", mode)
        equipped = lua.table()
        for gear_slot, (slot_id, _) in verdict.SLOTS.items():
            link = f"item:{gear_slot}:246"
            verdict.register_item(lua, link, 1, worn if gear_slot == slot else base_item(gear_slot), gear_slot)
            equipped[slot_id] = link
        lua.globals().EQUIPPED = equipped
        verdict.register_item(lua, "item:c:1", 1, other, slot)
        ns.ClearUpgradeIndicatorDecisionCache()
        return float(ns.BuildComparison("item:c:1", profile).selected.deltaScore)

    def pair_verdicts(self, mode: str, state: str, slot: str, a: dict, b: dict) -> tuple[float, float]:
        ratings = dict(STATES[state])
        forward = self.between(mode, ratings, slot, a, b)
        shifted = dict(ratings)
        for key, name in self.RATING_NAME.items():
            shifted[name] = shifted[name] + b.get(key, 0) - a.get(key, 0)
        backward = self.between(mode, shifted, slot, b, a)
        return forward, backward

    def test_two_pieces_are_never_both_better_than_each_other(self) -> None:
        a = base_item("chest")
        others = [
            {**a, "name": "same ilvl, stats moved", "crit_rating": 20, "haste_rating": 110, "mastery_rating": 80},
            {**a, "name": "versatility instead", "ilevel": 246, "versatility_rating": 72, "crit_rating": 30, "haste_rating": 50, "mastery_rating": 28},
            {**a, "name": "+4 ilvl", "ilevel": 250, "agility": 115, "crit_rating": 50, "haste_rating": 84, "mastery_rating": 49},
            {**a, "name": "-6 ilvl more top stats", "ilevel": 240, "agility": 104, "crit_rating": 40, "haste_rating": 84, "mastery_rating": 90},
            {**a, "name": "+6 ilvl worse split", "ilevel": 252, "agility": 117, "crit_rating": 60, "haste_rating": 20, "mastery_rating": 20, "versatility_rating": 40},
            {**a, "name": "+10 ilvl", "ilevel": 256, "agility": 122, "crit_rating": 80, "haste_rating": 60, "mastery_rating": 60},
            {**a, "name": "primary -4, better top stats", "agility": 106, "crit_rating": 70, "haste_rating": 110, "mastery_rating": 90},
        ]
        for mode in ("GUIDE", "MEASURED"):
            for state in STATES:
                for other in others:
                    forward, backward = self.pair_verdicts(mode, state, "chest", a, other)
                    self.assertFalse(forward > 0 and backward > 0, (mode, state, other["name"], forward, backward))

    def test_with_nothing_but_stats_the_two_directions_are_exactly_opposite(self) -> None:
        a = base_item("chest")
        b = {**a, "crit_rating": 20, "haste_rating": 110, "mastery_rating": 80}  # same item level, same primary
        for mode in ("GUIDE", "MEASURED"):
            for state in STATES:
                forward, backward = self.pair_verdicts(mode, state, "chest", a, b)
                self.assertAlmostEqual(0.0, forward + backward, places=6, msg=(mode, state, forward, backward))

    def test_six_item_levels_do_not_beat_a_much_better_split(self) -> None:
        # Seen in the game (head, Enhancement): the 256 piece has Haste + Versatility, the 250 piece has
        # Haste + Mastery (the top two stats) and 5 less Agility. Six item levels are a small step, so the
        # stats decide: in Guide the 250 piece is the upgrade and the 256 piece is not, from both sides.
        high = {"name": "256", "ilevel": 256, "agility": 91, "haste_rating": 66, "versatility_rating": 72}
        low = {"name": "250", "ilevel": 250, "agility": 86, "haste_rating": 84, "mastery_rating": 49}
        ratings = {"crit": 261, "haste": 663, "mastery": 677, "versatility": 97}
        for mode in ("GUIDE", "MEASURED"):
            low_over_high = self.between(mode, ratings, "head", high, low)
            shifted = dict(ratings, haste=ratings["haste"] + 84 - 66, mastery=ratings["mastery"] + 49,
                           versatility=ratings["versatility"] - 72)
            high_over_low = self.between(mode, shifted, "head", low, high)
            if mode == "GUIDE":
                self.assertGreater(low_over_high, 0, mode)
                self.assertLess(high_over_low, 0, mode)
            else:
                # Measured follows our own measurements (Versatility is worth more there): it may decide
                # the other way, but never both ways.
                self.assertFalse(low_over_high > 0 and high_over_low > 0, mode)

    # --- need in rating points, gated by the guide's order ---

    SCREENSHOT = {"ITEM_MOD_MASTERY_RATING_SHORT": 677 / 1215, "ITEM_MOD_HASTE_RATING_SHORT": 663 / 1044,
                  "ITEM_MOD_CRIT_RATING_SHORT": 261 / 950, "ITEM_MOD_VERSATILITY": 97 / 139}

    def test_the_top_of_the_order_is_boosted_first_and_the_stat_nearly_there_gives(self) -> None:
        # The Enhancement Totemic state of a real character: Mastery = Haste first, Crit third and
        # furthest behind, Versatility last and nearly at its target.
        _, weights = self.live("GUIDE", lambda key: self.SCREENSHOT[key])
        mastery, haste = weights["ITEM_MOD_MASTERY_RATING_SHORT"], weights["ITEM_MOD_HASTE_RATING_SHORT"]
        crit, vers = weights["ITEM_MOD_CRIT_RATING_SHORT"], weights["ITEM_MOD_VERSATILITY"]
        self.assertGreater(mastery[1], mastery[0])  # the top two are above their starting weight
        self.assertGreater(haste[1], haste[0])
        self.assertLess(vers[1], vers[0])           # the last stat, 42 rating short, gives back
        # Crit is far behind but ranks below the top two that are still far from their targets:
        # it is not boosted above them, it stays near its own starting weight.
        self.assertLess(abs(crit[1] / crit[0] - 1), 0.05)
        self.assertGreater(mastery[1], crit[1])

    def test_a_gap_a_gem_or_enchant_can_close_counts_for_nothing(self) -> None:
        # Every stat only 40 rating short of its target: no stat is boosted, the weights are the shares.
        _, weights = self.live_points("GUIDE", 40)
        for key, (base, live) in weights.items():
            self.assertAlmostEqual(base, live, places=6, msg=key)

    def test_lower_stats_take_over_as_the_top_ones_get_there(self) -> None:
        # Mastery and Haste at their targets, Crit and Versatility far behind: now Crit is boosted.
        fractions = {"ITEM_MOD_MASTERY_RATING_SHORT": 1.0, "ITEM_MOD_HASTE_RATING_SHORT": 1.0,
                     "ITEM_MOD_CRIT_RATING_SHORT": 0.3, "ITEM_MOD_VERSATILITY": 0.3}
        _, weights = self.live("GUIDE", lambda key: fractions[key])
        crit = weights["ITEM_MOD_CRIT_RATING_SHORT"]
        self.assertGreater(crit[1], crit[0])

    def live_points(self, mode: str, missing: float) -> tuple:
        lua, ns = self.lua, self.ns
        verdict.set_character(lua, STATES["mid"], 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", mode)
        targets = self.targets(profile)
        ratings = {}
        for name, key in (("crit", "ITEM_MOD_CRIT_RATING_SHORT"), ("haste", "ITEM_MOD_HASTE_RATING_SHORT"),
                          ("mastery", "ITEM_MOD_MASTERY_RATING_SHORT"), ("versatility", "ITEM_MOD_VERSATILITY")):
            ratings[name] = targets[key] - missing
        verdict.set_character(lua, ratings, 1600)
        profile = verdict.build_profile(lua, ns, "MYTHIC_PLUS", mode)
        keys = [str(profile.secondaryOrder[i]) for i in range(1, 5)]
        return profile, {k: ns.GetScoringSecondaryWeights(profile, k) for k in keys}

    def test_a_gain_of_a_few_points_is_not_an_upgrade(self) -> None:
        tiny = {**base_item("chest"), "name": "tiny", "mastery_rating": 81}     # +1 Mastery
        real = {**base_item("chest"), "name": "real", "mastery_rating": 100}    # +20 Mastery
        self.assertFalse(self.comparison("GUIDE", "mid", "chest", tiny).isUpgrade)
        self.assertTrue(self.comparison("GUIDE", "mid", "chest", real).isUpgrade)

    # --- pieces without a primary stat: the first secondary counts as the primary ---

    def test_a_trinket_without_primary_counts_its_first_secondary_as_primary(self) -> None:
        worn = {"name": "worn", "ilevel": 259, "versatility_rating": 100}          # last of the order
        first = {"name": "first", "ilevel": 259, "mastery_rating": 100}            # first of the order
        agility = {"name": "agility", "ilevel": 259, "agility": 100}               # the primary stat
        forward = self.between("GUIDE", STATES["mid"], "trinket1", worn, first)
        self.assertGreater(forward, 150)       # 100 of the first stat is worth about 100 primary, not 100 Versatility
        swap_to_primary = self.between("GUIDE", STATES["mid"], "trinket1", first, agility)
        self.assertLess(abs(swap_to_primary), 0.25 * forward)   # the first stat and the primary are close

    def test_two_trinkets_are_never_both_better_than_each_other(self) -> None:
        a = {"name": "a", "ilevel": 259, "haste_rating": 100}
        b = {"name": "b", "ilevel": 259, "agility": 89}
        for mode in ("GUIDE", "MEASURED"):
            for state in STATES:
                forward, backward = self.pair_verdicts(mode, state, "trinket1", a, b)
                self.assertFalse(forward > 0 and backward > 0, (mode, state, forward, backward))


if __name__ == "__main__":
    unittest.main()
