# Stat split probe (experiment)

Does a better split of the same rating points beat the guide's best-in-slot split?
Rating is moved between the four secondaries (total constant) and each move simulated with
SimulationCraft; the best clearly better move is taken until none helps. It is an upper bound:
real items may not offer that split. Nothing here is used by the addon.

| Spec | Goal | Hero tree | DPS gain | Guide split (rating order) | Best split found (rating order) | Same order |
|---|---|---|---|---|---|---|
| HUNTER_BEAST_MASTERY | MYTHIC_PLUS | dark-ranger | +3.06% | crit 1790 > mast 1446 > vers 233 > hast 101 | crit 1290 > mast 1246 > hast 1001 > vers 33 | no |
| HUNTER_BEAST_MASTERY | RAID | dark-ranger | +4.84% | crit 1580 > mast 1536 > hast 430 > vers 109 | mast 1536 > hast 1130 > crit 980 > vers 9 | no |
| MAGE_FIRE | MYTHIC_PLUS | frostfire | +0.73% | hast 1380 > mast 1148 > vers 694 > crit 88 | mast 1298 > hast 1280 > vers 694 > crit 38 | no |
| MAGE_FIRE | RAID | frostfire | +5.60% | hast 1446 > vers 660 > crit 651 > mast 651 | hast 1246 > mast 1101 > vers 1060 > crit 1 | no |
| PALADIN_RETRIBUTION | MYTHIC_PLUS | herald-of-the-sun | +0.48% | hast 1220 > mast 1125 > crit 963 > vers 73 | mast 1325 > crit 1013 > hast 970 > vers 73 | no |
| PALADIN_RETRIBUTION | RAID | herald-of-the-sun | +0.24% | crit 1389 > mast 1288 > hast 810 > vers 109 | crit 1389 > mast 1088 > hast 960 > vers 159 | yes |
| WARLOCK_DESTRUCTION | MYTHIC_PLUS | diabolist | +0.54% | mast 1269 > crit 1232 > hast 682 > vers 0 | crit 1432 > mast 1269 > hast 482 > vers 0 | no |
| WARLOCK_DESTRUCTION | RAID | diabolist | +3.66% | mast 1335 > hast 1111 > crit 667 > vers 109 | crit 1267 > mast 1235 > vers 709 > hast 11 | no |

## Findings (written by hand; 4 DPS specs, 8 loadouts, first hero tree each)

- The guide's best-in-slot split is **close to the best split in 4 of 8 loadouts** (gain 0.2% to 0.7%: Fire Mage M+,
  Retribution M+ and Raid, Destruction M+). That is within noise of the method.
- It leaves **3% to 6% DPS on the table in 4 of 8**: Fire Mage Raid +5.6%, Beast Mastery Raid +4.8%,
  Destruction Raid +3.7%, Beast Mastery M+ +3.1%. In these the best split is a different order of the four
  stats (for example Beast Mastery: less Crit, more Haste; Fire Mage Raid: almost no Crit).
- **Caveats.** (1) Upper bound: real items may not offer the split, and the guide's gear is chosen for other
  reasons too (effects, slots, availability). (2) One boss dummy with the default rotation of SimC; M+ has several
  targets and other priorities, so M+ results are less certain than Raid ones. (3) One hero tree per spec, one
  run per loadout with the Z >= 2 rule; a repeat with other seeds would confirm. (4) Some best splits are extreme
  (a stat at about 0 rating), which is a sign to look at the rotation and diminishing returns before trusting them.
