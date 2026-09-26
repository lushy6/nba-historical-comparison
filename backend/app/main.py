"""NBA Historical Comparison API - scoped filter and rich comparison endpoints."""

from functools import lru_cache
from typing import Annotated, Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.catalog import DatasetCatalog
from app.identity import (
    LocalIdentityIndex,
    VisualIdentityRecord,
    fold_name,
    identity_index_for,
    image_url_for,
)
from app.resolver import SchemaResolutionError, SchemaResolver
from app.schemas import (
    AppliedScope,
    FilterOptionsResponse,
    MetricGroups,
    PlayerComparisonResponse,
    PowerRanking,
    ProfileResponse,
    RadarMetric,
    RankedMatch,
    SearchItem,
    SearchResponse,
    TeamComparisonResponse,
    TeamContext,
    VisualIdentity,
)
from app.scope import ComparisonScope, ScopeValidationError, filter_frame
from app.similarity import ComparisonError, RankedComparison, SeasonProfile, SimilarityEngine


EntityKind = Literal["player", "team"]

app = FastAPI(
    title="NBA Historical Comparison API",
    version="0.2.0",
    description="Scoped Top-15 similarity comparisons for NBA historical data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=[],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, object]:
    catalog = DatasetCatalog.from_environment()
    payload = catalog.inspect().to_payload()
    index = identity_index_for(catalog)
    payload["identity_available"] = index is not None
    payload["source_format"] = catalog.inspect().source_format
    return payload


# ---------------------------------------------------------------------------
# Shared query dependencies
# ---------------------------------------------------------------------------

SeasonFromQuery = Annotated[int | None, Query(ge=1946, le=2100, description="Inclusive first season year")]
SeasonToQuery = Annotated[int | None, Query(ge=1946, le=2100, description="Inclusive last season year")]
TeamQuery = Annotated[str | None, Query(min_length=1, max_length=10, description="Filter by team abbreviation")]
SearchQuery = Annotated[str, Query(min_length=2, max_length=100)]


def _build_player_scope(
    season_from: SeasonFromQuery = None,
    season_to: SeasonToQuery = None,
    team: TeamQuery = None,
) -> ComparisonScope:
    try:
        return ComparisonScope(season_from=season_from, season_to=season_to, team=team)
    except ScopeValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _build_team_scope(
    season_from: SeasonFromQuery = None,
    season_to: SeasonToQuery = None,
    team: TeamQuery = None,
) -> ComparisonScope:
    if team is not None:
        raise HTTPException(
            status_code=422,
            detail="Team filtering is only available for player comparisons.",
        )
    try:
        return ComparisonScope(season_from=season_from, season_to=season_to, team=None)
    except ScopeValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


PlayerScope = Annotated[ComparisonScope, Depends(_build_player_scope)]
TeamScope = Annotated[ComparisonScope, Depends(_build_team_scope)]


# ---------------------------------------------------------------------------
# Filter metadata endpoints
# ---------------------------------------------------------------------------


@app.get("/api/players/filters", response_model=FilterOptionsResponse)
def player_filters() -> FilterOptionsResponse:
    try:
        return _filter_metadata("player")
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/teams/filters", response_model=FilterOptionsResponse)
def team_filters() -> FilterOptionsResponse:
    try:
        return _filter_metadata("team")
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


# ---------------------------------------------------------------------------
# Search endpoints
# ---------------------------------------------------------------------------


@app.get("/api/players/search", response_model=SearchResponse)
def search_players(q: SearchQuery, scope: PlayerScope) -> SearchResponse:
    return _search(q, "player", scope)


@app.get("/api/teams/search", response_model=SearchResponse)
def search_teams(q: SearchQuery, scope: TeamScope) -> SearchResponse:
    return _search(q, "team", scope)


# ---------------------------------------------------------------------------
# Compare endpoints
# ---------------------------------------------------------------------------


@app.get("/api/players/{profile_id}/compare", response_model=PlayerComparisonResponse)
def compare_player(profile_id: str, scope: PlayerScope) -> PlayerComparisonResponse:
    return _compare(profile_id, scope, kind="player")  # type: ignore[return-value]


@app.get("/api/teams/{profile_id}/compare", response_model=TeamComparisonResponse)
def compare_team(profile_id: str, scope: TeamScope) -> TeamComparisonResponse:
    return _compare(profile_id, scope, kind="team")  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolver() -> SchemaResolver:
    return SchemaResolver(DatasetCatalog.from_environment())


def _season_frame(kind: EntityKind):
    catalog = DatasetCatalog.from_environment()
    return _cached_season_frame(kind, catalog.source_signature())


@lru_cache(maxsize=8)
def _cached_season_frame(kind: EntityKind, source_signature: tuple[str, ...]):
    resolver = _resolver()
    if kind == "player":
        return resolver.resolve_player_seasons()
    return resolver.resolve_team_seasons()


def _filter_metadata(kind: EntityKind) -> FilterOptionsResponse:
    catalog = DatasetCatalog.from_environment()
    return _cached_filter_options(kind, catalog.source_signature())


@lru_cache(maxsize=8)
def _cached_filter_options(
    kind: EntityKind, source_signature: tuple[str, ...]
) -> FilterOptionsResponse:
    resolved = _cached_season_frame(kind, source_signature)
    return _filter_options(resolved.frame, kind=kind)


def _filter_options(frame: pd.DataFrame, *, kind: EntityKind) -> FilterOptionsResponse:
    seasons = _season_options(frame)
    if kind != "player":
        return FilterOptionsResponse(seasons=seasons)

    teams: list[TeamContext] = []
    team_filter_available = False
    if "team_codes" in frame.columns and "team_names" in frame.columns:
        code_map: dict[str, str] = {}
        for _, row in frame.iterrows():
            codes = _split_pipe(str(row.get("team_codes") or ""))
            names = _split_pipe(str(row.get("team_names") or ""))
            for code, name in zip(codes, names):
                if code and name and code not in code_map:
                    code_map[code] = name
        teams = [TeamContext(code=c, name=n) for c, n in sorted(code_map.items(), key=lambda x: x[1])]
        team_filter_available = bool(teams)

    return FilterOptionsResponse(
        seasons=seasons,
        teams=teams,
        team_filter_available=team_filter_available,
    )


def _season_options(frame: pd.DataFrame) -> list[int]:
    values = frame["season"].astype("string").str.extract(r"^(\d{4})", expand=False)
    return sorted({int(v) for v in values.dropna()})


def _search(query: str, kind: EntityKind, scope: ComparisonScope) -> SearchResponse:
    try:
        resolved = _season_frame(kind)
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        scoped = filter_frame(resolved.frame, scope, kind=kind)
    except ScopeValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    normalized_query = _searchable_text(query)
    matches = scoped.loc[
        scoped["name"].map(_searchable_text).str.contains(normalized_query, na=False, regex=False)
    ].head(12)
    index = identity_index_for(DatasetCatalog.from_environment())

    return SearchResponse(
        items=[
            SearchItem(
                **_profile_payload(SimilarityEngine._profile(row), kind, index).model_dump(),
                kind=kind,
            )
            for _, row in matches.iterrows()
        ]
    )


def _compare(profile_id: str, scope: ComparisonScope, *, kind: EntityKind):
    try:
        resolved = _season_frame(kind)
        result = SimilarityEngine().compare(
            resolved.frame,
            selected_profile_id=profile_id,
            base_features=resolved.base_features,
            advanced_features=resolved.advanced_features,
            scope=scope,
            kind=kind,
        )
    except SchemaResolutionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ComparisonError as error:
        detail = str(error)
        if "not found" in detail:
            raise HTTPException(status_code=404, detail=detail) from error
        raise HTTPException(status_code=422, detail=detail) from error

    catalog = DatasetCatalog.from_environment()
    index = identity_index_for(catalog)

    matches = [_ranked_match_payload(m, kind, index) for m in result.matches]
    response_cls = PlayerComparisonResponse if kind == "player" else TeamComparisonResponse
    return response_cls(
        selected=_profile_payload(result.selected, kind, index),
        match=matches[0],
        matches=matches,
        scope=AppliedScope(
            season_from=scope.season_from,
            season_to=scope.season_to,
            team=scope.team,
            eligible_count=result.eligible_count,
        ),
        features_used=list(result.features_used),
    )


def _ranked_match_payload(
    match: RankedComparison,
    kind: EntityKind,
    index: LocalIdentityIndex | None,
) -> RankedMatch:
    return RankedMatch(
        profile=_profile_payload(match.profile, kind, index),
        similarity_score=match.similarity_score,
        power_ranking=PowerRanking(rank=match.rank, tier=match.tier),
        metrics=MetricGroups(
            basic=[_metric_payload(p) for p in match.basic_metrics],
            advanced=[_metric_payload(p) for p in match.advanced_metrics],
        ),
    )


def _profile_payload(
    profile: SeasonProfile,
    kind: EntityKind,
    index: LocalIdentityIndex | None,
) -> ProfileResponse:
    teams = [
        TeamContext(code=code, name=name)
        for code, name in zip(profile.team_codes, profile.team_names)
    ]
    identity_record: VisualIdentityRecord | None = profile.visual
    if identity_record is None and index is not None:
        identity_record = index.resolve(kind, profile.name)

    if identity_record is not None:
        visual = VisualIdentity(
            kind=kind,
            nba_id=identity_record.nba_id,
            image_url=image_url_for(identity_record),
        )
    else:
        visual = VisualIdentity(kind=kind)

    return ProfileResponse(
        id=profile.profile_id,
        name=profile.name,
        season=profile.season,
        teams=teams,
        visual=visual,
    )


def _metric_payload(point) -> RadarMetric:
    return RadarMetric(
        metric=point.metric,
        label=point.label,
        selected_value=point.selected_value,
        match_value=point.match_value,
        selected_normalized=point.selected_normalized,
        match_normalized=point.match_normalized,
    )


def _split_pipe(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()] if value else []


def _searchable_text(value: object) -> str:
    return fold_name(value)
