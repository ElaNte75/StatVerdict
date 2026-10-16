# StatVerdict — where we stand (written 2026-10-16, version 2.2.42). The ONLY notes file: replace it, never add another.

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
- **Order of work (owner's rule, 2026-10-16): change the code, copy it to the game folder, let him test, and only when he says "ok" / "βάλτα" commit and
  push. Never commit, push or start a workflow unasked** (this replaces the old "pushes are pre-authorised"). Then: run `python -m unittest discover -s
  tools/tests` (needs `pip install lupa`), commit with named files (never `git add -A`), `git pull --rebase --autostash` first (the weekly bot changes
  the version lines and the data file), push `main` and `main:main-myh77p`, wait for the Tests workflow.
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
- **The repo is at 2.2.42 (2026-10-16), not yet on CurseForge** (1.1.0 is; 2.0.40 and 2.1.42 were never uploaded, their changes are all in 2.2.42). The
  changelog is `docs/changelog/2.2.42_pending.md` (also pasted in `StatVerdict/STORE.md`). The owner uploads by hand: `StatVerdict Ship (no bump).bat`
  builds `StatVerdict-<version>.zip` on his Desktop from the repo's `StatVerdict` folder; `StatVerdict Ship.bat` also bumps the version: do not use it.
  Bump helper: `release_prep.write_version(root, version, date)` sets the toc, `ns.VERSION`, `ns.RELEASE_DATE` and the `(vX.Y.Z)` in STORE.md.
- **Every Wednesday ~12:00 Greek time** `.github/workflows/classcodex-live-refresh.yml` refreshes the guide data and, when it changed, runs
  `tools/release_prep.py` (bumps WEEK, adds a data line to the pending changelog) and opens a GitHub issue ("Ώρα για ανέβασμα ...") that GitHub mails to the
  owner. It never publishes. The stat targets step now looks up about 3000 pieces on Wowhead (~20 minutes); NOT yet run on GitHub's machines (it ran
  locally): if Wowhead blocks them the step fails, the old file stays and the owner gets the failed-workflow mail.
- The data pipeline refuses to write targets without the upgrade-track tables (`--allow-missing-track-levels` overrides) and retries the fetch 4 times.
  The data root carries `trackSwap`, `trackTop`, `trackRanks` and `trackItemLevels`.
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
- **Open (owner decided to leave it, 2026-10-07):** over a BAG item there is no way to see the Off Spec view (Alt marks there, Ctrl is the Catalyst, Shift is
  the game's own comparison and must not be reused). The tooltip only says "Also an upgrade for Off Spec" + a grey "Alt-Left-Click: save in loadout". An idea
  not built: put the Off Spec points on that line ("Also an upgrade for Off Spec +N"). Also open: long notice sentences still wrap (data unavailable, rule
  reason...), and "21.5% better, based on what?" when the slot is empty was never looked at (needs a screenshot).
- **Abandoned (2026-10-08): showing only the compared piece's comparison tooltip** (rings/trinkets/one-hand: the game shows both
  ShoppingTooltip1/2). Seven attempts failed in game; do not retry the same ways. What was learned: the game shows the comparison
  tooltips BEFORE the item's post-call (no verdict yet, GameTooltip not yet IsShown); it rebuilds them about once a second;
  Hide() wipes a tooltip's text (it can no longer be identified) and the game shows it again; SetAlpha(0) is undone by its
  fade-in even when re-applied in OnUpdate (flicker); moving ShoppingTooltip2 needs BOTH anchor points of ShoppingTooltip1
  (TOP>GameTooltip:TOP and RIGHT>GameTooltip:LEFT), copying one put it over the item's tooltip. Hiding both at once in OnShow
  does NOT flicker (the only thing that worked). Debug output goes to a debug WINDOW, never the chat (the owner was spammed).
- **Character info (worn pieces), built 2026-10-08:** `ns.GetWornPieceInfo(link)` (`UI/SV_Render.lua`) says what is true of a worn piece
  (bis / catalyst gain / in both builds' loadouts). One mark in the middle of the icon (`UI/SV_UpgradeIndicatorView.lua`,
  `RefreshCatalystMarks`): BIS or CAT letters (12 pt, 10 pt inside the ring), the gold ring with two arrows (`Textures/SharedRing2.tga`)
  when in both loadouts; the same ring (`SharedRingBold.tga`, thicker) replaces the MS/OS letters on a bag item in both loadouts. The worn
  piece's tooltip never compares (owner name `Character*Slot`): only "StatVerdict info / Warning" lines (BIS in light blue, "Also part of
  your OS set" with OS/MS in green). Options: groups Window / Bag items / Item tooltips / Character info / Best in Slot / Ranked Trinkets
  (`showCharacterMarks`, `showWornInfo`). Bag Alt-click: right = Main Spec mark, left = Off Spec mark, independent toggles. Respec puts on
  marked pieces at 1.25 / 2.5 / 4 s, a ring/trinket/1H goes to the slot whose worn piece is not in the loadout. Marking a second ring
  takes the other slot. The Manual is now a list of topics (`Panel.OpenTopic / ShowTopics`, Back arrow, text size 100-175% only inside a
  topic). Colour rule from the owner: MS / OS are green letters everywhere; Best in Slot is light blue; still gold and to decide: the
  "Saved in MS Frost loadout" line and the stat-rank MS/OS pictures.
- **Loadouts, marks and Auto mark (built 2026-10-09; the owner tested all of it in the game except where said):**
  - Snapshot fields (`Core/SV_SpecSnapshot.lua`): `equipment` (the picture), `marked[slot]` (link), `markedGUID[slot]` (the piece's item GUID,
    `ns.GetBagItemGUID` / `ns.GetWornItemGUID` over `C_Item.GetItemGUID(ItemLocation...)`), `manualSlots[slot]` (a mark made by Alt-click: the lock is the GUID
    that was worn in the slot when it was made, so another worn piece lets go; `true` for a spec that is not played). An item LINK carries the spec id
    and level: never compare marks by link, use the GUID (links stay as the fallback for marks made before, which have no GUID).
  - `ns.AutoMarkWornPieces` (option `autoMark`, on when never set): after every capture and 7.5 s after a real spec change; it waits 7 s after a spec change
    (`AUTO_MARK_QUIET_SECONDS`) so the old spec's gear is not taken for the new one. Hand marks win until their piece is worn or another piece is worn there.
    The equip pass at respec (`EquipMarkedLoadoutItems`) uses the GUID when the mark has one and no longer asks the loadout slot to agree.
  - `CaptureActiveSpecSnapshot` returns the old table untouched when worn pieces, stats and hero tree are the same (no new revision, no refresh);
    `ScheduleCapture` only refreshes the screens when the revision changed (three captures follow every event). The character sheet marks are redrawn
    from `RequestRefresh` (its own 0.5 s redraw can come before the marks are updated).
  - Bags: marks are painted at once on container OnShow (`HookFrameShow`), and a button forgets that it was painted when it is hidden (OnHide)
    (otherwise a quick close/open left the marks hidden). Tooltips of bag pieces: saved in both = one line; saved in one = verdict for the other build +
    "Also saved in ..." (`ns.RenderTooltipLoadoutMembership(..., alsoLine)`). Indicator: arrow + letter when saved in one build and an upgrade for the other.
  - Alt-click (`UI/SV_UpgradeIndicatorView.lua`, `ns.TryApproveItemLink` in `StatVerdict.lua`): Auto mark on = either button saves for the build not played, and
    for the played one too when it is an upgrade there (`markPlayedToo`); off = Alt-Right Main, Alt-Left Off as before. `ns.MarkClickLabel` names the click in texts.
  - Right-click on a ring/trinket/one-hand weapon in the bags (`PrepareSmartEquip`, `smartEquipFrame`): the game picks the slot itself (by its own rule);
    we pick the piece up in PreClick and drop it on the slot the comparison names (`ns.EquipBagSlotInto`); if the game still replaced another piece, two
    equips put things right (`ns.EquipBagPieceByGUID`). NOT understood: what the game's own click does with the piece on the cursor; it worked in the owner's test.
  - Character info: red arrow (`SetWornDownArrow`, the bag arrow turned over, desaturated, red) when `ns.GetBagUpgradesForWornSlots` (Logic, cached, cleared on gear and
    bag events) finds a better bag piece for the played spec; click = ignore (`StatVerdictDB.ignoredWornWarnings[specID:wornGUID] = better link`, pruned when the worn piece
    is not worn any more); the ring is hidden while the arrow warns. The tooltip of a worn piece also says "Part of your MS Frost set" for a piece of one build only.
  - Auto mark also saves a piece you put on for the other build when `BuildComparison` says it is an upgrade there (`MarkForOtherBuildToo`; not on the very first pass
    after an update, `autoMarkSeeded`, so an update never rewrites the other build; a hand mark there wins). The red arrow skips empty slots.
  - An upgrade can change the item GUID (the owner saw the ring lost): `ns.ReconcileMarkedSerials` (before each capture burst and on bag events) moves the marks
    of every loadout of this character from a marked serial that is nowhere to the one unmarked piece of the same item that is here (item count incl. bank must match, level never lower),
    and records `StatVerdictDB.serialHistory[old] = new` (`SameSerial` follows it). The Catalyst makes a different item: no inheritance (open, owner informed).
  - Built 2026-10-09 after the owner's rule "comparisons always use the virtual loadouts": (B) `ns.GetPlayedLoadoutOverlay` (a marked piece waiting in the bags counts as what the
    played spec has in that slot; used by `SV_Comparison.lua` and `SV_Rules.lua`); (C) `ns.EnsureSelectedLoadouts` (a chosen build, played or not, gets a copy of what is worn with the
    current stats, called after each capture and from `SaveSelection`; the stats of a spec never played are an approximation); the Catalyst: `ReconcileMarkedSerials` also moves the marks
    to ONE new piece that fits the slot when the marked piece vanished since the last check and none of its item is left anywhere (`previousOwned`). Tests: `tools/tests/test_serial_marks.py`.
    The debug window used while building this lived only in the game copy.
- **Session 2026-10-10 (marks that did not hold, and speed):** the owner's saved file showed an Off Spec ring slot marked with the piece worn in the other
  ring slot, which made the real piece look like "another copy" (no mark, no tooltip line). Fixed in `Core/SV_SpecSnapshot.lua`: one piece is marked in one
  slot only (`ForgetMarksOfSerial`, used by Auto mark and Approve; `ns.DropDuplicateMarks` repairs old doubles at every capture); a plain hand lock (`true`,
  made while the spec was not played) binds to the worn piece and lets go (`AutoMarkWornPieces`); a second round of Auto mark when a mark was moved;
  captures also run at `PLAYER_REGEN_ENABLED` and after Approve/Remove (`ns.ScheduleLoadoutCapture`); `SnapshotHoldsPiece` knows a mark even when the
  picture's slot is empty. Speed (measured in game with a temporary window, now removed): `RequestStatAuditRefresh` and the stat events rebuild the window
  once per burst (`ScheduleAuditUpdate`, 0.1 s), `RefreshCatalystMarks` does nothing while `PaperDollFrame` is closed and requests coalesce
  (`ns.RequestCatalystMarks`), stat ranks on tooltips do less per line. Measured before: audit rebuild 19 ms avg / 80 max, marks 19 / 31, tooltip 3 / 21,
  Auto mark up to 15 ms once after a respec (left as it is). NOT re-measured after the change. StatVerdict used 6.6 ms CPU/sec in 15 minutes of play;
  FarmWise (the owner's other add-on) 15 ms/sec: a report for that project was written in the chat.
  Tests: `tools/tests/world_sim.py` (a simulated character: worn, bags, serials, spec changes, clock, events, honours `RegisterEvent`) runs the real
  `SV_SpecSnapshot.lua` and `SV_UpgradeIndicatorLogic.lua`; `test_loadout_world.py` (scenarios, incl. the owner's saved state) and `test_loadout_fuzz.py`
  (random play: no double marks, nothing lost, the played spec marks what it wears, a respec puts on every marked piece, upgrades keep marks). Seven
  mutations of the fixes were each caught. Not covered: the real game's event order, and the screens themselves.
- **Tier piece sockets (2026-10-12):** the guide data (Icy Veins "catalyst" block, `gear_by_slot` in `tools/classcodex_targets.py`) puts the
  bonus ids of the BASE piece on the tier piece (to reach the top upgrade level); a socket id among them made the Best in Slot tooltip recommend gems for
  a tier piece that has no socket (owner's Blood shoulders). `OwnBonusIDs` (`UI/SV_BisProgressPanel.lua`) keeps only upgrade-track ids for the socket
  count of a tier set piece (`ns.IsTierSetPiece`, `Core/SV_ItemReferenceBonuses.lua`); the shown link is unchanged. "Where to find" of a tier piece
  not in the journal: "Tier set piece / Raid, Great Vault or made at the Catalyst". NOT done: naming the base piece ("Catalyst from <item>"): the
  generated data does not keep the base item id (would need `tools/classcodex_targets.py` to write it, then the weekly regeneration).
- **Room to grow (2026-10-13):** `UpgradeHeadroom` / `PotentialPercent` in `Core/SV_Comparison.lua`: when a piece is below the upgrade threshold
  (`MIN_UPGRADE_PERCENT` 1%) but has more room on its upgrade track than the worn piece, it gets up to +1.5% (0.1% per item level) and counts as an
  upgrade (`potentialLift`; `deltaScore` includes the push, `rawDeltaScore` is the real one). Nothing is added to the tooltip (owner's rule). Tests:
  `tools/tests/test_upgrade_potential.py`. DROPPED by the owner: a "go upgrade with crests" mark on the character sheet (research: Season 2 Mistcrests,
  flat 20 per rank, one crest type per track, currency ids Veteran 3443 / Hero 3445, the others not verified). The player does the upgrading himself.
- **Vendor error (2026-10-15/16):** after the game update of 2026-10-14, opening a vendor (bags open with it) raised "attempt to call a nil value" in
  `[C] UpdateItems` of `ContainerFrameCombinedBags`, with no StatVerdict line in the stack. Found by switching hook groups off one at a time in the game copy: the
  culprit was `hooksecurefunc(<one bag window>, "UpdateItems", ...)` (`UI/SV_UpgradeIndicatorView.lua`); removed, with a test that keeps it out. LESSON: a
  temporary switch read from `StatVerdictDB` at file load never works (saved variables load AFTER the add-on's files): put the switch in the file itself.
  Also reported and NOT solved: StatVerdict tooltips that stay open or misbehave (asked the owner which tooltip and when).
- **Pitfall found:** the verdict block is skipped when the tooltip "already has a StatVerdict line" (`TooltipAlreadyHasStatVerdict`). Texture escapes
  hold the folder name `StatVerdict` in their path, so that check now strips `|T...|t` first. Any text we add to a tooltip must be checked against it.

## Targets, scoring and data (2026-10-16; read this before touching them)
- **Goals:** Overall (the guide's own "all" list, the default when nothing is chosen), Mythic+, Raid, PvP. PvE lists come from Icy Veins, PvP from u.gg.
- **Stat targets are our own plain sums, no simulation.** `tools/classcodex_targets.py`: every piece of the guide's Best in Slot list is moved to the 6/6 of
  the tier (`move_loadout_to_track`: known upgrade ids are swapped, a tier piece listed without any id gets the track's 6/6 id, crafted pieces stay), its stats
  (Wowhead tooltips, with the recommended gem and enchant) are added up, then the spec's fixed rating without gear (`tools/data/spec_base_stats.json`, measured
  once from the earlier simulation; five healers have none) is added. Tier 3 = Myth 6/6 (`targets.statTargets`), Tier 2 = Hero 6/6 (`targets.levels.hero`),
  Tier 1 = Champion 6/6 (`.champion`). PvP gear has no tracks: every tier shows the same targets. The Windwalker list of Icy Veins carries an older Myth
  rank id (12806): the Myth swap fixes it (it showed item level 289). `SelectTargetValues` in `Core/SV_ProfileRepository.lua` reads this; the u.gg
  `guideTargets` are gone from the data.
- **Safety net:** `tools/classcodex_carryover.py` (see `tools/README.md`): per part, last week's stays when the new is missing or invalid (max 30 days),
  more than 25% of contexts carried = nothing is written. The CLI prints the report and `--carry-report` writes it for the commit text.
- **Prospect (`Core/SV_Comparison.lua`):** a piece that can still be upgraded and sits on a higher upgrade track than the worn one is scored against the Myth
  targets (`profile.mythAuditTargets`, `ProspectProfile`). The game gives a piece's rank (`currentLevel`) but NOT `maxItemLevel`: `ns.GetItemUpgradeCeiling`
  (`Core/SV_ItemData.lua`) finds the top item level from `trackRanks` (the track whose rank has this item level) and then the track name. The earlier
  "room to grow" push (0.1% per level, max 1.5%) never worked in the game for the same reason; it does now. No tooltip line was added for it.
- **Primary stand-in boost (`Core/SV_Scoring.lua`, `PRIMARYLESS_EQUIP_LOCATIONS`):** only trinkets keep it (the first secondary of the order gets half the primary
  weight). Rings and necks lost it: neither side of a comparison has a primary, and it multiplied the first stat by about 3 (the Blood Pendant was -27%). A sweep of
  288 ring and 576 trinket scenarios: boost 0 gives 53 more arrows than 0.5 on rings (0.1: +28, 0.2: +7, 0.3: +0); on trinkets 0 gives +132 and 0.25 +60, so
  trinkets stay at 0.5. It is one number; if arrows on rings look too generous, set a small value for rings (the sweep scripts were temporary).
- **ClassCodex overlap:** the owner has ClassCodex installed; it appends its own "  #n" to stat lines. StatVerdict now adds only its MS/OS mark after a foreign
  rank (`StripForeignRank` in `UI/SV_Tooltip.lua`). Whether to replace their number is open (owner: later).
- **Names in the Best in Slot / Ranked Trinkets lists were grey** because the global `GetItemQualityColor` is gone: `LookupQualityRGB` /
  `GetQualityHex` in `UI/SV_BisProgressPanel.lua` try C_Item first.
- **Removed on 2026-10-16:** SimulationCraft (`simc_stat_engine.py`, the GitHub build steps, all its tests), the Method experiment (`method_*.py`, `tools/data/method`),
  the SimC comparison part of the test harness (`item_check_verdict.py` is now `tools/addon_harness.py`), the u.gg bins. Git history has them.
- Test helper: `tools/tests/wowhead_fakes.py` (`fake_wowhead`) stands in for the Wowhead lookup.
- **Not verified in the game:** the Hero/Champion numbers of other specs than the ones the owner looked at, the healers without a base rating, how many
  arrows ring scoring gives in real play, and the weekly workflow on GitHub's machines (Wowhead may refuse them).

## Open items
1. **User report** (CurseForge comment by Phaselord, 2026-10-04: window "loaded compact and laying over itself"): the owner asked for a screenshot, UI scale,
   resolution, language and UI add-ons; no answer yet. The likely cause (fresh installs got a different, shorter layout) is fixed in 2.0.40. If they answer and
   it is still unclear, build `/sv info` (a window with UI scale, resolution, locale, font-changing add-ons); it would stay like `/sv mouse`. An extra
   release inside the same week is allowed when it fixes a real user problem.
2. The owner may make Compact Mode the default later, after more players have seen it. Not decided.
3. The owner reported "a malfunction found while searching" that is not about this work: ask him for it first thing.
4. Tooltip keys in the Manual are written. `StatVerdict/STORE.md` still holds a copy of the changelog next to `docs/changelog/`: one source only? (asked, no answer)
5. Items showing a wrong item level: ask for the item name and the tier selected; trinkets without track info borrow ids from another list, else dungeon/raid
   drops get the shown tier's 6/6 id (`Repository.GetKnownBonusIDs`, `GetTrackTopBonusID`); crafted/vendor/event/PvP say "Other source".

## Tooling that stays (feeds the addon)
- `tools/classcodex_*.py`, `spec_catalog.py`, `wowhead_stat_engine.py`, `upgrade_tracks.py`, `lua_render.py`: the weekly data pipeline
  (`tools/README.md` explains it). `tools/release_prep.py`: the weekly version/changelog/issue step (tests in `test_release_prep.py`).
- `tools/item_sources.py`, `tools/blizzard_item_pool.py`, `tools/data/blizzard_item_pool.json`: the "Where to find" data (run by hand, needs Blizzard keys from the environment).
- `tools/addon_harness.py`: loads the whole addon in lupa for the scoring and tooltip tests.
- `.github/workflows/tests.yml`, `tools/tests/` (901 tests). Test pitfalls: lupa makes a new Python wrapper for every Lua table read (use `rawequal`);
  the shared `verdict.CHARACTER` dict must be restored after a test changes it; `FRAME_STUB` frames keep old anchors after `ClearAllPoints`.

## Guardrails (the owner's rules)
- The Guide is a 1:1 copy of the guides, never tuned. Sources may be named only in the single line "All guide information comes from Icy Veins and u.gg."
  (`Core/SV_WeightModes.lua`; test `NoDataSourceNamesShownTests`). A new source must be copied 1:1 and labelled as that source's own method.
- Never hand-edit `StatVerdict/Data/Generated/*.lua` (the weekly workflow regenerates it). Never weaken the geometry, "nothing moves" or real-data tests.
- Never commit secrets (Blizzard credentials only from the environment). Replaced features and data are deleted completely, never left commented out.
- Commits end with the co-author line the session gives. Push to `main` and `main-myh77p` only after the owner's "ok" (see How we work now). No PRs unless asked.
- Do not publish or upload anything for the owner; he uploads to CurseForge himself.

## Longer-term ideas (not started)
- **Another guide source** (Method, Murlok): not started; the earlier Method reader was deleted (it needed the simulation) and is in git history.
- **Tank simulation (on hold).** Own simulation is not worth it (gain at most 4-5%); any future UI must say "our own simulation estimate", never mixed with the Guide.
- Possible later: show the Catalyst information also for items that are not an upgrade as they are (today it lives inside the verdict block).
- Owner housekeeping: old GitHub repos `Scraper` and `farmerassistant` can be deleted on GitHub (other repositories: not touched); CurseForge cloud credits ($100) expire 2026-11-05.
