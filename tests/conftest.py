"""Shared fixtures: a small, deterministic synthetic dataset run through
the REAL pipeline stages (identity -> taxonomy -> reliability ->
percentiles -> performance score -> potential -> risk), not hand-mocked
per-module inputs. This means tests exercise the actual integration
between stages, the same way production does, while staying fast and
fully deterministic (no dependence on the real 28k-row dataset, which
can change).
"""
from __future__ import annotations

import os

# The test-suite hits the API far faster than any real client: switch the limiters off unless a test enables them.
os.environ.setdefault("SCOUTIQ_RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("SCOUTIQ_HEAVY_RATE_LIMIT_PER_MINUTE", "0")

import pandas as pd
import pytest

from src.identity.resolve_identity import assign_player_ids
from src.taxonomy.positions import assign_position_taxonomy
from src.features.reliability import compute_reliability_score
from src.features.percentiles import compute_percentiles
from src.features.performance_score import compute_performance_score
from src.features.potential import compute_potential
from src.features.risk import compute_risk


def _raw_rows() -> list[dict]:
    """20 player-seasons across 2 positions (CB, ST), several players with
    multi-season history (for identity/potential tests), one deliberate
    name collision (two different 'A. Silva's, disambiguated by
    nationality+birth year), and a range of minutes (for reliability/
    percentile threshold tests).
    """
    rows = []

    # --- Player A: a CB with 3 seasons of history, improving trend ---
    for season, perf_inputs in zip([2223, 2324, 2425], [(0.3, 0.5, 60), (0.5, 0.6, 70), (0.6, 0.7, 75)]):
        tkl, cmp_pct, minutes = perf_inputs
        rows.append(_row(
            player_id_seed="cb_player_a", season=season, short_name="A. Steady", nationality="England", born=1998,
            player_positions="CB", pos="DF", playing_time_min=2200, playing_time_starts=24, playing_time_mp=25,
            per_90_minutes_tackles_tkl=tkl, total_cmppct=cmp_pct, physic=75, passing=70, defending=78,
            age_fifa=25 + (season - 2223), value_eur=20_000_000, league_name="Premier League", club_name="Test United",
        ))

    # --- Player B: a CB with only 1 season (tests age-curve fallback path) ---
    rows.append(_row(
        player_id_seed="cb_player_b", season=2425, short_name="B. Rookie", nationality="Spain", born=2003,
        player_positions="CB", pos="DF", playing_time_min=900, playing_time_starts=10, playing_time_mp=10,
        per_90_minutes_tackles_tkl=0.4, total_cmppct=0.55, physic=68, passing=62, defending=65,
        age_fifa=20, value_eur=5_000_000, league_name="Eredivisie", club_name="Test Amsterdam",
    ))

    # --- Player C: low-minutes CB (tests reliability score + percentile peer-eligibility) ---
    rows.append(_row(
        player_id_seed="cb_player_c", season=2425, short_name="C. Bench", nationality="France", born=1999,
        player_positions="CB", pos="DF", playing_time_min=180, playing_time_starts=2, playing_time_mp=3,
        per_90_minutes_tackles_tkl=0.9, total_cmppct=0.9, physic=60, passing=55, defending=58,
        age_fifa=24, value_eur=2_000_000, league_name="Ligue 1", club_name="Test Paris",
    ))

    # --- Several more CBs so percentile peer groups have enough eligible players (min 5) ---
    for i, (tkl, cmp_pct, phys) in enumerate([(0.2, 0.4, 70), (0.35, 0.45, 72), (0.5, 0.5, 74), (0.6, 0.65, 80)]):
        rows.append(_row(
            player_id_seed=f"cb_filler_{i}", season=2425, short_name=f"CB Filler {i}", nationality="Brazil", born=2000,
            player_positions="CB", pos="DF", playing_time_min=2000, playing_time_starts=22, playing_time_mp=23,
            per_90_minutes_tackles_tkl=tkl, total_cmppct=cmp_pct, physic=phys, passing=60, defending=65,
            age_fifa=23, value_eur=8_000_000, league_name="Bundesliga", club_name=f"Test Club {i}",
        ))

    # --- Strikers, for a different position group and role-fit testing ---
    for i, (gls, xg) in enumerate([(1.2, 1.0), (0.9, 0.8), (0.6, 0.5), (0.4, 0.4), (0.2, 0.25)]):
        rows.append(_row(
            player_id_seed=f"st_player_{i}", season=2425, short_name=f"Striker {i}", nationality="Argentina", born=1999,
            player_positions="ST", pos="FW", playing_time_min=2100, playing_time_starts=23, playing_time_mp=24,
            per_90_minutes_gls=gls, per_90_minutes_x_g=xg, per_90_minutes_npx_g=xg * 0.9, shooting=60 + i * 5,
            physic=70, dribbling=65, passing=55, age_fifa=26 - i, value_eur=15_000_000 - i * 1_000_000,
            league_name="Serie A", club_name=f"Test Rome {i}",
        ))

    # --- Two players with the SAME name but different nationality/birth year (identity collision test) ---
    rows.append(_row(
        player_id_seed="silva_1", season=2425, short_name="A. Silva", nationality="Brazil", born=1995,
        player_positions="CM", pos="MF", playing_time_min=1800, playing_time_starts=20, playing_time_mp=20,
        age_fifa=29, value_eur=10_000_000, league_name="La Liga", club_name="Test Madrid",
    ))
    rows.append(_row(
        player_id_seed="silva_2", season=2425, short_name="A. Silva", nationality="Portugal", born=2001,
        player_positions="CM", pos="MF", playing_time_min=1500, playing_time_starts=17, playing_time_mp=18,
        age_fifa=23, value_eur=6_000_000, league_name="Liga Portugal", club_name="Test Porto",
    ))

    return rows


def _row(player_id_seed: str, **kwargs) -> dict:
    """A full-width row with sensible defaults, overridden by kwargs.
    player_id_seed is only used to keep long_name unique per synthetic
    player across seasons; actual player_id assignment is exercised for
    real by assign_player_ids in the fixture below.
    """
    defaults = {
        "long_name": player_id_seed,
        "preferred_foot": "Right",
        "overall": 72, "potential": 78, "pace": 70, "shooting": 55, "passing": 60,
        "dribbling": 60, "defending": 60, "physic": 65,
        "international_reputation": 2, "skill_moves": 3, "weak_foot": 3,
        "height_cm": 182, "weight_kg": 76, "wage_eur": 50_000,
        "per_90_minutes_gls": 0.1, "per_90_minutes_ast": 0.1, "per_90_minutes_x_g": 0.1,
        "per_90_minutes_x_ag": 0.1, "per_90_minutes_npx_g": 0.1,
        "per_90_minutes_prg_c": 0.5, "per_90_minutes_prg_p": 0.5, "per_90_minutes_prg_r": 0.5,
        "per_90_minutes_kp": 0.3, "per_90_minutes_1_3": 0.5, "per_90_minutes_ppa": 0.3,
        "per_90_minutes_crs_pa": 0.1, "per_90_minutes_total_cmp": 30, "total_cmppct": 0.75,
        "per_90_minutes_expected_x_a": 0.1, "per_90_minutes_tackles_tkl": 0.3,
        "per_90_minutes_tackles_tkl_w": 0.2, "per_90_minutes_int": 0.3, "per_90_minutes_tkl_int": 0.5,
        "per_90_minutes_clr": 0.5, "per_90_minutes_blocks_blocks": 0.3,
        "sca_sca90": 1.0, "gca_gca90": 0.2,
        "per_90_minutes_performance_saves": 0.0, "performance_savepct": 0.0, "performance_cspct": 0.0,
        "fifa_version": 25, "born_fifa": 2000,
    }
    defaults.update(kwargs)
    return defaults


@pytest.fixture(scope="module")
def raw_df() -> pd.DataFrame:
    return pd.DataFrame(_raw_rows())


@pytest.fixture(scope="module")
def pipeline_df(raw_df) -> pd.DataFrame:
    """The synthetic dataset run through every real pipeline stage."""
    df = assign_player_ids(raw_df.copy())
    df = assign_position_taxonomy(df)
    df = compute_reliability_score(df)
    df = compute_percentiles(df)
    df = compute_performance_score(df)
    df = compute_potential(df)
    df = compute_risk(df)
    return df
