"""Upgrade-track swap mapping, tested on a real subset of the game's DB2
tables (tools/tests/fixtures/wago_db2_upgrade_tracks, exported from
wago.tools on 2026-09-29: ItemBonusListGroupEntry groups 608-612, 614-618
and 630, with their ItemBonus and ItemScalingConfig rows)."""
from __future__ import annotations

import csv
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from tools.upgrade_tracks import (
    TrackSwap,
    build_track_swap,
    collect_bonus_ids,
    parse_track_groups,
    swap_bonus_ids,
)

FIXTURES = Path(__file__).parent / "fixtures" / "wago_db2_upgrade_tracks"


def rows(table: str) -> list[dict[str, str]]:
    with open(FIXTURES / f"{table}.csv", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


GROUPS = parse_track_groups(rows("ItemBonus"), rows("ItemBonusListGroupEntry"), rows("ItemScalingConfig"))


class ParseTrackGroupsTests(unittest.TestCase):
    def test_season_two_myth_track_ranks_and_item_levels(self) -> None:
        myth = GROUPS[618]
        self.assertEqual("myth", myth.track)
        self.assertEqual(
            [318, 321, 324, 328, 331, 334, 337, 340, 344],
            [myth.ranks[seq].item_level for seq in sorted(myth.ranks)],
        )
        # Ranks 7-9 carry the extension flag (Flags bit 1); 6/6 is the last normal rank.
        self.assertEqual(6, myth.max_rank)
        self.assertEqual(12854, myth.ranks[6].bonus_id)
        self.assertEqual(13848, myth.ranks[9].bonus_id)

    def test_track_names_come_from_the_type_34_code(self) -> None:
        self.assertEqual(
            {608: "adventurer", 609: "veteran", 610: "champion", 611: "hero", 612: "myth",
             614: "adventurer", 615: "veteran", 616: "champion", 617: "hero", 618: "myth", 630: "myth"},
            {gid: group.track for gid, group in GROUPS.items() if group.track},
        )

    def test_a_group_without_item_levels_has_none(self) -> None:
        self.assertIsNone(GROUPS[630].ranks[1].item_level)

    def test_a_myth_id_of_a_family_without_item_levels_lands_on_the_current_season(self) -> None:
        swap = build_track_swap({12897}, GROUPS)
        self.assertEqual({"myth": {12897: 12854}, "hero": {12897: 12846}, "champion": {12897: 12838}}, swap.swap)
        self.assertEqual({"hero": [], "champion": []}, swap.unmapped)
        self.assertEqual({"myth": 334, "hero": 321, "champion": 308}, swap.item_levels)

    def test_max_rank_levels_of_each_season_two_track(self) -> None:
        self.assertEqual(
            {"adventurer": 282, "veteran": 295, "champion": 308, "hero": 321, "myth": 334},
            {GROUPS[g].track: GROUPS[g].max_item_level for g in (614, 615, 616, 617, 618)},
        )


class BuildTrackSwapTests(unittest.TestCase):
    def test_every_myth_rank_lands_on_the_six_of_six_of_each_tier(self) -> None:
        swap = build_track_swap({12854, 13848, 12850}, GROUPS)
        # Tier 3 (myth): the extension rank (344) and a 2/6 id both become 6/6; 6/6 itself needs no entry.
        self.assertEqual({13848: 12854, 12850: 12854}, swap.swap["myth"])
        self.assertEqual({12854: 12846, 13848: 12846, 12850: 12846}, swap.swap["hero"])
        self.assertEqual({12854: 12838, 13848: 12838, 12850: 12838}, swap.swap["champion"])
        self.assertEqual({"myth": 334, "hero": 321, "champion": 308}, swap.item_levels)
        self.assertEqual({"hero": [], "champion": []}, swap.unmapped)

    def test_season_one_ids_land_on_the_current_season(self) -> None:
        swap = build_track_swap({12806, 13654}, GROUPS)
        self.assertEqual({12806: 12854, 13654: 12854}, swap.swap["myth"])
        self.assertEqual({12806: 12846, 13654: 12846}, swap.swap["hero"])
        self.assertEqual({12806: 12838, 13654: 12838}, swap.swap["champion"])

    def test_a_tier_never_raises_an_item_above_its_listed_track(self) -> None:
        swap = build_track_swap({12846, 12841}, GROUPS)  # Hero 6/6 and Hero 1/6
        self.assertEqual({}, swap.swap["myth"])
        self.assertEqual({12841: 12846}, swap.swap["hero"])
        self.assertEqual({12846: 12838, 12841: 12838}, swap.swap["champion"])

    def test_lower_tracks_and_non_track_ids_are_not_raised(self) -> None:
        swap = build_track_swap({12838, 12833, 6652, 8960}, GROUPS)
        self.assertEqual({"myth": {}, "hero": {}, "champion": {12833: 12838}}, swap.swap)
        self.assertEqual({"hero": [], "champion": []}, swap.unmapped)

    def test_item_levels_are_the_current_season(self) -> None:
        for observed in ({12806, 12854}, {12806}):
            self.assertEqual({"myth": 334, "hero": 321, "champion": 308}, build_track_swap(observed, GROUPS).item_levels)

    def test_a_family_whose_levels_do_not_overlap_is_left_unmapped(self) -> None:
        groups = parse_track_groups(rows("ItemBonus"), rows("ItemBonusListGroupEntry"), rows("ItemScalingConfig"))
        # Break the Hero track's item levels: the pairing check must refuse it.
        for rank in groups[617].ranks.values():
            rank.item_level = (rank.item_level or 0) + 1
        swap = build_track_swap({12854, 13848}, groups)
        self.assertEqual({13848: 12854}, swap.swap["myth"])  # Myth needs no pairing
        self.assertEqual({}, swap.swap["hero"])
        self.assertEqual({}, swap.swap["champion"])
        self.assertEqual({"hero": [12854, 13848], "champion": [12854, 13848]}, swap.unmapped)
        self.assertEqual({"myth": 334}, swap.item_levels)


class SwapBonusIdsTests(unittest.TestCase):
    swap = build_track_swap({12854, 12846, 13848}, GROUPS)

    def test_replaces_the_track_id_and_keeps_the_rest(self) -> None:
        self.assertEqual(([6652, 12846, 13334], True, False), swap_bonus_ids([6652, 12854, 13334], "hero", self.swap))

    def test_an_item_without_a_higher_track_id_is_untouched(self) -> None:
        self.assertEqual(([8960, 12838], False, False), swap_bonus_ids([8960, 12838], "champion", self.swap))
        self.assertEqual(([12846], False, False), swap_bonus_ids([12846], "hero", self.swap))

    def test_a_known_higher_track_id_without_a_mapping_is_a_miss(self) -> None:
        swap = TrackSwap({"hero": {}, "champion": {}}, {}, {"hero": [12854], "champion": [12854]}, {12854: "myth"})
        self.assertEqual(([12854], False, True), swap_bonus_ids([12854], "hero", swap))


class CollectBonusIdsTests(unittest.TestCase):
    def test_collects_gear_trinket_and_catalyst_bonus_ids(self) -> None:
        specs = {
            "DEATHKNIGHT_frost": {
                "gear": {"value": {"all": {"raid": [
                    {"itemId": 1, "slot": "Head", "bonusIDs": [12854]},
                    {"itemId": 2, "slot": "Chest", "catalyst": {"itemId": 3, "bonusIDs": [13848, 13847]}},
                ]}}},
                "trinkets": {"value": {"all": {"all": [{"itemId": 9, "tier": "S", "bonusIDs": [12806]}]}}},
                "enchants": {"value": {"all": {"all": {"Head": [{"id": 99999, "bonusIDs": [1]}]}}}},
            }
        }
        self.assertEqual({12854, 13848, 13847, 12806}, collect_bonus_ids(specs))


class FetchRetryTests(unittest.TestCase):
    """The weekly run once wrote its data without track levels because one read timed out."""

    class Response:
        def __init__(self, text: str) -> None:
            self.text = text

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> None:
            return None

        def read(self) -> bytes:
            return self.text.encode("utf-8")

    def test_a_timeout_is_retried_and_then_succeeds(self) -> None:
        import socket
        from unittest.mock import patch

        from tools import upgrade_tracks

        calls = [socket.timeout("timed out"), socket.timeout("timed out"), self.Response("A,B\n1,2\n")]

        def fake_urlopen(*_args, **_kwargs):
            outcome = calls.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch("tools.upgrade_tracks.urllib.request.urlopen", side_effect=fake_urlopen), \
                patch("tools.upgrade_tracks.time.sleep") as sleep, redirect_stderr(io.StringIO()):
            rows = upgrade_tracks.fetch_db2_rows("ItemBonus")
        self.assertEqual([{"A": "1", "B": "2"}], rows)
        self.assertEqual(2, sleep.call_count)

    def test_it_gives_up_after_the_last_attempt(self) -> None:
        import socket
        from unittest.mock import patch

        from tools import upgrade_tracks

        with patch("tools.upgrade_tracks.urllib.request.urlopen", side_effect=socket.timeout("timed out")) as opener, \
                patch("tools.upgrade_tracks.time.sleep"), redirect_stderr(io.StringIO()):
            with self.assertRaises(OSError):
                upgrade_tracks.fetch_db2_rows("ItemBonus", attempts=3)
        self.assertEqual(3, opener.call_count)


if __name__ == "__main__":
    unittest.main()
