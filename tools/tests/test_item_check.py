from __future__ import annotations

import json
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tools.item_check import (
    DEFAULT_PROFILE,
    QUEST_CANDIDATES,
    Candidate,
    build_candidates,
    check_items,
    delta,
    dps_result,
    main,
    parse_profile,
    render_markdown,
    render_sim_input,
    sanitize_profile,
    write_outputs,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "item_check_export.simc"

# DPS bonus of an item id in the fake SimC (single target, cleave).
BONUS = {
    2001: (500.0, 800.0),  # Spare Beads: neck upgrade
    2011: (-100.0, -50.0),  # Spare Band
    280377: (250.0, 300.0),
}
# Replacing this equipped ring loses more than the other one.
SLOT_PENALTY = {"finger1": 300.0, "finger2": 0.0}


class FakeSimc:
    """Stands in for SimulationCraft: reads the rendered input and returns a
    json2-shaped report. No binary, no network."""

    def __init__(self, fail_ids=(), hide_ids=()):
        self.fail_ids = set(fail_ids)
        self.hide_ids = set(hide_ids)
        self.inputs: list[str] = []

    def __call__(self, text: str) -> dict:
        self.inputs.append(text)
        cleave = "desired_targets=3" in text
        base = 30000.0 if cleave else 20000.0
        dps = base
        gear = {}
        for slot, item_id in re.findall(r"^([a-z_0-9]+)=,id=(\d+)", text, re.M):
            item_id = int(item_id)
            if item_id in self.fail_ids:
                raise RuntimeError(f"SimulationCraft failed with exit 1: bad item {item_id}")
            if item_id in BONUS:
                dps += BONUS[item_id][1 if cleave else 0]
                dps -= SLOT_PENALTY.get(slot, 0.0)
            if item_id in self.hide_ids:
                continue
            gear[slot] = {
                "name": f"item_{item_id}",
                "encoded_item": f"{slot}=,id={item_id}",
                "ilevel": 272 if item_id in (280377, 2001) else 250,
                "agility": 101,
                "haste_rating": 72,
            }
        return {
            "sim": {
                "players": [
                    {
                        "name": "Tester",
                        "gear": gear,
                        "collected_data": {
                            "dps": {"mean": dps, "mean_std_dev": 30.0},
                            "buffed_stats": {
                                "attribute": {"agility": 3000},
                                "stats": {
                                    "crit_rating": 500, "haste_rating": 700,
                                    "mastery_rating": 600, "versatility_rating": 300,
                                    "crit_pct": 20.5, "haste_pct": 18.2,
                                    "mastery_pct": 40.1, "versatility_pct": 3.3,
                                },
                                "resources": {},
                            },
                        },
                    }
                ]
            }
        }


def fixture_profile():
    return parse_profile(FIXTURE.read_text(encoding="utf-8"))


class ParseProfileTests(unittest.TestCase):
    def test_actor_equipped_and_bags(self):
        profile = fixture_profile()
        self.assertEqual(profile.class_token, "shaman")
        self.assertEqual(
            profile.actor_lines,
            ["level=90", "race=draenei", "role=attack", "spec=enhancement", "talents=AAAA"],
        )
        self.assertEqual(list(profile.equipped), ["head", "neck", "finger1", "finger2", "trinket1", "trinket2", "main_hand"])
        self.assertEqual(profile.equipped["head"].name, "Old Helm")
        self.assertEqual(profile.equipped["head"].ilevel, 250)
        self.assertEqual(profile.equipped["finger1"].fields, ",id=1011,enchant_id=8020,gem_id=240899,bonus_id=6652")
        # Only "Gear from Bags"; the Weekly Reward block is not a candidate.
        self.assertEqual([(b.slot, b.item_id, b.name) for b in profile.bags], [
            ("neck", 2001, "Spare Beads"), ("finger1", 2011, "Spare Band"), ("main_hand", 2031, "Spare Knife"),
        ])

    def test_sanitize_drops_identifying_lines_and_keeps_gear(self):
        text = sanitize_profile(FIXTURE.read_text(encoding="utf-8"))
        for forbidden in ("Somebody", "region", "server", "professions", "omnium", "Checksum", "currencies", "BBBB"):
            self.assertNotIn(forbidden, text)
        self.assertIn('shaman="Tester"', text)
        self.assertIn("talents=AAAA", text)
        self.assertIn("finger1=,id=1011,enchant_id=8020,gem_id=240899,bonus_id=6652", text)
        self.assertIn("# main_hand=,id=2031,crafted_stats=32/36,crafting_quality=5", text)
        again = parse_profile(text)
        original = fixture_profile()
        self.assertEqual(again.actor_lines, original.actor_lines)
        self.assertEqual({k: v.fields for k, v in again.equipped.items()}, {k: v.fields for k, v in original.equipped.items()})
        self.assertEqual([b.fields for b in again.bags], [b.fields for b in original.bags])

    def test_repo_profile_is_sanitized_and_parses(self):
        text = DEFAULT_PROFILE.read_text(encoding="utf-8")
        for forbidden in ("Electroq", "silvermoon", "region=", "server=", "professions", "omnium", "Checksum", "currencies"):
            self.assertNotIn(forbidden, text)
        profile = parse_profile(text)
        self.assertEqual(profile.actor_name, "Tester")
        self.assertIn("spec=enhancement", profile.actor_lines)
        self.assertEqual(len(profile.equipped), 16)
        self.assertEqual(len(profile.bags), 11)

    def test_candidates_include_quest_items_and_bags(self):
        candidates = build_candidates(fixture_profile())
        self.assertEqual(candidates[: len(QUEST_CANDIDATES)], list(QUEST_CANDIDATES))
        bag = {c.item_id: c for c in candidates[len(QUEST_CANDIDATES):]}
        self.assertEqual(bag[2011].target_slots, ("finger1", "finger2"))
        self.assertEqual(bag[2031].target_slots, ("main_hand",))
        self.assertEqual(bag[2001].name, "Spare Beads")
        trinket = next(c for c in candidates if c.item_id == 280377)
        self.assertEqual(trinket.target_slots, ("trinket1", "trinket2"))
        self.assertTrue(all("ilevel=272" in c.fields for c in QUEST_CANDIDATES))


class RenderTests(unittest.TestCase):
    def test_override_replaces_exactly_one_slot(self):
        profile = fixture_profile()
        text = render_sim_input(profile, "st", iterations=30000, target_error=0.05, override=("finger2", ",id=2011"))
        self.assertIn("finger2=,id=2011", text)
        self.assertNotIn("id=1012", text)
        self.assertIn("finger1=,id=1011", text)
        self.assertIn('shaman="Tester"', text)
        for option in ("iterations=30000", "target_error=0.05", "fight_style=Patchwerk", "desired_targets=1"):
            self.assertIn(option, text.splitlines())
        # deterministic=1 is rejected by SimC together with target_error.
        self.assertNotIn("deterministic", text)

    def test_cleave_scenario(self):
        text = render_sim_input(fixture_profile(), "cleave", iterations=100, target_error=0.1)
        self.assertIn("desired_targets=3", text.splitlines())
        self.assertIn("fight_style=Patchwerk", text.splitlines())


class ResultTests(unittest.TestCase):
    def test_dps_result_and_delta(self):
        report = {"sim": {"players": [{"collected_data": {"dps": {"mean": 1000.0, "mean_std_dev": 3.0}}}]}}
        self.assertEqual(dps_result(report), {"mean": 1000.0, "std_err": 3.0})
        d = delta({"mean": 1010.0, "std_err": 3.0}, {"mean": 1000.0, "std_err": 4.0})
        self.assertAlmostEqual(d["abs"], 10.0)
        self.assertAlmostEqual(d["pct"], 1.0)
        self.assertAlmostEqual(d["err95"], 1.96 * 5.0)
        with self.assertRaises(RuntimeError):
            dps_result({"sim": {"players": [{"collected_data": {}}]}})


class CheckItemsTests(unittest.TestCase):
    def run_check(self, fake, candidates=None):
        profile = fixture_profile()
        return check_items(
            fake, profile, candidates if candidates is not None else build_candidates(profile)[len(QUEST_CANDIDATES):],
            iterations=100, target_error=0.1, log=lambda _: None,
        )

    def test_rows_ranked_ring_slot_chosen_and_failures_reported(self):
        fake = FakeSimc(fail_ids={2031})
        result = self.run_check(fake)
        self.assertFalse(result["partial"])
        self.assertEqual(result["baseline"]["st"]["mean"], 20000.0)
        self.assertEqual(result["baseline"]["cleave"]["mean"], 30000.0)
        self.assertEqual(result["baseline"]["stats"]["ratings"]["haste"], 700)
        rows = {row["key"].split("-")[1]: row for row in result["rows"]}

        beads = rows["2001"]
        self.assertEqual(beads["rank"], 1)
        self.assertEqual(beads["replaced"], "Old Chain")
        self.assertAlmostEqual(beads["st"]["delta"]["abs"], 500.0)
        self.assertAlmostEqual(beads["cleave"]["delta"]["abs"], 800.0)
        self.assertEqual(beads["stats"], "Agi 101, Haste 72")
        self.assertEqual(beads["ilevel"], 272)
        # The raw item numbers are kept so the addon's verdict can be replayed on the same items.
        self.assertEqual(beads["gear"]["haste_rating"], 72)
        self.assertEqual(beads["replaced_gear"]["ilevel"], 250)
        self.assertIn("finger1", result["baseline"]["gear"])

        band = rows["2011"]
        self.assertEqual(band["replaced_slot"], "finger2")  # finger1 loses 300 more
        self.assertEqual(band["replaced"], "Ring Two")
        self.assertAlmostEqual(band["st"]["delta"]["abs"], -100.0)
        self.assertEqual(set(band["slot_attempts"]), {"finger1", "finger2"})
        self.assertEqual(band["rank"], 2)

        knife = rows["2031"]
        self.assertFalse(knife["simulable"])
        self.assertIsNone(knife["rank"])
        self.assertIn("not simulable", knife["note"])
        self.assertIn("bad item 2031", knife["note"])
        self.assertEqual(result["rows"][-1]["key"], knife["key"])

        # Cleave runs only the chosen ring slot: 2 baselines + 1 + 1 (beads)
        # + 2 + 1 (band) + 1 failed (knife).
        self.assertEqual(len(fake.inputs), 8)

    def test_breath_of_janalai_is_flagged_not_simulable(self):
        trinket = next(c for c in QUEST_CANDIDATES if c.item_id == 280377)
        result = self.run_check(FakeSimc(), [trinket])
        row = result["rows"][0]
        self.assertFalse(row["simulable"])
        self.assertIsNone(row["rank"])
        self.assertIn("not simulable", row["note"])
        self.assertIn("st", row)  # stats-only number is still reported

    def test_item_missing_from_report_gear_is_not_simulable(self):
        candidate = Candidate("x", "Ghost", "neck", ",id=2001", 233)
        result = self.run_check(FakeSimc(hide_ids={2001}), [candidate])
        self.assertFalse(result["rows"][0]["simulable"])
        self.assertIn("did not equip", result["rows"][0]["note"])

    def test_markdown_and_json_outputs(self):
        result = self.run_check(FakeSimc(fail_ids={2031}))
        md = render_markdown(result)
        self.assertIn("| Crit | 500 | 20.50 |", md)
        self.assertIn("| Rank | Slot | Candidate | ilvl | Stats | Replaces | DPS ST | Δ ST | DPS Cleave | Δ Cleave | Notes |", md)
        self.assertIn("| 1 | neck | Spare Beads | 272 | Agi 101, Haste 72 | Old Chain [220] | 20,500 | +500 (+2.50%) ±83 |", md)
        self.assertIn("Ring Two (finger2) [189]", md)
        self.assertNotIn("PARTIAL", md)
        with tempfile.TemporaryDirectory() as directory:
            out_json, out_md = Path(directory) / "a" / "r.json", Path(directory) / "b" / "r.md"
            write_outputs(result, out_json, out_md)
            self.assertEqual(json.loads(out_json.read_text(encoding="utf-8"))["rows"][0]["name"], "Spare Beads")
            self.assertEqual(out_md.read_text(encoding="utf-8"), md)

    def test_progress_writes_partial_results(self):
        snapshots = []
        profile = fixture_profile()
        check_items(
            FakeSimc(), profile, build_candidates(profile)[len(QUEST_CANDIDATES):][:1],
            iterations=100, target_error=0.1, log=lambda _: None,
            progress=lambda result: snapshots.append((result["partial"], len(result["rows"]))),
        )
        self.assertEqual(snapshots, [(True, 0), (True, 0), (True, 1)])
        partial = {"generated_at": "x", "character": "c", "settings": {
            "iterations": 1, "target_error": 1, "scenarios": {"st": "a", "cleave": "b"}, "error_note": "n"},
            "baseline": {}, "rows": [], "partial": True}
        self.assertIn("PARTIAL", render_markdown(partial))


class MainTests(unittest.TestCase):
    def test_main_writes_outputs_with_injected_runner(self):
        import tools.item_check as item_check

        fake = FakeSimc()
        original = item_check.make_runner
        item_check.make_runner = lambda *_args: fake
        try:
            with tempfile.TemporaryDirectory() as directory:
                out_json, out_md = Path(directory) / "r.json", Path(directory) / "r.md"
                with unittest.mock.patch("builtins.print"):
                    code = main([
                        "--simc-bin", "simc", "--profile", str(FIXTURE), "--out-json", str(out_json),
                        "--out-md", str(out_md), "--iterations", "10", "--target-error", "0.5",
                    ])
                self.assertEqual(code, 0)
                data = json.loads(out_json.read_text(encoding="utf-8"))
                self.assertFalse(data["partial"])
                self.assertEqual(len(data["rows"]), len(QUEST_CANDIDATES) + 3)
                self.assertTrue(out_md.exists())
        finally:
            item_check.make_runner = original


if __name__ == "__main__":
    unittest.main()
