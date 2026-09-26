import asyncio
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

import app.main as main
from test_api import get, seed_database


class CountingResolver:
    def __init__(self) -> None:
        self.player_calls = 0

    def resolve_player_seasons(self) -> object:
        self.player_calls += 1
        return object()


def test_cached_season_frame_reuses_a_resolved_source(monkeypatch) -> None:
    resolver = CountingResolver()
    main._cached_season_frame.cache_clear()
    monkeypatch.setattr(main, "_resolver", lambda: resolver)

    first = main._cached_season_frame("player", ("historical_csv", "fixture"))
    second = main._cached_season_frame("player", ("historical_csv", "fixture"))

    assert first is second
    assert resolver.player_calls == 1


@pytest.mark.parametrize("invalidation", ["source_update", "source_switch"])
def test_metadata_search_compare_share_cache_and_invalidate(
    tmp_path: Path, monkeypatch, invalidation: str
) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))
    main._cached_season_frame.cache_clear()
    resolvers = []
    original_resolver = main._resolver

    def make_resolver():
        resolver = Mock(wraps=original_resolver())
        resolvers.append(resolver)
        return resolver

    build_options = Mock(wraps=main._filter_options)
    monkeypatch.setattr(main, "_resolver", make_resolver)
    monkeypatch.setattr(main, "_filter_options", build_options)

    def request_all(expected_year: int) -> None:
        expected_season = f"{expected_year}-{(expected_year + 1) % 100:02d}"
        for kind, selected_id, query in (
            ("player", "7:2022-23", "cinder"),
            ("team", "1:2022-23", "canyon"),
        ):
            for _ in range(2):
                metadata = asyncio.run(get(f"/api/{kind}s/filters"))
                assert metadata.status_code == 200
                assert metadata.json()["seasons"] == [expected_year, 2015, 2022]
                search = asyncio.run(get(f"/api/{kind}s/search?q={query}"))
                assert search.status_code == 200
                assert search.json()["items"][0]["season"] == expected_season
                comparison = asyncio.run(get(f"/api/{kind}s/{selected_id}/compare"))
                assert comparison.status_code == 200
                assert {match["profile"]["season"] for match in comparison.json()["matches"]} == {
                    expected_season, "2015-16",
                }

    request_all(1997)
    assert len(resolvers) == 2
    assert sum(resolver.resolve_player_seasons.call_count for resolver in resolvers) == 1
    assert sum(resolver.resolve_team_seasons.call_count for resolver in resolvers) == 1
    assert build_options.call_count == 2

    old_signature = main.DatasetCatalog.from_environment().source_signature()
    if invalidation == "source_switch":
        database_path = tmp_path / "replacement.sqlite"
        seed_database(database_path)
        monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    previous_stat = database_path.stat()
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Player_Stats SET SEASON_ID = '1998-99' WHERE PLAYER_ID = 23")
        connection.execute("UPDATE Team_Stats SET SEASON_ID = '1998-99' WHERE TEAM_ID = 3")
    # Guarantee a distinct mtime even on file systems with coarse timestamp precision.
    os.utime(database_path, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000_000))
    assert main.DatasetCatalog.from_environment().source_signature() != old_signature

    request_all(1998)
    assert len(resolvers) == 4
    assert sum(resolver.resolve_player_seasons.call_count for resolver in resolvers) == 2
    assert sum(resolver.resolve_team_seasons.call_count for resolver in resolvers) == 2
    assert build_options.call_count == 4
