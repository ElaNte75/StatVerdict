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
