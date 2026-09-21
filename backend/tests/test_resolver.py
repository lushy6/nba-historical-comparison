import sqlite3
from pathlib import Path

import pytest

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
    assert profile["team_codes"] == ""
    assert profile["team_names"] == ""


def test_resolver_does_not_turn_missing_advanced_statistics_into_zeroes(tmp_path: Path) -> None:
    database_path = tmp_path / "nba.sqlite"
    build_player_database(database_path)

    resolved = SchemaResolver(DatasetCatalog(database_path)).resolve_player_seasons()

    assert "per" not in resolved.frame.columns
    assert "per" not in resolved.advanced_features


def test_sqlite_player_affiliations_aggregate_verified_source_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "nba.sqlite"
    build_player_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            ALTER TABLE Player_Stats ADD COLUMN TEAM_ID TEXT;
            ALTER TABLE Player_Stats ADD COLUMN TEAM_NAME TEXT;
            UPDATE Player_Stats SET TEAM_ID = 'HBR', TEAM_NAME = 'Harbor Pilots';
            INSERT INTO Player_Stats SELECT * FROM Player_Stats WHERE PLAYER_ID = 7;
            UPDATE Player_Stats SET TEAM_ID = 'AUR', TEAM_NAME = 'Aurora Comets'
              WHERE rowid = (SELECT max(rowid) FROM Player_Stats);
            """
        )

    frame = SchemaResolver(DatasetCatalog(database_path)).resolve_player_seasons().frame

    assert len(frame) == 3
    profile = frame.set_index("profile_id").loc["7:2022-23"]
    assert profile["team_codes"] == "AUR|HBR"
    assert profile["team_names"] == "Aurora Comets|Harbor Pilots"
    assert profile["points"] == 2640
    assert profile["bpm"] == 2.3
    assert list(frame.columns[:6]) == [
        "profile_id", "player_id", "season", "name", "team_codes", "team_names",
    ]


@pytest.mark.parametrize("columns", [
    ("TEAM_ID",), ("TEAM_NAME",), ("NAME",), ("ID", "TEAM_NAME"), ("TEAM_ID", "NAME"),
])
def test_sqlite_partial_or_ambiguous_team_mapping_has_empty_affiliation(tmp_path, columns) -> None:
    database_path = tmp_path / "nba.sqlite"
    build_player_database(database_path)
    with sqlite3.connect(database_path) as connection:
        for column in columns:
            connection.execute(f'ALTER TABLE Player_Stats ADD COLUMN "{column}" TEXT')
            connection.execute(f'UPDATE Player_Stats SET "{column}" = ?', ("Unverified",))

    frame = SchemaResolver(DatasetCatalog(database_path)).resolve_player_seasons().frame

    assert frame["team_codes"].eq("").all()
    assert frame["team_names"].eq("").all()


def test_sqlite_team_frames_include_verified_display_context(tmp_path) -> None:
    database_path = tmp_path / "nba.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Team_Stats (
              TEAM_ID TEXT, TEAM_NAME TEXT, SEASON_ID TEXT,
              EFG_PCT REAL, TOV_PCT REAL, OREB_PCT REAL, FTA_RATE REAL,
              OFF_RATING REAL, DEF_RATING REAL, NET_RATING REAL, PACE REAL
            );
            INSERT INTO Team_Stats VALUES
              ('AUR', 'Aurora Comets', '2022-23', .572, .123, .274, .201, 116.2, 110.4, 5.8, 99.1);
            """
        )

    frame = SchemaResolver(DatasetCatalog(database_path)).resolve_team_seasons().frame

    profile = frame.set_index("profile_id").loc["AUR:2022-23"]
    assert profile["team_codes"] == "AUR"
    assert profile["team_names"] == "Aurora Comets"
