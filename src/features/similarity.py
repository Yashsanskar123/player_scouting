from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from src.features.role_fit import compute_role_fit_scores


DEFAULT_FEATURE_COLUMNS = [
    'overall',
    'potential',
    'value_eur',
    'age_fifa',
    'pace',
    'shooting',
    'passing',
    'dribbling',
    'defending',
    'physic',
    'international_reputation',
    'weak_foot',
    'skill_moves',
]


def _resolve_feature_columns(df: pd.DataFrame, feature_columns: Iterable[str] | None = None) -> list[str]:
    available_columns = [col for col in (feature_columns or DEFAULT_FEATURE_COLUMNS) if col in df.columns]
    if not available_columns:
        raise ValueError("No compatible feature columns found for similarity scoring.")
    return available_columns


def _prepare_similarity_matrix(df: pd.DataFrame, feature_columns: Iterable[str] | None = None) -> tuple[pd.DataFrame, np.ndarray]:
    feature_columns = _resolve_feature_columns(df, feature_columns)
    working_df = df.copy()

    for column in feature_columns:
        working_df[column] = pd.to_numeric(working_df[column], errors='coerce').fillna(0)

    standardized = (working_df[feature_columns] - working_df[feature_columns].mean()) / working_df[feature_columns].std(ddof=0).replace(0, 1)
    standardized = standardized.fillna(0)
    values = standardized.to_numpy(dtype=float)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1

    return working_df, values / norms


def find_similar_players(
    df: pd.DataFrame,
    player_identifier: str,
    top_n: int = 5,
    feature_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Return the most similar players to a selected player using cosine similarity."""
    if df.empty:
        return df.copy()

    working_df, normalized_vectors = _prepare_similarity_matrix(df, feature_columns)

    player_name_col = None
    for candidate in ('player_name', 'short_name', 'long_name'):
        if candidate in working_df.columns:
            player_name_col = candidate
            break

    if player_name_col is None:
        raise ValueError("The dataset must contain a player name column for similarity lookup.")

    text_lookup = player_identifier.strip().lower()
    matches = working_df[player_name_col].fillna('').str.lower().str.contains(text_lookup, na=False)

    if not matches.any():
        raise ValueError(f"No player matched the identifier '{player_identifier}'.")

    row_index = matches.idxmax()
    target_vector = normalized_vectors[row_index]

    similarities = normalized_vectors @ target_vector
    similarities[row_index] = -1

    top_indices = np.argsort(similarities)[::-1][:top_n]

    result = working_df.iloc[top_indices].copy()
    result['similarity_score'] = similarities[top_indices]
    result = result.sort_values('similarity_score', ascending=False)

    return result.reset_index(drop=True)


def recommend_team_fit(
    df: pd.DataFrame,
    target_profile: dict | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """Rank players by how well they fit a target team profile."""
    if df.empty:
        return df.copy()

    target_profile = target_profile or {}

    working_df = df.copy()
    working_df['team_fit_score'] = 0

    min_overall = float(target_profile.get('min_overall', 70))
    max_budget_eur = target_profile.get('max_budget_eur')
    preferred_foot = (target_profile.get('preferred_foot') or '').strip().lower()
    target_positions = [item.strip().lower() for item in (target_profile.get('target_positions') or []) if item and item.strip()]

    if 'overall' in working_df.columns:
        working_df['team_fit_score'] += working_df['overall'].fillna(0) / 100 * 40

    if 'potential' in working_df.columns:
        working_df['team_fit_score'] += working_df['potential'].fillna(0) / 100 * 20

    if 'value_eur' in working_df.columns and max_budget_eur:
        working_df['value_eur'] = pd.to_numeric(working_df['value_eur'], errors='coerce').fillna(0)
        working_df['team_fit_score'] += (1 - (working_df['value_eur'] / max_budget_eur).clip(0, 1)) * 15

    if 'age_fifa' in working_df.columns:
        age_score = 1 - np.abs(working_df['age_fifa'].fillna(25) - target_profile.get('preferred_age', 25)) / 20
        working_df['team_fit_score'] += age_score.clip(0, 1) * 10

    if preferred_foot and 'preferred_foot' in working_df.columns:
        working_df['team_fit_score'] += working_df['preferred_foot'].fillna('').str.lower().eq(preferred_foot) * 10

    if 'is_top_league' in working_df.columns:
        working_df['team_fit_score'] += working_df['is_top_league'].astype(int) * 5

    if 'is_international_level' in working_df.columns:
        working_df['team_fit_score'] += working_df['is_international_level'].astype(int) * 5

    if target_positions:
        player_positions = working_df.get('player_positions', pd.Series([''] * len(working_df), index=working_df.index)).fillna('').astype(str)
        positions_match = player_positions.str.lower().str.split(',').apply(lambda values: any(value.strip() in target_positions for value in values if value.strip()))
        working_df['team_fit_score'] += positions_match.astype(int) * 15

    working_df['team_fit_score'] += working_df.get('scouting_score', 0).fillna(0) / 100 * 20

    working_df = working_df.loc[working_df.get('overall', 0).fillna(0) >= min_overall].copy()

    return working_df.sort_values('team_fit_score', ascending=False).head(top_n).reset_index(drop=True)


def optimize_squad(
    df: pd.DataFrame,
    formation: str = '4-3-3',
    top_n: int = 5,
) -> dict[str, object]:
    """Recommend a balanced squad mix based on positional coverage and scouting score."""
    if df.empty:
        return {
            'formation': formation,
            'team_score': 0,
            'recommended_players': [],
            'position_coverage': {},
        }

    working_df = df.copy()
    working_df['recommended_rank'] = pd.to_numeric(working_df.get('scouting_score', 0), errors='coerce').fillna(0)

    formation_parts = [int(part) for part in formation.split('-') if part.isdigit()]
    if not formation_parts:
        raise ValueError(f"Unsupported formation: {formation}")

    position_targets = {
        'GK': 1,
        'LB': 1,
        'CB': 2,
        'RB': 1,
        'CM': 2,
        'CDM': 1,
        'CAM': 1,
        'LW': 1,
        'RW': 1,
        'ST': 1,
    }

    coverage = {position: 0 for position in position_targets}
    for player_positions in working_df.get('player_positions', pd.Series([''] * len(working_df), index=working_df.index)).fillna('').astype(str):
        for position in position_targets:
            if position in player_positions.upper():
                coverage[position] += 1

    recommended = working_df.sort_values(['recommended_rank', 'overall'], ascending=[False, False]).head(top_n).copy()
    recommended['team_fit_score'] = pd.to_numeric(recommended.get('scouting_score', 0), errors='coerce').fillna(0)

    return {
        'formation': formation,
        'team_score': round(float(recommended['team_fit_score'].mean()) if not recommended.empty else 0, 2),
        'recommended_players': recommended[['player_name', 'player_positions', 'overall', 'scouting_score']].to_dict(orient='records'),
        'position_coverage': coverage,
    }


def build_player_scouting_report(
    df: pd.DataFrame,
    player_identifier: str,
    target_role: str = 'ST',
    top_n: int = 5,
) -> dict[str, object]:
    """Build a richer scouting report for a selected player."""
    if df.empty:
        return {
            'player': {},
            'similar_players': [],
            'role_fit': {},
            'team_fit_candidates': [],
        }

    player_name_col = None
    for candidate in ('player_name', 'short_name', 'long_name'):
        if candidate in df.columns:
            player_name_col = candidate
            break

    if player_name_col is None:
        raise ValueError("The dataset must contain a player name column for scouting report generation.")

    text_lookup = (player_identifier or '').strip().lower()
    if not text_lookup:
        raise ValueError("A player identifier is required for the scouting report.")

    player_matches = df[player_name_col].fillna('').str.lower().str.contains(text_lookup, na=False)
    if not player_matches.any():
        raise ValueError(f"No player matched the identifier '{player_identifier}'.")

    player_index = player_matches.idxmax()
    player_row = df.loc[player_index].copy()

    similar_players = find_similar_players(df, player_identifier=player_identifier, top_n=top_n)
    role_fit_scores = compute_role_fit_scores(df, target_role=target_role)

    player_label = str(player_row.get(player_name_col, '') or '').strip().lower()
    role_fit_row = role_fit_scores.loc[
        role_fit_scores[player_name_col].fillna('').str.lower().eq(player_label)
    ]

    player_snapshot = {
        'player_name': player_row.get(player_name_col),
        'overall': player_row.get('overall'),
        'potential': player_row.get('potential'),
        'age_fifa': player_row.get('age_fifa'),
        'league_name': player_row.get('league_name'),
        'preferred_foot': player_row.get('preferred_foot'),
        'player_positions': player_row.get('player_positions'),
        'scouting_score': player_row.get('scouting_score'),
        'value_eur': player_row.get('value_eur'),
        'is_top_league': player_row.get('is_top_league'),
        'is_international_level': player_row.get('is_international_level'),
    }

    role_fit_snapshot = {}
    if not role_fit_row.empty:
        role_fit_snapshot = role_fit_row.iloc[0].to_dict()

    team_fit_candidates = recommend_team_fit(
        df,
        target_profile={
            'min_overall': player_row.get('overall', 70),
            'max_budget_eur': player_row.get('value_eur', 0) * 1.5 or None,
            'preferred_age': int(player_row.get('age_fifa', 25) or 25),
            'preferred_foot': player_row.get('preferred_foot'),
            'target_positions': [position.strip() for position in str(player_row.get('player_positions', '')).split(',') if position.strip()],
        },
        top_n=top_n,
    )

    return {
        'player': player_snapshot,
        'similar_players': similar_players.to_dict(orient='records'),
        'role_fit': role_fit_snapshot,
        'team_fit_candidates': team_fit_candidates.to_dict(orient='records'),
    }
