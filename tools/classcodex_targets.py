"""Builds per-goal, per-spec, per-hero-talent BiS stat targets from the
already-merged ClassCodex data (tools/classcodex_build.py) by reconstructing
paper-doll stats through SimulationCraft (tools/simc_stat_engine.py).

See docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline-spec.md
for the full design and the real data shapes this module relies on.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, NamedTuple

try:
    from tools.classcodex_lua_sandbox import run_addon_namespace
    from tools.simc_stat_engine import run_simc, run_simc_with_recovery
    from tools.spec_catalog import SPEC_BY_KEY
except ModuleNotFoundError:
    from classcodex_lua_sandbox import run_addon_namespace
    from simc_stat_engine import run_simc, run_simc_with_recovery
    from spec_catalog import SPEC_BY_KEY

CLASSCODEX_SLOT_TO_SIMC: dict[str, str] = {
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
GOAL_CONTEXT_KEYS: dict[str, tuple[str, ...]] = {
    "MYTHIC_PLUS": ("mplus", "aoe"),
    "RAID": ("raid", "single-target"),
    "PVP": ("pvp",),
}

# First-choice context key per goal (kept for callers that resolve a single
# explicit key through select_context()).
GOAL_CONTEXT_KEY: dict[str, str] = {goal: keys[0] for goal, keys in GOAL_CONTEXT_KEYS.items()}

GOAL_LABEL: dict[str, str] = {"MYTHIC_PLUS": "Mythic+", "RAID": "Raid", "PVP": "PvP"}

# The addon's own canonical secondary-stat keys (STAT_KEY in
# StatVerdict/Core/SV_ProfileRepository.lua). Every stat name this pipeline
# emits -- targets, priority order/tiers, weights (tools/classcodex_weights.py
# imports this) -- goes through canonical_stat_name() so the generated files
# never leak a raw upstream token the addon would silently drop.
CANONICAL_SECONDARY_STATS: tuple[str, ...] = ("critical_strike", "haste", "mastery", "versatility")

# Lower-cased upstream spellings -> canonical. Covers ClassCodex priority
# tokens ("crit"), simc_stat_engine.parse_report rating keys ("crit"), SimC's
# util::stat_type_abbrev names used in scale-factor reports ("Crit",
# "Haste", "Mastery", "Vers"), SimC long names ("crit_rating", ...) and the
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


def select_context(nested: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> Any | None:
    """nested is a ClassCodex `{heroTalentKey: {contextKey: value}}` field
    (gear, talents, trinkets or statPriority's `.value`). Returns the exact
    goal context if present, else the `"all"` fallback, else None."""
    if not isinstance(nested, dict):
        return None
    by_context = nested.get(hero_talent_key)
    if not isinstance(by_context, dict):
        return None
    if context_key in by_context:
        return by_context[context_key]
    return by_context.get(FALLBACK_CONTEXT_KEY)


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
    if not isinstance(nested, dict):
        return None
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
                return value
    return None


def gear_by_simc_slot(gear_list: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """The usable entries of a ClassCodex gear list keyed by SimC slot token,
    skipping unknown slots and missing itemIds. If two entries map to the
    same slot, the LAST one wins -- the single rule every consumer (SimC
    items, BiS slots, item-level average) derives from, so they always
    describe the same loadout."""
    by_slot: dict[str, dict[str, Any]] = {}
    for entry in gear_list or []:
        if not isinstance(entry, dict):
            continue
        simc_slot = CLASSCODEX_SLOT_TO_SIMC.get(str(entry.get("slot") or ""))
        if simc_slot is None or not isinstance(entry.get("itemId"), (int, float)):
            continue
        by_slot[simc_slot] = entry
    return by_slot


def _bonus_ids(entry: dict[str, Any]) -> list[int] | None:
    bonus_ids = entry.get("bonusIDs")
    if not isinstance(bonus_ids, list):
        return None
    return [int(v) for v in bonus_ids if isinstance(v, (int, float))]


class LoadoutUpgrades(NamedTuple):
    """The recommended enchants and gems added to a simulated BiS loadout.

    enchants: {SimC slot: {"id": SpellItemEnchantment id (SimC enchant_id),
    "item_id"?: enchant scroll item id, "spell_id"?: enchant spell id}}.
    gems: gem item ids (SimC gem_id), primary gem first.

    enchant_alts / gem_alt: ONE alternative enchant per enchanted slot (same
    shape as `enchants`) and one alternative secondary gem, shown next to the
    recommended ones on the BiS slots. They are never simulated."""

    enchants: dict[str, dict[str, int]]
    gems: list[int]
    enchant_alts: dict[str, dict[str, int]] = {}
    gem_alt: int | None = None


NO_UPGRADES = LoadoutUpgrades({}, [])

# Slots that never get gems. ClassCodex does not say which items have a
# socket, so gems go on every other item and SimC fills whatever sockets an
# item really has (gem ids beyond an item's sockets are ignored; see
# simc_stat_engine.run_simc_with_recovery for the safety net).
GEMLESS_SIMC_SLOTS = frozenset({"TRINKET_1", "TRINKET_2"})


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def _pop(entry: dict[str, Any]) -> float:
    pop = entry.get("pop")
    return float(pop) if isinstance(pop, (int, float)) and not isinstance(pop, bool) else 0.0


def _scroll_to_enchant(enchants_value: Any) -> dict[int, dict[str, int]]:
    """u.gg's PvP enchant entries carry only the enchant SCROLL's item id in
    `id`; the PvE entries carry both the real enchant id and the scroll's
    itemId. This maps scroll item id -> {id, spell_id} from every entry that
    has both, so a PvP scroll can be turned into its real enchant."""
    mapping: dict[int, dict[str, int]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            item_id = _int_or_none(node.get("itemId"))
            enchant_id = _int_or_none(node.get("id"))
            if item_id is not None and enchant_id is not None and item_id != enchant_id:
                found = {"id": enchant_id}
                spell_id = _int_or_none(node.get("spellId"))
                if spell_id is not None:
                    found["spell_id"] = spell_id
                mapping.setdefault(item_id, found)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(enchants_value)
    return mapping


def select_loadout_upgrades(enchants_value: Any, gems_value: Any, hero_talent_key: str, goal: str) -> LoadoutUpgrades:
    """u.gg's most popular enchant per slot and most popular gem set for one
    goal/hero talent (goal context, then "all"; hero talent, then hero
    "all" -- see select_goal_context). Unknown slots and entries without a
    numeric id are skipped."""
    enchants: dict[str, dict[str, int]] = {}
    enchant_alts: dict[str, dict[str, int]] = {}
    scroll_map = _scroll_to_enchant(enchants_value)
    by_slot = select_goal_context(enchants_value, hero_talent_key, goal)
    if isinstance(by_slot, dict):
        for slot_name, entries in by_slot.items():
            simc_slot = CLASSCODEX_SLOT_TO_SIMC.get(str(slot_name))
            candidates = [
                e for e in (entries if isinstance(entries, list) else [])
                if isinstance(e, dict) and _int_or_none(e.get("id")) is not None
            ]
            if simc_slot is None or not candidates:
                continue
            best = max(candidates, key=_pop)
            enchant = _shape_enchant(best, scroll_map, goal)
            if enchant is None:
                continue
            enchants[simc_slot] = enchant
            # The alternative: the next most popular enchant with another
            # (real) id; untranslatable PvP scrolls are skipped.
            for entry in sorted(candidates, key=_pop, reverse=True):
                if entry is best:
                    continue
                alt = _shape_enchant(entry, scroll_map, goal)
                if alt is not None and alt["id"] != enchant["id"]:
                    enchant_alts[simc_slot] = alt
                    break

    gems: list[int] = []
    gem_alt: int | None = None
    gem_sets = select_goal_context(gems_value, hero_talent_key, goal)
    candidates = [e for e in (gem_sets if isinstance(gem_sets, list) else []) if isinstance(e, dict)]
    if candidates:
        best = max(candidates, key=_pop)
        primary = _int_or_none(best.get("primary"))
        if primary is not None:
            gems.append(primary)
        chosen_secondary = _secondary_gems(best)
        gems.extend(chosen_secondary)
        # The alternative: the first secondary gem of the next most popular
        # set whose first secondary differs from the chosen set's.
        for entry in sorted(candidates, key=_pop, reverse=True):
            if entry is best:
                continue
            secondary = _secondary_gems(entry)
            if secondary and secondary[0] not in chosen_secondary:
                gem_alt = secondary[0]
                break
    return LoadoutUpgrades(enchants, gems, enchant_alts, gem_alt)


def _secondary_gems(gem_set: dict[str, Any]) -> list[int]:
    secondary = gem_set.get("secondary")
    ids = [_int_or_none(gem) for gem in (secondary if isinstance(secondary, list) else [])]
    return [gem_id for gem_id in ids if gem_id is not None]


def _shape_enchant(entry: dict[str, Any], scroll_map: dict[int, dict[str, int]], goal: str) -> dict[str, int] | None:
    """One u.gg enchant entry as {"id", "item_id"?, "spell_id"?}, or None
    when it cannot be used."""
    enchant = {"id": _int_or_none(entry["id"])}
    for source_key, out_key in (("itemId", "item_id"), ("spellId", "spell_id")):
        value = _int_or_none(entry.get(source_key))
        if value is not None:
            enchant[out_key] = value
    if "item_id" not in enchant and "spell_id" not in enchant:
        # In PvP lists a bare id is a scroll item id: translate it to
        # the real enchant, or drop the enchant rather than ship a
        # scroll id where an enchant id belongs (PvE bare ids are
        # real enchant ids and stay as they are).
        real = scroll_map.get(enchant["id"])
        if real is not None:
            enchant = {"item_id": enchant["id"], **real}
        elif goal == "PVP":
            return None
    return enchant


def loadout_upgrades_for(fields: dict[str, Any], hero_talent_key: str, goal: str) -> LoadoutUpgrades:
    """select_loadout_upgrades on one spec's build() fields (shared by the
    targets and weights pipelines so both simulate the same gear)."""
    return select_loadout_upgrades(
        (fields.get("enchants") or {}).get("value"), (fields.get("gems") or {}).get("value"), hero_talent_key, goal
    )


def build_simc_items(
    gear_list: list[dict[str, Any]] | None, upgrades: LoadoutUpgrades | None = None
) -> dict[str, dict[str, Any]]:
    """Converts a ClassCodex gear list into a SimC items dict keyed by WoW API
    slot tokens (as defined in CLASSCODEX_SLOT_TO_SIMC). Each item carries its
    itemId, optional itemLevel (ilvl), and optional bonusIds (camelCase bonusIDs),
    plus -- when `upgrades` is given -- enchantIds for slots with a
    recommended enchant and gemIds on every non-trinket item.
    Skips entries with unknown slots or missing itemIds; see gear_by_simc_slot
    for duplicate slots."""
    upgrades = upgrades or NO_UPGRADES
    items: dict[str, dict[str, Any]] = {}
    for simc_slot, entry in gear_by_simc_slot(gear_list).items():
        item: dict[str, Any] = {"itemId": int(entry["itemId"])}
        ilvl = entry.get("ilvl")
        if isinstance(ilvl, (int, float)):
            item["itemLevel"] = ilvl
        bonus_ids = _bonus_ids(entry)
        if bonus_ids is not None:
            item["bonusIds"] = bonus_ids
        if upgrades.gems and simc_slot not in GEMLESS_SIMC_SLOTS:
            item["gemIds"] = list(upgrades.gems)
        enchant = upgrades.enchants.get(simc_slot)
        if enchant:
            item["enchantIds"] = [enchant["id"]]
        items[simc_slot] = item
    return items


def average_item_level(gear_list: list[dict[str, Any]] | None) -> float | None:
    """Calculates the average item level from a gear list, ignoring entries
    without an ilvl field. Returns None if no entries have an ilvl."""
    levels = [
        float(entry["ilvl"])
        for entry in (gear_list or [])
        if isinstance(entry, dict) and isinstance(entry.get("ilvl"), (int, float))
    ]
    if not levels:
        return None
    return sum(levels) / len(levels)


def select_talent_export(talents_value: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> str | None:
    """Selects a talent export string for a goal/hero-talent combo. Returns the
    export string marked as recommended if present, else the export string of the
    first entry, or None if no valid entry exists."""
    return talent_export_from_entries(select_context(talents_value, hero_talent_key, context_key))


def talent_export_from_entries(entries: Any) -> str | None:
    """Picks the export string from one already-selected ClassCodex talent
    context list: the entry marked `recommended`, else the first entry (real
    u.gg lists are already ordered most-picked first)."""
    exports = talent_exports_from_entries(entries)
    return exports[0] if exports else None


def talent_exports_from_entries(entries: Any) -> list[str]:
    """Every usable export string of one ClassCodex talent context list, in
    the order to try them: `recommended` entries first, then the rest in
    list order, without duplicates."""
    if not isinstance(entries, list):
        return []
    exports: list[str] = []
    ordered = [e for e in entries if isinstance(e, dict) and e.get("recommended") is True]
    ordered += [e for e in entries if isinstance(e, dict) and e.get("recommended") is not True]
    for entry in ordered:
        export = entry.get("export")
        if isinstance(export, str) and export and export not in exports:
            exports.append(export)
    return exports


# SimC's messages when it rejects a talent export for this spec.
TALENT_ERROR_MARKERS = ("is not available to player's spec", "Selected node")


def is_talent_error(message: str) -> bool:
    return any(marker in message for marker in TALENT_ERROR_MARKERS)


def run_with_talent_fallback(
    simc_binary: Path,
    spec: Any,
    items: dict[str, dict[str, Any]],
    talent_exports: list[str],
    *,
    render_kwargs: dict[str, Any] | None = None,
    run_kwargs: dict[str, Any] | None = None,
    run_simc_fn: Any = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str], str]:
    """Runs one loadout through run_simc_with_recovery with each talent
    export in turn, moving on only when SimC rejects the talents; if every
    export is rejected, runs once more without a `talents=` line. Any other
    error is re-raised. The returned recovery labels add "talent export N"
    (N >= 2) or "talents ignored" to the weapon labels."""
    last_error: RuntimeError | None = None
    for index, export in enumerate(talent_exports, 1):
        record = {"race": "human", "runTalentLoadout": export, "items": items, "level": 90}
        try:
            stats, report, recovery, actor = run_simc_with_recovery(
                simc_binary, spec, record, render_kwargs=render_kwargs, run_kwargs=run_kwargs, run_simc_fn=run_simc_fn
            )
        except RuntimeError as exc:
            if not is_talent_error(str(exc)):
                raise
            last_error = exc
            continue
        labels = [f"talent export {index}"] if index > 1 else []
        return stats, report, labels + recovery, actor
    if last_error is None:
        raise ValueError("no talent export to run")
    record = {"race": "human", "runTalentLoadout": "", "items": items, "level": 90}
    stats, report, recovery, actor = run_simc_with_recovery(
        simc_binary,
        spec,
        record,
        render_kwargs={**(render_kwargs or {}), "talents_optional": True},
        run_kwargs=run_kwargs,
        run_simc_fn=run_simc_fn,
    )
    return stats, report, ["talents ignored"] + recovery, actor


def build_trinkets(trinkets_value: dict[str, Any] | None, hero_talent_key: str, context_key: str) -> list[dict[str, Any]]:
    """Converts a ClassCodex trinket list (tiered S/A/B/C/D) into the addon's
    expected shape. Returns a list of dicts with item_id, bonus_ids, and tier."""
    return trinkets_from_entries(select_context(trinkets_value, hero_talent_key, context_key))


def trinkets_from_entries(entries: Any) -> list[dict[str, Any]]:
    """Shapes one already-selected ClassCodex trinket context list."""
    if not isinstance(entries, list):
        return []
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("itemId"), (int, float)):
            continue
        tier = entry.get("tier")
        if not isinstance(tier, str) or not tier:
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


def build_priority_row(
    stat_priority_value: dict[str, Any] | None,
    hero_talent_key: str,
    context_key: str,
    context_label: str,
    hero_talent_name: str,
) -> dict[str, Any] | None:
    """Converts ClassCodex's stat-priority tier-groups into an order/tiers row
    matching what the WoW addon's SV_ProfileRepository.lua validates. Returns
    a dict with context, heroTalent, order, and tiers, or None if no secondary list."""
    return priority_row_from_context(
        select_context(stat_priority_value, hero_talent_key, context_key), context_label, hero_talent_name
    )


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


SIMC_ERROR_HEAD_CHARS = 1200
SIMC_ERROR_TAIL_CHARS = 600


def format_simc_error(exc: BaseException) -> str:
    """The SimC error text for the CI log. SimC prints the real fatal error
    early and then pages of trailing `Trivial:` warnings, so a long message
    keeps both its head and its tail."""
    text = str(exc)
    if len(text) <= SIMC_ERROR_HEAD_CHARS + SIMC_ERROR_TAIL_CHARS:
        return text
    return text[:SIMC_ERROR_HEAD_CHARS] + " [...] " + text[-SIMC_ERROR_TAIL_CHARS:]


class ComboSkipped(Exception):
    """Raised by the per-combo builders with a short, human-readable reason
    for why one spec/goal/hero-talent combo produced no output (fail closed:
    the batch builders record the reason and move on)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_target_context(
    spec: Any,
    goal: str,
    gear_list: list[dict[str, Any]] | None,
    talents_value: dict[str, Any] | None,
    hero_talent_key: str,
    context_key: str,
    simc_binary: Path = Path("simc"),
) -> dict[str, Any] | None:
    """Reconstructs the `targets`/`bis` half of a ClassCodex per-goal profile
    by running the BiS gear loadout for one spec/goal/hero-talent through
    SimulationCraft. Returns None if there is no gear, no talent export, or
    the SimC run fails or yields fewer than two usable secondary stats."""
    try:
        return reconstruct_target_context(
            spec, goal, gear_list, select_talent_export(talents_value, hero_talent_key, context_key), simc_binary
        )
    except ComboSkipped:
        return None


SIMC_TARGET_SOURCE = "ClassCodex BiS + SimulationCraft"
WOWHEAD_TARGET_SOURCE = "ClassCodex BiS + Wowhead gear totals (no SimC support for this spec)"

# Specs SimC cannot model are not one clean error message (Holy Paladin:
# "unsupported spec"; Restoration Shaman: "isn't supported yet"; Mistweaver:
# "not currently supported"; Holy Priest / Discipline: broken action lists),
# so the gear-only Wowhead fallback runs whenever SimC still fails after the
# recovery layer, and the result is labelled in statTargets.source and
# targetMetadata.recovery so it stays auditable.


# u.gg's own stat targets (ClassCodex `statTargets`): one context key per
# goal (no aoe/single-target/"all" fallback exists upstream) and the three
# percentile bins the official ClassCodex addon offers (top20 is its default).
GUIDE_TARGET_CONTEXT_KEY: dict[str, str] = {"MYTHIC_PLUS": "mplus", "RAID": "raid", "PVP": "pvp"}
GUIDE_TARGET_BINS: tuple[str, ...] = ("top20", "top50", "top80")


def guide_targets_for(stat_targets_value: Any, hero_talent_key: str, goal: str) -> dict[str, dict[str, float]] | None:
    """u.gg's stat targets for one goal/hero talent as
    {bin: {canonical stat: rating}}, taken from the hero talent's entry,
    falling back to hero "all" (as the official ClassCodex addon does).
    Returns None when u.gg has nothing usable for this goal."""
    if not isinstance(stat_targets_value, dict):
        return None
    context_key = GUIDE_TARGET_CONTEXT_KEY[goal]
    hero_keys = [hero_talent_key]
    if hero_talent_key != ALL_HERO_TALENTS_KEY:
        hero_keys.append(ALL_HERO_TALENTS_KEY)
    for hero_key in hero_keys:
        by_context = stat_targets_value.get(hero_key)
        bins = by_context.get(context_key) if isinstance(by_context, dict) else None
        if not isinstance(bins, dict):
            continue
        result: dict[str, dict[str, float]] = {}
        for bin_key in GUIDE_TARGET_BINS:
            raw = bins.get(bin_key)
            stats = canonical_secondaries(raw) if isinstance(raw, dict) else {}
            if stats:
                result[bin_key] = stats
        if result:
            return result
    return None


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
) -> dict[str, float]:
    """Gear-only secondary totals from Wowhead tooltips (no base stats,
    racials or talents). Any lookup failure -- including one unresolved
    slot -- skips the combo rather than shipping a partial sum."""
    try:
        loadout = wowhead_reconstruct(items, primary=spec.primary)
    except Exception as exc:  # noqa: BLE001 - fail closed (network, parsing, ...)
        print(f"Wowhead fallback error for {spec.spec_name}: {exc}", file=sys.stderr)
        raise ComboSkipped("wowhead fallback failed") from exc
    if not isinstance(loadout, dict) or loadout.get("failures") or not isinstance(loadout.get("totals"), dict):
        failures = loadout.get("failures") if isinstance(loadout, dict) else None
        print(f"Wowhead fallback error for {spec.spec_name}: {failures or 'unusable result'}", file=sys.stderr)
        raise ComboSkipped("wowhead fallback failed")
    return canonical_secondaries(loadout["totals"])


def reconstruct_target_context(
    spec: Any,
    goal: str,
    gear_list: list[dict[str, Any]] | None,
    talent_loadout: str | list[str] | None,
    simc_binary: Path = Path("simc"),
    wowhead_reconstruct: Callable[..., dict[str, Any]] | None = None,
    extra_recovery: list[str] | None = None,
    upgrades: LoadoutUpgrades | None = None,
) -> dict[str, Any]:
    """build_target_context's core, taking an already-selected talent export
    (or the ordered list of exports to fall back through, see
    run_with_talent_fallback). Raises ComboSkipped (never returns None) so
    callers can report why.

    `wowhead_reconstruct` (tools/wowhead_stat_engine.reconstruct_loadout's
    signature) enables the gear-only fallback, used ONLY when SimC reports
    that it cannot model the spec (any SimC failure after recovery, or no usable stats);
    None disables it.

    `upgrades` (select_loadout_upgrades) adds the recommended enchants and
    gems to the simulated items; whatever was really applied (not dropped
    by a recovery step) is counted in targetMetadata and shown on the BiS
    slots."""
    items = build_simc_items(gear_list, upgrades)
    if not items:
        raise ComboSkipped("no usable gear for this goal")
    talent_exports = [talent_loadout] if isinstance(talent_loadout, str) else list(talent_loadout or [])
    talent_exports = [export for export in talent_exports if export]
    if not talent_exports:
        raise ComboSkipped("no talent export for this goal")

    source = SIMC_TARGET_SOURCE
    try:
        stats_by_actor, _report, recovery, actor_name = run_with_talent_fallback(
            # Paper-doll run: only the stat sheet is read, so skip the
            # spec's default action list (an outdated one fails the run).
            simc_binary, spec, items, talent_exports, render_kwargs={"stat_sheet_only": True}, run_simc_fn=run_simc
        )
    except Exception as exc:  # noqa: BLE001 - fail closed; caller skips this combo
        # The skip reason stays short (it is grouped in the run summary); the
        # actual SimC message goes to the log so a failure can be diagnosed.
        print(f"SimC error for {spec.spec_name}: {format_simc_error(exc)}", file=sys.stderr)
        if wowhead_reconstruct is None:
            raise ComboSkipped(f"SimC run failed ({type(exc).__name__})") from exc
        stats = wowhead_gear_stats(spec, items, wowhead_reconstruct)
        source = WOWHEAD_TARGET_SOURCE
        recovery = ["wowhead fallback"]
    else:
        reconstructed = stats_by_actor.get(actor_name)
        stats = canonical_secondaries((reconstructed or {}).get("ratings") or {})
        # SimC ran but produced no usable secondaries (Preservation Evoker):
        # the spec is not really modelled, use the gear-only fallback.
        if sum(1 for value in stats.values() if value > 0) < 2 and wowhead_reconstruct is not None:
            print(f"SimC produced no usable stats for {spec.spec_name}; using Wowhead fallback", file=sys.stderr)
            stats = wowhead_gear_stats(spec, items, wowhead_reconstruct)
            source = WOWHEAD_TARGET_SOURCE
            recovery = ["wowhead fallback"]
        elif not reconstructed:
            raise ComboSkipped("SimC report had no stats for the actor")
    # Same rule as the addon's CountPositiveTargets (SV_ProfileRepository.lua):
    # only values > 0 count as usable targets.
    if sum(1 for value in stats.values() if value > 0) < 2:
        raise ComboSkipped("fewer than 2 usable secondary stats")

    # Everything below derives from the same last-one-wins slot map as the
    # SimC items above, so BiS slots, item count and item level describe the
    # full ClassCodex loadout (even if a weapon recovery simulated without
    # one of the weapons, see targetMetadata.recovery).
    loadout_by_slot = gear_by_simc_slot(gear_list)
    loadout = list(loadout_by_slot.values())
    # Gems/enchants a recovery step dropped were not simulated, so they are
    # neither counted nor shown.
    gems_applied = "gems dropped" not in recovery
    enchants_applied = "enchants dropped" not in recovery
    upgrades = upgrades or NO_UPGRADES
    upgrade_enchants = upgrades.enchants
    bis_slots: list[dict[str, Any]] = []
    gem_count = 0
    enchant_count = 0
    for simc_slot, entry in loadout_by_slot.items():
        item: dict[str, Any] = {"item_id": int(entry["itemId"])}
        bonus_ids = _bonus_ids(entry)
        if bonus_ids is not None:
            item["bonus_ids"] = bonus_ids
        simulated = items[simc_slot]
        # The alternatives (never simulated) only sit next to a recommended
        # gem/enchant that really was simulated.
        if gems_applied and simulated.get("gemIds"):
            item["gem_ids"] = list(simulated["gemIds"])
            gem_count += 1
            if upgrades.gem_alt is not None:
                item["gem_alt_id"] = upgrades.gem_alt
        if enchants_applied and simulated.get("enchantIds"):
            item["enchant"] = dict(upgrade_enchants[simc_slot])
            enchant_count += 1
            if simc_slot in upgrades.enchant_alts:
                item["enchant_alt"] = dict(upgrades.enchant_alts[simc_slot])
        bis_slots.append({"slot": entry["slot"], "item": item})
    # averageItemLevel only averages entries that carry an ilvl, so
    # itemLevelSlots counts exactly those (0 for real PvP gear, which has none).
    item_level_slots = sum(1 for entry in loadout if isinstance(entry.get("ilvl"), (int, float)))
    target_metadata: dict[str, Any] = {
        "lowItemReplacements": 0,
        "unresolvedLowItems": 0,
        # Items that carried the recommended gems / slots that carried an
        # enchant in the simulated loadout (auditable; 0 when none/dropped).
        "gemCount": gem_count,
        "enchantCount": enchant_count,
    }
    recovery = list(extra_recovery or []) + list(recovery)
    if recovery:
        # Auditable: this combo only succeeded after a SimC recovery step.
        target_metadata["recovery"] = recovery

    return {
        "targets": {
            "averageItemLevel": average_item_level(loadout),
            "itemCount": len(items),
            "itemLevelSlots": item_level_slots,
            "statTargets": {"context": goal, "source": source, "stats": stats},
            "targetMetadata": target_metadata,
            "sourceGoal": goal,
        },
        "bis": {"label": "ClassCodex BiS", "slots": bis_slots},
    }


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


SANITY_GUIDE_BIN = "top50"


def format_rating_sanity(data: dict[str, Any]) -> str:
    """CI-log sanity check: per spec/goal/hero-talent context, our summed
    secondary rating (statTargets) against u.gg's summed top50 rating
    (guideTargets), plus the median ratio. A ratio well below 1 means the
    simulated loadout is missing stats real players have."""
    lines = [f"Rating sanity (ours vs u.gg {SANITY_GUIDE_BIN}, summed secondary rating):"]
    ratios: list[float] = []
    for spec_key, profile in sorted((data.get("profiles") or {}).items()):
        for goal, goal_data in ((profile or {}).get("goals") or {}).items():
            for hero, context in sorted(((goal_data or {}).get("heroTalents") or {}).items()):
                targets = (context or {}).get("targets") or {}
                ours = sum(((targets.get("statTargets") or {}).get("stats") or {}).values())
                guide = sum(((targets.get("guideTargets") or {}).get(SANITY_GUIDE_BIN) or {}).values())
                where = f"{spec_key}/{goal}/{hero}"
                if guide > 0:
                    ratio = ours / guide
                    ratios.append(ratio)
                    lines.append(f"  {where}: ours {ours:.0f} vs u.gg {SANITY_GUIDE_BIN} {guide:.0f} (ratio {ratio:.2f})")
                else:
                    lines.append(f"  {where}: ours {ours:.0f} vs u.gg {SANITY_GUIDE_BIN} n/a")
    if ratios:
        ordered = sorted(ratios)
        middle = len(ordered) // 2
        median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        lines.append(f"  median ratio {median:.2f} over {len(ratios)} context(s)")
    else:
        lines.append("  no context has u.gg targets to compare")
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


def previous_context_count(path: Path, namespace_key: str) -> int | None:
    """Context count of the previously generated file at `path`, loaded
    through the hardened Lua sandbox, or None if there is no previous file.
    Raises (fail closed) if the file exists but cannot be read back."""
    if not path.exists():
        return None
    namespace = run_addon_namespace(path.read_text(encoding="utf-8"), path.name, addon_name="StatVerdict")
    data = namespace.get(namespace_key) if isinstance(namespace, dict) else None
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not define ns.{namespace_key}")
    return count_contexts(data)


# Refuse to overwrite a previous file when the new run covers fewer than
# this fraction of its spec/goal/hero-talent contexts. 0.8 tolerates the
# odd combo dropping out upstream week to week, but not a broken SimC week
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


def build_all(
    specs: dict[str, dict[str, Any]],
    simc_binary: Path,
    goals: tuple[str, ...] = ("MYTHIC_PLUS", "RAID", "PVP"),
    skips: list[SkipRecord] | None = None,
    wowhead_reconstruct: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Loops over every ClassCodex spec/goal/hero-talent combo, reconstructing
    stat targets via SimC for each, and assembles the full per-spec document.
    Skips spec keys not in the SPEC_BY_KEY catalog and combos with no usable
    data or a failed SimC run; when `skips` is given, one SkipRecord per
    skipped spec/combo is appended to it. `wowhead_reconstruct` enables the
    gear-only fallback for specs SimC cannot initialise (see
    reconstruct_target_context)."""
    skipped: list[SkipRecord] = skips if skips is not None else []
    profiles: dict[str, Any] = {}
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
        stat_targets_value = (fields.get("statTargets") or {}).get("value")

        hero_talent_keys = sorted(_hero_talent_keys(gear_value, talents_value))
        if not hero_talent_keys:
            skipped.append(SkipRecord(catalog_key, None, None, "no gear or talents data"))
        goals_out: dict[str, Any] = {}
        for goal in goals:
            hero_talents_out: dict[str, Any] = {}
            for hero_talent_key in hero_talent_keys:
                gear_list = select_goal_context(gear_value, hero_talent_key, goal)
                talent_loadout = talent_exports_from_entries(select_goal_context(talents_value, hero_talent_key, goal))
                extra_recovery: list[str] = []
                if not talent_loadout:
                    # ClassCodex has no build for this goal/hero tree: borrow
                    # the same hero tree's build from another goal (talent
                    # stat effects are small next to gear) and say so.
                    for other_goal in goals:
                        borrowed = talent_exports_from_entries(
                            select_goal_context(talents_value, hero_talent_key, other_goal)
                        )
                        if borrowed:
                            talent_loadout = borrowed
                            extra_recovery.append(f"talents borrowed from {other_goal}")
                            break
                try:
                    target_context = reconstruct_target_context(
                        spec,
                        goal,
                        gear_list,
                        talent_loadout,
                        simc_binary,
                        wowhead_reconstruct=wowhead_reconstruct,
                        extra_recovery=extra_recovery,
                        upgrades=loadout_upgrades_for(fields, hero_talent_key, goal),
                    )
                except ComboSkipped as skip:
                    skipped.append(SkipRecord(catalog_key, goal, hero_talent_key, skip.reason))
                    continue
                # u.gg's own targets, independent of how the SimC run went.
                guide_targets = guide_targets_for(stat_targets_value, hero_talent_key, goal)
                if guide_targets:
                    target_context["targets"]["guideTargets"] = guide_targets
                target_context["trinkets"] = trinkets_from_entries(
                    select_goal_context(trinkets_value, hero_talent_key, goal)
                )
                row = priority_row_from_context(
                    select_goal_context(stat_priority_value, hero_talent_key, goal),
                    GOAL_LABEL[goal],
                    hero_talent_key,
                )
                target_context["priorityProfiles"] = [row] if row else []
                hero_talents_out[hero_talent_key] = target_context
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
