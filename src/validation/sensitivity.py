"""Weight sensitivity analysis.

Every weight in this project (role-fit component weights, performance-
score component weights) is a declared judgment call, not something
fitted or calibrated against an outcome. That's fine and stated
throughout the docs -- but it leaves one real question unanswered: if
those weights are off by a plausible margin, does the RANKING that comes
out the other end actually change? A score that's stable under +/-20%
weight perturbation is trustworthy even though the weights are
subjective. A score where the #1 ranked player flips under small
perturbations is fragile, and that fragility is worth knowing about
before handing a ranked list to a sporting director as a recommendation.

Method: for N trials, perturb each declared weight by a random factor in
[1-magnitude, 1+magnitude], renormalize so the weights still sum to the
same total (so perturbation changes RELATIVE emphasis, not overall
scale), recompute the ranking, and compare to the original via:
  - Spearman rank correlation across the full ranked pool
  - Top-10 overlap: how many of the original top 10 remain in the
    perturbed top 10
  - Top-1 stability: how often the #1 player is unchanged
"""
from __future__ import annotations

import random

import pandas as pd

from src.features.role_archetypes import compute_role_fit, ROLE_ARCHETYPES
from src.features.performance_score import compute_performance_score, POSITION_COMPONENT_WEIGHTS


def _perturb(weights: dict[str, float], magnitude: float, rng: random.Random) -> dict[str, float]:
    total = sum(weights.values())
    perturbed = {k: v * rng.uniform(1 - magnitude, 1 + magnitude) for k, v in weights.items()}
    perturbed_total = sum(perturbed.values())
    # Renormalize back to the original total so a perturbation trial
    # changes relative emphasis between features, not the overall scale
    # (which would trivially move every score up or down together and
    # tell us nothing about ranking stability).
    scale = total / perturbed_total if perturbed_total else 1.0
    return {k: v * scale for k, v in perturbed.items()}


def _spearman(a: pd.Series, b: pd.Series) -> float:
    ranks_a = a.rank()
    ranks_b = b.rank()
    return float(ranks_a.corr(ranks_b, method="pearson"))  # corr of ranks == Spearman


def role_fit_sensitivity(
    df: pd.DataFrame, role: str, n_trials: int = 50, magnitude: float = 0.2, seed: int = 42
) -> dict:
    # Players have several seasons: join on (player_id, season) or the comparison becomes many-to-many.
    _JOIN_KEYS = ["player_id", "season"] if "season" in df.columns else ["player_id"]
    rng = random.Random(seed)
    base_weights = ROLE_ARCHETYPES[role]["weights"]

    baseline = compute_role_fit(df, role)
    baseline_ranked = baseline.dropna(subset=["role_fit_score"]).sort_values("role_fit_score", ascending=False)
    baseline_top10 = set(baseline_ranked.head(10)["player_id"])
    baseline_top1 = baseline_ranked.iloc[0]["player_id"] if len(baseline_ranked) else None

    correlations, overlaps, top1_matches = [], [], []
    for _ in range(n_trials):
        trial_weights = _perturb(base_weights, magnitude, rng)
        trial = compute_role_fit(df, role, weights_override=trial_weights)
        trial_ranked = trial.dropna(subset=["role_fit_score"]).sort_values("role_fit_score", ascending=False)

        merged = baseline_ranked[_JOIN_KEYS + ["role_fit_score"]].merge(
            trial_ranked[_JOIN_KEYS + ["role_fit_score"]], on=_JOIN_KEYS, suffixes=("_base", "_trial")
        )
        correlations.append(_spearman(merged["role_fit_score_base"], merged["role_fit_score_trial"]))

        trial_top10 = set(trial_ranked.head(10)["player_id"])
        overlaps.append(len(baseline_top10 & trial_top10) / 10)

        trial_top1 = trial_ranked.iloc[0]["player_id"] if len(trial_ranked) else None
        top1_matches.append(trial_top1 == baseline_top1)

    return {
        "role": role,
        "n_trials": n_trials,
        "perturbation_magnitude": magnitude,
        "mean_rank_correlation": round(sum(correlations) / len(correlations), 3),
        "min_rank_correlation": round(min(correlations), 3),
        "mean_top10_overlap": round(sum(overlaps) / len(overlaps), 3),
        "top1_stability_rate": round(sum(top1_matches) / len(top1_matches), 3),
        "baseline_top1": baseline_top1,
    }


def performance_score_sensitivity(
    df: pd.DataFrame, position: str, n_trials: int = 50, magnitude: float = 0.2, seed: int = 42
) -> dict:
    if position not in POSITION_COMPONENT_WEIGHTS:
        raise ValueError(f"Unknown position: {position}. Available: {list(POSITION_COMPONENT_WEIGHTS)}")

    # Players have several seasons: join on (player_id, season) or the comparison becomes many-to-many.
    _JOIN_KEYS = ["player_id", "season"] if "season" in df.columns else ["player_id"]
    rng = random.Random(seed)
    base_weights = POSITION_COMPONENT_WEIGHTS[position]
    pool = df[df["canonical_position"] == position].copy()

    baseline = compute_performance_score(pool)
    baseline_ranked = baseline.dropna(subset=["performance_score"]).sort_values("performance_score", ascending=False)
    baseline_top10 = set(baseline_ranked.head(10)["player_id"])
    baseline_top1 = baseline_ranked.iloc[0]["player_id"] if len(baseline_ranked) else None

    correlations, overlaps, top1_matches = [], [], []
    for _ in range(n_trials):
        trial_weights = _perturb(base_weights, magnitude, rng)
        trial = compute_performance_score(pool, weights_override={position: trial_weights})
        trial_ranked = trial.dropna(subset=["performance_score"]).sort_values("performance_score", ascending=False)

        merged = baseline_ranked[_JOIN_KEYS + ["performance_score"]].merge(
            trial_ranked[_JOIN_KEYS + ["performance_score"]], on=_JOIN_KEYS, suffixes=("_base", "_trial")
        )
        correlations.append(_spearman(merged["performance_score_base"], merged["performance_score_trial"]))

        trial_top10 = set(trial_ranked.head(10)["player_id"])
        overlaps.append(len(baseline_top10 & trial_top10) / 10)

        trial_top1 = trial_ranked.iloc[0]["player_id"] if len(trial_ranked) else None
        top1_matches.append(trial_top1 == baseline_top1)

    return {
        "position": position,
        "n_trials": n_trials,
        "perturbation_magnitude": magnitude,
        "mean_rank_correlation": round(sum(correlations) / len(correlations), 3),
        "min_rank_correlation": round(min(correlations), 3),
        "mean_top10_overlap": round(sum(overlaps) / len(overlaps), 3),
        "top1_stability_rate": round(sum(top1_matches) / len(top1_matches), 3),
        "baseline_top1": baseline_top1,
    }
