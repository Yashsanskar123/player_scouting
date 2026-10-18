"""Recruitment market intelligence for the selected season.

This module keeps the market-opportunity definition transparent. It uses only
observable/modelled fields already present in ScoutIQ and does not invent
contract expiry, release clauses, transfer fees, or availability.
"""
from __future__ import annotations

import pandas as pd


FIT_WEIGHTS = {
    "value_leverage": 0.35,
    "wage_efficiency": 0.20,
    "current_performance": 0.20,
    "age_profile": 0.10,
    "uncertainty": 0.15,
}

RELIABILITY_TIER_RANK = {"Very Low": 0, "Low": 1, "Moderate": 2, "High": 3}

SEGMENT_DEFINITIONS = {
    "all": "All players meeting the base market-opportunity criteria.",
    "value": "Model fair value is at least 20% above the observed market-value signal.",
    "performance": "Performance score is at least 75 with a positive value gap.",
    "upside": "Age is 23 or below, potential is at least 75, and the value gap is positive.",
    "efficient": "Wage-to-value burden is at most 5% with a positive value gap.",
    "low_risk": "Positive value gap with LOW recruitment-risk tier.",
}


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _clean_number(value):
    if pd.isna(value):
        return None
    return float(value) if isinstance(value, float) else value


def _canonical_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one player-season row, preferring minutes then performance."""
    work = df.copy()

    if "player_id" not in work.columns:
        return work

    if "playing_time_min" in work.columns:
        work["_minutes_sort"] = (
            _numeric(work, "playing_time_min").fillna(-1)
        )
    else:
        work["_minutes_sort"] = -1

    work["_performance_sort"] = (
        _numeric(work, "performance_score").fillna(-1)
    )

    return (
        work.sort_values(
            ["_minutes_sort", "_performance_sort"],
            ascending=False,
        )
        .drop_duplicates("player_id", keep="first")
        .drop(
            columns=["_minutes_sort", "_performance_sort"],
            errors="ignore",
        )
    )


def _add_market_metrics(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()

    value = _numeric(work, "value_eur")
    gap = _numeric(work, "value_gap_pct")
    wage = _numeric(work, "wage_eur")
    performance = _numeric(work, "performance_score")
    age = _numeric(work, "age_fifa")
    risk = _numeric(work, "recruitment_risk_score")

    wage_to_value = pd.Series(
        float("nan"),
        index=work.index,
    )

    valid_value = (
        value.notna()
        & (value > 0)
        & wage.notna()
    )

    wage_to_value.loc[valid_value] = (
        wage.loc[valid_value]
        / value.loc[valid_value]
        * 100.0
    )

    work["wage_to_value_pct"] = wage_to_value

    components = pd.DataFrame(index=work.index)

    components["value_leverage"] = (
        50.0 + gap
    ).clip(0, 100)

    components["wage_efficiency"] = (
        100.0 - wage_to_value * 10.0
    ).clip(0, 100)

    components["current_performance"] = (
        performance
    ).clip(0, 100)

    components["age_profile"] = (
        100.0 - (age - 24.0).abs() * 7.0
    ).clip(0, 100)

    components["uncertainty"] = (
        100.0 - risk
    ).clip(0, 100)

    score = pd.Series(
        0.0,
        index=work.index,
    )

    available_weight = pd.Series(
        0.0,
        index=work.index,
    )

    for key, weight in FIT_WEIGHTS.items():
        available = components[key].notna()

        score = (
            score
            + components[key].fillna(0) * weight
        )

        available_weight = (
            available_weight
            + available.astype(float) * weight
        )

    work["opportunity_score"] = (
        score
        / available_weight.replace(0, pd.NA)
    ).round(1)

    work["_value"] = value
    work["_gap"] = gap
    work["_performance"] = performance
    work["_potential"] = _numeric(
        work,
        "development_potential",
    )
    work["_age"] = age
    work["_risk"] = risk

    return work


def _segment_mask(
    df: pd.DataFrame,
    segment: str,
) -> pd.Series:

    positive_gap = df["_gap"] > 0

    if segment == "value":
        return (
            positive_gap
            & (df["_gap"] >= 20)
        )

    if segment == "performance":
        return (
            positive_gap
            & (df["_performance"] >= 75)
        )

    if segment == "upside":
        return (
            positive_gap
            & (df["_age"] <= 23)
            & (df["_potential"] >= 75)
        )

    if segment == "efficient":
        return (
            positive_gap
            & df["wage_to_value_pct"].notna()
            & (df["wage_to_value_pct"] <= 5)
        )

    if segment == "low_risk":
        return (
            positive_gap
            & (
                df.get(
                    "recruitment_risk_tier",
                    pd.Series(index=df.index),
                )
                == "LOW"
            )
        )

    return positive_gap


def build_market_intelligence(
    df: pd.DataFrame,
    *,
    top_n: int = 20,
    min_performance_score: float = 60,
    min_value_gap_pct: float = 0,
    min_age: int | None = None,
    max_age: int | None = None,
    canonical_position: str | None = None,
    league_name: str | None = None,
    risk_tier: str | None = None,
    segment: str = "all",
    min_reliability_tier: str | None = None,
) -> dict:

    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    if (
        min_age is not None
        and max_age is not None
        and min_age > max_age
    ):
        raise ValueError(
            "min_age cannot be greater than max_age."
        )

    if (min_reliability_tier is not None
            and min_reliability_tier not in RELIABILITY_TIER_RANK):
        raise ValueError(
            f"Unknown reliability tier '{min_reliability_tier}'."
        )

    if segment not in SEGMENT_DEFINITIONS:
        raise ValueError(
            f"Unknown market segment '{segment}'."
        )

    work = _canonical_rows(df)
    work = _add_market_metrics(work)

    available_positions = sorted(
        {
            str(x)
            for x in work.get(
                "canonical_position",
                pd.Series(dtype=object),
            ).dropna().tolist()
        }
    )

    available_leagues = sorted(
        {
            str(x)
            for x in work.get(
                "league_name",
                pd.Series(dtype=object),
            ).dropna().tolist()
        }
    )

    base = work[
        work["_performance"]
        >= float(min_performance_score)
    ]

    base = base[
        base["_gap"]
        > float(min_value_gap_pct)
    ]

    if min_age is not None:
        base = base[
            base["_age"] >= min_age
        ]

    if max_age is not None:
        base = base[
            base["_age"] <= max_age
        ]

    if canonical_position:
        base = base[
            base["canonical_position"]
            == canonical_position
        ]

    if league_name:
        base = base[
            base["league_name"]
            == league_name
        ]

    if min_reliability_tier:
        rank = base.get(
            "sample_reliability_tier",
            pd.Series(index=base.index, dtype=object),
        ).map(RELIABILITY_TIER_RANK)
        base = base[rank >= RELIABILITY_TIER_RANK[min_reliability_tier]]

    if risk_tier:
        base = base[
            base["recruitment_risk_tier"]
            == risk_tier
        ]

    segment_masks = {
        key: _segment_mask(base, key)
        for key in SEGMENT_DEFINITIONS
    }

    selected = base[
        segment_masks[segment]
    ].copy()

    selected = selected.sort_values(
        [
            "opportunity_score",
            "_gap",
            "_performance",
        ],
        ascending=False,
        na_position="last",
    )

    def record(row) -> dict:
        keys = [
            "player_id",
            "short_name",
            "canonical_position",
            "club_name",
            "league_name",
            "age_fifa",
            "value_eur",
            "fair_value_eur",
            "value_gap_pct",
            "performance_score",
            "development_potential",
            "expected_performance_12m",
            "playing_time_min",
            "recruitment_risk_tier",
            "recruitment_risk_score",
            "sample_reliability_score",
            "wage_eur",
            "wage_to_value_pct",
            "opportunity_score",
        ]

        out = {}

        for key in keys:
            if key in row.index:
                value = row.get(key)
                out[key] = _clean_number(value)

        return out

    records = [
        record(row)
        for _, row in selected.head(top_n).iterrows()
    ]

    segment_counts = [
        {
            "key": key,
            "label": key.replace(
                "_",
                " ",
            ).title(),
            "description": description,
            "count": int(mask.sum()),
        }
        for key, (description, mask) in {
            key: (
                SEGMENT_DEFINITIONS[key],
                segment_masks[key],
            )
            for key in SEGMENT_DEFINITIONS
        }.items()
    ]

    def breakdown(
        column: str,
        limit: int = 8,
    ) -> list[dict]:

        if column not in base.columns:
            return []

        grouped = (
            base.groupby(
                column,
                dropna=False,
            )
            .agg(
                opportunities=(
                    "player_id",
                    "nunique",
                ),
                avg_gap=(
                    "_gap",
                    "mean",
                ),
                avg_performance=(
                    "_performance",
                    "mean",
                ),
            )
            .reset_index()
            .sort_values(
                "opportunities",
                ascending=False,
            )
            .head(limit)
        )

        result = []

        for _, row in grouped.iterrows():

            label = row[column]

            result.append(
                {
                    "name": (
                        None
                        if pd.isna(label)
                        else str(label)
                    ),
                    "opportunities": int(
                        row["opportunities"]
                    ),
                    "avg_gap": (
                        round(
                            float(row["avg_gap"]),
                            1,
                        )
                        if pd.notna(
                            row["avg_gap"]
                        )
                        else None
                    ),
                    "avg_performance": (
                        round(
                            float(
                                row[
                                    "avg_performance"
                                ]
                            ),
                            1,
                        )
                        if pd.notna(
                            row[
                                "avg_performance"
                            ]
                        )
                        else None
                    ),
                }
            )

        return result

    median_value = base["_value"].median()
    avg_gap = base["_gap"].mean()
    avg_score = base[
        "opportunity_score"
    ].mean()

    return {
        "total": int(len(base)),
        "selected_total": int(
            len(selected)
        ),
        "results": records,

        "summary": {
            "total_opportunities": int(
                len(base)
            ),
            "average_gap_pct": (
                round(
                    float(avg_gap),
                    1,
                )
                if pd.notna(avg_gap)
                else None
            ),
            "median_market_value_eur": (
                round(
                    float(median_value),
                    0,
                )
                if pd.notna(median_value)
                else None
            ),
            "average_opportunity_score": (
                round(
                    float(avg_score),
                    1,
                )
                if pd.notna(avg_score)
                else None
            ),
            "high_potential_count": int(
                segment_masks["upside"].sum()
            ),
            "high_performance_count": int(
                segment_masks["performance"].sum()
            ),
            "low_risk_count": int(
                segment_masks["low_risk"].sum()
            ),
        },

        "segments": segment_counts,

        "position_breakdown": breakdown(
            "canonical_position"
        ),

        "league_breakdown": breakdown(
            "league_name"
        ),

        "filter_options": {
            "positions": available_positions,
            "leagues": available_leagues,
            "risk_tiers": [
                "LOW",
                "MEDIUM",
                "HIGH",
            ],
        },

        "filters": {
            "min_performance_score":
                min_performance_score,
            "min_value_gap_pct":
                min_value_gap_pct,
            "min_age": min_age,
            "max_age": max_age,
            "canonical_position":
                canonical_position,
            "league_name":
                league_name,
            "risk_tier":
                risk_tier,
            "segment": segment,
        },

        "methodology": {
            "base_definition": (
                "performance score meets the "
                "selected minimum and model "
                "value gap is above the selected "
                "minimum."
            ),
            "opportunity_score": (
                "Transparent weighted signal using "
                "value leverage 35%, wage efficiency "
                "20%, current performance 20%, age "
                "profile 10%, and uncertainty 15%, "
                "renormalized when a component is "
                "unavailable."
            ),
            "fair_value_note": (
                "fair_value_eur is a trained-model "
                "estimate against this dataset's FIFA "
                "in-game valuation; it is not a real "
                "transfer-market appraisal."
            ),
            "data_boundary": (
                "Contract expiry, release clause, "
                "negotiated transfer fee, availability "
                "and scouting observations are not "
                "present in the current FIFA/FBref dataset."
            ),
        },
    }