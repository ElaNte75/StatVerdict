#!/usr/bin/env python3
"""Reconstruct paper-doll ratings from Wowhead item tooltips.

This is the healer path: SimulationCraft does not model healing throughput at
all (it is a DPS/damage simulator), so healer specs need a different way to
turn exact combat-log-verified gear into approximate secondary-stat targets.
This looks each equipped item up by ID + bonus/gem/enchant IDs using
Wowhead's public tooltip JSON (the same payload a hover tooltip uses) and
sums the ratings. It is not a site crawl.

It does not include base class stats, racials, or talent-driven stat
conversions, so it is less precise than the SimC path used for DPS/Tank —
but SimC gives healers nothing at all, so this is the healer target data.
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class TooltipCache:
    """Thread-safe cache so many characters wearing the same popular item
    (same item id + bonus/gem/enchant ids) only fetch its tooltip once."""

    def __init__(self) -> None:
        self._store: dict[tuple, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(item: dict[str, Any]) -> tuple:
        query = tooltip_query(item)
        return (int(item["itemId"]), query.get("bonus", ""), query.get("gems", ""), query.get("ench", ""))

    def get(self, item: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            return self._store.get(self._key(item))

    def set(self, item: dict[str, Any], value: dict[str, Any]) -> None:
        with self._lock:
            self._store[self._key(item)] = value

USER_AGENT = "StatVerdict-WowheadProof/0.1 (experimental; contact via GitHub ElaNte75/StatVerdict)"
TOOLTIP_URL = "https://nether.wowhead.com/tooltip/item/{item_id}"

STAT_LABELS = {
    "stamina": "stamina",
    "strength": "strength",
    "agility": "agility",
    "intellect": "intellect",
    "haste": "haste",
    "mastery": "mastery",
    "versatility": "versatility",
    "critical strike": "crit",
    "crit": "crit",
}

HYBRID_TO_PRIMARIES = {
    "strength or intellect": ("strength", "intellect"),
    "agility or intellect": ("agility", "intellect"),
    "agility or strength": ("agility", "strength"),
    "intellect or strength": ("strength", "intellect"),
    "intellect or agility": ("agility", "intellect"),
    "strength or agility": ("agility", "strength"),
}

STAT_LINE = re.compile(
    r"\+\s*([\d,]+)\s+(?:\[([^\]]+)\]|(Stamina|Strength|Agility|Intellect|Haste|Mastery|Versatility|Critical Strike|Crit)\b)",
    re.IGNORECASE,
)
ITEM_LEVEL = re.compile(r"Item Level\s+([\d,]+)", re.IGNORECASE)
ARMOR_LINE = re.compile(r"([\d,]+)\s+Armor\b", re.IGNORECASE)


def strip_tooltip(text: str) -> str:
    cleaned = re.sub(r"(?i)<br\s*/?>", " ", text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _number(value: str) -> int:
    return int(value.replace(",", ""))


def parse_tooltip_stats(tooltip: str) -> dict[str, Any]:
    text = strip_tooltip(tooltip)
    stats: dict[str, int] = {}
    hybrids: dict[str, int] = {}
    for amount_text, hybrid, plain in STAT_LINE.findall(text):
        amount = _number(amount_text)
        if hybrid:
            key = hybrid.strip().casefold()
            hybrids[key] = hybrids.get(key, 0) + amount
            continue
        mapped = STAT_LABELS.get(plain.casefold())
        if mapped:
            stats[mapped] = stats.get(mapped, 0) + amount
    item_level_match = ITEM_LEVEL.search(text)
    armor_match = ARMOR_LINE.search(text)
    return {
        "itemLevel": _number(item_level_match.group(1)) if item_level_match else None,
        "armor": _number(armor_match.group(1)) if armor_match else None,
        "stats": stats,
        "hybrids": hybrids,
        "text": text,
    }


def assign_hybrids(parsed: dict[str, Any], primary: str) -> dict[str, int]:
    totals = dict(parsed.get("stats") or {})
    for label, amount in (parsed.get("hybrids") or {}).items():
        options = HYBRID_TO_PRIMARIES.get(label)
        if options and primary in options:
            totals[primary] = totals.get(primary, 0) + int(amount)
        elif not options:
            continue
        else:
            totals[options[0]] = totals.get(options[0], 0) + int(amount)
    return totals


def tooltip_query(item: dict[str, Any]) -> dict[str, str]:
    params: dict[str, str] = {}
    bonuses = [str(int(value)) for value in item.get("bonusIds") or [] if isinstance(value, (int, float))]
    gems = [str(int(value)) for value in item.get("gemIds") or [] if isinstance(value, (int, float))]
    enchants = [str(int(value)) for value in item.get("enchantIds") or [] if isinstance(value, (int, float))]
    if bonuses:
        params["bonus"] = ":".join(bonuses)
    if gems:
        params["gems"] = ":".join(gems)
    if enchants:
        params["ench"] = ":".join(enchants)
    return params


def fetch_tooltip(item: dict[str, Any], *, timeout: int = 30, retries: int = 4) -> dict[str, Any]:
    item_id = int(item["itemId"])
    url = TOOLTIP_URL.format(item_id=item_id)
    query = tooltip_query(item)
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    last_error = "unknown error"
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/javascript,*/*",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or "tooltip" not in payload:
                raise ValueError("tooltip JSON missing tooltip field")
            parsed = parse_tooltip_stats(str(payload.get("tooltip") or ""))
            return {
                "itemId": item_id,
                "name": payload.get("name") or item.get("name") or "",
                "quality": payload.get("quality"),
                "icon": payload.get("icon"),
                "query": query,
                "wowheadItemLevel": parsed["itemLevel"],
                "armor": parsed["armor"],
                "stats": parsed["stats"],
                "hybrids": parsed["hybrids"],
                "url": url,
            }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Wowhead tooltip failed for item {item_id}: {last_error}")


def reconstruct_loadout(
    items: dict[str, dict[str, Any]],
    *,
    primary: str,
    delay: float = 0.25,
    cache: "TooltipCache | None" = None,
) -> dict[str, Any]:
    slots = {}
    totals: dict[str, int] = {}
    failures = []
    for slot, item in items.items():
        if not isinstance(item, dict) or not item.get("itemId"):
            continue
        try:
            cached = cache.get(item) if cache else None
            if cached is None:
                if delay:
                    time.sleep(delay)
                cached = fetch_tooltip(item)
                if cache:
                    cache.set(item, cached)
            # Copy before mutating: `cached` may be a shared object other
            # threads are reading concurrently out of the cache.
            tooltip = dict(cached)
            assigned = assign_hybrids(tooltip, primary)
            tooltip["assignedStats"] = assigned
            slots[slot] = tooltip
            for key, amount in assigned.items():
                totals[key] = totals.get(key, 0) + amount
        except RuntimeError as exc:
            failures.append({"slot": slot, "itemId": item.get("itemId"), "reason": str(exc)})
            slots[slot] = {
                "itemId": item.get("itemId"),
                "name": item.get("name"),
                "error": str(exc),
            }
    return {
        "slotCount": len(slots),
        "resolvedSlots": sum(1 for row in slots.values() if "assignedStats" in row),
        "totals": totals,
        "slots": slots,
        "failures": failures,
    }
