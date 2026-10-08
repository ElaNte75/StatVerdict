"""The Manual has its own text size (100% to 175%): the text and its window grow together, and it is remembered."""
import unittest
from pathlib import Path

from tools.tests.test_addon_lua import FRAME_STUB, LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ManualTextSizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.lua.execute("UIParent = { GetWidth = function() return 1920 end, GetHeight = function() return 1080 end }")
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")
        self.mode = "manual"
        self.ns.GetRightPanelMode = lambda: self.mode
        load_addon_file(self.lua, self.ns, "UI/SV_ManualDrawerPanel.lua")
        self.lua.globals().StatVerdictDB = self.lua.table()
        self.panel = self.ns.StatVerdictManualDrawerPanel
        self.frame = self.lua.eval("CreateFrame")()
        self.refreshed = []
        self.ns.RequestStatAuditRefresh = lambda: self.refreshed.append(1)

    def db(self):
        return self.lua.globals().StatVerdictDB

    def apply(self):
        """The Manual with a topic open (the text is only shown inside a topic)."""
        self.panel.Apply(self.frame)
        self.panel.OpenTopic(self.frame, 2)
        return self.frame.manualDrawerCard

    # --- the saved size -----------------------------------------------------------------------------------------------
    def test_it_is_100_percent_until_chosen(self) -> None:
        self.assertEqual(100, self.ns.GetManualTextScalePercent())
        self.lua.globals().StatVerdictDB = None
        self.assertEqual(100, self.ns.GetManualTextScalePercent())

    def test_a_saved_size_is_used_and_kept_between_100_and_175(self) -> None:
        self.db().manualTextScale = 150
        self.assertEqual(150, self.ns.GetManualTextScalePercent())
        self.db().manualTextScale = 20
        self.assertEqual(100, self.ns.GetManualTextScalePercent())  # the Manual only gets bigger
        self.db().manualTextScale = 900
        self.assertEqual(175, self.ns.GetManualTextScalePercent())

    # --- the text ---------------------------------------------------------------------------------------------------
    def test_the_text_grows_with_the_size(self) -> None:
        card = self.apply()
        # The stub's font object gives 12 pt; the text is set to that times the size.
        self.assertEqual({12.0}, {float(line._font[2]) for line in card.lines.values()})
        self.db().manualTextScale = 150
        card = self.apply()
        self.assertEqual({18.0}, {float(line._font[2]) for line in card.lines.values()})
        self.db().manualTextScale = 100
        card = self.apply()
        self.assertEqual({12.0}, {float(line._font[2]) for line in card.lines.values()})  # back to the usual size, not compounded

    def test_the_gaps_between_the_lines_grow_with_the_size(self) -> None:
        card = self.apply()
        first = [line.points[len(line.points)][5] for line in card.lines.values()][:3]
        self.db().manualTextScale = 175
        card = self.apply()
        bigger = [line.points[len(line.points)][5] for line in card.lines.values()][:3]
        self.assertGreater(abs(bigger[1]), abs(first[1]))

    # --- the window -------------------------------------------------------------------------------------------------
    def test_the_window_grows_with_the_size(self) -> None:
        self.assertEqual(300, self.panel.GetPreferredWidth(self.frame))
        self.db().manualTextScale = 150
        self.assertEqual(450, self.panel.GetPreferredWidth(self.frame))
        self.db().manualTextScale = 175
        self.assertEqual(525, self.panel.GetPreferredWidth(self.frame))

    def test_the_window_is_never_wider_than_most_of_the_screen(self) -> None:
        self.lua.execute("UIParent = { GetWidth = function() return 600 end, GetHeight = function() return 1080 end }")
        self.db().manualTextScale = 175
        self.assertEqual(480, self.panel.GetPreferredWidth(self.frame))

    def test_a_docked_manual_may_be_wide(self) -> None:
        source = Path("StatVerdict/UI/SV_DashboardLayout.lua").read_text(encoding="utf-8-sig")
        self.assertIn("return Clamp(baseWidth + delta, 200, 1100)", source)

    def test_a_floating_manual_is_higher_with_the_size_up_to_the_screen(self) -> None:
        layout = self.lua.table()
        layout.IsCompact = lambda: True
        layout.GetFloatingPanelHeight = lambda: 390
        self.ns.StatVerdictDashboardLayout = layout
        card = self.apply()
        self.assertEqual(390, card.svFloatingHeight)
        self.db().manualTextScale = 150
        card = self.apply()
        self.assertEqual(585, card.svFloatingHeight)
        self.lua.execute("UIParent = { GetWidth = function() return 1920 end, GetHeight = function() return 500 end }")
        self.db().manualTextScale = 175
        card = self.apply()
        self.assertEqual(425, card.svFloatingHeight)  # not higher than 85% of the screen

    def test_a_docked_manual_keeps_the_height_of_the_window(self) -> None:
        card = self.apply()
        self.assertIsNone(card.svFloatingHeight)

    # --- the slider ---------------------------------------------------------------------------------------------------
    def test_the_slider_is_at_the_bottom_left_with_four_steps(self) -> None:
        card = self.apply()
        row = card.sizeRow
        self.assertEqual("Text size", row.label.text)
        self.assertEqual("100%", row.value.text)
        self.assertEqual(4, len(list(row.slider.ticks.values())))  # 100, 125, 150, 175
        point = row.points[len(row.points)]
        self.assertEqual("BOTTOMLEFT", point[1])
        self.assertEqual((10, 12), (point[4], point[5]))

    def test_the_text_stops_above_the_slider(self) -> None:
        card = self.apply()
        points = {p[1]: p for p in card.scroll.points.values()}
        self.assertEqual(12 + 34 + 8 + 10, points["BOTTOMRIGHT"][5])  # + the thin line above the slider

    def test_a_floating_manual_keeps_the_slider_clear_of_the_close_button(self) -> None:
        layout = self.lua.table()
        layout.IsCompact = lambda: True
        layout.GetFloatingPanelHeight = lambda: 390
        self.ns.StatVerdictDashboardLayout = layout
        card = self.apply()
        card.svFloating = True  # what the floating panel sets for itself
        card = self.apply()
        docked_width = None
        card.svFloating = False
        card = self.apply()
        docked_width = card.sizeRow._width
        card.svFloating = True
        card = self.apply()
        self.assertEqual(docked_width - 78, card.sizeRow._width)

    def release(self, value):
        card = self.apply()
        row = card.sizeRow
        row.slider.GetValue = lambda self: value
        row.slider.scripts.OnMouseUp(row.slider)

    def test_letting_go_saves_the_size_and_redraws(self) -> None:
        self.release(150)
        self.assertEqual(150, self.db().manualTextScale)
        self.assertEqual(1, len(self.refreshed))

    def test_the_value_snaps_to_the_steps_and_the_range(self) -> None:
        self.release(137)
        self.assertEqual(125, self.db().manualTextScale)
        self.release(50)
        self.assertEqual(100, self.db().manualTextScale)
        self.release(260)
        self.assertEqual(175, self.db().manualTextScale)

    def test_dragging_changes_only_the_number(self) -> None:
        card = self.apply()
        row = card.sizeRow
        row.slider.scripts.OnMouseDown(row.slider)
        row.slider.GetValue = lambda self: 175
        row.slider.scripts.OnValueChanged(row.slider, 175)
        self.assertEqual("175%", row.value.text)
        self.assertIsNone(self.db().manualTextScale)
        self.assertEqual([], self.refreshed)

    def test_a_saved_size_is_shown_on_the_slider(self) -> None:
        self.db().manualTextScale = 175
        card = self.apply()
        self.assertEqual("175%", card.sizeRow.value.text)

    def test_it_is_the_manuals_own_and_does_not_touch_the_window_size(self) -> None:
        self.db().windowScale = 85
        self.release(175)
        self.assertEqual(85, self.db().windowScale)
        self.assertEqual(175, self.db().manualTextScale)

    def test_the_slider_explains_itself(self) -> None:
        source = Path("StatVerdict/UI/SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("from 100% up to 175%. It is remembered, and only the Manual uses it.", source)

    def test_the_manual_mentions_its_text_size(self) -> None:
        source = Path("StatVerdict/UI/SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("Text size", source)


if __name__ == "__main__":
    unittest.main()
