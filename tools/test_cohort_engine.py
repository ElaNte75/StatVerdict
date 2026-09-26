#!/usr/bin/env python3
"""
StatVerdict Benchmark Engine Prototype
Fetches live Mythic+ runs from Raider.IO, profiles top characters for a given spec,
and analyzes gear/stat cohorts (Top 20 vs Top 100).
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field

# Ensure clean UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

USER_AGENT = "StatVerdict-BenchmarkEngine/1.0"


def http_get_json(url: str, retries: int = 3, delay: float = 1.0) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [WARN] Request failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(delay)
    return None


@dataclass
class PlayerRef:
    name: str
    realm: str
    region: str
    spec: str
    class_name: str
    score: float = 0.0


def get_current_season_and_dungeons(expansion_id: int = 10) -> tuple[str, list[str]]:
    url = f"https://raider.io/api/v1/mythic-plus/static-data?expansion_id={expansion_id}"
    data = http_get_json(url)
    if not data:
        # Fallback to TWW S1
        return "season-tww-1", ["arakara-city-of-echoes", "the-stonevault", "mists-of-tirna-scithe"]

    seasons = data.get("seasons", [])
    season_slug = seasons[1]["slug"] if len(seasons) > 1 else "season-tww-1"
    # Filter to main season if cutoff slug
    for s in seasons:
        slug = s.get("slug", "")
        if "season-" in slug and not slug.endswith("-cutoffs") and not "remix" in slug:
            season_slug = slug
            break

    dungeons = [d["slug"] for d in data.get("dungeons", []) if "slug" in d]
    return season_slug, dungeons


def find_top_players_for_spec(
    target_class: str,
    target_spec: str,
    season: str,
    dungeons: list[str],
    limit: int = 20,
    max_pages_per_dungeon: int = 3,
) -> list[PlayerRef]:
    print(f"\n[1/3] Scanning top M+ runs for {target_spec} {target_class} (Season: {season})...")
    found_players: dict[str, PlayerRef] = {}

    for d_idx, dungeon in enumerate(dungeons):
        if len(found_players) >= limit:
            break
        print(f"  Scanning dungeon {d_idx + 1}/{len(dungeons)}: {dungeon}...")
        for page in range(max_pages_per_dungeon):
            if len(found_players) >= limit:
                break
            url = f"https://raider.io/api/v1/mythic-plus/runs?season={season}&region=world&dungeon={dungeon}&page={page}"
            data = http_get_json(url)
            if not data:
                continue

            rankings = data.get("rankings", [])
            if not rankings:
                break

            for entry in rankings:
                run = entry.get("run", {})
                mythic_level = run.get("mythic_level", 0)
                roster = run.get("roster", [])
                for member in roster:
                    char = member.get("character", {})
                    c_class = char.get("class", {}).get("name", "").lower()
                    c_spec = char.get("spec", {}).get("name", "").lower()

                    if c_class == target_class.lower() and c_spec == target_spec.lower():
                        name = char.get("name")
                        realm = char.get("realm", {}).get("slug")
                        region = char.get("region", {}).get("slug")
                        key = f"{region}:{realm}:{name}".lower()

                        if key not in found_players:
                            found_players[key] = PlayerRef(
                                name=name,
                                realm=realm,
                                region=region,
                                spec=target_spec,
                                class_name=target_class,
                                score=float(mythic_level),
                            )
                            print(f"    -> Found #{len(found_players)}: {name}-{realm} ({region.upper()}) [Key +{mythic_level}]")
                        if len(found_players) >= limit:
                            break
                if len(found_players) >= limit:
                    break

    # Sort descending by key level
    sorted_players = sorted(found_players.values(), key=lambda p: p.score, reverse=True)
    return sorted_players


def fetch_player_gear(player: PlayerRef) -> dict | None:
    enc_name = urllib.parse.quote(player.name)
    enc_realm = urllib.parse.quote(player.realm)
    url = f"https://raider.io/api/v1/characters/profile?region={player.region}&realm={enc_realm}&name={enc_name}&fields=gear"
    data = http_get_json(url)
    if not data or "gear" not in data:
        return None
    return data["gear"]


def analyze_cohort(cohort_name: str, profiles: list[dict]):
    print(f"\n==================================================")
    print(f"  COHORT REPORT: {cohort_name} (Sample size: {len(profiles)})")
    print(f"==================================================")

    if not profiles:
        print("  No profile data available.")
        return

    ilvls = [p["item_level_equipped"] for p in profiles if "item_level_equipped" in p]
    median_ilvl = statistics.median(ilvls) if ilvls else 0
    mean_ilvl = statistics.mean(ilvls) if ilvls else 0
    min_ilvl = min(ilvls) if ilvls else 0
    max_ilvl = max(ilvls) if ilvls else 0

    print(f"Item Level (Equipped):")
    print(f"  Median: {median_ilvl:.1f} | Mean: {mean_ilvl:.1f} (Range: {min_ilvl:.1f} - {max_ilvl:.1f})")

    # Slot distributions (Trinkets and Weapons)
    trinkets = Counter()
    weapons = Counter()
    for p in profiles:
        items = p.get("items", {})
        for t_slot in ("trinket1", "trinket2"):
            t = items.get(t_slot)
            if t and "name" in t:
                trinkets[t["name"]] += 1
        for w_slot in ("mainhand", "offhand"):
            w = items.get(w_slot)
            if w and "name" in w:
                weapons[w["name"]] += 1

    print(f"\nTop Trinkets (Usage across cohort):")
    total_trinket_slots = len(profiles) * 2
    for name, count in trinkets.most_common(5):
        pct = (count / len(profiles)) * 100
        print(f"  - {name}: {pct:.1f}% ({count} / {len(profiles)} players)")

    print(f"\nTop Weapons:")
    for name, count in weapons.most_common(3):
        pct = (count / len(profiles)) * 100
        print(f"  - {name}: {pct:.1f}%")


def main():
    target_class = "Paladin"
    target_spec = "Protection"

    if len(sys.argv) > 2:
        target_class = sys.argv[1]
        target_spec = sys.argv[2]

    print(f"==================================================")
    print(f" StatVerdict Live Benchmark Engine Prototype")
    print(f" Target: {target_spec} {target_class}")
    print(f"==================================================")

    season, dungeons = get_current_season_and_dungeons()
    # Gather top players (e.g. up to 25 for quick prototype run)
    players = find_top_players_for_spec(target_class, target_spec, season, dungeons, limit=20)

    if not players:
        print("No players found matching criteria.")
        return

    print(f"\n[2/3] Fetching character gear profiles for {len(players)} top players...")
    profiles = []
    for i, p in enumerate(players):
        gear = fetch_player_gear(p)
        if gear:
            profiles.append(gear)
            print(f"  [{i+1}/{len(players)}] {p.name}: ilvl {gear.get('item_level_equipped')}")
        time.sleep(0.15)  # respectful rate limiting

    print(f"\n[3/3] Generating Cohort Benchmarks...")

    # Define cohorts
    elite_cohort = profiles[:5]     # Top 5 elite
    competitive_cohort = profiles   # Top 20

    analyze_cohort("ELITE (Pinnacle Top 5)", elite_cohort)
    analyze_cohort("COMPETITIVE (Top 20)", competitive_cohort)

    print("\n[SUCCESS] Engine test run complete.")


if __name__ == "__main__":
    main()
