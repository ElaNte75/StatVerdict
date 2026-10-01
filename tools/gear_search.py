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

Tanks: the same search for three goals, `--objective dps` (full damage), `--objective survival` (least damage
taken per second) and `--objective balance` (the best damage dealt for the damage taken, the two counted as
the same percentage each). All the metrics come from one SimC run.

  python tools/gear_search.py --simc-bin .simc-build/simc --spec MAGE_FIRE [--goal MYTHIC_PLUS] [--hero frostfire]
  python tools/gear_search.py --simc-bin .simc-build/simc --spec DEATHKNIGHT_BLOOD --objective balance
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
# The weapons each spec may use, per simc slot: (journal slot types, weapon types or None for any).
# A slot a spec does not use (a two-hander has no off-hand) is simply absent. Specs not listed here are not searched.
WEAPON_RULES: dict[str, dict[str, tuple[set[str], set[str] | None]]] = {
    "MAGE_FIRE": {"MAIN_HAND": ({"WEAPON"}, {"Dagger", "Sword"}), "OFF_HAND": ({"HOLDABLE"}, None)},
    "DEATHKNIGHT_BLOOD": {"MAIN_HAND": ({"TWOHWEAPON"}, {"Axe", "Mace", "Sword", "Polearm"})},
    "DEMONHUNTER_VENGEANCE": {"MAIN_HAND": ({"WEAPON"}, {"Warglaives"}), "OFF_HAND": ({"WEAPON"}, {"Warglaives"})},
    "DRUID_GUARDIAN": {"MAIN_HAND": ({"TWOHWEAPON"}, {"Staff", "Polearm"})},
    "MONK_BREWMASTER": {"MAIN_HAND": ({"TWOHWEAPON"}, {"Staff", "Polearm"})},
    "PALADIN_PROTECTION": {"MAIN_HAND": ({"WEAPON"}, {"Axe", "Mace", "Sword"}), "OFF_HAND": ({"SHIELD"}, None)},
    "WARRIOR_PROTECTION": {"MAIN_HAND": ({"WEAPON"}, {"Axe", "Mace", "Sword"}), "OFF_HAND": ({"SHIELD"}, None)},
}
# Journal slot -> the simc slot tokens of the search.
POOL_SLOTS = {
    "HEAD": ["HEAD"], "NECK": ["NECK"], "SHOULDER": ["SHOULDER"], "CLOAK": ["BACK"], "CHEST": ["CHEST"],
    "ROBE": ["CHEST"], "WRIST": ["WRIST"], "HAND": ["HANDS"], "WAIST": ["WAIST"], "LEGS": ["LEGS"],
    "FEET": ["FEET"], "FINGER": ["FINGER_1", "FINGER_2"], "TRINKET": ["TRINKET_1", "TRINKET_2"],
    "WEAPON": ["MAIN_HAND", "OFF_HAND"], "TWOHWEAPON": ["MAIN_HAND"], "SHIELD": ["OFF_HAND"], "HOLDABLE": ["OFF_HAND"],
}
PAIRED = {"FINGER_1": "FINGER_2", "FINGER_2": "FINGER_1", "TRINKET_1": "TRINKET_2", "TRINKET_2": "TRINKET_1"}
SEARCH_FIGHT = ()  # Patchwerk, one target
FIGHTS = {"single target": (), "three targets": ("desired_targets=3",), "dungeon slice": ("fight_style=DungeonSlice",)}
METRIC_NAMES = {"Damage per Second": "dps", "Damage Taken per Second": "dtps"}
Z_NEEDED = 2.0
MAX_ROUNDS = 6


def objective_value(objective: str, metrics: dict[str, tuple[float, float]]) -> tuple[float, float]:
    """(value, standard error): bigger is better. `metrics` is {"dps": (mean, se), "dtps": (mean, se)}.
    dps: the damage. survival: minus the damage taken per second. balance: ln(dps) - ln(dtps), the two
    counted as the same percentage (a 1% better dps is worth a 1% lower damage taken)."""
    dps, dps_se = metrics["dps"]
    if objective == "dps":
        return dps, dps_se
    dtps, dtps_se = metrics["dtps"]
    if objective == "survival":
        return -dtps, dtps_se
    if objective == "balance":
        return math.log(dps) - math.log(dtps), math.hypot(dps_se / dps, dtps_se / dtps)
    raise ValueError(f"unknown objective {objective!r}")


def objective_gain_percent(objective: str, base: dict[str, tuple[float, float]], other: dict[str, tuple[float, float]]) -> float:
    """How much better `other` is than `base` for the objective, in percent (damage taken: how much lower)."""
    if objective == "dps":
        return 100 * (other["dps"][0] - base["dps"][0]) / base["dps"][0]
    if objective == "survival":
        return 100 * (base["dtps"][0] - other["dtps"][0]) / base["dtps"][0]
    return 100 * (math.exp(objective_value("balance", other)[0] - objective_value("balance", base)[0]) - 1)


def candidate_items(spec, pool: dict[str, Any], guide_entries: list[dict[str, Any]], baseline: dict[str, dict[str, Any]],
                    levels: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    """Per simc slot the candidate item dicts (itemId plus itemLevel or bonusIds), baseline excluded."""
    armor = ARMOR_TYPE[spec.class_name]
    rules = WEAPON_RULES[spec.key]
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
        for slot in slots:
            if slot in ("MAIN_HAND", "OFF_HAND"):
                rule = rules.get(slot)
                if rule is None or slot_type not in rule[0] or (rule[1] is not None and subclass not in rule[1]):
                    continue
            if slot in out and level_for(slot):
                out[slot][int(item_id)] = {"itemId": int(item_id), "itemLevel": level_for(slot)}
    for entry in guide_entries:  # the guide's own items keep their upgrade bonus ids
        slot = CLASSCODEX_SLOT_TO_SIMC.get(str(entry.get("slot") or ""))
        if slot in out and entry.get("itemId"):
            item = {"itemId": int(entry["itemId"])}
            if level_for(slot):  # same item level as the baseline slot, so only the choice of item is compared
                item["itemLevel"] = level_for(slot)
            elif entry.get("bonusIDs"):
                item["bonusIds"] = [int(v) for v in entry["bonusIDs"]]
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
        """Simulate `loadout` and each variant (name -> {slot: item}) in one SimC run. Returns
        ({name: {"dps": (mean, se), "dtps": (mean, se)}}, player); the loadout itself is "base"."""
        from tools.simc_stat_engine import render_item
        lines = []
        # The loadout is also a profileset (its first item put on again) so that every metric of
        # every entry is read the same way.
        first_slot = next(iter(loadout))
        for name, changes in {"base": {first_slot: loadout[first_slot]}, **variants}.items():
            for slot, item in changes.items():
                lines.append(f'profileset."{name}"+={render_item(slot, item)}')
        text, _ = render_profiles(
            self.spec, [{"race": "human", "runTalentLoadout": self.talents, "items": loadout, "level": 90}],
            iterations=iterations, max_time=300, fixed_time=1, target_error=target_error, seed=seed,
            global_lines=tuple(fight) + ("profileset_metric=dps,dtps",), extra_lines=tuple(lines),
            talents_optional=True,
        )
        stats, report = run_simc(self.simc_bin, text, timeout_seconds=7200, threads=self.threads)
        player = report["sim"]["players"][0]
        results: dict[str, dict[str, tuple[float, float]]] = {}
        for entry in (report["sim"].get("profilesets") or {}).get("results", []):
            metrics = {"dps": (float(entry["mean"]), float(entry["mean_stddev"]))}
            for extra in entry.get("additional_metrics") or []:
                short = METRIC_NAMES.get(extra.get("metric"))
                if short:
                    metrics[short] = (float(extra["mean"]), float(extra["mean_stddev"]))
            results[entry["name"]] = metrics
        return results, player


def search(sim: Sim, baseline, candidates, gems, objective="dps", log=print):
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
        base_value, base_se = objective_value(objective, results["base"])
        best_by_slot: dict[str, tuple[float, str]] = {}
        for name, metrics in results.items():
            if name == "base":
                continue
            value, se = objective_value(objective, metrics)
            gain = value - base_value
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
        base_check = objective_value(objective, check_results["base"])[0]
        single = objective_value(objective, check_results["single"])[0]
        joint = objective_value(objective, check_results["together"])[0]
        chosen = together if joint >= single else variants[single_name]
        for slot, item in chosen.items():
            loadout[slot] = {k: v for k, v in item.items()}
        better = check_results["together"] if joint >= single else check_results["single"]
        percent = objective_gain_percent(objective, check_results["base"], better)
        history.append({"round": round_number, "gain_single": single - base_check, "gain_together": joint - base_check,
                        "taken": {slot: item["itemId"] for slot, item in chosen.items()}, "gain_percent": percent})
        log(f"round {round_number}: taken {history[-1]['taken']}  ({percent:+.2f}% {objective})")
    return loadout, history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--spec", default="MAGE_FIRE")
    parser.add_argument("--goal", default="MYTHIC_PLUS")
    parser.add_argument("--hero")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--pool", type=Path, default=Path("tools/data/blizzard_item_pool.json"))
    parser.add_argument("--objective", choices=("dps", "survival", "balance"), default="dps")
    parser.add_argument("--out", type=Path, default=None, help="default: docs/gear-search/<spec>-<goal>-<objective>")
    args = parser.parse_args(argv)
    if args.out is None:
        args.out = Path("docs/gear-search") / f"{args.spec.lower()}-{args.goal.lower()}-{args.objective}"

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
    found, history = search(sim, baseline, candidates, upgrades, args.objective)

    comparison = {}
    for name, fight in FIGHTS.items():
        results, _p = sim.run(baseline, {"found": {slot: item for slot, item in found.items() if item != baseline.get(slot)}},
                              fight=fight, target_error=0.04, iterations=40000)
        guide, found_metrics = results["base"], results["found"]
        value, se = objective_value(args.objective, found_metrics)
        base_value, base_se = objective_value(args.objective, guide)
        comparison[name] = {
            "guide": {k: v[0] for k, v in guide.items()}, "found": {k: v[0] for k, v in found_metrics.items()},
            "dps_change_pct": 100 * (found_metrics["dps"][0] / guide["dps"][0] - 1),
            "damage_taken_change_pct": 100 * (found_metrics["dtps"][0] / guide["dtps"][0] - 1),
            "objective_gain_pct": objective_gain_percent(args.objective, guide, found_metrics),
            "z": (value - base_value) / math.hypot(se, base_se),
        }
    _r, found_player = sim.run(found, {}, target_error=0.1)
    _r, guide_player = sim.run(baseline, {}, target_error=0.1)

    def gear_names(player_doc: dict[str, Any]) -> dict[str, Any]:
        return {slot: {"name": g.get("name"), "ilevel": g.get("ilevel")} for slot, g in (player_doc.get("gear") or {}).items()
                if isinstance(g, dict)}

    result = {"spec": args.spec, "goal": args.goal, "hero": hero, "objective": args.objective, "buildId": fetched.build_id, "history": history,
              "comparison": comparison, "guide_gear": gear_names(guide_player), "found_gear": gear_names(found_player)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(comparison, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
