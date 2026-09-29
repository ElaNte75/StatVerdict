# Data quality audit: SV_ClassCodexTargets.lua (2026-09-29)

Scope: all 240 contexts (40 specs x 3 goals x 2 hero trees), read through
`tools/classcodex_lua_sandbox.run_addon_namespace`. Nothing was edited by hand.

## Result: no pipeline change needed

| Check | Result |
|---|---|
| Contexts present | 240 of 240 |
| Priority order complete (all 4 secondaries) | 240 of 240 |
| BiS slots, trinkets, `levels` (Champion/Hero) present | all |
| Guide targets present (Mythic+ and Raid) | all |
| Targets with an explicit value <= 0 | none (the writer omits zeros) |
| Own-target total vs. guide (top20) total outside 0.6x - 1.6x | 1 context (see below) |

### Stats missing from the own ("Measured") targets
A stat is absent when the best-in-slot gear carries none of it (the generated file only stores
positive totals). This is real data, not a fetch or SimC failure:

- **Versatility absent (36 own targets, 72 level targets):** Demon Hunter Havoc/Devourer, Druid Balance/Feral,
  Evoker Augmentation/Devastation, Hunter Survival, Mage Frost, Monk Windwalker, Priest Discipline/Shadow,
  Rogue Assassination, Shaman Elemental/Enhancement, Warlock (all three), Warrior Arms.
- **Mastery absent (4 own targets, 8 level targets):** Monk Mistweaver and Rogue Outlaw, Mythic+ only.

The addon used to drop those rows in Measured mode; fixed in the addon (a secondary always keeps its row,
target 0), commit "Fix: a secondary stat with no target keeps its row".

### Unusual values (reported, not changed)
- **Monk Windwalker, Mythic+ and Raid (both hero trees): average item level 289** while nearly every other
  Mythic+/Raid context is 314-340 (median 334 / 338). The BiS items and bonus ids match the Icy Veins source
  exactly (see `data-fidelity-report.md`), so the low value comes from the item levels SimC reports for that
  loadout (`itemLevelSource: simc`); the cause is not visible from the committed data. Evoker Devastation
  (313.7) and Augmentation (319.5) are similarly lower. Needs a SimC run to inspect per-slot item levels.
- **Warrior Protection PvP colossus:** own total 2148 vs guide 3902 (average item level 277.5). PvP gear from
  the PvP source has widely varying item levels (PvP contexts range 255-324), so this is plausible.
