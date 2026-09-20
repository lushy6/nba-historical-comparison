"""Read-only inspection for the user-supplied NBA SQLite database."""

from __future__ import annotations

import os
import sqlite3
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
    """Inspect a SQLite file without coupling production code to one dataset release."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @classmethod
    def from_environment(cls) -> "DatasetCatalog":
        configured_path = os.environ.get("NBA_DATABASE_PATH")
        project_root = Path(__file__).resolve().parents[2]
        path = Path(configured_path) if configured_path else project_root / "nba.sqlite"
        return cls(path)

    def inspect(self) -> CatalogReport:
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

    def _read_only_connection(self) -> sqlite3.Connection:
        database_uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        connection.execute("PRAGMA query_only = ON")
        return connection


def quote_identifier(identifier: str) -> str:
    """Quote a catalog-provided SQLite identifier without accepting arbitrary SQL."""

    return f'"{identifier.replace("\"", "\"\"")}"'
