from __future__ import annotations

import unittest

from tools.classcodex_build import build, build_stat_dr


def _plain_global_source(global_name: str, class_token: str, spec_token: str, fields: dict) -> str:
    """Builds minimal Lua source matching the real db_ugg.lua/db_icyveins.lua
    shape: ClassCodexSource = {...}; ClassCodexSource["<key>"] = {data={CLASS={spec={fields}}}}."""
    lua_fields = ", ".join(f'{name} = {{{value}}}' for name, value in fields.items())
    return (
        "ClassCodexSource = ClassCodexSource or {}\n"
        f'ClassCodexSource["{global_name}"] = {{data = {{{class_token} = {{{spec_token} = {{{lua_fields}}}}}}}}}\n'
    )


def _lists(lua_like) -> list:
    """Sandbox output turns Lua arrays into dicts keyed 1..n or lists; normalise to nested lists."""
    if isinstance(lua_like, dict):
        return [_lists(lua_like[key]) for key in sorted(lua_like)]
    if isinstance(lua_like, list):
        return [_lists(item) for item in lua_like]
    return lua_like


class ClassCodexBuildTests(unittest.TestCase):
    def test_icy_veins_wins_pve_and_ugg_wins_pvp_for_every_guide_field(self) -> None:
        for field_name in ("trinkets", "gear", "gems", "enchants", "talents"):
            with self.subTest(field_name=field_name):
                ugg = 'all = {mplus = {from = "ugg"}, raid = {from = "ugg"}, pvp = {from = "ugg"}}'
                icy = 'all = {all = {from = "icy"}, mplus = {from = "icy"}, pvp = {from = "icy"}}'
                sources = {
                    "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {field_name: ugg}),
                    "db_icyveins": _plain_global_source("icyveins", "DEATHKNIGHT", "frost", {field_name: icy}),
                }
                merged = build(sources)["DEATHKNIGHT_frost"][field_name]
                self.assertEqual("icyveins", merged["source"])
                hero = merged["value"]["all"]
                self.assertEqual("icy", hero["all"]["from"])
                self.assertEqual("icy", hero["mplus"]["from"])
                # u.gg's raid list would outrank Icy Veins' "all" for Raid: dropped.
                self.assertNotIn("raid", hero)
                self.assertEqual("ugg", hero["pvp"]["from"])
                self.assertEqual({"all": "icyveins", "mplus": "icyveins", "pvp": "ugg"}, merged["origins"]["all"])

    def test_icy_veins_spec_wide_pve_covers_ugg_hero_trees(self) -> None:
        ugg = (
            'deathbringer = {mplus = {{export = "U1"}}, pvp = {{export = "UP"}}},'
            ' rider = {raid = {{export = "U2"}}}'
        )
        icy = 'all = {mplus = {{export = "I1"}}, raid = {{export = "I2"}}}'
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"talents": ugg}),
            "db_icyveins": _plain_global_source("icyveins", "DEATHKNIGHT", "frost", {"talents": icy}),
        }
        value = build(sources)["DEATHKNIGHT_frost"]["talents"]["value"]
        self.assertEqual({"pvp"}, set(value["deathbringer"]))
        self.assertNotIn("rider", value)  # nothing PvP to add, PvE comes from Icy Veins' "all"
        self.assertEqual("I1", value["all"]["mplus"][0]["export"])

    def test_hero_trees_icy_veins_does_not_cover_for_pve_take_ugg(self) -> None:
        # Icy Veins' only hero-"all" entry is PvP: it covers no PvE, so u.gg
        # fills each hero tree it lacks; Icy Veins' own hero tree stays.
        ugg = 'rider = {mplus = {{export = "U1"}}}, deathbringer = {mplus = {{export = "U2"}}}'
        icy = 'all = {pvp = {{export = "IP"}}}, deathbringer = {mplus = {{export = "I2"}}}'
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"talents": ugg}),
            "db_icyveins": _plain_global_source("icyveins", "DEATHKNIGHT", "frost", {"talents": icy}),
        }
        merged = build(sources)["DEATHKNIGHT_frost"]["talents"]
        self.assertEqual("U1", merged["value"]["rider"]["mplus"][0]["export"])
        self.assertEqual({"mplus": "ugg"}, merged["origins"]["rider"])
        self.assertEqual("I2", merged["value"]["deathbringer"]["mplus"][0]["export"])
        self.assertEqual("IP", merged["value"]["all"]["pvp"][0]["export"])

    def test_stat_priority_follows_icy_veins_but_keeps_ugg_pvp(self) -> None:
        ugg = (
            'deathbringer = {["single-target"] = {secondary = {{"versatility"}, {"haste"}}},'
            ' pvp = {secondary = {{"mastery"}, {"crit"}}}},'
            ' wildhero = {["single-target"] = {secondary = {{"haste"}}}}'
        )
        icy = 'deathbringer = {all = {secondary = {{"crit"}, {"mastery", "versatility"}, {"haste"}}}}'
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "blood", {"statPriority": ugg}),
            "db_icyveins": _plain_global_source("icyveins", "DEATHKNIGHT", "blood", {"statPriority": icy}),
        }
        merged = build(sources)["DEATHKNIGHT_blood"]["statPriority"]
        self.assertEqual("icyveins", merged["source"])
        hero = merged["value"]["deathbringer"]
        self.assertEqual([["crit"], ["mastery", "versatility"], ["haste"]], _lists(hero["all"]["secondary"]))
        self.assertNotIn("single-target", hero)  # u.gg's PvE lists must not outrank the guide
        self.assertEqual([["mastery"], ["crit"]], _lists(hero["pvp"]["secondary"]))
        # A hero tree Icy Veins does not cover keeps u.gg's entry.
        self.assertIn("single-target", merged["value"]["wildhero"])

    def test_spec_wide_icy_veins_list_covers_hero_trees_it_does_not_name(self) -> None:
        ugg = (
            'druidclaw = {["single-target"] = {secondary = {{"versatility"}}}, pvp = {secondary = {{"mastery"}}}},'
            ' ["all"] = {pvp = {secondary = {{"crit"}}}}'
        )
        icy = '["all"] = {all = {secondary = {{"haste"}, {"versatility"}}}, damage = {secondary = {{"crit"}}}}'
        sources = {
            "db_ugg": _plain_global_source("ugg", "DRUID", "guardian", {"statPriority": ugg}),
            "db_icyveins": _plain_global_source("icyveins", "DRUID", "guardian", {"statPriority": icy}),
        }
        merged = build(sources)["DRUID_guardian"]["statPriority"]["value"]
        self.assertEqual([["haste"], ["versatility"]], _lists(merged["all"]["all"]["secondary"]))
        self.assertNotIn("single-target", merged["druidclaw"])
        self.assertEqual([["mastery"], ["crit"]][0], _lists(merged["druidclaw"]["pvp"]["secondary"])[0])
        self.assertEqual(["pvp"], list(merged["druidclaw"]))

    def test_ugg_pvp_list_wins_over_icy_veins_pvp(self) -> None:
        ugg = 'hero = {pvp = {secondary = {{"crit"}}}}'
        icy = 'hero = {all = {secondary = {{"haste"}}}, pvp = {secondary = {{"mastery"}}}}'
        sources = {
            "db_ugg": _plain_global_source("ugg", "HUNTER", "marksmanship", {"statPriority": ugg}),
            "db_icyveins": _plain_global_source("icyveins", "HUNTER", "marksmanship", {"statPriority": icy}),
        }
        merged = build(sources)["HUNTER_marksmanship"]["statPriority"]["value"]
        self.assertEqual([["crit"]], _lists(merged["hero"]["pvp"]["secondary"]))

    def test_stat_priority_falls_back_to_ugg_when_icy_veins_has_none(self) -> None:
        sources = {
            "db_ugg": _plain_global_source(
                "ugg", "DEATHKNIGHT", "blood", {"statPriority": 'hero = {pvp = {secondary = {{"crit"}}}}'}
            ),
            "db_icyveins": _plain_global_source("icyveins", "DEATHKNIGHT", "blood", {"gear": 'x = 1'}),
        }
        self.assertEqual("ugg", build(sources)["DEATHKNIGHT_blood"]["statPriority"]["source"])

    def test_each_source_fills_a_field_the_other_lacks(self) -> None:
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"trinkets": 'from = "ugg"'}),
            "db_icyveins": _plain_global_source(
                "icyveins", "DEATHKNIGHT", "frost", {"gear": 'from = "icyveins"'}
            ),
        }
        specs = build(sources)
        spec = specs["DEATHKNIGHT_frost"]
        self.assertEqual("ugg", spec["trinkets"]["source"])
        self.assertEqual("icyveins", spec["gear"]["source"])

    def test_a_spec_only_present_in_icyveins_still_comes_through(self) -> None:
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"gear": 'from = "ugg"'}),
            "db_icyveins": _plain_global_source(
                "icyveins", "PALADIN", "holy", {"gear": 'from = "icyveins"'}
            ),
        }
        specs = build(sources)
        self.assertIn("PALADIN_holy", specs)
        self.assertEqual("icyveins", specs["PALADIN_holy"]["gear"]["source"])

    def test_tierRank_is_never_extracted(self) -> None:
        sources = {
            "db_ugg": _plain_global_source(
                "ugg",
                "DEATHKNIGHT",
                "frost",
                {"statPriority": 'from = "ugg"', "tierRank": 'tier = "A"'},
            ),
            "db_icyveins": "ClassCodexSource = ClassCodexSource or {}\n",
        }
        spec = build(sources)["DEATHKNIGHT_frost"]
        self.assertIn("statPriority", spec)
        self.assertNotIn("tierRank", spec)

    def test_stat_targets_come_from_ugg_only(self) -> None:
        sources = {
            "db_ugg": _plain_global_source(
                "ugg", "DEATHKNIGHT", "frost", {"statTargets": "all = {mplus = {top50 = {crit = 699}}}"}
            ),
            "db_icyveins": _plain_global_source(
                "icyveins", "DEATHKNIGHT", "frost", {"statTargets": "all = {mplus = {top50 = {crit = 1}}}"}
            ),
        }
        spec = build(sources)["DEATHKNIGHT_frost"]
        self.assertEqual({"all": {"mplus": {"top50": {"crit": 699}}}}, spec["statTargets"]["value"])
        self.assertEqual("ugg", spec["statTargets"]["source"])
        only_icy = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"gear": 'from = "ugg"'}),
            "db_icyveins": sources["db_icyveins"],
        }
        self.assertNotIn("statTargets", build(only_icy)["DEATHKNIGHT_frost"])

    def test_enchants_and_gems_follow_icy_veins_for_pve(self) -> None:
        sources = {
            "db_ugg": _plain_global_source(
                "ugg",
                "DEATHKNIGHT",
                "frost",
                {
                    "gems": "all = {all = {{pop = 12.6, primary = 1, secondary = {2}}}, pvp = {{pop = 5, secondary = {3}}}}",
                    "enchants": "all = {all = {Head = {{id = 8017, itemId = 244007, spellId = 1236084, pop = 46.7}}},"
                    " pvp = {Head = {{id = 243951, pop = 60}}}}",
                },
            ),
            "db_icyveins": _plain_global_source(
                "icyveins",
                "DEATHKNIGHT",
                "frost",
                {
                    "gems": "all = {all = {{primary = 9, secondary = {8, 7}}}}",
                    "enchants": "all = {all = {Head = {{id = 244007}}}}",
                },
            ),
        }
        spec = build(sources)["DEATHKNIGHT_frost"]
        self.assertEqual(9, spec["gems"]["value"]["all"]["all"][0]["primary"])
        self.assertEqual([3], _lists(spec["gems"]["value"]["all"]["pvp"][0]["secondary"]))
        self.assertEqual(244007, spec["enchants"]["value"]["all"]["all"]["Head"][0]["id"])
        self.assertEqual(243951, spec["enchants"]["value"]["all"]["pvp"]["Head"][0]["id"])

    def test_enchant_lookup_spans_every_ugg_spec_and_the_game_data_recipes(self) -> None:
        ugg = (
            "ClassCodexSource = ClassCodexSource or {}\n"
            'ClassCodexSource["ugg"] = {data = {'
            "DEATHKNIGHT = {frost = {enchants = {all = {all = {"
            '["Main Hand"] = {{id = 3368, spellId = 53344}}}}}}},'
            "MAGE = {fire = {enchants = {all = {all = {"
            "Head = {{id = 8017, itemId = 244007, spellId = 1236084}}}, pvp = {Head = {{id = 243951}}}}}}}"
            "}}\n"
        )
        # Real db_gamedata: `enchants` names the scroll Icy Veins uses (243990
        # for spell 1236076; u.gg lists that spell with 243991); `recipes`
        # fills the rest, `enchants` winning on a shared item.
        game_data = (
            "ClassCodexGameData = {enchants = {[1236076] = 243990, [1236062] = 243962},"
            " recipes = {[1236084] = 244007, [999] = 243962}}\n"
        )
        specs = build({"db_ugg": ugg, "db_gamedata": game_data})
        lookup = specs["DEATHKNIGHT_frost"]["enchantLookup"]["value"]
        self.assertIs(lookup, specs["MAGE_fire"]["enchantLookup"]["value"])
        self.assertEqual({"id": 8017, "item_id": 244007, "spell_id": 1236084}, lookup["byItem"][244007])
        self.assertEqual({"id": 3368, "spell_id": 53344}, lookup["bySpell"][53344])
        self.assertNotIn(243951, lookup["byItem"])  # a bare PvP scroll id is not a real enchant
        self.assertEqual({243990: 1236076, 244007: 1236084, 243962: 1236062}, lookup["recipeSpellByItem"])

    def test_talents_are_extracted_alongside_the_other_fields(self) -> None:
        # Without `talents`, tools/classcodex_targets.py and
        # tools/classcodex_weights.py cannot build a single SimC profile.
        sources = {
            "db_ugg": _plain_global_source(
                "ugg",
                "DEATHKNIGHT",
                "frost",
                {
                    "talents": 'deathbringer = {mplus = {{export = "CsPAAA", pickrate = 21.8}}}',
                    "gear": 'all = {mplus = {{itemId = 1, slot = "Head"}}}',
                },
            ),
            "db_icyveins": "ClassCodexSource = ClassCodexSource or {}\n",
        }
        spec = build(sources)["DEATHKNIGHT_frost"]
        self.assertEqual("ugg", spec["talents"]["source"])
        self.assertEqual("CsPAAA", spec["talents"]["value"]["deathbringer"]["mplus"][0]["export"])
        self.assertIn("gear", spec)

    def test_missing_source_does_not_crash_the_build(self) -> None:
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"gear": 'from = "ugg"'}),
            # db_icyveins entirely absent, as classcodex_fetch would leave it
            # if that one file failed to fetch.
        }
        specs = build(sources)
        self.assertEqual("ugg", specs["DEATHKNIGHT_frost"]["gear"]["source"])

    def test_build_stat_dr_loads_the_addon_namespaced_module(self) -> None:
        source = "local addonName, ns = ...\nns.StatDR = {ready = true}"
        result = build_stat_dr(source)
        self.assertTrue(result["StatDR"]["ready"])


if __name__ == "__main__":
    unittest.main()
