# Item check: addon verdict vs SimulationCraft

Character: Enhancement Shaman. SimC run: 2026-09-29 19:35 UTC. The addon's answer is computed by its own `BuildComparison` on the same items SimC used.

**How to read it.** SimC is the reference (a real simulation). The addon does not simulate; it scores stats with weights. The question is only: does the addon recommend the items that really help, and not the ones that do not? Verdict Points are not DPS, so only the direction and the order are compared.

## MYTHIC_PLUS/GUIDE

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **1**
- OK: both say not an upgrade: **10**
- OK: both say upgrade: **5**
- WRONG: addon says upgrade, SimC says a loss: **1**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.75** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +445.52 | upgrade | 1485 -> 1380 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +53.92 | upgrade | 1485 -> 1380 (+105) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1485 -> 1470 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -144.04 | not an upgrade | 1485 -> 1462 (+23) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1485 -> 1504 (-19) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1485 -> 1472 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1485 -> 1572 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -31.65 | not an upgrade | 1485 -> 1483 (+2) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -170.19 | not an upgrade | 1485 -> 1469 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -313.03 | not an upgrade | 1485 -> 1523 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -76.22 | not an upgrade | 1485 -> 1495 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -230.61 | not an upgrade | 1485 -> 1509 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -231.42 | not an upgrade | 1485 -> 1511 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -291.86 | not an upgrade | 1485 -> 1507 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -571.60 | not an upgrade | 1485 -> 1525 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -418.08 | not an upgrade | 1485 -> 1505 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -456.56 | not an upgrade | 1485 -> 1498 (-13) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1485 -> 1489 (-4) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Elder Mossveil, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **12 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Elder Mossveil, Loa-Blessed Beads, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -337.8, Critical Strike +176.4, Haste -157.8, Item Level +104.0, Versatility +71.2
- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Item Level Guard +130.1, Haste +90.2, Critical Strike -39.1, Mastery -21.2, Item Level +14.0

## MYTHIC_PLUS/MEASURED

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.52, Agility 1.72, Crit 1.04, Haste 0.94, Mastery 1.28, Versatility 1.06.

- OK: both say not an upgrade: **10**
- OK: both say upgrade: **6**
- WRONG: addon says upgrade, SimC says a loss: **1**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.80** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +393.47 | upgrade | 1574 -> 1469 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +82.39 | upgrade | 1574 -> 1469 (+105) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1574 -> 1559 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +73.14 | upgrade | 1574 -> 1593 (-19) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1574 -> 1635 (-61) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1574 -> 1561 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1574 -> 1661 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -4.81 | not an upgrade | 1574 -> 1600 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -129.01 | not an upgrade | 1574 -> 1558 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -209.27 | not an upgrade | 1574 -> 1654 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -68.32 | not an upgrade | 1574 -> 1584 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -67.89 | not an upgrade | 1574 -> 1640 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -67.33 | not an upgrade | 1574 -> 1642 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -300.28 | not an upgrade | 1574 -> 1596 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -464.25 | not an upgrade | 1574 -> 1656 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -424.67 | not an upgrade | 1574 -> 1594 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -427.79 | not an upgrade | 1574 -> 1613 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1574 -> 1578 (-4) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **13 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Item Level Guard +166.7, Haste +60.7, Critical Strike -49.9, Mastery -17.5, Item Level +14.0

## RAID/GUIDE

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **1**
- OK: both say not an upgrade: **10**
- OK: both say upgrade: **5**
- WRONG: addon says upgrade, SimC says a loss: **1**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.75** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +457.01 | upgrade | 1009 -> 904 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +39.56 | upgrade | 1009 -> 904 (+105) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1009 -> 994 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -180.85 | not an upgrade | 1009 -> 1028 (-19) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1009 -> 1070 (-61) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1009 -> 996 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1009 -> 1096 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -44.95 | not an upgrade | 1009 -> 1035 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -185.10 | not an upgrade | 1009 -> 993 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -327.63 | not an upgrade | 1009 -> 1089 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -74.96 | not an upgrade | 1009 -> 1019 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -253.57 | not an upgrade | 1009 -> 1075 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -255.12 | not an upgrade | 1009 -> 1077 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -292.57 | not an upgrade | 1009 -> 1031 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -595.47 | not an upgrade | 1009 -> 1091 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -426.20 | not an upgrade | 1009 -> 1029 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -469.62 | not an upgrade | 1009 -> 1048 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1009 -> 1013 (-4) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **14 of 17** items (they differ on: Ophidian General's Barbute, Loa-Blessed Beads, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -355.1, Critical Strike +182.0, Haste -155.5, Item Level +104.0, Versatility +43.7
- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Item Level Guard +134.7, Haste +88.9, Critical Strike -40.3, Mastery -23.3, Item Level +14.0

## RAID/MEASURED

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.52, Agility 1.72, Crit 1.10, Haste 1.28, Mastery 0.84, Versatility 1.08.

- OK: both say not an upgrade: **8**
- OK: both say upgrade: **6**
- WRONG: addon says upgrade, SimC says a loss: **3**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.84** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +340.01 | upgrade | 1725 -> 1664 (+61) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +441.43 | upgrade | 1725 -> 1686 (+39) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +113.00 | upgrade | 1725 -> 1680 (+45) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +145.45 | upgrade | 1725 -> 1702 (+23) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +81.00 | upgrade | 1725 -> 1762 (-37) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +81.00 | upgrade | 1725 -> 1729 (-4) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1725 -> 1782 (-57) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | +13.67 | upgrade | 1725 -> 1746 (-21) | WRONG: addon says upgrade, SimC says a loss |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | +130.65 | upgrade | 1725 -> 1732 (-7) | WRONG: addon says upgrade, SimC says a loss |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -357.17 | not an upgrade | 1725 -> 1763 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -71.96 | not an upgrade | 1725 -> 1721 (+4) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -69.45 | not an upgrade | 1725 -> 1749 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -68.82 | not an upgrade | 1725 -> 1751 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -304.38 | not an upgrade | 1725 -> 1747 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -422.16 | not an upgrade | 1725 -> 1765 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -407.55 | not an upgrade | 1725 -> 1771 (-46) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -410.93 | not an upgrade | 1725 -> 1752 (-27) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | +6.00 | upgrade | 1725 -> 1773 (-48) | WRONG: addon says upgrade, SimC says a loss |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Rootspeaker's Leggings). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **11 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Elder Mossveil, Loa-Blessed Beads, Rootspeaker's Leggings, Mertei's Command Baton). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Elder Mossveil** (back, replaces Voidbreaker's Wrap): WRONG: addon says upgrade, SimC says a loss. Candidate Agi 48, Haste 47, Vers 28 at ilvl 250, replaced ilvl 246.
  - addon points by stat (weight x amount gained or lost): Mastery -43.9, Versatility +38.9, Haste +10.6, Item Level +8.0
- **Loa-Blessed Beads** (neck, replaces Voidbreaker's Choker): WRONG: addon says upgrade, SimC says a loss. Candidate Crit 75, Haste 100 at ilvl 233, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Critical Strike +132.8, Mastery -109.1, Haste +81.0, Item Level +26.0
- **Mertei's Command Baton** (main_hand, replaces Void-Touched Smasher): WRONG: addon says upgrade, SimC says a loss. Candidate Haste 44, Mastery 24 at ilvl 253, replaced ilvl 263.
  - addon points by stat (weight x amount gained or lost): Agility -168.0, Item Level Guard +161.3, Haste +66.9, Critical Strike -54.9, Item Level +14.0, Mastery -13.3
