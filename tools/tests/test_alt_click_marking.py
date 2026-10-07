"""Alt-click marking: right click = Main Spec, left click = Off Spec; a piece is in one build at a time, and a second
click on the same build takes it out again."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import FRAME_STUB, LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AltClickMarkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        SlashCmdList = {}
        print = function() end
        MAIN = { profile = { name = "main" } }
        OFF = { profile = { name = "off" } }
        SAVED = { main = false, off = false }  -- is the piece in that build's loadout
        """)
        load_addon_file(lua, self.ns, "StatVerdict.lua")
        self.ns.GetTooltipEvaluationContexts = lua.eval("function() return MAIN, OFF end")
        self.ns.IsItemInEquipmentSnapshot = lua.eval("function(profile, link) return SAVED[profile.name] end")
        self.ns.ApproveItemIntoVirtualLoadout = lua.eval(
            "function(link, profile, slot) SAVED[profile.name] = true return true, 'ok' end")
        self.ns.RemoveItemFromVirtualLoadout = lua.eval(
            "function(link, profile) SAVED[profile.name] = false return true, 'removed' end")

    def click(self, secondary: bool) -> tuple[bool, bool]:
        self.ns.TryApproveItemLink("item:1", None, secondary)
        return bool(self.lua.eval("SAVED.main")), bool(self.lua.eval("SAVED.off"))

    def test_right_click_marks_main_spec_and_a_second_click_takes_it_out(self) -> None:
        self.assertEqual((True, False), self.click(False))
        self.assertEqual((False, False), self.click(False))

    def test_left_click_marks_off_spec_and_a_second_click_takes_it_out(self) -> None:
        self.assertEqual((False, True), self.click(True))
        self.assertEqual((False, False), self.click(True))

    def test_a_click_for_the_other_build_moves_the_piece(self) -> None:
        self.click(False)
        self.assertEqual((False, True), self.click(True))  # Main Spec -> Off Spec in one click
        self.assertEqual((True, False), self.click(False))  # and back

    def test_without_an_off_spec_nothing_is_moved(self) -> None:
        self.ns.GetTooltipEvaluationContexts = self.lua.eval("function() return MAIN, nil end")
        self.assertEqual((True, False), self.click(False))
        self.assertEqual((False, False), self.click(False))


if __name__ == "__main__":
    unittest.main()
