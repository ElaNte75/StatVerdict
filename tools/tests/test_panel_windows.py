"""The main window and a panel in Compact Mode are two windows: a click brings the one clicked, all of it, to the front."""
import unittest
from pathlib import Path

from tools.tests.test_addon_lua import FRAME_STUB, LuaRuntime, load_addon_file, new_runtime

HARNESS = """
function MakeFrame(parent)
    local f = { parent = parent, shown = true, scripts = {}, hooks = {}, points = {}, level = 5, scale = 1, strata = "MEDIUM", raised = 0 }
    function f:SetFrameStrata(s) self.strata = s end
    function f:GetFrameStrata() return self.strata end
    function f:SetFrameLevel(l) self.level = l end
    function f:GetFrameLevel() return self.level end
    function f:SetToplevel(v) self.toplevel = v end
    function f:Raise() self.raised = self.raised + 1 end
    function f:IsShown() return self.shown end
    function f:Show() self.shown = true end
    function f:Hide() self.shown = false; if self.hooks.OnHide then self.hooks.OnHide(self) end end
    function f:GetParent() return self.parent end
    function f:SetParent(p) self.parent = p end
    function f:HookScript(name, fn) self.hooks[name] = fn end
    function f:SetScript(name, fn) self.scripts[name] = fn end
    function f:RegisterEvent(name) end
    function f:SetScale(s) self.scale = s end
    function f:GetScale() return self.scale end
    function f:ClearAllPoints() self.points = {} end
    function f:SetPoint(...) self.points[#self.points + 1] = { ... } end
    function f:SetHeight(h) self.h = h end
    function f:SetMovable(v) end
    function f:SetClampedToScreen(v) end
    function f:EnableMouse(v) end
    function f:RegisterForDrag(...) end
    function f:GetWidth() return 320 end
    function f:SetFrameLevel(l) self.level = l end
    function f:Hide2() end
    return f
end
watchers = {}
function CreateFrame()
    local w = MakeFrame()
    watchers[#watchers + 1] = w
    return w
end
mouse_over = {}
function GetMouseFoci() return mouse_over end
UIParent = MakeFrame()
function UIParent:GetWidth() return 1920 end
function UIParent:GetHeight() return 1080 end
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class PanelWindowTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.execute(HARNESS)
        self.g = self.lua.globals()
        self.g.StatVerdictDB = self.lua.table(compactMode=True)
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")
        load_addon_file(self.lua, self.ns, "UI/SV_WindowChrome.lua")
        load_addon_file(self.lua, self.ns, "UI/SV_DashboardLayout.lua")
        # The real button needs the whole frame API; a plain fake frame stands in for it here.
        self.ns.CreateFloatingButton = lambda card, label, click: self.g.MakeFrame(card)
        self.layout = self.ns.StatVerdictDashboardLayout
        self.window = self.g.MakeFrame()
        self.window.GetRight = self.lua.eval("function() return 600 end")
        self.window.GetLeft = self.lua.eval("function() return 100 end")
        self.window.GetTop = self.lua.eval("function() return 900 end")
        self.window.statProgressCard = self.g.MakeFrame(self.window)
        self.card = self.g.MakeFrame(self.window)
        self.card.preferredWidth = 320
        self.card.GetLeft = self.lua.eval("function() return 650 end")
        self.card.GetTop = self.lua.eval("function() return 890 end")

    def anchor(self):
        self.layout.AnchorAfterPreviousCard(self.card, self.window.statProgressCard, self.window, 0, 0, None)

    def same(self, a, b):
        return self.lua.eval("function(x, y) return rawequal(x, y) end")(a, b)

    # --- a window of its own ---------------------------------------------------------------------------------------
    def test_a_floating_panel_is_a_child_of_the_screen_and_a_top_level_window(self):
        self.anchor()
        self.assertTrue(self.same(self.card.parent, self.g.UIParent))
        self.assertTrue(self.card.toplevel)  # a click brings it, all of it, to the front

    def test_a_panel_that_has_just_opened_is_in_front(self):
        self.anchor()
        self.assertEqual(1, self.card.raised)
        self.anchor()  # the next passes of the layout do not raise it again
        self.assertEqual(1, self.card.raised)

    def test_it_takes_the_layer_and_the_size_of_the_main_window(self):
        self.window.strata = "HIGH"
        self.window.scale = 0.8
        self.anchor()
        self.assertEqual("HIGH", self.card.strata)
        self.assertEqual(0.8, self.card.scale)

    def test_the_main_window_changing_layer_takes_its_panels_along(self):
        self.anchor()
        self.ns.ApplyAlwaysOnTop(self.window)  # off by default: in front while worked in
        self.assertEqual("HIGH", self.window.strata)
        self.assertEqual("HIGH", self.card.strata)
        self.g.mouse_over = self.lua.table_from([self.g.MakeFrame()])  # a click somewhere else
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")
        self.assertEqual("BACKGROUND", self.window.strata)
        self.assertEqual("BACKGROUND", self.card.strata)  # the panel steps back with the window

    def test_always_on_top_puts_the_panels_in_front_too(self):
        self.anchor()
        self.g.StatVerdictDB.alwaysOnTop = True
        self.ns.ApplyAlwaysOnTop(self.window)
        self.assertEqual("HIGH", self.card.strata)

    def test_closing_the_main_window_closes_the_panels(self):
        self.anchor()
        self.assertTrue(self.card.shown)
        self.window.Hide(self.window)
        self.assertFalse(self.card.shown)

    def test_the_panels_do_not_show_while_the_main_window_is_hidden(self):
        self.anchor()
        self.window.shown = False
        self.card.shown = True
        self.layout.HideFloatingPanelsWithTheWindow(self.window)
        self.assertFalse(self.card.shown)
        self.window.shown = True
        self.card.shown = True
        self.layout.HideFloatingPanelsWithTheWindow(self.window)
        self.assertTrue(self.card.shown)

    # --- clicking ---------------------------------------------------------------------------------------------------
    def test_a_click_on_a_panel_window_counts_as_a_click_in_the_window_and_raises_the_panel(self):
        self.anchor()
        self.ns.ApplyAlwaysOnTop(self.window)
        self.window.svInFront = False
        self.window.strata = "BACKGROUND"
        child = self.g.MakeFrame(self.card)
        self.g.mouse_over = self.lua.table_from([child])
        before = self.card.raised
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")
        self.assertEqual("HIGH", self.window.strata)  # the window comes forward
        self.assertEqual(before + 1, self.card.raised)  # and the panel that was clicked stays above it

    def test_a_click_on_the_main_window_does_not_raise_a_panel(self):
        self.anchor()
        self.ns.ApplyAlwaysOnTop(self.window)
        before = self.card.raised
        self.g.mouse_over = self.lua.table_from([self.g.MakeFrame(self.window)])
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")
        self.assertEqual(before, self.card.raised)

    def test_a_click_somewhere_else_still_sends_both_windows_behind(self):
        self.anchor()
        self.ns.ApplyAlwaysOnTop(self.window)
        self.g.mouse_over = self.lua.table_from([self.g.MakeFrame()])
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")
        self.assertEqual("BACKGROUND", self.card.strata)

    # --- back to docked ---------------------------------------------------------------------------------------------
    def test_a_docked_panel_is_a_part_of_the_main_window_again(self):
        self.anchor()
        self.g.StatVerdictDB.compactMode = False
        self.layout.AnchorAfterPreviousCard(self.card, self.window.statProgressCard, self.window, 0, 0, None)
        self.assertTrue(self.same(self.card.parent, self.window))
        self.assertFalse(self.card.toplevel)
        self.assertEqual(1, self.card.scale)
        self.assertEqual(4, self.card.level)  # one under the window, as it always was
        self.assertFalse(self.card.svFloating)

    def test_a_docked_panel_is_not_touched_when_it_never_floated(self):
        self.g.StatVerdictDB.compactMode = False
        before = self.card.parent
        self.layout.AnchorAfterPreviousCard(self.card, self.window.statProgressCard, self.window, 0, 0, None)
        self.assertTrue(self.same(self.card.parent, before))

    def test_source_marks_the_panel_window_as_part_of_the_main_window(self):
        source = Path("StatVerdict/UI/SV_WindowChrome.lua").read_text(encoding="utf-8-sig")
        self.assertIn("if current.svWindow == frame then return true, current end", source)


if __name__ == "__main__":
    unittest.main()
