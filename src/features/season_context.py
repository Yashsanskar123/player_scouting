"""Season metadata and normalization for ScoutIQ's longitudinal analytics."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeasonMeta:
    season: int
    label: str
    short_label: str
    status: str = "completed"


def season_label(season: int) -> str:
    s = str(int(season))
    if len(s) != 4:
        return s
    start = int(s[:2])
    end = int(s[2:])
    start_year = 2000 + start
    end_year = 2000 + end
    return f"{start_year}/{str(end_year)[-2:]}"


def build_season_catalog(seasons: list[int] | tuple[int, ...], current: int | None = None) -> list[SeasonMeta]:
    ordered = sorted({int(s) for s in seasons})
    if not ordered:
        return []
    current = int(current if current is not None else ordered[-1])
    return [
        SeasonMeta(
            season=s,
            label=season_label(s),
            short_label=str(s),
            status="current" if s == current else "completed",
        )
        for s in ordered
    ]
