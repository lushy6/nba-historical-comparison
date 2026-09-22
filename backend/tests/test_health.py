import asyncio
import csv
from pathlib import Path

import httpx

from app.main import app


def build_historical_csv_source(tmp_path: Path) -> Path:
    """Create a minimal historical CSV source for testing."""
    historical_path = tmp_path / "historical"
    historical_path.mkdir()
    players_file = historical_path / "player_stats.csv"
    with players_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["season", "player", "team", "pts"])
        writer.writeheader()
        writer.writerow({"season": "2023", "player": "Test Player", "team": "BOS", "pts": "25"})
    return historical_path


def test_health_reports_when_the_optional_dataset_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))

    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dataset_missing"
    assert payload["database_path"] == "nba.sqlite"
    assert payload["tables"] == []
    assert "Place nba.sqlite" in payload["message"]
    # Task 9: health now exposes source_format and identity_available
    assert payload["identity_available"] is False
    assert payload["source_format"] in ("sqlite", "historical_csv")


def test_health_reports_csv_source_and_optional_identity(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(build_historical_csv_source(tmp_path)))
    monkeypatch.setenv("NBA_DATABASE_PATH", str(tmp_path / "missing.sqlite"))

    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_format"] == "historical_csv"
    assert payload["identity_available"] is False


def test_health_exposes_source_format_without_leaking_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(build_historical_csv_source(tmp_path)))
    monkeypatch.setenv("NBA_DATABASE_PATH", str(tmp_path / "missing.sqlite"))

    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_format"] == "historical_csv"
    assert payload["identity_available"] is False
    # Ensure no absolute local paths leak in the health response
    assert "C:\\" not in str(payload)
    assert "/home/" not in str(payload)
    assert tmp_path.name not in str(payload)
