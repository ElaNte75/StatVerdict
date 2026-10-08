# StatVerdict release verification

Run the automated gate first:

```powershell
pip install lupa
$env:PYTHONPATH = ".;tools"
python -m unittest discover -s tools/tests -v
```

Run it from the repository root (`lupa` runs the addon's Lua tests; without it they are skipped).

Never bypass it to create a release archive.

## In-game matrix

### Active spec

1. Hover an equippable upgrade and a downgrade.
2. Confirm only the upgrade receives a result.
3. Confirm the result says `equipped`, uses `Verdict Points`, and includes the
   heuristic and profile-source disclosures.
4. Equip the candidate and confirm caches and comparison baseline refresh.

### Off Spec

1. Select an Off Spec with no saved loadout: the tooltip must say the virtual
   loadout is missing and must not show a verdict.
2. Approve one or more bag items without changing spec: the tooltip must say
   Off Spec stats are not captured and must not use active-spec ratings.
3. Switch to the Off Spec once, allow capture, then switch back.
4. Confirm Off Spec results say `virtual loadout` and change only when that
   snapshot's gear or captured stats change.

### Goal isolation

For Mythic+, Raid, and PvP:

1. Select the goal and inspect Stat Progress, BiS, trinkets, and a verdict.
2. Confirm displayed references belong to that goal.
3. PvP must never display a PvE-derived average item-level claim.
4. Corrupt or remove a context in a development fixture and confirm the addon
   shows a quality failure instead of falling back to another context.

### Scoring edge cases

- Compare the same item with and without a gem: only actual gem stats score.
- Confirm an empty socket does not receive imaginary best-gem points.
- Compare physical weapons with different DPS and similar stat budgets.
- On a tank, compare pieces with different armor and stamina.
- Test 2H against MH+OH and the reverse; both replaced items must be listed.
- Compare two copies with the same item ID/ilvl but different bonus, gem, or
  enchant item strings; they must not be collapsed as the same copy.
- Confirm stale or invalid profile data produces no green upgrade arrow.

### Surface consistency

- Bag toggles affect bag arrows and MS/OS labels.
- Quest rewards, merchants, and Adventure Guide may still show upgrade arrows.
- Manual, tooltip, and store copy must describe the same behavior.
- The TOC, runtime version, changelog, and release archive version must match.

### Vanished gear (2.0.40)

1. Put a bag item into the Off Spec loadout (Approve), then sell it: a few seconds later the chat says it was removed, and the item no longer shows MS/OS anywhere.
2. Move an Off Spec item to the bank or the warband bank: it stays in the loadout.
3. Sell it, then buy it back from the vendor within 10 minutes: it is put back into the loadout.
4. After a loading screen, an old Off Spec item you no longer own (for example a former necklace) is removed within about 20 seconds.
5. The spec you are playing is never changed by this.
6. `/sv ag` then `/reload`: the Adventure Guide shows no marks and its tabs (Overview, Loot, ...) show their tooltip steadily; `/sv ag` and `/reload` again brings the marks back. (Reported: with the addon on, the tab tooltip blinks on and off while the mouse is on the Loot tab; the cause is not found yet.)

### Guide, tiers and tooltips (1.1.0)

1. Guide drawer: exactly one of Auto / Tier 1 / Tier 2 / Tier 3 is ticked, whatever you click.
2. Auto: the title bar names the tier and the progress to the next; the Auto row says the same.
3. Best in Slot: Tier 1 shows 308 (Champion), Tier 2 321 (Hero), Tier 3 334 (Myth 6/6); PvP is unchanged.
4. Hover a Best in Slot item and a ranked trinket: roomy tooltip, "Gems" / "Enchant" labels, and "Where to find" for a dungeon or raid item.
5. Options drawer: six dark cards with a small gold heading each (WINDOW, BAG ITEMS, ITEM TOOLTIPS, CHARACTER INFO, BEST IN SLOT, RANKED TRINKETS), a switch on every row (gold with the knob right when on, dark with the knob left when off), a short grey line under some rows, a child choice (Gems and enchants, Trinket effect, Auto-hide) hangs from a thin gold line; the list scrolls when it is taller than the panel; hovering a row shows what it does, every choice still works. Always on top is off by default: click another add-on, the chat or the world and the window steps behind; click it and it comes back. Compact Mode: ticked, the window gets about 40% shorter, shows one table (the Show Off Spec / Show Main Spec button under the dropdowns switches it, only when an Off Spec is set up; the heading of the build in view is gold, the other white), the buttons Guide / Best in Slot / Ranked Trinkets / Options are in one row under the table, the Manual opens from the last line of Options, and a side panel opens as its own window beside it (titled StatVerdict Guide, StatVerdict Options and so on; drag it by its title or an empty spot; the Close button at its bottom right closes it, no X in a corner; the main window does not change size; the next panel opens where you left it; the main window and a panel are two windows: drag the main window over the panel and click either one, it comes to the front whole, nothing of the two mixes; both step behind together when you click elsewhere with Always on top off; closing the main window closes the panel); Manual: a Text size slider at the bottom (100% to 200%, applied when the mouse lets go): the text and the window grow together, a floating Manual also gets higher (up to most of the screen), the size is remembered, and the Close button stays clear of the slider; Window size slider (75% to 100%, applied when the mouse lets go; the window keeps its top left corner, side panels and menus come along, works with and without Compact Mode, and each of the two remembers its own size: switching Compact Mode on or off takes the window to that mode's size); Auto-hide the left side (listed under Compact Mode; dimmed and unticked while Compact Mode is off, its own choice is kept): the window gets narrower, a thin strip with >> stands for the builds, the mouse on it shows them over the table and a moment after the mouse leaves they fold away (not while a dropdown menu is open); in Options, Manual sits left of Close at the bottom right (Manual replaces Options, never two panels at once); unticked, everything is back as before.
6. With an Off Spec set up: a checkbox in front of each spec's name in the main window switches the view (never the game spec), exactly one is on; the title bar, Best in Slot, trinkets and the Guide follow it, and each spec keeps its own tier.
