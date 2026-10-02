"""Prepares the weekly data-only release after the live data refresh changed the data.

Version scheme (owner's rule): MAJOR.MINOR.WEEK.
  - A data-only release changes only WEEK: the week the data was refreshed. A week with no release is skipped.
  - A functional change raises MINOR (a big one raises MAJOR and zeroes MINOR); that is done by hand, not here.
  - New year: the week number starts again at 1, so MINOR is raised by one and the version never goes backwards.
The week turns over on Wednesday (the game's weekly reset): the week of a date is the ISO week of that date minus two days.

What this does when the data changed:
  - A release is already waiting (docs/changelog/<version>_pending.md): it only adds a line about the new data to it.
  - Otherwise: it computes the next version, writes it into the toc, the Lua file and STORE.md, writes
    docs/changelog/<version>_<date>.md, and fails nothing when the week already has its release (then it does nothing).
It writes the text of the GitHub issue that reminds the owner to upload, and prints the issue title on stdout.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ADDON = "StatVerdict"
DATA_LINE = "- Guide data refreshed to the latest."
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def reset_week(day: date) -> int:
    """Week number of a date, counting weeks from Wednesday to Tuesday."""
    return (day - timedelta(days=2)).isocalendar()[1]


def parse_version(text: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(text.strip())
    if not match:
        raise ValueError(f"not a MAJOR.MINOR.WEEK version: {text!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def next_data_version(current: str, today: date) -> str | None:
    """The version of the data-only release made on `today`, or None when that week already has its release."""
    major, minor, week = parse_version(current)
    new_week = reset_week(today)
    if new_week > week:
        return f"{major}.{minor}.{new_week}"
    if new_week == week:
        return None
    return f"{major}.{minor + 1}.{new_week}"  # new year: the week restarted


def _read(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = _read(path)
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match for {pattern!r}")
    _write(path, new_text)


def read_version(root: Path) -> str:
    text = _read(root / ADDON / f"{ADDON}.toc")
    match = re.search(r"^(?:﻿)?## Version:\s*(\S+)", text, re.M)
    if not match:
        raise RuntimeError("no '## Version:' line in the toc")
    return match.group(1)


def write_version(root: Path, version: str) -> None:
    _replace_once(root / ADDON / f"{ADDON}.toc", r"^(﻿?## Version:[ \t]*)\S+", rf"\g<1>{version}")
    _replace_once(root / ADDON / f"{ADDON}.lua", r'^(ns\.VERSION = ")[^"]+(")', rf"\g<1>{version}\g<2>")
    _replace_once(root / ADDON / "STORE.md", r"\(v\d+\.\d+\.\d+\)", f"(v{version})")


def _add_data_line(changelog: Path) -> bool:
    """Adds the data line before the closing fence of the pending changelog; False when it is already there."""
    text = _read(changelog)
    if DATA_LINE in text:
        return False
    newline = "\r\n" if "\r\n" in text else "\n"
    marker = f"{newline}```"
    index = text.rfind(marker)
    if index == -1:
        raise RuntimeError(f"{changelog}: no closing code fence")
    _write(changelog, text[:index] + newline + DATA_LINE + text[index:])
    return True


def _issue_body(version: str, changelog_name: str, changelog_text: str, pending: bool) -> str:
    why = (
        "Η έκδοση που περίμενε ανέβασμα έχει τώρα και τα νέα δεδομένα των οδηγών."
        if pending
        else "Τα δεδομένα των οδηγών ανανεώθηκαν και η νέα έκδοση είναι έτοιμη."
    )
    return (
        f"{why}\n\n"
        f"**Έκδοση:** {version}\n\n"
        "**Τι να κάνεις:**\n"
        "1. Άνοιξε το παιχνίδι, κάνε `/reload` και δες ότι όλα δουλεύουν.\n"
        "2. Τρέξε το `StatVerdict Ship (no bump).bat` για να φτιαχτεί το zip στην επιφάνεια εργασίας.\n"
        "3. Ανέβασε το zip στο CurseForge με το κείμενο παρακάτω.\n"
        "4. Κλείσε αυτό το θέμα. Αν η έκδοση λέγεται `_pending`, πες στο Claude ότι ανέβηκε.\n\n"
        f"**Κείμενο αλλαγών** (`docs/changelog/{changelog_name}`):\n\n{changelog_text.strip()}\n"
    )


def prepare(root: Path, today: date) -> tuple[str, str] | None:
    """Prepares the release files. Returns (issue title, issue body), or None when there is nothing to do."""
    current = read_version(root)
    changelog_dir = root / "docs" / "changelog"
    pending = changelog_dir / f"{current}_pending.md"
    if pending.exists():
        _add_data_line(pending)
        title = f"Ώρα για ανέβασμα: StatVerdict {current} (με νέα δεδομένα)"
        return title, _issue_body(current, pending.name, _read(pending), pending=True)

    version = next_data_version(current, today)
    if version is None:
        return None
    write_version(root, version)
    name = f"{version}_{today.isoformat()}.md"
    text = (
        f"# StatVerdict {version}\n\n"
        f"Weekly data release, prepared {today.isoformat()} by the live data refresh. "
        "Only the guide data changed.\n"
        "The text below is what goes into the CurseForge changelog box.\n\n"
        f"```\n{version}\n{DATA_LINE}\n```\n"
    )
    changelog_dir.mkdir(parents=True, exist_ok=True)
    _write(changelog_dir / name, text)
    title = f"Ώρα για ανέβασμα: StatVerdict {version}"
    return title, _issue_body(version, name, text, pending=False)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--issue-body", type=Path, required=True, help="where to write the issue text")
    args = parser.parse_args(argv)
    result = prepare(args.root, args.today)
    if result is None:
        print("This week already has its release; nothing to prepare.", file=sys.stderr)
        return 0
    title, body = result
    args.issue_body.write_text(body, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(title)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
