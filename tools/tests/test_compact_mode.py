"""Compact Mode (Options > Window): one stat table at a time, the panel buttons in a row under it, a shorter window."""
import unittest

from tools.tests.test_addon_lua import FRAME_STUB, LuaRuntime, load_addon_file, new_runtime

ROW_MODES = ["Guide", "Best in Slot", "Ranked Trinkets", "Options"]


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class CompactModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        for name in ("UI/SV_LayoutOffsets.lua", "UI/SV_RightPanelMode.lua", "UI/SV_WindowChrome.lua",
                     "UI/SV_DashboardLayout.lua", "UI/SV_SettingsPanel.lua"):
            load_addon_file(self.lua, self.ns, name)
        self.lua.globals().StatVerdictDB = self.lua.table()
        self.ns.EnsureLayoutDB()  # every player starts from the shipped layout
        self.frame = self.lua.eval("CreateFrame")()
        self.frame.GetLeft = self.lua.eval("function() return 100 end")
        self.frame.GetTop = self.lua.eval("function() return 900 end")
        self.layout = self.ns.StatVerdictDashboardLayout
        self.settings = self.ns.StatVerdictSettingsPanel
        self.mode = None
        self.ns.GetRightPanelMode = lambda: self.mode

    def db(self):
        return self.lua.globals().StatVerdictDB

    def apply(self, compact):
        self.db().compactMode = compact
        self.layout.Apply(self.frame, 4, self.lua.table())
        return self.frame.settingsCard

    @staticmethod
    def last(region):
        return region.points[len(region.points)]

    def set_off_spec(self, ready, viewing):
        selection = self.lua.table(secondaryEnabled=ready, secondarySpecID=270 if ready else 0)
        self.ns.GetSavedStatAuditSelection = lambda: selection
        self.ns.GetStatAuditActiveView = lambda: viewing

    # --- the mode itself ---------------------------------------------------------------------------------------------
    def test_it_is_off_unless_the_option_is_ticked(self) -> None:
        self.assertFalse(self.layout.IsCompact())
        self.db().compactMode = True
        self.assertTrue(self.layout.IsCompact())
        self.db().compactMode = False
        self.assertFalse(self.layout.IsCompact())

    def test_the_view_is_main_unless_an_off_spec_is_set_up_and_selected(self) -> None:
        self.assertIsNone(self.layout.CompactView())
        self.db().compactMode = True
        self.set_off_spec(False, "OFF")
        self.assertEqual("MAIN", self.layout.CompactView())  # nothing to show for an Off Spec that is not set up
        self.set_off_spec(True, "MAIN")
        self.assertEqual("MAIN", self.layout.CompactView())
        self.set_off_spec(True, "OFF")
        self.assertEqual("OFF", self.layout.CompactView())

    # --- the window ---------------------------------------------------------------------------------------------------
    def test_the_window_keeps_its_normal_height_without_compact_mode(self) -> None:
        self.apply(False)
        self.assertEqual(449, self.frame._height)

    def test_the_compact_window_is_much_shorter(self) -> None:
        self.apply(True)
        self.assertEqual(281, self.frame._height)

    def test_both_cards_are_as_high_as_the_taller_one_needs(self) -> None:
        self.apply(True)
        height = self.layout.GetSetupCardHeight(self.frame)
        self.assertEqual(242, height)
        self.assertEqual(height, self.layout.GetStatsCardHeight(self.frame))
        self.assertLessEqual(self.settings.GetCompactHeight(), height)  # the left card's content fits

    def test_the_compact_window_is_as_wide_as_the_normal_one(self) -> None:
        self.apply(False)
        normal = self.frame._width
        self.apply(True)
        self.assertEqual(normal, self.frame._width)

    def test_an_open_side_panel_does_not_change_the_compact_window(self) -> None:
        self.apply(True)
        height, width = self.frame._height, self.frame._width
        self.mode = "weights"
        self.apply(True)
        self.assertEqual(height, self.frame._height)
        self.assertEqual(width, self.frame._width)

    def test_a_docked_panel_widens_the_normal_window_but_not_the_compact_one(self) -> None:
        self.apply(False)
        closed = self.frame._width
        self.mode = "weights"
        self.apply(False)
        self.assertGreater(self.frame._width, closed)  # docked: the window grows by the panel
        self.mode = None
        self.apply(True)
        compact_closed = self.frame._width
        self.mode = "weights"
        self.apply(True)
        self.assertEqual(compact_closed, self.frame._width)  # floating: the window stays as it is

    def test_going_back_to_normal_restores_the_height(self) -> None:
        self.apply(True)
        self.apply(False)
        self.assertEqual(449, self.frame._height)

    def test_the_button_row_sits_inside_the_stats_card_with_room_below(self) -> None:
        self.apply(True)
        left, top, width, height = self.layout.GetCompactButtonRow(self.frame)
        card_visible_bottom = 33 + self.layout.GetStatsCardHeight(self.frame) - 5  # the card's own bottom padding
        row_bottom = -top + height
        self.assertEqual(236, -top)  # 33 + 5 + the table's 190 + a gap of 8 under it
        self.assertEqual(10, card_visible_bottom - row_bottom)  # the card's outline is 10 below the buttons
        self.assertLessEqual(card_visible_bottom, self.frame._height - 6)  # inside the window

    def test_the_view_button_has_room_above_the_left_cards_bottom_edge(self) -> None:
        self.set_off_spec(True, "MAIN")
        card = self.apply(True)
        button = card.compactViewButton
        button_bottom = -self.last(button)[5] + button._height  # from the window's top
        card_bottom = 33 + self.layout.GetSetupCardHeight(self.frame) - 5  # the card's visible bottom edge
        self.assertGreaterEqual(card_bottom - button_bottom, 10)

    def test_the_title_has_no_checkbox_in_compact_mode(self) -> None:
        import pathlib
        source = pathlib.Path("StatVerdict/UI/SV_StatAudit.lua").read_text(encoding="utf-8-sig")
        start = source.index("local function SetSpecTitle(frame, which, text)")
        body = source[start:start + 900]
        self.assertIn("layout.IsCompact()", body)
        self.assertLess(body.index("layout.IsCompact()"), body.index("ns.SpecTitleText("))

    # --- the buttons --------------------------------------------------------------------------------------------------
    def compact_buttons(self, card=None):
        found = []
        for key in ("weightsDrawerButton", "bisDrawerButton", "trinketsDrawerButton", "optionsDrawerButton",
                    "manualDrawerButton"):
            button = self.frame["compact_" + key]
            found.append((key, button))
        return found

    def test_compact_mode_shows_four_buttons_in_one_row_and_no_manual_button(self) -> None:
        card = self.apply(True)
        shown = {key: button for key, button in self.compact_buttons() if button is not None and button.shown}
        self.assertEqual(
            sorted(["weightsDrawerButton", "bisDrawerButton", "trinketsDrawerButton", "optionsDrawerButton"]),
            sorted(shown))
        self.assertIsNone(self.frame["compact_manualDrawerButton"])
        order = ["weightsDrawerButton", "bisDrawerButton", "trinketsDrawerButton", "optionsDrawerButton"]
        self.assertEqual(["Guide", "Best in Slot", "Ranked Trinkets", "Options"],
                         [shown[key].label.text for key in order])
        left, top, width, height = self.layout.GetCompactButtonRow(self.frame)
        points = [self.last(shown[key]) for key in order]
        self.assertEqual([top] * 4, [p[5] for p in points])  # one row
        xs = [p[4] for p in points]
        self.assertEqual(left, xs[0])
        self.assertEqual(sorted(xs), xs)  # in order, left to right
        button_width = shown[order[0]]._width
        self.assertEqual([button_width] * 4, [shown[key]._width for key in order])
        self.assertLessEqual(xs[-1] + button_width, left + width)  # the row ends inside the stats card
        self.assertGreaterEqual(left + width - (xs[-1] + button_width), 0)
        self.assertEqual(height, shown[order[0]]._height)

    def test_the_vertical_buttons_and_the_panels_title_are_hidden_in_compact_mode(self) -> None:
        card = self.apply(False)
        for key in ("bisDrawerButton", "trinketsDrawerButton", "weightsDrawerButton", "optionsDrawerButton",
                    "manualDrawerButton"):
            self.assertIs(True, card[key].shown, key)
        card = self.apply(True)
        for key in ("bisDrawerButton", "trinketsDrawerButton", "weightsDrawerButton", "optionsDrawerButton",
                    "manualDrawerButton"):
            self.assertIs(False, card[key].shown, key)
        self.assertIs(False, card._svTitleHosts.optionsTitle.shown)

    def test_going_back_to_normal_brings_the_vertical_buttons_back_and_hides_the_row(self) -> None:
        self.apply(True)
        card = self.apply(False)
        self.assertIs(True, card.manualDrawerButton.shown)
        self.assertIs(True, card._svTitleHosts.optionsTitle.shown)
        for key, button in self.compact_buttons():
            if button is not None:
                self.assertIs(False, button.shown, key)

    def test_a_compact_button_opens_its_panel(self) -> None:
        self.apply(True)
        toggled = []
        self.ns.ToggleRightPanelMode = lambda mode: toggled.append(mode)
        for key in ("weightsDrawerButton", "bisDrawerButton", "trinketsDrawerButton", "optionsDrawerButton"):
            button = self.frame["compact_" + key]
            button.scripts.OnClick(button)
        self.assertEqual(["weights", "bis", "trinkets", "options"], toggled)

    # --- the view button ----------------------------------------------------------------------------------------------
    def test_the_view_button_is_hidden_without_an_off_spec(self) -> None:
        self.set_off_spec(False, "MAIN")
        card = self.apply(True)
        self.assertIs(False, card.compactViewButton.shown)

    def test_the_view_button_says_what_a_click_does(self) -> None:
        self.set_off_spec(True, "MAIN")
        card = self.apply(True)
        button = card.compactViewButton
        self.assertIs(True, button.shown)
        self.assertEqual("Show Off Spec", button.label.text)
        chosen = []
        self.ns.SetStatAuditActiveView = lambda view: chosen.append(view)
        button.scripts.OnClick(button)
        self.set_off_spec(True, "OFF")
        card = self.apply(True)
        self.assertEqual("Show Main Spec", card.compactViewButton.label.text)
        card.compactViewButton.scripts.OnClick(card.compactViewButton)
        self.assertEqual(["OFF", "MAIN"], chosen)  # a click asks for the other spec

    def colour(self, fontString):
        c = fontString._color
        return (c[1], c[2], c[3])

    def test_the_heading_of_the_build_in_view_is_gold_and_the_other_white(self) -> None:
        gold, white = (1.0, 0.82, 0.0), (1.0, 1.0, 1.0)
        self.set_off_spec(True, "MAIN")
        card = self.apply(True)
        self.assertEqual(gold, self.colour(card.title))  # Main Spec Build
        self.assertEqual(white, self.colour(card.offTitle))  # Off Spec Build
        self.set_off_spec(True, "OFF")
        card = self.apply(True)
        self.assertEqual(white, self.colour(card.title))
        self.assertEqual(gold, self.colour(card.offTitle))

    def test_without_an_off_spec_the_main_heading_is_the_one_in_gold(self) -> None:
        self.set_off_spec(False, "OFF")
        card = self.apply(True)
        self.assertEqual((1.0, 0.82, 0.0), self.colour(card.title))
        self.assertEqual((1.0, 1.0, 1.0), self.colour(card.offTitle))

    def test_outside_compact_mode_both_headings_stay_gold(self) -> None:
        self.set_off_spec(True, "OFF")
        self.apply(True)
        card = self.apply(False)
        self.assertEqual((1.0, 0.82, 0.0), self.colour(card.title))
        self.assertEqual((1.0, 0.82, 0.0), self.colour(card.offTitle))

    def test_the_view_button_is_on_the_same_line_as_the_panel_buttons(self) -> None:
        self.set_off_spec(True, "MAIN")
        card = self.apply(True)
        button = card.compactViewButton
        _, row_top, _, row_height = self.layout.GetCompactButtonRow(self.frame)
        self.assertEqual(row_top, self.last(button)[5])  # the same top
        self.assertEqual(row_height, button._height)  # the same height
        guide = self.frame.compact_weightsDrawerButton
        self.assertEqual(self.last(guide)[5], self.last(button)[5])
        self.assertEqual(guide._height, button._height)

    def test_the_view_button_is_below_the_dropdowns_and_inside_the_left_card(self) -> None:
        self.set_off_spec(True, "MAIN")
        card = self.apply(True)
        bottom = self.settings.GetCompactDropdownBottom()
        self.assertEqual(185, bottom)
        _, row_top, _, row_height = self.layout.GetCompactButtonRow(self.frame)
        card_top = -(33 + 5)  # the left card's visible top
        self.assertGreater(-row_top - (-card_top), bottom)  # below the lowest dropdown
        self.assertLessEqual(self.settings.GetCompactHeight(), self.layout.GetSetupCardHeight(self.frame))

    def test_the_view_button_is_not_shown_outside_compact_mode(self) -> None:
        self.set_off_spec(True, "MAIN")
        self.apply(True)
        card = self.apply(False)
        self.assertIs(False, card.compactViewButton.shown)

    # --- the table that is shown --------------------------------------------------------------------------------------
    def fake_frame_with_tables(self):
        make = self.lua.eval(
            "function(name) local f = { name = name, points = {}, shown = true } "
            "function f:Hide() self.shown = false end function f:Show() self.shown = true end "
            "function f:ClearAllPoints() self.points = {} end "
            "function f:SetPoint(...) self.points[#self.points + 1] = { ... } end "
            "function f:GetPoint(i) local p = self.points[i] if not p then return nil end return p[1], p[2], p[3], p[4], p[5] end "
            "function f:GetWidth() return self.w or 300 end function f:GetHeight() return self.h or 160 end "
            "function f:SetSize(w, h) self.w, self.h = w, h end return f end")
        frame = make("window")
        frame.statProgressTableCard = make("mainScreen")
        frame.offStatProgressTableCard = make("offScreen")
        frame.subtitle = make("mainTitle")
        frame.secondarySubtitle = make("offTitle")
        frame.offAvgProgressText = make("offAvg")
        frame._svTitleBoxes = self.lua.table(**{"stats.specTitle": make("mainBox"), "stats.offSpecTitle": make("offBox")})
        frame.statProgressTableCard.SetPoint(frame.statProgressTableCard, "TOPLEFT", "card", "TOPLEFT", 8, -30)
        frame._svTitleBoxes["stats.specTitle"].SetPoint(frame._svTitleBoxes["stats.specTitle"], "TOPLEFT", "card", "TOPLEFT", 11, -8)
        frame.offStatProgressTableCard.SetPoint(frame.offStatProgressTableCard, "TOPLEFT", "card", "TOPLEFT", 8, -221)
        frame._svTitleBoxes["stats.offSpecTitle"].SetPoint(frame._svTitleBoxes["stats.offSpecTitle"], "TOPLEFT", "card", "TOPLEFT", 12, -190)
        hidden = []
        self.ns.HideSpecSelectButton = lambda which: hidden.append(which)
        return frame, hidden

    def test_the_main_view_hides_the_off_spec_table_and_its_title(self) -> None:
        self.db().compactMode = True
        self.set_off_spec(True, "MAIN")
        frame, hidden = self.fake_frame_with_tables()
        self.layout.ApplyCompactViews(frame)
        self.assertIs(False, frame.offStatProgressTableCard.shown)
        self.assertIs(False, frame.secondarySubtitle.shown)
        self.assertIs(False, frame._svTitleBoxes["stats.offSpecTitle"].shown)
        self.assertIs(False, frame.offAvgProgressText.shown)
        self.assertIs(True, frame.statProgressTableCard.shown)
        self.assertEqual(["OFF"], hidden)

    def test_the_off_view_hides_the_main_table_and_puts_the_off_table_in_its_place(self) -> None:
        self.db().compactMode = True
        self.set_off_spec(True, "OFF")
        frame, hidden = self.fake_frame_with_tables()
        self.layout.ApplyCompactViews(frame)
        self.assertIs(False, frame.statProgressTableCard.shown)
        self.assertIs(False, frame.subtitle.shown)
        self.assertIs(False, frame._svTitleBoxes["stats.specTitle"].shown)
        self.assertEqual(["MAIN"], hidden)
        main = frame.statProgressTableCard.points[1]
        off = frame.offStatProgressTableCard.points[1]
        self.assertEqual((main[4], main[5]), (off[4], off[5]))  # the Off Spec table where the Main Spec table is
        box = frame._svTitleBoxes
        self.assertEqual(box["stats.specTitle"].points[1][5], box["stats.offSpecTitle"].points[1][5])
        self.assertEqual((frame.statProgressTableCard.GetWidth(frame.statProgressTableCard),
                          frame.statProgressTableCard.GetHeight(frame.statProgressTableCard)),
                         (frame.offStatProgressTableCard.w, frame.offStatProgressTableCard.h))

    def test_the_main_title_comes_back_when_the_view_goes_back_to_main(self) -> None:
        self.db().compactMode = True
        self.set_off_spec(True, "OFF")
        frame, _ = self.fake_frame_with_tables()
        self.layout.ApplyCompactViews(frame)
        self.assertIs(False, frame.subtitle.shown)
        self.set_off_spec(True, "MAIN")
        self.layout.ApplyCompactViews(frame)
        self.assertIs(True, frame.subtitle.shown)  # the Main Spec title is there again

    def test_the_main_title_comes_back_when_compact_mode_is_turned_off(self) -> None:
        self.db().compactMode = True
        self.set_off_spec(True, "OFF")
        frame, _ = self.fake_frame_with_tables()
        self.layout.ApplyCompactViews(frame)
        self.db().compactMode = False
        self.layout.ApplyCompactViews(frame)
        self.assertIs(True, frame.subtitle.shown)

    def test_the_off_table_inside_sits_exactly_where_the_main_table_inside_sits(self) -> None:
        self.db().compactMode = True
        self.set_off_spec(True, "OFF")
        frame, _ = self.fake_frame_with_tables()
        make = self.lua.eval(
            "function(rel, x, y, w, h) local f = { points = { { 'TOPLEFT', rel, 'TOPLEFT', x, y } }, w = w, h = h } "
            "function f:ClearAllPoints() self.points = {} end "
            "function f:SetPoint(...) self.points[#self.points + 1] = { ... } end "
            "function f:GetPoint(i) local p = self.points[i] if not p then return nil end return p[1], p[2], p[3], p[4], p[5] end "
            "function f:GetWidth() return self.w end function f:GetHeight() return self.h end "
            "function f:SetSize(w, h) self.w, self.h = w, h end return f end")
        frame.svMainStatContentHost = make(frame.statProgressTableCard, 5, -7, 383, 152)  # the Main table's own offset: 1 right, 3 down
        frame.svOffStatContentHost = make(frame.offStatProgressTableCard, 4, -4, 385, 152)
        self.layout.ApplyCompactViews(frame)
        point = frame.svOffStatContentHost.points[1]
        self.assertEqual((5, -7), (point[4], point[5]))
        self.assertTrue(self.lua.eval("function(a, b) return rawequal(a, b) end")(point[2], frame.offStatProgressTableCard))
        self.assertEqual((383, 152), (frame.svOffStatContentHost.w, frame.svOffStatContentHost.h))

    def test_nothing_is_changed_without_compact_mode(self) -> None:
        self.db().compactMode = False
        self.set_off_spec(True, "OFF")
        frame, hidden = self.fake_frame_with_tables()
        self.layout.ApplyCompactViews(frame)
        self.assertIs(True, frame.statProgressTableCard.shown)
        self.assertIs(True, frame.offStatProgressTableCard.shown)
        self.assertEqual([], hidden)
        self.assertEqual(-221, frame.offStatProgressTableCard.points[1][5])

    # --- side panels --------------------------------------------------------------------------------------------------
    # --- floating side panels -----------------------------------------------------------------------------------------
    def new_panel(self, width=320):
        self.apply(True)
        frame = self.frame
        frame.statProgressCard = self.lua.eval("CreateFrame")()
        card = self.lua.eval("CreateFrame")()
        card.preferredWidth = width
        self.lua.execute("UIParent = { GetWidth = function() return 1920 end, GetHeight = function() return 1080 end }")
        return frame, card

    def anchor(self, frame, card):
        self.layout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, 0, 0, None)

    def test_in_compact_mode_a_side_panel_is_anchored_alone_to_the_screen_at_its_full_height(self) -> None:
        frame, card = self.new_panel()
        frame.GetRight = self.lua.eval("function() return 600 end")
        self.anchor(frame, card)
        self.assertEqual(1, len(list(card.points.keys())))  # one anchor: it can be moved
        point = self.last(card)
        self.assertEqual("TOPLEFT", point[1])
        self.assertEqual("BOTTOMLEFT", point[3])
        self.assertEqual(390, card._height)  # as high as a docked panel in the normal window
        self.assertEqual(390, self.layout.GetFloatingPanelHeight())

    def test_it_opens_beside_the_window_on_the_right_level_with_its_top(self) -> None:
        frame, card = self.new_panel()
        frame.GetRight = self.lua.eval("function() return 600 end")
        self.anchor(frame, card)
        point = self.last(card)
        self.assertEqual(606, point[4])  # 6 right of the window
        self.assertEqual(900 - 10, point[5])  # level with the top of the cards

    def test_it_opens_on_the_left_when_there_is_no_room_on_the_right(self) -> None:
        frame, card = self.new_panel(width=320)
        frame.GetRight = self.lua.eval("function() return 1800 end")
        frame.GetLeft = self.lua.eval("function() return 1300 end")
        self.anchor(frame, card)
        self.assertEqual(1300 - 6 - 320, self.last(card)[4])  # the window's left edge minus the gap and the panel's width

    def test_a_saved_position_is_used_and_kept_on_the_screen(self) -> None:
        frame, card = self.new_panel()
        self.db().floatingPanelPos = self.lua.table(x=400, y=700)
        self.anchor(frame, card)
        self.assertEqual((400, 700), (self.last(card)[4], self.last(card)[5]))
        self.db().floatingPanelPos = self.lua.table(x=5000, y=-200)
        self.anchor(frame, card)
        left, top = self.last(card)[4], self.last(card)[5]
        self.assertEqual(1920 - 320, left)
        self.assertEqual(390, top)  # clamped so the whole panel is on the screen

    def test_dragging_a_panel_saves_where_it_was_dropped(self) -> None:
        frame, card = self.new_panel()
        self.anchor(frame, card)
        moved = []
        card.StartMoving = lambda self: moved.append("start")
        card.StopMovingOrSizing = lambda self: moved.append("stop")
        card.GetLeft = self.lua.eval("function() return 250 end")
        card.GetTop = self.lua.eval("function() return 640 end")
        card.scripts.OnDragStart(card)
        card.scripts.OnDragStop(card)
        self.assertEqual(["start", "stop"], moved)
        self.assertEqual((250, 640), (self.db().floatingPanelPos.x, self.db().floatingPanelPos.y))

    def test_a_floating_panel_has_a_close_button_in_the_bottom_right_corner_and_is_movable(self) -> None:
        frame, card = self.new_panel()
        self.anchor(frame, card)
        self.assertTrue(card.svFloating)
        close = card.svCloseButton
        self.assertIs(True, close.shown)
        self.assertEqual("Close", close.label.text)
        point = self.last(close)
        self.assertEqual("BOTTOMRIGHT", point[1])
        self.assertEqual((-14, 12), (point[4], point[5]))
        self.assertEqual((70, 24), (close._width, close._height))
        closed = []
        self.ns.SetRightPanelMode = lambda mode: closed.append(mode)
        close.scripts.OnClick(close)
        self.assertEqual([None], closed)

    def test_no_panel_has_an_x_button_in_a_corner(self) -> None:
        import pathlib
        source = pathlib.Path("StatVerdict/UI/SV_DashboardLayout.lua").read_text(encoding="utf-8-sig")
        self.assertNotIn("UIPanelCloseButton", source)
        frame, card = self.new_panel()
        self.anchor(frame, card)
        for point in card.svCloseButton.points.values():
            self.assertNotEqual("TOPRIGHT", point[1])
            self.assertNotEqual("TOPLEFT", point[1])

    def test_the_manual_button_of_options_sits_left_of_that_close_button(self) -> None:
        frame, card = self.new_panel()
        self.anchor(frame, card)
        size = self.layout.FLOAT_BUTTON
        close_right = -size.margin
        manual_right = -(size.margin + size.width + size.gap)
        self.assertEqual(-14, close_right)
        self.assertEqual(-90, manual_right)
        self.assertEqual(close_right, manual_right + size.width + size.gap)  # the two buttons touch with one gap between

    def test_the_manual_text_stops_above_the_text_size_slider_and_the_close_button(self) -> None:
        import pathlib
        source = pathlib.Path("StatVerdict/UI/SV_ManualDrawerPanel.lua").read_text(encoding="utf-8-sig")
        self.assertIn("local SCROLL_BOTTOM_PAD = SIZE_ROW_BOTTOM + SIZE_ROW_HEIGHT + 8", source)
        size = self.layout.FLOAT_BUTTON
        pad = 12 + 34 + 8  # the slider's distance from the bottom, its height and some air
        self.assertLessEqual(size.bottom + size.height, pad)  # the Close button is lower than the text stops

    # --- titles: "StatVerdict Guide" -----------------------------------------------------------------------------------
    def test_a_panel_title_names_the_addon_only_in_compact_mode(self) -> None:
        self.db().compactMode = False
        self.assertEqual("Guide", self.ns.PanelTitleText("Guide"))
        self.db().compactMode = True
        self.assertEqual("StatVerdict Guide", self.ns.PanelTitleText("Guide"))
        for name in ("Best in Slot", "Ranked Trinkets", "Options", "Manual"):
            self.assertEqual("StatVerdict " + name, self.ns.PanelTitleText(name))

    def test_a_floating_panel_shows_the_titled_chip_and_a_docked_one_the_plain_title(self) -> None:
        frame, card = self.new_panel()
        chip = self.lua.eval("CreateFrame")()
        chip.label = self.lua.eval("CreateFrame")()
        chip.svBaseText = "Guide"
        card.svTabTitleChip = chip
        self.anchor(frame, card)
        self.assertEqual("StatVerdict Guide", chip.label.text)
        self.apply(False)
        self.anchor(frame, card)
        self.assertEqual("Guide", chip.label.text)

    def chip_for(self, kind, view, compact):
        self.db().compactMode = compact
        self.set_off_spec(True, view)
        parent = self.lua.eval("CreateFrame")()
        parent.svTitlePanelKind = kind
        self.ns.PlaceMsOsTitleChip(parent, kind, kind)
        return parent.svViewToggle

    def test_best_in_slot_and_trinkets_have_a_two_line_title_in_their_own_window(self) -> None:
        self.assertEqual("StatVerdict Best in Slot\nMain Spec", self.chip_for("bis", "MAIN", True).label.text)
        self.assertEqual("StatVerdict Best in Slot\nOff Spec", self.chip_for("bis", "OFF", True).label.text)
        self.assertEqual("StatVerdict Ranked Trinkets\nMain Spec", self.chip_for("trinkets", "MAIN", True).label.text)
        self.assertEqual("StatVerdict Ranked Trinkets\nOff Spec", self.chip_for("trinkets", "OFF", True).label.text)

    def test_their_title_chip_is_higher_for_the_second_line(self) -> None:
        normal = self.chip_for("bis", "MAIN", False)
        self.assertEqual("Main Spec Best in Slot", normal.label.text)  # docked: as before, one line
        self.assertEqual(20, normal._height)  # the shipped layout makes the chip 4 lower than the default 24
        floating = self.chip_for("bis", "MAIN", True)
        self.assertEqual(20 + self.layout.FLOAT_TITLE_EXTRA, floating._height)  # 36: room for two lines
        self.assertEqual(16, self.layout.FLOAT_TITLE_EXTRA)

    def test_the_floating_panel_leaves_room_for_the_close_button(self) -> None:
        self.assertEqual(12 + 24 + 8, self.layout.GetFloatingBand())

    def test_a_panel_that_knows_its_height_gets_it(self) -> None:
        frame, card = self.new_panel()
        card.svFloatingHeight = 470
        self.anchor(frame, card)
        self.assertEqual(470, card._height)
        card.svFloatingHeight = None
        self.anchor(frame, card)
        self.assertEqual(390, card._height)

    def test_best_in_slot_and_trinkets_work_out_their_own_height(self) -> None:
        import pathlib
        source = pathlib.Path("StatVerdict/UI/SV_BisProgressPanel.lua").read_text(encoding="utf-8-sig")
        self.assertEqual(3, source.count("FitToWindowLayout(card, "))  # its definition, the trinkets list and the Best in Slot list
        self.assertIn("local available = cardHeight - ContentTopInset(card) - ContentBottomInset(card)", source)

    def test_the_title_chip_button_hands_the_drag_on_to_the_panel(self) -> None:
        frame, card = self.new_panel()
        card.svViewToggle = self.lua.eval("CreateFrame")()
        self.anchor(frame, card)
        moved = []
        card.StartMoving = lambda self: moved.append("start")
        card.svViewToggle.scripts.OnDragStart(card.svViewToggle)
        self.assertEqual(["start"], moved)

    def test_back_to_normal_the_panel_is_docked_again_without_close_button(self) -> None:
        frame, card = self.new_panel()
        self.anchor(frame, card)
        self.apply(False)
        self.anchor(frame, card)
        self.assertFalse(card.svFloating)
        self.assertIs(False, card.svCloseButton.shown)
        self.assertTrue(self.lua.eval("function(a, b) return rawequal(a, b) end")(self.last(card)[2], frame.statProgressCard))

    def test_a_side_panel_follows_the_stats_card_without_compact_mode(self) -> None:
        self.apply(False)
        frame = self.frame
        frame.statProgressCard = self.lua.eval("CreateFrame")()
        card = self.lua.eval("CreateFrame")()
        self.layout.AnchorAfterPreviousCard(card, frame.statProgressCard, frame, 0, 0, None)
        for point in card.points.values():
            self.assertTrue(self.lua.eval("function(a, b) return rawequal(a, b) end")(point[2], frame.statProgressCard))


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AutoHideLeftTests(unittest.TestCase):
    """Compact Mode with "Auto-hide the left side": a thin strip stands for the left column; the window is narrower."""

    setUp = CompactModeTests.setUp
    db = CompactModeTests.db
    last = staticmethod(CompactModeTests.last)
    set_off_spec = CompactModeTests.set_off_spec

    def apply(self, compact, hide):
        self.db().compactMode = compact
        self.db().autoHideLeft = hide
        self.layout.Apply(self.frame, 4, self.lua.table())
        return self.frame.settingsCard

    def test_it_only_applies_in_compact_mode_and_when_ticked(self) -> None:
        self.db().autoHideLeft = True
        self.db().compactMode = False
        self.assertFalse(self.layout.IsLeftAutoHidden())
        self.db().compactMode = True
        self.assertTrue(self.layout.IsLeftAutoHidden())
        self.db().autoHideLeft = False
        self.assertFalse(self.layout.IsLeftAutoHidden())

    def test_the_window_makes_room_only_for_the_strip(self) -> None:
        self.apply(True, False)
        wide = self.frame._width
        real = self.layout.GetSetupCardWidth(self.frame)
        self.apply(True, True)
        self.assertEqual(wide - (real - 22), self.frame._width)
        self.assertEqual(22, self.layout.GetSetupCardWidth(self.frame))
        edge = self.layout.GetRightEdgeInset()
        self.assertEqual(6 + 22 + self.layout.GetStatsCardWidth(self.frame) + edge, self.frame._width)  # strip + table

    def test_the_height_does_not_change(self) -> None:
        self.apply(True, False)
        height = self.frame._height
        self.apply(True, True)
        self.assertEqual(height, self.frame._height)

    def test_the_left_card_keeps_its_own_width_when_it_opens(self) -> None:
        card = self.apply(True, False)
        width = card._width
        card = self.apply(True, True)
        self.assertEqual(width, card._width)

    def test_the_strip_shows_and_the_left_card_is_folded_away(self) -> None:
        card = self.apply(True, True)
        strip = self.frame.svLeftStrip
        self.assertIs(True, strip.shown)
        self.assertIs(False, card.shown)
        left, top, width, height = self.layout.GetLeftStripRect(self.frame)
        point = self.last(strip)
        self.assertEqual((left, top), (point[4], point[5]))
        self.assertEqual((width, height), (strip._width, strip._height))
        self.assertEqual(self.layout.GetSetupCardHeight(self.frame) - 10, height)  # as high as the cards

    def test_the_strip_is_as_high_as_the_other_card_and_starts_at_the_same_top(self) -> None:
        self.apply(True, True)
        _, top, _, _ = self.layout.GetLeftStripRect(self.frame)
        self.assertEqual(-38, top)

    def test_the_mouse_on_the_strip_opens_the_column_over_the_table(self) -> None:
        card = self.apply(True, True)
        strip = self.frame.svLeftStrip
        strip.scripts.OnEnter(strip)
        self.assertIs(True, self.frame.svLeftOpen)
        self.assertIs(True, card.shown)
        self.assertGreater(card._frameLevel if card._frameLevel is not None else 31, 30)

    def test_it_stays_open_while_a_pass_of_the_layout_runs(self) -> None:
        card = self.apply(True, True)
        self.frame.svLeftStrip.scripts.OnEnter(self.frame.svLeftStrip)
        card = self.apply(True, True)
        self.assertIs(True, card.shown)

    def mouse(self, over_strip=False, over_card=False, menu=False):
        strip = self.frame.svLeftStrip
        strip.IsMouseOver = lambda self: over_strip
        self.frame.settingsCard.IsMouseOver = lambda self: over_card
        self.ns.IsChipDropdownOpen = lambda: menu
        return strip

    def test_it_folds_away_a_moment_after_the_mouse_leaves(self) -> None:
        self.apply(True, True)
        strip = self.frame.svLeftStrip
        strip.scripts.OnEnter(strip)
        strip = self.mouse()
        strip.scripts.OnUpdate(strip, 0.2)
        self.assertIs(True, self.frame.svLeftOpen)  # not at once
        strip.scripts.OnUpdate(strip, 0.2)
        self.assertIs(False, self.frame.svLeftOpen)
        self.assertIs(False, self.frame.settingsCard.shown)

    def test_it_stays_open_while_the_mouse_is_on_the_column_or_a_menu_is_open(self) -> None:
        self.apply(True, True)
        strip = self.frame.svLeftStrip
        strip.scripts.OnEnter(strip)
        for kwargs in ({"over_card": True}, {"over_strip": True}, {"menu": True}):
            strip = self.mouse(**kwargs)
            for _ in range(5):
                strip.scripts.OnUpdate(strip, 0.2)
            self.assertIs(True, self.frame.svLeftOpen, kwargs)

    def test_a_short_visit_resets_the_wait(self) -> None:
        self.apply(True, True)
        strip = self.frame.svLeftStrip
        strip.scripts.OnEnter(strip)
        strip = self.mouse()
        strip.scripts.OnUpdate(strip, 0.3)
        strip = self.mouse(over_card=True)
        strip.scripts.OnUpdate(strip, 0.3)
        strip = self.mouse()
        strip.scripts.OnUpdate(strip, 0.3)
        self.assertIs(True, self.frame.svLeftOpen)

    def test_turning_it_off_brings_the_column_back_and_hides_the_strip(self) -> None:
        self.apply(True, True)
        card = self.apply(True, False)
        self.assertIs(False, self.frame.svLeftStrip.shown)
        self.assertIs(True, card.shown)

    def test_without_compact_mode_nothing_is_folded(self) -> None:
        self.apply(True, True)
        card = self.apply(False, True)
        self.assertIs(True, card.shown)
        self.assertIs(False, self.frame.svLeftStrip.shown)
        self.assertEqual(449, self.frame._height)

    def test_the_window_is_never_narrower_than_its_title_bar(self) -> None:
        self.apply(True, True)
        narrow = self.frame._width
        for name in ("title", "versionLabel", "tierLabel"):
            label = self.lua.eval("CreateFrame")()
            label.GetStringWidth = self.lua.eval("function() return 150 end")
            self.frame[name] = label
        need = self.ns.GetTitleBarMinWidth(self.frame)
        self.assertEqual(12 + 150 + 8 + 150 + 10 + 150 + 10 + 22 + 6, need)
        self.assertGreater(need, narrow)
        self.apply(True, True)
        self.assertEqual(need, self.frame._width)

    FAKE = (
        "function(w) local f = { points = {}, shown = true, w = w or 300 } "
        "function f:Hide() self.shown = false end function f:Show() self.shown = true end "
        "function f:ClearAllPoints() self.points = {} end "
        "function f:SetPoint(...) self.points[#self.points + 1] = { ... } end "
        "function f:SetText(t) self.text = t end function f:SetFont(...) self.font = { ... } end "
        "function f:SetTextColor(r, g, b) self.color = { r, g, b } end "
        "function f:GetWidth() return self.w end function f:SetWidth(w) self.w = w end "
        "function f:GetStringWidth() return self.sw or 52 end function f:GetParent() return self.parent end "
        "function f:SetParent(p) self.parent = p end "
        "function f:CreateFontString() return Fake(0) end return f end"
    )

    def tag_frame(self, view="OFF"):
        self.db().compactMode = True
        self.db().autoHideLeft = True
        self.set_off_spec(True, view)
        self.lua.execute("Fake = " + self.FAKE)
        fake = self.lua.globals().Fake
        card = fake(300)
        frame = fake(300)
        frame.subtitle = fake(375)
        frame.subtitle.parent = card
        frame.subtitle.sw = 210
        frame.secondarySubtitle = fake(375)
        frame.secondarySubtitle.parent = card
        frame.secondarySubtitle.sw = 180
        fitted = []
        panel = self.lua.table()
        panel.FitSpecTitle = lambda f: fitted.append("main")
        panel.FitOffSpecTitle = lambda f: fitted.append("off")
        self.ns.StatVerdictStatProgressPanel = panel
        return frame, fitted

    def test_a_small_tag_names_the_spec_after_the_title_while_the_left_column_is_folded_away(self) -> None:
        frame, fitted = self.tag_frame("OFF")
        self.layout.UpdateSpecTag(frame, "OFF")
        tag = frame.svSpecTag
        self.assertEqual("(Off Spec)", tag.text)
        self.assertIs(True, tag.shown)
        self.assertEqual(9, tag.font[2])  # a small font, whatever the title's size
        self.assertEqual(180 + 6, tag.points[1][4])  # right after the end of the title's text
        self.assertEqual(["off"], fitted)  # the title was fitted again, with room for the tag

    def test_the_main_title_gets_the_main_tag(self) -> None:
        frame, fitted = self.tag_frame("MAIN")
        self.layout.UpdateSpecTag(frame, "MAIN")
        self.assertEqual("(Main Spec)", frame.svSpecTag.text)
        self.assertEqual(210 + 6, frame.svSpecTag.points[1][4])
        self.assertEqual(["main"], fitted)

    def test_the_title_makes_room_for_the_tag(self) -> None:
        frame, _ = self.tag_frame("MAIN")
        self.layout.UpdateSpecTag(frame, "MAIN")
        self.assertEqual(375 - (52 + 6), frame.subtitle.w)  # the tag is 52 wide plus the gap

    def test_the_tag_is_hidden_when_the_left_column_is_in_sight(self) -> None:
        frame, _ = self.tag_frame("OFF")
        self.layout.UpdateSpecTag(frame, "OFF")
        self.db().autoHideLeft = False
        self.layout.UpdateSpecTag(frame, "OFF")
        self.assertIs(False, frame.svSpecTag.shown)

    def test_no_tag_without_compact_mode(self) -> None:
        frame, _ = self.tag_frame("OFF")
        self.layout.UpdateSpecTag(frame, "OFF")
        self.db().compactMode = False
        self.layout.UpdateSpecTag(frame, self.layout.CompactView())
        self.assertIs(False, frame.svSpecTag.shown)

    def test_the_title_text_itself_is_not_changed(self) -> None:
        import pathlib
        source = pathlib.Path("StatVerdict/UI/SV_StatAudit.lua").read_text(encoding="utf-8-sig")
        self.assertNotIn("TitleWithSpec", source)
        layout = pathlib.Path("StatVerdict/UI/SV_DashboardLayout.lua").read_text(encoding="utf-8-sig")
        self.assertIn("Layout.UpdateSpecTag(frame, view)", layout)  # the tag is placed in every pass, after the titles were fitted

    def test_a_dropdown_menu_reports_when_it_is_open(self) -> None:
        import pathlib
        source = pathlib.Path("StatVerdict/UI/SV_ChipDropdown.lua").read_text(encoding="utf-8-sig")
        self.assertIn("function ns.IsChipDropdownOpen()", source)


    # --- the folded-away column opens above everything ---------------------------------------------------------------
    def test_the_opened_left_column_is_on_a_layer_above_the_table(self) -> None:
        make = self.lua.eval(
            "function() local f = { shown = true } "
            "function f:SetFrameStrata(s) self.strata = s end function f:SetFrameLevel(l) self.level = l end "
            "function f:Show() self.shown = true end function f:Hide() self.shown = false end "
            "function f:GetFrameLevel() return 5 end function f:GetFrameStrata() return 'HIGH' end return f end")
        frame, card = make(), make()
        frame.settingsCard = card
        self.layout.SetLeftOpen(frame, True)
        self.assertEqual("DIALOG", card.strata)
        self.assertEqual(35, card.level)
        self.layout.SetLeftOpen(frame, False)
        self.assertEqual("HIGH", card.strata)  # back on the window's own layer
        self.assertIs(False, card.shown)


if __name__ == "__main__":
    unittest.main()
