#!/usr/bin/env python3
"""Experiment: can SimulationCraft say how much each secondary stat is worth for a tank's
*survival*, and is that answer stable enough to build on?

For every tank spec, goal and hero tree it runs the same best-in-slot loadout the weights
pipeline uses (tools/classcodex_weights.py) with scale factors, and keeps the scale factors of
several metrics from the same run: dps (what Measured uses), dtps (damage taken per second),
dmg_taken, htps (healing taken: self healing and absorbs), deaths. Every loadout is run with
two seeds; the report says whether the stat order repeats, how it compares with the DPS order
and with the guide's order. It writes nothing into the addon.

  python tools/tank_survival_probe.py --simc-bin .simc-build/simc [--specs A,B] [--seeds 2]
"""
from __future__ import annotations

import argparse
import json
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
    from tools.classcodex_weights import (
        SCALE_FACTOR_SIM_SETTINGS,
        SCALE_FACTOR_TIMEOUT_SECONDS,
        parse_scale_factors,
        scale_factor_threads,
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
    from classcodex_weights import (
        SCALE_FACTOR_SIM_SETTINGS,
        SCALE_FACTOR_TIMEOUT_SECONDS,
        parse_scale_factors,
        scale_factor_threads,
    )
    from simc_stat_engine import run_simc
    from spec_catalog import SPEC_BY_KEY

STATS = ("crit", "haste", "mastery", "versatility")
# Metrics kept from every run. For the "taken" metrics smaller is better, so their value for the
# player is the negated scale factor.
METRICS = ("dps", "dtps", "dmg_taken", "htps", "deaths")
BENEFIT_SIGN = {"dps": 1.0, "dtps": -1.0, "dmg_taken": -1.0, "htps": 1.0, "deaths": -1.0}
TANK_SPECS = tuple(key for key, spec in SPEC_BY_KEY.items() if spec.role == "tank")


def order_of(values: dict[str, float]) -> list[str]:
    return sorted(STATS, key=lambda stat: -values.get(stat, 0.0))


def spearman(a: list[str], b: list[str]) -> float:
    rank_a = {stat: i for i, stat in enumerate(a)}
    rank_b = {stat: i for i, stat in enumerate(b)}
    n = len(a)
    d2 = sum((rank_a[s] - rank_b[s]) ** 2 for s in a)
    return 1 - 6 * d2 / (n * (n * n - 1))


def guide_orders(stat_priority: dict[str, Any] | None) -> dict[str, list[str]]:
    """The guide's secondary orders that exist for this spec (ties are kept in the given order)."""
    result: dict[str, list[str]] = {}
    root = (stat_priority or {}).get("value") if isinstance(stat_priority, dict) else None
    if not isinstance(root, dict):
        return result
    for tree_name, tree in root.items():
        if tree_name != "all" or not isinstance(tree, dict):
            continue
        for variant, block in tree.items():
            groups = block.get("secondary") if isinstance(block, dict) else None
            if not isinstance(groups, list):
                continue
            flat = [name for group in groups for name in (group if isinstance(group, list) else [group])]
            if all(stat in flat for stat in STATS):
                result[variant] = flat
    return result


def run_metrics(spec, gear_list, talent_loadout, simc_binary: Path, upgrades, seed: int) -> dict[str, dict[str, float]]:
    items = build_simc_items(gear_list, upgrades)
    if not items:
        raise ComboSkipped("no usable gear for this goal")
    exports = [talent_loadout] if isinstance(talent_loadout, str) else list(talent_loadout or [])
    exports = [export for export in exports if export]
    if not exports:
        raise ComboSkipped("no talent export for this goal")
    try:
        _stats, report, _recovery, actor = run_with_talent_fallback(
            simc_binary,
            spec,
            items,
            exports,
            render_kwargs={**SCALE_FACTOR_SIM_SETTINGS, "seed": seed},
            run_kwargs={"timeout_seconds": SCALE_FACTOR_TIMEOUT_SECONDS, "threads": scale_factor_threads()},
            run_simc_fn=run_simc,
        )
    except Exception as exc:  # noqa: BLE001 - reported, not fatal for the other loadouts
        print(f"SimC error for {spec.spec_name}: {format_simc_error(exc)}", file=sys.stderr)
        raise ComboSkipped(f"SimC run failed ({type(exc).__name__})") from exc
    out: dict[str, dict[str, float]] = {}
    for metric in METRICS:
        try:
            out[metric] = parse_scale_factors(report, metric).get(actor) or {}
        except ValueError:
            out[metric] = {}
    return out


def summarize(runs: list[dict[str, dict[str, float]]], guides: dict[str, list[str]]) -> dict[str, Any]:
    """Orders per metric (from the mean of the seeds), the seed-to-seed agreement, and the
    agreement with the DPS order and the guide's orders."""
    summary: dict[str, Any] = {"metrics": {}, "agreement": {}}
    orders_by_run: dict[str, list[list[str]]] = {}
    for metric in METRICS:
        per_run = []
        for run in runs:
            values = run.get(metric) or {}
            if all(stat in values for stat in STATS):
                per_run.append({s: BENEFIT_SIGN[metric] * values[s] for s in STATS})
        if not per_run:
            summary["metrics"][metric] = None
            continue
        mean = {s: sum(v[s] for v in per_run) / len(per_run) for s in STATS}
        best = max(mean.values())
        summary["metrics"][metric] = {
            "benefit": mean,
            "relative": {s: (mean[s] / best if best > 0 else None) for s in STATS},
            "order": order_of(mean),
            "per_seed_orders": [order_of(v) for v in per_run],
            "all_positive": all(v > 0 for v in mean.values()),
        }
        orders_by_run[metric] = [order_of(v) for v in per_run]
    for metric, orders in orders_by_run.items():
        if len(orders) >= 2:
            summary["agreement"][f"{metric}_seed_vs_seed"] = spearman(orders[0], orders[1])
    dps = summary["metrics"].get("dps")
    for metric in ("dtps", "dmg_taken", "htps", "deaths"):
        entry = summary["metrics"].get(metric)
        if dps and entry:
            summary["agreement"][f"dps_vs_{metric}"] = spearman(dps["order"], entry["order"])
    for guide_name, guide in guides.items():
        for metric in ("dps", "dtps", "dmg_taken"):
            entry = summary["metrics"].get(metric)
            if entry:
                summary["agreement"][f"guide_{guide_name}_vs_{metric}"] = spearman(entry["order"], list(guide))
    return summary


def render_md(document: dict[str, Any]) -> str:
    lines = [
        "# Tank survival probe (experiment)",
        "",
        "Can SimulationCraft rate each secondary stat for a tank's survival, and is the answer stable?",
        "Same best-in-slot loadouts as the Measured weights, scale factors of several metrics from one run,",
        f"{document['seeds']} seeds each. Nothing here is used by the addon. `dtps` etc. are shown as benefit",
        "(negated), so a bigger number is always better. Orders are best to worst.",
        "",
    ]
    for entry in document["results"]:
        title = f"{entry['spec']} / {entry['goal']} / {entry['heroTalent']}"
        lines += [f"## {title}", ""]
        if entry.get("skipped"):
            lines += [f"Skipped: {entry['skipped']}", ""]
            continue
        summary = entry["summary"]
        lines += ["| Metric | Order | Relative value (best = 1.00) | Seeds agree |", "|---|---|---|---|"]
        for metric in METRICS:
            data = summary["metrics"].get(metric)
            if not data:
                lines.append(f"| {metric} | no data | | |")
                continue
            relative = " / ".join(f"{s[:4]} {data['relative'][s]:.2f}" if data["relative"][s] is not None else f"{s[:4]} n/a" for s in data["order"])
            agree = summary["agreement"].get(f"{metric}_seed_vs_seed")
            positive = "" if data["all_positive"] else " (has non-positive values)"
            lines.append(f"| {metric} | {' > '.join(data['order'])} | {relative}{positive} | {'n/a' if agree is None else f'{agree:.2f}'} |")
        lines.append("")
        agreement = summary["agreement"]
        extras = {k: v for k, v in agreement.items() if not k.endswith("_seed_vs_seed")}
        if extras:
            lines.append("Order agreement (1.00 = same order, -1.00 = reversed): " + "; ".join(f"{k} {v:.2f}" for k, v in sorted(extras.items())))
            lines.append("")
        for name, order in entry.get("guide", {}).items():
            lines.append(f"Guide order ({name}): {' > '.join(order)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--specs", help="comma-separated StatVerdict spec keys (default: every tank)")
    parser.add_argument("--goals", default="MYTHIC_PLUS,RAID")
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--iterations", type=int, help="override the iteration cap (quick trial runs)")
    parser.add_argument("--out", type=Path, default=Path("docs/tank-survival-probe"))
    args = parser.parse_args(argv)
    if args.iterations:
        SCALE_FACTOR_SIM_SETTINGS["iterations"] = args.iterations
    wanted = set(args.specs.split(",")) if args.specs else set(TANK_SPECS)
    goals = tuple(args.goals.split(","))

    fetched = fetch_all()
    specs = build(fetched.sources)
    results: list[dict[str, Any]] = []
    document = {"buildId": fetched.build_id, "seeds": args.seeds, "results": results}

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
        guides = guide_orders(fields.get("statPriority"))
        for hero in sorted(_hero_talent_keys(gear_value, talents_value)):
            for goal in goals:
                base = {"spec": catalog_key, "goal": goal, "heroTalent": hero, "guide": guides}
                gear_list = select_goal_context(gear_value, hero, goal)
                loadout = talent_exports_from_entries(select_goal_context(talents_value, hero, goal))
                if not loadout:
                    for other in goals:
                        loadout = talent_exports_from_entries(select_goal_context(talents_value, hero, other))
                        if loadout:
                            break
                try:
                    runs = [
                        run_metrics(spec, gear_list, loadout, args.simc_bin, loadout_upgrades_for(fields, hero, goal), seed)
                        for seed in range(1, args.seeds + 1)
                    ]
                except ComboSkipped as skip:
                    results.append({**base, "skipped": skip.reason})
                else:
                    results.append({**base, "summary": summarize(runs, guides), "runs": runs})
                save()
                print(f"done {catalog_key} {goal} {hero}", flush=True)
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
