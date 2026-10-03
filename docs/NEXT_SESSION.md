# StatVerdict — where we stand (written 2026-10-03). The ONLY notes file: replace it, never add another.

Read this first, then `git log --oneline -25`, then `StatVerdict/VERIFICATION.md` (the in-game checklist).
When this file is rewritten, delete what is no longer true. Release notes live in `docs/changelog/`, one file per version
(`<version>_<date>.md`; the one being prepared ends in `_pending`).

## Who and how (read twice)
- Owner: Gchris (GitHub `ElaNte75/StatVerdict`). A non-programmer product owner who reads on a phone, in Greek.
- **Every answer: short, simple Greek, no technical terms. KEEP IT SHORT.** The owner said (2026-10-03) that long analyses make him skim, and
  he already missed a warning that way. Put the one decision you need from him in its own short block, and lead with it.
  Give a confidence ("yes, about 80%") and where it may fail. Go deeper only when asked.
- Agree the "what" first; the "how" is yours. Never change UI or product logic beyond what was agreed. Nothing in the UI may move unasked.
- "StatVerdict" / "the addon" = only the WoW addon in `StatVerdict/`. `tools/`, `.github/`, `docs/` support it.
- He tests in the game and answers with screenshots. Be honest about anything not verified in the game; say so when a result rests on my reading of code.
- He prefers things explained by what he sees (tooltip lines, tabs), not by code. Show the expected result as a short text sample.

## How we work now
- We edit the addon **directly in the game folder** `D:\Battlenet Games\World of Warcraft\_retail_\Interface\AddOns\StatVerdict` (a copy, not a link).
  The owner presses a macro that does `/reload`. Changed file LIST (`.toc`) or NEW files (textures) need a full game restart.
- When the owner says it is good: copy the changed files into `C:\Users\ElaNte\Desktop\Projects\StatVerdict\StatVerdict`, run
  `python -m unittest discover -s tools/tests` (needs `pip install lupa`), commit with named files (never `git add -A`), push `main` and
  `main:main-myh77p`, wait for the Tests workflow. Keep the two copies identical (compare ignoring CR). Before copying anything from the game
  folder, `git pull` first: the weekly bot changes the version lines and the data file in the repo.
- Temporary diagnostics go in the game copy only, marked TEMP, and are removed before copying. A timer that wraps only our own `ns.*` functions
  found the freezes; `/run print(C_AddOnProfiler.GetAddOnMetric("StatVerdict", Enum.AddOnProfilerMetric.PeakTime))` gives the peak.
  **Never wrap or replace game functions** (it taints Blizzard code: a PersonalResourceDisplay error appeared).
- A debug WINDOW (an EditBox in a frame) is better than chat output: chat scrolls too fast to copy.
- CI runs Python 3.12; the PC runs 3.14. Do not use `Path.read_text(newline=...)` (3.13+). Files mix CRLF/LF: edit with byte-safe code.
  A copy into the project can fail once with "Permission denied" (a Windows lock); retry.
- The permission classifier once blocked a script that rewrote test files; the owner said go and it passed. Do not work around a block: ask.

## Release state and versions
- **1.1.0 is on CurseForge** (old numbering). The owner uploads by hand: `StatVerdict Ship (no bump).bat` builds `StatVerdict-<version>.zip` on his Desktop
  (it is built from the PROJECT folder, so the copies must match). `StatVerdict Ship.bat` also bumps the version: do not use it any more.
- **Version scheme (owner's rule): `MAJOR.MINOR.WEEK`.** A data-only release changes only WEEK (weeks turn over on Wednesday, the weekly reset;
  a missed week is skipped in the number). A functional change raises MINOR (a big one raises MAJOR and zeroes MINOR). New year: WEEK restarts
  at 1 and MINOR goes up by one, so the version never goes backwards. Published versions keep their numbers.
- **The repo is at 1.1.1 (pending, not uploaded).** It has functional changes, so at upload time it becomes `1.2.<week>`: rename the toc `## Version`,
  `ns.VERSION` in `StatVerdict.lua`, the `(vX.Y.Z)` in `StatVerdict/STORE.md` line 1, and `docs/changelog/1.1.1_pending.md` to
  `<version>_<upload date>.md` (git mv). The owner says "ετοιμάζω την 1.1.1" -> do that, check the two copies match, push.
- **Every Wednesday ~15:00 Greek time** `.github/workflows/classcodex-live-refresh.yml` refreshes the guide data and, when it changed, runs
  `tools/release_prep.py` (bumps WEEK, writes the changelog file) and opens a GitHub issue ("Ώρα για ανέβασμα ...") that GitHub mails to the owner.
  While a `_pending` release exists it only adds a data line to it. It never publishes. Issue #1 is open: it waits for the 1.1.1 upload.
- The data pipeline now refuses to write targets without the upgrade-track tables (`--allow-missing-track-levels` overrides) and retries the
  fetch 4 times. Reason: one wago.tools timeout once produced data without `trackSwap`, and Best in Slot showed Myth items for every tier.
  The data root now also carries `trackTop` (the 6/6 bonus id of each track).
- GitHub e-mail: only failed workflows (set by the owner). Do not add experiment workflows.

## What 1.1.1 contains (see `docs/changelog/1.1.1_pending.md`, also in `StatVerdict/STORE.md`)
Fixed: vanished gear leaves saved loadouts (NOT verified in game); Adventure Guide tab flicker (GameTooltip click hook removed: it stole the mouse);
freezes when equipping, opening the window, or inspecting (evaluation contexts built once per scan / per game frame);
"10+ item levels always wins" now also when the points are small. New: `/sv ag`, `/sv mouse`; stat ranks on item tooltips; one full-width title chip on
every tab; Best in Slot / Ranked Trinkets follow the shown tier incl. trinkets listed without bonus ids and "Other source"; Catalyst handling; Alt build switch.

## Tooltip behaviour built on 2026-10-02/03 (all in `UI/SV_Tooltip.lua`, `UI/SV_Render.lua`, `Core/SV_ItemReferenceBonuses.lua`)
- **Stat ranks:** `+73 Critical Strike #1 [MS]`: gold number, then a gold MS/OS picture (`Textures/StatRankMS|OS.tga`, size 8x16 in `LABEL_SIZE`).
  Equal stats (guide "equal groups") share the same number. Switch: Features > "Stat Ranks on tooltips" (`StatVerdictDB.showStatRanks`).
  Not drawn in combat. The comparison block "If you replace this item..." is skipped. Matching uses the game's own stat words (works in every language).
- **Which build:** the one selected in the window (Main/Off). **Alt held shows the other build** (ranks AND the whole verdict block), only when an Off Spec is set.
  One grey line "Also an upgrade for <spec> (hold Alt)" when the other build gains too. `RefreshData` redraws on Alt press/release (MODIFIER_STATE_CHANGED).
- **Catalyst:** the item is judged as it is (the +100 is NOT in its points; converting costs a scarce Spark). Under the verdict: "Best in Slot after the
  Catalyst" (light blue) when the set piece, judged with its real stats at the item's own item level, comes out better, else "Not better after the
  Catalyst"; then "Hold Ctrl to preview". **Ctrl held swaps the tooltip for the set piece** (same item string, set piece id), nothing about saving is offered
  there; Ctrl up puts the item back. Shift is the game's own comparison and Alt is ours for the build: do not reuse them. Appears only when the BiS piece of
  that slot is a set piece, the item has an upgrade track, and is not itself the BiS piece. It is inside the verdict block, so it needs the item to be an
  upgrade as it is. **The Ctrl preview was reported working; the "no save in preview" and "Alt build verdict" changes are not yet confirmed by the owner.**
- **Pitfall found:** the verdict block is skipped when the tooltip "already has a StatVerdict line" (`TooltipAlreadyHasStatVerdict`). Texture escapes
  hold the folder name `StatVerdict` in their path, so that check now strips `|T...|t` first. Any text we add to a tooltip must be checked against it.

## Unpushed local work (push when the owner says OK, or now: push to main is pre-authorised)
Commits after `f2629df` (origin/main when this was written): Catalyst on Shift then Ctrl; no saving in preview; Alt shows the other build's verdict.
Tests: 591 pass. The weekly bot may have added data/version commits on origin: `git pull --rebase` first.

## Waiting for the owner's answer
1. **Key hints** ("yes" given in principle, not yet built): Features row label `Stat Ranks (Alt: other build)` and a short "Tooltip keys" section in the
   Manual (Alt = other build; Ctrl = Catalyst preview). Mind the Features geometry tests (nothing may move; the label must fit).
2. **Features tab beautification** is the next job the owner asked for (he finds it plain). Ask what looks ugly (frames, spacing, colours) first.
3. `StatVerdict/STORE.md` still holds a copy of the 1.1.1 changelog next to `docs/changelog/`: remove it from STORE.md so there is one source? (asked, no answer)
4. Delete the old remote branch `worktree-keylevel-bracket-benchmarks` (16 commits not in main, old Mythic+ benchmark work)? (asked, no answer)
5. Items showing a wrong item level: ask for the item name and the tier selected; trinkets without track info borrow ids from another list, else
   dungeon/raid drops get the shown tier's 6/6 id (`Repository.GetKnownBonusIDs`, `GetTrackTopBonusID`); crafted/vendor/event/PvP say "Other source".

## Tooling that stays (feeds the addon)
- `tools/classcodex_*.py`, `spec_catalog.py`, `simc_stat_engine.py`, `wowhead_stat_engine.py`, `upgrade_tracks.py`, `lua_render.py`: the weekly data pipeline
  (`tools/README.md` explains it). `tools/release_prep.py`: the weekly version/changelog/issue step (tests in `test_release_prep.py`).
- `tools/item_sources.py`, `tools/blizzard_item_pool.py`, `tools/data/blizzard_item_pool.json`: the "Where to find" data (run by hand, needs Blizzard keys from the environment).
- `tools/item_check_verdict.py`: despite the name, the harness that loads the whole addon in lupa for the scoring and tooltip tests.
- `tools/method_guides.py`, `method_targets.py`, `tools/data/method/`: Method as a second guide source (below).
- `.github/workflows/tests.yml`, `tools/tests/` (591 tests). Test pitfalls: lupa makes a new Python wrapper for every Lua table read (use `rawequal`);
  the shared `verdict.CHARACTER` dict must be restored after a test changes it; `FRAME_STUB` frames keep old anchors after `ClearAllPoints`.

## Guardrails (the owner's rules)
- The Guide is a 1:1 copy of the guides, never tuned. Sources may be named only in the single line "All guide information comes from Icy Veins and u.gg."
  (`Core/SV_WeightModes.lua`; test `NoDataSourceNamesShownTests`). A new source must be copied 1:1 and labelled as that source's own method.
- Never hand-edit `StatVerdict/Data/Generated/*.lua` (the weekly workflow regenerates it). Never weaken the geometry, "nothing moves" or real-data tests.
- Never commit secrets (Blizzard credentials only from the environment). Replaced features and data are deleted completely, never left commented out.
- Commits end with the co-author line the session gives. Pushes to `main` and `main-myh77p` are pre-authorised (inform, do not ask). No PRs unless asked.
- Do not publish or upload anything for the owner; he uploads to CurseForge himself.

## Longer-term ideas (not started)
- **Method (method.gg) as a second guide source.** Each source 1:1, labelled as that source's own method. Method allows reading (robots.txt) but forbids copying
  prose, so facts only. Murlok (murlok.io, real rating targets) is the next candidate; Wowhead blocks AI crawlers. `method_guides.py` reads all 39 specs
  (stat priority per hero tree, Best in Slot, enchants, gems); `method_targets.py` adds up the listed set with SimC. Known gaps: 17 specs `incomplete`
  (enchants as prose), some weapon slot names, Feral empty rows. Plan: fix gaps, add Method to the Guide drawer (single target, no tiers), verify.
- **Tank simulation (on hold).** Own DPS simulation is not worth it (gain at most 4-5%). For tanks the guide's Damage priority is within ~1% of the best-DPS
  split while 13-20% less damage taken was available at 4-6% less DPS (SimC estimate). Any future UI must say "our own simulation estimate", never mixed with the Guide.
- Possible later: show the Catalyst information also for items that are not an upgrade as they are (today it lives inside the verdict block).
- Owner housekeeping: old GitHub repos `Scraper` and `farmerassistant` can be deleted on GitHub; CurseForge cloud credits ($100) expire 2026-11-05.
