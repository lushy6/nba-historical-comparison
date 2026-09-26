import csv
from pathlib import Path

import pandas as pd
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
        directory / "Team Abbrev.csv",
        [
            {"season": 2023, "lg": "NBA", "team": "Aurora Comets", "abbreviation": "AUR", "playoffs": 0},
            {"season": 2023, "lg": "NBA", "team": "Harbor Pilots", "abbreviation": "HBR", "playoffs": 0},
        ],
    )
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
    assert player["team_codes"] == "AUR"
    assert player["team_names"] == "Aurora Comets"

    team = team_seasons.frame.set_index("profile_id").loc["AUR:2023"]
    assert team_seasons.source_table == "historical_csv:team_season"
    assert team["effective_field_goal_pct"] == 0.572
    assert team["turnover_pct"] == pytest.approx(0.123)
    assert team["net_rating"] == 5.8
    assert team["team_codes"] == "AUR"
    assert team["team_names"] == "Aurora Comets"


def add_traded_player(directory: Path, *, include_total: bool) -> None:
    for filename in ("Player Totals.csv", "Advanced.csv", "Player Per Game.csv"):
        with (directory / filename).open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        teams = ("HBR", "AUR", "TOT") if include_total else ("HBR", "AUR")
        for team in teams:
            row = {**rows[0], "player_id": "switch01", "player": "Switch Guard", "team": team}
            if filename == "Advanced.csv":
                row.update(mp=100 if team == "HBR" else 300, per=10 if team == "HBR" else 30)
                row["bpm"] = ""
            rows.append(row)
        write_csv(directory / filename, rows)


@pytest.mark.parametrize("include_total", [True, False])
def test_historical_total_row_keeps_all_verified_affiliations(tmp_path, include_total) -> None:
    directory = tmp_path / "historical"
    build_historical_csv_source(directory)
    add_traded_player(directory, include_total=include_total)
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=directory)

    frame = SchemaResolver(catalog).resolve_player_seasons().frame

    assert len(frame) == 3
    assert frame["profile_id"].is_unique
    player = frame.set_index("profile_id").loc["switch01:2023"]
    assert player["team_codes"] == "AUR|HBR"
    assert player["team_names"] == "Aurora Comets|Harbor Pilots"
    assert player["points"] == (1390 if include_total else 2780)
    assert player["per"] == (30 if include_total else 25)
    assert player["win_shares"] == pytest.approx(8.2 if include_total else 16.4)
    assert pd.isna(player["bpm"])
    assert pd.isna(player["pace"])


def test_historical_labels_are_season_specific_verified_and_stably_deduplicated(tmp_path) -> None:
    directory = tmp_path / "historical"
    build_historical_csv_source(directory)
    write_csv(
        directory / "Team Abbrev.csv",
        [
            {"season": 2023, "lg": "ABA", "team": "Wrong League", "abbreviation": "AUR"},
            {"season": 2023, "lg": "NBA", "team": "Verified Comets", "abbreviation": "AUR"},
            {"season": 2023, "lg": "NBA", "team": "Duplicate Label", "abbreviation": "AUR"},
            {"season": 2014, "lg": "NBA", "team": "Wrong Season", "abbreviation": "HBR"},
        ],
    )
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=directory)

    frame = SchemaResolver(catalog).resolve_player_seasons().frame.set_index("profile_id")

    assert len(frame) == 2
    assert frame.loc["aster01:2023", "team_names"] == "Verified Comets"
    assert frame.loc["beacon01:2015", "team_codes"] == ""
    assert frame.loc["beacon01:2015", "team_names"] == ""


def test_historical_affiliations_exclude_unverified_aggregate_markers(tmp_path) -> None:
    directory = tmp_path / "historical"
    build_historical_csv_source(directory)
    add_traded_player(directory, include_total=True)
    for filename in ("Player Totals.csv", "Advanced.csv", "Player Per Game.csv"):
        with (directory / filename).open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        write_csv(directory / filename, [
            {**row, "team": "2TM"} if row["team"] == "TOT" else row for row in rows
        ])
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=directory)

    frame = SchemaResolver(catalog).resolve_player_seasons().frame

    assert len(frame) == 3
    player = frame.set_index("profile_id").loc["switch01:2023"]
    assert player["team_codes"] == "AUR|HBR"
    assert player["team_names"] == "Aurora Comets|Harbor Pilots"
    # Existing non-TOT aggregation is preserved; synthetic totals need a separate statistics fix.
    assert player["points"] == 4170
    assert player["per"] == pytest.approx(19000 / 700)


def test_historical_total_without_individual_rows_has_no_invented_affiliation(tmp_path) -> None:
    directory = tmp_path / "historical"
    build_historical_csv_source(directory)
    for filename in ("Player Totals.csv", "Advanced.csv", "Player Per Game.csv"):
        with (directory / filename).open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        write_csv(directory / filename, [{**row, "team": "TOT"} for row in rows])
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=directory)

    frame = SchemaResolver(catalog).resolve_player_seasons().frame

    assert len(frame) == 2
    assert frame["team_codes"].eq("").all()
    assert frame["team_names"].eq("").all()
    assert frame.set_index("profile_id").loc["aster01:2023", "points"] == 1390


def test_historical_baa_affiliation_uses_verified_labels(tmp_path) -> None:
    directory = tmp_path / "historical"
    build_historical_csv_source(directory)
    for filename in ("Player Totals.csv", "Advanced.csv", "Player Per Game.csv", "Team Abbrev.csv"):
        with (directory / filename).open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        write_csv(directory / filename, [{**row, "lg": "BAA"} for row in rows])
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=directory)

    frame = SchemaResolver(catalog).resolve_player_seasons().frame

    assert frame.set_index("profile_id").loc["aster01:2023", "team_names"] == "Aurora Comets"


TEAM_ADVANCED_SOURCE = {
    "AUR": {"srs": 5.4, "ts_percent": 0.598, "x3p_ar": 0.421, "opp_e_fg_percent": 0.531,
            "opp_tov_percent": 13.2, "drb_percent": 76.1, "opp_ft_fga": 0.188},
    "HBR": {"srs": 4.1, "ts_percent": 0.590, "x3p_ar": 0.384, "opp_e_fg_percent": 0.529,
            "opp_tov_percent": 13.8, "drb_percent": 75.4, "opp_ft_fga": 0.191},
}


def _add_team_advanced_columns(source_directory: Path) -> None:
    path = source_directory / "Team Summaries.csv"
    frame = pd.read_csv(path)
    for column in TEAM_ADVANCED_SOURCE["AUR"]:
        frame[column] = frame["abbreviation"].map(lambda code: TEAM_ADVANCED_SOURCE[code][column])
    frame.to_csv(path, index=False)


def test_team_seasons_expose_advanced_metrics_from_team_summaries(tmp_path: Path) -> None:
    source_directory = tmp_path / "historical"
    build_historical_csv_source(source_directory)
    _add_team_advanced_columns(source_directory)
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=source_directory)

    team_seasons = SchemaResolver(catalog).resolve_team_seasons()

    assert team_seasons.advanced_features == (
        "simple_rating",
        "true_shooting_pct",
        "three_point_attempt_rate",
        "opp_effective_field_goal_pct",
        "opp_turnover_pct",
        "defensive_rebound_pct",
        "opp_free_throw_rate",
    )
    team = team_seasons.frame.set_index("profile_id").loc["AUR:2023"]
    assert team["simple_rating"] == 5.4
    assert team["true_shooting_pct"] == 0.598
    assert team["three_point_attempt_rate"] == 0.421
    assert team["opp_effective_field_goal_pct"] == 0.531
    # Percent-scale rates are stored as fractions, matching turnover_pct.
    assert team["opp_turnover_pct"] == pytest.approx(0.132)
    assert team["defensive_rebound_pct"] == pytest.approx(0.761)
    assert team["opp_free_throw_rate"] == 0.188


def test_team_seasons_without_advanced_columns_still_resolve(tmp_path: Path) -> None:
    source_directory = tmp_path / "historical"
    build_historical_csv_source(source_directory)
    catalog = DatasetCatalog(tmp_path / "missing.sqlite", historical_data_path=source_directory)

    team_seasons = SchemaResolver(catalog).resolve_team_seasons()

    assert team_seasons.advanced_features == ()
    assert "AUR:2023" in set(team_seasons.frame["profile_id"])
