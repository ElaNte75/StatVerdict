#!/usr/bin/env python3
"""Extract StatVerdictBridge SavedVariables export into SV_ProfileData files."""

from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_PROFILE_COUNT = 40
MAX_GENERATED_AGE_DAYS = 30
MAX_SCRAPE_AGE_DAYS = 120
MIN_CONTEXT_ITEMS = 10
MAX_LOW_ITEM_RATIO = 0.25


def find_bridge_sv(wtf_account_root: Path) -> Path:
    matches = sorted(wtf_account_root.rglob("StatVerdictBridge.lua"))
    if not matches:
        raise FileNotFoundError(
            f"No StatVerdictBridge.lua under {wtf_account_root}. "
            "Export in-game with /svbridge, then /reload."
        )
    # Prefer newest mtime.
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def extract_chunks(sv_text: str) -> list[str]:
    # Locate export.chunks array contents.
    m = re.search(r'\["chunks"\]\s*=\s*\{(.*?)\n\}', sv_text, flags=re.S)
    if not m:
        # Alternate without quotes on key
        m = re.search(r"\bchunks\s*=\s*\{(.*?)\n\}", sv_text, flags=re.S)
    if not m:
        raise ValueError("Could not find export.chunks in SavedVariables.")

    body = m.group(1)
    chunks = re.findall(r'"([^"]*)"', body)
    if not chunks:
        raise ValueError("export.chunks is empty.")
    return chunks


def lua_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def to_lua(value, indent: int = 0) -> str:
    pad = "    " * indent
    pad1 = "    " * (indent + 1)
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        # Keep ints clean.
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return lua_string(value)
    if isinstance(value, list):
        if not value:
            return "{}"
        lines = ["{"]
        for item in value:
            lines.append(f"{pad1}{to_lua(item, indent + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        # Stable-ish: sort keys, but keep profiles nested natural.
        for key in sorted(value.keys(), key=lambda k: str(k)):
            lua_key = f'["{key}"]' if not str(key).isidentifier() else key
            # Always quote string keys to match existing StatVerdict style.
            lua_key = f'["{str(key)}"]'
            lines.append(f"{pad1}{lua_key} = {to_lua(value[key], indent + 1)},")
        lines.append(f"{pad}}}")
        return "\n".join(lines)
    raise TypeError(f"Unsupported type: {type(value)}")


def write_outputs(profile_data: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "SV_ProfileData.json"
    lua_path = out_dir / "SV_ProfileData.lua"

    json_path.write_text(json.dumps(profile_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lua = (
        "local addonName, ns = ...\n\n"
        "-- Generated file. Do not edit manually.\n"
        "ns.GeneratedProfileData = "
        + to_lua(profile_data, 0)
        + "\n"
    )
    lua_path.write_text(lua, encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {lua_path}")


def parse_date(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing date")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def positive_target_count(targets: object) -> int:
    if not isinstance(targets, dict):
        return 0
    stats = targets.get("stats")
    if not isinstance(stats, dict):
        return 0
    return sum(1 for value in stats.values() if isinstance(value, (int, float)) and value > 0)


def validate_profile_data(profile_data: dict) -> None:
    errors: list[str] = []
    now = datetime.now(timezone.utc)
    source = profile_data.get("source")
    profiles = profile_data.get("profiles")
    if profile_data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if not isinstance(source, dict):
        errors.append("source metadata is missing")
        source = {}
    if not isinstance(profiles, dict) or len(profiles) != EXPECTED_PROFILE_COUNT:
        errors.append(f"expected {EXPECTED_PROFILE_COUNT} profiles")
        profiles = profiles if isinstance(profiles, dict) else {}

    for label, value, max_days in (
        ("generatedAt", profile_data.get("generatedAt"), MAX_GENERATED_AGE_DAYS),
        ("source.scrape", source.get("scrape"), MAX_SCRAPE_AGE_DAYS),
    ):
        try:
            age = (now - parse_date(value)).total_seconds() / 86400
            if age < -1 or age > max_days:
                errors.append(f"{label} age {age:.1f}d exceeds {max_days}d")
        except (TypeError, ValueError):
            errors.append(f"{label} is missing or invalid")

    summary = source.get("resolveSummary")
    resolved = summary.get("resolved", 0) if isinstance(summary, dict) else 0
    total = summary.get("total", 0) if isinstance(summary, dict) else 0
    if not isinstance(total, (int, float)) or total <= 0:
        errors.append("resolver summary is missing")
    elif not isinstance(resolved, (int, float)) or resolved / total < 0.99:
        errors.append("resolver success rate is below 99%")

    expected_goals = {"MYTHIC_PLUS", "RAID", "PVP"}
    for spec_key, profile in profiles.items():
        contexts = profile.get("contexts") if isinstance(profile, dict) else None
        if not isinstance(contexts, dict) or set(contexts) != expected_goals:
            errors.append(f"{spec_key}: expected exactly three goal contexts")
            continue
        for goal in sorted(expected_goals):
            context = contexts.get(goal)
            targets = context.get("targets") if isinstance(context, dict) else None
            bis = context.get("bis") if isinstance(context, dict) else None
            slots = bis.get("slots") if isinstance(bis, dict) else None
            if not isinstance(targets, dict):
                errors.append(f"{spec_key}/{goal}: targets missing")
                continue
            if targets.get("sourceGoal") != goal:
                errors.append(f"{spec_key}/{goal}: sourceGoal mismatch")
            if positive_target_count(targets.get("statTargets")) < 2:
                errors.append(f"{spec_key}/{goal}: fewer than two stat targets")
            if not isinstance(slots, list) or len(slots) < MIN_CONTEXT_ITEMS:
                errors.append(f"{spec_key}/{goal}: incomplete BiS reference set")

            item_count = targets.get("itemCount") or 0
            if goal == "PVP":
                if item_count != 0 or targets.get("averageItemLevel") is not None:
                    errors.append(f"{spec_key}/{goal}: cross-goal resolved gear totals")
                continue
            average = targets.get("averageItemLevel")
            if not isinstance(average, (int, float)) or average < 250:
                errors.append(f"{spec_key}/{goal}: implausible average item level")
            if not isinstance(item_count, (int, float)) or item_count < MIN_CONTEXT_ITEMS:
                errors.append(f"{spec_key}/{goal}: incomplete resolved target set")
            metadata = targets.get("targetMetadata")
            low_items = metadata.get("lowItemReplacements", 0) if isinstance(metadata, dict) else 0
            if item_count and low_items / item_count > MAX_LOW_ITEM_RATIO:
                errors.append(f"{spec_key}/{goal}: too many low-level replacements")

    if errors:
        preview = "\n".join(f"- {message}" for message in errors[:50])
        extra = len(errors) - 50
        suffix = f"\n- ... and {extra} more" if extra > 0 else ""
        raise ValueError(f"Profile quality validation failed:\n{preview}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sv", type=Path, help="Path to StatVerdictBridge.lua SavedVariables")
    parser.add_argument("--wtf-account", type=Path, help="WTF Account root to search")
    parser.add_argument("--out", type=Path, required=True, help="Data/Generated output directory")
    args = parser.parse_args()

    if args.sv:
        sv_path = args.sv
    elif args.wtf_account:
        sv_path = find_bridge_sv(args.wtf_account)
    else:
        raise SystemExit("Provide --sv or --wtf-account")

    print(f"Reading {sv_path}")
    text = sv_path.read_text(encoding="utf-8", errors="replace")
    if 'StatVerdictBridgeDB' not in text:
        raise SystemExit("StatVerdictBridgeDB not found in SavedVariables.")

    chunks = extract_chunks(text)
    b64 = "".join(chunks)
    raw = base64.b64decode(b64)
    profile_data = json.loads(raw.decode("utf-8"))

    if not isinstance(profile_data, dict) or "profiles" not in profile_data:
        raise SystemExit("Decoded payload is not a valid profile database.")

    try:
        validate_profile_data(profile_data)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    write_outputs(profile_data, args.out)
    profiles = profile_data.get("profiles") or {}
    print(f"Profiles: {len(profiles)}")
    print(f"generatedAt: {profile_data.get('generatedAt')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
