"""Every tab's title is one chip as wide as its card, with the same margin each side and the text centred."""
from __future__ import annotations

import unittest

from tools.tests.test_addon_lua import FRAME_STUB, load_addon_file, new_runtime


class TabTitleChipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lua = new_runtime()
        self.lua.execute(FRAME_STUB)
        self.ns = self.lua.table()
        load_addon_file(self.lua, self.ns, "UI/SV_RightPanelMode.lua")
        self.card = self.lua.eval("CreateFrame")()

    def points(self, frame) -> list[tuple]:
        return [tuple(frame.points[i][j] for j in (1, 3, 4, 5)) for i in range(1, len(frame.points) + 1)]

    def test_the_chip_spans_the_card_with_equal_margins(self) -> None:
        chip = self.ns.PlaceTabTitleChip(self.card, "Guide")
        self.assertEqual([("TOPLEFT", "TOPLEFT", 12, -12), ("TOPRIGHT", "TOPRIGHT", -12, -12)], self.points(chip))
        self.assertEqual(24, chip._height)

    def test_the_text_is_centred_and_is_the_cards_title(self) -> None:
        chip = self.ns.PlaceTabTitleChip(self.card, "Features")
        self.assertEqual("Features", chip.label.text)
        self.assertEqual("CENTER", chip.label.points[1][1])
        self.assertEqual("CENTER", chip.label.points[1][3])

    def test_asking_again_reuses_the_chip_and_places_it_the_same(self) -> None:
        first = self.ns.PlaceTabTitleChip(self.card, "Manual")
        second = self.ns.PlaceTabTitleChip(self.card, "Manual")
        self.assertTrue(self.lua.eval("rawequal")(first, second))
        # (the stub frame keeps old anchors; what counts is the last pair)
        self.assertEqual([("TOPLEFT", "TOPLEFT", 12, -12), ("TOPRIGHT", "TOPRIGHT", -12, -12)], self.points(second)[-2:])

    def test_it_is_not_a_button(self) -> None:
        chip = self.ns.PlaceTabTitleChip(self.card, "Guide")
        self.assertIs(False, chip._mouse)

    def test_best_in_slot_and_ranked_trinkets_use_the_same_span(self) -> None:
        for kind in ("bis", "trinkets"):
            card = self.lua.eval("CreateFrame")()
            self.ns.PlaceMsOsTitleChip(card, kind, kind)
            chip = card.svViewToggle
            self.assertEqual([("TOPLEFT", "TOPLEFT", 12, -12), ("TOPRIGHT", "TOPRIGHT", -12, -12)], self.points(chip), kind)
            self.assertEqual(24, chip._height, kind)


if __name__ == "__main__":
    unittest.main()
