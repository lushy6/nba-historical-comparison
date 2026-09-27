# NBA Historical Comparison ("Season Echoes") — Implementation Plan

_Last updated 2026-09-27 from a static code review. No commands, tests, or builds were run for this update._

## Goal

Rank the Top-15 most statistically similar NBA/BAA player or team seasons from the curated historical CSV catalog. Missing measures stay unavailable, and headshots and logos appear only on an exact local identity match.

## Current state

- **Code:** a FastAPI backend (`backend/app`: resolver, scope, similarity, identity) and a Next.js frontend.
- **Completed plans:** `docs/superpowers/plans/2026-09-20-nba-historical-comparison.md` and `...-similarity-discovery-upgrade.md` both merged as PR #1, commit `1b62df7`. They are kept as the historical record and have not been edited.
- **Data:** the local catalog `data/historical/` includes seasons through 2026. Basketball-Reference-style multi-team rows in this data use **`2TM`/`3TM`/`4TM`**. There are 3,051 such rows in `Player Totals.csv`, 2,838 in each of `Advanced.csv` and `Player Per Game.csv`, and **zero `TOT` rows**.
- **Stale worktree:** `.worktrees/similarity-discovery-upgrade/` still exists on disk, holding a `README.md` and `frontend/`. `git worktree list` no longer knows about it, so it is an orphaned directory. It is gitignored.
- **Uncommitted change:** only `frontend/next-env.d.ts`, which Next regenerates.

## Review findings

| ID | Severity | Type | Location | Finding |
|---|---|---|---|---|
| NHC-1 | **High** | **Confirmed** | `backend/app/resolver.py:405-438` | Multi-team seasons are counted two or three times over. The collapse logic only recognises `team == "TOT"`. With the local data's `2TM` markers, the `2TM` total row and each per-team row form one group with `group_size > 1`, and `PLAYER_BASE_METRICS`, `win_shares` and `vorp` are **summed across all of them**. The test at `backend/tests/test_historical_csv_resolver.py:263` pins this: `points == 4170` is 3 × 1,390, and the comment there admits "synthetic totals need a separate statistics fix". It affects every traded player's season in the modern data. Their totals are inflated about 2x, which distorts both their own comparisons and the scaler for everyone else. |
| NHC-2 | Medium | Confirmed logic; impact depends on the data | `backend/app/similarity.py:130-142` | The same issue as the MLB sibling. Advanced features the selected season has become mandatory for candidates through `dropna(subset=features)`. Steals, blocks and turnovers (pre-1973/74) and 3PA (pre-1979/80) also make old seasons unreachable from modern ones, and the relationship is asymmetric. |
| NHC-3 | Low | Risk | `backend/app/identity.py:41` | Identity is resolved by folded **name** only. The ambiguity guard prevents duplicates *inside* `nba.sqlite`, but a historical player who shares a name with a single different modern player gets the wrong headshot. Team names that moved franchise (e.g., "Charlotte Hornets" 1988-2002) get the current franchise's logo. |
| NHC-4 | Low | Hygiene | `.worktrees/` | An orphaned worktree directory is left over from the merged feature branch. The branch `feature/similarity-discovery-upgrade` also still exists locally and on origin. |
| NHC-5 | Low | Tests/CI | repo | There is no CI workflow. Nothing runs the backend or frontend suites on push. |

## Phases

### Phase 1: Fix multi-team aggregation (blocks trust in every result)

**Status: DONE 2026-09-27.** `backend/app/resolver.py` has `_is_multi_team_total()` (`TOT` or `\d+TM`), used by both the CSV and SQLite paths. The locking test now expects the season total (1,390), and there are a new `3TM` test and 10 marker cases. A mutation check confirmed both new tests fail under the old `TOT`-only rule. The suite is 90/90. On the real catalog, Agbaji 2025-26 = 314 and Alvarado = 510 (their `2TM` rows), and the maximum season is 4,029 (Chamberlain 1961-62). **P1.2 dropped as unnecessary**: the frame caches are in-process `lru_cache`s, which never outlive a code change (a restart, or `--reload`, clears them), and nothing persists frames to disk.

- **P1.1 Recognise synthetic totals** (NHC-1). Treat `team` matching `^(TOT|\d+TM)$` as the season total, as `nba-contract-value/importer/bref_nba.py:22` already does. Keep the total row's stats, and derive affiliations from the per-team rows only.
  - *Accept:* `test_historical_affiliations_exclude_unverified_aggregate_markers` is rewritten to expect `points == 1390` (the 2TM row). Team codes stay `AUR|HBR`, and `win_shares`/`vorp` equal the total row's values. A new test covers `3TM` with three team rows.
  - *Data check:* `Player Totals.csv` has zero `TOT` rows and 3,051 `2TM`/`3TM`/`4TM` rows. After the fix, no player-season's `points` should exceed that season's league maximum. Add that invariant as a test over the real catalog, marked to skip when the data is absent.
- **P1.2 Invalidate the caches.** The frame caches are keyed on file signatures, not code version. Add a resolver-version constant to the cache key so a running server can't serve old aggregates after a code change.

### Phase 2: Similarity semantics

- **P2.1 Rank on base features only, and show advanced metrics when both seasons have them** (NHC-2). Keep this in lock-step with the MLB sibling's P1.1.
  - *Accept:* a symmetry test (A→B score == B→A score) passes, and a 1965 player can appear in a 2020 player's pool when the base features exist for both.
- **P2.2 Reconsider totals versus rates.** The base metrics are season **totals**, so games played dominates the "shape" after scaling. Evaluate per-game or per-36 inputs behind a flag. Document the result either way.

### Phase 3: Identity and hygiene

- **P3.1 Season-aware identity** (NHC-3). Resolve players by `player_id` from `Player Totals.csv` where a crosswalk exists. Resolve teams by `(abbreviation, season)` against a franchise table, and fall back to a monogram otherwise.
  - *Accept:* 1995 "Charlotte Hornets" gets a monogram, not the current CHA logo.
- **P3.2 Clean up** (NHC-4). Delete `.worktrees/similarity-discovery-upgrade` after confirming it has no unique files (`git status` inside it, or diff against `main`). Delete the merged branch locally and on origin.
- **P3.3 CI** (NHC-5). Add a GitHub Actions workflow running `pytest` (fixture-only tests) and `npm run lint && npm run typecheck && npm test`.

## Sequencing

P1.1 comes first; everything else inherits correct aggregates from it. P2.1 changes scores, so ship it in the same release as P1 with a README note. P3 is independent.

## Validation (documented only; not run in this review)

```powershell
$env:NBA_HISTORICAL_DATA_PATH = "$PWD\data\historical"
cd backend; .\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend; npm run lint; npm run typecheck; npm test
# Spot check after P1.1: compare a known 2TM season (e.g., a 2025-26 deadline trade)
# and confirm points equal the Basketball-Reference season total, not a multiple of it.
```
