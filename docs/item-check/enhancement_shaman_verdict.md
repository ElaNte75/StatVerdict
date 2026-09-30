# Item check: addon verdict vs SimulationCraft

Character: Enhancement Shaman. SimC run: 2026-09-29 19:35 UTC. The addon's answer is computed by its own `BuildComparison` on the same items SimC used.

**How to read it.** SimC is the reference (a real simulation). The addon does not simulate; it scores stats with weights. The question is only: does the addon recommend the items that really help, and not the ones that do not? Verdict Points are not DPS, so only the direction and the order are compared.

## MYTHIC_PLUS/GUIDE

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **2**
- OK: both say not an upgrade: **10**
- OK: both say upgrade: **4**
- WRONG: addon says upgrade, SimC says a loss: **1**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.68** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +491.32 | upgrade | 1485 -> 1380 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | -40.20 | not an upgrade | 1485 -> 1380 (+105) | MISSED: SimC says upgrade, addon does not |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1485 -> 1470 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -325.32 | not an upgrade | 1485 -> 1462 (+23) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1485 -> 1504 (-19) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.65 | upgrade | 1485 -> 1472 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1485 -> 1572 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -53.29 | not an upgrade | 1485 -> 1483 (+2) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -250.47 | not an upgrade | 1485 -> 1469 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -356.99 | not an upgrade | 1485 -> 1523 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -78.62 | not an upgrade | 1485 -> 1495 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -360.73 | not an upgrade | 1485 -> 1509 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -361.06 | not an upgrade | 1485 -> 1511 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -277.54 | not an upgrade | 1485 -> 1507 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -668.20 | not an upgrade | 1485 -> 1525 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -424.44 | not an upgrade | 1485 -> 1505 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -477.48 | not an upgrade | 1485 -> 1498 (-13) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1485 -> 1489 (-4) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Elder Mossveil, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **11 of 17** items (they differ on: Chain of Vengeance, Choker of Anger, Ophidian General's Barbute, Elder Mossveil, Loa-Blessed Beads, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Chain of Vengeance** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 121, Haste 143 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -380.5, Haste +156.4, Item Level +104.0, Critical Strike +79.9
- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -380.5, Haste -182.5, Item Level +104.0, Critical Strike +92.4, Versatility +41.2
- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Haste +104.3, Item Level Guard +102.6, Mastery -26.4, Critical Strike -20.5, Item Level +14.0

## MYTHIC_PLUS/MEASURED

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.52, Agility 1.72, Crit 1.04, Haste 0.94, Mastery 1.28, Versatility 1.06.

- OK: both say not an upgrade: **10**
- OK: both say upgrade: **6**
- WRONG: addon says upgrade, SimC says a loss: **1**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.78** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +387.98 | upgrade | 1574 -> 1469 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +19.48 | upgrade | 1574 -> 1469 (+105) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +145.32 | upgrade | 1574 -> 1559 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +124.66 | upgrade | 1574 -> 1593 (-19) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1574 -> 1635 (-61) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1574 -> 1561 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +60.49 | upgrade | 1574 -> 1661 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -14.75 | not an upgrade | 1574 -> 1600 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -167.99 | not an upgrade | 1574 -> 1558 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -147.81 | not an upgrade | 1574 -> 1654 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -58.38 | not an upgrade | 1574 -> 1584 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -16.23 | not an upgrade | 1574 -> 1640 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -15.14 | not an upgrade | 1574 -> 1642 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -301.08 | not an upgrade | 1574 -> 1596 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -454.82 | not an upgrade | 1574 -> 1656 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -452.68 | not an upgrade | 1574 -> 1594 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -434.48 | not an upgrade | 1574 -> 1613 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1574 -> 1578 (-4) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **13 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Item Level Guard +198.6, Agility -168.0, Critical Strike -51.5, Haste +33.9, Mastery -21.0, Item Level +14.0

## RAID/GUIDE

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **2**
- OK: both say not an upgrade: **10**
- OK: both say upgrade: **4**
- WRONG: addon says upgrade, SimC says a loss: **1**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.67** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +486.99 | upgrade | 1009 -> 904 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | -38.59 | not an upgrade | 1009 -> 904 (+105) | MISSED: SimC says upgrade, addon does not |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1009 -> 994 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -301.60 | not an upgrade | 1009 -> 1028 (-19) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1009 -> 1070 (-61) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1009 -> 996 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1009 -> 1096 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -55.26 | not an upgrade | 1009 -> 1035 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -247.90 | not an upgrade | 1009 -> 993 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -346.30 | not an upgrade | 1009 -> 1089 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -76.54 | not an upgrade | 1009 -> 1019 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -340.70 | not an upgrade | 1009 -> 1075 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -341.25 | not an upgrade | 1009 -> 1077 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -280.04 | not an upgrade | 1009 -> 1031 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -659.25 | not an upgrade | 1009 -> 1091 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -429.65 | not an upgrade | 1009 -> 1029 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -479.05 | not an upgrade | 1009 -> 1048 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1009 -> 1013 (-4) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **13 of 17** items (they differ on: Chain of Vengeance, Ophidian General's Barbute, Loa-Blessed Beads, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Chain of Vengeance** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 121, Haste 143 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -382.9, Haste +147.2, Item Level +104.0, Critical Strike +93.2
- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -382.9, Haste -171.7, Critical Strike +107.8, Item Level +104.0, Versatility +41.2
- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Item Level Guard +112.4, Haste +98.1, Mastery -26.7, Critical Strike -23.9, Item Level +14.0

## RAID/MEASURED

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.52, Agility 1.72, Crit 1.10, Haste 1.28, Mastery 0.84, Versatility 1.08.

- OK: both say not an upgrade: **8**
- OK: both say upgrade: **6**
- WRONG: addon says upgrade, SimC says a loss: **3**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.85** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +317.02 | upgrade | 1725 -> 1664 (+61) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +520.52 | upgrade | 1725 -> 1686 (+39) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1725 -> 1680 (+45) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +213.07 | upgrade | 1725 -> 1702 (+23) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +107.11 | upgrade | 1725 -> 1762 (-37) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1725 -> 1729 (-4) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1725 -> 1782 (-57) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | +37.98 | upgrade | 1725 -> 1746 (-21) | WRONG: addon says upgrade, SimC says a loss |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | +192.52 | upgrade | 1725 -> 1732 (-7) | WRONG: addon says upgrade, SimC says a loss |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -362.16 | not an upgrade | 1725 -> 1763 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -77.52 | not an upgrade | 1725 -> 1721 (+4) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -1.28 | not an upgrade | 1725 -> 1749 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -0.47 | not an upgrade | 1725 -> 1751 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -308.38 | not an upgrade | 1725 -> 1747 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -372.83 | not an upgrade | 1725 -> 1765 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -383.36 | not an upgrade | 1725 -> 1771 (-46) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -388.82 | not an upgrade | 1725 -> 1752 (-27) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1725 -> 1773 (-48) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Rootspeaker's Leggings). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **11 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Elder Mossveil, Loa-Blessed Beads, Rootspeaker's Leggings, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Elder Mossveil** (back, replaces Voidbreaker's Wrap): WRONG: addon says upgrade, SimC says a loss. Candidate Agi 48, Haste 47, Vers 28 at ilvl 250, replaced ilvl 246.
  - addon points by stat (weight x amount gained or lost): Versatility +43.4, Mastery -25.7, Haste +12.3, Item Level +8.0
- **Loa-Blessed Beads** (neck, replaces Voidbreaker's Choker): WRONG: addon says upgrade, SimC says a loss. Candidate Crit 75, Haste 100 at ilvl 233, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Critical Strike +144.0, Haste +86.5, Mastery -64.0, Item Level +26.0
- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Item Level Guard +149.9, Haste +77.4, Critical Strike -59.5, Item Level +14.0, Mastery -7.8
