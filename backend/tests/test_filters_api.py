"""Tests for filter-metadata endpoints and scoped compare parameters."""

import asyncio
import sqlite3
from pathlib import Path

import httpx
import pytest

from app.main import app


def seed_database(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Players (PERSON_ID INTEGER PRIMARY KEY, PLAYER_NAME TEXT NOT NULL);
            CREATE TABLE Player_Stats (
              PLAYER_ID INTEGER, SEASON_ID TEXT,
              FG3A REAL, FG3M REAL, FGA REAL, FGM REAL, PTS REAL, BLK REAL,
              TOV REAL, STL REAL, AST REAL, REB REAL, FTA REAL, FTM REAL,
              TS_PCT REAL, EFG_PCT REAL, USG_PCT REAL, BPM REAL, VORP REAL
            );
            CREATE TABLE Teams (TEAM_ID INTEGER PRIMARY KEY, TEAM_NAME TEXT NOT NULL);
            CREATE TABLE Team_Stats (
              TEAM_ID INTEGER, SEASON_ID TEXT,
              EFG_PCT REAL, TOV_PCT REAL, OREB_PCT REAL, FTA_RATE REAL,
              OFF_RATING REAL, DEF_RATING REAL, NET_RATING REAL, PACE REAL
            );

            INSERT INTO Players VALUES (7, 'Aster Guard'), (11, 'Beacon Wing'), (23, 'Cinder Center');
            INSERT INTO Player_Stats VALUES
              (7, '2022-23', 500,190,1000,480,1320,35,140,95,310,260,290,240,.595,.575,.235,2.3,1.2),
              (11,'2015-16', 490,184,990,474,1300,33,137,93,305,278,280,230,.591,.571,.232,2.1,1.0),
              (23,'1997-98', 45,13,850,500,1190,160,120,58,165,780,350,255,.608,.582,.220,2.8,1.6);

            INSERT INTO Teams VALUES (1, 'Aurora Comets'), (2, 'Harbor Pilots'), (3, 'Canyon Stars');
            INSERT INTO Team_Stats VALUES
              (1,'2022-23',.572,.123,.274,.201,116.2,110.4,5.8,99.1),
              (2,'2015-16',.568,.126,.269,.198,115.4,111.0,4.4,98.8),
              (3,'1997-98',.502,.152,.218,.171,101.2,114.3,-13.1,91.5);
            """
        )


async def get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.fixture()
def db_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))
    import app.main as main_module
    main_module._cached_season_frame.cache_clear()
    return database_path


def test_player_filter_options_returns_sorted_seasons(db_env: Path) -> None:
    response = asyncio.run(get("/api/players/filters"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["seasons"] == [1997, 2015, 2022]
    assert "team_filter_available" in payload
    assert "teams" in payload


def test_team_filter_options_returns_sorted_seasons(db_env: Path) -> None:
    response = asyncio.run(get("/api/teams/filters"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["seasons"] == [1997, 2015, 2022]


def test_player_scoped_compare_respects_season_from_and_to(db_env: Path) -> None:
    response = asyncio.run(get("/api/players/7:2022-23/compare?season_from=2015&season_to=2016"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["season_from"] == 2015
    assert payload["scope"]["season_to"] == 2016
    assert payload["matches"][0]["profile"]["id"] == "11:2015-16"


def test_player_scoped_search_respects_season_from(db_env: Path) -> None:
    response = asyncio.run(get("/api/players/search?q=aster&season_from=2020"))
    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


def test_team_compare_rejects_team_filter_parameter(db_env: Path) -> None:
    response = asyncio.run(get("/api/teams/1:2022-23/compare?team=AUR"))
    assert response.status_code == 422
    assert "only available for player" in response.json()["detail"]


def test_compare_rejects_reversed_season_range(db_env: Path) -> None:
    response = asyncio.run(get("/api/players/7:2022-23/compare?season_from=2020&season_to=2010"))
    assert response.status_code == 422


def test_compare_returns_top15_ranked_matches(db_env: Path) -> None:
    response = asyncio.run(get("/api/players/7:2022-23/compare"))
    assert response.status_code == 200
    payload = response.json()
    assert 1 <= len(payload["matches"]) <= 15
    assert payload["match"] == payload["matches"][0]
    first_match = payload["matches"][0]
    assert "profile" in first_match
    assert "similarity_score" in first_match
    assert "power_ranking" in first_match
    assert "metrics" in first_match
    assert "basic" in first_match["metrics"]
    assert "advanced" in first_match["metrics"]
    assert "features_used" in payload
    assert "scope" in payload
    assert payload["scope"]["eligible_count"] >= 1
