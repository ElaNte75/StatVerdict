"""A piece the player wears: no comparison on its tooltip, only what its marks on the character sheet mean."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WornPieceInfoTests(unittest.TestCase):
    """ns.GetWornPieceInfo and the info block (UI/SV_Render.lua)."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        C_Item = { GetItemInfo = function() end }
        MAIN = { profile = { goal = "RAID", name = "main" } }
        OFF = { profile = { goal = "RAID", name = "off" } }
        BIS_ITEMS, GAIN, SAVED, MAIN_IS_PLAYED = {}, {}, {}, true
        """)
        self.ns.Colors = lua.table(white="|cffffffff", reset="|r", green="|cff00ff00", red="|cffff0000", yellow="|cffffff00")
        load_addon_file(lua, self.ns, "UI/SV_Render.lua")
        self.ns.GetTooltipEvaluationContexts = lua.eval("function() return MAIN, OFF end")
        self.ns.GetItemReferenceInfo = lua.eval("function(link) if BIS_ITEMS[link] then return { bis = {} } end end")
        self.ns.GetCatalystGain = lua.eval("function(context, link) return GAIN[link] end")
        self.ns.IsItemInEquipmentSnapshot = lua.eval("function(profile, link) return SAVED[profile.name .. ':' .. link] == true end")
        self.ns.ShouldUseEquipmentSnapshot = lua.eval("function(profile) return not MAIN_IS_PLAYED and profile.name == 'main' end")

    @staticmethod
    def plain(lines):
        import re
        return [re.sub(r"\|c[0-9a-fA-F]{8}|\|r", "", line) for line in lines]

    def info(self, link="item:1"):
        result = self.ns.GetWornPieceInfo(link)
        if not result:
            return None
        return {key: result[key] for key in ("bis", "gain", "shared", "otherLabel") if result[key] is not None}

    def tooltip_lines(self, link="item:1"):
        tooltip = self.lua.execute("""
        local lines = {}
        return { lines = lines, AddLine = function(self, text) lines[#lines + 1] = text end, Show = function() end }
        """)
        drawn = self.ns.RenderTooltipWornInfo(tooltip, link, self.lua.eval("MAIN"))
        return drawn, [str(tooltip.lines[i]) for i in range(1, len(tooltip.lines) + 1)]

    def test_a_piece_with_nothing_to_say_has_no_info(self) -> None:
        self.assertIsNone(self.info())
        drawn, lines = self.tooltip_lines()
        self.assertFalse(drawn)
        self.assertEqual([], lines)

    def test_a_best_in_slot_piece(self) -> None:
        self.lua.execute("BIS_ITEMS['item:1'] = true")
        self.assertEqual({"bis": True}, self.info())
        drawn, lines = self.tooltip_lines()
        self.assertTrue(drawn)
        self.assertTrue(any("StatVerdict info" in line for line in lines))
        self.assertTrue(any("This item is Best in Slot" in line for line in self.plain(lines)))
        self.assertTrue(any("|cff00ccffThis item is" in line for line in lines))  # light blue, the Best in Slot colour

    def test_a_piece_the_catalyst_makes_best_in_slot_is_one_warning_not_two_marks(self) -> None:
        self.lua.execute("GAIN['item:1'] = 96.3")
        info = self.info()
        self.assertEqual(96.3, info["gain"])
        self.assertFalse(info["bis"])
        drawn, lines = self.tooltip_lines()
        self.assertTrue(any("StatVerdict Warning" in line for line in lines))
        self.assertTrue(any("Catalyst it: Best in Slot" in line and "96.3" in line for line in lines))
        self.assertTrue(any("Hold Ctrl to preview" in line for line in lines))
        self.assertFalse(any("StatVerdict info" in line for line in lines))

    def test_a_best_in_slot_piece_never_gets_the_catalyst_line(self) -> None:
        self.lua.execute("BIS_ITEMS['item:1'] = true; GAIN['item:1'] = 50")
        self.assertNotIn("gain", self.info())

    def test_a_piece_in_both_sets_names_the_other_one(self) -> None:
        self.lua.execute("SAVED['main:item:1'] = true; SAVED['off:item:1'] = true")
        self.assertEqual({"bis": False, "shared": True, "otherLabel": "Off Spec"}, self.info())
        _, lines = self.tooltip_lines()
        self.assertTrue(any("Also part of your OS set" in line for line in self.plain(lines)))
        self.assertTrue(any("|cff00ff00OS|r" in line for line in lines))  # OS in green, as on the bag items

    def test_best_in_slot_and_in_both_sets(self) -> None:
        self.lua.execute("BIS_ITEMS['item:1'] = true; SAVED['main:item:1'] = true; SAVED['off:item:1'] = true")
        _, lines = self.tooltip_lines()
        plain = self.plain(lines)
        self.assertTrue(any("This item is Best in Slot" in line for line in plain))
        self.assertTrue(any("Also part of your OS set" in line for line in plain))
        self.assertFalse(any("Off Spec" in line for line in plain))

    def test_when_the_off_spec_is_played_the_other_set_is_the_main_spec(self) -> None:
        self.lua.execute("MAIN_IS_PLAYED = false; SAVED['main:item:1'] = true; SAVED['off:item:1'] = true")
        self.assertEqual("Main Spec", self.info()["otherLabel"])
        _, lines = self.tooltip_lines()
        self.assertTrue(any("|cff00ff00MS|r" in line for line in lines))  # MS in green

    def test_a_piece_in_one_set_only_is_not_shared(self) -> None:
        self.lua.execute("SAVED['main:item:1'] = true")
        self.assertIsNone(self.info())

    def test_without_an_off_spec_nothing_is_shared(self) -> None:
        self.ns.GetTooltipEvaluationContexts = self.lua.eval("function() return MAIN, nil end")
        self.lua.execute("SAVED['main:item:1'] = true; SAVED['off:item:1'] = true")
        self.assertIsNone(self.info())

    def test_all_three_lines_for_a_piece_that_has_everything(self) -> None:
        self.lua.execute("GAIN['item:1'] = 10; SAVED['main:item:1'] = true; SAVED['off:item:1'] = true")
        _, lines = self.tooltip_lines()
        self.assertTrue(any("Catalyst it" in line for line in lines))
        self.assertTrue(any("Also part of your OS set" in line for line in self.plain(lines)))


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WornPieceTooltipTests(unittest.TestCase):
    """The game tooltip of a worn piece: never a verdict (UI/SV_Tooltip.lua)."""

    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        GameTooltip = { lines = {}, owner = nil }
        function GameTooltip:AddLine(text) self.lines[#self.lines + 1] = text end
        function GameTooltip:GetName() return "WornTip" end
        function GameTooltip:NumLines() return #self.lines end
        function GameTooltip:GetItem() return "Item", "item:7" end
        function GameTooltip:Show() end
        function GameTooltip:GetOwner() return self.owner end
        function GameTooltip:HookScript() end
        VERDICT_CALLS, INFO_CALLS = 0, 0
        StatVerdictDB = {}
        CreateFrame = function() return { RegisterEvent = function() end, SetScript = function() end } end
        TooltipDataProcessor = { AddTooltipPostCall = function() end }
        Enum = { TooltipDataType = { Item = 0 } }
        InCombatLockdown = function() return false end
        C_Timer = { After = function() end }
        """)
        load_addon_file(lua, self.ns, "UI/SV_Tooltip.lua")
        self.ns.IsTooltipFromPlayerBags = lua.eval("function() return false end")
        self.ns.GetTooltipEvaluationContexts = lua.eval(
            "function() return { profile = { goal = 'RAID' }, specName = 'Frost' }, nil end")
        self.ns.BuildComparison = lua.eval(
            "function() return { selected = { isUpgrade = true, deltaScore = 5 } } end")
        self.ns.RenderTooltipVerdict = lua.eval(
            "function(tooltip) VERDICT_CALLS = VERDICT_CALLS + 1 tooltip:AddLine('StatVerdict Result') end")
        self.ns.RenderTooltipWornInfo = lua.eval(
            "function(tooltip) INFO_CALLS = INFO_CALLS + 1 tooltip:AddLine('StatVerdict info') return true end")

    def hover(self, owner_name):
        self.lua.execute("GameTooltip.lines = {}; VERDICT_CALLS, INFO_CALLS = 0, 0")
        self.lua.execute(
            "GameTooltip.owner = %s" % (
                "{ GetName = function() return '%s' end }" % owner_name if owner_name else "nil"))
        for i in range(1, 6):
            self.lua.execute(f"WornTipTextLeft{i} = nil")
        self.lua.execute("""
        for i = 1, #GameTooltip.lines do end
        """)
        self.ns.ProcessTooltip(self.lua.eval("GameTooltip"))
        return int(self.lua.eval("VERDICT_CALLS")), int(self.lua.eval("INFO_CALLS"))

    def test_a_worn_piece_never_gets_a_verdict_only_the_info(self) -> None:
        self.assertEqual((0, 1), self.hover("CharacterLegsSlot"))

    def test_the_option_off_leaves_a_worn_piece_plain(self) -> None:
        self.lua.execute("StatVerdictDB.showWornInfo = false")
        self.assertEqual((0, 0), self.hover("CharacterLegsSlot"))

    def test_the_inspect_window_is_not_a_worn_piece_of_the_player(self) -> None:
        self.assertEqual((1, 0), self.hover("InspectLegsSlot"))

    def test_any_other_item_keeps_its_verdict(self) -> None:
        self.assertEqual((1, 0), self.hover(None))
        self.assertEqual((1, 0), self.hover("ContainerFrame1Item3"))


if __name__ == "__main__":
    unittest.main()
