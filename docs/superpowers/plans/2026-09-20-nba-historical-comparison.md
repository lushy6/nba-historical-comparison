# NBA Historical Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` or an equivalent task-by-task workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a locally runnable NBA historical player and team comparison application that only activates after validating the supplied Kaggle SQLite database.

**Architecture:** FastAPI owns read-only catalog discovery, normalization, and pure similarity computation. Next.js owns user input, visual presentation, and accessible motion. The API boundary is typed and resilient to a missing or incompatible database.

**Tech Stack:** Python/FastAPI/Pandas/scikit-learn/SQLModel/pytest; Next.js/TypeScript/Tailwind/Framer Motion/Radix UI/Recharts.

**Spec:** `docs/superpowers/specs/2026-09-20-nba-historical-comparison-design.md`

## Global Constraints

- SQLite is opened read-only; `nba.sqlite` remains untracked.
- Production mappings are selected from `sqlite_master` and `PRAGMA table_info`, never unverified hard-coded schema declarations.
- Missing advanced metrics remain unavailable instead of becoming zeroes.
- API errors are typed and surfaced in the UI.
- All API and visual interactions preserve keyboard access and reduced-motion behavior.

---

### Task 1: Repository and executable scaffolding

**Files:** root Git configuration; backend packaging/configuration; frontend Next.js/Tailwind configuration; root documentation.

- [ ] Create the ignored local-data and build-output boundaries.
- [ ] Create the FastAPI and Next.js dependency manifests and executable scripts.
- [ ] Install dependencies, run empty test/lint/typecheck baselines, and commit the scaffold.

### Task 2: Dataset catalog and schema diagnostics

**Files:** `backend/app/catalog.py`, `backend/app/schemas.py`, `backend/tests/test_catalog.py`.

- [ ] Write failing tests for a missing database and a temporary SQLite catalog.
- [ ] Implement read-only file resolution, `sqlite_master` discovery, quoted catalog identifiers, and `PRAGMA table_info` inspection.
- [ ] Verify the tests pass and expose the catalog in `GET /api/health`.

### Task 3: Normalized source resolver

**Files:** `backend/app/resolver.py`, `backend/app/errors.py`, `backend/tests/test_resolver.py`.

- [ ] Write failing tests for candidate-source selection, missing required measures, and case-insensitive column aliases.
- [ ] Implement resolver diagnostics plus normalized player/team season frames using only catalog-confirmed identifiers.
- [ ] Run tests and a temporary-dataset end-to-end normalization check.

### Task 4: Similarity engine and comparison routes

**Files:** `backend/app/similarity.py`, `backend/app/main.py`, `backend/tests/test_similarity.py`, `backend/tests/test_api.py`.

- [ ] Write failing tests for self-exclusion, score bounds, tiers, dimension-consistent radar values, and typed endpoint failures.
- [ ] Implement scaling, cosine neighbor selection, rankings, and FastAPI search/comparison routes.
- [ ] Run the full backend suite and commit the API slice.

### Task 5: Polished client interface

**Files:** `frontend/src/app/*`, `frontend/src/components/*`, `frontend/src/lib/*`, frontend tests.

- [ ] Write failing UI tests for an accessible autocomplete, loading/error states, tier color semantics, and radar labels.
- [ ] Implement the responsive hero/search interface, typed API client, animated result entry, Radix result chooser, and Recharts player radar.
- [ ] Run frontend tests, lint, typecheck, and production build; commit the UI slice.

### Task 6: Integration and documented dataset handoff

**Files:** `README.md`, `backend/app/main.py`, smoke tests/config.

- [ ] Add CORS/configuration and a real-database smoke command that prints the selected catalog mapping.
- [ ] Verify graceful no-database behavior and the full browser flow using the temporary fixture.
- [ ] Document exactly where to place `nba.sqlite`, run all verification gates, and commit the integration slice.
