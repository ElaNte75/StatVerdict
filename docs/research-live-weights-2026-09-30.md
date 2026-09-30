# Research: is the live weight mechanism of the addon right? (2026-09-30)

Question from the owner: does the way the addon weighs stats and judges a piece of gear (a fixed budget of
weights, redistributed live by the stats the character has now, with diminishing returns and item level in
mind) match how World of Warcraft really works and how expert guides tell players to gear, and is it
implemented correctly?

Method: web research (search-result excerpts; the pages themselves were blocked by the sandbox's network
proxy, so quotes below are as returned by the search tool, not read in full), then experiments on the addon
itself in the test harness (real Lua 5.1, the real generated data, the real scoring code), and the SimC
item check of the owner's Enhancement Shaman (`docs/item-check/`).

## 1. What the game and the experts say

| Topic | What sources say | Sources |
|---|---|---|
| Diminishing returns | Every secondary stat has cuts on its percent: none up to 30%, then 10%, 20%, 30%, 40%, 50% per bracket. At level 90, 1% needs 44 Haste, 46 Crit, 54 Versatility rating; Mastery depends on the spec. Haste brackets: 1320-1760 (-10%), 1760-2200 (-20%), 2200-2640 (-30%), 2640-3080 (-40%), 3080+ (-50%). | [Maxroll](https://maxroll.gg/wow/resources/stat-diminishing-returns), [Wowhead](https://www.wowhead.com/guide/diminishing-returns-on-secondary-stats-in-world-of-warcraft), [Warcraft Wiki](https://warcraft.wiki.gg/wiki/Combat_rating_system) |
| Item level first | "Any increase in item level is an upgrade"; an item 10 or more item levels higher "will almost always be an upgrade"; the stat priority is "only really useful comparing" items of the same item level, because primary stat and secondaries both scale with item level. | [Icy Veins stat priority guides](https://www.icy-veins.com/wow/enhancement-shaman-pve-dps-stat-priority), community summaries ([Blizzard forums](https://us.forums.blizzard.com/en/wow/t/ilvl-vs-stats/1808601), [MMO-Champion](https://www.mmo-champion.com/threads/2643662-Is-everything-about-item-level-or-do-stats-even-matter)) |
| Jewelry exception | Rings, necks, trinkets have no primary stat, so secondaries matter more there: a lower item level piece with much better stats can beat a higher one. | same |
| Stat weights are local | Scale factors are "only valid linear approximations in a small area around the gear you simulate them with"; change the gear and the weights change, so they must be recomputed. Rings and necks are the most volatile; weights ignore trinket effects and set bonuses. Direct sims (Top Gear) are more accurate. | [Raidbots](https://support.raidbots.com/article/66-beware-of-stat-weights), [SimC wiki](https://github.com/simulationcraft/simc/wiki/Features), [Icy Veins forum](https://www.icy-veins.com/forums/topic/7275-scale-factors-and-you-an-explanation-of-stat-weights/) |
| Stat balance | Stats are multiplicative and each has diminishing value, so a balanced character out-performs a lopsided one at the same gear level. | general theorycraft, e.g. [Wowhead](https://www.wowhead.com/guide/diminishing-returns-on-secondary-stats-in-world-of-warcraft) |
| Enhancement Shaman (12.1) | Totemic: Item Level > Mastery > Haste > Crit > Versatility. Stormbringer: Item Level > Mastery > Crit > Haste > Versatility, with Crit and Mastery "neck-and-neck". Versatility is generally last. | [Icy Veins](https://www.icy-veins.com/wow/enhancement-shaman-pve-dps-stat-priority), [Maxroll/Method summaries](https://www.method.gg/guides/enhancement-shaman/stats-races-and-consumables) |

## 2. Does the design match this?

Yes, in concept. Compared with what experts say:

- **Live, local weights**: the guides' own warning ("weights are only valid near your current gear, re-sim when
  it changes") is exactly the reason for a live mechanism. The addon's idea is sound.
- **Item level and primary stat as fixed anchors**, secondaries redistributed inside a budget: consistent with
  "item level first, stat priority second".
- **Jewelry gets the primary stat's weight moved onto the top secondary** (+2.00): consistent with the jewelry
  exception.
- **Diminishing returns**: the vendored curve matches the published brackets (Haste cuts start at 1320 rating,
  Crit at 1380). It was loaded but never used; now the scoring uses it (see the commit "Scoring: diminishing
  returns").
- **Stat order for Enhancement Totemic** in the addon's guide data (Mastery, Haste, Crit, Versatility) is the
  same as Icy Veins'.

## 3. Is it implemented correctly? (experiments)

Verified by experiment, all with the real code:

1. **The budget is fixed.** The four secondary weights add up to exactly 6.00 in every situation tried (armor)
   and 8.00 on necks/rings (6.00 + the 2.00 primary transfer); the first stat takes from the last first. OK.
2. **The weights move with the character's current stats.** Same item, only the current Haste changed:
   Haste weight 1.99 (far below target) down to 1.35 (far above); Mastery 5.24 down to 4.21. OK. (An earlier
   test run showed no movement because the test environment did not define the game's rating ids
   `CR_HASTE_MELEE` etc.; that was the test's fault, fixed in `tools/item_check_verdict.py`.)
3. **The Stat Progress table now shows the weights the scoring really uses** (it used an older model before).
4. **Item level beats stats**, tested on a chest and a neck with two-stat items like real ones:
   - same split, any higher item level: upgrade, always. OK.
   - in **Measured** mode a higher item level was an upgrade for every split from +3 item levels. OK.
   - in **Guide** mode it is not: a chest **+10 item levels** with Crit+Versatility scored **-147** (Haste+Vers -38,
     Mastery+Vers -17), and +20 item levels with all stats in Versatility scored -177. This contradicts "10 or
     more item levels is almost always an upgrade". FINDING A.

## 4. Findings (what is wrong or fragile)

**A. The gaps between the four secondaries are far bigger than in reality (most important).**
The scoring turns the guide's *order* into fixed shares 4:3:2:1 of the secondary budget. Real stat values are
much closer: the SimC scale factors in the addon's own data for Enhancement Totemic Mythic+ are Mastery 1.00,
Versatility 0.83, Crit 0.81, Haste 0.74 (a spread of about 1.35x, not 4x); the guides call Crit and Mastery
"neck-and-neck". The steep shares let a bad split outweigh a large item-level gain (finding above) and are why
Guide mode misses two real upgrades (Choker of Anger and Ophidian General's Barbute, both about +1% in SimC).

What-if on the owner's character (17 SimC items, 4 situations), changing only the four shares:

| Shares | M+ Guide | M+ Measured | Raid Guide | Raid Measured |
|---|---|---|---|---|
| 4 : 3 : 2 : 1 (now) | 13/17, order 0.74 | 16/17, 0.89 | 14/17, 0.73 | 15/17, 0.89 |
| 1.5 : 1.25 : 1 : 0.8 | 15/17, 0.78 | 16/17, 0.89 | 15/17, 0.78 | 15/17, 0.89 |
| 1.35 : 1.2 : 1.1 : 1 | 15/17, 0.83 | 17/17, 0.90 | 15/17, 0.84 | 15/17, 0.89 |
| all equal | 15/17, 0.91 | 17/17, 0.91 | 15/17, 0.90 | 15/17, 0.88 |

("n/17" = items where the addon and SimC agree upgrade/not upgrade; the second number is rank agreement,
1.0 = same order.) Flatter shares agree with SimC better everywhere. Caution: one character, 17 items.

**B. Measured mode uses only the order of the SimC weights, not their size.** The magnitudes (0.74 to 1.00)
are thrown away and replaced by the same 4:3:2:1 shares. Proportional shares (`6.00 x weight / sum`) would
keep what was measured.

**C. The measured order differs from the guides for this spec.** Enhancement Totemic Raid: Haste 1.00, Crit
0.86, Vers 0.84, Mastery 0.66 (guides: Mastery first); Mythic+: Versatility second (guides: last). Values are
close, so the order is fragile (noise), or the loadout simulated differs from the guides'. Needs a look at the
SimC profile and talents used by the pipeline.

**D. Necks and rings are the most volatile** (also warned by Raidbots): the +2.00 transfer puts the top stat at
about 5.0 per point, more than Agility (4.0). Most misses in the SimC comparison are necks.

**E. Bag arrows can be stale** after a change in ratings that is not an equipment change (flask, food, potion,
level up); tooltips are always fresh. Also, buffs count as stats (combat ratings include consumables).

**F. Only one character was validated** (17 items). Enough to find A and B, not enough to tune numbers.

## 5. Recommendations (nothing below is implemented yet)

1. Flatten the secondary shares (A/B): Measured = proportional to the measured weights; Guide = a mild prior
   (for example 1.35 : 1.2 : 1.1 : 1) instead of 4:3:2:1. Needs the owner's decision (it changes the logic).
2. Build a wider validation before tuning numbers: the item check for 4-6 more specs/characters (a
   character file each), in the same workflow, and compare all with SimC.
3. Check the SimC pipeline against the guides for C (talent build, gear level, scenario).
4. Refresh bag arrows on rating changes, debounced (E).
5. Keep diminishing returns as implemented; it only matters above about 30% of a stat, so it changes little
   for low and mid gear and protects the high end.

## 6. Implemented after the owner's decision (2026-09-30)

Owner's rule: two data sets (Guide = 1:1 guide copy, Measured = our SimC), one decision mechanism. Only the
mechanism changed, not the data:

- **Item level wins.** A candidate more than 5 item levels above the equipped piece can no longer score below a
  floor that grows with the gap (gap 6-10, 11-20, 21+); up to +5 it may still lose. Necks, rings and trinkets are
  exempt (no primary stat). Row shown as "Item Level Guard".
- **Measured uses the size of the measured weights** (shares = 6.00 x weight / sum) instead of rank shares 4:3:2:1.
  Guide keeps rank shares (ties averaged) untouched.
- **Diminishing returns** now also apply in the equipped-set comparison.
- Tests: `tools/tests/test_scoring_mechanism.py`. Item check re-run: see `docs/item-check/enhancement_shaman_verdict.md`
  (Guide M+ rank agreement 0.68 in the first table; the Guide is not tuned toward SimC by design).

## 7. Live weights redone (2026-09-30, after in-game tests)

In-game screenshots (Guardian Druid and Blood Death Knight) showed three faults of the old live allocation:
saturating limits (a stat 40% or more short got the same boost whether 500 or 776 rating short), limits that
depended on the stat's rank (the last-ranked stat could gain at most +5%), and a "last first" donor order that
drained the last stat to a floor whenever every stat was short (Blood: Haste 42% short but weight 0.33, ten
times below Crit). A guide tie (Mastery = Versatility) also turned into a 2:1 split.

New rule, the same for Guide and Measured: each stat's fixed share is scaled by its distance from the target
(up to 1.5x with nothing yet, down to 0.65x at 60% or more over the target, same limits for every stat), then
all four are brought back to the fixed 6.00 budget in proportion. Ties stay equal for equal needs; nobody is
drained first. Guide data (order, ties) and Measured data (SimC weights) are unchanged.

Item check after the change (Enhancement Shaman, 17 items): Guide rank agreement with SimC M+ 0.75 (was 0.74),
Raid 0.75 (was 0.73); Measured M+ 0.80 (was 0.89), Raid 0.84 (was 0.89). The Measured order agreement fell a
little while the upgrade / not upgrade agreement stayed at 16 of 17 for M+; this is one character and should be
watched.

The stat target cards read Tier 1 (easiest, u.gg top80), Tier 2 (top50), Tier 3 (hardest, top20; the default) from
left to right. Saved keys unchanged.
