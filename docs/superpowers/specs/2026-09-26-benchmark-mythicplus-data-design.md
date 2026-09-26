# Benchmark: live Mythic+ data in the addon

Date: 2026-09-26. Status: draft, awaiting user review.

## Purpose

The GitHub pipeline now produces live Mythic+ benchmark data for all 40
specializations (Raider.IO combat-log runs, stats via SimulationCraft, or Wowhead
sums for healers). The addon still reads only the old ClassCodex file. This work
makes the addon use the live data for **Mythic+**, keeping the look, size and
verdict logic of the current interface unchanged.

## Agreed decisions

1. Mythic+ uses the live data. Raid and PvP keep using the old
   `SV_ProfileData.lua` exactly as today.
2. The interface style and window size do not change.
3. The addon-side data is a small file with only what the addon uses, in the same
   shape as the old Mythic+ context, so the scoring and rendering code is not
   rewritten.
4. Honest naming. For Mythic+ the item lists are **most popular among top players**,
   not curated best-in-slot, and are labelled "Popular" instead of "BiS".
   Raid/PvP keep "BiS" because those are still curated lists.
5. A new **Benchmark** button replaces **Summary** as the first button under Panels.
   It opens a right-side drawer, built like the existing Features/Manual drawers.
   The Summary panel is removed (Item Level, Attributes, Enhancements, Main/Off
   Spec Progress, BiS Progress readouts are intentionally lost).
6. The drawer lets the player choose the comparison group. Names:
   | Level | Data cohort | Meaning line in the drawer |
   |---|---|---|
   | Elite | TOP_25 | Gear of the top 25 players |
   | Standard (default) | TOP_100 | Gear of the top 100 players |
   | Broad | TOP_200 | Gear of the top 200 players |
7. The window still opens with all panels closed, as today.
8. Rule from the user: anything superseded is removed completely, including the
   old way and its leftovers. Risky removals are done in two steps: unplug first,
   delete after the user verifies in game (see Phases).

## Out of scope

Raid and PvP data; CurseForge publish action; the Demon Hunter Devourer
primary-stat bug in `Builder.lua`; workflow job renames; the
`actions/upload-artifact` bump.

## Data side

### Raw files leave the addon folder

`ship.ps1` copies the whole `Data` folder into the release zip and does not exclude
the six `SV_LiveBenchmarkData_*` files (about 300 MB). The pipeline will write the
raw files to `tools/data/live/` instead of `StatVerdict/Data/Generated/`. The addon
folder then contains only what the game loads. Workflow paths, engine defaults and
`tools/README.md` are updated accordingly.

### Compaction step

A new script `tools/addon_benchmarks.py` runs in the merge/validate job after
the six files exist. It reads them and writes **one** file,
`StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua`. Size gate: under 5 MB,
otherwise the job fails. The raw databases are kept only as JSON in
`tools/data/live/`; the raw `.lua` twins are no longer produced or committed (the
addon never loaded them).

Per specialization and per level (ELITE, STANDARD, BROAD) it writes a context in the
same shape the addon already consumes from the old file:

- `targets`: `averageItemLevel`, `itemCount` (number of resolved slots), `statTargets`
  (`context`, `source`, `stats` with keys `critical_strike`, `haste`, `mastery`,
  `versatility`, converted from the live keys `crit`, `haste`, ...),
  `targetMetadata`, `sourceGoal = "MYTHIC_PLUS"`. The profile's `primaryStat` is
  measured from the median primary stats (the raw label is not trusted; this fixes
  Devourer Demon Hunter, an Intellect spec labelled agility, for Mythic+).
- `bis` (rendered as "Popular"): `label`, and `slots` in the old order and slot
  names (Helm, Hands, Neck, Waist, Shoulders, Legs, Cloak, Feet, Chest, Ring, Ring,
  Trinket, Trinket, Bracers, Main Hand, Off Hand when the spec uses one). Each slot
  holds the most popular item of that slot from `popularItems` (`item_id`, `name`,
  `bonus_ids` from its most used variant) plus `usagePercent`. Rings and trinkets
  take the two most popular **distinct** items across both slots. No `source`
  (drop location) exists in the live data, so the field is absent.
- `trinkets`: ranked by usage; tier from usage share: S at 40% or more, A at 20%,
  B at 8%, C at 3%; trinkets below 3% are not listed. Only the tiers the addon
  already knows.
- `priorityProfiles`: one row per Hero Talent tree with `heroTalent` (name),
  `context = "Mythic+"`, `order` and `tiers` derived from that tree's median
  secondary stats (stats within 5% of each other share a tier). Trees without a
  valid cohort fall back to one spec-wide row.
- `cohort`: `sampleSize`, `minimumSample`, `confidence`, `status`, plus the
  file-level `generatedAt`, for the drawer's warnings.

A cohort whose `status` is not `ok` or whose sample is below its minimum is written
as absent, so the addon reports "no data" for it instead of guessing.

## Addon side

- `ProfileRepository`: when the goal is Mythic+, the context comes from
  `SV_MythicPlusBenchmarks` at the player's chosen level; for Raid/PvP it comes from
  the old data. Existing quality checks (at least 10 slots, item level at least 250,
  at least 2 stat targets) run on the new context unchanged. Freshness rule: the
  file's `generatedAt` must be within 30 days (the old "scrape date" rule does not
  apply to it). Failure keeps the current fail-closed behaviour ("data unavailable").
- Chosen level is stored in `StatVerdictDB.benchmarkLevel`, default `STANDARD`.
  Changing it refreshes the panels.
- `StatVerdict.toc` loads the new file; the raw files are not referenced.
- New `UI/SV_BenchmarkDrawerPanel.lua`, styled like `SV_OptionsDrawerPanel.lua`
  (width 280): three choices with the meaning line under each; for the selected
  level it shows sample size, confidence and data date; a "smaller sample, less
  stable" warning when the sample is small or confidence is not high; for Raid/PvP
  goals it states the choice applies to Mythic+ only.
- `SV_SettingsPanel.lua`: the Summary entry becomes Benchmark in the same position.
  `SV_RightPanelMode.lua` and `SV_DashboardLayout.lua`: mode `summary` becomes
  `benchmark`.
- Wording for Mythic+ only: button "Best in Slot" -> "Popular Gear", "Main/Off
  Spec Best in Slot" -> "... Popular Gear", "BiS Progress: 7/15" -> "Popular
  Progress: 7/15 - Standard", tooltip tag "(BIS)" -> "(Popular)", plus the
  explanatory strings and the Manual and `STORE.md` text. Raid/PvP keep "BiS".
- Known consequence: the Catalyst hint depends on the `source` field and does not
  fire for Mythic+ items. It stays in the code for Raid/PvP.

## Item score boosts (must keep working)

Mechanics a stat comparison cannot measure (trinket procs, item effects) are
represented by a boost in verdict points, taken from the reference lists. This is
implemented in `Core/SV_ItemReferenceBonuses.lua` and is **not changed**: an item
found in the `bis` slots gets +8 (`BIS_BONUS`); a trinket gets its tier bonus (S 95,
A 65, B 35, C 14, D 0) plus a rank bonus of up to 5 by its position inside the tier.
The reasoning stays the same: the higher an item stands in the list, the more its
mechanism is useful for this spec, so it is boosted.

The live data therefore has to satisfy the contract the boost code reads:

- every `bis.slots[i].item.item_id` is the numeric item id;
- `trinkets` is ordered by usage, highest first (rank inside a tier is the list
  position), each with a `tier` in S-D and an `item_id`;
- the boost applies to the level the player selected, because the context is built
  from that level.

Verification of this contract is part of the compaction tests. In phase 1 the
proposed tier thresholds and the number of slots with a clear favourite are reported
per specialization from the real data before they are locked, because a tier mistake
changes verdicts by up to 95 points. Boost constants stay as they are unless the user
decides otherwise after seeing those numbers.

## Verification

- Python tests for the compaction: all 40 specs x 3 levels present or explicitly
  absent; shape matches the old context; stat key conversion; tier thresholds;
  size under 5 MB; healer specs included.
- A validation run over the real generated files before the workflow commit.
- In-game checklist for the user: window opens with panels closed; Benchmark opens
  its drawer; switching Elite/Standard/Broad changes targets and Popular lists;
  Raid and PvP behave as before; a spec with missing data shows "unavailable";
  Popular labels appear for Mythic+ and BiS labels for Raid/PvP; a popular item or
  trinket that drops shows its boost tag and a higher verdict than an identical item
  outside the list.
- Lua files cannot be run outside WoW here, so they are checked by review and by
  the user's in-game test.

## Phases

1. Data: move raw files out of the addon folder, add the compaction step and tests,
   run the pipeline once.
2. Addon: read path, Benchmark drawer, wording, Summary unplugged (button, mode,
   `.toc` entry).
3. User verifies in game.
4. Cleanup (per the removal rule): delete the Summary panel code and its layout
   keys, the Mythic+ slice of `SV_ProfileData` if the ship and validation tools can
   drop it (decided with the user then), outdated `IMPROVEMENTS.md` items and any
   unused strings.
