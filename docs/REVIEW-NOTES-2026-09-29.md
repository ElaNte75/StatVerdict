# Deep review notes (2026-09-29, night): things to decide one by one

Written for the next session. Everything **sure** was cleaned up and pushed (section A). Everything I was
**not 100% sure about** was left untouched and is listed in section B with the evidence, my suggestion, and
why I stopped. Suggested order: B1 first (it decides B2/B3/B4), then the rest.

Tests at the end of the review: 481 of 481 passing.

## A. Already cleaned (safe, tests unchanged)

| Commit | What |
|---|---|
| Cleanup: remove 24 local functions nothing calls | 22 `local function`s (plus 2 that became unused) that were defined and never referenced in their file: `SV_Comparison` (SafeNumber), `SV_Modifiers` (GetProfileMaxGapUrgency, HasHigherPriorityGaps, GetExtraWeight), `SV_Scoring` (AddTrackedKeys), `SV_BisProgressPanel`/`SV_ManualDrawerPanel` (Register), `SV_SettingsPanel` (ApplyDropdownLabelFont, EnsureResizeRegion, EnsureViewToggle), `SV_StatAudit` (EnsureMissingSnapshotButtons, ClampWindowToScreen, SafeStringWidth, SetSetupCheckboxTextColor, EnsureWindowOnScreen, CreateSeparator, BuildAspectLabel), `SV_StatProgressPanel` (LayoutOffSpecEmptyHint, RegisterSummaryText, EnsureContentHost, GetSummaryCardWidth, EnsureSummaryHeightRegion). 226 lines gone, 0 added. |
| Cleanup: drop no-op 'hide legacy' helpers | `HideLegacyDualTabs`, `HideLegacyTitleFontSteppers`, `ClearLegacyLockButton` (and their calls): they only hid fields that no code assigns any more. |
| Cleanup: dead `_check_profiles.py` + stale instructions | Root `_check_profiles.py` read the removed `SV_ProfileData.lua` from hard-coded Windows paths. `Ship.bat` still described a Bridge export and a `Data\Generated` update that `ship.ps1` no longer does. `VERIFICATION.md` pointed at a `tests/` folder that does not exist (now `tools/tests`, needs `lupa`). The three workflows committed as "StatVerdict Benchmark Bot" (now "StatVerdict Data Bot"). |
| This commit | `SV_DashboardLayout.lua`: the unused fallback width of the Mode drawer (280) now matches the drawer (300). |

Also checked and found clean: the toc (every file exists, every Lua file under Core/UI/Data is listed), no
accidental globals at file level (only bindings, slash commands and the addon-compartment callbacks), no
`Raider`/Benchmark/Popular/Easy-Normal-Hard wording in player-visible strings, no debug `print` left over
(all prints are slash-command output), and every tool module under `tools/` is used by code, tests or a workflow.

## B. Open items (not changed, need a decision)

### B1. [DONE, see section C] A "dev build" layer that is not in the repo (biggest one)
- `ns.STATVERDICT_DEV_TOOLS` is read in 4 places (`StatVerdict.lua:177`, `SV_UpgradeIndicatorView.lua:79`,
  `SV_StatAudit.lua:1260,3836`) but **never set anywhere in the repo**; `ns.IS_DEV_BUILD` is true only for an addon
  folder called `StatVerdict_Dev` (`SV_Constants.lua:6`).
- `/sv help` advertises `/svdev`, `/svmove`, `/svbis` (only when the flag is set); no handler for them exists here.
- `ship.ps1` bans `UI\SV_AdvancedDevelopmentMode.lua` and `UI\SV_DevLayoutNudge.lua`, which are not in the repo, so they
  probably exist only on the owner's desktop.
- Roughly 340 references to `DevLayout` / `AdvDev` / `AdvancedDevelopment` across the UI (`SV_StatProgressPanel` 79,
  `SV_DashboardLayout` 67, `SV_RightPanelMode` 46, `SV_OptionsDrawerPanel` 40, `SV_LayoutOffsets` whole file, 449 lines...).
  With the flag never set these branches are dead in this repo, but the dev files (outside the repo) may call them.
- **Question for the owner:** does the dev build still exist and get used? If yes: commit it (or move the layout editor
  to its own folder) so the repo is complete. If no: remove `SV_LayoutOffsets.lua`, the `DevLayout` calls and the
  `IS_DEV_BUILD` / `STATVERDICT_DEV_TOOLS` branches in one careful pass (big diff, needs the UI geometry tests).
- Why I stopped: removing it may break something only visible outside the repo, and it touches most UI files.

### B2. [DONE, see section C] Exported functions nothing calls (34 found)
`ns.*` is private to the addon (not published as a global), so these are unreachable from other addons. Left in place
because several look like hooks for the missing dev files (B1) or small public-style APIs:
- Dev layout: `EnsureDevLayoutGripRegion`, `EnsureDevLayoutRimRegions`, `EnsureDevLayoutStripRegion`, `IsDevLayoutHidden`,
  `ToggleDevLayoutScreenLock`, `UnregisterDevLayoutRegionsByPrefix`, `RequestAdvancedDevelopmentModeLayoutRefresh`,
  `DebugHeroOptionsForSpec`, `ToggleStatAuditLayoutController`, `IsPublicStatVerdictLoaded`.
- Drawer / minimap API: `IsOptionsDrawerOpen`, `SetOptionsDrawerOpen`, `ToggleOptionsDrawer`, `IsStatVerdictMinimapButtonShown`,
  `SetStatVerdictMinimapButtonShown`, `CloseAllChipDropdowns`, `IsChipDropdown`, `IsBagIndicatorOptionEnabled`.
- Stats / layout helpers: `EnsureCachedStatAuditLiveModifiers`, `GetCurrentCharacterSheetStatValue`,
  `GetProfileSnapshotDisplayStats`, `GetStatAuditTargetPointTotal`, `GetStatVerdictWindowTitleBarHeight`,
  `Layout.GetFixedSlotRows`, `Layout.GetStatScreenWidth`, `Layout.GetWellLeft`, `Panel.UpdateProgressCache`.
- Constants: `ns.ACTIVE_PROVIDER`, `ns.ADDON_NAME`, `ns.ADDON_FOLDER`.
- Only tests call: `GetGearLevels`, `GetStatTargetBins`, `GetStatVerdictHeroSubTreeIDs`, `Panel.GetRecommendedTooltip`
  (fine to keep).
- **Suggestion:** after B1, delete the ones with no caller and no test in one commit.

### B3. "Hide legacy" code that may or may not do something
Still present because I could not prove the fields are never created (or they also clean up the dev layout registry):
`HideLegacyBagMarkerControls` (`SV_SettingsPanel.lua:277`), `HideLegacyTitleFontUi` (`SV_OptionsDrawerPanel.lua:329`, also
unregisters dev layout regions), `HideLegacyPanelTitle` (`SV_RightPanelMode.lua`), `EnsureOffSpecEmptyHint`
(`SV_StatProgressPanel.lua`, always returns nil), the "legacy floating text / incomplete-build" path in
`SV_StatAudit.lua` around lines 2539-2690 (an `EnsureIncompleteBuildText` is still created and shown), and comments
saying "retire legacy strips" in `SV_DashboardLayout.lua`. Fields such as `titleFontLabel`, `displayTitle`,
`offSpecEmptyHint` are never assigned in the repo. Needs a look in the running game before deleting.

### B4. One-time SavedVariables migrations
`SV_StatAudit.lua:838, 929, 942, 1297`, `SV_DashboardLayout.lua:138, 182`, `SV_RightPanelMode.lua:442`,
`SV_BisProgressPanel.lua:1348`, `SV_OptionsDrawerPanel.lua:509` migrate old saved keys (global custom table, old goal
"Overall/Leveling" to Mythic+, per-character layout to global, shared BiS/Trinkets key, per-drawer X...).
The owner said the addon is local-only, so they may be removable, but deleting them silently drops a user's saved layout
if an old `StatVerdictDB` still exists. **Question:** is any old `StatVerdictDB` still in use on the owner's machine?

### B5. Layout keys still named "benchmark.*"
`benchmark.card` / `benchmark.width` are the Mode drawer's saved layout keys (`SV_WeightsDrawerPanel.lua:27`,
`SV_DashboardLayout.lua:172,184,538`, `SV_LayoutOffsets.lua`); the comment says they are kept on purpose so saved
positions carry over. Renaming is trivial but resets saved drawer positions. Decide together with B4.

### B6. Stale roadmap `IMPROVEMENTS.md` (repo root, UTF-16)
Lists 5 old design problems (Fury Titan's Grip, prismatic sockets, 2H to 1H fallback, embellishment cap, tier-set
protection) and refers to the removed `SV_ProfileData.lua`. Embellishment and tier-set code now exists in `SV_Rules.lua`
(`embellished`, `WouldBreakTierSet`), so at least items 4 and 5 look implemented; 1-3 are unverified. Needs the owner
to say which are done, then either update or delete the file (also re-save it as UTF-8).

### B7. Quest / merchant / Adventure Guide arrows: intended or not?
`SV_QuestRewardIndicatorSource`, `SV_MerchantIndicatorSource`, `SV_AdventureGuideIndicatorSource` are loaded and active,
`VERIFICATION.md` says they "may still show upgrade arrows", while `SV_OptionsDrawerPanel.lua:498` says
"bags-only is already the behavior". One of the two statements is stale. Tomorrow's quest-chain test will show which.

### B8. Version mismatch
`StatVerdict.toc` Version 1.0.8 vs `ns.VERSION = "1.0.7"` (`StatVerdict.lua:4`); `STORE.md` changelog says 1.0.7.
`ship.ps1` bumps both together, so a run of it fixes it. Owner's decision (already in HANDOFF section 6).

### B9. Old design/plan docs and a foreign branch
- `docs/superpowers/plans/2026-09-26-benchmark-mythicplus-data.md`, `.../2026-09-27-keylevel-bracket-benchmarks-phase1.md`
  and `docs/superpowers/specs/2026-09-26-benchmark-mythicplus-data-design.md` describe the removed Raider.IO benchmark
  system. Historical value only. The other three plans (ClassCodex pipeline, wiring, full coverage) are current.
- Remote branch `origin/worktree-keylevel-bracket-benchmarks`: 64 commits, **no common history with `main`**, from
  2026-09-26/27 (Low/Mid/High key-level brackets, spec-name in the tier text, live benchmark refreshes, the Bridge export
  script, `StatVerdict/tests/test_profile_validation.py`). It is the old benchmark lineage that the ClassCodex rewrite
  replaced; the last UI commits there (class-coloured spec/hero name in the description text) were **not** verified to
  exist in `main`. Confirm they are obsolete before deleting the branch.
- Old repos `Scraper` and `farmerassistant`: only the owner can delete them on GitHub (HANDOFF section 6).

### B10. Data and tooling findings from earlier tonight (see also `overnight-progress.md`)
- Monk Windwalker average item level 289 in Mythic+ and Raid (others ~334); Evoker Devastation 314, Augmentation 320.
  BiS ids match the guide exactly, so the cause is in the SimC item levels; needs a SimC run inspecting per-slot levels.
- Item check weapon rows look extreme (-35% to -57%); the weapon swap in `tools/item_check.py` (MH vs OH, 1H vs 2H)
  should be checked before trusting weapon deltas.
- An unmatched non-empty hero-talent name (translated client) with no subtree id gives no profile by design; decide
  whether a guess is acceptable there.
- Measured-mode stat targets are 0 for a stat the best gear does not carry (Versatility on 18 specs); the row now shows
  with target 0. Decide whether such a row should look different in the UI (unchanged for now: UI is not mine to change).

## C. Development tooling removed (owner decision, later the same night)

The owner confirmed the in-game layout editor, debug pickers and their commands were only scaffolding used to
build the UI, and asked to delete everything not needed by the finished addon, as long as the UI does not change.
Removed (about 900 lines in all, nothing added; 481 of 481 tests pass):
- All calls to the empty dev-layout stubs (`RegisterDevLayoutRegion`, `UnregisterDevLayoutRegion*`,
  `RegisterDevLayoutOuterSpec`, `EnsureDevLayoutLockButton`, ...) plus the empty wrappers and `if ... end` shells they
  left, and the stubs themselves in `SV_LayoutOffsets.lua`.
- The debug class/spec override chain in `SV_StatAudit.lua` (override state, `BuildDebugBaseContext`, the
  `Debug*` helpers, `RefreshDebugOverrideFrame`, the debug interaction blocker), the always-hidden "profile key" debug
  texts (and their placement in `SV_StatProgressPanel.lua`), and the layout-controller panel code.
- Disabled indicator debug logging (`debugLines`, `DebugLine`, `DebugIndicatorState`, ~20 blocks) and the `/svdebug`
  and `/svlayout` slash commands; the `/sv help` lines for `/svdev`, `/svmove`, `/svbis`.
- `ns.IS_DEV_BUILD`, `ns.STATVERDICT_DEV_TOOLS`, `IsPublicStatVerdictLoaded`, the `StatVerdictDev_OnAddonCompartment*`
  callbacks, `ns.ADDON_NAME` / `ADDON_FOLDER` / `ACTIVE_PROVIDER`.
- The 34 exported functions nothing called (drawer/minimap Set/Is/Toggle helpers, unused layout getters, unused stat
  helpers), and every local function that became unused after the above.
Frame names are unchanged (`ns.UIName` still returns the same names).

**Kept on purpose (they place the finished UI or protect saved data):**
- The read side of `SV_LayoutOffsets.lua`: the seeded default offsets (about 250 lines of tuned positions) and
  `GetDevLayoutOffset / SizeDelta / HeightDelta / Padding`, plus `WriteDevLayoutOffset`, the `_abs` flag and the saved-layout
  fixes in `EnsureDevLayoutDB`. Removing them would move the UI.
- `RegisterDevLayoutEditOnly`, `RegisterDevLayoutBorderEditOnly` / `Unregister...`: not no-ops (they hide edit-only badges
  and set border colours).
- `EnsureDevLayoutTextHitRegion`, `EnsureDevLayoutWidthHandle`, `EnsureDevLayoutHeightHandle`, `IsDevLayoutEditActive`,
  `IsDevLayoutScreenLocked`: still called; they return nil/false/true so the code that uses their result is dead, but it
  needs a careful pass per call site (for example the "unlocked" branch of `PlaceSetupChild` in `SV_SettingsPanel.lua`).
- Edit-only badges ("Panel 1", "screen 1", ...) that are created and immediately hidden.

**Suggested follow-up (next session, low risk, needs an in-game check afterwards):**
1. Dead branches behind the constants above (unlocked placement, the text-hit/width/height handles, the edit-only badges).
2. Rename `DevLayout*` to `Layout*` and the `benchmark.*` keys (with a one-time key migration) so the names match what they do.
3. Retire the one-time SavedVariables migrations if no old `StatVerdictDB` is in use (B4).

**Not verified in the running game.** The UI was checked only through the geometry/smoke tests, a static scan for
calls to names that no longer exist, and the fact that every removed function was a no-op or unreachable.
If anything looks different in-game, `git log` shows the commit "Remove the development tooling ..." and
"Remove unused exported functions ..." to restore from.

## D. Second cleanup pass (2026-09-30) and what is left

Done (each in its own commit, tests 512/512):
- Docs: `IMPROVEMENTS.md` (all five items implemented), the three docs of the removed benchmark system, and stale
  entries of `.gitattributes` are gone.
- Names: `DevLayout*` helpers are `Layout*`; `ApplyRightDrawerCardDev` is `ApplyRightDrawerCard`; the Mode drawer's
  saved keys `benchmark.*` are `weights.*` and saved positions are moved once (test included).
- Editor leftovers: the hidden edit-only labels ("Panel 1/2", "screen 1/2", "box 1", "ms stats", "os stats"), the
  unlocked-placement branch of the Panel 1 children, the text-hit/width/height handle stubs, the edit-mode checks and
  every statement that hid a region no code creates (about 130 lines).

Left, on purpose (all need an in-game check or a bigger rewrite):
1. **The older weight model in `SV_Modifiers.lua` / `SV_LiveWeights.lua`** (point budget 10, tiers A/B/C, soft caps,
   `GetDynamicStatWeight`, `NormalizeStatAuditLiveWeights`...). The verdicts and now the Stat Progress table use the
   target-driven model in `SV_Scoring.lua`; the old one is only still used for the extras (weapon DPS, armor,
   stamina) and by many tests. Removing it means rewriting those tests and the table's row code.
2. Frames that are created and hidden but assigned: `devStatColumnRegions`, `devStatHeaderRegions`,
   `devStatProgressWidthRegion`, `devStatTableMoveGrip`, `devStatTableRegion`, `devTopLeftBase`
   (`SV_DashboardLayout.lua`): check that nothing uses them as anchors before removing.
3. One-time SavedVariables fixes in `EnsureLayoutDB` and the migrations listed in B4, the `HideLegacy*` helpers (B3).
4. The remote branch `origin/worktree-keylevel-bracket-benchmarks` (B9): not deleted, its last UI commits were not
   verified to exist in `main`.
5. `StatVerdictDB.statAuditDebugOverride` may still exist in old saved variables (harmless).

The research on the live weight mechanism, with the findings that matter most (steep 4:3:2:1 shares, measured
magnitudes discarded), is in `docs/research-live-weights-2026-09-30.md`.
