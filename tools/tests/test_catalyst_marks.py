"""The gold "!" on a worn piece of the character sheet when the Catalyst would make it Best in Slot."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class CatalystMarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.ns = self.lua.table()
        lua = self.lua
        lua.execute("""
        local function Frame()
            local f = { shown = true, marks = {} }
            function f:RegisterEvent() end
            function f:SetScript() end
            function f:HookScript() end
            function f:IsShown() return self.shown end
            function f:GetID() return self.id end
            function f:GetWidth() return 40 end
            function f:GetHeight() return 40 end
            function f:GetEffectiveAlpha() return 1 end
            function f:GetObjectType() return "Button" end
            function f:CreateFontString()
                local fs = { shown = false }
                function fs:SetDrawLayer() end
                function fs:SetFont() end
                function fs:SetText(t) self.text = t end
                function fs:SetPoint() end
                function fs:SetShown(v) self.shown = v end
                function fs:Show() self.shown = true end
                function fs:Hide() self.shown = false end
                return fs
            end
            return f
        end
        CreateFrame = function() return Frame() end
        C_Timer = { After = function() end }
        NUM_CONTAINER_SCAN_FRAMES = 0
        CharacterLegsSlot = Frame(); CharacterLegsSlot.id = 7
        CharacterHeadSlot = Frame(); CharacterHeadSlot.id = 1
        WORN = { [7] = "item:111", [1] = "item:222" }
        GetInventoryItemLink = function(unit, slot) return WORN[slot] end
        """)
        load_addon_file(lua, self.ns, "UI/SV_UpgradeIndicatorView.lua")
        self.ns.GetTooltipEvaluationContexts = lambda: lua.table(profile=lua.table(goal="RAID"))
        self.ns.GetCatalystGain = lua.eval("function(context, link) if link == 'item:111' then return 96.3 end end")
        self.ns.GetItemReferenceInfo = lua.eval("function(link, profile) if link == 'item:222' then return { bis = {} } end end")

    def mark_shown(self, frame: str, field: str = "StatVerdictCatalystMark") -> bool:
        return bool(self.lua.eval(f"{frame}.{field} and {frame}.{field}.shown or false"))

    def test_only_the_piece_the_catalyst_improves_is_marked(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterLegsSlot"))
        self.assertFalse(self.mark_shown("CharacterHeadSlot"))

    def test_a_best_in_slot_piece_gets_the_gold_tag_not_the_exclamation(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))
        self.assertFalse(self.mark_shown("CharacterLegsSlot", "StatVerdictBisMark"))

    def test_the_option_switches_every_mark_off(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.lua.execute("StatVerdictDB = { showCharacterMarks = false }")
        self.ns.RefreshCatalystMarks()
        self.assertFalse(self.mark_shown("CharacterLegsSlot"))
        self.assertFalse(self.mark_shown("CharacterHeadSlot", "StatVerdictBisMark"))
        self.lua.execute("StatVerdictDB = {}")  # never set: on
        self.ns.RefreshCatalystMarks()
        self.assertTrue(self.mark_shown("CharacterLegsSlot"))

    def test_the_mark_goes_when_the_piece_is_changed(self) -> None:
        self.ns.RefreshCatalystMarks()
        self.lua.execute("WORN[7] = 'item:333'")
        self.ns.RefreshCatalystMarks()
        self.assertFalse(self.mark_shown("CharacterLegsSlot"))


if __name__ == "__main__":
    unittest.main()
