"""Always on top (off unless the player turns it on).
Off: the window is in front while the player works in it and steps behind everything on a click anywhere else."""
import unittest
from pathlib import Path

from tools.tests.test_addon_lua import LuaRuntime, load_addon_file, new_runtime

ADDON = Path("StatVerdict")

HARNESS = """
function MakeFrame(parent)
    local f = { parent = parent, shown = true, scripts = {}, hooks = {} }
    function f:SetFrameStrata(s) self.strata = s end
    function f:SetToplevel(v) self.toplevel = v end
    function f:Raise() self.raised = (self.raised or 0) + 1 end
    function f:IsShown() return self.shown end
    function f:GetParent() return self.parent end
    function f:HookScript(name, fn) self.hooks[name] = fn end
    function f:SetScript(name, fn) self.scripts[name] = fn end
    function f:RegisterEvent(name) self.events = self.events or {}; self.events[#self.events + 1] = name end
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
"""


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AlwaysOnTopTests(unittest.TestCase):
    def setUp(self):
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.execute(HARNESS)
        load_addon_file(self.lua, self.ns, "UI/SV_WindowChrome.lua")
        self.g = self.lua.globals()
        self.frame = self.g.MakeFrame()
        self.child = self.g.MakeFrame(self.frame)
        self.other = self.g.MakeFrame()
        self.g.StatVerdictDB = self.lua.table()

    def press(self, *over):
        self.g.mouse_over = self.lua.table_from(list(over))
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")

    def start(self):
        self.ns.ApplyAlwaysOnTop(self.frame)

    def test_it_is_off_by_default(self):
        self.g.StatVerdictDB = None
        self.assertFalse(self.ns.AlwaysOnTopEnabled())
        self.g.StatVerdictDB = self.lua.table()
        self.assertFalse(self.ns.AlwaysOnTopEnabled())

    def test_on_keeps_the_window_in_front_whatever_is_clicked(self):
        self.g.StatVerdictDB = self.lua.table(alwaysOnTop=True)
        self.start()
        self.assertEqual("HIGH", self.frame.strata)
        self.press(self.other)
        self.assertEqual("HIGH", self.frame.strata)

    def test_off_starts_in_front_and_raises_when_clicked(self):
        self.start()
        self.assertEqual("HIGH", self.frame.strata)
        self.assertTrue(self.frame.toplevel)

    def test_off_a_click_anywhere_else_sends_it_behind(self):
        self.start()
        self.press(self.other)
        self.assertEqual("BACKGROUND", self.frame.strata)

    def test_a_click_on_the_world_with_nothing_under_the_mouse_sends_it_behind(self):
        self.start()
        self.press()
        self.assertEqual("BACKGROUND", self.frame.strata)

    def test_a_click_on_the_window_brings_it_forward_again(self):
        self.start()
        self.press(self.other)
        self.press(self.frame)
        self.assertEqual("HIGH", self.frame.strata)

    def test_a_click_on_a_part_of_the_window_counts_as_the_window(self):
        self.start()
        self.press(self.other)
        self.press(self.child)
        self.assertEqual("HIGH", self.frame.strata)

    def test_a_click_on_a_menu_that_belongs_to_the_window_keeps_it_in_front(self):
        self.start()
        menu = self.g.MakeFrame()
        menu.svOwnedWindow = True
        item = self.g.MakeFrame(menu)
        self.press(item)
        self.assertEqual("HIGH", self.frame.strata)

    def test_clicks_while_the_window_is_hidden_change_nothing(self):
        self.start()
        self.frame.shown = False
        self.press(self.other)
        self.assertEqual("HIGH", self.frame.strata)

    def test_showing_the_window_brings_it_forward(self):
        self.start()
        self.press(self.other)
        self.frame.hooks.OnShow(self.frame)
        self.assertEqual("HIGH", self.frame.strata)

    def test_turning_the_option_on_and_off_while_the_window_is_open(self):
        self.start()
        self.press(self.other)
        self.g.StatVerdictDB.alwaysOnTop = True
        self.ns.ApplyAlwaysOnTop()
        self.assertEqual("HIGH", self.frame.strata)
        self.press(self.other)
        self.assertEqual("HIGH", self.frame.strata)
        self.g.StatVerdictDB.alwaysOnTop = False
        self.ns.ApplyAlwaysOnTop()
        self.press(self.other)
        self.assertEqual("BACKGROUND", self.frame.strata)

    def test_it_listens_for_one_event_even_when_applied_twice(self):
        self.start()
        self.ns.ApplyAlwaysOnTop(self.frame)
        self.assertEqual(1, len(self.g.watchers))
        self.assertEqual("GLOBAL_MOUSE_DOWN", self.g.watchers[1].events[1])

    def test_an_older_game_without_mouse_foci_uses_the_single_focus(self):
        self.lua.execute("GetMouseFoci = nil; function GetMouseFocus() return mouse_focus end")
        self.start()
        self.g.mouse_focus = self.other
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")
        self.assertEqual("BACKGROUND", self.frame.strata)
        self.g.mouse_focus = self.child
        self.g.watchers[1].scripts.OnEvent(self.g.watchers[1], "GLOBAL_MOUSE_DOWN")
        self.assertEqual("HIGH", self.frame.strata)

    def test_a_missing_frame_is_ignored(self):
        self.ns.ApplyAlwaysOnTop(None)

    def test_the_main_window_applies_it_before_it_builds_any_child(self):
        source = (ADDON / "UI" / "SV_StatAudit.lua").read_text(encoding="utf-8-sig")
        create = source.index('CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictStatAuditFrame")')
        apply_at = source.index("ns.ApplyAlwaysOnTop(frame)", create)
        first_child = source.index("frame:CreateFontString", create)
        self.assertLess(apply_at, first_child)

    def test_the_menus_and_blocker_of_the_window_are_marked_as_part_of_it(self):
        dropdown = (ADDON / "UI" / "SV_ChipDropdown.lua").read_text(encoding="utf-8-sig")
        self.assertEqual(2, dropdown.count("svOwnedWindow = true"))
        audit = (ADDON / "UI" / "SV_StatAudit.lua").read_text(encoding="utf-8-sig")
        self.assertIn("blocker.svOwnedWindow = true", audit)

    def test_the_window_chrome_loads_before_the_main_window(self):
        toc = (ADDON / "StatVerdict.toc").read_text(encoding="utf-8-sig")
        self.assertLess(toc.index("UI/SV_WindowChrome.lua"), toc.index("UI/SV_StatAudit.lua"))


if __name__ == "__main__":
    unittest.main()
