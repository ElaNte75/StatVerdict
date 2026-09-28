"""Extracts real per-secondary-stat DPS/HPS-per-point weights from a
SimulationCraft calculate_scale_factors=1 json2 report. Field names here
are pinned to the documented-shape fixture (not a live capture; see README) at
tools/tests/fixtures/simc_scale_factor_report.json, produced by
docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline.md Task 8.

Also batch-builds those weights across every ClassCodex spec/goal/hero-talent
combo by reusing the BiS-reconstruction helpers from tools/classcodex_targets.py
(Task 10).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from tools.classcodex_targets import (
        GOAL_CONTEXT_KEY,
        _classcodex_key_to_catalog_key,
        _hero_talent_keys,
        build_simc_items,
        select_context,
        select_talent_export,
    )
    from tools.live_benchmark_engine import SPEC_BY_KEY
    from tools.simc_stat_engine import render_profiles, run_simc
except ModuleNotFoundError:
    from classcodex_targets import (
        GOAL_CONTEXT_KEY,
        _classcodex_key_to_catalog_key,
        _hero_talent_keys,
        build_simc_items,
        select_context,
        select_talent_export,
    )
    from live_benchmark_engine import SPEC_BY_KEY
    from simc_stat_engine import render_profiles, run_simc

SCALE_FACTOR_STATS = ("crit_rating", "haste_rating", "mastery_rating", "versatility_rating")
SIMC_TO_CANONICAL = {
    "crit_rating": "crit",
    "haste_rating": "haste",
    "mastery_rating": "mastery",
    "versatility_rating": "versatility",
}


def _players(report: dict[str, Any]) -> list[dict[str, Any]]:
    sim = report.get("sim", report)
    players = sim.get("players") or sim.get("player") or []
    return players if isinstance(players, list) else []


def parse_scale_factors(report: dict[str, Any]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for actor in _players(report):
        name = actor.get("name")
        if not isinstance(name, str):
            continue
        scaling = actor.get("scaling")
        if not isinstance(scaling, dict):
            raise ValueError(f"actor '{name}' has no 'scaling' block in its SimC report -- report shape changed")
        metric = scaling.get("dps") if isinstance(scaling.get("dps"), dict) else scaling
        weights: dict[str, float] = {}
        for raw_key, canonical in SIMC_TO_CANONICAL.items():
            value = metric.get(raw_key) if isinstance(metric, dict) else None
            if isinstance(value, (int, float)):
                weights[canonical] = float(value)
        if len(weights) < len(SIMC_TO_CANONICAL):
            missing = sorted(set(SIMC_TO_CANONICAL.values()) - set(weights))
            raise ValueError(f"actor '{name}' scaling data is missing: {', '.join(missing)}")
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
    items = build_simc_items(gear_list)
    if not items:
        return None
    talent_loadout = select_talent_export(talents_value, hero_talent_key, context_key)
    if not talent_loadout:
        return None

    record = {"race": "human", "runTalentLoadout": talent_loadout, "items": items, "level": 90}
    profile_text, actor_map = render_profiles(spec, [record])
    profile_text = profile_text.replace("calculate_scale_factors=0", "calculate_scale_factors=1")
    try:
        _stats_by_actor, report = run_simc(simc_binary, profile_text)
        weights_by_actor = parse_scale_factors(report)
    except Exception:  # noqa: BLE001 - fail closed; caller skips this combo
        return None
    actor_name = next(iter(actor_map))
    weights = weights_by_actor.get(actor_name)
    if not weights:
        return None
    highest = max(weights.values())
    if highest <= 0:
        return None
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
            context_key = GOAL_CONTEXT_KEY[goal]
            hero_talents_out: dict[str, Any] = {}
            for hero_talent_key in _hero_talent_keys(gear_value, talents_value):
                gear_list = select_context(gear_value, hero_talent_key, context_key)
                if not isinstance(gear_list, list) or not gear_list:
                    continue
                weights = build_weight_context(spec, gear_list, talents_value, hero_talent_key, context_key, simc_binary)
                if weights:
                    hero_talents_out[hero_talent_key] = weights
            if hero_talents_out:
                goals_out[goal] = hero_talents_out
        if goals_out:
            profiles[spec_key] = goals_out
    return {"profiles": profiles}
