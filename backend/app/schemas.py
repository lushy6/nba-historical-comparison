"""Typed public responses for the comparison API."""

from pydantic import BaseModel, Field


class SearchItem(BaseModel):
    id: str
    name: str
    season: str
    kind: str


class SearchResponse(BaseModel):
    items: list[SearchItem]


class ProfileResponse(BaseModel):
    id: str
    name: str
    season: str


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


class PlayerComparisonResponse(BaseModel):
    selected: ProfileResponse
    match: ProfileResponse
    similarity_score: float = Field(ge=0, le=100)
    power_ranking: PowerRanking
    features_used: list[str]
    radar: list[RadarMetric]


class TeamComparisonResponse(BaseModel):
    selected: ProfileResponse
    match: ProfileResponse
    similarity_score: float = Field(ge=0, le=100)
    power_ranking: PowerRanking
    features_used: list[str]
    metrics: list[RadarMetric]
