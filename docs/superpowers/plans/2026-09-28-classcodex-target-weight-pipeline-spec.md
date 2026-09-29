# ClassCodex Target & Stat-Weight Pipeline — Spec

## Background

StatVerdict scores a candidate item against the player's current gear using
per-goal (Mythic+/Raid/PvP) stat targets, best-in-slot references, ranked
trinkets, and a secondary-stat priority order. Historically all of this came
from Raider.IO leaderboard runs (Mythic+ only; Raid/PvP had no live source at
all).

2026-09-28: the project pivoted away from Raider.IO entirely. Rationale
(agreed, not to be re-litigated): a top-ranked player's gear reflects skill as
much as correct stat choices — "being #1 doesn't mean the stats are right." A
same-day spike proved this in practice: SimulationCraft's own scale-factor
calculation for Frost DK showed Mastery beating Versatility per point even
though Mastery was deep in diminishing returns and Versatility had almost
none — a plausible-sounding "prefer the stat with less DR" heuristic is wrong,
and raw priority order without a measured per-point value is not sufficient
either.

**Goal set:** MYTHIC_PLUS, RAID, PVP. A fourth "Casual" goal (Delves/Leveling)
was considered 2026-09-28 and dropped: ClassCodex's live data has talent
builds for those contexts but no gear/statPriority/trinkets data, so there is
nothing to build a goal from. Revisit only if ClassCodex ever adds that data.

## Agreed method (per goal, per spec, per hero-talent variant)

1. Take best-in-slot gear for that goal/spec/hero-talent from the already-live
   ClassCodex data (`tools/classcodex_build.py`'s `gear` field — already
   fetched weekly, already ugg-preferred/icyveins-fallback merged).
2. Reconstruct the resulting real stat totals from that exact gear via
   SimulationCraft (`tools/simc_stat_engine.py`, already built and proven for
   this exact "reconstruct paper-doll stats from an exact loadout" job,
   currently used for Raider.IO gear — works identically for BiS-list gear).
   This becomes the numeric stat target (replaces Raider.IO's role).
3. Separately, via SimC's own `calculate_scale_factors=1` mode (not gear
   reconstruction — a different sim run), compute the **true per-point value**
   of each secondary stat for that spec/goal/hero-talent. This replaces the
   addon's current `secondaryWeights` scoring, which only knows priority
   *rank position* (`secondaryWeights[1]`, `[2]`, ...), not a measured
   magnitude. Different per goal (e.g. Crit can matter more in Raid than
   Mythic+), matching that ClassCodex already ships separate priority lists
   per context.
4. Diminishing returns: `Shared/StatDR.lua` (already fetched weekly) is a
   live, in-game rating→percent calculation module (not static data) — it
   gets vendored into the addon as real Lua source, refreshed weekly like the
   other ClassCodex data. Applying it during scoring is **out of scope for
   this plan** (that is addon-side wiring, a later plan); this plan only
   needs to ship the vendored file.
5. Candidate-vs-current-gear comparison using steps 2-4's numbers is also
   addon-side wiring — **out of scope for this plan**.

**Cadence:** step 1's ClassCodex fetch stays weekly (already running,
`.github/workflows/classcodex-live-refresh.yml`). Step 3 (the per-point
weight simulation) only needs to rerun roughly every 15 days (game-balance
changes are infrequent) — its own GitHub Actions workflow, fully unattended,
no time limit per run.

## What this plan produces

Pure data-pipeline output — no addon runtime behavior changes, nothing wired
into `SV_ProfileRepository.lua` or `SV_ItemReferenceBonuses.lua` yet. That
wiring is a **separate, later plan**, written once this plan's real generated
output has been inspected (exact JSON shapes for SimC's scale-factor report,
ClassCodex's per-spec hero-talent key set, etc. are confirmed against live
data rather than assumed up front).

Three generated files, all under `StatVerdict/Data/Generated/`, all refreshed
by GitHub Actions and committed the same way `SV_ClassCodexLiveData.lua`
already is:

- `SV_ClassCodexTargets.lua` — per spec/goal/hero-talent: reconstructed stat
  targets, BiS item list, ranked trinkets, and priority order/tiers, in the
  same field shape (`targets`, `bis`, `trinkets`, `priorityProfiles`) that
  `SV_ProfileRepository.lua` already knows how to validate and consume for
  Mythic+ today (see `Repository.ValidateGeneratedContext`,
  `Repository.GetPriority` in `StatVerdict/Core/SV_ProfileRepository.lua`) —
  reusing that shape is deliberate, it is what makes the later wiring plan
  small. Weekly cadence, folds into the existing
  `classcodex-live-refresh.yml` workflow (which needs a SimC build step
  added, following the pattern already proven in
  `.github/workflows/weekly-benchmarks.yml`).
- `SV_ClassCodexWeights.lua` — per spec/goal/hero-talent: real per-secondary
  -stat weights from SimC's scale-factor mode. New workflow,
  `classcodex-stat-weights.yml`, cron roughly every 15 days plus manual
  dispatch.
- `SV_StatDR.lua` — `Shared/StatDR.lua`'s raw Lua source, vendored near
  verbatim (it defines real functions, so it must ship as actual Lua source,
  not be round-tripped through the JSON-shaped `to_lua()` serializer that
  the other generated files use — that would silently drop every function
  and keep only inert data). Weekly cadence, folds into the existing
  `classcodex-live-refresh.yml` run.

## Key data shapes already confirmed live (2026-09-28, build
`20260928064230-9b041a5-43564495`)

- `gear` (from `classcodex_build.build()`'s per-spec `gear` field `.value`):
  `{heroTalentKey: {contextKey: [itemEntry, ...]}}`. `contextKey` seen:
  `"all"`, `"mplus"`, `"raid"`, `"pvp"` — not every spec/source has every
  context (icyveins commonly lacks `"pvp"`; ugg commonly lacks `"all"`).
  `itemEntry`: `{itemId, slot="Head"|"Neck"|"Shoulders"|"Back"|"Chest"|
  "Wrist"|"Hands"|"Waist"|"Legs"|"Feet"|"Finger 1"|"Finger 2"|"Trinket 1"|
  "Trinket 2"|"Main Hand"|"Off Hand", bonusIDs=[...], ilvl=<int, ugg only>,
  catalyst={bonusIDs,itemId} (optional), source="<flavor text>"}`.
- `talents` (same per-spec shape family): `{heroTalentKey: {contextKey:
  [{export="<SimC talent string>", label, recommended=true|nil, labels=[...],
  tags=[...]}, ...]}}`. Contexts seen: `"delve"`, `"mplus"`, `"pvp"`,
  `"raid"`, `"leveling"` (the last two we do not need `"leveling"`/`"delve"`
  for the 3-goal set — see Background).
- `trinkets`: `{heroTalentKey: {contextKey: [{itemId, bonusIDs=[...]?,
  tier="S"|"A"|"B"|"C"|"D"}, ...]}}` — tier already assigned by ClassCodex,
  no popularity-threshold computation needed (unlike the old Raider.IO
  pipeline's `tools/addon_benchmarks.py::rank_trinkets`).
- `statPriority`: `{heroTalentKey: {contextKey: {secondary=[[stat,...],
  [stat,...], ...]}}}` — the outer list is already priority order, each
  inner list is a tie group (matches `priorityProfiles[].tiers` /
  `.order` in the addon's existing contract directly — no re-derivation of
  tiers needed, unlike `tools/addon_benchmarks.py::order_and_tiers`).
- `db_gamedata.lua` has no item names (only recipe/enchant ID lookups) — the
  generated files will carry `item_id` only; item display names are resolved
  addon-side from the item link (standard WoW UI capability), not baked into
  generated data.
- `Shared/StatDR.lua`: pure Lua, `local _, ns = ...` then `ns.StatDR = {}`
  plus three functions (`RawPercentFor`, `GoalPercent`, `TargetPercent`); no
  dependency on any other ClassCodex file.

## Explicitly out of scope for this plan

- Anything under `StatVerdict/Core/*.lua` or `StatVerdict/UI/*.lua` (addon
  runtime wiring) — next plan, after this one's real output is inspected.
- Removing the Raider.IO pipeline (`weekly-benchmarks.yml`,
  `tools/live_benchmark_engine.py`, `tools/addon_benchmarks.py`) — stays
  until the replacement is wired in and verified in-game (user's own
  standing rule, see memory `remove-superseded-code-completely`).
- Applying `StatDR.lua`'s diminishing-returns math anywhere — this plan only
  vendors the file.
