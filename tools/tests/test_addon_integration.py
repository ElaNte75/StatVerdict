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
WEIGHT_MODES = ("GUIDE", "MEASURED")
CANONICAL_STAT = {
    "ITEM_MOD_CRIT_RATING_SHORT": "critical_strike",
    "ITEM_MOD_HASTE_RATING_SHORT": "haste",
    "ITEM_MOD_MASTERY_RATING_SHORT": "mastery",
    "ITEM_MOD_VERSATILITY": "versatility",
}

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
local buildId, parseBuildTime = ...
local realTime = os.time
local now = assert(parseBuildTime(buildId)) + 3600
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
        lua.eval("function(src, buildId, parse) assert(loadstring(src))(buildId, parse) end")(
            PIN_TIME_TO_BUILD, ns.ClassCodexTargets.buildId, ns.ProfileRepository.ParseBuildTime)
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

    def test_hero_subtree_ids_cover_every_hero_key_in_the_data_exactly_once(self) -> None:
        ns, lua = self.ns, self.lua
        targets = ns.ClassCodexTargets.profiles
        data_keys = {hero for spec_key in targets.keys() for goal in targets[spec_key].goals.keys()
                     for hero in targets[spec_key].goals[goal].heroTalents.keys()}
        table = ns.GetStatVerdictHeroSubTreeIDs()
        mapped = [table[subtree_id] for subtree_id in table.keys()]
        self.assertEqual(len(mapped), len(set(mapped)), "a hero key is listed under two subtree IDs")
        self.assertEqual(sorted(data_keys), sorted(mapped))
        # Every spec/goal/hero cell resolves by ID alone, even with a translated name.
        for subtree_id in table.keys():
            hero = table[subtree_id]
            for spec_key in targets.keys():
                for goal in targets[spec_key].goals.keys():
                    if targets[spec_key].goals[goal].heroTalents[hero] is None:
                        continue
                    self.assertEqual(hero, ns.ProfileRepository.ResolveHeroKey(
                        spec_key, goal, "Nom traduit", subtree_id), f"{spec_key} {goal} {subtree_id}")

    def test_bis_items_and_ranked_trinkets_get_their_score_bonus_in_every_cell(self) -> None:
        """The user-visible promise: a best-in-slot item or a tiered trinket beats an
        otherwise equal item because the reference bonus is added to its score.
        Checked against every real cell (spec x goal x hero tree), through the same
        entry point the scoring uses (ns.GetItemReferenceInfo)."""
        ns, lua = self.ns, self.lua
        targets = ns.ClassCodexTargets.profiles
        tier_floor = {"S": 95, "A": 65, "B": 35, "C": 14, "D": 0}
        problems: list[str] = []
        checked_bis = checked_trinkets = 0
        for spec in SPECS:
            for goal in GOALS:
                heroes = targets[spec.key].goals[goal].heroTalents
                for hero in heroes.keys():
                    profile = lua.table(specKey=spec.key, goal=goal, heroKey=hero)
                    context = heroes[hero]
                    for entry in lua_list(context.bis.slots):
                        info = ns.GetItemReferenceInfo(f"item:{int(entry.item.item_id)}", profile)
                        checked_bis += 1
                        if info is None or info.bis is None or info.bonus < 8:
                            problems.append(f"{spec.key} {goal} {hero}: BiS {entry.slot} item {entry.item.item_id} has no bonus")
                    for entry in lua_list(context.trinkets):
                        info = ns.GetItemReferenceInfo(f"item:{int(entry.item_id)}", profile)
                        checked_trinkets += 1
                        floor = tier_floor[str(entry.tier).upper()]
                        if info is None or info.trinket is None or info.bonus < floor:
                            problems.append(f"{spec.key} {goal} {hero}: trinket {entry.item_id} tier {entry.tier} bonus too low")
        self.assertGreater(checked_bis, 2000)
        self.assertGreater(checked_trinkets, 500)
        if problems:
            self.fail("\n  ".join(problems[:20] + [f"({len(problems)} problems)"]))

    def test_bis_gems_and_enchants_have_the_shape_the_panel_reads(self) -> None:
        """The Best in Slot panel shows each slot's recommended gems and enchant:
        gem_ids is a list of positive item ids, enchant a table with a positive
        id and optional positive item_id / spell_id. Some slots must have one."""
        ns = self.ns
        targets = ns.ClassCodexTargets.profiles

        def positive_int(value) -> bool:
            return isinstance(value, (int, float)) and value > 0 and int(value) == value

        problems: list[str] = []
        with_enchant = with_gems = 0
        for spec_key in targets.keys():
            goals = targets[spec_key].goals
            for goal in goals.keys():
                heroes = goals[goal].heroTalents
                for hero in heroes.keys():
                    for entry in lua_list(heroes[hero].bis.slots):
                        where = f"{spec_key} {goal} {hero} {entry.slot}"
                        item = entry.item
                        if item.gem_ids is not None:
                            gems = lua_list(item.gem_ids)
                            if not gems or not all(positive_int(g) for g in gems):
                                problems.append(f"{where}: bad gem_ids {gems}")
                            with_gems += 1
                        enchant = item.enchant
                        if enchant is not None:
                            if not positive_int(enchant.id):
                                problems.append(f"{where}: enchant without a positive id")
                            for field in ("item_id", "spell_id"):
                                if enchant[field] is not None and not positive_int(enchant[field]):
                                    problems.append(f"{where}: bad enchant {field} {enchant[field]}")
                            with_enchant += 1
        self.assertGreater(with_enchant, 0)
        if problems:
            self.fail("\n  ".join(problems[:20] + [f"({len(problems)} problems)"]))
        print(f"\n[bis recommendations] {with_enchant} slots with an enchant, {with_gems} with gems")

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
        # guideTargets (ClassCodex / u.gg) may not be in the committed data yet:
        # absent means GUIDE shows our own targets; present is checked per row.
        self.cells_with_guide_targets: set[str] = set()

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
                    for mode in WEIGHT_MODES:
                        status = self.check_cell(spec, goal, hero, weights_root, problems, mode)
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
        print(f"\n[classcodex coverage] {len(rows)} cells with targets "
              f"({len(self.cells_with_guide_targets)} with ClassCodex top20 targets); "
              f"{len(no_weights)} use rank weights: " + ", ".join(no_weights))

    def test_guide_targets_check_catches_a_wrong_target(self) -> None:
        """Proves check_targets works on real data before the pipeline ships
        guideTargets: a fake top20 on one real cell passes for every mode, and a
        GUIDE profile showing our own targets instead is reported."""
        ns, lua = self.ns, self.lua
        spec = SPECS[0]
        hero = sorted(ns.ClassCodexTargets.profiles[spec.key].goals["MYTHIC_PLUS"].heroTalents.keys())[0]
        context = ns.ProfileRepository.GetContext(spec.key, "MYTHIC_PLUS", hero)
        own = context.targets.statTargets.stats
        saved = context.targets.guideTargets
        top20 = lua.table()
        for key in own.keys():
            top20[key] = own[key] * 1.1 + 50
        context.targets.guideTargets = lua.table(top20=top20)
        self.cells_with_guide_targets = set()
        try:
            for mode in WEIGHT_MODES:
                problems: list[str] = []
                self.check_targets(mode, context, self.build_profile(spec, "MYTHIC_PLUS", hero, mode), mode, problems)
                self.assertEqual([], problems, mode)
            wrong: list[str] = []
            self.check_targets("GUIDE", context, self.build_profile(spec, "MYTHIC_PLUS", hero, "MEASURED"),
                               "GUIDE", wrong)
            self.assertTrue(wrong)
        finally:
            context.targets.guideTargets = saved

    def build_profile(self, spec, goal, hero, mode: str):
        ns, lua = self.ns, self.lua
        db = lua.globals().StatVerdictDB
        saved = db.weightMode
        db.weightMode = mode
        try:
            return ns.ProfileRepository.BuildRuntimeProfile(lua.table(
                specKey=spec.key, goal=goal, heroTalentName=hero,
                specID=ns.GetStatVerdictSpecIDByKey(spec.key),
                role={"tank": "TANK", "healer": "HEALER"}.get(spec.role, "DAMAGER"),
            ))
        finally:
            db.weightMode = saved

    def check_cell(self, spec, goal, hero, weights_root, problems: list[str], mode: str) -> tuple[str, str]:
        ns, lua = self.ns, self.lua
        repo = ns.ProfileRepository
        cell = f"{spec.key} {goal} {hero} [{mode}]"
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

        profile = self.build_profile(spec, goal, hero, mode)
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
        if mode == "GUIDE":
            if profile.secondaryWeights is not None:
                problems.append(f"{cell}: guide mode must not use measured weights")
        elif weight_status == "ok" and profile.secondaryWeights is None:
            problems.append(f"{cell}: measured weights not applied")
        for stat_key in lua_list(profile.secondaryOrder):
            weight = ns.GetDefaultStatWeight(profile, stat_key)
            if not isinstance(weight, (int, float)) or weight <= 0:
                problems.append(f"{cell}: no scoring weight for {stat_key}")
        self.check_targets(cell, context, profile, mode, problems)
        return "ok", weight_status

    def check_targets(self, cell: str, context, profile, mode: str, problems: list[str]) -> None:
        """The audit rows show the mode's targets: GUIDE the ClassCodex (u.gg) top20
        targets when the data has them, MEASURED our own.
        A stat missing on one side uses the other side's target."""
        def positive(table, key):
            value = table[key] if table is not None else None
            return float(value) if isinstance(value, (int, float)) and value > 0 else None

        own = context.targets.statTargets.stats
        guide_root = context.targets.guideTargets
        guide = guide_root.top20 if guide_root is not None else None
        if guide is not None:
            self.cells_with_guide_targets.add(cell.rsplit(" [", 1)[0])
        for row in lua_list(profile.auditTargets.rows):
            canonical = CANONICAL_STAT.get(row.key)
            if canonical is None:
                continue
            own_value, guide_value = positive(own, canonical), positive(guide, canonical)
            target = float(row.target)
            expected = own_value if mode == "MEASURED" or guide_value is None else guide_value
            if expected is None or abs(target - expected) > 1e-6:
                problems.append(f"{cell}: {canonical} target {target}, expected {expected}")


if __name__ == "__main__":
    unittest.main()
