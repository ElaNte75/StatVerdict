"""Turns the raw fetched ClassCodex Lua sources (classcodex_fetch.FetchResult)
into StatVerdict's own clean, class-agnostic JSON shape.

Deliberately excludes `tierRank` (u.gg's spec popularity/parse-rank
numbers): a different concern (spec viability) from what this pipeline was
asked to build (stat priority, best-in-slot gear, ranked trinkets, PvP).

Both sources share the same shape once you reach a spec: a dict keyed by
hero talent (or "all" when the field doesn't vary by hero talent), then by
content context ("all"/"mplus"/"raid"/"single-target"/"aoe"/"pvp"/...).

Owner rule (2026-09-29): everything PvE (Mythic+, Raid) follows the Icy
Veins guide; PvP follows u.gg. GUIDE_FIELDS are merged per hero tree by
_merge_guide_field: Icy Veins' contexts are kept, u.gg's `pvp` context
replaces Icy Veins' one, and u.gg fills hero trees (or whole specs) Icy
Veins has no PvE data for. `statTargets` (u.gg's top20/top50/top80 stat
ratings) comes from u.gg ONLY (UGG_ONLY_FIELDS).

Every merged value records its base source (`source`) and, per hero tree
and context, which source each piece came from (`origins`), so a future
audit does not have to re-derive this.

Icy Veins' enchant ids are enchant SCROLL item ids, not SimC enchant ids;
`enchantLookup` (built from every u.gg enchant entry plus ClassCodex's
db_gamedata recipes) lets tools/classcodex_targets.py translate them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from tools.classcodex_lua_sandbox import run_addon_namespace, run_plain_global
except ModuleNotFoundError:
    from classcodex_lua_sandbox import run_addon_namespace, run_plain_global

CLASS_FOLDERS = (
    "DEATHKNIGHT",
    "DEMONHUNTER",
    "DRUID",
    "EVOKER",
    "HUNTER",
    "MAGE",
    "MONK",
    "PALADIN",
    "PRIEST",
    "ROGUE",
    "SHAMAN",
    "WARLOCK",
    "WARRIOR",
)

# Fields this pipeline extracts per spec. See module docstring for what is
# deliberately left out (tierRank). `talents` is required by
# tools/classcodex_targets.py and tools/classcodex_weights.py: every SimC run
# needs a real talent export string, so without it neither pipeline can
# produce a single profile.
EXTRACTED_FIELDS = ("statPriority", "trinkets", "gear", "talents", "statTargets", "gems", "enchants")

# Fields read from u.gg alone (see module docstring): if u.gg lacks one, it is
# omitted (Icy Veins has no such field).
UGG_ONLY_FIELDS = frozenset({"statTargets"})

# Fields merged by the PvE-from-Icy-Veins / PvP-from-u.gg rule.
GUIDE_FIELDS = frozenset({"statPriority", "trinkets", "gear", "talents", "gems", "enchants"})

SOURCE_PRIORITY = ("ugg", "icyveins")
ALL_HERO_KEY = "all"
PVP_CONTEXT_KEY = "pvp"

# Extra per-spec field (not a ClassCodex field): the enchant translation
# tables, see build_enchant_lookup.
ENCHANT_LOOKUP_FIELD = "enchantLookup"


@dataclass
class SourceLoadFailure(Exception):
    source: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.source}: {self.reason}"


@dataclass
class BuildResult:
    build_id: str
    published_at: str
    specs: dict[str, dict] = field(default_factory=dict)
    load_failures: list[SourceLoadFailure] = field(default_factory=list)


def _load_source_root(sources: dict[str, str], key: str, global_key: str) -> dict | None:
    """Returns ClassCodexSource[global_key]["data"], or None if that source
    failed to load entirely (fail-closed: the caller falls back to whatever
    other source is still available for each spec/field individually)."""
    raw = sources.get(key)
    if raw is None:
        return None
    parsed = run_plain_global(raw, f"{key}.lua", "ClassCodexSource")
    root = parsed.get(global_key) if isinstance(parsed, dict) else None
    data = root.get("data") if isinstance(root, dict) else None
    return data if isinstance(data, dict) else None


def _merge_field(per_source: dict[str, Any]) -> tuple[Any, str] | None:
    """per_source maps source name -> that source's value for one field of
    one spec (or None if absent). Picks the first non-empty value in
    SOURCE_PRIORITY order."""
    for source_name in SOURCE_PRIORITY:
        value = per_source.get(source_name)
        if value:
            return value, source_name
    return None


def _has_pve_content(contexts: Any) -> bool:
    """True when a hero tree's {context: value} dict holds any non-empty
    context other than "pvp"."""
    return isinstance(contexts, dict) and any(
        value for key, value in contexts.items() if key != PVP_CONTEXT_KEY
    )


def _merge_guide_field(per_source: dict[str, Any]) -> tuple[Any, str, dict[str, dict[str, str]]] | None:
    """Owner rule: everything PvE (Mythic+, Raid) follows the Icy Veins guide;
    everything PvP follows u.gg. Returns (merged value, base source,
    origins) where origins is {hero: {context: "icyveins"|"ugg"}}.

    Per hero tree, in the same {hero: {context: payload}} shape the
    consumers read (tools/classcodex_targets.select_goal_context):
      - Icy Veins' contexts are kept as-is. Its hero "all" entry applies to
        every hero tree through select_goal_context's hero fallback.
      - u.gg's "pvp" context replaces Icy Veins' one (Icy Veins' is used
        only when u.gg has none).
      - When Icy Veins covers a hero tree for PvE (a non-pvp context under
        that hero or under hero "all"), u.gg's PvE contexts (mplus, raid,
        single-target, aoe, ...) are dropped: they would otherwise come
        first in select_goal_context's fallback chains and outrank the
        guide.
      - A hero tree Icy Veins has no PvE data for gets u.gg's contexts.
    A spec/field Icy Veins lacks entirely is u.gg's value as-is."""
    icy = per_source.get("icyveins")
    ugg = per_source.get("ugg")
    if not (isinstance(icy, dict) and icy):
        return _with_flat_origins(_merge_field(per_source))
    merged: dict[str, dict[str, Any]] = {}
    origins: dict[str, dict[str, str]] = {}
    for hero_key, contexts in icy.items():
        if isinstance(contexts, dict) and contexts:
            merged[hero_key] = dict(contexts)
            origins[hero_key] = {context: "icyveins" for context in contexts}
    spec_wide_pve = _has_pve_content(icy.get(ALL_HERO_KEY))

    if isinstance(ugg, dict):
        for hero_key, contexts in ugg.items():
            if not isinstance(contexts, dict):
                continue
            icy_covers = spec_wide_pve or _has_pve_content(icy.get(hero_key))
            for context, value in contexts.items():
                if context != PVP_CONTEXT_KEY and icy_covers:
                    continue
                if not value:
                    continue
                merged.setdefault(hero_key, {})[context] = value
                origins.setdefault(hero_key, {})[context] = "ugg"
    if not merged:
        return _with_flat_origins(_merge_field(per_source))
    return merged, "icyveins", origins


def _with_flat_origins(merged: tuple[Any, str] | None) -> tuple[Any, str, dict[str, dict[str, str]]] | None:
    """A single-source value: every hero/context came from that source."""
    if merged is None:
        return None
    value, source = merged
    origins: dict[str, dict[str, str]] = {}
    if isinstance(value, dict):
        for hero_key, contexts in value.items():
            if isinstance(contexts, dict):
                origins[hero_key] = {context: source for context in contexts}
    return value, source, origins


def _int_key(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def build_enchant_lookup(ugg_root: dict | None, game_data: dict | None) -> dict[str, dict[int, Any]]:
    """Translation tables for enchant ids, from every u.gg enchant entry
    that carries the real enchant id (PvE entries: {id=<enchant id>,
    itemId=<scroll item id>, spellId=<enchant spell id>}, weapon runes:
    {id, spellId}) and from ClassCodex's db_gamedata `recipes`
    ({[spellId] = scroll itemId}):
      byItem:  scroll item id -> {"id", "spell_id"?, "item_id"}
      bySpell: enchant spell id -> {"id", "spell_id", "item_id"?}
      recipeSpellByItem: scroll item id -> enchant spell id (inverted recipes)
    Enchants are shared across specs, so the tables span every spec."""
    by_item: dict[int, dict[str, int]] = {}
    by_spell: dict[int, dict[str, int]] = {}
    if isinstance(ugg_root, dict):
        for class_data in ugg_root.values():
            if not isinstance(class_data, dict):
                continue
            for spec_data in class_data.values():
                if isinstance(spec_data, dict):
                    collect_real_enchants(spec_data.get("enchants"), by_item, by_spell)

    recipe_spell_by_item: dict[int, int] = {}
    recipes = game_data.get("recipes") if isinstance(game_data, dict) else None
    if isinstance(recipes, dict):
        for spell_id, item_id in recipes.items():
            spell_key, item_key = _int_key(spell_id), _int_key(item_id)
            if spell_key is not None and item_key is not None:
                recipe_spell_by_item.setdefault(item_key, spell_key)
    return {"byItem": by_item, "bySpell": by_spell, "recipeSpellByItem": recipe_spell_by_item}


def collect_real_enchants(
    enchants_value: Any, by_item: dict[int, dict[str, int]], by_spell: dict[int, dict[str, int]]
) -> None:
    """Adds every enchant entry of `enchants_value` (any nesting) whose `id`
    is a real enchant id -- it differs from the entry's itemId or spellId --
    to by_item (keyed by scroll item id) and by_spell (keyed by spell id).
    The first entry seen for a key wins."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            enchant_id = _int_key(node.get("id"))
            item_id = _int_key(node.get("itemId"))
            spell_id = _int_key(node.get("spellId"))
            is_real = enchant_id is not None and (
                (item_id is not None and item_id != enchant_id) or (spell_id is not None and spell_id != enchant_id)
            )
            if is_real:
                found = {"id": enchant_id}
                if spell_id is not None:
                    found["spell_id"] = spell_id
                if item_id is not None:
                    found["item_id"] = item_id
                    by_item.setdefault(item_id, found)
                if spell_id is not None:
                    by_spell.setdefault(spell_id, found)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(enchants_value)


def _load_game_data(sources: dict[str, str]) -> dict | None:
    raw = sources.get("db_gamedata")
    if raw is None:
        return None
    parsed = run_plain_global(raw, "db_gamedata.lua", "ClassCodexGameData")
    return parsed if isinstance(parsed, dict) else None


def build(fetch_sources: dict[str, str]) -> dict[str, dict]:
    """Returns {spec_key: {field: {"value": ..., "source": "ugg"|"icyveins",
    "origins": {hero: {context: source}}}}} for every class/spec found in
    either source, plus the shared ENCHANT_LOOKUP_FIELD
    ({"value": build_enchant_lookup(...), "source": "ugg+gamedata"}) on every
    spec. spec_key is "<CLASS>_<spec>"
    using the spec token exactly as the upstream data uses it (lowercase,
    hyphenated where the source hyphenates it -- StatVerdict's own spec-key
    mapping happens on the addon side, not here)."""
    roots: dict[str, dict | None] = {
        "ugg": _load_source_root(fetch_sources, "db_ugg", "ugg"),
        "icyveins": _load_source_root(fetch_sources, "db_icyveins", "icyveins"),
    }
    enchant_lookup = build_enchant_lookup(roots["ugg"], _load_game_data(fetch_sources))

    specs: dict[str, dict] = {}
    for class_folder in CLASS_FOLDERS:
        spec_keys: set[str] = set()
        for source_name, root in roots.items():
            class_data = root.get(class_folder) if isinstance(root, dict) else None
            if isinstance(class_data, dict):
                spec_keys.update(class_data.keys())

        for spec_token in spec_keys:
            spec_key = f"{class_folder}_{spec_token}"
            spec_out: dict[str, Any] = {}
            for field_name in EXTRACTED_FIELDS:
                per_source = {}
                for source_name, root in roots.items():
                    class_data = root.get(class_folder) if isinstance(root, dict) else None
                    spec_data = class_data.get(spec_token) if isinstance(class_data, dict) else None
                    per_source[source_name] = spec_data.get(field_name) if isinstance(spec_data, dict) else None
                if field_name in UGG_ONLY_FIELDS:
                    merged = _with_flat_origins(_merge_field({"ugg": per_source.get("ugg")}))
                elif field_name in GUIDE_FIELDS:
                    merged = _merge_guide_field(per_source)
                else:
                    merged = _with_flat_origins(_merge_field(per_source))
                if merged is not None:
                    value, source_name, origins = merged
                    spec_out[field_name] = {"value": value, "source": source_name, "origins": origins}
            if spec_out:
                spec_out[ENCHANT_LOOKUP_FIELD] = {"value": enchant_lookup, "source": "ugg+gamedata"}
                specs[spec_key] = spec_out

    return specs


def build_stat_dr(stat_dr_source: str) -> dict:
    """Loads Shared/StatDR.lua's namespace as-is. This is a live calculation
    module (it takes a player's *current* in-game stat values as input), not
    static reference data -- kept separate from `build()`'s per-spec output
    so a future decision to vendor it into the addon (instead of, or as well
    as, extracting numbers from it here) is not pre-empted by this function's
    shape."""
    return run_addon_namespace(stat_dr_source, "StatDR.lua", addon_name="ClassCodex")
