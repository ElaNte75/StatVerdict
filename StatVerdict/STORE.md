# StatVerdict — store & launch copy (v1.1.0)

Use this on CurseForge / Wago / Discord. Edit tone freely; keep the audience clear.

---

## Short summary (one line)

Gear upgrade verdicts for Main Spec and Off Spec — smart priorities, no SimulationCraft required.

---

## Tagline options

1. A practical gear check — without opening Raidbots.
2. Main Spec. Off Spec. Clear heuristic verdicts.
3. Gear advice for players who loot first and sim never.

---

## Who it’s for

StatVerdict is for **mid-level and casual players** who want a clear equip / skip answer while they play.

If you already use SimulationCraft for exact character-specific optimization, this addon is not trying to replace that workflow. It provides a fast, explainable heuristic for everyday loot decisions.

---

## What it does

- Marks supported bag and tooltip items when its model finds an upgrade for your **Main Spec** or **Off Spec**
- Shows **Stat Progress** toward build targets, with live Weights
- Lets you **Approve** bag pieces into a virtual loadout for a spec you are not wearing
- Tracks **Best in Slot** progress (Mythic+, Raid, PvP)
- **Guide** drawer: the stat priorities, Best in Slot lists and stat targets are copied from the guides (unchanged); choose Auto (follows your stats, the default) or Tier 1 / 2 / 3

---

## How it works (player-facing)

StatVerdict does **not** simulate your DPS. It uses a practical priority model:

1. **Armor & weapons** — item level and your primary stat (Strength, Agility, or Intellect) come first. Physical weapon DPS and tank armor/stamina are included where relevant. Crit, Haste, Mastery, and Versatility follow your build order, with capped live pressure.
2. **Rings & necks** — often have no primary stat; the top secondary is boosted so jewelry compares fairly.
3. **Trinkets** — validated, goal-specific Best-in-Slot tiers add reference value. StatVerdict does not calculate proc or on-use performance.

Targets and priorities come from bundled guide data. Freshness and quality checks disable a context instead of silently substituting another goal or stale fallback.

Verdict Points are arbitrary heuristic points, not DPS/HPS, survival, win rate, or a measured percentage gain. Empty sockets are not treated as already gemmed. Encounter mechanics, execution, most proc/on-use effects, embellishment power, tertiary value, set-bonus magnitude, and upgrade costs are outside the model.

---

## Why choose it

- **Fast** — verdicts where you already look: bags and tooltips
- **Two specs** — saved MS/OS loadouts; Off Spec live weights require one capture while that spec is active
- **Explainable** — weighted stat differences and reference data, not a hidden performance claim
- **Self-contained** — no external site required to get an answer

---

## Full description (paste-ready)

**StatVerdict** helps you decide whether gear is worth equipping for the specialization you care about — including an Off Spec you are not currently playing.

It is built for players who do **not** want to export characters into Raidbots or SimulationCraft for every drop. Instead, StatVerdict uses a clear priority model: item level and primary stats first, guide-ordered secondaries next, with special handling for rings, necks, and trinkets.

Open your bags, hover an item, and get a supported verdict for Main Spec and Off Spec. Use Stat Progress to see how close you are to your targets. Approve pieces into a virtual loadout when you are gearing a build you are not wearing right now; capture that specialization once before relying on its live weights.

StatVerdict will not replace a full sim. When required profile or snapshot data is missing, stale, or invalid, it reports that no trustworthy verdict is available instead of guessing.

---

## Suggested categories / keywords

Categories: Bags & Inventory, Tooltips, Unit Frames / HUD (if allowed), Raiding & Mythic+

Keywords: gear, upgrade, bis, offspec, mythic+, loot, stats, trinket, priority

---

## Changelog (1.1.0) — paste into CurseForge

```
1.1.0
New
- Guide drawer: Auto (the default) follows your own stats and moves you up to the next tier of targets once you cover about 90% of the current one. Or pick Tier 1, 2 or 3 yourself. The tier in use, and your progress to the next one, are shown in the title bar.
- Best in Slot and Ranked Trinkets follow the tier: Tier 1 shows Champion-track items, Tier 2 Hero, Tier 3 Myth 6/6, so an easier goal never shows gear only the best can have.
- Best in Slot and Ranked Trinkets tooltips: more room, clearer labels, and a "Where to find" line (dungeon or raid and boss) for items the Adventure Journal lists.
- New look for the Features drawer: three clear blocks (Bag Markers, Best in Slot, Ranked Trinkets).
Improved
- Upgrade arrows refresh faster and more reliably, and no longer flicker; buffs no longer move the verdicts.
- Verdicts are the same from both sides: two items can never both be better than each other, and 10 or more item levels always wins.
- Trinkets, rings and necks are compared fairly.
- Stat priorities, Best in Slot lists and stat targets are a 1:1 copy of the guides (Icy Veins and u.gg). The Measured mode has been removed.
- Guide data is now good for 60 days before it counts as out of date, and the message tells you to update.
```

---

## Older changelog (1.0.7)

```
1.0.7
- Added profile freshness, completeness, and goal-consistency gates
- Fixed Off Spec live weights to use captured Off Spec stats
- Added physical weapon DPS and tank armor/stamina to generated profiles
- Empty sockets no longer score as already filled
- Verdict tooltips now disclose heuristic units, baseline, source, and limitations
```

---

## Screenshot checklist (take these in-game)

1. Main window — Stat Progress bars + Weights visible
2. Bag item with MS / OS upgrade markers
3. Tooltip verdict on a hovered item
4. Best in Slot panel
5. Approve / virtual loadout moment (optional but strong)

---

## Launch note (author)

Before upload, run the profile validator and in-game verification checklist, attach current screenshots, and upload the version-matched archive only if every quality gate passes.
