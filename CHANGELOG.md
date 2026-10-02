# StatVerdict — changelog

One section per released version, newest first. The text under each version is what goes into the CurseForge changelog box.
The version in the repo (`StatVerdict.toc`, `ns.VERSION`, the header of `StatVerdict/STORE.md`) is the one being prepared;
everything fixed from now on goes into that section until it is uploaded.

## 1.1.1 (prepared, not uploaded yet)

```
1.1.1
New
- /sv ag switches the Adventure Guide marks off and on (type /reload afterwards), in case they get in the way of the Adventure Guide.
- /sv mouse lists, for 8 seconds, which frames sit under the mouse (handy for bug reports).
Fixed
- A saved loadout (Main Spec or Off Spec) no longer keeps gear that is gone. When an item of a saved loadout is sold, disenchanted, deleted or otherwise lost, it is removed from the loadout and the slot falls back to what you are wearing there. A line in the chat tells you. An item bought back from a vendor within 10 minutes goes back where it was.
- The Adventure Guide tabs (Overview, Loot, ...) no longer flicker or become hard to click while StatVerdict is running. StatVerdict no longer adds a click handler to the game tooltip, which was taking the mouse away from whatever the tooltip sat on.
- The short freeze when you equip an item or change spec is gone. StatVerdict now works out your build once per bag check instead of once per item.
```

## 1.1.0 (released 2026-10-01)

```
1.1.0
New
- Guide drawer: Auto (the default) follows your own stats and moves you up to the next tier of targets once you cover about 90% of the current one. Or pick Tier 1, 2 or 3 yourself. The tier in use, and your progress to the next one, are shown in the title bar.
- Best in Slot and Ranked Trinkets follow the tier: Tier 1 shows Champion-track items, Tier 2 Hero, Tier 3 Myth 6/6, so an easier goal never shows gear only the best can have.
- Best in Slot and Ranked Trinkets tooltips: more room, clearer labels, and a "Where to find" line (dungeon or raid and boss) for items the Adventure Journal lists.
- New look for the Features drawer: three clear blocks (Bag Markers, Best in Slot, Ranked Trinkets).
Improved
- Upgrade arrows refresh faster and more reliably, and no longer flicker; buffs no longer move the verdicts.
- Verdicts are the same from both sides: two items can never both be better than each other, and 10 or more item levels always wins.
- Trinkets, rings and necks are compared fairly.
- Stat priorities, Best in Slot lists and stat targets are a 1:1 copy of the guides (Icy Veins and u.gg). The Measured mode has been removed.
- Guide data is now good for 60 days before it counts as out of date, and the message tells you to update.
```

## 1.0.7

```
1.0.7
- Added profile freshness, completeness, and goal-consistency gates
- Fixed Off Spec live weights to use captured Off Spec stats
- Added physical weapon DPS and tank armor/stamina to generated profiles
- Empty sockets no longer score as already filled
- Verdict tooltips now disclose heuristic units, baseline, source, and limitations
```
