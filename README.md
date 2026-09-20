# NBA Historical Comparison

A local-first NBA historical-comparison application. The FastAPI backend discovers the actual schema in the Wyatt Walsh Kaggle `nba.sqlite` file at runtime, normalizes compatible player and team season data, and returns statistically comparable historical matches. The Next.js frontend presents those matches through an accessible, animated comparison dashboard.

## Status

The application is ready to run, but the licensed Kaggle export is deliberately not included. Place `nba.sqlite` in this repository root before starting the backend. At runtime, the service reads `sqlite_master` and `PRAGMA table_info` to discover the actual tables and columns, then only enables comparison types for compatible season-level data. It does not assume a table layout or fabricate data.

## Run locally

In one terminal, start the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In another terminal, start the web application:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend talks to `http://localhost:8000` by default. Override it with `NEXT_PUBLIC_API_URL` when the API runs elsewhere.

## Verify the dataset

With the API running, visit `http://localhost:8000/api/health`. A successful report returns `status: "dataset_ready"` together with the discovered tables. If the database is missing or lacks a compatible player/team season table, it returns a precise explanation; search and comparison requests return the same guidance instead of placeholder results.

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

The project intentionally never downloads, embeds, or commits the Kaggle database.
