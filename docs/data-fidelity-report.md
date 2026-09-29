# Fidelity check: generated targets vs raw Icy Veins data (2026-09-29)

Method: fetched the live build with `tools/classcodex_fetch.fetch_all()`, loaded the raw Icy Veins source
(`db_icyveins`), and compared it independently with `StatVerdict/Data/Generated/SV_ClassCodexTargets.lua`
for every spec x hero tree in **Mythic+ and Raid** (160 contexts: the goals sourced from Icy Veins; PvP comes
from the PvP source and is not compared). The raw list for the goal is used, else its "all" list. The
Catalyst rule is applied as documented in `classcodex_targets.gear_by_simc_slot` (the Catalyst result is the
BiS item and carries the bonus ids).

| What | Contexts compared | Differences |
|---|---|---|
| BiS item ids, per slot | 160 | **0** |
| BiS bonus ids, per slot | 160 | **0** |
| Trinket list (item id + tier) | 160 | 4 (intentional, below) |
| Gems (primary + secondary) | 160 | **0** |
| Enchants, per slot | 160 | **0** |

## The only differences
- **Druid Restoration, Mythic+ and Raid, both hero trees:** the guide lists trinket 193748 with tier `F-`.
  The generated data leaves it out on purpose: the addon only scores tiers S/A/B/C/D
  (`classcodex_targets.trinkets_from_entries`), so an `F-` row would be unscored.

## Notes
- Death Knight weapon runes are stored by spell id (e.g. 327082); the check compares the enchant item id,
  the enchant id and the spell id, so those match.
- Ours is faithful on every checked field; nothing to fix in `tools/`.
