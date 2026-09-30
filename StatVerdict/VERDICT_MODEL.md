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
- **Stat weights** follow the guides' priority by default (Guide mode; stats the
  guide calls roughly equal weigh alike); the Mode drawer can switch to Measured,
  our own simulated values. Guide stat targets come in three tiers (Tier 1 / Tier 2
  / Tier 3, the default being the most demanding); Measured targets come from
  best-in-slot gear at a chosen gear level (Champion / Hero / Myth). A stat with
  no target keeps its row with target 0.
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

## Item level wins, Measured weight sizes

- A candidate more than 5 item levels above the equipped piece never falls below a floor that grows with the gap
  (not for neck, ring, trinket). Up to +5 the stats can still decide.
- Measured secondary shares are proportional to the measured weights; Guide uses rank shares from the guide order.
- The live weights read the character's ratings when gear, spec, talents, level or login change, not on every
  buff: a flask, food or combat buff does not move the verdicts of the moment.
- Live secondary weights: each stat's fixed share is scaled by its distance from the target (same limits for
  every stat, no rank-based limits), then all four are brought back to the fixed budget in proportion; ties in
  the guide stay equal for equal needs.
