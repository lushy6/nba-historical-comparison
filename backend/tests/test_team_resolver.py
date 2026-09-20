import sqlite3
from pathlib import Path

from app.catalog import DatasetCatalog
from app.resolver import TEAM_COMPARISON_METRICS, SchemaResolver


def test_resolver_normalizes_team_four_factors_and_ratings(tmp_path: Path) -> None:
    database_path = tmp_path / "nba.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Teams (TEAM_ID INTEGER PRIMARY KEY, TEAM_NAME TEXT NOT NULL);
            CREATE TABLE Team_Stats (
              TEAM_ID INTEGER NOT NULL,
              SEASON_ID TEXT NOT NULL,
              EFG_PCT REAL, TOV_PCT REAL, OREB_PCT REAL, FTA_RATE REAL,
              OFF_RATING REAL, DEF_RATING REAL, NET_RATING REAL, PACE REAL
            );
            INSERT INTO Teams VALUES (1, 'Aurora Comets'), (2, 'Harbor Pilots');
            INSERT INTO Team_Stats VALUES
              (1, '2022-23', .572, .123, .274, .201, 116.2, 110.4, 5.8, 99.1),
              (2, '2022-23', .568, .126, .269, .198, 115.4, 111.0, 4.4, 98.8);
            """
        )

    resolved = SchemaResolver(DatasetCatalog(database_path)).resolve_team_seasons()

    assert resolved.source_table == "Team_Stats"
    assert resolved.base_features == TEAM_COMPARISON_METRICS
    profile = resolved.frame.set_index("profile_id").loc["1:2022-23"]
    assert profile["name"] == "Aurora Comets"
    assert profile["effective_field_goal_pct"] == .572
    assert profile["net_rating"] == 5.8
