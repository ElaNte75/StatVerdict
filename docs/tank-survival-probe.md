# Tank survival probe (experiment)

Can SimulationCraft rate each secondary stat for a tank's survival, and is the answer stable?
Same best-in-slot loadouts as the Measured weights, scale factors of several metrics from one run,
3 seeds each. Nothing here is used by the addon. `dtps` etc. are shown as benefit
(negated), so a bigger number is always better. Orders are best to worst.

## DEATHKNIGHT_BLOOD / MYTHIC_PLUS / deathbringer

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > mastery > haste > versatility | crit 1.00 / mast 0.99 / hast 0.99 / vers 0.89 | 0.40 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.54 / crit 0.33 / hast 0.27 | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.54 / crit 0.29 / hast 0.27 | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit n/a / hast n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.80; dps_vs_dmg_taken 0.00; dps_vs_dtps 0.00; dps_vs_htps 0.40; guide_all_vs_dmg_taken -0.80; guide_all_vs_dps 0.40; guide_all_vs_dtps -0.80; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.80; guide_pvp_vs_dtps -0.40

Guide order (all): haste > critical_strike > mastery > versatility
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEATHKNIGHT_BLOOD / RAID / deathbringer

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > versatility > mastery > critical_strike | hast 1.00 / vers 0.98 / mast 0.88 / crit 0.76 | 1.00 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.73 / hast 0.37 / crit 0.33 | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.72 / hast 0.35 / crit 0.31 | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit n/a / hast n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.40; dps_vs_dmg_taken 0.20; dps_vs_dtps 0.20; dps_vs_htps -0.20; guide_all_vs_dmg_taken -0.60; guide_all_vs_dps 0.20; guide_all_vs_dtps -0.60; guide_pvp_vs_dmg_taken -0.20; guide_pvp_vs_dps 0.60; guide_pvp_vs_dtps -0.20

Guide order (all): haste > critical_strike > mastery > versatility
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEATHKNIGHT_BLOOD / MYTHIC_PLUS / sanlayn

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > mastery > haste > versatility | crit 1.00 / mast 0.92 / hast 0.90 / vers 0.87 | 1.00 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.47 / crit 0.30 / hast 0.19 | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.46 / crit 0.26 / hast 0.20 | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast n/a / crit n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.80; dps_vs_dmg_taken 0.00; dps_vs_dtps 0.00; dps_vs_htps 0.00; guide_all_vs_dmg_taken -0.80; guide_all_vs_dps 0.40; guide_all_vs_dtps -0.80; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.80; guide_pvp_vs_dtps -0.40

Guide order (all): haste > critical_strike > mastery > versatility
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEATHKNIGHT_BLOOD / RAID / sanlayn

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > versatility > mastery > critical_strike | hast 1.00 / vers 0.91 / mast 0.83 / crit 0.71 | 1.00 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.60 / hast 0.34 / crit 0.25 | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.59 / hast 0.36 / crit 0.25 | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit n/a / hast n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.40; dps_vs_dmg_taken 0.20; dps_vs_dtps 0.20; dps_vs_htps -0.20; guide_all_vs_dmg_taken -0.60; guide_all_vs_dps 0.20; guide_all_vs_dtps -0.60; guide_pvp_vs_dmg_taken -0.20; guide_pvp_vs_dps 0.60; guide_pvp_vs_dtps -0.20

Guide order (all): haste > critical_strike > mastery > versatility
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEMONHUNTER_VENGEANCE / MYTHIC_PLUS / aldrachi-reaver

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.84 / crit 0.84 / hast 0.66 | 0.80 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.89 / crit 0.53 / hast 0.27 | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.87 / crit 0.42 / hast 0.20 | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast n/a / crit n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.60; dps_vs_dmg_taken 1.00; dps_vs_dtps 1.00; dps_vs_htps -1.00; guide_all_vs_dmg_taken -0.20; guide_all_vs_dps -0.20; guide_all_vs_dtps -0.20; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.40; guide_pvp_vs_dtps -0.40

Guide order (all): haste > mastery > versatility > critical_strike
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEMONHUNTER_VENGEANCE / RAID / aldrachi-reaver

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > mastery > versatility > haste | crit 1.00 / mast 0.92 / vers 0.89 / hast 0.50 | 1.00 |
| dtps | versatility > mastery > critical_strike > haste | vers 1.00 / mast 0.94 / crit 0.62 / hast 0.29 | 1.00 |
| dmg_taken | versatility > mastery > critical_strike > haste | vers 1.00 / mast 0.92 / crit 0.34 / hast 0.11 | 1.00 |
| htps | haste > critical_strike > mastery > versatility | hast n/a / crit n/a / mast n/a / vers n/a (has non-positive values) | 0.80 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.40; dps_vs_dmg_taken 0.20; dps_vs_dtps 0.20; dps_vs_htps -0.20; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps -0.80; guide_all_vs_dtps -0.40; guide_pvp_vs_dmg_taken 0.20; guide_pvp_vs_dps -0.60; guide_pvp_vs_dtps 0.20

Guide order (all): haste > mastery > versatility > critical_strike
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEMONHUNTER_VENGEANCE / MYTHIC_PLUS / annihilator

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | mastery > critical_strike > versatility > haste | mast 1.00 / crit 0.85 / vers 0.84 / hast 0.78 | 0.80 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.80 / crit 0.46 / hast 0.32 | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.79 / crit 0.51 / hast 0.30 | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast n/a / crit n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.00; dps_vs_dmg_taken 0.80; dps_vs_dtps 0.80; dps_vs_htps -0.80; guide_all_vs_dmg_taken -0.20; guide_all_vs_dps -0.40; guide_all_vs_dtps -0.20; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.80; guide_pvp_vs_dtps -0.40

Guide order (all): haste > mastery > versatility > critical_strike
Guide order (pvp): versatility > haste > critical_strike > mastery

## DEMONHUNTER_VENGEANCE / RAID / annihilator

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > mastery > versatility > haste | crit 1.00 / mast 0.91 / vers 0.87 / hast 0.62 | 1.00 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.92 / crit 0.65 / hast 0.31 | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.93 / crit 0.64 / hast 0.25 | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast n/a / crit n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.40; dps_vs_dmg_taken 0.40; dps_vs_dtps 0.40; dps_vs_htps -0.40; guide_all_vs_dmg_taken -0.20; guide_all_vs_dps -0.80; guide_all_vs_dtps -0.20; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.60; guide_pvp_vs_dtps -0.40

Guide order (all): haste > mastery > versatility > critical_strike
Guide order (pvp): versatility > haste > critical_strike > mastery

## DRUID_GUARDIAN / MYTHIC_PLUS / druid-of-the-claw

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > mastery > versatility > haste | crit 1.00 / mast 0.98 / vers 0.96 / hast 0.84 | 1.00 |
| dtps | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.86 / hast 0.56 / mast 0.50 | 1.00 |
| dmg_taken | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.84 / hast 0.58 / mast 0.50 | 1.00 |
| htps | mastery > haste > critical_strike > versatility | mast n/a / hast n/a / crit n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.40; dps_vs_dmg_taken 0.00; dps_vs_dtps 0.00; dps_vs_htps 0.00; guide_all_vs_dmg_taken 0.00; guide_all_vs_dps -1.00; guide_all_vs_dtps 0.00; guide_damage_vs_dmg_taken 0.40; guide_damage_vs_dps -0.80; guide_damage_vs_dtps 0.40; guide_pvp_vs_dmg_taken 0.20; guide_pvp_vs_dps -0.40; guide_pvp_vs_dtps 0.20

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > versatility > critical_strike > mastery
Guide order (pvp): versatility > mastery > haste > critical_strike

## DRUID_GUARDIAN / RAID / druid-of-the-claw

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > critical_strike > versatility > mastery | hast 1.00 / crit 0.85 / vers 0.84 / mast 0.78 | 1.00 |
| dtps | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.69 / hast 0.61 / mast 0.27 | 1.00 |
| dmg_taken | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.71 / hast 0.66 / mast 0.28 | 1.00 |
| htps | mastery > haste > critical_strike > versatility | mast n/a / hast n/a / crit n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.60; dps_vs_dmg_taken 0.20; dps_vs_dtps 0.20; dps_vs_htps -0.20; guide_all_vs_dmg_taken 0.00; guide_all_vs_dps 0.40; guide_all_vs_dtps 0.00; guide_damage_vs_dmg_taken 0.40; guide_damage_vs_dps 0.80; guide_damage_vs_dtps 0.40; guide_pvp_vs_dmg_taken 0.20; guide_pvp_vs_dps -0.60; guide_pvp_vs_dtps 0.20

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > versatility > critical_strike > mastery
Guide order (pvp): versatility > mastery > haste > critical_strike

## DRUID_GUARDIAN / MYTHIC_PLUS / elunes-chosen

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > versatility > mastery > haste | crit 1.00 / vers 0.99 / mast 0.92 / hast 0.78 | 1.00 |
| dtps | versatility > critical_strike > mastery > haste | vers 1.00 / crit 0.81 / mast 0.48 / hast 0.43 | 1.00 |
| dmg_taken | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.81 / hast 0.49 / mast 0.48 | 1.00 |
| htps | haste > mastery > critical_strike > versatility | hast n/a / mast n/a / crit n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.20; dps_vs_dmg_taken 0.60; dps_vs_dtps 0.80; dps_vs_htps -0.80; guide_all_vs_dmg_taken 0.00; guide_all_vs_dps -0.80; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken 0.40; guide_damage_vs_dps -0.40; guide_damage_vs_dtps -0.20; guide_pvp_vs_dmg_taken 0.20; guide_pvp_vs_dps -0.20; guide_pvp_vs_dtps 0.40

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > versatility > critical_strike > mastery
Guide order (pvp): versatility > mastery > haste > critical_strike

## DRUID_GUARDIAN / RAID / elunes-chosen

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > versatility > critical_strike > mastery | hast 1.00 / vers 0.98 / crit 0.93 / mast 0.84 | 1.00 |
| dtps | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.58 / hast 0.45 / mast 0.28 | 1.00 |
| dmg_taken | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.61 / hast 0.44 / mast 0.28 | 1.00 |
| htps | mastery > haste > critical_strike > versatility | mast n/a / hast n/a / crit n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.00; dps_vs_dmg_taken 0.40; dps_vs_dtps 0.40; dps_vs_htps -0.40; guide_all_vs_dmg_taken 0.00; guide_all_vs_dps 0.80; guide_all_vs_dtps 0.00; guide_damage_vs_dmg_taken 0.40; guide_damage_vs_dps 1.00; guide_damage_vs_dtps 0.40; guide_pvp_vs_dmg_taken 0.20; guide_pvp_vs_dps 0.00; guide_pvp_vs_dtps 0.20

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > versatility > critical_strike > mastery
Guide order (pvp): versatility > mastery > haste > critical_strike

## MONK_BREWMASTER / MYTHIC_PLUS / master-of-harmony

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | mastery > critical_strike > versatility > haste | mast 1.00 / crit 1.00 / vers 0.96 / hast 0.51 | 0.80 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.71 / hast 0.27 / crit 0.07 | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.69 / hast 0.24 / crit 0.09 | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit n/a / hast n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.00; dps_vs_dmg_taken 0.40; dps_vs_dtps 0.40; dps_vs_htps -0.40; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps 0.40; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken -0.20; guide_damage_vs_dps 0.80; guide_damage_vs_dtps -0.20; guide_pvp_vs_dmg_taken 0.60; guide_pvp_vs_dps 0.40; guide_pvp_vs_dtps 0.60

Guide order (all): critical_strike > versatility > mastery > haste
Guide order (damage): critical_strike > mastery > versatility > haste
Guide order (pvp): versatility > mastery > critical_strike > haste

## MONK_BREWMASTER / RAID / master-of-harmony

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.96 / hast 0.96 / mast 0.66 | 0.80 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.89 / hast 0.83 / crit -0.01 (has non-positive values) | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.94 / hast 0.91 / crit 0.00 | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit 1.00 / hast -27.88 / vers -29.82 / mast -33.38 (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.20; dps_vs_dmg_taken -0.40; dps_vs_dtps -0.40; dps_vs_htps 0.40; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps 0.60; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken -0.20; guide_damage_vs_dps 0.00; guide_damage_vs_dtps -0.20; guide_pvp_vs_dmg_taken 0.60; guide_pvp_vs_dps 0.40; guide_pvp_vs_dtps 0.60

Guide order (all): critical_strike > versatility > mastery > haste
Guide order (damage): critical_strike > mastery > versatility > haste
Guide order (pvp): versatility > mastery > critical_strike > haste

## MONK_BREWMASTER / MYTHIC_PLUS / shado-pan

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > haste > versatility > mastery | crit 1.00 / hast 0.93 / vers 0.86 / mast 0.84 | 0.80 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.68 / hast 0.12 / crit -0.02 (has non-positive values) | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.68 / hast 0.04 / crit -0.05 (has non-positive values) | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit 1.00 / hast -5.79 / vers -33.98 / mast -50.13 (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.80; dps_vs_dmg_taken -1.00; dps_vs_dtps -1.00; dps_vs_htps 1.00; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps 0.40; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken -0.20; guide_damage_vs_dps 0.20; guide_damage_vs_dtps -0.20; guide_pvp_vs_dmg_taken 0.60; guide_pvp_vs_dps -0.60; guide_pvp_vs_dtps 0.60

Guide order (all): critical_strike > versatility > mastery > haste
Guide order (damage): critical_strike > mastery > versatility > haste
Guide order (pvp): versatility > mastery > critical_strike > haste

## MONK_BREWMASTER / RAID / shado-pan

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > versatility > mastery > haste | crit 1.00 / vers 0.86 / mast 0.59 / hast 0.54 | 1.00 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.82 / hast 0.54 / crit 0.05 | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.69 / hast 0.45 / crit 0.03 | 1.00 |
| htps | critical_strike > haste > versatility > mastery | crit n/a / hast n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.20; dps_vs_dmg_taken -0.40; dps_vs_dtps -0.40; dps_vs_htps 0.40; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps 1.00; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken -0.20; guide_damage_vs_dps 0.80; guide_damage_vs_dtps -0.20; guide_pvp_vs_dmg_taken 0.60; guide_pvp_vs_dps 0.40; guide_pvp_vs_dtps 0.60

Guide order (all): critical_strike > versatility > mastery > haste
Guide order (damage): critical_strike > mastery > versatility > haste
Guide order (pvp): versatility > mastery > critical_strike > haste

## PALADIN_PROTECTION / MYTHIC_PLUS / lightsmith

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > versatility > mastery > haste | crit 1.00 / vers 0.85 / mast 0.83 / hast 0.76 | 1.00 |
| dtps | versatility > critical_strike > mastery > haste | vers 1.00 / crit 0.69 / mast 0.37 / hast 0.35 | 1.00 |
| dmg_taken | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.62 / hast 0.31 / mast 0.24 | 1.00 |
| htps | mastery > haste > critical_strike > versatility | mast n/a / hast n/a / crit n/a / vers n/a (has non-positive values) | 0.80 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.20; dps_vs_dmg_taken 0.60; dps_vs_dtps 0.80; dps_vs_htps -0.60; guide_all_vs_dmg_taken 0.00; guide_all_vs_dps -0.80; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken 0.20; guide_damage_vs_dps -0.20; guide_damage_vs_dtps -0.40; guide_pvp_vs_dmg_taken 0.40; guide_pvp_vs_dps -0.40; guide_pvp_vs_dtps -0.20

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > critical_strike > versatility > mastery
Guide order (pvp): haste > versatility > critical_strike > mastery

## PALADIN_PROTECTION / RAID / lightsmith

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > versatility > critical_strike > mastery | hast 1.00 / vers 0.93 / crit 0.93 / mast 0.86 | 0.80 |
| dtps | versatility > haste > critical_strike > mastery | vers 1.00 / hast 0.63 / crit 0.53 / mast 0.37 | 1.00 |
| dmg_taken | versatility > critical_strike > haste > mastery | vers 1.00 / crit 0.69 / hast 0.67 / mast 0.37 | 0.80 |
| htps | mastery > critical_strike > haste > versatility | mast n/a / crit n/a / hast n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.00; dps_vs_dmg_taken 0.40; dps_vs_dtps 0.80; dps_vs_htps -0.80; guide_all_vs_dmg_taken 0.00; guide_all_vs_dps 0.80; guide_all_vs_dtps 0.60; guide_damage_vs_dmg_taken 0.20; guide_damage_vs_dps 0.80; guide_damage_vs_dtps 0.40; guide_pvp_vs_dmg_taken 0.40; guide_pvp_vs_dps 1.00; guide_pvp_vs_dtps 0.80

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > critical_strike > versatility > mastery
Guide order (pvp): haste > versatility > critical_strike > mastery

## PALADIN_PROTECTION / MYTHIC_PLUS / templar

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | critical_strike > versatility > mastery > haste | crit 1.00 / vers 0.82 / mast 0.82 / hast 0.70 | 0.80 |
| dtps | versatility > critical_strike > mastery > haste | vers 1.00 / crit 0.84 / mast 0.39 / hast 0.33 | 1.00 |
| dmg_taken | versatility > critical_strike > mastery > haste | vers 1.00 / crit 0.79 / mast 0.38 / hast 0.21 | 1.00 |
| htps | haste > mastery > critical_strike > versatility | hast n/a / mast n/a / crit n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.20; dps_vs_dmg_taken 0.80; dps_vs_dtps 0.80; dps_vs_htps -0.80; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps -0.80; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken -0.40; guide_damage_vs_dps -0.20; guide_damage_vs_dtps -0.40; guide_pvp_vs_dmg_taken -0.20; guide_pvp_vs_dps -0.40; guide_pvp_vs_dtps -0.20

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > critical_strike > versatility > mastery
Guide order (pvp): haste > versatility > critical_strike > mastery

## PALADIN_PROTECTION / RAID / templar

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > critical_strike > versatility > mastery | hast 1.00 / crit 0.87 / vers 0.87 / mast 0.74 | 0.80 |
| dtps | versatility > critical_strike > mastery > haste | vers 1.00 / crit 0.72 / mast 0.35 / hast 0.21 | 1.00 |
| dmg_taken | versatility > critical_strike > mastery > haste | vers 1.00 / crit 0.68 / mast 0.38 / hast 0.25 | 1.00 |
| htps | haste > mastery > critical_strike > versatility | hast n/a / mast n/a / crit n/a / vers n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.60; dps_vs_dmg_taken -0.40; dps_vs_dtps -0.40; dps_vs_htps 0.40; guide_all_vs_dmg_taken -0.40; guide_all_vs_dps 0.40; guide_all_vs_dtps -0.40; guide_damage_vs_dmg_taken -0.40; guide_damage_vs_dps 1.00; guide_damage_vs_dtps -0.40; guide_pvp_vs_dmg_taken -0.20; guide_pvp_vs_dps 0.80; guide_pvp_vs_dtps -0.20

Guide order (all): haste > versatility > mastery > critical_strike
Guide order (damage): haste > critical_strike > versatility > mastery
Guide order (pvp): haste > versatility > critical_strike > mastery

## WARRIOR_PROTECTION / MYTHIC_PLUS / colossus

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.96 / crit 0.94 / hast 0.58 | 1.00 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.79 / crit 0.40 / hast -0.00 (has non-positive values) | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.78 / crit 0.31 / hast -0.08 (has non-positive values) | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast n/a / crit n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.60; dps_vs_dmg_taken 1.00; dps_vs_dtps 1.00; dps_vs_htps -1.00; guide_all_vs_dmg_taken -1.00; guide_all_vs_dps -1.00; guide_all_vs_dtps -1.00; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.40; guide_pvp_vs_dtps -0.40

Guide order (all): haste > critical_strike > versatility > mastery
Guide order (pvp): versatility > haste > critical_strike > mastery

## WARRIOR_PROTECTION / RAID / colossus

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > mastery > versatility > critical_strike | hast 1.00 / mast 0.87 / vers 0.83 / crit 0.64 | 1.00 |
| dtps | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.73 / hast 0.50 / crit 0.21 | 1.00 |
| dmg_taken | mastery > versatility > haste > critical_strike | mast 1.00 / vers 0.90 / hast 0.41 / crit 0.24 | 0.80 |
| htps | critical_strike > haste > versatility > mastery | crit n/a / hast n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.20; dps_vs_dmg_taken 0.40; dps_vs_dtps 0.40; dps_vs_htps -0.40; guide_all_vs_dmg_taken -0.80; guide_all_vs_dps 0.20; guide_all_vs_dtps -0.80; guide_pvp_vs_dmg_taken -0.20; guide_pvp_vs_dps 0.00; guide_pvp_vs_dtps -0.20

Guide order (all): haste > critical_strike > versatility > mastery
Guide order (pvp): versatility > haste > critical_strike > mastery

## WARRIOR_PROTECTION / MYTHIC_PLUS / mountain-thane

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | mastery > critical_strike > versatility > haste | mast 1.00 / crit 0.96 / vers 0.96 / hast 0.61 | 1.00 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.79 / crit 0.39 / hast 0.10 | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.78 / crit 0.44 / hast 0.15 | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast n/a / crit n/a / vers n/a / mast n/a (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths 0.00; dps_vs_dmg_taken 0.80; dps_vs_dtps 0.80; dps_vs_htps -0.80; guide_all_vs_dmg_taken -1.00; guide_all_vs_dps -0.80; guide_all_vs_dtps -1.00; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps -0.80; guide_pvp_vs_dtps -0.40

Guide order (all): haste > critical_strike > versatility > mastery
Guide order (pvp): versatility > haste > critical_strike > mastery

## WARRIOR_PROTECTION / RAID / mountain-thane

| Metric | Order | Relative value (best = 1.00) | Seeds agree |
|---|---|---|---|
| dps | haste > mastery > versatility > critical_strike | hast 1.00 / mast 0.75 / vers 0.71 / crit 0.59 | 1.00 |
| dtps | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.65 / crit 0.34 / hast -0.14 (has non-positive values) | 1.00 |
| dmg_taken | mastery > versatility > critical_strike > haste | mast 1.00 / vers 0.65 / crit 0.46 / hast -0.02 (has non-positive values) | 1.00 |
| htps | haste > critical_strike > versatility > mastery | hast 1.00 / crit -2.58 / vers -5.00 / mast -7.71 (has non-positive values) | 1.00 |
| deaths | critical_strike > haste > mastery > versatility | crit n/a / hast n/a / mast n/a / vers n/a (has non-positive values) | 1.00 |

Order agreement (1.00 = same order, -1.00 = reversed): dps_vs_deaths -0.20; dps_vs_dmg_taken -0.20; dps_vs_dtps -0.20; dps_vs_htps 0.20; guide_all_vs_dmg_taken -1.00; guide_all_vs_dps 0.20; guide_all_vs_dtps -1.00; guide_pvp_vs_dmg_taken -0.40; guide_pvp_vs_dps 0.00; guide_pvp_vs_dtps -0.40

Guide order (all): haste > critical_strike > versatility > mastery
Guide order (pvp): versatility > haste > critical_strike > mastery


---

## Findings (summary, written by hand after the full run: 6 tanks, 24 loadouts, 3 seeds each)

- **SimC gives a stable survival number.** Damage taken (`dtps`, `dmg_taken`) repeats exactly between seeds in
  24 of 24 loadouts (order agreement 1.00 / 0.98), more stable than the DPS order (0.91). `htps` and `deaths`
  are not usable (non-positive values in several loadouts).
- **It measures something different from DPS.** Average order agreement DPS vs damage taken: 0.28 (from -1.0
  to +1.0 by loadout). Mostly Mastery / Versatility on top and Haste / Crit at the bottom.
- **It does not agree with the guides' survival order.** Average agreement of the guide's tank order (`all`)
  with `dtps`: -0.42. Even the guide's own "damage" order agrees with `dtps` only at -0.05. So the SimC damage
  model is either missing what the guides value for tanks (spikes, active mitigation uptime, healing and
  absorb timing, deaths rather than averages), or the guides weigh things averages hide. This probe cannot say
  which one is right; it has no ground truth for "survival".
- **Weak stats are worth little.** In the average loadout the worst secondary is worth about 22% of the best for
  damage taken, in some loadouts even less than zero.
- **Conclusion:** SimC's `dtps` is a stable but unvalidated survival measure. It should not replace the guide as
  the survival side of a Damage-Survival balance. Use the guide as the survival side (as the guides intend) and
  keep Measured as the damage side.
