from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.classcodex_targets_cli import render_lua as render_targets_lua
from tools.classcodex_weights_cli import render_lua as render_weights_lua
from tools.tests.addon_fixtures import make_classcodex_targets, make_classcodex_weights

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


def now_build_id(days_ago: int = 0) -> str:
    """A ClassCodex buildId: UTC yyyymmddhhmmss, then commit and hash parts."""
    stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y%m%d%H%M%S")
    return f"{stamp}-6702fd4-878715d1"


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AddonLuaSyntaxTests(unittest.TestCase):
    def test_every_toc_file_compiles(self) -> None:
        lua = new_runtime()
        check = lua.eval("function(src, name) local f, err = load(src, name) if not f then return err end return nil end")
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

    def test_benchmark_is_relevant_only_when_a_build_uses_mythic_plus(self) -> None:
        cases = [
            ("MYTHIC_PLUS", None, False, True),
            ("RAID", None, False, False),
            ("PVP", None, False, False),
            ("RAID", "MYTHIC_PLUS", True, True),
            ("RAID", "MYTHIC_PLUS", False, False),  # an Off Spec goal without a configured Off Spec does not count
            ("PVP", "RAID", True, False),
        ]
        for main, off, enabled, expected in cases:
            selection = self.lua.table(goalMode=main, secondaryGoalMode=off, secondaryEnabled=enabled)
            self.ns.GetSavedStatAuditSelection = lambda selection=selection: selection
            self.assertEqual(expected, self.ns.IsBenchmarkRelevant(), (main, off, enabled))

    def test_benchmark_is_relevant_when_selection_is_unavailable(self) -> None:
        self.assertTrue(self.ns.IsBenchmarkRelevant())

    def test_small_sample_warning(self) -> None:
        small = self.lua.table(sampleSize=25, minimumSample=25, confidence="high")
        self.assertTrue(self.ns.IsBenchmarkSampleSmall(small))  # Elite: only the minimum sample
        enough = self.lua.table(sampleSize=100, minimumSample=25, confidence="high")
        self.assertFalse(self.ns.IsBenchmarkSampleSmall(enough))
        unsure = self.lua.table(sampleSize=100, minimumSample=25, confidence="medium")
        self.assertTrue(self.ns.IsBenchmarkSampleSmall(unsure))
        self.assertTrue(self.ns.IsBenchmarkSampleSmall(None))

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
    def build_runtime(self, build_id: str | None = None, targets: dict | None = None, weights: dict | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        build_id = build_id or now_build_id()
        targets_path = Path(self.tmp.name) / "SV_ClassCodexTargets.lua"
        targets_path.write_text(render_targets_lua(targets or make_classcodex_targets(build_id)), encoding="utf-8")
        weights_path = Path(self.tmp.name) / "SV_ClassCodexWeights.lua"
        weights_path.write_text(render_weights_lua(weights or make_classcodex_weights(build_id)), encoding="utf-8")
        lua = new_runtime()
        ns = lua.table()
        lua.globals().StatVerdictDB = lua.table()
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
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", None, None))
        self.assertIsNone(resolve("DEATHKNIGHT_BLOOD", "MYTHIC_PLUS", "", 31))
        self.assertIsNone(resolve("MAGE_FIRE", "MYTHIC_PLUS", "Sunfury", None))

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
        context = self.context(lua)
        context.heroTalentName = None
        self.assertIsNone(build(context))
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
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        # ClassCodex priority is haste > crit > mastery > vers; SimC measured vers above mastery.
        self.assertEqual([SECONDARY["haste"], SECONDARY["crit"], SECONDARY["vers"], SECONDARY["mastery"]], self.order(profile))
        self.assertEqual(1.0, profile.secondaryWeights[SECONDARY["haste"]])
        self.assertEqual(0.5, profile.secondaryWeights[SECONDARY["mastery"]])
        rows = profile.auditTargets.rows
        self.assertEqual([SECONDARY["haste"], SECONDARY["crit"], SECONDARY["vers"], SECONDARY["mastery"]],
                         [rows[i].key for i in range(1, len(rows) + 1)])

    def test_hero_tree_without_weights_keeps_the_classcodex_priority(self) -> None:
        lua, ns = self.build_runtime()
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroTalentName="Deathbringer"))
        self.assertIsNone(profile.secondaryWeights)
        self.assertEqual([SECONDARY["crit"], SECONDARY["mastery"], SECONDARY["vers"], SECONDARY["haste"]], self.order(profile))

    def test_tied_or_missing_weights_fall_back_to_the_classcodex_priority(self) -> None:
        build_id = now_build_id()
        weights = make_classcodex_weights(build_id)
        weights["profiles"]["DEATHKNIGHT_BLOOD"]["goals"]["MYTHIC_PLUS"]["heroTalents"]["sanlayn"] = {
            "critical_strike": 1.0, "haste": 1.0, "versatility": 0.4, "mastery": "junk",
        }
        lua, ns = self.build_runtime(build_id=build_id, weights=weights)
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
        lua, ns = self.build_runtime(build_id=build_id, weights=weights)
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertIsNone(profile.secondaryWeights)
        self.assertEqual(SECONDARY["haste"], profile.secondaryOrder[1])


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

    def test_measured_weights_scale_from_the_top_rank_weight(self) -> None:
        # Raw: primary 4, crit 1.0*4 = 4, haste 0.5*4 = 2, mastery 0.4*4 = 1.6, vers 0.25*4 = 1,
        # item level 1.2 -> 13.8 raw points in the same 10 point budget.
        result = self.weights(self.profile({"crit": 1.0, "haste": 0.5, "mastery": 0.4, "vers": 0.25}))
        scale = 10 / 13.8
        self.assertAlmostEqual(4 * scale, result[SECONDARY["crit"]])
        self.assertAlmostEqual(2 * scale, result[SECONDARY["haste"]])
        self.assertAlmostEqual(1.6 * scale, result[SECONDARY["mastery"]])
        self.assertAlmostEqual(1 * scale, result[SECONDARY["vers"]])
        self.assertAlmostEqual(result[STRENGTH], result[SECONDARY["crit"]])

    def test_a_stat_without_a_usable_weight_uses_its_rank_weight(self) -> None:
        result = self.weights(self.profile({"crit": 1.0, "haste": 0.5, "mastery": 0, "vers": None}))
        # mastery rank 3 -> 2.00, vers rank 4 -> 1.00; total 4+4+2+2+1+1.2 = 14.2
        scale = 10 / 14.2
        self.assertAlmostEqual(2 * scale, result[SECONDARY["mastery"]])
        self.assertAlmostEqual(1 * scale, result[SECONDARY["vers"]])
        self.assertAlmostEqual(2 * scale, result[SECONDARY["haste"]])


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class PanelModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        load_addon_file(self.lua, self.ns, "Core/SV_Benchmark.lua")
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")

    def use_goal(self, goal: str) -> None:
        selection = self.lua.table(goalMode=goal)
        self.ns.GetSavedStatAuditSelection = lambda: selection

    def test_benchmark_drawer_closes_itself_when_mythic_plus_is_no_longer_selected(self) -> None:
        self.use_goal("MYTHIC_PLUS")
        self.ns.SetRightPanelMode("benchmark")
        self.assertEqual("benchmark", self.ns.GetRightPanelMode())
        self.use_goal("RAID")
        self.assertIsNone(self.ns.GetRightPanelMode())
        self.use_goal("MYTHIC_PLUS")
        self.assertIsNone(self.ns.GetRightPanelMode())  # it stays closed until the player opens it again

    def test_benchmark_cannot_be_opened_without_mythic_plus_and_other_panels_stay(self) -> None:
        self.use_goal("RAID")
        self.ns.SetRightPanelMode("manual")
        self.ns.SetRightPanelMode("benchmark")
        self.assertEqual("manual", self.ns.GetRightPanelMode())
        self.ns.ToggleRightPanelMode("benchmark")
        self.assertEqual("manual", self.ns.GetRightPanelMode())

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
class BenchmarkDrawerSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        self.lua.globals().StatVerdictDB = self.lua.table()
        for relative in ("Core/SV_Benchmark.lua", "UI/SV_RightPanelMode.lua", "UI/SV_BenchmarkDrawerPanel.lua"):
            load_addon_file(self.lua, self.ns, relative)
        self.frame = self.lua.eval("CreateFrame")()
        self.ns.GetStatAuditGoalMode = lambda: "MYTHIC_PLUS"
        self.ns.GetSavedStatAuditSelection = lambda: self.lua.table(goalMode="MYTHIC_PLUS")
        self.available = True
        self.levels = {
            "ELITE": dict(sampleSize=25, minimumSample=25, confidence="high"),
            "STANDARD": dict(sampleSize=100, minimumSample=25, confidence="high"),
            "BROAD": dict(sampleSize=200, minimumSample=25, confidence="high"),
        }
        self.has_data = True
        self.apply_data()
        self.ns.ProfileRepository = self.lua.table(
            GetDataProvenance=lambda goal: self.lua.table(available=self.available, scrape="2026-09-26")
        )
        self.ns.SetRightPanelMode("benchmark")

    def apply_data(self) -> None:
        """Publish the fake benchmark file and the active profile for the current self.levels."""
        levels = self.lua.table()
        for key, values in self.levels.items():
            levels[key] = self.lua.table(benchmark=self.lua.table(**values))
        specs = self.lua.table(SPEC=self.lua.table(levels=levels))
        self.ns.MythicPlusBenchmarks = self.lua.table(profiles=specs)
        selected = self.levels[self.ns.GetBenchmarkLevel()]
        generated = self.lua.table(benchmark=self.lua.table(**selected))
        profile = self.lua.table(specKey="SPEC", generatedContext=generated)
        context = self.lua.table(profile=profile) if self.has_data else self.lua.table()
        self.ns.GetActivePanelContext = lambda: context

    def card(self):
        self.apply_data()
        self.ns.StatVerdictBenchmarkDrawerPanel.Apply(self.frame)
        return self.frame.benchmarkDrawerCard

    def test_level_cards_show_confidence_and_update_date(self) -> None:
        self.levels["ELITE"]["confidence"] = "medium"
        card = self.card()
        # The date is secondary: dimmed and without the word "Updated" so the line stays short.
        orange, green, date = "|cffff8000", "|cff33ff59", " |cff8c8c8c· 2026-09-26|r"
        self.assertEqual(orange + "Medium confidence|r" + date, card.levelRows[1].meaning.text)
        self.assertEqual(green + "High confidence|r" + date, card.levelRows[2].meaning.text)
        self.assertEqual(green + "High confidence|r" + date, card.levelRows[3].meaning.text)
        self.assertLessEqual(len("High confidence · 2026-09-26"), 32)

    def test_level_cards_fall_back_to_the_group_size_without_data(self) -> None:
        self.has_data = False
        card = self.card()
        self.assertEqual("Gear of the top 25 players", card.levelRows[1].meaning.text)

    def test_description_follows_the_selected_level(self) -> None:
        card = self.card()
        self.assertEqual("Standard benchmark", card.aboutTitle.text)
        self.assertIn("top 100", card.about.text)
        card.levelRows[1].scripts.OnClick()
        self.assertEqual("Elite benchmark", card.aboutTitle.text)
        self.assertIn("top 25", card.about.text)
        card.levelRows[3].scripts.OnClick()
        self.assertEqual("Broad benchmark", card.aboutTitle.text)
        self.assertIn("top 200", card.about.text)

    def test_description_hangs_from_its_title_so_it_cannot_leave_the_card(self) -> None:
        card = self.card()
        self.assertEqual("TOPLEFT", card.about.points[1][1])
        self.assertTrue(self.lua.eval("rawequal")(card.aboutTitle, card.about.points[1][2]))
        for level in self.ns.GetBenchmarkLevels().values():
            self.assertLessEqual(len(level.about), 300, level.key)  # about seven lines in the drawer

    def test_description_lines_have_extra_spacing(self) -> None:
        card = self.card()
        self.assertGreaterEqual(card.about.spacing, 3)

    def test_no_current_data_block_any_more(self) -> None:
        card = self.card()
        self.assertIsNone(card.dataRows)
        self.assertIsNone(card.infoTitle)

    def test_status_is_empty_when_all_is_well(self) -> None:
        self.assertEqual("", self.card().status.text)

    def test_small_sample_shows_the_warning(self) -> None:
        self.levels["STANDARD"] = dict(sampleSize=25, minimumSample=25, confidence="high")
        self.assertIn("Smaller sample", self.card().status.text)

    def test_clicking_a_level_row_saves_it_and_marks_it(self) -> None:
        card = self.card()
        self.assertEqual(["ELITE", "STANDARD", "BROAD"], [card.levelRows[i].key for i in (1, 2, 3)])
        self.assertTrue(card.levelRows[2].check.checked)
        card.levelRows[3].scripts.OnClick()
        self.assertEqual("BROAD", self.ns.GetBenchmarkLevel())
        self.assertFalse(card.levelRows[2].check.checked)
        self.assertTrue(card.levelRows[3].check.checked)

    def test_build_that_is_not_mythic_plus_gets_an_explanation(self) -> None:
        self.ns.GetStatAuditGoalMode = lambda: "RAID"
        self.assertIn("not Mythic+", self.card().status.text)

    def test_out_of_date_data_says_so(self) -> None:
        self.has_data = False
        self.available = False
        self.assertIn("out of date", self.card().status.text)

    def test_missing_level_data_says_no_data(self) -> None:
        self.has_data = False
        self.assertIn("No data for this build", self.card().status.text)

    def test_card_padding_copies_the_features_drawer(self) -> None:
        pads = {"options.card.pad": self.lua.table(top=5, bottom=5, left=0, right=0)}
        zero = self.lua.table(top=0, bottom=0, left=0, right=0)
        self.ns.GetDevLayoutPadding = lambda key: pads.get(key, zero)
        pad = self.ns.StatVerdictBenchmarkDrawerPanel.GetCardPad()
        self.assertEqual((5, 5, 0, 0), (pad.top, pad.bottom, pad.left, pad.right))
        pads["benchmark.card.pad"] = self.lua.table(top=2, bottom=3, left=0, right=0)
        pad = self.ns.StatVerdictBenchmarkDrawerPanel.GetCardPad()
        self.assertEqual((2, 3), (pad.top, pad.bottom))


if __name__ == "__main__":
    unittest.main()
