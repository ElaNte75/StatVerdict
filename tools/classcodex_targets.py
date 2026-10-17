"""Builds per-goal, per-spec, per-hero-tree BiS stat targets from the already-merged guide data
(tools/classcodex_build.py): the stats of the guide's Best in Slot pieces, with the recommended gems and
enchants, added up (Wowhead item tooltips) at Myth, Hero and Champion 6/6, plus the fixed rating each
specialization has without gear (tools/data/spec_base_stats.json). No simulation.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, NamedTuple

try:
    from tools.classcodex_rules import bis_gear, default_priority, guide_field, guide_field_with_fallback, pvp_bonus_lookup
    from tools.classcodex_build import ENCHANT_LOOKUP_FIELD, collect_real_enchants
    from tools.classcodex_lua_sandbox import run_addon_namespace
    from tools.spec_catalog import SPEC_BY_KEY
    from tools.upgrade_tracks import SWAP_TARGETS, TrackSwap, swap_bonus_ids
except ModuleNotFoundError:
    from classcodex_rules import bis_gear, default_priority, guide_field, guide_field_with_fallback, pvp_bonus_lookup
    from classcodex_build import ENCHANT_LOOKUP_FIELD, collect_real_enchants
    from classcodex_lua_sandbox import run_addon_namespace
    from spec_catalog import SPEC_BY_KEY
    from upgrade_tracks import SWAP_TARGETS, TrackSwap, swap_bonus_ids

CLASSCODEX_SLOT_TO_TOKEN: dict[str, str] = {
    "Head": "HEAD",
    "Neck": "NECK",
    "Shoulders": "SHOULDER",
    "Back": "BACK",
    "Chest": "CHEST",
    "Wrist": "WRIST",
    "Hands": "HANDS",
    "Waist": "WAIST",
    "Legs": "LEGS",
    "Feet": "FEET",
    "Finger 1": "FINGER_1",
    "Finger 2": "FINGER_2",
    "Trinket 1": "TRINKET_1",
    "Trinket 2": "TRINKET_2",
    "Main Hand": "MAIN_HAND",
    "Off Hand": "OFF_HAND",
}

FALLBACK_CONTEXT_KEY = "all"
ALL_HERO_TALENTS_KEY = "all"

# Per goal, the ClassCodex context keys to try, in order, before the final
# FALLBACK_CONTEXT_KEY ("all"). Real ClassCodex data (build
# 20260928064230-9b041a5-43564495) keys `statPriority` by "single-target" /
# "aoe" / "pvp" -- never "mplus"/"raid" -- while gear/talents use
# "mplus"/"raid"/"pvp". Mythic+ is AoE-heavy content and Raid is
# single-target-heavy, so those are each goal's second choice. PvP has no
# aoe/single-target equivalent.
# Overall is the guide's own "all" list; its talents exist only per goal, so
# those come from Mythic+.
GOAL_CONTEXT_KEYS: dict[str, tuple[str, ...]] = {
    "OVERALL": ("all", "mplus"),
    "MYTHIC_PLUS": ("mplus", "aoe"),
    "RAID": ("raid", "single-target"),
    "PVP": ("pvp",),
}

GOAL_LABEL: dict[str, str] = {"OVERALL": "Overall", "MYTHIC_PLUS": "Mythic+", "RAID": "Raid", "PVP": "PvP"}

# Every stat name this pipeline emits -- targets, priority order/tiers -- goes through canonical_stat_name() to the
# addon's own canonical keys (STAT_KEY in StatVerdict/Core/SV_ProfileRepository.lua), so the generated files never leak
# a raw upstream token the addon would silently drop.

# Lower-cased upstream spellings -> canonical. Covers the guide's priority tokens ("crit"), the short names
# ("Crit", "Haste", "Mastery", "Vers"), the long names ("crit_rating", ...), the Wowhead tooltip rating keys and the
# addon's own spellings.
STAT_TO_CANONICAL: dict[str, str] = {
    "crit": "critical_strike",
    "crit_rating": "critical_strike",
    "critical_strike": "critical_strike",
    "critical-strike": "critical_strike",
    "haste": "haste",
    "haste_rating": "haste",
    "mastery": "mastery",
    "mastery_rating": "mastery",
    "vers": "versatility",
    "versatility": "versatility",
    "versatility_rating": "versatility",
}


def canonical_stat_name(raw: Any) -> str | None:
    """Maps any known upstream spelling of a secondary stat to the addon's
    canonical key, or None if it is not one of the four secondaries."""
    if not isinstance(raw, str):
        return None
    return STAT_TO_CANONICAL.get(raw.strip().lower())


def select_goal_context(nested: dict[str, Any] | None, hero_talent_key: str, goal: str) -> Any | None:
    """Goal-based lookup used by the batch builders. Tries the goal's ordered
    context keys (GOAL_CONTEXT_KEYS) and then "all" under the requested hero
    talent; if none of those holds a non-empty value, repeats the same chain
    under the "all" hero-talent key. ClassCodex uses "all" as the hero key
    for fields that do not vary by hero talent (see tools/classcodex_build.py)
    and real data relies on it: Mythic+/Raid gear and all trinkets live only
    under hero "all", while talents and aoe/single-target stat priorities
    live only under the specific hero keys. Empty values are treated as
    absent so the chain keeps looking. Returns None if nothing matches."""
    return select_goal_context_keyed(nested, hero_talent_key, goal)[0]


def select_goal_context_keyed(
    nested: dict[str, Any] | None, hero_talent_key: str, goal: str
) -> tuple[Any | None, str | None, str | None]:
    """select_goal_context, also returning the (hero key, context key) the
    value was found under ((None, None, None) when nothing matched)."""
    if not isinstance(nested, dict):
        return None, None, None
    context_keys = GOAL_CONTEXT_KEYS[goal] + (FALLBACK_CONTEXT_KEY,)
    hero_keys = [hero_talent_key]
    if hero_talent_key != ALL_HERO_TALENTS_KEY:
        hero_keys.append(ALL_HERO_TALENTS_KEY)
    for hero_key in hero_keys:
        by_context = nested.get(hero_key)
        if not isinstance(by_context, dict):
            continue
        for context_key in context_keys:
            value = by_context.get(context_key)
            if value:
                return value, hero_key, context_key
    return None, None, None


def field_origin(field: dict[str, Any] | None, hero_talent_key: str, goal: str) -> str | None:
    """Which source (classcodex_build `origins`, else the field's `source`)
    the goal/hero-talent value of one build() field came from."""
    if not isinstance(field, dict):
        return None
    _value, hero_key, context_key = select_goal_context_keyed(field.get("value"), hero_talent_key, goal)
    if hero_key is None:
        return None
    origins = field.get("origins")
    origin = ((origins or {}).get(hero_key) or {}).get(context_key) if isinstance(origins, dict) else None
    return origin or field.get("source")


def gear_by_slot(gear_list: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """The usable entries of a ClassCodex gear list keyed by slot token (HEAD, FINGER_1, ...),
    skipping unknown slots and missing itemIds. If two entries map to the
    same slot, the LAST one wins -- the single rule every consumer (item
    totals, BiS slots) derives from, so they always describe the same loadout."""
    by_slot: dict[str, dict[str, Any]] = {}
    for entry in gear_list or []:
        if not isinstance(entry, dict):
            continue
        catalyst = entry.get("catalyst")
        if isinstance(catalyst, dict):
            # Icy Veins: {itemId = <the BiS tier piece>, catalyst = {itemId = <the base item that
            # converts into it>, bonusIDs = {...}}}. Checked against the item data (Head:
            # 271483 "Serpent Crown of the Ophidian Oracle" is the set piece, 251220 "Voidscarred
            # Crown" the base drop). The BiS item is the top-level one; only the catalyst block
            # carries the bonus ids that put it at max upgrade, so those are added to it.
            entry = {k: v for k, v in entry.items() if k not in ("catalyst", "bonusIDs")}
            if isinstance(catalyst.get("bonusIDs"), list):
                entry["bonusIDs"] = catalyst["bonusIDs"]
        slot_token = CLASSCODEX_SLOT_TO_TOKEN.get(str(entry.get("slot") or ""))
        if slot_token is None or not isinstance(entry.get("itemId"), (int, float)):
            continue
        by_slot[slot_token] = entry
    return by_slot


def _bonus_ids(entry: dict[str, Any]) -> list[int] | None:
    bonus_ids = entry.get("bonusIDs")
    if not isinstance(bonus_ids, list):
        return None
    return [int(v) for v in bonus_ids if isinstance(v, (int, float))]


class LoadoutUpgrades(NamedTuple):
    """The recommended enchants and gems added to the BiS loadout.

    enchants: {slot token: {"id"?: SpellItemEnchantment id,
    "item_id"?: enchant scroll item id, "spell_id"?: enchant spell id}};
    an enchant without "id" could not be translated (resolve_enchant) and
    is shown but never counted.
    gems: {"primary"?: gem item id, "secondary"?: gem item id}. The primary gem is
    UNIQUE-EQUIPPED (worn once); the secondary one fills every other socket.

    Only the single best choice is kept (owner decision 2026-09-29: no
    alternatives are shown)."""

    enchants: dict[str, dict[str, int]]
    gems: dict[str, int]


NO_UPGRADES = LoadoutUpgrades({}, {})

# Slots that never get gems.
GEMLESS_SLOTS = frozenset({"TRINKET_1", "TRINKET_2", "MAIN_HAND", "OFF_HAND"})

# APPROXIMATION: the guide does not say which items have sockets (the addon reads them at runtime from tooltips).
# So the secondary gem goes on every gem-able item and the item tooltip counts only the sockets an item really has
# (gem ids beyond an item's sockets are ignored). The unique primary gem is worn ONCE, on the first item present in
# this order (jewelry commonly carries the sockets); if that item has no socket, the primary is not counted.
PRIMARY_GEM_SLOT_ORDER = ("NECK", "FINGER_1", "FINGER_2", "HEAD")


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def _pop(entry: dict[str, Any]) -> float:
    pop = entry.get("pop")
    return float(pop) if isinstance(pop, (int, float)) and not isinstance(pop, bool) else 0.0


class EnchantLookup(NamedTuple):
    """Translation tables for enchant ids (see
    tools/classcodex_build.build_enchant_lookup)."""

    by_item: dict[int, dict[str, int]]
    by_spell: dict[int, dict[str, int]]
    recipe_spell_by_item: dict[int, int]


def _enchant_lookup(enchants_value: Any, lookup_value: Any) -> EnchantLookup:
    """The build's shared lookup (lookup_value, may be None) plus every real
    enchant entry found in enchants_value itself."""
    lookup = lookup_value if isinstance(lookup_value, dict) else {}
    by_item = dict(lookup.get("byItem") or {})
    by_spell = dict(lookup.get("bySpell") or {})
    collect_real_enchants(enchants_value, by_item, by_spell)
    return EnchantLookup(by_item, by_spell, dict(lookup.get("recipeSpellByItem") or {}))


def resolve_enchant(entry: dict[str, Any], lookup: EnchantLookup) -> dict[str, int] | None:
    """One ClassCodex enchant entry as {"id"?, "item_id"?, "spell_id"?}.

    `id` is present ONLY when it is a real SpellItemEnchantment id; an entry that cannot be
    translated keeps just the scroll item id / spell id it carried, so it can still be shown by
    name but is never counted. Shapes:
      - {id, itemId?, spellId?} with id differing from itemId/spellId
        (u.gg PvE): already real.
      - {id, spellId} with id == spellId (Icy Veins' weapon runes): a spell
        id, translated through lookup.by_spell.
      - bare {id} (Icy Veins, u.gg PvP): an enchant SCROLL item id,
        translated through lookup.by_item, else the db_gamedata recipe's
        spell id and lookup.by_spell.
    Returns None for an entry with no usable number at all."""
    raw_id = _int_or_none(entry.get("id"))
    item_id = _int_or_none(entry.get("itemId"))
    spell_id = _int_or_none(entry.get("spellId"))
    if raw_id is not None and (
        (item_id is not None and item_id != raw_id) or (spell_id is not None and spell_id != raw_id)
    ):
        enchant = {"id": raw_id}
        if item_id is not None:
            enchant["item_id"] = item_id
        if spell_id is not None:
            enchant["spell_id"] = spell_id
        return enchant
    if spell_id is not None:
        real = lookup.by_spell.get(spell_id)
        return dict(real) if real is not None else {"spell_id": spell_id}
    scroll_id = item_id if item_id is not None else raw_id
    if scroll_id is None:
        return None
    real = lookup.by_item.get(scroll_id)
    if real is not None:
        return {**real, "item_id": scroll_id}
    recipe_spell = lookup.recipe_spell_by_item.get(scroll_id)
    if recipe_spell is None:
        return {"item_id": scroll_id}
    real = lookup.by_spell.get(recipe_spell)
    if real is not None:
        return {**real, "item_id": scroll_id, "spell_id": recipe_spell}
    return {"item_id": scroll_id, "spell_id": recipe_spell}


def select_loadout_upgrades(
    enchants_value: Any, gems_value: Any, hero_talent_key: str, goal: str, enchant_lookup: Any = None
) -> LoadoutUpgrades:
    """The single best enchant per slot and gem set for one goal/hero talent
    (goal context, then "all"; hero talent, then hero "all" -- see
    select_goal_context): Icy Veins' lists hold one entry, u.gg's (PvP)
    are ranked by pop. Every enchant goes through resolve_enchant (with
    `enchant_lookup`, the build's enchantLookup value); one without a real
    `id` is kept for display only (build_loadout_items skips it). Unknown slots
    are skipped."""
    enchants: dict[str, dict[str, int]] = {}
    lookup = _enchant_lookup(enchants_value, enchant_lookup)
    by_slot = guide_field_with_fallback(enchants_value, goal)  # ClassCodex reads enchants under hero "all"
    if isinstance(by_slot, dict):
        for slot_name, entries in by_slot.items():
            slot_token = CLASSCODEX_SLOT_TO_TOKEN.get(str(slot_name))
            candidates = [e for e in (entries if isinstance(entries, list) else []) if isinstance(e, dict)]
            if slot_token is None or not candidates:
                continue
            enchant = resolve_enchant(max(candidates, key=_pop), lookup)
            if enchant:
                enchants[slot_token] = enchant

    gems: dict[str, int] = {}
    gem_sets = guide_field_with_fallback(gems_value, goal)  # ... and gems too
    candidates = [e for e in (gem_sets if isinstance(gem_sets, list) else []) if isinstance(e, dict)]
    if candidates:
        best = max(candidates, key=_pop)
        primary = _int_or_none(best.get("primary"))
        if primary is not None:
            gems["primary"] = primary
        secondary = _first_secondary_gem(best)
        if secondary is not None:
            gems["secondary"] = secondary
    return LoadoutUpgrades(enchants, gems)


def _first_secondary_gem(gem_set: dict[str, Any]) -> int | None:
    secondary = gem_set.get("secondary")
    ids = [_int_or_none(gem) for gem in (secondary if isinstance(secondary, list) else [])]
    return next((gem_id for gem_id in ids if gem_id is not None), None)


def loadout_upgrades_for(fields: dict[str, Any], hero_talent_key: str, goal: str) -> LoadoutUpgrades:
    """select_loadout_upgrades on one spec's build() fields (shared by the
    targets and weights pipelines so both simulate the same gear)."""
    return select_loadout_upgrades(
        (fields.get("enchants") or {}).get("value"),
        (fields.get("gems") or {}).get("value"),
        hero_talent_key,
        goal,
        (fields.get(ENCHANT_LOOKUP_FIELD) or {}).get("value"),
    )


def guide_gear_list(
    gear_value: Any, goal: str, pvp_bonus: dict[int, list[int]] | None = None
) -> list[dict[str, Any]] | None:
    """The Best in Slot list ClassCodex shows for the goal (hero "all"). PvP items without bonus ids borrow
    them by item id from u.gg's PvP gear lists, as ClassCodex does (PvpItemBonusIds)."""
    return _with_pvp_bonus(bis_gear(gear_value, goal), goal, pvp_bonus)


def guide_trinket_list(
    trinkets_value: Any, goal: str, pvp_bonus: dict[int, list[int]] | None = None
) -> list[dict[str, Any]] | None:
    return _with_pvp_bonus(guide_field(trinkets_value, goal), goal, pvp_bonus)


def _with_pvp_bonus(entries: Any, goal: str, pvp_bonus: dict[int, list[int]] | None) -> Any:
    if goal != "PVP" or not pvp_bonus or not isinstance(entries, list):
        return entries
    out = []
    for entry in entries:
        if isinstance(entry, dict) and not entry.get("bonusIDs") and entry.get("itemId") in pvp_bonus:
            entry = {**entry, "bonusIDs": list(pvp_bonus[entry["itemId"]])}
        out.append(entry)
    return out


def build_loadout_items(
    gear_list: list[dict[str, Any]] | None, upgrades: LoadoutUpgrades | None = None
) -> dict[str, dict[str, Any]]:
    """Converts a ClassCodex gear list into an items dict keyed by WoW API
    slot tokens (as defined in CLASSCODEX_SLOT_TO_TOKEN). Each item carries its
    itemId, optional itemLevel (ilvl), and optional bonusIds (camelCase bonusIDs),
    plus -- when `upgrades` is given -- enchantIds for slots with a
    recommended enchant and gemIds: the secondary gem on every non-trinket,
    non-weapon item, plus the unique primary gem once (see
    PRIMARY_GEM_SLOT_ORDER for this approximation).
    Skips entries with unknown slots or missing itemIds; see gear_by_slot
    for duplicate slots."""
    upgrades = upgrades or NO_UPGRADES
    gear = gear_by_slot(gear_list)
    primary = upgrades.gems.get("primary")
    secondary = upgrades.gems.get("secondary")
    primary_slot = next((slot for slot in PRIMARY_GEM_SLOT_ORDER if slot in gear), None) if primary is not None else None
    items: dict[str, dict[str, Any]] = {}
    for slot_token, entry in gear.items():
        item: dict[str, Any] = {"itemId": int(entry["itemId"])}
        ilvl = entry.get("ilvl")
        if isinstance(ilvl, (int, float)):
            item["itemLevel"] = ilvl
        bonus_ids = _bonus_ids(entry)
        if bonus_ids is not None:
            item["bonusIds"] = bonus_ids
        if slot_token not in GEMLESS_SLOTS:
            gem_ids = [primary] if slot_token == primary_slot else []
            if secondary is not None:
                gem_ids.append(secondary)
            if gem_ids:
                item["gemIds"] = gem_ids
        enchant = upgrades.enchants.get(slot_token)
        if enchant and enchant.get("id") is not None:
            # Never a scroll/spell id: untranslated enchants are display-only.
            item["enchantIds"] = [enchant["id"]]
        items[slot_token] = item
    return items


def trinkets_from_entries(entries: Any) -> list[dict[str, Any]]:
    """Shapes one already-selected ClassCodex trinket context list."""
    if not isinstance(entries, list):
        return []
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("itemId"), (int, float)):
            continue
        tier = entry.get("tier")
        # Only the tiers the addon scores (S, A, B, C, D); anything else in
        # the guide data (e.g. an odd "F-") would be an unscored row.
        if not isinstance(tier, str) or tier.upper() not in ("S", "A", "B", "C", "D"):
            continue
        bonus_ids = entry.get("bonusIDs")
        result.append(
            {
                "item_id": int(entry["itemId"]),
                "bonus_ids": [int(v) for v in bonus_ids if isinstance(v, (int, float))] if isinstance(bonus_ids, list) else [],
                "tier": tier,
            }
        )
    return result


def priority_row_from_context(context: Any, context_label: str, hero_talent_name: str) -> dict[str, Any] | None:
    """Shapes one already-selected ClassCodex stat-priority context. Stat
    tokens are normalized to the addon's canonical keys ("crit" ->
    "critical_strike"); non-strings, unknown tokens and repeats are dropped."""
    tiers = context.get("secondary") if isinstance(context, dict) else None
    if not isinstance(tiers, list) or not tiers:
        return None
    order: list[str] = []
    tie_groups: list[list[str]] = []
    for group in tiers:
        if not isinstance(group, list) or not group:
            continue
        valid_entries: list[str] = []
        for entry in group:
            # Icy Veins sometimes annotates a stat: {"stat": "versatility", "note": "to 24%"}.
            if isinstance(entry, dict):
                entry = entry.get("stat")
            canonical = canonical_stat_name(entry)
            if canonical is not None and canonical not in order and canonical not in valid_entries:
                valid_entries.append(canonical)
        if not valid_entries:
            continue
        order.extend(valid_entries)
        if len(valid_entries) > 1:
            tie_groups.append(valid_entries)
    if not order:
        return None
    return {
        "context": context_label,
        "heroTalent": hero_talent_name,
        "order": order,
        "tiers": tie_groups,
    }


class ComboSkipped(Exception):
    """Raised by the per-combo builders with a short, human-readable reason
    for why one spec/goal/hero-talent combo produced no output (fail closed:
    the batch builders record the reason and move on)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


GEAR_SUM_TARGET_SOURCE = "ClassCodex BiS + gear totals (Wowhead item tooltips)"
def canonical_secondaries(raw_stats: dict[str, Any]) -> dict[str, float]:
    """The four secondaries of a raw {stat name: number} dict, canonical keys."""
    stats: dict[str, float] = {}
    for raw, value in raw_stats.items():
        canonical = canonical_stat_name(raw)
        if canonical is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
            stats[canonical] = float(value)
    return stats


def wowhead_gear_stats(
    spec: Any, items: dict[str, dict[str, Any]], wowhead_reconstruct: Callable[..., dict[str, Any]]
) -> tuple[dict[str, float], dict[str, float]]:
    """Gear-only secondary totals from Wowhead tooltips (no base stats,
    racials or talents). Any lookup failure -- including one unresolved
    slot -- skips the combo rather than shipping a partial sum. Returns
    (secondary totals, {slot: item level Wowhead's tooltip shows})."""
    try:
        loadout = wowhead_reconstruct(items, primary=spec.primary)
    except Exception as exc:  # noqa: BLE001 - fail closed (network, parsing, ...)
        print(f"Wowhead lookup error for {spec.spec_name}: {exc}", file=sys.stderr)
        raise ComboSkipped("Wowhead lookup failed") from exc
    if not isinstance(loadout, dict) or loadout.get("failures") or not isinstance(loadout.get("totals"), dict):
        failures = loadout.get("failures") if isinstance(loadout, dict) else None
        print(f"Wowhead lookup error for {spec.spec_name}: {failures or 'unusable result'}", file=sys.stderr)
        raise ComboSkipped("Wowhead lookup failed")
    levels: dict[str, float] = {}
    for slot, row in (loadout.get("slots") or {}).items():
        level = row.get("wowheadItemLevel") if isinstance(row, dict) else None
        if isinstance(level, (int, float)) and not isinstance(level, bool):
            levels[slot] = float(level)
    return canonical_secondaries(loadout["totals"]), levels


def _level_entry(stats: dict[str, float], average: float | None) -> dict[str, Any] | None:
    if sum(1 for value in stats.values() if value > 0) < 2:
        return None
    entry: dict[str, Any] = {"statTargets": {"stats": stats}}
    if average is not None:
        entry["averageItemLevel"] = average
    return entry


def describe_bis_slots(
    gear_list: list[dict[str, Any]] | None,
    items: dict[str, dict[str, Any]],
    upgrades: LoadoutUpgrades | None,
) -> tuple[list[dict[str, Any]], int, int]:
    """(bis slots, gem count, enchant count) of a whole guide loadout: the slots as the addon shows
    them, with the enchants applied."""
    loadout_by_slot = gear_by_slot(gear_list)
    upgrades = upgrades or NO_UPGRADES
    upgrade_enchants = upgrades.enchants
    bis_slots: list[dict[str, Any]] = []
    gem_count = 0
    enchant_count = 0
    for slot_token, entry in loadout_by_slot.items():
        item: dict[str, Any] = {"item_id": int(entry["itemId"])}
        bonus_ids = _bonus_ids(entry)
        if bonus_ids is not None:
            item["bonus_ids"] = bonus_ids
        simulated = items[slot_token]
        if simulated.get("gemIds"):
            gem_count += 1
        enchant = upgrade_enchants.get(slot_token)
        if simulated.get("enchantIds"):
            item["enchant"] = dict(enchant)
            enchant_count += 1
        elif enchant and enchant.get("id") is None:
            # Untranslated guide enchant: shown by its scroll item / spell
            # id only, never part of the totals.
            item["enchant"] = dict(enchant)
        bis_slots.append({"slot": entry["slot"], "item": item})
    return bis_slots, gem_count, enchant_count


SPEC_BASE_STATS_PATH = Path(__file__).resolve().parent / "data" / "spec_base_stats.json"


def load_spec_base_stats(path: Path = SPEC_BASE_STATS_PATH) -> dict[str, dict[str, float]]:
    """{spec key: {canonical secondary: rating the spec has without any gear}} (see the file's _note)."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: {stat: float(value) for stat, value in stats.items()}
        for key, stats in raw.items()
        if not key.startswith("_") and isinstance(stats, dict)
    }


def add_base_stats(stats: dict[str, float], base_stats: dict[str, float] | None) -> dict[str, float]:
    """The gear totals plus what the character has without gear, so the targets compare with the character sheet."""
    if not base_stats:
        return dict(stats)
    return {stat: stats.get(stat, 0.0) + base_stats.get(stat, 0.0) for stat in {**stats, **base_stats}}


def move_loadout_to_track(
    items: dict[str, dict[str, Any]], target: str, track_swap: TrackSwap
) -> dict[str, dict[str, Any]]:
    """The loadout with every item of the guide's list at `target` track's 6/6: known upgrade ids are
    swapped, a piece the guide lists without any bonus id (a tier piece converted at the Catalyst) gets
    the track's 6/6 id. A piece with other ids and no upgrade track (crafted) stays as it is: it is
    the same in every tier."""
    moved: dict[str, dict[str, Any]] = {}
    top = track_swap.top.get(target)
    for slot, item in items.items():
        bonus_ids = list(item.get("bonusIds") or [])
        new_ids, swapped, _missed = swap_bonus_ids(bonus_ids, target, track_swap)
        if not bonus_ids and top is not None:
            new_ids, swapped = [top], True
        if swapped:
            item = {key: value for key, value in item.items() if key not in ("itemLevel", "bonusIds")}
            item["bonusIds"] = new_ids
        moved[slot] = item
    return moved


def gear_sum_target_context(
    spec: Any,
    goal: str,
    gear_list: list[dict[str, Any]] | None,
    wowhead_reconstruct: Callable[..., dict[str, Any]],
    upgrades: LoadoutUpgrades | None = None,
    track_swap: TrackSwap | None = None,
    base_stats: dict[str, float] | None = None,
) -> dict[str, Any]:
    """The target context of one goal/hero tree from the plain sum of the guide's Best in Slot pieces
    with their gems and enchants (Wowhead item tooltips): targets.statTargets at Myth 6/6 and
    targets.levels at Hero and Champion 6/6, plus the spec's fixed rating without gear (`base_stats`,
    spec_base_stats.json) so they compare with the character sheet. No race, food or buffs. PvP
    gear has no upgrade tracks: it is summed as the guide lists it and has no levels.
    Raises ComboSkipped when a piece cannot be looked up or fewer than 2 secondary stats come out."""
    items = build_loadout_items(gear_list, upgrades)
    if not items:
        raise ComboSkipped("no usable gear for this goal")
    use_tracks = track_swap is not None and goal != "PVP"
    myth_items = move_loadout_to_track(items, "myth", track_swap) if use_tracks else items
    stats, item_levels = wowhead_gear_stats(spec, myth_items, wowhead_reconstruct)
    if sum(1 for value in stats.values() if value > 0) < 2:
        raise ComboSkipped("fewer than 2 usable secondary stats")
    stats = add_base_stats(stats, base_stats)
    level_values = list(item_levels.values())
    average = sum(level_values) / len(level_values) if level_values else None

    levels: dict[str, dict[str, Any]] = {}
    if use_tracks:
        for target in SWAP_TARGETS:
            try:
                level_stats, level_item_levels = wowhead_gear_stats(
                    spec, move_loadout_to_track(items, target, track_swap), wowhead_reconstruct
                )
            except ComboSkipped:
                continue
            level_average = sum(level_item_levels.values()) / len(level_item_levels) if level_item_levels else None
            entry = _level_entry(add_base_stats(level_stats, base_stats), level_average)
            if entry:
                levels[target] = entry
    bis_slots, gem_count, enchant_count = describe_bis_slots(gear_list, items, upgrades)
    bis: dict[str, Any] = {"label": "ClassCodex BiS"}
    if (upgrades or NO_UPGRADES).gems:
        bis["gems"] = dict((upgrades or NO_UPGRADES).gems)
    bis["slots"] = bis_slots
    targets: dict[str, Any] = {
        "averageItemLevel": average,
        "itemCount": len(items),
        "itemLevelSlots": len(level_values),
        "statTargets": {"context": goal, "source": GEAR_SUM_TARGET_SOURCE, "stats": stats},
        "targetMetadata": {
            "itemLevelSource": "wowhead" if level_values else "none",
            "lowItemReplacements": 0,
            "unresolvedLowItems": 0,
            "gemCount": gem_count,
            "enchantCount": enchant_count,
            **({"baseStats": dict(base_stats)} if base_stats else {}),
        },
        "sourceGoal": goal,
    }
    if levels:
        targets["levels"] = levels
    return {"targets": targets, "bis": bis}


def _classcodex_key_to_catalog_key(spec_key: str) -> str:
    class_folder, _, spec_token = spec_key.partition("_")
    return f"{class_folder}_{spec_token.upper().replace('-', '_')}"


def _hero_talent_keys(gear_value: dict[str, Any] | None, talents_value: dict[str, Any] | None) -> set[str]:
    """The hero-talent variants to build for one spec. When any field names a
    real hero talent, only those are built ("all" is then just the shared
    fallback data source, see select_goal_context); "all" is only built as
    its own variant when no field varies by hero talent at all."""
    keys: set[str] = set()
    if isinstance(gear_value, dict):
        keys.update(gear_value.keys())
    if isinstance(talents_value, dict):
        keys.update(talents_value.keys())
    specific = {key for key in keys if key != ALL_HERO_TALENTS_KEY}
    return specific or keys


class SkipRecord(NamedTuple):
    """One spec/goal/hero-talent combo (or whole spec, when goal/hero are
    None) that produced no output, and why."""

    spec_key: str
    goal: str | None
    hero_talent_key: str | None
    reason: str


def format_skip_summary(skips: list[SkipRecord], detail_limit: int = 40) -> str:
    """Human-readable summary for CI logs: counts by reason, plus the full
    list when it is short enough to read."""
    if not skips:
        return "No combos were skipped."
    lines = [f"{len(skips)} combo(s) skipped:"]
    for reason, count in Counter(skip.reason for skip in skips).most_common():
        lines.append(f"  {count:4d} x {reason}")
    if len(skips) <= detail_limit:
        lines.append("Details:")
        for skip in sorted(skips, key=lambda s: (s.spec_key, s.goal or "", s.hero_talent_key or "")):
            where = "/".join(part for part in (skip.spec_key, skip.goal, skip.hero_talent_key) if part)
            lines.append(f"  {where}: {skip.reason}")
    return "\n".join(lines)


def format_rating_sanity(data: dict[str, Any]) -> str:
    """CI-log sanity check of the tier targets: per spec/goal/hero-talent
    PvE context, our summed secondary rating at Champion 6/6, Hero 6/6 and Myth 6/6
    (statTargets). They must grow with the tier; a context without a level, or
    whose totals do not grow, is listed as a problem."""
    lines = ["Tier targets sanity (summed secondary rating, Champion < Hero < Myth):"]
    checked, problems = 0, []
    for spec_key, profile in sorted((data.get("profiles") or {}).items()):
        for goal, goal_data in ((profile or {}).get("goals") or {}).items():
            for hero, context in sorted(((goal_data or {}).get("heroTalents") or {}).items()):
                targets = (context or {}).get("targets") or {}
                where = f"{spec_key}/{goal}/{hero}"
                top = sum(((targets.get("statTargets") or {}).get("stats") or {}).values())
                if goal == "PVP":  # PvP gear has no upgrade tracks: the addon shows one set of targets
                    continue
                levels = targets.get("levels") or {}
                champion = sum((((levels.get("champion") or {}).get("statTargets") or {}).get("stats") or {}).values())
                hero_total = sum((((levels.get("hero") or {}).get("statTargets") or {}).get("stats") or {}).values())
                checked += 1
                if champion <= 0 or hero_total <= 0:
                    problems.append(f"  {where}: missing Champion/Hero level (Myth {top:.0f})")
                elif not champion < hero_total < top:
                    problems.append(
                        f"  {where}: not growing with the tier (Champion {champion:.0f}, Hero {hero_total:.0f}, Myth {top:.0f})"
                    )
    lines.append(f"  {checked} context(s) checked, {len(problems)} problem(s)")
    lines.extend(problems)
    return "\n".join(lines)


def format_coverage_report(data: dict[str, Any], track_swap: TrackSwap | None = None) -> str:
    """CI-log coverage check of a build_all document, per goal: contexts by
    gear source (targetMetadata.gearSource), trinket-list lengths, BiS-slot
    enchants (total / with a real enchant id / untranslated, shown only),
    contexts with gems, averageItemLevel present vs None (with where the
    item level came from) and contexts with Hero/Champion levels; plus, up
    front, the upgrade-track swap coverage (ids mapped / unmapped per
    target track) and the 6/6 item level of each track."""
    lines = ["Coverage report (per goal):"]
    if track_swap is None:
        lines.append("  track swap: not available (no Hero/Champion levels)")
    else:
        for target in SWAP_TARGETS:
            unmapped = track_swap.unmapped.get(target) or []
            detail = f" ({', '.join(str(bonus_id) for bonus_id in unmapped)})" if unmapped else ""
            lines.append(
                f"  track swap {target}: {len(track_swap.swap.get(target) or {})} id(s) mapped, "
                f"{len(unmapped)} unmapped{detail}"
            )
        levels_text = ", ".join(f"{track} {level}" for track, level in track_swap.item_levels.items())
        lines.append(f"  6/6 item levels: {levels_text or 'unknown'}")
    per_goal: dict[str, dict[str, Counter]] = {}
    for profile in (data.get("profiles") or {}).values():
        for goal, goal_data in ((profile or {}).get("goals") or {}).items():
            stats = per_goal.setdefault(
                goal,
                {
                    key: Counter()
                    for key in ("gear", "trinkets", "enchants", "gems", "ilvl", "ilvl_source", "levels", "contexts")
                },
            )
            for context in ((goal_data or {}).get("heroTalents") or {}).values():
                targets = (context or {}).get("targets") or {}
                metadata = targets.get("targetMetadata") or {}
                stats["contexts"]["total"] += 1
                for track in targets.get("levels") or {}:
                    stats["levels"][track] += 1
                if metadata.get("swapMisses"):
                    stats["levels"]["contexts with swap misses"] += 1
                stats["gear"][metadata.get("gearSource") or "unknown"] += 1
                stats["trinkets"][len((context or {}).get("trinkets") or [])] += 1
                for slot in ((context or {}).get("bis") or {}).get("slots") or []:
                    enchant = (slot.get("item") or {}).get("enchant") if isinstance(slot, dict) else None
                    if isinstance(enchant, dict):
                        stats["enchants"]["total"] += 1
                        stats["enchants"]["translated" if enchant.get("id") is not None else "untranslated"] += 1
                stats["gems"]["with gems" if metadata.get("gemCount") else "without gems"] += 1
                stats["ilvl"]["present" if targets.get("averageItemLevel") is not None else "None"] += 1
                stats["ilvl_source"][metadata.get("itemLevelSource") or "unknown"] += 1

    def fmt(counter: Counter) -> str:
        return ", ".join(f"{key}: {count}" for key, count in sorted(counter.items(), key=lambda kv: str(kv[0])))

    if not per_goal:
        lines.append("  no contexts")
    for goal in sorted(per_goal):
        stats = per_goal[goal]
        lines.append(f"  {goal}:")
        lines.append(f"    contexts by gear source: {fmt(stats['gear'])}")
        lines.append(f"    trinket count distribution (length: contexts): {fmt(stats['trinkets'])}")
        enchants = stats["enchants"]
        lines.append(
            f"    enchants on BiS slots: total {enchants['total']}, translated {enchants['translated']}, "
            f"untranslated (shown, not counted) {enchants['untranslated']}"
        )
        lines.append(f"    gems: {fmt(stats['gems'])}")
        lines.append(f"    averageItemLevel: {fmt(stats['ilvl'])} (source {fmt(stats['ilvl_source'])})")
        lines.append(
            f"    contexts with levels: {fmt(stats['levels']) or 'none'} (of {stats['contexts']['total']})"
        )
    return "\n".join(lines)


def count_contexts(data: dict[str, Any]) -> int:
    """Number of spec/goal/hero-talent leaves in a generated document
    (profiles[specKey].goals[goal].heroTalents[hero]) -- the unit the
    coverage floor compares, finer than a spec count so losing e.g. every
    PvP context is noticed even when every spec survives."""
    total = 0
    for profile in (data.get("profiles") or {}).values():
        goals = profile.get("goals") if isinstance(profile, dict) else None
        for goal_data in (goals or {}).values():
            hero_talents = goal_data.get("heroTalents") if isinstance(goal_data, dict) else None
            total += len(hero_talents or {})
    return total


def load_previous_document(path: Path, namespace_key: str) -> dict[str, Any] | None:
    """The previously generated document at `path`, loaded through the hardened
    Lua sandbox, or None if there is no previous file. Raises (fail closed) if
    the file exists but cannot be read back."""
    if not path.exists():
        return None
    namespace = run_addon_namespace(path.read_text(encoding="utf-8"), path.name, addon_name="StatVerdict")
    data = namespace.get(namespace_key) if isinstance(namespace, dict) else None
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not define ns.{namespace_key}")
    return data


def previous_context_count(path: Path, namespace_key: str) -> int | None:
    """Context count of the previously generated file at `path`, or None if there is no previous file."""
    data = load_previous_document(path, namespace_key)
    return None if data is None else count_contexts(data)


# Refuse to overwrite a previous file when the new run covers fewer than
# this fraction of its spec/goal/hero-talent contexts. 0.8 tolerates the
# odd combo dropping out upstream week to week, but not a broken week
# (or a whole missing role/goal) silently replacing good data.
DEFAULT_MIN_COVERAGE_RATIO = 0.8


def coverage_problem(new_count: int, previous_count: int | None, min_ratio: float) -> str | None:
    """Returns why the new output must not be written, or None if it may."""
    if new_count <= 0:
        return "no spec/goal/hero-talent context produced any output"
    if previous_count and new_count < previous_count * min_ratio:
        return (
            f"coverage dropped from {previous_count} to {new_count} contexts "
            f"(below the {min_ratio:.0%} floor of the previous file)"
        )
    return None


def gate_and_write(
    data: dict[str, Any],
    out: Path,
    namespace_key: str,
    write_file: Callable[[dict[str, Any], Path], int],
    min_coverage_ratio: float = DEFAULT_MIN_COVERAGE_RATIO,
) -> int:
    """Shared fail-closed gate for the generated-file CLIs: refuses (returns
    exit code 1, writing nothing) when the document is empty, when the file
    it would replace cannot be read back, or when coverage dropped below the
    floor; otherwise writes via `write_file` and returns 0."""
    try:
        previous = previous_context_count(out, namespace_key)
    except Exception as exc:  # noqa: BLE001 - fail closed: never overwrite what we cannot read back
        print(f"Refusing to write: could not read the previous {out} to compare coverage ({exc})", file=sys.stderr)
        return 1
    new_count = count_contexts(data)
    problem = coverage_problem(new_count, previous, min_coverage_ratio)
    if problem:
        print(f"Refusing to write {out}: {problem}.", file=sys.stderr)
        return 1
    size = write_file(data, out)
    print(
        f"Wrote {out} ({size} bytes, {len(data.get('profiles') or {})} specs, {new_count} contexts; "
        f"previous file: {previous if previous is not None else 'none'})"
    )
    return 0


def finish_target_context(
    target_context: dict[str, Any],
    fields: dict[str, Any],
    hero_talent_key: str,
    goal: str,
    trinkets_value: Any,
    stat_priority_value: Any,
    pvp_bonus: dict[int, list[int]],
) -> dict[str, Any]:
    """Adds what every context carries besides its targets: where the gear list came from, the trinket
    list and the guide's stat order."""
    gear_source = field_origin(fields.get("gear"), "all", goal)
    if gear_source:
        target_context["targets"]["targetMetadata"]["gearSource"] = gear_source
    target_context["trinkets"] = trinkets_from_entries(guide_trinket_list(trinkets_value, goal, pvp_bonus))
    row = priority_row_from_context(
        default_priority(stat_priority_value, hero_talent_key, goal),
        GOAL_LABEL[goal],
        hero_talent_key,
    )
    target_context["priorityProfiles"] = [row] if row else []
    return target_context


def build_all(
    specs: dict[str, dict[str, Any]],
    goals: tuple[str, ...] = ("OVERALL", "MYTHIC_PLUS", "RAID", "PVP"),
    skips: list[SkipRecord] | None = None,
    wowhead_reconstruct: Callable[..., dict[str, Any]] | None = None,
    track_swap: TrackSwap | None = None,
) -> dict[str, Any]:
    """Loops over every spec/goal/hero-tree combo of the merged guide data and builds its context
    (gear_sum_target_context: the plain sum of the guide's pieces, `wowhead_reconstruct` looks the
    pieces up), then assembles the full per-spec document. Skips spec keys not in the SPEC_BY_KEY
    catalog and combos with no usable data or a failed lookup; when `skips` is given, one SkipRecord per
    skipped spec/combo is appended to it. `track_swap` adds each context's Hero and Champion levels;
    the caller writes trackSwap/trackItemLevels at the document root."""
    skipped: list[SkipRecord] = skips if skips is not None else []
    base_stats_by_spec = load_spec_base_stats()
    profiles: dict[str, Any] = {}
    pvp_bonus = pvp_bonus_lookup(specs)
    for spec_key, fields in specs.items():
        catalog_key = _classcodex_key_to_catalog_key(spec_key)
        spec = SPEC_BY_KEY.get(catalog_key)
        if spec is None:
            skipped.append(SkipRecord(spec_key, None, None, "spec not in StatVerdict's catalog"))
            continue

        gear_value = (fields.get("gear") or {}).get("value")
        talents_value = (fields.get("talents") or {}).get("value")
        trinkets_value = (fields.get("trinkets") or {}).get("value")
        stat_priority_value = (fields.get("statPriority") or {}).get("value")

        hero_talent_keys = sorted(_hero_talent_keys(gear_value, talents_value))
        if not hero_talent_keys:
            skipped.append(SkipRecord(catalog_key, None, None, "no gear or talents data"))
        goals_out: dict[str, Any] = {}
        for goal in goals:
            hero_talents_out: dict[str, Any] = {}
            for hero_talent_key in hero_talent_keys:
                gear_list = guide_gear_list(gear_value, goal, pvp_bonus)
                try:
                    target_context = gear_sum_target_context(
                        spec,
                        goal,
                        gear_list,
                        wowhead_reconstruct,
                        upgrades=loadout_upgrades_for(fields, hero_talent_key, goal),
                        track_swap=track_swap,
                        base_stats=base_stats_by_spec.get(catalog_key),
                    )
                except ComboSkipped as skip:
                    skipped.append(SkipRecord(catalog_key, goal, hero_talent_key, skip.reason))
                    continue
                hero_talents_out[hero_talent_key] = finish_target_context(
                    target_context, fields, hero_talent_key, goal, trinkets_value, stat_priority_value, pvp_bonus
                )
            if hero_talents_out:
                goals_out[goal] = {"heroTalents": hero_talents_out}

        if goals_out:
            # Keyed by the addon's own spec key (e.g. "DEATHKNIGHT_FROST", as
            # ns.GetStatVerdictSpecKeyBySpecID returns it), not ClassCodex's
            # raw "DEATHKNIGHT_frost".
            profiles[catalog_key] = {
                "specKey": catalog_key,
                "classToken": catalog_key.split("_", 1)[0],
                "primaryStat": spec.primary,
                "goals": goals_out,
            }

    return {"profiles": profiles}
