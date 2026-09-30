"""ClassCodex's own code as the ground truth for what the Guide should show.

The Guide of the addon must be a 1:1 copy of what the ClassCodex compendium (Icy Veins and u.gg) shows
for a class, spec, hero tree and content. Instead of re-implementing how ClassCodex picks its data, this
module downloads ClassCodex's own Lua (the same build as the data, checksum verified), loads its resolver
files in an embedded Lua with the real data and asks them:

  stat priority   ns.GetStatPriority, and the variant rule of Sections/Stats.lua (computeVariants: the
                  variants offered for a view, deduplicated, Mythic+ keeps the AoE order when there is one;
                  the first variant is what the compendium shows by default)
  stat targets    ns.GetStatTargets, for each of the three bins

Nothing is guessed: if ClassCodex changes its rule, the oracle changes with it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import lupa

try:
    from tools.classcodex_fetch import BASE_URL, GAME_VERSION_ID, _get, get_current_build, get_manifest
    from tools.classcodex_lua_sandbox import to_python
except ModuleNotFoundError:
    from classcodex_fetch import BASE_URL, GAME_VERSION_ID, _get, get_current_build, get_manifest
    from classcodex_lua_sandbox import to_python

ORACLE_FILES = ("Shared/SourceData.lua", "Shared/StatTargets.lua")
# The variants each view offers, in ClassCodex's order (Sections/Stats.lua CT_VARIANTS).
VARIANT_KEYS = {
    "mplus": ("mplus", "aoe", "damage"),
    "raid": ("single-target", "aoe", "damage"),
    "pvp": ("pvp",),
}
BINS = ("top20", "top50", "top80")


def fetch_classcodex_files(paths: tuple[str, ...] = ORACLE_FILES) -> dict[str, str]:
    config = get_current_build()
    manifest = get_manifest(config["manifestUrl"])
    by_path = {entry["path"]: entry for entry in manifest["files"]}
    out: dict[str, str] = {}
    for path in paths:
        full = f"ClassCodex/{path}"
        entry = by_path[full]
        raw = _get(f"{BASE_URL}/builds/{GAME_VERSION_ID}/{config['buildId']}/{full}")
        if entry.get("sha256") and hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"{full} checksum mismatch")
        out[path] = raw.decode("utf-8")
    return out


class Oracle:
    def __init__(self, sources: dict[str, str], code: dict[str, str]):
        self.runtime = lupa.LuaRuntime(unpack_returned_tuples=True)
        self.runtime.execute(sources["db_icyveins"])
        self.runtime.execute(sources["db_ugg"])
        self.runtime.execute("ClassCodexDB = { statTargetBin = 'top20' }")
        self.ns = self.runtime.table()
        load = self.runtime.eval("function(path, src, ns) local fn = assert(load(src, path)); return fn('ClassCodex', ns) end")
        for path in ORACLE_FILES:
            load(path, code[path], self.ns)

    def _priority(self, cls: str, spec: str, key: str, source: str, hero: str):
        result = self.ns.GetStatPriority(cls, spec, key, source, hero)
        if not result:
            return None, None
        tiers, hit = result
        return to_python(tiers), hit

    def default_priority(self, cls: str, spec: str, view: str, source: str, hero: str):
        """(tiers, hit context, variants offered) of the first variant ClassCodex shows for the view."""
        variants: list[tuple[Any, str]] = []
        seen: set[str] = set()
        for index, key in enumerate(VARIANT_KEYS[view]):
            tiers, hit = self._priority(cls, spec, key, source, hero)
            # A non-first variant that resolved through the wildcard is not offered again.
            if tiers and not (index > 0 and hit == "all"):
                signature = json.dumps(tiers)
                if signature not in seen:
                    seen.add(signature)
                    variants.append((tiers, hit))
        if view == "mplus" and any(hit == "aoe" for _t, hit in variants):
            variants = [(t, h) for t, h in variants if h != "all"]
        if not variants:
            return None, None, 0
        return variants[0][0], variants[0][1], len(variants)

    def targets(self, cls: str, spec: str, view: str, source: str, hero: str) -> dict[str, dict[str, float]] | None:
        """{bin: {stat: rating}} as ClassCodex resolves them (u.gg carries them; Icy Veins falls back to it)."""
        out: dict[str, dict[str, float]] = {}
        for bin_key in BINS:
            self.runtime.execute(f"ClassCodexDB.statTargetBin = '{bin_key}'")
            result = self.ns.GetStatTargets(cls, spec, view, source, hero)
            if not result:
                continue
            chosen = to_python(result.targets if hasattr(result, "targets") else result["targets"])
            used = result["bin"]
            if used == bin_key:
                out[bin_key] = {k: float(v) for k, v in chosen.items()}
        return out or None
