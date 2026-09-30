#!/usr/bin/env python3
"""Reconstruct paper-doll stats (and scale factors) from exact gear loadouts using SimC."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SIMC_SLOT_MAP = {
    "HEAD": "head",
    "NECK": "neck",
    "SHOULDER": "shoulders",
    "BACK": "back",
    "CHEST": "chest",
    "WRIST": "wrists",
    "HANDS": "hands",
    "WAIST": "waist",
    "LEGS": "legs",
    "FEET": "feet",
    "FINGER_1": "finger1",
    "FINGER_2": "finger2",
    "TRINKET_1": "trinket1",
    "TRINKET_2": "trinket2",
    "MAIN_HAND": "main_hand",
    "OFF_HAND": "off_hand",
}

SIMC_CLASS_MAP = {
    "death-knight": "deathknight",
    "demon-hunter": "demonhunter",
}


def simc_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return token


def render_item(slot: str, item: dict[str, Any]) -> str:
    simc_slot = SIMC_SLOT_MAP[slot]
    fields = [f"id={int(item['itemId'])}"]
    item_level = item.get("itemLevel")
    if isinstance(item_level, (int, float)):
        fields.append(f"ilevel={int(round(item_level))}")
    for source_key, simc_key in (
        ("bonusIds", "bonus_id"),
        ("gemIds", "gem_id"),
        ("enchantIds", "enchant_id"),
    ):
        values = [int(value) for value in item.get(source_key, []) if isinstance(value, (int, float))]
        if values:
            fields.append(f"{simc_key}=" + "/".join(str(value) for value in values))
    return f"{simc_slot}=," + ",".join(fields)


def render_player(
    *,
    actor_name: str,
    class_name: str,
    spec_name: str,
    role: str,
    race: str,
    talent_loadout: str,
    items: dict[str, dict[str, Any]],
    level: int = 90,
    stat_sheet_only: bool = False,
    talents_optional: bool = False,
) -> str:
    """`stat_sheet_only` adds `default_actions=0`, so SimC does not build the
    spec's default action list: a paper-doll run only reads the stat sheet,
    and an outdated default APL (e.g. Holy/Discipline Priest) would otherwise
    fail the whole run. `talents_optional` lets an empty loadout omit the
    `talents=` line (last-resort run when SimC rejects every export)
    instead of raising."""
    if not talent_loadout and not talents_optional:
        raise ValueError(f"{actor_name}: talent loadout is required")
    class_token = SIMC_CLASS_MAP.get(class_name.casefold(), simc_token(class_name))
    lines = [
        f'{class_token}="{actor_name}"',
        f"level={level}",
        f"race={simc_token(race)}",
        f"spec={simc_token(spec_name)}",
    ]
    if talent_loadout:
        lines.append(f"talents={talent_loadout}")
    if stat_sheet_only:
        lines.append("default_actions=0")
    if role == "tank":
        lines.append("role=tank")
    elif role == "healer":
        lines.append("role=heal")
    for slot in SIMC_SLOT_MAP:
        item = items.get(slot)
        if item:
            lines.append(render_item(slot, item))
    return "\n".join(lines)


def render_profiles(
    spec: Any,
    records: list[dict[str, Any]],
    *,
    iterations: int = 1,
    max_time: int = 1,
    fixed_time: int = 1,
    calculate_scale_factors: bool = False,
    scale_only: tuple[str, ...] | None = None,
    target_error: float | None = None,
    seed: int | None = None,
    extra_lines: tuple[str, ...] = (),
    global_lines: tuple[str, ...] = (),
    stat_sheet_only: bool = False,
    talents_optional: bool = False,
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Renders a SimC profile for one or more actors of `spec`.

    The defaults (1 iteration, 1-second fight, no scale factors) are for
    paper-doll reconstruction, where only the buffed stat sheet is read and
    combat outcomes are irrelevant. Scale-factor runs need real statistical
    power and must override them (see tools/classcodex_weights.py).
    `scale_only` is SimC's comma-separated stat filter (SimC splits on
    ",:;/|" and accepts its long stat names, e.g. "crit_rating").
    `target_error`, when set, lets SimC stop early once the DPS error is
    below that percentage, with `iterations` acting as the cap."""
    blocks = [
        f"iterations={int(iterations)}",
        f"max_time={int(max_time)}",
        f"fixed_time={int(fixed_time)}",
        f"calculate_scale_factors={1 if calculate_scale_factors else 0}",
    ]
    if scale_only:
        blocks.append("scale_only=" + ",".join(scale_only))
    if target_error is not None:
        blocks.append(f"target_error={target_error}")
    if seed is not None:
        blocks.append(f"seed={int(seed)}")
    blocks += list(global_lines)
    blocks += [
        "report_details=0",
        "allow_experimental_specializations=1",
    ]
    actor_map = {}
    for index, record in enumerate(records, 1):
        actor_name = f"sv_{index:04d}"
        blocks.append(
            render_player(
                actor_name=actor_name,
                class_name=spec.class_name,
                spec_name=spec.spec_name,
                role=spec.role,
                race=record.get("race") or "human",
                talent_loadout=record.get("runTalentLoadout") or "",
                items=record["items"],
                level=int(record.get("level") or 90),
                stat_sheet_only=stat_sheet_only,
                talents_optional=talents_optional,
            )
        )
        actor_map[actor_name] = record
    if extra_lines:
        # After the players: SimC profilesets refer to the actor defined above them.
        blocks.append("\n".join(extra_lines))
    return "\n\n".join(blocks) + "\n", actor_map


def _players(report: dict[str, Any]) -> list[dict[str, Any]]:
    sim = report.get("sim", report)
    players = sim.get("players") or sim.get("player") or []
    return players if isinstance(players, list) else []


def parse_gear_item_levels(actor: dict[str, Any]) -> dict[str, float]:
    """{SimC slot name: item level} of the items SimC actually equipped.

    VERIFIED against simulationcraft/simc branch `midnight` (read
    2026-09-29), engine/report/json/report_json.cpp: the player's to_json
    calls `gear_to_json( root[ "gear" ], p )` (line 888) unconditionally
    (not gated by report_details), and gear_to_json (line 382) writes, per
    slot, `root[ item.slot_name() ]` with "name", "encoded_item" and
    "ilevel" = item.item_level() (line 395) plus the item's stat values.
    Slot names are util::slot_type_string ("head", "shoulders", "wrists",
    "finger1", "trinket1", "main_hand", ...). Items that are inactive or
    carry no stats at all (item_t::has_stats) are NOT written, so the map
    can miss a slot."""
    gear = actor.get("gear")
    levels: dict[str, float] = {}
    if not isinstance(gear, dict):
        return levels
    for slot_name, slot in gear.items():
        ilevel = slot.get("ilevel") if isinstance(slot, dict) else None
        if isinstance(ilevel, (int, float)) and not isinstance(ilevel, bool) and ilevel > 0:
            levels[str(slot_name)] = float(ilevel)
    return levels


def parse_report(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per actor: buffed secondary ratings/percentages, attributes, health,
    armor, and `item_levels` (parse_gear_item_levels)."""
    output = {}
    for actor in _players(report):
        name = actor.get("name")
        buffed = actor.get("collected_data", {}).get("buffed_stats", {})
        attributes = buffed.get("attribute", {})
        stats = buffed.get("stats", {})
        resources = buffed.get("resources", {})
        if not isinstance(name, str) or not isinstance(stats, dict):
            continue
        output[name] = {
            "ratings": {
                "crit": stats.get("crit_rating"),
                "haste": stats.get("haste_rating"),
                "mastery": stats.get("mastery_rating"),
                "versatility": stats.get("versatility_rating"),
            },
            "percentages": {
                "crit": stats.get("crit_pct"),
                "haste": stats.get("haste_pct"),
                "mastery": stats.get("mastery_pct"),
                "versatility": stats.get("versatility_pct"),
            },
            "attributes": attributes,
            "health": resources.get("health"),
            "armor": stats.get("armor"),
            "item_levels": parse_gear_item_levels(actor),
        }
    return output


def run_simc(
    simc_binary: Path,
    profile_text: str,
    *,
    timeout_seconds: int = 300,
    threads: int = 1,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        profile_path = root / "profiles.simc"
        report_path = root / "report.json"
        profile_path.write_text(profile_text, encoding="utf-8")
        command = [
            str(simc_binary),
            str(profile_path),
            f"json2={report_path}",
            f"output={os.devnull}",
            f"html={os.devnull}",
            f"threads={max(1, threads)}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0 or not report_path.exists():
            detail = (completed.stderr or completed.stdout)[-4000:]
            raise RuntimeError(f"SimulationCraft failed with exit {completed.returncode}: {detail}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return parse_report(report), report


# SimC rejects a loadout that lists a 2-hander together with another weapon
# (ClassCodex lists Main Hand + Off Hand even when one of them is 2h).
WEAPON_CONFLICT_MARKERS = ("Off-Hand weapon equipped with a 2h", "both a 1-hand and 2-hand")
# Weapon slots dropped, in order, while the conflict persists (at most one
# retry per slot, so never more than two retries).
WEAPON_RECOVERY_SLOTS = ("OFF_HAND", "MAIN_HAND")


def is_weapon_conflict(message: str) -> bool:
    return any(marker in message for marker in WEAPON_CONFLICT_MARKERS)


# A SimC failure whose message mentions any of these (case-insensitive) may
# be caused by the recommended gems/enchants added to the loadout (e.g. a gem
# or enchant id SimC does not know): the run is retried without gems, then
# also without enchants, before giving up.
UPGRADE_ERROR_MARKERS = ("gem", "enchant", "socket")
# (item key stripped from every item, recovery label), in drop order.
UPGRADE_RECOVERY_STEPS = (("gemIds", "gems dropped"), ("enchantIds", "enchants dropped"))


def is_upgrade_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in UPGRADE_ERROR_MARKERS)


def run_simc_with_recovery(
    simc_binary: Path,
    spec: Any,
    record: dict[str, Any],
    *,
    render_kwargs: dict[str, Any] | None = None,
    run_kwargs: dict[str, Any] | None = None,
    run_simc_fn: Any = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str], str]:
    """Renders and runs one actor, retrying only on a SimC weapon conflict
    (first without the off-hand, then also without the main hand) or on an
    error mentioning gems/enchants/sockets (first without any gems, then
    also without any enchants). Any other error (or one that persists after
    those retries) is re-raised unchanged.
    Returns (stats_by_actor, report, recovery labels, actor name); the
    labels (e.g. ["dropped OFF_HAND"], ["gems dropped"]) say which retries
    were needed. `run_simc_fn` defaults to run_simc (injectable for tests
    and callers that patch their own reference)."""
    run = run_simc_fn or run_simc
    items = dict(record.get("items") or {})
    recovery: list[str] = []
    pending = list(WEAPON_RECOVERY_SLOTS)
    pending_upgrades = list(UPGRADE_RECOVERY_STEPS)
    while True:
        profile_text, actor_map = render_profiles(spec, [{**record, "items": items}], **(render_kwargs or {}))
        try:
            stats_by_actor, report = run(simc_binary, profile_text, **(run_kwargs or {}))
        except RuntimeError as exc:
            message = str(exc)
            droppable = [slot for slot in pending if slot in items]
            if is_weapon_conflict(message) and droppable:
                slot = droppable[0]
                pending = pending[pending.index(slot) + 1:]
                items.pop(slot)
                recovery.append(f"dropped {slot}")
                continue
            strippable = [
                step for step in pending_upgrades if any(item.get(step[0]) for item in items.values())
            ]
            if is_upgrade_error(message) and strippable:
                key, label = strippable[0]
                pending_upgrades = pending_upgrades[pending_upgrades.index(strippable[0]) + 1:]
                items = {slot: {k: v for k, v in item.items() if k != key} for slot, item in items.items()}
                recovery.append(label)
                continue
            raise
        return stats_by_actor, report, recovery, next(iter(actor_map))
