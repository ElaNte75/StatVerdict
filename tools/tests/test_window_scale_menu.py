"""A dropdown menu is not part of the window; it takes the window's size so it matches its dropdown."""
import pathlib
import unittest


class MenuScaleTests(unittest.TestCase):
    def test_the_menu_takes_the_scale_of_the_dropdown_it_hangs_from(self):
        source = pathlib.Path("StatVerdict/UI/SV_ChipDropdown.lua").read_text(encoding="utf-8-sig")
        start = source.index("menu:SetSize(width, height)")
        body = source[start:start + 700]
        self.assertIn("menu:SetScale(own / screen)", body)
        self.assertLess(body.index("menu:SetScale(own / screen)"), body.index('menu:SetPoint("TOPLEFT", dropdown'))


if __name__ == "__main__":
    unittest.main()
