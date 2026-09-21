import csv
from pathlib import Path

import pytest

from app.catalog import DatasetCatalog
from app.resolver import SchemaResolver


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_historical_csv_source(directory: Path) -> None:
    directory.mkdir()
    write_csv(
        directory / "Player Totals.csv",
        [
            {
                "season": 2023,
                "lg": "NBA",
                "player": "Aster Guard",
                "player_id": "aster01",
                "team": "AUR",
                "fg": 480,
                "fga": 1000,
                "x3p": 190,
                "x3pa": 500,
                "ft": 240,
                "fta": 290,
                "trb": 260,
                "ast": 310,
                "stl": 95,
                "blk": 35,
                "tov": 140,
                "pts": 1390,
            },
            {
                "season": 2015,
                "lg": "NBA",
                "player": "Beacon Wing",
                "player_id": "beacon01",
                "team": "HBR",
                "fg": 465,
                "fga": 970,
                "x3p": 175,
                "x3pa": 460,
                "ft": 222,
                "fta": 270,
                "trb": 280,
                "ast": 301,
                "stl": 91,
                "blk": 31,
                "tov": 134,
                "pts": 1327,
            },
        ],
    )
    write_csv(
        directory / "Advanced.csv",
        [
            {
                "season": 2023,
                "lg": "NBA",
                "player": "Aster Guard",
                "player_id": "aster01",
                "team": "AUR",
                "mp": 2400,
                "per": 22.5,
                "ts_percent": 0.595,
                "usg_percent": 23.5,
                "ws": 8.2,
                "bpm": 2.3,
                "vorp": 1.2,
            },
            {
                "season": 2015,
                "lg": "NBA",
                "player": "Beacon Wing",
                "player_id": "beacon01",
                "team": "HBR",
                "mp": 2300,
                "per": 21.3,
                "ts_percent": 0.59,
                "usg_percent": 23.2,
                "ws": 7.6,
                "bpm": 2.1,
                "vorp": 1.0,
            },
        ],
    )
    write_csv(
        directory / "Player Per Game.csv",
        [
            {
                "season": 2023,
                "lg": "NBA",
                "player": "Aster Guard",
                "player_id": "aster01",
                "team": "AUR",
                "e_fg_percent": 0.575,
            },
            {
                "season": 2015,
                "lg": "NBA",
                "player": "Beacon Wing",
                "player_id": "beacon01",
                "team": "HBR",
                "e_fg_percent": 0.57,
            },
        ],
    )
    write_csv(
        directory / "Team Summaries.csv",
        [
            {
                "season": 2023,
                "lg": "NBA",
                "team": "Aurora Comets",
                "abbreviation": "AUR",
                "playoffs": 0,
                "e_fg_percent": 0.572,
                "tov_percent": 12.3,
                "orb_percent": 27.4,
                "f_tr": 0.201,
                "o_rtg": 116.2,
                "d_rtg": 110.4,
                "n_rtg": 5.8,
                "pace": 99.1,
            },
            {
                "season": 2015,
                "lg": "NBA",
                "team": "Harbor Pilots",
                "abbreviation": "HBR",
                "playoffs": 0,
                "e_fg_percent": 0.568,
                "tov_percent": 12.6,
                "orb_percent": 26.9,
                "f_tr": 0.198,
                "o_rtg": 115.4,
                "d_rtg": 111.0,
                "n_rtg": 4.4,
                "pace": 98.8,
            },
        ],
    )


def test_resolver_normalizes_verified_historical_csv_season_data(tmp_path: Path) -> None:
    source_directory = tmp_path / "historical"
    build_historical_csv_source(source_directory)
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=source_directory)

    player_seasons = SchemaResolver(catalog).resolve_player_seasons()
    team_seasons = SchemaResolver(catalog).resolve_team_seasons()

    player = player_seasons.frame.set_index("profile_id").loc["aster01:2023"]
    assert player_seasons.source_table == "historical_csv:player_season"
    assert player["three_point_attempts"] == 500
    assert player["efg_pct"] == 0.575
    assert player["per"] == 22.5
    assert player["win_shares"] == 8.2

    team = team_seasons.frame.set_index("profile_id").loc["AUR:2023"]
    assert team_seasons.source_table == "historical_csv:team_season"
    assert team["effective_field_goal_pct"] == 0.572
    assert team["turnover_pct"] == pytest.approx(0.123)
    assert team["net_rating"] == 5.8
