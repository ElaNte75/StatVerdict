from __future__ import annotations

import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.classcodex_targets_cli import render_lua as render_targets_lua
from tools.classcodex_weights_cli import render_lua as render_weights_lua
from tools.tests.addon_fixtures import (
    add_gear_levels, add_guide_targets, add_track_data, make_classcodex_targets, make_classcodex_weights,
    make_guide_targets,
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

    def test_two_modes_with_guide_recommended(self) -> None:
        modes = self.ns.GetWeightModes()
        self.assertEqual(2, len(modes))
        self.assertEqual(["GUIDE", "MEASURED"], [modes[i].key for i in (1, 2)])
        self.assertEqual(["Guide", "Measured"], [modes[i].label for i in (1, 2)])
        self.assertEqual("Recommended", modes[1].hint)
        self.assertEqual(["From guides", "Our own measurement"], [modes[i].meaning for i in (1, 2)])
        self.assertEqual("Stat priority and stat targets taken straight from the guides. Recommended.",
                         modes[1].about)
        self.assertEqual("Our own simulation: stat targets from best-in-slot gear with recommended gems "
                         "and enchants, and stat values measured by our simulations.", modes[2].about)
        self.assertEqual("Measured", self.ns.GetWeightModeInfo("MEASURED").label)
        self.assertEqual("Guide", self.ns.GetWeightModeInfo("junk").label)
        self.assertEqual("Guide", self.ns.GetWeightModeInfo("BLEND").label)

    def test_blend_mode_is_gone(self) -> None:
        self.assertFalse(self.ns.SetWeightMode("BLEND"))
        self.lua.globals().StatVerdictDB.weightMode = "BLEND"
        self.assertEqual("GUIDE", self.ns.GetWeightMode())
        self.assertEqual({"audit": 0, "indicators": 0}, self.calls)

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

    def test_three_difficulties_from_easy_to_hard(self) -> None:
        bins = self.ns.GetStatTargetBins()
        # Saved keys stay top20/50/80, shown Tier 3 to Tier 1; Tier 1 (top20) is the default.
        self.assertEqual(3, len(bins))
        self.assertEqual(["top80", "top50", "top20"], [bins[i].key for i in (1, 2, 3)])
        self.assertEqual(["Tier 3", "Tier 2", "Tier 1"], [bins[i].label for i in (1, 2, 3)])
        self.assertEqual(["Tier 3: stat targets that most players reach. A comfortable goal.",
                          "Tier 2: the stats of a typical player. A solid, realistic goal.",
                          "Tier 1: the stats the best-equipped players reach. The most demanding goal."],
                         [bins[i].about for i in (1, 2, 3)])
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

    GEAR_ABOUT = [
        "Best in Slot, trinkets and targets at Champion-track gear. A comfortable goal.",
        "Best in Slot, trinkets and targets at Hero-track gear. A solid, realistic goal.",
        "Best in Slot, trinkets and targets at Myth-track gear. The most demanding goal.",
    ]

    def test_three_gear_levels_from_champion_to_myth(self) -> None:
        levels = self.ns.GetGearLevels()
        self.assertEqual(3, len(levels))
        self.assertEqual(["champion", "hero", "myth"], [levels[i].key for i in (1, 2, 3)])
        self.assertEqual(["Champion", "Hero", "Myth"], [levels[i].label for i in (1, 2, 3)])
        self.assertEqual(self.GEAR_ABOUT, [levels[i].about for i in (1, 2, 3)])
        self.assertEqual("myth", self.ns.GetGearLevel())
        for garbage in ("MYTH", "epic", 3, self.lua.table()):
            self.lua.globals().StatVerdictDB.gearLevel = garbage
            self.assertEqual("myth", self.ns.GetGearLevel(), garbage)

    def test_set_gear_level_saves_it_and_refreshes(self) -> None:
        self.assertTrue(self.ns.SetGearLevel("hero"))
        self.assertEqual("hero", self.lua.globals().StatVerdictDB.gearLevel)
        self.assertEqual("hero", self.ns.GetGearLevel())
        self.assertEqual({"audit": 1, "indicators": 1}, self.calls)
        self.assertFalse(self.ns.SetGearLevel("top20"))
        self.assertEqual("hero", self.ns.GetGearLevel())
        self.assertEqual({"audit": 1, "indicators": 1}, self.calls)
        # The guide's stat target bin is a separate choice, left alone.
        self.assertIsNone(self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual("top20", self.ns.GetStatTargetBin())

    def test_set_gear_level_drops_the_cached_provider_views(self) -> None:
        repo = self.ns.ProfileRepository
        dropped = []
        original = repo.InvalidateProviderViews
        repo.InvalidateProviderViews = lambda: (dropped.append(True), original())
        self.assertTrue(repo.SetGearLevel("champion"))
        self.assertEqual([True], dropped)
        self.assertFalse(repo.SetGearLevel("junk"))
        self.assertEqual([True], dropped)

    def test_the_cards_mean_tiers_in_guide_and_gear_levels_in_measured(self) -> None:
        self.lua.globals().StatVerdictDB.statTargetBin = "top50"
        self.lua.globals().StatVerdictDB.gearLevel = "champion"
        guide = self.ns.GetTargetChoice("GUIDE")
        self.assertEqual("Stat targets", guide.title)
        self.assertEqual(["top80", "top50", "top20"], [guide.options[i].key for i in (1, 2, 3)])
        self.assertEqual("top50", guide.selected)
        measured = self.ns.GetTargetChoice("MEASURED")
        self.assertEqual("Gear level", measured.title)
        self.assertEqual(["champion", "hero", "myth"], [measured.options[i].key for i in (1, 2, 3)])
        self.assertEqual("champion", measured.selected)
        # Each mode saves its own choice.
        self.assertTrue(measured.set("myth"))
        self.assertEqual("myth", self.lua.globals().StatVerdictDB.gearLevel)
        self.assertEqual("top50", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertTrue(guide.set("top80"))
        self.assertEqual("top80", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual("myth", self.lua.globals().StatVerdictDB.gearLevel)
        self.assertEqual("Stat targets", self.ns.GetTargetChoice("junk").title)

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
                      weight_mode: str | None = None, lua_setup: str | None = None):
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
        if lua_setup:
            lua.execute(lua_setup)
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
            self.assertEqual("StatVerdict data", info.sourceName)
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

    # The game's item data: BiS Head 1000, Shoulders 1002 and Chest 1004 are set
    # pieces; Legs 1008 is not; Hands 1006 is not loaded yet. Candidates 7000+ are
    # items the player found (7003 has no upgrade track).
    CATALYST_GAME = """
    SET_IDS = { [1000] = 1920, [1002] = 1920, [1004] = 1920 }
    LOADED = { [1000] = true, [1002] = true, [1004] = true, [1008] = true }
    EQUIP = { [7000] = "INVTYPE_HEAD", [7001] = "INVTYPE_NECK", [7002] = "INVTYPE_ROBE", [7003] = "INVTYPE_HEAD",
              [7004] = "INVTYPE_LEGS", [7005] = "INVTYPE_HAND", [7006] = "INVTYPE_SHOULDER" }
    TRACKED = { [7000] = true, [7001] = true, [7002] = true, [7004] = true, [7005] = true, [7006] = true }
    REQUESTED = {}
    EVENT_HANDLERS = {}
    local function IdOf(item) return tonumber(tostring(item):match("item:(%d+)") or item) end
    C_Item = {
        GetItemInfo = function(item)
            local id = IdOf(item)
            if not LOADED[id] then return nil end
            return "Item " .. id, "item:" .. id, 4, 600, 80, "Armor", "Plate", 1, EQUIP[id] or "", 0, 0, 4, 4, 1, 11,
                SET_IDS[id], false
        end,
        RequestLoadItemDataByID = function(id) REQUESTED[id] = true end,
        GetItemUpgradeInfo = function(link)
            if TRACKED[IdOf(link)] then return { trackString = "Hero", currentLevel = 1, maxLevel = 6 } end
            return nil
        end,
    }
    CreateFrame = function()
        local frame = { events = {} }
        function frame:RegisterEvent(event) self.events[event] = true end
        function frame:SetScript(_, handler) EVENT_HANDLERS[#EVENT_HANDLERS + 1] = { frame = self, handler = handler } end
        return frame
    end
    """

    def catalyst_runtime(self):
        lua, ns = self.build_runtime(lua_setup=self.CATALYST_GAME)
        ns.GetItemEquipLocation = lua.eval("function(link) return EQUIP[tonumber(tostring(link):match('item:(%d+)'))] end")
        return lua, ns, ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))

    def test_found_item_in_a_set_piece_slot_counts_as_the_set_piece(self) -> None:
        lua, ns, profile = self.catalyst_runtime()
        for link, slot, target in (("item:7000", "Head", 1000), ("item:7006", "Shoulders", 1002),
                                   ("item:7002", "Chest", 1004)):
            info = ns.GetItemReferenceInfo(link, profile)
            self.assertIsNotNone(info, link)
            self.assertIsNone(info.bis, link)
            self.assertEqual(8, info.catalystPath.bonus, link)  # same bonus a BiS item gets
            self.assertEqual(slot, info.catalystPath.slot, link)
            self.assertEqual(target, info.catalystPath.targetItemID, link)
            self.assertEqual(8, info.bonus, link)
            self.assertEqual(8, ns.GetItemReferenceBonus(link, profile)[0])

    def test_no_catalyst_rule_when_the_bis_piece_is_not_a_set_piece(self) -> None:
        lua, ns, profile = self.catalyst_runtime()
        self.assertIsNone(ns.GetItemReferenceInfo("item:7004", profile))  # Legs BiS 1008 has no set

    def test_the_set_piece_itself_is_plain_bis(self) -> None:
        lua, ns, profile = self.catalyst_runtime()
        lua.execute('EQUIP[1000] = "INVTYPE_HEAD"; TRACKED[1000] = true')
        info = ns.GetItemReferenceInfo("item:1000", profile)
        self.assertIsNotNone(info.bis)
        self.assertIsNone(info.catalystPath)
        self.assertEqual(8, info.bonus)

    def test_no_catalyst_rule_for_other_slots_or_items_without_an_upgrade_track(self) -> None:
        lua, ns, profile = self.catalyst_runtime()
        self.assertIsNone(ns.GetItemReferenceInfo("item:7001", profile))  # neck
        self.assertIsNone(ns.GetItemReferenceInfo("item:7003", profile))  # head, no upgrade track

    def test_unloaded_set_data_gives_no_rule_until_it_loads(self) -> None:
        lua, ns, profile = self.catalyst_runtime()
        calls = []
        ns.ClearUpgradeIndicatorDecisionCache = lambda: calls.append("clear")
        ns.RefreshUpgradeIndicators = lambda kind=None: calls.append(("refresh", kind))
        self.assertIsNone(ns.GetItemReferenceInfo("item:7005", profile))  # Hands BiS 1006 not loaded
        self.assertTrue(lua.globals().REQUESTED[1006])
        handlers = lua.globals().EVENT_HANDLERS
        self.assertEqual(1, len(handlers))
        self.assertTrue(handlers[1].frame.events["GET_ITEM_INFO_RECEIVED"])
        handlers[1].handler(handlers[1].frame, "GET_ITEM_INFO_RECEIVED", 4242, True)  # unrelated item
        self.assertEqual([], calls)
        lua.execute("LOADED[1006] = true; SET_IDS[1006] = 1920")
        handlers[1].handler(handlers[1].frame, "GET_ITEM_INFO_RECEIVED", 1006, True)
        self.assertEqual(["clear", ("refresh", "full")], calls)
        info = ns.GetItemReferenceInfo("item:7005", profile)
        self.assertEqual(1006, info.catalystPath.targetItemID)
        self.assertEqual(8, info.bonus)

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

    # --- Stat weight mode: GUIDE (default) / MEASURED ---------------------------
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
        for mode in ("GUIDE", "MEASURED"):
            lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual(mode, ns.ProfileRepository.GetWeightMode())

    def test_garbage_saved_weight_mode_falls_back_to_default(self) -> None:
        lua, ns = self.build_runtime()
        for garbage in ("nonsense", "guide", "BLEND", 3, lua.table()):
            lua.globals().StatVerdictDB.weightMode = garbage
            self.assertEqual("GUIDE", ns.ProfileRepository.GetWeightMode(), garbage)
        lua.globals().StatVerdictDB = None
        self.assertEqual("GUIDE", ns.ProfileRepository.GetWeightMode())
        lua.globals().StatVerdictDB = lua.table(weightMode="BLEND")
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

    def test_a_secondary_without_a_target_keeps_its_row_in_both_modes(self) -> None:
        # Our measured Versatility is 0 when the best gear carries none: the stat
        # must still show as a row (target 0), never be dropped.
        for weight_mode in (None, "MEASURED"):
            build_id = now_build_id()
            targets = add_guide_targets(make_classcodex_targets(build_id), "DEATHKNIGHT_BLOOD", "MYTHIC_PLUS",
                                        "sanlayn", make_guide_targets(**self.GUIDE_BINS))
            context = targets["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"]
            del context["targets"]["statTargets"]["stats"]["versatility"]
            targets_root = context["targets"]
            if weight_mode is None:
                targets_root["guideTargets"] = {}
            lua, ns = self.build_runtime(build_id=build_id, targets=targets, weight_mode=weight_mode)
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
            by_key = self.targets(profile)
            self.assertEqual(4, len(profile.auditTargets.rows), weight_mode)
            self.assertEqual(0, by_key[SECONDARY["vers"]], weight_mode)
            self.assertEqual(self.OWN_TARGETS["crit"], by_key[SECONDARY["crit"]], weight_mode)

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

    # --- Measured: the gear level picks our own targets and the item track ------
    HERO_TARGETS = {"crit": 1000.0, "haste": 800.0, "mastery": 600.0, "vers": 380.0}
    CHAMPION_TARGETS = {"crit": 900.0, "haste": 700.0, "mastery": 520.0, "vers": 330.0}

    def level_runtime(self, weight_mode: str | None = "MEASURED", levels: dict | None = None,
                      track: bool = True, guide: bool = True):
        build_id = now_build_id()
        targets = make_classcodex_targets(build_id)
        if guide:
            add_guide_targets(targets, "DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn",
                              make_guide_targets(**self.GUIDE_BINS))
        if levels is None:
            levels = {"hero": ((1000, 800, 600, 380), 276.0), "champion": ((900, 700, 520, 330), None)}
        if levels:
            add_gear_levels(targets, "DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "sanlayn", levels)
        if track:
            add_track_data(targets)
        return self.build_runtime(build_id=build_id, targets=targets, weight_mode=weight_mode)

    def test_measured_targets_follow_the_gear_level(self) -> None:
        lua, ns = self.level_runtime()
        repo = ns.ProfileRepository
        self.assertEqual("myth", repo.GetGearLevel())
        for level, expected, item_level in (("myth", self.OWN_TARGETS, 337.9),
                                            ("hero", self.HERO_TARGETS, 276.0),
                                            ("champion", self.CHAMPION_TARGETS, 337.9)):
            lua.globals().StatVerdictDB.gearLevel = level
            profile = repo.BuildRuntimeProfile(self.context(lua))
            self.assertEqual(expected, self.named_targets(profile), level)
            self.assertEqual(level, profile.gearLevel, level)
            # The level's item level when the data has one, else Myth's.
            self.assertEqual(item_level, profile.auditTargets.averageItemLevel, level)
            self.assertFalse(profile.invalidGeneratedContext, level)

    def test_measured_ignores_the_guide_bin(self) -> None:
        lua, ns = self.level_runtime()
        lua.globals().StatVerdictDB.gearLevel = "hero"
        for bin_key in ("top20", "top50", "top80"):
            lua.globals().StatVerdictDB.statTargetBin = bin_key
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
            self.assertEqual(self.HERO_TARGETS, self.named_targets(profile), bin_key)

    def test_measured_without_level_data_uses_the_myth_targets(self) -> None:
        for levels in ({}, {"hero": ((None, None, None, None), None)}):
            lua, ns = self.level_runtime(levels=levels)
            lua.globals().StatVerdictDB.gearLevel = "hero"
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
            self.assertEqual(self.OWN_TARGETS, self.named_targets(profile), levels)
            self.assertEqual(337.9, profile.auditTargets.averageItemLevel, levels)

    def test_guide_ignores_the_gear_level(self) -> None:
        lua, ns = self.level_runtime(weight_mode="GUIDE")
        lua.globals().StatVerdictDB.statTargetBin = "top50"
        for level in ("myth", "hero", "champion"):
            lua.globals().StatVerdictDB.gearLevel = level
            profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
            self.assertEqual({"crit": 900.0, "haste": 1000.0, "mastery": 600.0, "vers": 250.0},
                             self.named_targets(profile), level)
            self.assertEqual(337.9, profile.auditTargets.averageItemLevel, level)
        # Without guide targets, Guide falls back to Myth's own targets, whatever the level.
        lua, ns = self.level_runtime(weight_mode="GUIDE", guide=False)
        lua.globals().StatVerdictDB.gearLevel = "hero"
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(self.OWN_TARGETS, self.named_targets(profile))

    def test_changing_the_gear_level_rebuilds_the_cached_provider_view(self) -> None:
        lua, ns = self.level_runtime()
        ns.GetSnapshotHeroTalentName = lambda context: "San'layn"
        repo = ns.ProfileRepository
        myth = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertEqual(1140.0, self.named_targets(myth["DEATHKNIGHT"][250].default)["crit"])
        lua.globals().StatVerdictDB.gearLevel = "hero"
        hero = repo.RefreshProviderView("MYTHIC_PLUS")
        self.assertFalse(lua.eval("rawequal")(myth, hero))
        self.assertEqual(1000.0, self.named_targets(hero["DEATHKNIGHT"][250].default)["crit"])

    def swapped(self, ns, lua, *bonus_ids):
        result = ns.ProfileRepository.ApplyTrackSwap(lua.table(*bonus_ids))
        return [result[i] for i in range(1, len(result) + 1)]

    def test_track_swap_only_in_measured_below_myth(self) -> None:
        lua, ns = self.level_runtime()
        db = lua.globals().StatVerdictDB
        # Myth: nothing swapped.
        self.assertEqual([6652, 13334, 12854], self.swapped(ns, lua, 6652, 13334, 12854))
        db.gearLevel = "hero"
        # Bonus ids in the map are replaced (the renderer wrote its keys as strings); others stay.
        self.assertEqual([7652, 14334, 12854], self.swapped(ns, lua, 6652, 13334, 12854))
        db.gearLevel = "champion"
        self.assertEqual([8652, 15334, 12854], self.swapped(ns, lua, 6652, 13334, 12854))
        # Guide is a pure copy of the guide: never swapped.
        db.weightMode = "GUIDE"
        self.assertEqual([6652, 13334, 12854], self.swapped(ns, lua, 6652, 13334, 12854))
        self.assertIsNone(ns.ProfileRepository.GetActiveTrackSwap())

    def test_track_swap_accepts_numeric_keys_too(self) -> None:
        lua, ns = self.level_runtime(track=False)
        # Data built in Lua directly: numeric keys.
        ns.ClassCodexTargets.trackSwap = lua.eval("{ hero = { [6652] = 7652 } }")
        lua.globals().StatVerdictDB.gearLevel = "hero"
        self.assertEqual([7652, 99], self.swapped(ns, lua, 6652, 99))

    def test_old_data_without_track_swap_shows_the_items_as_they_are(self) -> None:
        lua, ns = self.level_runtime(track=False)
        for level in ("hero", "champion"):
            lua.globals().StatVerdictDB.gearLevel = level
            self.assertIsNone(ns.ProfileRepository.GetActiveTrackSwap(), level)
            self.assertEqual([6652, 101], self.swapped(ns, lua, 6652, 101), level)

    def test_best_in_slot_matching_by_item_id_ignores_the_gear_level(self) -> None:
        lua, ns = self.level_runtime()
        lua.globals().StatVerdictDB.gearLevel = "champion"
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        info = ns.GetItemReferenceInfo("item:1000::::::::90::::2:6652:100", profile)
        self.assertIsNotNone(info.bis)
        self.assertEqual("Head", info.bis.slot)
        trinket = ns.GetItemReferenceInfo("item:5001::::::::90::::1:8652", profile)
        self.assertEqual("S", trinket.trinket.tier)

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

        for rejected in ("blend", "nonsense"):
            ns.HandleWeightModeSlash(rejected)
            self.assertEqual("MEASURED", lua.globals().StatVerdictDB.weightMode, rejected)
            self.assertEqual(1, calls["invalidate"], rejected)
            self.assertIn("guide", printed[-1])  # usage line
            self.assertNotIn("blend", printed[-1].lower())
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
class TargetScoringCacheTests(unittest.TestCase):
    """Secondary weights follow the stat targets: a new gear level (or guide tier)
    gives the same profile id new targets, and the cached weights must follow."""

    def test_new_targets_for_the_same_profile_rescore_the_item(self) -> None:
        lua = new_runtime()
        lua.execute('C_Item = { GetItemStats = function() return { ITEM_MOD_CRIT_RATING_SHORT = 100 } end }')
        ns = lua.table()
        ns.StatNames = lua.table()
        for relative in ("Core/SV_Modifiers.lua", "Core/SV_Scoring.lua"):
            load_addon_file(lua, ns, relative)
        ns.GetCurrentStatRating = lambda key: 800

        def profile(crit_target):
            rows = lua.table(*[lua.table(key=key, target=target) for key, target in (
                (SECONDARY["crit"], crit_target), (SECONDARY["haste"], 800), (SECONDARY["mastery"], 800),
                (SECONDARY["vers"], 800))])
            return lua.table(id="MYTHIC_PLUS_TEST", primaryStat=STRENGTH,
                             secondaryOrder=lua.table(*SECONDARY.values()),
                             auditTargets=lua.table(rows=rows))

        def score(crit_target):
            return ns.GetItemProfileScore("item:1", profile(crit_target))[0]

        myth = score(1400)
        champion = score(700)
        # Far below the Myth crit target: crit is worth more than when it is already met.
        self.assertGreater(myth, champion)
        self.assertEqual(myth, score(1400))


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
class VerdictReferenceLabelTests(unittest.TestCase):
    CATALYST_TEXT = "Good if converted to the set piece with the Catalyst"

    def render(self, reference_info):
        lua = new_runtime()
        ns = lua.table()
        lua.execute("C_Item = { GetItemInfo = function() return nil end }")
        ns.Colors = lua.table(white="|cffffffff", reset="|r", green="|cff00ff00", red="|cffff0000", yellow="|cffffff00")
        load_addon_file(lua, ns, "UI/SV_Render.lua")
        ns.GetItemReferenceInfo = lambda link, profile: reference_info(lua) if reference_info else None
        tooltip = lua.execute("""
        local lines = {}
        return { lines = lines, AddLine = function(self, text) lines[#lines + 1] = text end, Show = function() end }
        """)
        selected = lua.table(isUpgrade=True, deltaScore=5, slotLabel="Head")
        context = lua.table(specName="Blood", profile=lua.table(goal="MYTHIC_PLUS"))
        ns.RenderTooltipVerdict(tooltip, context, lua.table(selected=selected, itemLink="item:7000"))
        return [tooltip.lines[i] for i in range(1, len(tooltip.lines) + 1)]

    def test_catalyst_candidate_gets_the_plain_catalyst_line(self) -> None:
        lines = self.render(lambda lua: lua.table(catalystPath=lua.table(bonus=8, slot="Head", targetItemID=1000)))
        catalyst = [line for line in lines if self.CATALYST_TEXT in line]
        self.assertEqual(1, len(catalyst))
        self.assertTrue(catalyst[0].startswith("|cffffffffReference: "))
        self.assertFalse(any("(BIS)" in line for line in lines))

    def test_bis_item_keeps_the_bis_tag_without_the_catalyst_line(self) -> None:
        lines = self.render(lambda lua: lua.table(bis=lua.table(bonus=8, slot="Head")))
        self.assertTrue(any("(BIS)" in line for line in lines))
        self.assertFalse(any(self.CATALYST_TEXT in line for line in lines))

    def test_no_reference_means_no_reference_line(self) -> None:
        lines = self.render(None)
        self.assertFalse(any("Reference:" in line for line in lines))


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
        self.assertIn('label = "Mode"', source)
        self.assertNotIn('label = "Weights"', source)
        self.assertIn('mode = "weights"', source)
        self.assertNotIn("IsBenchmarkRelevant", source)
        self.assertNotIn('label = "Benchmark"', source)
        self.assertIn('tooltip = "Choose how stat priorities and targets are decided: Guide or Measured."', source)
        self.assertNotIn("Blend", source)
        for path in toc_lua_files():
            self.assertNotIn("IsBenchmarkRelevant", path.read_text(encoding="utf-8-sig"), path.name)

    def test_manual_describes_the_weights_button(self) -> None:
        source = (ADDON / "UI" / "SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("Mode — choose how stat priorities and targets are decided: Guide (from the guides, "
                      "recommended) or Measured (our own measurement).", source)
        self.assertIn("With Guide you also pick a stat target difficulty: Tier 3, Tier 2 or Tier 1 "
                      "(the most demanding).", source)
        self.assertIn("With Measured you pick a gear level instead: Champion, Hero or Myth (the most "
                      "demanding); Best in Slot, trinkets and targets follow it.", source)
        for word in ("Easy", "Hard"):
            self.assertNotIn(word, source)
        self.assertNotIn("Benchmark", source)
        self.assertNotIn("Blend", source)


FRAME_STUB = """
-- Minimal stand-in for the WoW frame API: every method is a no-op that returns the
-- object itself, SetText records the text, and numeric getters return numbers.
local numeric = { GetFrameLevel = 1, GetWidth = 280, GetHeight = 500, GetStringWidth = 40, GetStringHeight = 12 }
local function Stub()
    local object = {}
    return setmetatable(object, { __index = function(t, key)
        if key == "SetText" then return function(self, value) rawset(self, "text", value) end end
        if key == "SetShown" then return function(self, value) rawset(self, "shown", value) end end
        if key == "CreateFontString" then
            return function(self, name, layer, template)
                local text = Stub()
                rawset(text, "_template", template)
                return text
            end
        end
        if key == "CreateTexture" then return function() return Stub() end end
        -- Sizes are recorded (underscore fields) for the drawer geometry checks.
        if key == "SetHeight" then return function(self, value) rawset(self, "_height", value) end end
        if key == "SetSize" then return function(self, w, h) rawset(self, "_width", w) rawset(self, "_height", h) end end
        if key == "SetAlpha" then return function(self, value) rawset(self, "_alpha", value) end end
        if key == "EnableMouse" then return function(self, value) rawset(self, "_mouse", value) end end
        if key == "Enable" then return function(self) rawset(self, "_enabled", true) end end
        if key == "Disable" then return function(self) rawset(self, "_enabled", false) end end
        if key == "SetPoint" then
            return function(self, ...)
                local points = rawget(self, "points") or {}
                points[#points + 1] = { ... }
                rawset(self, "points", points)
            end
        end
        if key == "SetSpacing" then return function(self, value) rawset(self, "spacing", value) end end
        if key == "SetJustifyV" then return function(self, value) rawset(self, "_justifyV", value) end end
        if key == "SetChecked" then return function(self, value) rawset(self, "checked", value) end end
        if key == "SetWidth" then return function(self, value) rawset(self, "_width", value) end end
        if key == "SetBackdrop" then return function(self, value) rawset(self, "_backdrop", value) end end
        if key == "SetBackdropColor" then
            return function(self, r, g, b, a) rawset(self, "_bg", { r, g, b, a }) end
        end
        if key == "SetBackdropBorderColor" then
            return function(self, r, g, b, a) rawset(self, "_border", { r, g, b, a }) end
        end
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
CreateFrame = function(kind, name, parent, template)
    local frame = Stub()
    rawset(frame, "_frameTemplate", template)
    return frame
end
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WeightsDrawerSmokeTests(unittest.TestCase):
    NO_DATA = "No measured data for this build: the guide is used."
    NO_GUIDE_TARGETS = "No guide targets for this build: our own are used."

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

    EASY = "Tier 3: stat targets that most players reach. A comfortable goal."
    NORMAL = "Tier 2: the stats of a typical player. A solid, realistic goal."
    HARD = "Tier 1: the stats the best-equipped players reach. The most demanding goal."
    CHAMPION = "Best in Slot, trinkets and targets at Champion-track gear. A comfortable goal."
    HERO = "Best in Slot, trinkets and targets at Hero-track gear. A solid, realistic goal."
    MYTH = "Best in Slot, trinkets and targets at Myth-track gear. The most demanding goal."

    def test_title_intro_and_two_mode_rows(self) -> None:
        card = self.card()
        self.assertEqual("Mode", card.title.text)
        self.assertEqual("Choose how stat priorities and targets are decided.", card.intro.text)
        self.assertEqual(2, len(card.modeRows))
        self.assertEqual(["GUIDE", "MEASURED"], [card.modeRows[i].key for i in (1, 2)])
        self.assertEqual(["Guide", "Measured"], [card.modeRows[i].label.text for i in (1, 2)])
        self.assertEqual("Recommended", card.modeRows[1].hint.text)
        for i in (1, 2):
            self.assertTrue(card.modeRows[i].meaning.text)

    def test_guide_is_selected_by_default(self) -> None:
        card = self.card()
        self.assertEqual([True, False], [card.modeRows[i].check.checked for i in (1, 2)])
        self.assertIn("guides", card.about.text)

    def test_clicking_a_row_sets_the_weight_mode_and_marks_it(self) -> None:
        card = self.card()
        card.modeRows[2].scripts.OnClick()
        self.assertEqual("MEASURED", self.lua.globals().StatVerdictDB.weightMode)
        self.assertEqual("MEASURED", self.ns.ProfileRepository.GetWeightMode())
        self.assertEqual([False, True], [card.modeRows[i].check.checked for i in (1, 2)])
        self.assertIn("simulations", card.about.text)
        self.assertGreaterEqual(self.refreshes, 1)
        card.modeRows[1].scripts.OnClick()
        self.assertEqual("GUIDE", self.lua.globals().StatVerdictDB.weightMode)
        self.assertEqual([True, False], [card.modeRows[i].check.checked for i in (1, 2)])
        self.assertIn("guides", card.about.text)

    def test_saved_mode_is_shown_as_selected(self) -> None:
        self.lua.globals().StatVerdictDB.weightMode = "MEASURED"
        card = self.card()
        self.assertEqual([False, True], [card.modeRows[i].check.checked for i in (1, 2)])

    def test_saved_blend_mode_shows_guide(self) -> None:
        self.lua.globals().StatVerdictDB.weightMode = "BLEND"
        card = self.card()
        self.assertEqual([True, False], [card.modeRows[i].check.checked for i in (1, 2)])
        self.assertIn("guides", card.about.text)

    def test_mode_description_sits_right_under_the_mode_rows(self) -> None:
        card = self.card()
        rawequal = self.lua.eval("rawequal")
        # Where the third (Blend) row used to be: hanging from the last mode row.
        self.assertEqual("TOPLEFT", card.about.points[1][1])
        self.assertTrue(rawequal(card.modeRows[2], card.about.points[1][2]))
        self.assertIsNone(card.aboutTitle)
        # Then the status line, the separator and the stat target group, in that order.
        self.assertTrue(rawequal(card.about, card.status.points[1][2]))
        self.assertTrue(rawequal(card.status, card.separator.points[1][2]))
        self.assertTrue(rawequal(card.separator, card.binGroup.points[1][2]))
        for mode in self.ns.GetWeightModes().values():
            self.assertLessEqual(len(mode.about), 300, mode.key)

    def test_description_lines_have_extra_spacing(self) -> None:
        card = self.card()
        self.assertGreaterEqual(card.about.spacing, 3)
        self.assertEqual(card.about._template, card.binNote._template)
        self.assertEqual(card.about.spacing, card.binNote.spacing)

    def test_no_current_data_block_any_more(self) -> None:
        card = self.card()
        self.assertIsNone(card.dataRows)
        self.assertIsNone(card.infoTitle)

    def test_status_is_empty_in_guide_mode_even_without_measured_data(self) -> None:
        self.measured = False
        self.assertEqual("", self.card().status.text)

    def test_status_is_empty_when_measured_data_exists(self) -> None:
        self.lua.globals().StatVerdictDB.weightMode = "MEASURED"
        self.assertEqual("", self.card().status.text)

    def test_status_says_the_guide_is_used_without_measured_data(self) -> None:
        self.measured = False
        self.lua.globals().StatVerdictDB.weightMode = "MEASURED"
        self.assertEqual(self.NO_DATA, self.card().status.text)

    def test_status_is_empty_without_an_active_build(self) -> None:
        self.has_profile = False
        for mode in ("GUIDE", "MEASURED"):
            self.lua.globals().StatVerdictDB.weightMode = mode
            self.assertEqual("", self.card().status.text, mode)

    def test_status_says_our_targets_are_used_without_guide_targets(self) -> None:
        self.guide_targets = False
        self.assertEqual(self.NO_GUIDE_TARGETS, self.card().status.text)
        # Only in Guide mode: Measured shows our own targets anyway.
        self.lua.globals().StatVerdictDB.weightMode = "MEASURED"
        self.assertEqual("", self.card().status.text)
        self.measured = False
        self.assertEqual(self.NO_DATA, self.card().status.text)

    def test_mode_rows_describe_targets_too(self) -> None:
        card = self.card()
        self.assertIn("guides", card.about.text)
        self.assertIn("stat targets", card.about.text)
        for i in (1, 2):
            self.assertLessEqual(len(card.modeRows[i].meaning.text), 31, i)  # one line in the row

    def test_no_raider_io_wording_left(self) -> None:
        source = (ADDON / "UI" / "SV_WeightsDrawerPanel.lua").read_text(encoding="utf-8-sig")
        for word in ("MythicPlusBenchmarks", "confidence", "sample", "Mythic+", "top 25", "Blend", "BLEND", "Tier"):
            self.assertNotIn(word, source)

    def bin_checks(self, card):
        return [card.binRows[i].check.checked for i in (1, 2, 3)]

    def test_stat_target_group_is_a_difficulty_from_easy_to_hard(self) -> None:
        card = self.card()
        self.assertEqual("Stat targets", card.binTitle.text)
        self.assertEqual(3, len(card.binRows))
        self.assertEqual(["top80", "top50", "top20"], [card.binRows[i].key for i in (1, 2, 3)])
        self.assertEqual(["Tier 3", "Tier 2", "Tier 1"], [card.binRows[i].label.text for i in (1, 2, 3)])
        # Side by side, left to right.
        xs = [card.binRows[i].points[1][4] for i in (1, 2, 3)]
        self.assertEqual(sorted(xs), xs)
        self.assertEqual(len(set(xs)), 3)
        # Default: Tier 1 (top20), explained under the options, starting with its name.
        self.assertEqual([False, False, True], self.bin_checks(card))
        self.assertEqual(self.HARD, card.binNote.text)
        self.assertTrue(card.binNote.text.startswith("Tier 1: "))

    def test_stat_target_group_shows_the_saved_difficulty(self) -> None:
        for key, checks, note in (("top80", [True, False, False], self.EASY),
                                  ("top50", [False, True, False], self.NORMAL)):
            self.lua.globals().StatVerdictDB.statTargetBin = key
            card = self.card()
            self.assertEqual(checks, self.bin_checks(card), key)
            self.assertEqual(note, card.binNote.text, key)

    def test_invalid_saved_bin_shows_hard(self) -> None:
        self.lua.globals().StatVerdictDB.statTargetBin = "top99"
        card = self.card()
        self.assertEqual([False, False, True], self.bin_checks(card))
        self.assertEqual(self.HARD, card.binNote.text)

    def test_clicking_a_difficulty_sets_it_and_refreshes(self) -> None:
        card = self.card()
        card.binRows[2].scripts.OnClick()
        self.assertEqual("top50", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual("top50", self.ns.ProfileRepository.GetStatTargetBin())
        self.assertEqual([False, True, False], self.bin_checks(card))
        self.assertEqual(self.NORMAL, card.binNote.text)
        self.assertGreaterEqual(self.refreshes, 1)
        card.binRows[1].scripts.OnClick()
        self.assertEqual("top80", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual([True, False, False], self.bin_checks(card))
        self.assertEqual(self.EASY, card.binNote.text)
        # The weight mode is left alone.
        self.assertEqual("GUIDE", self.ns.GetWeightMode())

    def labels(self, card):
        return [card.binRows[i].label.text for i in (1, 2, 3)]

    def assert_never_dimmed(self, card):
        for i in (1, 2, 3):
            option = card.binRows[i]
            self.assertFalse(option.dimmed, i)
            self.assertNotEqual(False, option._mouse, i)
            self.assertIn(option._alpha, (None, 1), i)

    def test_measured_turns_the_cards_into_gear_levels(self) -> None:
        self.lua.globals().StatVerdictDB.statTargetBin = "top50"
        card = self.card()
        self.assert_never_dimmed(card)
        card.modeRows[2].scripts.OnClick()
        self.assertEqual("Gear level", card.binTitle.text)
        self.assertEqual(["Champion", "Hero", "Myth"], self.labels(card))
        self.assertEqual(["champion", "hero", "myth"], [card.binRows[i].key for i in (1, 2, 3)])
        # Default Myth, explained under the cards; never dimmed, always clickable.
        self.assertEqual([False, False, True], self.bin_checks(card))
        self.assertEqual(self.MYTH, card.binNote.text)
        self.assert_never_dimmed(card)
        self.assertNotIn("Not used", card.binNote.text)

    def test_clicking_a_gear_level_sets_it_and_refreshes(self) -> None:
        self.lua.globals().StatVerdictDB.weightMode = "MEASURED"
        self.lua.globals().StatVerdictDB.statTargetBin = "top50"
        card = self.card()
        before = self.refreshes
        card.binRows[2].scripts.OnClick()
        self.assertEqual("hero", self.lua.globals().StatVerdictDB.gearLevel)
        self.assertEqual([False, True, False], self.bin_checks(card))
        self.assertEqual(self.HERO, card.binNote.text)
        self.assertGreater(self.refreshes, before)
        card.binRows[1].scripts.OnClick()
        self.assertEqual("champion", self.lua.globals().StatVerdictDB.gearLevel)
        self.assertEqual(self.CHAMPION, card.binNote.text)
        # The guide's tier is a separate, untouched choice.
        self.assertEqual("top50", self.lua.globals().StatVerdictDB.statTargetBin)
        self.assertEqual("MEASURED", self.ns.GetWeightMode())

    def test_each_mode_remembers_its_own_choice(self) -> None:
        db = self.lua.globals().StatVerdictDB
        db.statTargetBin = "top80"
        db.gearLevel = "hero"
        card = self.card()
        self.assertEqual("Stat targets", card.binTitle.text)
        self.assertEqual(["Tier 3", "Tier 2", "Tier 1"], self.labels(card))
        self.assertEqual([True, False, False], self.bin_checks(card))
        self.assertEqual(self.EASY, card.binNote.text)
        card.modeRows[2].scripts.OnClick()
        self.assertEqual([False, True, False], self.bin_checks(card))
        self.assertEqual(self.HERO, card.binNote.text)
        card.modeRows[1].scripts.OnClick()
        self.assertEqual(["Tier 3", "Tier 2", "Tier 1"], self.labels(card))
        self.assertEqual([True, False, False], self.bin_checks(card))
        self.assertEqual(self.EASY, card.binNote.text)
        self.assertEqual(("top80", "hero"), (db.statTargetBin, db.gearLevel))

    def test_hovering_follows_the_mode_shown(self) -> None:
        self.lua.globals().StatVerdictDB.weightMode = "MEASURED"
        self.lua.globals().StatVerdictDB.gearLevel = "champion"
        card = self.card()
        # The selected gear level stays gold while hovered.
        card.binRows[1].scripts.OnEnter(card.binRows[1])
        self.assertEqual(self.GOLD_BORDER, self.border(card.binRows[1]))
        card.binRows[3].scripts.OnEnter(card.binRows[3])
        self.assertNotEqual(self.GOLD_BORDER, self.border(card.binRows[3]))

    # --- Difficulty chips: same look as the mode rows ---------------------------
    GOLD_BORDER = (1.0, 0.82, 0.0)

    def border(self, region):
        return tuple(round(region._border[i], 2) for i in (1, 2, 3))

    def test_difficulties_are_equal_chips_in_one_row(self) -> None:
        card = self.card()
        chips = [card.binRows[i] for i in (1, 2, 3)]
        for chip in chips:
            # Same frame and backdrop style as the mode rows.
            self.assertEqual("BackdropTemplate", chip._frameTemplate)
            self.assertEqual(card.modeRows[1]._backdrop.edgeFile, chip._backdrop.edgeFile)
            self.assertEqual(card.modeRows[1]._backdrop.bgFile, chip._backdrop.bgFile)
            self.assertEqual("TOPLEFT", chip.points[1][1])
        self.assertEqual(1, len({chip._width for chip in chips}))
        self.assertEqual(1, len({chip._height for chip in chips}))
        self.assertEqual(1, len({chip.points[1][5] for chip in chips}))  # one row
        width = chips[0]._width
        xs = [chip.points[1][4] for chip in chips]
        self.assertEqual(0, xs[0])
        gaps = [xs[i + 1] - xs[i] - width for i in (0, 1)]
        self.assertEqual(gaps[0], gaps[1])
        self.assertGreaterEqual(gaps[0], 6)
        # The row spans the drawer's text width exactly.
        self.assertAlmostEqual(self.DRAWER_TEXT_WIDTH, xs[2] + width, delta=0.01)

    def test_selected_chip_is_gold_and_ticked_like_the_mode_rows(self) -> None:
        self.lua.globals().StatVerdictDB.statTargetBin = "top50"
        card = self.card()
        selected, other = card.binRows[2], card.binRows[1]
        self.assertTrue(selected.check.checked)
        self.assertEqual(self.border(card.modeRows[1]), self.border(selected))
        self.assertEqual(self.GOLD_BORDER, self.border(selected))
        self.assertEqual(self.border(card.modeRows[2]), self.border(other))
        self.assertNotEqual(self.GOLD_BORDER, self.border(other))
        self.assertEqual(tuple(card.modeRows[1]._bg[i] for i in (1, 2, 3)),
                         tuple(selected._bg[i] for i in (1, 2, 3)))
        self.assertEqual(tuple(card.modeRows[2]._bg[i] for i in (1, 2, 3)),
                         tuple(other._bg[i] for i in (1, 2, 3)))

    def test_hovering_a_chip_lights_its_border(self) -> None:
        card = self.card()
        chip = card.binRows[1]
        resting = self.border(chip)
        chip.scripts.OnEnter(chip)
        self.assertNotEqual(resting, self.border(chip))
        self.assertEqual(self.border(card.modeRows[2]), resting)
        chip.scripts.OnLeave(chip)
        self.assertEqual(resting, self.border(chip))
        # The selected chip stays gold while hovered.
        card.binRows[3].scripts.OnEnter(card.binRows[3])
        self.assertEqual(self.GOLD_BORDER, self.border(card.binRows[3]))

    def test_stat_target_group_has_room_to_breathe(self) -> None:
        card = self.card()
        group = card.binGroup
        self.assertLessEqual(group.points[1][5], -16)  # margin under the separator
        title_bottom = self.region_top(card, card.binTitle) - self.text_height(card.binTitle, 252)
        chip = card.binRows[1]
        chip_top = self.region_top(card, group) + chip.points[1][5]
        self.assertGreaterEqual(title_bottom - chip_top, 12)  # the cards never crowd the title
        self.assertGreaterEqual(chip._height, 26)
        note_top = self.region_top(card, card.binNote)
        self.assertGreaterEqual(chip_top - chip._height - note_top, 8)
        group_bottom = self.region_top(card, group) - group._height
        self.assertGreaterEqual(note_top - card.binNote._height - group_bottom, 4)

    # --- Geometry: the whole drawer must fit the card ---------------------------
    # The drawer card spans the Stat Progress card: frame height 440 minus the title
    # well (33), the well padding (6) and a gutter above and below (2 x 10).
    CARD_HEIGHT = 440 - 33 - 6 - 2 * 10
    BOTTOM_BORDER = 6
    DRAWER_TEXT_WIDTH = 280 - 2 * 14
    # Conservative pixel sizes of the WoW fonts used (font size, average character width).
    FONTS = {"GameFontNormal": (12, 6.5), "GameFontNormalSmall": (10, 5.5), "GameFontHighlightSmall": (10, 5.5)}

    def text_height(self, text_object, width: int) -> float:
        size, char_width = self.FONTS[text_object._template]
        per_line = max(1, int(width // char_width))
        lines, current = 0, 0
        for word in (text_object.text or "").split():
            need = len(word) if current == 0 else current + 1 + len(word)
            if current and need > per_line:
                lines, current = lines + 1, len(word)
            else:
                current = need
        lines += 1 if current else 0
        spacing = text_object.spacing or 2
        return 0 if lines == 0 else lines * size + (lines - 1) * spacing

    def region_top(self, card, region) -> float:
        """Distance of a region's top from the card's top (negative is down), following
        its first anchor the way WoW does for TOPLEFT points."""
        point = region.points[1]
        relative, relative_point, y = point[2], point[3], point[5]
        if self.lua.eval("rawequal")(relative, card):
            return y
        base = self.region_top(card, relative)
        if str(relative_point).startswith("BOTTOM"):
            base -= self.region_height(relative)
        return base + y

    def region_height(self, region) -> float:
        if region._height is not None:
            return region._height
        return self.text_height(region, self.DRAWER_TEXT_WIDTH)

    def lowest_bottom(self, card) -> float:
        return self.region_top(card, card.binGroup) - self.region_height(card.binGroup)

    def test_whole_drawer_fits_the_card_in_every_state(self) -> None:
        worst = 0
        for mode in ("GUIDE", "MEASURED"):
            for measured in (True, False):
                for guide_targets in (True, False):
                    self.lua.globals().StatVerdictDB.weightMode = mode
                    self.measured, self.guide_targets = measured, guide_targets
                    card = self.card()
                    bottom = self.lowest_bottom(card)
                    worst = min(worst, bottom)
                    self.assertGreaterEqual(bottom, -(self.CARD_HEIGHT - self.BOTTOM_BORDER),
                                            (mode, measured, guide_targets))
                    # Every card label fits its card beside the tick.
                    for i in (1, 2, 3):
                        chip = card.binRows[i]
                        label_width = len(chip.label.text) * self.FONTS["GameFontHighlightSmall"][1]
                        self.assertLessEqual(4 + 20 + 1 + label_width + 4, chip._width, chip.label.text)
        # Every explanation (tiers and gear levels) fits its reserved space (two lines).
        abouts = [bin.about for bin in self.ns.GetStatTargetBins().values()]
        abouts += [level.about for level in self.ns.GetGearLevels().values()]
        self.assertEqual(6, len(abouts))
        for about in abouts:
            card.binNote.text = about
            self.assertLessEqual(self.text_height(card.binNote, self.DRAWER_TEXT_WIDTH), card.binNote._height, about)
        print(f"\n[weights drawer] content bottom {-worst:.0f}px of {self.CARD_HEIGHT - self.BOTTOM_BORDER}px")

    # --- Nothing moves: every element keeps its place and size in every state ------
    def region_left(self, card, region) -> float:
        point = region.points[1]
        relative, x = point[2], point[4]
        if self.lua.eval("rawequal")(relative, card):
            return x
        return self.region_left(card, relative) + x

    def layout_snapshot(self, card):
        regions = {"mode row 1": card.modeRows[1], "mode row 2": card.modeRows[2],
                   "mode explanation": card.about, "status line": card.status,
                   "separator": card.separator, "group": card.binGroup, "group title": card.binTitle,
                   "card 1": card.binRows[1], "card 2": card.binRows[2], "card 3": card.binRows[3],
                   "card explanation": card.binNote}
        snapshot = {}
        for name, region in regions.items():
            if name.startswith("card ") and name != "card explanation":
                top = self.region_top(card, card.binGroup) + region.points[1][5]
                left = self.region_left(card, card.binGroup) + region.points[1][4]
                height, width = region._height, region._width
            else:
                top, left = self.region_top(card, region), self.region_left(card, region)
                # Width follows the anchors: the right edge's anchor and offset.
                points = region.points
                height = self.region_height(region)
                width = None if points[2] is None else (points[2][3], points[2][4])
            snapshot[name] = (round(top, 3), round(left, 3), round(height, 3), width)
        return snapshot

    def test_nothing_moves_or_resizes_in_any_state(self) -> None:
        db = self.lua.globals().StatVerdictDB
        tiers, levels = ("top80", "top50", "top20"), ("champion", "hero", "myth")
        reference, states = None, 0
        for mode in ("GUIDE", "MEASURED"):
            for index in range(3):
                for measured in (True, False):
                    for guide_targets in (True, False):
                        db.weightMode, db.statTargetBin, db.gearLevel = mode, tiers[index], levels[index]
                        self.measured, self.guide_targets = measured, guide_targets
                        state = (mode, index + 1, measured, guide_targets)
                        snapshot = self.layout_snapshot(self.card())
                        states += 1
                        if reference is None:
                            reference = snapshot
                            continue
                        for name, value in snapshot.items():
                            self.assertEqual(reference[name], value, (name, state))
        self.assertEqual(24, states)

    def test_reserved_blocks_hold_their_longest_text(self) -> None:
        card = self.card()
        for mode in self.ns.GetWeightModes().values():
            card.about.text = mode.about
            self.assertLessEqual(self.text_height(card.about, self.DRAWER_TEXT_WIDTH), card.about._height, mode.key)
        for status in (self.NO_DATA, self.NO_GUIDE_TARGETS):
            card.status.text = status
            self.assertLessEqual(self.text_height(card.status, self.DRAWER_TEXT_WIDTH), card.status._height, status)
        # Shorter texts start at the top of their block and leave the space below empty.
        for text in (card.about, card.status, card.binNote):
            self.assertEqual("TOP", text._justifyV)

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
-- The game's tooltip data per hyperlink (nil = not loaded yet).
TOOLTIP_DATA = {}
C_TooltipInfo = { GetHyperlink = function(link) return TOOLTIP_DATA[link] end }
-- The game's line type for a gem socket (filled or empty) in tooltip data.
Enum = Enum or {}
Enum.TooltipDataLineType = { None = 0, GemSocket = 3 }
-- Records what the panel asks the game tooltip to show, in order.
TOOLTIP_CALLS = {}
GameTooltip = {}
function GameTooltip:SetOwner(owner, anchor)
    self.owner = owner
    TOOLTIP_CALLS[#TOOLTIP_CALLS + 1] = { "SetOwner", anchor }
end
function GameTooltip:SetHyperlink(link) TOOLTIP_CALLS[#TOOLTIP_CALLS + 1] = { "SetHyperlink", link } end
function GameTooltip:AddLine(text) TOOLTIP_CALLS[#TOOLTIP_CALLS + 1] = { "AddLine", text } end
function GameTooltip:Show() TOOLTIP_CALLS[#TOOLTIP_CALLS + 1] = { "Show" } end
function GameTooltip:Hide() self.owner = nil TOOLTIP_CALLS[#TOOLTIP_CALLS + 1] = { "Hide" } end
function GameTooltip:IsOwned(frame) return self.owner == frame end
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
    rawset(frame, "Show", function(self) rawset(self, "_visible", true) end)
    rawset(frame, "Hide", function(self) rawset(self, "_visible", false) end)
    CREATED[#CREATED + 1] = frame
    return frame
end
"""

# One real Guardian Druid Mythic+ head slot from the generated data.
GUARDIAN_HEAD = {
    "item_id": 271528,
    "bonus_ids": [13334, 6652, 13696, 13847, 13692, 13698, 12854],
    "gem_ids": [240983, 240894],
    "enchant": {"id": 7961, "item_id": 243951, "spell_id": 1236056},
}
GUARDIAN_HEAD_LINK = ("item:271528:7961:240983:240894:::::90:104::0:7:"
                      "13334:6652:13696:13847:13692:13698:12854")
EPIC = (0.64, 0.21, 0.93)
# The game's tooltip for that head, as in the owner's screenshot (left, right, colour).
GUARDIAN_HEAD_TOOLTIP = [
    ("Enigmatic Dreamwatcher's Somnolent Stare", None, EPIC),
    ("Heroic", None, (0.12, 1, 0)),
    ("Venomcursed", None, (0.12, 1, 0)),
    ("Item Level 334", None, (1, 0.82, 0)),
    ("Upgrade Level: Myth 6/6", None, (1, 0.82, 0)),
    ("Binds when picked up", None, (1, 1, 1)),
    ("Head", "Leather", (1, 1, 1)),
    ("147 Armor", None, (1, 1, 1)),
    ("+189 Agility", None, (1, 1, 1)),
    ("+3,910 Stamina", None, (1, 1, 1)),
    ("+142 Haste #1", None, (1, 1, 1)),
    ("+59 Versatility #2", None, (1, 1, 1)),
    ("+189 Intellect", None, (0.5, 0.5, 0.5)),
    ("Equip: Your attacks have a chance to lull your foes.", None, (0.12, 1, 0)),
    ("Bark of the Enigmatic Dreamwatcher (0/5)", None, (1, 0.82, 0)),
    ("  Enigmatic Dreamwatcher's Somnolent Stare", None, (0.5, 0.5, 0.5)),
    ("  Enigmatic Dreamwatcher's Bark Mantle", None, (0.5, 0.5, 0.5)),
    ("(2) Set: Your abilities grow stronger.", None, (0.5, 0.5, 0.5)),
    ("(4) Set: Your abilities grow much stronger.", None, (0.5, 0.5, 0.5)),
]
GUARDIAN_HEAD_KEPT = [
    ("Enigmatic Dreamwatcher's Somnolent Stare", None),
    ("Item Level 334", None),
    ("Upgrade Level: Myth 6/6", None),
    ("Binds when picked up", None),
    ("Head", "Leather"),
    ("147 Armor", None),
    ("+189 Agility", None),
    ("+3,910 Stamina", None),
    ("+142 Haste", None),
    ("+59 Versatility", None),
    ("+189 Intellect", None),
    ("Part of the tier set", None),
]
# The Recommended block: dim sub-headings, one name per line, only the best choice.
HEAD_RECOMMENDED = [
    ("Recommended", None),
    ("Gems", None),
    ("Flawless Gem", None),
    ("Quick Gem", None),
    ("Enchant", None),
    ("Enchant Helm - Scroll", None),
]
GEM_SOCKET = 3  # Enum.TooltipDataLineType.GemSocket
# The same head as the game shows it with two sockets: the first filled by the
# recommended gem (its stat and icon), the second still empty.
GUARDIAN_HEAD_SOCKETED_TOOLTIP = GUARDIAN_HEAD_TOOLTIP[:13] + [
    ("+147 Haste", None, (1, 1, 1), {"type": GEM_SOCKET, "gemIcon": 4643916}),
    ("Prismatic Socket", None, (0.5, 0.5, 0.5), {"type": GEM_SOCKET, "socketType": "Prismatic"}),
    ("Socket Bonus: +15 Haste", None, (0.5, 0.5, 0.5)),
] + GUARDIAN_HEAD_TOOLTIP[13:]
# A ring with a single empty socket.
ONE_SOCKET_RING_TOOLTIP = [
    ("Band of Tests", None, EPIC),
    ("Item Level 334", None, (1, 0.82, 0)),
    ("Finger", None, (1, 1, 1)),
    ("+3,000 Stamina", None, (1, 1, 1)),
    ("+400 Mastery", None, (1, 1, 1)),
    ("Prismatic Socket", None, (0.5, 0.5, 0.5), {"type": GEM_SOCKET, "socketType": "Prismatic"}),
]


def socketed_item_tooltip(name: str, sockets: int) -> list:
    """A plain item's tooltip with `sockets` empty Prismatic sockets."""
    return [
        (name, None, EPIC),
        ("Item Level 334", None, (1, 0.82, 0)),
        ("+3,000 Stamina", None, (1, 1, 1)),
        ("+400 Mastery", None, (1, 1, 1)),
    ] + [("Prismatic Socket", None, (0.5, 0.5, 0.5), {"type": GEM_SOCKET, "socketType": "Prismatic"})] * sockets


# The guide's gems: one unique-equipped primary gem, one secondary gem for the rest.
PRIMARY_GEM = 240990
SECONDARY_GEM = 240894
GUIDE_GEMS = {"primary": PRIMARY_GEM, "secondary": SECONDARY_GEM}
BIS_SLOTS = ("Head", "Neck", "Shoulders", "Back", "Chest", "Wrist", "Hands", "Waist", "Legs", "Feet",
             "Finger 1", "Finger 2", "Trinket 1", "Trinket 2", "Main Hand", "Off Hand")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class BisPanelTests(unittest.TestCase):
    """Best in Slot rows are a compact list; hovering one shows our own small
    tooltip: the recommended item's identity and stats, then the gems/enchant."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.lua.execute(BIS_PANEL_STUB)
        self.lua.globals().StatVerdictDB = self.lua.table()
        self.ns = self.lua.table()
        self.mode = "bis"
        self.ns.GetRightPanelMode = lambda: self.mode
        load_addon_file(self.lua, self.ns, "UI/SV_BisProgressPanel.lua")
        self.panel = self.ns.StatVerdictBisProgressPanel
        # The first frame the file creates listens for item data arriving.
        self.item_events = self.lua.globals().CREATED[1]
        self.frame = self.lua.eval("CreateFrame")()
        g = self.lua.globals()
        g.ITEM_NAMES[1001] = "Crown of Tests"
        g.ITEM_NAMES[1002] = "Amulet of Tests"
        g.ITEM_NAMES[1003] = "Blade of Tests"
        g.ITEM_NAMES[240983] = "Flawless Gem"
        g.ITEM_NAMES[240894] = "Quick Gem"
        g.ITEM_NAMES[240990] = "Indecipherable Eversong Diamond"
        g.ITEM_NAMES[243951] = "Enchant Helm - Scroll"

    # --- helpers ---------------------------------------------------------------------

    def slots(self, *entries):
        table = self.lua.table()
        for index, entry in enumerate(entries, start=1):
            table[index] = entry
        return table

    def item(self, item_id, gems=None, enchant=None, bonus_ids=None, gem_ids=None):
        gems = gem_ids if gems is None else gems
        item = self.lua.table(item_id=item_id)
        if bonus_ids is not None:
            item.bonus_ids = self.lua.table(*bonus_ids)
        if gems is not None:
            item.gem_ids = self.lua.table(*gems)
        if enchant is not None:
            item.enchant = self.lua.table(**enchant)
        return item

    def entry(self, slot="Head", **item):
        return self.lua.table(slot=slot, item=self.item(**item))

    def guardian_head(self):
        return self.lua.table(slot="Head", item=self.item(**GUARDIAN_HEAD))

    def tooltip_lines(self, rows):
        lines = self.lua.table()
        for index, (left, right, color, *extra) in enumerate(rows, start=1):
            line = self.lua.table(leftText=left, leftColor=self.lua.table(r=color[0], g=color[1], b=color[2]))
            if right is not None:
                line.rightText = right
            for key, value in (extra[0] if extra else {}).items():
                line[key] = value
            lines[index] = line
        return lines

    def game_knows(self, link, rows):
        self.lua.globals().TOOLTIP_DATA[link] = self.lua.table(lines=self.tooltip_lines(rows))

    def refresh(self, *entries, spec_id=None, gems=None):
        bis = self.lua.table(slots=self.slots(*entries))
        if gems is not None:
            bis.gems = self.lua.table(**gems)
        profile = self.lua.table(generatedContext=self.lua.table(bis=bis), specID=spec_id)
        self.panel.Refresh(self.frame, profile)
        return self.frame.bisProgressCard

    def refresh_trinkets(self, count=1):
        self.mode = "trinkets"
        trinkets = self.slots(*[self.lua.table(item_id=1003, tier="S", bonus_ids=self.lua.table(6652))
                                for _ in range(count)])
        profile = self.lua.table(generatedContext=self.lua.table(trinkets=trinkets))
        self.panel.Refresh(self.frame, profile)
        return self.frame.bisProgressCard

    @staticmethod
    def pairs_of(lines):
        return [(lines[i].left, lines[i].right) for i in range(1, len(lines) + 1)]

    def hover(self, row):
        """Hovers a row; returns the shown tooltip lines as (left, right) pairs."""
        row.scripts.OnEnter(row)
        tip = self.panel.GetRecommendedTooltip()
        self.assertTrue(tip._visible)
        return self.pairs_of(tip.shownLines)

    # --- hyperlink -------------------------------------------------------------------

    def test_recommended_link_for_a_real_guardian_head(self) -> None:
        self.assertEqual(GUARDIAN_HEAD_LINK, self.panel.BuildRecommendedItemLink(self.guardian_head(), 104))

    def test_recommended_link_uses_the_player_level(self) -> None:
        self.lua.globals().UnitLevel = self.lua.eval("function() return 80 end")
        link = self.panel.BuildRecommendedItemLink(self.entry(item_id=1001, bonus_ids=[10, 11]), None)
        self.assertEqual("item:1001::::::::80:0::0:2:10:11", link)

    def test_recommended_link_without_bonuses_gems_or_enchant(self) -> None:
        link = self.panel.BuildRecommendedItemLink(self.lua.table(slot="Neck", item_id=1002), None)
        self.assertEqual("item:1002::::::::90:0::0:0", link)

    def test_recommended_link_keeps_at_most_four_gems(self) -> None:
        link = self.panel.BuildRecommendedItemLink(self.entry(item_id=1001, gems=[1, 2, 3, 4, 5]), 0)
        self.assertEqual("item:1001::1:2:3:4:::90:0::0:0", link)

    # --- line filter -----------------------------------------------------------------

    def test_filter_keeps_identity_and_stats_of_the_guardian_head(self) -> None:
        kept = self.panel.FilterItemTooltipLines(self.tooltip_lines(GUARDIAN_HEAD_TOOLTIP))
        self.assertEqual(GUARDIAN_HEAD_KEPT, self.pairs_of(kept))
        self.assertEqual(list(EPIC), [kept[1].color[i] for i in (1, 2, 3)])  # quality colour
        self.assertEqual([0.5, 0.5, 0.5], [kept[11].color[i] for i in (1, 2, 3)])  # inactive stat stays grey

    def test_set_name_becomes_a_plain_gold_line_with_a_small_gap(self) -> None:
        kept = self.panel.FilterItemTooltipLines(self.tooltip_lines(GUARDIAN_HEAD_TOOLTIP))
        set_line = kept[len(kept)]
        self.assertEqual("Part of the tier set", set_line.left)
        self.assertEqual([1, 0.82, 0], [set_line.color[i] for i in (1, 2, 3)])  # the game's set colour
        self.assertGreaterEqual(set_line.gap, 3)
        self.assertLessEqual(set_line.gap, 6)
        # Items outside a set get no set line at all.
        plain = self.pairs_of(self.panel.FilterItemTooltipLines(self.tooltip_lines(ONE_SOCKET_RING_TOOLTIP)))
        self.assertNotIn(("Part of the tier set", None), plain)

    def test_filter_drops_sockets_enchant_and_everything_after_the_stats(self) -> None:
        rows = self.tooltip_lines([
            ("|cffa335eeBlade of Tests|r", None, EPIC),
            ("Item Level 334", None, (1, 0.82, 0)),
            ("Unique-Equipped", None, (1, 1, 1)),
            ("One-Hand", "Dagger", (1, 1, 1)),
            ("210 - 350 Damage", "Speed 1.80", (1, 1, 1)),
            ("(155.6 damage per second)", None, (1, 1, 1)),
            ("+120 Agility", None, (1, 1, 1)),
            ("+70 Critical Strike", None, (1, 1, 1)),
            ("Enchanted: +80 Haste", None, (0.12, 1, 0)),
            ("+70 Haste", None, (1, 1, 1)),
            ("Durability 100 / 100", None, (1, 1, 1)),
            ("Requires Level 90", None, (1, 1, 1)),
            ("Use: Stab things.", None, (0.12, 1, 0)),
            ('"A very sharp test."', None, (1, 0.82, 0)),
        ])
        rows[10].gemIcon = 1234  # a filled socket
        kept = self.pairs_of(self.panel.FilterItemTooltipLines(rows))
        self.assertEqual([
            ("Blade of Tests", None),
            ("Item Level 334", None),
            ("One-Hand", "Dagger"),
            ("210 - 350 Damage", "Speed 1.80"),
            ("(155.6 damage per second)", None),
            ("+120 Agility", None),
            ("+70 Critical Strike", None),
        ], kept)

    def test_filter_drops_the_socket_lines_of_the_socketed_head(self) -> None:
        kept = self.panel.FilterItemTooltipLines(self.tooltip_lines(GUARDIAN_HEAD_SOCKETED_TOOLTIP))
        self.assertEqual(GUARDIAN_HEAD_KEPT, self.pairs_of(kept))

    # --- gems per socket -------------------------------------------------------------

    def gems_for(self, gem_ids, rows):
        lines = None if rows is None else self.tooltip_lines(rows)
        kept = self.panel.GemsForSockets(self.lua.table(*gem_ids), lines)
        return [kept[i] for i in range(1, len(kept) + 1)]

    def test_gems_follow_the_sockets_of_the_recommended_item(self) -> None:
        gems = [240983, 240894]
        self.assertEqual(gems, self.gems_for(gems, GUARDIAN_HEAD_SOCKETED_TOOLTIP))  # 2 sockets
        self.assertEqual([240983], self.gems_for(gems, ONE_SOCKET_RING_TOOLTIP))  # 1 socket
        self.assertEqual([], self.gems_for(gems, GUARDIAN_HEAD_TOOLTIP))  # no sockets
        self.assertEqual([240983], self.gems_for([240983], GUARDIAN_HEAD_SOCKETED_TOOLTIP))  # fewer gems
        self.assertEqual([], self.gems_for(gems, None))  # socket count unknown: none, never a guess
        self.assertEqual([], self.gems_for(gems, []))

    def test_filter_stops_at_equip_text_when_an_item_has_no_stats(self) -> None:
        kept = self.pairs_of(self.panel.FilterItemTooltipLines(self.tooltip_lines([
            ("Trinket of Tests", None, EPIC),
            ("Item Level 334", None, (1, 0.82, 0)),
            ("Trinket", None, (1, 1, 1)),
            ("Equip: +500 Haste while testing.", None, (0.12, 1, 0)),
            ("+300 Mastery", None, (1, 1, 1)),
        ])))
        self.assertEqual([("Trinket of Tests", None), ("Item Level 334", None), ("Trinket", None)], kept)

    # --- our tooltip -----------------------------------------------------------------

    def test_hover_shows_the_item_then_the_recommended_block(self) -> None:
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_SOCKETED_TOOLTIP)
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertEqual(GUARDIAN_HEAD_KEPT + HEAD_RECOMMENDED, self.hover(card.rows[1]))
        self.assertEqual([], [None for _ in self.lua.globals().TOOLTIP_CALLS])  # never the game tooltip

    def shown(self):
        tip = self.panel.GetRecommendedTooltip()
        return [tip.shownLines[i] for i in range(1, len(tip.shownLines) + 1)]

    def test_recommended_block_is_stacked_with_dim_headings_and_indented_names(self) -> None:
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_SOCKETED_TOOLTIP)
        self.hover(self.refresh(self.guardian_head(), spec_id=104).rows[1])
        block = {line.left: line for line in self.shown()[len(GUARDIAN_HEAD_KEPT):]}
        for heading in ("Gems", "Enchant"):
            self.assertEqual([0.55, 0.55, 0.55], [block[heading].color[i] for i in (1, 2, 3)], heading)
            self.assertFalse(block[heading].indent, heading)
        for name in ("Flawless Gem", "Quick Gem", "Enchant Helm - Scroll"):
            self.assertTrue(block[name].indent, name)
            self.assertTrue(block[name].wrap, name)  # wraps instead of widening the tooltip
        # A small gap between the gems and the enchant; a bigger one before the block.
        self.assertGreater(block["Enchant"].gap, 0)
        self.assertTrue(block["Recommended"].gapBefore)

    def test_gem_and_enchant_names_use_the_item_quality_colour(self) -> None:
        g = self.lua.globals()
        g.GetItemQualityColor = self.lua.eval(
            "function(q) if q == 4 then return 0.64, 0.21, 0.93, 'ffa335ee' end return 1, 1, 1, 'ffffffff' end")
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_SOCKETED_TOOLTIP)
        self.hover(self.refresh(self.guardian_head(), spec_id=104).rows[1])
        block = {line.left: line for line in self.shown()[len(GUARDIAN_HEAD_KEPT):]}
        for name in ("Flawless Gem", "Quick Gem", "Enchant Helm - Scroll"):
            self.assertEqual([0.64, 0.21, 0.93], [block[name].color[i] for i in (1, 2, 3)], name)

    def test_names_are_white_until_the_game_knows_them(self) -> None:
        g = self.lua.globals()
        g.GetItemQualityColor = self.lua.eval("function(q) return 0.64, 0.21, 0.93, 'ffa335ee' end")
        entry = self.entry(item_id=1001, gems=[777001], enchant={"id": 8017, "item_id": 777002})
        self.game_knows(self.panel.BuildRecommendedItemLink(entry, 0), ONE_SOCKET_RING_TOOLTIP)
        self.hover(self.refresh(entry).rows[1])
        block = {line.left: line for line in self.shown()}
        for name in ("Gem #777001", "Enchant #8017"):
            self.assertEqual([1, 1, 1], [block[name].color[i] for i in (1, 2, 3)], name)

    # --- enchant without a real enchant id (scroll id not translated) ---------------

    def test_link_leaves_the_enchant_out_without_a_real_id(self) -> None:
        for enchant in ({"item_id": 243951, "spell_id": 1236056}, {"item_id": 243951}, {"spell_id": 1236056}):
            link = self.panel.BuildRecommendedItemLink(
                self.entry(item_id=1001, gems=[240983], enchant=enchant), 0)
            self.assertEqual("item:1001::240983::::::90:0::0:0", link, enchant)

    def test_enchant_without_id_is_named_from_its_scroll_or_spell(self) -> None:
        g = self.lua.globals()
        g.SPELL_NAMES[1236001] = "Radiant Mastery"
        card = self.refresh(
            self.entry(slot="Head", item_id=1001, enchant={"item_id": 243951, "spell_id": 1236001}),
            self.entry(slot="Finger 1", item_id=1001, enchant={"spell_id": 1236001}),
            self.entry(slot="Wrist", item_id=1001, enchant={"item_id": 777003}),
        )
        self.assertIn(("Enchant Helm - Scroll", None), self.hover(card.rows[1]))
        self.assertIn(("Radiant Mastery", None), self.hover(card.rows[2]))
        # Scroll not loaded yet: its number stands in, and the load is requested.
        self.assertIn(("Enchant #777003", None), self.hover(card.rows[3]))
        self.assertTrue(g.REQUESTED[777003])

    def test_item_without_sockets_shows_no_gems(self) -> None:
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_TOOLTIP)
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertEqual(GUARDIAN_HEAD_KEPT + [
            ("Recommended", None),
            ("Enchant", None),
            ("Enchant Helm - Scroll", None),
        ], self.hover(card.rows[1]))
        self.assertFalse(self.shown()[-2].gap)  # no gems above: no extra gap

    def test_one_socket_shows_only_the_first_gem(self) -> None:
        entry = self.entry(slot="Finger 1", item_id=1001, gems=[240983, 240894])
        self.game_knows(self.panel.BuildRecommendedItemLink(entry, 0), ONE_SOCKET_RING_TOOLTIP)
        card = self.refresh(entry)
        lines = self.hover(card.rows[1])
        self.assertIn(("Flawless Gem", None), lines)
        self.assertNotIn(("Quick Gem", None), lines)

    def test_recommended_block_does_not_widen_the_tooltip(self) -> None:
        g = self.lua.globals()
        g.ITEM_NAMES[243951] = "Enchant Helm - A Very Long Scroll Name That Goes On And On"
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_SOCKETED_TOOLTIP)
        self.hover(self.refresh(self.guardian_head(), spec_id=104).rows[1])
        with_block = self.panel.GetRecommendedTooltip()._width
        g.StatVerdictDB.showBisGemsEnchants = False
        self.hover(self.refresh(self.guardian_head(), spec_id=104).rows[1])
        self.assertEqual(self.panel.GetRecommendedTooltip()._width, with_block)

    def test_tooltip_frame_sits_next_to_the_row_and_ignores_the_mouse(self) -> None:
        card = self.refresh(self.guardian_head())
        row = card.rows[1]
        self.hover(row)
        tip = self.panel.GetRecommendedTooltip()
        self.assertIs(False, tip._mouse)
        last = tip.points[len(tip.points)]
        self.assertEqual(("TOPLEFT", "TOPRIGHT"), (last[1], last[3]))
        self.assertTrue(self.lua.eval("function(a, b) return a == b end")(last[2], row))
        row.scripts.OnLeave(row)
        self.assertIs(False, tip._visible)

    def test_toggle_off_shows_the_item_without_the_recommended_block(self) -> None:
        self.lua.globals().StatVerdictDB.showBisGemsEnchants = False
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_TOOLTIP)
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertEqual(GUARDIAN_HEAD_KEPT, self.hover(card.rows[1]))

    def test_toggle_is_on_without_saved_settings(self) -> None:
        self.lua.globals().StatVerdictDB = None
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertIn(("Recommended", None), self.hover(card.rows[1]))

    # --- Features: our tooltip / game tooltip / nothing ------------------------------

    def game_tooltip_calls(self):
        calls = self.lua.globals().TOOLTIP_CALLS
        return [tuple(calls[i][j] for j in range(1, len(calls[i]) + 1)) for i in range(1, len(calls) + 1)]

    def our_tooltip_hidden(self):
        tip = self.panel.GetRecommendedTooltip()
        return tip is None or not tip._visible

    def rich_entry(self):
        return self.entry(item_id=1001, bonus_ids=[10, 11], gems=[240983], enchant={"id": 7961})

    def test_plain_link_is_only_the_item_and_its_bonuses(self) -> None:
        self.assertEqual("item:1001::::::::90:104::0:2:10:11",
                         self.panel.BuildPlainRecommendedItemLink(self.rich_entry(), 104))
        self.assertEqual("item:1002::::::::90:0::0:0",
                         self.panel.BuildPlainRecommendedItemLink(self.lua.table(slot="Neck", item_id=1002), None))

    def use_game_tooltip(self):
        g = self.lua.globals()
        g.StatVerdictDB.showBisTooltip = False
        g.StatVerdictDB.bisUseGameTooltip = True

    def test_game_tooltip_chosen_shows_the_plain_recommended_item(self) -> None:
        self.use_game_tooltip()
        row = self.refresh(self.rich_entry(), spec_id=104).rows[1]
        row.scripts.OnEnter(row)
        self.assertEqual([
            ("SetOwner", "ANCHOR_RIGHT"),
            ("SetHyperlink", "item:1001::::::::90:104::0:2:10:11"),
            ("Show",),
        ], self.game_tooltip_calls())
        self.assertTrue(self.our_tooltip_hidden())
        row.scripts.OnLeave(row)
        self.assertEqual(("Hide",), self.game_tooltip_calls()[-1])

    def test_game_tooltip_is_not_replaced_when_item_data_arrives(self) -> None:
        self.use_game_tooltip()
        row = self.refresh(self.rich_entry(), spec_id=104).rows[1]
        row.scripts.OnEnter(row)
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 1001, True)
        self.assertTrue(self.our_tooltip_hidden())

    def test_both_off_shows_nothing(self) -> None:
        for game_value in (None, False):  # unset counts as off
            self.lua.globals().TOOLTIP_CALLS = self.lua.table()
            g = self.lua.globals()
            g.StatVerdictDB.showBisTooltip = False
            g.StatVerdictDB.bisUseGameTooltip = game_value
            row = self.refresh(self.rich_entry(), spec_id=104).rows[1]
            row.scripts.OnEnter(row)
            self.assertEqual([], self.game_tooltip_calls(), game_value)
            self.assertTrue(self.our_tooltip_hidden(), game_value)

    def test_our_tooltip_wins_if_both_are_saved_on(self) -> None:
        self.lua.globals().StatVerdictDB.bisUseGameTooltip = True
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_TOOLTIP)
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertIn(("Recommended", None), self.hover(card.rows[1]))
        self.assertEqual([], self.game_tooltip_calls())

    def test_old_gems_choice_still_works_with_our_tooltip_explicitly_on(self) -> None:
        g = self.lua.globals()
        g.StatVerdictDB.showBisTooltip = True
        g.StatVerdictDB.showBisGemsEnchants = False
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_TOOLTIP)
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertEqual(GUARDIAN_HEAD_KEPT, self.hover(card.rows[1]))

    def test_ranked_trinkets_ignore_the_best_in_slot_options(self) -> None:
        g = self.lua.globals()
        g.StatVerdictDB.showBisTooltip = False
        card = self.refresh_trinkets()
        card.rows[1].scripts.OnEnter(card.rows[1])
        self.assertEqual([
            ("SetOwner", "ANCHOR_RIGHT"),
            ("SetHyperlink", "item:1003::::::::90::::1:6652"),
            ("Show",),
        ], self.game_tooltip_calls())

    # --- Measured gear level: the items at the chosen track --------------------------

    def use_level(self, mode, level, track_swap=True):
        """Loads the repository with the data root's trackSwap (string keys, as the
        generated file writes them) and saves the mode and gear level."""
        load_addon_file(self.lua, self.ns, "Core/SV_ProfileRepository.lua")
        root = self.lua.table(profiles=self.lua.table())
        if track_swap:
            root.trackSwap = self.lua.eval(
                '{ hero = { ["6652"] = 7652, ["13334"] = 14334 }, champion = { ["6652"] = 8652 } }')
            root.trackItemLevels = self.lua.table(myth=289, hero=276, champion=263)
        self.ns.ClassCodexTargets = root
        db = self.lua.globals().StatVerdictDB
        db.weightMode = mode
        db.gearLevel = level

    HERO_HEAD_LINK = ("item:271528:7961:240983:240894:::::90:104::0:7:"
                      "14334:7652:13696:13847:13692:13698:12854")

    def test_hero_level_swaps_the_track_in_our_tooltip(self) -> None:
        self.use_level("MEASURED", "hero")
        self.assertEqual(self.HERO_HEAD_LINK, self.panel.BuildRecommendedItemLink(self.guardian_head(), 104))
        # The game knows only the Hero-track link: our tooltip reads that one.
        self.game_knows(self.HERO_HEAD_LINK, GUARDIAN_HEAD_SOCKETED_TOOLTIP)
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertEqual(GUARDIAN_HEAD_KEPT + HEAD_RECOMMENDED, self.hover(card.rows[1]))
        self.assertIn("14334:7652", card.rows[1].itemLink)

    def test_champion_level_swaps_the_game_tooltip_link(self) -> None:
        self.use_level("MEASURED", "champion")
        self.use_game_tooltip()
        row = self.refresh(self.entry(item_id=1001, bonus_ids=[6652, 11]), spec_id=104).rows[1]
        row.scripts.OnEnter(row)
        self.assertIn(("SetHyperlink", "item:1001::::::::90:104::0:2:8652:11"), self.game_tooltip_calls())

    def test_hero_level_swaps_the_ranked_trinket_links(self) -> None:
        self.use_level("MEASURED", "hero")
        card = self.refresh_trinkets()
        card.rows[1].scripts.OnEnter(card.rows[1])
        self.assertIn(("SetHyperlink", "item:1003::::::::90::::1:7652"), self.game_tooltip_calls())

    def test_myth_guide_and_old_data_keep_the_items_as_listed(self) -> None:
        for mode, level, track_swap in (("MEASURED", "myth", True), ("GUIDE", "hero", True),
                                        ("GUIDE", "champion", True), ("MEASURED", "hero", False)):
            self.use_level(mode, level, track_swap)
            self.assertEqual(GUARDIAN_HEAD_LINK, self.panel.BuildRecommendedItemLink(self.guardian_head(), 104),
                             (mode, level))
            self.lua.globals().TOOLTIP_CALLS = self.lua.table()
            card = self.refresh_trinkets()
            card.rows[1].scripts.OnEnter(card.rows[1])
            self.assertIn(("SetHyperlink", "item:1003::::::::90::::1:6652"), self.game_tooltip_calls(),
                          (mode, level))
            self.mode = "bis"

    def test_owned_state_still_matches_by_item_id(self) -> None:
        self.use_level("MEASURED", "champion")
        g = self.lua.globals()
        g.GetInventoryItemLink = self.lua.eval(
            'function(unit, slot) if slot == 1 then return "item:271528::::::::90::::1:6652" end end')
        card = self.refresh(self.guardian_head(), spec_id=104)
        self.assertEqual(("You have this item", None), self.hover(card.rows[1])[-1])
        self.assertIn("1/1", card.summary.text)

    def test_owned_item_adds_a_dim_line(self) -> None:
        g = self.lua.globals()
        g.GetInventoryItemLink = self.lua.eval(
            'function(unit, slot) if slot == 1 then return "item:271528::::::::90" end end')
        card = self.refresh(self.guardian_head(), spec_id=104)
        lines = self.hover(card.rows[1])
        self.assertEqual(("You have this item", None), lines[-1])
        tip = self.panel.GetRecommendedTooltip()
        last = tip.shownLines[len(tip.shownLines)]
        self.assertEqual([0.55, 0.55, 0.55], [last.color[i] for i in (1, 2, 3)])

    def test_item_without_gems_or_enchant_has_no_block(self) -> None:
        card = self.refresh(self.entry(slot="Neck", item_id=1002, bonus_ids=[5]),
                            self.entry(slot="Neck", item_id=1002, gems=[], enchant={}))
        for index in (1, 2):
            self.assertNotIn(("Recommended", None), self.hover(card.rows[index]), index)

    def test_without_game_data_the_name_shows_and_the_rest_fills_in(self) -> None:
        g = self.lua.globals()
        card = self.refresh(self.guardian_head(), spec_id=104)
        lines = self.hover(card.rows[1])
        # Name, then Recommended with the enchant only: sockets unknown, so no gems yet.
        self.assertEqual(4, len(lines))
        self.assertIn("item:271528", lines[0][0])
        self.assertEqual([("Recommended", None), ("Enchant", None), ("Enchant Helm - Scroll", None)], lines[1:])
        self.assertTrue(g.REQUESTED[271528])
        self.game_knows(GUARDIAN_HEAD_LINK, GUARDIAN_HEAD_SOCKETED_TOOLTIP)
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 271528, True)
        tip = self.panel.GetRecommendedTooltip()
        shown = self.pairs_of(tip.shownLines)
        self.assertEqual(GUARDIAN_HEAD_KEPT + HEAD_RECOMMENDED, shown)

    def test_gem_and_enchant_names_fill_in_when_they_arrive(self) -> None:
        g = self.lua.globals()
        entry = self.entry(item_id=1001, gems=[777001], enchant={"id": 8017, "item_id": 777002})
        self.game_knows(self.panel.BuildRecommendedItemLink(entry, 0), ONE_SOCKET_RING_TOOLTIP)
        card = self.refresh(entry)
        lines = self.hover(card.rows[1])
        self.assertIn(("Gem #777001", None), lines)
        self.assertIn(("Enchant #8017", None), lines)
        self.assertTrue(g.REQUESTED[777001] and g.REQUESTED[777002])
        g.ITEM_NAMES[777001] = "Masterful Gem"
        g.ITEM_NAMES[777002] = "Enchant Helm - Scroll"
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 777001, True)
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 777002, True)
        shown = self.pairs_of(self.panel.GetRecommendedTooltip().shownLines)
        self.assertIn(("Masterful Gem", None), shown)
        self.assertIn(("Enchant Helm - Scroll", None), shown)

    def test_enchant_name_falls_back_to_spell_then_id(self) -> None:
        self.lua.globals().SPELL_NAMES[1236001] = "Radiant Mastery"
        card = self.refresh(
            self.entry(slot="Finger 1", item_id=1001, enchant={"id": 8017, "spell_id": 1236001}),
            self.entry(slot="Main Hand", item_id=1003, enchant={"id": 3368}),
        )
        self.assertIn(("Radiant Mastery", None), self.hover(card.rows[1]))
        self.assertIn(("Enchant #3368", None), self.hover(card.rows[2]))

    def test_pvp_enchant_id_is_the_scroll_item(self) -> None:
        # PvP data: {id = <enchant scroll item id>} with no item_id / spell_id.
        g = self.lua.globals()
        card = self.refresh(self.entry(slot="Chest", item_id=1001, enchant={"id": 243981}))
        self.assertIn(("Enchant #243981", None), self.hover(card.rows[1]))  # not loaded yet
        self.assertTrue(g.REQUESTED[243981])
        g.ITEM_NAMES[243981] = "Enchant Chest - Crystalline Radiance"
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 243981, True)
        self.assertIn(("Enchant Chest - Crystalline Radiance", None),
                      self.pairs_of(self.panel.GetRecommendedTooltip().shownLines))

    def test_real_enchant_id_is_never_read_as_an_item(self) -> None:
        # 7961 is an enchant id here; an unrelated item with that number must not show.
        g = self.lua.globals()
        g.ITEM_NAMES[7961] = "Phantom Blade"
        card = self.refresh(self.entry(item_id=1001, enchant={"id": 7961, "item_id": 777002}))
        self.assertIn(("Enchant #7961", None), self.hover(card.rows[1]))

    def test_ranked_trinkets_keep_the_game_tooltip(self) -> None:
        self.refresh(self.guardian_head())
        card = self.refresh_trinkets()
        card.rows[1].scripts.OnEnter(card.rows[1])
        calls = self.lua.globals().TOOLTIP_CALLS
        self.assertEqual([
            ("SetOwner", "ANCHOR_RIGHT"),
            ("SetHyperlink", "item:1003::::::::90::::1:6652"),
            ("Show",),
        ], [tuple(calls[i][j] for j in range(1, len(calls[i]) + 1)) for i in range(1, len(calls) + 1)])
        tip = self.panel.GetRecommendedTooltip()
        self.assertTrue(tip is None or not tip._visible)

    # --- guide gems: one unique primary gem, a secondary gem everywhere else ----------

    def gem_block(self, lines):
        """The names under the "Gems" heading of a shown tooltip (empty without one)."""
        lefts = [left for left, _ in lines]
        if "Gems" not in lefts:
            return []
        out = []
        for left in lefts[lefts.index("Gems") + 1:]:
            if left in ("Enchant", "You have this item"):
                break
            out.append(left)
        return out

    def socketed_entry(self, slot, item_id, sockets, known=True, **item):
        entry = self.entry(slot=slot, item_id=item_id, **item)
        if known:
            self.game_knows(self.panel.BuildRecommendedItemLink(entry, 0),
                            socketed_item_tooltip(f"Item {item_id}", sockets))
        return entry

    def test_unique_primary_gem_only_on_the_first_socketed_slot(self) -> None:
        card = self.refresh(
            self.socketed_entry("Head", 1001, 0),
            self.socketed_entry("Neck", 1002, 2),
            self.socketed_entry("Finger 1", 1003, 1),
            self.socketed_entry("Wrist", 1004, 3),
            gems=GUIDE_GEMS,
        )
        self.assertEqual([], self.gem_block(self.hover(card.rows[1])))  # no sockets: no Gems part
        self.assertEqual(["Indecipherable Eversong Diamond", "Quick Gem"], self.gem_block(self.hover(card.rows[2])))
        self.assertEqual(["Quick Gem"], self.gem_block(self.hover(card.rows[3])))
        self.assertEqual(["Quick Gem x3"], self.gem_block(self.hover(card.rows[4])))

    def test_primary_slot_counts_the_other_sockets_as_secondary(self) -> None:
        card = self.refresh(self.socketed_entry("Head", 1001, 3), self.socketed_entry("Neck", 1002, 2),
                            gems=GUIDE_GEMS)
        self.assertEqual(["Indecipherable Eversong Diamond", "Quick Gem x2"],
                         self.gem_block(self.hover(card.rows[1])))
        self.assertEqual(["Quick Gem x2"], self.gem_block(self.hover(card.rows[2])))

    def test_gem_block_keeps_its_look(self) -> None:
        g = self.lua.globals()
        g.GetItemQualityColor = self.lua.eval(
            "function(q) if q == 4 then return 0.64, 0.21, 0.93, 'ffa335ee' end return 1, 1, 1, 'ffffffff' end")
        card = self.refresh(self.socketed_entry("Neck", 1002, 2, enchant={"id": 8017, "item_id": 243951}),
                            gems=GUIDE_GEMS)
        self.hover(card.rows[1])
        block = {line.left: line for line in self.shown()}
        self.assertEqual([0.55, 0.55, 0.55], [block["Gems"].color[i] for i in (1, 2, 3)])
        for name in ("Indecipherable Eversong Diamond", "Quick Gem"):
            self.assertTrue(block[name].indent and block[name].wrap, name)
            self.assertEqual([0.64, 0.21, 0.93], [block[name].color[i] for i in (1, 2, 3)], name)
        self.assertGreater(block["Enchant"].gap, 0)
        self.assertIn("Enchant Helm - Scroll", block)

    def test_no_primary_anywhere_until_earlier_slots_are_known(self) -> None:
        g = self.lua.globals()
        head = self.socketed_entry("Head", 1001, 0, known=False)
        card = self.refresh(head, self.socketed_entry("Neck", 1002, 2), gems=GUIDE_GEMS)
        # The head's sockets are unknown: the neck might not be the first socketed slot.
        self.assertEqual(["Quick Gem x2"], self.gem_block(self.hover(card.rows[2])))
        self.assertTrue(g.REQUESTED[1001])
        # The head arrives with no sockets: the neck is the first socketed slot after all.
        self.game_knows(self.panel.BuildRecommendedItemLink(head, 0), socketed_item_tooltip("Item 1001", 0))
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 1001, True)
        self.assertEqual(["Indecipherable Eversong Diamond", "Quick Gem"],
                         self.gem_block(self.pairs_of(self.panel.GetRecommendedTooltip().shownLines)))

    def test_primary_moves_to_an_earlier_slot_once_it_is_known(self) -> None:
        head = self.socketed_entry("Head", 1001, 0, known=False)
        card = self.refresh(head, self.socketed_entry("Neck", 1002, 1), gems=GUIDE_GEMS)
        self.assertEqual(["Quick Gem"], self.gem_block(self.hover(card.rows[2])))
        self.game_knows(self.panel.BuildRecommendedItemLink(head, 0), socketed_item_tooltip("Item 1001", 1))
        self.item_events.scripts.OnEvent(self.item_events, "GET_ITEM_INFO_RECEIVED", 1001, True)
        self.assertEqual(["Quick Gem"], self.gem_block(self.pairs_of(self.panel.GetRecommendedTooltip().shownLines)))
        self.assertEqual(["Indecipherable Eversong Diamond"], self.gem_block(self.hover(card.rows[1])))

    def test_only_a_primary_gem_in_the_data(self) -> None:
        card = self.refresh(self.socketed_entry("Head", 1001, 2), self.socketed_entry("Neck", 1002, 1),
                            gems={"primary": PRIMARY_GEM})
        self.assertEqual(["Indecipherable Eversong Diamond"], self.gem_block(self.hover(card.rows[1])))
        self.assertNotIn(("Gems", None), self.hover(card.rows[2]))

    def test_only_a_secondary_gem_in_the_data(self) -> None:
        card = self.refresh(self.socketed_entry("Head", 1001, 2), self.socketed_entry("Neck", 1002, 1),
                            gems={"secondary": SECONDARY_GEM})
        self.assertEqual(["Quick Gem x2"], self.gem_block(self.hover(card.rows[1])))
        self.assertEqual(["Quick Gem"], self.gem_block(self.hover(card.rows[2])))

    def test_unknown_sockets_of_the_hovered_item_show_no_gems(self) -> None:
        card = self.refresh(self.socketed_entry("Head", 1001, 2, known=False), gems=GUIDE_GEMS)
        self.assertNotIn(("Gems", None), self.hover(card.rows[1]))

    def test_old_gem_ids_are_ignored_once_the_guide_gems_exist(self) -> None:
        entry = self.entry(slot="Neck", item_id=1002, gems=[240983, 240983])
        link = self.panel.BuildRecommendedItemLink(entry, 0, True)
        self.assertEqual("item:1002::::::::90:0::0:0", link)  # no per-slot gems in the link
        self.game_knows(link, socketed_item_tooltip("Item 1002", 2))
        card = self.refresh(entry, gems=GUIDE_GEMS)
        lines = self.hover(card.rows[1])
        self.assertEqual(["Indecipherable Eversong Diamond", "Quick Gem"], self.gem_block(lines))
        self.assertNotIn(("Flawless Gem", None), lines)

    def test_old_data_without_guide_gems_keeps_the_per_slot_gems(self) -> None:
        entry = self.entry(slot="Neck", item_id=1002, gems=[240983, 240894])
        self.game_knows(self.panel.BuildRecommendedItemLink(entry, 0), socketed_item_tooltip("Item 1002", 2))
        card = self.refresh(self.entry(slot="Head", item_id=1001, gems=[240983]), entry)
        self.assertEqual(["Flawless Gem", "Quick Gem"], self.gem_block(self.hover(card.rows[2])))

    def plan(self, gems, counts, index):
        """The pure gem plan for slot `index` with stub socket counts (None = unknown)."""
        slots = self.slots(*[self.entry(slot=f"S{i}", item_id=5000 + i) for i in range(len(counts))])
        count_of = self.lua.eval("function(counts) return function(entry) return counts[entry.item.item_id] end end")(
            self.lua.table_from({5000 + i: c for i, c in enumerate(counts) if c is not None}))
        plan = self.panel.SlotGemPlan(self.lua.table(**gems), slots, index, count_of)
        return [(plan[i].id, plan[i].count) for i in range(1, len(plan) + 1)]

    def test_slot_gem_plan_is_pure_and_gives_the_primary_once(self) -> None:
        counts = [0, 2, 1, None, 3]
        self.assertEqual([], self.plan(GUIDE_GEMS, counts, 1))
        self.assertEqual([(PRIMARY_GEM, 1), (SECONDARY_GEM, 1)], self.plan(GUIDE_GEMS, counts, 2))
        self.assertEqual([(SECONDARY_GEM, 1)], self.plan(GUIDE_GEMS, counts, 3))
        self.assertEqual([], self.plan(GUIDE_GEMS, counts, 4))  # own count unknown
        self.assertEqual([(SECONDARY_GEM, 3)], self.plan(GUIDE_GEMS, counts, 5))
        # An unknown earlier slot means no primary yet, never a possibly wrong one.
        self.assertEqual([(SECONDARY_GEM, 2)], self.plan(GUIDE_GEMS, [None, 2], 2))
        self.assertEqual([], self.plan({"primary": PRIMARY_GEM}, [None, 2], 2))

    # --- compact rows and geometry ---------------------------------------------------

    def test_rows_show_only_slot_and_coloured_name(self) -> None:
        card = self.refresh(self.entry(item_id=1001, gems=[240983], enchant={"id": 8017, "item_id": 243951}))
        row = card.rows[1]
        self.assertEqual("Head", row.slot.text)
        self.assertEqual("|cffdbdbdbCrown of Tests|r", row.name.text)
        self.assertIsNone(row.details)

    def test_card_width_does_not_grow_with_gems_or_enchant(self) -> None:
        plain = self.refresh(self.entry(item_id=1001)).preferredWidth
        full = self.refresh(self.entry(item_id=1001, gems=[240983, 240894],
                                       enchant={"id": 8017, "item_id": 243951})).preferredWidth
        self.assertEqual(plain, full)
        # status 16 + gap 2 + slot (min 36) + 16 + owned (min 12) + 16 + name + 24, at least 240.
        name_width = len(self.frame.bisProgressCard.rows[1].name.text) * 6
        self.assertEqual(max(240, 16 + 2 + 36 + 16 + 12 + 16 + name_width + 24), full)

    def row_geometry(self, card):
        points = card.contentHost.points
        host_y = [points[i][5] for i in range(1, len(points) + 1) if points[i][1] == "TOPLEFT"][-1]
        rows = []
        for index in range(1, 17):
            row = card.rows[index]
            y = row.points[len(row.points)][5]
            rows.append((-host_y - y, -host_y - y + row._height))  # top, bottom from card top
        return rows

    def full_bis(self, card_height):
        entries = [self.entry(slot=slot, item_id=1001) for slot in BIS_SLOTS]
        card = self.refresh(*entries)
        card.GetHeight = self.lua.eval(f"function() return {card_height} end")
        return self.refresh(*entries)

    def test_sixteen_rows_never_overlap_the_progress_footer(self) -> None:
        for height in (300, 360, 420):
            card = self.full_bis(height)
            self.assertEqual("BiS Progress: 0/16", card.summary.text)
            footer_top = height - 12 - 12  # anchored 12 above the bottom, 12 high
            rows = self.row_geometry(card)
            self.assertLessEqual(rows[-1][1], footer_top, height)
            for upper, lower in zip(rows, rows[1:]):
                self.assertLessEqual(upper[1], lower[0], height)  # rows do not overlap each other

    def test_rows_keep_their_spacing_when_they_fit(self) -> None:
        rows = self.row_geometry(self.full_bis(500))
        self.assertEqual([50 + 21 * i for i in range(16)], [top for top, _ in rows])
        self.assertEqual({20}, {bottom - top for top, bottom in rows})

    def trinkets_at(self, card_height, count):
        self.mode = "bis"
        self.refresh(self.entry(item_id=1001))
        self.frame.bisProgressCard.GetHeight = self.lua.eval(f"function() return {card_height} end")
        return self.refresh_trinkets(count=count)

    def test_ranked_trinkets_rows_keep_the_old_spacing_when_they_fit(self) -> None:
        for height, count in ((360, 10), (500, 14)):
            card = self.trinkets_at(height, count)
            rows = self.row_geometry(card)
            self.assertEqual([50 + 21 * i for i in range(16)], [top for top, _ in rows], (height, count))
            self.assertEqual({20}, {bottom - top for top, bottom in rows})
            self.assertEqual("|cffff8000#1 S|r", card.rows[1].slot.text)

    def test_fourteen_ranked_trinkets_never_overlap_the_footer(self) -> None:
        for height in (300, 360, 420):
            card = self.trinkets_at(height, 14)
            self.assertEqual("Trinkets: 14 ranked · Owned 0/14", card.summary.text)
            footer_top = height - 12 - 12
            rows = self.row_geometry(card)[:14]
            self.assertLessEqual(rows[-1][1], footer_top, height)
            for upper, lower in zip(rows, rows[1:]):
                self.assertLessEqual(upper[1], lower[0], height)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class BisTooltipFeatureToggleTests(unittest.TestCase):
    """Features → Best in Slot: our tooltip, its gems/enchants block (a child of
    it), and the game tooltip fallback. Unset saved values count as on."""

    OPTIONS = [
        ("showBisTooltip", "Best in Slot tooltip"),
        ("showBisGemsEnchants", "Gems and enchants"),
        ("bisUseGameTooltip", "Use the game tooltip instead"),
    ]

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        self.ns.GetRightPanelMode = lambda: "options"
        load_addon_file(self.lua, self.ns, "UI/SV_OptionsDrawerPanel.lua")
        self.frame = self.lua.eval("CreateFrame")()
        self.lua.globals().StatVerdictDB = self.lua.table()

    def check(self, key="showBisGemsEnchants"):
        self.ns.StatVerdictOptionsDrawerPanel.Apply(self.frame)
        return self.frame.optionsDrawerCard.bagIndicatorChecks[key]

    def click(self, key, checked):
        check = self.check(key)
        check.GetChecked = lambda self: checked
        check.scripts.OnClick(check)
        return self.check(key)

    def db(self):
        return self.lua.globals().StatVerdictDB

    def active(self, check):
        return check._enabled is not False and check._alpha == 1

    def test_three_options_in_order_under_the_best_in_slot_title(self) -> None:
        checks = [self.check(key) for key, _ in self.OPTIONS]
        self.assertEqual([label for _, label in self.OPTIONS], [c.Text.text for c in checks])
        self.assertEqual("Best in Slot", self.frame.optionsDrawerCard.bisTooltipTitle.text)
        points = [c.points[len(c.points)] for c in checks]
        xs, ys = [p[4] for p in points], [p[5] for p in points]
        self.assertEqual([0, -24, -48], ys)  # same step as the Bag Markers rows
        self.assertGreater(xs[1], xs[0])  # gems and enchants sits under the tooltip option
        self.assertEqual(xs[0], xs[2])

    def test_block_fits_all_three_rows(self) -> None:
        self.check()
        card = self.frame.optionsDrawerCard
        self.assertEqual(72, card.bisTooltipChecksBlock._height)
        self.assertEqual(24 * 2, card.bagChecksBlock._height)

    def states(self):
        """(checked, active) for options 1, 2, 3."""
        return [(bool(c.checked), self.active(c)) for c in (self.check(k) for k, _ in self.OPTIONS)]

    def test_defaults_ours_on_gems_on_game_tooltip_off(self) -> None:
        self.assertEqual([(True, True), (True, True), (False, True)], self.states())

    def test_defaults_without_saved_settings(self) -> None:
        self.lua.globals().StatVerdictDB = None
        self.assertEqual([(True, True), (True, True), (False, True)], self.states())

    def test_our_tooltip_and_gems_save_their_choice(self) -> None:
        for key in ("showBisGemsEnchants", "showBisTooltip"):
            self.assertFalse(self.click(key, False).checked, key)
            self.assertIs(False, self.db()[key], key)
            self.assertTrue(self.click(key, True).checked, key)
            self.assertIs(True, self.db()[key], key)

    def test_game_tooltip_saves_its_choice(self) -> None:
        self.assertTrue(self.click("bisUseGameTooltip", True).checked)
        self.assertIs(True, self.db().bisUseGameTooltip)
        self.assertFalse(self.click("bisUseGameTooltip", False).checked)
        self.assertIs(False, self.db().bisUseGameTooltip)

    def test_old_gems_and_enchants_choice_is_kept(self) -> None:
        self.db().showBisGemsEnchants = False
        self.assertEqual([(True, True), (False, True), (False, True)], self.states())

    def test_both_tooltip_options_are_always_clickable_and_white(self) -> None:
        for ours, game in ((None, None), (False, None), (False, True), (False, False), (True, False)):
            self.db().showBisTooltip = ours
            self.db().bisUseGameTooltip = game
            for key in ("showBisTooltip", "bisUseGameTooltip"):
                check = self.check(key)
                self.assertTrue(self.active(check), (key, ours, game))
                self.assertEqual(1, check._alpha, (key, ours, game))

    def test_ticking_the_game_tooltip_turns_ours_off(self) -> None:
        self.click("bisUseGameTooltip", True)
        self.assertEqual([(False, True), (True, False), (True, True)], self.states())
        self.assertIs(False, self.db().showBisTooltip)
        self.assertIs(True, self.db().bisUseGameTooltip)

    def test_ticking_ours_turns_the_game_tooltip_off(self) -> None:
        self.click("bisUseGameTooltip", True)
        self.click("showBisTooltip", True)
        self.assertEqual([(True, True), (True, True), (False, True)], self.states())
        self.assertIs(True, self.db().showBisTooltip)
        self.assertIs(False, self.db().bisUseGameTooltip)

    def test_unticking_the_active_one_leaves_both_off(self) -> None:
        self.click("showBisTooltip", False)
        self.assertEqual([(False, True), (True, False), (False, True)], self.states())
        self.click("bisUseGameTooltip", True)
        self.click("bisUseGameTooltip", False)
        self.assertEqual([(False, True), (True, False), (False, True)], self.states())
        self.assertIs(False, self.db().showBisTooltip)
        self.assertIs(False, self.db().bisUseGameTooltip)

    def test_gems_is_locked_and_keeps_its_value_while_ours_is_off(self) -> None:
        self.db().showBisGemsEnchants = False
        for other in (("showBisTooltip", False), ("bisUseGameTooltip", True)):
            self.db().showBisTooltip = None
            self.db().bisUseGameTooltip = None
            self.click(*other)
            gems = self.check("showBisGemsEnchants")
            self.assertFalse(self.active(gems), other)
            self.assertLess(gems._alpha, 1, other)
            self.assertFalse(self.click("showBisGemsEnchants", True).checked, other)
            self.assertIs(False, self.db().showBisGemsEnchants, other)
        self.click("showBisTooltip", True)
        self.assertEqual((False, True), self.states()[1])
        self.assertTrue(self.click("showBisGemsEnchants", True).checked)

    def test_both_saved_on_our_tooltip_wins(self) -> None:
        self.db().bisUseGameTooltip = True
        self.assertEqual([(True, True), (True, True), (False, True)], self.states())

    def test_bag_marker_toggles_are_unchanged(self) -> None:
        self.click("showBisTooltip", False)
        card = self.frame.optionsDrawerCard
        self.assertEqual("Upgrade Arrow", card.bagIndicatorChecks["showUpgradeArrow"].Text.text)
        self.assertEqual("|cff00ff00MS|r / |cff00ff00OS|r Labels", card.bagIndicatorChecks["showMsOsLabels"].Text.text)
        self.assertEqual("Bag Markers", card.bagMarkersTitle.text)
        for key in ("showUpgradeArrow", "showMsOsLabels"):
            self.assertTrue(self.active(card.bagIndicatorChecks[key]), key)

    def test_manual_describes_the_three_options(self) -> None:
        source = (ADDON / "UI" / "SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        for _, label in self.OPTIONS:
            self.assertIn(label, source)
        self.assertIn("turns the other off", source)
        self.assertNotIn("untick one to pick the other", source)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class FeaturesDrawerGeometryTests(unittest.TestCase):
    """Features drawer: wider than before, equal left/right margins for every title,
    checkbox group and label, and the window grows with it (like the other drawers)."""

    WIDTH = 320
    MARGIN = 14
    CHECK = 22
    GAP = 5
    INDENT = 18
    CHAR_W = 6.5  # generous per-character width of the 11pt checkbox label font
    LABELS = {
        "showUpgradeArrow": "Upgrade Arrow",
        "showMsOsLabels": "MS / OS Labels",
        "showBisTooltip": "Best in Slot tooltip",
        "showBisGemsEnchants": "Gems and enchants",
        "bisUseGameTooltip": "Use the game tooltip instead",
    }

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        self.ns.GetRightPanelMode = lambda: "options"
        load_addon_file(self.lua, self.ns, "UI/SV_DashboardLayout.lua")
        load_addon_file(self.lua, self.ns, "UI/SV_OptionsDrawerPanel.lua")
        self.frame = self.lua.eval("CreateFrame")()
        self.lua.globals().StatVerdictDB = self.lua.table()
        self.panel = self.ns.StatVerdictOptionsDrawerPanel
        self.layout = self.ns.StatVerdictDashboardLayout
        self.panel.Apply(self.frame)
        self.card = self.frame.optionsDrawerCard
        # Real frames report the width they were given; re-apply so the window syncs to it.
        self.card.GetWidth = self.lua.eval("function(self) return rawget(self, '_width') end")
        self.panel.Apply(self.frame)

    @staticmethod
    def last_point(region):
        return region.points[len(region.points)]

    def test_drawer_is_wider_than_before(self) -> None:
        self.assertEqual(self.WIDTH, self.panel.GetPreferredWidth(self.frame))
        self.assertEqual(self.WIDTH, self.layout.GetRightPanelWidth(self.frame))
        self.assertEqual(self.WIDTH, self.card._width)

    def test_titles_and_groups_share_the_left_margin(self) -> None:
        for region in (self.card.title, self.card.bagMarkersTitle, self.card.bisTooltipTitle,
                       self.card.bagChecksBlock, self.card.bisTooltipChecksBlock):
            self.assertEqual(self.MARGIN, self.last_point(region)[4])

    def test_groups_keep_the_same_margin_on_the_right(self) -> None:
        for block in (self.card.bagChecksBlock, self.card.bisTooltipChecksBlock):
            left = self.last_point(block)[4]
            self.assertEqual(self.MARGIN, self.card._width - (left + block._width))

    def test_every_label_fits_with_the_right_margin(self) -> None:
        checks = self.card.bagIndicatorChecks
        for key, label in self.LABELS.items():
            check = checks[key]
            block = self.card.bisTooltipChecksBlock if key.startswith(("showBis", "bisUse")) \
                else self.card.bagChecksBlock
            indent = self.last_point(check)[4]
            self.assertEqual(self.INDENT if key == "showBisGemsEnchants" else 0, indent, key)
            label_left = self.last_point(block)[4] + indent + self.CHECK + self.GAP
            label_right = label_left + check.Text._width
            self.assertEqual(self.MARGIN, self.card._width - label_right, key)  # right padding
            self.assertGreaterEqual(check.Text._width, len(label) * self.CHAR_W, key)  # not cut off

    def test_longest_label_has_room_on_both_sides(self) -> None:
        longest = max(self.LABELS.values(), key=len)
        self.assertEqual("Use the game tooltip instead", longest)
        text_right = self.MARGIN + self.CHECK + self.GAP + len(longest) * self.CHAR_W
        self.assertGreaterEqual(self.card._width - text_right, 3 * self.MARGIN)

    def test_window_grows_with_the_drawer_and_keeps_its_edge(self) -> None:
        right_x = self.layout.GetRightPanelX(self.frame)
        edge = self.layout.GetRightEdgeInset()
        self.assertEqual(right_x, self.last_point(self.card)[4])
        self.assertEqual(right_x + self.WIDTH + edge, self.frame._width)
        self.assertGreaterEqual(self.frame._width - (right_x + self.card._width), 6)
        self.assertLessEqual(self.frame._width, 1120)  # no wider than the dashboard's base window width

    def test_other_drawers_keep_their_width(self) -> None:
        widths = {"SV_WeightsDrawerPanel.lua": 280, "SV_ManualDrawerPanel.lua": 300}
        for name, width in widths.items():
            source = (ADDON / "UI" / name).read_text(encoding="utf-8-sig")
            self.assertIn(f"local DRAWER_PREFERRED_WIDTH = {width}\n", source, name)


if __name__ == "__main__":
    unittest.main()


class NoDataSourceNamesShownTests(unittest.TestCase):
    """The addon never names where stat data comes from: no player-visible string
    literal may mention ClassCodex, Icy Veins or u.gg. Comments and snake_case saved
    keys (such as "generated_classcodex") are skipped."""

    FORBIDDEN = ("classcodex", "icy", "u.gg")
    # A string literal, or the start of a comment (the rest of the line is skipped).
    TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|' + r"'((?:[^'\\]|\\.)*)'|(--)")
    SAVED_KEY = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")

    def scanned_files(self):
        files = sorted((ADDON / "UI").glob("*.lua"))
        files += [ADDON / "Core" / "SV_WeightModes.lua", ADDON / "Core" / "SV_ProfileRepository.lua",
                  ADDON / "StatVerdict.lua"]
        return files

    def shown_strings_of(self, source):
        for number, line in enumerate(source.splitlines(), 1):
            for match in self.TOKEN.finditer(line):
                if match.group(3):
                    break
                text = match.group(1) if match.group(1) is not None else match.group(2)
                if not self.SAVED_KEY.match(text):
                    yield number, text

    def test_scan_skips_comments_and_saved_keys_only(self) -> None:
        source = 'x = "ClassCodex" -- "u.gg"\n-- "Icy Veins"\ny = { source = "generated_classcodex", t = \'Icy\' }\n'
        self.assertEqual([(1, "ClassCodex"), (3, "Icy")], list(self.shown_strings_of(source)))

    def test_no_player_visible_string_names_a_data_source(self) -> None:
        offenders = []
        for path in self.scanned_files():
            for number, text in self.shown_strings_of(path.read_text(encoding="utf-8-sig")):
                if any(word in text.lower() for word in self.FORBIDDEN):
                    offenders.append(f"{path.name}:{number}: {text}")
        self.assertEqual([], offenders)
