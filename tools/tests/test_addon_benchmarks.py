from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.addon_benchmarks import (
    BRACKETS,
    MAX_FILE_BYTES,
    SAMPLE_SIZES,
    TARGET_KEYS,
    build_addon_data,
    build_level_context,
    build_profile,
    build_report,
    build_priority_profiles,
    measured_primary_stat,
    order_and_tiers,
    pick_popular_slots,
    rank_trinkets,
    render_lua,
    secondary_stats,
    valid_cohort,
    write_addon_file,
)
from tools.tests.addon_fixtures import (
    make_bracket_profile,
    make_bracket_raw_database,
    make_gear_cohort,
    make_item,
    make_popular_items,
    make_stat_cohort,
)


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
        profile = make_bracket_profile()
        rows = build_priority_profiles(profile, "MID", "TOP_100", profile["cohorts"]["MID_100"])
        self.assertEqual([31, 33, None], [r.get("heroSubTreeID") for r in rows])
        self.assertEqual(["haste", "mastery", "critical-strike", "versatility"], rows[0]["order"])
        self.assertEqual(["critical-strike", "mastery", "versatility", "haste"], rows[1]["order"])
        self.assertEqual(["critical-strike", "haste", "mastery", "versatility"], rows[2]["order"])
        self.assertTrue(all(r["context"] == "Mythic+" for r in rows))

    def test_insufficient_hero_tree_gets_no_row(self) -> None:
        profile = make_bracket_profile()
        rows = build_priority_profiles(profile, "MID", "TOP_100", profile["cohorts"]["MID_100"])
        self.assertNotIn(35, [r.get("heroSubTreeID") for r in rows])

    def test_hero_tree_rows_are_scoped_to_their_own_bracket(self) -> None:
        # A hero tree's inner cohort keys (TOP_20/50/100) are shared naming across brackets -
        # build_priority_profiles must not pull a MID hero-tree row into the LOW context.
        profile = make_bracket_profile()
        low_rows = build_priority_profiles(profile, "LOW", "TOP_20", profile["cohorts"]["LOW_20"])
        mid_rows = build_priority_profiles(profile, "MID", "TOP_100", profile["cohorts"]["MID_100"])
        self.assertEqual([31, 33, None], [r.get("heroSubTreeID") for r in low_rows])
        self.assertEqual([31, 33, None], [r.get("heroSubTreeID") for r in mid_rows])

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


class AssemblyTests(unittest.TestCase):
    def test_level_context_has_the_shape_the_addon_reads(self) -> None:
        profile = make_bracket_profile()
        context = build_level_context(profile, "MID", "MID_100")
        targets = context["targets"]
        self.assertEqual("MYTHIC_PLUS", targets["sourceGoal"])
        self.assertEqual(326.9, targets["averageItemLevel"])
        self.assertEqual(15, targets["itemCount"])
        self.assertEqual(
            {"critical_strike": 1140.0, "haste": 900.0, "mastery": 680.0, "versatility": 430.0},
            targets["statTargets"]["stats"],
        )
        self.assertEqual("Popular", context["bis"]["label"])
        self.assertEqual(15, len(context["bis"]["slots"]))
        self.assertEqual(["S", "S", "A"], [t["tier"] for t in context["trinkets"]])
        self.assertEqual(
            {"level": "MID", "cohort": "MID_100", "sampleSize": 100, "minimumSample": 25,
             "confidence": "high", "completeness": 1.0},
            context["benchmark"],
        )

    def test_invalid_cohort_gives_no_context(self) -> None:
        profile = make_bracket_profile()
        profile["cohorts"]["LOW_20"]["status"] = "insufficient"
        self.assertIsNone(build_level_context(profile, "LOW", "LOW_20"))
        self.assertIsNotNone(build_level_context(profile, "MID", "MID_100"))

    def test_too_few_slots_or_low_item_level_gives_no_context(self) -> None:
        profile = make_bracket_profile()
        profile["gearCohorts"]["MID_100"]["popularItems"] = {"HEAD": make_gear_cohort(100)["popularItems"]["HEAD"]}
        self.assertIsNone(build_level_context(profile, "MID", "MID_100"))
        profile = make_bracket_profile()
        profile["cohorts"]["MID_100"]["averageItemLevel"] = 200.0
        self.assertIsNone(build_level_context(profile, "MID", "MID_100"))

    def test_profile_keeps_only_valid_levels_and_measured_primary(self) -> None:
        profile = make_bracket_profile(spec_key_class="demon-hunter", primary="agility")
        for cohort in profile["cohorts"].values():
            cohort["statTargets"]["stats"].update({"strength": 300.0, "agility": 500.0, "intellect": 2400.0})
        profile["cohorts"]["LOW_20"]["status"] = "insufficient"
        built = build_profile("DEMONHUNTER_DEVOURER", profile)
        self.assertEqual("DEMONHUNTER", built["classToken"])
        self.assertEqual("intellect", built["primaryStat"])
        # LOW_20 was invalidated; the other two LOW sizes and both other brackets stay whole.
        self.assertEqual(["100", "50"], sorted(built["levels"]["LOW"]))
        self.assertEqual(["100", "20", "50"], sorted(built["levels"]["MID"]))
        self.assertEqual(["100", "20", "50"], sorted(built["levels"]["HIGH"]))

    def test_profile_that_is_not_ok_is_left_out(self) -> None:
        profile = make_bracket_profile()
        profile["status"] = "failed"
        self.assertIsNone(build_profile("DEATHKNIGHT_BLOOD", profile))

    def test_addon_data_uses_the_oldest_generated_at(self) -> None:
        older = make_bracket_raw_database("2026-09-01T00:00:00Z")
        newer = make_bracket_raw_database(
            "2026-09-20T00:00:00Z", {"MAGE_FIRE": make_bracket_profile("mage", "intellect")}
        )
        data = build_addon_data([newer, older])
        self.assertEqual("2026-09-01T00:00:00Z", data["generatedAt"])
        self.assertEqual(1, data["schemaVersion"])
        self.assertEqual(["DEATHKNIGHT_BLOOD", "MAGE_FIRE"], sorted(data["profiles"]))
        self.assertEqual("season-mn-2", data["source"]["season"])

    def test_lua_output_and_size_gate(self) -> None:
        data = build_addon_data([make_bracket_raw_database("2026-09-26T00:00:00Z")])
        text = render_lua(data)
        self.assertTrue(text.startswith("local addonName, ns = ...\n"))
        self.assertIn("ns.MythicPlusBenchmarks = {", text)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out" / "SV_MythicPlusBenchmarks.lua"
            size = write_addon_file(data, path)
            self.assertEqual(size, path.stat().st_size)
            self.assertLess(size, MAX_FILE_BYTES)
        oversized = {"schemaVersion": 1, "generatedAt": "x", "source": {}, "profiles": {"a": "x" * (MAX_FILE_BYTES + 1)}}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                write_addon_file(oversized, Path(tmp) / "big.lua")
            self.assertFalse((Path(tmp) / "big.lua").exists())

    def test_report_lists_each_spec(self) -> None:
        data = build_addon_data([make_bracket_raw_database("2026-09-26T00:00:00Z")])
        report = build_report(data)
        self.assertIn("DEATHKNIGHT_BLOOD", report)
        self.assertIn("MID_100", report)
        self.assertIn("tiers S:2 A:1 B:0 C:0", report)
        self.assertIn("clear favourites (>=40%): 15/15", report)


class TwoAxisLevelsTests(unittest.TestCase):
    def test_levels_nested_by_bracket_then_sample_size(self) -> None:
        profile = make_bracket_profile()
        built = build_profile("DEATHKNIGHT_BLOOD", profile)
        self.assertEqual(sorted(BRACKETS), sorted(built["levels"]))
        for bracket in BRACKETS:
            self.assertEqual(sorted(str(s) for s in SAMPLE_SIZES), sorted(built["levels"][bracket]))
        self.assertEqual("MID", built["levels"]["MID"]["100"]["benchmark"]["level"])
        self.assertEqual("MID_100", built["levels"]["MID"]["100"]["benchmark"]["cohort"])

    def test_high_bracket_gear_differs_from_low_and_mid(self) -> None:
        profile = make_bracket_profile()
        built = build_profile("DEATHKNIGHT_BLOOD", profile)
        high_helm = built["levels"]["HIGH"]["100"]["bis"]["slots"][0]["item"]["item_id"]
        mid_helm = built["levels"]["MID"]["100"]["bis"]["slots"][0]["item"]["item_id"]
        self.assertNotEqual(high_helm, mid_helm)


class OffHandTests(unittest.TestCase):
    def labels(self, popular) -> list[str]:
        return [s["slot"] for s in pick_popular_slots(popular)]

    def test_rarely_used_off_hand_is_not_listed(self) -> None:
        popular = make_popular_items()
        popular["OFF_HAND"] = [make_item(7001, "Rare Off Hand", 3, 3.0, [1])]
        self.assertNotIn("Off Hand", self.labels(popular))

    def test_off_hand_next_to_a_two_hander_is_not_listed(self) -> None:
        # Top main hand 43% + off hands 51% cannot overlap, so the main hand is a two-hander.
        popular = make_popular_items()
        popular["MAIN_HAND"] = [make_item(7002, "Staff", 43, 43.0, [1]), make_item(7003, "Wand", 20, 20.0, [1])]
        popular["OFF_HAND"] = [make_item(7004, "Lantern", 39, 39.0, [1]), make_item(7005, "Orb", 12, 12.0, [1])]
        self.assertNotIn("Off Hand", self.labels(popular))

    def test_off_hand_that_pairs_with_a_one_hander_is_listed(self) -> None:
        popular = make_popular_items()
        popular["MAIN_HAND"] = [make_item(7006, "Sword", 60, 60.0, [1])]
        popular["OFF_HAND"] = [make_item(7007, "Shield", 95, 95.0, [1])]
        labels = self.labels(popular)
        self.assertEqual("Off Hand", labels[-1])
        self.assertEqual(16, len(labels))


if __name__ == "__main__":
    unittest.main()
