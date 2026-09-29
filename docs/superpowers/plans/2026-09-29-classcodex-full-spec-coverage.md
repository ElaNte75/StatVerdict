# ClassCodex Full Spec Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the target/weight pipelines produce usable data for all 40 specs x 3 goals (MYTHIC_PLUS/RAID/PVP), by fixing the real SimC failures found in the first live run (2026-09-29).

**Architecture:** Keep SimulationCraft as the primary engine. Add a shared recovery layer around `run_simc` (weapon conflicts, talent-export fallback, stat-sheet-only mode) and a gear-only Wowhead-tooltip fallback for specs SimC cannot initialise at all. Weights stay SimC-measured only; a missing weight is simply absent from the file (the addon falls back to rank-based weights, its existing behaviour).

**Tech Stack:** Python 3.12, unittest, SimulationCraft (`midnight` branch), GitHub Actions. Tests: `python -m unittest discover -s tools/tests`.

**Spec:** `docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline-spec.md`

## Global Constraints
- Do not touch anything under `StatVerdict/Core/` or `StatVerdict/UI/`.
- Output shape of `SV_ClassCodexTargets.lua` / `SV_ClassCodexWeights.lua` must not change (only additive, optional `targetMetadata` keys and a different `statTargets.source` string).
- Stat names stay addon-canonical (`critical_strike`, `haste`, `mastery`, `versatility`); spec keys stay `CLASS_SPEC` upper-case.
- Every failure still fails closed with a `ComboSkipped` reason; nothing may silently produce a partial or guessed number, except the Wowhead fallback which must be labelled in `statTargets.source`.
- The unit tests must never touch the network or a real SimC binary (inject fakes).

## Evidence (real errors from run 36544293528, one line per root cause)
1. Frost DK: `Off-Hand weapon equipped with a 2h`. Windwalker, Brewmaster: `both a 1-hand and 2-hand weapon equipped at once` (ClassCodex lists Main Hand + Off Hand even when one of them is 2h).
2. Holy Priest: `Unable to create action 'divine_star,...'`; Discipline: `could not find spell data for Action 'evangelism_radiance'` — SimC's *default action list* is broken/outdated; irrelevant for a stat-sheet run.
3. Mistweaver: only a trailing `Trivial:` warning was visible (real error cut off by the 500-char log tail) — needs a fuller log first.
4. Restoration Druid: `Selected node 82241 entry 103320 is not available to player's spec` (talent export rejected by SimC).
5. Restoration Shaman: `role (hybrid) or spec isn't supported yet`; Holy Paladin: `is using an unsupported spec` — SimC cannot initialise these at all.
6. Other gaps: 6 combos with `fewer than 2 usable secondary stats`, 5 with `no talent export for this goal` (inspect after the fixes; they may vanish).

## Review Focus
- A combo that only succeeds after recovery must say so (`targetMetadata.recovery`) so it is auditable.
- The Wowhead fallback must never run for a spec SimC handled fine, and must produce >= 2 positive secondary stats or skip.
- Dropping the off-hand must not change `bis.slots` (the addon compares real BiS items); only the simulated loadout changes.
- Weights for a combo that needed weapon recovery are still valid; weights for a healer whose SimC run yields all-zero hps must be skipped, not written.

### Task 1: Full SimC error in the log
**Files:** Modify `tools/classcodex_targets.py`, `tools/classcodex_weights.py`; tests in `tools/tests/test_classcodex_run_reporting.py`.
- [ ] Print the first 1200 characters AND the last 600 of the SimC error (not only the last 500) so the real fatal error is visible next to trailing `Trivial:` lines. Test: a fake `run_simc` raising a long message; assert both head and tail appear on stderr.
- [ ] Commit.

### Task 2: Recovery layer in `tools/simc_stat_engine.py`
**Files:** Modify `tools/simc_stat_engine.py`; tests `tools/tests/test_simc_stat_engine.py`.
**Produces:** `run_simc_with_recovery(simc_binary, spec, record, *, render_kwargs, run_kwargs) -> (stats_by_actor, report, recovery: list[str], actor_name)` where `recovery` lists e.g. `["dropped OFF_HAND"]`.
- [ ] `render_player`/`render_profiles`: new keyword `stat_sheet_only: bool = False` -> adds `default_actions=0` to the player block (skips the default action list). Test it renders that line only when requested.
- [ ] `run_simc_with_recovery` retry order on `RuntimeError` text match: (a) message contains `Off-Hand weapon equipped with a 2h` or `both a 1-hand and 2-hand` -> re-render without `OFF_HAND`; if it still fails with the same class of message -> also without `MAIN_HAND`; (b) any other error -> re-raise unchanged. Never more than 2 retries. Tests use a fake `run_simc` (monkeypatch) proving the order, the recovery labels, and that other errors are not retried.
- [ ] Commit.

### Task 3: Talent-export fallback
**Files:** Modify `tools/classcodex_targets.py`, `tools/classcodex_weights.py`; tests in their test files.
- [ ] New `talent_exports_from_entries(entries) -> list[str]` (recommended first, then the rest in order, de-duplicated). Keep `talent_export_from_entries` behaviour identical (returns first of that list).
- [ ] When SimC fails with `is not available to player's spec` (or `Selected node`), try the next export; if all exports fail, run once more WITHOUT a `talents=` line (add `talents_optional` support in `render_player`: empty loadout omits the line instead of raising) and record `"talents ignored"` in `targetMetadata.recovery`. Test with fakes.
- [ ] Commit.

### Task 4: Targets use the recovery layer
**Files:** Modify `tools/classcodex_targets.py` (`reconstruct_target_context`), tests.
- [ ] Use `render_profiles(..., stat_sheet_only=True)` and `run_simc_with_recovery`; write `targetMetadata.recovery` (list, omitted when empty) and keep `bis.slots` = the full ClassCodex list.
- [ ] Commit.

### Task 5: Weights use the recovery layer, skip empty healer results
**Files:** Modify `tools/classcodex_weights.py`, tests.
- [ ] Weapon recovery + talent fallback apply; do NOT use `stat_sheet_only` (scale factors need a rotation). If all scale factors are 0 (healer/support spec whose action list did nothing) -> `ComboSkipped("no positive <metric> scale factor")` (already the rule; add a test with an all-zero report).
- [ ] Commit.

### Task 6: Wowhead gear-only fallback for specs SimC cannot initialise
**Files:** Modify `tools/classcodex_targets.py`, `tools/classcodex_targets_cli.py`; use existing `tools/wowhead_stat_engine.reconstruct_loadout` (inject it as a parameter for tests); tests.
- [ ] Trigger ONLY when the SimC error text contains `unsupported` or `isn't supported yet` (Holy Paladin, Restoration Shaman). Items: `build_simc_items` output; `primary` from the spec's primary stat. Convert `totals` to canonical secondaries; require >= 2 positive; set `statTargets.source = "ClassCodex BiS + Wowhead gear totals (no SimC support for this spec)"` and `targetMetadata.recovery = ["wowhead fallback"]`.
- [ ] Any Wowhead failure -> `ComboSkipped("wowhead fallback failed")`. Test with a fake `reconstruct_loadout`.
- [ ] The CLI must not fail the whole run when Wowhead is unreachable (skips are reported as usual).
- [ ] Commit.

### Task 7: Live verification and coverage report
- [ ] Run full unit suite (must be green). Push to `main`, dispatch `classcodex-live-refresh.yml`, wait, then run the coverage script (`tools/classcodex_coverage_report.py`, new, small: loads the two generated Lua files via `classcodex_lua_sandbox.run_addon_namespace` and prints a spec x goal table with missing cells; unit-test it on tiny fixtures).
- [ ] Iterate (Tasks 1-6 style fixes) until every spec has MYTHIC_PLUS/RAID/PVP targets, or the only remaining gaps are combos where ClassCodex itself has no data (document those in the final report with the exact reason).
- [ ] Then dispatch `classcodex-stat-weights.yml` (all 6 shards) and confirm the gate keeps the previous file when coverage drops.
