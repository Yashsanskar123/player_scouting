import pandas as pd


def _resolve_column(df: pd.DataFrame, *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def add_player_master_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create initial player-level analytics features for scouting and team-building."""
    df = df.copy()

    if 'player_name' not in df.columns:
        player_name_candidates = [
            ('short_name', 'long_name'),
            ('long_name', 'short_name'),
            ('player', 'long_name'),
            ('player', 'short_name'),
        ]

        for primary_candidate, fallback_candidate in player_name_candidates:
            if primary_candidate in df.columns:
                if fallback_candidate in df.columns:
                    df['player_name'] = df[primary_candidate].fillna(df[fallback_candidate])
                else:
                    df['player_name'] = df[primary_candidate]
                break

    age_col = _resolve_column(df, 'age_fifa', 'age', 'age_fbref')
    if age_col:
        df['age_fifa'] = pd.to_numeric(df[age_col], errors='coerce')

    overall_col = _resolve_column(df, 'overall', 'overall_rating')
    if overall_col:
        df['overall'] = pd.to_numeric(df[overall_col], errors='coerce')

    potential_col = _resolve_column(df, 'potential', 'potential_rating')
    if potential_col:
        df['potential'] = pd.to_numeric(df[potential_col], errors='coerce')

    value_col = _resolve_column(df, 'value_eur', 'value', 'value_eur_clean')
    if value_col:
        df['value_eur'] = pd.to_numeric(df[value_col], errors='coerce')

    if 'age_fifa' in df.columns:
        df['age_band'] = pd.cut(
            df['age_fifa'],
            bins=[0, 20, 24, 28, 32, 100],
            labels=['U20', '21-24', '25-28', '29-32', '33+'],
            right=False,
        )

    if {'overall', 'potential'}.issubset(df.columns):
        df['current_value_score'] = df['overall'] * 1.5 + df['potential'] * 1.0
        if 'age_fifa' in df.columns:
            df['development_score'] = df['potential'] - df['overall'] + (100 - df['age_fifa']) * 0.5
        else:
            df['development_score'] = df['potential'] - df['overall']

    if 'value_eur' in df.columns:
        value_eur = pd.to_numeric(df['value_eur'], errors='coerce').replace(0, pd.NA)
        if 'overall' in df.columns:
            df['value_efficiency'] = pd.to_numeric(df['overall'], errors='coerce') / value_eur
        else:
            df['value_efficiency'] = 0
        df['value_efficiency'] = df['value_efficiency'].fillna(0)

    if 'preferred_foot' in df.columns:
        df['is_right_footed'] = df['preferred_foot'].fillna('').str.lower().eq('right')

    return df


def add_team_building_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create basic team-building help features."""
    df = df.copy()

    league_col = _resolve_column(df, 'league_name', 'league')
    if league_col:
        df['league_name'] = df[league_col].fillna('').astype(str)

    if 'league_name' in df.columns:
        top_leagues = {'Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1'}
        df['is_top_league'] = df['league_name'].fillna('').isin(top_leagues)

    if 'international_reputation' in df.columns:
        df['is_international_level'] = pd.to_numeric(df['international_reputation'], errors='coerce').fillna(0) >= 2

    if 'club_name' in df.columns:
        df['club_name_clean'] = df['club_name'].fillna('').astype(str).str.strip()

    return df
