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
import math
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
SCHEMA_VERSION = 4
MAX_INSUFFICIENT_SPECS = 4
DEFAULT_COHORTS = (25, 100, 250)
DEFAULT_MAX_RUN_CHECKS = 3
SUPPORTED_REGIONS = ("eu", "us", "kr", "tw")
RANKING_REGIONS = ("world",) + SUPPORTED_REGIONS
STAT_KEYS = ("strength", "agility", "intellect", "stamina", "crit", "haste", "mastery", "versatility")
SECONDARY_STATS = ("crit", "haste", "mastery", "versatility")
RIO_SLOT_MAP = {
    "head": "HEAD", "neck": "NECK", "shoulder": "SHOULDER", "back": "BACK",
    "chest": "CHEST", "wrist": "WRIST", "hands": "HANDS", "waist": "WAIST",
    "legs": "LEGS", "feet": "FEET", "finger1": "FINGER_1", "finger2": "FINGER_2",
    "trinket1": "TRINKET_1", "trinket2": "TRINKET_2",
    "mainhand": "MAIN_HAND", "offhand": "OFF_HAND",
}
SWAPPABLE_SLOT_GROUPS = (("FINGER_1", "FINGER_2"), ("TRINKET_1", "TRINKET_2"))


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


class ApiError(RuntimeError):
    pass


class JsonClient:
    def __init__(self, delay: float = 0.05):
        self.delay = max(0.0, delay)
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_lock = threading.Lock()

    def request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        method: str = "GET",
        form: dict[str, str] | None = None,
        retries: int = 4,
        cache_key: str | None = None,
    ) -> dict[str, Any]:
        if cache_key:
            with self.cache_lock:
                cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
        last_error = "unknown error"
        for attempt in range(retries):
            try:
                if self.delay:
                    time.sleep(self.delay)
                body = urllib.parse.urlencode(form).encode() if form is not None else None
                request = urllib.request.Request(url, headers=request_headers, data=body, method=method)
                with urllib.request.urlopen(request, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if cache_key:
                        with self.cache_lock:
                            self.cache[cache_key] = result
                    return result
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    payload = json.loads(exc.read().decode("utf-8", "replace"))
                    if isinstance(payload, dict):
                        detail = str(payload.get("detail") or payload.get("title") or payload.get("type") or "")
                except (ValueError, OSError):
                    detail = ""
                last_error = f"HTTP {exc.code} {exc.reason}" + (f" ({detail})" if detail else "")
                if exc.code not in (429, 500, 502, 503, 504):
                    break
                retry_after = float(exc.headers.get("Retry-After", 0) or 0)
                time.sleep(max(retry_after, 2**attempt))
            except (OSError, ValueError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(2**attempt)
        parsed_url = urllib.parse.urlsplit(url)
        safe_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        raise ApiError(f"Request failed: {safe_endpoint}: {last_error}")


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
            if "global" in self.tokens:
                return self.tokens["global"]
            credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            data = self.http.request(
                "https://oauth.battle.net/token",
                method="POST",
                form={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise ApiError("Blizzard OAuth returned no access token")
            self.tokens["global"] = token
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
            },
            headers={"Authorization": f"Bearer {self.token(region)}"},
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_liquid_armory_import(path: Path | None, season: str) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "status": "unavailable",
            "reason": "No approved Liquid Armory export supplied",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source metadata missing")
        source = {}
    if source.get("name") != "Liquid Armory":
        errors.append("source.name must be Liquid Armory")
    if source.get("season") != season:
        errors.append(f"season must be {season}")
    if source.get("acquisition") != "authorized_export":
        errors.append("source.acquisition must be authorized_export")
    captured_at = source.get("capturedAt")
    try:
        age_days = (datetime.now(timezone.utc) - parse_utc(captured_at)).total_seconds() / 86400
        if age_days < 0 or age_days > 30:
            errors.append("export is older than 30 days")
    except (AttributeError, TypeError, ValueError):
        errors.append("source.capturedAt must be an ISO-8601 timestamp")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        errors.append("profiles must be an object")
        profiles = {}
    unknown = sorted(set(profiles).difference(SPEC_BY_KEY))
    if unknown:
        errors.append(f"unknown specialization keys: {', '.join(unknown)}")
    for spec_key, profile in profiles.items():
        simulations = profile.get("simulations") if isinstance(profile, dict) else None
        if not isinstance(simulations, list):
            errors.append(f"{spec_key}: simulations must be a list")
            continue
        for index, simulation in enumerate(simulations):
            trinkets = simulation.get("trinkets") if isinstance(simulation, dict) else None
            if not isinstance(trinkets, list):
                errors.append(f"{spec_key}/simulation {index}: trinkets must be a list")
                continue
            for trinket in trinkets:
                if not isinstance(trinket, dict) or not isinstance(trinket.get("itemId"), int):
                    errors.append(f"{spec_key}/simulation {index}: trinket itemId missing")
                    break
                if trinket.get("track") not in ("Adventurer", "Veteran", "Champion", "Hero", "Myth"):
                    errors.append(f"{spec_key}/simulation {index}: invalid trinket track")
                    break
                if not isinstance(trinket.get("itemLevel"), (int, float)):
                    errors.append(f"{spec_key}/simulation {index}: trinket itemLevel missing")
                    break
    if errors:
        raise ValueError("Liquid Armory import validation failed:\n" + "\n".join(f"- {row}" for row in errors[:30]))
    return {"status": "ok", "data": data}


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
        if isinstance(row, dict):
            value = safe_number(row.get("rating_normalized"))
            if value is None:
                value = safe_number(row.get("rating"))
        else:
            value = safe_number(row)
        if value is not None and value >= 0:
            values.append(value)
    return max(values) if values else None


def parse_character_stats(stats: dict[str, Any]) -> dict[str, float]:
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
    return parsed


def describe_stat_shapes(stats: dict[str, Any]) -> str:
    keys = (
        "strength",
        "agility",
        "intellect",
        "stamina",
        "melee_crit",
        "melee_haste",
        "mastery",
        "versatility",
    )
    descriptions = []
    for key in keys:
        value = stats.get(key)
        if isinstance(value, dict):
            shape = "{" + ",".join(sorted(str(child) for child in value.keys())) + "}"
        else:
            shape = type(value).__name__
        descriptions.append(f"{key}:{shape}")
    return ",".join(descriptions)


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


def parse_active_hero_talent(
    specializations: dict[str, Any], expected_spec: str
) -> tuple[dict[str, Any] | None, str | None]:
    active_spec = specializations.get("active_specialization")
    active_spec_name = active_spec.get("name") if isinstance(active_spec, dict) else None
    if active_spec_name and active_spec_name != expected_spec:
        return None, f"Active specialization is {active_spec_name}, expected {expected_spec}"

    tree = specializations.get("active_hero_talent_tree")
    if not isinstance(tree, dict):
        for specialization in specializations.get("specializations", []):
            spec_row = specialization.get("specialization", {}) if isinstance(specialization, dict) else {}
            if spec_row.get("name") != expected_spec:
                continue
            for loadout in specialization.get("loadouts", []):
                if isinstance(loadout, dict) and loadout.get("is_active"):
                    tree = loadout.get("selected_hero_talent_tree")
                    break

    tree_id = tree.get("id") if isinstance(tree, dict) else None
    tree_name = tree.get("name") if isinstance(tree, dict) else None
    if not isinstance(tree_id, int) or not isinstance(tree_name, str) or not tree_name:
        return None, "Active hero talent tree missing from Blizzard profile"
    return {"key": f"HERO_{tree_id}", "id": tree_id, "name": tree_name}, None


def _integer_list(values: Any) -> tuple[int, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(sorted(int(value) for value in values if isinstance(value, (int, float))))


def _rio_item_fingerprint(item: dict[str, Any]) -> tuple[Any, ...]:
    enchants = item.get("enchants")
    if not isinstance(enchants, list) and isinstance(item.get("enchant"), (int, float)):
        enchants = [item["enchant"]]
    return (
        int(item.get("item_id") or 0),
        round(float(item.get("item_level") or 0), 3),
        _integer_list(item.get("bonuses")),
        _integer_list(item.get("gems")),
        _integer_list(enchants),
    )


def _blizzard_item_fingerprint(item: dict[str, Any]) -> tuple[Any, ...]:
    gems = []
    for socket in item.get("sockets", []):
        socket_item = socket.get("item") if isinstance(socket, dict) else None
        if isinstance(socket_item, dict) and isinstance(socket_item.get("id"), (int, float)):
            gems.append(int(socket_item["id"]))
    enchants = []
    for enchantment in item.get("enchantments", []):
        if not isinstance(enchantment, dict):
            continue
        value = enchantment.get("enchantment_id")
        if isinstance(value, (int, float)):
            enchants.append(int(value))
    return (
        int(item.get("item", {}).get("id") or 0),
        round(float(item.get("level", {}).get("value") or 0), 3),
        _integer_list(item.get("bonus_list")),
        tuple(sorted(gems)),
        tuple(sorted(enchants)),
    )


def parse_rio_gear(gear: dict[str, Any]) -> tuple[dict[str, tuple[Any, ...]], dict[str, dict[str, Any]]]:
    fingerprints = {}
    items = {}
    for rio_slot, item in (gear.get("items") or {}).items():
        if not isinstance(item, dict):
            continue
        slot = RIO_SLOT_MAP.get(str(rio_slot).lower())
        if not slot:
            continue
        raw_enchants = item.get("enchants")
        if not isinstance(raw_enchants, list) and isinstance(item.get("enchant"), (int, float)):
            raw_enchants = [item["enchant"]]
        fingerprints[slot] = _rio_item_fingerprint(item)
        items[slot] = {
            "itemId": int(item.get("item_id") or 0),
            "name": str(item.get("name") or ""),
            "itemLevel": safe_number(item.get("item_level")),
            "quality": int(item["item_quality"]) if isinstance(item.get("item_quality"), (int, float)) else None,
            "bonusIds": list(_integer_list(item.get("bonuses"))),
            "gemIds": list(_integer_list(item.get("gems"))),
            "enchantIds": list(_integer_list(raw_enchants)),
            "tier": item.get("tier"),
        }
    return fingerprints, items


def parse_blizzard_gear(equipment: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    fingerprints = {}
    for item in equipment.get("equipped_items", []):
        if not isinstance(item, dict):
            continue
        slot = item.get("slot", {}).get("type")
        if slot:
            fingerprints[str(slot)] = _blizzard_item_fingerprint(item)
    return fingerprints


def enrich_items_from_blizzard(
    items: dict[str, dict[str, Any]], equipment: dict[str, Any]
) -> None:
    for equipped in equipment.get("equipped_items", []):
        if not isinstance(equipped, dict):
            continue
        slot = equipped.get("slot", {}).get("type")
        target = items.get(str(slot))
        if not target:
            continue
        stats = {}
        for stat in equipped.get("stats", []):
            if not isinstance(stat, dict):
                continue
            stat_type = stat.get("type", {}).get("type") or stat.get("type", {}).get("name")
            value = safe_number(stat.get("value"))
            if stat_type and value is not None:
                stats[str(stat_type)] = value
        spells = []
        for spell in equipped.get("spells", []):
            raw_spell = spell.get("spell", {}) if isinstance(spell, dict) else {}
            spell_id = raw_spell.get("id")
            if isinstance(spell_id, (int, float)):
                spells.append({"id": int(spell_id), "name": raw_spell.get("name")})
        item_set = equipped.get("set") if isinstance(equipped.get("set"), dict) else None
        target["blizzardDetails"] = {
            "stats": stats,
            "armor": safe_number(equipped.get("armor", {}).get("value")),
            "weapon": equipped.get("weapon"),
            "set": (
                {"id": item_set.get("item_set", {}).get("id"), "name": item_set.get("name")}
                if item_set else None
            ),
            "spells": spells,
            "modifiedCraftingStats": equipped.get("modified_crafting_stat") or [],
        }


def gear_fingerprints_match(
    expected: dict[str, tuple[Any, ...]], actual: dict[str, tuple[Any, ...]]
) -> tuple[bool, str | None]:
    if len(expected) < 12 or len(actual) < 12:
        return False, f"Incomplete gear snapshot (run={len(expected)}, Blizzard={len(actual)})"
    expected_copy = dict(expected)
    actual_copy = dict(actual)
    for left, right in SWAPPABLE_SLOT_GROUPS:
        expected_pair = sorted((expected_copy.pop(left, None), expected_copy.pop(right, None)), key=repr)
        actual_pair = sorted((actual_copy.pop(left, None), actual_copy.pop(right, None)), key=repr)
        if expected_pair != actual_pair:
            return False, f"Gear mismatch in {left}/{right}"
    all_slots = sorted(set(expected_copy) | set(actual_copy))
    for slot in all_slots:
        if expected_copy.get(slot) != actual_copy.get(slot):
            return False, f"Gear mismatch in {slot}"
    return True, None


def parse_run_roster_snapshot(
    detail: dict[str, Any], character: dict[str, Any], expected_spec: str
) -> tuple[dict[str, Any] | None, str | None]:
    logged = detail.get("logged_details")
    if not isinstance(logged, dict) or not detail.get("loggedSources"):
        return None, "Run has no combat-log details"
    snapshots = []
    target_name = str(character["name"]).casefold()
    target_realm = str(character["realm"]).casefold()
    for encounter in logged.get("encounters", []):
        if not isinstance(encounter, dict):
            continue
        for member in encounter.get("roster", []):
            candidate = member.get("character", {}) if isinstance(member, dict) else {}
            realm = candidate.get("realm", {}).get("slug")
            if str(candidate.get("name", "")).casefold() != target_name or str(realm).casefold() != target_realm:
                continue
            if candidate.get("spec", {}).get("name") != expected_spec:
                return None, f"Logged run specialization is not {expected_spec}"
            gear = member.get("items")
            if not isinstance(gear, dict) or gear.get("source") != "db":
                continue
            fingerprints, items = parse_rio_gear(gear)
            talent = candidate.get("talentLoadout") or {}
            hero_id = talent.get("heroSubTreeId")
            snapshots.append(
                {
                    "gearUpdatedAt": gear.get("updated_at"),
                    "itemLevel": safe_number(gear.get("item_level_equipped")),
                    "fingerprint": fingerprints,
                    "items": items,
                    "heroTalentId": int(hero_id) if isinstance(hero_id, (int, float)) else None,
                    "talentLoadout": talent.get("exportLoadoutText") or talent.get("loadoutText"),
                }
            )
    if not snapshots:
        return None, "Target character has no exact combat-log gear snapshot"
    return max(snapshots, key=lambda row: str(row.get("gearUpdatedAt") or "")), None


def fetch_exact_run_snapshot(
    http: JsonClient,
    spec: Spec,
    character: dict[str, Any],
    season: str,
    max_run_checks: int,
) -> tuple[dict[str, Any] | None, str | None]:
    runs = [
        run for run in character.get("runs", [])
        if isinstance(run, dict) and run.get("loggedRunId") and run.get("keystoneRunId")
    ]
    runs.sort(key=lambda row: (-int(row.get("period") or 0), -float(row.get("score") or 0)))
    reasons = Counter()
    for run in runs[:max_run_checks]:
        try:
            detail = http.request(
                "https://raider.io/api/v1/mythic-plus/run-details",
                params={"season": season, "id": int(run["keystoneRunId"])},
                cache_key=f"run:{season}:{int(run['keystoneRunId'])}",
            )
        except ApiError as exc:
            reasons[str(exc)] += 1
            continue
        snapshot, reason = parse_run_roster_snapshot(detail, character, spec.spec_name)
        if snapshot:
            return {
                **snapshot,
                "runId": int(run["keystoneRunId"]),
                "loggedRunId": int(run["loggedRunId"]),
                "completedAt": detail.get("completed_at"),
                "mythicLevel": int(run.get("mythicLevel") or detail.get("mythic_level") or 0),
                "runScore": safe_number(run.get("score")),
            }, None
        if reason:
            reasons[reason] += 1
    if not runs:
        return None, "No logged runs among ranked runs"
    summary = "; ".join(f"{count}x {reason}" for reason, count in reasons.most_common(2))
    return None, summary or "No usable logged run snapshot"


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
    spec_name: str,
    page: int,
    page_size: int,
    access_key: str | None,
) -> tuple[list[dict[str, Any]], int]:
    params: dict[str, Any] = {
        "season": season,
        "region": region,
        "class": class_name,
        "spec": spec_name.lower().replace(" ", "-"),
        "page": page,
        "pageSize": page_size,
    }
    if access_key:
        params["access_key"] = access_key
    data = http.request("https://raider.io/api/mythic-plus/rankings/specs", params=params)
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
    rank = safe_number(entry.get("rank"))
    if region not in SUPPORTED_REGIONS or not realm or not name or score is None or rank is None:
        return None
    if str(realm).lower() == "anonymous" or str(name).lower().startswith("anon"):
        return None
    return {
        "region": region,
        "realm": realm,
        "name": name,
        "activeSpec": spec_name,
        "level": int(level or 0),
        "score": score,
        "rank": int(rank),
        "runs": list(entry.get("runs") or []),
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
    discovered: dict[str, dict[str, Any]] = {}
    for region in regions:
        for page in range(max_pages):
            entries, last_page = ranking_page(
                http,
                season=season,
                region=region,
                class_name=spec.class_name,
                spec_name=spec.spec_name,
                page=page,
                page_size=100,
                access_key=access_key,
            )
            for entry in entries:
                ref = character_ref(entry)
                if not ref:
                    continue
                if ref.get("activeSpec") != spec.spec_name:
                    continue
                key = f"{ref['region']}:{ref['realm']}:{ref['name']}".lower()
                previous = discovered.get(key)
                if previous is None or ref["score"] > previous["score"]:
                    discovered[key] = ref
            if page >= last_page or any(row["rank"] >= target_count for row in discovered.values()):
                break
    ranked = sorted(discovered.values(), key=lambda row: (row["rank"], row["region"], row["realm"], row["name"]))
    max_level = max((row["level"] for row in ranked), default=0)
    return [row for row in ranked if row["level"] == max_level and row["rank"] <= target_count]


def fetch_record(
    http: JsonClient,
    blizzard: BlizzardClient,
    spec: Spec,
    character: dict[str, Any],
    season: str,
    max_run_checks: int,
) -> tuple[dict[str, Any] | None, str | None]:
    run, run_reason = fetch_exact_run_snapshot(http, spec, character, season, max_run_checks)
    if not run:
        return None, run_reason

    record = {
        **character,
        "itemLevel": run["itemLevel"],
        "items": run["items"],
        "run": {
            key: run[key]
            for key in ("runId", "loggedRunId", "completedAt", "gearUpdatedAt", "mythicLevel", "runScore")
        },
        "runHeroTalentId": run["heroTalentId"],
        "runTalentLoadout": run.get("talentLoadout"),
        "statEligible": False,
        "statFailureReason": None,
    }
    try:
        specializations_raw = blizzard.character_resource(character, "specializations")
        equipment_before = blizzard.character_resource(character, "equipment")
    except ApiError as exc:
        record["statFailureReason"] = str(exc)
        return record, None

    hero_talent, hero_talent_reason = parse_active_hero_talent(specializations_raw, spec.spec_name)
    if not hero_talent:
        record["statFailureReason"] = hero_talent_reason
        return record, None
    if run["heroTalentId"] is None or hero_talent["id"] != run["heroTalentId"]:
        record["statFailureReason"] = (
            f"Hero talent mismatch (run={run['heroTalentId']}, Blizzard={hero_talent['id']})"
        )
        return record, None

    before_fingerprint = parse_blizzard_gear(equipment_before)
    matches, mismatch_reason = gear_fingerprints_match(run["fingerprint"], before_fingerprint)
    if not matches:
        record["statFailureReason"] = mismatch_reason
        return record, None
    enrich_items_from_blizzard(record["items"], equipment_before)

    try:
        stats_raw = blizzard.character_resource(character, "statistics")
        equipment_after = blizzard.character_resource(character, "equipment")
    except ApiError as exc:
        record["statFailureReason"] = str(exc)
        return record, None
    after_fingerprint = parse_blizzard_gear(equipment_after)
    if before_fingerprint != after_fingerprint:
        record["statFailureReason"] = "Blizzard equipment changed during collection"
        return record, None

    stats = parse_character_stats(stats_raw)
    required_stats = {"stamina", "crit", "haste", "mastery", "versatility", spec.primary}
    missing_stats = sorted(required_stats.difference(stats))
    if missing_stats:
        parsed_keys = ",".join(sorted(stats.keys())) or "none"
        record["statFailureReason"] = (
            "Profile schema mismatch "
            f"(missing={','.join(missing_stats) or 'none'}; parsed={parsed_keys}; "
            f"shapes={describe_stat_shapes(stats_raw)})"
        )
        return record, None

    record.update(
        {
            "stats": stats,
            "heroTalent": hero_talent,
            "statEligible": True,
        }
    )
    return record, None


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


def minimum_sample_size(rank_ceiling: int) -> int:
    configured = {25: 10, 100: 25, 250: 50}
    if rank_ceiling <= 10:
        return rank_ceiling
    return configured.get(rank_ceiling, max(1, math.ceil(rank_ceiling * 0.25)))


def records_within_rank(records: list[dict[str, Any]], rank_ceiling: int) -> list[dict[str, Any]]:
    return [
        row for index, row in enumerate(records, 1)
        if int(row.get("rank") or index) <= rank_ceiling
    ]


def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + (z * z / total)
    centre = proportion + (z * z / (2 * total))
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def aggregate_items(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_slot: dict[str, Counter[tuple[int, str]]] = defaultdict(Counter)
    variants: dict[tuple[str, int], Counter[tuple[Any, ...]]] = defaultdict(Counter)
    variant_details: dict[tuple[str, int, tuple[Any, ...]], dict[str, Any]] = {}
    evidence: dict[tuple[str, int], list[int]] = defaultdict(list)
    for record in records:
        for slot, item in record["items"].items():
            item_id = int(item["itemId"])
            by_slot[slot][(item_id, item["name"])] += 1
            variant = (
                item.get("itemLevel"),
                tuple(item.get("bonusIds") or ()),
                tuple(item.get("gemIds") or ()),
                tuple(item.get("enchantIds") or ()),
                item.get("tier"),
            )
            variants[(slot, item_id)][variant] += 1
            if item.get("blizzardDetails"):
                variant_details[(slot, item_id, variant)] = item["blizzardDetails"]
            run_id = record.get("run", {}).get("runId")
            if isinstance(run_id, int) and len(evidence[(slot, item_id)]) < 10:
                evidence[(slot, item_id)].append(run_id)
    output: dict[str, list[dict[str, Any]]] = {}
    for slot, counts in sorted(by_slot.items()):
        rows = []
        for (item_id, name), count in counts.most_common(10):
            lower = wilson_lower_bound(count, len(records))
            variant_rows = []
            for variant, variant_count in variants[(slot, item_id)].most_common(10):
                item_level, bonuses, gems, enchants, tier = variant
                variant_rows.append(
                    {
                        "itemLevel": item_level,
                        "bonusIds": list(bonuses),
                        "gemIds": list(gems),
                        "enchantIds": list(enchants),
                        "tier": tier,
                        "count": variant_count,
                        "blizzardDetails": variant_details.get((slot, item_id, variant)),
                    }
                )
            rows.append(
                {
                    "itemId": item_id,
                    "name": name,
                    "count": count,
                    "usagePercent": round((count / len(records)) * 100, 2),
                    "confidence95LowerPercent": round(lower * 100, 2),
                    "observedBisCandidate": lower >= 0.5,
                    "variants": variant_rows,
                    "evidenceRunIds": evidence[(slot, item_id)],
                }
            )
        output[slot] = rows
    return output


def aggregate_pair_usage(
    records: list[dict[str, Any]], slots: tuple[str, str]
) -> list[dict[str, Any]]:
    counts: Counter[tuple[int, ...]] = Counter()
    names: dict[tuple[int, ...], list[str]] = {}
    for record in records:
        pair = [record["items"].get(slot) for slot in slots]
        if any(not item for item in pair):
            continue
        key = tuple(sorted(int(item["itemId"]) for item in pair))
        counts[key] += 1
        names[key] = sorted(str(item["name"]) for item in pair)
    return [
        {
            "itemIds": list(key),
            "names": names[key],
            "count": count,
            "usagePercent": round((count / len(records)) * 100, 2),
        }
        for key, count in counts.most_common(10)
    ] if records else []


def aggregate_socket_and_enchant_usage(records: list[dict[str, Any]]) -> dict[str, Any]:
    gems: Counter[int] = Counter()
    enchants: dict[str, Counter[int]] = defaultdict(Counter)
    for record in records:
        for slot, item in record["items"].items():
            gems.update(int(value) for value in item.get("gemIds", []))
            enchants[slot].update(int(value) for value in item.get("enchantIds", []))
    return {
        "gems": [{"itemId": item_id, "count": count} for item_id, count in gems.most_common(20)],
        "enchantsBySlot": {
            slot: [{"enchantId": enchant_id, "count": count} for enchant_id, count in counts.most_common(10)]
            for slot, counts in sorted(enchants.items())
        },
    }


def aggregate_set_configurations(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[tuple[str, int], ...]] = Counter()
    for record in records:
        tiers = Counter(str(item["tier"]) for item in record["items"].values() if item.get("tier"))
        counts[tuple(sorted(tiers.items()))] += 1
    return [
        {
            "sets": [{"tier": tier, "pieces": pieces} for tier, pieces in key],
            "count": count,
            "usagePercent": round((count / len(records)) * 100, 2),
        }
        for key, count in counts.most_common(10)
    ] if records else []


def aggregate_talent_loadouts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[int | None, str]] = Counter()
    for record in records:
        code = record.get("runTalentLoadout")
        if isinstance(code, str) and code:
            counts[(record.get("runHeroTalentId"), code)] += 1
    return [
        {
            "heroTalentId": hero_id,
            "loadoutCode": code,
            "count": count,
            "usagePercent": round((count / len(records)) * 100, 2),
        }
        for (hero_id, code), count in counts.most_common(10)
    ] if records else []


def aggregate_run_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    levels = [
        record["run"]["mythicLevel"]
        for record in records
        if record.get("run", {}).get("mythicLevel") is not None
    ]
    item_levels = [record["itemLevel"] for record in records if record.get("itemLevel") is not None]
    ranks = [record["rank"] for record in records]
    return {
        "rankRange": {"highest": min(ranks), "lowest": max(ranks)} if ranks else None,
        "mythicLevel": {
            "median": round(statistics.median(levels), 2),
            "p25": round(percentile(levels, 0.25), 2),
            "p75": round(percentile(levels, 0.75), 2),
        } if levels else None,
        "equippedItemLevel": {
            "median": round(statistics.median(item_levels), 2),
            "p25": round(percentile(item_levels, 0.25), 2),
            "p75": round(percentile(item_levels, 0.75), 2),
        } if item_levels else None,
    }


def aggregate_quality_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    qualities: Counter[int] = Counter()
    total_slots = 0
    slots_with_quality = 0
    for record in records:
        for item in record["items"].values():
            total_slots += 1
            quality = item.get("quality")
            if isinstance(quality, int):
                qualities[quality] += 1
                slots_with_quality += 1
    return {
        "slotsWithQuality": slots_with_quality,
        "totalSlots": total_slots,
        "coverage": round(slots_with_quality / total_slots, 4) if total_slots else 0.0,
        "byQuality": {str(quality): count for quality, count in sorted(qualities.items())},
    }


def aggregate_gear_cohort(records: list[dict[str, Any]], rank_ceiling: int) -> dict[str, Any]:
    cohort = records_within_rank(records, rank_ceiling)
    minimum = minimum_sample_size(rank_ceiling)
    return {
        "status": "ok" if len(cohort) >= minimum else "insufficient",
        "rankCeiling": rank_ceiling,
        "sampleSize": len(cohort),
        "minimumSample": minimum,
        "rankCoverage": round(len(cohort) / rank_ceiling, 4),
        "popularItems": aggregate_items(cohort),
        "popularTrinketPairs": aggregate_pair_usage(cohort, ("TRINKET_1", "TRINKET_2")),
        "popularRingPairs": aggregate_pair_usage(cohort, ("FINGER_1", "FINGER_2")),
        "setConfigurations": aggregate_set_configurations(cohort),
        "socketAndEnchantUsage": aggregate_socket_and_enchant_usage(cohort),
        "talentLoadouts": aggregate_talent_loadouts(cohort),
        "runMetrics": aggregate_run_metrics(cohort),
        "qualityCoverage": aggregate_quality_coverage(cohort),
    }


def aggregate_cohort(records: list[dict[str, Any]], requested_size: int) -> dict[str, Any]:
    cohort = robust_records(records_within_rank(records, requested_size))
    minimum = minimum_sample_size(requested_size)
    if not cohort:
        return {
            "status": "insufficient",
            "requestedSize": requested_size,
            "rankCeiling": requested_size,
            "sampleSize": 0,
            "minimumSample": minimum,
            "completeness": 0.0,
            "confidence": "none",
            "statTargets": {"method": "median_character_sheet_rating", "stats": {}, "dispersion": {}},
            "popularItems": {},
        }
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
        "status": "ok" if len(cohort) >= minimum else "insufficient",
        "requestedSize": requested_size,
        "rankCeiling": requested_size,
        "sampleSize": len(cohort),
        "minimumSample": minimum,
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


def aggregate_hero_trees(
    records: list[dict[str, Any]], cohort_sizes: tuple[int, ...]
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata: dict[str, dict[str, Any]] = {}
    for record in records:
        tree = record.get("heroTalent")
        if not isinstance(tree, dict) or not tree.get("key"):
            continue
        grouped[tree["key"]].append(record)
        metadata[tree["key"]] = {"id": tree["id"], "name": tree["name"]}

    trees = {}
    for key in sorted(grouped):
        tree_records = sorted(
            grouped[key], key=lambda row: (-row["score"], row["region"], row["realm"], row["name"])
        )
        cohorts = {
            f"TOP_{size}": aggregate_cohort(tree_records, size) for size in cohort_sizes
        }
        base = cohorts[f"TOP_{min(cohort_sizes)}"]
        trees[key] = {
            **metadata[key],
            "status": base["status"],
            "fallback": "spec",
            "sampleCount": len(robust_records(tree_records)),
            "cohorts": cohorts,
        }
    return trees


def aggregate_hero_gear_trees(
    records: list[dict[str, Any]], cohort_sizes: tuple[int, ...]
) -> dict[str, dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    names = {
        int(record["heroTalent"]["id"]): record["heroTalent"]["name"]
        for record in records
        if isinstance(record.get("heroTalent"), dict)
    }
    for record in records:
        hero_id = record.get("runHeroTalentId")
        if isinstance(hero_id, int):
            grouped[hero_id].append(record)
    return {
        f"HERO_{hero_id}": {
            "id": hero_id,
            "name": names.get(hero_id),
            "fallback": "spec",
            "cohorts": {
                f"TOP_{size}": aggregate_gear_cohort(tree_records, size)
                for size in cohort_sizes
            },
        }
        for hero_id, tree_records in sorted(grouped.items())
    }


def compare_hero_trees(
    hero_trees: dict[str, dict[str, Any]], cohort_size: int
) -> dict[str, Any]:
    usable = [
        tree for tree in hero_trees.values()
        if tree.get("cohorts", {}).get(f"TOP_{cohort_size}", {}).get("status") == "ok"
    ]
    if len(usable) < 2:
        return {
            "status": "insufficient",
            "cohort": f"TOP_{cohort_size}",
            "reason": "At least two complete hero-tree cohorts are required",
        }

    stat_ranges = {}
    for stat in ("crit", "haste", "mastery", "versatility"):
        values = {
            tree["name"]: tree["cohorts"][f"TOP_{cohort_size}"]["statTargets"]["stats"][stat]
            for tree in usable
        }
        low = min(values.values())
        high = max(values.values())
        stat_ranges[stat] = {
            "byTree": values,
            "absoluteRange": round(high - low, 2),
            "relativeRangePercent": round(((high - low) / low) * 100, 2) if low > 0 else None,
        }
    return {
        "status": "ok",
        "cohort": f"TOP_{cohort_size}",
        "treesCompared": len(usable),
        "statRanges": stat_ranges,
    }


def validate_database(
    database: dict[str, Any], required_minimum: int, max_insufficient_specs: int = MAX_INSUFFICIENT_SPECS
) -> None:
    errors = []
    if database.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion mismatch")
    totals = database.get("source", {}).get("totals")
    if isinstance(totals, dict):
        if totals.get("candidates", 0) <= 0:
            errors.append("no ranked candidates were collected")
        if totals.get("verifiedRuns", 0) <= 0:
            errors.append("no combat-log run snapshots were verified")
        if totals.get("exactStatMatches", 0) <= 0:
            errors.append("no exact Raider.IO-to-Blizzard stat matches were found")
    profiles = database.get("profiles")
    if not isinstance(profiles, dict) or len(profiles) != len(SPECS):
        errors.append(f"expected {len(SPECS)} profiles")
        profiles = profiles if isinstance(profiles, dict) else {}
    insufficient_specs = []
    for spec in SPECS:
        profile = profiles.get(spec.key)
        cohorts = profile.get("cohorts") if isinstance(profile, dict) else None
        if not isinstance(cohorts, dict):
            errors.append(f"{spec.key}: cohorts missing")
            continue
        base_ok = False
        for label, cohort in cohorts.items():
            if not isinstance(cohort, dict):
                errors.append(f"{spec.key}/{label}: malformed cohort")
                continue
            sample = cohort.get("sampleSize", 0)
            requested = cohort.get("requestedSize", 0)
            minimum = cohort.get("minimumSample", minimum_sample_size(requested))
            stats = cohort.get("statTargets", {}).get("stats", {})
            complete = requested > 0 and sample >= minimum
            expected_status = "ok" if complete else "insufficient"
            if cohort.get("status") != expected_status:
                errors.append(f"{spec.key}/{label}: status must be {expected_status}")
            if complete and not all(key in stats for key in ("stamina", "crit", "haste", "mastery", "versatility")):
                errors.append(f"{spec.key}/{label}: required stat targets missing")
            if label == f"TOP_{required_minimum}" and complete:
                base_ok = True
        if profile.get("status") != ("ok" if base_ok else "insufficient"):
            errors.append(f"{spec.key}: profile status does not match its base cohort")
        candidate_count = profile.get("candidateCount", 0)
        verified_count = profile.get("verifiedRunCount", 0)
        stat_count = profile.get("exactStatMatchCount", 0)
        if not (0 <= stat_count <= verified_count <= candidate_count):
            errors.append(f"{spec.key}: candidate/run/stat counts are inconsistent")
        gear_cohorts = profile.get("gearCohorts")
        if not isinstance(gear_cohorts, dict):
            errors.append(f"{spec.key}: gearCohorts missing")
        else:
            for label, gear_cohort in gear_cohorts.items():
                if not isinstance(gear_cohort, dict):
                    errors.append(f"{spec.key}/{label}: malformed gear cohort")
                    continue
                sample = gear_cohort.get("sampleSize", 0)
                minimum = gear_cohort.get("minimumSample", 0)
                expected = "ok" if sample >= minimum and minimum > 0 else "insufficient"
                if gear_cohort.get("status") != expected:
                    errors.append(f"{spec.key}/{label}: gear status must be {expected}")
                required_metrics = (
                    "popularItems",
                    "popularTrinketPairs",
                    "popularRingPairs",
                    "setConfigurations",
                    "socketAndEnchantUsage",
                    "talentLoadouts",
                    "runMetrics",
                    "qualityCoverage",
                )
                missing_metrics = [key for key in required_metrics if key not in gear_cohort]
                if missing_metrics:
                    errors.append(
                        f"{spec.key}/{label}: gear metrics missing {','.join(missing_metrics)}"
                    )
        hero_trees = profile.get("heroTalentTrees")
        if not isinstance(hero_trees, dict):
            errors.append(f"{spec.key}: heroTalentTrees missing")
        else:
            for tree_key, tree in hero_trees.items():
                tree_cohorts = tree.get("cohorts") if isinstance(tree, dict) else None
                if not isinstance(tree_cohorts, dict):
                    errors.append(f"{spec.key}/{tree_key}: hero cohorts missing")
                    continue
                base = tree_cohorts.get(f"TOP_{required_minimum}", {})
                expected = "ok" if base.get("status") == "ok" else "insufficient"
                if tree.get("status") != expected:
                    errors.append(f"{spec.key}/{tree_key}: hero-tree status must be {expected}")
        if not base_ok:
            insufficient_specs.append(spec.key)
    if len(insufficient_specs) > max_insufficient_specs:
        errors.append(
            f"{len(insufficient_specs)} specs lack a complete TOP_{required_minimum} cohort "
            f"(allowed {max_insufficient_specs}): {', '.join(insufficient_specs)}"
        )
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
            target_count=max_size,
            max_pages=args.max_pages,
            access_key=access_key,
        )
        print(f"  candidates={len(candidates)}; collecting exact logged runs", flush=True)
        run_records = []
        failure_reasons: Counter[str] = Counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    fetch_record,
                    http,
                    blizzard,
                    spec,
                    candidate,
                    season_slug,
                    args.max_run_checks,
                ): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                record, reason = future.result()
                if record:
                    run_records.append(record)
                elif reason:
                    failure_reasons[reason] += 1
        run_records.sort(key=lambda row: (row["rank"], row["region"], row["realm"], row["name"]))
        stat_records = [record for record in run_records if record.get("statEligible")]
        stat_failure_reasons = Counter(
            record["statFailureReason"]
            for record in run_records
            if not record.get("statEligible") and record.get("statFailureReason")
        )
        failure_summary = [
            {"reason": reason, "count": count} for reason, count in failure_reasons.most_common(3)
        ]
        if not run_records:
            summary = "; ".join(f"{row['count']}x {row['reason']}" for row in failure_summary)
            message = f"{spec.key}: no exact logged-run snapshots; {summary or 'no candidates found'}"
            print(f"::warning title=Insufficient benchmark data::{message}", file=sys.stderr)
        cohorts = {}
        for size in args.cohorts:
            cohorts[f"TOP_{size}"] = aggregate_cohort(stat_records, size)
        gear_cohorts = {
            f"TOP_{size}": aggregate_gear_cohort(run_records, size)
            for size in args.cohorts
        }
        hero_trees = aggregate_hero_trees(stat_records, args.cohorts)
        hero_gear_trees = aggregate_hero_gear_trees(run_records, args.cohorts)
        base = cohorts[f"TOP_{min(args.cohorts)}"]
        profiles[spec.key] = {
            "status": base["status"],
            "class": spec.class_name,
            "spec": spec.spec_name,
            "role": spec.role,
            "primaryStat": spec.primary,
            "candidateCount": len(candidates),
            "verifiedRunCount": len(run_records),
            "exactStatMatchCount": len(stat_records),
            "coverage": {
                "verifiedRunRatio": round(len(run_records) / len(candidates), 4) if candidates else 0.0,
                "exactStatMatchRatio": round(len(stat_records) / len(candidates), 4) if candidates else 0.0,
                "exactOfVerifiedRatio": round(len(stat_records) / len(run_records), 4) if run_records else 0.0,
            },
            "runFailureReasons": failure_summary,
            "statMatchFailureReasons": [
                {"reason": reason, "count": count}
                for reason, count in stat_failure_reasons.most_common(5)
            ],
            "cohorts": cohorts,
            "gearCohorts": gear_cohorts,
            "heroTalentTrees": hero_trees,
            "heroTalentGearTrees": hero_gear_trees,
            "heroTalentAnalysis": compare_hero_trees(hero_trees, min(args.cohorts)),
        }
        print(
            f"  runs={len(run_records)}/{len(candidates)} exactStats={len(stat_records)}; "
            + f"status={profiles[spec.key]['status']}; heroTrees={len(hero_gear_trees)}; "
            + ", ".join(f"{label}={row['status']}({row['sampleSize']})" for label, row in cohorts.items()),
            flush=True,
        )
    database = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now(),
        "source": {
            "ranking": "Raider.IO character rankings",
            "characterStats": "Blizzard Profile API character statistics",
            "equipment": "Blizzard Profile API character equipment",
            "heroTalents": "Blizzard Profile API character specializations",
            "runSnapshots": "Raider.IO combat-log run details",
            "season": season_slug,
            "expansionId": expansion_id,
            "regions": list(args.regions),
            "rankCeilings": list(args.cohorts),
            "aggregation": "median with 15% item-level outlier rejection",
            "acceptance": (
                "Combat-log run gear only; Blizzard statistics accepted only after exact "
                "spec, hero talent, item, item-level, bonus, gem, and enchant match"
            ),
            "totals": {
                "candidates": sum(profile["candidateCount"] for profile in profiles.values()),
                "verifiedRuns": sum(profile["verifiedRunCount"] for profile in profiles.values()),
                "exactStatMatches": sum(profile["exactStatMatchCount"] for profile in profiles.values()),
            },
        },
        "profiles": profiles,
        "externalSimulations": load_liquid_armory_import(args.liquid_data, season_slug),
    }
    validate_database(database, min(args.cohorts), args.max_insufficient_specs)
    return database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=Path("StatVerdict/Data/Generated/SV_LiveBenchmarkData.json"))
    parser.add_argument("--lua-out", type=Path, default=Path("StatVerdict/Data/Generated/SV_LiveBenchmarkData.lua"))
    parser.add_argument("--validate-only", type=Path)
    parser.add_argument("--season", help="Emergency Raider.IO season override")
    parser.add_argument("--regions", default="world")
    parser.add_argument("--cohorts", default=",".join(str(value) for value in DEFAULT_COHORTS))
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--max-insufficient-specs", type=int, default=MAX_INSUFFICIENT_SPECS)
    parser.add_argument("--max-run-checks", type=int, default=DEFAULT_MAX_RUN_CHECKS)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--request-delay", type=float, default=0.05)
    parser.add_argument("--blizzard-client-id")
    parser.add_argument("--blizzard-client-secret")
    parser.add_argument("--raiderio-access-key")
    parser.add_argument(
        "--liquid-data",
        type=Path,
        default=Path("tools/data/liquid_armory_export.json"),
        help="Optional approved Liquid Armory JSON export; the engine never scrapes the site",
    )
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
        validate_database(database, min(args.cohorts), args.max_insufficient_specs)
        print(f"Validated {len(database['profiles'])} benchmark profiles.")
        return 0
    database = build_database(args)
    write_database(database, args.json_out, args.lua_out)
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.lua_out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}".replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Benchmark engine failed::{message}", file=sys.stderr)
        raise
