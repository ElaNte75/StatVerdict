#!/usr/bin/env python3
"""Reads the Method (method.gg) class guides: the stat priority line and the Best in Slot tables.

Only facts are kept (item ids and names, the order of the stats, where an item drops), never the prose.
The guide is copied 1:1: the tables are read as they are, per tab (Overall, Raiding, Mythic+).
It writes nothing into the addon.

  python tools/method_guides.py --out tools/data/method [--specs guardian-druid,brewmaster-monk]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

BASE = "https://www.method.gg/guides/"
USER_AGENT = "Mozilla/5.0 (compatible; StatVerdictDataBot; +https://github.com/ElaNte75/StatVerdict)"
TANK_SLUGS = ("blood-death-knight", "vengeance-demon-hunter", "guardian-druid", "brewmaster-monk",
              "protection-paladin", "protection-warrior")


def all_slugs() -> list[str]:
    """Method's guide slug of every spec in the catalog: '<spec>-<class>' ('beast-mastery-hunter')."""
    try:
        from tools.spec_catalog import SPEC_BY_KEY
    except ModuleNotFoundError:
        from spec_catalog import SPEC_BY_KEY
    return [f"{s.spec_name.lower().replace(' ', '-')}-{s.class_name}" for s in SPEC_BY_KEY.values()]


TABS = {"overall_table": "overall", "raid_table": "raid", "dungeon_table": "mythic_plus"}
STAT_WORDS = {"haste": "haste", "vers": "versatility", "versatility": "versatility", "crit": "crit",
              "critical": "crit", "mastery": "mastery"}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def text_of(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


STAT_PATTERN = r"(?:critical strike|crit|haste|versatility|vers|mastery)"
HERO_LABEL = re.compile(r"((?:[A-Z][\w'’\-]+ ?){1,3}):\s*(?=(?:Strength|Agility|Intellect|Item Level|ilvl|Haste|Crit|Mastery|Vers)\b)")
END_MARKERS = ("Stat Outline", "Stat Summary", "Secondary Stats", "Stat Breakdown", "Races")
RATING_RANGE = re.compile(r"(crit\w*|haste|mastery|vers\w*)\s*:\s*~?\s*(\d{3,4})(?:\s*-\s*(\d{3,4}))?\s*rating", re.I)


def _chain(segment: str) -> list[list[str]] | None:
    """The secondary stats of one 'A > B = C ...' chain as tie groups, best first. '>=' keeps the written order
    (the stat on the left first); a plain space between two stats (a list written one stat per line) counts as '>'."""
    tokens = re.findall(STAT_PATTERN + r"|>>|>=|≥|>|=", segment, flags=re.I)
    groups: list[list[str]] = []
    pending_operator = ">"
    for token in tokens:
        word = token.lower()
        if word in (">>", ">", ">=", "≥", "="):
            pending_operator = "=" if word == "=" else ">"
            continue
        stat = STAT_WORDS.get(word.split(" ")[0])
        if stat is None or any(stat in group for group in groups):
            continue
        if groups and pending_operator == "=":
            groups[-1].append(stat)
        else:
            groups.append([stat])
        pending_operator = ">"
    return groups if sum(len(g) for g in groups) >= 3 else None


def _label(match) -> tuple[str, int]:
    """(hero name, where it starts): a stat word written just before the name ('... > Haste San’layn:') is not part of it."""
    raw = match.group(1)
    name = re.sub(r"^(?:(?:crit|haste|vers|mastery)\w* |stat ranking?s? |ranking |stat priority )+", "", raw.strip(), flags=re.I)
    return name, match.start() + raw.find(name)


def parse_rating_ranges(section: str) -> list[dict[str, Any]]:
    """Some guides give rating ranges ('Mastery: ~1200-1400 rating'), per variant label when there are several."""
    marks = list(re.finditer(r"((?:[A-Z][\w'’\-]+ ?){1,3}):\s*(?=Intellect|Strength|Agility)", section))
    segments = [("", section)] if not marks else [
        (marks[i].group(1).strip(), section[marks[i].end():marks[i + 1].start() if i + 1 < len(marks) else len(section)])
        for i in range(len(marks))]
    out = []
    for label, body in segments:
        ranges = {}
        for stat, lo, hi in RATING_RANGE.findall(body):
            ranges[STAT_WORDS.get(stat.lower().split(" ")[0], stat.lower())] = [int(lo), int(hi or lo)]
        if ranges:
            label = re.sub(r"^(?:(?:crit|haste|vers|mastery)\w* )+", "", label, flags=re.I)
            out.append({"hero": label or None, "ranges": ranges})
    return out


def priority_section(page: str) -> str:
    text = text_of(page)
    start = max(text.rfind("Stat Rankings"), text.rfind("Stat Ranking"), text.rfind("Stat Priorities"))
    ends = [e for e in (text.find(marker, start + 15) for marker in END_MARKERS) if e > 0]
    return text[start:min(ends)] if start >= 0 and ends else ""


def parse_priority(page: str) -> list[dict[str, Any]]:
    """The guide's stat priority as variants [{"hero": name or None, "secondary": [[stat, ...], ...], "line": text}].
    The section sits between the 'Stat Priorities / Stat Rankings' heading and 'Stat Outline'."""
    section = priority_section(page)
    if not section:
        return []
    # Only the part that holds the order itself: from the first sentence with an operator or a stat run.
    marks = [(m, _label(m)) for m in HERO_LABEL.finditer(section)]
    variants: list[dict[str, Any]] = []
    if marks:
        for index, (mark, label) in enumerate(marks):
            stop = marks[index + 1][1][1] if index + 1 < len(marks) else len(section)
            chain = _chain(section[mark.end():stop])
            if chain:
                variants.append({"hero": label[0], "secondary": chain, "line": section[mark.end():stop].strip()})
        return variants
    # No hero labels: the order is the last sentence that holds three or more stats.
    candidates = [s for s in re.split(r"(?<=[.:])\s+", section) if len(re.findall(STAT_PATTERN, s, flags=re.I)) >= 3]
    for sentence in reversed(candidates):
        chain = _chain(sentence)
        if chain:
            return [{"hero": None, "secondary": chain, "line": sentence.strip()}]
    return []


def parse_tables(page: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for tab_id, name in TABS.items():
        start = page.find(f'id="{tab_id}"')
        if start < 0:
            continue
        # Only the tab's own table: later tables on the page (bonus roll targets, ...) are other things.
        end = page.find("</table>", start)
        block = page[start:end if end > 0 else len(page)]
        rows = []
        for row in re.findall(r"<tr>(.*?)</tr>", block, flags=re.S):
            cells = re.findall(r"<td>(.*?)</td>", row, flags=re.S)
            if len(cells) < 3 or text_of(cells[0]).lower() == "slot":
                continue
            link = re.search(r'item=(\d+)[^"]*?(?:\?([^"]*))?"', cells[1])
            bonus = re.search(r"bonus=([\d:]+)", cells[1])
            rows.append({
                "slot": text_of(cells[0]),
                "itemId": int(link.group(1)) if link else None,
                "name": text_of(re.sub(r"\(.*?\)", "", re.sub(r"<a[^>]*>(.*?)</a>", r"\1", cells[1]))),
                "note": (re.search(r"\(([^)]*)\)", text_of(cells[1])) or [None, ""])[1],
                "bonusIds": bonus.group(1) if bonus else "",
                "source": text_of(cells[2]),
            })
        if rows:
            out[name] = rows
    return out


def _section(page: str, start_id: str, end_id: str) -> str:
    a = page.find(f'id="{start_id}"')
    b = page.find(f'id="{end_id}"', a + 1)
    return page[a:b] if a >= 0 and b > a else ""


def _item_links(fragment: str) -> list[tuple[int, str]]:
    return [(int(i), text_of(n)) for i, n in re.findall(r'item=(\d+)[^"]*"[^>]*>(.*?)</a>', fragment, flags=re.S)]


def parse_enchants(page: str) -> dict[str, int]:
    """{slot label: enchant item id}: the first (best) enchant of each slot, from a table row ('Head | Best | Cheaper')
    or from a line 'Head: <link>'."""
    section = _section(page, "enchants", "gems")
    out: dict[str, int] = {}
    for row in re.findall(r"<tr>(.*?)</tr>", section, flags=re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)
        if len(cells) >= 2:
            links = _item_links(cells[1])
            if links and text_of(cells[0]).lower() != "slot":
                out.setdefault(text_of(cells[0]), links[0][0])
    for label, body in re.findall(r"<(?:strong|b)>([^<:]+):</(?:strong|b)>\s*(.*?)(?:</p>|<br)", section, flags=re.S):
        links = _item_links(body)
        if links:
            out.setdefault(label.strip(), links[0][0])
    return out


def parse_gems(page: str) -> dict[str, Any]:
    """Gems as the page links them, in order: 'primary' = the first Diamond (the unique gem), 'others' = every other
    gem link in order of appearance with its note (a hero tree in brackets, when there is one). The prose around the
    links is free text, so more than one entry in 'others' means the guide offers a choice; the first one is used."""
    section = _section(page, "gems", "consumables")
    primary = None
    others: list[dict[str, Any]] = []
    for item_id, name in _item_links(section):
        if "diamond" in name.lower():
            if primary is None:
                primary = item_id
            continue
        tail = section[section.find(f"item={item_id}"):]
        note = re.search(r"</a>\s*\(([^)]{1,30})\)", tail)
        others.append({"itemId": item_id, "name": name, "note": note.group(1) if note else ""})
    return {"primary": primary, "others": others}


def parse_enchants_and_gems(page: str) -> dict[str, Any]:
    return {"enchants": parse_enchants(page), "gems": parse_gems(page)}


def read_spec(slug: str) -> dict[str, Any]:
    stats_page = fetch(f"{BASE}{slug}/stats-races-and-consumables")
    gear_page = fetch(f"{BASE}{slug}/gearing")
    updated = re.search(r"Last Updated:\s*([^<]+?)\s*<", re.sub(r"\s+", " ", stats_page))
    return {
        "slug": slug,
        "updated": updated.group(1).strip() if updated else "",
        "priority": parse_priority(stats_page),
        "ratingRanges": parse_rating_ranges(priority_section(stats_page)),
        "bestInSlot": parse_tables(gear_page),
        **parse_enchants_and_gems(stats_page),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("tools/data/method"))
    parser.add_argument("--specs", default="all", help="comma-separated slugs, or 'all' (every spec in the catalog)")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    failed = False
    slugs = all_slugs() if args.specs == "all" else args.specs.split(",")
    for slug in slugs:
        try:
            data = read_spec(slug)
            (args.out / f"{slug}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
            counts = {k: len(v) for k, v in data["bestInSlot"].items()}
            print(slug, data["updated"], [(v["hero"], v["secondary"]) for v in data["priority"]], counts)
        except Exception as exc:  # noqa: BLE001  one spec failing must not stop the others
            failed = True
            print(f"{slug}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
