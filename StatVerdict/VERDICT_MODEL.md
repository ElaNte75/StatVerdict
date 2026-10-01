# StatVerdict verdict contract

StatVerdict is a deterministic heuristic gear comparer. It is not a combat
simulation and its scores are not DPS, healing, survival, or win-rate
percentages.

## Signals

- **Verdict points** are the weighted stat difference between a candidate and
  its comparison baseline, plus any validated reference adjustment.
- **Upgrade** means verdict points are positive after eligibility and safety
  rules. It does not mean a measured performance gain.
- **Live weights** redistribute a capped secondary-stat budget toward profile
  targets. Item level and primary-stat weights remain fixed anchors.
- **Best in Slot and trinket references** (Mythic+, Raid and PvP: curated guide
  lists, tiered trinkets) are hints from goal-specific profile data. They may only
  affect a verdict when that data passes the profile quality and freshness checks.
  A found item with an upgrade track counts like the Best in Slot piece when that
  piece is a tier-set piece (the Catalyst rule).
- **Stat weights** follow the guides' priority (stats the guide calls roughly
  equal weigh alike), copied unchanged. Guide stat targets come in three tiers
  (Tier 1 / Tier 2 / Tier 3), chosen in the Guide drawer: Auto (the default) or one
  fixed tier, never both. Auto shows the targets of the next tier above the highest
  one the stats cover: it moves up at 90% of a tier's rating targets and back down
  only below 80% (remembered per spec); Best in Slot and trinkets follow the tier
  shown. A stat with no target keeps its row with target 0.
- **Diminishing returns.** A swap is judged by what it really adds to the stats you have now:
  the game takes an increasing cut off rating past about 30% of a stat, so the change in the
  effective stat (after the cuts) is scored, not a straight count of rating. Below the first
  cut the two are identical.
- **Main Spec baseline** is currently equipped gear.
- **Off Spec baseline** is the saved virtual loadout. Dynamic off-spec weights
  require stats captured while that specialization was active.

## Fail-closed rules

StatVerdict must not produce an authoritative verdict when:

- the selected goal has no matching generated context;
- profile data is stale, incomplete, cross-goal, or fails its quality checks;
- an Off Spec virtual loadout or its captured stats are missing;
- item data needed for a comparison is unavailable.

The UI must identify unavailable or degraded data instead of silently replacing
it with another goal, another specialization's live stats, or a hard-coded
target presented as sourced data.

## Modelled inputs

- item level;
- the profile primary stat;
- Crit, Haste, Mastery, and Versatility in profile order;
- actual socketed gem stats;
- weapon DPS for weapon comparisons;
- armor and stamina for tank profiles;
- validated goal-specific BiS/trinket references;
- equip restrictions, unique-equipped limits, tier preservation, and weapon-set
  replacement rules.

Empty sockets have no immediate stat value. Their potential is shown only as
item context and is not treated as if a best-in-slot gem were already present.

## Not modelled

- encounter mechanics and player execution;
- proc/on-use value outside validated bundled reference tiers;
- embellishment damage or healing;
- tertiary-stat value, enchants, set-bonus magnitude, and crafted-effect value;
- future upgrade currency cost or probabilistic loot value.

These omissions must not be described as included in store copy, the in-game
manual, or tooltips.

## Data provenance

Generated profiles record their source, scrape date, generation date, resolver
summary, and per-context quality state. Shipping is blocked when required
profiles are missing, unresolved data exceeds the accepted threshold, targets
are implausible, or data is too old. Runtime loading repeats the safety checks
so manually copied or stale generated files fail closed.

## Item level wins

- A candidate 10 or more item levels above the equipped piece never falls below a floor that grows with the gap
  (not for neck, ring, trinket). Up to +5 the stats can still decide.
- Secondary shares are rank shares from the guide order.
- The live weights read the character's ratings when gear, spec, talents, level or login change, not on every
  buff: a flask, food or combat buff does not move the verdicts of the moment.
- Live secondary weights: the guide's order becomes starting shares of the fixed 6.00 budget (places worth
  1.4 : 1.25 : 1.1 : 1, stats the guide calls equal share the average). Each share is then scaled by the
  stat's need: rating missing, counted in points (a gap a gem or enchant can close counts for nothing, the full
  +25% from about 400 points), only as far as the stats above it in the order have got to their own targets
  (the gate: the top of the order is filled first, the stats below take over as it gets there), and down to
  0.75x for rating over the target. The four are brought back to the budget in proportion, so nobody is drained
  first and ties stay equal for equal needs. The Weight cell's tooltip shows the starting and the current value.
- A piece counts as an upgrade from 1% of the score of the piece it replaces (item level 10 or more excepted).
- A swap is judged with the live weights read at the MIDDLE of the swap (rating now plus half of the change), so
  the verdict of piece A over piece B is exactly the opposite of B over A: two pieces are never both better than
  each other. Item level wins in both directions from 10 item levels (jewelry and trinkets excepted), and the
  small-primary forgiveness is given and taken back the same way.
- Pieces without a primary stat (rings, necks, trinkets): the first secondary of the guide's order is scored as the
  primary stat, the others keep their weights; a trinket's stats are no longer damped. An item of the guide's
  Best in Slot list gets a bonus of 100 (it wins whatever its stats, unless the Item Level Guard decides
  against it), a trinket of the list also its tier bonus (S 95, A 65, B 35, C 14, D 0) and a small one for its
  place inside the tier. A piece the Catalyst can turn into the set piece of the list counts as that piece.
