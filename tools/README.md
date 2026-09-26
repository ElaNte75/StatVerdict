# StatVerdict live benchmark engine

The production engine builds transparent Mythic+ cohort benchmarks for all 40
specializations.

## Sources and meaning

- Raider.IO supplies the current season leaderboard, character identity, score,
  class, role, and specialization discovery.
- Blizzard Profile API supplies current character-sheet ratings and equipped
  items.
- Targets are medians from the selected cohort, not simulated optimums.

The profile APIs show what a character is wearing when indexed. They do not
prove that the same loadout was worn in every ranked run. For that reason the
output is labelled as an observed cohort benchmark, never as a mathematically
optimal BiS set.

## Cohorts

The default database stores `TOP_20`, `TOP_100`, and `TOP_500`. Each larger
cohort includes the smaller one. The engine records:

- requested and actual sample size;
- completeness and confidence;
- median and mean equipped item level;
- median Strength/Agility/Intellect, Stamina, Crit, Haste, Mastery, and
  Versatility ratings;
- interquartile ranges so a wide or unstable target is visible;
- item popularity by equipment slot.

Character profiles more than 15% away from the sample's median item level are
rejected as stale/outlier profiles. The generated files replace the previous
files only after all quality gates pass.

## Required credentials

Create a Blizzard API client at:

`https://develop.battle.net/access/clients`

Add these repository secrets under:

`Settings → Secrets and variables → Actions → New repository secret`

- `BLIZZARD_CLIENT_ID`
- `BLIZZARD_CLIENT_SECRET`

Optional:

- `RAIDERIO_ACCESS_KEY` — create a Raider.IO application/key if higher request
  limits are needed. The engine works without it for smaller/manual runs.

Never commit credentials to this repository.

## Local usage

PowerShell:

```powershell
$env:BLIZZARD_CLIENT_ID = "..."
$env:BLIZZARD_CLIENT_SECRET = "..."
$env:RAIDERIO_ACCESS_KEY = "..." # optional

python tools/live_benchmark_engine.py --cohorts 20,100,500
```

Fast smoke run:

```powershell
python tools/live_benchmark_engine.py --cohorts 3 --max-pages 5
```

Validation only:

```powershell
python tools/live_benchmark_engine.py `
  --cohorts 20,100,500 `
  --validate-only StatVerdict/Data/Generated/SV_LiveBenchmarkData.json
```

## Automation

`.github/workflows/weekly-benchmarks.yml` runs every Wednesday at 15:00 UTC,
which is 18:00 in Greece during daylight-saving time. GitHub cron uses UTC and
does not automatically move for winter time. The workflow can also be launched
manually from the repository's Actions tab with custom cohort sizes.

The workflow:

1. runs deterministic tests;
2. discovers the active expansion and main season;
3. builds all 40 specialization profiles;
4. validates completeness and required ratings;
5. commits only validated generated files.

Any API, freshness, sample-size, or quality failure stops the workflow and
preserves the last known-good database.
