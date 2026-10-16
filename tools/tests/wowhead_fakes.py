"""A stand-in for the Wowhead item lookup (tools/wowhead_stat_engine.reconstruct_loadout) for the tests."""
from __future__ import annotations

from typing import Any, Callable

# The item level a 6/6 upgrade id gives (the ids the fake track data in the tests uses).
LEVEL_OF_BONUS_ID = {12854: 334, 12846: 321, 12838: 308}


def fake_wowhead(
    totals: dict[str, float] | None = None, *, calls: list | None = None, fail: Exception | None = None
) -> Callable[..., dict[str, Any]]:
    """A reconstruct function that returns `totals` (default crit 100, haste 50, mastery 30, versatility 20)
    for every loadout, with the item level of each piece taken from its upgrade id (280 without one).
    `calls` collects the loadouts asked for; `fail` makes every lookup raise it."""
    amounts = {"crit": 100.0, "haste": 50.0, "mastery": 30.0, "versatility": 20.0} if totals is None else totals

    def reconstruct(items: dict[str, dict[str, Any]], primary: str | None = None, **_kwargs: Any) -> dict[str, Any]:
        if fail is not None:
            raise fail
        if calls is not None:
            calls.append(items)
        slots = {}
        for slot, item in items.items():
            ids = item.get("bonusIds") or []
            slots[slot] = {"wowheadItemLevel": next((LEVEL_OF_BONUS_ID[i] for i in ids if i in LEVEL_OF_BONUS_ID), 280)}
        return {"totals": dict(amounts), "slots": slots, "failures": []}

    return reconstruct
