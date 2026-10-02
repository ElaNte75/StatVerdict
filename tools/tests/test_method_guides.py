import unittest

from tools import method_guides as m


def page(section: str) -> str:
    return f"<h2>Stat Priorities</h2><p>{section}</p><h3>Stat Outline</h3>"


class PriorityTests(unittest.TestCase):
    def test_plain_chain_with_ge(self):
        out = m.parse_priority(page("Item Level > Haste > Vers >= Crit > Mastery"))
        self.assertEqual(out[0]["secondary"], [["haste"], ["versatility"], ["crit"], ["mastery"]])

    def test_ties_and_double_arrow(self):
        out = m.parse_priority(page("Generally speaking, it will be: Agility >> Crit = Vers > Mastery >> Haste."))
        self.assertEqual(out[0]["secondary"], [["crit", "versatility"], ["mastery"], ["haste"]])

    def test_hero_variants_keep_the_last_stat_of_the_first_one(self):
        out = m.parse_priority(page(
            "The stat priority for each Hero Talent are as follows: Deathbringer: Strength > Crit = Vers = Mastery > Haste "
            "San’layn: Strength > Haste > Crit = Vers = Mastery"))
        self.assertEqual([v["hero"] for v in out], ["Deathbringer", "San’layn"])
        self.assertEqual(out[0]["secondary"], [["crit", "versatility", "mastery"], ["haste"]])
        self.assertEqual(out[1]["secondary"], [["haste"], ["crit", "versatility", "mastery"]])

    def test_no_section_gives_nothing(self):
        self.assertEqual(m.parse_priority("<p>nothing here</p>"), [])


class TableTests(unittest.TestCase):
    def test_rows_are_read_with_item_id_note_and_source(self):
        html = ('<div role="tabpanel" id="overall_table"><table><tr><th>Slot</th></tr><tr><td>Head</td>'
                '<td><a href="https://www.wowhead.com/ptr/item=271875/x?bonus=1:2">Gaze Of The Watcher</a> (Tier Set)</td>'
                '<td>Ula&rsquo;tek (Catalyst)</td></tr></table></div>')
        rows = m.parse_tables(html)["overall"]
        self.assertEqual(rows[0]["itemId"], 271875)
        self.assertEqual(rows[0]["name"], "Gaze Of The Watcher")
        self.assertEqual(rows[0]["note"], "Tier Set")
        self.assertEqual(rows[0]["source"], "Ula’tek (Catalyst)")
        self.assertEqual(rows[0]["bonusIds"], "1:2")


if __name__ == "__main__":
    unittest.main()
