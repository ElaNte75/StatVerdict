"""Options > Window: Always on top works, Compact Mode is a placeholder; every choice explains itself on hover."""
import pathlib
import unittest

from tools.tests import test_addon_lua as base
from tools.tests.test_addon_lua import LuaRuntime

ALL_KEYS = [
    "showUpgradeArrow", "showMsOsLabels", "showStatRanks", "showCharacterMarks", "showBisTooltip", "showBisGemsEnchants",
    "bisUseGameTooltip", "showTrinketTooltip", "showTrinketEffect", "trinketUseGameTooltip",
    "alwaysOnTop", "compactMode", "autoHideLeft",
]


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WindowGroupTests(unittest.TestCase):
    setUp = base.BisTooltipFeatureToggleTests.setUp
    check = base.BisTooltipFeatureToggleTests.check
    click = base.BisTooltipFeatureToggleTests.click
    db = base.BisTooltipFeatureToggleTests.db
    active = base.BisTooltipFeatureToggleTests.active

    def test_the_window_choices_come_first_in_order(self) -> None:
        keys = ("alwaysOnTop", "compactMode", "autoHideLeft")
        checks = [self.check(key) for key in keys]
        self.assertEqual(["Always on top", "Compact Mode", "Auto-hide the left side"], [c.Text.text for c in checks])
        last = lambda region: region.points[len(region.points)]
        self.assertEqual([-26, -62, -98], [last(c.svRow)[5] for c in checks])  # a row with a grey line is 36 high
        card = self.frame.optionsDrawerCard
        self.assertGreater(last(card.windowGroup)[5], last(card.bagGroup)[5])  # above the bag choices
        self.assertEqual("WINDOW", card.windowGroup.heading.text)

    def test_always_on_top_is_off_until_the_player_turns_it_on(self) -> None:
        self.assertFalse(self.check("alwaysOnTop").checked)
        self.lua.globals().StatVerdictDB = None
        self.assertFalse(self.check("alwaysOnTop").checked)

    def test_ticking_always_on_top_saves_it_and_applies_it_at_once(self) -> None:
        applied = []
        self.ns.ApplyAlwaysOnTop = lambda *args: applied.append(self.db().alwaysOnTop)
        self.assertTrue(self.click("alwaysOnTop", True).checked)
        self.assertIs(True, self.db().alwaysOnTop)
        self.assertFalse(self.click("alwaysOnTop", False).checked)
        self.assertIs(False, self.db().alwaysOnTop)
        self.assertEqual([True, False], applied)  # the window is told after each change, with the value already saved

    def test_a_saved_always_on_top_shows_a_gold_switch(self) -> None:
        self.db().alwaysOnTop = True
        check = self.check("alwaysOnTop")
        self.assertTrue(check.checked)
        knob = check.svRow.switch.knob._color
        self.assertEqual((1.0, 0.82, 0.0), (knob[1], knob[2], knob[3]))

    def test_compact_mode_is_off_until_ticked_and_asks_for_a_redraw(self) -> None:
        refreshed = []
        self.ns.RequestStatAuditRefresh = lambda: refreshed.append(self.db().compactMode)
        check = self.check("compactMode")
        self.assertFalse(check.checked)
        self.assertTrue(self.active(check))
        self.assertTrue(self.click("compactMode", True).checked)
        self.assertIs(True, self.db().compactMode)
        self.assertFalse(self.click("compactMode", False).checked)
        self.assertEqual([True, False], refreshed)  # the window redraws after each change, with the value already saved

    def compact_card(self, compact):
        layout = self.lua.table()
        layout.IsCompact = lambda: compact
        layout.FLOAT_BUTTON = self.lua.table(width=70, height=24, margin=14, bottom=12, gap=6)
        layout.GetFloatingBand = lambda: 12 + 24 + 8
        self.ns.StatVerdictDashboardLayout = layout
        # The layout file makes the buttons; this harness only needs a stand-in with the same look of a frame.
        self.ns.CreateFloatingButton = lambda card, label, onClick: self.make_button(card, label, onClick)
        self.check()
        return self.frame.optionsDrawerCard

    def make_button(self, card, label, onClick):
        button = self.lua.eval("CreateFrame")()
        button.label = self.lua.eval("CreateFrame")()
        button.label.SetText(button.label, label)
        button.scripts = self.lua.table(OnClick=onClick)
        return button

    def test_the_manual_button_shows_only_in_compact_mode(self) -> None:
        card = self.compact_card(False)
        self.assertIsNone(card.manualButton)
        card = self.compact_card(True)
        self.assertIs(True, card.manualButton.shown)
        card = self.compact_card(False)
        self.assertIs(False, card.manualButton.shown)

    def test_options_has_no_close_button_of_its_own(self) -> None:
        card = self.compact_card(True)
        self.assertIsNone(card.closeButton)  # the Close button of every floating panel comes with the panel window

    def test_manual_sits_left_of_the_close_corner_at_the_bottom(self) -> None:
        card = self.compact_card(True)
        point = card.manualButton.points[len(card.manualButton.points)]
        self.assertEqual("BOTTOMRIGHT", point[1])
        self.assertEqual(-(14 + 70 + 6), point[4])  # the margin, the Close button's width and a gap from the right edge
        self.assertEqual(12, point[5])  # the same height above the bottom as the Close button
        self.assertEqual("Manual", card.manualButton.label.text)

    def test_the_list_stops_above_the_bottom_buttons(self) -> None:
        card = self.compact_card(True)
        points = {p[1]: p for p in card.scroll.points.values()}
        band = points["BOTTOMRIGHT"][5]  # how far above the card's bottom the list stops
        buttons_top = 12 + 24  # the buttons are 12 above the bottom edge and 24 high
        self.assertGreaterEqual(band, buttons_top)

    def test_the_manual_button_opens_the_manual_instead_of_options(self) -> None:
        card = self.compact_card(True)
        calls = []
        self.ns.SetRightPanelMode = lambda mode: calls.append(mode)
        card.manualButton.scripts.OnClick(card.manualButton)
        self.assertEqual(["manual"], calls)

    def test_only_one_panel_is_ever_open(self) -> None:
        self.lua.execute("StatVerdictDB = StatVerdictDB or {}")
        self.lua.globals().StatVerdictDB = self.lua.table()
        load = __import__("tools.tests.test_addon_lua", fromlist=["load_addon_file"]).load_addon_file
        load(self.lua, self.ns, "UI/SV_RightPanelMode.lua")
        self.ns.RequestStatAuditRefresh = lambda: None
        panels = ("showBisPanel", "showTrinketPanel", "showWeightsPanel", "showOptionsPanel", "showManualPanel")
        for mode in ("options", "manual", "weights", "bis", "trinkets", "options"):
            self.ns.SetRightPanelMode(mode)
            self.assertEqual(1, sum(1 for key in panels if self.db()[key] is True), mode)

    def test_bag_marker_choices_still_save_and_refresh(self) -> None:
        self.assertFalse(self.click("showStatRanks", False).checked)
        self.assertIs(False, self.db().showStatRanks)
        self.assertTrue(self.click("showStatRanks", True).checked)

    def test_every_choice_explains_itself(self) -> None:
        for key in ALL_KEYS:
            check = self.check(key)
            self.assertTrue(check.svTip and len(check.svTip) > 20, key)
            self.assertTrue(check.svTipTitle, key)

    def test_hovering_a_choice_shows_its_explanation(self) -> None:
        self.lua.execute(
            "GameTooltip = { lines = {} } "
            "function GameTooltip:SetOwner(o) self.owner = o self.lines = {} end "
            "function GameTooltip:AddLine(text) self.lines[#self.lines + 1] = text end "
            "function GameTooltip:Show() self.shown = true end "
            "function GameTooltip:Hide() self.shown = false end "
            "function GameTooltip:GetOwner() return self.owner end"
        )
        check = self.check("alwaysOnTop")
        row = check.svRow
        row.scripts.OnEnter(row)
        tip = self.lua.globals().GameTooltip
        self.assertTrue(tip.shown)
        self.assertEqual("Always on top", tip.lines[1])
        self.assertIn("in front of everything", tip.lines[2])
        row.scripts.OnLeave(row)
        self.assertFalse(tip.shown)

    def test_the_ms_os_label_tooltip_has_a_plain_title(self) -> None:
        self.assertEqual("MS / OS Labels on bag items", self.check("showMsOsLabels").svTipTitle)  # no colour codes

    def test_the_tab_and_its_button_are_called_options(self) -> None:
        import re
        from pathlib import Path
        settings = Path("StatVerdict/UI/SV_SettingsPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn('label = "Options",', settings)
        self.assertNotIn('label = "Features"', settings)
        panel = Path("StatVerdict/UI/SV_OptionsDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn('PlaceTabTitleChip(card, "Options")', panel)
        self.assertIsNone(re.search(r'PlaceTabTitleChip\(card, "Features"\)', panel))

    def test_the_manual_explains_every_new_choice_and_key(self) -> None:
        from pathlib import Path
        manual = Path("StatVerdict/UI/SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertNotIn("Features", manual)
        for phrase in ("Window and Compact Mode", "Always on top", "Compact Mode", "Auto-hide the left side",
                       "Show Off Spec / Show Main Spec", "StatVerdict Guide", "Close at its bottom right",
                       "Manual button next to Close", "Item tooltips", "Stat Ranks", "Hold Alt", "Hold Ctrl",
                       "Shift is the game's own comparison", "put on (only those in your bags"):
            self.assertIn(phrase, manual, phrase)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WindowSizeSliderTests(unittest.TestCase):
    check = base.BisTooltipFeatureToggleTests.check
    db = base.BisTooltipFeatureToggleTests.db

    def setUp(self) -> None:
        base.BisTooltipFeatureToggleTests.setUp(self)
        base.load_addon_file(self.lua, self.ns, "UI/SV_WindowChrome.lua")  # the saved size and which mode's size it is

    def row(self):
        self.check()
        return self.frame.optionsDrawerCard.sliderRows["windowScale"]

    def test_the_slider_is_the_last_line_of_the_window_card(self) -> None:
        row = self.row()
        card = self.frame.optionsDrawerCard
        last = lambda region: region.points[len(region.points)]
        self.assertEqual("Window size", row.label.text)
        self.assertEqual(-(26 + 36 * 3), last(row)[5])  # under the three switches
        self.assertEqual(46, row._height)
        self.assertEqual(26 + 36 * 3 + 46 + 6, card.windowGroup._height)

    def test_it_runs_from_75_to_100_percent_in_steps_of_5(self) -> None:
        slider = self.row().slider
        self.assertEqual((75, 100), (slider.minimum, slider.maximum)) if hasattr(slider, "minimum") and slider.minimum else None
        source = pathlib.Path("StatVerdict/UI/SV_OptionsDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn('min = 75, max = 100, step = 5, default = 85', source)  # never smaller than three quarters

    def test_it_starts_at_85_percent(self) -> None:
        row = self.row()
        self.assertEqual("85%", row.value.text)  # the size the add-on was tuned on

    def test_a_saved_size_is_shown(self) -> None:
        self.db().windowScale = 85
        row = self.row()
        self.assertEqual("85%", row.value.text)

    def test_a_saved_size_outside_the_range_is_brought_back_into_it(self) -> None:
        self.db().windowScale = 40
        self.assertEqual("75%", self.row().value.text)
        self.db().windowScale = 300
        self.assertEqual("100%", self.row().value.text)

    def release(self, row, value):
        row.slider.GetValue = lambda self: value
        row.slider.scripts.OnMouseUp(row.slider)

    def test_letting_go_of_the_slider_saves_the_size_and_resizes_the_window(self) -> None:
        applied = []
        self.ns.ApplyWindowScale = lambda: applied.append(self.db().windowScale)
        row = self.row()
        self.release(row, 80)
        self.assertEqual(80, self.db().windowScale)
        self.assertEqual([80], applied)  # the window is told after the value was saved

    def test_dragging_only_changes_the_number_not_the_window(self) -> None:
        applied = []
        self.ns.ApplyWindowScale = lambda: applied.append(1)
        row = self.row()
        row.slider.scripts.OnMouseDown(row.slider)
        row.slider.GetValue = lambda self: 90
        row.slider.scripts.OnValueChanged(row.slider, 90)
        self.assertEqual("90%", row.value.text)  # the number follows the thumb
        self.assertEqual([], applied)  # the window waits until the mouse lets go
        self.assertIsNone(self.db().windowScale)

    def test_a_value_set_without_dragging_is_applied(self) -> None:
        applied = []
        self.ns.ApplyWindowScale = lambda: applied.append(self.db().windowScale)
        row = self.row()
        row.slider.GetValue = lambda self: 75
        row.slider.scripts.OnValueChanged(row.slider, 75)  # a click on the track, the arrow keys
        self.assertEqual([75], applied)

    def test_the_value_snaps_to_the_step_and_to_the_range(self) -> None:
        self.ns.ApplyWindowScale = lambda: None
        row = self.row()
        self.release(row, 92)
        self.assertEqual(90, self.db().windowScale)
        self.release(row, 60)
        self.assertEqual(75, self.db().windowScale)
        self.release(row, 130)
        self.assertEqual(100, self.db().windowScale)
        self.release(row, 87)
        self.assertEqual(85, self.db().windowScale)

    def test_the_window_is_not_resized_again_for_the_same_size(self) -> None:
        applied = []
        self.ns.ApplyWindowScale = lambda: applied.append(1)
        row = self.row()
        self.release(row, 80)
        self.release(row, 80)
        self.assertEqual(1, len(applied))

    def test_filling_the_list_from_the_saved_value_does_not_resize_the_window(self) -> None:
        applied = []
        self.ns.ApplyWindowScale = lambda: applied.append(1)
        self.db().windowScale = 90
        row = self.row()
        # While the list sets the slider from the saved value the game reports a change: it must not count as the player's.
        row.slider.svSyncing = True
        row.slider.GetValue = lambda self: 90
        row.slider.scripts.OnValueChanged(row.slider, 90)
        row.slider.svSyncing = False
        self.assertEqual([], applied)
        self.assertEqual("90%", row.value.text)

    def test_the_normal_window_and_compact_mode_keep_their_own_size(self) -> None:
        self.ns.ApplyWindowScale = lambda: None
        row = self.row()
        self.release(row, 90)
        self.assertEqual(90, self.db().windowScale)
        self.assertIsNone(self.db().windowScaleCompact)
        self.db().compactMode = True
        row = self.row()
        self.release(row, 80)
        self.assertEqual(80, self.db().windowScaleCompact)
        self.assertEqual(90, self.db().windowScale)  # the normal window's size is not touched

    def test_the_slider_shows_the_size_of_the_mode_the_window_is_in(self) -> None:
        self.db().windowScale = 90
        self.db().windowScaleCompact = 80
        self.assertEqual("90%", self.row().value.text)
        self.db().compactMode = True
        self.assertEqual("80%", self.row().value.text)

    def test_compact_mode_starts_with_the_size_of_the_normal_window(self) -> None:
        self.db().windowScale = 85
        self.db().compactMode = True
        self.assertEqual("85%", self.row().value.text)  # no jump when the mode is switched the first time

    def test_switching_the_mode_resizes_the_window_and_refreshes_the_slider(self) -> None:
        applied = []
        self.ns.ApplyWindowScale = lambda: applied.append(self.db().compactMode)
        self.ns.RequestStatAuditRefresh = lambda: None
        self.db().windowScale = 90
        self.db().windowScaleCompact = 80
        self.check()
        check = self.frame.optionsDrawerCard.bagIndicatorChecks["compactMode"]
        check.GetChecked = lambda self: True
        check.scripts.OnClick(check)
        self.assertEqual([True], applied)  # the window takes the size of Compact Mode
        self.assertEqual("80%", self.frame.optionsDrawerCard.sliderRows["windowScale"].value.text)

    def test_a_faint_line_marks_every_step(self) -> None:
        slider = self.row().slider
        self.assertEqual(6, len(list(slider.ticks.values())))  # 75, 80, 85, 90, 95, 100
        for tick in slider.ticks.values():
            self.assertEqual(1, tick._width)  # a thin line
            alpha = tick._color[4]
            self.assertLess(alpha, 0.6)  # faint

    def test_the_lines_sit_where_the_thumb_stops(self) -> None:
        row = self.row()
        slider = row.slider
        ticks = [slider.ticks[i] for i in range(1, 7)]
        xs = [t.points[len(t.points)][4] for t in ticks]
        width = self.frame.optionsDrawerCard.content._width - 2 - 2 * 10  # the slider is as wide as the row less its padding
        self.assertEqual(4, xs[0])  # half a thumb in from the left end
        self.assertEqual(width - 4, xs[-1])  # and from the right end
        gaps = {round(xs[i + 1] - xs[i], 6) for i in range(5)}
        self.assertEqual(1, len(gaps))  # evenly spaced: the steps are equal
        for tick in ticks:
            self.assertEqual("CENTER", tick.points[len(tick.points)][1])
            self.assertEqual("LEFT", tick.points[len(tick.points)][3])

    def test_the_slider_and_its_thumb_are_easy_to_grab(self) -> None:
        source = pathlib.Path("StatVerdict/UI/SV_OptionsDrawerPanel.lua").read_text(encoding="utf-8-sig")
        shared = pathlib.Path("StatVerdict/UI/SV_RightPanelMode.lua").read_text(encoding="utf-8-sig")
        self.assertIn("local SLIDER_HEIGHT = 16", shared)
        self.assertIn("thumb:SetSize(SLIDER_THUMB_WIDTH, SLIDER_HEIGHT)", shared)
        self.assertIn("ns.CreateStepSlider(group, {", source)  # the Options use the shared slider

    def test_the_slider_explains_itself(self) -> None:
        source = pathlib.Path("StatVerdict/UI/SV_OptionsDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("from 100% down to 75% (it starts at 85%). It works in the normal window and in Compact Mode, and each remembers its own size.", source)

    def test_the_manual_explains_the_size_slider(self) -> None:
        manual = pathlib.Path("StatVerdict/UI/SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("Window size", manual)


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class WindowScaleTests(unittest.TestCase):
    def setUp(self) -> None:
        from tools.tests.test_addon_lua import load_addon_file, new_runtime
        self.lua = new_runtime()
        self.ns = self.lua.table()
        self.lua.execute("UIParent = {}")
        load_addon_file(self.lua, self.ns, "UI/SV_WindowChrome.lua")
        self.g = self.lua.globals()
        self.g.StatVerdictDB = self.lua.table()

    def make_window(self, scale, left, top):
        make = self.lua.eval(
            "function(scale, left, top) local f = { scale = scale, left = left, top = top, points = {} } "
            "function f:GetScale() return self.scale end function f:SetScale(s) self.scale = s end "
            "function f:GetLeft() return self.left end function f:GetTop() return self.top end "
            "function f:ClearAllPoints() self.points = {} end "
            "function f:SetPoint(...) self.points[#self.points + 1] = { ... } end return f end")
        return make(scale, left, top)

    def test_the_size_is_85_percent_unless_saved(self) -> None:
        self.assertEqual(0.85, self.ns.GetWindowScale())
        self.g.StatVerdictDB = None
        self.assertEqual(0.85, self.ns.GetWindowScale())  # a new player gets the size the add-on was tuned on

    def test_compact_mode_starts_at_85_percent_too(self) -> None:
        self.g.StatVerdictDB.compactMode = True
        self.assertEqual(0.85, self.ns.GetWindowScale())

    def test_the_key_depends_on_the_mode(self) -> None:
        self.assertEqual("windowScale", self.ns.GetWindowScaleKey())
        self.g.StatVerdictDB.compactMode = True
        self.assertEqual("windowScaleCompact", self.ns.GetWindowScaleKey())
        self.g.StatVerdictDB = None
        self.assertEqual("windowScale", self.ns.GetWindowScaleKey())

    def test_each_mode_has_its_own_size_and_compact_follows_the_normal_one_until_chosen(self) -> None:
        self.g.StatVerdictDB.windowScale = 90
        self.assertEqual(0.9, self.ns.GetWindowScale())
        self.g.StatVerdictDB.compactMode = True
        self.assertEqual(0.9, self.ns.GetWindowScale())  # nothing chosen for Compact Mode yet
        self.g.StatVerdictDB.windowScaleCompact = 80
        self.assertEqual(0.8, self.ns.GetWindowScale())
        self.g.StatVerdictDB.compactMode = False
        self.assertEqual(0.9, self.ns.GetWindowScale())

    def test_the_saved_size_is_a_percent_between_75_and_100(self) -> None:
        self.g.StatVerdictDB.windowScale = 80
        self.assertEqual(0.8, self.ns.GetWindowScale())
        self.g.StatVerdictDB.windowScale = 10
        self.assertEqual(0.75, self.ns.GetWindowScale())  # never smaller than three quarters
        self.g.StatVerdictDB.windowScale = 500
        self.assertEqual(1.0, self.ns.GetWindowScale())

    def test_a_new_size_keeps_the_top_left_corner_where_it_was_on_the_screen(self) -> None:
        window = self.make_window(1.0, 400, 700)
        self.g.StatVerdictDB.windowScale = 80
        ratio, left, top = self.ns.ChangeWindowScale(window)
        self.assertEqual(0.8, window.scale)
        # In units of the smaller window the same corner has bigger numbers: 400 / 0.8, 700 / 0.8.
        self.assertEqual((500, 875), (left, top))
        point = window.points[1]
        self.assertEqual(("TOPLEFT", "BOTTOMLEFT", 500, 875), (point[1], point[3], point[4], point[5]))
        self.assertEqual(1.25, ratio)

    def test_going_back_to_100_percent_puts_it_back(self) -> None:
        window = self.make_window(0.8, 500, 875)
        self.g.StatVerdictDB.windowScale = 100
        ratio, left, top = self.ns.ChangeWindowScale(window)
        self.assertEqual((400, 700), (left, top))

    def test_nothing_happens_when_the_size_is_the_same(self) -> None:
        window = self.make_window(0.9, 100, 200)
        self.g.StatVerdictDB.windowScale = 90
        self.assertIsNone(self.ns.ChangeWindowScale(window))
        self.assertEqual([], list(window.points.values()))

    def test_the_saved_spot_of_the_side_panels_follows(self) -> None:
        window = self.make_window(1.0, 400, 700)
        self.g.StatVerdictDB.floatingPanelPos = self.lua.table(x=800, y=600)
        self.g.StatVerdictDB.windowScale = 80
        self.ns.ChangeWindowScale(window)
        spot = self.g.StatVerdictDB.floatingPanelPos
        self.assertEqual((1000, 750), (spot.x, spot.y))

    def test_a_window_without_a_position_yet_only_changes_size(self) -> None:
        window = self.make_window(1.0, None, None)
        self.g.StatVerdictDB.windowScale = 90
        ratio, left, top = self.ns.ChangeWindowScale(window)
        self.assertEqual(0.9, window.scale)
        self.assertIsNone(left)

    def test_the_main_window_takes_the_size_before_it_is_placed_and_fits_the_screen_in_its_own_units(self) -> None:
        source = pathlib.Path("StatVerdict/UI/SV_StatAudit.lua").read_text(encoding="utf-8-sig")
        create = source.index('CreateFrame("Frame", ns.UIName and ns.UIName("StatVerdictStatAuditFrame")')
        self.assertLess(source.index("frame:SetScale(ns.GetWindowScale())", create), source.index("ApplyUserWindowPosition(frame)", create))
        fit = source.index("local function FitWindowOnScreen")
        self.assertIn("local pw = (UIParent:GetWidth() or 0) / scale", source[fit:fit + 700])
        self.assertIn("function ns.ApplyWindowScale()", source)

    def test_floating_panels_are_kept_on_the_screen_in_the_windows_own_units(self) -> None:
        source = pathlib.Path("StatVerdict/UI/SV_DashboardLayout.lua").read_text(encoding="utf-8-sig")
        self.assertIn("screenW, screenH = screenW / scale, screenH / scale", source)
        self.assertIn("Layout.ClampFloatingPosition(x, y, width, height, RelativeScale(card))", source)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AutoHideOptionTests(unittest.TestCase):
    setUp = base.BisTooltipFeatureToggleTests.setUp
    check = base.BisTooltipFeatureToggleTests.check
    click = base.BisTooltipFeatureToggleTests.click
    db = base.BisTooltipFeatureToggleTests.db
    active = base.BisTooltipFeatureToggleTests.active

    def test_it_is_off_until_ticked_and_asks_for_a_redraw(self) -> None:
        self.db().compactMode = True
        refreshed = []
        self.ns.RequestStatAuditRefresh = lambda: refreshed.append(self.db().autoHideLeft)
        self.assertFalse(self.check("autoHideLeft").checked)
        self.assertTrue(self.click("autoHideLeft", True).checked)
        self.assertFalse(self.click("autoHideLeft", False).checked)
        self.assertEqual([True, False], refreshed)

    def test_it_sits_under_compact_mode_a_step_in(self) -> None:
        compact = self.check("compactMode")
        auto = self.check("autoHideLeft")
        last = lambda region: region.points[len(region.points)]
        self.assertGreater(last(auto.Text)[4], last(compact.Text)[4])  # indented like Gems and enchants under the tooltip
        self.assertEqual(last(compact.svRow)[5] - 36, last(auto.svRow)[5])  # directly below it (a row with a grey line is 36)
        self.assertIs(True, auto.svRow.connector.shown)  # hangs from a thin gold line
        self.assertIs(False, compact.svRow.connector.shown)

    def test_while_compact_mode_is_off_it_is_dimmed_and_does_nothing(self) -> None:
        check = self.check("autoHideLeft")
        self.assertFalse(self.active(check))
        self.assertLess(check._alpha, 1)
        self.assertFalse(self.click("autoHideLeft", True).checked)
        self.assertIsNone(self.db().autoHideLeft)  # the click was ignored
        row = check.svRow
        row.scripts.OnClick(row)
        self.assertIsNone(self.db().autoHideLeft)

    def test_it_cannot_stay_ticked_when_compact_mode_is_off(self) -> None:
        self.db().compactMode = True
        self.assertTrue(self.click("autoHideLeft", True).checked)
        self.db().compactMode = False
        check = self.check("autoHideLeft")
        self.assertFalse(check.checked)  # shown unticked
        self.assertFalse(self.active(check))
        self.assertEqual((0.55, 0.57, 0.62), tuple(check.Text._color[i] for i in (1, 2, 3)))  # grey, and the switch is off
        self.assertEqual((0.55, 0.57, 0.62), tuple(check.svRow.switch.knob._color[i] for i in (1, 2, 3)))

    def test_its_own_choice_is_kept_and_comes_back_with_compact_mode(self) -> None:
        self.db().compactMode = True
        self.click("autoHideLeft", True)
        self.db().compactMode = False
        self.check("autoHideLeft")
        self.assertIs(True, self.db().autoHideLeft)  # still saved
        self.db().compactMode = True
        self.assertTrue(self.check("autoHideLeft").checked)

    def test_ticking_compact_mode_unlocks_it_at_once(self) -> None:
        self.assertFalse(self.active(self.check("autoHideLeft")))
        self.click("compactMode", True)
        self.assertTrue(self.active(self.check("autoHideLeft")))
        self.click("compactMode", False)
        self.assertFalse(self.active(self.check("autoHideLeft")))

    def test_it_explains_that_it_belongs_to_compact_mode(self) -> None:
        self.assertIn("Compact Mode", self.check("autoHideLeft").svTip)
