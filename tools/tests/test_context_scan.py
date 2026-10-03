"""One scan or window refresh builds the evaluation contexts once (the freeze when the window opened came from
rebuilding the profile about 250 times)."""
from __future__ import annotations

import unittest

from tools import item_check_verdict as v


class ContextScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lua, cls.ns = v.load_addon()
        cls.saved_character = dict(v.CHARACTER)  # shared with other tests: put back in tearDownClass
        v.CHARACTER.update(classFile="DEATHKNIGHT", className="Death Knight", specKey="DEATHKNIGHT_BLOOD", specID=250,
                           role="TANK", heroTalentName="Deathbringer")
        cls.lua.execute("""
        UnitClass = function() return "Death Knight", "DEATHKNIGHT", 6 end
        GetSpecialization = function() return 1 end
        GetSpecializationInfo = function() return 250, "Blood", "", 0, "TANK", "STRENGTH" end
        TEST_TIME = 1
        GetTime = function() return TEST_TIME end
        """)

    @classmethod
    def tearDownClass(cls) -> None:
        v.CHARACTER.clear()
        v.CHARACTER.update(cls.saved_character)

    def same(self, a, b) -> bool:
        """The very same Lua table (Python makes a new wrapper object every time one is read)."""
        return bool(self.lua.eval("rawequal")(a, b))

    def next_frame(self) -> None:
        self.lua.execute("TEST_TIME = TEST_TIME + 1")

    def setUp(self) -> None:
        # No scan left open by an earlier test, and a frame of its own.
        for _ in range(5):
            self.ns.EndContextScan()
        self.next_frame()

    def test_within_one_frame_the_context_is_built_once(self) -> None:
        first = self.ns.GetEvaluationContext()
        self.assertTrue(self.same(first, self.ns.GetEvaluationContext()))

    def test_the_next_frame_builds_again(self) -> None:
        first = self.ns.GetEvaluationContext()
        self.next_frame()
        self.assertFalse(self.same(first, self.ns.GetEvaluationContext()))

    def test_a_reset_drops_the_frame_cache(self) -> None:
        first = self.ns.GetEvaluationContext()
        self.ns.ResetContextScan()
        self.assertFalse(self.same(first, self.ns.GetEvaluationContext()))

    def test_inside_a_scan_the_context_is_built_once(self) -> None:
        self.ns.BeginContextScan()
        try:
            first = self.ns.GetEvaluationContext()
            self.assertTrue(self.same(first, self.ns.GetEvaluationContext()))
        finally:
            self.ns.EndContextScan()

    def test_a_new_scan_starts_empty(self) -> None:
        self.ns.BeginContextScan()
        first = self.ns.GetEvaluationContext()
        self.ns.EndContextScan()
        self.ns.BeginContextScan()
        try:
            self.assertFalse(self.same(first, self.ns.GetEvaluationContext()))
        finally:
            self.ns.EndContextScan()

    def test_scans_nest_and_the_outer_one_owns_the_cache(self) -> None:
        self.ns.BeginContextScan()
        outer = self.ns.GetEvaluationContext()
        self.ns.BeginContextScan()
        self.assertTrue(self.same(outer, self.ns.GetEvaluationContext()))
        self.ns.EndContextScan()
        self.assertTrue(self.same(outer, self.ns.GetEvaluationContext()))  # the inner end did not drop it
        self.ns.EndContextScan()
        self.assertFalse(self.same(outer, self.ns.GetEvaluationContext()))

    def test_a_changed_selection_drops_what_the_scan_built(self) -> None:
        self.ns.BeginContextScan()
        try:
            first = self.ns.GetEvaluationContext()
            self.ns.ResetContextScan()
            self.assertFalse(self.same(first, self.ns.GetEvaluationContext()))
        finally:
            self.ns.EndContextScan()

    def test_extra_ends_do_no_harm(self) -> None:
        self.ns.EndContextScan()
        self.ns.EndContextScan()
        self.ns.BeginContextScan()
        try:
            first = self.ns.GetEvaluationContext()
            self.assertTrue(self.same(first, self.ns.GetEvaluationContext()))
        finally:
            self.ns.EndContextScan()

    def test_the_tooltip_contexts_are_built_once_per_scan(self) -> None:
        """The real function the window and the bag scan call for every row: saving the selection at its end must
        not throw away what the scan has just built."""
        self.lua.globals().StatVerdictDB = self.lua.table()
        self.ns.BeginContextScan()
        try:
            first, _ = self.ns.GetTooltipEvaluationContexts()
            second, _ = self.ns.GetTooltipEvaluationContexts()
            self.assertIsNotNone(first)
            self.assertTrue(self.same(first, second))
        finally:
            self.ns.EndContextScan()

    def test_the_tooltip_contexts_are_built_once_per_frame(self) -> None:
        self.lua.globals().StatVerdictDB = self.lua.table()
        first, _ = self.ns.GetTooltipEvaluationContexts()
        second, _ = self.ns.GetTooltipEvaluationContexts()
        self.assertIsNotNone(first)
        self.assertTrue(self.same(first, second))

    def test_changing_the_selection_gives_new_contexts(self) -> None:
        self.lua.globals().StatVerdictDB = self.lua.table()
        first, _ = self.ns.GetTooltipEvaluationContexts()
        self.ns.GetSavedStatAuditSelection  # the saved selection exists
        self.ns.ResetContextScan()  # what saving a changed selection does
        second, _ = self.ns.GetTooltipEvaluationContexts()
        self.assertFalse(self.same(first, second))


if __name__ == "__main__":
    unittest.main()
