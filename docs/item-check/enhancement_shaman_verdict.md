# Item check: addon verdict vs SimulationCraft

Character: Enhancement Shaman. SimC run: 2026-09-29 19:35 UTC. The addon's answer is computed by its own `BuildComparison` on the same items SimC used.

**How to read it.** SimC is the reference (a real simulation). The addon does not simulate; it scores stats with weights. The question is only: does the addon recommend the items that really help, and not the ones that do not? Verdict Points are not DPS, so only the direction and the order are compared.

## MYTHIC_PLUS/GUIDE

Hero tree used: `totemic`. Weights the addon uses per point of each stat: Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **2**
- OK: both say not an upgrade: **11**
- OK: both say upgrade: **4**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.78** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +451.60 | upgrade | 1485 -> 1380 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +7.20 | upgrade | 1485 -> 1380 (+105) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +56.80 | upgrade | 1485 -> 1470 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -152.40 | not an upgrade | 1485 -> 1462 (+23) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | -47.80 | not an upgrade | 1485 -> 1504 (-19) | MISSED: SimC says upgrade, addon does not |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +69.80 | upgrade | 1485 -> 1472 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1485 -> 1572 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -41.80 | not an upgrade | 1485 -> 1483 (+2) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -203.40 | not an upgrade | 1485 -> 1469 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -292.40 | not an upgrade | 1485 -> 1523 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -71.60 | not an upgrade | 1485 -> 1495 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -229.00 | not an upgrade | 1485 -> 1509 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -229.60 | not an upgrade | 1485 -> 1511 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -290.20 | not an upgrade | 1485 -> 1507 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -585.40 | not an upgrade | 1485 -> 1525 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -433.80 | not an upgrade | 1485 -> 1505 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -465.00 | not an upgrade | 1485 -> 1498 (-13) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -136.00 | not an upgrade | 1485 -> 1489 (-4) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Elder Mossveil, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **14 of 17** items (they differ on: Choker of Anger, Elder Mossveil, Loa-Blessed Beads). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -360.8, Critical Strike +168.0, Haste -138.6, Item Level +104.0, Versatility +75.0
- **Ophidian General's Barbute** (head, replaces Elder Mosshorns): MISSED: SimC says upgrade, addon does not. Candidate Agi 106, Haste 72, Vers 79 at ilvl 272, replaced ilvl 250.
  - addon points by stat (weight x amount gained or lost): Mastery -117.6, Versatility +47.4, Item Level +44.0, Haste -21.6

## MYTHIC_PLUS/MEASURED

Hero tree used: `totemic`. Weights the addon uses per point of each stat: Item level 0.52, Agility 1.72, Crit 1.04, Haste 0.94, Mastery 1.28, Versatility 1.06.

- MISSED: SimC says upgrade, addon does not: **1**
- OK: both say not an upgrade: **11**
- OK: both say upgrade: **5**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.79** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +398.80 | upgrade | 1574 -> 1469 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | -72.00 | not an upgrade | 1574 -> 1469 (+105) | MISSED: SimC says upgrade, addon does not |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +136.00 | upgrade | 1574 -> 1559 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +90.00 | upgrade | 1574 -> 1593 (-19) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +61.40 | upgrade | 1574 -> 1635 (-61) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +49.40 | upgrade | 1574 -> 1561 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +64.84 | upgrade | 1574 -> 1661 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -16.60 | not an upgrade | 1574 -> 1600 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -231.00 | not an upgrade | 1574 -> 1558 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -111.20 | not an upgrade | 1574 -> 1654 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -54.80 | not an upgrade | 1574 -> 1584 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -35.80 | not an upgrade | 1574 -> 1640 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -32.80 | not an upgrade | 1574 -> 1642 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -290.20 | not an upgrade | 1574 -> 1596 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -479.80 | not an upgrade | 1574 -> 1656 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -465.00 | not an upgrade | 1574 -> 1594 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -433.80 | not an upgrade | 1574 -> 1613 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -188.80 | not an upgrade | 1574 -> 1578 (-4) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **13 of 17** items (they differ on: Chain of Vengeance, Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Chain of Vengeance** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 121, Haste 143 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -360.8, Critical Strike +145.2, Item Level +104.0, Haste +39.6

## RAID/GUIDE

Hero tree used: `totemic`. Weights the addon uses per point of each stat: Item level 0.50, Agility 1.65, Crit 0.83, Haste 1.65, Mastery 1.65, Versatility 0.41.

- MISSED: SimC says upgrade, addon does not: **2**
- OK: both say not an upgrade: **11**
- OK: both say upgrade: **4**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.78** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +451.60 | upgrade | 1009 -> 904 (+105) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +7.20 | upgrade | 1009 -> 904 (+105) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +56.80 | upgrade | 1009 -> 994 (+15) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | -152.40 | not an upgrade | 1009 -> 1028 (-19) | MISSED: SimC says upgrade, addon does not |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | -47.80 | not an upgrade | 1009 -> 1070 (-61) | MISSED: SimC says upgrade, addon does not |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +69.80 | upgrade | 1009 -> 996 (+13) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1009 -> 1096 (-87) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | -41.80 | not an upgrade | 1009 -> 1035 (-26) | OK: both say not an upgrade |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | -203.40 | not an upgrade | 1009 -> 993 (+16) | OK: both say not an upgrade |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -292.40 | not an upgrade | 1009 -> 1089 (-80) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -71.60 | not an upgrade | 1009 -> 1019 (-10) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -229.00 | not an upgrade | 1009 -> 1075 (-66) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -229.60 | not an upgrade | 1009 -> 1077 (-68) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -290.20 | not an upgrade | 1009 -> 1031 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -585.40 | not an upgrade | 1009 -> 1091 (-82) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -433.80 | not an upgrade | 1009 -> 1029 (-20) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -465.00 | not an upgrade | 1009 -> 1048 (-39) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -136.00 | not an upgrade | 1009 -> 1013 (-4) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Choker of Anger, Ophidian General's Barbute, Loa-Blessed Beads). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **16 of 17** items (they differ on: Loa-Blessed Beads). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Choker of Anger** (neck, replaces Voidbreaker's Choker): MISSED: SimC says upgrade, addon does not. Candidate Crit 140, Vers 125 at ilvl 272, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Mastery -360.8, Critical Strike +168.0, Haste -138.6, Item Level +104.0, Versatility +75.0
- **Ophidian General's Barbute** (head, replaces Elder Mosshorns): MISSED: SimC says upgrade, addon does not. Candidate Agi 106, Haste 72, Vers 79 at ilvl 272, replaced ilvl 250.
  - addon points by stat (weight x amount gained or lost): Mastery -117.6, Versatility +47.4, Item Level +44.0, Haste -21.6

## RAID/MEASURED

Hero tree used: `totemic`. Weights the addon uses per point of each stat: Item level 0.52, Agility 1.72, Crit 1.10, Haste 1.28, Mastery 0.84, Versatility 1.08.

- OK: both say not an upgrade: **9**
- OK: both say upgrade: **6**
- WRONG: addon says upgrade, SimC says a loss: **2**
- not compared: **1**
- Rank agreement (Spearman, addon points vs SimC gain, 17 items): **0.81** (1.0 = same order, 0 = unrelated)

| Item | Slot | SimC gain (ST) | SimC says | Addon points | Addon says | Target stats: shortfall before -> after | Result |
|---|---|---:|---|---:|---|---|---|
| Collar of Jealousy | neck | +2.33% ±0.07 | upgrade | +334.20 | upgrade | 1725 -> 1664 (+61) | OK: both say upgrade |
| Chain of Vengeance | neck | +1.46% ±0.07 | upgrade | +563.00 | upgrade | 1725 -> 1686 (+39) | OK: both say upgrade |
| Faithleaper's Sabatons | feet | +1.17% ±0.07 | upgrade | +13.00 | upgrade | 1725 -> 1680 (+45) | OK: both say upgrade |
| Choker of Anger | neck | +1.11% ±0.07 | upgrade | +118.00 | upgrade | 1725 -> 1702 (+23) | OK: both say upgrade |
| Ophidian General's Barbute | head | +1.05% ±0.07 | upgrade | +80.60 | upgrade | 1725 -> 1762 (-37) | OK: both say upgrade |
| Fangsmasher Gauntlets | hands | +0.96% ±0.07 | upgrade | +77.60 | upgrade | 1725 -> 1729 (-4) | OK: both say upgrade |
| Breath of Jan'alai | trinket | +0.28% ±0.07 | unreliable | +50.60 | upgrade | 1725 -> 1782 (-57) | not compared |
| Elder Mossveil | back | -0.13% ±0.07 | downgrade | +38.60 | upgrade | 1725 -> 1746 (-21) | WRONG: addon says upgrade, SimC says a loss |
| Loa-Blessed Beads | neck | -0.21% ±0.07 | downgrade | +213.00 | upgrade | 1725 -> 1732 (-7) | WRONG: addon says upgrade, SimC says a loss |
| Tarnished Dawnlit Pendant | neck | -0.41% ±0.07 | downgrade | -436.80 | not an upgrade | 1725 -> 1763 (-38) | OK: both say not an upgrade |
| Rootspeaker's Leggings | legs | -0.55% ±0.07 | downgrade | -87.20 | not an upgrade | 1725 -> 1721 (+4) | OK: both say not an upgrade |
| Voidbreaker's Circle | finger | -1.11% ±0.07 | downgrade | -9.80 | not an upgrade | 1725 -> 1749 (-24) | OK: both say not an upgrade |
| Voidbreaker's Signet | finger | -1.14% ±0.07 | downgrade | -9.80 | not an upgrade | 1725 -> 1751 (-26) | OK: both say not an upgrade |
| Voidbreaker's Sash | waist | -1.29% ±0.07 | downgrade | -305.80 | not an upgrade | 1725 -> 1747 (-22) | OK: both say not an upgrade |
| Tarnished Dawnlit Corsair's Tunic | chest | -6.74% ±0.07 | downgrade | -407.20 | not an upgrade | 1725 -> 1765 (-40) | OK: both say not an upgrade |
| Dawnforged Ritual Knife | main_hand | -35.23% ±0.06 | downgrade | -360.00 | not an upgrade | 1725 -> 1771 (-46) | OK: both say not an upgrade |
| Blood-Tempered Bulwark | off_hand | -42.30% ±0.06 | downgrade | -391.20 | not an upgrade | 1725 -> 1752 (-27) | OK: both say not an upgrade |
| Mertei's Command Baton | main_hand | -56.86% ±0.05 | downgrade | -110.20 | not an upgrade | 1725 -> 1773 (-48) | OK: both say not an upgrade |

### Three-way check: SimC DPS, target stats, addon

The addon aims at the target stats (the ratings that give the best result), SimC measures DPS. An item is counted as helping the targets when it lowers the total rating shortfall.

- Target stats agree with SimC on **14 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Rootspeaker's Leggings). A difference here points at the *targets* (or at what the targets leave out: item level, primary stat).
- Addon agrees with the target stats on **12 of 17** items (they differ on: Ophidian General's Barbute, Fangsmasher Gauntlets, Elder Mossveil, Loa-Blessed Beads, Rootspeaker's Leggings). A difference here points at the *addon's scoring* (weights, live modifiers, item level).


### Disagreements: why the addon answers as it does

- **Elder Mossveil** (back, replaces Voidbreaker's Wrap): WRONG: addon says upgrade, SimC says a loss. Candidate Agi 48, Haste 47, Vers 28 at ilvl 250, replaced ilvl 246.
  - addon points by stat (weight x amount gained or lost): Versatility +33.6, Mastery -19.8, Haste +16.8, Item Level +8.0
- **Loa-Blessed Beads** (neck, replaces Voidbreaker's Choker): WRONG: addon says upgrade, SimC says a loss. Candidate Crit 75, Haste 100 at ilvl 233, replaced ilvl 220.
  - addon points by stat (weight x amount gained or lost): Critical Strike +135.0, Haste +101.2, Mastery -49.2, Item Level +26.0
