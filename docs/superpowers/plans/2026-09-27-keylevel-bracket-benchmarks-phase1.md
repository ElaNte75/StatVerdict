# Key-Level Bracket Benchmarks — Phase 1 (Data Pipeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current "top 25/100/200 players overall" benchmark cohorts with three key-level
difficulty brackets (Low/Mid/High), each offering a choice of sample tightness (20/50/100 players), so a
player's in-game targets come from peers near their own Mythic+ level instead of only the world's best.
This plan covers the Python data pipeline and the addon-facing JSON/Lua data file it produces. It does
**not** touch the GitHub Actions workflow or the addon's in-game selector UI — see "Out of scope" below.

**Architecture:** `tools/live_benchmark_engine.py` gains a bracket-aware candidate-discovery step (new
function, used only for the LOW and MID brackets; HIGH reuses the existing top-of-rankings discovery
unchanged) and restructures its cohort dictionaries from a single `TOP_{size}` axis to a two-axis
`{BRACKET}_{size}` scheme. `tools/addon_benchmarks.py` restructures its output the same way, replacing the
flat `ELITE/STANDARD/BROAD` levels with `levels: { LOW/MID/HIGH: { 20/50/100: {...} } }`. Existing
aggregation, SimC/Wowhead reconstruction, and gear-cohort logic are reused unchanged — only which
population of candidates feeds each bracket, and how cohort dictionaries are keyed, changes.

**Tech Stack:** Python 3.14, stdlib `urllib`/`unittest`, Raider.IO public JSON API (no auth key required
for the ranking endpoint used here).

**Spec:** No separate spec document exists; the agreed requirements are captured below in "Global
Constraints" (agreed with the user in conversation, 2026-09-27, after a live read-only data probe
confirming feasibility for rare specs and small regions).

**Out of scope for this plan (tracked as a later "Phase 2" plan):**
- `.github/workflows/weekly-benchmarks.yml` / `benchmark-retry.yml` — job matrix, parallelism, runtime.
  The live pipeline keeps producing today's `ELITE/STANDARD/BROAD` shape until Phase 2 ships; Phase 1's
  new code path is exercised by its own tests and by manual CLI runs, not by the scheduled workflow.
- `StatVerdict/Core/SV_Benchmark.lua`, `StatVerdict/UI/SV_BenchmarkDrawerPanel.lua`, and
  `tools/tests/test_addon_lua.py` — the in-game selector (still reads `ELITE/STANDARD/BROAD`) and its
  end-to-end Lua test. Changing these needs the user's in-game eyes on the layout/wording, which is a
  separate, iterative pass — not something to blueprint unattended.
- Cleanup of the old `TOP_25/TOP_100/TOP_200` cohort code path. Per the user's standing rule (removing
  superseded code only after in-game verification), that happens once Phase 2 ships and the user confirms
  the new levels work in game.

## Global Constraints

- Three brackets, boundaries based on a character's best (highest) Mythic+ key level this season, agreed
  2026-09-27: **LOW** = best key 2–9, **MID** = best key 10–15, **HIGH** = best key 16 and up (no ceiling).
  These exact numbers must live as ONE named constant (`BRACKET_CEILINGS`) so they are a one-line change
  later, never duplicated or hard-coded elsewhere.
- Three sample sizes per bracket, agreed 2026-09-27: **20 / 50 / 100** best-scoring qualifying players.
  Reuse the existing "collect the largest size once, slice smaller sizes from the same pool" pattern
  already used for today's 25/100/200 — never re-run discovery or reconstruction per size.
- Selection stays global across all regions merged by score (no per-region quotas or floors) — unchanged
  from today's `discover_candidates`.
- Bracket membership uses a character's best key across **all** their ranked runs this season (logged or
  not) — the strongest available skill signal. The existing requirement that gear can only be sourced from
  a combat-log-**logged** run is unchanged and unrelated to bracket membership.
- HIGH has no ceiling, so HIGH's candidate discovery is **exactly today's existing `discover_candidates`**,
  called unmodified. Do not build new discovery logic for HIGH.
- LOW and MID need a new bracket-aware discovery function. A live read-only probe (2026-09-27, Survival
  Hunter and Feral Druid, all 4 regions) confirmed real players exist at low key ceilings even for
  lower-population specs and small regions (Korea/Taiwan had 15–40; EU/US had 800+), but also confirmed
  naive linear paging from page 0 is too slow to rely on for popular specs (an earlier full spike needed
  ~1,000+ pages of depth to reach single-digit keys for one common tank spec on EU). The new function must
  locate the right depth first (binary search over pages), then scan forward from there — never plain
  linear-from-zero.
- This is a breaking change to the raw per-spec JSON shape (`cohorts`/`gearCohorts` keys move from
  `TOP_{size}` to `{BRACKET}_{size}`, e.g. `MID_50`). Nothing outside `tools/live_benchmark_engine.py` and
  `tools/addon_benchmarks.py` reads that raw shape directly, so this is safe within Phase 1's scope.
- No change to how a single candidate's record is fetched (`fetch_record`) or to stat reconstruction
  (SimC / Wowhead tooltip methods) — only which population feeds each bracket, and cohort key naming.

## Review Focus

1. **Rare spec + small region, LOW bracket:** even with full paging, a niche spec's smallest region (e.g.
   Taiwan) may never reach the target candidate count. The bracket must degrade to today's existing
   `"insufficient"` status, never crash or silently ship an empty/wrong cohort. → covered in Task 2's tests.
2. **A candidate with no runs, or runs missing `mythicLevel`:** best-key computation must return `None`
   (treated as "does not qualify for any ceiling") rather than raising. → covered in Task 1's tests.
3. **MID/LOW binary search finds no qualifying page at all** (plausible if a spec's whole ranked population
   already plays above the ceiling): must return an empty list, not loop forever or raise. → covered in
   Task 1's tests.
4. **A page's entries straddle the ceiling** (some qualify, some don't, since score and key level correlate
   but are not perfectly monotonic): the scan after the located pivot page must keep going past a
   non-qualifying entry rather than stopping at the first miss, until `target_count` is reached or pages
   run out. → covered in Task 1's tests.
5. **`validate_database`'s "is this spec's data complete" gate** currently checks one cohort
   (`TOP_{required_minimum}`). With 3 brackets × 3 sizes, a spec could have a complete HIGH bracket but a
   totally missing LOW bracket and still look "ok" if the gate isn't updated — it must require the
   smallest size complete in **all three** brackets. → covered in Task 4's tests.

---

## File Structure

- Modify: `tools/live_benchmark_engine.py` — bracket constants, new discovery function, main-loop wiring,
  cohort key renaming, `validate_database` gate update.
- Modify: `tools/addon_benchmarks.py` — `LEVELS`/`build_profile`/`build_level_context`/`build_report`
  restructured for the two-axis shape.
- Modify: `tools/tests/test_live_benchmark_engine.py` — new tests for the bracket logic, updated fixtures.
- Modify: `tools/tests/test_addon_benchmarks.py` — updated fixtures/assertions for the new `levels` shape.
- Modify: `tools/tests/addon_fixtures.py` — shared fixture builder updated for the new cohort keys.

---

## Task 1: Best-key computation and bracket-ceiling candidate discovery

**Files:**
- Modify: `tools/live_benchmark_engine.py` (add near `discover_candidates`, `tools/live_benchmark_engine.py:715`)
- Test: `tools/tests/test_live_benchmark_engine.py`

**Interfaces:**
- Produces: `BRACKET_CEILINGS: dict[str, int | None]` = `{"LOW": 9, "MID": 15, "HIGH": None}` (ordered
  low-to-high; iteration order matters for later tasks).
- Produces: `SAMPLE_SIZES: tuple[int, ...]` = `(20, 50, 100)`.
- Produces: `best_key_level(runs: list[dict[str, Any]]) -> int | None` — highest `mythicLevel` across
  `runs`, or `None` if none present/parseable.
- Produces: `discover_candidates_by_ceiling(http, spec, *, season, regions, ceiling, target_count, max_pages, access_key) -> list[dict[str, Any]]` — same return shape as `discover_candidates` (list of `character_ref`-style dicts, globally ranked, deduped, `rank` renumbered 1..N), but only including characters whose `best_key_level(entry["runs"])` is `<= ceiling`.
- Consumes: `JsonClient`, `Spec`, `ranking_page`, `character_ref` (all existing, unchanged).

- [ ] **Step 1: Write the failing tests**

```python
# Added to tools/tests/test_live_benchmark_engine.py, inside BenchmarkEngineTests (or a new class)
from tools.live_benchmark_engine import (
    BRACKET_CEILINGS,
    SAMPLE_SIZES,
    best_key_level,
    discover_candidates_by_ceiling,
)


class BestKeyLevelTests(unittest.TestCase):
    def test_uses_highest_mythic_level_across_runs(self):
        runs = [{"mythicLevel": 7}, {"mythicLevel": 12}, {"mythicLevel": 3}]
        self.assertEqual(12, best_key_level(runs))

    def test_ignores_runs_without_a_usable_level(self):
        runs = [{"mythicLevel": None}, {}, {"mythicLevel": "not-a-number"}]
        self.assertIsNone(best_key_level(runs))

    def test_empty_runs_list_returns_none(self):
        self.assertIsNone(best_key_level([]))

    def test_mixed_valid_and_invalid_runs(self):
        runs = [{"mythicLevel": None}, {"mythicLevel": 5}]
        self.assertEqual(5, best_key_level(runs))


def _spec_ref(name: str, rank: int, score: float, runs: list[dict]) -> dict:
    return {
        "character": {
            "name": name,
            "realm": {"slug": "test-realm"},
            "region": {"slug": "eu"},
            "spec": {"name": "Blood"},
            "race": {"slug": "human"},
            "level": 80,
        },
        "rank": rank,
        "score": score,
        "runs": runs,
    }


class FakeRankingHttp:
    """Serves canned ranking pages for one spec/region, one call per page."""

    def __init__(self, pages: list[list[dict]]):
        self.pages = pages  # index 0 = page 0, etc.
        self.calls: list[int] = []

    def ranking_page_for(self, *, season, region, class_name, spec_name, page, page_size, access_key):
        self.calls.append(page)
        last_page = len(self.pages) - 1
        if page > last_page:
            return [], last_page
        return self.pages[page], last_page


class DiscoverCandidatesByCeilingTests(unittest.TestCase):
    def setUp(self):
        self.spec = next(s for s in SPECS if s.key == "DEATHKNIGHT_BLOOD")

    def _patch_ranking_page(self, fake: FakeRankingHttp):
        return patch(
            "tools.live_benchmark_engine.ranking_page",
            side_effect=lambda http, **kw: fake.ranking_page_for(**kw),
        )

    def test_finds_candidates_at_or_under_ceiling_and_skips_above(self):
        # Page 0: everyone above the ceiling (best key 20). Page 1: everyone at/under it.
        pages = [
            [_spec_ref(f"High{i}", i, 4000 - i, [{"mythicLevel": 20}]) for i in range(1, 6)],
            [_spec_ref(f"Low{i}", i, 1000 - i, [{"mythicLevel": 8}]) for i in range(1, 6)],
        ]
        fake = FakeRankingHttp(pages)
        with self._patch_ranking_page(fake):
            result = discover_candidates_by_ceiling(
                object(), self.spec, season="test-season", regions=("eu",),
                ceiling=9, target_count=5, max_pages=10, access_key=None,
            )
        self.assertEqual(5, len(result))
        self.assertTrue(all(row["name"].startswith("Low") for row in result))
        self.assertEqual(list(range(1, 6)), [row["rank"] for row in result])

    def test_returns_empty_when_nobody_qualifies(self):
        pages = [[_spec_ref(f"High{i}", i, 4000 - i, [{"mythicLevel": 25}]) for i in range(1, 6)]]
        fake = FakeRankingHttp(pages)
        with self._patch_ranking_page(fake):
            result = discover_candidates_by_ceiling(
                object(), self.spec, season="test-season", regions=("eu",),
                ceiling=9, target_count=5, max_pages=10, access_key=None,
            )
        self.assertEqual([], result)

    def test_stops_once_target_count_reached_without_reading_every_page(self):
        # 20 pages, all qualifying; only the first 2 should ever be requested for target_count=10.
        pages = [
            [_spec_ref(f"P{page}_{i}", i, 1000 - page * 10 - i, [{"mythicLevel": 5}]) for i in range(1, 6)]
            for page in range(20)
        ]
        fake = FakeRankingHttp(pages)
        with self._patch_ranking_page(fake):
            result = discover_candidates_by_ceiling(
                object(), self.spec, season="test-season", regions=("eu",),
                ceiling=9, target_count=10, max_pages=20, access_key=None,
            )
        self.assertEqual(10, len(result))
        self.assertLess(max(fake.calls), 19, "should not have scanned every page once target_count was met")

    def test_merges_across_regions_globally_by_score_no_region_quota(self):
        eu_pages = [[_spec_ref("EuTop", 1, 500, [{"mythicLevel": 8}])]]
        us_pages = [
            [_spec_ref(f"UsPlayer{i}", i, 900 - i, [{"mythicLevel": 8}]) for i in range(1, 4)]
        ]
        fake_eu = FakeRankingHttp(eu_pages)
        fake_us = FakeRankingHttp(us_pages)

        def routed(http, **kw):
            fake = fake_eu if kw["region"] == "eu" else fake_us
            return fake.ranking_page_for(**kw)

        with patch("tools.live_benchmark_engine.ranking_page", side_effect=routed):
            result = discover_candidates_by_ceiling(
                object(), self.spec, season="test-season", regions=("eu", "us"),
                ceiling=9, target_count=4, max_pages=10, access_key=None,
            )
        self.assertEqual(4, len(result))
        # US players (score 899/898/897) must outrank the single EU player (score 500).
        self.assertEqual(["UsPlayer1", "UsPlayer2", "UsPlayer3", "EuTop"], [row["name"] for row in result])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -k "BestKeyLevel or DiscoverCandidatesByCeiling" -v`
Expected: FAIL with `ImportError` (`BRACKET_CEILINGS`, `SAMPLE_SIZES`, `best_key_level`,
`discover_candidates_by_ceiling` do not exist yet).

- [ ] **Step 3: Implement `best_key_level` and the bracket constants**

Add near the top of `tools/live_benchmark_engine.py`, next to `DEFAULT_COHORTS` (`tools/live_benchmark_engine.py:55`):

```python
# Key-level difficulty brackets, agreed with the user 2026-09-27. A character's bracket is
# decided by the HIGHEST Mythic+ key they ran this season, across ALL their ranked runs (not
# only combat-log-tracked ones) - the best available skill signal. None means "no ceiling".
# Change these two numbers only here; nothing else in the pipeline hard-codes them.
BRACKET_CEILINGS: dict[str, int | None] = {"LOW": 9, "MID": 15, "HIGH": None}
SAMPLE_SIZES: tuple[int, ...] = (20, 50, 100)


def best_key_level(runs: list[dict[str, Any]]) -> int | None:
    """Highest mythicLevel across a character's runs, or None if none is usable."""
    levels = [
        int(run["mythicLevel"])
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("mythicLevel"), (int, float))
        and not isinstance(run.get("mythicLevel"), bool)
    ]
    return max(levels) if levels else None
```

- [ ] **Step 4: Run tests to verify `BestKeyLevelTests` passes**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -k BestKeyLevel -v`
Expected: PASS (4 tests). `DiscoverCandidatesByCeilingTests` still fails (function missing).

- [ ] **Step 5: Implement `discover_candidates_by_ceiling`**

Add directly after `discover_candidates` (`tools/live_benchmark_engine.py:715-760`):

```python
def _page_has_qualifying_entry(
    http: JsonClient, spec: Spec, *, season: str, region: str, page: int, page_size: int,
    ceiling: int, access_key: str | None,
) -> tuple[bool, list[dict[str, Any]], int]:
    entries, last_page = ranking_page(
        http, season=season, region=region, class_name=spec.class_name,
        spec_name=spec.spec_name, page=page, page_size=page_size, access_key=access_key,
    )
    qualifying = [
        e for e in entries
        if (ref := character_ref(e)) and ref.get("activeSpec") == spec.spec_name
        and (level := best_key_level(ref.get("runs") or [])) is not None and level <= ceiling
    ]
    return bool(qualifying), entries, last_page


def _locate_ceiling_pivot(
    http: JsonClient, spec: Spec, *, season: str, region: str, ceiling: int,
    last_page: int, access_key: str | None,
) -> int | None:
    """Binary search for the shallowest page containing a qualifying (best key <= ceiling)
    entry. Score decreases monotonically with page depth, and key level correlates with score,
    so pages containing a qualifying entry form a (roughly) contiguous tail run from some pivot
    page to last_page. Returns None if no page in [0, last_page] qualifies."""
    has_any, _, _ = _page_has_qualifying_entry(
        http, spec, season=season, region=region, page=last_page, page_size=100,
        ceiling=ceiling, access_key=access_key,
    )
    if not has_any:
        return None
    low, high = 0, last_page
    while low < high:
        mid = (low + high) // 2
        found, _, _ = _page_has_qualifying_entry(
            http, spec, season=season, region=region, page=mid, page_size=100,
            ceiling=ceiling, access_key=access_key,
        )
        if found:
            high = mid
        else:
            low = mid + 1
    return low


def discover_candidates_by_ceiling(
    http: JsonClient,
    spec: Spec,
    *,
    season: str,
    regions: tuple[str, ...],
    ceiling: int,
    target_count: int,
    max_pages: int,
    access_key: str | None,
) -> list[dict[str, Any]]:
    """Like discover_candidates, but only for characters whose best key this season is <=
    ceiling. Locates the right paging depth per region with a binary search (see
    _locate_ceiling_pivot) instead of scanning linearly from page 0, since qualifying
    candidates for a low ceiling can sit 1000+ pages deep for a popular spec."""
    discovered: dict[str, dict[str, Any]] = {}
    for region in regions:
        _, probe_last_page = ranking_page(
            http, season=season, region=region, class_name=spec.class_name,
            spec_name=spec.spec_name, page=0, page_size=100, access_key=access_key,
        )
        pivot = _locate_ceiling_pivot(
            http, spec, season=season, region=region, ceiling=ceiling,
            last_page=probe_last_page, access_key=access_key,
        )
        if pivot is None:
            continue
        page = pivot
        pages_scanned = 0
        while page <= probe_last_page and pages_scanned < max_pages:
            entries, last_page = ranking_page(
                http, season=season, region=region, class_name=spec.class_name,
                spec_name=spec.spec_name, page=page, page_size=100, access_key=access_key,
            )
            pages_scanned += 1
            for entry in entries:
                ref = character_ref(entry)
                if not ref or ref.get("activeSpec") != spec.spec_name:
                    continue
                level = best_key_level(ref.get("runs") or [])
                if level is None or level > ceiling:
                    continue
                key = f"{ref['region']}:{ref['realm']}:{ref['name']}".lower()
                previous = discovered.get(key)
                if previous is None or ref["score"] > previous["score"]:
                    ref["regionalRank"] = ref["rank"]
                    discovered[key] = ref
            region_count = sum(1 for row in discovered.values() if row["region"] == region)
            if page >= last_page or region_count >= target_count:
                break
            page += 1
    ranked = sorted(
        discovered.values(),
        key=lambda row: (-row["score"], row["region"], row["realm"], row["name"]),
    )[:target_count]
    for merged_rank, row in enumerate(ranked, 1):
        row["rank"] = merged_rank
    return ranked
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -k "BestKeyLevel or DiscoverCandidatesByCeiling" -v`
Expected: PASS (8 tests).

- [ ] **Step 7: Commit**

```bash
git add tools/live_benchmark_engine.py tools/tests/test_live_benchmark_engine.py
git commit -m "feat: bracket-ceiling candidate discovery for key-level benchmarks

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Wire brackets into the main collection loop; rename cohort keys

**Files:**
- Modify: `tools/live_benchmark_engine.py:1564-1712` (the per-spec loop and `database` assembly inside
  the function that currently builds `TOP_{size}` cohorts — locate via `for index, spec in enumerate(active_specs, 1):`)
- Modify: `tools/live_benchmark_engine.py:1751-1759` (`--cohorts` CLI arg)
- Test: `tools/tests/test_live_benchmark_engine.py`

**Interfaces:**
- Consumes: `BRACKET_CEILINGS`, `SAMPLE_SIZES`, `discover_candidates_by_ceiling`, `discover_candidates` (Task 1 + existing).
- Produces: each spec's `profile["cohorts"]` / `profile["gearCohorts"]` keyed `f"{bracket}_{size}"` (e.g.
  `"LOW_20"`, `"MID_100"`, `"HIGH_50"`) for every `bracket in BRACKET_CEILINGS` and `size in SAMPLE_SIZES`.
- Produces: CLI flag renamed `--sample-sizes` (was `--cohorts`), same comma-separated-ints parsing,
  default `",".join(str(v) for v in SAMPLE_SIZES)`.

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_live_benchmark_engine.py, new test in BenchmarkMergeAndRetryTests or a new class
class BracketCohortKeyTests(unittest.TestCase):
    def test_cohort_keys_cover_every_bracket_and_size(self):
        records = [
            {
                "name": f"P{i}", "realm": "r", "region": "eu", "score": 1000 - i,
                "itemLevel": 320, "verifiedRank": i,
                "stats": {k: 1000 + i for k in ("strength", "agility", "intellect", "stamina",
                                                  "crit", "haste", "mastery", "versatility")},
                "items": {},
            }
            for i in range(1, 25)
        ]
        cohorts = {
            f"{bracket}_{size}": aggregate_cohort(records, size)
            for bracket in BRACKET_CEILINGS for size in SAMPLE_SIZES
        }
        self.assertEqual(9, len(cohorts))
        self.assertIn("LOW_20", cohorts)
        self.assertIn("MID_50", cohorts)
        self.assertIn("HIGH_100", cohorts)
        # 24 records is enough for the 20-cohort (min sample 5) but not the 100-cohort.
        self.assertEqual("ok", cohorts["LOW_20"]["status"])
        self.assertEqual("insufficient", cohorts["LOW_100"]["status"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -k BracketCohortKey -v`
Expected: PASS already (this test only exercises `aggregate_cohort`, which is unchanged) — this step is
a sanity check that the *shape* the rest of this task relies on is correct before touching the main loop.
If it fails, fix the test's fixture data, not `aggregate_cohort`.

- [ ] **Step 3: Rewrite the per-spec collection loop**

In the function containing `for index, spec in enumerate(active_specs, 1):` (`tools/live_benchmark_engine.py:1566`),
replace the single `discover_candidates` call and the single `cohorts = {...}` block
(`tools/live_benchmark_engine.py:1568-1670`) with a per-bracket loop. Keep everything about
`fetch_record`/SimC/Wowhead reconstruction identical — it now just runs once per bracket instead of once
per spec:

```python
        max_size = max(SAMPLE_SIZES)
        bracket_cohorts: dict[str, Any] = {}
        bracket_gear_cohorts: dict[str, Any] = {}
        bracket_hero_trees: dict[str, Any] = {}
        bracket_hero_gear_trees: dict[str, Any] = {}
        bracket_run_counts: dict[str, int] = {}
        for bracket, ceiling in BRACKET_CEILINGS.items():
            print(f"[{index:02d}/{len(active_specs)}] {spec.key}/{bracket}: discovering candidates", flush=True)
            if ceiling is None:
                candidates = discover_candidates(
                    http, spec, season=season_slug, regions=args.regions,
                    target_count=max_size * args.candidate_multiplier,
                    max_pages=args.max_pages, access_key=access_key,
                )
            else:
                candidates = discover_candidates_by_ceiling(
                    http, spec, season=season_slug, regions=args.regions, ceiling=ceiling,
                    target_count=max_size * args.candidate_multiplier,
                    max_pages=args.max_pages, access_key=access_key,
                )
            print(f"  candidates={len(candidates)}; collecting exact logged runs", flush=True)
            run_records = []
            failure_reasons: Counter[str] = Counter()
            candidates_checked = 0
            batch_size = max(args.workers, args.workers * 4)
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for offset in range(0, len(candidates), batch_size):
                    batch = candidates[offset:offset + batch_size]
                    candidates_checked += len(batch)
                    futures = {
                        pool.submit(fetch_record, http, spec, candidate, season_slug, args.max_run_checks): candidate
                        for candidate in batch
                    }
                    for future in as_completed(futures):
                        record, reason = future.result()
                        if record:
                            run_records.append(record)
                        elif reason:
                            failure_reasons[reason] += 1
                    if len(run_records) >= max_size:
                        break
            run_records.sort(key=lambda row: (-row["score"], row["region"], row["realm"], row["name"]))
            run_records = run_records[:max_size]
            for verified_rank, record in enumerate(run_records, 1):
                record["verifiedRank"] = verified_rank
            if spec.role == "healer":
                print(f"  verifiedRuns={len(run_records)}; reconstructing stats from Wowhead tooltips", flush=True)
                stat_records, stat_failure_reasons = reconstruct_stats_with_wowhead(
                    spec, run_records, delay=args.wowhead_delay, workers=args.workers,
                )
                reconstruction_method = "median_wowhead_tooltip_summed_loadout"
            else:
                print(f"  verifiedRuns={len(run_records)}; reconstructing stats with SimulationCraft", flush=True)
                assert simc_binary is not None
                stat_records, stat_failure_reasons = reconstruct_stats_with_simc(
                    simc_binary, spec, run_records, timeout_seconds=args.simc_timeout, threads=args.simc_threads,
                )
                reconstruction_method = "median_simc_reconstructed_loadout"
            if not run_records:
                summary = "; ".join(f"{c}x {r}" for r, c in failure_reasons.most_common(3))
                message = f"{spec.key}/{bracket}: no exact logged-run snapshots; {summary or 'no candidates found'}"
                print(f"::warning title=Insufficient benchmark data::{message}", file=sys.stderr)
            for size in SAMPLE_SIZES:
                bracket_cohorts[f"{bracket}_{size}"] = aggregate_cohort(stat_records, size, reconstruction_method)
                bracket_gear_cohorts[f"{bracket}_{size}"] = aggregate_gear_cohort(run_records, size)
            hero_trees = aggregate_hero_trees(stat_records, SAMPLE_SIZES, reconstruction_method)
            hero_gear_trees = aggregate_hero_gear_trees(run_records, SAMPLE_SIZES)
            for tree_key, tree in hero_trees.items():
                bracket_hero_trees[f"{bracket}:{tree_key}"] = tree
            for tree_key, tree in hero_gear_trees.items():
                bracket_hero_gear_trees[f"{bracket}:{tree_key}"] = tree
            bracket_run_counts[bracket] = len(run_records)
            print(
                f"  {bracket}: runs={len(run_records)}/{candidates_checked}; "
                + ", ".join(f"{size}={bracket_cohorts[f'{bracket}_{size}']['status']}" for size in SAMPLE_SIZES),
                flush=True,
            )
        base = bracket_cohorts[f"LOW_{min(SAMPLE_SIZES)}"]
        profiles[spec.key] = {
            "status": base["status"],
            "class": spec.class_name,
            "spec": spec.spec_name,
            "role": spec.role,
            "primaryStat": spec.primary,
            "verifiedRunCount": sum(bracket_run_counts.values()),
            "cohorts": bracket_cohorts,
            "gearCohorts": bracket_gear_cohorts,
            "heroTalentTrees": bracket_hero_trees,
            "heroTalentGearTrees": bracket_hero_gear_trees,
        }
```

Notes for whoever implements this step:
- `spec.key` here is the loop variable from the existing `for index, spec in enumerate(active_specs, 1):`
  — do not confuse with `bracket` (the new inner loop variable).
- The pre-existing fields `candidateCount`, `coverage`, `runFailureReasons`, `statMatchFailureReasons`,
  `heroTalentAnalysis` become per-bracket rather than per-spec; drop them from `profiles[spec.key]` in this
  task (they were diagnostics, not consumed by `addon_benchmarks.py`) rather than inventing a 3x-nested
  shape for them. If a later session wants them back, add `profiles[spec.key]["byBracket"][bracket] = {...}`
  as a separate, explicit addition — do not guess at a shape now.
- Delete the old single `discover_candidates(...)` / `cohorts = {...}` / `gear_cohorts = {...}` /
  `hero_trees = ...` / `hero_gear_trees = ...` / `base = cohorts[...]` / `profiles[spec.key] = {...}` block
  this replaces (`tools/live_benchmark_engine.py:1568-1670`) entirely — do not leave the old block
  commented out or dead.

- [ ] **Step 4: Update the `database["source"]` metadata block**

In the same function, where `database = {...}` is assembled (`tools/live_benchmark_engine.py:1684-1710`),
replace `"rankCeilings": list(args.cohorts)` with:

```python
            "sampleSizes": list(SAMPLE_SIZES),
            "keyBrackets": {name: ceiling for name, ceiling in BRACKET_CEILINGS.items()},
```

- [ ] **Step 5: Rename the `--cohorts` CLI flag to `--sample-sizes`**

At `tools/live_benchmark_engine.py:1753`, change:

```python
    parser.add_argument("--cohorts", default=",".join(str(value) for value in DEFAULT_COHORTS))
```

to:

```python
    parser.add_argument("--sample-sizes", default=",".join(str(value) for value in SAMPLE_SIZES))
```

Then find every remaining use of `args.cohorts` in the file (there is parsing code shortly after argument
definition that turns the comma-separated string into a tuple of ints — search for `args.cohorts =` or
similar normalization) and rename to `args.sample_sizes`. Remove `DEFAULT_COHORTS` (`tools/live_benchmark_engine.py:55`)
once nothing references it — `SAMPLE_SIZES` (Task 1) replaces it.

- [ ] **Step 6: Update `validate_database`'s and `write_retry_queue`'s references to `TOP_{...}`/`args.cohorts`**

Task 4 (below) rewrites `validate_database`'s completeness gate in full — for this task, only fix what
would otherwise crash: search the file for `args.cohorts` and `min(args.cohorts)` outside the section
already changed in Steps 3-5, and rename to `args.sample_sizes` / `min(args.sample_sizes)` so the module
still imports and runs. Leave the `TOP_{required_minimum}` string-matching logic for Task 4.

- [ ] **Step 7: Run the full test file and fix remaining breaks**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -v`
Expected: some pre-existing tests that build fixtures with `TOP_25`/`TOP_100`/`TOP_200` keys or call
`build_database`/`validate_database` end-to-end will fail here — that is expected and is fully resolved by
Task 4. Confirm the *only* failures are in `validate_database`/`merge`/`retry` related tests (i.e. Task 1's
new tests and `BracketCohortKeyTests` still pass), then proceed; do not silence or skip failing tests.

- [ ] **Step 8: Commit**

```bash
git add tools/live_benchmark_engine.py tools/tests/test_live_benchmark_engine.py
git commit -m "feat: collect benchmark cohorts per key-level bracket instead of one pool

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: `addon_benchmarks.py` — two-axis `levels` output

**Files:**
- Modify: `tools/addon_benchmarks.py`
- Modify: `tools/tests/addon_fixtures.py`
- Test: `tools/tests/test_addon_benchmarks.py`

**Interfaces:**
- Consumes: `profile["cohorts"]` / `profile["gearCohorts"]` keyed `f"{bracket}_{size}"` (Task 2's output shape).
- Produces: `build_profile(...)["levels"]` shaped `{bracket: {str(size): build_level_context(...)}}` for
  every `bracket in ("LOW", "MID", "HIGH")` and `size in (20, 50, 100)` that has valid data (same
  "drop it if not valid" behavior `build_level_context` already has, just nested one level deeper).

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_addon_benchmarks.py — adapt the existing profile-fixture builder (in
# tools/tests/addon_fixtures.py) to emit LOW/MID/HIGH x 20/50/100 cohort keys instead of
# TOP_25/TOP_100/TOP_200, then:

class TwoAxisLevelsTests(unittest.TestCase):
    def test_levels_nested_by_bracket_then_sample_size(self):
        profile = build_full_profile_fixture()  # updated fixture, see Step 3
        built = build_profile("DEATHKNIGHT_BLOOD", profile)
        self.assertIn("LOW", built["levels"])
        self.assertIn("MID", built["levels"])
        self.assertIn("HIGH", built["levels"])
        self.assertIn("20", built["levels"]["MID"])
        self.assertIn("50", built["levels"]["MID"])
        self.assertIn("100", built["levels"]["MID"])
        self.assertEqual("MID", built["levels"]["MID"]["100"]["benchmark"]["level"])
        self.assertEqual("MID_100", built["levels"]["MID"]["100"]["benchmark"]["cohort"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tools/tests/test_addon_benchmarks.py -k TwoAxisLevels -v`
Expected: FAIL (`build_full_profile_fixture` doesn't exist yet / `built["levels"]` still flat `ELITE/STANDARD/BROAD`).

- [ ] **Step 3: Update `tools/tests/addon_fixtures.py`'s profile builder**

Find the fixture function that currently builds a profile dict with `"cohorts": {"TOP_25": ..., "TOP_100":
..., "TOP_200": ...}` (and the matching `"gearCohorts"`). Change it to accept/produce keys for
`("LOW", "MID", "HIGH")` × `(20, 50, 100)`, i.e. 9 entries each, reusing whatever per-cohort stub data it
already builds (same stub cohort dict shape, just under 9 keys instead of 3). Keep the function's public
name if other tests still reference it; add a `bracket sizes` parameter only if needed to avoid duplicating
the whole function.

- [ ] **Step 4: Rewrite `LEVELS`, `build_level_context`, `build_profile`, `build_report` in `tools/addon_benchmarks.py`**

Replace the constant at `tools/addon_benchmarks.py:27`:

```python
LEVELS = {"ELITE": "TOP_25", "STANDARD": "TOP_100", "BROAD": "TOP_200"}
```

with:

```python
BRACKETS = ("LOW", "MID", "HIGH")
SAMPLE_SIZES = (20, 50, 100)
```

Change `build_level_context` (`tools/addon_benchmarks.py:227-259`) to take the already-composed cohort key
and bracket name directly instead of deriving the label from `LEVELS`:

```python
def build_level_context(profile: dict[str, Any], bracket: str, cohort_key: str) -> dict[str, Any] | None:
    cohort = (profile.get("cohorts") or {}).get(cohort_key)
    gear = (profile.get("gearCohorts") or {}).get(cohort_key)
    if not valid_cohort(cohort) or not isinstance(gear, dict) or gear.get("status") != "ok":
        return None
    popular = gear.get("popularItems") or {}
    slots = pick_popular_slots(popular)
    average = cohort.get("averageItemLevel")
    stats = secondary_stats(cohort, TARGET_KEYS)
    if len(slots) < MIN_SLOTS or not isinstance(average, (int, float)) or average < MIN_ITEM_LEVEL or len(stats) < 2:
        return None
    return {
        "targets": {
            "averageItemLevel": float(average),
            "itemCount": len(slots),
            "itemLevelSlots": len(slots),
            "statTargets": {"context": "Mythic+", "source": "StatVerdict live benchmarks", "stats": stats},
            "targetMetadata": {"lowItemReplacements": 0, "unresolvedLowItems": 0},
            "sourceGoal": GOAL,
        },
        "bis": {"label": "Popular", "slots": slots},
        "trinkets": rank_trinkets(popular),
        "priorityProfiles": build_priority_profiles(profile, cohort_key, cohort),
        "benchmark": {
            "level": bracket,
            "cohort": cohort_key,
            "sampleSize": int(cohort.get("sampleSize") or 0),
            "minimumSample": int(cohort.get("minimumSample") or 0),
            "confidence": cohort.get("confidence") or "unknown",
            "completeness": float(cohort.get("completeness") or 0.0),
        },
    }
```

Change `build_profile` (`tools/addon_benchmarks.py:262-279`):

```python
def build_profile(spec_key: str, profile: dict[str, Any]) -> dict[str, Any] | None:
    if profile.get("status") != "ok":
        return None
    levels: dict[str, dict[str, Any]] = {}
    for bracket in BRACKETS:
        for size in SAMPLE_SIZES:
            cohort_key = f"{bracket}_{size}"
            context = build_level_context(profile, bracket, cohort_key)
            if context:
                levels.setdefault(bracket, {})[str(size)] = context
    if not levels:
        return None
    reference_key = next(
        (f"{b}_100" for b in ("HIGH", "MID", "LOW") if f"{b}_100" in (profile.get("cohorts") or {})
         and valid_cohort(profile["cohorts"][f"{b}_100"])),
        None,
    )
    reference = (profile.get("cohorts") or {}).get(reference_key) if reference_key else None
    return {
        "specKey": spec_key,
        "classToken": _class_token(profile.get("class")),
        "primaryStat": measured_primary_stat(reference, str(profile.get("primaryStat") or "")),
        "levels": levels,
    }
```

Update `build_report` (`tools/addon_benchmarks.py:323-345`) to iterate the new nesting instead of the
fixed `("ELITE", "STANDARD", "BROAD")` tuple:

```python
    for spec_key in sorted(data["profiles"]):
        profile = data["profiles"][spec_key]
        for bracket in BRACKETS:
            for size in SAMPLE_SIZES:
                context = profile["levels"].get(bracket, {}).get(str(size))
                label = f"{bracket}_{size}"
                if not context:
                    lines.append(f"{spec_key} {label}: no data")
                    continue
                slots = context["bis"]["slots"]
                favourites = sum(1 for s in slots if s["usagePercent"] >= 40.0)
                counts = {tier: 0 for tier, _ in TIER_THRESHOLDS}
                for trinket in context["trinkets"]:
                    counts[trinket["tier"]] += 1
                tiers = " ".join(f"{tier}:{counts[tier]}" for tier, _ in TIER_THRESHOLDS)
                bench = context["benchmark"]
                lines.append(
                    f"{spec_key} {label}: sample {bench['sampleSize']} ({bench['confidence']}), "
                    f"primary {profile['primaryStat']}, slots {len(slots)}, "
                    f"clear favourites (>=40%): {favourites}/{len(slots)}, tiers {tiers}"
                )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tools/tests/test_addon_benchmarks.py -v`
Expected: PASS. Fix any remaining fixture references to `ELITE`/`STANDARD`/`BROAD`/`TOP_25` etc. found
along the way — grep the test file for those literals to be sure none are left.

- [ ] **Step 6: Commit**

```bash
git add tools/addon_benchmarks.py tools/tests/addon_fixtures.py tools/tests/test_addon_benchmarks.py
git commit -m "feat: build addon benchmark file with bracket x sample-size levels

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: `validate_database` completeness gate for the new key scheme

**Files:**
- Modify: `tools/live_benchmark_engine.py:1330-1450` (`validate_database` and its helpers)
- Test: `tools/tests/test_live_benchmark_engine.py`

**Interfaces:**
- Consumes: `BRACKET_CEILINGS`, `SAMPLE_SIZES` (Task 1), the `{bracket}_{size}` cohort keys (Task 2).
- Produces: `validate_database(database, min_size, max_insufficient_specs, expected_specs)` — same
  signature and same "raise `ValueError` with a bullet list of problems" behavior, but a spec now counts
  as complete only when its smallest sample size (20) is `"ok"` in **all three** brackets.

- [ ] **Step 1: Write the failing test**

```python
class ValidateDatabaseBracketGateTests(unittest.TestCase):
    def _profile(self, ok_brackets: set[str]) -> dict:
        cohorts = {}
        gear_cohorts = {}
        for bracket in BRACKET_CEILINGS:
            for size in SAMPLE_SIZES:
                sample = size if bracket in ok_brackets else 0
                cohorts[f"{bracket}_{size}"] = {
                    "status": "ok" if bracket in ok_brackets else "insufficient",
                    "requestedSize": size, "sampleSize": sample, "minimumSample": min(size, 5),
                    "statTargets": {"stats": {
                        "stamina": 1, "crit": 1, "haste": 1, "mastery": 1, "versatility": 1,
                    }},
                }
                gear_cohorts[f"{bracket}_{size}"] = {
                    "status": "ok" if bracket in ok_brackets else "insufficient",
                    "sampleSize": sample, "minimumSample": min(size, 5),
                    "popularItems": {}, "popularTrinketPairs": [], "popularRingPairs": [],
                    "setConfigurations": [], "socketAndEnchantUsage": {}, "talentLoadouts": [],
                    "runMetrics": {}, "qualityCoverage": {},
                }
        return {
            "status": "ok" if ok_brackets == set(BRACKET_CEILINGS) else "insufficient",
            "class": "death-knight", "spec": "Blood", "role": "tank", "primaryStat": "strength",
            "verifiedRunCount": 60, "cohorts": cohorts, "gearCohorts": gear_cohorts,
            "heroTalentTrees": {},
        }

    def _database(self, profile: dict) -> dict:
        spec = next(s for s in SPECS if s.key == "DEATHKNIGHT_BLOOD")
        return {
            "schemaVersion": SCHEMA_VERSION, "generatedAt": utc_now(),
            "source": {"totals": {"verifiedRuns": 60, "reconstructedStats": 60}},
            "profiles": {spec.key: profile},
        }, [spec]

    def test_all_brackets_ok_passes(self):
        database, specs = self._database(self._profile(set(BRACKET_CEILINGS)))
        validate_database(database, min(SAMPLE_SIZES), 0, expected_specs=specs)  # must not raise

    def test_missing_low_bracket_fails(self):
        database, specs = self._database(self._profile({"MID", "HIGH"}))
        with self.assertRaises(ValueError) as ctx:
            validate_database(database, min(SAMPLE_SIZES), 0, expected_specs=specs)
        self.assertIn("LOW", str(ctx.exception))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -k ValidateDatabaseBracketGate -v`
Expected: FAIL — `test_missing_low_bracket_fails` does not raise, because the current gate only checks
one `TOP_{required_minimum}` label, which no longer exists.

- [ ] **Step 3: Rewrite the completeness gate**

In `validate_database` (`tools/live_benchmark_engine.py:1368-1441`), the loop `for spec in expected_specs:`
currently tracks a single `base_ok` flag via `if label == f"TOP_{required_minimum}" and complete: base_ok = True`.
Replace that with tracking completeness per bracket:

```python
        bracket_ok = {bracket: False for bracket in BRACKET_CEILINGS}
        for label, cohort in cohorts.items():
            if not isinstance(cohort, dict):
                errors.append(f"{spec.key}/{label}: malformed cohort")
                continue
            sample = cohort.get("sampleSize", 0)
            requested = cohort.get("requestedSize", 0)
            minimum = cohort.get("minimumSample", minimum_sample_size(requested))
            stats = cohort.get("statTargets", {}).get("stats", {})
            complete = requested > 0 and sample >= minimum
            expected_status = "ok" if complete else "insufficient"
            if cohort.get("status") != expected_status:
                errors.append(f"{spec.key}/{label}: status must be {expected_status}")
            if complete and not all(key in stats for key in ("stamina", "crit", "haste", "mastery", "versatility")):
                errors.append(f"{spec.key}/{label}: required stat targets missing")
            bracket, _, size_text = label.partition("_")
            if bracket in bracket_ok and size_text == str(required_minimum) and complete:
                bracket_ok[bracket] = True
        base_ok = all(bracket_ok.values())
        if not base_ok:
            missing = [b for b, ok in bracket_ok.items() if not ok]
            errors.append(f"{spec.key}: missing a complete {required_minimum}-sample cohort for bracket(s) {', '.join(missing)}")
```

This replaces the existing `base_ok = False` initializer and the inner `if label == f"TOP_{required_minimum}"...`
line; leave the rest of the per-cohort loop body (status/stat checks) unchanged. Also update the hero-tree
check a few lines below (`tools/live_benchmark_engine.py:1436`, `base = tree_cohorts.get(f"TOP_{required_minimum}", {})`)
— hero trees are now keyed `f"{bracket}:{tree_key}"` (Task 2 Step 3) with per-bracket cohorts inside, so
change this to check the `MID_{required_minimum}` cohort (MID is the closest equivalent to today's
"the normal default") inside each hero tree's own `cohorts` dict:

```python
                base = tree_cohorts.get(f"MID_{required_minimum}", {})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tools/tests/test_live_benchmark_engine.py -v`
Expected: PASS, full file. This is the point where Task 2 Step 7's deferred failures must now all be
resolved — if any remain, fix them here (they are all `validate_database`/merge/retry related by
construction, per Task 2 Step 7).

- [ ] **Step 5: Commit**

```bash
git add tools/live_benchmark_engine.py tools/tests/test_live_benchmark_engine.py
git commit -m "fix: validate_database requires every bracket complete, not just one cohort

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: Manual end-to-end smoke check (no in-game step)

**Files:** none modified — verification only.

- [ ] **Step 1: Run the full Python test suite**

Run: `python -m pytest tools/tests/ -v`
Expected: PASS, zero failures, zero skips introduced by this plan.

- [ ] **Step 2: Run a tiny real pipeline slice against the live Raider.IO API**

Pick one cheap, well-known spec/role and the smallest sample size only, to sanity-check the new discovery
and output shape against real data without a full 40-spec run:

```bash
python tools/live_benchmark_engine.py --specs DEATHKNIGHT_BLOOD --sample-sizes 20 --regions eu \
  --simc-bin "$SIMC_BINARY" --json-out /tmp/sv_bracket_smoke.json --lua-out /tmp/sv_bracket_smoke.lua
python -c "
import json
data = json.load(open('/tmp/sv_bracket_smoke.json'))
profile = data['profiles']['DEATHKNIGHT_BLOOD']
print('status:', profile['status'])
print('cohort keys:', sorted(profile['cohorts'].keys()))
for key in sorted(profile['cohorts']):
    c = profile['cohorts'][key]
    print(f'  {key}: status={c[\"status\"]} sample={c[\"sampleSize\"]}')
"
```

Expected: `cohort keys` prints exactly `LOW_20`, `MID_20`, `HIGH_20` (only size 20 was requested), each
with a real `sampleSize` count and `status` of `ok` or `insufficient` depending on live data — LOW and MID
are new; confirm their `sampleSize` is nonzero, since that's the concrete proof the bracket-ceiling
discovery (Task 1) actually found real low/mid-key players and not an empty set.

- [ ] **Step 3: Run `addon_benchmarks.py --report` against the smoke output**

```bash
python tools/addon_benchmarks.py --inputs /tmp --report
```

(First move/rename `/tmp/sv_bracket_smoke.json` to match the `SV_LiveBenchmarkData_*.json` glob
`load_databases` expects, e.g. `/tmp/SV_LiveBenchmarkData_Smoke.json`, before running this step.)

Expected: prints one line per `DEATHKNIGHT_BLOOD {bracket}_{size}` combination found, with real sample
sizes and stat-priority tiers — confirms Task 3's builder correctly consumes Task 2's new cohort shape
end-to-end.

- [ ] **Step 4: Report results to the user in plain language, no further action**

This task has no commit — it is a verification checkpoint. Summarize for the user (per the project's
"explain simply" convention): did the smoke run find real Low/Mid players for this spec, and did the
report step produce sensible output. Do not proceed to Phase 2 planning in the same sitting unless asked.
