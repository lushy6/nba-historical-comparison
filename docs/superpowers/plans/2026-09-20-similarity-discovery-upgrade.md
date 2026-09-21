# NBA Similarity Discovery Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver filterable, Top 15 NBA player/team similarity discovery with asset-backed entity cards and locally interactive Basic/Advanced charts.

**Architecture:** FastAPI will preserve affiliation and optional visual identity in normalized season frames, filter candidate pools before cosine scoring, and return a fully hydrated Top 15 response. The Next.js client will own scope controls and active-match state, rendering all chart transitions from the one comparison response rather than making per-row network requests.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Pandas, scikit-learn, pytest; Next.js App Router, TypeScript, Tailwind CSS, Framer Motion, Radix Tooltip/Popover, Recharts, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-20-similarity-discovery-upgrade-design.md`

## Global Constraints

- Season data continues to come from the verified local historical CSV catalog; source data and `nba.sqlite` remain untracked and read-only.
- `season_from` and `season_to` are inclusive four-digit source-season bounds; equal values express one exact season.
- Team filtering applies only to player candidate pools and matches any verified affiliation on a traded-player season.
- Missing historic features are omitted from both similarity and charts; zero is never an imputed substitute for an unavailable statistic.
- The compare endpoint returns no more than 15 alternatives and contains enough metric data for client-side active-match changes.
- Only chart geometry may interpolate its SVG path. All client chrome motion is transform/opacity-only, less than 300ms, reduced-motion-aware, and keyboard actions do not animate.
- NBA CDN media is requested only after an exact optional local identity match; uncertain, missing, and failed images use a stable fallback without layout shift.
- Preserve all existing unrelated uncommitted work. Stage and commit only files belonging to each verified implementation slice.

---

### Task 1: Define shared scope, visual identity, and Top 15 response contracts

**Files:**
- Create: `backend/app/scope.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_scope.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Produces `ComparisonScope(season_from: int | None, season_to: int | None, team: str | None)`.
- Produces `filter_frame(frame: pd.DataFrame, scope: ComparisonScope, *, kind: Literal["player", "team"]) -> pd.DataFrame`.
- Produces Pydantic `VisualIdentity`, `TeamContext`, `FilterOptionsResponse`, `AppliedScope`, `MetricGroups`, and `RankedMatch` models.
- Changes both comparison response models to expose `matches`, `scope`, and a compatibility `match` field.

- [ ] **Step 1: Write scope tests before the implementation**

```python
# backend/tests/test_scope.py
import pandas as pd
import pytest

from app.scope import ComparisonScope, ScopeValidationError, filter_frame


def player_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"profile_id": "a:1997", "season": "1997", "team_codes": "CHI|WAS"},
            {"profile_id": "b:1998", "season": "1998", "team_codes": "LAL"},
            {"profile_id": "c:2001", "season": "2001", "team_codes": "CHI"},
        ]
    )


def test_player_scope_is_inclusive_and_matches_any_affiliation() -> None:
    filtered = filter_frame(
        player_frame(),
        ComparisonScope(season_from=1997, season_to=1998, team="CHI"),
        kind="player",
    )
    assert filtered["profile_id"].tolist() == ["a:1997"]


def test_team_scope_rejects_team_filter() -> None:
    with pytest.raises(ScopeValidationError, match="only available for player"):
        filter_frame(player_frame(), ComparisonScope(None, None, "CHI"), kind="team")


def test_scope_rejects_reversed_range() -> None:
    with pytest.raises(ScopeValidationError, match="must not exceed"):
        ComparisonScope(season_from=2000, season_to=1999, team=None)
```

- [ ] **Step 2: Run the new tests and confirm they fail because `app.scope` is absent**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_scope.py -q`

Expected: collection failure naming `app.scope`.

- [ ] **Step 3: Implement a pure scope module**

```python
# backend/app/scope.py
from dataclasses import dataclass
from typing import Literal
import re

import pandas as pd


class ScopeValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ComparisonScope:
    season_from: int | None = None
    season_to: int | None = None
    team: str | None = None

    def __post_init__(self) -> None:
        if self.season_from is not None and self.season_to is not None and self.season_from > self.season_to:
            raise ScopeValidationError("The first season must not exceed the last season.")
        if self.team is not None:
            object.__setattr__(self, "team", self.team.upper())


def filter_frame(frame: pd.DataFrame, scope: ComparisonScope, *, kind: Literal["player", "team"]) -> pd.DataFrame:
    if kind == "team" and scope.team:
        raise ScopeValidationError("Team filtering is only available for player comparisons.")
    seasons = frame["season"].astype("string").str.extract(r"^(\d{4})", expand=False)
    mask = pd.Series(True, index=frame.index)
    if scope.season_from is not None:
        mask &= seasons.astype("Int64") >= scope.season_from
    if scope.season_to is not None:
        mask &= seasons.astype("Int64") <= scope.season_to
    if scope.team:
        escaped = re.escape(scope.team)
        mask &= frame["team_codes"].astype("string").str.contains(
            rf"(?:^|\|){escaped}(?:\||$)", regex=True, na=False
        )
    return frame.loc[mask].copy()
```

- [ ] **Step 4: Define the public Pydantic models**

Add the following types in `backend/app/schemas.py`; make all collections use `Field(default_factory=list)` where a default is required.

```python
class VisualIdentity(BaseModel):
    kind: Literal["player", "team"]
    nba_id: str | None = None
    image_url: str | None = None


class TeamContext(BaseModel):
    code: str
    name: str


class ProfileResponse(BaseModel):
    id: str
    name: str
    season: str
    teams: list[TeamContext] = Field(default_factory=list)
    visual: VisualIdentity


class MetricGroups(BaseModel):
    basic: list[RadarMetric]
    advanced: list[RadarMetric]


class RankedMatch(BaseModel):
    profile: ProfileResponse
    similarity_score: float = Field(ge=0, le=100)
    power_ranking: PowerRanking
    metrics: MetricGroups


class AppliedScope(BaseModel):
    season_from: int | None = None
    season_to: int | None = None
    team: str | None = None
    eligible_count: int = Field(ge=0)
```

Change player and team comparison responses to contain `selected`, `match`, `matches`, `scope`, and `features_used`; player/team responses no longer own divergent `radar`/`metrics` top-level fields.

- [ ] **Step 5: Run scope and existing schema-dependent API tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_scope.py tests/test_api.py -q`

Expected: scope tests pass; API tests may now fail only where they still assert the superseded response shape.

- [ ] **Step 6: Update API fixture assertions to the new typed fields**

Replace one-match assertions with `comparison["matches"][0]`, verify `comparison["match"] == comparison["matches"][0]`, and assert `comparison["scope"]["eligible_count"] >= 1`. Do not remove the pre-existing basic radar test until Task 4 moves it to `metrics.basic`.

- [ ] **Step 7: Run the focused backend suite and commit the contract slice**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_scope.py tests/test_api.py -q`

Commit:

```powershell
git add backend/app/scope.py backend/app/schemas.py backend/tests/test_scope.py backend/tests/test_api.py
git commit -m "feat: define scoped top-match API contracts"
```

### Task 2: Add safe optional NBA identity lookup and CDN URL formation

**Files:**
- Create: `backend/app/identity.py`
- Create: `backend/tests/test_identity.py`
- Modify: `backend/app/catalog.py`

**Interfaces:**
- Produces `VisualIdentityRecord(kind: Literal["player", "team"], nba_id: str)`.
- Produces `LocalIdentityIndex(database_path: Path).resolve(kind: str, name: str) -> VisualIdentityRecord | None`.
- Produces `image_url_for(identity: VisualIdentityRecord) -> str`.
- Never opens a database for writing and returns `None` for unavailable, missing, or ambiguous identity matches.

- [ ] **Step 1: Write identity tests with a temporary SQLite index**

```python
# backend/tests/test_identity.py
import sqlite3

from app.identity import LocalIdentityIndex, image_url_for


def seed(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE player (id INTEGER, full_name TEXT);
            CREATE TABLE team (id INTEGER, full_name TEXT);
            INSERT INTO player VALUES (2544, 'LeBron James'), (999, 'Duplicate Name'), (998, 'Duplicate Name');
            INSERT INTO team VALUES (1610612747, 'Los Angeles Lakers');
            """
        )


def test_exact_player_lookup_returns_official_headshot_url(tmp_path) -> None:
    path = tmp_path / "identity.sqlite"
    seed(path)
    identity = LocalIdentityIndex(path).resolve("player", "LeBron James")
    assert identity is not None
    assert identity.nba_id == "2544"
    assert image_url_for(identity).endswith("/2544.png")


def test_ambiguous_or_missing_identity_returns_none(tmp_path) -> None:
    path = tmp_path / "identity.sqlite"
    seed(path)
    index = LocalIdentityIndex(path)
    assert index.resolve("player", "Duplicate Name") is None
    assert index.resolve("team", "Missing Team") is None
```

- [ ] **Step 2: Run the test to verify it fails before the index exists**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_identity.py -q`

Expected: collection failure naming `app.identity`.

- [ ] **Step 3: Implement the isolated read-only index**

```python
# backend/app/identity.py
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Literal


IdentityKind = Literal["player", "team"]


@dataclass(frozen=True)
class VisualIdentityRecord:
    kind: IdentityKind
    nba_id: str


class LocalIdentityIndex:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def resolve(self, kind: IdentityKind, name: str) -> VisualIdentityRecord | None:
        if not self.database_path.is_file():
            return None
        table = "player" if kind == "player" else "team"
        try:
            uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as connection:
                rows = connection.execute(
                    f"SELECT id FROM {table} WHERE lower(full_name) = lower(?)", (name,)
                ).fetchall()
        except sqlite3.Error:
            return None
        ids = {str(row[0]) for row in rows if row[0] is not None}
        if len(ids) != 1:
            return None
        return VisualIdentityRecord(kind=kind, nba_id=ids.pop())


def image_url_for(identity: VisualIdentityRecord) -> str:
    if identity.kind == "player":
        return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{identity.nba_id}.png"
    return f"https://cdn.nba.com/logos/nba/{identity.nba_id}/primary/L/logo.svg"
```

Use `DatasetCatalog._read_only_connection()` only where an already-inspected catalog supplies a compatible identity table. Otherwise the static `player`/`team` table names above are allowed exclusively inside this optional identity module and query no untrusted identifier.

- [ ] **Step 4: Add a cache keyed by `DatasetCatalog.source_signature()` and database metadata**

Expose `identity_signature()` from `DatasetCatalog`, returning a tuple containing the optional database path, byte size, and modification timestamp when the SQLite file exists. Use that signature in an `@lru_cache` factory in `identity.py` so request handling does not reopen SQLite for every avatar.

- [ ] **Step 5: Run the identity tests and the catalog suite**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_identity.py tests/test_catalog.py -q`

Expected: all tests pass and no test writes to SQLite after setup.

- [ ] **Step 6: Commit the optional identity slice**

```powershell
git add backend/app/identity.py backend/app/catalog.py backend/tests/test_identity.py
git commit -m "feat: resolve optional NBA visual identities safely"
```

### Task 3: Preserve historical player affiliation and team labels in the resolver

**Files:**
- Modify: `backend/app/resolver.py`
- Modify: `backend/tests/test_historical_csv_resolver.py`
- Modify: `backend/tests/test_resolver.py`

**Interfaces:**
- Player frames contain `team_codes` and `team_names` before feature columns.
- Team frames contain `team_codes` and `team_names` with their own verified display context.
- `ResolvedSeasonFrame` exposes no user-facing Pydantic data; it keeps a stable DataFrame boundary.

- [ ] **Step 1: Extend the historical fixture with team abbreviation data and traded-player rows**

Add `Team Abbrev.csv` to `build_historical_csv_source()` and create a multi-team test fixture with non-total and total rows:

```python
write_csv(
    directory / "Team Abbrev.csv",
    [
        {"season": 2023, "lg": "NBA", "team": "Aurora Comets", "abbreviation": "AUR", "playoffs": 0},
        {"season": 2023, "lg": "NBA", "team": "Harbor Pilots", "abbreviation": "HBR", "playoffs": 0},
    ],
)


def test_historical_total_row_keeps_all_verified_affiliations(tmp_path) -> None:
    # Build matching totals/advanced/per-game rows for player "switch01" with AUR, HBR, and TOT entries.
    frame = SchemaResolver(catalog).resolve_player_seasons().frame
    player = frame.set_index("profile_id").loc["switch01:2023"]
    assert player["team_codes"] == "AUR|HBR"
    assert player["team_names"] == "Aurora Comets|Harbor Pilots"
```

- [ ] **Step 2: Run the resolver test to confirm affiliation columns are absent**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_historical_csv_resolver.py -q`

Expected: the new assertion fails with a missing `team_codes` column.

- [ ] **Step 3: Load and join the verified abbreviation catalog**

In `SchemaResolver`, add `_historical_team_labels()` that reads `Team Abbrev.csv`, filters NBA/BAA rows, coerces `season` and `abbreviation` to string, drops duplicate `(season, abbreviation)` values stably, and returns `season`, `team_code`, `team_name`. Do not infer team aliases from the team summary data.

- [ ] **Step 4: Carry affiliations through player-row collapse**

Before discarding individual rows, construct affiliations by grouping the non-`TOT` source rows on `(season, lg, player_id)`. Build sorted unique code and label values joined by `|`. Merge that table into total rows and single/multi-team aggregate rows. A one-team profile receives the same single code/label; a total profile receives the union from its source teammates. Keep statistical totals and weighted advanced calculations unchanged.

Return player-frame columns in this order:

```python
[
    "profile_id", "player_id", "season", "name", "team_codes", "team_names",
    *PLAYER_BASE_METRICS, *PLAYER_ADVANCED_METRICS,
]
```

- [ ] **Step 5: Populate fallback SQLite affiliations only when the source relation verifies them**

For the schema-adaptive SQLite resolver, detect a catalog-confirmed `team_id`/`team_name` mapping on the chosen player season relation. If present, aggregate verified names/codes into the same two columns. If absent, add empty strings for both fields so team filtering can be explicitly disabled by API metadata rather than incorrectly matching all players.

- [ ] **Step 6: Add team-frame display context and run resolver tests**

Return `team_codes=team_id` and `team_names=name` in historical team frames. Add equivalent fields for schema-adaptive team frames. Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_historical_csv_resolver.py tests/test_resolver.py -q
```

Expected: historical and SQLite fixture normalizations pass, including total-row affiliation behavior.

- [ ] **Step 7: Commit resolver enrichment**

```powershell
git add backend/app/resolver.py backend/tests/test_historical_csv_resolver.py backend/tests/test_resolver.py
git commit -m "feat: preserve season team affiliations"
```

### Task 4: Refactor the pure similarity engine for scoped Top 15 results

**Files:**
- Modify: `backend/app/similarity.py`
- Modify: `backend/tests/test_similarity.py`

**Interfaces:**
- `SimilarityEngine.compare(..., scope: ComparisonScope, kind: Literal["player", "team"], limit: int = 15) -> ComparisonResult`.
- `ComparisonResult.matches` is an ordered tuple of `RankedComparison` objects.
- Each ranked object exposes `profile`, `similarity_score`, `rank`, `tier`, `basic_metrics`, and `advanced_metrics`.
- `ComparisonResult.eligible_count` represents complete, scope-matching alternatives before the limit is applied.

- [ ] **Step 1: Write failure tests for scope, deterministic Top 15, and metric groups**

```python
def test_similarity_returns_at_most_fifteen_scope_eligible_matches() -> None:
    frame = many_player_rows(18)
    result = SimilarityEngine().compare(
        frame,
        selected_profile_id="selected:2000",
        base_features=("points",),
        advanced_features=("bpm",),
        scope=ComparisonScope(season_from=1995, season_to=2005, team="CHI"),
        kind="player",
    )
    assert len(result.matches) == 15
    assert [match.rank for match in result.matches] == list(range(1, 16))
    assert all("CHI" in match.profile.team_codes for match in result.matches)
    assert result.eligible_count >= 15
    assert result.matches[0].basic_metrics[0].metric == "points"
    assert result.matches[0].advanced_metrics[0].metric == "bpm"


def test_similarity_reports_no_eligible_alternative_after_scope() -> None:
    with pytest.raises(ComparisonError, match="No eligible historical alternatives"):
        SimilarityEngine().compare(
            player_frame(), selected_profile_id="7:2022-23",
            base_features=PLAYER_BASE_METRICS, advanced_features=(),
            scope=ComparisonScope(season_from=1900, season_to=1901, team=None), kind="player",
        )
```

- [ ] **Step 2: Run the focused test and confirm the old engine does not accept scope**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_similarity.py -q`

Expected: failure citing the unsupported `scope` keyword argument.

- [ ] **Step 3: Introduce ranked result dataclasses**

```python
@dataclass(frozen=True)
class MetricGroups:
    basic: tuple[RadarPoint, ...]
    advanced: tuple[RadarPoint, ...]


@dataclass(frozen=True)
class RankedComparison:
    profile: SeasonProfile
    similarity_score: float
    rank: int
    tier: str
    metrics: MetricGroups


@dataclass(frozen=True)
class ComparisonResult:
    selected: SeasonProfile
    matches: tuple[RankedComparison, ...]
    eligible_count: int
    features_used: tuple[str, ...]
```

Extend `SeasonProfile` with `team_codes`, `team_names`, and optional `visual` identity data. Keep it independent from FastAPI/Pydantic classes.

- [ ] **Step 4: Implement candidate-only filtering and stable scoring**

Use `filter_frame(frame.drop(selected_index), scope, kind=kind)` before complete-feature filtering. Build the scaler on eligible candidate values only, transform selected values using that fitted scaler, calculate cosine similarities, and create a DataFrame holding `profile_id`, raw score, and original source order. Sort with:

```python
ranking = ranking.sort_values(
    ["similarity", "profile_id"], ascending=[False, True], kind="stable"
).head(limit)
```

Map the cosine values with `round((similarity + 1) * 50, 1)`. Preserve the existing zero-norm handling, applying it after selected and candidate norms are known. Raise `ComparisonError("No eligible historical alternatives remain for the selected filters.")` when no complete candidate remains.

- [ ] **Step 5: Generate metric groups for every retained match**

Generate basic points from `usable_base` and advanced points from `usable_advanced`. Compute min/max domains from `pd.concat([selected.to_frame().T, complete_candidates])` so the selected profile remains representable at 0–100 even when it falls outside the candidate range. Reuse those domains for every Top 15 item. Each point retains selected raw/normalized data and only changes the active match raw/normalized values.

- [ ] **Step 6: Preserve historical missing-metric behavior and run all engine tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_similarity.py -q`

Expected: old pre-three-point test now asserts unavailable fields are absent from both the feature list and every metric group.

- [ ] **Step 7: Commit the engine slice**

```powershell
git add backend/app/similarity.py backend/tests/test_similarity.py
git commit -m "feat: rank scoped top NBA similarities"
```

### Task 5: Expose filter options, scoped search, and rich compare responses

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_resolver_cache.py`
- Create: `backend/tests/test_filters_api.py`

**Interfaces:**
- `GET /api/players/filters` returns player seasons, team options, and availability.
- `GET /api/teams/filters` returns team seasons.
- Search and compare routes accept the scope query parameters defined by Task 1.
- `_comparison_payload` maps a `ComparisonResult` into rich Pydantic response models without recomputing metrics.

- [ ] **Step 1: Add endpoint-level tests before routing changes**

```python
# backend/tests/test_filters_api.py
def test_player_filter_options_and_scoped_compare(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))

    options = asyncio.run(get("/api/players/filters"))
    assert options.status_code == 200
    assert options.json()["seasons"] == [1997, 2015, 2022]

    response = asyncio.run(get("/api/players/7:2022-23/compare?season_from=2015&season_to=2016"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["season_from"] == 2015
    assert payload["matches"][0]["profile"]["id"] == "11:2015-16"


def test_team_compare_rejects_player_team_filter(tmp_path, monkeypatch) -> None:
    # Seed the same fixture and assert 422 plus a user-displayable detail.
    response = asyncio.run(get("/api/teams/1:2022-23/compare?team=AUR"))
    assert response.status_code == 422
    assert "only available for player" in response.json()["detail"]
```

- [ ] **Step 2: Run the new endpoint test and verify the routes are absent**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_filters_api.py -q`

Expected: a 404 for `/filters` and missing scope fields in compare payloads.

- [ ] **Step 3: Add a shared FastAPI scope dependency**

In `main.py`, define `scope_from_query()` with `Query(ge=1946, le=2100)` parameters and construct `ComparisonScope`. Catch `ScopeValidationError` and return HTTP 422. Call this dependency from both search routes and both compare routes. Reject a team parameter for team routes before resolving the full comparison frame.

- [ ] **Step 4: Implement metadata from the cached frame**

Build filter options from `_season_frame(kind).frame`:

```python
def _season_options(frame: pd.DataFrame) -> list[int]:
    values = frame["season"].astype("string").str.extract(r"^(\d{4})", expand=False)
    return sorted({int(value) for value in values.dropna()})
```

For player team options, split `team_codes` and `team_names` in paired positions, de-duplicate by code, and sort by label. Set `team_filter_available=False` when all codes are empty. Cache metadata under the same catalog source signature as the resolved frame.

- [ ] **Step 5: Enrich search rows and comparison profiles**

Apply scope to search frames, construct `TeamContext` from the paired frame strings, and obtain the optional `VisualIdentity` from the cached `LocalIdentityIndex`. Add a focused helper:

```python
def _profile_payload(row: pd.Series, kind: EntityKind) -> ProfileResponse:
    return ProfileResponse(
        id=str(row["profile_id"]), name=str(row["name"]), season=str(row["season"]),
        teams=_team_contexts(row), visual=_visual_payload(row, kind),
    )
```

Use it for selected, `match`, every `matches` item, and search results so media and team context cannot diverge between views.

- [ ] **Step 6: Wire the Top 15 engine to comparison routes**

Pass `scope` and `kind` to `SimilarityEngine.compare`. Convert `result.matches` to `RankedMatch` objects. Set `match` to the first mapped element. Pass `AppliedScope` with the canonical scope and `result.eligible_count`. Preserve 404 for an unknown profile, return 422 for invalid scopes/no eligible candidates, and retain 503 for unresolved data sources.

- [ ] **Step 7: Prove cache behavior and run the backend API suite**

Add a cache test that calls filter metadata, search, and compare against one source signature and asserts resolver construction occurs once per kind. Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_filters_api.py tests/test_resolver_cache.py -q
```

- [ ] **Step 8: Commit the HTTP API slice**

```powershell
git add backend/app/main.py backend/app/schemas.py backend/tests/test_api.py backend/tests/test_filters_api.py backend/tests/test_resolver_cache.py
git commit -m "feat: expose scoped top-match comparison API"
```

### Task 6: Establish frontend response types, remote-image safety, and entity media

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/next.config.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/entity-avatar.tsx`
- Create: `frontend/src/components/entity-avatar.test.tsx`

**Interfaces:**
- Produces TypeScript `ComparisonScope`, `FilterOptions`, `VisualIdentity`, `RankedMatch`, and rich `Comparison` types that mirror the API models.
- Produces `loadFilterOptions(kind, signal)` and scope-aware `searchHistory`/`loadComparison` functions.
- Produces `EntityAvatar({ entity, size, decorative? })` with fixed geometry and fallback behavior.

- [ ] **Step 1: Install the Radix tooltip primitive and add the allowed image host**

Run: `cd frontend; npm install @radix-ui/react-tooltip`

Create `frontend/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [{ protocol: "https", hostname: "cdn.nba.com" }],
  },
};

export default nextConfig;
```

- [ ] **Step 2: Write API serialization tests**

```typescript
it("serializes only populated scope fields", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [] }))));
  await searchHistory("player", "james", { season_from: 2003, season_to: 2013, team: "MIA" });
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/players/search?q=james&season_from=2003&season_to=2013&team=MIA"),
    expect.any(Object),
  );
});
```

- [ ] **Step 3: Update TypeScript models and fetch functions**

Use `URLSearchParams` instead of handwritten query concatenation. Define a single `scopeParams(scope)` helper that omits null/undefined values. Ensure `loadComparison` has the signature:

```typescript
export function loadComparison(
  kind: EntityKind,
  profileId: string,
  scope: ComparisonScope,
  signal?: AbortSignal,
): Promise<Comparison>;
```

Add `loadFilterOptions(kind, signal)` targeting `/api/${kind}s/filters`.

- [ ] **Step 4: Write avatar skeleton/fallback tests**

```typescript
it("uses a stable monogram after a remote image error", () => {
  render(<EntityAvatar entity={playerWithImage} size="medium" />);
  fireEvent.error(screen.getByRole("img", { name: /LeBron James/i }));
  expect(screen.getByText("LJ")).toBeInTheDocument();
});

it("renders a decorative fallback without an accessible duplicate label", () => {
  render(<EntityAvatar entity={teamWithoutImage} size="small" decorative />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
```

- [ ] **Step 5: Implement `EntityAvatar` with fixed-size states**

Use `next/image` only when `entity.visual.image_url` exists. Hold `loading` and `failed` local state. Render a fixed CSS frame from the first paint, a skeleton pseudo-element while loading, and a deterministic two-character monogram after failure or no URL. Use `<Image fill sizes="...">` inside a positioned media container; do not let intrinsic dimensions set layout.

- [ ] **Step 6: Run client unit checks and commit the foundation**

Run:

```powershell
cd frontend
npm run test -- --run src/components/entity-avatar.test.tsx src/lib/api.test.ts
npm run typecheck
```

Commit:

```powershell
git add frontend/package.json frontend/package-lock.json frontend/next.config.ts frontend/src/lib frontend/src/components/entity-avatar.tsx frontend/src/components/entity-avatar.test.tsx
git commit -m "feat: add typed comparison data and entity media"
```

### Task 7: Build accessible range controls and a selectable Top 15 leaderboard

**Files:**
- Create: `frontend/src/components/comparison-filters.tsx`
- Create: `frontend/src/components/comparison-filters.test.tsx`
- Create: `frontend/src/components/similarity-leaderboard.tsx`
- Create: `frontend/src/components/similarity-leaderboard.test.tsx`
- Modify: `frontend/src/components/search-experience.tsx`
- Modify: `frontend/src/components/search-experience.test.tsx`
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- `ComparisonFilters({ kind, value, options, onChange, disabled })` emits one immutable `ComparisonScope`.
- `SimilarityLeaderboard({ selectedId, matches, onSelect })` calls `onSelect(profileId)` from pointer or keyboard activation.
- `SearchExperience` owns scope, filter metadata, request cancellation, comparison result, and active match ID.

- [ ] **Step 1: Write filter interaction tests**

```typescript
it("emits an inclusive player scope with a team", () => {
  const onChange = vi.fn();
  render(<ComparisonFilters kind="player" value={{}} options={playerOptions} onChange={onChange} disabled={false} />);
  fireEvent.change(screen.getByLabelText("From season"), { target: { value: "2003" } });
  fireEvent.change(screen.getByLabelText("To season"), { target: { value: "2013" } });
  fireEvent.change(screen.getByLabelText("Team"), { target: { value: "MIA" } });
  expect(onChange).toHaveBeenLastCalledWith({ season_from: 2003, season_to: 2013, team: "MIA" });
});

it("does not render a team selector for team comparisons", () => {
  render(<ComparisonFilters kind="team" value={{}} options={teamOptions} onChange={vi.fn()} disabled={false} />);
  expect(screen.queryByLabelText("Team")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Implement native, labelled range controls**

Render From season and To season `<select>` controls, each with an empty `All history` value. In player mode render Team only when `team_filter_available` is true. Disable controls while initial filter options are loading. Convert selected DOM values to `number | undefined`; retain all other scope values when one field changes. Put controls in a labelled `fieldset` called `Comparison pool`.

- [ ] **Step 3: Write leaderboard interaction tests**

```typescript
it("marks the active row and changes it through keyboard activation", () => {
  const onSelect = vi.fn();
  render(<SimilarityLeaderboard selectedId="a" matches={matches} onSelect={onSelect} />);
  const second = screen.getByRole("button", { name: /2.*Beacon Wing.*91.2/i });
  fireEvent.keyDown(second, { key: "Enter" });
  expect(onSelect).toHaveBeenCalledWith("b");
  expect(screen.getByRole("button", { name: /1.*Aster Guard/i })).toHaveAttribute("aria-current", "true");
});
```

- [ ] **Step 4: Implement compact visual leaderboard rows**

Each semantic `<button>` contains rank, `EntityAvatar`, name, season/team context, tier, and score. Use `aria-current="true"` for the active match. Apply `data-active` for presentation; do not make a clickable `<div>`. Rows use CSS `transform: scale(0.97)` on `:active`, are keyboard-focusable by default, and have no entrance animation when focused by keyboard.

- [ ] **Step 5: Refactor `SearchExperience` state and effects**

Load options once whenever `kind` changes. Maintain `scope`, reset it to `{}` on kind switch, and clear a comparison only after the user changes scope. Pass scope into search and compare API calls. Keep the current 160ms search debounce and `AbortController`; add `scope` to its dependency list. When compare resolves, set `activeMatchId` to `comparison.matches[0].profile.id`.

Show filter-loading skeleton controls before options arrive, show a concise inline error if options fail, and include team/season/avatar context in autocomplete rows. Update test fixtures to return `visual`, `teams`, `matches`, and `scope` fields.

- [ ] **Step 6: Add motion-safe styles and run component tests**

Use transitions restricted to `transform` and `opacity`; apply background, border, and text color changes immediately. Build any skeleton shine with a pseudo-element whose animation changes only its `transform` and `opacity`. Add fine-pointer hover gating and a reduced-motion block that removes spatial transforms. Run:

```powershell
cd frontend
npm run test -- --run src/components/comparison-filters.test.tsx src/components/similarity-leaderboard.test.tsx src/components/search-experience.test.tsx
npm run lint
```

- [ ] **Step 7: Commit controls and leaderboard**

```powershell
git add frontend/src/components/comparison-filters.tsx frontend/src/components/comparison-filters.test.tsx frontend/src/components/similarity-leaderboard.tsx frontend/src/components/similarity-leaderboard.test.tsx frontend/src/components/search-experience.tsx frontend/src/components/search-experience.test.tsx frontend/src/app/globals.css
git commit -m "feat: filter comparison pools and browse top matches"
```

### Task 8: Replace the static result panel with dynamic metric-mode charts and intent-aware tooltips

**Files:**
- Create: `frontend/src/components/tooltip-intent.tsx`
- Create: `frontend/src/components/tooltip-intent.test.tsx`
- Create: `frontend/src/components/comparison-charts.tsx`
- Create: `frontend/src/components/comparison-charts.test.tsx`
- Modify: `frontend/src/components/comparison-dashboard.tsx`
- Delete: `frontend/src/components/player-radar.tsx`
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- `TooltipIntentProvider` exposes `requestOpen(key, open)` and gives the first hover a 500ms delay, then sibling hovers immediate eligibility.
- `ComparisonCharts({ kind, selected, activeMatch, matches })` derives all Recharts data locally.
- `ComparisonDashboard({ comparison, kind, activeMatchId, onActiveMatchChange })` composes header, leaderboard, metric toggle, and charts.

- [ ] **Step 1: Write fake-timer tooltip intent tests**

```typescript
it("delays the first tooltip and opens the next graph mark immediately", () => {
  vi.useFakeTimers();
  render(<TooltipHarness />);
  fireEvent.pointerEnter(screen.getByRole("button", { name: "First mark" }));
  expect(screen.queryByText("First detail")).not.toBeInTheDocument();
  vi.advanceTimersByTime(500);
  expect(screen.getByText("First detail")).toBeInTheDocument();
  fireEvent.pointerEnter(screen.getByRole("button", { name: "Second mark" }));
  expect(screen.getByText("Second detail")).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement shared intent state**

Store only the active key, its timer, and a short `instantUntil` timestamp in context. Clear timers on unmount and pointer leave. Use `@radix-ui/react-tooltip` with `delayDuration={500}` and `skipDelayDuration={0}` for non-chart help controls. For Recharts, render a controlled custom tooltip driven by chart mouse events and the same provider state.

- [ ] **Step 3: Write chart derivation tests**

```typescript
it("switches a player from 12 basic radar dimensions to advanced dimensions", () => {
  render(<ComparisonCharts kind="player" selected={selected} activeMatch={match} matches={matches} />);
  expect(screen.getByLabelText(/radar.*12 primary/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
  expect(screen.getByLabelText(/radar.*advanced/i)).toBeInTheDocument();
  expect(screen.getByText("BPM")).toBeInTheDocument();
});

it("updates the active name in every chart when the active match changes", () => {
  const { rerender } = render(<ComparisonCharts kind="team" selected={selected} activeMatch={first} matches={[first, second]} />);
  rerender(<ComparisonCharts kind="team" selected={selected} activeMatch={second} matches={[first, second]} />);
  expect(screen.getAllByText(second.profile.name).length).toBeGreaterThan(0);
});
```

- [ ] **Step 4: Implement the metric toggle and reusable chart derivations**

Expose `Basic` and `Advanced` as an accessible pressed-button group. Derive the active metric group from `activeMatch.metrics[mode]`. Use this source for all charts; do not separately select metric columns in the client.

Build:

- a `RadarChart` with selected and active datasets, `isAnimationActive`, `animationDuration={220}`, and an ease-out animation;
- a `ScatterChart` containing selected plus all matches, using Points/Assists or BPM/Win Shares for players and eFG%/turnover rate or Net Rating/Pace for teams;
- a horizontal `BarChart` of active-match deltas over every current metric-group point.

When a requested scatter pair is unavailable in a historic profile, render a compact, descriptive unavailable state instead of an invalid point.

- [ ] **Step 5: Refactor the dashboard around active local match state**

Find `activeMatch` with `comparison.matches.find`; fall back to `comparison.matches[0]`. Put `SimilarityLeaderboard` beside/above the chart panel according to responsive breakpoints. Header image, score, tier, and all chart labels derive from this same object. Keep no duplicate `useState` for metric values.

Wrap dashboard reconfiguration in a short `motion.section` transition using full `transform` strings and opacity. Use `AnimatePresence` only for occasional result swaps, not keyboard-selected rows. Remove `player-radar.tsx` after every import has moved to `comparison-charts.tsx`.

- [ ] **Step 6: Add chart and reduced-motion styles**

Give each chart card a fixed min-height. Use CSS transform/opacity transitions for control/list chrome and let Recharts own the one required SVG path interpolation. In `prefers-reduced-motion`, set Recharts animation duration to zero and remove spatial card transforms while keeping score and color states readable without transition.

- [ ] **Step 7: Run chart and dashboard checks, then commit**

Run:

```powershell
cd frontend
npm run test -- --run src/components/tooltip-intent.test.tsx src/components/comparison-charts.test.tsx src/components/search-experience.test.tsx
npm run lint
npm run typecheck
```

Commit:

```powershell
git add frontend/src/components/tooltip-intent.tsx frontend/src/components/tooltip-intent.test.tsx frontend/src/components/comparison-charts.tsx frontend/src/components/comparison-charts.test.tsx frontend/src/components/comparison-dashboard.tsx frontend/src/components/player-radar.tsx frontend/src/app/globals.css
git commit -m "feat: visualize active NBA similarities dynamically"
```

### Task 9: Run real-data integration checks and document the upgraded local setup

**Files:**
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: `backend/tests/test_health.py`
- Modify: `frontend/src/app/page.test.tsx`

**Interfaces:**
- README documents `NBA_HISTORICAL_DATA_PATH`, optional `NBA_DATABASE_PATH` identity lookup, and the current endpoints.
- `.gitignore` ignores `data/` as well as standalone SQLite files.
- Health output distinguishes the CSV comparison source from optional identity availability without exposing local paths beyond the intended status response.

- [ ] **Step 1: Write a health contract test for the CSV source and optional identity state**

```python
def test_health_reports_csv_source_and_optional_identity(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(build_historical_csv_source(tmp_path)))
    monkeypatch.setenv("NBA_DATABASE_PATH", str(tmp_path / "missing.sqlite"))
    response = asyncio.run(get("/api/health"))
    assert response.status_code == 200
    assert response.json()["source_format"] == "historical_csv"
    assert response.json()["identity_available"] is False
```

- [ ] **Step 2: Implement and test the health additions**

Add `source_format` and `identity_available` to the health payload. Do not add a database write, upload endpoint, or remote asset fetch to health.

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_health.py -q`

- [ ] **Step 3: Update local-run and data-source documentation**

Replace the obsolete README statement that only a root `nba.sqlite` can enable comparisons. Document:

```powershell
$env:NBA_HISTORICAL_DATA_PATH = 'C:\path\to\data\historical'
$env:NBA_DATABASE_PATH = 'C:\Users\birbu\OneDrive\Documentos\nba.sqlite' # optional visual identity only
```

List all four filter/search endpoints, comparison scope parameters, dataset attribution, fallback-media behavior, and the external-brand-asset licensing note. Add `data/` and `*.sqlite` to `.gitignore` without removing existing ignore rules.

- [ ] **Step 4: Execute all static verification gates**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run test -- --run
npm run lint
npm run typecheck
npm run build
```

Expected: every command exits zero.

- [ ] **Step 5: Perform real-data API smoke checks**

Start FastAPI with the CSV data path and optional identity database path. Confirm all responses below are HTTP 200 and validate the stated behavior:

```text
GET /api/players/filters
GET /api/players/search?q=jokic&season_from=2018&season_to=2026
GET /api/players/jokic-id:2023/compare?season_from=1990&season_to=2026
GET /api/teams/search?q=boston&season_from=2000&season_to=2026
GET /api/teams/BOS:2023/compare?season_from=1980&season_to=2026
```

Use IDs returned by the preceding search endpoint rather than inventing `jokic-id:2023`. Verify Top 15 length, range adherence, a valid optional media URL/fallback field, active chart data, and no source writes.

- [ ] **Step 6: Perform browser verification in the running local app**

Verify these user paths with browser automation:

1. Search a player, set an exact season range, select a result, and confirm the leaderboard has up to 15 rows.
2. Select another leaderboard row and confirm score/header/radar/scatter/bars update without a new compare request.
3. Change to Advanced and confirm advanced labels appear with a smooth, short chart update.
4. Switch to Teams and confirm the Team select disappears while From/To controls remain.
5. Force an image load error in component testing and confirm the rendered card dimensions do not move.

- [ ] **Step 7: Review the complete diff, commit, and report verification**

```powershell
git diff --check
git status --short
git add README.md .gitignore backend/tests/test_health.py frontend/src/app/page.test.tsx
git commit -m "docs: document filterable similarity discovery"
```

Report the exact test/build commands and results, the live smoke examples used, and any unrelated user changes intentionally left unstaged.

## Plan Self-Review

- Spec coverage is mapped: range/team filtering (Tasks 1, 3, 5, 7), Top 15 scoring (Task 4), assets (Tasks 2 and 6), dynamic visuals/tooltips/motion (Task 8), and documentation/real verification (Task 9).
- Contract names remain consistent: `ComparisonScope`, `RankedMatch`, `MetricGroups`, `EntityAvatar`, `ComparisonFilters`, and `SimilarityLeaderboard` are defined before consumers rely on them.
- The plan adds no authentication, live statistics API, source-data mutation, or image archive beyond the approved scope.
