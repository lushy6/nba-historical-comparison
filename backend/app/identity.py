"""Safe, optional NBA identities for locally available visual assets."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sqlite3
from typing import Literal, TYPE_CHECKING
from unicodedata import combining, normalize

if TYPE_CHECKING:
    from app.catalog import DatasetCatalog


IdentityKind = Literal["player", "team"]
IdentitySignature = tuple[str, int | None, int | None]


@dataclass(frozen=True)
class VisualIdentityRecord:
    kind: IdentityKind
    nba_id: str


class LocalIdentityIndex:
    """Resolve known local NBA player and team identities without writing to SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._records: dict[IdentityKind, dict[str, VisualIdentityRecord | None]] = {}

    def resolve(self, kind: IdentityKind, name: str) -> VisualIdentityRecord | None:
        if kind not in {"player", "team"} or not self.database_path.is_file():
            return None
        records = self._records.get(kind)
        if records is None:
            records = self._load_records(kind)
            self._records[kind] = records
        return records.get(fold_name(name))

    def _load_records(self, kind: IdentityKind) -> dict[str, VisualIdentityRecord | None]:
        table = "player" if kind == "player" else "team"
        try:
            uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                rows = connection.execute(f"SELECT id, full_name FROM {table}").fetchall()
        except sqlite3.Error:
            return {}

        records: dict[str, VisualIdentityRecord | None] = {}
        for nba_id, full_name in rows:
            if nba_id is None or full_name is None:
                continue
            key = fold_name(str(full_name))
            candidate = VisualIdentityRecord(kind=kind, nba_id=str(nba_id))
            existing = records.get(key)
            if existing is None and key in records:
                continue
            if existing is not None and existing.nba_id != candidate.nba_id:
                records[key] = None
            else:
                records[key] = candidate
        return records


def fold_name(value: object) -> str:
    """Case- and accent-insensitive key: the catalog spells "Jokić", the index "Jokic"."""

    return "".join(
        character
        for character in normalize("NFKD", str(value))
        if not combining(character)
    ).casefold()


@lru_cache(maxsize=8)
def _cached_identity_index(signature: IdentitySignature) -> LocalIdentityIndex | None:
    database_path, byte_size, modification_time = signature
    if byte_size is None or modification_time is None:
        return None
    return LocalIdentityIndex(Path(database_path))


def identity_index_for(catalog: DatasetCatalog) -> LocalIdentityIndex | None:
    """Return the signature-cached optional index for a catalog's SQLite file."""

    return _cached_identity_index(catalog.identity_signature())


def image_url_for(identity: VisualIdentityRecord) -> str:
    if identity.kind == "player":
        return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{identity.nba_id}.png"
    return f"https://cdn.nba.com/logos/nba/{identity.nba_id}/primary/L/logo.svg"
