from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.live_benchmark_engine import (
    SCHEMA_VERSION,
    SPECS,
    aggregate_cohort,
    aggregate_gear_cohort,
    aggregate_hero_trees,
    compare_hero_trees,
    gear_fingerprints_match,
    load_liquid_armory_import,
    merge_partial_databases,
    parse_active_hero_talent,
    parse_blizzard_gear,
    parse_character_stats,
    parse_equipment,
    parse_rio_gear,
    parse_run_roster_snapshot,
    reconstruct_stats_with_simc,
    reconstruct_stats_with_wowhead,
    validate_database,
    utc_now,
    write_retry_queue,
)


def record(index: int, item_level: float = 320) -> dict:
    return {
        "name": f"Player{index}",
        "realm": "test-realm",
        "region": "eu",
        "score": 4000 - index,
        "itemLevel": item_level,
        "stats": {
            "strength": 2000 + index,
            "agility": 2000 + index,
            "intellect": 2000 + index,
            "stamina": 10000 + index,
            "crit": 500 + index,
            "haste": 600 + index,
            "mastery": 700 + index,
            "versatility": 800 + index,
        },
        "items": {
            "HEAD": {"itemId": 100, "name": "Test Helm", "itemLevel": item_level},
            "TRINKET_1": {"itemId": 200, "name": "Test Trinket", "itemLevel": item_level},
        },
    }


def gear_cohort_stub(status: str, sample_size: int, minimum_sample: int = 3) -> dict:
    return {
        "status": status,
        "sampleSize": sample_size,
        "minimumSample": minimum_sample,
        "popularItems": {},
        "popularTrinketPairs": [],
        "popularRingPairs": [],
        "setConfigurations": [],
        "socketAndEnchantUsage": {},
        "talentLoadouts": [],
        "runMetrics": {},
        "qualityCoverage": {},
    }


class BenchmarkEngineTests(unittest.TestCase):
    def test_simc_reconstruction_marks_exact_run_eligible(self) -> None:
        run_record = {
            **record(1),
            "race": "night-elf",
            "items": {"HEAD": {"itemId": 271474, "itemLevel": 321}},
            "runTalentLoadout": "CoPAAAA",
            "runHeroTalentId": 31,
            "statEligible": False,
        }
        reconstructed = {
            "sv_0001": {
                "ratings": {"crit": 101, "haste": 202, "mastery": 303, "versatility": 404},
                "percentages": {"crit": 0.1},
                "attributes": {"strength": 500, "stamina": 600},
                "health": 7000,
                "armor": 800,
            }
        }
        with patch("tools.live_benchmark_engine.run_simc", return_value=(reconstructed, {})):
            accepted, failures = reconstruct_stats_with_simc(
                Path("simc"), SPECS[0], [run_record], timeout_seconds=10, threads=1
            )
        self.assertEqual(1, len(accepted))
        self.assertFalse(failures)
        self.assertTrue(run_record["statEligible"])
        self.assertEqual(303, run_record["stats"]["mastery"])
        self.assertEqual("HERO_31", run_record["heroTalent"]["key"])

    def test_simc_batch_failure_marks_every_eligible_run(self) -> None:
        runs = [
            {
                **record(index),
                "race": "night-elf",
                "items": {"HEAD": {"itemId": 271474, "itemLevel": 321}},
                "runTalentLoadout": "CoPAAAA",
                "statEligible": False,
            }
            for index in (1, 2)
        ]
        with patch(
            "tools.live_benchmark_engine.run_simc",
            side_effect=RuntimeError("heal actor unsupported"),
        ):
            accepted, failures = reconstruct_stats_with_simc(
                Path("simc"), SPECS[0], runs, timeout_seconds=10, threads=1
            )
        self.assertEqual([], accepted)
        self.assertEqual(2, sum(failures.values()))
        self.assertTrue(
            all(
                str(row["statFailureReason"]).startswith("SimulationCraft batch failed:")
                for row in runs
            )
        )

    def test_simc_timeout_is_caught_and_does_not_crash_the_run(self) -> None:
        # Regression test: a spec whose SimC batch hangs past --simc-timeout
        # must be recorded as a failure for that spec only, not raise and
        # take down the whole 40-spec run (this is what happened with
        # Windwalker Monk in the run that stalled the pipeline).
        runs = [
            {
                **record(1),
                "race": "night-elf",
                "items": {"HEAD": {"itemId": 271474, "itemLevel": 321}},
                "runTalentLoadout": "CoPAAAA",
                "statEligible": False,
            }
        ]
        with patch(
            "tools.live_benchmark_engine.run_simc",
            side_effect=subprocess.TimeoutExpired(cmd="simc", timeout=1800),
        ):
            accepted, failures = reconstruct_stats_with_simc(
                Path("simc"), SPECS[0], runs, timeout_seconds=1800, threads=2
            )
        self.assertEqual([], accepted)
        self.assertEqual(1, sum(failures.values()))
        self.assertTrue(
            str(runs[0]["statFailureReason"]).startswith("SimulationCraft batch failed:")
        )

    def test_wowhead_reconstruction_sums_tooltips_for_healers(self) -> None:
        # SimulationCraft does not simulate healing at all, so healer specs
        # use this Wowhead-tooltip path instead. Confirms: stats come back
        # keyed the same way as the SimC path, an item shared by two
        # characters is only fetched once, and a character with no usable
        # gear is marked as a failure rather than silently dropped.
        healer_spec = next(spec for spec in SPECS if spec.role == "healer")
        shared_item = {"itemId": 100, "name": "Shared Trinket", "itemLevel": 320}
        run_a = {**record(1), "items": {"HEAD": shared_item, "TRINKET_1": shared_item}}
        run_b = {**record(2), "items": {"HEAD": shared_item}}
        run_c = {**record(3), "items": {}}  # no gear at all -> must fail, not crash

        def fake_reconstruct_loadout(items, *, primary, delay, cache):
            if not items:
                raise RuntimeError("no items")
            return {
                "totals": {
                    "stamina": 1000,
                    healer_spec.primary: 500,
                    "crit": 10,
                    "haste": 20,
                    "mastery": 30,
                    "versatility": 40,
                }
            }

        with patch(
            "tools.live_benchmark_engine.reconstruct_loadout", side_effect=fake_reconstruct_loadout
        ) as mocked:
            accepted, failures = reconstruct_stats_with_wowhead(
                healer_spec, [run_a, run_b, run_c], delay=0, workers=4
            )
        self.assertEqual(2, len(accepted))
        self.assertEqual(1000, accepted[0]["stats"]["stamina"])
        self.assertTrue(accepted[0]["statEligible"])
        self.assertEqual("wowhead_tooltip_sum", accepted[0]["statReconstructionMethod"])
        self.assertEqual("Run snapshot lacks gear", run_c["statFailureReason"])
        self.assertEqual(1, sum(failures.values()))
        self.assertEqual(2, mocked.call_count)  # once per record, cache lives inside reconstruct_loadout

    def test_wowhead_reconstruction_fails_closed_on_missing_stats(self) -> None:
        healer_spec = next(spec for spec in SPECS if spec.role == "healer")
        run = {**record(1), "items": {"HEAD": {"itemId": 100, "itemLevel": 320}}}
        with patch(
            "tools.live_benchmark_engine.reconstruct_loadout",
            return_value={"totals": {"stamina": 1000}},  # missing primary + secondaries
        ):
            accepted, failures = reconstruct_stats_with_wowhead(
                healer_spec, [run], delay=0, workers=1
            )
        self.assertEqual([], accepted)
        self.assertEqual(1, sum(failures.values()))
        self.assertTrue(str(run["statFailureReason"]).startswith("Wowhead tooltip stats missing:"))

    def test_catalog_has_forty_unique_specs(self) -> None:
        self.assertEqual(40, len(SPECS))
        self.assertEqual(40, len({spec.key for spec in SPECS}))

    def test_parse_character_sheet_ratings(self) -> None:
        raw = {
            "strength": {"base": 100, "effective": 120},
            "agility": {"base": 10, "effective": 10},
            "intellect": {"base": 20, "effective": 20},
            "stamina": {"base": 900, "effective": 950},
            "melee_crit": {"rating_bonus": 12.1, "rating_normalized": 501, "value": 17.1},
            "spell_crit": {"rating_bonus": 12.1, "rating_normalized": 501, "value": 17.1},
            "melee_haste": {"rating_bonus": 9.4, "rating_normalized": 602, "value": 9.4},
            "mastery": {"rating_bonus": 20.2, "rating_normalized": 703, "value": 38.0},
            "versatility": 804.0,
        }
        parsed = parse_character_stats(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(120, parsed["strength"])
        self.assertEqual(501, parsed["crit"])
        self.assertEqual(804, parsed["versatility"])

    def test_parse_authoritative_equipment(self) -> None:
        average, items = parse_equipment(
            {
                "equipped_items": [
                    {
                        "item": {"id": 123},
                        "slot": {"type": "HEAD"},
                        "name": "Verified Helm",
                        "level": {"value": 320},
                    },
                    {
                        "item": {"id": 456},
                        "slot": {"type": "CHEST"},
                        "name": {"en_US": "Verified Chest"},
                        "level": {"value": 322},
                    },
                ]
            }
        )
        self.assertEqual(321, average)
        self.assertEqual("Verified Helm", items["HEAD"]["name"])
        self.assertEqual("Verified Chest", items["CHEST"]["name"])

    def test_parse_active_hero_talent(self) -> None:
        tree, reason = parse_active_hero_talent(
            {
                "active_specialization": {"id": 250, "name": "Blood"},
                "active_hero_talent_tree": {"id": 31, "name": "San'layn"},
            },
            "Blood",
        )
        self.assertIsNone(reason)
        self.assertEqual(
            {"key": "HERO_31", "id": 31, "name": "San'layn"},
            tree,
        )

    def test_parse_active_hero_talent_from_active_loadout(self) -> None:
        tree, reason = parse_active_hero_talent(
            {
                "active_specialization": {"id": 250, "name": "Blood"},
                "specializations": [
                    {
                        "specialization": {"id": 250, "name": "Blood"},
                        "loadouts": [
                            {
                                "is_active": True,
                                "selected_hero_talent_tree": {"id": 32, "name": "Deathbringer"},
                            }
                        ],
                    }
                ],
            },
            "Blood",
        )
        self.assertIsNone(reason)
        self.assertEqual("Deathbringer", tree["name"])

    def test_cohort_uses_median_and_rejects_ilvl_outlier(self) -> None:
        records = [record(index) for index in range(10)]
        records.append(record(99, item_level=100))
        cohort = aggregate_cohort(records, 10)
        self.assertEqual(10, cohort["sampleSize"])
        self.assertEqual(320, cohort["averageItemLevel"])
        self.assertEqual(604.5, cohort["statTargets"]["stats"]["haste"])
        self.assertEqual(100.0, cohort["popularItems"]["HEAD"][0]["usagePercent"])

    def test_database_validation_requires_all_specs(self) -> None:
        cohort = aggregate_cohort([record(index) for index in range(3)], 3)
        database = {
            "schemaVersion": SCHEMA_VERSION,
            "profiles": {
                spec.key: {
                    "status": "ok",
                    "candidateCount": 3,
                    "verifiedRunCount": 3,
                    "reconstructedStatCount": 3,
                    "cohorts": {"TOP_3": copy.deepcopy(cohort)},
                    "gearCohorts": {"TOP_3": gear_cohort_stub("ok", 3)},
                    "heroTalentTrees": {},
                }
                for spec in SPECS
            },
        }
        validate_database(database, 3)
        database["source"] = {
            "totals": {"candidates": 3, "verifiedRuns": 1, "reconstructedStats": 0}
        }
        with self.assertRaisesRegex(ValueError, "no Raider.IO loadouts"):
            validate_database(database, 3)
        del database["source"]
        del database["profiles"][SPECS[0].key]
        with self.assertRaisesRegex(ValueError, "expected 40 profiles"):
            validate_database(database, 3)

    def test_rare_spec_is_flagged_insufficient_without_failing_the_run(self) -> None:
        full = aggregate_cohort([record(index) for index in range(3)], 3)
        sparse = aggregate_cohort([record(0)], 3)
        empty = aggregate_cohort([], 3)
        self.assertEqual("ok", full["status"])
        self.assertEqual("insufficient", sparse["status"])
        self.assertEqual("insufficient", empty["status"])
        profiles = {
            spec.key: {
                "status": "ok",
                "candidateCount": 3,
                "verifiedRunCount": 3,
                "reconstructedStatCount": 3,
                "cohorts": {"TOP_3": copy.deepcopy(full)},
                "gearCohorts": {"TOP_3": gear_cohort_stub("ok", 3)},
                "heroTalentTrees": {},
            }
            for spec in SPECS
        }
        profiles[SPECS[0].key] = {
            "status": "insufficient",
            "candidateCount": 3,
            "verifiedRunCount": 1,
            "reconstructedStatCount": 1,
            "cohorts": {"TOP_3": sparse},
            "gearCohorts": {"TOP_3": gear_cohort_stub("insufficient", 1)},
            "heroTalentTrees": {},
        }
        profiles[SPECS[1].key] = {
            "status": "insufficient",
            "candidateCount": 3,
            "verifiedRunCount": 0,
            "reconstructedStatCount": 0,
            "cohorts": {"TOP_3": empty},
            "gearCohorts": {"TOP_3": gear_cohort_stub("insufficient", 0)},
            "heroTalentTrees": {},
        }
        database = {"schemaVersion": SCHEMA_VERSION, "profiles": profiles}
        validate_database(database, 3, max_insufficient_specs=2)
        with self.assertRaisesRegex(ValueError, "2 specs lack a complete TOP_3"):
            validate_database(database, 3, max_insufficient_specs=1)
        profiles[SPECS[0].key]["status"] = "ok"
        with self.assertRaisesRegex(ValueError, "profile status does not match"):
            validate_database(database, 3, max_insufficient_specs=2)

    def test_hero_tree_cohorts_and_comparison(self) -> None:
        records = []
        for index in range(6):
            row = record(index)
            row["heroTalent"] = {
                "key": "HERO_31" if index < 3 else "HERO_32",
                "id": 31 if index < 3 else 32,
                "name": "San'layn" if index < 3 else "Deathbringer",
            }
            row["stats"]["haste"] = 900 + index if index < 3 else 300 + index
            row["stats"]["crit"] = 300 + index if index < 3 else 900 + index
            records.append(row)

        trees = aggregate_hero_trees(records, (3,))
        self.assertEqual("ok", trees["HERO_31"]["status"])
        self.assertEqual("spec", trees["HERO_31"]["fallback"])
        analysis = compare_hero_trees(trees, 3)
        self.assertEqual("ok", analysis["status"])
        self.assertGreater(analysis["statRanges"]["haste"]["relativeRangePercent"], 100)

    def test_hero_tree_analysis_fails_closed_with_one_complete_tree(self) -> None:
        records = [record(index) for index in range(3)]
        for row in records:
            row["heroTalent"] = {"key": "HERO_31", "id": 31, "name": "San'layn"}
        analysis = compare_hero_trees(aggregate_hero_trees(records, (3,)), 3)
        self.assertEqual("insufficient", analysis["status"])

    def test_exact_gear_fingerprint_checks_item_level_bonuses_gems_and_enchants(self) -> None:
        rio_items = {}
        blizzard_items = []
        slots = [
            ("head", "HEAD"), ("neck", "NECK"), ("shoulder", "SHOULDER"), ("back", "BACK"),
            ("chest", "CHEST"), ("wrist", "WRIST"), ("hands", "HANDS"), ("waist", "WAIST"),
            ("legs", "LEGS"), ("feet", "FEET"), ("finger1", "FINGER_1"), ("finger2", "FINGER_2"),
        ]
        for index, (rio_slot, blizzard_slot) in enumerate(slots, 1):
            rio_items[rio_slot] = {
                "item_id": 1000 + index,
                "name": f"Item {index}",
                "item_level": 321,
                "bonuses": [10, 20],
                "gems": [2000 + index],
                "enchants": [3000 + index],
            }
            blizzard_items.append(
                {
                    "item": {"id": 1000 + index},
                    "slot": {"type": blizzard_slot},
                    "level": {"value": 321},
                    "bonus_list": [20, 10],
                    "sockets": [{"item": {"id": 2000 + index}}],
                    "enchantments": [{"enchantment_id": 3000 + index}],
                }
            )
        expected, _ = parse_rio_gear({"items": rio_items})
        actual = parse_blizzard_gear({"equipped_items": blizzard_items})
        self.assertEqual((True, None), gear_fingerprints_match(expected, actual))
        blizzard_items[0]["level"]["value"] = 322
        matched, reason = gear_fingerprints_match(
            expected, parse_blizzard_gear({"equipped_items": blizzard_items})
        )
        self.assertFalse(matched)
        self.assertIn("HEAD", reason)

    def test_logged_run_snapshot_requires_combat_log_db_gear(self) -> None:
        character = {"name": "Tank", "realm": "test-realm"}
        member = {
            "character": {
                "name": "Tank",
                "realm": {"slug": "test-realm"},
                "spec": {"name": "Blood"},
                "talentLoadout": {"heroSubTreeId": 31, "exportLoadoutText": "CODE"},
            },
            "items": {
                "source": "db",
                "updated_at": "2026-09-26T12:00:00Z",
                "item_level_equipped": 321,
                "items": {
                    "head": {"item_id": 123, "name": "Verified Helm", "item_level": 321}
                },
            },
        }
        detail = {
            "loggedSources": [{"characterName": "Logger"}],
            "logged_details": {"encounters": [{"roster": [member]}]},
        }
        snapshot, reason = parse_run_roster_snapshot(detail, character, "Blood")
        self.assertIsNone(reason)
        self.assertEqual(31, snapshot["heroTalentId"])
        self.assertEqual(123, snapshot["items"]["HEAD"]["itemId"])
        member["items"]["source"] = "s3"
        snapshot, reason = parse_run_roster_snapshot(detail, character, "Blood")
        self.assertIsNone(snapshot)
        self.assertIn("no exact combat-log", reason)

    def test_observed_bis_candidate_uses_base_item_across_variants(self) -> None:
        records = []
        for index in range(10):
            row = record(index)
            row["rank"] = index + 1
            row["run"] = {"runId": 5000 + index}
            row["items"]["HEAD"] = {
                "itemId": 777 if index < 9 else 888,
                "name": "Consensus Helm" if index < 9 else "Other Helm",
                "itemLevel": 321 if index % 2 else 324,
                "bonusIds": [1],
                "gemIds": [],
                "enchantIds": [],
                "tier": "36",
            }
            records.append(row)
        cohort = aggregate_gear_cohort(records, 10)
        helm = cohort["popularItems"]["HEAD"][0]
        self.assertEqual(9, helm["count"])
        self.assertEqual(2, len(helm["variants"]))
        self.assertTrue(helm["observedBisCandidate"])

    def test_liquid_import_is_optional_and_strictly_validated(self) -> None:
        self.assertEqual("unavailable", load_liquid_armory_import(None, "season-test")["status"])
        payload = {
            "schemaVersion": 1,
            "source": {
                "name": "Liquid Armory",
                "season": "season-test",
                "capturedAt": utc_now(),
                "acquisition": "authorized_export",
                "url": "https://liquidarmory.com/",
                "simcHash": "example",
            },
            "profiles": {
                "DEATHKNIGHT_BLOOD": {
                    "simulations": [
                        {
                            "profileName": "Blood Single Target",
                            "fightStyle": "single_target",
                            "trinkets": [
                                {
                                    "itemId": 123,
                                    "name": "Test Trinket",
                                    "track": "Myth",
                                    "itemLevel": 334,
                                    "absoluteValue": 1000,
                                }
                            ],
                        }
                    ]
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liquid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual("ok", load_liquid_armory_import(path, "season-test")["status"])
            payload["source"]["acquisition"] = "manual_user_export"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "authorized_export"):
                load_liquid_armory_import(path, "season-test")
            payload["source"]["acquisition"] = "authorized_export"
            payload["profiles"]["DEATHKNIGHT_BLOOD"]["simulations"][0]["trinkets"][0]["track"] = "Wrong"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid trinket track"):
                load_liquid_armory_import(path, "season-test")


class BenchmarkMergeAndRetryTests(unittest.TestCase):
    @staticmethod
    def _fake_profile(spec_key: str, ok: bool) -> dict:
        spec = next(s for s in SPECS if s.key == spec_key)
        return {
            "status": "ok" if ok else "insufficient",
            "class": spec.class_name,
            "spec": spec.spec_name,
            "role": spec.role,
            "primaryStat": spec.primary,
            "candidateCount": 1,
            "verifiedRunCount": 1 if ok else 0,
            "reconstructedStatCount": 1 if ok else 0,
            "coverage": {},
            "runFailureReasons": [],
            "statMatchFailureReasons": [],
            "cohorts": {},
            "gearCohorts": {},
            "heroTalentTrees": {},
            "heroTalentGearTrees": {},
            "heroTalentAnalysis": {},
        }

    def _write(self, directory: Path, name: str, profiles: dict) -> Path:
        path = directory / name
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "generatedAt": utc_now(),
                    "source": {"totals": {"candidates": 0, "verifiedRuns": 0, "reconstructedStats": 0}},
                    "profiles": profiles,
                    "externalSimulations": {"status": "unavailable"},
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_merge_combines_disjoint_role_group_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            dps = self._write(
                directory, "dps.json", {"DEATHKNIGHT_FROST": self._fake_profile("DEATHKNIGHT_FROST", True)}
            )
            tank = self._write(
                directory, "tank.json", {"DEATHKNIGHT_BLOOD": self._fake_profile("DEATHKNIGHT_BLOOD", True)}
            )
            merged = merge_partial_databases([dps, tank])
        self.assertEqual({"DEATHKNIGHT_FROST", "DEATHKNIGHT_BLOOD"}, set(merged["profiles"]))
        self.assertEqual(2, merged["source"]["totals"]["candidates"])

    def test_merge_rejects_overlap_unless_override_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            older = self._write(
                directory, "older.json", {"MAGE_FIRE": self._fake_profile("MAGE_FIRE", False)}
            )
            retried = self._write(
                directory, "retried.json", {"MAGE_FIRE": self._fake_profile("MAGE_FIRE", True)}
            )
            with self.assertRaisesRegex(ValueError, "MAGE_FIRE"):
                merge_partial_databases([older, retried])
            merged = merge_partial_databases([older, retried], allow_override=True)
        self.assertEqual("ok", merged["profiles"]["MAGE_FIRE"]["status"])

    def test_retry_queue_lists_only_non_ok_specs(self) -> None:
        database = {
            "profiles": {
                "MAGE_FIRE": self._fake_profile("MAGE_FIRE", True),
                "DRUID_RESTORATION": self._fake_profile("DRUID_RESTORATION", False),
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retry.json"
            failing = write_retry_queue(database, path)
            self.assertEqual(["DRUID_RESTORATION"], failing)
            self.assertEqual(["DRUID_RESTORATION"], json.loads(path.read_text())["specs"])


if __name__ == "__main__":
    unittest.main()
