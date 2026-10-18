"""Recruitment-grade squad optimization using an auditable ILP.

The optimizer keeps exact formation constraints and budget feasibility, while
making the objective explicit. Different recruitment strategies change the
weights on current performance, 12-month expectation, development potential,
value efficiency and evidence reliability; no opaque universal score is used.
"""
from __future__ import annotations

import pandas as pd
import pulp


FORMATIONS = {
    "4-3-3": {
        "GK": 1,
        "CB": 2,
        "LB": 1,
        "RB": 1,
        "CM": 2,
        "CDM": 1,
        "LW": 1,
        "RW": 1,
        "ST": 1,
    },
    "4-2-3-1": {
        "GK": 1,
        "CB": 2,
        "LB": 1,
        "RB": 1,
        "CDM": 2,
        "CAM": 1,
        "LW": 1,
        "RW": 1,
        "ST": 1,
    },
    "4-4-2": {
        "GK": 1,
        "CB": 2,
        "LB": 1,
        "RB": 1,
        "CM": 2,
        "LW": 1,
        "RW": 1,
        "ST": 2,
    },
    "3-4-3": {
        "GK": 1,
        "CB": 3,
        "LWB": 1,
        "RWB": 1,
        "CM": 2,
        "LW": 1,
        "RW": 1,
        "ST": 1,
    },
    "3-5-2": {
        "GK": 1,
        "CB": 3,
        "LWB": 1,
        "RWB": 1,
        "CM": 2,
        "CAM": 1,
        "ST": 2,
    },
}


STRATEGIES = {
    "balanced": {
        "label": "Balanced",
        "description": (
            "Balances current output, near-term projection, upside, "
            "value efficiency and evidence reliability."
        ),
        "performance": 0.35,
        "expected_12m": 0.20,
        "potential": 0.15,
        "value": 0.15,
        "reliability": 0.15,
    },
    "performance": {
        "label": "Performance first",
        "description": (
            "Prioritizes current on-pitch production while retaining "
            "smaller future and evidence signals."
        ),
        "performance": 0.60,
        "expected_12m": 0.20,
        "potential": 0.05,
        "value": 0.05,
        "reliability": 0.10,
    },
    "development": {
        "label": "Development",
        "description": (
            "Prioritizes development potential and 12-month expectation "
            "for a succession-oriented XI."
        ),
        "performance": 0.20,
        "expected_12m": 0.25,
        "potential": 0.35,
        "value": 0.05,
        "reliability": 0.15,
    },
    "value": {
        "label": "Value efficiency",
        "description": (
            "Prioritizes output relative to market value while retaining "
            "performance and evidence safeguards."
        ),
        "performance": 0.30,
        "expected_12m": 0.15,
        "potential": 0.10,
        "value": 0.35,
        "reliability": 0.10,
    },
}


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _minmax(series: pd.Series, default: float = 50.0) -> pd.Series:
    values = _numeric(series)
    valid = values.dropna()

    if valid.empty:
        return pd.Series(default, index=series.index, dtype=float)

    lo = float(valid.min())
    hi = float(valid.max())

    if hi <= lo:
        return pd.Series(default, index=series.index, dtype=float)

    return ((values - lo) / (hi - lo) * 100).fillna(default)


def _value_efficiency(pool: pd.DataFrame) -> pd.Series:
    value = _numeric(
        pool.get(
            "value_eur",
            pd.Series(index=pool.index, dtype=float),
        )
    )

    performance = _numeric(
        pool.get(
            "performance_score",
            pd.Series(index=pool.index, dtype=float),
        )
    )

    fair = _numeric(
        pool.get(
            "fair_value_eur",
            pd.Series(index=pool.index, dtype=float),
        )
    )

    ratio = pd.Series(index=pool.index, dtype=float)

    positive_value = value > 0

    ratio.loc[positive_value] = (
        performance.loc[positive_value]
        / value.loc[positive_value].clip(lower=1)
    )

    # If fair value exists, blend affordability versus fair value into the
    # value signal without pretending fair value is a transfer fee.
    fair_ratio = pd.Series(index=pool.index, dtype=float)

    valid_fair = (
        positive_value
        & fair.notna()
        & (fair > 0)
    )

    fair_ratio.loc[valid_fair] = (
        fair.loc[valid_fair]
        / value.loc[valid_fair]
    )

    raw = (
        ratio.fillna(0) * 0.65
        + fair_ratio.fillna(1).clip(0, 3) * 33.33 * 0.35
    )

    return _minmax(raw, default=50.0)


def _prepare_objective(
    pool: pd.DataFrame,
    strategy: str,
) -> pd.DataFrame:

    weights = STRATEGIES[strategy]

    prepared = pool.copy()

    prepared["_performance_norm"] = _minmax(
        prepared["performance_score"]
    )

    prepared["_expected_norm"] = _minmax(
        prepared.get(
            "expected_performance_12m",
            pd.Series(index=prepared.index, dtype=float),
        )
    )

    prepared["_potential_norm"] = _minmax(
        prepared.get(
            "development_potential",
            pd.Series(index=prepared.index, dtype=float),
        )
    )

    prepared["_value_norm"] = _value_efficiency(prepared)

    prepared["_reliability_norm"] = _minmax(
        prepared.get(
            "sample_reliability_score",
            pd.Series(index=prepared.index, dtype=float),
        )
    )

    prepared["_objective_score"] = (
        prepared["_performance_norm"] * weights["performance"]
        + prepared["_expected_norm"] * weights["expected_12m"]
        + prepared["_potential_norm"] * weights["potential"]
        + prepared["_value_norm"] * weights["value"]
        + prepared["_reliability_norm"] * weights["reliability"]
    )

    return prepared


def optimize_squad_ilp(
    candidates: pd.DataFrame,
    formation: str = "4-3-3",
    budget_eur: float | None = None,
    quality_col: str = "performance_score",
    cost_col: str = "value_eur",
    position_col: str = "canonical_position",
    strategy: str = "balanced",
) -> dict:
    """Select an exact legal XI using a 0/1 ILP under budget.

    ``strategy`` changes transparent objective weights only. Formation
    requirements and affordability remain hard constraints for every strategy.
    """

    if formation not in FORMATIONS:
        raise ValueError(
            f"Unsupported formation: {formation}. "
            f"Available: {list(FORMATIONS)}"
        )

    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unsupported strategy: {strategy}. "
            f"Available: {list(STRATEGIES)}"
        )

    if budget_eur is not None and budget_eur < 0:
        raise ValueError("budget_eur must be non-negative.")

    requirements = FORMATIONS[formation]

    required_columns = {
        quality_col,
        cost_col,
        position_col,
    }

    missing = sorted(
        required_columns - set(candidates.columns)
    )

    if missing:
        raise ValueError(
            f"Missing optimizer columns: {missing}"
        )

    pool = candidates.dropna(
        subset=[
            quality_col,
            cost_col,
            position_col,
        ]
    ).copy()

    pool = pool[
        pool[position_col].isin(requirements.keys())
    ].copy()

    if pool.empty:
        return {
            "status": "infeasible",
            "reason": (
                "No candidates with required positions/data available."
            ),
            "formation": formation,
            "strategy": strategy,
        }

    prepared = _prepare_objective(
        pool,
        strategy,
    )

    prob = pulp.LpProblem(
        "squad_optimizer",
        pulp.LpMaximize,
    )

    choice_vars = {
        idx: pulp.LpVariable(
            f"x_{idx}",
            cat="Binary",
        )
        for idx in prepared.index
    }

    prob += pulp.lpSum(
        choice_vars[idx]
        * float(
            prepared.loc[idx, "_objective_score"]
        )
        for idx in prepared.index
    )

    for position, count in requirements.items():

        eligible = prepared.index[
            prepared[position_col] == position
        ]

        if len(eligible) < count:
            return {
                "status": "infeasible",
                "reason": (
                    f"Not enough candidates for position "
                    f"{position}: need {count}, "
                    f"have {len(eligible)}."
                ),
                "formation": formation,
                "strategy": strategy,
                "candidate_pool_size": int(
                    len(prepared)
                ),
            }

        prob += pulp.lpSum(
            choice_vars[idx]
            for idx in eligible
        ) == count

    if budget_eur is not None:
        prob += pulp.lpSum(
            choice_vars[idx]
            * float(
                prepared.loc[idx, cost_col]
            )
            for idx in prepared.index
        ) <= budget_eur

    solver = pulp.PULP_CBC_CMD(
        msg=False
    )

    prob.solve(solver)

    status = pulp.LpStatus[prob.status]

    if status != "Optimal":

        reason = (
            "No feasible XI satisfies all formation "
            "and budget constraints."
            if status == "Infeasible"
            else f"Solver returned {status}."
        )

        return {
            "status": status.lower(),
            "formation": formation,
            "strategy": strategy,
            "budget_eur": budget_eur,
            "candidate_pool_size": int(
                len(prepared)
            ),
            "reason": reason,
        }

    selected_idx = [
        idx
        for idx, var in choice_vars.items()
        if var.value() == 1
    ]

    selected = prepared.loc[
        selected_idx
    ].copy()

    name_col = (
        "short_name"
        if "short_name" in selected.columns
        else selected.columns[0]
    )

    total_cost = float(
        _numeric(
            selected[cost_col]
        ).sum()
    )

    total_performance = float(
        _numeric(
            selected[quality_col]
        ).sum()
    )

    objective_total = float(
        selected["_objective_score"].sum()
    )

    def mean_or_none(column: str):

        if column not in selected.columns:
            return None

        value = _numeric(
            selected[column]
        ).mean()

        return (
            round(float(value), 1)
            if pd.notna(value)
            else None
        )

    output_columns = [
        "player_id",
        name_col,
        position_col,
        "club_name",
        "league_name",
        quality_col,
        cost_col,
        "fair_value_eur",
        "value_gap_pct",
        "development_potential",
        "expected_performance_12m",
        "age_fifa",
        "playing_time_min",
        "sample_reliability_score",
        "recruitment_risk_tier",
        "_objective_score",
    ]

    output_columns = [
        c
        for c in output_columns
        if c in selected.columns
    ]

    selected_players = (
        selected[
            output_columns
        ]
        .rename(
            columns={
                "_objective_score": "optimizer_score"
            }
        )
        .to_dict(
            orient="records"
        )
    )

    return {
        "status": "optimal",
        "formation": formation,
        "strategy": strategy,
        "strategy_label": STRATEGIES[strategy]["label"],
        "strategy_description": STRATEGIES[strategy]["description"],
        "strategy_weights": {
            k: STRATEGIES[strategy][k]
            for k in [
                "performance",
                "expected_12m",
                "potential",
                "value",
                "reliability",
            ]
        },
        "budget_eur": budget_eur,
        "candidate_pool_size": int(
            len(prepared)
        ),
        "selected_count": int(
            len(selected)
        ),
        "total_cost_eur": total_cost,
        "budget_remaining_eur": (
            budget_eur - total_cost
            if budget_eur is not None
            else None
        ),
        "budget_utilization_pct": (
            round(
                total_cost
                / budget_eur
                * 100,
                1,
            )
            if budget_eur
            and budget_eur > 0
            else None
        ),
        "projected_squad_quality": (
            round(
                total_performance
                / len(selected),
                1,
            )
            if len(selected)
            else 0
        ),
        "average_age": mean_or_none(
            "age_fifa"
        ),
        "average_potential": mean_or_none(
            "development_potential"
        ),
        "average_expected_performance_12m": (
            mean_or_none(
                "expected_performance_12m"
            )
        ),
        "average_reliability": mean_or_none(
            "sample_reliability_score"
        ),
        "average_value_gap_pct": mean_or_none(
            "value_gap_pct"
        ),
        "objective_score": (
            round(
                objective_total
                / len(selected),
                1,
            )
            if len(selected)
            else 0
        ),
        "selected_players": selected_players,
        "methodology": {
            "optimization": (
                "0/1 integer linear program with exact "
                "formation-position constraints and an "
                "optional hard budget ceiling."
            ),
            "objective": (
                "Transparent weighted combination of "
                "normalized current performance, "
                "12-month expected performance, "
                "development potential, value efficiency "
                "and sample reliability."
            ),
            "value_boundary": (
                "Market value and fair value are used as "
                "analytical signals; they are not asserted "
                "to be transfer fees or contract terms."
            ),
        },
    }


def simulate_transfer(
    current_squad_quality: float,
    outgoing_quality: float,
    incoming_quality: float,
    squad_size_before: int,
    squad_size_after: int | None = None,
) -> dict:
    """Calculate the before/after average quality for a transfer action."""

    if squad_size_before <= 0:
        raise ValueError(
            "squad_size_before must be positive."
        )

    squad_size_after = (
        squad_size_after
        if squad_size_after is not None
        else squad_size_before
    )

    if squad_size_after <= 0:
        raise ValueError(
            "squad_size_after must be positive."
        )

    total_before = (
        current_squad_quality
        * squad_size_before
    )

    total_after = (
        total_before
        - outgoing_quality
        + incoming_quality
    )

    new_average = (
        total_after
        / squad_size_after
    )

    return {
        "before_squad_rating": round(
            current_squad_quality,
            1,
        ),
        "after_squad_rating": round(
            new_average,
            1,
        ),
        "delta": round(
            new_average
            - current_squad_quality,
            1,
        ),
    }