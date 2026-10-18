"""Multi-facet player similarity engine (spec section 14).

Replaces the old single blended cosine-similarity score with four
separate, independently interpretable facets. Each facet is standardized
and compared with cosine similarity over a feature set specific to that
facet, so "similar tactically" and "similar in market profile" can (and
often do) disagree -- that disagreement is the point.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

FACETS = {
    "statistical": [
        "per_90_minutes_gls_pctile", "per_90_minutes_ast_pctile", "per_90_minutes_prg_c_pctile",
        "per_90_minutes_prg_p_pctile", "per_90_minutes_tackles_tkl_pctile", "per_90_minutes_int_pctile",
        "total_cmppct_pctile", "per_90_minutes_kp_pctile", "sca_sca90_pctile",
    ],
    "physical": ["pace", "physic", "height_cm", "weight_kg"],
    "tactical": [
        "component_attacking", "component_chance_creation", "component_passing",
        "component_progression", "component_defending",
    ],
    "market": ["value_eur", "wage_eur", "age_fifa"],
}


def _standardized_vectors(df: pd.DataFrame, columns: list[str]) -> tuple[np.ndarray, list[str]]:
    available = [c for c in columns if c in df.columns]
    if not available:
        return np.zeros((len(df), 0)), []
    values = df[available].apply(pd.to_numeric, errors="coerce")
    values = values.fillna(values.median())
    standardized = (values - values.mean()) / values.std(ddof=0).replace(0, 1)
    standardized = standardized.fillna(0)
    matrix = standardized.to_numpy(dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return matrix / norms, available


def find_similar_players_multifacet(
    df: pd.DataFrame,
    player_id: str,
    top_n: int = 10,
    facets: Iterable[str] | None = None,
    restrict_to_broad_position_group: bool = True,
) -> pd.DataFrame:
    """Return top-N similar players with a separate similarity % per facet
    (spec section 14's example output), keyed on player_id -- never on
    fuzzy name matching.

    By default, the comparison pool is restricted to the target player's
    broad position group (Defender/Midfielder/Winger/Forward/Goalkeeper).
    Comparing a striker to centre-backs by raw feature distance can score
    deceptively high on facets like physical/market similarity even
    though no recruitment analyst would call them comparable players;
    position-restriction is what makes "similar player" mean something
    football-relevant rather than just numerically nearby.
    """
    if "player_id" not in df.columns:
        raise ValueError("DataFrame must have player_id assigned before similarity search.")

    if player_id not in set(df["player_id"]):
        raise ValueError(f"No player found with player_id '{player_id}'.")

    if restrict_to_broad_position_group and "broad_position_group" in df.columns:
        target_group = df.loc[df["player_id"] == player_id, "broad_position_group"].iloc[0]
        if pd.notna(target_group):
            df = df[df["broad_position_group"] == target_group]

    target_idx = df.index[df["player_id"] == player_id][0]
    facets = list(facets or FACETS.keys())

    result = df.copy()
    facet_scores = {}

    for facet in facets:
        cols = FACETS.get(facet, [])
        matrix, used_cols = _standardized_vectors(df, cols)
        if matrix.shape[1] == 0:
            facet_scores[facet] = pd.Series(pd.NA, index=df.index)
            continue
        target_vec = matrix[df.index.get_loc(target_idx)]
        sims = matrix @ target_vec  # cosine similarity, vectors already unit-normalized
        facet_scores[facet] = pd.Series(((sims + 1) / 2 * 100).round(1), index=df.index)  # rescale [-1,1] -> [0,100]

    for facet, scores in facet_scores.items():
        result[f"{facet}_similarity"] = scores

    facet_cols = [f"{f}_similarity" for f in facets if f"{f}_similarity" in result.columns]
    result["overall_similarity"] = result[facet_cols].mean(axis=1, skipna=True)

    result = result[result["player_id"] != player_id]
    return result.sort_values("overall_similarity", ascending=False).head(top_n)
