"""End-to-end: raw ClassCodex Lua source -> tools.classcodex_build.build() ->
tools.classcodex_targets.build_all / tools.classcodex_weights.build_all_weights,
with only SimulationCraft mocked.

The fixture mirrors the layout of the REAL live data (verified against build
20260928064230-9b041a5-43564495 on 2026-09-28), which differs from what the
unit tests' hand-written dicts assume:
  - Mythic+/Raid gear exists only under hero key "all"; the specific hero keys
    only carry PvP gear, and PvP gear entries have no "ilvl".
  - talents exist only under the specific hero keys (never "all"), with extra
    per-encounter contexts ("mplus:12813", "raid:3379", ...), no
    `recommended` flag (ordered most-picked first), and PvP entries carry
    `honor` instead of `pickrate`.
  - trinkets exist only under hero "all", contexts "all" and "pvp".
  - statPriority is keyed by "aoe"/"single-target"/"pvp" under the specific
    hero keys, and only "pvp" under hero "all".
This is the test that would have caught the missing `talents` extraction.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tools.classcodex_build import build
from tools.classcodex_targets import build_all
from tools.classcodex_weights import build_all_weights

SLOTS = (
    "Head", "Neck", "Shoulders", "Back", "Chest", "Wrist", "Hands", "Waist",
    "Legs", "Feet", "Finger 1", "Finger 2", "Trinket 1", "Trinket 2", "Main Hand", "Off Hand",
)


def _gear_lua(base_item_id: int, with_ilvl: bool) -> str:
    rows = []
    for index, slot in enumerate(SLOTS):
        ilvl = f", ilvl = {330 + index % 3}" if with_ilvl else ""
        rows.append(f'{{slot = "{slot}", itemId = {base_item_id + index}, bonusIDs = {{6652, 13668}}{ilvl}}}')
    return "{" + ", ".join(rows) + "}"


def _talents_lua(prefix: str) -> str:
    return (
        "{"
        f'mplus = {{{{export = "{prefix}-MPLUS-TOP", pickrate = 21.8, topDps = true}}, {{export = "{prefix}-MPLUS-2", pickrate = 9.1}}}}, '
        f'["mplus:12813"] = {{{{export = "{prefix}-DUNGEON", pickrate = 30.0}}}}, '
        f'raid = {{{{export = "{prefix}-RAID-TOP", pickrate = 40.2}}}}, '
        f'["raid:3379"] = {{{{export = "{prefix}-BOSS", pickrate = 50.0}}}}, '
        f'pvp = {{{{export = "{prefix}-PVP", honor = 1200}}}}'
        "}"
    )


def _priority_lua(first: str) -> str:
    return f'{{secondary = {{{{"{first}"}}, {{"haste", "mastery"}}, {{"versatility"}}}}}}'


REAL_SHAPED_UGG = (
    "ClassCodexSource = ClassCodexSource or {}\n"
    'ClassCodexSource["ugg"] = {data = {DEATHKNIGHT = {frost = {\n'
    "  gear = {\n"
    f"    all = {{mplus = {_gear_lua(1000, True)}, raid = {_gear_lua(2000, True)}, pvp = {_gear_lua(3000, False)}}},\n"
    f"    deathbringer = {{pvp = {_gear_lua(4000, False)}}},\n"
    f'    ["rider-of-the-apocalypse"] = {{pvp = {_gear_lua(5000, False)}}},\n'
    "  },\n"
    "  talents = {\n"
    f"    deathbringer = {_talents_lua('DB')},\n"
    f'    ["rider-of-the-apocalypse"] = {_talents_lua("RIDER")},\n'
    "  },\n"
    "  trinkets = {\n"
    '    all = {all = {{itemId = 270175, bonusIDs = {13848}, tier = "S"}, {itemId = 270176, tier = "A"}},\n'
    '           pvp = {{itemId = 280001, tier = "S"}}},\n'
    "  },\n"
    "  statPriority = {\n"
    f'    all = {{pvp = {_priority_lua("versatility")}}},\n'
    f'    deathbringer = {{aoe = {_priority_lua("mastery")}, ["single-target"] = {_priority_lua("crit")}, pvp = {_priority_lua("versatility")}}},\n'
    f'    ["rider-of-the-apocalypse"] = {{aoe = {_priority_lua("mastery")}, ["single-target"] = {_priority_lua("crit")}, pvp = {_priority_lua("versatility")}}},\n'
    "  },\n"
    "}}}}\n"
)

REAL_SHAPED_SOURCES = {
    "db_ugg": REAL_SHAPED_UGG,
    "db_icyveins": "ClassCodexSource = ClassCodexSource or {}\n",
}

RECONSTRUCTED = {"ratings": {"crit": 1500.0, "haste": 1200.0, "mastery": 1800.0, "versatility": 700.0}}


class RealShapedPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.specs = build(REAL_SHAPED_SOURCES)

    def test_build_extracts_every_field_the_simc_pipelines_need(self) -> None:
        spec = self.specs["DEATHKNIGHT_frost"]
        for field_name in ("gear", "talents", "trinkets", "statPriority"):
            self.assertIn(field_name, spec)

    def test_targets_pipeline_produces_every_goal_for_every_hero_talent(self) -> None:
        profiles_seen: list[str] = []

        def fake_run_simc(_binary, profile_text, **_kwargs):
            profiles_seen.append(profile_text)
            return {"sv_0001": RECONSTRUCTED}, {}

        with patch("tools.classcodex_targets.run_simc", side_effect=fake_run_simc):
            data = build_all(self.specs, Path("simc"))

        self.assertTrue(data["profiles"], "real-shaped data must produce at least one profile")
        profile = data["profiles"]["DEATHKNIGHT_frost"]
        for goal in ("MYTHIC_PLUS", "RAID", "PVP"):
            self.assertEqual(
                {"deathbringer", "rider-of-the-apocalypse"},
                set(profile["goals"][goal]["heroTalents"]),
                f"{goal} should have one entry per real hero talent",
            )

        mplus = profile["goals"]["MYTHIC_PLUS"]["heroTalents"]["deathbringer"]
        # Mythic+ gear came from hero "all" (with ilvl), trinkets from all/all,
        # priority from the hero's "aoe" list (mastery first), labelled for the goal.
        self.assertAlmostEqual(330.9375, mplus["targets"]["averageItemLevel"])  # 16 slots at ilvl 330-332
        self.assertEqual([270175, 270176], [t["item_id"] for t in mplus["trinkets"]])
        self.assertEqual("Mythic+", mplus["priorityProfiles"][0]["context"])
        self.assertEqual("mastery", mplus["priorityProfiles"][0]["order"][0])

        raid = profile["goals"]["RAID"]["heroTalents"]["deathbringer"]
        self.assertEqual("Raid", raid["priorityProfiles"][0]["context"])

        pvp = profile["goals"]["PVP"]["heroTalents"]["rider-of-the-apocalypse"]
        self.assertIsNone(pvp["targets"]["averageItemLevel"])  # real PvP gear has no ilvl
        self.assertEqual([280001], [t["item_id"] for t in pvp["trinkets"]])
        self.assertEqual("PvP", pvp["priorityProfiles"][0]["context"])

        # Each goal used the hero's own top-picked talent build for that goal,
        # never a per-encounter variant.
        talents_used = sorted(line for text in profiles_seen for line in text.splitlines() if line.startswith("talents="))
        self.assertIn("talents=DB-MPLUS-TOP", talents_used)
        self.assertIn("talents=RIDER-RAID-TOP", talents_used)
        self.assertIn("talents=DB-PVP", talents_used)
        self.assertNotIn("talents=DB-DUNGEON", talents_used)
        self.assertEqual(6, len(profiles_seen))  # 3 goals x 2 hero talents

    def test_weights_pipeline_produces_every_goal_for_every_hero_talent(self) -> None:
        by_stat = {"Str": 0.0, "Crit": 0.653, "Haste": 0.492, "Mastery": 0.455, "Vers": 0.345}
        report = {"sim": {"players": [{"name": "sv_0001", "scale_factors": by_stat, "scale_factors_all": {"dps": by_stat}}]}}
        with patch("tools.classcodex_weights.run_simc", return_value=({}, report)):
            data = build_all_weights(self.specs, Path("simc"))

        self.assertTrue(data["profiles"], "real-shaped data must produce at least one weights profile")
        profile = data["profiles"]["DEATHKNIGHT_frost"]
        for goal in ("MYTHIC_PLUS", "RAID", "PVP"):
            self.assertEqual({"deathbringer", "rider-of-the-apocalypse"}, set(profile[goal]))


if __name__ == "__main__":
    unittest.main()
