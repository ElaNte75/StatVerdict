#!/usr/bin/env python3
"""The pool of items that can drop this season, from Blizzard's Game Data API (journal).

For the season's dungeons and raids (journal expansion "Current Season") it lists every item of every
encounter with its source, then adds the item's slot, armor type and base stats (at base item level; SimC
gives the real stats at an item level and upgrade level). Nothing is invented: crafted items, the Catalyst
and world / delve sources are not in the journal and are marked as missing.

Credentials come from the environment, never from files: BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET.

  python tools/blizzard_item_pool.py [--region us] [--out tools/data/blizzard_item_pool.json] [--with-items]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SEASON_TIER_ID = 505  # journal expansion "Current Season"
TIMEOUT = 30


class BlizzardClient:
    def __init__(self, client_id: str, client_secret: str, region: str = "us"):
        self.region = region
        self.base = f"https://{region}.api.blizzard.com"
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        request = urllib.request.Request(
            "https://oauth.battle.net/token",
            data=b"grant_type=client_credentials",
            headers={"Authorization": f"Basic {credentials}"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            self.token = json.load(response)["access_token"]

    def get(self, path: str) -> dict[str, Any]:
        sep = "&" if "?" in path else "?"
        url = f"{self.base}{path}{sep}namespace=static-{self.region}&locale=en_US"
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)


def season_instances(client: BlizzardClient) -> list[tuple[int, str, str]]:
    season = client.get(f"/data/wow/journal-expansion/{SEASON_TIER_ID}")
    return [(d["id"], d["name"], "dungeon") for d in season.get("dungeons", [])] + [
        (r["id"], r["name"], "raid") for r in season.get("raids", [])
    ]


def build_pool(client: BlizzardClient, with_items: bool = False) -> dict[str, Any]:
    pool: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for instance_id, name, kind in season_instances(client):
        try:
            instance = client.get(f"/data/wow/journal-instance/{instance_id}")
        except Exception as exc:  # noqa: BLE001 - reported, the rest still runs
            problems.append(f"instance {name}: {exc}")
            continue
        for encounter_ref in instance.get("encounters", []):
            try:
                encounter = client.get(f"/data/wow/journal-encounter/{encounter_ref['id']}")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"encounter {encounter_ref.get('name')}: {exc}")
                continue
            for entry in encounter.get("items", []):
                item = entry["item"]
                row = pool.setdefault(str(item["id"]), {"name": item["name"], "sources": []})
                row["sources"].append({"instance": name, "kind": kind, "encounter": encounter["name"]})
    if with_items:
        for item_id, row in pool.items():
            try:
                data = client.get(f"/data/wow/item/{item_id}")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"item {item_id}: {exc}")
                continue
            preview = data.get("preview_item") or {}
            row.update(
                {
                    "level": data.get("level"),
                    "slot": (data.get("inventory_type") or {}).get("type"),
                    "class": (data.get("item_class") or {}).get("name"),
                    "subclass": (data.get("item_subclass") or {}).get("name"),
                    "stats": {
                        s["type"]["type"]: s["value"]
                        for s in preview.get("stats", [])
                        if isinstance(s, dict) and not s.get("is_negated")
                    },
                }
            )
    return {"seasonTier": SEASON_TIER_ID, "region": client.region, "items": pool, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us")
    parser.add_argument("--out", type=Path, default=Path("tools/data/blizzard_item_pool.json"))
    parser.add_argument("--with-items", action="store_true", help="also fetch slot, type and base stats per item")
    args = parser.parse_args(argv)
    client_id, client_secret = os.environ.get("BLIZZARD_CLIENT_ID"), os.environ.get("BLIZZARD_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET must be set in the environment", file=sys.stderr)
        return 1
    pool = build_pool(BlizzardClient(client_id, client_secret, args.region), args.with_items)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pool, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(pool['items'])} items, {len(pool['problems'])} problems -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
