from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from tools.classcodex_targets import (
    ComboSkipped,
    LoadoutUpgrades,
    add_base_stats,
    build_all,
    build_loadout_items,
    format_rating_sanity,
    gear_sum_target_context,
    load_spec_base_stats,
    priority_row_from_context,
    select_goal_context,
    select_loadout_upgrades,
    trinkets_from_entries,
)
from tools.spec_catalog import SPEC_BY_KEY
from tools.tests.wowhead_fakes import fake_wowhead
from tools.upgrade_tracks import TrackSwap


class SelectGoalContextTests(unittest.TestCase):
    def test_exact_first_choice_key_wins_over_fallback_keys(self) -> None:
        nested = {"deathbringer": {"mplus": ["M"], "aoe": ["A"], "all": ["X"]}}
        self.assertEqual(["M"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_mythic_plus_falls_back_to_aoe_when_mplus_is_absent(self) -> None:
        nested = {"deathbringer": {"aoe": ["A"], "single-target": ["S"], "all": ["X"]}}
        self.assertEqual(["A"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_raid_falls_back_to_single_target_when_raid_is_absent(self) -> None:
        nested = {"deathbringer": {"aoe": ["A"], "single-target": ["S"], "all": ["X"]}}
        self.assertEqual(["S"], select_goal_context(nested, "deathbringer", "RAID"))

    def test_all_is_the_last_resort_context(self) -> None:
        nested = {"deathbringer": {"pvp": ["P"], "all": ["X"]}}
        self.assertEqual(["X"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))
        self.assertEqual(["X"], select_goal_context(nested, "deathbringer", "RAID"))

    def test_pvp_never_uses_aoe_or_single_target(self) -> None:
        nested = {"deathbringer": {"aoe": ["A"], "single-target": ["S"]}}
        self.assertIsNone(select_goal_context(nested, "deathbringer", "PVP"))

    def test_falls_back_to_the_all_hero_key_when_the_hero_has_no_match(self) -> None:
        # Real ClassCodex layout: Mythic+ gear only exists under hero "all",
        # the specific hero keys only carry PvP gear.
        nested = {"all": {"mplus": ["ALL-M"]}, "deathbringer": {"pvp": ["DB-P"]}}
        self.assertEqual(["ALL-M"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))
        self.assertEqual(["DB-P"], select_goal_context(nested, "deathbringer", "PVP"))

    def test_a_hero_specific_all_context_beats_the_all_hero(self) -> None:
        nested = {"all": {"mplus": ["ALL-M"]}, "deathbringer": {"all": ["DB-X"]}}
        self.assertEqual(["DB-X"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_empty_values_are_skipped_so_the_chain_keeps_looking(self) -> None:
        nested = {"deathbringer": {"mplus": [], "aoe": ["A"]}}
        self.assertEqual(["A"], select_goal_context(nested, "deathbringer", "MYTHIC_PLUS"))

    def test_returns_none_when_nothing_matches(self) -> None:
        self.assertIsNone(select_goal_context({"deathbringer": {"pvp": ["P"]}}, "deathbringer", "RAID"))
        self.assertIsNone(select_goal_context(None, "deathbringer", "RAID"))


class BuildLoadoutItemsTests(unittest.TestCase):
    def test_converts_slot_names_and_carries_ilvl_and_bonus_ids(self) -> None:
        gear = [
            {"itemId": 271474, "slot": "Head", "bonusIDs": [13695, 13692], "ilvl": 334},
            {"itemId": 268265, "slot": "Neck", "bonusIDs": [6652, 13668]},
        ]
        items = build_loadout_items(gear)
        self.assertEqual(
            {"itemId": 271474, "itemLevel": 334, "bonusIds": [13695, 13692]},
            items["HEAD"],
        )
        self.assertEqual({"itemId": 268265, "bonusIds": [6652, 13668]}, items["NECK"])
        self.assertNotIn("itemLevel", items["NECK"])

    def test_skips_entries_with_unknown_slot_names(self) -> None:
        gear = [{"itemId": 1, "slot": "Relic", "bonusIDs": []}]
        self.assertEqual({}, build_loadout_items(gear))


def build_trinkets(trinkets_value, hero, context_key):
    return trinkets_from_entries(trinkets_value[hero][context_key])


def build_priority_row(stat_priority, hero, context_key, label, hero_name):
    return priority_row_from_context(stat_priority[hero].get(context_key), label, hero_name)


class BuildTrinketsAndPriorityTests(unittest.TestCase):
    def test_build_trinkets_passes_through_tier_and_bonus_ids(self) -> None:
        trinkets = {"all": {"raid": [{"itemId": 270175, "bonusIDs": [13848], "tier": "S"}]}}
        result = build_trinkets(trinkets, "all", "raid")
        self.assertEqual([{"item_id": 270175, "bonus_ids": [13848], "tier": "S"}], result)

    def test_build_trinkets_defaults_missing_bonus_ids_to_empty_list(self) -> None:
        trinkets = {"all": {"all": [{"itemId": 1, "tier": "A"}]}}
        result = build_trinkets(trinkets, "all", "all")
        self.assertEqual([{"item_id": 1, "bonus_ids": [], "tier": "A"}], result)

    def test_build_priority_row_converts_tier_groups_to_order_and_tiers(self) -> None:
        stat_priority = {
            "deathbringer": {"mplus": {"secondary": [["crit"], ["haste", "mastery"], ["versatility"]]}}
        }
        row = build_priority_row(stat_priority, "deathbringer", "mplus", "Mythic+", "deathbringer")
        self.assertEqual(
            {
                "context": "Mythic+",
                "heroTalent": "deathbringer",
                # ClassCodex's raw "crit" is normalized to the addon's canonical key.
                "order": ["critical_strike", "haste", "mastery", "versatility"],
                "tiers": [["haste", "mastery"]],
            },
            row,
        )

    def test_build_priority_row_normalizes_tiers_and_drops_unknown_or_repeated_tokens(self) -> None:
        stat_priority = {
            "deathbringer": {"mplus": {"secondary": [["Crit", "vers"], ["leech"], ["crit", "mastery"]]}}
        }
        row = build_priority_row(stat_priority, "deathbringer", "mplus", "Mythic+", "deathbringer")
        self.assertEqual(["critical_strike", "versatility", "mastery"], row["order"])
        self.assertEqual([["critical_strike", "versatility"]], row["tiers"])

    def test_build_priority_row_returns_none_when_no_secondary_list(self) -> None:
        stat_priority = {"deathbringer": {"raid": {}}}
        self.assertIsNone(build_priority_row(stat_priority, "deathbringer", "raid", "Raid", "deathbringer"))

    def test_build_priority_row_drops_non_string_group_elements(self) -> None:
        stat_priority = {
            "deathbringer": {"mplus": {"secondary": [["crit", 123], ["haste"]]}}
        }
        row = build_priority_row(stat_priority, "deathbringer", "mplus", "Mythic+", "deathbringer")
        # Non-string element (123) should be dropped from both order and tiers
        self.assertEqual(
            {
                "context": "Mythic+",
                "heroTalent": "deathbringer",
                "order": ["critical_strike", "haste"],
                "tiers": [],  # First group only has 1 valid string, so not a tie
            },
            row,
        )


ENCHANTS = {
    "all": {
        "all": {
            "Head": [{"id": 7991, "pop": 36.8}, {"id": 8017, "itemId": 243981, "spellId": 1236001, "pop": 46.7}],
            "Main Hand": [{"id": 3368, "spellId": 53344, "pop": 63.2}],
            "Relic": [{"id": 1, "pop": 99}],
        },
        "pvp": {"Head": [{"id": 243981, "pop": 33.3}]},
    }
}
GEMS = {
    "all": {
        "all": [
            {"primary": 240983, "pop": 9.5, "secondary": [240892]},
            {"primary": 240983, "pop": 12.6, "secondary": [240908, 240910]},
        ],
        "pvp": [{"pop": 50, "secondary": [240900]}],
    }
}
UPGRADE_GEAR = [
    {"itemId": 1, "slot": "Head", "ilvl": 300, "bonusIDs": [7]},
    {"itemId": 2, "slot": "Neck", "ilvl": 300},
    {"itemId": 3, "slot": "Trinket 1", "ilvl": 300},
    {"itemId": 4, "slot": "Main Hand", "ilvl": 300},
]


class LoadoutUpgradeTests(unittest.TestCase):
    def test_picks_the_most_popular_enchant_per_slot_and_gem_set(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "deathbringer", "RAID")
        self.assertEqual(
            {
                "HEAD": {"id": 8017, "item_id": 243981, "spell_id": 1236001},
                "MAIN_HAND": {"id": 3368, "spell_id": 53344},
            },
            upgrades.enchants,
        )
        # One unique primary gem + the first secondary gem of the chosen set.
        self.assertEqual({"primary": 240983, "secondary": 240908}, upgrades.gems)

    def test_the_goal_context_wins_over_all(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "deathbringer", "PVP")
        # The PvP list's bare id is the scroll's item id: it is translated to the real enchant
        # the PvE list knows for that scroll.
        self.assertEqual({"HEAD": {"id": 8017, "item_id": 243981, "spell_id": 1236001}}, upgrades.enchants)
        self.assertEqual({"secondary": 240900}, upgrades.gems)  # no primary in this set

    def test_missing_data_gives_no_upgrades(self) -> None:
        upgrades = select_loadout_upgrades(None, None, "all", "RAID")
        self.assertEqual({}, upgrades.enchants)
        self.assertEqual({}, upgrades.gems)

    def test_build_loadout_items_adds_enchants_and_gems_except_on_trinkets_and_weapons(self) -> None:
        items = build_loadout_items(UPGRADE_GEAR, select_loadout_upgrades(ENCHANTS, GEMS, "all", "RAID"))
        self.assertEqual([8017], items["HEAD"]["enchantIds"])
        # The unique primary gem is worn once: on the neck (first of NECK,
        # FINGER_1, FINGER_2, HEAD present); every other item gets the secondary.
        self.assertEqual([240983, 240908], items["NECK"]["gemIds"])
        self.assertEqual([240908], items["HEAD"]["gemIds"])
        self.assertNotIn("enchantIds", items["NECK"])
        self.assertNotIn("gemIds", items["TRINKET_1"])
        self.assertNotIn("gemIds", items["MAIN_HAND"])
        self.assertEqual([3368], items["MAIN_HAND"]["enchantIds"])

    def test_the_primary_gem_goes_on_the_first_present_slot_in_order(self) -> None:
        gems = {"all": {"all": [{"primary": 9, "secondary": [8, 7]}]}}
        upgrades = select_loadout_upgrades(None, gems, "all", "RAID")

        def carriers(slots):
            gear = [{"itemId": i + 1, "slot": slot} for i, slot in enumerate(slots)]
            items = build_loadout_items(gear, upgrades)
            return {s: v["gemIds"] for s, v in items.items() if "gemIds" in v}

        self.assertEqual({"FINGER_1": [9, 8], "FINGER_2": [8], "HEAD": [8], "CHEST": [8]},
                         carriers(["Chest", "Head", "Finger 2", "Finger 1"]))
        self.assertEqual({"FINGER_2": [9, 8], "HEAD": [8]}, carriers(["Head", "Finger 2"]))
        self.assertEqual({"HEAD": [9, 8], "CHEST": [8]}, carriers(["Chest", "Head"]))
        # None of the four present: the primary is not simulated at all.
        self.assertEqual({"CHEST": [8]}, carriers(["Chest", "Trinket 1"]))

    def test_primary_only_or_secondary_only_sets(self) -> None:
        only_primary = select_loadout_upgrades(None, {"all": {"all": [{"primary": 9}]}}, "all", "RAID")
        items = build_loadout_items([{"itemId": 1, "slot": "Neck"}, {"itemId": 2, "slot": "Head"}], only_primary)
        self.assertEqual([9], items["NECK"]["gemIds"])
        self.assertNotIn("gemIds", items["HEAD"])
        only_secondary = select_loadout_upgrades(None, {"all": {"all": [{"secondary": [8]}]}}, "all", "RAID")
        items = build_loadout_items([{"itemId": 1, "slot": "Neck"}, {"itemId": 2, "slot": "Head"}], only_secondary)
        self.assertEqual([8], items["NECK"]["gemIds"])
        self.assertEqual([8], items["HEAD"]["gemIds"])


class TargetUpgradeTests(unittest.TestCase):
    spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]

    def test_the_looked_up_loadout_and_bis_slots_carry_the_same_gems_and_enchants(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "all", "RAID")
        calls: list = []
        context = gear_sum_target_context(self.spec, "RAID", UPGRADE_GEAR, fake_wowhead(calls=calls), upgrades=upgrades)
        self.assertEqual({"itemId": 1, "itemLevel": 300, "bonusIds": [7], "gemIds": [240908], "enchantIds": [8017]}, calls[0]["HEAD"])
        self.assertEqual({"itemId": 2, "itemLevel": 300, "gemIds": [240983, 240908]}, calls[0]["NECK"])
        metadata = context["targets"]["targetMetadata"]
        self.assertEqual(2, metadata["enchantCount"])
        self.assertEqual(2, metadata["gemCount"])  # head + neck
        self.assertEqual({"primary": 240983, "secondary": 240908}, context["bis"]["gems"])
        self.assertEqual(
            [
                {
                    "slot": "Head",
                    "item": {
                        "item_id": 1,
                        "bonus_ids": [7],
                        "enchant": {"id": 8017, "item_id": 243981, "spell_id": 1236001},
                    },
                },
                {"slot": "Neck", "item": {"item_id": 2}},
                {"slot": "Trinket 1", "item": {"item_id": 3}},
                {
                    "slot": "Main Hand",
                    "item": {
                        "item_id": 4,
                        "enchant": {"id": 3368, "spell_id": 53344},
                    },
                },
            ],
            context["bis"]["slots"],
        )

    def test_build_all_uses_the_specs_enchants_and_gems(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": UPGRADE_GEAR}}},
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
                "enchants": {"value": ENCHANTS, "source": "ugg"},
                "gems": {"value": GEMS, "source": "ugg"},
            }
        }
        calls: list = []
        data = build_all(specs, goals=("RAID",), wowhead_reconstruct=fake_wowhead(calls=calls))
        self.assertEqual([8017], calls[0]["HEAD"]["enchantIds"])
        metadata = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["deathbringer"]["targets"][
            "targetMetadata"
        ]
        self.assertEqual(2, metadata["enchantCount"])


class RatingSanityReportTests(unittest.TestCase):
    @staticmethod
    def context(champion: float, hero: float, top: float) -> dict:
        def stats(total: float) -> dict:
            return {"statTargets": {"stats": {"critical_strike": total}}}

        return {"targets": {"statTargets": {"stats": {"critical_strike": top}},
                            "levels": {"champion": stats(champion), "hero": stats(hero)}}}

    def test_reports_the_contexts_whose_tier_targets_do_not_grow(self) -> None:
        data = {
            "profiles": {
                "DEATHKNIGHT_FROST": {
                    "goals": {
                        "RAID": {
                            "heroTalents": {
                                "deathbringer": self.context(1000, 1100, 1200),
                                "rider": self.context(1000, 1300, 1200),
                                "slayer": {"targets": {"statTargets": {"stats": {"haste": 100.0}}}},
                            }
                        },
                        "PVP": {"heroTalents": {"deathbringer": self.context(2000, 1900, 1900)}},
                    }
                }
            }
        }
        report = format_rating_sanity(data)
        self.assertIn("3 context(s) checked, 2 problem(s)", report)
        self.assertIn("DEATHKNIGHT_FROST/RAID/rider: not growing with the tier (Champion 1000, Hero 1300, Myth 1200)", report)
        self.assertIn("DEATHKNIGHT_FROST/RAID/slayer: missing Champion/Hero level (Myth 100)", report)
        self.assertNotIn("deathbringer", report)  # grows; PvP has no tracks and is not judged


class BuildAllTests(unittest.TestCase):
    def test_builds_one_profile_per_spec_with_a_context_per_goal_and_hero_talent(self) -> None:
        specs = {
            "DEATHKNIGHT_blood": {
                "gear": {"value": {"all": {"mplus": [{"itemId": 1, "slot": "Head", "ilvl": 330}], "raid": [{"itemId": 2, "slot": "Head", "ilvl": 330}]}}, "source": "ugg"},
                "talents": {"value": {"all": {"mplus": [{"export": "M", "recommended": True}], "raid": [{"export": "R", "recommended": True}]}}, "source": "ugg"},
                "trinkets": {"value": {"all": {"all": [{"itemId": 9, "tier": "S"}]}}, "source": "ugg"},
                "statPriority": {"value": {"all": {"mplus": {"secondary": [["crit"], ["haste"]]}}}, "source": "ugg"},
            }
        }
        data = build_all(specs, goals=("MYTHIC_PLUS", "RAID"), wowhead_reconstruct=fake_wowhead())

        # Keyed by the addon's own (uppercase) spec key, not ClassCodex's raw casing.
        self.assertEqual(["DEATHKNIGHT_BLOOD"], list(data["profiles"]))
        profile = data["profiles"]["DEATHKNIGHT_BLOOD"]
        self.assertEqual("DEATHKNIGHT_BLOOD", profile["specKey"])
        self.assertEqual("DEATHKNIGHT", profile["classToken"])
        mplus_context = profile["goals"]["MYTHIC_PLUS"]["heroTalents"]["all"]
        self.assertIn("targets", mplus_context)
        self.assertEqual([{"item_id": 9, "bonus_ids": [], "tier": "S"}], mplus_context["trinkets"])
        self.assertEqual(1, len(mplus_context["priorityProfiles"]))
        self.assertNotIn("PVP", profile["goals"])  # no PVP data anywhere in this fixture

    def test_overall_has_its_own_list(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {
                    "all": [{"itemId": 11, "slot": "Head", "ilvl": 330}],
                    "mplus": [{"itemId": 22, "slot": "Head", "ilvl": 330}],
                }}},
                "talents": {"value": {"deathbringer": {"mplus": [{"export": "M"}]}}},
                "statPriority": {"value": {"all": {"all": {"secondary": [["crit"], ["haste"]]}}}},
            }
        }
        calls: list = []
        data = build_all(specs, goals=("OVERALL", "MYTHIC_PLUS"), wowhead_reconstruct=fake_wowhead(calls=calls))
        goals = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]
        overall = goals["OVERALL"]["heroTalents"]["deathbringer"]
        mplus = goals["MYTHIC_PLUS"]["heroTalents"]["deathbringer"]
        self.assertEqual(11, overall["bis"]["slots"][0]["item"]["item_id"])
        self.assertEqual(22, mplus["bis"]["slots"][0]["item"]["item_id"])
        self.assertEqual("Overall", overall["priorityProfiles"][0]["context"])
        self.assertEqual(2, len(calls))

    def test_skips_a_spec_key_not_in_the_catalog(self) -> None:
        specs = {"NOTASPEC_madeup": {"gear": {"value": {}, "source": "ugg"}}}
        data = build_all(specs, wowhead_reconstruct=fake_wowhead())
        self.assertEqual({}, data["profiles"])


class PvpEnchantScrollTests(unittest.TestCase):
    ENCHANTS = {
        "all": {
            "all": {"Head": [{"id": 7961, "itemId": 243981, "spellId": 1236100, "pop": 50}]},
            "pvp": {
                "Head": [{"id": 243981, "pop": 60}],
                "Chest": [{"id": 999999, "pop": 60}],
            },
        }
    }

    def test_a_bare_pvp_scroll_id_becomes_the_real_enchant(self) -> None:
        from tools.classcodex_targets import select_loadout_upgrades

        upgrades = select_loadout_upgrades(self.ENCHANTS, None, "hero", "PVP")
        head = upgrades.enchants["HEAD"]
        self.assertEqual({"id": 7961, "item_id": 243981, "spell_id": 1236100}, head)

    def test_an_unknown_bare_scroll_id_is_kept_for_display_but_never_simulated(self) -> None:
        upgrades = select_loadout_upgrades(self.ENCHANTS, None, "hero", "PVP")
        self.assertEqual({"item_id": 999999}, upgrades.enchants["CHEST"])
        items = build_loadout_items([{"itemId": 5, "slot": "Chest"}], upgrades)
        self.assertNotIn("enchantIds", items["CHEST"])


# Real shapes (2026-09-29): Icy Veins' enchant ids are scroll item ids, its
# weapon runes are {id = spellId, spellId}; u.gg's PvE entries carry the real
# enchant id, the scroll's itemId and the spellId.
ICY_ENCHANTS = {
    "all": {
        "all": {
            "Head": [{"id": 244007}],
            "Shoulders": [{"id": 243962}],
            "Chest": [{"id": 777777}],
            "Main Hand": [{"id": 53344, "spellId": 53344}],
            "Off Hand": [{"id": 62158, "spellId": 62158}],
        }
    }
}
LOOKUP = {
    "byItem": {244007: {"id": 8017, "item_id": 244007, "spell_id": 1236084}},
    "bySpell": {
        1236084: {"id": 8017, "item_id": 244007, "spell_id": 1236084},
        1236062: {"id": 7973, "item_id": 243963, "spell_id": 1236062},
        53344: {"id": 3368, "spell_id": 53344},
    },
    # db_gamedata recipes inverted: scroll item -> enchant spell.
    "recipeSpellByItem": {244007: 1236084, 243962: 1236062},
}


class CoverageReportTests(unittest.TestCase):
    def test_build_all_records_the_gear_source_and_the_report_counts_it(self) -> None:
        from tools.classcodex_targets import format_coverage_report

        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {
                    "value": {
                        "all": {"raid": [{"itemId": 1, "slot": "Head", "bonusIDs": [13848]}], "pvp": [{"itemId": 2, "slot": "Head"}]},
                    },
                    "source": "icyveins",
                    "origins": {"all": {"raid": "icyveins", "pvp": "ugg"}},
                },
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}], "pvp": [{"export": "P"}]}}},
                "trinkets": {"value": {"all": {"all": [{"itemId": 9, "tier": "S"}, {"itemId": 8, "tier": "A"}]}}},
                "enchants": {"value": ICY_ENCHANTS, "source": "icyveins"},
                "enchantLookup": {"value": LOOKUP},
                "gems": {"value": {"all": {"all": [{"primary": 1, "secondary": [2]}]}}},
            }
        }
        data = build_all(specs, goals=("RAID", "PVP"), wowhead_reconstruct=fake_wowhead())
        goals = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]
        raid = goals["RAID"]["heroTalents"]["deathbringer"]["targets"]["targetMetadata"]
        pvp = goals["PVP"]["heroTalents"]["deathbringer"]["targets"]["targetMetadata"]
        self.assertEqual("icyveins", raid["gearSource"])
        self.assertEqual("ugg", pvp["gearSource"])

        report = format_coverage_report(data)
        self.assertIn("  RAID:", report)
        self.assertIn("contexts by gear source: icyveins: 1", report)
        self.assertIn("contexts by gear source: ugg: 1", report)
        self.assertIn("trinket count distribution (length: contexts): 2: 1", report)
        # Only the Head slot exists: its Icy Veins scroll translates.
        self.assertIn("enchants on BiS slots: total 1, translated 1, untranslated (shown, not counted) 0", report)
        self.assertIn("gems: with gems: 1", report)
        self.assertIn("averageItemLevel: present: 1 (source wowhead: 1)", report)

    def test_empty_document(self) -> None:
        from tools.classcodex_targets import format_coverage_report

        self.assertIn("no contexts", format_coverage_report({"profiles": {}}))


class GearSumItemLevelTests(unittest.TestCase):
    """The average item level is the one the lookup reports for the pieces (Icy Veins gear has bonusIDs but no ilvl)."""

    spec = SPEC_BY_KEY["DEATHKNIGHT_FROST"]
    gear = [
        {"itemId": 1, "slot": "Head", "bonusIDs": [13848]},
        {"itemId": 2, "slot": "Neck", "bonusIDs": [13848]},
    ]

    @staticmethod
    def lookup(levels):
        def reconstruct(items, primary=None, **_kwargs):
            slots = {slot: ({"wowheadItemLevel": levels[slot]} if slot in levels else {}) for slot in items}
            return {"totals": {"crit": 1.0, "haste": 2.0}, "slots": slots, "failures": []}

        return reconstruct

    def test_average_item_level_comes_from_the_lookup(self) -> None:
        context = gear_sum_target_context(self.spec, "RAID", self.gear, self.lookup({"HEAD": 289, "NECK": 285}))
        targets = context["targets"]
        self.assertEqual(287.0, targets["averageItemLevel"])
        self.assertEqual(2, targets["itemLevelSlots"])
        self.assertEqual("wowhead", targets["targetMetadata"]["itemLevelSource"])

    def test_without_item_levels_the_average_stays_none(self) -> None:
        context = gear_sum_target_context(self.spec, "RAID", self.gear, self.lookup({}))
        self.assertIsNone(context["targets"]["averageItemLevel"])
        self.assertEqual(0, context["targets"]["itemLevelSlots"])
        self.assertEqual("none", context["targets"]["targetMetadata"]["itemLevelSource"])

    def test_a_catalyst_entry_looks_up_and_shows_the_tier_piece_at_max_upgrade(self) -> None:
        gear = [
            {
                "slot": "Head",
                "source": "Catalyst from Ula'tek",
                "itemId": 271537,
                "catalyst": {"itemId": 271875, "bonusIDs": [13848, 13847]},
            }
        ]
        calls: list = []
        context = gear_sum_target_context(self.spec, "RAID", gear, fake_wowhead(calls=calls))
        # The top-level item is the BiS tier piece; the catalyst block names the base item that
        # converts into it and carries the max-upgrade bonus ids.
        self.assertEqual({"itemId": 271537, "bonusIds": [13848, 13847]}, calls[0]["HEAD"])
        self.assertEqual({"item_id": 271537, "bonus_ids": [13848, 13847]}, context["bis"]["slots"][0]["item"])


class IcyVeinsEnchantTranslationTests(unittest.TestCase):
    def test_scroll_ids_and_rune_spells_become_real_enchants(self) -> None:
        upgrades = select_loadout_upgrades(ICY_ENCHANTS, None, "deathbringer", "RAID", LOOKUP)
        self.assertEqual({"id": 8017, "item_id": 244007, "spell_id": 1236084}, upgrades.enchants["HEAD"])
        # Not a u.gg itemId, but the recipe names its spell, which u.gg knows.
        self.assertEqual({"id": 7973, "item_id": 243962, "spell_id": 1236062}, upgrades.enchants["SHOULDER"])
        self.assertEqual({"id": 3368, "spell_id": 53344}, upgrades.enchants["MAIN_HAND"])

    def test_untranslatable_enchants_keep_only_their_item_or_spell_id(self) -> None:
        upgrades = select_loadout_upgrades(ICY_ENCHANTS, None, "deathbringer", "RAID", LOOKUP)
        self.assertEqual({"item_id": 777777}, upgrades.enchants["CHEST"])
        self.assertEqual({"spell_id": 62158}, upgrades.enchants["OFF_HAND"])
        gear = [
            {"itemId": 1, "slot": "Chest", "bonusIDs": [13848]},
            {"itemId": 2, "slot": "Off Hand", "bonusIDs": [13848]},
            {"itemId": 3, "slot": "Head", "bonusIDs": [13848]},
        ]
        items = build_loadout_items(gear, upgrades)
        self.assertNotIn("enchantIds", items["CHEST"])
        self.assertNotIn("enchantIds", items["OFF_HAND"])
        self.assertEqual([8017], items["HEAD"]["enchantIds"])
        calls: list = []
        context = gear_sum_target_context(
            SPEC_BY_KEY["DEATHKNIGHT_FROST"], "RAID", gear, fake_wowhead(calls=calls), upgrades=upgrades)
        looked_up = str(calls[0])
        self.assertNotIn("777777", looked_up)
        self.assertNotIn("62158", looked_up)
        slots = {slot["slot"]: slot["item"] for slot in context["bis"]["slots"]}
        self.assertEqual({"item_id": 777777}, slots["Chest"]["enchant"])
        self.assertEqual({"spell_id": 62158}, slots["Off Hand"]["enchant"])
        self.assertEqual(8017, slots["Head"]["enchant"]["id"])
        self.assertEqual(1, context["targets"]["targetMetadata"]["enchantCount"])

    def test_icy_veins_single_gem_set_primary_and_first_secondary(self) -> None:
        gems = {"all": {"all": [{"primary": 240967, "secondary": [240908, 240898]}]}}
        self.assertEqual({"primary": 240967, "secondary": 240908}, select_loadout_upgrades(None, gems, "hero", "RAID").gems)

    def test_bis_has_no_gems_key_without_gems_and_no_per_slot_gem_ids(self) -> None:
        context = gear_sum_target_context(
            SPEC_BY_KEY["DEATHKNIGHT_FROST"], "RAID", UPGRADE_GEAR, fake_wowhead(),
            upgrades=select_loadout_upgrades(ENCHANTS, None, "all", "RAID"),
        )
        self.assertNotIn("gems", context["bis"])
        self.assertEqual(0, context["targets"]["targetMetadata"]["gemCount"])
        context = gear_sum_target_context(
            SPEC_BY_KEY["DEATHKNIGHT_FROST"], "RAID", UPGRADE_GEAR, fake_wowhead(),
            upgrades=select_loadout_upgrades(None, GEMS, "all", "PVP"),
        )
        self.assertEqual({"secondary": 240900}, context["bis"]["gems"])
        for slot in context["bis"]["slots"]:
            self.assertNotIn("gem_ids", slot["item"])

    def test_build_all_passes_the_builds_enchant_lookup(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": [{"itemId": 1, "slot": "Head", "ilvl": 300}]}}},
                "talents": {"value": {"deathbringer": {"raid": [{"export": "X"}]}}},
                "enchants": {"value": ICY_ENCHANTS, "source": "icyveins"},
                "enchantLookup": {"value": LOOKUP, "source": "ugg+gamedata"},
            }
        }
        calls: list = []
        build_all(specs, goals=("RAID",), wowhead_reconstruct=fake_wowhead(calls=calls))
        self.assertEqual([8017], calls[0]["HEAD"]["enchantIds"])


class NoAlternativesTests(unittest.TestCase):
    """Owner decision 2026-09-29: only the single best gem/enchant is kept."""

    def test_upgrades_carry_only_the_best_choice(self) -> None:
        self.assertEqual(("enchants", "gems"), LoadoutUpgrades._fields)

    def test_bis_slots_never_carry_alternatives(self) -> None:
        upgrades = select_loadout_upgrades(ENCHANTS, GEMS, "all", "RAID")
        context = gear_sum_target_context(
            SPEC_BY_KEY["DEATHKNIGHT_FROST"], "RAID", UPGRADE_GEAR, fake_wowhead(), upgrades=upgrades
        )
        for slot in context["bis"]["slots"]:
            self.assertNotIn("gem_alt_id", slot["item"])
            self.assertNotIn("enchant_alt", slot["item"])


class WowheadItemLevelTests(unittest.TestCase):
    def test_the_fallback_reports_the_item_level_wowhead_shows(self) -> None:
        from tools.classcodex_targets import wowhead_gear_stats

        def fake(items, *, primary):
            return {
                "totals": {"crit": 900, "haste": 1200},
                "slots": {"HEAD": {"wowheadItemLevel": 334}, "NECK": {"wowheadItemLevel": 344}, "BACK": {"error": "x"}},
                "failures": [],
            }

        stats, levels = wowhead_gear_stats(SPEC_BY_KEY["DEATHKNIGHT_FROST"], {"HEAD": {"itemId": 1}}, fake)
        self.assertEqual({"critical_strike": 900.0, "haste": 1200.0}, stats)
        self.assertEqual({"HEAD": 334.0, "NECK": 344.0}, levels)


class AnnotatedPriorityEntryTests(unittest.TestCase):
    def test_icy_veins_stat_notes_keep_the_stat(self) -> None:
        row = priority_row_from_context(
            {"secondary": [[{"stat": "versatility", "note": "to 24%"}], ["mastery"], ["haste"], ["crit"]]}, "PvP", "hero"
        )
        self.assertEqual(["versatility", "mastery", "haste", "critical_strike"], row["order"])


class CatalystEntryTests(unittest.TestCase):
    def test_the_bis_item_is_the_tier_piece_and_keeps_the_catalyst_bonus_ids(self) -> None:
        from tools.classcodex_targets import gear_by_slot

        entry = {"slot": "Head", "itemId": 271483, "source": "Catalyst from Voidscar Arena",
                 "catalyst": {"itemId": 251220, "bonusIDs": [12854]}}
        head = gear_by_slot([entry])["HEAD"]
        self.assertEqual(271483, head["itemId"])
        self.assertEqual([12854], head["bonusIDs"])
        self.assertNotIn("catalyst", head)

    def test_entries_without_a_catalyst_block_are_unchanged(self) -> None:
        from tools.classcodex_targets import gear_by_slot

        head = gear_by_slot([{"slot": "Head", "itemId": 1, "bonusIDs": [5]}])["HEAD"]
        self.assertEqual((1, [5]), (head["itemId"], head["bonusIDs"]))


class GearSumTargetsTests(unittest.TestCase):
    """The targets as the plain sum of the guide's pieces: no simulation, every piece moved to the 6/6 of the tier."""

    spec = SPEC_BY_KEY["MONK_WINDWALKER"]
    track_swap = TrackSwap(
        swap={"myth": {12806: 12854}, "hero": {12806: 12846, 12854: 12846}, "champion": {12806: 12838, 12854: 12838, 12846: 12838}},
        item_levels={"myth": 334, "hero": 321, "champion": 308},
        unmapped={},
        track_of={12806: "myth", 12854: "myth", 12846: "hero", 12838: "champion"},
        top={"myth": 12854, "hero": 12846, "champion": 12838},
    )
    gear = [
        {"itemId": 1, "slot": "Head", "bonusIDs": [12806, 13367]},   # an older Myth rank
        {"itemId": 2, "slot": "Chest", "bonusIDs": []},             # a tier piece listed without ids
        {"itemId": 3, "slot": "Wrist", "bonusIDs": [13751, 12497]},  # crafted: no upgrade track
    ]

    def run_context(self, goal: str = "MYTHIC_PLUS", track_swap=None):
        asked: list[dict] = []

        def reconstruct(items, primary=None):
            asked.append(items)
            level = {12854: 334, 12846: 321, 12838: 308}
            total = 0
            slots = {}
            for slot, item in items.items():
                ids = item.get("bonusIds") or []
                ilvl = next((level[i] for i in ids if i in level), 280)
                slots[slot] = {"wowheadItemLevel": ilvl}
                total += ilvl
            return {"totals": {"crit": total, "haste": total // 2}, "slots": slots, "failures": []}

        context = gear_sum_target_context(self.spec, goal, self.gear, reconstruct, track_swap=track_swap or self.track_swap)
        return context["targets"], asked

    def test_every_piece_is_moved_to_the_6_of_the_tier_and_crafted_stays(self) -> None:
        targets, asked = self.run_context()
        by_tier = {tier: {slot: item.get("bonusIds") for slot, item in items.items()} for tier, items in zip(("myth", "hero", "champion"), asked)}
        self.assertEqual({"HEAD": [12854, 13367], "CHEST": [12854], "WRIST": [13751, 12497]}, by_tier["myth"])
        self.assertEqual({"HEAD": [12846, 13367], "CHEST": [12846], "WRIST": [13751, 12497]}, by_tier["hero"])
        self.assertEqual({"HEAD": [12838, 13367], "CHEST": [12838], "WRIST": [13751, 12497]}, by_tier["champion"])

    def test_the_tiers_grow_and_the_stats_are_the_sums(self) -> None:
        targets, _asked = self.run_context()
        champion = targets["levels"]["champion"]["statTargets"]["stats"]["critical_strike"]
        hero = targets["levels"]["hero"]["statTargets"]["stats"]["critical_strike"]
        myth = targets["statTargets"]["stats"]["critical_strike"]
        self.assertEqual((308 + 308 + 280, 321 + 321 + 280, 334 + 334 + 280), (champion, hero, myth))
        self.assertLess(champion, hero)
        self.assertLess(hero, myth)
        self.assertAlmostEqual((334 + 334 + 280) / 3, targets["averageItemLevel"])
        self.assertEqual("wowhead", targets["targetMetadata"]["itemLevelSource"])

    def test_pvp_gear_has_no_tracks_so_no_levels(self) -> None:
        targets, asked = self.run_context("PVP")
        self.assertNotIn("levels", targets)
        self.assertEqual(1, len(asked))
        self.assertEqual([12806, 13367], asked[0]["HEAD"]["bonusIds"])

    def test_without_the_track_tables_only_the_listed_levels_are_summed(self) -> None:
        with patch("tools.classcodex_targets.wowhead_gear_stats", return_value=({"critical_strike": 5.0, "haste": 4.0}, {})) as stats:
            context = gear_sum_target_context(self.spec, "RAID", self.gear, lambda *a, **k: {})
        self.assertEqual(1, stats.call_count)
        self.assertNotIn("levels", context["targets"])

    def test_the_base_rating_of_the_spec_is_added_to_every_tier(self) -> None:
        def reconstruct(items, primary=None):
            return {"totals": {"crit": 100, "haste": 50}, "slots": {}, "failures": []}

        plain = gear_sum_target_context(self.spec, "RAID", self.gear, reconstruct, track_swap=self.track_swap)["targets"]
        base = {"critical_strike": 200.0, "haste": 30.0}
        with_base = gear_sum_target_context(
            self.spec, "RAID", self.gear, reconstruct, track_swap=self.track_swap, base_stats=base)["targets"]
        self.assertEqual(plain["statTargets"]["stats"]["critical_strike"] + 200, with_base["statTargets"]["stats"]["critical_strike"])
        for tier in ("hero", "champion"):
            self.assertEqual(plain["levels"][tier]["statTargets"]["stats"]["haste"] + 30,
                             with_base["levels"][tier]["statTargets"]["stats"]["haste"])
        self.assertEqual(base, with_base["targetMetadata"]["baseStats"])
        self.assertNotIn("baseStats", plain["targetMetadata"])

    def test_the_shipped_base_ratings_cover_every_spec(self) -> None:
        base = load_spec_base_stats()
        self.assertEqual(40, len(base))
        self.assertGreater(base["DEATHKNIGHT_FROST"]["critical_strike"], 150)
        self.assertEqual({"critical_strike": 3.0, "haste": 5.0}, add_base_stats({"critical_strike": 1.0, "haste": 2.0}, {"critical_strike": 2.0, "haste": 3.0}))
        self.assertEqual({"haste": 2.0}, add_base_stats({"haste": 2.0}, None))

    def test_build_all_uses_the_gear_sums(self) -> None:
        specs = {
            "MONK_windwalker": {
                "gear": {"value": {"all": {"mplus": self.gear}}, "source": "icyveins"},
                "talents": {"value": {"shado-pan": {"mplus": [{"export": "X"}]}}},
            }
        }
        def reconstruct(items, primary=None):
            return {"totals": {"crit": 100, "haste": 50}, "slots": {}, "failures": []}

        data = build_all(specs, goals=("MYTHIC_PLUS",), wowhead_reconstruct=reconstruct, track_swap=self.track_swap)
        context = data["profiles"]["MONK_WINDWALKER"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["shado-pan"]
        self.assertEqual("ClassCodex BiS + gear totals (Wowhead item tooltips)", context["targets"]["statTargets"]["source"])
        self.assertEqual(3, len(context["bis"]["slots"]))
        self.assertEqual("icyveins", context["targets"]["targetMetadata"]["gearSource"])


if __name__ == "__main__":
    unittest.main()
