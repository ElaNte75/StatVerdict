#!/usr/bin/env python3
"""Reconstruct paper-doll stats from exact Raider.IO run loadouts using SimC."""

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
) -> str:
    if not talent_loadout:
        raise ValueError(f"{actor_name}: talent loadout is required")
    lines = [
        f'{simc_token(class_name)}="{actor_name}"',
        f"level={level}",
        f"race={simc_token(race)}",
        f"spec={simc_token(spec_name)}",
        f"talents={talent_loadout}",
    ]
    if role == "tank":
        lines.append("role=tank")
    elif role == "healer":
        lines.append("role=heal")
    for slot in SIMC_SLOT_MAP:
        item = items.get(slot)
        if item:
            lines.append(render_item(slot, item))
    return "\n".join(lines)


def render_profiles(spec: Any, records: list[dict[str, Any]]) -> tuple[str, dict[str, dict[str, Any]]]:
    blocks = [
        "iterations=1",
        "max_time=1",
        "fixed_time=1",
        "calculate_scale_factors=0",
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
            )
        )
        actor_map[actor_name] = record
    return "\n\n".join(blocks) + "\n", actor_map


def _players(report: dict[str, Any]) -> list[dict[str, Any]]:
    sim = report.get("sim", report)
    players = sim.get("players") or sim.get("player") or []
    return players if isinstance(players, list) else []


def parse_report(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
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
