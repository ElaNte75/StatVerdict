from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.addon_benchmarks import build_addon_data, render_lua
from tools.tests.addon_fixtures import make_profile, make_raw_database

try:
    from lupa import LuaRuntime
except ImportError:  # optional dev dependency: pip install lupa
    LuaRuntime = None

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "StatVerdict"


def toc_lua_files() -> list[Path]:
    files = []
    for line in (ADDON / "StatVerdict.toc").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("##"):
            files.append(ADDON / line.replace("\\", "/"))
    return files


def new_runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("time = os.time")  # WoW provides time()
    return lua


def load_addon_file(lua, ns, relative_path: str) -> None:
    loader = lua.eval("function(path) local f, err = loadfile(path) if not f then error(err) end return f end")
    loader(str(ADDON / relative_path))("StatVerdict", ns)


def write_data_file(path: Path, generated_at: str, profiles: dict | None = None) -> None:
    data = build_addon_data([make_raw_database(generated_at, profiles)])
    path.write_text(render_lua(data), encoding="utf-8")


def now_stamp(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AddonLuaSyntaxTests(unittest.TestCase):
    def test_every_toc_file_compiles(self) -> None:
        lua = new_runtime()
        check = lua.eval("function(src, name) local f, err = load(src, name) if not f then return err end return nil end")
        for path in toc_lua_files():
            self.assertTrue(path.exists(), f"{path} is listed in the .toc but missing")
            error = check(path.read_text(encoding="utf-8-sig"), "@" + path.name)
            self.assertIsNone(error, f"{path.name}: {error}")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class BenchmarkCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_Benchmark.lua")

    def test_default_level_is_standard(self) -> None:
        self.assertEqual("STANDARD", self.ns.GetBenchmarkLevel())

    def test_set_level_is_saved_and_unknown_is_rejected(self) -> None:
        self.assertTrue(self.ns.SetBenchmarkLevel("ELITE"))
        self.assertEqual("ELITE", self.ns.GetBenchmarkLevel())
        self.assertEqual("ELITE", self.lua.globals().StatVerdictDB.benchmarkLevel)
        self.assertFalse(self.ns.SetBenchmarkLevel("TOP_25"))
        self.assertEqual("ELITE", self.ns.GetBenchmarkLevel())

    def test_garbage_saved_value_falls_back_to_default(self) -> None:
        self.lua.globals().StatVerdictDB.benchmarkLevel = "nonsense"
        self.assertEqual("STANDARD", self.ns.GetBenchmarkLevel())

    def test_level_names_and_meaning_lines(self) -> None:
        levels = self.ns.GetBenchmarkLevels()
        self.assertEqual(["Elite", "Standard", "Broad"], [levels[i].label for i in (1, 2, 3)])
        self.assertEqual("Gear of the top 25 players", levels[1].meaning)

    def test_wording_is_popular_for_mythic_plus_and_bis_otherwise(self) -> None:
        mplus = self.ns.GetReferenceWording("MYTHIC_PLUS")
        self.assertEqual("Popular Gear", mplus.button)
        self.assertEqual("Main Spec Popular Gear", mplus.main)
        self.assertEqual("Popular Progress", mplus.progress)
        self.assertEqual(" · Standard", mplus.progressSuffix)
        self.assertEqual("Popular", mplus.tag)
        raid = self.ns.GetReferenceWording("RAID")
        self.assertEqual("Best in Slot", raid.button)
        self.assertEqual("BiS Progress", raid.progress)
        self.assertEqual("", raid.progressSuffix)
        self.assertEqual("BIS", raid.tag)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class RepositoryTests(unittest.TestCase):
    def build_runtime(self, generated_at: str | None = None, level: str | None = None, profiles: dict | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data_path = Path(self.tmp.name) / "SV_MythicPlusBenchmarks.lua"
        write_data_file(data_path, generated_at or now_stamp(), profiles)
        lua = new_runtime()
        ns = lua.table()
        db = lua.table()
        if level:
            db.benchmarkLevel = level
        lua.globals().StatVerdictDB = db
        lua.eval("function(path, ns) local f = assert(loadfile(path)) f('StatVerdict', ns) end")(str(data_path), ns)
        for relative in ("Core/SV_Benchmark.lua", "Core/SV_ProfileRepository.lua", "Core/SV_ItemReferenceBonuses.lua"):
            load_addon_file(lua, ns, relative)
        ns.GetStatVerdictSpecIDByKey = lua.eval("function(key) return 250 end")
        ns.GetStatVerdictRoleBySpecID = lua.eval("function(id) return 'TANK' end")
        return lua, ns

    def context(self, lua, **extra):
        table = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS", role="TANK", specID=250, classFile="DEATHKNIGHT")
        for key, value in extra.items():
            table[key] = value
        return table

    def targets(self, profile) -> dict:
        rows = profile.auditTargets.rows
        return {rows[i].key: rows[i].target for i in range(1, len(rows) + 1)}

    def test_mythic_plus_profile_is_built_from_the_live_file(self) -> None:
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertFalse(profile.invalidGeneratedContext)
        self.assertEqual("ITEM_MOD_STRENGTH_SHORT", profile.primaryStat)
        self.assertEqual(1140.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])

    def test_level_choice_changes_the_targets(self) -> None:
        lua, ns = self.build_runtime(level="ELITE")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(1300.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])

    def test_hero_tree_id_selects_its_priority_and_unknown_uses_spec_wide(self) -> None:
        lua, ns = self.build_runtime()
        hero = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=31))
        self.assertEqual("ITEM_MOD_HASTE_RATING_SHORT", hero.secondaryOrder[1])
        self.assertEqual("ITEM_MOD_MASTERY_RATING_SHORT", hero.secondaryOrder[2])
        other = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=33))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", other.secondaryOrder[1])
        unknown = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(["ITEM_MOD_CRIT_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT"],
                         [unknown.secondaryOrder[1], unknown.secondaryOrder[2]])
        mismatch = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=99))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", mismatch.secondaryOrder[1])

    def test_missing_level_shows_no_data_instead_of_another_level(self) -> None:
        profile = make_profile()
        profile["cohorts"]["TOP_25"]["status"] = "insufficient"
        lua, ns = self.build_runtime(level="ELITE", profiles={"DEATHKNIGHT_BLOOD": profile})
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))
        lua, ns = self.build_runtime(profiles={"DEATHKNIGHT_BLOOD": profile})
        self.assertIsNotNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))

    def test_stale_data_fails_closed(self) -> None:
        lua, ns = self.build_runtime(generated_at=now_stamp(days_ago=40))
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))

    def test_raid_still_reads_the_old_file_only(self) -> None:
        lua, ns = self.build_runtime()
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal="RAID")))

    def test_provider_view_lists_specs_from_the_live_file(self) -> None:
        lua, ns = self.build_runtime()
        provider = ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")
        self.assertIsNotNone(provider["DEATHKNIGHT"][250].default)

    def test_provenance_uses_the_live_file_for_mythic_plus(self) -> None:
        lua, ns = self.build_runtime()
        info = ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS")
        self.assertTrue(info.available)
        self.assertEqual("StatVerdict live benchmarks · Standard", info.sourceName)
        self.assertEqual(now_stamp()[:10], info.scrape)

    def test_popular_items_and_trinkets_keep_their_boosts(self) -> None:
        lua, ns = self.build_runtime()
        profile = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        helm = ns.GetItemReferenceInfo("item:1000", profile)
        self.assertEqual(8, helm.bonus)
        self.assertIsNotNone(helm.bis)
        # The two most popular trinkets are also in the popular-slot list, so they get
        # the +8 list bonus on top of their tier bonus (same as the old BiS data did).
        alpha = ns.GetItemReferenceInfo("item:5001", profile)
        self.assertEqual("S", alpha.trinket.tier)
        self.assertEqual(108, alpha.bonus)  # list 8 + tier 95 + rank bonus 5
        gamma = ns.GetItemReferenceInfo("item:5003", profile)
        self.assertEqual(107, gamma.bonus)  # list 8 + tier 95 + rank bonus 4
        beta = ns.GetItemReferenceInfo("item:5002", profile)
        self.assertEqual("A", beta.trinket.tier)
        self.assertEqual(70, beta.bonus)  # tier 65 + rank bonus 5 (not in the popular-slot list)
        self.assertIsNone(ns.GetItemReferenceInfo("item:1001", profile))  # second most popular helm: not listed
        self.assertIsNone(ns.GetItemReferenceInfo("item:5004", profile))  # below the 3% floor
        self.assertIsNone(ns.GetItemReferenceInfo("item:999999", profile))

    def test_boost_follows_the_selected_level(self) -> None:
        lua, ns = self.build_runtime(level="BROAD")
        profile = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1000", profile).bonus)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class PanelModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")

    def test_benchmark_is_a_valid_mode_and_summary_is_not(self) -> None:
        self.ns.SetRightPanelMode("benchmark")
        self.assertEqual("benchmark", self.ns.GetRightPanelMode())
        self.ns.SetRightPanelMode("summary")
        self.assertIsNone(self.ns.GetRightPanelMode())

    def test_window_opens_with_every_panel_closed(self) -> None:
        self.assertIsNone(self.ns.GetRightPanelMode())

    def test_toc_lists_benchmark_drawer_and_not_summary(self) -> None:
        names = [path.name for path in toc_lua_files()]
        self.assertIn("SV_BenchmarkDrawerPanel.lua", names)
        self.assertNotIn("SV_CharacterSummaryDrawerPanel.lua", names)


if __name__ == "__main__":
    unittest.main()
