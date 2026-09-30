#!/usr/bin/env python3
"""Is every Guide number in the addon an exact copy of what the guide sources publish?

Reads the raw ClassCodex sources (Icy Veins for PvE, u.gg for PvP and for stat targets; the owner
rule of 2026-09-29) and the generated addon data (StatVerdict/Data/Generated/SV_ClassCodexTargets.lua),
and compares them for every spec x goal x hero tree:

  priority   the stat order and the ties (stats the guide calls equal)
  targets    the stat targets of the three tiers (top20 / top50 / top80)
  bis        the Best in Slot item, bonus ids, for every slot (Catalyst: the tier piece is the item,
             the catalyst block supplies the max-upgrade bonus ids)
  gems       primary and (first) secondary gem
  enchants   presence and id per slot
  trinkets   the ranked list (item, tier, bonus ids)

It reads the raw data its own way (it does not use the selection code of the pipeline), so a wrong
rule in the pipeline shows up here. The source of a value is chosen as: PvE goals Icy Veins, else u.gg;
PvP goal u.gg, else Icy Veins; stat targets u.gg only. Within a source: the hero tree's own list
beats the shared one, and the goal's list ("mplus", "raid", "pvp") beats "all".

  python tools/guide_fidelity_check.py [--out docs/guide-fidelity]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from tools.classcodex_build import _load_source_root
    from tools.classcodex_fetch import fetch_all
    from tools.classcodex_lua_sandbox import new_sandboxed_runtime, to_python
    from tools.classcodex_oracle import Oracle, fetch_classcodex_files
except ModuleNotFoundError:
    from classcodex_build import _load_source_root
    from classcodex_fetch import fetch_all
    from classcodex_lua_sandbox import new_sandboxed_runtime, to_python
    from classcodex_oracle import Oracle, fetch_classcodex_files

GOAL_CONTEXT = {"MYTHIC_PLUS": "mplus", "RAID": "raid", "PVP": "pvp"}
GOAL_SOURCES = {"MYTHIC_PLUS": ("icyveins", "ugg"), "RAID": ("icyveins", "ugg"), "PVP": ("ugg", "icyveins")}
STAT_NAME = {"crit": "critical_strike", "haste": "haste", "mastery": "mastery", "versatility": "versatility"}
STATS = tuple(STAT_NAME.values())
CATEGORIES = ("priority", "targets", "bis", "gems", "enchants", "trinkets", "priorityNotes", "trinketsNotScored")
SLOT_NAMES = {
    "Head", "Neck", "Shoulders", "Back", "Chest", "Wrist", "Hands", "Waist", "Legs", "Feet",
    "Finger 1", "Finger 2", "Trinket 1", "Trinket 2", "Main Hand", "Off Hand",
}


def load_generated(path: Path) -> dict[str, Any]:
    runtime = new_sandboxed_runtime()
    namespace = runtime.table()
    load = runtime.eval("function(src, ns) local fn = assert(load(src)); return fn('StatVerdict', ns) end")
    load(path.read_text(encoding="utf-8"), namespace)
    return to_python(namespace)["ClassCodexTargets"]


def context_chain(context: str) -> list[str]:
    """ClassCodex's own chain (Shared/SourceData.lua contextChain): the context, the part before ':',
    generic pvp falls back to the shuffle bracket, and everything but PvP falls back to "all"."""
    chain = [context]
    if ":" in context:
        chain.append(context.split(":", 1)[0])
    if context == "pvp":
        chain.append("pvp:shuffle")
    is_pvp = context == "pvp" or context.startswith("pvp:")
    if context != "all" and not is_pvp:
        chain.append("all")
    return chain


def resolve_category(category: Any, hero: str, context: str) -> tuple[Any, str | None, str | None]:
    """ClassCodex's ResolveCategory: the CONTEXT is the outer loop and the hero tree the inner one
    (the hero's own list, then the shared "all" list), so a goal-specific shared list beats the hero's
    general list."""
    if not isinstance(category, dict):
        return None, None, None
    heroes = ["all"] if hero == "all" else [hero, "all"]
    for ctx in context_chain(context):
        for h in heroes:
            by_context = category.get(h)
            if isinstance(by_context, dict) and by_context.get(ctx) is not None:
                return by_context[ctx], h, ctx
    return None, None, None


def source_field(roots: dict, source: str, cls: str, spec: str, field: str):
    return (((roots.get(source) or {}).get(cls) or {}).get(spec) or {}).get(field)


def raw_value(root: dict | None, cls: str, spec: str, field: str, hero: str, context: str) -> Any:
    return resolve_category(((root or {}).get(cls) or {}).get(spec, {}).get(field), hero, context)[0]


def pick_context(roots: dict, cls: str, spec: str, field: str, hero: str):
    """Like pick, but the general ("all") context, for the PvP fallback of gems and enchants."""
    for source in ("ugg", "icyveins"):
        value = resolve_category(((roots.get(source) or {}).get(cls) or {}).get(spec, {}).get(field), hero, "all")[0]
        if value is not None:
            return value, source
    return None, None


def pick(roots: dict, cls: str, spec: str, field: str, hero: str, goal: str, only: tuple[str, ...] | None = None):
    """The first source (owner rule) that has a value for the goal's context."""
    context = GOAL_CONTEXT[goal] if field == "gear" else ("pvp" if goal == "PVP" else "all")
    for source in only or GOAL_SOURCES[goal]:
        value = raw_value(roots.get(source), cls, spec, field, hero, context)
        if value is not None:
            return value, source
    return None, None


DISPLAY_STAT = {"Critical Strike": "critical_strike", "Haste": "haste", "Mastery": "mastery", "Versatility": "versatility"}
VIEW = {"MYTHIC_PLUS": "mplus", "RAID": "raid", "PVP": "pvp"}


def stat_groups(tiers: Any) -> tuple[list[str], list[list[str]], list[str]] | None:
    """(order, ties, notes) of ClassCodex tiers like [["Mastery", "Haste"], ["Critical Strike"], ...].
    An entry can carry a breakpoint ("Haste to 18%") and a stat can come twice; the first place counts for
    the order, and such entries are returned as notes for a human to look at."""
    if not isinstance(tiers, list):
        return None
    order: list[str] = []
    ties: list[list[str]] = []
    notes: list[str] = []
    for tier in tiers:
        names = []
        for display in tier:
            stat, note = display, ""
            for label in DISPLAY_STAT:
                if display == label or display.startswith(label + " "):
                    stat, note = label, display[len(label):].strip()
                    break
            if note:
                notes.append(display)
            name = DISPLAY_STAT.get(stat, stat)
            if name in order or name in names:
                notes.append(f"{name} listed again")
                continue
            names.append(name)
        order += names
        if len(names) > 1:
            ties.append(names)
    return order, ties, notes


def spec_token_to_key(cls: str, spec: str) -> str:
    return f"{cls}_{spec}".upper().replace("-", "_")


def pvp_bonus_lookup(roots: dict) -> dict[int, list[int]]:
    """ClassCodex (GearingUtils PvpItemBonusIds): PvP items without bonus ids borrow them, by item id, from
    the first u.gg PvP gear list that has them."""
    lookup: dict[int, list[int]] = {}
    for specs in (roots.get("ugg") or {}).values():
        for data in specs.values():
            items = (((data.get("gear") or {}).get("all")) or {}).get("pvp")
            for entry in items or []:
                if isinstance(entry, dict) and entry.get("itemId") and entry.get("bonusIDs") and entry["itemId"] not in lookup:
                    lookup[entry["itemId"]] = list(entry["bonusIDs"])
    return lookup


def check_context(oracle, roots, cls, spec, goal, hero, generated, out: list[dict[str, Any]]) -> None:
    where = f"{spec_token_to_key(cls, spec)} / {goal} / {hero}"

    def diff(category: str, what: str, expected: Any, actual: Any) -> None:
        out.append({"category": category, "where": where, "what": what, "expected": expected, "actual": actual})

    # priority ------------------------------------------------------------------------------
    value, source = None, None
    for candidate in GOAL_SOURCES[goal]:
        tiers, _hit, _n = oracle.default_priority(cls.upper(), spec, VIEW[goal], candidate, hero)
        if tiers:
            value, source = tiers, candidate
            break
    expected = stat_groups(value)
    profiles = [p for p in (generated.get("priorityProfiles") or []) if isinstance(p, dict)]
    profile = profiles[0] if profiles else None
    if expected is None:
        if profile:
            diff("priority", "generated has a priority the guide does not", None, profile.get("order"))
    elif not profile:
        diff("priority", "generated has no priority", expected[0], None)
    else:
        if list(profile.get("order") or []) != expected[0]:
            diff("priority", f"order ({source})", expected[0], profile.get("order"))
        if [list(t) for t in (profile.get("tiers") or [])] != expected[1]:
            diff("priority", f"ties ({source})", expected[1], [list(t) for t in (profile.get("tiers") or [])])
        for note in expected[2]:
            out.append({"category": "priorityNotes", "where": where, "what": note, "expected": None, "actual": None})

    # targets (ClassCodex: the source's own, else u.gg) -------------------------------------
    guide_targets = ((generated.get("targets") or {}).get("guideTargets")) or {}
    wanted = None
    for candidate in GOAL_SOURCES[goal]:
        wanted = oracle.targets(cls.upper(), spec, VIEW[goal], candidate, hero)
        if wanted:
            break
    if wanted:
        for tier in ("top20", "top50", "top80"):
            want = {STAT_NAME.get(k, k): float(v) for k, v in (wanted.get(tier) or {}).items()}
            have = {k: float(v) for k, v in (guide_targets.get(tier) or {}).items()}
            if want != have:
                diff("targets", tier, want, have)
    elif guide_targets:
        diff("targets", "generated has targets the guide does not", None, sorted(guide_targets))

    # best in slot --------------------------------------------------------------------------
    value, source = pick(roots, cls, spec, "gear", "all", goal)  # ClassCodex reads BiS gear under hero "all"
    want_slots: dict[str, dict[str, Any]] = {}
    for entry in value or []:
        if isinstance(entry, dict) and entry.get("slot") in SLOT_NAMES:
            catalyst = entry.get("catalyst") if isinstance(entry.get("catalyst"), dict) else None
            bonus = (catalyst or {}).get("bonusIDs") if catalyst else entry.get("bonusIDs")
            if not bonus and goal == "PVP":
                bonus = PVP_BONUS.get(entry.get("itemId"))
            want_slots[entry["slot"]] = {"item_id": entry.get("itemId"), "bonus_ids": list(bonus or [])}
    bis = generated.get("bis") or {}
    have_slots = {
        s.get("slot"): {"item_id": (s.get("item") or {}).get("item_id"), "bonus_ids": list((s.get("item") or {}).get("bonus_ids") or [])}
        for s in (bis.get("slots") or []) if isinstance(s, dict)
    }
    for slot in sorted(set(want_slots) | set(have_slots)):
        if want_slots.get(slot) != have_slots.get(slot):
            diff("bis", slot, want_slots.get(slot), have_slots.get(slot))

    # gems ----------------------------------------------------------------------------------
    value, source = pick(roots, cls, spec, "gems", "all", goal)
    if value is None and goal == "PVP":
        value, source = pick_context(roots, cls, spec, "gems", "all")
    entry = value[0] if isinstance(value, list) and value and isinstance(value[0], dict) else None
    if entry:
        secondary = entry.get("secondary")
        want = {"primary": entry.get("primary"), "secondary": secondary[0] if isinstance(secondary, list) and secondary else secondary}
        have = {"primary": (bis.get("gems") or {}).get("primary"), "secondary": (bis.get("gems") or {}).get("secondary")}
        if want != have:
            diff("gems", "primary/secondary", want, have)

    # enchants ------------------------------------------------------------------------------
    value, source = pick(roots, cls, spec, "enchants", "all", goal)
    if value is None and goal == "PVP":
        value, source = pick_context(roots, cls, spec, "enchants", "all")
    have_enchants = {
        s.get("slot"): (s.get("item") or {}).get("enchant")
        for s in (bis.get("slots") or []) if isinstance(s, dict)
    }
    for slot, options in (value or {}).items():
        first = options[0] if isinstance(options, list) and options else None
        ids = {v for k, v in (first or {}).items() if k in ("id", "itemId", "item_id", "spellId", "spell_id") and v is not None}
        have = have_enchants.get(slot)
        if first is None:
            continue
        if not isinstance(have, dict):
            diff("enchants", slot, sorted(ids), None)
        elif not ids & {have.get("id"), have.get("item_id"), have.get("spell_id")}:
            diff("enchants", slot, sorted(ids), have)

    # trinkets ------------------------------------------------------------------------------
    value, source = pick(roots, cls, spec, "trinkets", "all", goal)
    entries = [e for e in (value or []) if isinstance(e, dict)]

    def shaped(entry):
        bonus = entry.get("bonusIDs") or (PVP_BONUS.get(entry.get("itemId")) if goal == "PVP" else None)
        return (entry.get("itemId"), entry.get("tier") or "S", list(bonus or []))

    want_list = [shaped(e) for e in entries if (e.get("tier") or "S") in ("S", "A", "B", "C", "D")]
    not_scored = [shaped(e) for e in entries if (e.get("tier") or "S") not in ("S", "A", "B", "C", "D")]
    have_list = [
        (e.get("item_id"), e.get("tier"), list(e.get("bonus_ids") or []))
        for e in (generated.get("trinkets") or []) if isinstance(e, dict)
    ]
    if want_list != have_list:
        diff("trinkets", "ranked list", want_list, have_list)
    for item_id, tier, _bonus in not_scored:
        out.append({"category": "trinketsNotScored", "where": where, "what": f"item {item_id} has tier {tier}", "expected": None, "actual": None})


PVP_BONUS: dict[int, list[int]] = {}


def run(generated_path: Path) -> dict[str, Any]:
    fetched = fetch_all()
    roots = {
        "ugg": _load_source_root(fetched.sources, "db_ugg", "ugg"),
        "icyveins": _load_source_root(fetched.sources, "db_icyveins", "icyveins"),
    }
    generated = load_generated(generated_path)
    PVP_BONUS.update(pvp_bonus_lookup(roots))
    oracle = Oracle(fetched.sources, fetch_classcodex_files())
    by_key = {}
    for cls, specs in (roots["icyveins"] or {}).items():
        for spec in specs:
            by_key[spec_token_to_key(cls, spec)] = (cls, spec)
    for cls, specs in (roots["ugg"] or {}).items():
        for spec in specs:
            by_key.setdefault(spec_token_to_key(cls, spec), (cls, spec))
    differences: list[dict[str, Any]] = []
    contexts = 0
    not_in_addon: list[str] = []
    for key, profile in sorted((generated.get("profiles") or {}).items()):
        if key not in by_key:
            not_in_addon.append(f"{key}: in the addon but not in the raw sources")
            continue
        cls, spec = by_key[key]
        for goal, goal_doc in (profile.get("goals") or {}).items():
            for hero, doc in (goal_doc.get("heroTalents") or {}).items():
                contexts += 1
                check_context(oracle, roots, cls, spec, goal, hero, doc, differences)
    missing = sorted(key for key in by_key if key not in (generated.get("profiles") or {}))
    return {
        "rawBuild": fetched.build_id,
        "generatedBuild": generated.get("buildId"),
        "contexts": contexts,
        "specsInRawNotInAddon": missing,
        "notes": not_in_addon,
        "differences": differences,
    }


def render_md(result: dict[str, Any]) -> str:
    counts = {c: 0 for c in CATEGORIES}
    contexts_with = {c: set() for c in CATEGORIES}
    for d in result["differences"]:
        counts[d["category"]] += 1
        contexts_with[d["category"]].add(d["where"])
    lines = [
        "# Guide fidelity: addon data vs the guide sources",
        "",
        f"Raw build `{result['rawBuild']}`, addon data build `{result['generatedBuild']}`, "
        f"{result['contexts']} contexts (spec x goal x hero tree).",
        "",
        "| What | Differences | Contexts affected |", "|---|---|---|",
    ]
    for category in CATEGORIES:
        lines.append(f"| {category} | {counts[category]} | {len(contexts_with[category])} |")
    lines += ["", f"Specs in the raw sources but not in the addon: {', '.join(result['specsInRawNotInAddon']) or 'none'}", ""]
    for category in CATEGORIES:
        rows = [d for d in result["differences"] if d["category"] == category]
        if not rows:
            continue
        lines += [f"## {category} ({len(rows)})", ""]
        for d in rows[:40]:
            lines.append(f"- {d['where']} - {d['what']}: expected `{json.dumps(d['expected'])}`, addon has `{json.dumps(d['actual'])}`")
        if len(rows) > 40:
            lines.append(f"- ... and {len(rows) - 40} more (see the json)")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", type=Path, default=Path("StatVerdict/Data/Generated/SV_ClassCodexTargets.lua"))
    parser.add_argument("--out", type=Path, default=Path("docs/guide-fidelity"))
    args = parser.parse_args(argv)
    result = run(args.generated)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.with_suffix(".json").write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    args.out.with_suffix(".md").write_text(render_md(result), encoding="utf-8")
    print(f"{result['contexts']} contexts, {len(result['differences'])} differences")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
