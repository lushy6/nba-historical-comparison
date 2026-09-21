# NBA Similarity Discovery Upgrade — Design Specification

## Objective

Upgrade Season Echoes from a single-neighbor lookup into an interactive NBA
similarity discovery workspace. A visitor can constrain the eligible historical
pool by an inclusive season range and, for player comparisons, team affiliation;
inspect the top 15 statistically nearest seasons; then switch the active match
and its basic or advanced visual profile without another network request.

The upgrade preserves the project's local-first statistical source. It continues
to use the verified historical CSV catalog for season data and uses the local
`nba.sqlite` only as an optional, read-only identity index for NBA CDN imagery.
No scraped statistics, synthetic values, or local copies of third-party imagery
are introduced.

## Confirmed Product Decisions

- Season filtering is an **inclusive range**: `season_from` through `season_to`.
  Leaving either bound empty means unbounded history; matching bounds expresses
  an exact-season filter.
- Player filtering also accepts one team code. A player who appeared for that
  franchise during a traded season remains eligible, even if their final season
  total is represented by a `TOT` source row.
- Team filtering is season-range only.
- The compare endpoint returns at most 15 ranked alternatives in one response.
  Switching between them must not trigger another comparison request.
- Basic and advanced metric modes change the visualizations, not the honesty of
  the score: similarity still uses every recorded, compatible feature for the
  selected profile.

## Current-State Findings

The current historical CSV source resolves 25,753 player seasons and 1,724 team
seasons. The player source contains a `team` code, but the existing normalized
frame emits only `profile_id`, player identity, season, name, and metrics. That
loss of affiliation makes a reliable team filter impossible today.

The supplied SQLite database at `C:\Users\birbu\OneDrive\Documentos\nba.sqlite`
contains identity tables (`player`, `team`) with official numeric NBA IDs, but
its 16 tables do not supply the historical season-level metrics required for
comparison. It is therefore an optional identity source, not a replacement for
the historical CSV season source.

## Architecture

```text
Next.js App Router
    |-- search + inclusive scope controls
    |-- Top 15 leaderboard / active-match state
    |-- reusable radar, scatter, and delta-bar visualizations
    `-- entity media + skeleton/fallback components
                         |
                         v
FastAPI
    |-- filter option endpoints
    |-- typed search and comparison routes
    |-- cached normalized season frames
    |-- candidate-pool filter service
    |-- Top 15 cosine-similarity engine
    `-- optional read-only SQLite identity lookup
                         |
                         v
Historical CSV statistics + optional local nba.sqlite identity tables
```

`SchemaResolver` remains the only layer allowed to interpret source data. It
will enrich its application-owned frames with affiliation and optional visual
identity before `SimilarityEngine` receives them. `SimilarityEngine` remains a
pure DataFrame calculation layer: it filters a supplied candidate frame,
standardizes compatible features, ranks alternatives, and creates metric points
for each ranked result. FastAPI owns query validation and response shaping. The
client owns active leaderboard selection and presentation only.

## Data Contract

### Normalized player profiles

Player frames gain the following non-metric fields:

- `team_codes`: an ordered, immutable affiliation collection expressed as a
  pipe-delimited internal string while in Pandas, serialized as a string array
  in HTTP models.
- `primary_team_code`: a single-team display value when a season has one
  affiliation; `null` for a multi-team total.
- `team_names`: full historical team labels resolved from `Team Abbrev.csv`.
- `nba_person_id`: optional exact-name identity match from local SQLite.

For a player with a `TOT` row, the metric values continue to come from the total
row. Its affiliation fields come from the non-total rows sharing the player,
league, and season. For a player with multiple non-total rows but no total row,
aggregation keeps the existing statistical semantics and produces the union of
those affiliations. This makes filtering accurate without duplicating one
player-season into multiple similarity candidates.

The existing schema-adaptive SQLite resolver will populate these fields where a
team association can be verified. Where its source relation does not expose one,
the player team filter is reported unavailable rather than guessed.

### Normalized team profiles

Team profiles retain their abbreviation as `team_id` and gain optional
`nba_team_id` from an exact identity match. Historic team names that cannot be
matched remain fully comparable and use a fallback visual treatment.

### Comparison scope

```python
@dataclass(frozen=True)
class ComparisonScope:
    season_from: int | None
    season_to: int | None
    team: str | None  # player comparisons only; canonical upper-case code
```

Validation rules:

- each supplied season is a four-digit value represented by the source catalog;
- `season_from <= season_to` when both are provided;
- player `team` is a known canonical code in the resolved catalog;
- team comparison rejects a `team` parameter;
- the selected profile is excluded only after being identified, so it is always
  displayed even if a later scope adjustment no longer includes it;
- a scope with no eligible alternative produces HTTP 422 with a precise,
  user-displayable message.

## HTTP API Contract

### Filter metadata

```text
GET /api/players/filters
GET /api/teams/filters
```

Player responses provide sorted seasons, a `team_filter_available` flag, and
team options with canonical code and label. Team responses provide sorted
seasons. The client must use these options rather than hard-code modern teams or
eras.

### Search

```text
GET /api/players/search?q=&season_from=&season_to=&team=
GET /api/teams/search?q=&season_from=&season_to=
```

The result keeps the current short autocomplete list and adds team context plus
an optional visual identity object:

```json
{
  "id": "jamesle01:2024",
  "name": "LeBron James",
  "season": "2024",
  "kind": "player",
  "teams": [{"code": "LAL", "name": "Los Angeles Lakers"}],
  "visual": {"kind": "player", "nba_id": "2544", "image_url": "..."}
}
```

### Comparison

```text
GET /api/players/{profile_id}/compare?season_from=&season_to=&team=
GET /api/teams/{profile_id}/compare?season_from=&season_to=
```

Both comparison responses contain:

```text
selected: ProfileResponse
match: RankedMatch                 # same object as matches[0], retained during migration
matches: RankedMatch[]             # one to fifteen, rank ordered
scope: AppliedComparisonScope      # canonical filters + eligible_count
features_used: string[]            # actual score inputs for selected season
```

Each `RankedMatch` contains rank, profile identity, similarity score, tier, and
two metric groups. A metric group is a list of `RadarMetric`-compatible points
with selected and match raw values plus shared normalized values. Returning the
metric groups for every ranked match allows immediate local selection without
recalculating or fetching.

`basic_metrics` maps to the 12 player counting metrics or the team Four Factors.
`advanced_metrics` maps to player efficiency/value metrics or team ratings and
pace. Missing historic measures remain omitted. Metric labels and domains come
from the backend, so the frontend never invents a number or scale.

## Similarity Algorithm

1. Resolve the selected row from the full cached season frame.
2. Select the base and advanced features actually recorded for that profile.
3. Apply the requested scope to candidate rows, then drop profiles missing any
   selected feature. Do not replace missing data with zero.
4. De-duplicate by profile ID, exclude the selected profile, and require at
   least one remaining candidate.
5. Fit `StandardScaler` on the eligible complete comparison set and calculate
   cosine similarity from the selected profile to each candidate.
6. Convert cosine similarity to a bounded 0–100 score, descending-sort with a
   stable profile-ID tie-breaker, and retain the first 15.
7. Assign tiers using the existing thresholds: 90+ Mirror, 84+ Strong echo,
   75+ Shared shape, otherwise Distant cousin.
8. Generate basic and advanced metric points using the same eligible set for
   normalization. The score and every graph therefore describe the same pool.

The `rank` is the displayed placement among retained Top 15 matches, while
`eligible_count` reveals the size of the scope after complete-feature checks.

## Visual Identity and Asset Policy

`EntityAvatar` is a focused frontend component shared by autocomplete rows,
comparison headers, and leaderboard items. It has three states:

1. a fixed-size shimmer skeleton while the image is resolving;
2. an optimized remote NBA CDN headshot or team logo when the optional exact
   local identity mapping is present;
3. a deterministic monogram plus color treatment on missing or failed media.

No image is bundled, scraped, or used if the identity match is ambiguous. The
Next image configuration permits only the explicit NBA CDN host. The visual
identity lookup is read-only and cached by catalog signature. Any public or
commercial deployment must independently validate NBA trademark and media-use
rights; this project only requests remote imagery at runtime.

## Client Experience

### Search and scope controls

`SearchExperience` gains persisted scope state per entity kind. Player mode
shows From season, To season, and Team selects; team mode shows only the season
range. The controls are accessible native/select-style controls with clear
labels, an All history default, and a visible summary of the applied pool.

Changing scope cancels obsolete autocomplete requests, clears an incompatible
active comparison, and uses an `AbortController` for every fetch. Selecting a
search result makes one compare request for the fully hydrated Top 15 payload.

### Comparison workspace

`ComparisonDashboard` becomes a composition root for:

- a selected-vs-active header with entity images and score treatment;
- a selectable Top 15 `SimilarityLeaderboard` with rank, tier, season/team
  context, and keyboard-operable rows;
- `MetricModeToggle` for Basic and Advanced views;
- a shared `ComparisonCharts` section containing radar, scatter, and delta-bar
  views.

The radar displays selected and active profiles. The scatter displays the
selected profile plus all Top 15 candidates and emphasizes the active row.
Basic player scatter axes are Points and Assists; advanced player axes are BPM
and Win Shares. Basic team axes are eFG% and turnover percentage; advanced team
axes are Net Rating and Pace. The delta bars compare selected and active values
across the active metric group.

Changing the active leaderboard row or metric mode updates local state only.
Recharts interpolates radar geometry over a short duration; all surrounding UI
motion uses only `transform` and `opacity`.

### Interaction, motion, and accessibility

- List, dashboard, and card entrance use 180–240ms strong ease-out transforms
  and opacity, with a 30–60ms non-blocking stagger for initially rendered rows.
- Pressable controls, leaderboard rows, and cards use `scale(0.97)` on press.
- Framer Motion layout transitions are reserved for interrupted dashboard
  reconfiguration and use a short, low-bounce spring. Repeated keyboard actions
  do not animate.
- Hover effects are limited to fine-pointer devices. Reduced-motion users retain
  opacity feedback but do not receive spatial movement.
- A shared tooltip-intent provider delays the first graph tooltip by 500ms;
  while it is active or immediately after it closes, sibling chart marks open
  their tooltips without delay. Recharts receives a custom accessible tooltip,
  and Radix Tooltip uses matching `delayDuration`/`skipDelayDuration` for
  non-chart controls.
- Skeleton frames reserve the final image dimensions to prevent layout shift;
  avatars include descriptive alt text or are hidden when decorative.

## File Boundaries

```text
backend/app/
  resolver.py                 # affiliation + optional identity enrichment
  similarity.py               # scope-filtered Top 15 pure calculations
  schemas.py                  # scope, visual identity, match-list response models
  main.py                     # query validation, filters routes, response mapping
  identity.py                 # read-only exact-match identity lookup and CDN URL formation
backend/tests/
  test_historical_csv_resolver.py
  test_resolver.py
  test_similarity.py
  test_api.py
  test_identity.py

frontend/src/
  lib/types.ts                # rich API models
  lib/api.ts                  # query serialization and typed fetches
  components/entity-avatar.tsx
  components/comparison-filters.tsx
  components/similarity-leaderboard.tsx
  components/comparison-charts.tsx
  components/tooltip-intent.tsx
  components/search-experience.tsx
  components/comparison-dashboard.tsx
  app/globals.css
```

The existing `player-radar.tsx` will either become part of
`comparison-charts.tsx` or be retired after the shared replacement has tests.
Components do not receive raw DataFrames or construct metric labels; their
inputs are typed HTTP models.

## Verification Strategy

### Backend

- Resolver fixtures prove one-team, `TOT`, and multi-team player affiliation
  behavior, historical team-name mapping, optional identity mapping, and no
  identity result on ambiguous names.
- Similarity tests prove inclusive range boundaries, team membership matching,
  selected-profile exclusion, stable Top 15 ordering, fewer-than-15 pools,
  no-result validation, bounded scores, and missing pre-three-point-era metrics.
- Endpoint tests prove every filter contract, metadata response, Top 15 schema,
  primary-match compatibility, and no database writes.

### Frontend

- Component tests cover scope serialization, cancel-safe search behavior,
  keyboard selection, active Top 15 selection, Basic/Advanced data switching,
  image fallback, and accessible labels.
- Tooltip tests use fake timers to prove first-hover delay and instant sibling
  tooltip behavior.

### End-to-end verification

- Run the full backend pytest suite.
- Run frontend Vitest, ESLint, TypeScript checking, and production build.
- Start FastAPI and Next.js against the real historical CSV source; verify a
  player comparison, team comparison, an exact-year range, a multi-year range,
  a player team filter, Top 15 selection, and both metric modes in the browser.
- Confirm network requests contain the expected canonical scope and that no
  image failure changes card geometry.

## Out of Scope

- Accounts, saved comparisons, sharing, public deployment, or changes to the
  underlying Kaggle data.
- A paid or live statistical API.
- Hand-maintained historic photo/logo archives or guessed identity mappings.
- Ranking player quality independently of similarity; the existing tier remains
  a similarity tier, not a claim of all-time basketball value.

## Success Criteria

1. Users can apply inclusive From/To season ranges, and player users can apply
   a real team filter, before selecting a historical comparable.
2. Player and team requests return ordered Top 15 results, each with a valid
   0–100 score, tier, and honest metric data.
3. Selecting a Top 15 row changes every visualization without another API call.
4. Basic and Advanced modes work for player and team radar, scatter, and delta
   bar charts, including partial historic profiles.
5. Entity imagery is polished when safely identifiable and always has a stable,
   accessible fallback.
6. UI interaction remains keyboard-accessible, reduced-motion-aware, free of
   layout shifts, and constrained to fast transform/opacity motion outside chart
   path interpolation.
7. Existing and new backend/frontend verification gates pass.
