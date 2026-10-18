"""Generates a formal data dictionary for every column in the dataset, per
spec section 3. This is derived entirely from observable column properties
plus known FIFA/FBref naming conventions -- it does not invent semantics
for columns it can't identify.
"""
from __future__ import annotations

import pandas as pd

FIFA_ATTRIBUTE_COLS = {
    "overall", "potential", "value_eur", "wage_eur", "age_fifa", "height_cm", "weight_kg",
    "pace", "shooting", "passing", "dribbling", "defending", "physic",
    "goalkeeping_diving", "goalkeeping_handling", "goalkeeping_kicking",
    "goalkeeping_positioning", "goalkeeping_reflexes", "goalkeeping_speed",
    "preferred_foot", "weak_foot", "skill_moves", "international_reputation",
    "body_type", "born_fifa", "club_team_id", "club_name", "league_id",
    "league_name", "club_jersey_number", "nationality_name", "player_positions",
    "short_name", "long_name", "fifa_version",
}

FBREF_PREFIXES = ("per_90_minutes_", "standard_", "expected_", "sca_", "gca_",
                   "challenges_", "performance_", "penalty_kicks_", "total_",
                   "short_", "medium_", "long_")
FBREF_EXTRA_COLS = {"season", "player", "playing_time_mp", "playing_time_starts",
                    "playing_time_min", "playing_time_90s", "league", "team",
                    "nation", "pos", "age_fbref", "born_fbref"}


def _source(col: str) -> str:
    if col in FIFA_ATTRIBUTE_COLS:
        return "FIFA"
    if col in FBREF_EXTRA_COLS or col.startswith(FBREF_PREFIXES):
        return "FBref"
    return "derived"


def _is_per90(col: str) -> bool:
    return col.startswith("per_90_minutes_") or col.endswith("_90")


def _is_percentage(series: pd.Series, col: str) -> bool:
    return "pct" in col.lower()


def _valid_range(series: pd.Series) -> str:
    if not pd.api.types.is_numeric_dtype(series):
        return ""
    non_null = series.dropna()
    if non_null.empty:
        return ""
    return f"{non_null.min():.2f} to {non_null.max():.2f}"


def _aggregation(col: str, is_pct: bool, is_per90: bool) -> str:
    if is_per90:
        return "rate (per 90 minutes)"
    if is_pct:
        return "percentage"
    if col in {"value_eur", "wage_eur", "overall", "potential", "age_fifa"}:
        return "point-in-time attribute"
    return "total / count"


def build_data_dictionary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    n = len(df)
    for col in df.columns:
        series = df[col]
        is_pct = _is_percentage(series, col)
        is_per90 = _is_per90(col)
        missing = int(series.isna().sum())
        rows.append({
            "feature": col,
            "source": _source(col),
            "dtype": str(series.dtype),
            "aggregation": _aggregation(col, is_pct, is_per90),
            "missing_count": missing,
            "missingness_pct": round(missing / n * 100, 2) if n else 0.0,
            "valid_range": _valid_range(series),
            "is_percentage": is_pct,
            "is_per90_rate": is_per90,
        })
    return pd.DataFrame(rows).sort_values(["source", "feature"]).reset_index(drop=True)


def write_data_dictionary(df: pd.DataFrame, out_csv: str, out_md: str | None = None) -> pd.DataFrame:
    dictionary = build_data_dictionary(df)
    dictionary.to_csv(out_csv, index=False)

    if out_md:
        lines = ["# Data Dictionary", "", f"Total features: {len(dictionary)}", ""]
        lines.append("| Feature | Source | Aggregation | Missing % | Valid Range |")
        lines.append("|---|---|---|---|---|")
        for _, r in dictionary.iterrows():
            lines.append(
                f"| `{r['feature']}` | {r['source']} | {r['aggregation']} | "
                f"{r['missingness_pct']}% | {r['valid_range']} |"
            )
        with open(out_md, "w") as f:
            f.write("\n".join(lines))

    return dictionary
