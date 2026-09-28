"""Builds per-goal, per-spec, per-hero-talent BiS stat targets from the
already-merged ClassCodex data (tools/classcodex_build.py) by reconstructing
paper-doll stats through SimulationCraft (tools/simc_stat_engine.py) — the
same engine already proven on Raider.IO run gear.

See docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline-spec.md
for the full design and the real data shapes this module relies on.
"""
from __future__ import annotations

from typing import Any

CLASSCODEX_SLOT_TO_SIMC: dict[str, str] = {
    "Head": "HEAD",
    "Neck": "NECK",
    "Shoulders": "SHOULDER",
    "Back": "BACK",
    "Chest": "CHEST",
    "Wrist": "WRIST",
    "Hands": "HANDS",
    "Waist": "WAIST",
    "Legs": "LEGS",
    "Feet": "FEET",
    "Finger 1": "FINGER_1",
    "Finger 2": "FINGER_2",
    "Trinket 1": "TRINKET_1",
    "Trinket 2": "TRINKET_2",
    "Main Hand": "MAIN_HAND",
    "Off Hand": "OFF_HAND",
}

GOAL_CONTEXT_KEY: dict[str, str] = {
    "MYTHIC_PLUS": "mplus",
    "RAID": "raid",
    "PVP": "pvp",
}

FALLBACK_CONTEXT_KEY = "all"


def select_context(nested: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> Any | None:
    """nested is a ClassCodex `{heroTalentKey: {contextKey: value}}` field
    (gear, talents, trinkets or statPriority's `.value`). Returns the exact
    goal context if present, else the `"all"` fallback, else None."""
    if not isinstance(nested, dict):
        return None
    by_context = nested.get(hero_talent_key)
    if not isinstance(by_context, dict):
        return None
    if context_key in by_context:
        return by_context[context_key]
    return by_context.get(FALLBACK_CONTEXT_KEY)
