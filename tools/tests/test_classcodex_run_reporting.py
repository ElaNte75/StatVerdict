"""Skip reporting (I4) and the coverage floor (I5) shared by both generated-
file CLI (tools/classcodex_targets_cli.py)."""
from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import classcodex_targets_cli
from tools.classcodex_fetch import FetchResult
from tools.classcodex_targets import (
    SkipRecord,
    build_all,
    count_contexts,
    coverage_problem,
    format_simc_error,
    format_skip_summary,
    gate_and_write,
    previous_context_count,
)


def doc(contexts_per_spec: dict[str, int]) -> dict:
    """A generated document with the given number of MYTHIC_PLUS hero-talent
    contexts per spec."""
    return {
        "schemaVersion": 1,
        "profiles": {
            spec_key: {
                "specKey": spec_key,
                "goals": {"MYTHIC_PLUS": {"heroTalents": {f"hero{i}": {"critical_strike": 1.0} for i in range(count)}}},
            }
            for spec_key, count in contexts_per_spec.items()
        },
    }


SPECS = {
    "DEATHKNIGHT_frost": {
        "gear": {"value": {"all": {"mplus": [{"itemId": 1, "slot": "Head"}], "raid": [{"itemId": 2, "slot": "Head"}]}}},
        # Only Mythic+ has a talent export; Raid borrows it (labelled), and a
        # spec with no export anywhere is reported as skipped (see NOTALENTS).
        "talents": {"value": {"deathbringer": {"mplus": [{"export": "M"}]}}},
    },
    "NOTASPEC_madeup": {"gear": {"value": {}}},
}

NO_TALENTS = {
    "DEATHKNIGHT_frost": {
        "gear": {"value": {"all": {"mplus": [{"itemId": 1, "slot": "Head"}], "raid": [{"itemId": 2, "slot": "Head"}]}}},
        "talents": {"value": {"deathbringer": {}}},
    },
}


class SkipRecordingTests(unittest.TestCase):
    def test_build_all_reports_every_skipped_combo_with_a_reason(self) -> None:
        reconstructed = {"ratings": {"crit": 1.0, "haste": 2.0, "mastery": 3.0, "versatility": 4.0}}
        skips: list[SkipRecord] = []
        with patch("tools.classcodex_targets.run_simc", return_value=({"sv_0001": reconstructed}, {})):
            data = build_all(SPECS, Path("simc"), goals=("MYTHIC_PLUS", "RAID"), skips=skips)
        self.assertIn("DEATHKNIGHT_FROST", data["profiles"])
        self.assertIn(SkipRecord("NOTASPEC_madeup", None, None, "spec not in StatVerdict's catalog"), skips)
        self.assertEqual(1, len(skips))
        borrowed = data["profiles"]["DEATHKNIGHT_FROST"]["goals"]["RAID"]["heroTalents"]["deathbringer"]
        self.assertEqual(["talents borrowed from MYTHIC_PLUS"], borrowed["targets"]["targetMetadata"]["recovery"])

    def test_a_combo_with_no_talent_export_anywhere_is_skipped(self) -> None:
        skips: list[SkipRecord] = []
        build_all(NO_TALENTS, Path("simc"), goals=("MYTHIC_PLUS", "RAID"), skips=skips)
        self.assertIn(SkipRecord("DEATHKNIGHT_FROST", "RAID", "deathbringer", "no talent export for this goal"), skips)

    def test_build_all_reports_simc_failures(self) -> None:
        skips: list[SkipRecord] = []
        with patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError("boom")):
            data = build_all(SPECS, Path("simc"), goals=("MYTHIC_PLUS",), skips=skips)
        self.assertEqual({}, data["profiles"])
        self.assertIn(SkipRecord("DEATHKNIGHT_FROST", "MYTHIC_PLUS", "deathbringer", "SimC run failed (RuntimeError)"), skips)

    def test_skip_argument_is_optional(self) -> None:
        with patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError("boom")):
            self.assertEqual({}, build_all(SPECS, Path("simc"))["profiles"])


LONG_SIMC_ERROR = "FATAL-HEAD " + ("x" * 3000) + " Trivial: TAIL-END"


class SimcErrorLoggingTests(unittest.TestCase):
    """The real fatal SimC error is usually near the start of its output,
    followed by pages of trailing `Trivial:` warnings; both ends must be
    visible in the log."""

    def test_targets_log_the_head_and_the_tail_of_a_long_simc_error(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr), patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError(LONG_SIMC_ERROR)):
            build_all(SPECS, Path("simc"), goals=("MYTHIC_PLUS",))
        self.assertIn("FATAL-HEAD", stderr.getvalue())
        self.assertIn("TAIL-END", stderr.getvalue())
        self.assertLess(len(stderr.getvalue()), 2500)

    def test_short_errors_are_logged_whole(self) -> None:
        self.assertEqual("boom", format_simc_error(RuntimeError("boom")))
        formatted = format_simc_error(RuntimeError(LONG_SIMC_ERROR))
        self.assertTrue(formatted.startswith(LONG_SIMC_ERROR[:1200]))
        self.assertTrue(formatted.endswith(LONG_SIMC_ERROR[-600:]))


class FormatSkipSummaryTests(unittest.TestCase):
    def test_counts_by_reason_and_lists_details_when_short(self) -> None:
        skips = [
            SkipRecord("MAGE_FIRE", "RAID", "sunfury", "SimC run failed (RuntimeError)"),
            SkipRecord("MAGE_FROST", "RAID", "frostfire", "SimC run failed (RuntimeError)"),
            SkipRecord("NOTASPEC_x", None, None, "spec not in StatVerdict's catalog"),
        ]
        summary = format_skip_summary(skips)
        self.assertIn("3 combo(s) skipped", summary)
        self.assertIn("2 x SimC run failed (RuntimeError)", summary)
        self.assertIn("MAGE_FIRE/RAID/sunfury: SimC run failed (RuntimeError)", summary)
        self.assertIn("NOTASPEC_x: spec not in StatVerdict's catalog", summary)

    def test_omits_details_when_the_list_is_long(self) -> None:
        skips = [SkipRecord(f"SPEC_{i}", "PVP", "h", "no usable gear for this goal") for i in range(50)]
        summary = format_skip_summary(skips, detail_limit=40)
        self.assertIn("50 x no usable gear for this goal", summary)
        self.assertNotIn("Details:", summary)

    def test_says_so_when_nothing_was_skipped(self) -> None:
        self.assertEqual("No combos were skipped.", format_skip_summary([]))


class CoverageTests(unittest.TestCase):
    def test_count_contexts_counts_hero_talent_leaves(self) -> None:
        self.assertEqual(5, count_contexts(doc({"A_X": 2, "B_Y": 3})))
        self.assertEqual(0, count_contexts({"profiles": {}}))

    def test_coverage_problem(self) -> None:
        self.assertIsNotNone(coverage_problem(0, None, 0.8))
        self.assertIsNone(coverage_problem(10, None, 0.8))  # first run: no baseline
        self.assertIsNone(coverage_problem(80, 100, 0.8))
        self.assertIn("100 to 79", coverage_problem(79, 100, 0.8))
        self.assertIsNone(coverage_problem(1, 100, 0.0))  # explicit override

    def test_gate_writes_on_a_first_run_and_reads_its_own_output_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            with redirect_stdout(io.StringIO()):
                code = gate_and_write(doc({"A_X": 2}), out, "ClassCodexTargets", classcodex_targets_cli.write_addon_file)
            self.assertEqual(0, code)
            self.assertEqual(2, previous_context_count(out, "ClassCodexTargets"))

    def test_gate_refuses_to_shrink_coverage_past_the_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            classcodex_targets_cli.write_addon_file(doc({"A_X": 5, "B_Y": 5}), out)
            before = out.read_bytes()
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = gate_and_write(doc({"A_X": 5}), out, "ClassCodexTargets", classcodex_targets_cli.write_addon_file)
            self.assertEqual(1, code)
            self.assertEqual(before, out.read_bytes())
            self.assertIn("coverage dropped from 10 to 5", stderr.getvalue())

    def test_gate_refuses_an_empty_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            with redirect_stderr(io.StringIO()):
                code = gate_and_write(doc({}), out, "ClassCodexTargets", classcodex_targets_cli.write_addon_file)
            self.assertEqual(1, code)
            self.assertFalse(out.exists())

    def test_gate_refuses_when_the_previous_file_cannot_be_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            out.write_text("this is not lua {{{", encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                code = gate_and_write(doc({"A_X": 1}), out, "ClassCodexTargets", classcodex_targets_cli.write_addon_file)
            self.assertEqual(1, code)
            self.assertEqual("this is not lua {{{", out.read_text(encoding="utf-8"))


class CliReportingTests(unittest.TestCase):
    def test_targets_cli_prints_the_skip_summary_and_refuses_an_empty_result(self) -> None:
        fetched = FetchResult(build_id="b1", published_at="2026-09-28", sources={})
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, redirect_stderr(stderr), \
                patch("tools.classcodex_targets_cli.fetch_all", return_value=fetched), \
                patch("tools.classcodex_targets_cli.build", return_value=SPECS), \
                patch("tools.classcodex_targets_cli.reconstruct_loadout", side_effect=OSError("no network in tests")),                 patch("tools.classcodex_targets.run_simc", side_effect=RuntimeError("boom")):
            out = Path(tmp) / "SV_ClassCodexTargets.lua"
            code = classcodex_targets_cli.main(["--simc-bin", "simc", "--out", str(out)])
            self.assertFalse(out.exists())
        self.assertEqual(1, code)
        self.assertIn("wowhead fallback failed", stderr.getvalue())
        self.assertIn("Refusing to write", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
