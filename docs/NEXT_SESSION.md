# Next local session — reminder (written 2026-09-29 night, for the morning of 2026-09-30)

You are a fresh local Claude Code session on the owner's Windows PC (project folder
`C:\Users\ElaNte\Desktop\Projects\StatVerdict`). The previous local session got too long. Read, in this order:
1. this file, 2. `docs/HANDOFF.md` (full project/architecture/rules — still valid), 3. your project memory
(auto-loaded: `memory/MEMORY.md` and the files it links, especially `statverdict-classcodex-live-pivot-2026-09-28.md` and
`todo-2026-09-30-owner-notes.md`), 4. `git log --oneline -40`.

## Do this first, before anything else
1. **Turn on Remote Control for THIS session** (the owner wants to follow and steer it from the phone): call
   `mcp__ccd_session_mgmt__set_remote_control` with `session_id: "self"`, `enabled: true` (load it via ToolSearch first;
   the app will ask the owner to approve). Confirm the state is "on" and tell the owner in one line.
2. `git pull` (main). Nothing local should be uncommitted; everything was pushed. Old worktrees may exist under
   `.claude/worktrees/` (leftovers of subagent work; safe to prune with `git worktree prune` once you are sure they are merged).
3. Owner language: simple Greek, short, no code in the main explanation (see HANDOFF section 1).

## Where things stand (all on `main`)
- Data pipeline, addon wiring, Mode drawer (Guide / Measured; Tier 3/2/1 in Guide, Champion/Hero/Myth gear level in
  Measured), own Best-in-Slot tooltip with gems/enchants (unique gem once), 3 tooltip options in Features, Catalyst rule,
  fixed Mode-drawer layout, wider Features drawer: done and tested (471 tests). Raider.IO is completely removed.
- Not verified in the game yet: Catalyst/set detection, Shaman hero subTreeIDs 54-56, non-English clients.

## What happened overnight (check it, do not assume)
- **Cloud session** (owner started it with "Continue in Cloud" from the desktop app, told to read `docs/HANDOFF.md`) was
  asked to do, in order and cost-consciously (owner's cloud credits were ~97 of 100 dollars used!):
  item-check watching/fixing; the Versatility-missing-in-Measured bug; guide ties; wider Gear-level cards; then data-quality
  audit of the 240 contexts, fidelity audit vs raw Icy Veins data, docs refresh (STORE.md / VERDICT_MODEL.md), robustness
  tests, code review. It keeps `docs/overnight-progress.md`. See `git log origin/main` and that file to learn what it did;
  review its commits before building on them (run the tests).
- **Item check** (GitHub Action `item-check.yml`, run id 36612825165, started ~2026-09-29 18:32 UTC): SimC DPS delta of
  each candidate item for the owner's Enhancement Shaman (anonymised profile in `tools/data/characters/enhancement_shaman.simc`).
  Result table: `docs/item-check/enhancement_shaman.md` (+ `.json`), committed by the workflow. Check `gh run list --workflow item-check.yml`.
  Explain the table to the owner in plain Greek: which quest reward is a real upgrade and by how much (single target vs 3 targets).

## The owner's plan for the day
1. Play the 12.1 catch-up questline "Return to Amani'Zar" on the Enhancement Shaman (240 ilvl) and note, for each reward,
   what the addon says (upgrade arrow / verdict / percentage). Quest rewards (all ilvl 272, Adventurer 3/6):
   Severing the Serpent's Head -> head (Ophidian General's Barbute 278882); Down With the Skies -> boots (Faithleaper's
   Sabatons 278894); Situation Normal, All Snaked Up -> gloves (Fangsmasher Gauntlets 278898); Fire, the Only Way to Be Sure
   -> trinket Breath of Jan'alai 280377 (SimC cannot simulate its on-use effect); Death of Furies -> neck choice
   (Collar of Jealousy 279194 / Choker of Anger 279195 / Chain of Vengeance 279196).
2. Then compare addon verdicts vs the SimC table: where we agree, where we disagree; investigate disagreements (the addon
   scores by guide priorities/targets, not by DPS, so expect agreement in ranking, not identical numbers).

## Open bugs / notes from the owner (see `todo-2026-09-30-owner-notes.md`)
- Versatility row missing in Measured mode for Enhancement Shaman (rank numbers 1,3,4); order wrong. (Overnight cloud job was asked to fix — verify.)
- Guide ties ("Mastery / Haste" roughly equal): check ranking/weights treat them as roughly equal.
- Gear-level cards a bit wider, all equal.
- Later: premium restyle of older panels; better names than Tier 3/2/1; layout-jump items (BiS/Trinket auto-width, row pitch,
  drawer widths) need an owner decision; owner asked Myth = 334 (6/6) or 344? (keep 334 unless told).
- Owner still has to delete the old GitHub repos `Scraper` and `farmerassistant`.

## Rules that must not be broken (details in HANDOFF section 1 and 7)
Simple Greek; agree the "what", autonomy on the "how"; no data-source names in any player-visible text (test enforces it);
nothing may jump/shift in the UI on toggles; do not hand-edit generated files; commits end with
`Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; push to main is pre-authorised.
Cloud credits are almost used up (they expire 2026-11-05): do not start expensive cloud sessions without asking.

---

# Appendix — why we decided things (so you can continue the conversation as if you had been there)

## How the owner works and talks
- Greek, informal, sometimes voice-dictated text with garbled words/other languages: when a sentence is unintelligible, say so
  briefly and ask; do not guess. Often sends in-game screenshots: read them carefully (they show the real UI).
- Wants step-by-step instructions for anything in the Claude/WoW UI, one step at a time, and wants to be told plainly what he
  must do himself. Appreciates honest "I cannot verify this" more than confident guesses.
- Is the product owner; decides *what*. He gave standing autonomy on *how* ("decide, document, do not keep asking"), but
  NOT on UI/product logic: he approved every UI change explicitly (Benchmark drawer -> Mode, Tier cards, tooltip options...).
- Played characters he tests with: Blood DK (Deathbringer), Guardian Druid (Elune's Chosen), Enhancement Shaman "ElectroQ" (Totemic,
  ilvl 240). He cares about PvE (Mythic+/Raid); PvP is only a courtesy for other players. Older panels he built himself look
  "childish" to him; he loves the polish of the Mode drawer and wants that "premium" look later everywhere.
- Very sensitive to: things jumping/shifting on toggles, cramped padding, source names showing in the UI, mixed languages in
  the UI, and being told about "u.gg" (he associates it with PvP).

## Decision log (what -> why)
1. **Raider.IO dropped everywhere.** Owner: a top player's gear reflects skill as much as correct stats ("being #1 does not
   mean the stats are right"). New method: guide best-in-slot gear + SimulationCraft + guide priorities.
2. **Guide = default and a 100% copy of the guide.** Our SimC measured weights disagreed with the guide's stat order in ~97% of
   cells (same order in 6 of 196); owner does not want the addon to contradict what players read on Icy Veins ("so people don't
   lose trust"). So GUIDE mode copies the guide (priority + target numbers); MEASURED is our own science, kept as an option.
   BLEND (average of both) was built and then removed by the owner as too confusing.
3. **PvE from Icy Veins, PvP from u.gg.** Owner's rule; Icy Veins has no stat-target numbers, so the target numbers (any content)
   come from u.gg's top20/50/80 player percentiles — the same numbers the official ClassCodex addon shows. A mismatch with the
   owner's local ClassCodex was only data staleness (his installed copy was 2 days old).
4. **Never show data-source names** in the UI ("From guides" / "Our own measurement"): owner does not want users to see where
   the data comes from.
5. **Difficulty levels.** Guide: Tier 3/2/1 (= u.gg top80/50/20; Easy/Normal/Hard felt like a game difficulty; owner may find a
   better name later). Measured: the same 3 cards become Champion/Hero/Myth *gear level* (our SimC at that upgrade track and the
   BiS/trinket items at that track). Myth 6/6 is item level 334 per game DB2 and the owner's own tooltip; 344 is a Myth extension
   rank; Hero 6/6 = 321, Champion 6/6 = 308.
6. **One best gem and one best enchant, no alternatives** (owner: "we always give the best performance; the player can pick an
   alternative himself"). The primary gem is unique-equipped (Thalassian Diamond): shown once, on the first socketed slot; SimC gets
   it once too (on neck/ring/head, approximation because sockets are not in the data).
7. **Own Best-in-Slot tooltip** because the game tooltip (with comparison and set bonus text) was too heavy: only name, ilvl/track,
   stats, "Part of the tier set", "Recommended" gems/enchant, "You have this item". Features options: own tooltip / gems+enchants /
   game tooltip; options 1 and 3 turn each other off (owner: greying out was confusing because players cannot see how to enable a
   greyed option).
8. **Catalyst rule.** A found head/shoulders/chest/hands/legs item counts like BiS when the BiS piece for that slot is a tier-set
   piece, because the Catalyst can convert it into that piece (higher ilvl -> better stats); message: "Good if converted to the
   set piece with the Catalyst" (never negative wording, no comparisons).
9. **Layout rule.** Reserve space for the longest text/worst state; nothing moves on any toggle. Owner also wants proper padding
   and drawers that grow the window instead of overlapping its border.
10. **Freshness.** Weekly data refresh (GitHub Actions); no external app for the user; the addon treats data older than 30 days as
    stale (owner has not answered whether to relax it). Players get new data only through addon releases (`ship.ps1` -> CurseForge,
    owner's manual step; an automatic CurseForge/Wago publish was discussed, owner has not set up the account/token).
11. **Cloud.** GitHub Actions is free for this public repo (item check, refreshes). Claude cloud credits (~97 of 100 dollars used)
    are only for cloud *sessions*. The overnight cloud session was given the HANDOFF file; its results are in
    `docs/overnight-progress.md`, `docs/data-quality-report.md`, `docs/data-fidelity-report.md`.
12. **Why an item check.** Owner wants proof the addon's verdicts are sound: SimC DPS delta per candidate item for a real character
    (table in `docs/item-check/enhancement_shaman.md`, e.g. Collar of Jealousy +2.32% ST, Chain of Vengeance +1.50%, Choker of Anger
    +1.15%, Sabatons +1.08%, Barbute +1.03%, Gauntlets +0.98%; bag junk negative), compared tomorrow with what the addon says in game.

## Things the overnight cloud reported that need YOUR attention
- Windwalker Monk contexts have average item level ~289 while every other spec is ~334 (items match the source): SimC/level issue,
  probably a missing slot in the ilvl average (SimC omits items with no stats) or an unswapped track id. Investigate, it affects
  Measured targets for that spec.
- Versatility in Measured: the cloud says missing stats are genuine (BiS gear has none: 36 targets in 18 specs) and "the earlier
  addon fix covers it". The owner's rule is "never drop a secondary stat row" — verify in game with the Enhancement Shaman.
- A non-English hero-tree name without a subtree id yields no profile (deliberate). Low priority.
