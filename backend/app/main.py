from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.catalog import DatasetCatalog
from app.resolver import SchemaResolutionError, SchemaResolver
from app.schemas import (
    PlayerComparisonResponse,
    ProfileResponse,
    PowerRanking,
    RadarMetric,
    SearchItem,
    SearchResponse,
    TeamComparisonResponse,
)
from app.similarity import ComparisonError, ComparisonResult, SimilarityEngine


app = FastAPI(
    title="NBA Historical Comparison API",
    version="0.1.0",
    description="Schema-discovered comparisons for the local NBA SQLite dataset.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=[],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return DatasetCatalog.from_environment().inspect().to_payload()


SearchQuery = Annotated[str, Query(min_length=2, max_length=100)]


@app.get("/api/players/search", response_model=SearchResponse)
def search_players(q: SearchQuery) -> SearchResponse:
    return _search(q, "player")


@app.get("/api/teams/search", response_model=SearchResponse)
def search_teams(q: SearchQuery) -> SearchResponse:
    return _search(q, "team")


@app.get("/api/players/{profile_id}/compare", response_model=PlayerComparisonResponse)
def compare_player(profile_id: str) -> PlayerComparisonResponse:
    try:
        resolved = _resolver().resolve_player_seasons()
        result = SimilarityEngine().compare(
            resolved.frame,
            selected_profile_id=profile_id,
            base_features=resolved.base_features,
            advanced_features=resolved.advanced_features,
        )
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ComparisonError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return PlayerComparisonResponse(
        **_comparison_payload(result),
        radar=[RadarMetric(**_metric_payload(point)) for point in result.radar],
    )


@app.get("/api/teams/{profile_id}/compare", response_model=TeamComparisonResponse)
def compare_team(profile_id: str) -> TeamComparisonResponse:
    try:
        resolved = _resolver().resolve_team_seasons()
        result = SimilarityEngine().compare(
            resolved.frame,
            selected_profile_id=profile_id,
            base_features=resolved.base_features,
            advanced_features=resolved.advanced_features,
        )
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ComparisonError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return TeamComparisonResponse(
        **_comparison_payload(result),
        metrics=[RadarMetric(**_metric_payload(point)) for point in result.radar],
    )


def _resolver() -> SchemaResolver:
    return SchemaResolver(DatasetCatalog.from_environment())


def _search(query: str, kind: Literal["player", "team"]) -> SearchResponse:
    try:
        resolved = (
            _resolver().resolve_player_seasons()
            if kind == "player"
            else _resolver().resolve_team_seasons()
        )
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    matches = resolved.frame.loc[
        resolved.frame["name"].str.contains(query, case=False, na=False, regex=False)
    ].head(12)
    return SearchResponse(
        items=[
            SearchItem(
                id=str(row.profile_id),
                name=str(row.name),
                season=str(row.season),
                kind=kind,
            )
            for row in matches.itertuples(index=False)
        ]
    )


def _comparison_payload(result: ComparisonResult) -> dict[str, object]:
    return {
        "selected": ProfileResponse(
            id=result.selected.profile_id,
            name=result.selected.name,
            season=result.selected.season,
        ),
        "match": ProfileResponse(
            id=result.match.profile_id,
            name=result.match.name,
            season=result.match.season,
        ),
        "similarity_score": result.similarity_score,
        "power_ranking": PowerRanking(rank=result.rank, tier=result.tier),
        "features_used": list(result.features_used),
    }


def _metric_payload(point) -> dict[str, object]:
    return {
        "metric": point.metric,
        "label": point.label,
        "selected_value": point.selected_value,
        "match_value": point.match_value,
        "selected_normalized": point.selected_normalized,
        "match_normalized": point.match_normalized,
    }
