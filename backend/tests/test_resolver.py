import sqlite3
from pathlib import Path

from app.catalog import DatasetCatalog
from app.resolver import PLAYER_BASE_METRICS, SchemaResolver


def build_player_database(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Players (
              PERSON_ID INTEGER PRIMARY KEY,
              PLAYER_NAME TEXT NOT NULL
            );
            CREATE TABLE Player_Stats (
              PLAYER_ID INTEGER NOT NULL,
              SEASON_ID TEXT NOT NULL,
              FG3A REAL, FG3M REAL, FGA REAL, FGM REAL, PTS REAL,
              BLK REAL, TOV REAL, STL REAL, AST REAL, REB REAL, FTA REAL, FTM REAL,
              TS_PCT REAL, EFG_PCT REAL, USG_PCT REAL, BPM REAL, VORP REAL
            );

            INSERT INTO Players VALUES (7, 'Aster Guard');
            INSERT INTO Players VALUES (11, 'Beacon Wing');
            INSERT INTO Players VALUES (23, 'Cinder Center');

            INSERT INTO Player_Stats VALUES
              (7, '2022-23', 500, 190, 1000, 480, 1320, 35, 140, 95, 310, 260, 290, 240, .595, .575, .235, 2.3, 1.2),
              (11, '2022-23', 460, 175, 970, 465, 1270, 31, 134, 91, 301, 280, 270, 222, .590, .570, .232, 2.1, 1.0),
              (23, '2022-23', 45, 13, 850, 500, 1190, 160, 120, 58, 165, 780, 350, 255, .608, .582, .220, 2.8, 1.6);
            """
        )


def test_resolver_normalizes_a_catalog_confirmed_player_season_source(tmp_path: Path) -> None:
    database_path = tmp_path / "nba.sqlite"
    build_player_database(database_path)

    resolved = SchemaResolver(DatasetCatalog(database_path)).resolve_player_seasons()

    assert resolved.source_table == "Player_Stats"
    assert resolved.base_features == PLAYER_BASE_METRICS
    assert resolved.advanced_features == ("ts_pct", "efg_pct", "usg_pct", "bpm", "vorp")
    profile = resolved.frame.set_index("profile_id").loc["7:2022-23"]
    assert profile["name"] == "Aster Guard"
    assert profile["three_point_attempts"] == 500
    assert profile["turnovers"] == 140


def test_resolver_does_not_turn_missing_advanced_statistics_into_zeroes(tmp_path: Path) -> None:
    database_path = tmp_path / "nba.sqlite"
    build_player_database(database_path)

    resolved = SchemaResolver(DatasetCatalog(database_path)).resolve_player_seasons()

    assert "per" not in resolved.frame.columns
    assert "per" not in resolved.advanced_features
