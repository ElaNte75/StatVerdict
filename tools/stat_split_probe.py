#!/usr/bin/env python3
"""Experiment: does a stat split found by simulation beat the split of the guide's best-in-slot gear?

For a DPS spec it takes the same best-in-slot loadout the Measured pipeline uses and moves rating
points between the four secondary stats (the total stays the same), simulating every move with
SimulationCraft profilesets and always taking the best one that is clearly better than the
current split, until no move helps. The result says how much DPS a better split could add and
which split that is. It is an upper bound: it ignores which real items exist.
It writes nothing into the addon.

  python tools/stat_split_probe.py --simc-bin .simc-build/simc --specs MAGE_FIRE,HUNTER_BEAST_MASTERY
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
        ComboSkipped,
        _classcodex_key_to_catalog_key,
        _hero_talent_keys,
        build_simc_items,
        format_simc_error,
        loadout_upgrades_for,
        run_with_talent_fallback,
        select_goal_context,
        talent_exports_from_entries,
    )
    from tools.simc_stat_engine import run_simc
    from tools.spec_catalog import SPEC_BY_KEY
except ModuleNotFoundError:
    from classcodex_build import build
    from classcodex_fetch import fetch_all
    from classcodex_targets import (
        ComboSkipped,
        _classcodex_key_to_catalog_key,
        _hero_talent_keys,
        build_simc_items,
        format_simc_error,
        loadout_upgrades_for,
        run_with_talent_fallback,
        select_goal_context,
        talent_exports_from_entries,
    )
    from simc_stat_engine import run_simc
    from spec_catalog import SPEC_BY_KEY

STATS = ("crit", "haste", "mastery", "versatility")
SIMC_STAT = {stat: f"enchant_{stat}_rating" for stat in STATS}  # additive manual stat lines
STEPS = (200, 100, 50)
MAX_ROUNDS = 14
Z_NEEDED = 2.0  # a move must beat the current split by this many standard errors


def variant_name(deltas: dict[str, int]) -> str:
    return "d_" + "_".join(f"{stat[:1]}{deltas[stat]:+d}" for stat in STATS)


def variant_lines(deltas: dict[str, int]) -> list[str]:
    name = variant_name(deltas)
    return [
        f'profileset."{name}"+={SIMC_STAT[stat]}={deltas[stat]}' for stat in STATS if deltas[stat] != 0
    ] or [f'profileset."{name}"+=enchant_crit_rating=0']


def candidate_moves(state: dict[str, int], base: dict[str, float], step: int) -> list[dict[str, int]]:
    """Every move of `step` rating from one stat to another that keeps all four ratings >= 0."""
    moves = []
    for give, take in itertools.permutations(STATS, 2):
        if base[give] + state[give] - step < 0:
            continue
        moved = dict(state)
        moved[give] -= step
        moved[take] += step
        moves.append(moved)
    return moves


def simulate(spec, items, exports, simc_binary: Path, variants: list[dict[str, int]], settings: dict[str, Any]):
    lines: list[str] = []
    for deltas in variants:
        lines += variant_lines(deltas)
    try:
        stats, report, _recovery, actor = run_with_talent_fallback(
            simc_binary,
            spec,
            items,
            exports,
            render_kwargs={**settings, "extra_lines": tuple(lines)},
            run_kwargs={"timeout_seconds": 3600, "threads": 4},
            run_simc_fn=run_simc,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"SimC error for {spec.spec_name}: {format_simc_error(exc)}", file=sys.stderr)
        raise ComboSkipped(f"SimC run failed ({type(exc).__name__})") from exc
    results = {}
    for entry in (report.get("sim", {}).get("profilesets") or {}).get("results", []):
        results[entry["name"]] = (float(entry["mean"]), float(entry["mean_stddev"]))
    return stats[actor]["ratings"], results


def verify(spec, items, exports, simc_binary: Path, settings: dict[str, Any], deltas: dict[str, int], seeds=(101, 102, 103)):
    """The found split against the guide's split, head to head with fresh seeds and a tighter error.
    Returns the gain of each seed (percent) and how many seeds agree that the found split is better."""
    tight = {**settings, "target_error": 0.03, "iterations": 40000}
    zero = {stat: 0 for stat in STATS}
    gains = []
    for seed in seeds:
        _ratings, results = simulate(spec, items, exports, simc_binary, [zero, deltas], {**tight, "seed": seed})
        a, b = results[variant_name(zero)], results[variant_name(deltas)]
        gains.append(100 * (b[0] - a[0]) / a[0])
    return {"gains_pct": gains, "mean_gain_pct": sum(gains) / len(gains), "seeds_better": sum(1 for g in gains if g > 0)}


def climb(spec, items, exports, simc_binary: Path, settings: dict[str, Any]) -> dict[str, Any]:
    state = {stat: 0 for stat in STATS}
    base: dict[str, float] | None = None
    history: list[dict[str, Any]] = []
    step_index = 0
    first_dps = None
    for round_number in range(1, MAX_ROUNDS + 1):
        step = STEPS[step_index]
        # The base ratings are needed to know the floor, so the first round starts from a probe.
        moves = candidate_moves(state, base, step) if base else []
        ratings, results = simulate(spec, items, exports, simc_binary, [state] + moves, settings)
        if base is None:
            base = {stat: float(ratings[stat] or 0) for stat in STATS}
            continue
        current = results.get(variant_name(state))
        if current is None:
            raise ComboSkipped("current split missing from the profileset results")
        if first_dps is None:
            first_dps = current
        scored = [(results[variant_name(m)], m) for m in moves if variant_name(m) in results]
        best = max(scored, key=lambda item: item[0][0], default=None)
        if best is not None:
            (mean, se), moved = best
            gain = mean - current[0]
            z = gain / math.hypot(se, current[1]) if gain > 0 else 0.0
        else:
            gain, z, moved, mean = 0.0, 0.0, None, current[0]
        history.append({"round": round_number, "step": step, "dps": current[0], "best_gain_pct": 100 * gain / current[0], "z": z})
        if moved is not None and z >= Z_NEEDED:
            state = moved
        elif step_index + 1 < len(STEPS):
            step_index += 1
        else:
            break
    final = results.get(variant_name(state)) or current
    check = verify(spec, items, exports, simc_binary, settings, state) if any(state.values()) else None
    return {
        "verify": check,
        "base_ratings": base,
        "deltas": state,
        "final_ratings": {stat: base[stat] + state[stat] for stat in STATS},
        "start_dps": first_dps[0],
        "final_dps": final[0],
        "gain_pct": 100 * (final[0] - first_dps[0]) / first_dps[0],
        "history": history,
    }


def order(ratings: dict[str, float]) -> list[str]:
    return sorted(STATS, key=lambda stat: -ratings[stat])


def check_text(check) -> str:
    if not check:
        return "no change to check"
    gains = " / ".join(f"{g:+.2f}%" for g in check["gains_pct"])
    return f"{gains} ({check['seeds_better']}/{len(check['gains_pct'])} better)"


def render_md(document: dict[str, Any]) -> str:
    lines = [
        "# Stat split probe (experiment)",
        "",
        "Does a better split of the same rating points beat the guide's best-in-slot split?",
        "Rating is moved between the four secondaries (total constant) and each move simulated with",
        "SimulationCraft; the best clearly better move is taken until none helps. It is an upper bound:",
        "real items may not offer that split. Nothing here is used by the addon.",
        "",
        "| Spec | Goal | Hero tree | DPS gain (search) | Head-to-head check (3 fresh seeds) | Guide split (rating order) | Best split found (rating order) | Same order |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for entry in document["results"]:
        head = f"| {entry['spec']} | {entry['goal']} | {entry['heroTalent']} |"
        if entry.get("skipped"):
            lines.append(f"{head} skipped: {entry['skipped']} | | | | |")
            continue
        r = entry["result"]
        base_order, final_order = order(r["base_ratings"]), order(r["final_ratings"])
        fmt = lambda ratings: " > ".join(f"{s[:4]} {ratings[s]:.0f}" for s in order(ratings))
        lines.append(
            f"{head} {r['gain_pct']:+.2f}% | {check_text(r.get('verify'))} | {fmt(r['base_ratings'])} | {fmt(r['final_ratings'])} | "
            f"{'yes' if base_order == final_order else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--specs", required=True, help="comma-separated StatVerdict spec keys")
    parser.add_argument("--goals", default="MYTHIC_PLUS,RAID")
    parser.add_argument("--all-hero-trees", action="store_true", help="default: the first hero tree only")
    parser.add_argument("--target-error", type=float, default=0.08)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--fight-style-mplus", default="DungeonSlice", help="SimC fight style used for the M+ goal")
    parser.add_argument("--out", type=Path, default=Path("docs/stat-split-probe-2"))
    args = parser.parse_args(argv)
    settings = {
        "iterations": args.iterations, "target_error": args.target_error,
        "max_time": 300, "fixed_time": 1,
    }

    wanted = set(args.specs.split(","))
    goals = tuple(args.goals.split(","))
    fetched = fetch_all()
    specs = build(fetched.sources)
    results: list[dict[str, Any]] = []
    document = {"buildId": fetched.build_id, "results": results}

    def save() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.with_suffix(".json").write_text(json.dumps(document, indent=1, sort_keys=True), encoding="utf-8")
        args.out.with_suffix(".md").write_text(render_md(document), encoding="utf-8")

    for spec_key, fields in specs.items():
        catalog_key = _classcodex_key_to_catalog_key(spec_key)
        if catalog_key not in wanted or catalog_key not in SPEC_BY_KEY:
            continue
        spec = SPEC_BY_KEY[catalog_key]
        gear_value = (fields.get("gear") or {}).get("value")
        talents_value = (fields.get("talents") or {}).get("value")
        heroes = sorted(_hero_talent_keys(gear_value, talents_value))
        if not args.all_hero_trees:
            heroes = heroes[:1]
        for hero in heroes:
            for goal in goals:
                base = {"spec": catalog_key, "goal": goal, "heroTalent": hero}
                exports = talent_exports_from_entries(select_goal_context(talents_value, hero, goal))
                if not exports:
                    for other in goals:
                        exports = talent_exports_from_entries(select_goal_context(talents_value, hero, other))
                        if exports:
                            break
                items = build_simc_items(select_goal_context(gear_value, hero, goal), loadout_upgrades_for(fields, hero, goal))
                try:
                    if not items or not exports:
                        raise ComboSkipped("no usable gear or talents")
                    goal_settings = dict(settings)
                    if goal == "MYTHIC_PLUS" and args.fight_style_mplus:
                        goal_settings["global_lines"] = (f"fight_style={args.fight_style_mplus}",)
                    results.append({**base, "result": climb(spec, items, exports, args.simc_bin, goal_settings)})
                except ComboSkipped as skip:
                    results.append({**base, "skipped": skip.reason})
                save()
                print(f"done {catalog_key} {goal} {hero}", flush=True)
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
