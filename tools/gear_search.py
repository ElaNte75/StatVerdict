#!/usr/bin/env python3
"""Pilot: does a search over real items beat the guide's Best in Slot, by simulation?

For one spec, goal and hero tree it starts from the guide's Best in Slot loadout (same gems and enchants),
and tries, slot by slot, every candidate item of that slot: the season's drops (Blizzard journal pool,
tools/data/blizzard_item_pool.json) that the class can wear, plus every item of the guide's own lists for the
spec (crafted items, tier pieces). All candidates are simulated at the item level of the slot they replace.
The best clearly better items are taken, round after round, until nothing is better. The found loadout is then
compared with the guide's, head to head, in several fights.

Limits of the pilot: armor slots, jewelry, trinkets and one-hand weapons with an off-hand (no two-handers);
the class's armor type and weapon types are listed below; trinket effects SimC does not know count only as
their stats; set bonuses count through the items' own set ids.

  python tools/gear_search.py --simc-bin .simc-build/simc --spec MAGE_FIRE [--goal MYTHIC_PLUS] [--hero frostfire]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from tools.classcodex_build import build
    from tools.classcodex_fetch import fetch_all
    from tools.classcodex_targets import (
        _classcodex_key_to_catalog_key,
        build_simc_items,
        guide_gear_list,
        guide_trinket_list,
        loadout_upgrades_for,
        select_goal_context,
        talent_exports_from_entries,
        CLASSCODEX_SLOT_TO_SIMC,
        GEMLESS_SIMC_SLOTS,
    )
    from tools.simc_stat_engine import parse_gear_item_levels, render_profiles, run_simc
    from tools.spec_catalog import SPEC_BY_KEY
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).parent))
    from classcodex_build import build
    from classcodex_fetch import fetch_all
    from classcodex_targets import (
        _classcodex_key_to_catalog_key,
        build_simc_items,
        guide_gear_list,
        guide_trinket_list,
        loadout_upgrades_for,
        select_goal_context,
        talent_exports_from_entries,
        CLASSCODEX_SLOT_TO_SIMC,
        GEMLESS_SIMC_SLOTS,
    )
    from simc_stat_engine import parse_gear_item_levels, render_profiles, run_simc
    from spec_catalog import SPEC_BY_KEY

ARMOR_TYPE = {
    "mage": "Cloth", "priest": "Cloth", "warlock": "Cloth",
    "rogue": "Leather", "druid": "Leather", "monk": "Leather", "demon-hunter": "Leather",
    "hunter": "Mail", "shaman": "Mail", "evoker": "Mail",
    "warrior": "Plate", "paladin": "Plate", "death-knight": "Plate",
}
# One-hand weapon types per class for the pilot (only the classes tried so far).
ONE_HAND_TYPES = {"mage": {"Dagger", "Sword"}}
# Journal slot -> the simc slot tokens of the pilot.
POOL_SLOTS = {
    "HEAD": ["HEAD"], "NECK": ["NECK"], "SHOULDER": ["SHOULDER"], "CLOAK": ["BACK"], "CHEST": ["CHEST"],
    "ROBE": ["CHEST"], "WRIST": ["WRIST"], "HAND": ["HANDS"], "WAIST": ["WAIST"], "LEGS": ["LEGS"],
    "FEET": ["FEET"], "FINGER": ["FINGER_1", "FINGER_2"], "TRINKET": ["TRINKET_1", "TRINKET_2"],
    "WEAPON": ["MAIN_HAND"], "HOLDABLE": ["OFF_HAND"],
}
PAIRED = {"FINGER_1": "FINGER_2", "FINGER_2": "FINGER_1", "TRINKET_1": "TRINKET_2", "TRINKET_2": "TRINKET_1"}
SEARCH_FIGHT = ()  # Patchwerk, one target
FIGHTS = {"single target": (), "three targets": ("desired_targets=3",), "dungeon slice": ("fight_style=DungeonSlice",)}
Z_NEEDED = 2.0
MAX_ROUNDS = 6


def candidate_items(spec, pool: dict[str, Any], guide_entries: list[dict[str, Any]], baseline: dict[str, dict[str, Any]],
                    levels: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    """Per simc slot the candidate item dicts (itemId plus itemLevel or bonusIds), baseline excluded."""
    armor = ARMOR_TYPE[spec.class_name]
    one_hand = ONE_HAND_TYPES[spec.class_name]
    out: dict[str, dict[int, dict[str, Any]]] = {slot: {} for slot in baseline}

    def level_for(slot: str) -> int | None:
        value = levels.get({"SHOULDER": "shoulders", "WRIST": "wrists", "FINGER_1": "finger1", "FINGER_2": "finger2",
                            "TRINKET_1": "trinket1", "TRINKET_2": "trinket2"}.get(slot, slot.lower()))
        return int(round(value)) if value else None

    for item_id, row in pool.items():
        slot_type, item_class, subclass = row.get("slot"), row.get("class"), row.get("subclass")
        slots = POOL_SLOTS.get(slot_type)
        if not slots:
            continue
        if slot_type in ("HEAD", "SHOULDER", "CHEST", "ROBE", "WRIST", "HAND", "WAIST", "LEGS", "FEET") and subclass != armor:
            continue
        if slot_type == "CLOAK" and subclass != "Cloth":
            continue
        if slot_type == "WEAPON" and subclass not in one_hand:
            continue
        if slot_type == "HOLDABLE" and item_class != "Armor":
            continue
        for slot in slots:
            if slot in out and level_for(slot):
                out[slot][int(item_id)] = {"itemId": int(item_id), "itemLevel": level_for(slot)}
    for entry in guide_entries:  # the guide's own items keep their upgrade bonus ids
        slot = CLASSCODEX_SLOT_TO_SIMC.get(str(entry.get("slot") or ""))
        if slot in out and entry.get("itemId"):
            item = {"itemId": int(entry["itemId"])}
            if entry.get("bonusIDs"):
                item["bonusIds"] = [int(v) for v in entry["bonusIDs"]]
            elif level_for(slot):
                item["itemLevel"] = level_for(slot)
            out[slot][item["itemId"]] = item
    for slot, base in baseline.items():
        out[slot].pop(int(base["itemId"]), None)
    return {slot: list(items.values()) for slot, items in out.items()}


def decorate(slot: str, item: dict[str, Any], baseline: dict[str, dict[str, Any]], gems: dict[str, Any]) -> dict[str, Any]:
    """The candidate with the slot's enchant and gems of the baseline loadout (the guide's recommendations)."""
    base = baseline[slot]
    out = dict(item)
    if base.get("enchantIds"):
        out["enchantIds"] = list(base["enchantIds"])
    if base.get("gemIds") and slot not in GEMLESS_SIMC_SLOTS:
        out["gemIds"] = list(base["gemIds"])
    return out


class Sim:
    def __init__(self, simc_bin: Path, spec, talents: str, threads: int):
        self.simc_bin, self.spec, self.talents, self.threads = simc_bin, spec, talents, threads

    def run(self, loadout: dict[str, dict[str, Any]], variants: dict[str, dict[str, dict[str, Any]]], fight=(),
            target_error=0.15, iterations=12000, seed=None):
        """Simulate `loadout` (name 'base') and each variant (name -> {slot: item}) in one SimC run."""
        from tools.simc_stat_engine import render_item
        lines = []
        for name, changes in variants.items():
            for slot, item in changes.items():
                lines.append(f'profileset."{name}"+={render_item(slot, item)}')
        text, _ = render_profiles(
            self.spec, [{"race": "human", "runTalentLoadout": self.talents, "items": loadout, "level": 90}],
            iterations=iterations, max_time=300, fixed_time=1, target_error=target_error, seed=seed,
            global_lines=tuple(fight), extra_lines=tuple(lines), talents_optional=True,
        )
        stats, report = run_simc(self.simc_bin, text, timeout_seconds=7200, threads=self.threads)
        player = report["sim"]["players"][0]
        base = player["collected_data"]["dps"]
        results = {"base": (float(base["mean"]), float(base["mean_std_dev"]))}
        for entry in (report["sim"].get("profilesets") or {}).get("results", []):
            results[entry["name"]] = (float(entry["mean"]), float(entry["mean_stddev"]))
        return results, player


def search(sim: Sim, baseline, candidates, gems, log=print):
    loadout = {slot: dict(item) for slot, item in baseline.items()}
    history = []
    for round_number in range(1, MAX_ROUNDS + 1):
        variants, meta = {}, {}
        for slot, items in candidates.items():
            for item in items:
                if PAIRED.get(slot) and int(loadout[PAIRED[slot]]["itemId"]) == item["itemId"]:
                    continue  # unique: the other ring / trinket already is this item
                name = f"{slot}:{item['itemId']}"
                variants[name] = {slot: decorate(slot, item, baseline, gems)}
                meta[name] = (slot, item)
        results, _player = sim.run(loadout, variants)
        base_mean, base_se = results["base"]
        best_by_slot: dict[str, tuple[float, str]] = {}
        for name, (mean, se) in results.items():
            if name == "base":
                continue
            gain = mean - base_mean
            z = gain / math.hypot(se, base_se)
            slot = meta[name][0]
            if z >= Z_NEEDED and (slot not in best_by_slot or gain > best_by_slot[slot][0]):
                best_by_slot[slot] = (gain, name)
        if not best_by_slot:
            log(f"round {round_number}: nothing better, stop")
            break
        ordered = sorted(best_by_slot.items(), key=lambda kv: -kv[1][0])
        combined = {}
        used = set()
        for slot, (gain, name) in ordered:
            item_id = meta[name][1]["itemId"]
            if item_id in used:
                continue
            used.add(item_id)
            combined[name] = {slot: decorate(slot, meta[name][1], baseline, gems)}
        # the single best, and all the best ones together, against the current loadout
        single_name = ordered[0][1][1]
        together = {slot: item for changes in combined.values() for slot, item in changes.items()}
        check_results, _ = sim.run(loadout, {"single": variants[single_name], "together": together})
        single, joint = check_results["single"][0], check_results["together"][0]
        chosen = together if joint >= single else variants[single_name]
        for slot, item in chosen.items():
            loadout[slot] = {k: v for k, v in item.items()}
        history.append({"round": round_number, "base": base_mean, "gain_single": single - check_results["base"][0],
                        "gain_together": joint - check_results["base"][0],
                        "taken": {slot: item["itemId"] for slot, item in chosen.items()}})
        log(f"round {round_number}: taken {history[-1]['taken']}  (+{max(single, joint) - check_results['base'][0]:.0f} dps)")
    return loadout, history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--spec", default="MAGE_FIRE")
    parser.add_argument("--goal", default="MYTHIC_PLUS")
    parser.add_argument("--hero")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--pool", type=Path, default=Path("tools/data/blizzard_item_pool.json"))
    parser.add_argument("--out", type=Path, default=Path("docs/gear-search"))
    args = parser.parse_args(argv)

    spec = SPEC_BY_KEY[args.spec]
    pool = json.loads(args.pool.read_text(encoding="utf-8"))["items"]
    fetched = fetch_all()
    specs = build(fetched.sources)
    key = next(k for k in specs if _classcodex_key_to_catalog_key(k) == args.spec)
    fields = specs[key]
    gear_value = fields["gear"]["value"]
    talents_value = fields["talents"]["value"]
    from tools.classcodex_targets import _hero_talent_keys
    hero = args.hero or sorted(_hero_talent_keys(gear_value, talents_value))[0]
    talents = talent_exports_from_entries(select_goal_context(talents_value, hero, args.goal))[0]
    upgrades = loadout_upgrades_for(fields, hero, args.goal)
    guide_list = guide_gear_list(gear_value, args.goal) or []
    baseline = build_simc_items(guide_list, upgrades)
    guide_entries = []
    for goal in ("MYTHIC_PLUS", "RAID"):
        guide_entries += guide_gear_list(gear_value, goal) or []
        guide_entries += [{**e, "slot": slot} for e in (guide_trinket_list(fields["trinkets"]["value"], goal) or [])
                          for slot in ("Trinket 1", "Trinket 2")]
    sim = Sim(args.simc_bin, spec, talents, args.threads)
    _results, player = sim.run(baseline, {}, target_error=0.1)
    levels = parse_gear_item_levels(player)
    candidates = candidate_items(spec, pool, guide_entries, baseline, levels)
    print("candidates per slot:", {slot: len(items) for slot, items in candidates.items()}, flush=True)
    found, history = search(sim, baseline, candidates, upgrades)

    comparison = {}
    for name, fight in FIGHTS.items():
        results, _p = sim.run(baseline, {"found": {slot: item for slot, item in found.items() if item != baseline.get(slot)}},
                              fight=fight, target_error=0.04, iterations=40000)
        guide_mean, guide_se = results["base"]
        found_mean, found_se = results["found"]
        comparison[name] = {"guide": guide_mean, "found": found_mean, "gain_pct": 100 * (found_mean - guide_mean) / guide_mean,
                            "error_pct": 100 * math.hypot(guide_se, found_se) * 1.96 / guide_mean}
    _r, found_player = sim.run(found, {}, target_error=0.1)
    _r, guide_player = sim.run(baseline, {}, target_error=0.1)

    def gear_names(player_doc: dict[str, Any]) -> dict[str, Any]:
        return {slot: {"name": g.get("name"), "ilevel": g.get("ilevel")} for slot, g in (player_doc.get("gear") or {}).items()
                if isinstance(g, dict)}

    result = {"spec": args.spec, "goal": args.goal, "hero": hero, "buildId": fetched.build_id, "history": history,
              "comparison": comparison, "guide_gear": gear_names(guide_player), "found_gear": gear_names(found_player)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(comparison, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
