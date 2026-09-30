import unittest

from tools import classcodex_rules as rules


def secondary(*groups):
    return {"secondary": [list(g) for g in groups]}


class ResolveTests(unittest.TestCase):
    def test_the_context_is_tried_before_the_hero_tree(self) -> None:
        # Holy Paladin shape: the hero's own list is "all", the shared list has "mplus".
        category = {
            "lightsmith": {"all": "hero general"},
            "all": {"all": "shared general", "mplus": "shared mplus"},
        }
        self.assertEqual("shared mplus", rules.resolve_category(category, "lightsmith", "mplus")[0])
        self.assertEqual("hero general", rules.resolve_category(category, "lightsmith", "raid")[0])

    def test_pvp_falls_back_to_the_shuffle_bracket_and_never_to_all(self) -> None:
        self.assertEqual(["pvp", "pvp:shuffle"], rules.context_chain("pvp"))
        self.assertEqual(["mplus", "all"], rules.context_chain("mplus"))
        self.assertEqual(["pvp:3v3", "pvp"], rules.context_chain("pvp:3v3"))
        category = {"all": {"all": "pve", "pvp:shuffle": "shuffle"}}
        self.assertEqual("shuffle", rules.resolve_category(category, "all", "pvp")[0])
        self.assertIsNone(rules.resolve_category({"all": {"all": "pve"}}, "all", "pvp")[0])


class PriorityTests(unittest.TestCase):
    def test_mythic_plus_shows_the_aoe_order_when_there_is_one(self) -> None:
        value = {"all": {"all": secondary(["mastery"], ["haste", "crit"]), "aoe": secondary(["mastery"], ["crit"], ["haste"])}}
        shown = rules.default_priority(value, "hero", "MYTHIC_PLUS")
        self.assertEqual([["mastery"], ["crit"], ["haste"]], shown["secondary"])

    def test_raid_shows_single_target_else_the_general_order(self) -> None:
        with_single = {"all": {"all": secondary(["haste"]), "single-target": secondary(["crit"])}}
        self.assertEqual([["crit"]], rules.default_priority(with_single, "h", "RAID")["secondary"])
        only_general = {"all": {"all": secondary(["haste"]), "aoe": secondary(["crit"])}}
        self.assertEqual([["haste"]], rules.default_priority(only_general, "h", "RAID")["secondary"])

    def test_mythic_plus_without_aoe_keeps_the_general_order_and_tank_damage_is_not_the_default(self) -> None:
        value = {"all": {"all": secondary(["haste"], ["vers"]), "damage": secondary(["crit"], ["haste"])}}
        self.assertEqual([["haste"], ["vers"]], rules.default_priority(value, "h", "MYTHIC_PLUS")["secondary"])

    def test_hero_specific_lists_win_inside_a_context(self) -> None:
        value = {"totemic": {"all": secondary(["mastery", "haste"])}, "all": {"pvp": secondary(["vers"])}}
        self.assertEqual([["mastery", "haste"]], rules.default_priority(value, "totemic", "MYTHIC_PLUS")["secondary"])
        self.assertEqual([["vers"]], rules.default_priority(value, "totemic", "PVP")["secondary"])

    def test_no_priority_when_the_guide_has_none(self) -> None:
        self.assertIsNone(rules.default_priority({}, "h", "RAID"))
        self.assertIsNone(rules.default_priority({"all": {"all": {"secondary": []}}}, "h", "RAID"))


class GearTests(unittest.TestCase):
    def test_bis_is_read_under_hero_all_and_the_goal_context(self) -> None:
        gear = {"all": {"mplus": ["m"], "all": ["a"], "pvp": ["p"]}, "totemic": {"mplus": ["hero"]}}
        self.assertEqual(["m"], rules.bis_gear(gear, "MYTHIC_PLUS"))
        self.assertEqual(["a"], rules.bis_gear(gear, "RAID"))
        self.assertEqual(["p"], rules.bis_gear(gear, "PVP"))

    def test_trinkets_use_pvp_or_all_and_gems_enchants_fall_back_for_pvp(self) -> None:
        field = {"all": {"all": ["pve"]}}
        self.assertEqual(["pve"], rules.guide_field(field, "RAID"))
        self.assertIsNone(rules.guide_field(field, "PVP"))
        self.assertEqual(["pve"], rules.guide_field_with_fallback(field, "PVP"))

    def test_pvp_items_without_bonus_ids_borrow_them_by_item_id(self) -> None:
        specs = {
            "A": {"gear": {"value": {"all": {"pvp": [{"itemId": 5, "bonusIDs": [1, 2]}, {"itemId": 6}]}}}},
            "B": {"gear": {"value": {"all": {"pvp": [{"itemId": 5, "bonusIDs": [9]}]}}}},
        }
        self.assertEqual({5: [1, 2]}, rules.pvp_bonus_lookup(specs))


if __name__ == "__main__":
    unittest.main()
