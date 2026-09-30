# Stat split probe (experiment)

Does a better split of the same rating points beat the guide's best-in-slot split?
Rating is moved between the four secondaries (total constant) and each move simulated with
SimulationCraft; the best clearly better move is taken until none helps. It is an upper bound:
real items may not offer that split. Nothing here is used by the addon.

| Spec | Goal | Hero tree | DPS gain | Guide split (rating order) | Best split found (rating order) | Same order |
|---|---|---|---|---|---|---|
| HUNTER_BEAST_MASTERY | MYTHIC_PLUS | dark-ranger | +3.06% | crit 1790 > mast 1446 > vers 233 > hast 101 | crit 1290 > mast 1246 > hast 1001 > vers 33 | no |
