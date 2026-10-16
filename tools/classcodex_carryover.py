"""Safety net of the weekly data job: what is missing or unusable in freshly built data stays as it was.

Every spec/goal/hero-tree context has four parts: the Best in Slot list (`bis`), the trinkets, the stat
order (`priorityProfiles`) and the measured targets (`targets`). Each part is checked on its own. A part that
is valid in the new data replaces the old one; a part that is missing or invalid is taken from the
previous generated file, as long as that part is not older than MAX_CARRY_AGE_DAYS. A context the new
run did not produce at all is carried whole. Where each carried part came from is written to the context
(`carried = {part: build id}`), and the report names every one, so a bad week is never silent.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any

PARTS: tuple[str, ...] = ("bis", "trinkets", "priorityProfiles", "targets")
SECONDARIES: frozenset[str] = frozenset({"critical_strike", "haste", "mastery", "versatility"})
MIN_BIS_SLOTS = 12
# Stricter than the add-on, which stops trusting data after 60 days (buildId prefix): a carried part must not live long.
MAX_CARRY_AGE_DAYS = 30
# More contexts than this share needing a carried part means the new data is broken, not just thin.
MAX_CARRIED_SHARE = 0.25


def build_time(build_id: Any) -> datetime | None:
    """The time in front of a build id like '20261014113733-cf94a55-a900207b', or None."""
    if not isinstance(build_id, str) or len(build_id) < 14 or not build_id[:14].isdigit():
        return None
    try:
        return datetime.strptime(build_id[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _positive(stats: Any) -> int:
    if not isinstance(stats, dict):
        return 0
    return sum(1 for value in stats.values() if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0)


def part_problem(context: Any, part: str, goal: str) -> str | None:
    """Why one part of a context cannot be used, or None when it is fine."""
    if not isinstance(context, dict):
        return "no context"
    value = context.get(part)
    if part == "bis":
        slots = value.get("slots") if isinstance(value, dict) else None
        if not isinstance(slots, list) or len(slots) < MIN_BIS_SLOTS:
            return "Best in Slot list too short"
        if any(not isinstance((slot or {}).get("item"), dict) or not (slot["item"].get("item_id")) for slot in slots):
            return "Best in Slot list has a slot without an item"
        return None
    if part == "trinkets":
        return None if isinstance(value, list) and value else "no trinkets"
    if part == "priorityProfiles":
        order = value[0].get("order") if isinstance(value, list) and value and isinstance(value[0], dict) else None
        if not isinstance(order, list) or not SECONDARIES <= set(order):
            return "stat order lacks the four secondary stats"
        return None
    if part == "targets":
        if not isinstance(value, dict):
            return "no targets"
        if _positive((value.get("statTargets") or {}).get("stats")) < 2:
            return "fewer than two usable stat targets"
        if goal != "PVP":
            levels = value.get("levels") or {}
            for track in ("hero", "champion"):
                if _positive((((levels.get(track) or {}).get("statTargets")) or {}).get("stats")) < 2:
                    return f"no {track} level targets"
        return None
    return f"unknown part {part}"


def _iter_contexts(data: dict[str, Any]):
    for spec_key, profile in sorted((data.get("profiles") or {}).items()):
        for goal, goal_data in sorted(((profile or {}).get("goals") or {}).items()):
            for hero, context in sorted(((goal_data or {}).get("heroTalents") or {}).items()):
                yield spec_key, goal, hero, context


def _find(data: dict[str, Any] | None, spec_key: str, goal: str, hero: str) -> dict[str, Any] | None:
    try:
        context = data["profiles"][spec_key]["goals"][goal]["heroTalents"][hero]  # type: ignore[index]
    except (KeyError, TypeError):
        return None
    return context if isinstance(context, dict) else None


def _place(data: dict[str, Any], spec_key: str, goal: str, hero: str, context: dict[str, Any], previous: dict[str, Any]) -> None:
    profile = data.setdefault("profiles", {}).setdefault(spec_key, {})
    old_profile = previous["profiles"][spec_key]
    for key in ("specKey", "classToken", "primaryStat"):
        profile.setdefault(key, old_profile.get(key))
    profile.setdefault("goals", {}).setdefault(goal, {}).setdefault("heroTalents", {})[hero] = context


def carry_over(
    new: dict[str, Any], previous: dict[str, Any] | None, max_age_days: int = MAX_CARRY_AGE_DAYS
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(merged data, report). `new` is not changed. report = {"carried": [(where, part, build id, why)],
    "dropped": [(where, why)], "contexts": total contexts of the merged data, "carriedContexts": how many
    needed at least one carried part}."""
    merged = copy.deepcopy(new)
    report: dict[str, Any] = {"carried": [], "dropped": [], "contexts": 0, "carriedContexts": 0}
    if not isinstance(previous, dict):
        report["contexts"] = sum(1 for _ in _iter_contexts(merged))
        return merged, report
    now = build_time(new.get("buildId")) or datetime.now(timezone.utc)
    limit = timedelta(days=max_age_days)
    previous_build = previous.get("buildId")

    def origin_of(old_context: dict[str, Any], part: str) -> str | None:
        return ((old_context.get("carried") or {}).get(part)) or previous_build

    def usable(old_context: dict[str, Any], part: str, goal: str) -> tuple[bool, str]:
        if part_problem(old_context, part, goal):
            return False, "the previous part is not usable either"
        born = build_time(origin_of(old_context, part))
        if born is None or now - born > limit:
            return False, f"the previous part is older than {max_age_days} days"
        return True, ""

    # 1. contexts the new run has, part by part
    for spec_key, goal, hero, context in list(_iter_contexts(merged)):
        old = _find(previous, spec_key, goal, hero)
        where = f"{spec_key}/{goal}/{hero}"
        carried_here = False
        for part in PARTS:
            problem = part_problem(context, part, goal)
            if problem is None:
                continue
            if old is None:
                report["dropped"].append((where, f"{part}: {problem}, nothing to carry"))
                context["__broken__"] = True
                continue
            ok, why = usable(old, part, goal)
            if not ok:
                report["dropped"].append((where, f"{part}: {problem}; {why}"))
                context["__broken__"] = True
                continue
            context[part] = copy.deepcopy(old[part])
            context.setdefault("carried", {})[part] = origin_of(old, part)
            report["carried"].append((where, part, origin_of(old, part), problem))
            carried_here = True
        if carried_here:
            report["carriedContexts"] += 1

    # 2. contexts only the previous file has
    for spec_key, goal, hero, old in list(_iter_contexts(previous)):
        if _find(merged, spec_key, goal, hero) is not None:
            continue
        where = f"{spec_key}/{goal}/{hero}"
        carried: dict[str, str] = {}
        failed = None
        for part in PARTS:
            ok, why = usable(old, part, goal)
            if not ok:
                failed = f"{part}: {why}"
                break
            carried[part] = origin_of(old, part) or ""
        if failed:
            report["dropped"].append((where, f"not produced this week; {failed}"))
            continue
        copy_context = copy.deepcopy(old)
        copy_context["carried"] = carried
        _place(merged, spec_key, goal, hero, copy_context, previous)
        report["carried"].append((where, "whole context", previous_build, "not produced this week"))
        report["carriedContexts"] += 1

    # 3. contexts that stayed broken are removed
    for spec_key, goal, hero, context in list(_iter_contexts(merged)):
        if context.pop("__broken__", False):
            del merged["profiles"][spec_key]["goals"][goal]["heroTalents"][hero]
            if not merged["profiles"][spec_key]["goals"][goal]["heroTalents"]:
                del merged["profiles"][spec_key]["goals"][goal]
            if not merged["profiles"][spec_key]["goals"]:
                del merged["profiles"][spec_key]
    report["contexts"] = sum(1 for _ in _iter_contexts(merged))
    return merged, report


def carry_problem(report: dict[str, Any], max_share: float = MAX_CARRIED_SHARE) -> str | None:
    """Why the merged data must not be written (too much of it is carried), or None."""
    total = report.get("contexts") or 0
    if total and report["carriedContexts"] / total > max_share:
        return (
            f"{report['carriedContexts']} of {total} contexts needed data from the previous week "
            f"(more than {max_share:.0%}): the new data is broken"
        )
    return None


def format_report(report: dict[str, Any]) -> str:
    """The text for the job log and the commit message."""
    carried, dropped = report["carried"], report["dropped"]
    if not carried and not dropped:
        return "Carry-over: nothing needed from the previous week."
    lines = [
        f"Carry-over: {len(carried)} part(s) in {report['carriedContexts']} of {report['contexts']} context(s) "
        f"kept from an earlier week, {len(dropped)} context(s) dropped."
    ]
    for where, part, build_id, why in carried:
        lines.append(f"  kept {part} of {where} from build {build_id} ({why})")
    for where, why in dropped:
        lines.append(f"  dropped {where}: {why}")
    return "\n".join(lines)
