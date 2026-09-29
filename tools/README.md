# StatVerdict data pipelines

Everything the addon knows about a specialization (Mythic+, Raid and PvP stat
targets, best-in-slot gear, ranked trinkets, stat priority and measured stat
weights) comes from the ClassCodex data below. The addon loads the generated
files from `StatVerdict/Data/Generated/` (see `StatVerdict/StatVerdict.toc`);
they are produced by GitHub Actions and must not be edited by hand.

## ClassCodex live data (stat priority, BiS gear, ranked trinkets, PvP)

**Source:** the same public build host the official Icy Veins / U.GG desktop
app itself updates from (`wow-class-codex.s3.us-east-1.amazonaws.com`) --
confirmed 2026-09-28 by reading that app's own local network log. No login,
no browser, no app required: plain HTTPS to a versioned build-manifest
system (`channels/.../config.json` -> `builds/.../manifest.json` -> the
files themselves, each checksum-verified against the manifest).

This replaces the abandoned `Scraper` repository, which pulled from a
third-party GitHub mirror (`Tharavol/ClassCodexContinued`) that mirror's own
README now says is frozen and stale -- confirmed live: it was missing
Critical Strike from Frost Death Knight's stat priority entirely, while this
source and the real installed addon both have it correctly.

- `tools/classcodex_fetch.py` -- fetches and checksum-verifies the four
  needed files (`db_ugg.lua`, `db_icyveins.lua`, `db_gamedata.lua`,
  `Shared/StatDR.lua`). Fails closed (raises `FetchFailure`) on any network,
  JSON, layout, or checksum problem rather than writing partial data.
- `tools/classcodex_lua_sandbox.py` -- hardened embedded-Lua execution for
  this third-party data (ported from the abandoned Scraper repo's
  already-security-reviewed sandbox: `os`/`io`/`load`-family globals
  removed, `python.eval` escape closed, Python-object attribute access
  denied at runtime construction).
- `tools/classcodex_build.py` -- merges the two sources per spec (u.gg is
  consistently the more granular of the two -- hero-talent-specific where
  IcyVeins only has "all" -- so it wins whenever both have a field;
  IcyVeins fills gaps). Deliberately excludes u.gg's flat `statTargets`
  (a generic number not derived from real gear) and `tierRank`
  (spec popularity/parse-rank, a different concern).
- `tools/classcodex_cli.py` -- fetches the live build and writes
  `StatVerdict/Data/Generated/SV_StatDR.lua` (the stat diminishing-returns
  module the addon loads); `--report` prints a per-spec source summary of the
  built data instead of writing. The per-spec data itself is not written as a
  file: the targets and weights pipelines below build it in memory.

## Stat targets and stat weights (what the addon reads)

- `tools/classcodex_targets.py` / `tools/classcodex_targets_cli.py` -- for
  every spec, goal (`MYTHIC_PLUS`, `RAID`, `PVP`) and hero talent, rebuilds
  the character-sheet stats of the ClassCodex BiS gear through
  SimulationCraft (`tools/simc_stat_engine.py`; specs SimC cannot model use a
  gear-only Wowhead fallback, `tools/wowhead_stat_engine.py`) and writes
  `SV_ClassCodexTargets.lua`: targets, BiS list, ranked trinkets and stat
  priority per spec/goal/hero talent. Each context also gets
  `targets.levels.hero` / `.champion`: the same loadout re-simulated at Hero
  and Champion 6/6, and the file root carries `trackSwap` (Myth/Hero bonus id
  -> Hero/Champion 6/6 bonus id) and `trackItemLevels`.
- `tools/upgrade_tracks.py` -- the upgrade tracks (Adventurer to Myth), their
  ranks and item levels from the game's DB2 tables on wago.tools, and the
  verified Myth -> Hero / Champion swap table used above.
- `tools/classcodex_weights.py` / `tools/classcodex_weights_cli.py` -- real
  SimC scale-factor stat weights per spec/goal/hero talent, normalised so the
  best secondary stat is 1.0, written to `SV_ClassCodexWeights.lua`. A missing
  combination makes the addon fall back to rank-position weights.
- `tools/spec_catalog.py` -- the 40 specializations (addon spec key, names,
  role, primary stat); `tools/lua_render.py` -- renders data as Lua.

Inside the addon, `StatVerdict/Core/SV_ProfileRepository.lua` is the only
reader of these files. It picks the player's hero tree by its subtree ID (a
fixed table in `SV_SpecMeta.lua`, from Blizzard's TraitSubTree data, since hero
tree names are translated on non-English clients), then by name, fails closed
on data older than 30 days (from the `buildId` time prefix), and never falls
back to another hero tree's data.

## Automation

- `.github/workflows/classcodex-live-refresh.yml` runs weekly and on manual
  dispatch: tests, StatDR, then the SimC stat targets. It commits
  only files that actually changed.
- `.github/workflows/classcodex-stat-weights.yml` runs on the 1st and 16th
  of each month (and on manual dispatch), sharded by role, and merges the
  shards into one weights file behind the same fail-closed write gate.

Run the tests locally with `python -m unittest discover -s tools/tests`
(`pip install lupa` so the addon Lua tests run instead of being skipped).
