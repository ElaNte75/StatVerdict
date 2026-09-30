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
