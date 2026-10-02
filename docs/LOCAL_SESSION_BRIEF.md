# StatVerdict — brief for a new local session (written 2026-10-02)

Read this first, then `docs/HANDOFF.md` (older, detailed notes) and `StatVerdict/VERIFICATION.md` (in-game checklist).

## Who and how
- Owner: Gchris (GitHub `ElaNte75/StatVerdict`). A **non-programmer product owner**, reads on a phone, Greek speaker.
- **Standing rule: every answer in short, simple Greek, no technical terms.** Give confidence ("ναι, περίπου 80%") and say where it may fail. Go deeper only when asked.
- "StatVerdict" / "το πρόσθετο" = only the WoW addon in `StatVerdict/`. Everything in `tools/`, `docs/`, `.github/` is research/tooling around it.
- The addon is tested by the owner **in game**; he reports back with screenshots/videos.

## Guardrails (the owner's rules)
- Guide = **1:1 copy** of guides, never tuned. Sources shown in the UI only via the single line "All guide information comes from Icy Veins and u.gg." (`Core/SV_WeightModes.lua`; test `NoDataSourceNamesShownTests`). A new source (see Method below) must be copied 1:1 and labelled as that source's own method.
- Never hand-edit `StatVerdict/Data/Generated/*.lua` (regenerate with tools/workflows). Never weaken geometry/real-data tests.
- Nothing in the UI may move except what the owner asks.
- **Run all tests before every push:** `python -m unittest discover -s tools/tests` (560 tests, ~7 s; needs `pip install lupa`).
- Never commit secrets (Blizzard Client ID/Secret were once pasted in chat; credentials only from env `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET`).
- Do **not** `git add -A` blindly: once two 77 MB Python wheels were committed by accident (removed in the next commit but they stay in history).
- Commit messages end with `Co-Authored-By: Claude ... <noreply@anthropic.com>` (use the attribution the session gives). Do not create PRs unless asked.

## Release state
- **1.1.0 is published on CurseForge.** The owner uploads manually (`StatVerdict Ship (no bump).bat` builds the zip on his Desktop; it keeps the version).
- **Version in the repo is 1.1.1** (toc, `ns.VERSION`, `STORE.md` header, a test checks they match). Planned upload: **next Wednesday**, one batch of fixes, so users are not pestered with updates. Everything fixed from now on goes into 1.1.1; keep the 1.1.1 changelog in `StatVerdict/STORE.md` up to date.
- Changelog 1.1.1 so far: vanished gear leaves saved loadouts; `/sv ag`; `/sv mouse`.
- Working branch `main-myh77p`; pushes go to both `main` and `main-myh77p`.
- `Update StatVerdict (pull and link).bat` (repo root): `git pull` + links `D:\Battlenet Games\World of Warcraft\_retail_\Interface\AddOns\StatVerdict` to the project folder, so only `/reload` is needed. A local session can simply edit the project folder directly and the owner reloads.

## What the addon does (short)
Bag/tooltip upgrade verdicts for Main Spec and Off Spec from a heuristic score; Guide drawer (Auto / Tier 1-3 stat-target tiers, per spec), Best in Slot + ranked trinkets that follow the tier, "Where to find" lines, Features drawer. Data comes from `Data/Generated/*` (ClassCodex = Icy Veins + u.gg; refreshed weekly by `.github/workflows/classcodex-live-refresh.yml`).

## Open problems (need work)
1. **Adventure Guide tab flicker / blocked clicks (reported, not solved).** Hovering a not-selected tab of an instance page (Overview / Loot / ...) makes its tooltip blink on/off and the tab hard to click, looking faded "like a layer on top". Videos show it clearly with the addon on and **not at all with the addon disabled**. `/sv ag` + `/reload` (marks off) made it less frequent but not gone, so a second cause exists in StatVerdict. Static code review found nothing: indicators are textures/fontstrings (click-through); AG scan in `UI/SV_AdventureGuideIndicatorSource.lua` walks the whole EncounterJournal frame tree and requests item data; `UI/SV_UpgradeIndicatorView.lua` reacts to GET_ITEM_INFO_RECEIVED with a full refresh. **Next step: `/sv mouse`** (8 s list of frames under the mouse; just fixed a bug in it) while hovering the tab, or Blizzard's `/fstack`. Also try bisecting by disabling parts (quest source, merchant source, tooltip post-call).
2. **Vanished gear (new in 1.1.1, NOT verified in game).** `ns.PruneVanishedLoadoutItems` in `Core/SV_SpecSnapshot.lua`: items of a saved loadout (not the active spec) that are no longer owned are removed after two looks 3 s apart, slot falls back to the worn item, chat message, buyback within 10 min restores. Checklist in `VERIFICATION.md`. Known risk: items only in the warband bank before it is loaded. Tests: `tools/tests/test_loadout_vanish.py`.
3. Reported but explained: StatVerdict memory ~8 MB is normal; "AddonCompartment attempt to call a nil value" is probably another addon (Class Codex disabled but not reloaded).

## Research / tooling state (the "clutter" — candidates to delete or archive)
The owner finds many of these tools clutter and wants a cleanup later. Suggested triage:
- **Keep (feed the addon):** `tools/classcodex_*.py`, `tools/upgrade_tracks.py`, `tools/item_sources.py`, `tools/blizzard_item_pool.py`, `tools/lua_render.py`, `tools/spec_catalog.py`, `tools/simc_stat_engine.py`, `.github/workflows/classcodex-live-refresh.yml`, `tools/tests/`.
- **Keep, new, not yet in the addon:** `tools/method_guides.py` + `tools/method_targets.py` + `tools/data/method/*` (see below).
- **Research only (candidates to remove/archive):** `tools/gear_search.py`, `stat_split_probe.py`, `tank_survival_probe.py`, `guide_lean_probe.py`, `item_check*.py`, `wowhead_stat_engine.py`, `guide_fidelity_check.py`, `classcodex_weights.py`; `.github/workflows/guide-lean-probe.yml`, `item-check.yml`; most of `docs/` result files (`gear-search*`, `stat-split-probe*`, `tank-survival-probe*`, `item-check/`, reports). Check `tools/tests` for tests that import them before deleting.
- Removed already: Measured mode, gear levels, `/svweights`, ClassCodex weights data/workflow.

## Method (method.gg) as a second guide source — in progress
- Why: players follow different camps (Icy Veins, Method, ...). Owner's rule: present each source's method **1:1**, labelled as that source's (e.g. Murlok = "from the top 50 players", not a simulation).
- Research in `docs/guide-source-research.md`: Method allowed by robots.txt (terms forbid copying prose → facts only); Murlok (murlok.io) = second candidate (has real rating targets); **Wowhead blocks AI crawlers → skip**. Method has **no PvP** WoW gear guides.
- `tools/method_guides.py` reads all 39 specs: stat priority (variants per hero tree; free text, parser tolerant but fragile), Best in Slot tabs overall/raid/mythic_plus (item ids, notes, sources), enchants, gems, rating ranges where given (only Shadow Priest). Output `tools/data/method/<slug>.json`.
- `tools/method_targets.py` adds up the listed set with SimC's stat sheet (item level 334, one unique Diamond, secondary gem only in real sockets, enchants only on slots that take them, first of "A or B") → `<slug>-targets.json`. Healers: stat sheet read with another spec of the class.
- **Known gaps:** 17 specs have `incomplete` (enchants written as prose, ring enchant not read); some weapon slot names unrecognised ("Mainhand", "Two-Hand", "Alt. Main Hand"); Feral page has empty rows; head enchants untranslated (leech, no secondary rating).
- **Not in the addon yet.** Plan: fix the gaps, then add Method as a second source in the Guide drawer (single target, no tiers, labelled "from Method's Best in Slot"), verified from several sides before release.

## Tank simulation project (own results) — on hold
- Owner agreed: **DPS own simulation is not worth it** (gain ≤ 4-5%). The tank idea may be worth it: guide's Damage priority for Guardian/Brewmaster/Prot Paladin is within ~1% of the best-DPS split, while ~13-20% less damage taken was available at ~4-6% less DPS (SimC estimate; mastery/Blood Shield over-rewarded in the dtps metric). Results in GitHub Actions artifacts of the "Guide lean probe" run.
- Second survival metric (damage taken minus own healing) exists in `gear_search.py`; deaths are always 0 (unusable). Not integrated; any future UI option must be labelled "our own simulation estimate" and never mixed into Guide.

## Useful commands
- Tests: `python -m unittest discover -s tools/tests`
- SimC build (local, for research): see `.github/workflows/item-check.yml` (clones simulationcraft/simc `midnight`, cmake). GitHub Actions runners are far faster than a 4-core container.
- In game: `/sva` window, `/sv help`, `/sv ag`, `/sv mouse`.
