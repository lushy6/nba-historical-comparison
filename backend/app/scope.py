"""Pure comparison-scope validation and DataFrame filtering."""

from dataclasses import dataclass
import re
from typing import Literal

import pandas as pd


class ScopeValidationError(ValueError):
    """Raised when a requested comparison scope is invalid."""


@dataclass(frozen=True)
class ComparisonScope:
    season_from: int | None = None
    season_to: int | None = None
    team: str | None = None

    def __post_init__(self) -> None:
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
