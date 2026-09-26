#!/usr/bin/env python3
"""Live proof that an exact Raider.IO run can be reconstructed by SimC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from tools.live_benchmark_engine import JsonClient, parse_run_roster_snapshot
from tools.simc_stat_engine import render_profiles, run_simc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--season", default="season-mn-2")
    parser.add_argument("--run-id", type=int, default=13135682)
    parser.add_argument("--name", default="Wazocutie")
    parser.add_argument("--realm", default="silvermoon")
    args = parser.parse_args()

    http = JsonClient(0.05)
    detail = http.request(
        "https://raider.io/api/v1/mythic-plus/run-details",
        params={"season": args.season, "id": args.run_id},
    )
    snapshot, reason = parse_run_roster_snapshot(
        detail,
        {"name": args.name, "realm": args.realm},
        "Blood",
    )
    if not snapshot:
        raise RuntimeError(reason or "No exact run snapshot")

    record = {
        "name": args.name,
        "realm": args.realm,
        "region": "eu",
        "race": snapshot.get("race"),
        "level": 90,
        "items": snapshot["items"],
        "runTalentLoadout": snapshot["talentLoadout"],
    }
    spec = SimpleNamespace(
        class_name="death-knight",
        spec_name="Blood",
        role="tank",
    )
    profile, actor_map = render_profiles(spec, [record])
    stats_by_actor, report = run_simc(args.simc_bin, profile, timeout_seconds=600)
    actor_name = next(iter(actor_map))
    stats = stats_by_actor.get(actor_name)
    if not stats:
        raise RuntimeError("SimulationCraft JSON contained no reconstructed actor stats")
    ratings = stats.get("ratings", {})
    missing = [
        key for key in ("crit", "haste", "mastery", "versatility")
        if not isinstance(ratings.get(key), (int, float))
    ]
    if missing:
        raise RuntimeError(f"SimulationCraft ratings missing: {','.join(missing)}")
    attributes = stats.get("attributes", {})
    missing_attributes = [
        key for key in ("strength", "stamina")
        if not isinstance(attributes.get(key), (int, float))
    ]
    if missing_attributes:
        raise RuntimeError(
            f"SimulationCraft attributes missing: {','.join(missing_attributes)}"
        )
    if not isinstance(stats.get("health"), (int, float)):
        raise RuntimeError("SimulationCraft health is missing")

    build = report.get("version") or report.get("sim", {}).get("version")
    print(
        json.dumps(
            {
                "runId": args.run_id,
                "character": args.name,
                "itemLevel": snapshot["itemLevel"],
                "heroTalentId": snapshot["heroTalentId"],
                "gearSlots": len(snapshot["items"]),
                "simcVersion": build,
                "reconstructed": stats,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
