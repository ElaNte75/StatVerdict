#!/usr/bin/env python3
"""Item check: measures with SimulationCraft how much each candidate item
changes the DPS of one real character (a SimC addon export), so the result
can be compared with the addon's in-game verdicts.

For every candidate the character's profile is copied with only that one
slot swapped, and baseline + candidates are simulated in two scenarios
(single-target Patchwerk and a steady 3-target cleave). Ring/trinket
candidates are tried in both slots on the single-target run; the better slot
is kept and reused for the cleave run.

SimC option names used here were VERIFIED against simulationcraft/simc
branch `midnight` (commit f7ee0f4, read 2026-09-29):
  * engine/sim/sim.cpp: `fight_style` (opt_func parse_fight_style),
    `desired_targets` (opt_int), `target_error` (opt_float), `iterations`,
    `deterministic` (opt_bool). `deterministic=1` exists but SimC throws
    "'deterministic=1' cannot be used with non-zero target_error values!",
    so it is NOT used: precision comes from iterations + target_error and
    every delta is reported with its statistical error.
  * engine/util/util.cpp fight_style_string: "Patchwerk", "HecticAddCleave",
    "CleaveAdd", "CastingPatchwerk", "DungeonSlice", ... HecticAddCleave is
    one boss plus waves of 5 adds with movement (not a steady 3 targets), so
    the cleave scenario is Patchwerk + desired_targets=3.
  * engine/item/item.cpp: item options `ilevel`, `drop_level`,
    `content_tuning`, `crafted_stats`, `crafting_quality` all exist.
  * engine/interfaces/sc_js.cpp: an extended sample (collected_data.dps)
    is written with "mean" and "mean_std_dev".
  * Breath of Jan'alai (280377): the item exists in SimC's item data, but its
    on-use spell 1308728 has no handler in engine/player/unique_gear_midnight.cpp
    and its effects (a periodic trigger aura) do not qualify for SimC's
    generic offensive on-use (engine/item/special_effect.cpp
    is_offensive_spell_action), so only its Agility is simulated.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from tools.simc_stat_engine import parse_report, run_simc
except ModuleNotFoundError:  # run as `python tools/item_check.py`
    from simc_stat_engine import parse_report, run_simc

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = REPO_ROOT / "tools" / "data" / "characters" / "enhancement_shaman.simc"
DEFAULT_OUT_JSON = REPO_ROOT / "docs" / "item-check" / "enhancement_shaman.json"
DEFAULT_OUT_MD = REPO_ROOT / "docs" / "item-check" / "enhancement_shaman.md"

ITEM_SLOTS = (
    "head", "neck", "shoulder", "shoulders", "back", "chest", "wrist", "wrists",
    "hands", "waist", "legs", "feet", "finger1", "finger2", "trinket1",
    "trinket2", "main_hand", "off_hand",
)
# A candidate for one of these groups is tried in every listed slot.
SLOT_GROUPS = {
    "finger": ("finger1", "finger2"),
    "trinket": ("trinket1", "trinket2"),
}
# Actor option lines copied into the repo profile / every sim input. Anything
# else (region, server, professions, omnium_talents, checksum, currencies,
# saved-loadout comments, ...) is dropped.
ACTOR_KEYS = ("level", "race", "role", "spec", "talents")
CONFIDENCE_Z = 1.96  # SimC's default 95% confidence estimator

SCENARIOS = {
    "st": {"label": "Single target (Patchwerk)", "options": {"fight_style": "Patchwerk", "desired_targets": 1}},
    "cleave": {"label": "3-target cleave (Patchwerk, desired_targets=3)", "options": {"fight_style": "Patchwerk", "desired_targets": 3}},
}

# item id -> reason why SimC cannot fully simulate the item.
NOT_SIMULABLE = {
    280377: (
        "not simulable: SimC midnight has no handler for the on-use fire cone "
        "(spell 1308728), so only its Agility is counted"
    ),
}

ITEM_LINE_RE = re.compile(r"^(?P<slot>[a-z_0-9]+)=(?P<fields>,?id=.*)$")
NAME_COMMENT_RE = re.compile(r"^#\s*(?P<name>.+?)\s*\((?P<ilevel>\d+)\)\s*$")
ACTOR_RE = re.compile(r'^(?P<cls>[a-z]+)="(?P<name>[^"]*)"\s*$')


@dataclass
class ItemLine:
    slot: str
    fields: str  # everything after "slot=", e.g. ",id=1,bonus_id=2"
    name: str = ""
    ilevel: int | None = None

    @property
    def item_id(self) -> int | None:
        match = re.search(r"(?:^|,)id=(\d+)", self.fields)
        return int(match.group(1)) if match else None

    def render(self, slot: str | None = None) -> str:
        return f"{slot or self.slot}={self.fields}"


@dataclass
class Profile:
    class_token: str
    actor_name: str
    actor_lines: list[str]
    equipped: dict[str, ItemLine]
    bags: list[ItemLine] = field(default_factory=list)


@dataclass
class Candidate:
    key: str
    name: str
    group: str  # a SimC slot, or "finger"/"trinket"
    fields: str
    ilevel: int | None
    stats_hint: str = ""
    source: str = ""

    @property
    def item_id(self) -> int | None:
        return ItemLine(self.group, self.fields).item_id

    @property
    def target_slots(self) -> tuple[str, ...]:
        return SLOT_GROUPS.get(self.group, (self.group,))


# Quest rewards of the 12.1 questline "Return to Amani'Zar" (Adventurer 3/6,
# item level 272). Their secondary stats are fixed in SimC's item data.
QUEST_CANDIDATES = (
    Candidate("278882", "Ophidian General's Barbute", "head", ",id=278882,ilevel=272", 272, "Agi 106, Haste 72, Vers 79", "quest"),
    Candidate("278894", "Faithleaper's Sabatons", "feet", ",id=278894,ilevel=272", 272, "Crit 59, Mastery 54", "quest"),
    Candidate("278898", "Fangsmasher Gauntlets", "hands", ",id=278898,ilevel=272", 272, "Crit 59, Haste 54", "quest"),
    Candidate("279194", "Collar of Jealousy", "neck", ",id=279194,ilevel=272", 272, "Haste 121, Mastery 143", "quest"),
    Candidate("279195", "Choker of Anger", "neck", ",id=279195,ilevel=272", 272, "Crit 140, Vers 125", "quest"),
    Candidate("279196", "Chain of Vengeance", "neck", ",id=279196,ilevel=272", 272, "Crit 121, Haste 143", "quest"),
    Candidate("280377", "Breath of Jan'alai", "trinket", ",id=280377,ilevel=272", 272, "Agi 101 + on-use", "quest"),
)


def slot_group(slot: str) -> str:
    for group, slots in SLOT_GROUPS.items():
        if slot in slots:
            return group
    return slot


def parse_profile(text: str) -> Profile:
    """Parses a SimC addon export: actor lines, equipped items and the
    commented items of the "### Gear from Bags" block."""
    class_token = actor_name = ""
    actor: dict[str, str] = {}
    equipped: dict[str, ItemLine] = {}
    bags: list[ItemLine] = []
    section = "main"
    pending_name: tuple[str, int] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("###"):
            section = "bags" if "gear from bags" in line.lower() else "other"
            pending_name = None
            continue
        if not line:
            continue
        commented = line.startswith("#")
        body = line.lstrip("#").strip() if commented else line
        name_match = NAME_COMMENT_RE.match(line) if commented else None
        item_match = ITEM_LINE_RE.match(body)
        if item_match and item_match.group("slot") in ITEM_SLOTS:
            name, ilevel = pending_name or ("", None)
            item = ItemLine(item_match.group("slot"), item_match.group("fields"), name, ilevel)
            if commented and section == "bags":
                bags.append(item)
            elif not commented and section == "main":
                equipped[item.slot] = item
            pending_name = None
            continue
        if name_match:
            pending_name = (name_match.group("name"), int(name_match.group("ilevel")))
            continue
        if commented or section != "main":
            continue
        actor_match = ACTOR_RE.match(line)
        if actor_match and not class_token:
            class_token, actor_name = actor_match.group("cls"), actor_match.group("name")
            continue
        key, sep, value = line.partition("=")
        if sep and key in ACTOR_KEYS and key not in actor:
            actor[key] = value
    if not class_token:
        raise ValueError("profile has no actor line (e.g. shaman=\"Name\")")
    if not equipped:
        raise ValueError("profile has no equipped items")
    actor_lines = [f"{key}={actor[key]}" for key in ACTOR_KEYS if key in actor]
    return Profile(class_token, actor_name, actor_lines, equipped, bags)


def sanitize_profile(text: str, actor_name: str = "Tester") -> str:
    """The repo copy of a SimC export: renamed character, only spec / race /
    level / talents / gear (bonus ids, enchants, gems) and the bag items;
    region, server, professions, checksum, omnium and currency lines are
    dropped."""
    profile = parse_profile(text)
    lines = [
        "# Item-check profile: sanitized SimulationCraft addon export",
        "# (character renamed; account and location lines removed).",
        "",
        f'{profile.class_token}="{actor_name}"',
        *profile.actor_lines,
        "",
    ]
    for item in profile.equipped.values():
        if item.name:
            lines.append(f"# {item.name} ({item.ilevel})")
        lines.append(item.render())
    lines += ["", "### Gear from Bags", "#"]
    for item in profile.bags:
        if item.name:
            lines.append(f"# {item.name} ({item.ilevel})")
        lines.append(f"# {item.render()}")
        lines.append("#")
    lines.append("### End of Gear from Bags")
    return "\n".join(lines) + "\n"


def build_candidates(profile: Profile) -> list[Candidate]:
    candidates = list(QUEST_CANDIDATES)
    for index, item in enumerate(profile.bags, 1):
        candidates.append(
            Candidate(
                key=f"bag{index:02d}-{item.item_id}",
                name=item.name or f"item {item.item_id}",
                group=slot_group(item.slot),
                fields=item.fields,
                ilevel=item.ilevel,
                source="bags",
            )
        )
    return candidates


def render_sim_input(
    profile: Profile,
    scenario: str,
    *,
    iterations: int,
    target_error: float,
    override: tuple[str, str] | None = None,
    actor_name: str = "Tester",
) -> str:
    """One SimC input: sim options, the actor, and its gear with at most one
    slot replaced (`override` = (slot, item fields))."""
    options = SCENARIOS[scenario]["options"]
    lines = [
        f"iterations={int(iterations)}",
        f"target_error={target_error}",
        f"fight_style={options['fight_style']}",
        f"desired_targets={int(options['desired_targets'])}",
        "report_details=0",
        "",
        f'{profile.class_token}="{actor_name}"',
        *profile.actor_lines,
    ]
    for slot, item in profile.equipped.items():
        if override and slot == override[0]:
            continue
        lines.append(item.render())
    if override:
        lines.append(f"{override[0]}={override[1]}")
    return "\n".join(lines) + "\n"


# --- report parsing -------------------------------------------------------

STAT_LABELS = (
    ("crit_rating", "Crit"),
    ("haste_rating", "Haste"),
    ("mastery_rating", "Mastery"),
    ("versatility_rating", "Vers"),
)


def first_player(report: dict[str, Any]) -> dict[str, Any]:
    sim = report.get("sim", report)
    players = sim.get("players") or []
    if not players:
        raise RuntimeError("SimC report has no players")
    return players[0]


def dps_result(report: dict[str, Any]) -> dict[str, float]:
    dps = first_player(report).get("collected_data", {}).get("dps", {})
    mean, err = dps.get("mean"), dps.get("mean_std_dev")
    if not isinstance(mean, (int, float)):
        raise RuntimeError("SimC report has no collected_data.dps.mean")
    return {"mean": float(mean), "std_err": float(err) if isinstance(err, (int, float)) else 0.0}


def equipped_item(report: dict[str, Any], slot: str) -> dict[str, Any] | None:
    gear = first_player(report).get("gear") or {}
    aliases = {"shoulder": "shoulders", "wrist": "wrists"}
    return gear.get(slot) or gear.get(aliases.get(slot, slot))


def format_item_stats(gear_item: dict[str, Any] | None) -> str:
    if not gear_item:
        return ""
    parts = []
    for key, value in gear_item.items():
        if "agi" in key and isinstance(value, (int, float)):
            parts.append(f"Agi {round(value)}")
            break
    for key, label in STAT_LABELS:
        value = gear_item.get(key)
        if isinstance(value, (int, float)) and value > 0:
            parts.append(f"{label} {round(value)}")
    return ", ".join(parts)


def raw_gear(gear_item: dict[str, Any] | None) -> dict[str, Any] | None:
    """The numbers SimC reports for one item (item level, primary and secondary stats,
    armor, weapon values), kept in the JSON so the addon's verdict can be replayed on
    exactly the same items (tools/item_check_verdict.py)."""
    if not isinstance(gear_item, dict):
        return None
    out: dict[str, Any] = {}
    for key, value in gear_item.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) or key in ("name", "slot"):
            out[key] = value
    return out


def delta(candidate: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    diff = candidate["mean"] - baseline["mean"]
    err = CONFIDENCE_Z * math.hypot(candidate["std_err"], baseline["std_err"])
    pct = 100.0 * diff / baseline["mean"] if baseline["mean"] else 0.0
    return {"abs": diff, "pct": pct, "err95": err}


# --- running --------------------------------------------------------------

Runner = Callable[[str], dict[str, Any]]


def make_runner(simc_binary: Path, threads: int, timeout_seconds: int) -> Runner:
    def run(profile_text: str) -> dict[str, Any]:
        _, report = run_simc(simc_binary, profile_text, threads=threads, timeout_seconds=timeout_seconds)
        return report

    return run


def item_is_equipped(report: dict[str, Any], slot: str, item_id: int | None) -> bool:
    gear_item = equipped_item(report, slot)
    if not gear_item:
        return False
    if item_id is None:
        return True
    encoded = str(gear_item.get("encoded_item", ""))
    return re.search(rf"(?:^|,)id={item_id}(?:,|$)", encoded) is not None


def run_candidate(
    runner: Runner,
    profile: Profile,
    candidate: Candidate,
    scenario: str,
    slot: str,
    sim_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """{"slot", "dps", "gear"} or {"slot", "error"}."""
    text = render_sim_input(profile, scenario, override=(slot, candidate.fields), **sim_kwargs)
    try:
        report = runner(text)
        result = dps_result(report)
    except Exception as exc:  # SimC rejected the item / crashed
        return {"slot": slot, "error": str(exc).strip()[:500]}
    if not item_is_equipped(report, slot, candidate.item_id):
        return {"slot": slot, "error": "SimC did not equip the item (missing from the report's gear)"}
    return {"slot": slot, "dps": result, "gear": equipped_item(report, slot)}


def check_items(
    runner: Runner,
    profile: Profile,
    candidates: list[Candidate],
    *,
    iterations: int,
    target_error: float,
    progress: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    sim_kwargs = {"iterations": iterations, "target_error": target_error}
    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "character": "Enhancement Shaman",
        "settings": {
            "iterations": iterations,
            "target_error": target_error,
            "scenarios": {key: value["label"] for key, value in SCENARIOS.items()},
            "error_note": "± is the 95% confidence interval of the difference (1.96 x combined mean_std_dev)",
        },
        "baseline": {},
        "rows": [],
        "partial": True,
    }
    baseline_report: dict[str, Any] = {}
    for scenario in SCENARIOS:
        log(f"baseline {scenario} ...")
        report = runner(render_sim_input(profile, scenario, **sim_kwargs))
        result["baseline"][scenario] = dps_result(report)
        if scenario == "st":
            baseline_report = report
            result["baseline"]["gear"] = {
                slot: raw_gear(item) for slot, item in (first_player(report).get("gear") or {}).items()
                if raw_gear(item) is not None
            }
            stats = parse_report(report)
            player_stats = next(iter(stats.values()), {})
            result["baseline"]["stats"] = {
                "ratings": player_stats.get("ratings", {}),
                "percentages": player_stats.get("percentages", {}),
                "agility": (player_stats.get("attributes") or {}).get("agility"),
            }
        if progress:
            progress(result)

    for candidate in candidates:
        row: dict[str, Any] = {
            "key": candidate.key,
            "slot": candidate.group,
            "name": candidate.name,
            "item_id": candidate.item_id,
            "ilevel": candidate.ilevel,
            "stats": candidate.stats_hint,
            "source": candidate.source,
            "note": NOT_SIMULABLE.get(candidate.item_id or 0, ""),
            "simulable": (candidate.item_id or 0) not in NOT_SIMULABLE,
        }
        slots = [slot for slot in candidate.target_slots if slot in profile.equipped] or list(candidate.target_slots)
        log(f"{candidate.name} ({candidate.group}) st: {', '.join(slots)}")
        attempts = [run_candidate(runner, profile, candidate, "st", slot, sim_kwargs) for slot in slots]
        ok = [attempt for attempt in attempts if "dps" in attempt]
        if not ok:
            row["simulable"] = False
            row["note"] = "not simulable: " + "; ".join(f"{a['slot']}: {a['error']}" for a in attempts)
            result["rows"].append(row)
            if progress:
                progress(result)
            continue
        best = max(ok, key=lambda attempt: attempt["dps"]["mean"])
        slot = best["slot"]
        replaced = profile.equipped.get(slot)
        row["replaced_slot"] = slot
        row["replaced"] = (replaced.name or f"item {replaced.item_id}") if replaced else "(empty)"
        row["replaced_ilevel"] = replaced.ilevel if replaced else None
        gear = best.get("gear") or {}
        if isinstance(gear.get("ilevel"), (int, float)):
            row["ilevel"] = round(gear["ilevel"])
        row["stats"] = format_item_stats(gear) or candidate.stats_hint
        row["gear"] = raw_gear(gear)
        row["replaced_gear"] = raw_gear(equipped_item(baseline_report, slot)) if baseline_report else None
        row["st"] = {"dps": best["dps"], "delta": delta(best["dps"], result["baseline"]["st"])}
        row["slot_attempts"] = {
            attempt["slot"]: (round(attempt["dps"]["mean"], 1) if "dps" in attempt else attempt["error"])
            for attempt in attempts
        }
        log(f"{candidate.name} cleave: {slot}")
        cleave = run_candidate(runner, profile, candidate, "cleave", slot, sim_kwargs)
        if "dps" in cleave:
            row["cleave"] = {"dps": cleave["dps"], "delta": delta(cleave["dps"], result["baseline"]["cleave"])}
        else:
            row["cleave_error"] = cleave["error"]
        result["rows"].append(row)
        if progress:
            progress(result)

    rank_rows(result["rows"])
    result["partial"] = False
    return result


def sort_key(row: dict[str, Any]) -> tuple[int, float]:
    if "st" not in row:
        return (2, 0.0)
    return (0 if row.get("simulable", True) else 1, -row["st"]["delta"]["abs"])


def rank_rows(rows: list[dict[str, Any]]) -> None:
    rows.sort(key=sort_key)
    rank = 0
    for row in rows:
        if "st" in row and row.get("simulable", True):
            rank += 1
            row["rank"] = rank
        else:
            row["rank"] = None


# --- output ---------------------------------------------------------------

def fmt_num(value: float) -> str:
    return f"{value:,.0f}"


def fmt_delta(block: dict[str, Any] | None) -> str:
    if not block:
        return "—"
    d = block["delta"]
    return f"{d['abs']:+,.0f} ({d['pct']:+.2f}%) ±{d['err95']:,.0f}"


def render_markdown(result: dict[str, Any]) -> str:
    settings = result["settings"]
    baseline = result.get("baseline", {})
    lines = [
        f"# Item check: {result['character']}",
        "",
        f"Generated {result['generated_at']} with SimulationCraft (midnight). "
        f"iterations ≤ {settings['iterations']}, target_error {settings['target_error']}%.",
        f"Scenarios: ST = {settings['scenarios']['st']}; Cleave = {settings['scenarios']['cleave']}.",
        f"Deltas are candidate minus baseline; {settings['error_note']}. "
        "A delta smaller than its ± is within simulation noise.",
    ]
    if result.get("partial"):
        lines += ["", "**PARTIAL RESULT: the run did not finish; rows below are the ones completed so far.**"]
    stats = baseline.get("stats")
    if stats:
        ratings, pct = stats.get("ratings", {}), stats.get("percentages", {})
        lines += ["", "## Baseline (current gear)", "", "| Stat | Rating | % |", "|---|---:|---:|"]
        for key, label in (("crit", "Crit"), ("haste", "Haste"), ("mastery", "Mastery"), ("versatility", "Versatility")):
            rating, percent = ratings.get(key), pct.get(key)
            lines.append(
                f"| {label} | {fmt_num(rating) if isinstance(rating, (int, float)) else '?'} | "
                f"{f'{percent:.2f}' if isinstance(percent, (int, float)) else '?'} |"
            )
        if isinstance(stats.get("agility"), (int, float)):
            lines.append(f"| Agility | {fmt_num(stats['agility'])} | |")
    for scenario, label in (("st", "ST"), ("cleave", "Cleave")):
        if scenario in baseline:
            b = baseline[scenario]
            lines.append("")
            lines.append(f"Baseline DPS {label}: {fmt_num(b['mean'])} (±{CONFIDENCE_Z * b['std_err']:,.0f})")
    lines += [
        "",
        "## Candidates (sorted by single-target delta)",
        "",
        "| Rank | Slot | Candidate | ilvl | Stats | Replaces | DPS ST | Δ ST | DPS Cleave | Δ Cleave | Notes |",
        "|---:|---|---|---:|---|---|---:|---|---:|---|---|",
    ]
    for row in sorted(result.get("rows", []), key=sort_key):
        replaced = row.get("replaced", "—")
        if row.get("replaced_slot") and row["replaced_slot"] != row["slot"]:
            replaced = f"{replaced} ({row['replaced_slot']})"
        if row.get("replaced_ilevel"):
            replaced = f"{replaced} [{row['replaced_ilevel']}]"
        notes = row.get("note", "")
        if row.get("cleave_error"):
            notes = (notes + "; " if notes else "") + "cleave failed: " + row["cleave_error"]
        cells = [
            str(row["rank"]) if row.get("rank") else "—",
            row["slot"],
            row["name"],
            str(row.get("ilevel") or "?"),
            row.get("stats") or "",
            replaced,
            fmt_num(row["st"]["dps"]["mean"]) if "st" in row else "—",
            fmt_delta(row.get("st")),
            fmt_num(row["cleave"]["dps"]["mean"]) if "cleave" in row else "—",
            fmt_delta(row.get("cleave")),
            notes.replace("|", "/").replace("\n", " "),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def write_outputs(result: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(result), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--simc-bin", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=30000)
    parser.add_argument("--target-error", type=float, default=0.05)
    parser.add_argument("--timeout", type=int, default=3600, help="seconds per SimC run")
    args = parser.parse_args(argv)

    profile = parse_profile(args.profile.read_text(encoding="utf-8"))
    candidates = build_candidates(profile)
    print(f"{len(candidates)} candidates, {len(profile.equipped)} equipped slots", flush=True)
    runner = make_runner(args.simc_bin, args.threads, args.timeout)
    result = check_items(
        runner,
        profile,
        candidates,
        iterations=args.iterations,
        target_error=args.target_error,
        progress=lambda partial: write_outputs(partial, args.out_json, args.out_md),
        log=lambda message: print(message, flush=True),
    )
    write_outputs(result, args.out_json, args.out_md)
    print(render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
