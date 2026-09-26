"""Pure, testable similarity calculations for normalized NBA season profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from app.identity import VisualIdentityRecord
from app.scope import ComparisonScope, filter_frame, filter_match_pool


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
    team_codes: tuple[str, ...] = ()
    team_names: tuple[str, ...] = ()
    visual: VisualIdentityRecord | None = None


@dataclass(frozen=True)
class RadarPoint:
    metric: str
    label: str
    selected_value: float
    match_value: float
    selected_normalized: float
    match_normalized: float


@dataclass(frozen=True)
class MetricGroups:
    basic: tuple[RadarPoint, ...]
    advanced: tuple[RadarPoint, ...]


@dataclass(frozen=True)
class RankedComparison:
    profile: SeasonProfile
    similarity_score: float
    rank: int
    tier: str
    metrics: MetricGroups

    @property
    def basic_metrics(self) -> tuple[RadarPoint, ...]:
        return self.metrics.basic

    @property
    def advanced_metrics(self) -> tuple[RadarPoint, ...]:
        return self.metrics.advanced


@dataclass(frozen=True)
class ComparisonResult:
    selected: SeasonProfile
    matches: tuple[RankedComparison, ...]
    eligible_count: int
    features_used: tuple[str, ...]


class SimilarityEngine:
    """Compare one profile to all other complete profiles in a normalized data frame."""

    def compare(
        self,
        frame: pd.DataFrame,
        *,
        selected_profile_id: str,
        base_features: Sequence[str],
        advanced_features: Sequence[str],
        scope: ComparisonScope,
        kind: Literal["player", "team"],
        limit: int = 15,
    ) -> ComparisonResult:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ComparisonError("The comparison result limit must be a positive integer.")
        limit = min(limit, 15)

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

        usable_base = tuple(
            feature
            for feature in base_features
            if pd.notna(selected[feature])
        )
        if not usable_base:
            raise ComparisonError("The requested profile has no recorded base measures to compare.")

        usable_advanced = tuple(
            feature
            for feature in advanced_features
            if feature in frame.columns and pd.notna(selected[feature])
        )
        features = tuple((*usable_base, *usable_advanced))
        scoped_candidates = filter_frame(
            frame.loc[frame["profile_id"] != selected_profile_id], scope, kind=kind
        ).dropna(subset=list(features)).drop_duplicates(subset=["profile_id"], keep="first")
        # The match pool narrows which profiles are ranked, not the yardstick: scaling and
        # radar domains come from the season/team scope, so a season scores the same
        # whether or not the selected entity's other seasons are listed beside it.
        complete_candidates = filter_match_pool(scoped_candidates, selected_profile_id, scope.pool)
        if complete_candidates.empty:
            raise ComparisonError(
                "No eligible historical alternatives remain for the selected filters."
            )

        scaler = StandardScaler().fit(scoped_candidates.loc[:, features])
        candidate_values = scaler.transform(complete_candidates.loc[:, features])
        selected_values = scaler.transform(selected.to_frame().T.loc[:, features])
        similarities = cosine_similarity(selected_values, candidate_values).ravel()

        # If every requested feature is constant, standardized values are zero. Identical
        # profiles are still a perfect match; no statistical signal means no invented gap.
        candidate_zero_norm = np.linalg.norm(candidate_values, axis=1) == 0
        selected_zero_norm = np.linalg.norm(selected_values[0]) == 0
        if selected_zero_norm:
            similarities[candidate_zero_norm] = 1.0

        ranking = pd.DataFrame(
            {
                "profile_id": complete_candidates["profile_id"].astype(str).to_numpy(),
                "similarity": similarities,
                "source_order": np.arange(len(complete_candidates)),
            }
        ).sort_values(
            ["similarity", "profile_id"], ascending=[False, True], kind="stable"
        ).head(limit)

        domain_profiles = pd.concat(
            [selected.to_frame().T.loc[:, features], scoped_candidates.loc[:, features]]
        )
        domains = {
            feature: (float(domain_profiles[feature].min()), float(domain_profiles[feature].max()))
            for feature in features
        }
        matches: list[RankedComparison] = []
        for rank, entry in enumerate(ranking.itertuples(index=False), 1):
            match = complete_candidates.iloc[entry.source_order]
            score = round((float(entry.similarity) + 1) * 50, 1)
            matches.append(
                RankedComparison(
                    profile=self._profile(match),
                    similarity_score=score,
                    rank=rank,
                    tier=similarity_tier(score),
                    metrics=MetricGroups(
                        basic=self._radar(domains, selected, match, usable_base),
                        advanced=self._radar(domains, selected, match, usable_advanced),
                    ),
                )
            )

        return ComparisonResult(
            selected=self._profile(selected),
            matches=tuple(matches),
            eligible_count=len(complete_candidates),
            features_used=features,
        )

    @staticmethod
    def _profile(row: pd.Series) -> SeasonProfile:
        return SeasonProfile(
            profile_id=str(row["profile_id"]),
            name=str(row["name"]),
            season=str(row["season"]),
            team_codes=_team_values(row.get("team_codes")),
            team_names=_team_values(row.get("team_names")),
            visual=row.get("visual") if isinstance(row.get("visual"), VisualIdentityRecord) else None,
        )

    @staticmethod
    def _radar(
        domains: dict[str, tuple[float, float]],
        selected: pd.Series,
        match: pd.Series,
        features: tuple[str, ...],
    ) -> tuple[RadarPoint, ...]:
        points: list[RadarPoint] = []
        for feature in features:
            minimum, maximum = domains[feature]
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


def _team_values(value: object) -> tuple[str, ...]:
    return tuple(value.split("|")) if isinstance(value, str) and value else ()


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
