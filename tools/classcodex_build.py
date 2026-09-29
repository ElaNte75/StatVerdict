"""Turns the raw fetched ClassCodex Lua sources (classcodex_fetch.FetchResult)
into StatVerdict's own clean, class-agnostic JSON shape.

Deliberately excludes `tierRank` (u.gg's spec popularity/parse-rank
numbers): a different concern (spec viability) from what this pipeline was
asked to build (stat priority, best-in-slot gear, ranked trinkets, PvP).

`statTargets` (u.gg's per-hero/context top20/top50/top80 stat ratings),
`gems` and `enchants` are taken from u.gg ONLY (UGG_ONLY_FIELDS): Icy Veins'
versions have different shapes (its enchant `id` is an item id, not a SimC
enchant id), so they are never used as a fallback.

Both sources share the same shape once you reach a spec: a dict keyed by
hero talent (or "all" when the field doesn't vary by hero talent), then by
content context ("all"/"single-target"/"aoe"/"pvp"/...). u.gg's version is
consistently the more granular of the two (hero-talent-specific where
IcyVeins only has "all"), so it is preferred whenever it has data for a
given spec/field; IcyVeins fills in anything u.gg is missing. Every merged
value records which source it actually came from, so a future audit does
not have to re-derive this.
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
# omitted rather than filled from Icy Veins' differently shaped data.
UGG_ONLY_FIELDS = frozenset({"statTargets", "gems", "enchants"})

SOURCE_PRIORITY = ("ugg", "icyveins")
ALL_HERO_KEY = "all"


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


def _merge_stat_priority(per_source: dict[str, Any]) -> tuple[Any, str] | None:
    """The stat priority follows the Icy Veins guide (the project owner's
    reference, and what the official ClassCodex addon shows on its Icy Veins
    tab). Icy Veins only publishes one PvE list per hero tree (context "all"),
    so per hero tree: Icy Veins' list is kept as-is; u.gg's PvP list (the only
    PvP-specific one) is added under "pvp"; hero trees Icy Veins does not
    cover fall back to u.gg's full entry. u.gg's single-target/aoe lists are
    dropped whenever Icy Veins covers the hero tree, so they cannot outrank
    the guide."""
    icy = per_source.get("icyveins")
    ugg = per_source.get("ugg")
    if not (isinstance(icy, dict) and icy):
        return _merge_field(per_source)
    merged: dict[str, Any] = {}
    for hero_key, contexts in icy.items():
        if isinstance(contexts, dict) and contexts:
            merged[hero_key] = dict(contexts)
    spec_wide = icy.get(ALL_HERO_KEY) if isinstance(icy.get(ALL_HERO_KEY), dict) else {}

    def icy_has_pvp(hero_key: str) -> bool:
        own = icy.get(hero_key)
        return bool((isinstance(own, dict) and own.get("pvp")) or spec_wide.get("pvp"))

    if isinstance(ugg, dict):
        for hero_key, contexts in ugg.items():
            if not isinstance(contexts, dict):
                continue
            if hero_key in merged or spec_wide:
                # Icy Veins covers this hero tree (by name or through its
                # spec-wide list): u.gg contributes only its PvP list, and
                # only when Icy Veins has no PvP list of its own.
                if contexts.get("pvp") and not icy_has_pvp(hero_key):
                    merged.setdefault(hero_key, {})["pvp"] = contexts["pvp"]
            else:
                merged[hero_key] = dict(contexts)
    if not merged:
        return _merge_field(per_source)
    return merged, "icyveins"


def build(fetch_sources: dict[str, str]) -> dict[str, dict]:
    """Returns {spec_key: {field: {"value": ..., "source": "ugg"|"icyveins"}}}
    for every class/spec found in either source. spec_key is "<CLASS>_<spec>"
    using the spec token exactly as the upstream data uses it (lowercase,
    hyphenated where the source hyphenates it -- StatVerdict's own spec-key
    mapping happens on the addon side, not here)."""
    roots: dict[str, dict | None] = {
        "ugg": _load_source_root(fetch_sources, "db_ugg", "ugg"),
        "icyveins": _load_source_root(fetch_sources, "db_icyveins", "icyveins"),
    }

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
                    merged = _merge_field({"ugg": per_source.get("ugg")})
                elif field_name == "statPriority":
                    merged = _merge_stat_priority(per_source)
                else:
                    merged = _merge_field(per_source)
                if merged is not None:
                    value, source_name = merged
                    spec_out[field_name] = {"value": value, "source": source_name}
            if spec_out:
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
