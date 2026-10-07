"""The verdict block is for the Main Spec first; Alt shows the other one, only when an Off Spec is set;
a build that gains from the item too gets one gold line."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AltBuildVerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_Tooltip.lua")
        lua = self.lua
        lua.execute("""
        RENDERED, LINK = {}, 1000
        TIP = { lines = {} }
        function TIP:GetName() return "AltVerdictTip" end
        function TIP:NumLines() return #self.lines end
        function TIP:GetItem() return "Item", "item:" .. LINK end
        function TIP:AddLine(text)
            self.lines[#self.lines + 1] = text
            _G["AltVerdictTipTextLeft" .. #self.lines] = { GetText = function() return text end }
        end
        function TIP:Show() end
        -- A build gains from the item when its profile says so.
        UPGRADES = { Blood = true, Frost = true }
        """)
        self.ns.ProfileRepository = lua.table(GetDataProvenance=lambda goal=None: lua.table(available=True))
        self.ns.BuildComparison = lua.eval(
            "function(link, profile) return { selected = { isUpgrade = UPGRADES[profile.specName] == true, deltaScore = 5 } } end")
        # Draws like the real one: a header line (so the verdict counts as shown) and which build it was for.
        self.ns.RenderTooltipVerdict = lua.eval("""
        function(tooltip, context, comparison, isSecondary)
            if not comparison.selected.isUpgrade then return end
            RENDERED[#RENDERED + 1] = context.specName .. (isSecondary and ":secondary" or ":primary")
            tooltip:AddLine("|cffff8000StatVerdict Result|r " .. context.specName)
        end""")
        self.ns.IsTooltipFromPlayerBags = lua.eval("function() return TIP_IN_BAGS == true end")
        self.set_builds(off_spec=True)

    def set_builds(self, off_spec: bool) -> None:
        lua = self.lua
        lua.globals().BLOOD = lua.table(specName="Blood", profile=lua.table(specName="Blood", goal="RAID"), goal="RAID")
        lua.globals().FROST = lua.table(specName="Frost", profile=lua.table(specName="Frost", goal="RAID"), goal="RAID")
        self.ns.GetTooltipEvaluationContexts = lua.eval(
            "function() return BLOOD" + (", FROST" if off_spec else "") + " end")

    def hover(self, alt=False, upgrades=("Blood", "Frost"), same_item=False, in_bags=False):
        lua = self.lua
        if not same_item:
            lua.execute("LINK = LINK + 1")  # every hover is another item unless said otherwise
        lua.execute(f"RENDERED = {{}}; TIP.lines = {{}}")
        lua.execute("IsAltKeyDown = function() return " + ("true" if alt else "false") + " end")  # Alt is held, not switched
        lua.execute("TIP_IN_BAGS = " + ("true" if in_bags else "false"))
        lua.execute("UPGRADES = { " + ", ".join(f"{name} = true" for name in upgrades) + " }")
        self.ns.ProcessTooltip(lua.eval("TIP"))
        rendered = [str(lua.eval(f"RENDERED[{i}]")) for i in range(1, int(lua.eval("#RENDERED")) + 1)]
        lines = [str(lua.eval(f"TIP.lines[{i}]")) for i in range(1, int(lua.eval("#TIP.lines")) + 1)]
        return rendered, lines

    def test_the_selected_build_is_shown_by_default(self) -> None:
        rendered, _ = self.hover()
        self.assertEqual(["Blood:primary"], rendered)

    def test_alt_shows_the_other_build(self) -> None:
        rendered, lines = self.hover(alt=True)
        self.assertEqual(["Frost:secondary"], rendered)
        self.assertEqual(1, len([line for line in lines if "Also an upgrade for Main Spec" in line]))  # the way back

    def test_without_an_off_spec_alt_does_nothing(self) -> None:
        self.set_builds(off_spec=False)
        rendered, lines = self.hover(alt=True)
        self.assertEqual(["Blood:primary"], rendered)
        self.assertFalse(any("Also an upgrade" in line for line in lines))

    def test_a_build_that_gains_too_gets_one_gold_line(self) -> None:
        _, lines = self.hover(upgrades=("Blood", "Frost"))
        hints = [line for line in lines if "Also an upgrade for Off Spec" in line]
        self.assertEqual(1, len(hints))
        self.assertIs(True, lines[-1] == hints[0])  # at the very end

    def test_no_line_when_the_other_build_does_not_gain(self) -> None:
        _, lines = self.hover(upgrades=("Blood",))
        self.assertFalse(any("Also an upgrade" in line for line in lines))

    def test_a_build_with_nothing_falls_back_to_the_other(self) -> None:
        rendered, _ = self.hover(upgrades=("Frost",))
        self.assertEqual(["Frost:secondary"], rendered)  # Blood has nothing to say, Frost does
        rendered, _ = self.hover(upgrades=("Blood",))
        self.assertEqual(["Blood:primary"], rendered)  # and the Main Spec comes first when it has something to say

    def test_alt_is_held_not_switched_letting_go_goes_back(self) -> None:
        rendered, _ = self.hover(alt=True)
        self.assertEqual(["Frost:secondary"], rendered)
        rendered, _ = self.hover(same_item=True)  # Alt let go: the first build again, nothing stays
        self.assertEqual(["Blood:primary"], rendered)

    def test_over_a_bag_item_alt_changes_nothing(self) -> None:
        rendered, lines = self.hover(alt=True, in_bags=True)  # Alt is the marking key there
        self.assertEqual(["Blood:primary"], rendered)
        self.assertEqual(1, len([line for line in lines if "Also an upgrade for Off Spec" in line]))


if __name__ == "__main__":
    unittest.main()
