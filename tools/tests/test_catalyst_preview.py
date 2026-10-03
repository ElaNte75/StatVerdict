"""Holding Ctrl over an item the Catalyst can convert swaps the tooltip for the Best in Slot set piece it would become."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class CatalystPreviewTests(unittest.TestCase):
    ORIGINAL = "item:7000::::::::90::::1:12854"

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_Render.lua")  # holds the set piece's item string
        load_addon_file(self.lua, self.ns, "UI/SV_Tooltip.lua")
        lua = self.lua
        lua.execute("""
        CTRL = false
        IsControlKeyDown = function() return CTRL end
        SET_CALLS = {}
        FAIL_SET = false
        GameTooltip = {
            lines = {},
            link = nil,
            GetItem = function(self) return "Item", self.link end,
            AddLine = function(self, text) self.lines[#self.lines + 1] = text end,
            Show = function() end,
            SetHyperlink = function(self, link)
                SET_CALLS[#SET_CALLS + 1] = link
                if FAIL_SET then error("no such item") end
                self.link = link
                self.lines = {}
                SV_TEST_NS.ProcessTooltip(self)  -- what the game's post-call does after SetHyperlink
            end,
        }
        """)
        lua.globals().SV_TEST_NS = self.ns
        self.ns.ProfileRepository = lua.table(GetDataProvenance=lambda goal=None: lua.table(available=True))
        self.ns.GetStatAuditGoalMode = lambda: "RAID"
        self.ns.BuildComparison = lambda *_args: None  # no verdict is needed; what was processed is recorded below
        self.ns.GetTooltipEvaluationContexts = lambda: lua.table(goal="RAID", profile=lua.table(goal="RAID"))
        # Which item each processing pass saw (the stat ranks run once per pass).
        lua.execute("PROCESSED = {}")
        self.ns.AddStatRanksToTooltip = lua.eval("function(tip) PROCESSED[#PROCESSED + 1] = tip.link end")
        self.ns.GetItemReferenceInfo = lua.eval(
            "function(link) if tostring(link):find('^item:7000') then "
            "return { catalystPath = { targetItemID = 555 }, catalystBonus = 100 } end end")

    def hover(self, link: str, ctrl: bool, tooltip: str = "GameTooltip"):
        self.lua.execute(f"CTRL = {str(ctrl).lower()}; SET_CALLS = {{}}; PROCESSED = {{}}; GameTooltip.link = '{link}'; GameTooltip.lines = {{}}")
        self.ns.ProcessTooltip(self.lua.eval(tooltip))
        calls = [str(self.lua.eval(f"SET_CALLS[{i}]")) for i in range(1, int(self.lua.eval("#SET_CALLS")) + 1)]
        processed = [str(self.lua.eval(f"PROCESSED[{i}]")) for i in range(1, int(self.lua.eval("#PROCESSED")) + 1)]
        return calls, processed

    def test_ctrl_over_a_convertible_item_shows_the_set_piece_with_the_same_item_level(self) -> None:
        calls, processed = self.hover(self.ORIGINAL, ctrl=True)
        self.assertEqual(["item:555::::::::90::::1:12854"], calls)  # only the id changes: level and bonus ids stay
        self.assertEqual(["item:555::::::::90::::1:12854"], processed)  # only the set piece was filled, not the item

    def test_the_swap_happens_once_and_does_not_loop(self) -> None:
        calls, _ = self.hover(self.ORIGINAL, ctrl=True)
        self.assertEqual(1, len(calls))

    def test_without_ctrl_nothing_is_swapped(self) -> None:
        calls, processed = self.hover(self.ORIGINAL, ctrl=False)
        self.assertEqual([], calls)
        self.assertEqual([self.ORIGINAL], processed)

    def test_an_item_without_a_catalyst_path_is_never_swapped(self) -> None:
        calls, processed = self.hover("item:8000::::::::90", ctrl=True)
        self.assertEqual([], calls)
        self.assertEqual(["item:8000::::::::90"], processed)

    def test_only_the_main_hover_tooltip_is_swapped(self) -> None:
        self.lua.execute("""
        OTHER = { lines = {}, GetItem = function() return "Item", "item:7000::::::::90" end,
                  AddLine = function(self, text) self.lines[#self.lines + 1] = text end, Show = function() end,
                  SetHyperlink = function() SET_CALLS[#SET_CALLS + 1] = "other" end }
        """)
        self.lua.execute("CTRL = true; SET_CALLS = {}")
        self.ns.ProcessTooltip(self.lua.eval("OTHER"))
        self.assertEqual(0, int(self.lua.eval("#SET_CALLS")))

    def test_in_combat_nothing_is_swapped(self) -> None:
        self.lua.execute("InCombatLockdown = function() return true end")
        calls, _ = self.hover(self.ORIGINAL, ctrl=True)
        self.assertEqual([], calls)

    def test_a_failed_swap_leaves_the_normal_tooltip(self) -> None:
        self.lua.execute("FAIL_SET = true")
        calls, processed = self.hover(self.ORIGINAL, ctrl=True)
        self.assertEqual(1, len(calls))  # tried once
        self.assertEqual([self.ORIGINAL], processed)  # and the item itself is shown as usual

    def test_one_pass_only_so_the_stat_ranks_are_not_added_twice(self) -> None:
        _, processed = self.hover(self.ORIGINAL, ctrl=True)
        self.assertEqual(1, len(processed))

    def test_alt_does_not_swap_it_is_the_stat_ranks_key(self) -> None:
        self.lua.execute("IsAltKeyDown = function() return true end")  # even a held Alt does not swap
        calls, processed = self.hover(self.ORIGINAL, ctrl=False)
        self.assertEqual([], calls)
        self.assertEqual([self.ORIGINAL], processed)

    def test_the_set_piece_is_never_offered_for_saving(self) -> None:
        # Saving works on items the player owns: while the set piece shows, the tooltip is not "from the bags".
        self.lua.execute("BAG_CHECKS = 0")
        self.ns.IsTooltipFromPlayerBags = self.lua.eval("function() BAG_CHECKS = BAG_CHECKS + 1 return true end")
        self.hover(self.ORIGINAL, ctrl=True)
        self.assertEqual(0, int(self.lua.eval("BAG_CHECKS")))  # the set piece pass never asked
        self.hover(self.ORIGINAL, ctrl=False)
        self.assertGreater(int(self.lua.eval("BAG_CHECKS")), 0)  # the item itself still does


if __name__ == "__main__":
    unittest.main()
