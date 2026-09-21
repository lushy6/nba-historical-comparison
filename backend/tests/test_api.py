import asyncio
import sqlite3
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas import (
    AppliedScope,
    MetricGroups,
    PlayerComparisonResponse,
    PowerRanking,
    ProfileResponse,
    RankedMatch,
    VisualIdentity,
)


def seed_database(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Players (PERSON_ID INTEGER PRIMARY KEY, PLAYER_NAME TEXT NOT NULL);
            CREATE TABLE Player_Stats (
              PLAYER_ID INTEGER, SEASON_ID TEXT,
              FG3A REAL, FG3M REAL, FGA REAL, FGM REAL, PTS REAL, BLK REAL,
              TOV REAL, STL REAL, AST REAL, REB REAL, FTA REAL, FTM REAL,
              TS_PCT REAL, EFG_PCT REAL, USG_PCT REAL, BPM REAL, VORP REAL
            );
            CREATE TABLE Teams (TEAM_ID INTEGER PRIMARY KEY, TEAM_NAME TEXT NOT NULL);
            CREATE TABLE Team_Stats (
              TEAM_ID INTEGER, SEASON_ID TEXT,
              EFG_PCT REAL, TOV_PCT REAL, OREB_PCT REAL, FTA_RATE REAL,
              OFF_RATING REAL, DEF_RATING REAL, NET_RATING REAL, PACE REAL
            );

            INSERT INTO Players VALUES (7, 'Aster Guard'), (11, 'Beacon Wing'), (23, 'Cinder Center');
            INSERT INTO Player_Stats VALUES
              (7, '2022-23', 500,190,1000,480,1320,35,140,95,310,260,290,240,.595,.575,.235,2.3,1.2),
              (11,'2015-16', 490,184,990,474,1300,33,137,93,305,278,280,230,.591,.571,.232,2.1,1.0),
              (23,'1997-98', 45,13,850,500,1190,160,120,58,165,780,350,255,.608,.582,.220,2.8,1.6);

            INSERT INTO Teams VALUES (1, 'Aurora Comets'), (2, 'Harbor Pilots'), (3, 'Canyon Stars');
            INSERT INTO Team_Stats VALUES
              (1,'2022-23',.572,.123,.274,.201,116.2,110.4,5.8,99.1),
              (2,'2015-16',.568,.126,.269,.198,115.4,111.0,4.4,98.8),
              (3,'1997-98',.502,.152,.218,.171,101.2,114.3,-13.1,91.5);
            """
        )


async def get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def _profile(profile_id: str) -> ProfileResponse:
    return ProfileResponse(
        id=profile_id,
        name="Test Player",
        season="2022-23",
        visual=VisualIdentity(kind="player"),
    )


def _ranked_match(profile_id: str) -> RankedMatch:
    return RankedMatch(
        profile=_profile(profile_id),
        similarity_score=90,
        power_ranking=PowerRanking(rank=1, tier="Mirror"),
        metrics=MetricGroups(),
    )


def _comparison_kwargs(matches: list[RankedMatch]) -> dict[str, object]:
    return {
        "selected": _profile("selected:2022-23"),
        "match": _ranked_match("legacy:2022-23"),
        "matches": matches,
        "scope": AppliedScope(eligible_count=len(matches)),
        "features_used": [],
    }


def test_comparison_response_rejects_empty_or_overlong_match_lists() -> None:
    with pytest.raises(ValidationError):
        PlayerComparisonResponse(**_comparison_kwargs([]))

    with pytest.raises(ValidationError):
        PlayerComparisonResponse(
            **_comparison_kwargs([_ranked_match(f"match-{index}:2022-23") for index in range(16)])
        )


def test_comparison_response_uses_first_ranked_match_as_compatibility_match() -> None:
    first = _ranked_match("first:2022-23")
    response = PlayerComparisonResponse(
        **_comparison_kwargs([first, _ranked_match("second:2022-23")])
    )

    assert response.match == first


def test_player_search_and_comparison_return_typed_visual_data(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))

    search_response = asyncio.run(get("/api/players/search?q=aster"))
    comparison_response = asyncio.run(get("/api/players/7:2022-23/compare"))

    assert search_response.status_code == 200
    assert search_response.json()["items"] == [
        {
            "id": "7:2022-23", "name": "Aster Guard", "season": "2022-23", "kind": "player",
            "teams": [], "visual": {"kind": "player", "nba_id": None, "image_url": None},
        }
    ]
    comparison = comparison_response.json()
    assert comparison_response.status_code == 200
    match = comparison["matches"][0]
    assert comparison["match"] == match
    assert match["profile"]["id"] == "11:2015-16"
    assert 0 <= match["similarity_score"] <= 100
    assert match["power_ranking"]["tier"] == "Mirror"
    assert comparison["scope"]["eligible_count"] >= 1
    assert len(match["metrics"]["basic"]) == 12


def test_team_search_and_comparison_return_four_factor_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))

    search_response = asyncio.run(get("/api/teams/search?q=harbor"))
    comparison_response = asyncio.run(get("/api/teams/1:2022-23/compare"))

    assert search_response.status_code == 200
    assert search_response.json()["items"][0]["name"] == "Harbor Pilots"
    comparison = comparison_response.json()
    assert comparison_response.status_code == 200
    match = comparison["matches"][0]
    assert comparison["match"] == match
    assert match["profile"]["id"] == "2:2015-16"
    assert comparison["scope"]["eligible_count"] >= 1
    assert match["metrics"]["basic"][0]["metric"] == "effective_field_goal_pct"


@pytest.mark.parametrize("kind", ["player", "team"])
@pytest.mark.parametrize("identity_available", [False, True])
def test_search_and_comparison_share_team_and_identity_context(
    tmp_path: Path, monkeypatch, kind: str, identity_available: bool
) -> None:
    database_path = tmp_path / "nba.sqlite"
    seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            ALTER TABLE Player_Stats ADD COLUMN TEAM_ID TEXT;
            ALTER TABLE Player_Stats ADD COLUMN TEAM_NAME TEXT;
            UPDATE Player_Stats SET TEAM_ID = 'AUR', TEAM_NAME = 'Aurora Comets';
            INSERT INTO Player_Stats SELECT * FROM Player_Stats WHERE PLAYER_ID = 7;
            UPDATE Player_Stats SET TEAM_ID = 'HAR', TEAM_NAME = 'Harbor Pilots'
                WHERE rowid = (SELECT MAX(rowid) FROM Player_Stats);
            CREATE TABLE player (id INTEGER, full_name TEXT);
            CREATE TABLE team (id INTEGER, full_name TEXT);
            """
        )
        if identity_available:
            connection.executescript(
                """
                INSERT INTO player VALUES (7, 'Aster Guard'), (11, 'Beacon Wing'), (23, 'Cinder Center');
                INSERT INTO team VALUES (1, 'Aurora Comets'), (2, 'Harbor Pilots'), (3, 'Canyon Stars');
                """
            )
    monkeypatch.setenv("NBA_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("NBA_HISTORICAL_DATA_PATH", str(tmp_path / "not-present"))
    selected_id = "7:2022-23" if kind == "player" else "1:2022-23"
    response = asyncio.run(get(f"/api/{kind}s/{selected_id}/compare"))
    assert response.status_code == 200
    comparison = response.json()
    profiles = [comparison["selected"], *(match["profile"] for match in comparison["matches"])]
    for profile in profiles:
        search = asyncio.run(get(f"/api/{kind}s/search?q={profile['name']}"))
        assert search.status_code == 200
        assert search.json()["items"] == [{**profile, "kind": kind}]
        assert profile["teams"]
        assert profile["visual"]["kind"] == kind
        if identity_available:
            nba_id = profile["id"].split(":")[0]
            assert profile["visual"]["nba_id"] == nba_id
            expected_url = (
                f"https://cdn.nba.com/headshots/nba/latest/1040x760/{nba_id}.png"
                if kind == "player"
                else f"https://cdn.nba.com/logos/nba/{nba_id}/primary/L/logo.svg"
            )
            assert profile["visual"]["image_url"] == expected_url
        else:
            assert profile["visual"] == {"kind": kind, "nba_id": None, "image_url": None}
    if kind == "player":
        assert comparison["selected"]["teams"] == [
            {"code": "AUR", "name": "Aurora Comets"},
            {"code": "HAR", "name": "Harbor Pilots"},
        ]
