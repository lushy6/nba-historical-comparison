"""Typed public responses for the comparison API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator


class SearchItem(BaseModel):
    id: str
    name: str
    season: str
    kind: str


class SearchResponse(BaseModel):
    items: list[SearchItem] = Field(default_factory=list)


class VisualIdentity(BaseModel):
    kind: Literal["player", "team"]
    nba_id: str | None = None
    image_url: str | None = None


class TeamContext(BaseModel):
    code: str
    name: str


class FilterOptionsResponse(BaseModel):
    seasons: list[int] = Field(default_factory=list)
    teams: list[TeamContext] = Field(default_factory=list)
    team_filter_available: bool = False


class ProfileResponse(BaseModel):
    id: str
    name: str
    season: str
    teams: list[TeamContext] = Field(default_factory=list)
    visual: VisualIdentity = Field(
        default_factory=lambda: VisualIdentity(kind="player")
    )


class PowerRanking(BaseModel):
    rank: int = Field(ge=1)
    tier: str


class RadarMetric(BaseModel):
    metric: str
    label: str
    selected_value: float
    match_value: float
    selected_normalized: float = Field(ge=0, le=100)
    match_normalized: float = Field(ge=0, le=100)


class MetricGroups(BaseModel):
    basic: list[RadarMetric] = Field(default_factory=list)
    advanced: list[RadarMetric] = Field(default_factory=list)


class RankedMatch(BaseModel):
    profile: ProfileResponse
    similarity_score: float = Field(ge=0, le=100)
    power_ranking: PowerRanking
    metrics: MetricGroups


class AppliedScope(BaseModel):
    season_from: int | None = None
    season_to: int | None = None
    team: str | None = None
    eligible_count: int = Field(ge=0)


class _ComparisonResponse(BaseModel):
    """Migration contract shared by player and team comparison responses.

    Task 5 will perform the fully scoped route-level mapping. Until then this
    adapter lets the existing single-result route publish the canonical shape
    without duplicating similarity domain objects in the transport layer.
    """

    entity_kind: ClassVar[Literal["player", "team"]]

    selected: ProfileResponse
    match: RankedMatch
    matches: list[RankedMatch] = Field(min_length=1, max_length=15)
    scope: AppliedScope
    features_used: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _adapt_legacy_single_match(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data

        payload = dict(data)
        legacy_match = payload.get("match")
        if legacy_match is not None and not _is_ranked_match(legacy_match):
            basic_metrics = payload.pop("radar", payload.pop("metrics", []))
            ranked_match = {
                "profile": legacy_match,
                "similarity_score": payload.pop("similarity_score"),
                "power_ranking": payload.pop("power_ranking"),
                "metrics": {"basic": basic_metrics, "advanced": []},
            }
            payload["match"] = ranked_match
            payload["matches"] = [ranked_match]
            payload["scope"] = {"eligible_count": 1}
        elif payload.get("matches"):
            payload["match"] = payload["matches"][0]

        return payload

    @model_validator(mode="after")
    def _make_first_match_compatible(self) -> _ComparisonResponse:
        self.match = self.matches[0]
        _set_profile_kind(self.selected, self.entity_kind)
        for ranked_match in self.matches:
            _set_profile_kind(ranked_match.profile, self.entity_kind)
        return self


class PlayerComparisonResponse(_ComparisonResponse):
    entity_kind: ClassVar[Literal["player", "team"]] = "player"


class TeamComparisonResponse(_ComparisonResponse):
    entity_kind: ClassVar[Literal["player", "team"]] = "team"


def _is_ranked_match(value: object) -> bool:
    if isinstance(value, RankedMatch):
        return True
    return isinstance(value, Mapping) and "profile" in value


def _set_profile_kind(profile: ProfileResponse, kind: Literal["player", "team"]) -> None:
    profile.visual = profile.visual.model_copy(update={"kind": kind})
