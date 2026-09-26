#!/usr/bin/env python3
"""Build StatVerdict cohort benchmarks from Raider.IO and Blizzard APIs.

Raider.IO supplies season rankings and equipped item references. Blizzard's
profile API supplies the character-sheet ratings. The engine never derives
ratings from item names or invents missing values.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

USER_AGENT = "StatVerdict-LiveBenchmark/1.0"
SCHEMA_VERSION = 1
DEFAULT_COHORTS = (20, 100, 500)
SUPPORTED_REGIONS = ("eu", "us", "kr", "tw")
RANKING_REGIONS = ("world",) + SUPPORTED_REGIONS
STAT_KEYS = ("strength", "agility", "intellect", "stamina", "crit", "haste", "mastery", "versatility")


@dataclass(frozen=True)
class Spec:
    key: str
    class_name: str
    spec_name: str
    role: str
    primary: str


SPECS = (
    Spec("DEATHKNIGHT_BLOOD", "death-knight", "Blood", "tank", "strength"),
    Spec("DEATHKNIGHT_FROST", "death-knight", "Frost", "dps", "strength"),
    Spec("DEATHKNIGHT_UNHOLY", "death-knight", "Unholy", "dps", "strength"),
    Spec("DEMONHUNTER_DEVOURER", "demon-hunter", "Devourer", "dps", "agility"),
    Spec("DEMONHUNTER_HAVOC", "demon-hunter", "Havoc", "dps", "agility"),
    Spec("DEMONHUNTER_VENGEANCE", "demon-hunter", "Vengeance", "tank", "agility"),
    Spec("DRUID_BALANCE", "druid", "Balance", "dps", "intellect"),
    Spec("DRUID_FERAL", "druid", "Feral", "dps", "agility"),
    Spec("DRUID_GUARDIAN", "druid", "Guardian", "tank", "agility"),
    Spec("DRUID_RESTORATION", "druid", "Restoration", "healer", "intellect"),
    Spec("EVOKER_AUGMENTATION", "evoker", "Augmentation", "dps", "intellect"),
    Spec("EVOKER_DEVASTATION", "evoker", "Devastation", "dps", "intellect"),
    Spec("EVOKER_PRESERVATION", "evoker", "Preservation", "healer", "intellect"),
    Spec("HUNTER_BEAST_MASTERY", "hunter", "Beast Mastery", "dps", "agility"),
    Spec("HUNTER_MARKSMANSHIP", "hunter", "Marksmanship", "dps", "agility"),
    Spec("HUNTER_SURVIVAL", "hunter", "Survival", "dps", "agility"),
    Spec("MAGE_ARCANE", "mage", "Arcane", "dps", "intellect"),
    Spec("MAGE_FIRE", "mage", "Fire", "dps", "intellect"),
    Spec("MAGE_FROST", "mage", "Frost", "dps", "intellect"),
    Spec("MONK_BREWMASTER", "monk", "Brewmaster", "tank", "agility"),
    Spec("MONK_MISTWEAVER", "monk", "Mistweaver", "healer", "intellect"),
    Spec("MONK_WINDWALKER", "monk", "Windwalker", "dps", "agility"),
    Spec("PALADIN_HOLY", "paladin", "Holy", "healer", "intellect"),
    Spec("PALADIN_PROTECTION", "paladin", "Protection", "tank", "strength"),
    Spec("PALADIN_RETRIBUTION", "paladin", "Retribution", "dps", "strength"),
    Spec("PRIEST_DISCIPLINE", "priest", "Discipline", "healer", "intellect"),
    Spec("PRIEST_HOLY", "priest", "Holy", "healer", "intellect"),
    Spec("PRIEST_SHADOW", "priest", "Shadow", "dps", "intellect"),
    Spec("ROGUE_ASSASSINATION", "rogue", "Assassination", "dps", "agility"),
    Spec("ROGUE_OUTLAW", "rogue", "Outlaw", "dps", "agility"),
    Spec("ROGUE_SUBTLETY", "rogue", "Subtlety", "dps", "agility"),
    Spec("SHAMAN_ELEMENTAL", "shaman", "Elemental", "dps", "intellect"),
    Spec("SHAMAN_ENHANCEMENT", "shaman", "Enhancement", "dps", "agility"),
    Spec("SHAMAN_RESTORATION", "shaman", "Restoration", "healer", "intellect"),
    Spec("WARLOCK_AFFLICTION", "warlock", "Affliction", "dps", "intellect"),
    Spec("WARLOCK_DEMONOLOGY", "warlock", "Demonology", "dps", "intellect"),
    Spec("WARLOCK_DESTRUCTION", "warlock", "Destruction", "dps", "intellect"),
    Spec("WARRIOR_ARMS", "warrior", "Arms", "dps", "strength"),
    Spec("WARRIOR_FURY", "warrior", "Fury", "dps", "strength"),
    Spec("WARRIOR_PROTECTION", "warrior", "Protection", "tank", "strength"),
)
SPEC_BY_KEY = {spec.key: spec for spec in SPECS}
STREAM_SPECS: dict[tuple[str, str], list[Spec]] = defaultdict(list)
for _spec in SPECS:
    STREAM_SPECS[(_spec.class_name, _spec.role)].append(_spec)


class ApiError(RuntimeError):
    pass


class JsonClient:
    def __init__(self, delay: float = 0.05):
        self.delay = max(0.0, delay)

    def request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        method: str = "GET",
        form: dict[str, str] | None = None,
        retries: int = 4,
    ) -> dict[str, Any]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                if self.delay:
                    time.sleep(self.delay)
                body = urllib.parse.urlencode(form).encode() if form is not None else None
                request = urllib.request.Request(url, headers=request_headers, data=body, method=method)
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in (429, 500, 502, 503, 504):
                    break
                retry_after = float(exc.headers.get("Retry-After", 0) or 0)
                time.sleep(max(retry_after, 2**attempt))
            except (OSError, ValueError) as exc:
                last_error = exc
                time.sleep(2**attempt)
        raise ApiError(f"Request failed: {url}: {last_error}")


class BlizzardClient:
    def __init__(self, client_id: str, client_secret: str, delay: float = 0.05):
        if not client_id or not client_secret:
            raise ValueError("BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET are required")
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = JsonClient(delay)
        self.tokens: dict[str, str] = {}
        self.token_lock = threading.Lock()

    def token(self, region: str) -> str:
        with self.token_lock:
            if region in self.tokens:
                return self.tokens[region]
            credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            data = self.http.request(
                f"https://{region}.battle.net/oauth/token",
                method="POST",
                form={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise ApiError(f"Blizzard OAuth returned no token for {region}")
            self.tokens[region] = token
            return token

    def character_resource(self, character: dict[str, Any], resource: str) -> dict[str, Any]:
        region = character["region"]
        realm = urllib.parse.quote(character["realm"], safe="")
        name = urllib.parse.quote(character["name"].lower(), safe="")
        return self.http.request(
            f"https://{region}.api.blizzard.com/profile/wow/character/{realm}/{name}/{resource}",
            params={
                "namespace": f"profile-{region}",
                "locale": "en_US",
                "access_token": self.token(region),
            },
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def nested_rating(stats: dict[str, Any], keys: Iterable[str]) -> float | None:
    values = []
    for key in keys:
        row = stats.get(key)
        value = safe_number(row.get("rating")) if isinstance(row, dict) else safe_number(row)
        if value is not None and value >= 0:
            values.append(value)
    return max(values) if values else None


def parse_character_stats(stats: dict[str, Any]) -> dict[str, float] | None:
    parsed: dict[str, float] = {}
    for key in ("strength", "agility", "intellect", "stamina"):
        row = stats.get(key)
        value = None
        if isinstance(row, dict):
            value = safe_number(row.get("effective"))
            if value is None:
                value = safe_number(row.get("base"))
        if value is not None:
            parsed[key] = value
    rating_groups = {
        "crit": ("melee_crit", "spell_crit", "ranged_crit"),
        "haste": ("melee_haste", "spell_haste", "ranged_haste"),
        "mastery": ("mastery",),
        "versatility": ("versatility",),
    }
    for output_key, source_keys in rating_groups.items():
        value = nested_rating(stats, source_keys)
        if value is not None:
            parsed[output_key] = value
    required = {"stamina", "crit", "haste", "mastery", "versatility"}
    return parsed if required.issubset(parsed) else None


def parse_equipment(equipment: dict[str, Any]) -> tuple[float | None, dict[str, dict[str, Any]]]:
    slots: dict[str, dict[str, Any]] = {}
    levels = []
    for entry in equipment.get("equipped_items", []):
        if not isinstance(entry, dict):
            continue
        slot = entry.get("slot", {}).get("type")
        item_id = entry.get("item", {}).get("id")
        raw_name = entry.get("name")
        name = raw_name.get("en_US") if isinstance(raw_name, dict) else raw_name
        level = safe_number(entry.get("level", {}).get("value"))
        if not slot or not item_id:
            continue
        slots[str(slot)] = {
            "itemId": int(item_id),
            "name": str(name or ""),
            "itemLevel": level,
        }
        if level:
            levels.append(level)
    return (statistics.mean(levels) if levels else None), slots


def active_season(http: JsonClient, expansion_min: int = 10, expansion_max: int = 14) -> tuple[int, dict[str, Any]]:
    now = utc_now()
    candidates: list[tuple[str, int, dict[str, Any]]] = []
    for expansion_id in range(expansion_min, expansion_max + 1):
        try:
            data = http.request(
                "https://raider.io/api/v1/mythic-plus/static-data",
                params={"expansion_id": expansion_id},
            )
        except ApiError:
            continue
        for season in data.get("seasons", []):
            if not season.get("is_main_season"):
                continue
            starts = season.get("starts", {})
            start = starts.get("eu") or starts.get("us")
            if isinstance(start, str) and start <= now:
                candidates.append((start, expansion_id, season))
    if not candidates:
        raise ApiError("Unable to detect an active main Mythic+ season")
    _, expansion_id, season = max(candidates, key=lambda row: row[0])
    return expansion_id, season


def ranking_page(
    http: JsonClient,
    *,
    season: str,
    region: str,
    class_name: str,
    role: str,
    page: int,
    access_key: str | None,
) -> tuple[list[dict[str, Any]], int]:
    params: dict[str, Any] = {
        "season": season,
        "region": region,
        "class": class_name,
        "role": role,
        "page": page,
    }
    if access_key:
        params["access_key"] = access_key
    data = http.request("https://raider.io/api/mythic-plus/rankings/characters", params=params)
    rankings = data.get("rankings", data)
    entries = rankings.get("rankedCharacters", rankings.get("rankings", []))
    ui = rankings.get("ui", {})
    return list(entries or []), int(ui.get("lastPage", page))


def character_ref(entry: dict[str, Any]) -> dict[str, Any] | None:
    character = entry.get("character")
    if not isinstance(character, dict):
        return None
    region = character.get("region", {}).get("slug")
    realm = character.get("realm", {}).get("slug")
    name = character.get("name")
    spec_name = character.get("spec", {}).get("name")
    level = safe_number(character.get("level"))
    score = safe_number(entry.get("score"))
    if region not in SUPPORTED_REGIONS or not realm or not name or score is None:
        return None
    return {
        "region": region,
        "realm": realm,
        "name": name,
        "activeSpec": spec_name,
        "level": int(level or 0),
        "score": score,
    }


def discover_candidates(
    http: JsonClient,
    spec: Spec,
    *,
    season: str,
    regions: tuple[str, ...],
    target_count: int,
    max_pages: int,
    access_key: str | None,
) -> list[dict[str, Any]]:
    stream_specs = STREAM_SPECS[(spec.class_name, spec.role)]
    unique_role_spec = len(stream_specs) == 1
    discovered: dict[str, dict[str, Any]] = {}
    for region in regions:
        for page in range(max_pages):
            entries, last_page = ranking_page(
                http,
                season=season,
                region=region,
                class_name=spec.class_name,
                role=spec.role,
                page=page,
                access_key=access_key,
            )
            for entry in entries:
                ref = character_ref(entry)
                if not ref:
                    continue
                if not unique_role_spec and ref.get("activeSpec") != spec.spec_name:
                    continue
                key = f"{ref['region']}:{ref['realm']}:{ref['name']}".lower()
                previous = discovered.get(key)
                if previous is None or ref["score"] > previous["score"]:
                    discovered[key] = ref
            if page >= last_page or len(discovered) >= target_count:
                break
    ranked = sorted(discovered.values(), key=lambda row: (-row["score"], row["region"], row["realm"], row["name"]))
    max_level = max((row["level"] for row in ranked), default=0)
    return [row for row in ranked if row["level"] == max_level][:target_count]


def fetch_record(blizzard: BlizzardClient, spec: Spec, character: dict[str, Any]) -> dict[str, Any] | None:
    try:
        stats_raw = blizzard.character_resource(character, "statistics")
        equipment_raw = blizzard.character_resource(character, "equipment")
    except ApiError as exc:
        print(f"WARN {spec.key} {character['name']}: {exc}", file=sys.stderr)
        return None
    stats = parse_character_stats(stats_raw)
    item_level, items = parse_equipment(equipment_raw)
    if not stats or item_level is None or len(items) < 12:
        return None
    if spec.primary not in stats:
        return None
    return {
        **character,
        "stats": stats,
        "itemLevel": item_level,
        "items": items,
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def robust_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    levels = [row["itemLevel"] for row in records]
    if not levels:
        return []
    median = statistics.median(levels)
    floor = max(1.0, median * 0.85)
    ceiling = median * 1.15
    return [row for row in records if floor <= row["itemLevel"] <= ceiling]


def aggregate_items(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_slot: dict[str, Counter[tuple[int, str]]] = defaultdict(Counter)
    for record in records:
        for slot, item in record["items"].items():
            by_slot[slot][(item["itemId"], item["name"])] += 1
    output: dict[str, list[dict[str, Any]]] = {}
    for slot, counts in sorted(by_slot.items()):
        output[slot] = [
            {
                "itemId": item_id,
                "name": name,
                "count": count,
                "usagePercent": round((count / len(records)) * 100, 2),
            }
            for (item_id, name), count in counts.most_common(10)
        ]
    return output


def aggregate_cohort(records: list[dict[str, Any]], requested_size: int) -> dict[str, Any]:
    cohort = robust_records(records)[:requested_size]
    if not cohort:
        raise ValueError("cohort has no valid records")
    stat_targets = {}
    dispersions = {}
    for stat_key in STAT_KEYS:
        values = [row["stats"][stat_key] for row in cohort if stat_key in row["stats"]]
        if not values:
            continue
        stat_targets[stat_key] = round(statistics.median(values), 2)
        dispersions[stat_key] = {
            "p25": round(percentile(values, 0.25), 2),
            "p75": round(percentile(values, 0.75), 2),
        }
    levels = [row["itemLevel"] for row in cohort]
    completeness = len(cohort) / requested_size
    return {
        "requestedSize": requested_size,
        "sampleSize": len(cohort),
        "completeness": round(completeness, 4),
        "confidence": "high" if completeness >= 0.9 else ("medium" if completeness >= 0.6 else "low"),
        "scoreRange": {
            "highest": round(cohort[0]["score"], 2),
            "lowest": round(cohort[-1]["score"], 2),
        },
        "averageItemLevel": round(statistics.median(levels), 2),
        "meanItemLevel": round(statistics.mean(levels), 2),
        "statTargets": {
            "method": "median_character_sheet_rating",
            "stats": stat_targets,
            "dispersion": dispersions,
        },
        "popularItems": aggregate_items(cohort),
    }


def validate_database(database: dict[str, Any], required_minimum: int) -> None:
    errors = []
    if database.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion mismatch")
    profiles = database.get("profiles")
    if not isinstance(profiles, dict) or len(profiles) != len(SPECS):
        errors.append(f"expected {len(SPECS)} profiles")
        profiles = profiles if isinstance(profiles, dict) else {}
    for spec in SPECS:
        profile = profiles.get(spec.key)
        cohorts = profile.get("cohorts") if isinstance(profile, dict) else None
        if not isinstance(cohorts, dict):
            errors.append(f"{spec.key}: cohorts missing")
            continue
        for label, cohort in cohorts.items():
            sample = cohort.get("sampleSize", 0) if isinstance(cohort, dict) else 0
            requested = cohort.get("requestedSize", 0) if isinstance(cohort, dict) else 0
            stats = cohort.get("statTargets", {}).get("stats", {}) if isinstance(cohort, dict) else {}
            if label == f"TOP_{required_minimum}" and sample < required_minimum:
                errors.append(f"{spec.key}/{label}: sample {sample} below {required_minimum}")
            if requested <= 0 or sample / requested < 0.9:
                errors.append(f"{spec.key}/{label}: cohort completeness below 90%")
            if not all(key in stats for key in ("stamina", "crit", "haste", "mastery", "versatility")):
                errors.append(f"{spec.key}/{label}: required stat targets missing")
    if errors:
        preview = "\n".join(f"- {message}" for message in errors[:50])
        suffix = f"\n- ... and {len(errors) - 50} more" if len(errors) > 50 else ""
        raise ValueError(f"Benchmark quality validation failed:\n{preview}{suffix}")


def to_lua(value: Any, indent: int = 0) -> str:
    pad = "    " * indent
    child = "    " * (indent + 1)
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "{}"
        return "{\n" + "\n".join(f"{child}{to_lua(item, indent + 1)}," for item in value) + f"\n{pad}}}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = []
        for key in sorted(value, key=str):
            rows.append(f"{child}[{json.dumps(str(key), ensure_ascii=False)}] = {to_lua(value[key], indent + 1)},")
        return "{\n" + "\n".join(rows) + f"\n{pad}}}"
    raise TypeError(f"Unsupported type: {type(value)}")


def write_database(database: dict[str, Any], json_path: Path, lua_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    lua_path.parent.mkdir(parents=True, exist_ok=True)
    json_tmp = json_path.with_suffix(json_path.suffix + ".tmp")
    lua_tmp = lua_path.with_suffix(lua_path.suffix + ".tmp")
    json_tmp.write_text(json.dumps(database, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lua_tmp.write_text(
        "local addonName, ns = ...\n\n"
        "-- Generated by tools/live_benchmark_engine.py. Do not edit manually.\n"
        "ns.LiveBenchmarkData = "
        + to_lua(database)
        + "\n",
        encoding="utf-8",
    )
    json_tmp.replace(json_path)
    lua_tmp.replace(lua_path)


def build_database(args: argparse.Namespace) -> dict[str, Any]:
    client_id = args.blizzard_client_id or os.environ.get("BLIZZARD_CLIENT_ID", "")
    client_secret = args.blizzard_client_secret or os.environ.get("BLIZZARD_CLIENT_SECRET", "")
    access_key = args.raiderio_access_key or os.environ.get("RAIDERIO_ACCESS_KEY") or None
    http = JsonClient(args.request_delay)
    blizzard = BlizzardClient(client_id, client_secret, args.request_delay)
    expansion_id, season = active_season(http)
    season_slug = args.season or season["slug"]
    max_size = max(args.cohorts)
    profiles: dict[str, Any] = {}
    for index, spec in enumerate(SPECS, 1):
        print(f"[{index:02d}/{len(SPECS)}] {spec.key}: discovering candidates", flush=True)
        candidates = discover_candidates(
            http,
            spec,
            season=season_slug,
            regions=args.regions,
            target_count=max_size + max(20, max_size // 5),
            max_pages=args.max_pages,
            access_key=access_key,
        )
        print(f"  candidates={len(candidates)}; collecting Blizzard profiles", flush=True)
        records = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(fetch_record, blizzard, spec, candidate): candidate for candidate in candidates}
            for future in as_completed(futures):
                record = future.result()
                if record:
                    records.append(record)
        records.sort(key=lambda row: (-row["score"], row["region"], row["realm"], row["name"]))
        cohorts = {}
        for size in args.cohorts:
            cohorts[f"TOP_{size}"] = aggregate_cohort(records, size)
        profiles[spec.key] = {
            "class": spec.class_name,
            "spec": spec.spec_name,
            "role": spec.role,
            "primaryStat": spec.primary,
            "candidateCount": len(candidates),
            "validRecordCount": len(robust_records(records)),
            "cohorts": cohorts,
        }
    database = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now(),
        "source": {
            "ranking": "Raider.IO character rankings",
            "characterStats": "Blizzard Profile API character statistics",
            "equipment": "Blizzard Profile API character equipment",
            "season": season_slug,
            "expansionId": expansion_id,
            "regions": list(args.regions),
            "aggregation": "median with 15% item-level outlier rejection",
        },
        "profiles": profiles,
    }
    validate_database(database, min(args.cohorts))
    return database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=Path("StatVerdict/Data/Generated/SV_LiveBenchmarkData.json"))
    parser.add_argument("--lua-out", type=Path, default=Path("StatVerdict/Data/Generated/SV_LiveBenchmarkData.lua"))
    parser.add_argument("--validate-only", type=Path)
    parser.add_argument("--season", help="Emergency Raider.IO season override")
    parser.add_argument("--regions", default="world")
    parser.add_argument("--cohorts", default="20,100,500")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--request-delay", type=float, default=0.05)
    parser.add_argument("--blizzard-client-id")
    parser.add_argument("--blizzard-client-secret")
    parser.add_argument("--raiderio-access-key")
    args = parser.parse_args()
    args.regions = tuple(value.strip().lower() for value in args.regions.split(",") if value.strip())
    args.cohorts = tuple(sorted({int(value) for value in args.cohorts.split(",") if int(value) > 0}))
    if not args.regions or not set(args.regions).issubset(RANKING_REGIONS):
        parser.error(f"regions must be a subset of {RANKING_REGIONS}")
    if not args.cohorts:
        parser.error("at least one cohort size is required")
    return args


def main() -> int:
    args = parse_args()
    if args.validate_only:
        database = json.loads(args.validate_only.read_text(encoding="utf-8"))
        validate_database(database, min(args.cohorts))
        print(f"Validated {len(database['profiles'])} benchmark profiles.")
        return 0
    database = build_database(args)
    write_database(database, args.json_out, args.lua_out)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.lua_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
