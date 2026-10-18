"""Focused development-decision intelligence for ScoutIQ."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.advanced_potential import compute_advanced_potential
from src.features.role_archetypes import (
    ROLE_ARCHETYPES,
    compute_role_fit,
    explain_role_fit,
    recommended_roles_for_position,
)

METRICS = {
    "attacking": [
        ("per_90_minutes_gls", "Goals / 90"),
        ("per_90_minutes_x_g", "xG / 90"),
        ("per_90_minutes_ast", "Assists / 90"),
        ("per_90_minutes_x_ag", "xA / 90"),
        ("per_90_minutes_kp", "Key passes / 90"),
        ("sca_sca90", "Shot-creating actions"),
        ("gca_gca90", "Goal-creating actions"),
    ],
    "progression": [
        ("per_90_minutes_prg_c", "Progressive carries"),
        ("per_90_minutes_prg_p", "Progressive passes"),
        ("per_90_minutes_prg_r", "Progressive receptions"),
        ("per_90_minutes_1_3", "Final-third passes"),
        ("per_90_minutes_ppa", "Penalty-area passes"),
    ],
    "passing": [
        ("per_90_minutes_total_cmp", "Completed passes"),
        ("total_cmppct", "Pass completion"),
        ("per_90_minutes_expected_x_a", "Expected assists"),
    ],
    "defending": [
        ("per_90_minutes_tackles_tkl", "Tackles"),
        ("per_90_minutes_tackles_tkl_w", "Tackles won"),
        ("per_90_minutes_int", "Interceptions"),
        ("per_90_minutes_tkl_int", "Tackles + interceptions"),
        ("per_90_minutes_clr", "Clearances"),
        ("per_90_minutes_blocks_blocks", "Blocks"),
    ],
    "goalkeeping": [
        ("per_90_minutes_performance_saves", "Saves"),
        ("performance_savepct", "Save percentage"),
        ("performance_cspct", "Clean-sheet percentage"),
    ],
}

POSITION_GROUPS = {
    "GK": ["goalkeeping"],
    "CB": ["defending", "passing", "progression"],
    "LB": ["defending", "progression", "passing"],
    "RB": ["defending", "progression", "passing"],
    "LWB": ["progression", "defending", "attacking", "passing"],
    "RWB": ["progression", "defending", "attacking", "passing"],
    "CDM": ["passing", "defending", "progression"],
    "CM": ["passing", "progression", "defending", "attacking"],
    "CAM": ["attacking", "passing", "progression"],
    "LW": ["attacking", "progression", "passing"],
    "RW": ["attacking", "progression", "passing"],
    "ST": ["attacking", "progression"],
    "CF": ["attacking", "passing", "progression"],
}


def _num(v):
    if v is None or pd.isna(v):
        return None
    return float(v)


def _metrics(row, position):
    groups = POSITION_GROUPS.get(
        str(position),
        ["attacking", "progression", "passing", "defending"],
    )

    out = []

    for group in groups:
        for key, label in METRICS[group]:
            col = f"{key}_pctile"

            if col not in row.index:
                continue

            value = pd.to_numeric(
                pd.Series([row.get(col)]),
                errors="coerce",
            ).iloc[0]

            if pd.notna(value):
                out.append(
                    {
                        "metric": key,
                        "label": label,
                        "group": group,
                        "percentile": round(float(value), 1),
                    }
                )

    return out


def build_development_lab(
    df: pd.DataFrame,
    player_id: str,
    season: int | None = None,
) -> dict:
    if df.empty or "player_id" not in df.columns:
        raise ValueError("No player data is available")

    matches = df[df.player_id == player_id].copy()

    if season is not None:
        matches = matches[matches.season == season]

    if matches.empty:
        suffix = f" in season {season}" if season is not None else ""
        raise ValueError(
            f"No player found with player_id '{player_id}'{suffix}."
        )

    selected = matches.sort_values("season").iloc[-1]
    selected_season = int(selected.season)

    advanced = compute_advanced_potential(df.copy())

    history = advanced[
        (advanced.player_id == player_id)
        & (
            pd.to_numeric(
                advanced.season,
                errors="coerce",
            )
            <= selected_season
        )
    ].sort_values("season")

    current = history.iloc[-1]

    position = (
        str(current.canonical_position)
        if pd.notna(current.get("canonical_position"))
        else None
    )

    trajectory = [
        {
            "season": int(r.season),
            "performance": _num(r.get("performance_score")),
            "expected_12m": _num(r.get("expected_performance_12m")),
            "development_potential": _num(
                r.get("development_potential")
            ),
            "minutes": _num(r.get("playing_time_min")),
        }
        for _, r in history.iterrows()
    ]

    current_score = _num(current.get("current_ability"))

    if current_score is None:
        current_score = _num(current.get("performance_score"))

    expected12 = _num(current.get("potential_12m"))

    if expected12 is None:
        expected12 = _num(
            current.get("expected_performance_12m")
        )

    projection24 = _num(current.get("potential_24m"))

    observed_change = None

    if (
        len(trajectory) >= 2
        and trajectory[-1]["performance"] is not None
        and trajectory[-2]["performance"] is not None
    ):
        observed_change = round(
            trajectory[-1]["performance"]
            - trajectory[-2]["performance"],
            1,
        )

    available = _metrics(current, position)

    priorities = [
        x
        for x in sorted(
            available,
            key=lambda x: x["percentile"],
        )
        if x["percentile"] < 55
    ][:3]

    strengths = sorted(
        available,
        key=lambda x: x["percentile"],
        reverse=True,
    )[:3]

    roles = []

    for role in (
        recommended_roles_for_position(position)
        if position
        else list(ROLE_ARCHETYPES)
    ):
        scored = compute_role_fit(
            df[df.season == selected_season],
            role,
        )

        pr = scored[scored.player_id == player_id]

        if pr.empty:
            continue

        row = pr.iloc[0]

        roles.append(
            {
                "role": role,
                "role_fit_score": _num(
                    row.get("role_fit_score")
                ),
                "coverage_pct": _num(
                    row.get("role_fit_coverage_pct")
                ),
                **explain_role_fit(row, role),
            }
        )

    roles.sort(
        key=lambda x: (
            x["role_fit_score"]
            if x["role_fit_score"] is not None
            else -1
        ),
        reverse=True,
    )

    direction = str(
        current.get("development_trajectory")
        or "unknown"
    )

    status = str(
        current.get("potential_projection_status")
        or "unknown"
    )

    risks = []

    if len(trajectory) < 3:
        risks.append("Limited longitudinal evidence")

    reliability = _num(
        current.get("sample_reliability_score")
    )

    if reliability is not None and reliability < 60:
        risks.append("Lower evidence reliability")

    if direction == "falling":
        risks.append("Recent performance decline")

    minutes = _num(current.get("playing_time_min"))

    if minutes is not None and minutes < 900:
        risks.append("Limited current-season minutes")

    if status == "low_evidence":
        risks.append("Small empirical projection cohort")

    case = []

    if (
        expected12 is not None
        and current_score is not None
        and expected12 > current_score + 2
    ):
        case.append(
            "The validated 12M expectation is above "
            "the current observed level."
        )

    if direction == "rising":
        case.append(
            "Recent observed performance is rising."
        )

    if (
        projection24 is not None
        and expected12 is not None
        and projection24 > expected12 + 2
    ):
        case.append(
            "The 24M signal extends the trajectory upward; "
            "it is exploratory."
        )

    if not case:
        case.append(
            "No clear directional development case; "
            "validate the identified priorities and preserve "
            "existing strengths."
        )

    return {
        "player": {
            "player_id": player_id,
            "short_name": current.get("short_name"),
            "canonical_position": position,
            "club_name": current.get("club_name"),
            "league_name": current.get("league_name"),
            "age_fifa": _num(current.get("age_fifa")),
            "season": selected_season,
        },
        "outlook": {
            "current": current_score,
            "expected_12m": expected12,
            "projection_24m": projection24,
            "peak_projection": _num(
                current.get("peak_projection")
            ),
            "development_potential": _num(
                current.get("development_potential")
            ),
            "trajectory": direction,
            "breakout_probability": _num(
                current.get("breakout_probability")
            ),
            "decline_probability": _num(
                current.get("decline_probability")
            ),
            "projection_status": status,
            "evidence_sample": int(
                current.get("potential_evidence_sample") or 0
            ),
        },
        "trajectory": trajectory,
        "observed_change": observed_change,
        "development_priorities": priorities,
        "strengths_to_preserve": strengths,
        "role_evolution": {
            "current_position": position,
            "roles": roles[:4],
        },
        "development_case": case,
        "risks": risks,
        "evidence": {
            "seasons_observed": len(trajectory),
            "sample_reliability_score": reliability,
            "sample_reliability_tier": current.get(
                "sample_reliability_tier"
            ),
            "fifa_potential_benchmark": _num(
                current.get("fifa_potential_benchmark")
            ),
        },
        "methodology": {
            "validated_12m":
                "12M uses the existing walk-forward-validated "
                "recency/mean estimator.",
            "exploratory_24m":
                "24M is an exploratory recursive extension, "
                "not a validated forecast.",
            "peak":
                "Peak is an exploratory ceiling signal, "
                "not a guaranteed career peak.",
            "priorities":
                "Priorities use the lowest available positional "
                "peer percentiles among relevant dimensions.",
            "role":
                "Role evolution uses the existing transparent "
                "role-fit model.",
        },
    }