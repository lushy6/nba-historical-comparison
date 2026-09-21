"""Read-only inspection for the user-supplied NBA SQLite database."""

from __future__ import annotations

import os
import sqlite3
from csv import reader
from dataclasses import dataclass
from pathlib import Path


MISSING_DATASET_MESSAGE = "Place nba.sqlite in the project root to enable comparisons."


@dataclass(frozen=True)
class CatalogTable:
    """A table and the column names SQLite reports for it."""

    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class CatalogReport:
    """A serializable summary of database availability and its discovered shape."""

    status: str
    database_path: str
    tables: tuple[CatalogTable, ...]
    message: str
    source_format: str = "sqlite"

    def to_payload(self) -> dict[str, object]:
        if self.status == "dataset_missing":
            return {
                "status": self.status,
                "database_path": self.database_path,
                "tables": [],
                "message": self.message,
            }

        return {
            "status": self.status,
            "database_path": self.database_path,
            "tables": [
                {"name": table.name, "columns": list(table.columns)} for table in self.tables
            ],
            "message": self.message,
        }


class DatasetCatalog:
    """Inspect either the legacy SQLite file or the verified historical CSV catalog."""

    def __init__(
        self, database_path: Path, historical_data_path: Path | None = None
    ) -> None:
        self.database_path = database_path
        self.historical_data_path = historical_data_path

    @classmethod
    def from_environment(cls) -> "DatasetCatalog":
        configured_path = os.environ.get("NBA_DATABASE_PATH")
        project_root = Path(__file__).resolve().parents[2]
        path = Path(configured_path) if configured_path else project_root / "nba.sqlite"
        configured_historical_path = os.environ.get("NBA_HISTORICAL_DATA_PATH")
        historical_path = (
            Path(configured_historical_path)
            if configured_historical_path
            else project_root / "data" / "historical"
        )
        return cls(path, historical_data_path=historical_path)

    def inspect(self) -> CatalogReport:
        if self._has_historical_csv_source():
            return self._inspect_historical_csv_source()

        if not self.database_path.is_file():
            return CatalogReport(
                status="dataset_missing",
                database_path=self.database_path.name,
                tables=(),
                message=MISSING_DATASET_MESSAGE,
            )

        try:
            with self._read_only_connection() as connection:
                table_names = [
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        """
                    )
                ]
                tables = tuple(
                    CatalogTable(
                        name=table_name,
                        columns=tuple(
                            row[1]
                            for row in connection.execute(
                                f"PRAGMA table_info({quote_identifier(table_name)})"
                            )
                        ),
                    )
                    for table_name in table_names
                )
        except sqlite3.Error as error:
            return CatalogReport(
                status="dataset_unreadable",
                database_path=self.database_path.name,
                tables=(),
                message=f"SQLite could not be inspected: {error}",
            )

        return CatalogReport(
            status="dataset_ready",
            database_path=self.database_path.name,
            tables=tables,
            message="SQLite catalog discovered. Source mappings are validated before comparisons run.",
        )

    def source_signature(self) -> tuple[str, ...]:
        """Return a cheap cache key that changes whenever the active source changes."""

        if self._has_historical_csv_source():
            assert self.historical_data_path is not None
            files = tuple(
                f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
                for path in sorted(self.historical_data_path.glob("*.csv"))
            )
            return ("historical_csv", str(self.historical_data_path.resolve()), *files)

        if self.database_path.is_file():
            stat = self.database_path.stat()
            return (
                "sqlite",
                str(self.database_path.resolve()),
                str(stat.st_size),
                str(stat.st_mtime_ns),
            )
        return ("missing", str(self.database_path.resolve()))

    def _has_historical_csv_source(self) -> bool:
        return bool(
            self.historical_data_path
            and self.historical_data_path.is_dir()
            and any(self.historical_data_path.glob("*.csv"))
        )

    def _inspect_historical_csv_source(self) -> CatalogReport:
        assert self.historical_data_path is not None
        try:
            tables = tuple(
                CatalogTable(name=path.name, columns=self._csv_columns(path))
                for path in sorted(self.historical_data_path.glob("*.csv"))
            )
        except (OSError, UnicodeDecodeError) as error:
            return CatalogReport(
                status="dataset_unreadable",
                database_path=str(self.historical_data_path),
                tables=(),
                message=f"Historical CSV data could not be inspected: {error}",
                source_format="historical_csv",
            )

        return CatalogReport(
            status="dataset_ready",
            database_path=str(self.historical_data_path),
            tables=tables,
            message="Historical CSV catalog discovered. Source mappings are validated before comparisons run.",
            source_format="historical_csv",
        )

    @staticmethod
    def _csv_columns(path: Path) -> tuple[str, ...]:
        with path.open(encoding="utf-8", newline="") as file:
            return tuple(next(reader(file), ()))

    def _read_only_connection(self) -> sqlite3.Connection:
        database_uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        return connection


def quote_identifier(identifier: str) -> str:
    """Quote a catalog-provided SQLite identifier without accepting arbitrary SQL."""

    return f'"{identifier.replace("\"", "\"\"")}"'
