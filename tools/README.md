# StatVerdict live benchmark engine

The production engine builds transparent Mythic+ cohort benchmarks for all 40
specializations.

## Sources and acceptance contract

- Raider.IO specialization rankings supply the current-season rank and scored
  runs.
- Only combat-log-tracked run details are accepted for observed gear. The
  roster snapshot must have `source: "db"` inside `logged_details`; mutable
  profile/Armory snapshots such as `source: "s3"` are rejected.
- The run snapshot supplies the specialization, Hero Talent ID, exact item IDs,
  item levels, bonus IDs, gems, enchants, tier identifiers, and loadout code
  used during the run.
- SimulationCraft reconstructs the character-sheet stats from that exact run
  gear, race, specialization, full talent loadout, and Hero Talent.

No current Armory profile is used, so later gear/spec changes cannot alter the
historical run evidence.

## Cohorts

The default verified cohorts are `TOP_25`, `TOP_100`, and `TOP_200`. Rankings
from EU, US (including Oceania), KR, and TW are merged by score. The collector
scans farther down the ranking until it has enough unique verified characters.

For reconstructed stat profiles the engine records:

- requested and actual sample size;
- completeness and confidence;
- median and mean equipped item level;
- median Strength/Agility/Intellect, Stamina, Crit, Haste, Mastery, and
  Versatility ratings;
- interquartile ranges so a wide or unstable target is visible;
- sample requirements and exact-match failure reasons.

For verified run gear it also records:

- base-item popularity per slot, with item-level/bonus/gem/enchant variants;
- 95% Wilson lower confidence bounds;
- `observedBisCandidate` only when the lower confidence bound exceeds 50%;
- top trinket and ring pairs;
- tier/set configurations;
- gem and enchant usage;
- evidence run IDs for auditability.

Each specialization stores stat and gear cohorts separately for every observed
Hero Talent tree. Insufficient tree data declares a specialization fallback.
`heroTalentAnalysis` compares secondary-stat medians only when at least two
tree cohorts meet their minimum sample.

Exact stat profiles more than 15% away from the sample's median item level are
rejected as outliers. Generated files replace previous files only after all
quality gates pass.

## Liquid Armory simulations

Liquid Armory publishes SimulationCraft-based trinket rankings but currently
has no documented public ingestion API. The engine never scrapes the site. It
can merge an approved JSON export from
`tools/data/liquid_armory_export.json`; the import must identify its
acquisition method, season, capture date, item level, upgrade track, profile,
fight style, and SimulationCraft provenance. Missing data is reported as
`externalSimulations.status = "unavailable"` and does not silently become
observed Raider.IO data.

Use `tools/liquid_armory_export.example.json` as the import contract. An
export may be ingested only with explicit authorization and must use
`authorized_export`. Automated bundle parsing, DOM extraction, browser
automation, and manual dataset mirroring are intentionally unsupported.

## Optional credential

- `RAIDERIO_ACCESS_KEY` — create a Raider.IO application/key if higher request
  limits are needed. The engine works without it for smaller/manual runs.

Never commit credentials to this repository.

## Local usage

PowerShell:

```powershell
$env:RAIDERIO_ACCESS_KEY = "..." # optional
$env:SIMC_BINARY = "C:\path\to\simc.exe"

python tools/live_benchmark_engine.py --cohorts 25,100,200
```

Fast smoke run:

```powershell
python tools/live_benchmark_engine.py --simc-bin C:\path\to\simc.exe --cohorts 3 --max-pages 1 --max-run-checks 1 --max-insufficient-specs 40
```

Validation only:

```powershell
python tools/live_benchmark_engine.py `
  --cohorts 25,100,200 `
  --validate-only StatVerdict/Data/Generated/SV_LiveBenchmarkData.json
```

## Automation

`.github/workflows/weekly-benchmarks.yml` checks twice monthly and can also be
launched manually. It builds and caches SimulationCraft's `midnight` branch.

The workflow:

1. runs deterministic tests;
2. discovers the active expansion and main season;
3. builds all 40 specialization profiles;
4. validates completeness and required ratings;
5. commits only validated generated files.

The engine uses Raider.IO's specialization ranking endpoint directly. Sparse
cohorts are published as `status: "insufficient"` and must not be used as
targets. Gear popularity may remain usable even when too few loadouts can be
reconstructed by SimulationCraft.

Any API, schema, or quality failure, or more than `--max-insufficient-specs`
(default 4) insufficient specs, stops the workflow and preserves the last
known-good database.
