import pandas as pd
import pytest

from app.resolver import PLAYER_BASE_METRICS
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
    )

    assert result.selected.profile_id == "7:2022-23"
    assert result.match.profile_id == "11:2015-16"
    assert 0 <= result.similarity_score <= 100
    assert result.rank == 1
    assert result.tier == "Mirror"
    assert result.features_used[-3:] == ("ts_pct", "efg_pct", "bpm")


def test_similarity_returns_twelve_normalized_radar_dimensions() -> None:
    result = SimilarityEngine().compare(
        player_frame(),
        selected_profile_id="7:2022-23",
        base_features=PLAYER_BASE_METRICS,
        advanced_features=(),
    )

    assert len(result.radar) == 12
    assert result.radar[0].metric == "three_point_attempts"
    assert all(0 <= point.selected_normalized <= 100 for point in result.radar)
    assert all(0 <= point.match_normalized <= 100 for point in result.radar)


def test_similarity_rejects_a_selection_without_another_complete_candidate() -> None:
    with pytest.raises(ComparisonError, match="at least two complete profiles"):
        SimilarityEngine().compare(
            player_frame().iloc[:1],
            selected_profile_id="7:2022-23",
            base_features=PLAYER_BASE_METRICS,
            advanced_features=(),
        )
