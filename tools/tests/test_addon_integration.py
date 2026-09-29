"""Whole-addon check in a fake WoW: every .toc file loaded in order into one Lua
runtime together with the REAL generated ClassCodex files, then every
spec x goal x hero talent cell is pushed through the repository and profile
builder the way the game would. Runs against whatever data is committed, so a
bad data refresh fails CI before it can reach players.

Missing TARGETS for any spec/goal/hero cell is a failure. Missing WEIGHTS is
allowed (the addon falls back to rank weights) and only reported."""
from __future__ import annotations

import unittest

from tools.spec_catalog import SPECS
from tools.tests.test_addon_lua import FRAME_STUB, LuaRuntime, compile_lua_file, new_runtime, toc_lua_files

GOALS = ("MYTHIC_PLUS", "RAID", "PVP")

# Every other WoW global the addon touches while loading is a stub object:
# calling it (or any method on it) returns another stub. Removed again once
# the files are loaded, so the checks below see plain nil for WoW APIs.
WOW_GLOBALS_STUB = """
local function MakeStub()
    return setmetatable({}, {
        __index = function(t, key)
            if type(key) == "string" and key:match("^%u") then
                local child = MakeStub()
                rawset(t, key, child)
                return child
            end
            return nil
        end,
        __call = function() return MakeStub() end,
    })
end
setmetatable(_G, { __index = function(_, key)
    if type(key) == "string" and key:match("^%u") then return MakeStub() end
    return nil
end })
"""

# The data's own build time stands in for "now", so the 30-day freshness check
# tests the data, not the date the test happens to run on.
PIN_TIME_TO_BUILD = """
local buildId = ...
local realTime = os.time
local y, mo, d, h, mi, s = buildId:match("^(%d%d%d%d)(%d%d)(%d%d)(%d%d)(%d%d)(%d%d)")
local now = realTime({ year = tonumber(y), month = tonumber(mo), day = tonumber(d),
    hour = tonumber(h), min = tonumber(mi), sec = tonumber(s) }) + 3600
time = function(t) if t then return realTime(t) end return now end
"""


def lua_list(table) -> list:
    return [table[i] for i in range(1, len(table) + 1)] if table is not None else []


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WholeAddonWithRealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        lua = new_runtime()
        lua.execute(FRAME_STUB)
        lua.execute(WOW_GLOBALS_STUB)
        lua.globals().StatVerdictDB = lua.table()
        ns = lua.table()
        for path in toc_lua_files():
            compile_lua_file(lua, path)("StatVerdict", ns)
        lua.execute("setmetatable(_G, nil)")
        lua.eval("function(src, buildId) assert(loadstring or load)(src)(buildId) end")(
            PIN_TIME_TO_BUILD, ns.ClassCodexTargets.buildId)
        cls.lua, cls.ns = lua, ns

    def test_every_toc_file_loaded_and_exposes_the_repository(self) -> None:
        for name in ("ClassCodexTargets", "ClassCodexWeights", "ProfileRepository", "GetDefaultStatWeight",
                     "GetItemReferenceInfo", "LoadEvaluationProfile"):
            self.assertIsNotNone(self.ns[name], name)

    def test_spec_meta_matches_the_generated_data(self) -> None:
        """SV_SpecMeta must know every spec in the data, and each spec's hero-tree
        options must be exactly the hero trees the data has for that spec."""
        ns = self.ns
        targets = ns.ClassCodexTargets.profiles

        def normalize(name: str) -> str:
            return "".join(ch for ch in name.lower() if ch.isalnum())

        problems: list[str] = []
        for spec_key in targets.keys():
            if ns.GetStatVerdictSpecIDByKey(spec_key) is None:
                problems.append(f"{spec_key}: in the data but has no spec ID")

        spec_ids = [i for i in range(1, 5000) if ns.GetStatVerdictSpecKeyBySpecID(i) is not None]
        self.assertTrue(spec_ids)
        for spec_id in spec_ids:
            spec_key = ns.GetStatVerdictSpecKeyBySpecID(spec_id)
            if ns.GetStatVerdictRoleBySpecID(spec_id) is None:
                problems.append(f"{spec_key} ({spec_id}): no role")
            options = {normalize(name) for name in lua_list(ns.GetStatVerdictHeroOptionsBySpecID(spec_id))}
            profile = targets[spec_key]
            if profile is None:
                problems.append(f"{spec_key} ({spec_id}): spec ID but no data")
                continue
            data_heroes = {normalize(hero) for goal in profile.goals.keys()
                           for hero in profile.goals[goal].heroTalents.keys()}
            if options != data_heroes:
                problems.append(f"{spec_key} ({spec_id}): hero options {sorted(options)} != data {sorted(data_heroes)}")
        if problems:
            self.fail("\n  ".join(["SpecMeta out of date:"] + problems))

    def test_missing_hero_tree_name_uses_the_first_sorted_hero_key(self) -> None:
        ns, lua = self.ns, self.lua
        targets = ns.ClassCodexTargets.profiles
        for spec in SPECS:
            for goal in GOALS:
                expected = sorted(targets[spec.key].goals[goal].heroTalents.keys())[0]
                profile = ns.ProfileRepository.BuildRuntimeProfile(lua.table(
                    specKey=spec.key, goal=goal, specID=ns.GetStatVerdictSpecIDByKey(spec.key)))
                self.assertIsNotNone(profile, f"{spec.key} {goal}")
                self.assertEqual(expected, profile.heroKey, f"{spec.key} {goal}")
                self.assertTrue(profile.heroKeyGuessed, f"{spec.key} {goal}")
                unknown = ns.ProfileRepository.BuildRuntimeProfile(lua.table(
                    specKey=spec.key, goal=goal, heroTalentName="Not A Hero Tree"))
                self.assertIsNone(unknown, f"{spec.key} {goal}")

    def test_every_spec_goal_and_hero_talent_cell(self) -> None:
        ns, lua = self.ns, self.lua
        repo = ns.ProfileRepository
        targets = ns.ClassCodexTargets.profiles
        weights_root = ns.ClassCodexWeights.profiles if ns.ClassCodexWeights else None
        problems: list[str] = []
        rows: list[tuple[str, str, str, str, str]] = []
        no_weights: list[str] = []

        for spec in SPECS:
            spec_profile = targets[spec.key]
            if spec_profile is None:
                problems.append(f"{spec.key}: no targets for this spec at all")
                continue
            goals = spec_profile.goals
            hero_keys = sorted({hero for goal in GOALS if goals and goals[goal] and goals[goal].heroTalents
                                for hero in goals[goal].heroTalents.keys()})
            if not hero_keys:
                problems.append(f"{spec.key}: no hero talent has targets")
            for goal in GOALS:
                for hero in hero_keys:
                    cell = f"{spec.key} {goal} {hero}"
                    status = self.check_cell(spec, goal, hero, weights_root, problems)
                    rows.append((spec.key, goal, hero, status[0], status[1]))
                    if status[0] == "ok" and status[1] == "-":
                        no_weights.append(cell)

        # Weights for a cell without targets would be silently unused.
        if weights_root is not None:
            for spec_key in weights_root.keys():
                goals = weights_root[spec_key].goals
                for goal in goals.keys():
                    for hero in goals[goal].heroTalents.keys():
                        if repo.GetContext(spec_key, goal, hero) is None:
                            problems.append(f"{spec_key} {goal} {hero}: weights but no targets")

        if problems:
            table = "\n".join(f"  {s:<24} {g:<12} {h:<28} targets={t:<8} weights={w}" for s, g, h, t, w in rows)
            self.fail(f"{len(problems)} problem(s):\n  " + "\n  ".join(problems) + "\n\nCoverage:\n" + table)
        print(f"\n[classcodex coverage] {len(rows)} cells with targets; {len(no_weights)} use rank weights: "
              + ", ".join(no_weights))

    def check_cell(self, spec, goal, hero, weights_root, problems: list[str]) -> tuple[str, str]:
        ns, lua = self.ns, self.lua
        repo = ns.ProfileRepository
        cell = f"{spec.key} {goal} {hero}"
        context = repo.GetContext(spec.key, goal, hero)
        if context is None:
            problems.append(f"{cell}: no targets")
            return "MISSING", "?"
        result = repo.ValidateGeneratedContext(context, goal)
        valid, reason = result if isinstance(result, tuple) else (result, None)
        if not valid:
            problems.append(f"{cell}: invalid targets ({reason})")
            return "INVALID", "?"

        weights = repo.GetWeights(spec.key, goal, hero)
        weight_status = "-"
        if weights is not None:
            values = [weights[key] for key in ("critical_strike", "haste", "mastery", "versatility")]
            if any(not isinstance(v, (int, float)) or v <= 0 or v > 1.0 + 1e-9 for v in values) \
                    or abs(max(values) - 1.0) > 1e-6:
                problems.append(f"{cell}: weights not normalised to a best stat of 1.0: {values}")
                weight_status = "BAD"
            else:
                weight_status = "ok"

        profile = repo.BuildRuntimeProfile(lua.table(
            specKey=spec.key, goal=goal, heroTalentName=hero,
            specID=ns.GetStatVerdictSpecIDByKey(spec.key),
            role={"tank": "TANK", "healer": "HEALER"}.get(spec.role, "DAMAGER"),
        ))
        if profile is None:
            problems.append(f"{cell}: BuildRuntimeProfile returned nothing")
            return "NOPROFILE", weight_status
        if profile.invalidGeneratedContext:
            problems.append(f"{cell}: profile marked invalid ({profile.auditTargets.invalidReason})")
        if profile.heroKey != hero:
            problems.append(f"{cell}: profile built for hero {profile.heroKey}")
        if not lua_list(profile.secondaryOrder):
            problems.append(f"{cell}: empty secondaryOrder")
        if not lua_list(profile.auditTargets.rows):
            problems.append(f"{cell}: no audit target rows")
        if weight_status == "ok" and profile.secondaryWeights is None:
            problems.append(f"{cell}: measured weights not applied")
        for stat_key in lua_list(profile.secondaryOrder):
            weight = ns.GetDefaultStatWeight(profile, stat_key)
            if not isinstance(weight, (int, float)) or weight <= 0:
                problems.append(f"{cell}: no scoring weight for {stat_key}")
        return "ok", weight_status


if __name__ == "__main__":
    unittest.main()
