# StatVerdict — store & launch copy (v1.0.7)

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
- Tracks **Best in Slot** progress for your chosen goal (Mythic+, Raid, PvP)

---

## How it works (player-facing)

StatVerdict does **not** simulate your DPS. It uses a practical priority model:

1. **Armor & weapons** — item level and your primary stat (Strength, Agility, or Intellect) come first. Physical weapon DPS and tank armor/stamina are included where relevant. Crit, Haste, Mastery, and Versatility follow your build order, with capped live pressure.
2. **Rings & necks** — often have no primary stat; the top secondary is boosted so jewelry compares fairly.
3. **Trinkets** — validated, goal-specific Best-in-Slot tiers add reference value. StatVerdict does not calculate proc or on-use performance.

Targets and priorities come from bundled ClassCodex profile data. Freshness and quality checks disable a context instead of silently substituting another goal or stale fallback.

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

It is built for players who do **not** want to export characters into Raidbots or SimulationCraft for every drop. Instead, StatVerdict uses a clear priority model: item level and primary stats first, ClassCodex-ordered secondaries next, with special handling for rings, necks, and trinkets.

Open your bags, hover an item, and get a supported verdict for Main Spec and Off Spec. Use Stat Progress to see how close you are to your targets. Approve pieces into a virtual loadout when you are gearing a build you are not wearing right now; capture that specialization once before relying on its live weights.

StatVerdict will not replace a full sim. When required profile or snapshot data is missing, stale, or invalid, it reports that no trustworthy verdict is available instead of guessing.

---

## Suggested categories / keywords

Categories: Bags & Inventory, Tooltips, Unit Frames / HUD (if allowed), Raiding & Mythic+

Keywords: gear, upgrade, bis, offspec, mythic+, loot, stats, trinket, priority

---

## Changelog stub (1.0.7)

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
