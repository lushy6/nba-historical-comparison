import pandas as pd
import pytest

from app.resolver import PLAYER_BASE_METRICS
from app.identity import VisualIdentityRecord
from app.scope import ComparisonScope
from app.similarity import ComparisonError, SimilarityEngine


def player_frame() -> pd.DataFrame:
    rows = []
    for profile_id, name, scale, ts_pct in (
        ("7:2022-23", "Aster Guard", 1.00, 0.595),
        ("11:2015-16", "Beacon Wing", 0.98, 0.591),
        ("23:1997-98", "Cinder Center", 0.42, 0.535),
    ):
        row = {
            "profile_id": profile_id,
            "name": name,
            "season": profile_id.split(":")[1],
            "ts_pct": ts_pct,
            "efg_pct": ts_pct - 0.02,
            "bpm": scale * 2,
        }
        row.update({feature: index * 10 * scale for index, feature in enumerate(PLAYER_BASE_METRICS, 1)})
        rows.append(row)
    return pd.DataFrame(rows)


def test_similarity_returns_the_closest_other_profile_with_a_bounded_score() -> None:
    result = SimilarityEngine().compare(
        player_frame(),
        selected_profile_id="7:2022-23",
        base_features=PLAYER_BASE_METRICS,
        advanced_features=("ts_pct", "efg_pct", "bpm"),
        scope=ComparisonScope(),
        kind="player",
    )

    assert result.selected.profile_id == "7:2022-23"
    assert result.matches[0].profile.profile_id == "11:2015-16"
    assert all(0 <= match.similarity_score <= 100 for match in result.matches)
    assert result.matches[0].rank == 1
    assert result.matches[0].tier == "Mirror"
    assert result.features_used[-3:] == ("ts_pct", "efg_pct", "bpm")


def test_similarity_returns_twelve_normalized_radar_dimensions() -> None:
    result = SimilarityEngine().compare(
        player_frame(),
        selected_profile_id="7:2022-23",
        base_features=PLAYER_BASE_METRICS,
        advanced_features=(),
        scope=ComparisonScope(),
        kind="player",
    )

    for match in result.matches:
        assert len(match.basic_metrics) == 12
        assert match.basic_metrics[0].metric == "three_point_attempts"
        assert all(0 <= point.selected_normalized <= 100 for point in match.basic_metrics)
        assert all(0 <= point.match_normalized <= 100 for point in match.basic_metrics)
        assert match.advanced_metrics == ()


def test_similarity_rejects_a_selection_without_another_complete_candidate() -> None:
    with pytest.raises(ComparisonError, match="No eligible historical alternatives"):
        SimilarityEngine().compare(
            player_frame().iloc[:1],
            selected_profile_id="7:2022-23",
            base_features=PLAYER_BASE_METRICS,
            advanced_features=(),
            scope=ComparisonScope(),
            kind="player",
        )


def test_similarity_excludes_unrecorded_era_metrics_without_imputing_zeroes() -> None:
    frame = pd.DataFrame(
        [
            {"profile_id": "old:1950", "name": "Old Star", "season": "1950", "points": 1300, "three_point_attempts": None},
            {"profile_id": "peer:1951", "name": "Old Peer", "season": "1951", "points": 1280, "three_point_attempts": None},
            {"profile_id": "modern:2023", "name": "Modern Guard", "season": "2023", "points": 500, "three_point_attempts": 600},
        ]
    )
    frame["bpm"] = [None, None, 2.0]

    result = SimilarityEngine().compare(
        frame,
        selected_profile_id="old:1950",
        base_features=("points", "three_point_attempts"),
        advanced_features=("bpm", "unavailable_advanced"),
        scope=ComparisonScope(),
        kind="player",
    )

    assert result.matches[0].profile.profile_id == "peer:1951"
    assert result.features_used == ("points",)
    for match in result.matches:
        assert [point.metric for point in match.basic_metrics] == ["points"]
        assert match.advanced_metrics == ()


def many_player_rows(count: int) -> pd.DataFrame:
    selected = {
        "profile_id": "selected:1990", "name": "Selected Player", "season": "1990",
        "team_codes": "LAL", "team_names": "Los Angeles Lakers", "points": 20, "bpm": 2,
    }
    candidates = [
        {
            **selected, "profile_id": f"peer-{index:02}:2000", "season": "2000",
            "team_codes": "CHI|BOS", "team_names": "Chicago Bulls|Boston Celtics",
        }
        for index in range(count)
    ]
    return pd.DataFrame([selected, *reversed(candidates)])


def test_similarity_returns_at_most_fifteen_scope_eligible_matches() -> None:
    frame = many_player_rows(18)
    extras = [
        {**frame.iloc[1], "profile_id": "too-old", "season": "1994"},
        {**frame.iloc[1], "profile_id": "too-new", "season": "2006"},
        {**frame.iloc[1], "profile_id": "wrong-team", "team_codes": "LAL"},
        {**frame.iloc[1], "profile_id": "incomplete-base", "points": None},
        {**frame.iloc[1], "profile_id": "incomplete-advanced", "bpm": None},
        {**frame.iloc[1], "profile_id": "selected:1990"},
        dict(frame.iloc[1]),
    ]
    frame = pd.concat([frame, pd.DataFrame(extras)], ignore_index=True)
    result = SimilarityEngine().compare(
        frame, selected_profile_id="selected:1990", base_features=("points",),
        advanced_features=("bpm",),
        scope=ComparisonScope(season_from=1995, season_to=2005, team="CHI"), kind="player",
    )

    assert result.selected.profile_id == "selected:1990"
    assert result.selected.team_codes == ("LAL",)
    assert len(result.matches) == 15
    assert [match.rank for match in result.matches] == list(range(1, 16))
    assert [match.profile.profile_id for match in result.matches] == [
        f"peer-{index:02}:2000" for index in range(15)
    ]
    assert result.eligible_count == 18
    for match in result.matches:
        assert match.profile.team_codes == ("CHI", "BOS")
        assert match.profile.team_names == ("Chicago Bulls", "Boston Celtics")
        assert match.similarity_score == 100
        assert match.basic_metrics[0].metric == "points"
        assert match.advanced_metrics[0].metric == "bpm"


def test_similarity_caps_an_oversized_limit_at_fifteen_matches() -> None:
    result = SimilarityEngine().compare(
        many_player_rows(18), selected_profile_id="selected:1990",
        base_features=("points",), advanced_features=(),
        scope=ComparisonScope(), kind="player", limit=16,
    )

    assert len(result.matches) == 15
    assert [match.rank for match in result.matches] == list(range(1, 16))
    assert result.eligible_count == 18


@pytest.mark.parametrize("limit", (0, -1))
def test_similarity_rejects_a_non_positive_limit(limit: int) -> None:
    with pytest.raises(ComparisonError, match="limit must be a positive integer"):
        SimilarityEngine().compare(
            many_player_rows(2), selected_profile_id="selected:1990",
            base_features=("points",), advanced_features=(),
            scope=ComparisonScope(), kind="player", limit=limit,
        )


def test_similarity_reports_no_eligible_alternative_after_scope() -> None:
    with pytest.raises(ComparisonError, match="No eligible historical alternatives"):
        SimilarityEngine().compare(
            player_frame(), selected_profile_id="7:2022-23",
            base_features=PLAYER_BASE_METRICS, advanced_features=(),
            scope=ComparisonScope(season_from=1900, season_to=1901), kind="player",
        )


def test_similarity_excludes_incomplete_candidates_without_imputing() -> None:
    frame = many_player_rows(2)
    frame.loc[frame["profile_id"] != "selected:1990", "bpm"] = None
    with pytest.raises(ComparisonError, match="No eligible historical alternatives"):
        SimilarityEngine().compare(
            frame, selected_profile_id="selected:1990", base_features=("points",),
            advanced_features=("bpm",), scope=ComparisonScope(), kind="player",
        )


def test_similarity_fits_scaler_to_complete_scoped_candidates_only() -> None:
    frame = pd.DataFrame([
        {"profile_id": "selected", "name": "Selected", "season": "1990", "points": 30, "bpm": 0},
        {"profile_id": "low", "name": "Low", "season": "2000", "points": 0, "bpm": 0},
        {"profile_id": "mid", "name": "Mid", "season": "2000", "points": 10, "bpm": 10},
        {"profile_id": "high", "name": "High", "season": "2000", "points": 20, "bpm": 0},
        {"profile_id": "outside", "name": "Outside", "season": "1900", "points": 900, "bpm": 900},
        {"profile_id": "incomplete", "name": "Incomplete", "season": "2000", "points": 900, "bpm": None},
    ])
    result = SimilarityEngine().compare(
        frame, selected_profile_id="selected", base_features=("points",),
        advanced_features=("bpm",), scope=ComparisonScope(season_from=2000), kind="player",
    )

    assert result.eligible_count == 3
    assert result.matches[0].profile.profile_id == "high"
    # Candidate mean=(10, 10/3), variance=(200/3, 200/9): cosine=3.5/sqrt(13).
    assert result.matches[0].similarity_score == 98.5
    assert result.matches[0].basic_metrics[0].match_normalized == 66.7
    assert result.matches[0].advanced_metrics[0].match_normalized == 0
    for match in result.matches:
        assert match.basic_metrics[0].selected_value == 30
        assert match.basic_metrics[0].selected_normalized == 100
        assert match.advanced_metrics[0].selected_value == 0
        assert match.advanced_metrics[0].selected_normalized == 0


def test_similarity_uses_all_eligible_candidates_for_domains_before_limit() -> None:
    frame = many_player_rows(3)
    frame.loc[frame["profile_id"] == "peer-02:2000", "points"] = 100
    result = SimilarityEngine().compare(
        frame, selected_profile_id="selected:1990", base_features=("points",),
        advanced_features=(), scope=ComparisonScope(), kind="player", limit=1,
    )
    assert len(result.matches) == 1
    assert result.eligible_count == 3
    assert result.matches[0].profile.profile_id == "peer-00:2000"
    assert result.matches[0].basic_metrics[0].selected_normalized == 0
    assert result.matches[0].basic_metrics[0].match_normalized == 0


@pytest.mark.parametrize("selected_value, expected_score", [(20, 100), (30, 50)])
def test_similarity_handles_constant_candidates_honestly(selected_value, expected_score) -> None:
    frame = many_player_rows(1)
    frame.loc[0, "points"] = selected_value
    result = SimilarityEngine().compare(
        frame, selected_profile_id="selected:1990", base_features=("points",),
        advanced_features=(), scope=ComparisonScope(), kind="player",
    )
    assert result.matches[0].similarity_score == expected_score


def test_similarity_supports_team_scope_and_optional_visual_identity_without_mutation() -> None:
    frame = many_player_rows(2)
    visual = VisualIdentityRecord(kind="team", nba_id="1610612741")
    frame["visual"] = [visual, None, None]
    original = frame.copy(deep=True)
    result = SimilarityEngine().compare(
        frame, selected_profile_id="selected:1990", base_features=("points",),
        advanced_features=(), scope=ComparisonScope(season_from=2000), kind="team",
    )
    assert result.selected.visual == visual
    assert result.matches[0].profile.visual is None
    assert result.eligible_count == 2
    pd.testing.assert_frame_equal(frame, original)


def multi_season_frame() -> pd.DataFrame:
    rows = []
    for profile_id, name, scale in (
        ("aster:2024", "Aster Guard", 1.00),
        ("aster:2023", "Aster Guard", 0.99),
        ("beacon:2016", "Beacon Wing", 0.97),
        ("cinder:1998", "Cinder Center", 0.40),
    ):
        row = {"profile_id": profile_id, "name": name, "season": profile_id.split(":")[1]}
        row.update({feature: index * 10 * scale for index, feature in enumerate(PLAYER_BASE_METRICS, 1)})
        rows.append(row)
    return pd.DataFrame(rows)


def _pool_ids(pool: str) -> list[str]:
    result = SimilarityEngine().compare(
        multi_season_frame(),
        selected_profile_id="aster:2024",
        base_features=PLAYER_BASE_METRICS,
        advanced_features=(),
        scope=ComparisonScope(pool=pool),
        kind="player",
    )
    return [match.profile.profile_id for match in result.matches]


def test_match_pool_all_includes_other_seasons_of_the_same_entity() -> None:
    assert set(_pool_ids("all")) == {"aster:2023", "beacon:2016", "cinder:1998"}


def test_match_pool_others_excludes_every_season_of_the_selected_entity() -> None:
    assert set(_pool_ids("others")) == {"beacon:2016", "cinder:1998"}


def test_match_pool_same_keeps_only_other_seasons_of_the_selected_entity() -> None:
    assert _pool_ids("same") == ["aster:2023"]


def test_match_pool_same_without_other_seasons_explains_the_empty_pool() -> None:
    with pytest.raises(ComparisonError, match="No eligible historical alternatives"):
        SimilarityEngine().compare(
            multi_season_frame(),
            selected_profile_id="beacon:2016",
            base_features=PLAYER_BASE_METRICS,
            advanced_features=(),
            scope=ComparisonScope(pool="same"),
            kind="player",
        )


def test_match_pool_filters_results_without_changing_the_scoring_yardstick() -> None:
    def scores(pool: str) -> dict[str, tuple[float, tuple]]:
        result = SimilarityEngine().compare(
            multi_season_frame(),
            selected_profile_id="aster:2024",
            base_features=PLAYER_BASE_METRICS,
            advanced_features=(),
            scope=ComparisonScope(pool=pool),
            kind="player",
        )
        return {
            match.profile.profile_id: (match.similarity_score, match.basic_metrics)
            for match in result.matches
        }

    everyone = scores("all")
    for pool in ("others", "same"):
        for profile_id, scored in scores(pool).items():
            assert scored == everyone[profile_id]
