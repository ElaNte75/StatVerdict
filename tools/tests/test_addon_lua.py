from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.classcodex_targets_cli import render_lua as render_targets_lua
from tools.classcodex_weights_cli import render_lua as render_weights_lua
from tools.tests.addon_fixtures import (
    add_guide_targets, make_classcodex_targets, make_classcodex_weights, make_guide_targets,
)

try:
    # WoW runs Lua 5.1: test the addon on a 5.1 runtime so syntax or library
    # calls newer Lua versions added (goto, //, integer division, utf8...) fail here.
    from lupa.lua51 import LuaRuntime
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
    lua.execute("time = os.time; date = os.date")  # WoW provides time() and date()
    return lua


def compile_lua_file(lua, path: Path):
    """Compile a Lua file the way WoW does: a leading UTF-8 BOM is allowed
    (the WoW loader skips it; plain Lua 5.1 loadfile does not)."""
    compile_source = lua.eval("function(src, name) local f, err = loadstring(src, name) if not f then error(err) end return f end")
    return compile_source(Path(path).read_text(encoding="utf-8-sig"), "@" + str(path))


def load_addon_file(lua, ns, relative_path: str) -> None:
    compile_lua_file(lua, ADDON / relative_path)("StatVerdict", ns)


def now_build_id(days_ago: int = 0) -> str:
    """A ClassCodex buildId: UTC yyyymmddhhmmss, then commit and hash parts."""
    stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y%m%d%H%M%S")
    return f"{stamp}-6702fd4-878715d1"


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AddonLuaSyntaxTests(unittest.TestCase):
    def test_addon_tests_run_on_wows_lua_version(self) -> None:
        lua = new_runtime()
        self.assertEqual("Lua 5.1", lua.eval("_VERSION"))
        # 5.2+ syntax must not compile here, so it is caught before it reaches the game.
        check = lua.eval("function(src) local f, err = loadstring(src) return f == nil end")
        self.assertTrue(check("goto done ::done::"))
        self.assertTrue(check("local x = 7 // 2"))

    def test_every_toc_file_compiles(self) -> None:
        lua = new_runtime()
        check = lua.eval("function(src, name) local f, err = loadstring(src, name) if not f then return err end return nil end")
        for path in toc_lua_files():
            self.assertTrue(path.exists(), f"{path} is listed in the .toc but missing")
            error = check(path.read_text(encoding="utf-8-sig"), "@" + path.name)
            self.assertIsNone(error, f"{path.name}: {error}")

    def test_toc_loads_the_classcodex_data_before_the_core_files(self) -> None:
        names = [path.relative_to(ADDON).as_posix() for path in toc_lua_files()]
        data = ["Data/Generated/SV_ClassCodexTargets.lua", "Data/Generated/SV_ClassCodexWeights.lua",
                "Data/Generated/SV_StatDR.lua"]
        for name in data:
            self.assertIn(name, names)
            self.assertLess(names.index(name), names.index("Core/SV_Constants.lua"), name)
        self.assertNotIn("Data/Generated/SV_MythicPlusBenchmarks.lua", names)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WeightModeCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_WeightModes.lua")
        load_addon_file(self.lua, self.ns, "Core/SV_ProfileRepository.lua")
        self.calls = {"audit": 0, "indicators": 0}
        self.ns.RequestStatAuditRefresh = lambda: self.calls.__setitem__("audit", self.calls["audit"] + 1)
        self.ns.RefreshUpgradeIndicators = lambda *a: self.calls.__setitem__("indicators", self.calls["indicators"] + 1)

    def test_three_modes_with_guide_recommended(self) -> None:
        modes = self.ns.GetWeightModes()
        self.assertEqual(["GUIDE", "MEASURED", "BLEND"], [modes[i].key for i in (1, 2, 3)])
        self.assertEqual(["Guide", "Measured", "Blend"], [modes[i].label for i in (1, 2, 3)])
        self.assertEqual("Recommended", modes[1].hint)
        self.assertEqual("Priority and stat targets exactly as in ClassCodex (Icy Veins / u.gg); "
                         "weights follow that priority. Recommended.", modes[1].about)
        self.assertEqual("Our own: priority and weights from simulations, stat targets from best-in-slot "
                         "gear with recommended gems and enchants.", modes[2].about)
        self.assertEqual("Guide priority; weights and stat targets are the average of the guide's and ours.",
                         modes[3].about)
        for i in (1, 2, 3):
            self.assertTrue(modes[i].meaning)
        self.assertEqual("Measured", self.ns.GetWeightModeInfo("MEASURED").label)
        self.assertEqual("Guide", self.ns.GetWeightModeInfo("junk").label)

    def test_default_mode_is_guide_and_old_benchmark_level_is_ignored(self) -> None:
        self.lua.globals().StatVerdictDB.benchmarkLevel = "ELITE"
        self.assertEqual("GUIDE", self.ns.GetWeightMode())

    def test_set_mode_saves_it_and_refreshes(self) -> None:
        self.assertTrue(self.ns.SetWeightMode("MEASURED"))
        self.assertEqual("MEASURED", self.lua.globals().StatVerdictDB.weightMode)
        self.assertEqual("MEASURED", self.ns.GetWeightMode())
        self.assertEqual({"audit": 1, "indicators": 1}, self.calls)
        self.assertFalse(self.ns.SetWeightMode("ELITE"))
        self.assertEqual("MEASURED", self.ns.GetWeightMode())
        self.assertEqual({"audit": 1, "indicators": 1}, self.calls)

    def test_three_stat_target_levels_like_classcodex(self) -> None:
        bins = self.ns.GetStatTargetBins()
        self.assertEqual(["top20", "top50", "top80"], [bins[i].key for i in (1, 2, 3)])
        self.assertEqual(["Top 20%", "Top 50%", "Top 80%"], [bins[i].label for i in (1, 2, 3)])
        self.assertEqual("top20", self.ns.GetStatTargetBin())

    def test_set_stat_target_bin_saves_it_and_refreshes(self) -> None:
        self.assertTrue(self.ns.SetStatTargetBin("top50"))
        self.assertEqual("top50", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual("top50", self.ns.GetStatTargetBin())
        self.assertEqual({"audit": 1, "indicators": 1}, self.calls)
        self.assertFalse(self.ns.SetStatTargetBin("top99"))
        self.assertEqual("top50", self.ns.GetStatTargetBin())
        self.assertEqual({"audit": 1, "indicators": 1}, self.calls)

    def test_set_stat_target_bin_drops_the_cached_provider_views(self) -> None:
        repo = self.ns.ProfileRepository
        dropped = []
        original = repo.InvalidateProviderViews
        repo.InvalidateProviderViews = lambda: (dropped.append(True), original())
        self.assertTrue(repo.SetStatTargetBin("top80"))
        self.assertEqual([True], dropped)
        self.assertFalse(repo.SetStatTargetBin("junk"))
        self.assertEqual([True], dropped)

    def test_raider_io_helpers_are_gone(self) -> None:
        for name in ("IsBenchmarkRelevant", "IsBenchmarkSampleSmall", "GetBenchmarkLevel",
                     "SetBenchmarkLevel", "GetBenchmarkLevels", "GetBenchmarkLevelInfo"):
            self.assertIsNone(self.ns[name], name)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class CoreProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_WeightModes.lua")

    def test_wording_is_best_in_slot_for_every_goal(self) -> None:
        for goal in ("MYTHIC_PLUS", "RAID", "PVP"):
            wording = self.ns.GetReferenceWording(goal)
            self.assertEqual("Best in Slot", wording.button, goal)
            self.assertEqual("Main Spec Best in Slot", wording.main, goal)
            self.assertEqual("Off Spec Best in Slot", wording.off, goal)
            self.assertEqual("BiS Progress", wording.progress, goal)
            self.assertEqual("BIS", wording.tag, goal)
            self.assertFalse(wording.popular, goal)

    def build_runtime(self, build_id: str | None = None, targets: dict | None = None, weights: dict | None = None,
                      weight_mode: str | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        build_id = build_id or now_build_id()
        targets_path = Path(self.tmp.name) / "SV_ClassCodexTargets.lua"
        targets_path.write_text(render_targets_lua(targets or make_classcodex_targets(build_id)), encoding="utf-8")
        weights_path = Path(self.tmp.name) / "SV_ClassCodexWeights.lua"
        weights_path.write_text(render_weights_lua(weights or make_classcodex_weights(build_id)), encoding="utf-8")
        lua = new_runtime()
        ns = lua.table()
        lua.globals().StatVerdictDB = lua.table(weightMode=weight_mode)
        load = lua.eval("function(path, ns) local f = assert(loadfile(path)) f('StatVerdict', ns) end")
        load(str(targets_path), ns)
        load(str(weights_path), ns)
        for relative in ("Core/SV_SpecMeta.lua", "Core/SV_ProfileRepository.lua", "Core/SV_ItemReferenceBonuses.lua"):
            load_addon_file(lua, ns, relative)
        return lua, ns

    def context(self, lua, **extra):
        table = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS", role="TANK", specID=250,
                          classFile="DEATHKNIGHT", heroTalentName="San'layn")
        for key, value in extra.items():
            table[key] = value
        return table

    def targets(self, profile) -> dict:
        rows = profile.auditTargets.rows
        return {rows[i].key: rows[i].target for i in range(1, len(rows) + 1)}

    def test_context_is_looked_up_per_hero_talent(self) -> None:
        lua, ns = self.build_runtime()
        repo = ns.ProfileRepository
        sanlayn = repo.GetContext("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn")
        self.assertEqual(1140, sanlayn.targets.statTargets.stats.critical_strike)
        deathbringer = repo.GetContext("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "deathbringer")
        self.assertEqual(1300, deathbringer.targets.statTargets.stats.critical_strike)
        self.assertIsNone(repo.GetContext("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", None))
        self.assertIsNone(repo.GetContext("DEATHKNIGHT_BLOOD", "RAID", "deathbringer"))
        self.assertIsNone(repo.GetContext("MAGE_FIRE", "MYTHIC_PLUS", "sunfury"))
        self.assertIsNone(repo.GetContext("DEATHKNIGHT_BLOOD", "NOT_A_GOAL", "sanlayn"))

    def test_hero_talent_names_resolve_to_classcodex_keys(self) -> None:
        lua, ns = self.build_runtime()
        resolve = ns.ProfileRepository.ResolveHeroKey
        self.assertEqual("sanlayn", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "San'layn", 31))
        self.assertEqual("deathbringer", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "Deathbringer", None))
        self.assertEqual("master-of-harmony", resolve("MONK_BREWMASTER", "MYTHIC_PLUS", "Master of Harmony", None))
        # A hero tree without data for this goal never borrows another tree's data.
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "RAID", "Deathbringer", 33))
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "Rider of the Apocalypse", 32))
        self.assertIsNone(resolve("MAGE_FIRE", "MYTHIC_PLUS", "Sunfury", None))
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "Not A Hero Tree", None))

    def test_hero_subtree_id_resolves_before_the_name(self) -> None:
        # Non-English clients get translated hero tree names; the subtree ID does not change.
        lua, ns = self.build_runtime()
        resolve = ns.ProfileRepository.ResolveHeroKey
        self.assertEqual("deathbringer", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "Todesbringer", 33))
        self.assertEqual("sanlayn", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "산레인", 31))
        # A known ID wins over a name that points elsewhere, and is not a guess.
        self.assertEqual("sanlayn", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "Deathbringer", 31))
        self.assertEqual("sanlayn", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", None, 31))  # not ("sanlayn", True)
        # A known ID whose tree has no data for this goal never falls back to a name or guess.
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "RAID", "San'layn", 33))
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "San'layn", 32))
        # An unknown ID falls back to the name.
        self.assertEqual("deathbringer", resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "Deathbringer", 9999))

    def test_profile_and_boosts_use_the_hero_subtree_id(self) -> None:
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(
            self.context(lua, heroTalentName="Todesbringer", heroSubTreeID=33))
        self.assertEqual("deathbringer", profile.heroKey)
        self.assertFalse(profile.heroKeyGuessed)
        ns.GetSnapshotHeroTalentName = lambda profile: "Todesbringer"
        ns.GetSnapshotHeroSubTreeID = lambda profile: 33
        bare = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1500", bare).bonus)
        named = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS", heroTalentName="San'layn", heroSubTreeID=31)
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1000", named).bonus)

    def test_missing_hero_tree_name_guesses_the_first_key_in_sorted_order(self) -> None:
        lua, ns = self.build_runtime()
        resolve = ns.ProfileRepository.ResolveHeroKey
        # No hero tree yet (below hero-talent level, or a snapshot without it):
        # the first key in sorted order, flagged as a guess.
        self.assertEqual(("deathbringer", True), resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", None, None))
        self.assertEqual(("deathbringer", True), resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "", None))
        self.assertEqual(("deathbringer", True), resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "", 9999))
        self.assertEqual(("sanlayn", True), resolve("DEATHKNIGHT_BLOOD", "RAID", None, None))
        self.assertIsNone(resolve("MAGE_FIRE", "MYTHIC_PLUS", None, None))
        context = self.context(lua)
        context.heroTalentName = None
        profile = ns.ProfileRepository.BuildRuntimeProfile(context)
        self.assertEqual("deathbringer", profile.heroKey)
        self.assertTrue(profile.heroKeyGuessed)
        self.assertEqual(1300.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])
        named = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertFalse(named.heroKeyGuessed)

    def test_profile_is_built_from_the_players_hero_context(self) -> None:
        lua, ns = self.build_runtime()
        sanlayn = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertFalse(sanlayn.invalidGeneratedContext)
        self.assertEqual("sanlayn", sanlayn.heroKey)
        self.assertEqual("ITEM_MOD_STRENGTH_SHORT", sanlayn.primaryStat)
        self.assertEqual(1140.0, self.targets(sanlayn)["ITEM_MOD_CRIT_RATING_SHORT"])
        self.assertEqual("ITEM_MOD_HASTE_RATING_SHORT", sanlayn.secondaryOrder[1])
        deathbringer = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroTalentName="Deathbringer"))
        self.assertEqual("deathbringer", deathbringer.heroKey)
        self.assertEqual(1300.0, self.targets(deathbringer)["ITEM_MOD_CRIT_RATING_SHORT"])
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", deathbringer.secondaryOrder[1])
        self.assertEqual(1500, deathbringer.generatedContext.bis.slots[1].item.item_id)

    def test_hero_name_falls_back_to_the_spec_snapshot(self) -> None:
        lua, ns = self.build_runtime()
        ns.GetSnapshotHeroTalentName = lambda context: "Deathbringer"
        context = self.context(lua)
        context.heroTalentName = None
        self.assertEqual("deathbringer", ns.ProfileRepository.BuildRuntimeProfile(context).heroKey)

    def test_unknown_or_missing_hero_tree_gives_no_data(self) -> None:
        lua, ns = self.build_runtime()
        build = ns.ProfileRepository.BuildRuntimeProfile
        self.assertIsNone(build(self.context(lua, heroTalentName="Rider of the Apocalypse")))
        self.assertIsNone(build(self.context(lua, heroTalentName="Not A Hero Tree")))
        self.assertIsNone(build(self.context(lua, goal="RAID", heroTalentName="Deathbringer")))

    def test_raid_and_pvp_are_read_from_the_classcodex_file(self) -> None:
        lua, ns = self.build_runtime()
        raid = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal="RAID"))
        self.assertEqual("RAID", raid.goal)
        self.assertEqual(1200.0, self.targets(raid)["ITEM_MOD_CRIT_RATING_SHORT"])
        pvp = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal="PVP"))
        self.assertFalse(pvp.invalidGeneratedContext)  # PvP gear carries no item level
        self.assertEqual(800.0, self.targets(pvp)["ITEM_MOD_VERSATILITY"])
        self.assertEqual("ITEM_MOD_VERSATILITY", pvp.secondaryOrder[1])

    def test_mythic_plus_with_an_implausible_item_level_is_rejected(self) -> None:
        build_id = now_build_id()
        data = make_classcodex_targets(build_id)
        data["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"]["targets"]["averageItemLevel"] = 100
        pvp = data["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["PVP"]["heroTalents"]["sanlayn"]
        pvp["targets"]["averageItemLevel"] = 100  # an item level PvP does carry is still checked
        lua, ns = self.build_runtime(build_id=build_id, targets=data)
        for goal in ("MYTHIC_PLUS", "PVP"):
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal=goal))
            self.assertTrue(profile.invalidGeneratedContext, goal)
            self.assertEqual(0, len(profile.auditTargets.rows), goal)
        data["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["RAID"]["heroTalents"]["sanlayn"]["targets"].pop("averageItemLevel")
        lua, ns = self.build_runtime(build_id=build_id, targets=data)
        raid = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal="RAID"))
        self.assertTrue(raid.invalidGeneratedContext)  # only PvP may lack an item level

    def test_too_few_reference_items_is_rejected(self) -> None:
        build_id = now_build_id()
        data = make_classcodex_targets(build_id)
        context = data["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"]
        context["bis"]["slots"] = context["bis"]["slots"][:5]
        lua, ns = self.build_runtime(build_id=build_id, targets=data)
        self.assertTrue(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)).invalidGeneratedContext)

    def test_stale_data_fails_closed(self) -> None:
        lua, ns = self.build_runtime(build_id=now_build_id(days_ago=40))
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))
        self.assertIsNone(ns.ProfileRepository.GetContext("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn"))
        self.assertFalse(ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS").available)

    FIXED_ZONE = """
    -- A fake clock in a fixed time zone UTC+offset: time(t) reads t as local time.
    local offset, now = ...
    local function days_from_civil(y, m, d)
        if m <= 2 then y = y - 1 end
        local era = math.floor(y / 400)
        local yoe = y - era * 400
        local doy = math.floor((153 * ((m + 9) % 12) + 2) / 5) + d - 1
        return era * 146097 + yoe * 365 + math.floor(yoe / 4) - math.floor(yoe / 100) + doy - 719468
    end
    time = function(t)
        if t == nil then return now end
        return days_from_civil(t.year, t.month, t.day) * 86400
            + (t.hour or 12) * 3600 + (t.min or 0) * 60 + (t.sec or 0) - offset
    end
    date = function(format, t)
        if format == "!*t" then return os.date("!*t", t) end
        if format == "*t" then return os.date("!*t", t + offset) end
        error("unsupported format " .. tostring(format))
    end
    """

    def test_build_time_is_read_as_utc_in_any_time_zone(self) -> None:
        build_utc = int(datetime(2026, 9, 29, 6, 49, 54, tzinfo=timezone.utc).timestamp())
        for hours in (14, 3, 0, -10):
            lua, ns = self.build_runtime()
            lua.eval("function(src, offset, now) assert(loadstring(src))(offset, now) end")(
                self.FIXED_ZONE, hours * 3600, build_utc)
            self.assertEqual(build_utc, ns.ProfileRepository.ParseBuildTime("20260929064954-6702fd4-878715d1"), hours)
        # And on this machine's real clock and zone.
        lua, ns = self.build_runtime()
        now = int(datetime.now(timezone.utc).timestamp())
        self.assertLessEqual(abs(ns.ProfileRepository.ParseBuildTime(now_build_id()) - now), 5)

    def test_freshness_does_not_shift_with_the_time_zone(self) -> None:
        # 29 days 20 hours old: fresh everywhere. Read as local time at UTC+10 it
        # would look 30 days 6 hours old and be dropped as stale.
        build = datetime(2026, 9, 29, 6, 49, 54, tzinfo=timezone.utc)
        now = int((build + timedelta(days=29, hours=20)).timestamp())
        lua, ns = self.build_runtime(build_id=build.strftime("%Y%m%d%H%M%S") + "-6702fd4-878715d1")
        lua.eval("function(src, offset, now) assert(loadstring(src))(offset, now) end")(self.FIXED_ZONE, 36000, now)
        self.assertTrue(ns.ProfileRepository.GetDataProvenance("MYTHIC_PLUS").available)

    def test_build_time_without_date_still_parses(self) -> None:
        lua, ns = self.build_runtime()
        lua.execute("date = nil")
        self.assertIsNotNone(ns.ProfileRepository.ParseBuildTime(now_build_id()))

    def test_garbage_build_id_fails_closed(self) -> None:
        lua, ns = self.build_runtime(build_id="not-a-date")
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))

    def test_provider_view_lists_specs_from_the_classcodex_file(self) -> None:
        lua, ns = self.build_runtime()
        ns.GetSnapshotHeroTalentName = lambda context: "San'layn"
        provider = ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual("sanlayn", provider["DEATHKNIGHT"][250].default.heroKey)
        pvp = ns.ProfileRepository.RefreshProviderView("PVP")
        self.assertIsNotNone(pvp["DEATHKNIGHT"][250].default)

    def count_profile_builds(self, lua, ns):
        counter = {"n": 0}
        original = ns.ProfileRepository.BuildRuntimeProfile

        def counting(context):
            counter["n"] += 1
            return original(context)

        ns.ProfileRepository.BuildRuntimeProfile = counting
        return counter

    def test_provider_view_is_cached_until_its_inputs_change(self) -> None:
        lua, ns = self.build_runtime()
        load_addon_file(lua, ns, "Core/SV_ProfileLoader.lua")
        hero = {"name": "San'layn", "id": 31}
        ns.GetSnapshotHeroTalentName = lambda context: hero["name"]
        ns.GetSnapshotHeroSubTreeID = lambda context: hero["id"]
        ns.GetStatAuditGoalMode = lambda: "MYTHIC_PLUS"
        builds = self.count_profile_builds(lua, ns)
        repo = ns.ProfileRepository
        first = repo.RefreshProviderView("MYTHIC_PLUS")
        per_view = builds["n"]
        self.assertGreater(per_view, 0)
        # Tooltips and bag items call this path over and over: no rebuild.
        for _ in range(5):
            self.assertTrue(lua.eval("rawequal")(first, repo.RefreshProviderView("MYTHIC_PLUS")))
            self.assertTrue(lua.eval("rawequal")(first, repo.GetProviderView("MYTHIC_PLUS")))
        self.assertEqual(per_view, builds["n"])
        for _ in range(5):
            ns.LoadEvaluationProfile(self.context(lua))
        self.assertEqual(per_view + 5, builds["n"])  # only the player's own profile each time
        self.assertTrue(lua.eval("rawequal")(first, ns.ProfileProviders.Generated))
        # Another goal has its own view; switching back reuses the cached one.
        repo.RefreshProviderView("RAID")
        after_raid = builds["n"]
        self.assertTrue(lua.eval("rawequal")(first, repo.RefreshProviderView("MYTHIC_PLUS")))
        self.assertTrue(lua.eval("rawequal")(first, ns.ProfileProviders.Generated))
        self.assertEqual(after_raid, builds["n"])
        # A new hero tree in the spec snapshot changes the input: rebuilt once.
        hero.update(name="Deathbringer", id=33)
        rebuilt = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual("deathbringer", rebuilt["DEATHKNIGHT"][250].default.heroKey)
        self.assertEqual(after_raid + per_view, builds["n"])
        repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual(after_raid + per_view, builds["n"])
        # Explicit invalidation forces a rebuild.
        repo.InvalidateProviderViews()
        repo.GetProviderView("MYTHIC_PLUS")
        self.assertEqual(after_raid + 2 * per_view, builds["n"])

    def test_provider_view_empties_when_the_data_goes_stale(self) -> None:
        lua, ns = self.build_runtime()
        view = ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")
        self.assertIsNotNone(view["DEATHKNIGHT"])
        ns.ClassCodexTargets.buildId = now_build_id(days_ago=40)
        self.assertIsNone(ns.ProfileRepository.RefreshProviderView("MYTHIC_PLUS")["DEATHKNIGHT"])

    def test_provenance_uses_the_classcodex_build_date(self) -> None:
        lua, ns = self.build_runtime()
        for goal in ("MYTHIC_PLUS", "RAID", "PVP"):
            info = ns.ProfileRepository.GetDataProvenance(goal)
            self.assertTrue(info.available, goal)
            self.assertEqual("StatVerdict ClassCodex data", info.sourceName)
            self.assertEqual(datetime.now(timezone.utc).strftime("%Y-%m-%d"), info.scrape)
        self.assertFalse(ns.ProfileRepository.GetDataProvenance(None).available)

    def test_measured_weights_are_exposed_per_hero_talent(self) -> None:
        lua, ns = self.build_runtime()
        weights = ns.ProfileRepository.GetWeights("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn")
        self.assertEqual(1.0, weights.haste)
        self.assertEqual(0.8, weights.critical_strike)
        self.assertIsNone(ns.ProfileRepository.GetWeights("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "deathbringer"))
        self.assertIsNone(ns.ProfileRepository.GetWeights("DEATHKNIGHT_BLOOD", "RAID", "sanlayn"))
        self.assertIsNone(ns.ProfileRepository.GetWeights("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", None))

    def test_bis_items_and_trinkets_keep_their_boosts(self) -> None:
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        helm = ns.GetItemReferenceInfo("item:1000", profile)
        self.assertEqual(8, helm.bonus)
        self.assertIsNotNone(helm.bis)
        # The two S trinkets are also in the BiS list, so they get the +8 list bonus
        # on top of their tier bonus.
        alpha = ns.GetItemReferenceInfo("item:5001", profile)
        self.assertEqual("S", alpha.trinket.tier)
        self.assertEqual(108, alpha.bonus)  # list 8 + tier 95 + rank bonus 5
        gamma = ns.GetItemReferenceInfo("item:5003", profile)
        self.assertEqual(107, gamma.bonus)  # list 8 + tier 95 + rank bonus 4
        beta = ns.GetItemReferenceInfo("item:5002", profile)
        self.assertEqual("A", beta.trinket.tier)
        self.assertEqual(70, beta.bonus)  # tier 65 + rank bonus 5 (not in the BiS list)
        self.assertIsNone(ns.GetItemReferenceInfo("item:1500", profile))  # the other hero tree's helm
        self.assertIsNone(ns.GetItemReferenceInfo("item:999999", profile))

    def test_boost_follows_the_players_hero_tree(self) -> None:
        lua, ns = self.build_runtime()
        deathbringer = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroTalentName="Deathbringer"))
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1500", deathbringer).bonus)
        self.assertIsNone(ns.GetItemReferenceInfo("item:1000", deathbringer))

    def test_boost_resolves_the_hero_tree_for_a_bare_profile(self) -> None:
        lua, ns = self.build_runtime()
        named = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS", heroTalentName="Deathbringer")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1500", named).bonus)
        ns.GetSnapshotHeroTalentName = lambda profile: "San'layn"
        by_spec_id = lua.table(specID=250, goal="MYTHIC_PLUS")
        ns.GetStatVerdictSpecKeyBySpecID = lua.eval("function(id) return id == 250 and 'DEATHKNIGHT_BLOOD' or nil end")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1000", by_spec_id).bonus)
        ns.GetSnapshotHeroTalentName = lambda profile: None
        self.assertIsNone(ns.GetItemReferenceInfo("item:1000", lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")))

    def test_pvp_and_raid_lists_give_boosts_too(self) -> None:
        lua, ns = self.build_runtime()
        for goal in ("RAID", "PVP"):
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, goal=goal))
            info = ns.GetItemReferenceInfo("item:5001", profile)
            self.assertEqual(goal, info.goal)
            self.assertEqual(108, info.bonus, goal)
            self.assertIsNone(info.catalystPath)  # no catalyst data in ClassCodex BiS lists

    def order(self, profile) -> list[str]:
        return [profile.secondaryOrder[i] for i in range(1, len(profile.secondaryOrder) + 1)]

    def test_measured_weights_order_the_secondaries(self) -> None:
        lua, ns = self.build_runtime(weight_mode="MEASURED")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        # ClassCodex priority is haste > crit > mastery > vers; SimC measured vers above mastery.
        self.assertEqual([SECONDARY["haste"], SECONDARY["crit"], SECONDARY["vers"], SECONDARY["mastery"]], self.order(profile))
        self.assertEqual(1.0, profile.secondaryWeights[SECONDARY["haste"]])
        self.assertEqual(0.5, profile.secondaryWeights[SECONDARY["mastery"]])
        rows = profile.auditTargets.rows
        self.assertEqual([SECONDARY["haste"], SECONDARY["crit"], SECONDARY["vers"], SECONDARY["mastery"]],
                         [rows[i].key for i in range(1, len(rows) + 1)])

    def test_stat_audit_base_modifiers_match_the_scoring_weights(self) -> None:
        lua, ns = self.build_runtime(weight_mode="MEASURED")
        load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        rows = profile.auditTargets.rows
        base = {rows[i].key: rows[i].baseModifier for i in range(1, len(rows) + 1)}
        # haste 1.0, crit 0.8, vers 0.6, mastery 0.5 share the rank total 4+3+2+1 = 10.
        total = 1.0 + 0.8 + 0.6 + 0.5
        for stat, weight in (("haste", 1.0), ("crit", 0.8), ("vers", 0.6), ("mastery", 0.5)):
            self.assertAlmostEqual(10 * weight / total, base[SECONDARY[stat]], msg=stat)
            self.assertEqual(ns.GetMeasuredSecondaryRawWeight(profile, SECONDARY[stat]), base[SECONDARY[stat]])
        # Without measured weights the rows keep the rank weights.
        plain = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroTalentName="Deathbringer"))
        rows = plain.auditTargets.rows
        self.assertEqual([4.0, 3.0, 2.0, 1.0], [rows[i].baseModifier for i in range(1, len(rows) + 1)])

    def test_hero_tree_without_weights_keeps_the_classcodex_priority(self) -> None:
        lua, ns = self.build_runtime(weight_mode="MEASURED")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroTalentName="Deathbringer"))
        self.assertIsNone(profile.secondaryWeights)
        self.assertEqual([SECONDARY["crit"], SECONDARY["mastery"], SECONDARY["vers"], SECONDARY["haste"]], self.order(profile))

    def test_tied_or_missing_weights_fall_back_to_the_classcodex_priority(self) -> None:
        build_id = now_build_id()
        weights = make_classcodex_weights(build_id)
        weights["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"] = {
            "critical_strike": 1.0, "haste": 1.0, "versatility": 0.4, "mastery": "junk",
        }
        lua, ns = self.build_runtime(build_id=build_id, weights=weights, weight_mode="MEASURED")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        # haste/crit tie -> priority order (haste first); mastery has no usable weight -> after
        # the measured stats.
        self.assertEqual([SECONDARY["haste"], SECONDARY["crit"], SECONDARY["vers"], SECONDARY["mastery"]], self.order(profile))
        self.assertIsNone(profile.secondaryWeights[SECONDARY["mastery"]])

    def test_weights_that_are_all_unusable_mean_no_weights(self) -> None:
        build_id = now_build_id()
        weights = make_classcodex_weights(build_id)
        weights["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"] = {
            "critical_strike": 0, "haste": -1,
        }
        lua, ns = self.build_runtime(build_id=build_id, weights=weights, weight_mode="MEASURED")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertIsNone(profile.secondaryWeights)
        self.assertEqual(SECONDARY["haste"], profile.secondaryOrder[1])

    # --- Stat weight mode: GUIDE (default) / MEASURED / BLEND -----------------
    # Fixture San'layn: guide haste > crit > mastery > vers; SimC measured
    # haste 1.0, crit 0.8, vers 0.6, mastery 0.5 (vers above mastery: they disagree).
    GUIDE_ORDER = ("haste", "crit", "mastery", "vers")
    MEASURED_ORDER = ("haste", "crit", "vers", "mastery")

    def keys(self, *names: str) -> list[str]:
        return [SECONDARY[name] for name in names]

    def weight_table(self, profile) -> dict | None:
        weights = profile.secondaryWeights
        return None if weights is None else {key: weights[key] for key in weights.keys()}

    def base_modifiers(self, profile) -> list[float]:
        rows = profile.auditTargets.rows
        return [rows[i].baseModifier for i in range(1, len(rows) + 1)]

    def test_weight_mode_defaults_to_guide(self) -> None:
        lua, ns = self.build_runtime()
        self.assertEqual("GUIDE", ns.ProfileRepository.DEFAULT_WEIGHT_MODE)
        self.assertEqual("GUIDE", ns.ProfileRepository.GetWeightMode())
        for mode in ("GUIDE", "MEASURED", "BLEND"):
            lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual(mode, ns.ProfileRepository.GetWeightMode())

    def test_garbage_saved_weight_mode_falls_back_to_default(self) -> None:
        lua, ns = self.build_runtime()
        for garbage in ("nonsense", "guide", 3, lua.table()):
            lua.globals().StatVerdictDB.weightMode = garbage
            self.assertEqual("GUIDE", ns.ProfileRepository.GetWeightMode(), garbage)
        lua.globals().StatVerdictDB = None
        self.assertEqual("GUIDE", ns.ProfileRepository.GetWeightMode())
        lua.globals().StatVerdictDB = lua.table(weightMode="junk")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(profile))
        self.assertIsNone(profile.secondaryWeights)

    def test_guide_mode_follows_the_priority_list_only(self) -> None:
        lua, ns = self.build_runtime(weight_mode="GUIDE")
        load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(profile))
        self.assertIsNone(profile.secondaryWeights)
        self.assertEqual([4.0, 3.0, 2.0, 1.0], self.base_modifiers(profile))

    def test_guide_mode_scores_exactly_like_the_no_weights_path(self) -> None:
        # Same regression promise as ScoringWeightTests.test_without_measured_weights_
        # the_rank_weights_are_unchanged: GUIDE must be the pre-measured-weights scoring,
        # i.e. identical to a runtime that has no weights file at all.
        guide_lua, guide_ns = self.build_runtime(weight_mode="GUIDE")
        plain_lua, plain_ns = self.build_runtime(weight_mode="MEASURED")
        plain_ns.ClassCodexWeights = None
        for lua, ns in ((guide_lua, guide_ns), (plain_lua, plain_ns)):
            load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
            ns.GetDynamicStatWeight = lambda profile, key, weight: weight
        stat_keys = [STRENGTH, *SECONDARY.values(), "STATVERDICT_ITEM_LEVEL", "STATVERDICT_MAIN_HAND_DPS"]
        for goal in ("MYTHIC_PLUS", "RAID", "PVP"):
            guide = guide_ns.ProfileRepository.BuildRuntimeProfile(self.context(guide_lua, goal=goal))
            plain = plain_ns.ProfileRepository.BuildRuntimeProfile(self.context(plain_lua, goal=goal))
            self.assertEqual(self.order(plain), self.order(guide), goal)
            self.assertIsNone(guide.secondaryWeights)
            self.assertEqual(self.base_modifiers(plain), self.base_modifiers(guide), goal)
            for key in stat_keys:
                self.assertEqual(plain_ns.GetDefaultStatWeight(plain, key), guide_ns.GetDefaultStatWeight(guide, key), key)
                for delta in (10, -10):
                    self.assertEqual(plain_ns.GetDeltaAdjustedStatWeight(plain, key, delta, 1.0),
                                     guide_ns.GetDeltaAdjustedStatWeight(guide, key, delta, 1.0), (key, delta))

    def test_measured_mode_sorts_by_the_measured_weights(self) -> None:
        lua, ns = self.build_runtime(weight_mode="MEASURED")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.keys(*self.MEASURED_ORDER), self.order(profile))
        self.assertEqual({SECONDARY["haste"]: 1.0, SECONDARY["crit"]: 0.8, SECONDARY["vers"]: 0.6,
                          SECONDARY["mastery"]: 0.5}, self.weight_table(profile))

    def test_blend_mode_keeps_the_guide_order_and_mixes_the_weights(self) -> None:
        lua, ns = self.build_runtime(weight_mode="BLEND")
        load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(profile))
        # Guide rank weights 4/3/2/1 over the top one: 1.0 / 0.75 / 0.5 / 0.25,
        # mixed 50/50 with the measured weights; the max is already 1.0.
        expected = {"haste": 0.5 * 1.0 + 0.5 * 1.0, "crit": 0.5 * 0.75 + 0.5 * 0.8,
                    "mastery": 0.5 * 0.5 + 0.5 * 0.5, "vers": 0.5 * 0.25 + 0.5 * 0.6}
        weights = self.weight_table(profile)
        self.assertEqual(set(self.keys(*expected)), set(weights))
        for name, value in expected.items():
            self.assertAlmostEqual(value, weights[SECONDARY[name]], msg=name)
        # Same downstream path as measured weights: the audit rows show the scoring weight.
        rows = profile.auditTargets.rows
        for i in range(1, len(rows) + 1):
            self.assertEqual(ns.GetMeasuredSecondaryRawWeight(profile, rows[i].key), rows[i].baseModifier)

    def test_blend_mode_renormalises_and_leaves_unmeasured_stats_on_the_guide(self) -> None:
        build_id = now_build_id()
        weights = make_classcodex_weights(build_id)
        weights["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"] = {
            "critical_strike": 1.0, "haste": 0.4, "versatility": 0.6, "mastery": "junk",
        }
        lua, ns = self.build_runtime(build_id=build_id, weights=weights, weight_mode="BLEND")
        load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(profile))
        # haste 0.5+0.2 = 0.7, crit 0.375+0.5 = 0.875, vers 0.125+0.3 = 0.425; / 0.875.
        weights = self.weight_table(profile)
        self.assertEqual(set(self.keys("haste", "crit", "vers")), set(weights))
        self.assertAlmostEqual(0.7 / 0.875, weights[SECONDARY["haste"]])
        self.assertAlmostEqual(1.0, weights[SECONDARY["crit"]])
        self.assertAlmostEqual(0.425 / 0.875, weights[SECONDARY["vers"]])

    def test_blend_mode_without_measured_weights_is_pure_guide(self) -> None:
        lua, ns = self.build_runtime(weight_mode="BLEND")
        load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroTalentName="Deathbringer"))
        self.assertIsNone(profile.secondaryWeights)
        self.assertEqual(self.keys("crit", "mastery", "vers", "haste"), self.order(profile))
        self.assertEqual([4.0, 3.0, 2.0, 1.0], self.base_modifiers(profile))

    def test_blend_mode_gives_tied_guide_stats_the_same_guide_share(self) -> None:
        build_id = now_build_id()
        targets = make_classcodex_targets(build_id)
        context = targets["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"]
        context["priorityProfiles"][0]["tiers"] = [["critical_strike", "mastery"]]
        weights = make_classcodex_weights(build_id)
        weights["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"] = {
            "critical_strike": 0.5, "haste": 1.0, "versatility": 0.5, "mastery": 0.5,
        }
        lua, ns = self.build_runtime(build_id=build_id, targets=targets, weights=weights, weight_mode="BLEND")
        load_addon_file(lua, ns, "Core/SV_Modifiers.lua")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        weights = self.weight_table(profile)
        # crit (rank 2) and mastery (rank 3) are one guide tier: both use rank 2's 0.75.
        self.assertAlmostEqual(0.5 * 0.75 + 0.25, weights[SECONDARY["crit"]])
        self.assertAlmostEqual(0.5 * 0.75 + 0.25, weights[SECONDARY["mastery"]])

    def test_switching_weight_mode_rebuilds_the_cached_provider_view(self) -> None:
        lua, ns = self.build_runtime()
        ns.GetSnapshotHeroTalentName = lambda context: "San'layn"
        repo = ns.ProfileRepository
        guide = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(guide["DEATHKNIGHT"][250].default))
        self.assertTrue(lua.eval("rawequal")(guide, repo.RefreshProviderView("MYTHIC_PLUS")))
        self.assertTrue(repo.SetWeightMode("MEASURED"))
        measured = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertFalse(lua.eval("rawequal")(guide, measured))
        self.assertEqual(self.keys(*self.MEASURED_ORDER), self.order(measured["DEATHKNIGHT"][250].default))
        # A saved value changed behind the repository's back also counts as a new input.
        lua.globals().StatVerdictDB.weightMode = "GUIDE"
        again = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(again["DEATHKNIGHT"][250].default))
        self.assertFalse(repo.SetWeightMode("bogus"))
        self.assertEqual("GUIDE", lua.globals().StatVerdictDB.weightMode)

    # --- Stat targets follow the mode too -------------------------------------
    # Fixture San'layn M+ own targets (BiS gear): crit 1140, haste 900, mastery 680,
    # vers 430. Guide (u.gg, as the ClassCodex addon shows): top20 has no mastery.
    OWN_TARGETS = {"crit": 1140.0, "haste": 900.0, "mastery": 680.0, "vers": 430.0}
    GUIDE_BINS = {"top20": (1000, 1200, None, 300), "top50": (900, 1000, 600, 250), "top80": (800, 900, 550, 200)}

    def guide_runtime(self, weight_mode: str | None = None, bins: dict | None = None):
        build_id = now_build_id()
        targets = add_guide_targets(make_classcodex_targets(build_id), "DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn",
                                    make_guide_targets(**(self.GUIDE_BINS if bins is None else bins)))
        return self.build_runtime(build_id=build_id, targets=targets, weight_mode=weight_mode)

    def named_targets(self, profile) -> dict[str, float]:
        by_key = self.targets(profile)
        return {name: by_key[key] for name, key in SECONDARY.items() if key in by_key}

    def test_guide_mode_shows_the_classcodex_top20_targets(self) -> None:
        lua, ns = self.guide_runtime()
        self.assertEqual("top20", ns.ProfileRepository.DEFAULT_STAT_TARGET_BIN)
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        # mastery is not in the guide's top20: our own target fills that stat.
        self.assertEqual({"crit": 1000.0, "haste": 1200.0, "mastery": 680.0, "vers": 300.0}, self.named_targets(profile))
        self.assertEqual("top20", profile.statTargetBin)
        self.assertFalse(profile.guideTargetsMissing)
        self.assertEqual("GUIDE", profile.auditTargets.targetMode)
        # Priority order is still the guide's.
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(profile))

    def test_saved_stat_target_bin_picks_the_guide_bin(self) -> None:
        lua, ns = self.guide_runtime()
        repo = ns.ProfileRepository
        for bin_key, expected in (("top50", (900, 1000, 600, 250)), ("top80", (800, 900, 550, 200))):
            lua.globals().StatVerdictDB.statTargetBin = bin_key
            self.assertEqual(bin_key, repo.GetStatTargetBin())
            profile = repo.BuildRuntimeProfile(self.context(lua))
            self.assertEqual(dict(zip(("crit", "haste", "mastery", "vers"), map(float, expected))),
                             self.named_targets(profile), bin_key)
            self.assertEqual(bin_key, profile.statTargetBin)
        for garbage in ("top99", "TOP50", 50, lua.table()):
            lua.globals().StatVerdictDB.statTargetBin = garbage
            self.assertEqual("top20", repo.GetStatTargetBin(), garbage)
        lua.globals().StatVerdictDB = None
        self.assertEqual("top20", repo.GetStatTargetBin())

    def test_guide_mode_without_classcodex_targets_uses_our_own(self) -> None:
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.OWN_TARGETS, self.named_targets(profile))
        self.assertTrue(profile.guideTargetsMissing)
        # A guide without the chosen bin (or with nothing usable in it) counts as missing too.
        for bins in ({"top50": (900, 1000, 600, 250)}, {"top20": (None, None, None, None)}):
            lua, ns = self.guide_runtime(bins=bins)
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
            self.assertEqual(self.OWN_TARGETS, self.named_targets(profile), bins)
            self.assertTrue(profile.guideTargetsMissing, bins)

    def test_measured_mode_keeps_our_own_targets(self) -> None:
        lua, ns = self.guide_runtime(weight_mode="MEASURED")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.OWN_TARGETS, self.named_targets(profile))
        self.assertEqual(self.keys(*self.MEASURED_ORDER), self.order(profile))
        self.assertEqual("MEASURED", profile.auditTargets.targetMode)

    def test_blend_mode_averages_guide_and_own_targets(self) -> None:
        lua, ns = self.guide_runtime(weight_mode="BLEND")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        # mastery has no guide target: it keeps ours.
        self.assertEqual({"crit": (1000 + 1140) / 2, "haste": (1200 + 900) / 2, "mastery": 680.0,
                          "vers": (300 + 430) / 2}, self.named_targets(profile))
        self.assertEqual(self.keys(*self.GUIDE_ORDER), self.order(profile))
        lua.globals().StatVerdictDB.statTargetBin = "top50"
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual((680 + 600) / 2, self.named_targets(profile)["mastery"])
        # Without guide targets BLEND shows our own.
        plain_lua, plain_ns = self.build_runtime(weight_mode="BLEND")
        plain = plain_ns.ProfileRepository.BuildRuntimeProfile(self.context(plain_lua))
        self.assertEqual(self.OWN_TARGETS, self.named_targets(plain))

    def test_blend_uses_the_guide_target_when_ours_is_missing(self) -> None:
        build_id = now_build_id()
        targets = add_guide_targets(make_classcodex_targets(build_id), "DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn",
                                    make_guide_targets(top20=(1000, 1200, 500, 300)))
        stats = targets["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"][
            "targets"]["statTargets"]["stats"]
        del stats["mastery"]
        lua, ns = self.build_runtime(build_id=build_id, targets=targets, weight_mode="BLEND")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(500.0, self.named_targets(profile)["mastery"])

    def test_quality_checks_still_read_our_own_targets(self) -> None:
        build_id = now_build_id()
        targets = add_guide_targets(make_classcodex_targets(build_id), "DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn",
                                    make_guide_targets(**self.GUIDE_BINS))
        context = targets["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"]
        context["targets"]["statTargets"]["stats"] = {"haste": 900}
        lua, ns = self.build_runtime(build_id=build_id, targets=targets)
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertTrue(profile.invalidGeneratedContext)
        self.assertEqual([], [profile.auditTargets.rows[i] for i in range(1, len(profile.auditTargets.rows) + 1)])

    def test_changing_the_stat_target_bin_rebuilds_the_cached_provider_view(self) -> None:
        lua, ns = self.guide_runtime()
        ns.GetSnapshotHeroTalentName = lambda context: "San'layn"
        repo = ns.ProfileRepository
        top20 = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual(1000.0, self.named_targets(top20["DEATHKNIGHT"][250].default)["crit"])
        lua.globals().StatVerdictDB.statTargetBin = "top80"
        top80 = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertFalse(lua.eval("rawequal")(top20, top80))
        self.assertEqual(800.0, self.named_targets(top80["DEATHKNIGHT"][250].default)["crit"])

    def test_weights_slash_command_sets_the_mode_and_refreshes(self) -> None:
        lua, ns = self.build_runtime()
        printed: list[str] = []
        lua.globals().print = lambda *args: printed.append(" ".join(str(a) for a in args))
        calls = {"invalidate": 0, "audit": 0, "indicators": 0}
        original_invalidate = ns.ProfileRepository.InvalidateProviderViews

        def invalidate():
            calls["invalidate"] += 1
            return original_invalidate()

        ns.ProfileRepository.InvalidateProviderViews = invalidate
        ns.RequestStatAuditRefresh = lambda: calls.__setitem__("audit", calls["audit"] + 1)
        ns.RefreshUpgradeIndicators = lambda *a: calls.__setitem__("indicators", calls["indicators"] + 1)

        ns.HandleWeightModeSlash("")
        self.assertIn("GUIDE", printed[-1])
        self.assertEqual({"invalidate": 0, "audit": 0, "indicators": 0}, calls)

        ns.HandleWeightModeSlash("  Measured ")
        self.assertEqual("MEASURED", lua.globals().StatVerdictDB.weightMode)
        self.assertEqual({"invalidate": 1, "audit": 1, "indicators": 1}, calls)
        self.assertIn("MEASURED", printed[-1])

        ns.HandleWeightModeSlash("blend")
        self.assertEqual("BLEND", ns.ProfileRepository.GetWeightMode())
        ns.HandleWeightModeSlash("nonsense")
        self.assertEqual("BLEND", lua.globals().StatVerdictDB.weightMode)
        self.assertEqual(2, calls["invalidate"])
        self.assertIn("guide", printed[-1])  # usage line
        ns.HandleWeightModeSlash("guide")
        self.assertEqual("GUIDE", lua.globals().StatVerdictDB.weightMode)

    def test_weights_slash_command_is_registered(self) -> None:
        lua = new_runtime()
        lua.execute(FRAME_STUB)
        lua.globals().SlashCmdList = lua.table()
        lua.globals().StatVerdictDB = lua.table()
        ns = lua.table()
        ns.HandleWeightModeSlash = lambda msg: None
        load_addon_file(lua, ns, "StatVerdict.lua")
        self.assertEqual("/svweights", lua.globals().SLASH_STATVERDICTWEIGHTS1)
        self.assertIsNotNone(lua.globals().SlashCmdList["STATVERDICTWEIGHTS"])


SECONDARY = {
    "crit": "ITEM_MOD_CRIT_RATING_SHORT",
    "haste": "ITEM_MOD_HASTE_RATING_SHORT",
    "mastery": "ITEM_MOD_MASTERY_RATING_SHORT",
    "vers": "ITEM_MOD_VERSATILITY",
}
STRENGTH = "ITEM_MOD_STRENGTH_SHORT"


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ScoringWeightTests(unittest.TestCase):
    """ns.GetDefaultStatWeight with measured weights vs. the rank-position weights."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_Modifiers.lua")

    def profile(self, weights: dict | None = None, equal_groups: list | None = None):
        order = self.lua.table(SECONDARY["crit"], SECONDARY["haste"], SECONDARY["mastery"], SECONDARY["vers"])
        groups = self.lua.table(*[self.lua.table(*group) for group in (equal_groups or [])])
        profile = self.lua.table(id="TEST", primaryStat=STRENGTH, secondaryOrder=order, equalGroups=groups,
                                 extraWeights=self.lua.table(), role="DAMAGER")
        if weights is not None:
            profile.secondaryWeights = self.lua.table_from({SECONDARY[k]: v for k, v in weights.items()})
        return profile

    def weights(self, profile) -> dict:
        keys = [STRENGTH, *SECONDARY.values(), "STATVERDICT_ITEM_LEVEL"]
        return {key: self.ns.GetDefaultStatWeight(profile, key) for key in keys}

    def test_without_measured_weights_the_rank_weights_are_unchanged(self) -> None:
        # Raw 4/4/3/2/1 + item level 1.2 = 15.2, scaled into the 10 point budget.
        self.assertEqual({
            STRENGTH: 2.6315789473684212,
            SECONDARY["crit"]: 2.6315789473684212,
            SECONDARY["haste"]: 1.973684210526316,
            SECONDARY["mastery"]: 1.3157894736842106,
            SECONDARY["vers"]: 0.6578947368421053,
            "STATVERDICT_ITEM_LEVEL": 0.7894736842105263,
        }, self.weights(self.profile()))
        grouped = self.weights(self.profile(equal_groups=[[2, 3]]))
        self.assertEqual(1.851851851851852, grouped[SECONDARY["haste"]])
        self.assertEqual(1.851851851851852, grouped[SECONDARY["mastery"]])

    def test_measured_weights_split_the_same_secondary_share(self) -> None:
        # The secondaries keep their rank-weight total (4+3+2+1 = 10), split by the
        # measured weights: 10 * w / (1.0+0.5+0.4+0.25). Primary 4 and item level 1.2
        # keep the same share of the 10 point budget as without weights (15.2 raw).
        result = self.weights(self.profile({"crit": 1.0, "haste": 0.5, "mastery": 0.4, "vers": 0.25}))
        scale = 10 / 15.2
        share = 10 / 2.15
        self.assertAlmostEqual(1.0 * share * scale, result[SECONDARY["crit"]])
        self.assertAlmostEqual(0.5 * share * scale, result[SECONDARY["haste"]])
        self.assertAlmostEqual(0.4 * share * scale, result[SECONDARY["mastery"]])
        self.assertAlmostEqual(0.25 * share * scale, result[SECONDARY["vers"]])
        self.assertAlmostEqual(4 * scale, result[STRENGTH])
        self.assertAlmostEqual(1.2 * scale, result["STATVERDICT_ITEM_LEVEL"])
        self.assertAlmostEqual(10 * scale, sum(result[key] for key in SECONDARY.values()))

    def test_a_stat_without_a_usable_weight_uses_its_rank_weight(self) -> None:
        result = self.weights(self.profile({"crit": 1.0, "haste": 0.5, "mastery": 0, "vers": None}))
        # crit/haste share ranks 1-2 (4+3 = 7) by weight: 4.667 / 2.333; mastery rank 3 -> 2.00,
        # vers rank 4 -> 1.00. Total stays 4 + 10 + 1.2 = 15.2.
        scale = 10 / 15.2
        self.assertAlmostEqual(7 * 1.0 / 1.5 * scale, result[SECONDARY["crit"]])
        self.assertAlmostEqual(7 * 0.5 / 1.5 * scale, result[SECONDARY["haste"]])
        self.assertAlmostEqual(2 * scale, result[SECONDARY["mastery"]])
        self.assertAlmostEqual(1 * scale, result[SECONDARY["vers"]])

    def delta_multiplier(self, profile, stat_key: str, delta: float) -> float:
        self.ns.GetDynamicStatWeight = lambda profile, key, weight: weight
        return self.ns.GetDeltaAdjustedStatWeight(profile, stat_key, delta, 1.0)

    def test_measured_weights_turn_off_the_rank_gain_and_loss_multipliers(self) -> None:
        weighted = self.profile({"crit": 1.0, "haste": 0.5, "mastery": 0.4, "vers": 0.25})
        for key in SECONDARY.values():
            self.assertEqual(1.0, self.delta_multiplier(weighted, key, 10), key)
            self.assertEqual(1.0, self.delta_multiplier(weighted, key, -10), key)
        self.assertEqual(1.05, self.delta_multiplier(weighted, STRENGTH, -10))  # primary unchanged

    def test_without_measured_weights_the_rank_multipliers_stay(self) -> None:
        plain = self.profile()
        self.assertEqual([1.0, 0.9, 0.8, 0.7],
                         [self.delta_multiplier(plain, SECONDARY[k], 10) for k in ("crit", "haste", "mastery", "vers")])
        self.assertEqual([1.5, 1.3, 1.15, 1.0],
                         [self.delta_multiplier(plain, SECONDARY[k], -10) for k in ("crit", "haste", "mastery", "vers")])


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class TooltipProvenanceTests(unittest.TestCase):
    TOOLTIP = """
    local lines = {}
    return {
        lines = lines,
        GetItem = function() return nil, "item:1000" end,
        AddLine = function(self, text) lines[#lines + 1] = text end,
        Show = function() end,
    }
    """

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_Tooltip.lua")
        self.asked = []

        def provenance(goal=None):
            self.asked.append(goal)
            # Like the repository: no goal (or stale data) means unavailable.
            return self.lua.table(available=goal == "RAID")

        self.ns.ProfileRepository = self.lua.table(GetDataProvenance=provenance)
        self.ns.GetStatAuditGoalMode = lambda: "PVP"

    def lines(self, context):
        self.ns.GetTooltipEvaluationContexts = lambda: context
        tooltip = self.lua.execute(self.TOOLTIP)
        self.ns.ProcessTooltip(tooltip)
        return [tooltip.lines[i] for i in range(1, len(tooltip.lines) + 1)]

    def test_unavailable_data_is_checked_for_the_contexts_goal(self) -> None:
        lines = self.lines(self.lua.table(goal="PVP"))
        self.assertEqual(["PVP"], self.asked)
        self.assertTrue(any("profile data unavailable" in line for line in lines))

    def test_available_goal_shows_no_unavailable_notice(self) -> None:
        self.assertEqual([], self.lines(self.lua.table(goal="RAID")))
        self.assertEqual(["RAID"], self.asked)

    def test_context_without_a_goal_uses_the_selected_goal(self) -> None:
        lines = self.lines(self.lua.table())
        self.assertEqual(["PVP"], self.asked)
        self.assertTrue(any("profile data unavailable" in line for line in lines))


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class PanelModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_WeightModes.lua")
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")

    def use_goal(self, goal: str) -> None:
        selection = self.lua.table(goalMode=goal)
        self.ns.GetSavedStatAuditSelection = lambda: selection
        self.ns.GetStatAuditGoalMode = lambda: goal

    def test_weights_drawer_opens_for_every_goal(self) -> None:
        for goal in ("MYTHIC_PLUS", "RAID", "PVP"):
            self.use_goal(goal)
            self.ns.SetRightPanelMode("manual")
            self.ns.SetRightPanelMode("weights")
            self.assertEqual("weights", self.ns.GetRightPanelMode(), goal)
            self.assertTrue(self.lua.globals().StatVerdictDB.showWeightsPanel, goal)
            self.ns.ToggleRightPanelMode("weights")
            self.assertIsNone(self.ns.GetRightPanelMode(), goal)

    def test_old_benchmark_mode_and_summary_are_not_valid(self) -> None:
        self.ns.SetRightPanelMode("benchmark")
        self.assertIsNone(self.ns.GetRightPanelMode())
        self.ns.SetRightPanelMode("summary")
        self.assertIsNone(self.ns.GetRightPanelMode())
        self.lua.globals().StatVerdictDB.showBenchmarkPanel = True  # old saved flag is ignored
        self.assertIsNone(self.ns.GetRightPanelMode())

    def test_window_opens_with_every_panel_closed(self) -> None:
        self.assertIsNone(self.ns.GetRightPanelMode())

    def test_toc_lists_weights_drawer_and_not_benchmark_or_summary(self) -> None:
        names = [path.name for path in toc_lua_files()]
        self.assertIn("SV_WeightModes.lua", names)
        self.assertIn("SV_WeightsDrawerPanel.lua", names)
        self.assertLess(names.index("SV_WeightModes.lua"), names.index("SV_WeightsDrawerPanel.lua"))
        for gone in ("SV_Benchmark.lua", "SV_BenchmarkDrawerPanel.lua", "SV_CharacterSummaryDrawerPanel.lua"):
            self.assertNotIn(gone, names)

    def test_weights_button_is_never_locked(self) -> None:
        source = (ADDON / "UI" / "SV_SettingsPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn('label = "Weights"', source)
        self.assertIn('mode = "weights"', source)
        self.assertNotIn("IsBenchmarkRelevant", source)
        self.assertNotIn('label = "Benchmark"', source)
        for path in toc_lua_files():
            self.assertNotIn("IsBenchmarkRelevant", path.read_text(encoding="utf-8-sig"), path.name)

    def test_manual_describes_the_weights_button(self) -> None:
        source = (ADDON / "UI" / "SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("Weights — choose how stat priorities are decided: Guide, Measured or Blend.", source)
        self.assertNotIn("Benchmark", source)


FRAME_STUB = """
-- Minimal stand-in for the WoW frame API: every method is a no-op that returns the
-- object itself, SetText records the text, and numeric getters return numbers.
local numeric = { GetFrameLevel = 1, GetWidth = 280, GetHeight = 500, GetStringWidth = 40, GetStringHeight = 12 }
local function Stub()
    local object = {}
    return setmetatable(object, { __index = function(t, key)
        if key == "SetText" then return function(self, value) rawset(self, "text", value) end end
        if key == "SetShown" then return function(self, value) rawset(self, "shown", value) end end
        if key == "CreateFontString" or key == "CreateTexture" then return function() return Stub() end end
        if key == "SetPoint" then
            return function(self, ...)
                local points = rawget(self, "points") or {}
                points[#points + 1] = { ... }
                rawset(self, "points", points)
            end
        end
        if key == "SetSpacing" then return function(self, value) rawset(self, "spacing", value) end end
        if key == "SetChecked" then return function(self, value) rawset(self, "checked", value) end end
        if key == "SetScript" then
            return function(self, name, fn)
                local scripts = rawget(self, "scripts") or {}
                scripts[name] = fn
                rawset(self, "scripts", scripts)
            end
        end
        if key == "Text" then  -- UICheckButtonTemplate provides a label FontString
            local label = Stub()
            rawset(t, "Text", label)
            return label
        end
        if numeric[key] then return function() return numeric[key] end end
        if key == "GetFont" then return function() return "font", 12, "" end end
        -- WoW methods are PascalCase; lowercase keys are plain fields and are nil until set.
        if type(key) == "string" and key:match("^%u") then return function(self) return self end end
        return nil
    end })
end
CreateFrame = function() return Stub() end
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WeightsDrawerSmokeTests(unittest.TestCase):
    NO_DATA = "No measured data for this build: the guide is used."
    NO_GUIDE_TARGETS = "No ClassCodex targets for this build: our own are used."

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        for relative in ("Core/SV_WeightModes.lua", "Core/SV_ProfileRepository.lua",
                         "UI/SV_RightPanelMode.lua", "UI/SV_WeightsDrawerPanel.lua"):
            load_addon_file(self.lua, self.ns, relative)
        self.frame = self.lua.eval("CreateFrame")()
        self.refreshes = 0

        def refresh():
            self.refreshes += 1

        self.ns.RequestStatAuditRefresh = refresh
        self.ns.GetStatAuditGoalMode = lambda: "RAID"
        self.measured = True
        self.guide_targets = True
        self.has_profile = True
        self.ns.SetRightPanelMode("weights")

    def card(self):
        weights = self.lua.table(haste=1.0, mastery=0.8) if self.measured else None
        profile = self.lua.table(specKey="SPEC", secondaryWeights=weights,
                                 guideTargetsMissing=not self.guide_targets)
        context = self.lua.table(profile=profile) if self.has_profile else self.lua.table()
        self.ns.GetActivePanelContext = lambda: context
        self.ns.StatVerdictWeightsDrawerPanel.Apply(self.frame)
        return self.frame.weightsDrawerCard

    def test_title_intro_and_three_mode_rows(self) -> None:
        card = self.card()
        self.assertEqual("Weights", card.title.text)
        self.assertEqual("Choose how stat priorities and targets are decided.", card.intro.text)
        self.assertEqual(["GUIDE", "MEASURED", "BLEND"], [card.modeRows[i].key for i in (1, 2, 3)])
        self.assertEqual(["Guide", "Measured", "Blend"], [card.modeRows[i].label.text for i in (1, 2, 3)])
        self.assertEqual("Recommended", card.modeRows[1].hint.text)
        for i in (1, 2, 3):
            self.assertTrue(card.modeRows[i].meaning.text)

    def test_guide_is_selected_by_default(self) -> None:
        card = self.card()
        self.assertEqual([True, False, False], [card.modeRows[i].check.checked for i in (1, 2, 3)])
        self.assertEqual("Guide weights", card.aboutTitle.text)
        self.assertIn("Icy Veins", card.about.text)

    def test_clicking_a_row_sets_the_weight_mode_and_marks_it(self) -> None:
        card = self.card()
        card.modeRows[2].scripts.OnClick()
        self.assertEqual("MEASURED", self.lua.globals().StatVerdictDB.weightMode)
        self.assertEqual("MEASURED", self.ns.ProfileRepository.GetWeightMode())
        self.assertEqual([False, True, False], [card.modeRows[i].check.checked for i in (1, 2, 3)])
        self.assertEqual("Measured weights", card.aboutTitle.text)
        self.assertIn("simulations", card.about.text)
        self.assertGreaterEqual(self.refreshes, 1)
        card.modeRows[3].scripts.OnClick()
        self.assertEqual("BLEND", self.lua.globals().StatVerdictDB.weightMode)
        self.assertEqual([False, False, True], [card.modeRows[i].check.checked for i in (1, 2, 3)])
        self.assertEqual("Blend weights", card.aboutTitle.text)

    def test_saved_mode_is_shown_as_selected(self) -> None:
        self.lua.globals().StatVerdictDB.weightMode = "BLEND"
        card = self.card()
        self.assertEqual([False, False, True], [card.modeRows[i].check.checked for i in (1, 2, 3)])

    def test_description_hangs_from_its_title_so_it_cannot_leave_the_card(self) -> None:
        card = self.card()
        self.assertEqual("TOPLEFT", card.about.points[1][1])
        self.assertTrue(self.lua.eval("rawequal")(card.aboutTitle, card.about.points[1][2]))
        for mode in self.ns.GetWeightModes().values():
            self.assertLessEqual(len(mode.about), 300, mode.key)  # about seven lines in the drawer

    def test_description_lines_have_extra_spacing(self) -> None:
        self.assertGreaterEqual(self.card().about.spacing, 3)

    def test_no_current_data_block_any_more(self) -> None:
        card = self.card()
        self.assertIsNone(card.dataRows)
        self.assertIsNone(card.infoTitle)

    def test_status_is_empty_in_guide_mode_even_without_measured_data(self) -> None:
        self.measured = False
        self.assertEqual("", self.card().status.text)

    def test_status_is_empty_when_measured_data_exists(self) -> None:
        for mode in ("MEASURED", "BLEND"):
            self.lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual("", self.card().status.text, mode)

    def test_status_says_the_guide_is_used_without_measured_data(self) -> None:
        self.measured = False
        for mode in ("MEASURED", "BLEND"):
            self.lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual(self.NO_DATA, self.card().status.text, mode)

    def test_status_is_empty_without_an_active_build(self) -> None:
        self.has_profile = False
        for mode in ("GUIDE", "MEASURED"):
            self.lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual("", self.card().status.text, mode)

    def test_status_says_our_targets_are_used_without_classcodex_targets(self) -> None:
        self.guide_targets = False
        self.assertEqual(self.NO_GUIDE_TARGETS, self.card().status.text)
        # Only in Guide mode: Measured shows our own targets anyway, Blend keeps its own message.
        for mode in ("MEASURED", "BLEND"):
            self.lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual("", self.card().status.text, mode)
        self.measured = False
        self.assertEqual(self.NO_DATA, self.card().status.text)

    def test_mode_rows_describe_targets_too(self) -> None:
        card = self.card()
        self.assertIn("ClassCodex", card.about.text)
        self.assertIn("stat targets", card.about.text)
        for i in (1, 2, 3):
            self.assertLessEqual(len(card.modeRows[i].meaning.text), 31, i)  # one line in the row

    def test_no_raider_io_wording_left(self) -> None:
        source = (ADDON / "UI" / "SV_WeightsDrawerPanel.lua").read_text(encoding="utf-8-sig")
        for word in ("MythicPlusBenchmarks", "confidence", "sample", "Mythic+", "top 25"):
            self.assertNotIn(word, source)

    def bin_checks(self, card):
        return [card.binRows[i].check.checked for i in (1, 2, 3)]

    def test_stat_target_group_below_the_mode_rows(self) -> None:
        card = self.card()
        self.assertEqual("Stat targets", card.binTitle.text)
        self.assertEqual("Applies to Guide and Blend.", card.binNote.text)
        self.assertEqual(["top20", "top50", "top80"], [card.binRows[i].key for i in (1, 2, 3)])
        self.assertEqual(["Top 20%", "Top 50%", "Top 80%"], [card.binRows[i].label.text for i in (1, 2, 3)])
        self.assertEqual([True, False, False], self.bin_checks(card))
        # The status line (and the description under it) hangs below the group.
        self.assertTrue(self.lua.eval("rawequal")(card.binGroup, card.status.points[1][2]))

    def test_stat_target_group_shows_the_saved_bin(self) -> None:
        self.lua.globals().StatVerdictDB.statTargetBin = "top80"
        self.assertEqual([False, False, True], self.bin_checks(self.card()))

    def test_invalid_saved_bin_shows_top_20(self) -> None:
        self.lua.globals().StatVerdictDB.statTargetBin = "top99"
        self.assertEqual([True, False, False], self.bin_checks(self.card()))

    def test_clicking_a_stat_target_level_sets_it_and_refreshes(self) -> None:
        card = self.card()
        card.binRows[2].scripts.OnClick()
        self.assertEqual("top50", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual("top50", self.ns.ProfileRepository.GetStatTargetBin())
        self.assertEqual([False, True, False], self.bin_checks(card))
        self.assertGreaterEqual(self.refreshes, 1)
        card.binRows[1].scripts.OnClick()
        self.assertEqual("top20", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual([True, False, False], self.bin_checks(card))
        # The weight mode is left alone.
        self.assertEqual("GUIDE", self.ns.GetWeightMode())

    def test_card_padding_copies_the_features_drawer(self) -> None:
        # The layout key stays "benchmark.card" so saved drawer positions carry over.
        pads = {"options.card.pad": self.lua.table(top=5, bottom=5, left=0, right=0)}
        zero = self.lua.table(top=0, bottom=0, left=0, right=0)
        self.ns.GetDevLayoutPadding = lambda key: pads.get(key, zero)
        pad = self.ns.StatVerdictWeightsDrawerPanel.GetCardPad()
        self.assertEqual((5, 5, 0, 0), (pad.top, pad.bottom, pad.left, pad.right))
        pads["benchmark.card.pad"] = self.lua.table(top=2, bottom=3, left=0, right=0)
        pad = self.ns.StatVerdictWeightsDrawerPanel.GetCardPad()
        self.assertEqual((2, 3), (pad.top, pad.bottom))


BIS_PANEL_STUB = """
-- Item and spell data the game would have (or not yet) cached.
ITEM_NAMES = {}
SPELL_NAMES = {}
REQUESTED = {}
C_Item = {
    GetItemInfo = function(item)
        local id = tonumber(item) or tonumber(tostring(item):match("item:(%d+)"))
        return ITEM_NAMES[id], nil, 4
    end,
    RequestLoadItemDataByID = function(id) REQUESTED[id] = true end,
}
C_Spell = { GetSpellName = function(id) return SPELL_NAMES[id] end }
CREATED = {}
local plainCreate = CreateFrame
-- Font strings measure their text (6 px a character) so the auto width can be checked.
local function MeasuredFontString()
    local text = plainCreate()
    rawset(text, "GetStringWidth", function(self) return #(rawget(self, "text") or "") * 6 end)
    return text
end
CreateFrame = function(...)
    local frame = plainCreate(...)
    rawset(frame, "CreateFontString", function() return MeasuredFontString() end)
    CREATED[#CREATED + 1] = frame
    return frame
end
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class BisPanelRecommendationTests(unittest.TestCase):
    """Each Best in Slot row shows the item with its recommended gems and enchant."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.lua.execute(BIS_PANEL_STUB)
        self.ns = self.lua.table()
        self.mode = "bis"
        self.ns.GetRightPanelMode = lambda: self.mode
        load_addon_file(self.lua, self.ns, "UI/SV_BisProgressPanel.lua")
        # The first frame the file creates listens for item data arriving.
        self.item_events = self.lua.globals().CREATED[1]
        self.frame = self.lua.eval("CreateFrame")()
        g = self.lua.globals()
        g.ITEM_NAMES[1001] = "Crown of Tests"
        g.ITEM_NAMES[1002] = "Amulet of Tests"
        g.ITEM_NAMES[1003] = "Blade of Tests"

    def slots(self, *entries):
        table = self.lua.table()
        for index, entry in enumerate(entries, start=1):
            table[index] = entry
        return table

    def item(self, item_id, gems=None, enchant=None):
        item = self.lua.table(item_id=item_id)
        if gems is not None:
            item.gem_ids = self.lua.table(*gems)
        if enchant is not None:
            item.enchant = self.lua.table(**enchant)
        return item

    def refresh(self, *entries):
        bis = self.lua.table(slots=self.slots(*entries))
        profile = self.lua.table(generatedContext=self.lua.table(bis=bis))
        self.ns.StatVerdictBisProgressPanel.Refresh(self.frame, profile)
        return self.frame.bisProgressCard

    def test_row_shows_gems_and_enchant_next_to_the_item(self) -> None:
        g = self.lua.globals()
        g.ITEM_NAMES[213746] = "Masterful Gem"
        g.ITEM_NAMES[213743] = "Quick Gem"
        g.ITEM_NAMES[243981] = "Enchant Helm - Scroll"
        card = self.refresh(self.lua.table(slot="Head", item=self.item(
            1001, gems=[213746, 213743], enchant={"id": 8017, "item_id": 243981, "spell_id": 1236001})))
        row = card.rows[1]
        self.assertIn("Crown of Tests", row.name.text)
        self.assertEqual("Gems: Masterful Gem, Quick Gem  ·  Enchant: Enchant Helm - Scroll", row.details.text)

    def test_enchant_name_falls_back_to_spell_then_id(self) -> None:
        self.lua.globals().SPELL_NAMES[1236001] = "Radiant Mastery"
        card = self.refresh(
            self.lua.table(slot="Ring", item=self.item(1001, enchant={"id": 8017, "spell_id": 1236001})),
            self.lua.table(slot="Main Hand", item=self.item(1003, enchant={"id": 3368})),
        )
        self.assertEqual("Enchant: Radiant Mastery", card.rows[1].details.text)
        self.assertEqual("Enchant: Enchant #3368", card.rows[2].details.text)

    def test_line_is_empty_without_gems_or_enchant(self) -> None:
        card = self.refresh(
            self.lua.table(slot="Neck", item=self.item(1002)),
            self.lua.table(slot="Neck", item=self.item(1002, gems=[], enchant={})),
        )
        for index in (1, 2):
            self.assertEqual("", card.rows[index].details.text, index)

    def test_old_data_with_a_flat_entry_has_no_errors(self) -> None:
        card = self.refresh(self.lua.table(slot="Neck", item_id=1002))
        self.assertIn("Amulet of Tests", card.rows[1].name.text)
        self.assertEqual("", card.rows[1].details.text)

    def test_gem_names_fill_in_when_the_item_data_arrives(self) -> None:
        g = self.lua.globals()
        card = self.refresh(self.lua.table(slot="Head", item=self.item(1001, gems=[213746])))
        self.assertEqual("Gems: Gem #213746", card.rows[1].details.text)
        self.assertTrue(g.REQUESTED[213746])
        g.ITEM_NAMES[213746] = "Masterful Gem"
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 213746, True)
        self.assertEqual("Gems: Masterful Gem", card.rows[1].details.text)

    def test_enchant_scroll_name_fills_in_when_the_item_data_arrives(self) -> None:
        g = self.lua.globals()
        card = self.refresh(self.lua.table(slot="Head", item=self.item(
            1001, enchant={"id": 8017, "item_id": 243981})))
        self.assertEqual("Enchant: Enchant #8017", card.rows[1].details.text)
        g.ITEM_NAMES[243981] = "Enchant Helm - Scroll"
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 243981, True)
        self.assertEqual("Enchant: Enchant Helm - Scroll", card.rows[1].details.text)

    def test_ranked_trinkets_rows_have_no_recommendation_line(self) -> None:
        self.refresh(self.lua.table(slot="Head", item=self.item(1001, gems=[213746])))
        self.mode = "trinkets"
        trinkets = self.slots(self.lua.table(item_id=1003, tier="S"))
        profile = self.lua.table(generatedContext=self.lua.table(trinkets=trinkets))
        self.ns.StatVerdictBisProgressPanel.Refresh(self.frame, profile)
        self.assertEqual("", self.frame.bisProgressCard.rows[1].details.text)

    def test_panel_width_makes_room_for_the_line(self) -> None:
        plain = self.refresh(self.lua.table(slot="Head", item=self.item(1001))).preferredWidth
        with_line = self.refresh(self.lua.table(slot="Head", item=self.item(
            1001, enchant={"id": 3368}))).preferredWidth
        self.assertGreater(with_line, plain)


if __name__ == "__main__":
    unittest.main()
