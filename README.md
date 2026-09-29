# NBA Historical Comparison

A local-first NBA historical-comparison application. The FastAPI backend discovers and normalizes player and team season data from a verified historical CSV catalog, then returns up to 15 statistically ranked historical matches. The Next.js frontend presents those matches through a filterable, animated comparison dashboard with radar, delta-bar, and scatter charts.

## Status

The application is ready to run locally. You must supply the historical CSV catalog before starting the backend.

## Data sources

### Historical CSV catalog (required)

```powershell
$env:NBA_HISTORICAL_DATA_PATH = 'C:\path\to\data\historical'
```

The historical directory must contain season-level CSV files with verified NBA statistics from the [curated NBA/ABA/BAA historical dataset](https://github.com/cmuchina3/nba-stats-1947-present-curated). This is the primary comparison source and supports the full range of season filtering. The following files are required:

- `Player Totals.csv`
- `Advanced.csv`
- `Player Per Game.csv`
- `Team Summaries.csv`
- `Team Abbrev.csv`

### Optional - Visual identity index

```powershell
$env:NBA_DATABASE_PATH = 'C:\Users\birbu\OneDrive\Documentos\nba.sqlite'  # optional: used only for player/team avatar CDN URL resolution
```

When `NBA_DATABASE_PATH` points to a compatible SQLite file that contains `player` and `team` tables with `id`/`full_name` columns, the API resolves official NBA headshot and logo CDN URLs. Missing, ambiguous, or failed imagery falls back to a stable two-character monogram; the comparison data is never affected by identity availability.

The SQLite identity database is read-only and never written to.

## Run locally

In one terminal, start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Set the historical CSV data path, then:
uvicorn app.main:app --reload --port 8000
```

In another terminal, start the web application:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend talks to `http://localhost:8000` by default. Override it with `NEXT_PUBLIC_API_BASE_URL` when the API runs elsewhere.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Source availability, `source_format`, and `identity_available` |
| GET | `/api/players/filters` | Available seasons, teams, and `team_filter_available` flag |
| GET | `/api/teams/filters` | Available team seasons |
| GET | `/api/players/search?q=&season_from=&season_to=&team=` | Scoped player search |
| GET | `/api/teams/search?q=&season_from=&season_to=` | Scoped team search |
| GET | `/api/players/{id}/compare?season_from=&season_to=&team=&pool=` | Player similarity with Top-15 matches |
| GET | `/api/teams/{id}/compare?season_from=&season_to=&pool=` | Team similarity with Top-15 matches |

### Scope parameters

- `season_from` / `season_to`: Inclusive four-digit integer year bounds. Equal values select a single season. Leaving either bound empty means unbounded history. Team comparisons do not accept a `team` filter.
- `team`: Player comparison filter by team abbreviation code (e.g. `LAL`, `MIA`). Applies to player candidate pools only; a player who appeared for that franchise during a traded season remains eligible. Omit to compare across all teams.
- `pool` (compare routes only): Whether matches may include other seasons of the selected player or team. `all` (default) allows both, `others` excludes the selected entity, and `same` keeps only its other seasons. The pool narrows which profiles are ranked, not how they are scored: standardization and radar domains always come from the season/team scope, so a season receives the same score in every pool. An unknown value returns HTTP 422.

### Inclusive season ranges

Season bounds are inclusive. `season_from=2018&season_to=2026` includes all seasons from 2018 through 2026. The `season` field in player and team profiles is a four-digit source-season year extracted from the leading digits of the catalog season string.

### Player-only team filtering

Team filtering is available only for player comparisons. When a team code is supplied, the backend filters candidate player rows to those with a verified affiliation on any traded-player season within the scope. Team-comparison routes reject a `team` parameter with HTTP 422 and the detail `Team filtering is only available for player comparisons.`

### Top-15 response shape

All comparison responses include:

- `selected`: The chosen profile with visual identity and team context
- `match`: Same object as `matches[0]` (compatibility alias)
- `matches`: Up to 15 ranked alternatives, each containing `profile`, `similarity_score`, `power_ranking` (with `rank` and `tier`), and `metrics` (with `basic` and `advanced` arrays of `RadarMetric` points)
- `scope`: Applied bounds including `season_from`, `season_to`, `team`, `pool`, and `eligible_count`
- `features_used`: The base measures that determined the cosine similarity score

Each `RadarMetric` point contains `metric` (canonical key), `label` (display label), `selected_value`, `match_value`, `selected_normalized`, and `match_normalized`. Player scoring uses base measures recorded in every season of the selected scope. A player season missing an otherwise available base measure is excluded; an era-wide missing measure is omitted from that scope's scoring dimensions. Base measures omitted from scoring, and advanced measures, can still appear in the radar when both seasons recorded them. No missing value is filled with zero. The scaler uses the same scoped, base-complete population whichever player season is selected, so a pair scored in both directions gets the same score.

This scoring rule changed on 2026-09-29, and earlier similarity scores are not directly comparable. On the local 25,753-row historical player catalog, the full-history comparison for `arizatr01:2020` now uses six shared base measures and has 25,752 eligible alternatives; the prior method used 19 base and advanced measures and had 20,477. Counts depend on the local data snapshot and the selected scope.

### Team metrics

Team comparisons rank on eight basic measures from `Team Summaries.csv` (eFG%, TOV%, ORB%, FT rate, offensive/defensive/net rating, pace). Seven optional advanced measures — SRS, TS%, 3PA rate, and the defensive four factors — appear in the radar when both teams recorded them. Teams missing a required basic measure remain ineligible. On the local catalog, Atlanta's 2020 season now has 1,432 eligible alternatives using eight scoring measures, compared with 1,313 alternatives using 15 measures under the previous rule.

### Source format and identity health

`GET /api/health` returns:

- `source_format`: `"historical_csv"` when the CSV catalog is available, `"sqlite"` for the legacy database format, or `"dataset_missing"` when no source is found
- `identity_available`: `true` only when a compatible SQLite identity index exists and is readable; `false` otherwise

No absolute local file paths are exposed in the health response.

### Fallback media behavior and NBA CDN licensing

Avatar images are served from NBA CDN URLs (`https://cdn.nba.com`) when a verified local identity index is available. When image URLs are missing, unavailable, or fail to load, the UI renders a stable two-character monogram fallback that preserves card dimensions. CDN imagery requires an internet connection and may be subject to NBA brand asset licensing terms; this project only requests remote imagery at runtime and does not bundle, scrape, or cache NBA brand assets.

## Dataset attribution

This project uses the verified historical CSV catalog curated from public NBA/ABA/BAA statistics data:

- [https://github.com/cmuchina3/nba-stats-1947-present-curated](https://github.com/cmuchina3/nba-stats-1947-present-curated)
- [https://www.kaggle.com/sumitrodatta/nba-aba-baa-stats](https://www.kaggle.com/sumitrodatta/nba-aba-baa-stats)

## Quality checks

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run test -- --run
npm run lint
npm run typecheck
npm run build
```

The project intentionally never downloads, embeds, or commits the historical CSV data, SQLite database, or any NBA brand assets.
