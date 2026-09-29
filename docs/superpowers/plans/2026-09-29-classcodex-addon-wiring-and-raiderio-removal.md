# ClassCodex Addon Wiring + Raider.IO Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** The addon reads Mythic+, Raid and PvP targets / best-in-slot / trinkets / priority / real stat weights from the new ClassCodex generated files, and every trace of the old Raider.IO pipeline is deleted.

**Architecture:** `SV_ProfileRepository.lua` becomes the only reader of `ns.ClassCodexTargets` (per spec -> goal -> hero-talent context) and `ns.ClassCodexWeights`. The per-hero-talent context has the exact field shape the addon already consumes (`targets`, `bis`, `trinkets`, `priorityProfiles`), so `SV_ItemReferenceBonuses.lua`, `SV_BisProgressPanel.lua` and `SV_StatAudit.lua` keep working through `profile.generatedContext`. Real measured weights replace the rank-position weights inside the existing scoring budget (same scale, so item verdict behaviour stays the same shape). Missing weights fall back to the current rank weights.

**Tech Stack:** Lua 5.1 (WoW), Python unittest + lupa for addon tests (`python -m unittest discover -s tools/tests`).

**Spec:** `docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline-spec.md` (+ this plan).

## Global Constraints
- The user-visible interface and product logic must not change, EXCEPT what is listed under "UI consequences" below once the owner approves it. No new panels, no re-layout, no changed strings beyond that list.
- The addon is not public: no backwards-compat shims, no dual-reading of old and new data. Delete superseded code and data outright (repo rule: replaced features are fully deleted).
- Generated files are read-only inputs (produced by GitHub Actions); do not hand-edit `SV_ClassCodex*.lua`.
- All Lua must compile (`AddonLuaSyntaxTests`), `.toc` must list every loaded file and no missing ones.
- Files loaded by the game: `SV_ClassCodexTargets.lua` (4 MB) is the size ceiling; do not add further generated files of that size.

## Data facts (real, from generated files on main, 2026-09-29)
- `ns.ClassCodexTargets = { buildId, profiles = { [SPEC_KEY] = { specKey, classToken, primaryStat, goals = { [GOAL] = { heroTalents = { [heroKey] = { targets, bis, trinkets, priorityProfiles } } } } } } }`. SPEC_KEY is the addon's own key (`DEATHKNIGHT_FROST`). Goals: `MYTHIC_PLUS`, `RAID`, `PVP`. `heroKey` is ClassCodex's lower-case key with dashes (`sanlayn`, `master-of-harmony`, `conduit-of-the-celestials`).
- `targets = { averageItemLevel (nil/absent for PvP), itemCount, itemLevelSlots, statTargets = { context, source, stats = { critical_strike, haste, mastery, versatility } }, targetMetadata = { lowItemReplacements, unresolvedLowItems, recovery? }, sourceGoal }`. Stat targets are ratings.
- `bis.slots[] = { slot = "Head", item = { item_id, bonus_ids } }` (no `source` field, no names).
- `trinkets[] = { item_id, bonus_ids, tier }`, `priorityProfiles[] = { context, heroTalent, order, tiers }`.
- `ns.ClassCodexWeights = { buildId, profiles = { [SPEC_KEY] = { goals = { [GOAL] = { heroTalents = { [heroKey] = { critical_strike = 1.0, haste = 0.84, mastery = .., versatility = .. } } } } } } }`, normalised so the highest stat is 1.0. Some combos may be absent (healers whose SimC run had no healing output); absent = use rank weights.
- `ns.StatDR` (from `SV_StatDR.lua`) exists but is NOT applied anywhere in this plan.
- Freshness: `ClassCodexTargets.buildId` looks like `20260929064954-...` (UTC yyyymmddhhmmss prefix). The old `generatedAt` age check (30 days) must be reproduced from that prefix.
- PvP entries have no `averageItemLevel` (ClassCodex PvP gear carries no item level) -> the max-level item-level validation must not reject PvP for that reason.

## UI consequences -- PENDING OWNER ANSWER (asked 2026-09-29; do NOT execute Task 3 until the parent says it is approved)
1. Because Raider.IO cohorts (Top 25/100/200 -> Elite/Standard/Broad) no longer exist, the Benchmark level selector has no data behind it. Remove the Benchmark drawer/button/mode, `SV_Benchmark.lua` level logic and its saved variable use, and the manual-drawer text about it. (If the owner objects later this is a single revert.)
2. Mythic+ wording changes from "Popular Gear / Popular Progress" to the curated "Best in Slot / BiS Progress" wording that Raid/PvP already use (the data is now a curated BiS list, so "popular" would be false).
Nothing else in the UI changes. Until approval, Tasks 1, 2, 4, 5 (Python/CI side only) and 6 proceed; the Benchmark drawer stays untouched (it will just show its existing "no data" state because `ns.MythicPlusBenchmarks` is gone) and `SV_ManualDrawerPanel.lua` is not edited.

## Review Focus
- Hero-talent selection: player's hero tree name/subTreeID must map to the right ClassCodex key (`San'layn` -> `sanlayn`, `Master of Harmony` -> `master-of-harmony`); unknown hero tree -> the first available hero key of that spec/goal is NOT acceptable silently: use spec-wide fallback = the hero key with best-matching name else `nil` (no data), never a wrong tree's data.
- A spec/goal with no data must degrade to "no data", not error (Lua nil-safety), same as today's missing-level path.
- Stale data (buildId older than 30 days) must fail closed like before.
- PvP contexts pass validation without averageItemLevel; M+/Raid still reject an implausible item level.
- Weights: measured weights order `secondaryOrder`; a tie/absent weight falls back to ClassCodex priority order; a spec with weights for only some hero keys uses the rank fallback for the others.
- Scoring scale: top measured secondary must get the same raw weight as rank 1 today (4.00), so the point budget and every delta/percent display keep their scale.
- After deletion nothing may still reference `MythicPlusBenchmarks`, `GetBenchmarkLevel`, `Raider`, `weekly-benchmarks`, `live_benchmark_engine`, `addon_benchmarks`.

### Task 1: Load the new data and expose it through the repository
**Files:** Modify `StatVerdict/StatVerdict.toc` (replace `Data/Generated/SV_MythicPlusBenchmarks.lua` with `SV_ClassCodexTargets.lua`, `SV_ClassCodexWeights.lua`, `SV_StatDR.lua`, loaded BEFORE Core files); Modify `StatVerdict/Core/SV_ProfileRepository.lua`; Test `tools/tests/test_addon_lua.py` (+ small fixture helper in `tools/tests/addon_fixtures.py`).
**Interfaces (produces):** `Repository.GetContext(specKey, goal, heroKey?)`, `Repository.ResolveHeroKey(specKey, goal, heroTalentName, heroSubTreeID) -> heroKey|nil`, `Repository.GetWeights(specKey, goal, heroKey) -> table|nil`, freshness check from `buildId`.
- [ ] Failing tests: load repository with a tiny hand-written `ns.ClassCodexTargets` fixture; assert context lookup per hero, name-normalisation matching (`San'layn`, `Master of Harmony`), unknown hero -> nil, stale buildId -> nil, PvP without averageItemLevel valid, M+ with averageItemLevel 100 invalid.
- [ ] Implement: replace `GetMythicPlusRoot`/`GetGoalRoot`/`GetContext` to read `ns.ClassCodexTargets.profiles[specKey].goals[goal].heroTalents[heroKey]`; rewrite `ValidateGeneratedContext` (drop the `sourceGoal`/level logic that no longer applies, keep item-count/BiS-slot minimums, skip ilvl minimum when `averageItemLevel` is nil AND `goal == "PVP"`); `GetDataProvenance` reads `buildId` + source name "StatVerdict ClassCodex data"; `BuildProviderView` iterates the new `profiles`.
- [ ] `BuildRuntimeProfile`: use the resolved hero context; `primaryStat` from `profiles[spec].primaryStat`; `priority` from `context.priorityProfiles[1]`.
- [ ] Run the whole suite; commit.

### Task 2: Real weights in scoring
**Files:** Modify `SV_ProfileRepository.lua` (profile gets `secondaryWeights`, sorted `secondaryOrder`), `StatVerdict/Core/SV_Modifiers.lua` (`GetRawDefaultStatWeight`); Tests in `test_addon_lua.py`.
- [ ] Failing test (drive `ns.GetDefaultStatWeight` with a hand-built profile): with `secondaryWeights = {crit=1.0, haste=0.5, ...}` the raw weight of crit equals `model.secondary[1]` (4.00) and haste 2.00 before budgeting; without `secondaryWeights` behaviour is byte-identical to today (regression test using current expectations).
- [ ] Implement in `GetRawDefaultStatWeight`: if `profile.secondaryWeights[statKey]` is a positive number -> `weight * model.secondary[1]`; else existing rank path. `secondaryOrder` is sorted by weight descending when weights exist (ties by ClassCodex priority order, then by key), otherwise ClassCodex priority (existing `BuildSecondaryOrder`).
- [ ] Keep `equalGroups`, delta gain/loss calibration and budget logic untouched.
- [ ] Commit.

### Task 3 (GATED - wait for owner approval): Mythic+ wording + remove the Benchmark selector (UI consequences 1 and 2)
**Files:** Modify/Delete: `Core/SV_Benchmark.lua` (delete the level machinery; keep `ns.GetReferenceWording` returning the BiS wording for every goal), delete `UI/SV_BenchmarkDrawerPanel.lua`, edit `.toc`, `UI/SV_RightPanelMode.lua`, `UI/SV_DashboardLayout.lua`, `UI/SV_SettingsPanel.lua`, `UI/SV_ManualDrawerPanel.lua`, `UI/SV_OptionsDrawerPanel.lua` and anything else that references `Benchmark` (grep first; remove the button/mode cleanly, keep neighbouring layout unchanged); update `tools/tests/test_addon_lua.py` (delete Benchmark drawer/level tests, keep and adapt the rest).
- [ ] Grep for `Benchmark|ELITE|STANDARD|BROAD|benchmarkLevel|IsBenchmarkRelevant|IsBenchmarkSampleSmall|popular` across `StatVerdict/`; remove or adapt every hit. `StatVerdictDB.benchmarkLevel` is simply no longer read.
- [ ] Layout: where the Benchmark button sat, close the gap the way the layout code does for hidden buttons (do not redesign).
- [ ] Update `SV_ManualDrawerPanel.lua` help text: drop the Benchmark line, change "Popular Gear (Best in Slot for Raid and PvP)" to "Best in Slot".
- [ ] Suite green; commit.

### Task 4: Consumers adapt (ItemReferenceBonuses, BisProgressPanel, StatAudit)
**Files:** `Core/SV_ItemReferenceBonuses.lua`, `UI/SV_BisProgressPanel.lua`, `UI/SV_StatAudit.lua`, `UI/SV_StatProgressPanel.lua`.
- [ ] `ResolveHeroDocument` must resolve the hero key of the *current* player/profile (profile carries `heroTalentName`/`heroSubTreeID` or the repository can resolve via snapshot helpers) and call `GetContext(specKey, goal, heroKey)`.
- [ ] `bis.slots[].source` no longer exists: `ResolveBis` keeps working (only needs `slot`, `item.item_id`); catalyst-path detection depended on `source`; with no `source` data it never fires. Remove the dead catalyst code path and its bonus constant instead of leaving it unreachable.
- [ ] `SV_StatAudit.lua` lines referencing `sampleSize`, `liveOverride`, `confidence`: remove the sample-size/low-confidence display logic that only Raider.IO produced; confirm remaining audit rows still render from `targets.statTargets.stats`.
- [ ] Tests: `GetItemReferenceInfo` returns BiS/trinket bonuses from the new shape; trinket tier ranking unchanged.
- [ ] Suite green; commit.

### Task 5: Delete Raider.IO everything
**Files to delete:** `.github/workflows/weekly-benchmarks.yml`, `benchmark-retry.yml`, `benchmark-smoke.yml`, `tools/live_benchmark_engine.py` (KEEP `SPEC_BY_KEY`/spec catalog: it is imported by `classcodex_targets.py`/`classcodex_weights.py` -> move the catalog into a new `tools/spec_catalog.py` first, update imports, then delete the rest), `tools/addon_benchmarks.py`, `tools/test_cohort_engine.py`, `tools/data/live/`, `tools/data/benchmark_retry_queue.json`, `StatVerdict/Data/Generated/SV_MythicPlusBenchmarks.lua`, `tools/wowhead_stat_engine.py` STAYS (used by the fallback), old Raider.IO-only tests and fixtures (`tools/tests/test_live_benchmark_engine.py`, `test_addon_benchmarks.py`, `addon_fixtures.py` pieces only if unused), README/VERIFICATION mentions, `.gitignore` entries that only served them.
- [ ] Do the catalog move first with tests green, then delete file by file; after each deletion run the suite.
- [ ] Final grep (case-insensitive) for `raider`, `MythicPlusBenchmarks`, `live_benchmark_engine`, `addon_benchmarks`, `weekly-benchmarks`, `TOP_25` across the repo excluding `docs/superpowers/plans/*` history and `.claude/worktrees`; every hit must be removed or justified in the final report.
- [ ] `simc-proof.yml` and its `tools/simc_proof.py` are Raider.IO-run based -> delete them too if they depend on Raider.IO data; keep anything only depending on `simc_stat_engine.py`.
- [ ] Commit.

### Task 6: Whole-addon verification in a fake WoW
- [ ] Add one integration test that loads EVERY `.toc` file in order into one lupa runtime with minimal WoW API stubs (as far as the existing tests already stub) plus the REAL generated `SV_ClassCodexTargets.lua`/`SV_ClassCodexWeights.lua`, then for every spec key x goal x hero key asserts: `GetContext` non-nil, `ValidateGeneratedContext` passes, weights (when present) sum sensibly, `BuildRuntimeProfile` returns a profile with non-empty `secondaryOrder` and `auditTargets.rows`. Print a coverage table on failure. (This is the "500 angles" check: it runs against the real data on every CI run.)
- [ ] Commit; final report lists any spec/goal/hero cell that has no data.
