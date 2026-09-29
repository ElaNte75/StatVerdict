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


class ClassCodexBuildTests(unittest.TestCase):
    def test_prefers_ugg_over_icyveins_when_both_have_a_field(self) -> None:
        sources = {
            "db_ugg": _plain_global_source("ugg", "DEATHKNIGHT", "frost", {"statPriority": 'from = "ugg"'}),
            "db_icyveins": _plain_global_source(
                "icyveins", "DEATHKNIGHT", "frost", {"statPriority": 'from = "icyveins"'}
            ),
        }
        specs = build(sources)
        self.assertEqual("ugg", specs["DEATHKNIGHT_frost"]["statPriority"]["source"])
        self.assertEqual("ugg", specs["DEATHKNIGHT_frost"]["statPriority"]["value"]["from"])

    def test_falls_back_to_icyveins_when_ugg_lacks_the_field(self) -> None:
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

    def test_statTargets_and_tierRank_are_never_extracted(self) -> None:
        sources = {
            "db_ugg": _plain_global_source(
                "ugg",
                "DEATHKNIGHT",
                "frost",
                {
                    "statPriority": 'from = "ugg"',
                    "statTargets": 'crit = 699',
                    "tierRank": 'tier = "A"',
                },
            ),
            "db_icyveins": "ClassCodexSource = ClassCodexSource or {}\n",
        }
        specs = build(sources)
        spec = specs["DEATHKNIGHT_frost"]
        self.assertIn("statPriority", spec)
        self.assertNotIn("statTargets", spec)
        self.assertNotIn("tierRank", spec)

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
