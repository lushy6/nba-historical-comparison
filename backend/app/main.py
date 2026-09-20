from fastapi import FastAPI

from app.catalog import DatasetCatalog


app = FastAPI(
    title="NBA Historical Comparison API",
    version="0.1.0",
    description="Schema-discovered comparisons for the local NBA SQLite dataset.",
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return DatasetCatalog.from_environment().inspect().to_payload()
