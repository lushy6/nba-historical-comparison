"""Pure comparison-scope validation and DataFrame filtering."""

from dataclasses import dataclass
import re
from typing import Literal

import pandas as pd


class ScopeValidationError(ValueError):
    """Raised when a requested comparison scope is invalid."""


# Whether matches may include other seasons of the selected player or team:
# "all" allows both, "others" excludes the same entity, "same" keeps only it.
MatchPool = Literal["all", "others", "same"]
MATCH_POOLS: tuple[MatchPool, ...] = ("all", "others", "same")


@dataclass(frozen=True)
class ComparisonScope:
    season_from: int | None = None
    season_to: int | None = None
    team: str | None = None
    pool: MatchPool = "all"

    def __post_init__(self) -> None:
        if self.pool not in MATCH_POOLS:
            raise ScopeValidationError(
                "The match pool must be one of: " + ", ".join(MATCH_POOLS) + "."
            )
        if (
            self.season_from is not None
            and self.season_to is not None
            and self.season_from > self.season_to
        ):
            raise ScopeValidationError("The first season must not exceed the last season.")
        if self.team is not None:
            object.__setattr__(self, "team", self.team.upper())


def filter_frame(
    frame: pd.DataFrame,
    scope: ComparisonScope,
    *,
    kind: Literal["player", "team"],
) -> pd.DataFrame:
    """Return an independent frame containing rows eligible under ``scope``."""
    if kind == "team" and scope.team:
        raise ScopeValidationError("Team filtering is only available for player comparisons.")

    seasons = frame["season"].astype("string").str.extract(r"^(\d{4})", expand=False)
    mask = pd.Series(True, index=frame.index)
    if scope.season_from is not None:
        mask &= seasons.astype("Int64") >= scope.season_from
    if scope.season_to is not None:
        mask &= seasons.astype("Int64") <= scope.season_to
    if scope.team:
        escaped = re.escape(scope.team)
        mask &= frame["team_codes"].astype("string").str.contains(
            rf"(?:^|\|){escaped}(?:\||$)", regex=True, na=False
        )
    return frame.loc[mask].copy()


def entity_key(profile_id: object) -> str:
    """The player or team behind a ``<entity>:<season>`` profile ID."""
    return str(profile_id).rsplit(":", 1)[0]


def filter_match_pool(
    candidates: pd.DataFrame, selected_profile_id: str, pool: MatchPool
) -> pd.DataFrame:
    """Keep candidates allowed by ``pool`` relative to the selected profile's entity."""
    if pool == "all":
        return candidates
    same_entity = candidates["profile_id"].map(entity_key) == entity_key(selected_profile_id)
    return candidates.loc[same_entity if pool == "same" else ~same_entity]
