"""The weekly data-only release: version numbers (MAJOR.MINOR.WEEK) and the files it prepares."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from tools import release_prep as rp


class WeekTests(unittest.TestCase):
    def test_the_week_turns_over_on_wednesday(self) -> None:
        tuesday, wednesday = date(2026, 10, 6), date(2026, 10, 7)
        self.assertEqual(40, rp.reset_week(tuesday))
        self.assertEqual(41, rp.reset_week(wednesday))
        self.assertEqual(41, rp.reset_week(date(2026, 10, 8)))  # a Thursday upload is still that week
        self.assertEqual(41, rp.reset_week(date(2026, 10, 13)))  # up to the next Tuesday
        self.assertEqual(42, rp.reset_week(date(2026, 10, 14)))


class NextVersionTests(unittest.TestCase):
    def test_a_data_release_moves_only_the_week(self) -> None:
        self.assertEqual("1.2.41", rp.next_data_version("1.2.40", date(2026, 10, 7)))

    def test_skipped_weeks_are_skipped_in_the_number(self) -> None:
        self.assertEqual("1.2.44", rp.next_data_version("1.2.41", date(2026, 10, 28)))

    def test_the_old_numbering_moves_to_the_week_scheme(self) -> None:
        self.assertEqual("1.1.41", rp.next_data_version("1.1.1", date(2026, 10, 7)))

    def test_the_same_week_has_no_second_release(self) -> None:
        self.assertIsNone(rp.next_data_version("1.2.41", date(2026, 10, 9)))

    def test_a_new_year_raises_minor_so_the_version_never_goes_backwards(self) -> None:
        new = rp.next_data_version("1.3.52", date(2027, 1, 6))
        self.assertEqual("1.4.1", new)
        self.assertGreater(tuple(map(int, new.split("."))), (1, 3, 52))

    def test_bad_versions_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            rp.parse_version("1.1")


TOC = "﻿## Interface: 120100\n## Title: StatVerdict\n## Version: {version}\n## SavedVariables: StatVerdictDB\nCore/A.lua\n"
LUA = 'local addonName, ns = ...\n\nns.VERSION = "{version}"\nns.RELEASE_DATE = "2000-01-01"\n\nlocal x = 1\n'
STORE = "# StatVerdict — store & launch copy (v{version})\n\nText with (v9.9.9) later on.\n"
PENDING = "# StatVerdict {version}\n\nWaiting.\n\n```\n{version}\nFixed\n- Something.\n```\n"


def write_raw(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def build_tree(root: Path, version: str, pending: bool, newline: str = "\n") -> None:
    addon = root / "StatVerdict"
    addon.mkdir(parents=True)
    write_raw(addon / "StatVerdict.toc", TOC.format(version=version).replace("\n", newline))
    write_raw(addon / "StatVerdict.lua", LUA.format(version=version).replace("\n", newline))
    write_raw(addon / "STORE.md", STORE.format(version=version).replace("\n", newline))
    changelog = root / "docs" / "changelog"
    changelog.mkdir(parents=True)
    (changelog / "1.1.0_2026-10-01.md").write_text("old\n", encoding="utf-8")
    if pending:
        write_raw(changelog / f"{version}_pending.md", PENDING.format(version=version).replace("\n", newline))


class PrepareTests(unittest.TestCase):
    def run_prepare(self, version: str, today: date, pending: bool, newline: str = "\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        build_tree(root, version, pending, newline)
        return root, rp.prepare(root, today)

    def test_a_data_release_writes_the_version_everywhere_and_a_changelog(self) -> None:
        root, result = self.run_prepare("1.2.40", date(2026, 10, 7), pending=False)
        self.assertEqual("1.2.41", rp.read_version(root))
        lua = (root / "StatVerdict" / "StatVerdict.lua").read_text(encoding="utf-8")
        self.assertIn('ns.VERSION = "1.2.41"', lua)
        self.assertIn('ns.RELEASE_DATE = "2026-10-07"', lua)  # the window shows it as the last update
        store = (root / "StatVerdict" / "STORE.md").read_text(encoding="utf-8")
        self.assertIn("(v1.2.41)", store.splitlines()[0])
        self.assertIn("(v9.9.9)", store)  # only the header is touched
        written = root / "docs" / "changelog" / "1.2.41_2026-10-07.md"
        self.assertIn(rp.DATA_LINE, written.read_text(encoding="utf-8"))
        title, body = result
        self.assertIn("1.2.41", title)
        self.assertIn("StatVerdict Ship (no bump).bat", body)
        self.assertIn(rp.DATA_LINE, body)

    def test_the_toc_keeps_its_byte_order_mark_and_the_other_lines(self) -> None:
        root, _ = self.run_prepare("1.2.40", date(2026, 10, 7), pending=False)
        raw = (root / "StatVerdict" / "StatVerdict.toc").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf## Interface: 120100"))
        self.assertIn(b"## Version: 1.2.41\n", raw)
        self.assertIn(b"## SavedVariables: StatVerdictDB", raw)

    def test_windows_line_endings_survive(self) -> None:
        root, _ = self.run_prepare("1.2.40", date(2026, 10, 7), pending=False, newline="\r\n")
        raw = (root / "StatVerdict" / "StatVerdict.toc").read_bytes()
        self.assertIn(b"## Version: 1.2.41\r\n", raw)
        self.assertNotIn(b"\n\n", raw.replace(b"\r\n", b""))

    def test_a_waiting_release_only_gets_the_data_line(self) -> None:
        root, result = self.run_prepare("1.2.40", date(2026, 10, 7), pending=True)
        self.assertEqual("1.2.40", rp.read_version(root))
        text = (root / "docs" / "changelog" / "1.2.40_pending.md").read_text(encoding="utf-8")
        self.assertEqual(1, text.count(rp.DATA_LINE))
        self.assertTrue(text.rstrip().endswith("```"))
        self.assertIn("1.2.40", result[0])
        self.assertFalse(list((root / "docs" / "changelog").glob("1.2.41*")))

    def test_running_twice_adds_the_data_line_only_once(self) -> None:
        root, _ = self.run_prepare("1.2.40", date(2026, 10, 7), pending=True)
        rp.prepare(root, date(2026, 10, 7))
        text = (root / "docs" / "changelog" / "1.2.40_pending.md").read_text(encoding="utf-8")
        self.assertEqual(1, text.count(rp.DATA_LINE))

    def test_a_week_that_already_has_its_release_does_nothing(self) -> None:
        root, result = self.run_prepare("1.2.41", date(2026, 10, 9), pending=False)
        self.assertIsNone(result)
        self.assertEqual("1.2.41", rp.read_version(root))


class RepositoryTests(unittest.TestCase):
    def test_the_real_repository_can_be_read(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.assertRegex(rp.read_version(root), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
