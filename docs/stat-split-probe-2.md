# Stat split probe (experiment)

Does a better split of the same rating points beat the guide's best-in-slot split?
Rating is moved between the four secondaries (total constant) and each move simulated with
SimulationCraft; the best clearly better move is taken until none helps. It is an upper bound:
real items may not offer that split. Nothing here is used by the addon.

| Spec | Goal | Hero tree | DPS gain (search) | Head-to-head check (3 fresh seeds) | Guide split (rating order) | Best split found (rating order) | Same order |
|---|---|---|---|---|---|---|---|
| HUNTER_BEAST_MASTERY | MYTHIC_PLUS | dark-ranger | +2.18% | +2.27% / +2.26% / +2.32% (3/3 better) | crit 1790 > mast 1446 > vers 233 > hast 101 | mast 1646 > crit 1390 > hast 401 > vers 133 | no |
| HUNTER_BEAST_MASTERY | RAID | dark-ranger | +5.01% | +5.02% / +5.05% / +5.03% (3/3 better) | crit 1580 > mast 1536 > hast 430 > vers 109 | mast 1436 > hast 1330 > crit 880 > vers 9 | no |
