import pandas as pd


def _resolve_column(df: pd.DataFrame, *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def calculate_player_scouting_score(df: pd.DataFrame) -> pd.DataFrame:
    """Create a simple scouting score for initial ranking."""
    df = df.copy()

    def safe_numeric(series_or_value, default=0):
        if series_or_value is None:
            return pd.Series(default, index=df.index)
        if isinstance(series_or_value, pd.Series):
            return pd.to_numeric(series_or_value, errors='coerce').fillna(default)
        return pd.Series(pd.to_numeric([series_or_value] * len(df), errors='coerce').fillna(default), index=df.index)

    overall_col = _resolve_column(df, 'overall', 'overall_rating')
    potential_col = _resolve_column(df, 'potential', 'potential_rating')
    current_value_score_col = _resolve_column(df, 'current_value_score')
    development_score_col = _resolve_column(df, 'development_score')
    value_efficiency_col = _resolve_column(df, 'value_efficiency')

    overall = safe_numeric(df.get(overall_col) if overall_col else None)
    potential = safe_numeric(df.get(potential_col) if potential_col else None)
    current_value_score = safe_numeric(df.get(current_value_score_col) if current_value_score_col else None)
    development_score = safe_numeric(df.get(development_score_col) if development_score_col else None)
    value_efficiency = safe_numeric(df.get(value_efficiency_col) if value_efficiency_col else None)

    df['scouting_score'] = (
        overall * 0.45
        + potential * 0.25
        + current_value_score * 0.10
        + development_score * 0.10
        + value_efficiency * 20
    )

    return df
