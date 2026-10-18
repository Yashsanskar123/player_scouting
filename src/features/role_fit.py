from __future__ import annotations

import pandas as pd


ROLE_COLUMNS = {
    'ST': ['shooting', 'pace', 'dribbling', 'physic'],
    'LW': ['pace', 'dribbling', 'shooting', 'passing'],
    'RW': ['pace', 'dribbling', 'shooting', 'passing'],
    'CAM': ['passing', 'dribbling', 'shooting', 'vision'],
    'CM': ['passing', 'defending', 'dribbling', 'physic'],
    'CDM': ['defending', 'passing', 'physic', 'pace'],
    'CB': ['defending', 'physic', 'pace', 'passing'],
    'LB': ['pace', 'defending', 'passing', 'dribbling'],
    'RB': ['pace', 'defending', 'passing', 'dribbling'],
    'GK': ['goalkeeping_diving', 'goalkeeping_handling', 'goalkeeping_reflexes', 'goalkeeping_positioning'],
}


def _resolve_role_columns(target_role: str) -> list[str]:
    role_columns = ROLE_COLUMNS.get(target_role.upper(), [])
    return [col for col in role_columns if col in pd.Index([])]


def compute_role_fit_scores(df: pd.DataFrame, target_role: str) -> pd.DataFrame:
    """Score players against a target role using the most relevant skill attributes."""
    result = df.copy()
    target_role = target_role.upper()

    role_columns = ROLE_COLUMNS.get(target_role, [])
    if not role_columns:
        raise ValueError(f"Unsupported target role: {target_role}")

    result['role_fit_score'] = 0.0

    for column in role_columns:
        if column in result.columns:
            numeric_values = pd.to_numeric(result[column], errors='coerce').fillna(0)
            result['role_fit_score'] += numeric_values / 100

    if 'overall' in result.columns:
        result['role_fit_score'] += pd.to_numeric(result['overall'], errors='coerce').fillna(0) / 100 * 0.5

    if 'scouting_score' in result.columns:
        result['role_fit_score'] += pd.to_numeric(result['scouting_score'], errors='coerce').fillna(0) / 100 * 0.2

    result['role_fit_score'] = result['role_fit_score'].clip(0, 1.5)
    return result.sort_values('role_fit_score', ascending=False).reset_index(drop=True)


def score_team_composition(df: pd.DataFrame, formation: str = '4-3-3') -> dict[str, object]:
    """Score a squad for balance and coverage across positions."""
    if df.empty:
        return {'team_score': 0, 'position_coverage': {}, 'formation': formation}

    position_map = {
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

    formation_parts = [part for part in formation.split('-') if part]
    total_players = sum(int(part) for part in formation_parts)

    positions_needed = {}
    for part in formation_parts:
        if part:
            positions_needed[int(part)] = positions_needed.get(int(part), 0) + 1

    coverage = {}

    for position, count in position_map.items():
        position_count = 0
        for player in df['player_positions'].fillna('').astype(str):
            if position in player.upper():
                position_count += 1
        coverage[position] = position_count

    position_coverage = {position: min(count, 1) for position, count in coverage.items()}

    team_score = 0.0
    for position, count in coverage.items():
        if position in position_coverage:
            team_score += min(count / max(1, position_map[position]), 1)

    team_score = team_score / len(position_map) * 100

    return {
        'team_score': round(team_score, 2),
        'position_coverage': position_coverage,
        'formation': formation,
        'total_players_expected': total_players,
        'players_available': len(df),
    }
