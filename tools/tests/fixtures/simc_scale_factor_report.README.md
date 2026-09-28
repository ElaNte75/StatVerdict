# simc_scale_factor_report.json

**Not a live capture.** Written from documented knowledge of SimC's
`calculate_scale_factors=1` json2 report shape (a `scaling` object per
player, keyed by metric then `<stat>_rating`) because this repository's
working environment could not build SimC or get a GitHub Actions dispatch
to run at the time (see the SDD ledger for
docs/superpowers/plans/2026-09-28-classcodex-target-weight-pipeline.md,
Task 8's ruling). Replace this file with a real captured report — and
re-run `tools/tests/test_simc_scale_factor_report_fixture.py` and
`tools/tests/test_classcodex_weights.py` against it — before trusting
`SV_ClassCodexWeights.lua`'s numbers in-game.
