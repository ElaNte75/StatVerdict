"""Odd characters and odd inputs must never raise: no spec, no hero talent, empty
gear, garbage links, junk saved variables. The addon answers nil / a fallback."""
from __future__ import annotations

import unittest

from tools.tests import test_addon_integration as integration
from tools.tests import test_addon_lua as core

LuaRuntime = core.LuaRuntime

# What the game's item API returns for an odd item: junk and non-finite stat values, an empty item.
ITEM_API_STUB = """
C_Item = setmetatable({}, {__index = function() return function() return nil end end})
GetItemInfo = function() return "n", "l", 4, "x", 0, "Armor", "Cloth", 1, "INVTYPE_HEAD" end
GetItemStats = function()
    return {ITEM_MOD_CRIT_RATING_SHORT = "abc", ITEM_MOD_STAMINA_SHORT = -5, [1] = 2, ITEM_MOD_HASTE_RATING_SHORT = 1 / 0}
end
GetDetailedItemLevelInfo = function() return nil end
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class OddCharacterRepositoryTests(unittest.TestCase):
    build_runtime = core.CoreProfileTests.build_runtime
    context = core.CoreProfileTests.context

    def setUp(self) -> None:
        self.lua, self.ns = self.build_runtime()
        self.repo = self.ns.ProfileRepository

    def profile(self, **extra):
        return self.repo.BuildRuntimeProfile(self.context(self.lua, **extra))

    def test_a_character_without_a_hero_talent_still_gets_a_profile(self) -> None:
        for name in (None, ""):
            profile = self.profile(heroTalentName=name)
            self.assertIsNotNone(profile, repr(name))
            self.assertTrue(profile.heroKeyGuessed, repr(name))
        profile = self.profile(heroTalentName=None, heroSubTreeID=-5)
        self.assertIsNotNone(profile)

    def test_odd_hero_talent_names_never_raise(self) -> None:
        # A name that matches no hero tree (a translated one, junk, a wrong type) gives no
        # profile rather than a guessed one (ResolveHeroKey: "no data rather than a guess");
        # the hero subtree id is what identifies it on non-English clients.
        for name in ("Ñandú ünï ☃ %s %d ( [", "x" * 5000, 42, True, self.lua.table()):
            self.profile(heroTalentName=name)

    def test_no_or_unknown_spec_gives_no_profile_not_an_error(self) -> None:
        lua = self.lua
        for context in (None, lua.table(), lua.table(goal="RAID"), lua.table(specID=99999),
                        self.context(lua, specKey="NOPE_NOPE"), self.context(lua, specKey=5)):
            self.assertIsNone(self.repo.BuildRuntimeProfile(context))

    def test_an_invalid_goal_falls_back_to_the_default_goal(self) -> None:
        lua = self.lua
        for goal in ("BOGUS", 42, lua.table()):
            self.assertIsNotNone(self.profile(goal=goal), repr(goal))

    def test_lookups_with_nothing_or_nonsense_answer_nil(self) -> None:
        lua, repo = self.lua, self.repo
        self.assertIsNone(repo.GetContext(None, None, None))
        self.assertIsNone(repo.GetContext(lua.table(), lua.table(), lua.table()))
        repo.ResolveHeroKey(None, None, None, None)
        repo.ResolveHeroKey("NOPE", "RAID", "x", 1)
        repo.GetProviderView("BOGUS")
        repo.GetProviderView(None)
        repo.RefreshProviderView(None)
        repo.GetDataProvenance(None)
        repo.GetDataProvenance("X")

    def test_bad_settings_are_refused_not_saved(self) -> None:
        repo, lua = self.repo, self.lua
        self.assertFalse(repo.SetStatTargetBin(None))
        self.assertFalse(repo.SetStatTargetBin(5))
        self.assertFalse(repo.SetStatTargetBin(lua.table()))
        self.assertEqual("auto", repo.GetStatTargetBin())

    def test_missing_or_garbage_saved_variables_use_the_defaults(self) -> None:
        for saved in ("'garbage'", "{weightMode = 5, gearLevel = {}, statTargetBin = 7}", "nil"):
            self.lua.execute(f"StatVerdictDB = {saved}")
            self.assertEqual("auto", self.repo.GetStatTargetBin(), saved)
            self.assertIsNotNone(self.profile(), saved)
        self.assertTrue(self.repo.SetStatTargetBin("top50"))  # recreates the table after nil


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class OddItemsAndProfilesTests(unittest.TestCase):
    """The scoring layer with the real addon loaded: nil / empty / junk profiles and item links."""

    @classmethod
    def setUpClass(cls) -> None:
        integration.WholeAddonWithRealDataTests.setUpClass()
        cls.lua = integration.WholeAddonWithRealDataTests.lua
        cls.ns = integration.WholeAddonWithRealDataTests.ns
        cls.lua.execute(ITEM_API_STUB)

    def test_no_api_raises_for_odd_profiles_and_links(self) -> None:
        lua, ns = self.lua, self.ns
        real = ns.ProfileRepository.BuildRuntimeProfile(
            lua.table(specKey="SHAMAN_ENHANCEMENT", goal="MYTHIC_PLUS", role="DAMAGER", specID=263))
        self.assertIsNotNone(real)
        profiles = {"nil": None, "empty": lua.table(), "real": real, "string": "x",
                    "no order": lua.table(id="X", primaryStat="ITEM_MOD_AGILITY_SHORT"),
                    "bad order": lua.table(secondaryOrder=lua.table(1, "a", None), primaryStat=5)}
        links = {"nil": None, "empty": "", "garbage": "not a link", "number": 12345, "table": lua.table(),
                 "unknown item": "|cff0070dd|Hitem:999999999::::::::::::::|h[Nope]|h|r"}
        problems = []
        for profile_name, profile in profiles.items():
            calls = {
                "GetDefaultStatWeight": lambda: ns.GetDefaultStatWeight(profile, "ITEM_MOD_CRIT_RATING_SHORT"),
                "GetDefaultStatWeight(nil stat)": lambda: ns.GetDefaultStatWeight(profile, None),
                "GetTrackedProfileStats": lambda: ns.GetTrackedProfileStats(profile),
                "LoadEvaluationProfile": lambda: ns.LoadEvaluationProfile(profile),
                "EquippedSet(nil)": lambda: ns.GetWeightedDeltaScoreForEquippedSet(None, None, profile, None),
            }
            for link_name, link in links.items():
                calls.update({
                    f"GetItemReferenceInfo[{link_name}]": lambda link=link: ns.GetItemReferenceInfo(link, profile),
                    f"GetItemReferenceBonus[{link_name}]": lambda link=link: ns.GetItemReferenceBonus(link, profile),
                    f"GetItemStatsForProfile[{link_name}]": lambda link=link: ns.GetItemStatsForProfile(link, profile, 1),
                    f"GetItemProfileScore[{link_name}]": lambda link=link: ns.GetItemProfileScore(link, profile, 1),
                    f"GetWeightedDeltaScore[{link_name}]": lambda link=link: ns.GetWeightedDeltaScore(link, link, profile, None),
                    f"GetDeltaRows[{link_name}]": lambda link=link: ns.GetDeltaRows(link, None, profile, 1),
                })
            for call_name, call in calls.items():
                try:
                    call()
                except Exception as error:  # noqa: BLE001 - any Lua error is the bug
                    problems.append(f"{call_name} with {profile_name} profile: {str(error).splitlines()[0]}")
        self.assertEqual([], problems)


if __name__ == "__main__":
    unittest.main()
