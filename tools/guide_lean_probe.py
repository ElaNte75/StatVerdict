#!/usr/bin/env python3
"""Experiment: where does the guide's Damage stat priority lean for a tank (defence, offence, middle)?

For a tank spec it takes the guide's best-in-slot loadout and the total of its secondary rating, then
simulates (SimulationCraft profilesets, dps and damage taken per second together):
  guide      the loadout as the guide has it
  priority   the same total rating split by the guide's stat priority (places 1.4 : 1.25 : 1.1 : 1, ties averaged)
  dps / survival / balance   the best split of the same total found by hill climbing for that goal
The report places the guide's priority between the best-damage and the best-survival split.
It is a simulation estimate; it writes nothing into the addon.

  python tools/guide_lean_probe.py --simc-bin /tmp/simc-build/simc --specs DRUID_GUARDIAN,MONK_BREWMASTER,PALADIN_PROTECTION
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from tools.classcodex_build import build
    from tools.classcodex_fetch import fetch_all
    from tools.classcodex_targets import (
        _classcodex_key_to_catalog_key, _hero_talent_keys, build_simc_items, guide_gear_list,
        loadout_upgrades_for, select_goal_context, talent_exports_from_entries,
    )
    from tools.classcodex_rules import default_priority, guide_field
    from tools.gear_search import METRIC_NAMES, objective_gain_percent, objective_value
    from tools.simc_stat_engine import render_profiles, run_simc
    from tools.spec_catalog import SPEC_BY_KEY
except ModuleNotFoundError:  # run as a script
    from classcodex_build import build
    from classcodex_fetch import fetch_all
    from classcodex_targets import (
        _classcodex_key_to_catalog_key, _hero_talent_keys, build_simc_items, guide_gear_list,
        loadout_upgrades_for, select_goal_context, talent_exports_from_entries,
    )
    from classcodex_rules import default_priority, guide_field
    from gear_search import METRIC_NAMES, objective_gain_percent, objective_value
    from simc_stat_engine import render_profiles, run_simc
    from spec_catalog import SPEC_BY_KEY

STATS = ("crit", "haste", "mastery", "versatility")
SIMC_STAT = {stat: f"enchant_{stat}_rating" for stat in STATS}
PLACE_WEIGHTS = (1.4, 1.25, 1.1, 1.0)
STEPS = (150, 75)
MAX_ROUNDS = 10
Z_NEEDED = 2.0
OBJECTIVES = ("dps", "survival", "balance")


def priority_shares(groups: list[list[str]]) -> dict[str, float]:
    """Rating shares from the guide order: each place has a weight, tied stats share their places' average."""
    weights: dict[str, float] = {}
    place = 0
    for group in groups:
        stats = [s for s in group if s in STATS]
        if not stats:
            continue
        average = sum(PLACE_WEIGHTS[place:place + len(stats)]) / len(stats)
        for stat in stats:
            weights[stat] = average
        place += len(stats)
    total = sum(weights.values())
    return {stat: weights.get(stat, 1.0) / (total or 1.0) for stat in STATS}


def name_of(deltas: dict[str, int]) -> str:
    return "d_" + "_".join(f"{stat[:1]}{deltas[stat]:+d}" for stat in STATS)


class Runner:
    def __init__(self, simc_bin: Path, spec, items, exports, fight, threads: int):
        self.simc_bin, self.spec, self.items, self.exports, self.fight, self.threads = simc_bin, spec, items, exports, fight, threads

    def run(self, variants: list[dict[str, int]], target_error=0.12, iterations=12000, seed=None):
        lines: list[str] = []
        for deltas in variants:
            name = name_of(deltas)
            moved = [f'profileset."{name}"+={SIMC_STAT[s]}={deltas[s]}' for s in STATS if deltas[s]]
            lines += moved or [f'profileset."{name}"+=enchant_crit_rating=0']
        talents = next(iter(self.exports))
        text, _ = render_profiles(
            self.spec, [{"race": "human", "runTalentLoadout": talents, "items": self.items, "level": 90}],
            iterations=iterations, max_time=300, fixed_time=1, target_error=target_error, seed=seed,
            global_lines=tuple(self.fight) + ("profileset_metric=dps,dtps",), extra_lines=tuple(lines),
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
        ratings = (stats.get(player.get("name")) or next(iter(stats.values())))["ratings"]
        return ratings, results


def climb(runner: Runner, base: dict[str, float], objective: str, log) -> dict[str, int]:
    state = {stat: 0 for stat in STATS}
    step_index = 0
    for round_number in range(1, MAX_ROUNDS + 1):
        step = STEPS[step_index]
        moves = []
        for give, take in itertools.permutations(STATS, 2):
            if base[give] + state[give] - step < 0:
                continue
            moved = dict(state)
            moved[give] -= step
            moved[take] += step
            moves.append(moved)
        _r, results = runner.run([state] + moves)
        current = objective_value(objective, results[name_of(state)])
        best, best_z, best_move = None, 0.0, None
        for move in moves:
            value = objective_value(objective, results[name_of(move)])
            gain = value[0] - current[0]
            z = gain / math.hypot(value[1], current[1]) if gain > 0 else 0.0
            if best is None or gain > best:
                best, best_z, best_move = gain, z, move
        log(f"  {objective} round {round_number} step {step}: best z {best_z:.1f}")
        if best_move is not None and best_z >= Z_NEEDED:
            state = best_move
        elif step_index + 1 < len(STEPS):
            step_index += 1
        else:
            break
    return state


def analyse(runner: Runner, groups: list[list[str]], log) -> dict[str, Any]:
    ratings, _ = runner.run([{s: 0 for s in STATS}])
    base = {s: float(ratings[s] or 0) for s in STATS}
    total = sum(base.values())
    shares = priority_shares(groups)
    target = {s: round(total * shares[s]) for s in STATS}
    splits: dict[str, dict[str, int]] = {"guide": {s: 0 for s in STATS},
                                         "priority": {s: int(target[s] - base[s]) for s in STATS}}
    for objective in OBJECTIVES:
        splits[objective] = climb(runner, base, objective, log)
    # Everything compared head to head in one run per seed, tighter error.
    names = {key: name_of(split) for key, split in splits.items()}
    seeds = []
    for seed in (201, 202):
        _r, results = runner.run(list(splits.values()), target_error=0.05, iterations=30000, seed=seed)
        seeds.append({key: results[name] for key, name in names.items()})
    merged = {key: {m: (sum(s[key][m][0] for s in seeds) / len(seeds), max(s[key][m][1] for s in seeds))
                    for m in ("dps", "dtps")} for key in splits}
    return {"base": base, "splits": {k: {s: base[s] + v[s] for s in STATS} for k, v in splits.items()}, "metrics": merged}


def render_md(document: dict[str, Any]) -> str:
    lines = [
        "# Where the guide's Damage priority leans (simulation estimate)", "",
        "Same guide loadout, same total secondary rating; only the split changes. Percent against the guide's own split.", "",
        "| Spec | Split | dps | damage taken | Rating (crit/haste/mastery/vers) |", "|---|---|---|---|---|",
    ]
    for entry in document["results"]:
        if entry.get("skipped"):
            lines.append(f"| {entry['spec']} | skipped: {entry['skipped']} | | | |")
            continue
        r = entry["result"]
        base = r["metrics"]["guide"]
        for key in ("guide", "priority", "dps", "balance", "survival"):
            m = r["metrics"][key]
            dps = 100 * (m["dps"][0] / base["dps"][0] - 1)
            dtps = 100 * (m["dtps"][0] / base["dtps"][0] - 1)
            ratings = "/".join(f"{r['splits'][key][s]:.0f}" for s in STATS)
            lines.append(f"| {entry['spec']} | {key} | {dps:+.2f}% | {dtps:+.2f}% | {ratings} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--specs", required=True)
    parser.add_argument("--goal", default="MYTHIC_PLUS")
    parser.add_argument("--fight", default="", help="extra SimC fight lines, comma separated (default: Patchwerk)")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--out", type=Path, default=Path("docs/guide-lean-probe"))
    args = parser.parse_args(argv)
    wanted = set(args.specs.split(","))
    fetched = fetch_all()
    specs = build(fetched.sources)
    results: list[dict[str, Any]] = []
    document = {"buildId": fetched.build_id, "results": results}
    # Patchwerk: SimC's DungeonSlice fight has the tank take no damage at all (dtps 0), so it cannot be used here.
    fight = tuple(args.fight.split(",")) if args.fight else ()

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".json").write_text(json.dumps(document, indent=1, sort_keys=True), encoding="utf-8")
        args.out.with_suffix(".md").write_text(render_md(document), encoding="utf-8")

    failed = False
    for spec_key, fields in specs.items():
        catalog_key = _classcodex_key_to_catalog_key(spec_key)
        if catalog_key not in wanted or catalog_key not in SPEC_BY_KEY:
            continue
        spec = SPEC_BY_KEY[catalog_key]
        entry = {"spec": catalog_key, "goal": args.goal}
        try:
            gear_value = (fields.get("gear") or {}).get("value")
            talents_value = (fields.get("talents") or {}).get("value")
            hero = sorted(_hero_talent_keys(gear_value, talents_value))[0]
            exports = talent_exports_from_entries(select_goal_context(talents_value, hero, args.goal))
            items = build_simc_items(guide_gear_list(gear_value, args.goal), loadout_upgrades_for(fields, hero, args.goal))
            priority = default_priority((fields.get("statPriority") or {}).get("value"), hero, args.goal)
            groups = (priority or {}).get("secondary") or []
            if not (items and exports and groups):
                raise RuntimeError("no gear, talents or priority")
            entry["heroTalent"], entry["priority"] = hero, groups
            runner = Runner(args.simc_bin, spec, items, exports, fight, args.threads)
            entry["result"] = analyse(runner, groups, lambda m: print(m, flush=True))
        except Exception as exc:  # noqa: BLE001  one spec failing must not lose the others
            entry["skipped"] = f"{type(exc).__name__}: {exc}"
            failed = True
        results.append(entry)
        save()
        print(f"done {catalog_key}", flush=True)
    save()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
