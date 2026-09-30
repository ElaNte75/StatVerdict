import unittest

from tools import stat_split_probe as probe


class SplitMathTests(unittest.TestCase):
    def test_moves_keep_the_total_and_respect_the_floor(self) -> None:
        base = {"crit": 88.0, "haste": 1380.0, "mastery": 1148.0, "versatility": 694.0}
        state = {stat: 0 for stat in probe.STATS}
        moves = probe.candidate_moves(state, base, 100)
        self.assertTrue(all(sum(move.values()) == 0 for move in moves))
        # crit has only 88 rating: it can not give 100, so 9 of the 12 moves remain
        self.assertEqual(9, len(moves))
        self.assertTrue(all(move["crit"] >= 0 for move in moves))

    def test_variant_lines_name_and_values(self) -> None:
        deltas = {"crit": -100, "haste": 100, "mastery": 0, "versatility": 0}
        self.assertEqual("d_c-100_h+100_m+0_v+0", probe.variant_name(deltas))
        self.assertEqual(
            ['profileset."d_c-100_h+100_m+0_v+0"+=enchant_crit_rating=-100',
             'profileset."d_c-100_h+100_m+0_v+0"+=enchant_haste_rating=100'],
            probe.variant_lines(deltas),
        )

    def test_extra_lines_come_after_the_players(self) -> None:
        from tools.simc_stat_engine import render_profiles
        from tools.spec_catalog import SPEC_BY_KEY
        text, _ = render_profiles(SPEC_BY_KEY["MAGE_FIRE"], [{"items": {}, "runTalentLoadout": ""}],
                                  extra_lines=('profileset."x"+=enchant_crit_rating=1',), talents_optional=True)
        self.assertTrue(text.rstrip().endswith('profileset."x"+=enchant_crit_rating=1'))


if __name__ == "__main__":
    unittest.main()
