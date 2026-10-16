# StatVerdict data pipelines

Everything the addon knows about a specialization (Overall, Mythic+, Raid and PvP stat
targets, best-in-slot gear, ranked trinkets and stat priority) comes from the ClassCodex data below. The addon loads the generated
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
  file: the targets pipeline below builds it in memory.

## Stat targets (what the addon reads)

- `tools/classcodex_targets.py` / `tools/classcodex_targets_cli.py` -- for
  every spec, goal (`OVERALL`, `MYTHIC_PLUS`, `RAID`, `PVP`) and hero tree, takes the guide's Best in Slot list
  (Icy Veins for the PvE goals, u.gg for PvP), moves every piece to its top level, adds up the stats of the pieces with
  the recommended gems and enchants (item tooltips from Wowhead, `tools/wowhead_stat_engine.py`) and adds the fixed
  rating the spec has without gear (`tools/data/spec_base_stats.json`). Myth 6/6 gives `targets.statTargets`,
  Hero and Champion 6/6 give `targets.levels.hero` / `.champion` (PvP gear has no upgrade levels, so no levels). It
  writes `SV_ClassCodexTargets.lua`: targets, BiS list, ranked trinkets and stat order per spec/goal/hero tree, and
  at the file root `trackSwap` (bonus id -> the 6/6 bonus id of a track), `trackTop`, `trackRanks` and
  `trackItemLevels`. No simulation: the targets are plain sums, so they are exact for the list and carry no race, food
  or buffs.
- `tools/classcodex_carryover.py` -- the weekly safety net: a part (Best in Slot list, trinkets, stat order, targets) of a
  context that is missing or unusable in the new data is taken from the previous file, up to 30 days old, and the
  context says where from (`carried`); the run writes nothing when more than a quarter of the contexts needed it.
- `tools/upgrade_tracks.py` -- the upgrade tracks (Adventurer to Myth), their
  ranks and item levels from the game's DB2 tables on wago.tools, and the
  verified Myth -> Hero / Champion swap table used above.
- `tools/item_sources.py` -- writes `SV_ItemSources.lua` (where each item drops: dungeon or raid and boss) from the
  Adventure Journal pool `tools/data/blizzard_item_pool.json` (refreshed with `tools/blizzard_item_pool.py`, which needs
  Blizzard API credentials from the environment); the tooltips' "Where to find" lines read it. Items the journal
  does not list get no line.
- `tools/spec_catalog.py` -- the 40 specializations (addon spec key, names,
  role, primary stat); `tools/lua_render.py` -- renders data as Lua.
- `tools/addon_harness.py` -- loads the whole addon in Lua; the scoring tests build on it.

Inside the addon, `StatVerdict/Core/SV_ProfileRepository.lua` is the only
reader of these files. It picks the player's hero tree by its subtree ID (a
fixed table in `SV_SpecMeta.lua`, from Blizzard's TraitSubTree data, since hero
tree names are translated on non-English clients), then by name, fails closed
on data older than 60 days (from the `buildId` time prefix), and never falls
back to another hero tree's data.

## Automation

- `.github/workflows/classcodex-live-refresh.yml` runs weekly and on manual
  dispatch: tests, StatDR, then the stat targets (a lookup of about 3000 pieces, roughly 20 minutes). It commits
  only files that actually changed, with what it carried over from last week in the commit text.

Run the tests locally with `python -m unittest discover -s tools/tests`
(`pip install lupa` so the addon Lua tests run instead of being skipped).
