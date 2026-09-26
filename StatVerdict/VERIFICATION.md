# StatVerdict release verification

Run the automated gate first:

```powershell
python -m unittest discover -s tests -v
python scripts/extract_bridge_export.py --wtf-account "<retail>\WTF\Account" --out Data\Generated
```

The second command must finish without profile-quality errors. Never bypass it
to create a release archive.

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
