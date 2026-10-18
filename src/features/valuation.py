from __future__ import annotations

import numpy as np
import pandas as pd


def segment_players_by_value(df: pd.DataFrame) -> pd.DataFrame:
    """Assign a value-tier segment to players based on market value and performance."""
    result = df.copy()

    if 'value_eur' in result.columns:
        result['value_eur'] = pd.to_numeric(result['value_eur'], errors='coerce').fillna(0)

    performance_score = 0
    if 'scouting_score' in result.columns:
        performance_score = pd.to_numeric(result['scouting_score'], errors='coerce').fillna(0)
    elif {'overall', 'potential'}.issubset(result.columns):
        performance_score = (
            pd.to_numeric(result['overall'], errors='coerce').fillna(0) * 0.7
            + pd.to_numeric(result['potential'], errors='coerce').fillna(0) * 0.3
        )

    result['value_performance_ratio'] = 0
    if 'value_eur' in result.columns:
        result['value_performance_ratio'] = (
            performance_score / result['value_eur'].replace(0, pd.NA)
        )
        result['value_performance_ratio'] = result['value_performance_ratio'].fillna(0)

    value_thresholds = [0, 2_000_000, 5_000_000, 10_000_000, 20_000_000, float('inf')]
    segment_labels = ['Emerging', 'Budget', 'Value', 'Premium', 'Elite']

    if 'value_eur' in result.columns:
        result['value_segment'] = pd.cut(
            result['value_eur'],
            bins=value_thresholds,
            labels=segment_labels,
            right=False,
        )
        result['value_segment'] = result['value_segment'].fillna('Elite')

    return result


def score_team_chemistry(df: pd.DataFrame) -> dict[str, object]:
    """Estimate team chemistry using position balance and player profile similarity."""
    if df.empty:
        return {
            'team_chemistry_score': 0,
            'position_balance': {},
            'age_balance': 0,
        }

    balance = {'ST': 0, 'CM': 0, 'CB': 0, 'GK': 0}
    total_players = len(df)

    for player in df['player_positions'].fillna('').astype(str):
        for position in balance:
            if position in player.upper():
                balance[position] += 1

    position_balance = {position: round(count / max(total_players, 1), 2) for position, count in balance.items()}

    ages = pd.to_numeric(df.get('age_fifa', pd.Series([25] * len(df))), errors='coerce').fillna(25)
    age_balance = round(1 - (ages.std(ddof=0) / 10), 2)

    chemistry_score = 0
    chemistry_score += sum(position_balance.values()) / len(position_balance) * 50
    chemistry_score += max(0, age_balance) * 50

    return {
        'team_chemistry_score': round(chemistry_score, 2),
        'position_balance': position_balance,
        'age_balance': round(age_balance, 2),
    }


def find_market_opportunities(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Find players with the strongest value-for-performance upside."""
    if df.empty:
        return df.copy()

    result = df.copy()

    if 'scouting_score' in result.columns:
        scout_score = pd.to_numeric(result['scouting_score'], errors='coerce').fillna(0)
    else:
        overall = pd.to_numeric(result.get('overall', pd.Series(0, index=result.index)), errors='coerce').fillna(0)
        potential = pd.to_numeric(result.get('potential', pd.Series(0, index=result.index)), errors='coerce').fillna(0)
        scout_score = (overall * 0.7) + (potential * 0.3)

    if 'potential' in result.columns:
        potential = pd.to_numeric(result['potential'], errors='coerce').fillna(0)
    else:
        potential = pd.Series(0, index=result.index)

    if 'value_eur' in result.columns:
        value_eur = pd.to_numeric(result['value_eur'], errors='coerce').fillna(0)
    else:
        value_eur = pd.Series(0, index=result.index)

    max_value = value_eur.max()
    if pd.notna(max_value) and max_value > 0:
        normalized_value = (value_eur / max_value).clip(0, 1)
        value_opportunity = (1 - normalized_value) * 100
    else:
        value_opportunity = pd.Series(0, index=result.index)

    result['opportunity_score'] = (
        scout_score * 0.45
        + potential * 0.30
        + value_opportunity * 0.25
    )
    result['opportunity_score'] = result['opportunity_score'].clip(0, 100)

    result['value_opportunity'] = value_opportunity

    return result.sort_values('opportunity_score', ascending=False).head(top_n).reset_index(drop=True)


def find_transfer_market_intelligence(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Estimate transfer-market leverage and fair-value signals for players."""
    if df.empty:
        return df.copy()

    result = df.copy()

    if 'value_eur' not in result.columns:
        result['value_eur'] = 0

    value_eur = pd.to_numeric(result['value_eur'], errors='coerce').fillna(0)
    overall = pd.to_numeric(result.get('overall', pd.Series(0, index=result.index)), errors='coerce').fillna(0)
    potential = pd.to_numeric(result.get('potential', pd.Series(0, index=result.index)), errors='coerce').fillna(0)
    scouting_score = pd.to_numeric(result.get('scouting_score', pd.Series(0, index=result.index)), errors='coerce').fillna(0)

    fair_market_value = (overall * 150000) + (potential * 120000) + (scouting_score * 250000)
    fair_market_value = fair_market_value.round(0)

    transfer_value_delta = fair_market_value - value_eur
    transfer_value_delta = transfer_value_delta.fillna(0)

    result['fair_market_value'] = fair_market_value
    result['transfer_value_delta'] = transfer_value_delta
    result['transfer_value_delta_pct'] = np.where(value_eur > 0, (transfer_value_delta / value_eur) * 100, 0)

    result['transfer_market_score'] = (
        (scouting_score / 100) * 40
        + (overall / 100) * 30
        + (potential / 100) * 20
        + np.where(transfer_value_delta > 0, 10, 0)
    )

    return result.sort_values('transfer_market_score', ascending=False).head(top_n).reset_index(drop=True)
