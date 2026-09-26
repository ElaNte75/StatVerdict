from __future__ import annotations

import unittest

from tools.addon_benchmarks import (
    TARGET_KEYS,
    build_priority_profiles,
    measured_primary_stat,
    order_and_tiers,
    pick_popular_slots,
    rank_trinkets,
    secondary_stats,
    valid_cohort,
)
from tools.tests.addon_fixtures import make_item, make_popular_items, make_profile, make_stat_cohort


class PickPopularSlotsTests(unittest.TestCase):
    def test_single_slot_takes_top_item_and_its_most_used_variant(self) -> None:
        popular = {
            "HEAD": [
                {
                    **make_item(1, "Helm", 60, 60.0, [1]),
                    "variants": [
                        {"itemLevel": 320.0, "bonusIds": [7], "count": 10},
                        {"itemLevel": 330.0, "bonusIds": [8, 9], "count": 50},
                    ],
                },
                make_item(2, "Other Helm", 20, 20.0, [2]),
            ]
        }
        slots = pick_popular_slots(popular)
        self.assertEqual(1, len(slots))
        self.assertEqual("Helm", slots[0]["slot"])
        self.assertEqual({"item_id": 1, "name": "Helm", "bonus_ids": [8, 9]}, slots[0]["item"])
        self.assertEqual(60.0, slots[0]["usagePercent"])

    def test_rings_pool_both_slots_and_stay_distinct(self) -> None:
        slots = pick_popular_slots(make_popular_items())
        rings = [s for s in slots if s["slot"] == "Ring"]
        self.assertEqual([1902, 1901], [s["item"]["item_id"] for s in rings])
        self.assertEqual([75.0, 70.0], [s["usagePercent"] for s in rings])

    def test_trinket_slots_are_two_distinct_items(self) -> None:
        slots = pick_popular_slots(make_popular_items())
        trinkets = [s for s in slots if s["slot"] == "Trinket"]
        self.assertEqual([5001, 5003], [s["item"]["item_id"] for s in trinkets])

    def test_missing_slot_is_skipped_and_order_follows_the_panel(self) -> None:
        slots = pick_popular_slots(make_popular_items())
        labels = [s["slot"] for s in slots]
        self.assertNotIn("Off Hand", labels)
        self.assertEqual(
            ["Helm", "Hands", "Neck", "Waist", "Shoulders", "Legs", "Cloak", "Feet", "Chest",
             "Ring", "Ring", "Trinket", "Bracers", "Trinket", "Main Hand"],
            labels,
        )


class RankTrinketsTests(unittest.TestCase):
    def test_pooled_usage_orders_and_assigns_tiers(self) -> None:
        ranked = rank_trinkets(make_popular_items())
        self.assertEqual([5001, 5003, 5002], [t["item_id"] for t in ranked])
        self.assertEqual(["S", "S", "A"], [t["tier"] for t in ranked])
        self.assertEqual([50.0, 45.0, 35.0], [t["usagePercent"] for t in ranked])

    def test_below_three_percent_is_not_listed(self) -> None:
        ranked = rank_trinkets(make_popular_items())
        self.assertNotIn(5004, [t["item_id"] for t in ranked])

    def test_tier_boundaries(self) -> None:
        popular = {
            "TRINKET_1": [
                make_item(1, "s", 40, 40.0, [1]),
                make_item(2, "a", 20, 20.0, [1]),
                make_item(3, "b", 8, 8.0, [1]),
                make_item(4, "c", 3, 3.0, [1]),
                make_item(5, "none", 2, 2.99, [1]),
            ]
        }
        ranked = rank_trinkets(popular)
        self.assertEqual(["S", "A", "B", "C"], [t["tier"] for t in ranked])

    def test_same_item_in_both_slots_is_listed_once(self) -> None:
        popular = {
            "TRINKET_1": [make_item(9, "x", 30, 30.0, [1])],
            "TRINKET_2": [make_item(9, "x", 20, 20.0, [1])],
        }
        ranked = rank_trinkets(popular)
        self.assertEqual(1, len(ranked))
        self.assertEqual(50.0, ranked[0]["usagePercent"])
        self.assertEqual("S", ranked[0]["tier"])

    def test_list_is_capped_at_the_panel_row_count(self) -> None:
        popular = {"TRINKET_1": [make_item(i, f"t{i}", 5, 5.0, [1]) for i in range(1, 30)]}
        self.assertEqual(16, len(rank_trinkets(popular)))


class TargetsAndPriorityTests(unittest.TestCase):
    def test_secondary_stats_are_renamed_for_the_addon(self) -> None:
        cohort = make_stat_cohort(100, 1140, 900, 680, 430)
        self.assertEqual(
            {"critical_strike": 1140.0, "haste": 900.0, "mastery": 680.0, "versatility": 430.0},
            secondary_stats(cohort, TARGET_KEYS),
        )

    def test_order_and_tiers_group_stats_within_five_percent(self) -> None:
        order, tiers = order_and_tiers({"haste": 1000.0, "mastery": 900.0, "critical-strike": 600.0, "versatility": 590.0})
        self.assertEqual(["haste", "mastery", "critical-strike", "versatility"], order)
        self.assertEqual([["haste"], ["mastery"], ["critical-strike", "versatility"]], tiers)

    def test_priority_rows_per_valid_hero_tree_plus_spec_wide_row(self) -> None:
        profile = make_profile()
        rows = build_priority_profiles(profile, "TOP_100", profile["cohorts"]["TOP_100"])
        self.assertEqual([31, 33, None], [r.get("heroSubTreeID") for r in rows])
        self.assertEqual(["haste", "mastery", "critical-strike", "versatility"], rows[0]["order"])
        self.assertEqual(["critical-strike", "mastery", "versatility", "haste"], rows[1]["order"])
        self.assertEqual(["critical-strike", "haste", "mastery", "versatility"], rows[2]["order"])
        self.assertTrue(all(r["context"] == "Mythic+" for r in rows))

    def test_insufficient_hero_tree_gets_no_row(self) -> None:
        profile = make_profile()
        rows = build_priority_profiles(profile, "TOP_100", profile["cohorts"]["TOP_100"])
        self.assertNotIn(35, [r.get("heroSubTreeID") for r in rows])

    def test_valid_cohort_needs_ok_status_and_minimum_sample(self) -> None:
        self.assertTrue(valid_cohort(make_stat_cohort(100, 1, 1, 1, 1)))
        self.assertFalse(valid_cohort(make_stat_cohort(100, 1, 1, 1, 1, status="insufficient")))
        self.assertFalse(valid_cohort(make_stat_cohort(20, 1, 1, 1, 1, minimum=25)))
        self.assertFalse(valid_cohort(None))

    def test_primary_stat_is_measured_not_trusted(self) -> None:
        # Devourer Demon Hunter is an Intellect spec but the raw label says agility.
        cohort = make_stat_cohort(100, 1, 1, 1, 1, primaries=(300.0, 500.0, 2400.0))
        self.assertEqual("intellect", measured_primary_stat(cohort, "agility"))
        empty = make_stat_cohort(100, 1, 1, 1, 1, primaries=(0.0, 0.0, 0.0))
        self.assertEqual("agility", measured_primary_stat(empty, "agility"))


if __name__ == "__main__":
    unittest.main()
