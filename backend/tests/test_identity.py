import sqlite3
from contextlib import closing
from os import replace
from pathlib import Path

from app.catalog import DatasetCatalog
from app.identity import LocalIdentityIndex, identity_index_for, image_url_for


def seed(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE player (id INTEGER, full_name TEXT);
            CREATE TABLE team (id INTEGER, full_name TEXT);
            INSERT INTO player VALUES
                (2544, 'LeBron James'),
                (999, 'Duplicate Name'),
                (998, 'Duplicate Name');
            INSERT INTO team VALUES (1610612747, 'Los Angeles Lakers');
            """
        )


def test_exact_player_lookup_returns_official_headshot_url(tmp_path: Path) -> None:
    path = tmp_path / "identity.sqlite"
    seed(path)

    identity = LocalIdentityIndex(path).resolve("player", "LeBron James")

    assert identity is not None
    assert identity.nba_id == "2544"
    assert image_url_for(identity).endswith("/2544.png")


def test_ambiguous_or_missing_identity_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "identity.sqlite"
    seed(path)
    index = LocalIdentityIndex(path)

    assert index.resolve("player", "Duplicate Name") is None
    assert index.resolve("team", "Missing Team") is None


def test_cached_index_is_replaced_when_optional_database_changes(tmp_path: Path) -> None:
    path = tmp_path / "identity.sqlite"
    replacement_path = tmp_path / "replacement.sqlite"
    seed(path)
    seed(replacement_path)
    with closing(sqlite3.connect(replacement_path)) as connection:
        connection.execute("INSERT INTO player VALUES (203999, 'New Player')")
        connection.commit()
    catalog = DatasetCatalog(path)

    first_index = identity_index_for(catalog)
    assert first_index is not None
    assert first_index.resolve("player", "LeBron James") is not None
    replace(replacement_path, path)

    refreshed_index = identity_index_for(catalog)

    assert first_index is not refreshed_index
    assert refreshed_index is not None
    assert refreshed_index.resolve("player", "New Player") is not None


def test_missing_optional_database_has_no_cached_index(tmp_path: Path) -> None:
    catalog = DatasetCatalog(tmp_path / "identity.sqlite")

    assert identity_index_for(catalog) is None


def test_identity_index_returns_none_when_database_disappears_before_stat(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "identity.sqlite"
    path.write_text("optional database")
    catalog = DatasetCatalog(path)
    original_is_file = Path.is_file

    def delete_after_existence_check(candidate: Path) -> bool:
        if candidate == path:
            candidate.unlink()
            return True
        return original_is_file(candidate)

    monkeypatch.setattr(Path, "is_file", delete_after_existence_check)

    assert identity_index_for(catalog) is None


def test_accented_catalog_names_resolve_to_ascii_identity_names(tmp_path: Path) -> None:
    path = tmp_path / "identity.sqlite"
    seed(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("INSERT INTO player VALUES (203999, 'Nikola Jokic')")
        connection.execute("INSERT INTO player VALUES (1630578, 'Alperen Şengün')")
        connection.commit()
    index = LocalIdentityIndex(path)

    jokic = index.resolve("player", "Nikola Jokić")
    sengun = index.resolve("player", "ALPEREN SENGUN")

    assert jokic is not None and jokic.nba_id == "203999"
    assert sengun is not None and sengun.nba_id == "1630578"


def test_names_that_collide_only_after_accent_folding_stay_ambiguous(tmp_path: Path) -> None:
    path = tmp_path / "identity.sqlite"
    seed(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("INSERT INTO player VALUES (1, 'Jose Garcia')")
        connection.execute("INSERT INTO player VALUES (2, 'José García')")
        connection.commit()

    assert LocalIdentityIndex(path).resolve("player", "José García") is None
