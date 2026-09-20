"""Convert catalog-confirmed NBA SQLite relations into stable analytical frames."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable

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


METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "player_id": ("PERSON_ID", "PLAYER_ID", "PLAYERID", "ID"),
    "player_name": ("PLAYER_NAME", "FULL_NAME", "DISPLAY_FIRST_LAST", "NAME"),
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
}

PLAYER_ADVANCED_METRICS = ("ts_pct", "efg_pct", "usg_pct", "per", "win_shares", "bpm", "vorp", "pace")


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
        source_table = self._find_player_stats_table(report)
        source_columns = self._column_mapping(source_table)
        source_frame = self._load_table(source_table, source_columns)

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

    def _require_ready_catalog(self, report: CatalogReport) -> None:
        if report.status != "dataset_ready":
            raise SchemaResolutionError(report.message)

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

    def _load_table(self, table: CatalogTable, column_mapping: dict[str, str]) -> pd.DataFrame:
        select_list = ", ".join(
            f"{quote_identifier(source_column)} AS {quote_identifier(normalized_name)}"
            for normalized_name, source_column in column_mapping.items()
        )
        query = f"SELECT {select_list} FROM {quote_identifier(table.name)}"
        with self.catalog._read_only_connection() as connection:
            frame = pd.read_sql_query(query, connection)

        if "player_id" in frame.columns:
            frame["player_id"] = frame["player_id"].astype("string")
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
        return grouped


def _canonical_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())
