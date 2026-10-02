#!/usr/bin/env python3
"""The stat targets of Method's Best in Slot sets: the secondary rating the set they list adds up to.

Nothing is tuned: it is the arithmetic of the guide's own list (items, enchants, gems), counted by SimulationCraft's
stat sheet, under the game's rules: one unique Diamond gem in total, the other gems only into real sockets, an enchant
only on a slot that takes it. Where the guide leaves a choice open ("A or B"), the first listed is used and said so.
Item level is not written by the guide: every item is taken at the season's top upgrade (SEASON_MAX_ILVL).

  python tools/method_targets.py --simc-bin /tmp/simc-build/simc [--slugs guardian-druid]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from tools import method_guides
    from tools.classcodex_build import build
    from tools.classcodex_fetch import fetch_all
    from tools.classcodex_targets import (
        LoadoutUpgrades, _classcodex_key_to_catalog_key, _enchant_lookup, _hero_talent_keys, build_simc_items,
        resolve_enchant, run_with_talent_fallback, select_goal_context, talent_exports_from_entries,
    )
    from tools.classcodex_build import ENCHANT_LOOKUP_FIELD
    from tools.simc_stat_engine import run_simc
    from tools.spec_catalog import SPEC_BY_KEY
except ModuleNotFoundError:
    import method_guides
    from classcodex_build import ENCHANT_LOOKUP_FIELD, build
    from classcodex_fetch import fetch_all
    from classcodex_targets import (
        LoadoutUpgrades, _classcodex_key_to_catalog_key, _enchant_lookup, _hero_talent_keys, build_simc_items,
        resolve_enchant, run_with_talent_fallback, select_goal_context, talent_exports_from_entries,
    )
    from simc_stat_engine import run_simc
    from spec_catalog import SPEC_BY_KEY

SEASON_MAX_ILVL = 334  # Midnight Season 2: Myth 6/6 (tools/upgrade_tracks.py)
SLUG_TO_SPEC = {
    "blood-death-knight": "DEATHKNIGHT_BLOOD", "vengeance-demon-hunter": "DEMONHUNTER_VENGEANCE",
    "guardian-druid": "DRUID_GUARDIAN", "brewmaster-monk": "MONK_BREWMASTER",
    "protection-paladin": "PALADIN_PROTECTION", "protection-warrior": "WARRIOR_PROTECTION",
}
CONTEXT_OF_TAB = {"raid": "RAID", "mythic_plus": "MYTHIC_PLUS"}
# Method's slot words -> the slot names the shared loadout builder reads.
SLOT_NAMES = {"head": "Head", "neck": "Neck", "shoulders": "Shoulders", "shoulder": "Shoulders", "cloak": "Back",
              "back": "Back", "chest": "Chest", "wrist": "Wrist", "gloves": "Hands", "hands": "Hands", "belt": "Waist",
              "legs": "Legs", "boots": "Feet", "feet": "Feet", "main hand": "Main Hand", "weapon": "Main Hand",
              "off hand": "Off Hand"}
# Enchant labels -> SimC slots. A ring enchant goes on both rings; a weapon enchant on the main hand, and on the off
# hand too when it is a second weapon (dual wield), never on a shield.
ENCHANT_SLOTS = {"head": ["HEAD"], "shoulders": ["SHOULDER"], "shoulder": ["SHOULDER"], "chest": ["CHEST"],
                 "legs": ["LEGS"], "boots": ["FEET"], "feet": ["FEET"], "rings": ["FINGER_1", "FINGER_2"],
                 "ring": ["FINGER_1", "FINGER_2"], "weapon": ["MAIN_HAND"], "cloak": ["BACK"], "wrist": ["WRIST"],
                 "gloves": ["HANDS"], "belt": ["WAIST"]}
DUAL_WIELD = {"DEMONHUNTER_VENGEANCE"}
STATS = ("crit", "haste", "mastery", "versatility")


def gear_entries(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """The tab's rows as a loadout list (one entry per slot, rings and trinkets numbered in order)."""
    entries, problems = [], []
    counters = {"ring": 0, "trinket": 0}
    for row in rows:
        label = row["slot"].strip().lower()
        if row.get("itemId") is None:
            problems.append(f"row without item: {row['slot']}")
            continue
        if label.startswith("ring"):
            counters["ring"] += 1
            slot = f"Finger {counters['ring']}"
        elif label.startswith("trinket"):
            counters["trinket"] += 1
            slot = f"Trinket {counters['trinket']}"
        else:
            slot = SLOT_NAMES.get(label)
        if slot is None:
            problems.append(f"unknown slot: {row['slot']}")
            continue
        entries.append({"slot": slot, "itemId": row["itemId"], "ilvl": SEASON_MAX_ILVL})
    return entries, problems


def pick_secondary(gems: dict[str, Any], hero: str | None) -> tuple[int | None, str]:
    others = gems.get("others") or []
    norm = lambda text: re.sub(r"[^a-z]", "", text.lower())
    if hero:
        for gem in others:
            if gem["note"] and norm(gem["note"]) == norm(hero):
                return gem["itemId"], f"gem for {hero}"
    plain = [g for g in others if not g["note"]]
    chosen = (plain or others or [None])[0]
    if chosen is None:
        return None, "no secondary gem listed"
    note = f"first of {len(plain or others)} listed gems" if len(plain or others) > 1 else "the one listed gem"
    return chosen["itemId"], note


def loadout_upgrades(data: dict[str, Any], hero: str | None, lookup, spec_key: str, gear: list[dict[str, Any]]):
    enchants: dict[str, dict[str, int]] = {}
    unresolved: list[str] = []
    off_hand_is_weapon = any(e["slot"] == "Off Hand" for e in gear) and spec_key in DUAL_WIELD
    for label, scroll_id in data["enchants"].items():
        slots = list(ENCHANT_SLOTS.get(label.strip().lower(), []))
        if label.strip().lower() == "weapon" and off_hand_is_weapon:
            slots.append("OFF_HAND")
        resolved = resolve_enchant({"id": scroll_id}, lookup)
        if not slots:
            unresolved.append(f"{label}: slot not understood")
        elif not resolved or resolved.get("id") is None:
            unresolved.append(f"{label}: enchant {scroll_id} could not be translated")
        else:
            for slot in slots:
                enchants[slot] = resolved
    gems: dict[str, int] = {}
    if data["gems"].get("primary"):
        gems["primary"] = data["gems"]["primary"]
    secondary, why = pick_secondary(data["gems"], hero)
    if secondary:
        gems["secondary"] = secondary
    return LoadoutUpgrades(enchants, gems), unresolved, why


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("tools/data/method"))
    parser.add_argument("--slugs", default=",".join(SLUG_TO_SPEC))
    args = parser.parse_args(argv)
    fetched = fetch_all()
    specs = build(fetched.sources)
    failed = False
    for slug in args.slugs.split(","):
        try:
            data = json.loads((args.data / f"{slug}.json").read_text(encoding="utf-8"))
            catalog_key = SLUG_TO_SPEC[slug]
            spec = SPEC_BY_KEY[catalog_key]
            fields = next(f for k, f in specs.items() if _classcodex_key_to_catalog_key(k) == catalog_key)
            talents_value = (fields.get("talents") or {}).get("value")
            gear_value = (fields.get("gear") or {}).get("value")
            heroes = sorted(_hero_talent_keys(gear_value, talents_value))
            lookup = _enchant_lookup((fields.get("enchants") or {}).get("value"), (fields.get(ENCHANT_LOOKUP_FIELD) or {}).get("value"))
            # A page whose enchants could not be read (written as prose, not a list) gives understated ratings:
            # said in the file so nothing downstream shows the numbers as complete.
            incomplete = [] if {"rings", "ring"} & {k.strip().lower() for k in data["enchants"]} else ["ring enchant not read from the guide"]
            out: dict[str, Any] = {"slug": slug, "updated": data["updated"], "itemLevel": SEASON_MAX_ILVL,
                                   "incomplete": incomplete, "results": {}}
            variants = [v["hero"] for v in data["priority"]] or [None]
            for tab, goal in CONTEXT_OF_TAB.items():
                rows = data["bestInSlot"].get(tab)
                if not rows:
                    continue
                entries, problems = gear_entries(rows)
                for hero_label in variants:
                    upgrades, unresolved, gem_note = loadout_upgrades(data, hero_label, lookup, catalog_key, entries)
                    items = build_simc_items(entries, upgrades)
                    exports = talent_exports_from_entries(select_goal_context(talents_value, heroes[0], goal)) if heroes else []
                    stats, report, recovery, actor = run_with_talent_fallback(args.simc_bin, spec, items, exports, run_simc_fn=run_simc)
                    ratings = stats[actor]["ratings"]
                    out["results"][f"{tab}/{hero_label or 'all'}"] = {
                        "ratings": {s: ratings[s] for s in STATS},
                        "items": len(entries), "problems": problems, "enchantsNotApplied": unresolved,
                        "secondaryGem": gem_note, "simcRecovery": recovery,
                    }
            (args.data / f"{slug}-targets.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
            print(slug, {k: (v["ratings"], v["enchantsNotApplied"], v["problems"]) for k, v in out["results"].items()})
        except Exception as exc:  # noqa: BLE001
            failed = True
            print(f"{slug}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
