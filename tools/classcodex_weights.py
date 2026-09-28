"""Extracts real per-secondary-stat DPS/HPS-per-point weights from a
SimulationCraft calculate_scale_factors=1 json2 report. Field names here
are pinned to a real captured report -- see
tools/tests/fixtures/simc_scale_factor_report.json and
tools/tests/test_simc_scale_factor_report_fixture.py, produced by
docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline.md Task 8.
"""
from __future__ import annotations

from typing import Any

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
