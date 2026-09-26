# StatVerdict Bridge (dev only)

Μικρό addon **μόνο για εσένα**. Δεν ανεβαίνει στο Curse.

## Εγκατάσταση

1. Αντίγραψε τον φάκελο `StatVerdictBridge` στο:
   `...\World of Warcraft\_retail_\Interface\AddOns\StatVerdictBridge`
2. Βεβαιώσου ότι το **ClassCodex** είναι ενεργό.
3. Στο παιχνίδι: `/svbridge` → **Export from ClassCodex** → Reload όταν ζητηθεί.
4. Στο PC, μέσα στο project `StatVerdict`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ship.ps1
```

Το script:
- διαβάζει το export από `WTF\Account\...\SavedVariables\StatVerdictBridge.lua`
- γράφει `Data\Generated\SV_ProfileData.lua` (+ `.json`)
- ανεβάζει version
- φτιάχνει στην **Επιφάνεια εργασίας** το `StatVerdict-x.y.z.zip`

Μετά ανεβάζεις το zip στο Curse.

## Commands

- `/svbridge` — άνοιγμα UI
- `/svbridge export` — ξεκινάει απευθείας το export
- `/svbridge status` — κατάσταση τελευταίου export
