# simc_scale_factor_report.json

**Shape verified against SimC's source; values are illustrative, not a live
capture.**

The key layout of this fixture was verified on 2026-09-28 by reading
SimulationCraft's own report writer on the `midnight` branch
(`simulationcraft/simc`):

- `engine/report/json/report_json.cpp`: each entry of `sim.players[]` gets
  `scale_factors` (for the sim's single `scaling_metric`, default DPS),
  `scale_factors_all` (one sub-object per metric, keyed by
  `util::scale_metric_type_abbrev`: `dps`, `prioritydps`, `dpse`, `hps`,
  `hpse`, `aps`, `haps`, `dtps`, `dmg_taken`, `htps`, `deaths`, `time`,
  `raid_dps`, `dhaps`) and `scale_deltas`, all only when scale factors were
  calculated. Values are raw per-point amounts unless
  `normalize_scale_factors` is on (this project never turns it on).
- `engine/util/util.cpp` (`util::stat_type_abbrev`): stat keys are SimC's
  short names -- `Crit`, `Haste`, `Mastery`, `Vers` for the secondaries,
  `Str`/`Agi`/`Int`/`Sta` for primaries. Which keys appear depends on the
  player's `scales_with` flags, so a real report may list more stats than
  the four this project reads; the parser ignores the rest.
- `engine/sim/scale_factor_control.cpp`: `scale_only=` takes a list split
  on `,:;/|` and parsed with `util::parse_stat_type`, which accepts the long
  names (`crit_rating`, ...), so
  `scale_only=crit_rating,haste_rating,mastery_rating,versatility_rating`
  is valid.

The earlier version of this fixture (a guessed `scaling.dps.crit_rating`
layout) was wrong; `tools/classcodex_weights.py::parse_scale_factors` now
reads `players[].scale_factors_all[<metric>]` with the abbreviated keys.

What is still unverified: the numbers themselves, and whether SimC emits
every metric sub-object for every role. A real captured report (one SimC
run with `calculate_scale_factors=1`) should still replace this file when a
machine with a SimC build is available -- re-run
`tools/tests/test_simc_scale_factor_report_fixture.py` and
`tools/tests/test_classcodex_weights.py` against it.
