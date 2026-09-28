"""Extracts real per-secondary-stat DPS/HPS-per-point weights from a
SimulationCraft calculate_scale_factors=1 json2 report, and batch-builds
them across every ClassCodex spec/goal/hero-talent combo by reusing the
BiS-reconstruction helpers from tools/classcodex_targets.py.

Report shape VERIFIED against SimC's own source (simulationcraft/simc,
branch `midnight`, read 2026-09-28): engine/report/json/report_json.cpp
writes, per entry of `sim.players[]`, a `scale_factors` object (for the
sim's single `scaling_metric`) and a `scale_factors_all` object keyed by
util::scale_metric_type_abbrev ("dps", "hps", "dtps", ...), each mapping
util::stat_type_abbrev names ("Crit", "Haste", "Mastery", "Vers", "Str",
"Agi", "Int", ...) to the raw per-point value (not normalized unless
normalize_scale_factors is set, which this module never does). Both are
only written when scale factors were actually calculated. See
tools/tests/fixtures/simc_scale_factor_report.README.md.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from tools.classcodex_targets import (
        CANONICAL_SECONDARY_STATS,
        ComboSkipped,
        _classcodex_key_to_catalog_key,
        _hero_talent_keys,
        build_simc_items,
        canonical_stat_name,
        select_goal_context,
        select_talent_export,
        talent_export_from_entries,
    )
    from tools.live_benchmark_engine import SPEC_BY_KEY
    from tools.simc_stat_engine import render_profiles, run_simc
except ModuleNotFoundError:
    from classcodex_targets import (
        CANONICAL_SECONDARY_STATS,
        ComboSkipped,
        _classcodex_key_to_catalog_key,
        _hero_talent_keys,
        build_simc_items,
        canonical_stat_name,
        select_goal_context,
        select_talent_export,
        talent_export_from_entries,
    )
    from live_benchmark_engine import SPEC_BY_KEY
    from simc_stat_engine import render_profiles, run_simc

# SimC long stat names for its `scale_only=` filter (SimC's parse_stat_type
# accepts these; verified in engine/util/util.cpp + scale_factor_control.cpp).
# Restricting the run to the four secondaries this project scores avoids
# spending sim time on primary-stat/stamina deltas nobody reads.
SCALE_FACTOR_STATS = ("crit_rating", "haste_rating", "mastery_rating", "versatility_rating")

# Settings for a real (not noise) scale-factor run. Paper-doll
# reconstruction's 1-iteration/1-second defaults would make every weight
# statistical noise. SimC runs one baseline sim plus one delta sim per
# scaled stat (5 sims here), each with these settings:
#   - target_error=0.1: stop once the DPS mean's error is below 0.1%, the
#     precision commonly used for stat weights;
#   - iterations=10000: hard cap on that, so a slow/noisy spec cannot run
#     away with the CI budget;
#   - max_time=300 + fixed_time=1: SimC's standard 5-minute single-target
#     (Patchwerk-style) fight.
# Rough budget: ~10k iterations x 5 sims on 4 threads is well under a
# minute per combo for typical specs; ~40 combos per workflow shard fits
# comfortably inside the shard's timeout (.github/workflows/classcodex-stat-weights.yml).
SCALE_FACTOR_SIM_SETTINGS: dict[str, Any] = {
    "iterations": 10000,
    "target_error": 0.1,
    "max_time": 300,
    "fixed_time": 1,
    "calculate_scale_factors": True,
    "scale_only": SCALE_FACTOR_STATS,
}
# Per-SimC-process safety net only (a hung run should not eat the whole
# shard's timeout); normal runs finish far below it.
SCALE_FACTOR_TIMEOUT_SECONDS = 1200


def scale_factor_threads() -> int:
    """All cores of the runner (GitHub's standard ubuntu-latest has 4). The
    weights pipeline runs one SimC process at a time, unlike the Raider.IO
    pipeline, which keeps run_simc's threads=1 default and parallelizes
    across worker processes instead."""
    return max(1, os.cpu_count() or 1)


def scale_metric_for_role(role: str) -> str:
    """SimC metric (util::scale_metric_type_abbrev) whose scale factors
    measure what this role actually cares about."""
    return "hps" if role == "healer" else "dps"


def _players(report: dict[str, Any]) -> list[dict[str, Any]]:
    sim = report.get("sim", report)
    players = sim.get("players") or sim.get("player") or []
    return players if isinstance(players, list) else []


def parse_scale_factors(report: dict[str, Any], metric: str = "dps") -> dict[str, dict[str, float]]:
    """Returns {actor name: {canonical stat: raw per-point value}} for the
    four secondary stats, read from `players[].scale_factors_all[metric]`.
    Raises ValueError (fail closed) if an actor lacks that block or any of
    the four stats."""
    result: dict[str, dict[str, float]] = {}
    for actor in _players(report):
        name = actor.get("name")
        if not isinstance(name, str):
            continue
        all_metrics = actor.get("scale_factors_all")
        if not isinstance(all_metrics, dict):
            raise ValueError(
                f"actor '{name}' has no 'scale_factors_all' block in its SimC report -- "
                "scale factors were not calculated, or the report shape changed"
            )
        by_stat = all_metrics.get(metric)
        if not isinstance(by_stat, dict):
            raise ValueError(f"actor '{name}' has no '{metric}' scale factors")
        weights: dict[str, float] = {}
        for raw_key, value in by_stat.items():
            canonical = canonical_stat_name(raw_key)
            if canonical is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
                weights[canonical] = float(value)
        missing = [stat for stat in CANONICAL_SECONDARY_STATS if stat not in weights]
        if missing:
            raise ValueError(f"actor '{name}' '{metric}' scale factors are missing: {', '.join(missing)}")
        result[name] = weights
    return result


def build_weight_context(
    spec: Any,
    gear_list: list[dict[str, Any]] | None,
    talents_value: dict[str, Any] | None,
    hero_talent_key: str,
    context_key: str,
    simc_binary: Path,
) -> dict[str, float] | None:
    """Runs one spec/goal/hero-talent's BiS gear loadout through SimulationCraft
    with calculate_scale_factors enabled and normalizes the resulting per-stat
    weights against the highest-weighted stat. Returns None if there is no
    gear, no talent export, or the SimC run fails or yields no weights."""
    try:
        return compute_weight_context(
            spec, gear_list, select_talent_export(talents_value, hero_talent_key, context_key), simc_binary
        )
    except ComboSkipped:
        return None


def compute_weight_context(
    spec: Any,
    gear_list: list[dict[str, Any]] | None,
    talent_loadout: str | None,
    simc_binary: Path,
) -> dict[str, float]:
    """build_weight_context's core, taking an already-selected talent export.
    Raises ComboSkipped (never returns None) so callers can report why."""
    items = build_simc_items(gear_list)
    if not items:
        raise ComboSkipped("no usable gear for this goal")
    if not talent_loadout:
        raise ComboSkipped("no talent export for this goal")

    record = {"race": "human", "runTalentLoadout": talent_loadout, "items": items, "level": 90}
    profile_text, actor_map = render_profiles(spec, [record], **SCALE_FACTOR_SIM_SETTINGS)
    try:
        _stats_by_actor, report = run_simc(
            simc_binary,
            profile_text,
            timeout_seconds=SCALE_FACTOR_TIMEOUT_SECONDS,
            threads=scale_factor_threads(),
        )
    except Exception as exc:  # noqa: BLE001 - fail closed; caller skips this combo
        raise ComboSkipped(f"SimC run failed ({type(exc).__name__})") from exc
    metric = scale_metric_for_role(spec.role)
    try:
        weights_by_actor = parse_scale_factors(report, metric)
    except ValueError as exc:
        raise ComboSkipped(f"scale-factor report unusable ({metric})") from exc
    actor_name = next(iter(actor_map))
    weights = weights_by_actor.get(actor_name)
    if not weights:
        raise ComboSkipped("SimC report had no scale factors for the actor")
    # Real per-point values for the four secondaries of a live spec are never
    # negative; a negative one means the sim was noise-dominated. Fail closed
    # rather than ship it.
    if any(value < 0 for value in weights.values()):
        raise ComboSkipped(f"negative {metric} scale factor (noise)")
    highest = max(weights.values())
    if highest <= 0:
        raise ComboSkipped(f"no positive {metric} scale factor")
    return {stat: value / highest for stat, value in weights.items()}


def build_all_weights(
    specs: dict[str, dict[str, Any]],
    simc_binary: Path,
    goals: tuple[str, ...] = ("MYTHIC_PLUS", "RAID", "PVP"),
) -> dict[str, Any]:
    """Loops over every ClassCodex spec/goal/hero-talent combo, deriving real
    per-stat SimC scale-factor weights for each, and assembles the full
    per-spec document. Skips spec keys not in the SPEC_BY_KEY catalog and
    goals with no usable hero-talent context anywhere."""
    profiles: dict[str, Any] = {}
    for spec_key, fields in specs.items():
        catalog_key = _classcodex_key_to_catalog_key(spec_key)
        spec = SPEC_BY_KEY.get(catalog_key)
        if spec is None:
            continue
        gear_value = (fields.get("gear") or {}).get("value")
        talents_value = (fields.get("talents") or {}).get("value")

        goals_out: dict[str, Any] = {}
        for goal in goals:
            hero_talents_out: dict[str, Any] = {}
            for hero_talent_key in sorted(_hero_talent_keys(gear_value, talents_value)):
                gear_list = select_goal_context(gear_value, hero_talent_key, goal)
                if not isinstance(gear_list, list) or not gear_list:
                    continue
                talent_loadout = talent_export_from_entries(select_goal_context(talents_value, hero_talent_key, goal))
                try:
                    weights = compute_weight_context(spec, gear_list, talent_loadout, simc_binary)
                except ComboSkipped:
                    continue
                hero_talents_out[hero_talent_key] = weights
            if hero_talents_out:
                goals_out[goal] = hero_talents_out
        if goals_out:
            profiles[spec_key] = goals_out
    return {"profiles": profiles}
