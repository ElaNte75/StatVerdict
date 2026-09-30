"""How ClassCodex (the compendium that shows the Icy Veins and u.gg guides) picks the data it shows.

A port of ClassCodex's own rules, so that the addon's Guide is a 1:1 copy of what the compendium shows:

  Shared/SourceData.lua     ResolveCategory / contextChain: for a class, spec, hero tree and context, the
                            CONTEXT is tried first (the goal's own context, then the part before ':', pvp ->
                            pvp:shuffle, everything but PvP -> "all") and, inside a context, the hero tree's
                            own list before the shared ("all") list
  Sections/Stats.lua        computeVariants: the stat priority variants a view offers ("mplus": mplus, aoe,
                            damage; "raid": single-target, aoe, damage), deduplicated by their order, Mythic+
                            keeps the AoE order when there is one; the first variant is the default shown
  Shared/GearingUtils.lua   Best in Slot, trinkets, gems and enchants are read under the hero "all" (BiS under
                            the goal's context, the others under "all", or "pvp" for PvP); PvP items without
                            bonus ids borrow them by item id from u.gg's PvP gear lists

tools/classcodex_oracle.py runs ClassCodex's real Lua and tools/guide_fidelity_check.py compares the addon's
generated data with it, so a mistake in this port is reported.
"""
from __future__ import annotations

import json
from typing import Any

WILDCARD = "all"
GOAL_VIEW = {"MYTHIC_PLUS": "mplus", "RAID": "raid", "PVP": "pvp"}
VARIANT_KEYS = {
    "mplus": ("mplus", "aoe", "damage"),
    "raid": ("single-target", "aoe", "damage"),
    "pvp": ("pvp",),
}


def context_chain(context: str) -> list[str]:
    chain = [context]
    if ":" in context:
        chain.append(context.split(":", 1)[0])
    if context == "pvp":
        chain.append("pvp:shuffle")
    is_pvp = context == "pvp" or context.startswith("pvp:")
    if context != WILDCARD and not is_pvp:
        chain.append(WILDCARD)
    return chain


def resolve_category(category: Any, hero: str, context: str) -> tuple[Any, str | None, str | None]:
    """(value, hero key, context key) or (None, None, None)."""
    if not isinstance(category, dict):
        return None, None, None
    heroes = [WILDCARD] if hero == WILDCARD else [hero, WILDCARD]
    for ctx in context_chain(context):
        for hero_key in heroes:
            by_context = category.get(hero_key)
            if isinstance(by_context, dict) and by_context.get(ctx) is not None:
                return by_context[ctx], hero_key, ctx
    return None, None, None


def _has_secondary(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("secondary"))


def default_priority(stat_priority: Any, hero: str, goal: str) -> dict[str, Any] | None:
    """The stat priority ({"secondary": [[...], ...]}) ClassCodex shows by default for the goal's view."""
    view = GOAL_VIEW[goal]
    variants: list[tuple[dict[str, Any], str]] = []
    seen: set[str] = set()
    for index, key in enumerate(VARIANT_KEYS[view]):
        value, _hero, hit = resolve_category(stat_priority, hero, key)
        if not _has_secondary(value) and key != WILDCARD:
            value, _hero, hit = resolve_category(stat_priority, hero, WILDCARD)
        if not _has_secondary(value):
            continue
        # A non-first variant that resolved through the wildcard is not offered again.
        if index > 0 and hit == WILDCARD:
            continue
        signature = json.dumps(value["secondary"], sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        variants.append((value, hit))
    if view == "mplus" and any(hit == "aoe" for _value, hit in variants):
        variants = [(value, hit) for value, hit in variants if hit != WILDCARD]
    return variants[0][0] if variants else None


def bis_gear(gear: Any, goal: str) -> list[dict[str, Any]] | None:
    """ClassCodex's Best in Slot list: hero "all", the goal's context (PvP: pvp, else the shuffle bracket)."""
    value, _hero, _ctx = resolve_category(gear, WILDCARD, GOAL_VIEW[goal])
    return value if isinstance(value, list) else None


def guide_field(field: Any, goal: str) -> Any:
    """Trinkets, gems, enchants: hero "all", context "pvp" for PvP else "all" (PvP falls back to "all" for
    gems and enchants, not for trinkets)."""
    context = "pvp" if goal == "PVP" else WILDCARD
    value, _hero, _ctx = resolve_category(field, WILDCARD, context)
    return value


def guide_field_with_fallback(field: Any, goal: str) -> Any:
    value = guide_field(field, goal)
    if value is None and goal == "PVP":
        value, _hero, _ctx = resolve_category(field, WILDCARD, WILDCARD)
    return value


def pvp_bonus_lookup(specs: dict[str, dict[str, Any]]) -> dict[int, list[int]]:
    """Bonus ids by item id from the PvP gear lists of the merged build() result (u.gg's PvP gear)."""
    lookup: dict[int, list[int]] = {}
    for fields in specs.values():
        gear = (fields.get("gear") or {}).get("value")
        items = ((gear or {}).get(WILDCARD) or {}).get("pvp") if isinstance(gear, dict) else None
        for entry in items or []:
            item_id = entry.get("itemId") if isinstance(entry, dict) else None
            bonus = entry.get("bonusIDs") if isinstance(entry, dict) else None
            if item_id and isinstance(bonus, list) and bonus and item_id not in lookup:
                lookup[item_id] = [int(v) for v in bonus]
    return lookup
