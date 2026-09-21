"""Convert catalog-confirmed NBA SQLite relations into stable analytical frames."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.catalog import CatalogReport, CatalogTable, DatasetCatalog, quote_identifier


PLAYER_BASE_METRICS = (
    "three_point_attempts",
    "three_point_made",
    "field_goal_attempts",
    "field_goals_made",
    "points",
    "blocks",
    "turnovers",
    "steals",
    "assists",
    "rebounds",
    "free_throw_attempts",
    "free_throws_made",
)

TEAM_COMPARISON_METRICS = (
    "effective_field_goal_pct",
    "turnover_pct",
    "offensive_rebound_pct",
    "free_throw_rate",
    "offensive_rating",
    "defensive_rating",
    "net_rating",
    "pace",
)


METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "player_id": ("PERSON_ID", "PLAYER_ID", "PLAYERID", "ID"),
    "player_name": ("PLAYER_NAME", "FULL_NAME", "DISPLAY_FIRST_LAST", "NAME"),
    "team_id": ("TEAM_ID", "TEAMID", "ID"),
    "team_name": ("TEAM_NAME", "FULL_NAME", "NICKNAME", "NAME"),
    "season": ("SEASON_ID", "SEASON", "SEASON_YEAR", "YEAR"),
    "three_point_attempts": ("FG3A", "3PA", "THREE_PA", "THREE_POINT_ATTEMPTS"),
    "three_point_made": ("FG3M", "3PM", "THREE_PM", "THREE_POINT_MADE"),
    "field_goal_attempts": ("FGA", "FIELD_GOAL_ATTEMPTS"),
    "field_goals_made": ("FGM", "FIELD_GOALS_MADE"),
    "points": ("PTS", "POINTS"),
    "blocks": ("BLK", "BLOCKS"),
    "turnovers": ("TOV", "TO", "TURNOVERS"),
    "steals": ("STL", "STEALS"),
    "assists": ("AST", "ASSISTS"),
    "rebounds": ("REB", "TOTAL_REBOUNDS", "REBOUNDS"),
    "free_throw_attempts": ("FTA", "FREE_THROW_ATTEMPTS"),
    "free_throws_made": ("FTM", "FREE_THROWS_MADE"),
    "per": ("PER", "PLAYER_EFFICIENCY_RATING"),
    "win_shares": ("WS", "WIN_SHARES"),
    "bpm": ("BPM", "BOX_PLUS_MINUS"),
    "vorp": ("VORP", "VALUE_OVER_REPLACEMENT_PLAYER"),
    "ts_pct": ("TS_PCT", "TS_PERCENTAGE", "TRUE_SHOOTING_PCT"),
    "efg_pct": ("EFG_PCT", "E_FG_PCT", "EFFECTIVE_FIELD_GOAL_PCT"),
    "usg_pct": ("USG_PCT", "USAGE_PCT", "USAGE_PERCENTAGE"),
    "pace": ("PACE",),
    "effective_field_goal_pct": ("EFG_PCT", "E_FG_PCT", "EFFECTIVE_FIELD_GOAL_PCT"),
    "turnover_pct": ("TOV_PCT", "TURNOVER_PCT", "TOV_PERCENTAGE"),
    "offensive_rebound_pct": ("OREB_PCT", "ORB_PCT", "OFFENSIVE_REBOUND_PCT"),
    "free_throw_rate": ("FTA_RATE", "FTR", "FREE_THROW_RATE"),
    "offensive_rating": ("OFF_RATING", "OFFENSIVE_RATING", "ORTG"),
    "defensive_rating": ("DEF_RATING", "DEFENSIVE_RATING", "DRTG"),
    "net_rating": ("NET_RATING", "NETRTG"),
}

PLAYER_ADVANCED_METRICS = ("ts_pct", "efg_pct", "usg_pct", "per", "win_shares", "bpm", "vorp", "pace")

HISTORICAL_PLAYER_TOTALS = "Player Totals.csv"
HISTORICAL_PLAYER_ADVANCED = "Advanced.csv"
HISTORICAL_PLAYER_PER_GAME = "Player Per Game.csv"
HISTORICAL_TEAM_SUMMARIES = "Team Summaries.csv"

HISTORICAL_PLAYER_KEY = ("season", "lg", "player_id", "team")
HISTORICAL_LEAGUES = {"NBA", "BAA"}


class SchemaResolutionError(RuntimeError):
    """Raised when the supplied dataset cannot satisfy an analytical contract."""


@dataclass(frozen=True)
class ResolvedSeasonFrame:
    """A normalized analytical data set plus its verified origin."""

    frame: pd.DataFrame
    source_table: str
    base_features: tuple[str, ...]
    advanced_features: tuple[str, ...]


class SchemaResolver:
    """Resolve schema aliases from inspected metadata before selecting any data."""

    def __init__(self, catalog: DatasetCatalog) -> None:
        self.catalog = catalog

    def resolve_player_seasons(self) -> ResolvedSeasonFrame:
        report = self.catalog.inspect()
        self._require_ready_catalog(report)
        if report.source_format == "historical_csv":
            return self._resolve_historical_csv_player_seasons()
        source_table = self._find_player_stats_table(report)
        source_columns = self._column_mapping(source_table)
        source_frame = self._load_table(source_table, source_columns)
        # Generic ID/NAME aliases can describe a player, so they do not verify a team.
        has_affiliation = (
            _canonical_identifier(source_columns.get("team_id", "")) == "teamid"
            and _canonical_identifier(source_columns.get("team_name", "")) == "teamname"
        )
        source_frame["team_codes"] = ""
        source_frame["team_names"] = ""
        if has_affiliation:
            valid_team = (
                source_frame["team_id"].notna()
                & source_frame["team_name"].notna()
                & source_frame["team_id"].ne("")
                & source_frame["team_name"].ne("")
                & source_frame["team_id"].str.upper().ne("TOT")
            )
            source_frame.loc[valid_team, "team_codes"] = source_frame.loc[valid_team, "team_id"]
            source_frame.loc[valid_team, "team_names"] = source_frame.loc[valid_team, "team_name"]

        if "player_name" not in source_frame.columns:
            source_frame = self._attach_player_names(report, source_table.name, source_frame)

        required_columns = ("player_id", "player_name", "season", *PLAYER_BASE_METRICS)
        missing_columns = [column for column in required_columns if column not in source_frame.columns]
        if missing_columns:
            raise SchemaResolutionError(
                "A player season source was found but cannot be normalized; missing "
                + ", ".join(missing_columns)
                + "."
            )

        normalized = self._aggregate_player_seasons(source_frame)
        advanced_features = tuple(
            metric for metric in PLAYER_ADVANCED_METRICS if metric in normalized.columns
        )
        return ResolvedSeasonFrame(
            frame=normalized,
            source_table=source_table.name,
            base_features=PLAYER_BASE_METRICS,
            advanced_features=advanced_features,
        )

    def resolve_team_seasons(self) -> ResolvedSeasonFrame:
        report = self.catalog.inspect()
        self._require_ready_catalog(report)
        if report.source_format == "historical_csv":
            return self._resolve_historical_csv_team_seasons()
        source_table = self._find_team_stats_table(report)
        source_frame = self._load_table(source_table, self._column_mapping(source_table))

        if "team_name" not in source_frame.columns:
            source_frame = self._attach_team_names(report, source_table.name, source_frame)

        required_columns = ("team_id", "team_name", "season", *TEAM_COMPARISON_METRICS)
        missing_columns = [column for column in required_columns if column not in source_frame.columns]
        if missing_columns:
            raise SchemaResolutionError(
                "A team season source was found but cannot be normalized; missing "
                + ", ".join(missing_columns)
                + "."
            )

        return ResolvedSeasonFrame(
            frame=self._aggregate_team_seasons(source_frame),
            source_table=source_table.name,
            base_features=TEAM_COMPARISON_METRICS,
            advanced_features=(),
        )

    def _resolve_historical_csv_player_seasons(self) -> ResolvedSeasonFrame:
        totals = self._load_historical_csv(
            HISTORICAL_PLAYER_TOTALS,
            (
                *HISTORICAL_PLAYER_KEY,
                "player",
                "fg",
                "fga",
                "x3p",
                "x3pa",
                "ft",
                "fta",
                "trb",
                "ast",
                "stl",
                "blk",
                "tov",
                "pts",
            ),
        ).rename(
            columns={
                "player": "player_name",
                "x3pa": "three_point_attempts",
                "x3p": "three_point_made",
                "fga": "field_goal_attempts",
                "fg": "field_goals_made",
                "pts": "points",
                "blk": "blocks",
                "tov": "turnovers",
                "stl": "steals",
                "ast": "assists",
                "trb": "rebounds",
                "fta": "free_throw_attempts",
                "ft": "free_throws_made",
            }
        )
        advanced = self._load_historical_csv(
            HISTORICAL_PLAYER_ADVANCED,
            (*HISTORICAL_PLAYER_KEY, "mp", "per", "ts_percent", "usg_percent", "ws", "bpm", "vorp"),
        ).rename(
            columns={
                "mp": "advanced_minutes",
                "ts_percent": "ts_pct",
                "usg_percent": "usg_pct",
                "ws": "win_shares",
            }
        )
        per_game = self._load_historical_csv(
            HISTORICAL_PLAYER_PER_GAME,
            (*HISTORICAL_PLAYER_KEY, "e_fg_percent"),
        ).rename(columns={"e_fg_percent": "efg_pct"})

        frame = self._filter_historical_leagues(totals).merge(
            self._filter_historical_leagues(
                advanced.loc[
                    :,
                    [*HISTORICAL_PLAYER_KEY, "advanced_minutes", "per", "ts_pct", "usg_pct", "win_shares", "bpm", "vorp"],
                ]
            ),
            on=HISTORICAL_PLAYER_KEY,
            how="left",
            validate="one_to_one",
        ).merge(
            self._filter_historical_leagues(
                per_game.loc[:, [*HISTORICAL_PLAYER_KEY, "efg_pct"]]
            ),
            on=HISTORICAL_PLAYER_KEY,
            how="left",
            validate="one_to_one",
        )
        frame["season"] = frame["season"].astype("string")
        frame["team"] = frame["team"].astype("string")
        frame = frame.merge(
            self._historical_team_labels(),
            left_on=["season", "team"],
            right_on=["season", "team_code"],
            how="left",
            validate="many_to_one",
        )
        normalized = self._collapse_historical_player_rows(frame)
        advanced_features = tuple(
            metric
            for metric in PLAYER_ADVANCED_METRICS
            if metric in normalized.columns and normalized[metric].notna().any()
        )
        return ResolvedSeasonFrame(
            frame=normalized,
            source_table="historical_csv:player_season",
            base_features=PLAYER_BASE_METRICS,
            advanced_features=advanced_features,
        )

    def _resolve_historical_csv_team_seasons(self) -> ResolvedSeasonFrame:
        frame = self._filter_historical_leagues(
            self._load_historical_csv(
                HISTORICAL_TEAM_SUMMARIES,
                (
                    "season",
                    "lg",
                    "team",
                    "abbreviation",
                    "e_fg_percent",
                    "tov_percent",
                    "orb_percent",
                    "f_tr",
                    "o_rtg",
                    "d_rtg",
                    "n_rtg",
                    "pace",
                ),
            )
        ).rename(
            columns={
                "team": "team_name",
                "abbreviation": "team_id",
                "e_fg_percent": "effective_field_goal_pct",
                "tov_percent": "turnover_pct",
                "orb_percent": "offensive_rebound_pct",
                "f_tr": "free_throw_rate",
                "o_rtg": "offensive_rating",
                "d_rtg": "defensive_rating",
                "n_rtg": "net_rating",
            }
        )
        for metric in TEAM_COMPARISON_METRICS:
            frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
        for metric in ("turnover_pct", "offensive_rebound_pct"):
            frame[metric] = frame[metric].where(frame[metric] <= 1, frame[metric] / 100)

        clean = frame.dropna(subset=["team_id", "team_name", "season"]).copy()
        clean["team_id"] = clean["team_id"].astype("string")
        clean["season"] = clean["season"].astype("string")
        clean = clean.rename(columns={"team_name": "name"})
        clean["team_codes"] = clean["team_id"]
        clean["team_names"] = clean["name"]
        clean.insert(0, "profile_id", clean["team_id"] + ":" + clean["season"])
        return ResolvedSeasonFrame(
            frame=clean.loc[:, [
                "profile_id", "team_id", "season", "name", "team_codes", "team_names",
                *TEAM_COMPARISON_METRICS,
            ]],
            source_table="historical_csv:team_season",
            base_features=TEAM_COMPARISON_METRICS,
            advanced_features=(),
        )

    def _require_ready_catalog(self, report: CatalogReport) -> None:
        if report.status != "dataset_ready":
            raise SchemaResolutionError(report.message)

    def _load_historical_csv(
        self, filename: str, required_columns: tuple[str, ...]
    ) -> pd.DataFrame:
        directory = self._historical_data_directory()
        path = directory / filename
        if not path.is_file():
            raise SchemaResolutionError(f"Historical CSV source is missing {filename}.")
        frame = pd.read_csv(path, low_memory=False)
        missing_columns = [column for column in required_columns if column not in frame.columns]
        if missing_columns:
            raise SchemaResolutionError(
                f"Historical CSV source {filename} is missing " + ", ".join(missing_columns) + "."
            )
        return frame

    def _historical_data_directory(self) -> Path:
        if self.catalog.historical_data_path is None:
            raise SchemaResolutionError("No historical CSV data directory was configured.")
        return self.catalog.historical_data_path

    def _historical_team_labels(self) -> pd.DataFrame:
        labels = self._filter_historical_leagues(
            self._load_historical_csv(
                "Team Abbrev.csv", ("season", "lg", "team", "abbreviation")
            )
        ).rename(columns={"abbreviation": "team_code", "team": "team_name"})
        labels["season"] = labels["season"].astype("string")
        labels["team_code"] = labels["team_code"].astype("string")
        return labels.drop_duplicates(["season", "team_code"], keep="first").loc[
            :, ["season", "team_code", "team_name"]
        ]

    @staticmethod
    def _filter_historical_leagues(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.loc[frame["lg"].astype("string").isin(HISTORICAL_LEAGUES)].copy()

    @staticmethod
    def _collapse_historical_player_rows(frame: pd.DataFrame) -> pd.DataFrame:
        numeric_columns = [
            *PLAYER_BASE_METRICS,
            "advanced_minutes",
            "per",
            "ts_pct",
            "efg_pct",
            "usg_pct",
            "win_shares",
            "bpm",
            "vorp",
        ]
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

        key_columns = ["season", "lg", "player_id"]
        total_rows = frame.loc[
            frame["team"].astype("string").str.upper() == "TOT"
        ].drop_duplicates(subset=key_columns, keep="first")
        non_total_rows = frame.loc[
            frame["team"].astype("string").str.upper() != "TOT"
        ]
        verified_affiliations = non_total_rows.loc[
            non_total_rows["team_name"].notna() & non_total_rows["team_name"].ne("")
        ]
        affiliations = verified_affiliations.groupby(
            key_columns, as_index=False, sort=False, dropna=False
        ).agg(team_codes=("team_code", _joined_unique), team_names=("team_name", _joined_unique))
        non_total_rows = non_total_rows.merge(
            total_rows.loc[:, key_columns].assign(_has_total=True),
            on=key_columns,
            how="left",
        ).loc[lambda rows: rows["_has_total"].isna()].drop(columns="_has_total")
        group_size = non_total_rows.groupby(key_columns, dropna=False)["team"].transform("size")
        single_rows = non_total_rows.loc[group_size == 1]

        combined_rows: list[pd.Series] = []
        for _, group in non_total_rows.loc[group_size > 1].groupby(
            key_columns, sort=False, dropna=False
        ):
            combined = group.iloc[0].copy()
            for column in PLAYER_BASE_METRICS:
                combined[column] = group[column].sum(min_count=1)
            weights = group["advanced_minutes"].fillna(0)
            for column in ("per", "ts_pct", "efg_pct", "usg_pct", "bpm"):
                combined[column] = _weighted_mean(group[column], weights)
            for column in ("win_shares", "vorp"):
                combined[column] = group[column].sum(min_count=1)
            combined_rows.append(combined)

        normalized = pd.concat(
            [total_rows, single_rows, pd.DataFrame(combined_rows)], ignore_index=True
        ).dropna(subset=["player_id", "player_name", "season"])
        normalized = normalized.merge(
            affiliations, on=key_columns, how="left", validate="one_to_one"
        )
        normalized[["team_codes", "team_names"]] = normalized[
            ["team_codes", "team_names"]
        ].fillna("")
        normalized["player_id"] = normalized["player_id"].astype("string")
        normalized["season"] = normalized["season"].astype("string")
        normalized = normalized.rename(columns={"player_name": "name"})
        for feature in PLAYER_ADVANCED_METRICS:
            if feature not in normalized.columns:
                normalized[feature] = pd.NA
        normalized.insert(0, "profile_id", normalized["player_id"] + ":" + normalized["season"])
        return normalized.loc[
            :,
            [
                "profile_id", "player_id", "season", "name", "team_codes", "team_names",
                *PLAYER_BASE_METRICS, *PLAYER_ADVANCED_METRICS,
            ],
        ]

    def _find_player_stats_table(self, report: CatalogReport) -> CatalogTable:
        required = ("player_id", "season", *PLAYER_BASE_METRICS)
        candidates = [
            table
            for table in report.tables
            if all(metric in self._column_mapping(table) for metric in required)
        ]
        if not candidates:
            raise SchemaResolutionError(
                "No catalog-confirmed player season table contains the 12 required base statistics. "
                "Inspect /api/health after placing the exact nba.sqlite file in the project root."
            )

        return max(
            candidates,
            key=lambda table: (
                "player" in _canonical_identifier(table.name),
                "stat" in _canonical_identifier(table.name),
                len(self._column_mapping(table)),
            ),
        )

    def _find_team_stats_table(self, report: CatalogReport) -> CatalogTable:
        required = ("team_id", "season", *TEAM_COMPARISON_METRICS)
        candidates = [
            table
            for table in report.tables
            if all(metric in self._column_mapping(table) for metric in required)
        ]
        if not candidates:
            raise SchemaResolutionError(
                "No catalog-confirmed team season table contains Four Factors, ratings, and pace. "
                "Inspect /api/health after placing the exact nba.sqlite file in the project root."
            )

        return max(
            candidates,
            key=lambda table: (
                "team" in _canonical_identifier(table.name),
                "stat" in _canonical_identifier(table.name),
                len(self._column_mapping(table)),
            ),
        )

    def _attach_player_names(
        self, report: CatalogReport, source_table_name: str, source_frame: pd.DataFrame
    ) -> pd.DataFrame:
        candidate_tables = [
            table
            for table in report.tables
            if table.name != source_table_name
            and {"player_id", "player_name"}.issubset(self._column_mapping(table))
        ]
        if not candidate_tables:
            return source_frame

        identity_table = max(
            candidate_tables,
            key=lambda table: ("player" in _canonical_identifier(table.name), len(table.columns)),
        )
        identity_columns = self._column_mapping(identity_table)
        names = self._load_table(
            identity_table,
            {
                "player_id": identity_columns["player_id"],
                "player_name": identity_columns["player_name"],
            },
        ).drop_duplicates(subset=["player_id"])
        return source_frame.merge(names, on="player_id", how="left", validate="many_to_one")

    def _attach_team_names(
        self, report: CatalogReport, source_table_name: str, source_frame: pd.DataFrame
    ) -> pd.DataFrame:
        candidate_tables = [
            table
            for table in report.tables
            if table.name != source_table_name
            and {"team_id", "team_name"}.issubset(self._column_mapping(table))
        ]
        if not candidate_tables:
            return source_frame

        identity_table = max(
            candidate_tables,
            key=lambda table: ("team" in _canonical_identifier(table.name), len(table.columns)),
        )
        identity_columns = self._column_mapping(identity_table)
        names = self._load_table(
            identity_table,
            {
                "team_id": identity_columns["team_id"],
                "team_name": identity_columns["team_name"],
            },
        ).drop_duplicates(subset=["team_id"])
        return source_frame.merge(names, on="team_id", how="left", validate="many_to_one")

    def _load_table(self, table: CatalogTable, column_mapping: dict[str, str]) -> pd.DataFrame:
        select_list = ", ".join(
            f"{quote_identifier(source_column)} AS {quote_identifier(normalized_name)}"
            for normalized_name, source_column in column_mapping.items()
        )
        query = f"SELECT {select_list} FROM {quote_identifier(table.name)}"
        with self.catalog._read_only_connection() as connection:
            frame = pd.read_sql_query(query, connection)

        for identifier in ("player_id", "team_id"):
            if identifier in frame.columns:
                frame[identifier] = frame[identifier].astype("string")
        if "season" in frame.columns:
            frame["season"] = frame["season"].astype("string")
        return frame

    @staticmethod
    def _column_mapping(table: CatalogTable) -> dict[str, str]:
        normalized_columns = {
            _canonical_identifier(column): column for column in table.columns
        }
        mapping: dict[str, str] = {}
        for metric, aliases in METRIC_ALIASES.items():
            for alias in aliases:
                matched_column = normalized_columns.get(_canonical_identifier(alias))
                if matched_column:
                    mapping[metric] = matched_column
                    break
        return mapping

    @staticmethod
    def _aggregate_player_seasons(frame: pd.DataFrame) -> pd.DataFrame:
        numeric_features = [
            feature
            for feature in (*PLAYER_BASE_METRICS, *PLAYER_ADVANCED_METRICS)
            if feature in frame.columns
        ]
        for feature in numeric_features:
            frame[feature] = pd.to_numeric(frame[feature], errors="coerce")

        clean = frame.dropna(subset=["player_id", "player_name", "season", *PLAYER_BASE_METRICS])
        aggregations: dict[str, str] = {
            "player_name": "first",
            **{feature: "sum" for feature in PLAYER_BASE_METRICS},
            **{
                feature: "mean"
                for feature in PLAYER_ADVANCED_METRICS
                if feature in clean.columns
            },
        }
        grouped = (
            clean.groupby(["player_id", "season"], as_index=False, dropna=False)
            .agg(aggregations)
            .rename(columns={"player_name": "name"})
            .sort_values(["player_id", "season"], kind="stable")
            .reset_index(drop=True)
        )
        grouped.insert(0, "profile_id", grouped["player_id"] + ":" + grouped["season"])
        affiliations = clean.groupby(["player_id", "season"], as_index=False, dropna=False).agg(
            team_codes=("team_codes", _joined_unique), team_names=("team_names", _joined_unique)
        )
        grouped = grouped.merge(
            affiliations, on=["player_id", "season"], how="left", validate="one_to_one"
        )
        return grouped.loc[:, [
            "profile_id", "player_id", "season", "name", "team_codes", "team_names",
            *numeric_features,
        ]]

    @staticmethod
    def _aggregate_team_seasons(frame: pd.DataFrame) -> pd.DataFrame:
        for feature in TEAM_COMPARISON_METRICS:
            frame[feature] = pd.to_numeric(frame[feature], errors="coerce")

        clean = frame.dropna(subset=["team_id", "team_name", "season", *TEAM_COMPARISON_METRICS])
        aggregations: dict[str, str] = {
            "team_name": "first",
            **{feature: "mean" for feature in TEAM_COMPARISON_METRICS},
        }
        grouped = (
            clean.groupby(["team_id", "season"], as_index=False, dropna=False)
            .agg(aggregations)
            .rename(columns={"team_name": "name"})
            .sort_values(["team_id", "season"], kind="stable")
            .reset_index(drop=True)
        )
        grouped.insert(0, "profile_id", grouped["team_id"] + ":" + grouped["season"])
        grouped.insert(4, "team_codes", grouped["team_id"])
        grouped.insert(5, "team_names", grouped["name"])
        return grouped


def _canonical_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _joined_unique(values: pd.Series) -> str:
    return "|".join(sorted({str(value) for value in values.dropna() if str(value)}))


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float("nan")
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())
