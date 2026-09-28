from __future__ import annotations

import unittest

from tools.classcodex_targets import GOAL_CONTEXT_KEY, select_context


class SelectContextTests(unittest.TestCase):
    def test_returns_the_exact_goal_context_when_present(self) -> None:
        nested = {"deathbringer": {"mplus": ["A"], "all": ["B"]}}
        result = select_context(nested, "deathbringer", GOAL_CONTEXT_KEY["MYTHIC_PLUS"])
        self.assertEqual(["A"], result)

    def test_falls_back_to_all_when_the_goal_context_is_missing(self) -> None:
        nested = {"deathbringer": {"all": ["B"]}}
        result = select_context(nested, "deathbringer", GOAL_CONTEXT_KEY["PVP"])
        self.assertEqual(["B"], result)

    def test_returns_none_when_neither_the_goal_context_nor_all_exists(self) -> None:
        nested = {"deathbringer": {"raid": ["C"]}}
        result = select_context(nested, "deathbringer", GOAL_CONTEXT_KEY["PVP"])
        self.assertIsNone(result)

    def test_returns_none_for_an_unknown_hero_talent_key(self) -> None:
        nested = {"deathbringer": {"all": ["B"]}}
        result = select_context(nested, "sanlayn", GOAL_CONTEXT_KEY["MYTHIC_PLUS"])
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
