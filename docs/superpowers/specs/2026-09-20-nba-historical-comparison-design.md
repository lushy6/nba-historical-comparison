# NBA Historical Comparison — Design Specification

## Objective

Build a local-first NBA historical comparison application for a fan or analyst who wants to select a player or team and find the closest comparable historical season. Results must make the underlying comparison understandable: a normalized 0–100 similarity score, an explanatory tier, and a radar comparison of the primary player measures.

The only production data source is the user's local `nba.sqlite` from Kaggle dataset `wyattowalsh/basketball`. The application must inspect the local database catalog before selecting source tables and columns. It must not assume a version-specific table layout or fabricate statistics when the database is absent or incomplete.

## Capability Map

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `data-contract` | Locate the SQLite file, inspect tables/columns, select compatible source relations, and normalize rows | — |
| `similarity-engine` | Scale comparable numeric features, compute neighbors, scores, tiers, and radar values | `data-contract` |
| `comparison-api` | Validate requests and expose search/comparison/health HTTP contracts | `data-contract`, `similarity-engine` |
| `comparison-ui` | Search, request state, visual comparison, accessibility, reduced-motion behavior | `comparison-api` |

Build order: `data-contract` → `similarity-engine` → `comparison-api` → `comparison-ui`.

## Architecture

```text
Next.js App Router  ─── fetch ───▶ FastAPI
     │                              │
     │                              ├── DatasetCatalog (sqlite_master + PRAGMA)
     │                              ├── SchemaResolver (actual table/column aliases)
     │                              └── SimilarityService (Pandas + StandardScaler + cosine)
     │                                                        │
     └──── radar / score / tier ◀────────────────────────────┘
                                        nba.sqlite (read-only)
```

`DatasetCatalog` is responsible for safely opening the path configured by `NBA_DATABASE_PATH` (defaulting to repository-root `nba.sqlite`), listing the schema, and enforcing read-only connections. `SchemaResolver` generates parameterized SQL only from inspected identifiers and converts source tables into stable, application-owned normalized frames. It fails with a typed diagnostics response when a dataset version lacks the necessary columns.

The similarity engine never reaches into SQLite directly. It receives a frame of per-player or per-team season statistics, drops the selected record, standardizes comparable features, calculates cosine similarity, then maps the resulting value into 0–100 and a human-readable tier. Radar values are min–max normalized per feature for visual comparability, while raw formatted values remain available for honest tooltips.

## API Contract

| Endpoint | Success response | Failure behavior |
| --- | --- | --- |
| `GET /api/health` | database status, discovered table names, resolver readiness | reports missing/unreadable dataset without a server error |
| `GET /api/players/search?q=` | matching IDs, names, team/season context | empty query validates to 422 |
| `GET /api/teams/search?q=` | matching IDs, names, season context | empty query validates to 422 |
| `GET /api/players/{id}/compare` | selected season, closest match, score, tier, feature/raw radar values | 404 if selection absent; 503 plus diagnostics if dataset unresolved |
| `GET /api/teams/{id}/compare` | selected team season, closest match, score, tier, comparable metrics | same typed error model |

Responses are Pydantic models. The frontend owns no data assumptions beyond those models.

## Tech Stack and Commands

- Backend: Python 3.12, FastAPI, SQLModel/SQLAlchemy, Pandas, SciPy, scikit-learn, pytest.
- Frontend: Next.js App Router, TypeScript, Tailwind CSS, Framer Motion, Radix UI, Recharts.
- Data: the local Kaggle SQLite export only; it is ignored by Git.

Planned commands:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
npm run dev
```

## Project Structure

```text
backend/app/
  catalog.py       # read-only SQLite inspection
  resolver.py      # schema-to-normalized-frame mapping
  similarity.py    # pure data-science logic
  schemas.py       # HTTP response and error models
  main.py          # FastAPI routing and dependency composition
backend/tests/     # unit and endpoint tests; temporary SQLite fixtures only
frontend/src/app/  # App Router page, layout, global styles
frontend/src/components/ # search and comparison composition
frontend/src/lib/  # typed API client and presentation helpers
```

## Code Style

Use small, typed functions with an explicit boundary between untrusted source data and application models.

```python
def similarity_score(selected: pd.Series, candidates: pd.DataFrame, features: Sequence[str]) -> pd.Series:
    matrix = StandardScaler().fit_transform(candidates.loc[:, features])
    target = StandardScaler().fit(candidates.loc[:, features]).transform(selected[features].to_frame().T)
    return pd.Series(cosine_similarity(target, matrix)[0], index=candidates.index)
```

Identifiers from the database are allowed only after catalog inspection and are quoted; all values use bound parameters. React components receive typed data, use semantic controls/labels, and honor `prefers-reduced-motion`.

## Testing Strategy

- Backend unit tests create a temporary SQLite fixture to prove catalog discovery, resolver diagnostics, standardization, exclusion of the selected record, score bounds, tier thresholds, and formatted radar output.
- Backend endpoint tests run through FastAPI `TestClient` with dependency-injected temporary database paths.
- Frontend component tests cover search states, error state, score/tier presentation, and accessible chart labels.
- A production database is never required for test execution. Once `nba.sqlite` is supplied, an integration smoke command validates the live catalog and chosen mappings before comparisons are enabled.

## Boundaries

- Always: inspect `sqlite_master` and `PRAGMA table_info` before source queries; use read-only database connections; parameterize values; validate API input; test each behavior before implementation; respect reduced-motion preferences.
- Ask first: download a copy of the Kaggle dataset, alter the dataset, add authentication, publish/deploy, or connect a third-party analytics API.
- Never: commit `nba.sqlite`, invent production source columns, present missing advanced metrics as zero, scrape NBA data, or expose a writable database endpoint.

## Success Criteria

1. A clean clone can install and build both applications without `nba.sqlite`.
2. `GET /api/health` clearly reports a missing dataset and does not crash.
3. With a compatible `nba.sqlite`, the catalog logs the actual tables/columns and resolves player/team season sources based on inspected metadata.
4. Player and team compare endpoints return an alternative historical match, a bounded 0–100 score, a tier, and consistent radar/metric data.
5. The UI supports keyboard-operable search, loading/error/empty comparison states, responsive layout, readable contrast, and reduced-motion alternatives.
6. Backend tests, frontend tests/typecheck/lint/build, and an integration smoke test pass.

## Open Questions

None block the scaffold. The data resolver remains intentionally version-adaptive until the user places the actual `nba.sqlite` in the project root, at which point its diagnostic endpoint will pin the verified source mapping.
