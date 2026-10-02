import unittest

from tools import method_targets as t


class GearTests(unittest.TestCase):
    def test_rows_become_slots_with_numbered_rings_and_trinkets(self):
        rows = [{"slot": "Head", "itemId": 1}, {"slot": "Cloak", "itemId": 2}, {"slot": "Ring", "itemId": 3},
                {"slot": "Ring", "itemId": 4}, {"slot": "Trinket #1", "itemId": 5}, {"slot": "Trinket", "itemId": 6},
                {"slot": "Weapon", "itemId": 7}, {"slot": "Mystery", "itemId": 8}, {"slot": "Neck", "itemId": None}]
        entries, problems = t.gear_entries(rows)
        self.assertEqual([e["slot"] for e in entries],
                         ["Head", "Back", "Finger 1", "Finger 2", "Trinket 1", "Trinket 2", "Main Hand"])
        self.assertTrue(all(e["ilvl"] == t.SEASON_MAX_ILVL for e in entries))
        self.assertEqual(len(problems), 2)

    def test_secondary_gem_follows_the_hero_note_else_the_first_plain_one(self):
        gems = {"primary": 9, "others": [{"itemId": 1, "name": "a", "note": "San'layn"},
                                         {"itemId": 2, "name": "b", "note": "Deathbringer"}]}
        self.assertEqual(t.pick_secondary(gems, "Deathbringer")[0], 2)
        self.assertEqual(t.pick_secondary(gems, "San’layn")[0], 1)
        plain = {"others": [{"itemId": 5, "name": "x", "note": ""}, {"itemId": 6, "name": "y", "note": ""}]}
        self.assertEqual(t.pick_secondary(plain, None)[0], 5)
        self.assertEqual(t.pick_secondary({"others": []}, None)[0], None)


if __name__ == "__main__":
    unittest.main()
