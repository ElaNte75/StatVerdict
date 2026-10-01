"""Replays the addon's own verdict on the items of an item-check result and lines it
up against SimulationCraft's answer for the same items.

    python tools/item_check_verdict.py [docs/item-check/enhancement_shaman.json]

The whole addon is loaded in a fake WoW (real Lua 5.1 through lupa, the real generated
ClassCodex data) and every candidate is put through ns.BuildComparison, the function
that decides the upgrade arrow and the Verdict Points, against the exact items SimC
reported as equipped. Nothing here is a copy of the scoring: if the addon changes,
the answer changes.

Output: <input>_verdict.md next to the input. Development tool, not part of the addon.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

from tools.tests.test_addon_lua import FRAME_STUB, compile_lua_file, new_runtime, toc_lua_files
from tools.tests.test_addon_integration import PIN_TIME_TO_BUILD, WOW_GLOBALS_STUB

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "item-check" / "enhancement_shaman.json"

# SimC slot -> (inventory slot id, equip location)
SLOTS = {
    "head": (1, "INVTYPE_HEAD"), "neck": (2, "INVTYPE_NECK"), "shoulders": (3, "INVTYPE_SHOULDER"),
    "shoulder": (3, "INVTYPE_SHOULDER"), "back": (15, "INVTYPE_CLOAK"), "chest": (5, "INVTYPE_CHEST"),
    "wrists": (9, "INVTYPE_WRIST"), "wrist": (9, "INVTYPE_WRIST"), "hands": (10, "INVTYPE_HAND"),
    "waist": (6, "INVTYPE_WAIST"), "legs": (7, "INVTYPE_LEGS"), "feet": (8, "INVTYPE_FEET"),
    "finger1": (11, "INVTYPE_FINGER"), "finger2": (12, "INVTYPE_FINGER"),
    "trinket1": (13, "INVTYPE_TRINKET"), "trinket2": (14, "INVTYPE_TRINKET"),
    "main_hand": (16, "INVTYPE_WEAPON"), "off_hand": (17, "INVTYPE_WEAPON"),
}
JEWELRY_OR_CLOAK = {"neck", "back", "finger1", "finger2", "trinket1", "trinket2"}
STAT_KEYS = {
    "agility": "ITEM_MOD_AGILITY_SHORT",
    "strength": "ITEM_MOD_STRENGTH_SHORT",
    "intellect": "ITEM_MOD_INTELLECT_SHORT",
    "stamina": "ITEM_MOD_STAMINA_SHORT",
    "crit_rating": "ITEM_MOD_CRIT_RATING_SHORT",
    "haste_rating": "ITEM_MOD_HASTE_RATING_SHORT",
    "mastery_rating": "ITEM_MOD_MASTERY_RATING_SHORT",
    "versatility_rating": "ITEM_MOD_VERSATILITY",
}
COMBAT_RATING = {"crit": 9, "haste": 18, "mastery": 26, "versatility": 29}  # CR_* ids the addon may ask for
# Verdict of the addon that counts as "it recommends the item".
NOISE_FLOOR_PCT = 0.15  # a SimC gain smaller than this is treated as "no real difference"

CHARACTER = {"classFile": "SHAMAN", "className": "Shaman", "specKey": "SHAMAN_ENHANCEMENT", "specID": 263,
             "role": "DAMAGER", "heroTalentName": "Totemic"}

INVSLOT_LUA = """
INVSLOT_HEAD, INVSLOT_NECK, INVSLOT_SHOULDER, INVSLOT_BODY, INVSLOT_CHEST = 1, 2, 3, 4, 5
INVSLOT_WAIST, INVSLOT_LEGS, INVSLOT_FEET, INVSLOT_WRIST, INVSLOT_HAND = 6, 7, 8, 9, 10
INVSLOT_FINGER1, INVSLOT_FINGER2, INVSLOT_TRINKET1, INVSLOT_TRINKET2 = 11, 12, 13, 14
INVSLOT_BACK, INVSLOT_MAINHAND, INVSLOT_OFFHAND, INVSLOT_RANGED, INVSLOT_TABARD = 15, 16, 17, 18, 19
"""

ITEM_API_LUA = """
ITEMS = {}
local function info(link) return ITEMS[link] end
GetItemInfo = function(link)
    local i = info(link); if not i then return nil end
    return i.name, link, 4, i.ilvl, 80, "Armor", i.subclass, 1, i.equipLoc, 0, 0, i.classID, i.subID
end
GetItemInfoInstant = function(link)
    local i = info(link); if not i then return nil end
    return i.id, "Armor", i.subclass, i.equipLoc, 0, i.classID, i.subID
end
GetDetailedItemLevelInfo = function(link) local i = info(link); return i and i.ilvl or nil end
GetItemStats = function(link) local i = info(link); return i and i.stats or nil end
GetInventoryItemLink = function(unit, slot) return EQUIPPED and EQUIPPED[slot] or nil end
C_Item = setmetatable({
    GetItemStats = function(link) local i = info(link); return i and i.stats or nil end,
    GetItemInfo = function(link) return GetItemInfo(link) end,
    GetItemInfoInstant = function(link) return GetItemInfoInstant(link) end,
    GetDetailedItemLevelInfo = function(link) return GetDetailedItemLevelInfo(link) end,
    GetItemNumSockets = function() return 0 end,
}, {__index = function() return function() return nil end end})
"""


def lua_pairs(table) -> dict:
    return {key: table[key] for key in table.keys()} if table is not None else {}


def lua_list(table) -> list:
    return [table[i] for i in range(1, len(table) + 1)] if table is not None else []


def load_addon():
    """The whole addon (toc order) with the real generated data, in a fake WoW."""
    lua = new_runtime()
    lua.execute(FRAME_STUB)
    lua.execute(WOW_GLOBALS_STUB)
    # Real numbers, not stubs: the addon builds its slot tables from these while loading.
    lua.execute(INVSLOT_LUA)
    lua.globals().StatVerdictDB = lua.table()
    ns = lua.table()
    lua.globals().SV_TEST_NS = ns
    for path in toc_lua_files():
        compile_lua_file(lua, path)("StatVerdict", ns)
    lua.execute("setmetatable(_G, nil)")
    lua.eval("function(src, buildId, parse) assert(loadstring(src))(buildId, parse) end")(
        PIN_TIME_TO_BUILD, ns.ClassCodexTargets.buildId, ns.ProfileRepository.ParseBuildTime)
    lua.execute(ITEM_API_LUA)
    return lua, ns


def item_stats(raw: dict[str, Any]) -> dict[str, float]:
    return {lua_key: float(raw[key]) for key, lua_key in STAT_KEYS.items() if isinstance(raw.get(key), (int, float))}


def register_item(lua, link: str, item_id: int, raw: dict[str, Any], slot: str) -> None:
    _, equip_loc = SLOTS[slot]
    stats = lua.table_from(item_stats(raw))
    sub_id = 0 if slot in JEWELRY_OR_CLOAK else 3  # 3 = mail, the Shaman armor type
    subclass = "Miscellaneous" if slot in JEWELRY_OR_CLOAK else "Mail"
    lua.globals().ITEMS[link] = lua.table(
        id=item_id, name=str(raw.get("name") or f"item {item_id}"), ilvl=float(raw.get("ilevel") or 0),
        equipLoc=equip_loc, stats=stats, classID=4, subID=sub_id, subclass=subclass)


def set_character(lua, ratings: dict[str, float], agility: float) -> None:
    """The WoW APIs that say who is playing and how many rating points they have now."""
    crit, haste = ratings.get("crit", 0), ratings.get("haste", 0)
    mastery, vers = ratings.get("mastery", 0), ratings.get("versatility", 0)
    lua.execute(f"""
    -- The game defines these rating ids; without them the addon cannot read the character's
    -- ratings and its live weights stay neutral.
    CR_CRIT_MELEE, CR_HASTE_MELEE, CR_MASTERY, CR_VERSATILITY_DAMAGE_DONE = 9, 18, 26, 29
    UnitClass = function() return "Shaman", "SHAMAN", 7 end
    UnitLevel = function() return 90 end
    UnitName = function() return "Tester" end
    GetSpecialization = function() return 2 end
    GetSpecializationInfo = function() return 263, "Enhancement", "", 0, "DAMAGER", "AGILITY" end
    GetCombatRating = function(id)
        if id == 9 then return {crit} end
        if id == 18 then return {haste} end
        if id == 26 then return {mastery} end
        if id == 29 then return {vers} end
        return 0
    end
    UnitStat = function() return {agility}, {agility}, 0, 0 end
    """)
    # The addon reads ratings at gear/spec changes only; a new character is such a change.
    lua.execute("if SV_TEST_NS and SV_TEST_NS.InvalidateCurrentStatRatings then SV_TEST_NS.InvalidateCurrentStatRatings() end")


def build_profile(lua, ns, goal: str, mode: str):
    ns.ProfileRepository.InvalidateProviderViews()
    context = lua.table(**CHARACTER)
    context.goal = goal
    return ns.ProfileRepository.BuildRuntimeProfile(context)


def compare(lua, ns, profile, baseline_gear: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    """The addon's answer for one candidate: does it recommend it, and with how many points."""
    slot = row.get("replaced_slot") or row["slot"]
    candidate_raw = row.get("gear")
    if not candidate_raw or slot not in SLOTS:
        return None
    equipped = lua.table()
    for gear_slot, raw in baseline_gear.items():
        if gear_slot not in SLOTS:
            continue
        link = f"item:{gear_slot}:{int(raw.get('ilevel') or 0)}"
        register_item(lua, link, 900000 + SLOTS[gear_slot][0], raw, gear_slot)
        equipped[SLOTS[gear_slot][0]] = link
    lua.globals().EQUIPPED = equipped
    candidate_link = f"item:candidate:{row['item_id']}"
    register_item(lua, candidate_link, int(row["item_id"]), candidate_raw, slot)
    ns.ClearUpgradeIndicatorDecisionCache()
    comparison = ns.BuildComparison(candidate_link, profile)
    selected = comparison.selected if comparison is not None else None
    if selected is None:
        return {"verdict": "no verdict", "points": None, "slot": None, "reason": "the addon gives no comparison"}
    points = selected.deltaScore if selected.deltaScore is not None else selected.rawDeltaScore
    rows = []
    for entry in lua_list(selected.deltaRows):
        if isinstance(entry.signedPoints, (int, float)):
            rows.append({"label": str(entry.statName or entry.statKey), "delta": float(entry.signedPoints),
                         "amount": entry.amount, "weight": entry.weight})
    return {
        "verdict": "upgrade" if (selected.isUpgrade and points and points > 0) else "not an upgrade",
        "points": float(points) if points is not None else None,
        "slot": selected.slotID if isinstance(selected.slotID, (int, float)) else None,
        "breakdown": rows,
    }


RATING_KEYS = {
    "crit": ("ITEM_MOD_CRIT_RATING_SHORT", "crit_rating"),
    "haste": ("ITEM_MOD_HASTE_RATING_SHORT", "haste_rating"),
    "mastery": ("ITEM_MOD_MASTERY_RATING_SHORT", "mastery_rating"),
    "versatility": ("ITEM_MOD_VERSATILITY", "versatility_rating"),
}


def target_progress(profile, ratings: dict[str, float], candidate: dict[str, Any], replaced: dict[str, Any] | None):
    """How far the four secondary stats are from the profile's target stats before and after the swap.

    The addon's aim is to bring the character to its target stats (the ratings that give the
    best result), so an item helps when it lowers the total shortfall: the rating points still
    missing to reach each target (a stat above its target has no shortfall). Returns None when the
    profile has no targets."""
    targets = {}
    for row in lua_list(profile.auditTargets.rows):
        if isinstance(row.target, (int, float)) and row.target > 0:
            targets[str(row.key)] = float(row.target)
    if not targets:
        return None
    before = after = 0.0
    per_stat = []
    for name, (lua_key, gear_key) in RATING_KEYS.items():
        target = targets.get(lua_key)
        if target is None:
            continue
        now = float(ratings.get(name, 0))
        new = now + float(candidate.get(gear_key, 0) or 0) - float((replaced or {}).get(gear_key, 0) or 0)
        short_before, short_after = max(0.0, target - now), max(0.0, target - new)
        before += short_before
        after += short_after
        per_stat.append({"stat": name, "target": target, "now": now, "after": new})
    return {"before": before, "after": after, "closer_by": before - after, "per_stat": per_stat}


def simc_verdict(row: dict[str, Any]) -> tuple[str, float | None, float | None]:
    """What SimC says about one row: upgrade / same / downgrade beyond its own noise."""
    st = row.get("st")
    if not st:
        return "not simulated", None, None
    pct, err = st["delta"]["pct"], st["delta"]["err95"]
    base = st["dps"]["mean"] - st["delta"]["abs"]
    err_pct = 100.0 * err / base if base else 0.0
    if not row.get("simulable", True):
        return "unreliable", pct, err_pct
    if pct - err_pct > 0 and pct >= NOISE_FLOOR_PCT:
        return "upgrade", pct, err_pct
    if pct + err_pct < 0:
        return "downgrade", pct, err_pct
    return "same", pct, err_pct


def spearman(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None

    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out

    a, b = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else None


def classify(simc: str, addon: str) -> str:
    if simc in ("not simulated", "unreliable"):
        return "not compared"
    recommends = addon == "upgrade"
    if simc == "upgrade":
        return "OK: both say upgrade" if recommends else "MISSED: SimC says upgrade, addon does not"
    if simc in ("same", "downgrade"):
        if not recommends:
            return "OK: both say not an upgrade"
        return "WRONG: addon says upgrade, SimC says " + ("no gain" if simc == "same" else "a loss")
    return "not compared"


def replay(data: dict[str, Any], goals=("MYTHIC_PLUS", "RAID"), modes=("GUIDE",)) -> dict[str, Any]:
    lua, ns = load_addon()
    baseline = data["baseline"]
    stats = baseline.get("stats") or {}
    set_character(lua, stats.get("ratings") or {}, float(stats.get("agility") or 0))
    gear = baseline.get("gear") or {}
    if not gear:
        raise SystemExit("the result has no baseline gear: re-run the item check workflow (it now records it)")
    out: dict[str, Any] = {"runs": {}}
    for goal in goals:
        for mode in modes:
            profile = build_profile(lua, ns, goal, mode)
            if profile is None:
                out["runs"][f"{goal}/{mode}"] = {"error": "no profile for this goal"}
                continue
            results = []
            for row in data["rows"]:
                if "gear" not in row:
                    continue
                # the replaced item is the baseline item of the slot SimC chose
                row_gear = {**gear}
                answer = compare(lua, ns, profile, row_gear, row)
                simc, pct, err_pct = simc_verdict(row)
                slot_key = row.get("replaced_slot") or row["slot"]
                progress = target_progress(profile, stats.get("ratings") or {}, row.get("gear") or {},
                                           row.get("replaced_gear") or gear.get(slot_key))
                results.append({"row": row, "addon": answer, "simc": simc, "pct": pct, "err_pct": err_pct,
                                "target": progress})
            weights = {}
            for label, key in (("Item level", "STATVERDICT_ITEM_LEVEL"), ("Agility", "ITEM_MOD_AGILITY_SHORT"),
                               ("Crit", "ITEM_MOD_CRIT_RATING_SHORT"), ("Haste", "ITEM_MOD_HASTE_RATING_SHORT"),
                               ("Mastery", "ITEM_MOD_MASTERY_RATING_SHORT"), ("Versatility", "ITEM_MOD_VERSATILITY")):
                value = ns.GetDefaultStatWeight(profile, key)
                if isinstance(value, (int, float)):
                    weights[label] = float(value)
            out["runs"][f"{goal}/{mode}"] = {"heroKey": str(profile.heroKey), "weights": weights, "rows": results}
    return out


def target_diagnosis(rows: list[dict[str, Any]]) -> str:
    """Three-way check: SimC (real DPS), the target stats, and the addon. Where two agree and
    the third does not, that third one is the suspect."""
    tally = {"targets_vs_simc": [0, 0], "addon_vs_targets": [0, 0]}
    odd_targets, odd_addon = [], []
    for r in rows:
        target, addon = r.get("target"), (r["addon"] or {}).get("verdict")
        if not target or addon is None or r["simc"] in ("unreliable", "not simulated"):
            continue
        helps_target = target["closer_by"] > 0.5
        simc_helps = r["simc"] == "upgrade"
        addon_helps = addon == "upgrade"
        tally["targets_vs_simc"][0] += helps_target == simc_helps
        tally["targets_vs_simc"][1] += 1
        tally["addon_vs_targets"][0] += addon_helps == helps_target
        tally["addon_vs_targets"][1] += 1
        if helps_target != simc_helps:
            odd_targets.append(r["row"]["name"])
        if addon_helps != helps_target:
            odd_addon.append(r["row"]["name"])
    a, b = tally["targets_vs_simc"], tally["addon_vs_targets"]
    out = ["### Three-way check: SimC DPS, target stats, addon", "",
           "The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. "
           "An item is counted as helping the targets when it lowers the total rating shortfall.", "",
           f"- Target stats agree with SimC on **{a[0]} of {a[1]}** items"
           + (f" (they differ on: {', '.join(odd_targets)})" if odd_targets else "")
           + ". A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).",
           f"- Addon agrees with the target stats on **{b[0]} of {b[1]}** items"
           + (f" (they differ on: {', '.join(odd_addon)})" if odd_addon else "")
           + ". A difference here points at the *addon's scoring* (weights, live modifiers, item level).", ""]
    return "\n".join(out)


def render(data: dict[str, Any], replayed: dict[str, Any]) -> str:
    lines = [
        "# Item check: addon verdict vs SimulationCraft",
        "",
        f"Character: {data.get('character')}. SimC run: {data.get('generated_at')}. "
        "The addon's answer is computed by its own `BuildComparison` on the same items SimC used.",
        "",
        "**How to read it.** SimC is the reference (a real simulation). The addon does not simulate; it scores "
        "stats with weights. The question is only: does the addon recommend the items that really help, and not "
        "the ones that do not? Verdict Points are not DPS, so only the direction and the order are compared.",
        "",
    ]
    for run_key, run in replayed["runs"].items():
        lines += [f"## {run_key}", ""]
        if "error" in run:
            lines += [run["error"], ""]
            continue
        rows = run["rows"]
        tally: dict[str, int] = {}
        pairs = []
        for r in rows:
            r["class"] = classify(r["simc"], (r["addon"] or {}).get("verdict", "no verdict"))
            tally[r["class"]] = tally.get(r["class"], 0) + 1
            if r["addon"] and r["addon"].get("points") is not None and r["pct"] is not None and r["simc"] != "unreliable":
                pairs.append((r["addon"]["points"], r["pct"]))
        rho = spearman(pairs)
        lines += [f"Hero tree used: `{run['heroKey']}`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): "
                  + ", ".join(f"{k} {v:.2f}" for k, v in run["weights"].items()) + ".", ""]
        lines += [f"- {name}: **{count}**" for name, count in sorted(tally.items())]
        lines += [f"- Rank agreement (Spearman, addon points vs SimC gain, {len(pairs)} items): "
                  + (f"**{rho:.2f}** (1.0 = same order, 0 = unrelated)" if rho is not None else "n/a"), ""]
        lines += ["| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |",
                  "|---|---|---:|---|---:|---|---|---|"]
        for r in sorted(rows, key=lambda r: -(r["pct"] if r["pct"] is not None else -999)):
            row, addon = r["row"], r["addon"] or {}
            pts = addon.get("points")
            gain = f"{r['pct']:+.2f}% ±{r['err_pct']:.2f}" if r["pct"] is not None else "-"
            target = r.get("target")
            short = f"{target['before']:.0f} -> {target['after']:.0f} ({target['closer_by']:+.0f})" if target else "-"
            lines.append(f"| {row['name']} | {row['slot']} | {gain} | {r['simc']} | "
                         f"{'-' if pts is None else f'{pts:+.2f}'} | {addon.get('verdict', 'no verdict')} | {short} | {r['class']} |")
        lines += ["", target_diagnosis(rows)]
        bad = [r for r in rows if r["class"].startswith(("WRONG", "MISSED"))]
        if bad:
            lines += ["", "### Disagreements: why the addon answers as it does", ""]
            for r in bad:
                row, addon = r["row"], r["addon"] or {}
                lines.append(f"- **{row['name']}** ({row['slot']}, replaces {row.get('replaced')}): {r['class']}. "
                             f"Candidate {row.get('stats')} at ilvl {row.get('ilevel')}, replaced ilvl {row.get('replaced_ilevel')}.")
                if addon.get("breakdown"):
                    parts = ", ".join(f"{b['label']} {b['delta']:+.1f}" for b in addon["breakdown"])
                    lines.append(f"  - addon points by stat (weight x amount gained or lost): {parts}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_INPUT
    data = json.loads(path.read_text(encoding="utf-8"))
    replayed = replay(data)
    target = path.with_name(path.stem + "_verdict.md")
    target.write_text(render(data, replayed), encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
