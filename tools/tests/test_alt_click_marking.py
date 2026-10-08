"""Alt-click marking: right click switches the Main Spec mark on or off, left click the Off Spec mark; independent of each other."""
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

    def test_the_two_builds_are_independent_a_piece_can_be_in_both(self) -> None:
        self.assertEqual((True, False), self.click(False))  # right click: Main Spec
        self.assertEqual((True, True), self.click(True))  # left click: Off Spec as well, Main Spec stays
        self.assertEqual((True, False), self.click(True))  # left click again: only the Off Spec goes
        self.assertEqual((False, False), self.click(False))

    def test_without_an_off_spec_nothing_is_moved(self) -> None:
        self.ns.GetTooltipEvaluationContexts = self.lua.eval("function() return MAIN, nil end")
        self.assertEqual((True, False), self.click(False))
        self.assertEqual((False, False), self.click(False))


if __name__ == "__main__":
    unittest.main()
