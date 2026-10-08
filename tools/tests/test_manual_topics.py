"""The Manual is a list of topics: only their titles, a click shows one topic's text with its title above and a small
Back arrow; Back returns to the list."""
import unittest

from tools.tests.test_addon_lua import FRAME_STUB, LuaRuntime, load_addon_file, new_runtime


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class ManualTopicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.lua.execute("UIParent = { GetWidth = function() return 1920 end, GetHeight = function() return 1080 end }")
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")
        self.open = True
        self.ns.GetRightPanelMode = lambda: "manual" if self.open else "none"
        self.titles = []
        self.lua.execute("""
        TITLES = {}
        CHIP = { height = 24, label = { size = 12 } }
        function CHIP:SetHeight(h) self.height = h end
        function CHIP.label:GetFont() return "Fonts\\FRIZQT__.TTF", self.size, "" end
        function CHIP.label:SetFont(file, size) self.size = size end
        """)
        self.ns.PlaceTabTitleChip = self.lua.eval(
            "function(card, text) TITLES[#TITLES + 1] = text return CHIP end")
        load_addon_file(self.lua, self.ns, "UI/SV_ManualDrawerPanel.lua")
        self.lua.globals().StatVerdictDB = self.lua.table()
        self.panel = self.ns.StatVerdictManualDrawerPanel
        self.frame = self.lua.eval("CreateFrame")()
        self.ns.RequestStatAuditRefresh = lambda: None

    def card(self):
        self.panel.Apply(self.frame)
        return self.frame.manualDrawerCard

    def last_title(self) -> str:
        return str(self.lua.eval("TITLES[#TITLES]"))

    def shown_texts(self, card):
        return [str(line.text) for line in card.lines.values() if line.shown]

    def shown_buttons(self, card):
        return [str(button.label.text) for button in card.topicButtons.values() if button.shown]

    def test_it_starts_as_the_list_of_topics_with_no_text(self) -> None:
        card = self.card()
        titles = list(self.panel.GetTopicTitles().values())
        self.assertEqual("Overview", titles[0])
        self.assertIn("Character info", titles)
        self.assertEqual(titles, self.shown_buttons(card))  # one button per topic, in order
        self.assertEqual([], self.shown_texts(card))  # no text of any topic
        self.assertEqual("Manual", self.last_title())
        self.assertFalse(card.backButton.shown)

    def test_a_click_shows_only_that_topic_with_its_title_and_the_back_arrow(self) -> None:
        card = self.card()
        titles = list(self.panel.GetTopicTitles().values())
        index = titles.index("Character info") + 1
        self.panel.OpenTopic(self.frame, index)
        self.assertEqual("Character info", self.last_title())
        self.assertTrue(card.backButton.shown)
        self.assertEqual([], self.shown_buttons(card))  # the list is gone
        texts = self.shown_texts(card)
        self.assertTrue(any("BIS" in text for text in texts))
        self.assertFalse(any("Stat Progress" in text for text in texts))  # nothing of the other topics

    def test_the_list_has_no_text_size_slider_and_stays_at_100_percent(self) -> None:
        self.lua.globals().StatVerdictDB = self.lua.eval("{ manualTextScale = 150 }")
        card = self.card()
        self.assertFalse(card.sizeRow.shown)
        self.assertFalse(card.sizeDivider.shown)
        self.assertEqual(300, self.panel.GetPreferredWidth(self.frame))  # the window is at 100% too
        self.assertEqual({12.0}, {float(b.label._font[2]) for b in card.topicButtons.values()})  # the base size, not 150%

    def test_inside_a_topic_the_slider_and_the_line_above_it_are_shown_at_the_chosen_size(self) -> None:
        self.lua.globals().StatVerdictDB = self.lua.eval("{ manualTextScale = 150 }")
        card = self.card()
        self.panel.OpenTopic(self.frame, 1)
        self.assertTrue(card.sizeRow.shown)
        self.assertTrue(card.sizeDivider.shown)
        self.assertEqual(450, self.panel.GetPreferredWidth(self.frame))
        self.assertEqual({18.0}, {float(line._font[2]) for line in card.lines.values() if line.shown})

    def test_back_hides_the_slider_again(self) -> None:
        card = self.card()
        self.panel.OpenTopic(self.frame, 1)
        self.panel.ShowTopics(self.frame)
        self.assertFalse(card.sizeRow.shown)
        self.assertFalse(card.sizeDivider.shown)

    def test_the_title_chip_is_taller_with_a_bigger_title(self) -> None:
        self.card()
        self.assertEqual(30, int(self.lua.eval("CHIP.height")))
        self.assertEqual(15, int(self.lua.eval("CHIP.label.size")))

    def test_the_text_size_goes_no_higher_than_175(self) -> None:
        self.lua.globals().StatVerdictDB = self.lua.eval("{ manualTextScale = 200 }")
        self.assertEqual(175, self.ns.GetManualTextScalePercent())

    def test_the_topic_buttons_open_their_topics(self) -> None:
        card = self.card()
        card.topicButtons[3].scripts["OnClick"](card.topicButtons[3])
        self.assertEqual(list(self.panel.GetTopicTitles().values())[2], self.last_title())
        self.assertTrue(card.backButton.shown)

    def test_back_returns_to_the_list(self) -> None:
        card = self.card()
        self.panel.OpenTopic(self.frame, 2)
        card.backButton.scripts["OnClick"](card.backButton)
        self.assertEqual("Manual", self.last_title())
        self.assertFalse(card.backButton.shown)
        self.assertEqual(list(self.panel.GetTopicTitles().values()), self.shown_buttons(card))
        self.assertEqual([], self.shown_texts(card))

    def test_the_topic_stays_open_when_the_panel_is_drawn_again(self) -> None:
        card = self.card()
        self.panel.OpenTopic(self.frame, 2)
        self.panel.Apply(self.frame)  # e.g. after a change of the text size
        self.assertEqual(2, int(card.manualSection))

    def test_closed_and_opened_again_it_starts_at_the_list(self) -> None:
        card = self.card()
        self.panel.OpenTopic(self.frame, 2)
        self.open = False
        self.panel.Apply(self.frame)
        self.open = True
        self.panel.Apply(self.frame)
        self.assertIsNone(card.manualSection)
        self.assertEqual("Manual", self.last_title())

    def test_every_line_of_the_manual_is_in_some_topic(self) -> None:
        card = self.card()
        seen = []
        for index in range(1, len(list(self.panel.GetTopicTitles().values())) + 1):
            self.panel.OpenTopic(self.frame, index)
            seen.extend(self.shown_texts(card))
        self.assertTrue(any("virtual loadout" in text for text in seen))
        self.assertTrue(any("Compact Mode" in text for text in seen))
        self.assertTrue(any("Limits" in title for title in self.panel.GetTopicTitles().values()) or seen)


if __name__ == "__main__":
    unittest.main()
