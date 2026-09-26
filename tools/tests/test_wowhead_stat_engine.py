from __future__ import annotations

import unittest

from tools.wowhead_stat_engine import assign_hybrids, parse_tooltip_stats, tooltip_query


SAMPLE_TOOLTIP = """
<table><tr><td>Relentless Rider's Crown<br>Item Level 289<br>
Upgrade Level: Myth 6/6<br>Head Plate<br>244 Armor<br>
+124 [Strength or Intellect]<br>+2,326 Stamina<br>+ 107 Haste<br>+ 57 Mastery
</td></tr></table>
"""


class WowheadStatEngineTests(unittest.TestCase):
    def test_parse_hybrid_and_secondaries(self) -> None:
        parsed = parse_tooltip_stats(SAMPLE_TOOLTIP)
        self.assertEqual(289, parsed["itemLevel"])
        self.assertEqual(244, parsed["armor"])
        self.assertEqual(2326, parsed["stats"]["stamina"])
        self.assertEqual(107, parsed["stats"]["haste"])
        self.assertEqual(57, parsed["stats"]["mastery"])
        self.assertEqual(124, parsed["hybrids"]["strength or intellect"])

    def test_hybrid_follows_spec_primary(self) -> None:
        parsed = parse_tooltip_stats(SAMPLE_TOOLTIP)
        frost = assign_hybrids(parsed, "strength")
        resto = assign_hybrids(parsed, "intellect")
        self.assertEqual(124, frost["strength"])
        self.assertNotIn("intellect", frost)
        self.assertEqual(124, resto["intellect"])
        self.assertNotIn("strength", resto)

    def test_tooltip_query_encodes_bonus_gems_enchants(self) -> None:
        query = tooltip_query(
            {
                "itemId": 249970,
                "bonusIds": [4786, 12806],
                "gemIds": [240894],
                "enchantIds": [7991],
            }
        )
        self.assertEqual("4786:12806", query["bonus"])
        self.assertEqual("240894", query["gems"])
        self.assertEqual("7991", query["ench"])


if __name__ == "__main__":
    unittest.main()
