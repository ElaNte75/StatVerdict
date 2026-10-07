# StatVerdict — where we stand (written 2026-10-05, version 2.0.40). The ONLY notes file: replace it, never add another.

Read this first, then `git log --oneline -25`, then `StatVerdict/VERIFICATION.md` (the in-game checklist).
When this file is rewritten, delete what is no longer true. Release notes live in `docs/changelog/`, one file per version
(`<version>_<date>.md`; one being prepared ends in `_pending`).

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
- The repo `C:\Users\ElaNte\Desktop\Projects\StatVerdict_Addon` is the one place to edit. The game folder
  `D:\Battlenet Games\World of Warcraft\_retail_\Interface\AddOns\StatVerdict` is a COPY the owner tests in: after every change copy the changed
  files there (compare ignoring CR; `diff -rq --strip-trailing-cr StatVerdict "<game folder>"`). The owner presses a macro that does `/reload`.
  Changed file LIST (`.toc`) or NEW files (textures) need a full game restart.
- When the owner says it is good: run `python -m unittest discover -s tools/tests` (needs `pip install lupa`), commit with named files (never
  `git add -A`), `git pull --rebase` first (the weekly bot changes the version lines and the data file), push `main` and `main:main-myh77p`, wait for the
  Tests workflow. His own wording: he says "ok" when something is good; do not commit before he does.
- Temporary diagnostics go in the game copy only, marked TEMP, and are removed before copying. **Never wrap or replace game functions** (it taints
  Blizzard code). A debug WINDOW (an EditBox in a frame) is better than chat output.
- CI runs Python 3.12; the PC runs 3.14. Do not use `Path.read_text(newline=...)` (3.13+). Files mix CRLF/LF: edit with byte-safe code (read bytes,
  replace `\r\n`, write back). In this shell a Python string with a backslash-n written through a heredoc can turn into a real newline: write scripts
  to a file or build the escape with `chr(92)`. The lupa test harness (`FRAME_STUB` in `tools/tests/test_addon_lua.py`) returns the object itself for
  any PascalCase method it does not know and records some setters (`_width`, `_height`, `points`, `_color`, `_font`, `_parent`, `_scale`, `_strata`...);
  `ClearAllPoints` does NOT clear `points` there, so look at the last point. A fake frame in a test often needs its own `GetPoint`/`GetWidth`.
- The permission classifier once blocked a script that rewrote test files; the owner said go and it passed. Do not work around a block: ask.

## Release state and versions
- **Version scheme (owner's rule): `MAJOR.MINOR.WEEK`.** A data-only release changes only WEEK (weeks turn over on Wednesday, the weekly reset, see
  `tools/release_prep.py: reset_week`; a missed week is skipped in the number). A functional change raises MINOR (a big one raises MAJOR and zeroes
  MINOR). New year: WEEK restarts at 1 and MINOR goes up by one. Published versions keep their numbers.
- **The repo is at 2.0.40 (2026-10-05, a Monday, so week 40; Wednesday 2026-10-07 starts week 41), not yet on CurseForge** (1.1.0 is). The changelog is
  `docs/changelog/2.0.40_2026-10-05.md` (also pasted in `StatVerdict/STORE.md`). The owner uploads by hand: `StatVerdict Ship (no bump).bat` builds
  `StatVerdict-<version>.zip` on his Desktop from the repo's `StatVerdict` folder. `StatVerdict Ship.bat` also bumps the version: do not use it.
  Bump helper: `release_prep.write_version(root, version, date)` sets the toc, `ns.VERSION`, `ns.RELEASE_DATE` and the `(vX.Y.Z)` in STORE.md.
- **Every Wednesday ~15:00 Greek time** `.github/workflows/classcodex-live-refresh.yml` refreshes the guide data and, when it changed, runs
  `tools/release_prep.py` (bumps WEEK, writes the changelog file) and opens a GitHub issue ("Ώρα για ανέβασμα ...") that GitHub mails to the owner.
  **The repo is now at 2.1.41 with `docs/changelog/2.1.41_pending.md`** (the Alt / Catalyst work below, committed 2026-10-07; owner decides when to upload;
  the bot only adds its data line to a pending file). If 2.0.40 was never uploaded, its changelog text (and STORE.md) still describes the old Alt switch: ask.
  Weekly time moved to 09:00 UTC (12:00 Greek summer time). It never publishes. GitHub issue #1 ("waits for the 1.1.1 upload") may still be open: the owner can close it after uploading.
- The data pipeline refuses to write targets without the upgrade-track tables (`--allow-missing-track-levels` overrides) and retries the fetch 4 times.
  The data root also carries `trackTop` (the 6/6 bonus id of each track) and `trackRanks` (every rank 1..6: `{bonus id, item level}`, from
  `upgrade_tracks.build_track_swap(...).ranks`; the 2026-10-07 data file got it by hand, the next bot run writes it itself).
- GitHub e-mail: only failed workflows (set by the owner). Do not add experiment workflows.

## What 2.0.40 contains (the changelog file has the full text)
Fixed: vanished gear leaves saved loadouts (NOT verified in game); Adventure Guide tab flicker; freezes when equipping, opening the window, inspecting;
"10+ item levels always wins" also when the points are small; Best in Slot / Ranked Trinkets follow the shown tier. **The window now looks the same for every
player** (see below). New: `/sv ag`, `/sv mouse`; stat ranks on tooltips; Alt = other build, Ctrl = Catalyst preview; marked pieces put on at respec; the
Features tab became **Options** with a new look, **Always on top**, **Compact Mode**, **Auto-hide the left side**, **Window size**, the Manual's **Text size**.

## How the window works now (built 2026-10-05, all verified in the game by the owner except where noted)
- **Layout seed.** A fresh install used to get a window 50 units shorter than the owner's (old seed in `UI/SV_LayoutOffsets.lua`, 67 keys, against his 135).
  Now `layoutSeedVersion = 2`: once per player `devDashboardOffsets` (`DEFAULT_DASHBOARD_OFFSETS`, 105 keys), `statAuditLayout` (`DEFAULT_STAT_AUDIT_LAYOUT`) and
  `specTitleFontSize = 13` are replaced by the owner's tuned values, and the leftovers of the removed AdvDev dev tools are deleted from the saved file
  (`LEFTOVER_DEV_KEYS`). Window position, builds and every other setting are not touched. The AdvDev tools no longer exist; nothing writes those keys any more.
- **Always on top** (`ns.ApplyAlwaysOnTop`, `UI/SV_WindowChrome.lua`): off by default. Off = the window is in front (strata HIGH) while the player works in it and
  goes to BACKGROUND on any click elsewhere (`GLOBAL_MOUSE_DOWN`); a click on it, on a panel window of its own, or on an object marked `svOwnedWindow`
  (dropdown menus, blocker) brings it back. On = HIGH always. Other add-ons on higher layers (Liatrix...) cannot be covered, deliberately: going higher would
  cover the game's own pop-ups.
- **Options drawer** (`UI/SV_OptionsDrawerPanel.lua`): four dark cards (WINDOW, BAG ITEMS AND TOOLTIPS, BEST IN SLOT, RANKED TRINKETS), a switch per row (gold
  on), a grey line under rows that need one, a scroll frame; 320 wide for everyone (the old saved -69 narrowing was dropped). Child choices (Gems and
  enchants, Trinket effect, Auto-hide) hang from a gold line; Auto-hide is locked and shown unticked while Compact Mode is off (its saved choice is kept).
  The switch rows keep an invisible `CheckButton` per choice (`bagIndicatorChecks[key]`, `svRow`, `svSelected`, `svLocked`): tests rely on that.
- **Compact Mode** (`compactMode`, off by default; `Layout.IsCompact()` in `UI/SV_DashboardLayout.lua`): one stat table at a time (`Layout.CompactView()`),
  the Show Off Spec / Show Main Spec button under the dropdowns, the four panel buttons in one row inside the stats card, no Manual button (Options has
  a Manual button), window 281 high instead of 449, headings of the build in view gold, no checkbox in the spec titles. The Off table takes the Main table's
  place AND its inner offset (`ApplyCompactViews`), so nothing jumps. The Main title is hidden in the Off view and shown again next pass.
- **Panels in Compact Mode are windows of their own** (`Layout.AnchorFloatingPanel`): children of `UIParent`, top level, same strata and scale as the main
  window (`ns.SyncFloatingPanelStrata`), hidden with it, draggable, saved position `floatingPanelPos`, a Close button bottom right (no X), Manual left of
  Close in Options, titles "StatVerdict Guide"..., Best in Slot / Ranked Trinkets have a two-line title and work out their own height
  (`FitToWindowLayout` in `UI/SV_BisProgressPanel.lua`). Docked again when Compact Mode is off (`ReleaseFloatingPanel` puts the card back under the window).
  Only one panel is ever open (`ns.SetRightPanelMode`).
- **Auto-hide the left side**: a 22-wide strip `>>`; the mouse on it opens the left card over the table on strata DIALOG (`Layout.SetLeftOpen`), it folds away
  0.35 s after the mouse leaves, not while a dropdown menu is open (`ns.IsChipDropdownOpen`). A small "(Main Spec)"/"(Off Spec)" tag follows the table title
  (`Layout.UpdateSpecTag`). The window is never narrower than its title bar (`ns.GetTitleBarMinWidth`).
- **Window size** (`windowScale` for the normal window, `windowScaleCompact` for Compact Mode, which follows the normal one until chosen; 75..100, default **85**,
  step 5): `ns.GetWindowScale`, `ns.ChangeWindowScale` (keeps the top left corner, scales `floatingPanelPos`), `ns.ApplyWindowScale`; applied when the mouse lets go
  of the slider (`ns.CreateStepSlider` in `UI/SV_RightPanelMode.lua`, with a faint line per step). Dropdown menus take the dropdown's scale. NOT verified: whether
  `GetLeft()` is in the frame's own units on every game build (the scale change assumes it is).
- **Manual** (`UI/SV_ManualDrawerPanel.lua`): a Text size slider (100..200, `manualTextScale`) scales the font sizes, the spacing and the width (and the height of a
  floating Manual); it has new sections "Window and Compact Mode" and "Item tooltips".

## Tooltip behaviour built on 2026-10-02/03 (all in `UI/SV_Tooltip.lua`, `UI/SV_Render.lua`, `Core/SV_ItemReferenceBonuses.lua`)
- **Stat ranks:** `+73 Critical Strike #1 [MS]`: gold number, then a gold MS/OS picture (`Textures/StatRankMS|OS.tga`, size 8x16 in `LABEL_SIZE`).
  Equal stats (guide "equal groups") share the same number. Switch: Options > "Stat Ranks on tooltips" (`StatVerdictDB.showStatRanks`).
  Not drawn in combat. The comparison block "If you replace this item..." is skipped. Matching uses the game's own stat words (works in every language).
- **Which build:** the one selected in the window (Main/Off). **Alt HELD shows the other build** (ranks AND the whole verdict block), only when an Off Spec is set
  and NOT over a bag item (Alt-click marks there: `tooltipInBags`, set once per tooltip in `ProcessTooltip`). Letting go brings the first build back (no toggle).
  One gold line "Also an upgrade for Off Spec" ("Main Spec" while Alt is held) when the other build gains too. `RefreshData` redraws on Alt press/release.
- **Verdict line:** "Better than <item name>: +points" (no "virtual loadout" wording).
- **Catalyst:** the item is judged as it is (the +100 is NOT in its points; converting costs a scarce Spark). Under the verdict: "Best in Slot after the
  Catalyst" (light blue) when the set piece, judged with its real stats at the item's own item level, comes out better, else "Not better after the
  Catalyst"; then "Hold Ctrl to preview". **Ctrl held swaps the tooltip for the set piece** (same item string, set piece id), nothing about saving is offered
  there; Ctrl up puts the item back. Shift is the game's own comparison and Alt is ours for the build: do not reuse them. Appears only when the BiS piece of
  that slot is a set piece, the item has an upgrade track, and is not itself the BiS piece. It is inside the verdict block, so it needs the item to be an
  upgrade as it is. **2026-10-07 fixes:** the set piece is now built with the track bonus id that gives the item's own item level
  (`ns.CatalystTargetItemString` in `UI/SV_Render.lua`, from `trackRanks`): copying the item's own bonus ids made the game read the set piece at its base level
  (219 instead of 292), so "Not better" was wrong and Ctrl showed a weak piece. No track level found = no Catalyst lines at all. For an item that is no upgrade
  as it is, or the piece worn, `ns.RenderTooltipCatalystOnly` draws a short block: "StatVerdict Warning / Main Spec <spec> / Catalyst it: Best in Slot +N /
  Hold Ctrl to preview" (Main Spec only, only when the gain is positive). The game's comparison tooltip (ShoppingTooltip) gives no link, only an item id:
  `GetTooltipItemLink` finds the worn link by id. Character sheet (`UI/SV_UpgradeIndicatorView.lua`, `RefreshCatalystMarks`): gold BIS on worn Best in Slot
  pieces, gold CAT where the Catalyst would make the piece Best in Slot (all in the middle of the slot); Options > "Marks on the character sheet"
  (`showCharacterMarks`, on by default). **Not confirmed by the owner in game: the ones above that are not named here; the Ctrl preview was reported working; the "no save in preview" and "Alt build verdict" changes are not yet confirmed by the owner.**
- **Pitfall found:** the verdict block is skipped when the tooltip "already has a StatVerdict line" (`TooltipAlreadyHasStatVerdict`). Texture escapes
  hold the folder name `StatVerdict` in their path, so that check now strips `|T...|t` first. Any text we add to a tooltip must be checked against it.

## Open items
1. **User report** (CurseForge comment by Phaselord, 2026-10-04: window "loaded compact and laying over itself"): the owner asked for a screenshot, UI scale,
   resolution, language and UI add-ons; no answer yet. The likely cause (fresh installs got a different, shorter layout) is fixed in 2.0.40. If they answer and
   it is still unclear, build `/sv info` (a window with UI scale, resolution, locale, font-changing add-ons); it would stay like `/sv mouse`. An extra
   release inside the same week is allowed when it fixes a real user problem.
2. The owner may make Compact Mode the default later, after more players have seen it. Not decided.
3. The owner reported "a malfunction found while searching" that is not about this work: ask him for it first thing.
4. Tooltip keys in the Manual are written. `StatVerdict/STORE.md` still holds a copy of the changelog next to `docs/changelog/`: one source only? (asked, no answer)
5. Delete the old remote branch `worktree-keylevel-bracket-benchmarks` (16 commits not in main, old Mythic+ benchmark work)? (asked, no answer)
6. Items showing a wrong item level: ask for the item name and the tier selected; trinkets without track info borrow ids from another list, else dungeon/raid
   drops get the shown tier's 6/6 id (`Repository.GetKnownBonusIDs`, `GetTrackTopBonusID`); crafted/vendor/event/PvP say "Other source".

## Tooling that stays (feeds the addon)
- `tools/classcodex_*.py`, `spec_catalog.py`, `simc_stat_engine.py`, `wowhead_stat_engine.py`, `upgrade_tracks.py`, `lua_render.py`: the weekly data pipeline
  (`tools/README.md` explains it). `tools/release_prep.py`: the weekly version/changelog/issue step (tests in `test_release_prep.py`).
- `tools/item_sources.py`, `tools/blizzard_item_pool.py`, `tools/data/blizzard_item_pool.json`: the "Where to find" data (run by hand, needs Blizzard keys from the environment).
- `tools/item_check_verdict.py`: despite the name, the harness that loads the whole addon in lupa for the scoring and tooltip tests.
- `tools/method_guides.py`, `method_targets.py`, `tools/data/method/`: Method as a second guide source (below).
- `.github/workflows/tests.yml`, `tools/tests/` (788 tests). Test pitfalls: lupa makes a new Python wrapper for every Lua table read (use `rawequal`);
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
