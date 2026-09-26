from __future__ import annotations

import unittest

from tools.addon_benchmarks import pick_popular_slots
from tools.tests.addon_fixtures import make_item, make_popular_items


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


if __name__ == "__main__":
    unittest.main()
