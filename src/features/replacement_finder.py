"""Replacement Finder (spec section 15).

Given an outgoing player, find who could replace them -- constrained by
budget/age, ranked by a blend of role fit and similarity, and explained in
terms an analyst can act on (cheaper/younger/lower-risk/better-fit-role
than the outgoing player), not just a bare similarity percentage.

Built on top of the existing multi-facet similarity engine
(src/features/similarity_v2.py) rather than a separate model -- a
replacement candidate IS a similar player, additionally filtered by
budget/age and explained relative to who's leaving. Reusing the engine
means the position-restriction bug fix and the tactical/statistical/
physical/market facet split already apply here for free.
"""
from __future__ import annotations

import pandas as pd

from src.features.similarity_v2 import find_similar_players_multifacet
from src.utils import to_native as _native


def _num(value):
    return pd.to_numeric(value, errors="coerce")


def _pct(value):
    return float(value) if pd.notna(value) else None


COMPONENTS = (
    ("attacking", "Attacking"), ("chance_creation", "Chance creation"), ("passing", "Passing"), ("progression", "Progression"),
    ("defending", "Defending"), ("physical", "Physical"), ("goalkeeping", "Goalkeeping"),
)
SIMILAR_WITHIN = 5.0   # component scores within 5 points count as "similar"
DIFFERENT_BY = 8.0     # 8+ points apart counts as clearly better / weaker


def compare_components(outgoing, candidate) -> dict:
    """Skill-by-skill comparison (the same 0-100 component scores that make up the performance score)."""
    rows, similar, better, weaker = [], [], [], []
    for key, label in COMPONENTS:
        a, b = _num(outgoing.get(f"component_{key}")), _num(candidate.get(f"component_{key}"))
        if pd.isna(a) or pd.isna(b):
            continue
        diff = float(b - a)
        rows.append({"key": key, "label": label, "outgoing": round(float(a), 1), "candidate": round(float(b), 1), "difference": round(diff, 1)})
        if abs(diff) <= SIMILAR_WITHIN:
            similar.append(label)
        elif diff >= DIFFERENT_BY:
            better.append({"label": label, "points": round(diff, 1)})
        elif diff <= -DIFFERENT_BY:
            weaker.append({"label": label, "points": round(-diff, 1)})
    return {"component_comparison": rows, "similar_in": similar,
            "better_in": sorted(better, key=lambda x: -x["points"]), "weaker_in": sorted(weaker, key=lambda x: -x["points"])}


def find_replacements(
    df: pd.DataFrame,
    outgoing_player_id: str,
    budget_eur: float | None = None,
    max_age: int | None = None,
    min_age: int | None = None,
    top_n: int = 10,
    restrict_to_position_group: bool = True,
) -> dict:
    if "player_id" not in df.columns:
        raise ValueError("df must have player_id assigned.")

    if top_n < 1:
        raise ValueError("top_n must be at least 1.")

    if min_age is not None and max_age is not None and min_age > max_age:
        raise ValueError("min_age cannot be greater than max_age.")

    outgoing_matches = df[df["player_id"] == outgoing_player_id]
    if outgoing_matches.empty:
        raise ValueError(
            f"No player found with player_id '{outgoing_player_id}'."
        )

    outgoing = (
        outgoing_matches.sort_values("season").iloc[-1]
        if "season" in df.columns
        else outgoing_matches.iloc[0]
    )

    similarity_df = (
        df.sort_values("season").drop_duplicates(
            "player_id",
            keep="last"
        )
        if "season" in df.columns
        else df
    )

    pool = find_similar_players_multifacet(
        similarity_df,
        player_id=outgoing_player_id,
        top_n=min(max(200, top_n * 20), 500),
        restrict_to_broad_position_group=restrict_to_position_group,
    )

    if budget_eur is not None:
        pool = pool[
            _num(pool["value_eur"]) <= budget_eur
        ]
    if max_age is not None:
        pool = pool[
            _num(pool["age_fifa"]) <= max_age
        ]
    if min_age is not None:
        pool = pool[
            _num(pool["age_fifa"]) >= min_age
        ]

    outgoing_value = _num(outgoing.get("value_eur"))
    outgoing_age = _num(outgoing.get("age_fifa"))
    outgoing_perf = _num(outgoing.get("performance_score"))
    outgoing_potential = _num(
        outgoing.get("development_potential")
    )
    outgoing_wage = _num(outgoing.get("wage_eur"))
    outgoing_group = outgoing.get("broad_position_group")

    outgoing_dict = {
        "player_id": outgoing_player_id,
        "short_name": _native(outgoing.get("short_name")),
        "canonical_position": _native(
            outgoing.get("canonical_position")
        ),
        "broad_position_group": _native(
            outgoing.get("broad_position_group")
        ),
        "club_name": _native(outgoing.get("club_name")),
        "age_fifa": _native(outgoing.get("age_fifa")),
        "value_eur": _native(outgoing.get("value_eur")),
        "performance_score": _native(
            outgoing.get("performance_score")
        ),
        "development_potential": _native(
            outgoing.get("development_potential")
        ),
        "expected_performance_12m": _native(
            outgoing.get("expected_performance_12m")
        ),
        "recruitment_risk_tier": _native(
            outgoing.get("recruitment_risk_tier")
        ),
    }

    if pool.empty:
        return {
            "outgoing_player": outgoing_dict,
            "constraints": {
                "budget_eur": budget_eur,
                "min_age": min_age,
                "max_age": max_age,
            },
            "candidate_pool_size": 0,
            "candidates": [],
            "scenarios": [],
            "note": (
                "No candidates matched the given "
                "budget/age constraints. Try widening them."
            ),
            "methodology": {
                "position_constraint": (
                    "same broad position group as outgoing player"
                ),
                "fit_weights": {
                    "tactical": 0.35,
                    "statistical": 0.35,
                    "physical": 0.15,
                    "market": 0.15,
                },
            },
        }

    pool = pool.copy()
    pool["replacement_fit_score"] = (
        pool["tactical_similarity"].fillna(0) * 0.35
        + pool["statistical_similarity"].fillna(0) * 0.35
        + pool["physical_similarity"].fillna(0) * 0.15
        + pool["market_similarity"].fillna(0) * 0.15
    ).round(1)

    ranked = pool.sort_values(
        "replacement_fit_score",
        ascending=False
    )
    qualifying_pool_size = len(ranked)

    candidates = []
    for _, row in ranked.head(top_n).iterrows():
        row_value = _num(row.get("value_eur"))
        row_age = _num(row.get("age_fifa"))
        row_perf = _num(row.get("performance_score"))
        row_potential = _num(
            row.get("development_potential")
        )

        advantages = []
        watchouts = []

        if (
            pd.notna(row_value)
            and pd.notna(outgoing_value)
            and outgoing_value > 0
        ):
            delta = (row_value / outgoing_value - 1) * 100

            if delta <= -15:
                advantages.append(
                    f"{abs(delta):.0f}% below outgoing value (cheaper)"
                )
            elif delta >= 15:
                watchouts.append(
                    f"{delta:.0f}% above outgoing value"
                )

        if pd.notna(row_age) and pd.notna(outgoing_age):
            age_delta = row_age - outgoing_age

            if age_delta <= -2:
                advantages.append(
                    f"{abs(age_delta):.0f} years younger"
                )
            elif age_delta >= 2:
                watchouts.append(
                    f"{age_delta:.0f} years older"
                )

        if pd.notna(row_perf) and pd.notna(outgoing_perf):
            if row_perf >= outgoing_perf + 5:
                advantages.append("higher current performance")
            elif row_perf <= outgoing_perf - 5:
                watchouts.append("lower current performance")

        if (
            pd.notna(row_potential)
            and pd.notna(outgoing_potential)
            and row_potential >= outgoing_potential + 5
        ):
            advantages.append("higher development potential")

        row_wage = _num(row.get("wage_eur"))
        if pd.notna(row_wage) and pd.notna(outgoing_wage) and outgoing_wage > 0:
            wage_delta = (row_wage / outgoing_wage - 1) * 100
            if wage_delta <= -20:
                advantages.append(f"{abs(wage_delta):.0f}% lower wage (FIFA estimate)")
            elif wage_delta >= 20:
                watchouts.append(f"{wage_delta:.0f}% higher wage (FIFA estimate)")
        other_group = bool(pd.notna(outgoing_group) and row.get("broad_position_group") != outgoing_group)
        if other_group:
            watchouts.append(f"Plays as a {row.get('broad_position_group')}: a style match only, confirm he can do the role")
        comparison = compare_components(outgoing, row)
        if row.get("recruitment_risk_tier") == "LOW":
            advantages.append("LOW recruitment-risk tier")
        elif row.get("recruitment_risk_tier") == "HIGH":
            watchouts.append("HIGH recruitment-risk tier")

        candidates.append({
            "player_id": _native(row.get("player_id")),
            "short_name": _native(row.get("short_name")),
            "canonical_position": _native(row.get("canonical_position")),
            "broad_position_group": _native(
                row.get("broad_position_group")
            ),
            "club_name": _native(row.get("club_name")),
            "league_name": _native(row.get("league_name")),
            "age_fifa": _native(row.get("age_fifa")),
            "value_eur": _native(row.get("value_eur")),
            "fair_value_eur": _native(
                row.get("fair_value_eur")
            ),
            "value_gap_pct": _native(
                row.get("value_gap_pct")
            ),
            "performance_score": _native(row.get("performance_score")),
            "development_potential": _native(
                row.get("development_potential")
            ),
            "expected_performance_12m": _native(
                row.get("expected_performance_12m")
            ),
            "playing_time_min": _native(
                row.get("playing_time_min")
            ),
            "recruitment_risk_tier": _native(row.get("recruitment_risk_tier")),
            "sample_reliability_score": _native(
                row.get("sample_reliability_score")
            ),
            "replacement_fit_score": _native(row.get("replacement_fit_score")),
            "tactical_similarity": _native(row.get("tactical_similarity")),
            "statistical_similarity": _native(row.get("statistical_similarity")),
            "physical_similarity": _native(row.get("physical_similarity")),
            "market_similarity": _native(row.get("market_similarity")),
            "overall_similarity": _native(row.get("overall_similarity")),
            "wage_eur": _native(row.get("wage_eur")),
            "wage_vs_outgoing_pct": _pct(round((row_wage / outgoing_wage - 1) * 100, 1)) if pd.notna(row_wage) and pd.notna(outgoing_wage) and outgoing_wage > 0 else None,
            "different_position_group": other_group,
            **comparison,
            "advantages": advantages,
            "watchouts": watchouts,
        })

    pool = pool.copy()
    pool["_value"] = _num(pool.get("value_eur"))
    pool["_perf"] = _num(pool.get("performance_score"))
    pool["_potential"] = _num(
        pool.get("development_potential")
    )
    pool["_age"] = _num(pool.get("age_fifa"))
    pool["_reliability"] = _num(
        pool.get("sample_reliability_score")
    )

    def best_row(frame):
        if frame.empty:
            return None
        return frame.iloc[0]

    scenarios = []

    like_for_like = ranked.iloc[0] if not ranked.empty else None
    if like_for_like is not None:
        scenarios.append({
            "key": "like_for_like",
            "label": "Like-for-like",
            "description": "Closest overall replacement profile.",
            "player_id": _native(like_for_like.player_id),
        })

    younger = pool[
        pool["_age"].notna()
        & pd.notna(outgoing_age)
        & (pool["_age"] <= outgoing_age - 2)
    ].sort_values(
        ["replacement_fit_score", "_potential"],
        ascending=False
    )
    younger_row = best_row(younger)
    if younger_row is not None:
        scenarios.append({
            "key": "succession",
            "label": "Succession option",
            "description": (
                "Younger candidate retaining strong replacement fit."
            ),
            "player_id": _native(younger_row.player_id),
        })

    if pd.notna(outgoing_value) and outgoing_value > 0:
        value_pool = pool[
            pool["_value"].notna()
            & (pool["_value"] < outgoing_value * 0.85)
        ].sort_values(
            "replacement_fit_score",
            ascending=False
        )
    else:
        value_pool = pool.iloc[0:0]

    value_row = best_row(value_pool)
    if value_row is not None:
        scenarios.append({
            "key": "value",
            "label": "Lower-cost option",
            "description": (
                "Candidate priced materially below the outgoing player's value."
            ),
            "player_id": _native(value_row.player_id),
        })

    upside = pool[
        pool["_potential"].notna()
    ].sort_values(
        ["_potential", "replacement_fit_score"],
        ascending=False
    )
    upside_row = best_row(upside)
    if upside_row is not None:
        scenarios.append({
            "key": "upside",
            "label": "Higher-upside option",
            "description": (
                "Candidate with the strongest development-potential "
                "signal in the qualifying pool."
            ),
            "player_id": _native(upside_row.player_id),
        })

    reliable = pool[
        pool["_reliability"].notna()
    ].sort_values(
        ["_reliability", "replacement_fit_score"],
        ascending=False
    )
    reliable_row = best_row(reliable)
    if reliable_row is not None:
        scenarios.append({
            "key": "evidence",
            "label": "Evidence-led option",
            "description": (
                "Candidate with the strongest evidence-reliability "
                "signal in the qualifying pool."
            ),
            "player_id": _native(reliable_row.player_id),
        })

    best_value = value_row if value_row is not None else None
    return {
        "outgoing_player": outgoing_dict,
        "constraints": {
            "budget_eur": budget_eur,
            "min_age": min_age,
            "max_age": max_age,
        },
        "candidate_pool_size": qualifying_pool_size,
        "candidates": candidates,
        "scenarios": scenarios,
        "best_value_alternative_player_id": (
            _native(best_value.player_id)
            if best_value is not None
            else None
        ),
        "methodology": {
            "position_constraint": (
                "same broad position group as outgoing player"
            ),
            "fit_weights": {
                "tactical": 0.35,
                "statistical": 0.35,
                "physical": 0.15,
                "market": 0.15,
            },
            "scenario_note": (
                "Scenarios are descriptive views of the same qualifying "
                "pool, not universal rankings or transfer predictions."
            ),
        },
    }
