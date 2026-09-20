"""Pure, testable similarity calculations for normalized NBA season profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler


RADAR_LABELS = {
    "three_point_attempts": "3PA",
    "three_point_made": "3PM",
    "field_goal_attempts": "FGA",
    "field_goals_made": "FGM",
    "points": "PTS",
    "blocks": "BLK",
    "turnovers": "TOV",
    "steals": "STL",
    "assists": "AST",
    "rebounds": "REB",
    "free_throw_attempts": "FTA",
    "free_throws_made": "FTM",
}


class ComparisonError(ValueError):
    """Raised for a valid request that cannot produce an honest comparison."""


@dataclass(frozen=True)
class SeasonProfile:
    profile_id: str
    name: str
    season: str


@dataclass(frozen=True)
class RadarPoint:
    metric: str
    label: str
    selected_value: float
    match_value: float
    selected_normalized: float
    match_normalized: float


@dataclass(frozen=True)
class ComparisonResult:
    selected: SeasonProfile
    match: SeasonProfile
    similarity_score: float
    rank: int
    tier: str
    features_used: tuple[str, ...]
    radar: tuple[RadarPoint, ...]


class SimilarityEngine:
    """Compare one profile to all other complete profiles in a normalized data frame."""

    def compare(
        self,
        frame: pd.DataFrame,
        *,
        selected_profile_id: str,
        base_features: Sequence[str],
        advanced_features: Sequence[str],
    ) -> ComparisonResult:
        selected_rows = frame.loc[frame["profile_id"] == selected_profile_id]
        if selected_rows.empty:
            raise ComparisonError("The requested profile was not found in the resolved dataset.")
        selected = selected_rows.iloc[0]

        missing_base = [feature for feature in base_features if feature not in frame.columns]
        if missing_base:
            raise ComparisonError(
                "The resolved dataset is missing required comparison measures: "
                + ", ".join(missing_base)
                + "."
            )

        usable_advanced = tuple(
            feature
            for feature in advanced_features
            if feature in frame.columns and pd.notna(selected[feature])
        )
        features = tuple((*base_features, *usable_advanced))
        complete_profiles = frame.dropna(subset=list(features)).copy()
        complete_profiles = complete_profiles.drop_duplicates(subset=["profile_id"], keep="first")

        if (
            selected_profile_id not in set(complete_profiles["profile_id"])
            or len(complete_profiles) < 2
        ):
            raise ComparisonError("A comparison needs at least two complete profiles.")

        selected_index = complete_profiles.index[
            complete_profiles["profile_id"] == selected_profile_id
        ][0]
        scaled_values = StandardScaler().fit_transform(complete_profiles.loc[:, features])
        selected_position = complete_profiles.index.get_loc(selected_index)
        similarities = cosine_similarity(
            scaled_values[[selected_position]], scaled_values
        ).ravel()
        similarities[selected_position] = -np.inf

        # If every requested feature is constant, standardized values are zero. Identical
        # profiles are still a perfect match; no statistical signal means no invented gap.
        zero_norm = np.linalg.norm(scaled_values, axis=1) == 0
        if zero_norm[selected_position]:
            similarities[zero_norm] = 1.0
            similarities[selected_position] = -np.inf

        best_position = int(np.argmax(similarities))
        best_similarity = float(similarities[best_position])
        match = complete_profiles.iloc[best_position]
        score = round((best_similarity + 1) * 50, 1)

        return ComparisonResult(
            selected=self._profile(selected),
            match=self._profile(match),
            similarity_score=score,
            rank=1,
            tier=similarity_tier(score),
            features_used=features,
            radar=self._radar(
                complete_profiles,
                selected,
                match,
                tuple(base_features),
            ),
        )

    @staticmethod
    def _profile(row: pd.Series) -> SeasonProfile:
        return SeasonProfile(
            profile_id=str(row["profile_id"]),
            name=str(row["name"]),
            season=str(row["season"]),
        )

    @staticmethod
    def _radar(
        complete_profiles: pd.DataFrame,
        selected: pd.Series,
        match: pd.Series,
        base_features: tuple[str, ...],
    ) -> tuple[RadarPoint, ...]:
        points: list[RadarPoint] = []
        for feature in base_features:
            minimum = float(complete_profiles[feature].min())
            maximum = float(complete_profiles[feature].max())
            points.append(
                RadarPoint(
                    metric=feature,
                    label=RADAR_LABELS.get(feature, feature.replace("_", " ").title()),
                    selected_value=float(selected[feature]),
                    match_value=float(match[feature]),
                    selected_normalized=_normalize(float(selected[feature]), minimum, maximum),
                    match_normalized=_normalize(float(match[feature]), minimum, maximum),
                )
            )
        return tuple(points)


def similarity_tier(score: float) -> str:
    if score >= 90:
        return "Mirror"
    if score >= 84:
        return "Strong echo"
    if score >= 75:
        return "Shared shape"
    return "Distant cousin"


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if minimum == maximum:
        return 50.0
    return round((value - minimum) / (maximum - minimum) * 100, 1)
