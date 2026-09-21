import sqlite3
from pathlib import Path

from app.catalog import DatasetCatalog


def test_catalog_reports_a_missing_dataset_without_connecting(tmp_path: Path) -> None:
    report = DatasetCatalog(tmp_path / "nba.sqlite").inspect()

    assert report.status == "dataset_missing"
    assert report.tables == ()
    assert report.message == "Place nba.sqlite in the project root to enable comparisons."


def test_catalog_discovers_tables_and_columns_from_sqlite_metadata(tmp_path: Path) -> None:
    database_path = tmp_path / "nba.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Players (
              PERSON_ID INTEGER PRIMARY KEY,
              PLAYER_NAME TEXT NOT NULL,
              FROM_YEAR INTEGER
            );
            CREATE TABLE Team_Stats (
              TEAM_ID INTEGER NOT NULL,
              SEASON_ID TEXT NOT NULL,
              PTS REAL
            );
            """
        )

    report = DatasetCatalog(database_path).inspect()

    assert report.status == "dataset_ready"
    assert [table.name for table in report.tables] == ["Players", "Team_Stats"]
    assert report.tables[0].columns == ("PERSON_ID", "PLAYER_NAME", "FROM_YEAR")
    assert report.tables[1].columns == ("TEAM_ID", "SEASON_ID", "PTS")


def test_catalog_signature_prefers_the_configured_historical_csv_source(tmp_path: Path) -> None:
    historical_directory = tmp_path / "historical"
    historical_directory.mkdir()
    (historical_directory / "Player Totals.csv").write_text("season,player\n2023,Aster Guard\n")

    signature = DatasetCatalog(
        tmp_path / "missing.sqlite", historical_data_path=historical_directory
    ).source_signature()

    assert signature[0] == "historical_csv"
    assert signature[1] == str(historical_directory.resolve())
