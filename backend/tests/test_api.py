import asyncio
import sqlite3
from pathlib import Path

import httpx

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


def test_player_search_and_comparison_return_typed_visual_data(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))

    search_response = asyncio.run(get("/api/players/search?q=aster"))
    comparison_response = asyncio.run(get("/api/players/7:2022-23/compare"))

    assert search_response.status_code == 200
    assert search_response.json()["items"] == [
        {"id": "7:2022-23", "name": "Aster Guard", "season": "2022-23", "kind": "player"}
    ]
    comparison = comparison_response.json()
    assert comparison_response.status_code == 200
    assert comparison["match"]["id"] == "11:2015-16"
    assert 0 <= comparison["similarity_score"] <= 100
    assert comparison["power_ranking"]["tier"] == "Mirror"
    assert len(comparison["radar"]) == 12


def test_team_search_and_comparison_return_four_factor_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))

    search_response = asyncio.run(get("/api/teams/search?q=harbor"))
    comparison_response = asyncio.run(get("/api/teams/1:2022-23/compare"))

    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["name"] == "Harbor Pilots"
    comparison = comparison_response.json()
    assert comparison_response.status_code == 200
    assert comparison["match"]["id"] == "2:2015-16"
    assert comparison["metrics"][0]["metric"] == "effective_field_goal_pct"
