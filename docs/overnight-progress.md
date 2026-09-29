# Overnight progress (2026-09-29)

Working through five jobs in order; each is committed and pushed on its own.

| # | Job | Status |
|---|---|---|
| 1 | Data quality audit of the 240 contexts | done: `docs/data-quality-report.md`, no pipeline fix needed |
| 2 | Fidelity check against raw Icy Veins data | done: `docs/data-fidelity-report.md`, 0 real differences |
| 3 | Update STORE.md / VERDICT_MODEL.md | done: Easy/Normal/Hard -> Tier 3/2/1, Weights drawer -> Mode drawer, data-source names removed from store copy |
| 4 | Robustness tests (odd characters) | done: `tools/tests/test_addon_robustness.py` (8 tests); no crash found |
| 5 | Lua review for small safe fixes | done: no change needed (see below) |

Earlier tonight (HANDOFF section 5): Versatility row fix, guide ties, wider level cards - all on `main`.
Item check run 36612825165: finished, table committed at `docs/item-check/enhancement_shaman.md` (see summary).

Open findings for the owner:
- Windwalker average item level 289 (see data-quality-report.md) needs a SimC look.
- Robustness: an unmatched, non-empty hero-talent name (e.g. a translated one) gives no profile when the client
  does not also supply the hero subtree id (by design: "no data rather than a guess"). Not changed (logic);
  owner decision if guessing should apply there too.

## Job 5: Lua review (no code changed)
- Every file loaded from the toc defines only intended globals (key bindings, slash commands, addon compartment
  callbacks); no accidental global function or variable at file level.
- Every toc entry exists on disk, and every Lua file under Core/UI/Data is in the toc.
- All `print` calls are user-facing slash-command output or a chat fallback; no debug leftovers, no TODO/FIXME.

## Open for the owner
- Item check: weapon rows look extreme (Dawnforged Ritual Knife -35%, Blood-Tempered Bulwark -42%, Mertei's Command
  Baton -57% in `docs/item-check/enhancement_shaman.md`); worth confirming the weapon swap is modelled right
  (one-hand vs two-hand, off-hand slot) before trusting weapon deltas. Armour/jewellery rows look plausible
  (errors about +-46 DPS).
- Windwalker average item level 289 needs a SimC look (data-quality-report.md).
- Unmatched non-empty hero names give no profile without a subtree id (see robustness note above).
