# Item check: addon verdict vs SimulationCraft

Character: Enhancement Shaman. SimC run: 2026-09-29 19:35 UTC. The addon's answer is computed by its own `BuildComparison` on the same items SimC used.

**How to read it.** SimC is the reference (a real simulation). The addon does not simulate; it scores stats with weights. The question is only: does the addon recommend the items that really help, and not the ones that do not? Verdict Points are not DPS, so only the direction and the order are compared.

## MYTHIC_PLUS/GUIDE

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **3**
- OK: both say not an upgrade: **11**
- OK: both say upgrade: **3**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.70** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +497.78 | upgrade | 1485 -> 1380 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | -96.44 | not an upgrade | 1485 -> 1380 (+105) | MISSED: SimC says upgrade, addon does not |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +26.04 | upgrade | 1485 -> 1470 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -327.22 | not an upgrade | 1485 -> 1462 (+23) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | -101.79 | not an upgrade | 1485 -> 1504 (-19) | MISSED: SimC says upgrade, addon does not |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +75.19 | upgrade | 1485 -> 1472 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1485 -> 1572 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -68.49 | not an upgrade | 1485 -> 1483 (+2) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -290.37 | not an upgrade | 1485 -> 1469 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -328.87 | not an upgrade | 1485 -> 1523 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -71.78 | not an upgrade | 1485 -> 1495 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -350.85 | not an upgrade | 1485 -> 1509 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -351.18 | not an upgrade | 1485 -> 1511 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -277.16 | not an upgrade | 1485 -> 1507 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -683.02 | not an upgrade | 1485 -> 1525 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -447.24 | not an upgrade | 1485 -> 1505 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -490.40 | not an upgrade | 1485 -> 1498 (-13) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -117.10 | not an upgrade | 1485 -> 1489 (-4) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Elder Mossveil, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **13 of 17** items (they differ on: Chain of Vengeance, Choker of Anger, Elder Mossveil, Loa-Blessed Beads). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Chain of Vengeance** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 121, Haste 143 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -411.6, Haste +131.3, Item Level +104.0, Critical Strike +79.9
- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -411.6, Haste -153.2, Item Level +104.0, Critical Strike +92.4, Versatility +41.2
- **Ophidian General's Barbute** (head, replaces Elder Mosshorns): MISSED: SimC says upgrade, addon does not. Candidate Agi 106, Haste 72, Vers 79 at ilvl 272, replaced ilvl 250.
  - addon points by stat (weight x amount gained or lost): Mastery -148.0, Item Level +44.0, Versatility +26.1, Haste -23.9

## MYTHIC_PLUS/MEASURED

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.52, Agility 1.72, Crit 1.04, Haste 0.94, Mastery 1.28, Versatility 1.06.

- MISSED: SimC says upgrade, addon does not: **1**
- OK: both say not an upgrade: **11**
- OK: both say upgrade: **5**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.77** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +413.76 | upgrade | 1574 -> 1469 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | -146.47 | not an upgrade | 1574 -> 1469 (+105) | MISSED: SimC says upgrade, addon does not |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +153.47 | upgrade | 1574 -> 1559 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +50.91 | upgrade | 1574 -> 1593 (-19) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +43.08 | upgrade | 1574 -> 1635 (-61) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +45.49 | upgrade | 1574 -> 1561 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +71.80 | upgrade | 1574 -> 1661 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -33.01 | not an upgrade | 1574 -> 1600 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -286.04 | not an upgrade | 1574 -> 1558 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -91.73 | not an upgrade | 1574 -> 1654 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -49.26 | not an upgrade | 1574 -> 1584 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -54.11 | not an upgrade | 1574 -> 1640 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -50.77 | not an upgrade | 1574 -> 1642 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -285.85 | not an upgrade | 1574 -> 1596 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -512.60 | not an upgrade | 1574 -> 1656 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -486.13 | not an upgrade | 1574 -> 1594 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -447.91 | not an upgrade | 1574 -> 1613 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -199.81 | not an upgrade | 1574 -> 1578 (-4) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **13 of 17** items (they differ on: Chain of Vengeance, Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Chain of Vengeance** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 121, Haste 143 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -396.9, Critical Strike +124.6, Item Level +104.0, Haste +21.8

## RAID/GUIDE

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **3**
- OK: both say not an upgrade: **11**
- OK: both say upgrade: **3**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.70** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +496.70 | upgrade | 1009 -> 904 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | -100.16 | not an upgrade | 1009 -> 904 (+105) | MISSED: SimC says upgrade, addon does not |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +34.56 | upgrade | 1009 -> 994 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -318.74 | not an upgrade | 1009 -> 1028 (-19) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | -102.79 | not an upgrade | 1009 -> 1070 (-61) | MISSED: SimC says upgrade, addon does not |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +73.67 | upgrade | 1009 -> 996 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1009 -> 1096 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -70.37 | not an upgrade | 1009 -> 1035 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -292.49 | not an upgrade | 1009 -> 993 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -322.83 | not an upgrade | 1009 -> 1089 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -70.50 | not an upgrade | 1009 -> 1019 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -342.81 | not an upgrade | 1009 -> 1075 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -343.22 | not an upgrade | 1009 -> 1077 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -278.04 | not an upgrade | 1009 -> 1031 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -680.90 | not an upgrade | 1009 -> 1091 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -450.88 | not an upgrade | 1009 -> 1029 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -491.96 | not an upgrade | 1009 -> 1048 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -122.26 | not an upgrade | 1009 -> 1013 (-4) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **15 of 17** items (they differ on: Chain of Vengeance, Loa-Blessed Beads). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Chain of Vengeance** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 121, Haste 143 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -414.9, Haste +126.1, Item Level +104.0, Critical Strike +84.7
- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -414.9, Haste -147.1, Item Level +104.0, Critical Strike +98.0, Versatility +41.2
- **Ophidian General's Barbute** (head, replaces Elder Mosshorns): MISSED: SimC says upgrade, addon does not. Candidate Agi 106, Haste 72, Vers 79 at ilvl 272, replaced ilvl 250.
  - addon points by stat (weight x amount gained or lost): Mastery -149.9, Item Level +44.0, Versatility +26.1, Haste -22.9

## RAID/MEASURED

Hero tree used: `totemic`. Base weights per point of each stat, before the live adjustment (the per-stat lines under a disagreement show the live weights actually used): Item level 0.52, Agility 1.72, Crit 1.10, Haste 1.28, Mastery 0.84, Versatility 1.08.

- OK: both say not an upgrade: **7**
- OK: both say upgrade: **6**
- WRONG: addon says upgrade, SimC says a loss: **4**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.81** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +315.97 | upgrade | 1725 -> 1664 (+61) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +636.95 | upgrade | 1725 -> 1686 (+39) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +36.25 | upgrade | 1725 -> 1680 (+45) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +188.72 | upgrade | 1725 -> 1702 (+23) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +83.25 | upgrade | 1725 -> 1762 (-37) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +75.12 | upgrade | 1725 -> 1729 (-4) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1725 -> 1782 (-57) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | +43.31 | upgrade | 1725 -> 1746 (-21) | WRONG: addon says upgrade, SimC says a loss |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | +267.97 | upgrade | 1725 -> 1732 (-7) | WRONG: addon says upgrade, SimC says a loss |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -443.27 | not an upgrade | 1725 -> 1763 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -87.72 | not an upgrade | 1725 -> 1721 (+4) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | +12.07 | upgrade | 1725 -> 1749 (-24) | WRONG: addon says upgrade, SimC says a loss |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | +10.75 | upgrade | 1725 -> 1751 (-26) | WRONG: addon says upgrade, SimC says a loss |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -316.42 | not an upgrade | 1725 -> 1747 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -367.59 | not an upgrade | 1725 -> 1765 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -354.11 | not an upgrade | 1725 -> 1771 (-46) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -387.91 | not an upgrade | 1725 -> 1752 (-27) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -123.21 | not an upgrade | 1725 -> 1773 (-48) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Rootspeaker's Leggings). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **10 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Elder Mossveil, Loa-Blessed Beads, Rootspeaker's Leggings, Voidbreaker's Circle, Voidbreaker's Signet). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Elder Mossveil** (back, replaces Voidbreaker's Wrap): WRONG: addon says upgrade, SimC says a loss. Candidate Agi 48, Haste 47, Vers 28 at ilvl 250, replaced ilvl 246.
  - addon points by stat (weight x amount gained or lost): Versatility +29.7, Haste +16.5, Mastery -10.9, Item Level +8.0
- **Loa-Blessed Beads** (neck, replaces Voidbreaker's Choker): WRONG: addon says upgrade, SimC says a loss. Candidate Crit 75, Haste 100 at ilvl 233, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Critical Strike +168.8, Haste +100.3, Mastery -27.1, Item Level +26.0
- **Voidbreaker's Circle** (finger, replaces Omission of Light): WRONG: addon says upgrade, SimC says a loss. Candidate Crit 86, Vers 72 at ilvl 220, replaced ilvl 189.
  - addon points by stat (weight x amount gained or lost): Versatility +76.3, Mastery -33.0, Item Level Guard -30.0, Item Level -26.0, Critical Strike +24.8
- **Voidbreaker's Signet** (finger, replaces Omission of Light): WRONG: addon says upgrade, SimC says a loss. Candidate Crit 84, Vers 75 at ilvl 220, replaced ilvl 189.
  - addon points by stat (weight x amount gained or lost): Versatility +79.5, Mastery -33.0, Item Level Guard -30.0, Item Level -26.0, Critical Strike +20.2
