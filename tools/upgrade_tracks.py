"""Item upgrade tracks (Adventurer / Veteran / Champion / Hero / Myth) from
the game's own DB2 tables, and the bonus-id swap that moves a Best-in-Slot
item from the Myth track to the Hero or Champion track at that track's
6/6 (max) rank.

Source: wago.tools DB2 CSV exports (https://wago.tools/db2/<Table>/csv),
researched 2026-09-29:

  * ItemBonusListGroupEntry: one row per upgrade rank -- the group
    (ItemBonusListGroupID) is one track of one item family, SequenceValue
    is the rank, ItemBonusListID the bonus id an item at that rank carries.
    Flags bit 1 (value 1) marks the extension ranks past the normal 6/6
    (e.g. Myth 7-9 = 337/340/344 in Midnight Season 2).
  * ItemBonus: a rank's bonus list holds a type 34 row (Value_0 = the
    group id, Value_1 = the track code, see TRACK_CODES) and a type 49 row
    (SimC's ITEM_BONUS_SCALE_CONFIG, Value_0 = ItemScalingConfig id).
  * ItemScalingConfig.ItemLevel: the item level of that rank.

Two item families are live in the data: groups 608-612 (Midnight Season 1:
Myth 272-289) and 614-618 (Season 2: Myth 318-334, 6/6 = 334). Within a
family each track's 6/6 equals the next track's 2/6 (Hero 6/6 321 = Myth
2/6 321, Champion 6/6 308 = Hero 2/6 308), which pair_group() checks
before pairing two groups, so nothing is ever mapped on a guess.
"""
from __future__ import annotations

import csv
import io
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable, NamedTuple

WAGO_DB2_URL = "https://wago.tools/db2/{table}/csv"
DB2_TABLES = ("ItemBonus", "ItemBonusListGroupEntry", "ItemScalingConfig")

# ItemBonus type 34 Value_1 -> track. The same five codes label both
# families (608-612 and 614-618) in ascending item-level order.
TRACK_CODES: dict[int, str] = {971: "adventurer", 972: "veteran", 973: "champion", 974: "hero", 978: "myth"}
TRACK_ORDER: tuple[str, ...] = ("adventurer", "veteran", "champion", "hero", "myth")
# The lower tracks BiS items can be moved down to (the stat-target level pipeline
# in classcodex_targets.py runs once per target).
SWAP_TARGETS: tuple[str, ...] = ("hero", "champion")

ITEM_BONUS_TRACK = 34
ITEM_BONUS_SCALE_CONFIG = 49
EXTENSION_RANK_FLAG = 1
# Groups of one family sit next to each other (608..612, 614..618).
MAX_FAMILY_ID_GAP = 4


@dataclass
class Rank:
    bonus_id: int
    item_level: int | None
    extension: bool


@dataclass
class TrackGroup:
    group_id: int
    track: str | None
    ranks: dict[int, Rank] = field(default_factory=dict)

    @property
    def max_rank(self) -> int | None:
        """The last normal rank (6/6): extension ranks are not counted."""
        normal = [seq for seq, rank in self.ranks.items() if not rank.extension]
        return max(normal) if normal else None

    @property
    def max_bonus_id(self) -> int | None:
        return self.ranks[self.max_rank].bonus_id if self.max_rank is not None else None

    @property
    def max_item_level(self) -> int | None:
        return self.ranks[self.max_rank].item_level if self.max_rank is not None else None


def _int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_track_groups(
    item_bonus_rows: Iterable[dict[str, str]],
    group_entry_rows: Iterable[dict[str, str]],
    scaling_config_rows: Iterable[dict[str, str]],
) -> dict[int, TrackGroup]:
    """Every upgrade-track group (a group some bonus list names in a type 34
    ItemBonus row) with its ranks and item levels."""
    item_level_by_config = {
        _int(row.get("ID")): _int(row.get("ItemLevel")) for row in scaling_config_rows
    }
    code_by_group: dict[int, int] = {}
    config_by_list: dict[int, int] = {}
    for row in item_bonus_rows:
        bonus_type = _int(row.get("Type"))
        parent = _int(row.get("ParentItemBonusListID"))
        value0 = _int(row.get("Value_0"))
        if parent is None or value0 is None:
            continue
        if bonus_type == ITEM_BONUS_TRACK:
            code = _int(row.get("Value_1"))
            if code is not None:
                code_by_group.setdefault(value0, code)
        elif bonus_type == ITEM_BONUS_SCALE_CONFIG:
            config_by_list[parent] = value0

    groups: dict[int, TrackGroup] = {}
    for row in group_entry_rows:
        group_id = _int(row.get("ItemBonusListGroupID"))
        bonus_id = _int(row.get("ItemBonusListID"))
        seq = _int(row.get("SequenceValue"))
        if group_id not in code_by_group or bonus_id is None or seq is None or seq < 1:
            continue
        group = groups.setdefault(group_id, TrackGroup(group_id, TRACK_CODES.get(code_by_group[group_id])))
        config = config_by_list.get(bonus_id)
        flags = _int(row.get("Flags")) or 0
        group.ranks[seq] = Rank(
            bonus_id,
            item_level_by_config.get(config) if config is not None else None,
            bool(flags & EXTENSION_RANK_FLAG),
        )
    return groups


def pair_group(groups: dict[int, TrackGroup], upper: TrackGroup) -> TrackGroup | None:
    """The same family's group one track below `upper`: the nearest lower
    group id with that track, accepted only if its 6/6 item level equals
    `upper`'s 2/6 item level (the overlap every real family shows)."""
    if upper.track not in TRACK_ORDER or TRACK_ORDER.index(upper.track) == 0:
        return None
    lower_track = TRACK_ORDER[TRACK_ORDER.index(upper.track) - 1]
    candidates = [
        group for gid, group in groups.items()
        if group.track == lower_track and 0 < upper.group_id - gid <= MAX_FAMILY_ID_GAP
    ]
    if not candidates:
        return None
    lower = max(candidates, key=lambda group: group.group_id)
    second = upper.ranks.get(2)
    if lower.max_item_level is None or second is None or second.item_level != lower.max_item_level:
        return None
    return lower


def family_group(groups: dict[int, TrackGroup], source: TrackGroup, target_track: str) -> TrackGroup | None:
    """Walks down from `source` one verified track at a time to `target_track`."""
    current: TrackGroup | None = source
    while current is not None and current.track != target_track:
        current = pair_group(groups, current)
    return current


class TrackSwap(NamedTuple):
    """swap: {target track: {source bonus id: target 6/6 bonus id}}.
    item_levels: {"myth"|"hero"|"champion": item level of a 6/6 item}.
    unmapped: {target track: sorted source ids above that track with no
    verified mapping}. track_of: {observed upgrade-track bonus id: track}.
    top: {"myth"|"hero"|"champion": the 6/6 bonus id of the current season}: what an item of that track gets
    when the guide lists it without any bonus id."""

    swap: dict[str, dict[int, int]]
    item_levels: dict[str, int]
    unmapped: dict[str, list[int]]
    track_of: dict[int, str]
    top: dict[str, int] = {}


def _is_above(track: str | None, target: str) -> bool:
    return track in TRACK_ORDER and TRACK_ORDER.index(track) > TRACK_ORDER.index(target)


# The tracks whose items a tier moves to that tier's 6/6 (best rank): a tier never
# raises an item above the track it is listed on (a Hero-track item cannot become
# Myth), but every rank, extension rank and older-season family of the listed
# tracks lands on the current season's 6/6, so a tier shows one level.
TIER_SOURCE_TRACKS: dict[str, tuple[str, ...]] = {
    "myth": ("myth",),
    "hero": ("hero", "myth"),
    "champion": ("champion", "hero", "myth"),
}


def build_track_swap(observed_ids: Iterable[int], groups: dict[int, TrackGroup]) -> TrackSwap:
    """swap[target]: every observed bonus id on a source track of that target
    (TIER_SOURCE_TRACKS) -> the current season's 6/6 bonus id of the target
    track, for the targets myth, hero and champion. Ids already at that 6/6
    are left out. The current season is the Myth group with the highest 6/6
    item level; its Hero / Champion groups are walked down one verified track at
    a time."""
    group_of_bonus: dict[int, TrackGroup] = {}
    for group in groups.values():
        for rank in group.ranks.values():
            group_of_bonus[rank.bonus_id] = group
    myth_groups = [group for group in groups.values()
                   if group.track == "myth" and group.max_item_level is not None]
    current: dict[str, TrackGroup] = {}
    if myth_groups:
        myth = max(myth_groups, key=lambda group: group.max_item_level or 0)
        current["myth"] = myth
        for target in SWAP_TARGETS:
            destination = family_group(groups, myth, target)
            if destination is not None:
                current[target] = destination

    swap: dict[str, dict[int, int]] = {target: {} for target in TIER_SOURCE_TRACKS}
    unmapped: dict[str, list[int]] = {target: [] for target in SWAP_TARGETS}
    track_of: dict[int, str] = {}
    for bonus_id in sorted(set(observed_ids)):
        group = group_of_bonus.get(bonus_id)
        if group is None or group.track is None:
            continue
        track_of[bonus_id] = group.track
        for target, sources in TIER_SOURCE_TRACKS.items():
            if group.track not in sources:
                continue
            destination = current.get(target)
            if destination is not None and destination.max_bonus_id is not None:
                if bonus_id != destination.max_bonus_id:
                    swap[target][bonus_id] = destination.max_bonus_id
            elif target in unmapped:
                unmapped[target].append(bonus_id)

    item_levels = {target: group.max_item_level for target, group in current.items()
                   if group.max_item_level is not None}
    top = {target: group.max_bonus_id for target, group in current.items() if group.max_bonus_id is not None}
    return TrackSwap(swap, item_levels, unmapped, track_of, top)


def swap_bonus_ids(bonus_ids: list[int], target: str, track_swap: TrackSwap) -> tuple[list[int], bool, bool]:
    """(new bonus ids, whether any id was swapped, whether an id of a track
    above `target` had no mapping and was left as it is)."""
    mapping = track_swap.swap.get(target) or {}
    swapped = missed = False
    result: list[int] = []
    for bonus_id in bonus_ids:
        if bonus_id in mapping:
            result.append(mapping[bonus_id])
            swapped = True
            continue
        if _is_above(track_swap.track_of.get(bonus_id), target):
            missed = True
        result.append(bonus_id)
    return result, swapped, missed


# build() fields whose entries are items carrying bonus ids.
ITEM_FIELDS = ("gear", "trinkets")


def collect_bonus_ids(specs: dict[str, dict[str, Any]]) -> set[int]:
    """Every bonus id on a gear or trinket entry (`bonusIDs` and
    `catalyst.bonusIDs`) of a classcodex_build.build() result."""
    found: set[int] = set()

    def add(values: Any) -> None:
        for value in values if isinstance(values, list) else []:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                found.add(int(value))

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "itemId" in node:
                add(node.get("bonusIDs"))
                catalyst = node.get("catalyst")
                if isinstance(catalyst, dict):
                    add(catalyst.get("bonusIDs"))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for fields in specs.values():
        for name in ITEM_FIELDS:
            walk(((fields or {}).get(name) or {}).get("value"))
    return found


def fetch_db2_rows(table: str, timeout: float = 120.0, attempts: int = 4, pause: float = 10.0) -> list[dict[str, str]]:
    """One DB2 table from wago.tools. A timeout or a dropped connection is retried (pause, 2 x pause, ... between
    the attempts): the weekly run once wrote its data without track levels because one read timed out."""
    url = WAGO_DB2_URL.format(table=table)
    request = urllib.request.Request(url, headers={"User-Agent": "StatVerdict-UpgradeTracks/1.0"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8")
            return list(csv.DictReader(io.StringIO(text)))
        except (urllib.error.URLError, OSError) as exc:
            if attempt == attempts:
                raise
            print(f"{table}: attempt {attempt}/{attempts} failed ({exc}); trying again", file=sys.stderr)
            time.sleep(pause * attempt)
    raise AssertionError("unreachable")


def fetch_track_groups() -> dict[int, TrackGroup]:
    """parse_track_groups on the live wago.tools exports (network)."""
    item_bonus, group_entries, scaling = (fetch_db2_rows(table) for table in DB2_TABLES)
    return parse_track_groups(item_bonus, group_entries, scaling)


def load_track_swap(specs: dict[str, dict[str, Any]]) -> TrackSwap | None:
    """build_track_swap for every bonus id in `specs`, or None (with the
    reason on stderr) when the DB2 tables cannot be fetched. The targets CLI
    then refuses to write (see --allow-missing-track-levels)."""
    try:
        groups = fetch_track_groups()
    except (urllib.error.URLError, OSError, ValueError, csv.Error) as exc:
        print(f"Upgrade-track tables unavailable: {exc}", file=sys.stderr)
        return None
    return build_track_swap(collect_bonus_ids(specs), groups)
