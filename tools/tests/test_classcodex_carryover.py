"""The weekly job keeps last week's part where this week's is missing or unusable."""
from __future__ import annotations

import copy
import unittest

from tools.classcodex_carryover import carry_over, carry_problem, format_report, part_problem

OLD_BUILD = "20261007113733-aaaaaaa-11111111"
NEW_BUILD = "20261014113733-bbbbbbb-22222222"


def make_context(seed: int = 1, goal: str = "RAID") -> dict:
    stats = lambda total: {"critical_strike": total, "haste": total / 2, "mastery": total / 3, "versatility": total / 4}
    context = {
        "targets": {
            "statTargets": {"stats": stats(1000 + seed)},
            "levels": {
                "hero": {"statTargets": {"stats": stats(900 + seed)}},
                "champion": {"statTargets": {"stats": stats(800 + seed)}},
            },
        },
        "bis": {"slots": [{"slot": f"S{i}", "item": {"item_id": seed * 100 + i}} for i in range(15)]},
        "trinkets": [{"item_id": 5000 + seed, "tier": "S"}],
        "priorityProfiles": [{"order": ["critical_strike", "haste", "mastery", "versatility"]}],
    }
    if goal == "PVP":
        del context["targets"]["levels"]
    return context


def make_doc(build: str, contexts: dict[tuple[str, str, str], dict]) -> dict:
    profiles: dict = {}
    for (spec, goal, hero), context in contexts.items():
        profile = profiles.setdefault(spec, {"specKey": spec, "classToken": "X", "primaryStat": "strength", "goals": {}})
        profile["goals"].setdefault(goal, {"heroTalents": {}})["heroTalents"][hero] = context
    return {"buildId": build, "profiles": profiles}


KEY = ("DEATHKNIGHT_BLOOD", "RAID", "sanlayn")


class PartCheckTests(unittest.TestCase):
    def test_a_good_context_has_no_problem(self) -> None:
        for goal in ("RAID", "PVP"):
            context = make_context(goal=goal)
            for part in ("bis", "trinkets", "priorityProfiles", "targets"):
                self.assertIsNone(part_problem(context, part, goal), (goal, part))

    def test_each_part_is_judged_on_its_own(self) -> None:
        context = make_context()
        context["bis"]["slots"] = context["bis"]["slots"][:5]
        context["trinkets"] = []
        context["priorityProfiles"][0]["order"] = ["haste"]
        del context["targets"]["levels"]["hero"]
        for part in ("bis", "trinkets", "priorityProfiles", "targets"):
            self.assertIsNotNone(part_problem(context, part, "RAID"), part)
        self.assertIsNone(part_problem(context, "targets", "PVP"))  # PvP has no levels


class CarryOverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old = make_doc(OLD_BUILD, {KEY: make_context(1)})

    def test_good_new_data_replaces_the_old_and_nothing_is_carried(self) -> None:
        new = make_doc(NEW_BUILD, {KEY: make_context(2)})
        merged, report = carry_over(new, self.old)
        self.assertEqual(new, merged)
        self.assertEqual([], report["carried"])
        self.assertIn("nothing needed", format_report(report))

    def test_only_the_broken_part_stays_as_it_was(self) -> None:
        broken = make_context(2)
        broken["priorityProfiles"] = []
        new = make_doc(NEW_BUILD, {KEY: broken})
        merged, report = carry_over(new, self.old)
        context = merged["profiles"][KEY[0]]["goals"][KEY[1]]["heroTalents"][KEY[2]]
        self.assertEqual(self.old["profiles"][KEY[0]]["goals"]["RAID"]["heroTalents"]["sanlayn"]["priorityProfiles"],
                         context["priorityProfiles"])
        self.assertEqual(make_context(2)["bis"], context["bis"])  # the valid parts are the new ones
        self.assertEqual({"priorityProfiles": OLD_BUILD}, context["carried"])
        self.assertEqual(1, report["carriedContexts"])
        self.assertIn("kept priorityProfiles of DEATHKNIGHT_BLOOD/RAID/sanlayn", format_report(report))
        self.assertNotIn("carried", new["profiles"][KEY[0]]["goals"]["RAID"]["heroTalents"]["sanlayn"])  # input untouched

    def test_a_context_missing_this_week_is_carried_whole(self) -> None:
        other = ("DEATHKNIGHT_BLOOD", "RAID", "deathbringer")
        old = make_doc(OLD_BUILD, {KEY: make_context(1), other: make_context(3)})
        new = make_doc(NEW_BUILD, {KEY: make_context(2)})
        merged, report = carry_over(new, old)
        carried = merged["profiles"][KEY[0]]["goals"]["RAID"]["heroTalents"]["deathbringer"]
        self.assertEqual(make_context(3)["bis"], carried["bis"])
        self.assertEqual(OLD_BUILD, carried["carried"]["bis"])
        self.assertEqual(1, report["carriedContexts"])

    def test_a_part_older_than_the_limit_is_not_carried_and_the_context_goes(self) -> None:
        old = make_doc("20260901113733-aaaaaaa-11111111", {KEY: make_context(1)})
        broken = make_context(2)
        broken["trinkets"] = []
        merged, report = carry_over(make_doc(NEW_BUILD, {KEY: broken}), old)
        self.assertEqual({}, merged["profiles"])
        self.assertIn("older than 30 days", format_report(report))

    def test_a_carried_part_keeps_the_build_it_really_came_from(self) -> None:
        first_broken = make_context(2)
        first_broken["trinkets"] = []
        week2, _ = carry_over(make_doc(NEW_BUILD, {KEY: first_broken}), self.old)
        second_broken = make_context(3)
        second_broken["trinkets"] = []
        week3, _ = carry_over(make_doc("20261021113733-ccccccc-33333333", {KEY: second_broken}), week2)
        context = week3["profiles"][KEY[0]]["goals"]["RAID"]["heroTalents"]["sanlayn"]
        self.assertEqual({"trinkets": OLD_BUILD}, context["carried"])
        week4, report = carry_over(make_doc("20261109113733-ddddddd-44444444", {KEY: second_broken}), week3)
        self.assertEqual({}, week4["profiles"])  # 33 days after the part's own build

    def test_nothing_to_carry_from_drops_a_broken_context(self) -> None:
        broken = make_context(2)
        broken["bis"]["slots"] = []
        merged, report = carry_over(make_doc(NEW_BUILD, {KEY: broken}), None)
        self.assertEqual(0, len(report["carried"]))
        merged, report = carry_over(make_doc(NEW_BUILD, {KEY: broken}), make_doc(OLD_BUILD, {}))
        self.assertEqual({}, merged["profiles"])
        self.assertEqual(1, len(report["dropped"]))

    def test_too_many_carried_contexts_is_a_problem(self) -> None:
        keys = [("S", "RAID", f"h{i}") for i in range(8)]
        old = make_doc(OLD_BUILD, {key: make_context(i) for i, key in enumerate(keys, 1)})
        new_contexts = {key: make_context(i) for i, key in enumerate(keys, 1)}
        for key in keys[:2]:
            new_contexts[key]["trinkets"] = []
        _, report = carry_over(make_doc(NEW_BUILD, copy.deepcopy(new_contexts)), old)
        self.assertEqual(2, report["carriedContexts"])
        self.assertIsNone(carry_problem(report))  # 2 of 8 = 25%, at the limit
        new_contexts[keys[2]]["trinkets"] = []
        _, report = carry_over(make_doc(NEW_BUILD, new_contexts), old)
        self.assertIn("3 of 8", carry_problem(report))


if __name__ == "__main__":
    unittest.main()
