"""Market value model (spec section 27), replacing the fabricated
`overall*150000 + potential*120000 + ...` formula with an actual trained
regression model.

Model: HistGradientBoostingRegressor (sklearn) predicting value_eur (we
avoid xgboost/lightgbm as hard dependencies to keep the environment
lightweight; swapping in XGBoost is a drop-in change if preferred).

Leakage guards (spec section 67):
  - We do NOT use `wage_eur` as a feature (wages are typically set with
    knowledge of market value -- using it would leak the target).
  - We do NOT use any feature derived FROM value_eur (e.g. the old
    value_efficiency) as an input.
  - Train/test split is done BEFORE any scaling/imputation is fit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

TARGET = "value_eur"

FEATURE_COLUMNS = [
    "age_fifa", "overall", "potential", "pace", "shooting", "passing", "dribbling",
    "defending", "physic", "international_reputation", "skill_moves", "weak_foot",
    "performance_score", "component_attacking", "component_chance_creation",
    "component_passing", "component_progression", "component_defending",
    "sample_reliability_score", "positional_versatility_score",
]
CATEGORICAL_COLUMNS = ["canonical_position", "league_name"]


def _build_category_maps(df: pd.DataFrame) -> dict[str, dict]:
    """Fit categorical -> integer-code maps ONCE on the full dataset, so
    training and later prediction always use the same encoding (avoids
    silent code mismatches if predict is later called on a subset)."""
    maps = {}
    for c in CATEGORICAL_COLUMNS:
        if c in df.columns:
            categories = sorted(df[c].dropna().unique().tolist())
            maps[c] = {cat: i for i, cat in enumerate(categories)}
    return maps


def _apply_category_maps(df: pd.DataFrame, maps: dict[str, dict]) -> pd.DataFrame:
    df = df.copy()
    for c, mapping in maps.items():
        if c in df.columns:
            df[c] = df[c].map(mapping)
    return df


def _build_training_frame(df: pd.DataFrame, category_maps: dict[str, dict]) -> pd.DataFrame:
    cols = [c for c in FEATURE_COLUMNS if c in df.columns] + [c for c in CATEGORICAL_COLUMNS if c in df.columns]
    keep_cols = cols + [TARGET]
    if "player_id" in df.columns:
        keep_cols = keep_cols + ["player_id"]
    frame = df[keep_cols].copy()
    frame = frame[frame[TARGET].notna() & (frame[TARGET] > 0)]
    frame = _apply_category_maps(frame, category_maps)
    for c in FEATURE_COLUMNS:
        if c in frame.columns:
            frame[c] = pd.to_numeric(frame[c], errors="coerce")
    return frame


def train_valuation_model(df: pd.DataFrame, random_state: int = 42) -> dict:
    """Train the model and return it along with evaluation metrics and
    feature importances. Uses log1p(value_eur) as the regression target
    since transfer values are heavily right-skewed.
    """
    category_maps = _build_category_maps(df)
    frame = _build_training_frame(df, category_maps)
    feature_cols = [c for c in frame.columns if c not in (TARGET, "player_id")]

    X = frame[feature_cols]
    y = np.log1p(frame[TARGET])

    # Group split by player_id, NOT a plain random row split: 85% of rows
    # in this dataset belong to a player with multiple seasons, and their
    # stats are highly autocorrelated season-to-season. A random split lets
    # the same player leak across train/test, which inflates accuracy
    # metrics without the model actually generalizing to a player it has
    # never seen. Grouping by player_id is the honest evaluation.
    if "player_id" in frame.columns:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
        train_idx, test_idx = next(splitter.split(X, y, groups=frame["player_id"]))
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    else:
        X_train, X_test, y_train, y_test = X, X, y, y  # degrades gracefully if player_id absent

    model = HistGradientBoostingRegressor(
        max_iter=300, max_depth=6, learning_rate=0.08, random_state=random_state,
    )
    model.fit(X_train, y_train)

    pred_test_log = model.predict(X_test)
    pred_test = np.expm1(pred_test_log)
    actual_test = np.expm1(y_test)

    mae = mean_absolute_error(actual_test, pred_test)
    rmse = mean_squared_error(actual_test, pred_test) ** 0.5
    r2 = r2_score(y_test, pred_test_log)  # R^2 computed in log-space, the space the model was fit in
    mape = float(np.mean(np.abs((actual_test - pred_test) / actual_test.replace(0, np.nan).fillna(1))) * 100)

    importance = permutation_importance(model, X_test, y_test, n_repeats=5, random_state=random_state)
    importance_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": importance.importances_mean,
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    return {
        "model": model,
        "feature_columns": feature_cols,
        "category_maps": category_maps,
        "metrics": {
            "MAE_eur": round(float(mae), 0),
            "RMSE_eur": round(float(rmse), 0),
            "R2_log_space": round(float(r2), 4),
            "MAPE_pct": round(mape, 2),
            "n_train": len(X_train),
            "n_test": len(X_test),
        },
        "feature_importance": importance_df,
    }


def predict_fair_value(model_bundle: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Apply a trained model bundle to produce fair_value_eur predictions
    and a value gap vs actual market value_eur for every row (spec 28).
    """
    frame = df.copy()  # this is what gets returned -- keep human-readable columns intact
    encoded = _apply_category_maps(frame, model_bundle["category_maps"])  # separate frame, used only to build X

    feature_cols = model_bundle["feature_columns"]
    for c in feature_cols:
        if c not in encoded.columns:
            encoded[c] = np.nan
        elif c in FEATURE_COLUMNS:
            encoded[c] = pd.to_numeric(encoded[c], errors="coerce")

    X = encoded[feature_cols]
    pred_log = model_bundle["model"].predict(X)
    frame["fair_value_eur"] = np.expm1(pred_log).round(0)

    if "value_eur" in df.columns:
        actual = pd.to_numeric(df["value_eur"], errors="coerce")
        frame["value_eur"] = actual
        frame["value_gap_eur"] = frame["fair_value_eur"] - actual
        frame["value_gap_pct"] = np.where(actual > 0, frame["value_gap_eur"] / actual * 100, np.nan)

    return frame
