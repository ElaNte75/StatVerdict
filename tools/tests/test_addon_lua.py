from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.addon_benchmarks import build_addon_data, render_lua
from tools.tests.addon_fixtures import make_bracket_profile, make_bracket_raw_database

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
    data = build_addon_data([make_bracket_raw_database(generated_at, profiles)])
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

    def test_default_level_is_mid(self) -> None:
        self.assertEqual("MID", self.ns.GetBenchmarkLevel())

    def test_set_level_is_saved_and_unknown_is_rejected(self) -> None:
        self.assertTrue(self.ns.SetBenchmarkLevel("LOW"))
        self.assertEqual("LOW", self.ns.GetBenchmarkLevel())
        self.assertEqual("LOW", self.lua.globals().StatVerdictDB.benchmarkLevel)
        self.assertFalse(self.ns.SetBenchmarkLevel("TOP_25"))
        self.assertEqual("LOW", self.ns.GetBenchmarkLevel())

    def test_garbage_saved_value_falls_back_to_default(self) -> None:
        self.lua.globals().StatVerdictDB.benchmarkLevel = "nonsense"
        self.assertEqual("MID", self.ns.GetBenchmarkLevel())

    def test_level_names_and_meaning_lines(self) -> None:
        # Top-to-bottom order is Tier 3 (highest) down to Tier 1 (lowest), like a leaderboard.
        levels = self.ns.GetBenchmarkLevels()
        self.assertEqual(["Tier 3", "Tier 2", "Tier 1"], [levels[i].label for i in (1, 2, 3)])
        self.assertEqual("Players with a highest key of 16 or higher", levels[1].meaning)

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
        self.assertTrue(self.ns.IsBenchmarkSampleSmall(small))  # right at the minimum
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
        self.assertEqual(" · Tier 2", mplus.progressSuffix)
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
        self.assertEqual(1140.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])  # default level is MID

    def test_level_choice_changes_the_targets(self) -> None:
        lua, ns = self.build_runtime(level="LOW")
        profile = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(1300.0, self.targets(profile)["ITEM_MOD_CRIT_RATING_SHORT"])

    def test_hero_tree_id_selects_its_priority_and_unknown_uses_spec_wide(self) -> None:
        lua, ns = self.build_runtime()  # default level MID
        # The fixture swaps HERO_31's crit/haste specifically for MID (see addon_fixtures.py),
        # so this also proves the addon is really reading MID's own hero-tree row, not LOW/HIGH's.
        hero = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=31))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", hero.secondaryOrder[1])
        self.assertEqual("ITEM_MOD_MASTERY_RATING_SHORT", hero.secondaryOrder[2])
        other = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=33))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", other.secondaryOrder[1])
        unknown = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua))
        self.assertEqual(["ITEM_MOD_CRIT_RATING_SHORT", "ITEM_MOD_HASTE_RATING_SHORT"],
                         [unknown.secondaryOrder[1], unknown.secondaryOrder[2]])
        mismatch = ns.ProfileRepository.BuildRuntimeProfile(self.context(lua, heroSubTreeID=99))
        self.assertEqual("ITEM_MOD_CRIT_RATING_SHORT", mismatch.secondaryOrder[1])

    def test_missing_level_shows_no_data_instead_of_another_level(self) -> None:
        profile = make_bracket_profile()
        profile["cohorts"]["LOW"]["status"] = "insufficient"
        lua, ns = self.build_runtime(level="LOW", profiles={"DEATHKNIGHT_BLOOD": profile})
        self.assertIsNone(ns.ProfileRepository.BuildRuntimeProfile(self.context(lua)))
        lua, ns = self.build_runtime(profiles={"DEATHKNIGHT_BLOOD": profile})  # default level MID: still ok
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
        self.assertEqual("StatVerdict live benchmarks · Tier 2", info.sourceName)
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
        # The High bracket's favourite helm (1500) differs from Low/Mid's (1000).
        lua, ns = self.build_runtime(level="HIGH")
        profile = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1500", profile).bonus)
        self.assertIsNone(ns.GetItemReferenceInfo("item:1000", profile))
        lua, ns = self.build_runtime()  # default level MID
        profile = lua.table(specKey="DEATHKNIGHT_BLOOD", goal="MYTHIC_PLUS")
        self.assertEqual(8, ns.GetItemReferenceInfo("item:1000", profile).bonus)
        self.assertIsNone(ns.GetItemReferenceInfo("item:1500", profile))


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
            "LOW": dict(sampleSize=100, minimumSample=25, confidence="high"),
            "MID": dict(sampleSize=100, minimumSample=25, confidence="high"),
            "HIGH": dict(sampleSize=100, minimumSample=25, confidence="high"),
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
        # Row order top-to-bottom is now Tier 3 (HIGH), Tier 2 (MID), Tier 1 (LOW) - a
        # leaderboard shape, highest tier on top.
        self.levels["LOW"]["confidence"] = "medium"
        card = self.card()
        orange, green = "|cffff8000", "|cff33ff59"
        self.assertEqual(green + "High confidence|r", card.levelRows[1].meaning.text)  # HIGH
        self.assertEqual(green + "High confidence|r", card.levelRows[2].meaning.text)  # MID
        self.assertEqual(orange + "Medium confidence|r", card.levelRows[3].meaning.text)  # LOW
        # The date is right-aligned on its own, the same way the hint is (per the user's request).
        self.assertEqual("2026-09-26", card.levelRows[1].date.text)
        self.assertEqual("2026-09-26", card.levelRows[3].date.text)

    def test_level_cards_fall_back_to_the_group_size_without_data(self) -> None:
        self.has_data = False
        card = self.card()
        self.assertEqual("Players with a highest key of 16 or higher", card.levelRows[1].meaning.text)  # HIGH
        self.assertEqual("", card.levelRows[1].date.text)  # no live data: nothing to date

    def test_description_follows_the_selected_level(self) -> None:
        card = self.card()
        self.assertEqual("Tier 2 benchmark", card.aboutTitle.text)  # default level is MID
        self.assertIn("between 10 and 15", card.about.text)
        card.levelRows[1].scripts.OnClick()  # HIGH, now on top
        self.assertEqual("Tier 3 benchmark", card.aboutTitle.text)
        self.assertIn("16 or higher", card.about.text)
        card.levelRows[3].scripts.OnClick()  # LOW, now on the bottom
        self.assertEqual("Tier 1 benchmark", card.aboutTitle.text)
        self.assertIn("9 or lower", card.about.text)

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
        self.levels["MID"] = dict(sampleSize=25, minimumSample=25, confidence="high")
        self.assertIn("Smaller sample", self.card().status.text)

    def test_clicking_a_level_row_saves_it_and_marks_it(self) -> None:
        card = self.card()
        self.assertEqual(["HIGH", "MID", "LOW"], [card.levelRows[i].key for i in (1, 2, 3)])
        self.assertTrue(card.levelRows[2].check.checked)  # MID is the default
        card.levelRows[3].scripts.OnClick()  # LOW, now on the bottom
        self.assertEqual("LOW", self.ns.GetBenchmarkLevel())
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
