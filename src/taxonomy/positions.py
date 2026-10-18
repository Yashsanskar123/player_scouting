"""
Canonical position taxonomy.

Source of truth for primary/secondary position is FIFA's `player_positions`
column, which is fine-grained (CB, ST, CDM, LB, ...). FBref's `pos` column
(DF/MF/FW/GK) is coarser and used only as a cross-validation signal.

This module never invents a position: if a player has no usable position
data, canonical_position is left null and flagged in data quality, not
guessed.
"""
from __future__ import annotations

import pandas as pd

# Canonical fine-grained position set (spec section 7)
CANONICAL_POSITIONS = [
    "GK",
    "CB", "LB", "RB", "LWB", "RWB",
    "CDM", "CM",
    "CAM",
    "LW", "RW",
    "ST", "CF",
]

# Raw FIFA position tokens -> canonical bucket (FIFA already uses these tokens
# almost verbatim; this just guards against noisy variants like LCB/RCB/LM/RM
# which are common in player_positions strings).
POSITION_ALIASES = {
    "GK": "GK",
    "CB": "CB", "LCB": "CB", "RCB": "CB", "SW": "CB",
    "LB": "LB", "LWB": "LWB",
    "RB": "RB", "RWB": "RWB",
    "CDM": "CDM",
    "CM": "CM", "LCM": "CM", "RCM": "CM",
    "LM": "CM",   # wide midfielders folded into CM bucket for taxonomy purposes
    "RM": "CM",
    "CAM": "CAM", "LAM": "CAM", "RAM": "CAM",
    "LW": "LW", "LF": "LW",
    "RW": "RW", "RF": "RW",
    "ST": "ST",
    "CF": "CF",
}

BROAD_GROUP = {
    "GK": "Goalkeeper",
    "CB": "Defender", "LB": "Defender", "RB": "Defender", "LWB": "Defender", "RWB": "Defender",
    "CDM": "Midfielder", "CM": "Midfielder",
    "CAM": "Midfielder",
    "LW": "Winger", "RW": "Winger",
    "ST": "Forward", "CF": "Forward",
}

# FBref broad group, used only to cross-check FIFA-derived canonical position
FBREF_BROAD = {
    "GK": "Goalkeeper",
    "DF": "Defender",
    "MF": "Midfielder",
    "FW": "Forward",
}


def _first_token(raw: str) -> str | None:
    if not raw or pd.isna(raw):
        return None
    parts = [p.strip().upper() for p in str(raw).split(",") if p.strip()]
    return parts[0] if parts else None


def _all_tokens(raw: str) -> list[str]:
    if not raw or pd.isna(raw):
        return []
    return [p.strip().upper() for p in str(raw).split(",") if p.strip()]


def assign_position_taxonomy(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical_position, secondary_positions, broad_position_group,
    positional_versatility_score, and a position_data_conflict flag.

    Does not overwrite player_positions/pos; adds new columns only.
    """
    df = df.copy()

    source_col = "player_positions" if "player_positions" in df.columns else None
    fbref_col = "pos" if "pos" in df.columns else None

    if source_col is None:
        df["canonical_position"] = pd.NA
        df["secondary_positions"] = pd.NA
        df["broad_position_group"] = pd.NA
        df["positional_versatility_score"] = pd.NA
        df["position_data_conflict"] = False
        return df

    primary_raw = df[source_col].map(_first_token)
    df["canonical_position"] = primary_raw.map(lambda t: POSITION_ALIASES.get(t, t) if t else pd.NA)

    all_tokens = df[source_col].map(_all_tokens)
    df["secondary_positions"] = all_tokens.map(
        lambda toks: ",".join(sorted({POSITION_ALIASES.get(t, t) for t in toks[1:]})) if len(toks) > 1 else ""
    )

    df["broad_position_group"] = df["canonical_position"].map(BROAD_GROUP)

    # Versatility: how many distinct canonical positions a player is listed for.
    df["positional_versatility_score"] = all_tokens.map(
        lambda toks: len({POSITION_ALIASES.get(t, t) for t in toks}) if toks else 0
    )

    # Cross-check against FBref's broad bucket where available.
    if fbref_col is not None:
        fbref_primary = df[fbref_col].map(_first_token)
        fbref_broad = fbref_primary.map(lambda t: FBREF_BROAD.get(t))
        df["position_data_conflict"] = (
            fbref_broad.notna() & df["broad_position_group"].notna() & (fbref_broad != df["broad_position_group"])
        )
    else:
        df["position_data_conflict"] = False

    return df
