import pandas as pd
import pytest

from app.scope import ComparisonScope, ScopeValidationError, filter_frame


def player_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"profile_id": "a:1997", "season": "1997", "team_codes": "CHI|WAS"},
            {"profile_id": "b:1998", "season": "1998", "team_codes": "LAL"},
            {"profile_id": "c:2001", "season": "2001", "team_codes": "CHI"},
        ]
    )


def test_player_scope_is_inclusive_and_matches_any_affiliation() -> None:
    filtered = filter_frame(
        player_frame(),
        ComparisonScope(season_from=1997, season_to=1998, team="CHI"),
        kind="player",
    )
    assert filtered["profile_id"].tolist() == ["a:1997"]


def test_scope_uses_the_leading_year_of_hyphenated_seasons() -> None:
    frame = pd.DataFrame(
        [
            {"profile_id": "a:2022-23", "season": "2022-23", "team_codes": "CHI"},
            {"profile_id": "b:2026", "season": "2026", "team_codes": "LAL"},
        ]
    )

    filtered = filter_frame(
        frame, ComparisonScope(season_from=2022, season_to=2022), kind="player"
    )

    assert filtered["profile_id"].tolist() == ["a:2022-23"]


def test_team_scope_rejects_team_filter() -> None:
    with pytest.raises(ScopeValidationError, match="only available for player"):
        filter_frame(player_frame(), ComparisonScope(None, None, "CHI"), kind="team")


def test_scope_rejects_reversed_range() -> None:
    with pytest.raises(ScopeValidationError, match="must not exceed"):
        ComparisonScope(season_from=2000, season_to=1999, team=None)
