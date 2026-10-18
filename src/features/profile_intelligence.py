from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.search_intelligence import canonical_player_season


COMPONENTS = [
    "attacking",
    "chance_creation",
    "passing",
    "progression",
    "defending",
    "physical",
    "goalkeeping",
]

MIN_MINUTES_FOR_TREND = 900


def _num(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _slope(values: pd.Series) -> float | None:
    vals = pd.to_numeric(values, errors="coerce").dropna()

    if len(vals) < 2:
        return None

    x = np.arange(len(vals), dtype=float)

    return float(
        np.polyfit(
            x,
            vals.to_numpy(dtype=float),
            1,
        )[0]
    )


def _unique_sequence(values) -> list[str]:
    out: list[str] = []

    for value in values:
        if value is None or pd.isna(value):
            continue

        text = str(value)

        if text and text not in out:
            out.append(text)

    return out


def build_profile_intelligence(
    facts: pd.DataFrame,
    player_id: str,
    season: int,
) -> dict:
    """
    Build season-aware longitudinal intelligence for one player.

    This layer is descriptive rather than predictive. It summarizes
    observed history through the selected season and exposes transparent
    windows, trends, consistency, role changes and component evolution.
    """

    df = canonical_player_season(facts)

    if df.empty:
        return {
            "player_id": player_id,
            "season": season,
            "available": False,
        }

    # Never use seasons after the selected analysis season.
    df = df[
        pd.to_numeric(df["season"], errors="coerce") <= int(season)
    ].copy()

    matches = (
        df[df["player_id"] == player_id]
        .sort_values("season")
        .copy()
    )

    if matches.empty:
        return {
            "player_id": player_id,
            "season": season,
            "available": False,
        }

    seasons = matches["season"].astype(int).tolist()

    last3 = set(seasons[-3:])
    last5 = set(seasons[-5:])

    perf = pd.to_numeric(
        matches.get("performance_score"),
        errors="coerce",
    )

    mins = pd.to_numeric(
        matches.get("playing_time_min"),
        errors="coerce",
    ).fillna(0)

    recent3 = perf[
        matches["season"].isin(last3)
    ].dropna()

    recent5 = perf[
        matches["season"].isin(last5)
    ].dropna()

    # Only meaningful playing-time seasons are used for trend calculation.
    trend_eligible = matches[
        mins >= MIN_MINUTES_FOR_TREND
    ].copy()

    trend_perf = pd.to_numeric(
        trend_eligible.get("performance_score"),
        errors="coerce",
    ).dropna()

    peak_idx = (
        perf.idxmax()
        if perf.notna().any()
        else None
    )

    selected_rows = matches[
        matches["season"] == int(season)
    ]

    selected = (
        selected_rows.iloc[-1]
        if not selected_rows.empty
        else matches.iloc[-1]
    )

    trajectory = []

    for _, row in matches.iterrows():
        item = {
            "season": int(row["season"]),
            "age": _num(row.get("age_fifa")),
            "performance": _num(row.get("performance_score")),
            "potential": _num(row.get("development_potential")),
            "expected_12m": _num(
                row.get("expected_performance_12m")
            ),
            "minutes": _num(
                row.get("playing_time_min")
            ),
            "market_value": _num(
                row.get("value_eur")
            ),
            "fair_value": _num(
                row.get("fair_value_eur")
            ),
            "position": row.get("canonical_position"),
            "club": row.get("club_name"),
            "league": row.get("league_name"),
        }

        for component in COMPONENTS:
            col = f"component_{component}"

            if col in matches.columns:
                item[component] = _num(
                    row.get(col)
                )

        trajectory.append(item)

    # Existing position/season-aware component scores.
    component_evolution = []

    for component in COMPONENTS:
        col = f"component_{component}"

        if col not in matches.columns:
            continue

        values = pd.to_numeric(
            matches[col],
            errors="coerce",
        )

        valid = values.dropna()

        if valid.empty:
            continue

        component_evolution.append(
            {
                "component": component,
                "current": _num(values.iloc[-1]),
                "first": _num(values.iloc[0]),
                "change": (
                    _num(values.iloc[-1] - values.iloc[0])
                    if len(valid) >= 2
                    else None
                ),
                "trend_per_season": _slope(values),
            }
        )

    positions = _unique_sequence(
        matches.get(
            "canonical_position",
            pd.Series(dtype=object),
        ).tolist()
    )

    clubs = _unique_sequence(
        matches.get(
            "club_name",
            pd.Series(dtype=object),
        ).tolist()
    )

    leagues = _unique_sequence(
        matches.get(
            "league_name",
            pd.Series(dtype=object),
        ).tolist()
    )

    position_values = matches.get(
        "canonical_position",
        pd.Series(dtype=object),
    ).tolist()

    club_values = matches.get(
        "club_name",
        pd.Series(dtype=object),
    ).tolist()

    league_values = matches.get(
        "league_name",
        pd.Series(dtype=object),
    ).tolist()

    role_changes = sum(
        1
        for a, b in zip(
            position_values,
            position_values[1:],
        )
        if pd.notna(a)
        and pd.notna(b)
        and a != b
    )

    club_changes = sum(
        1
        for a, b in zip(
            club_values,
            club_values[1:],
        )
        if pd.notna(a)
        and pd.notna(b)
        and a != b
    )

    league_changes = sum(
        1
        for a, b in zip(
            league_values,
            league_values[1:],
        )
        if pd.notna(a)
        and pd.notna(b)
        and a != b
    )

    slope = _slope(trend_perf)

    return {
        "player_id": player_id,
        "season": int(season),
        "available": True,

        "windows": {
            "three_year": {
                "seasons": sorted(last3),
                "sample": int(len(recent3)),
                "average_performance": (
                    _num(recent3.mean())
                    if len(recent3)
                    else None
                ),
            },
            "five_year": {
                "seasons": sorted(last5),
                "sample": int(len(recent5)),
                "average_performance": (
                    _num(recent5.mean())
                    if len(recent5)
                    else None
                ),
                "consistency_std": (
                    _num(recent5.std(ddof=0))
                    if len(recent5) >= 2
                    else None
                ),
            },
        },

        "trend": {
            "performance_slope_per_season": slope,
            "eligible_seasons": int(len(trend_perf)),
            "minimum_minutes": MIN_MINUTES_FOR_TREND,
            "interpretation": (
                "improving"
                if slope is not None and slope >= 3
                else "declining"
                if slope is not None and slope <= -3
                else "stable_or_unclear"
            ),
        },

        "peak": {
            "performance": (
                _num(perf.loc[peak_idx])
                if peak_idx is not None
                else None
            ),
            "season": (
                int(matches.loc[peak_idx, "season"])
                if peak_idx is not None
                else None
            ),
        },

        "selected_season": {
            "season": int(selected["season"]),
            "performance": _num(
                selected.get("performance_score")
            ),
            "potential": _num(
                selected.get("development_potential")
            ),
            "minutes": _num(
                selected.get("playing_time_min")
            ),
            "age": _num(
                selected.get("age_fifa")
            ),
            "position": selected.get(
                "canonical_position"
            ),
            "club": selected.get("club_name"),
            "league": selected.get("league_name"),
        },

        "trajectory": trajectory,

        "component_evolution": component_evolution,

        "role_evolution": {
            "positions": positions,
            "changes": role_changes,
            "current": selected.get(
                "canonical_position"
            ),
        },

        "club_league_trajectory": {
            "clubs": clubs,
            "leagues": leagues,
            "club_changes": club_changes,
            "league_changes": league_changes,
        },

        "method": {
            "historical_cutoff": int(season),
            "trend_min_minutes": MIN_MINUTES_FOR_TREND,
            "windows": (
                "Most recent 3 and 5 observed seasons "
                "up to the selected season"
            ),
            "component_basis": (
                "Existing position- and season-aware "
                "percentile component scores where available"
            ),
        },
    }