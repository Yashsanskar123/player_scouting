"""
Canonical player identity resolution.

The processed dataset contains multiple naming variants for the same
real-world player across seasons, for example:

    L. Messi
    Lionel Messi
    Lionel Andres Messi Cuccittini
    Lionel Andres Messi Cuccitini

A canonical player_id must therefore NOT be generated directly from the
display name.

Strategy
--------
1. Use birth year + nationality as the primary identity anchors.
2. Use normalized name information to disambiguate when those anchors
   are shared by multiple real players.
3. Preserve the same canonical ID across seasons when the stable
   identity anchors remain consistent.
4. Keep genuinely different players separate even when names overlap.
5. Make the resolution deterministic and auditable.

This is deliberately rule-based rather than fuzzy ML matching.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd


def _normalize_text(value: object) -> str:
    """Normalize names/text for deterministic comparisons."""
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()

    # Remove accents.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    # Keep alphanumeric characters only.
    text = re.sub(r"[^a-z0-9]+", " ", text)

    return " ".join(text.split())


def _birth_year(row: pd.Series) -> str:
    """
    Return the most reliable available birth year.

    FIFA and FBref both expose birth year in this dataset.
    """
    for column in ("born_fifa", "born_fbref"):
        if column in row.index and pd.notna(row[column]):
            try:
                return str(int(float(row[column])))
            except (TypeError, ValueError):
                continue

    return ""


def _nationality(row: pd.Series) -> str:
    for column in ("nationality_name", "nation"):
        if column in row.index and pd.notna(row[column]):
            value = _normalize_text(row[column])
            if value:
                return value

    return ""


def _name_variants(row: pd.Series) -> set[str]:
    """
    Return normalized forms of the available player names.

    Multiple forms are retained because source systems can expose:
      - abbreviated names
      - full names
      - slightly different spellings
    """
    variants: set[str] = set()

    for column in ("long_name", "short_name", "player"):
        if column in row.index:
            value = _normalize_text(row[column])
            if value:
                variants.add(value)

    return variants

def _name_similarity(name_a: str, name_b: str) -> float:
    """
    Compare two normalized player names.

    Used only inside an already constrained birth-year +
    nationality identity bucket.
    """
    if not name_a or not name_b:
        return 0.0

    return SequenceMatcher(
        None,
        name_a,
        name_b,
    ).ratio()


def _identity_anchor(row: pd.Series) -> tuple[str, str]:
    """
    Stable identity anchor.

    Birth year + nationality are deliberately separated from the name.
    """
    return (
        _birth_year(row),
        _nationality(row),
    )


def _fallback_key(row: pd.Series) -> str:
    """
    Conservative fallback for records where stable anchors are incomplete.

    We use the strongest available identity information rather than
    creating an arbitrary ID from the row.
    """
    birth = _birth_year(row)
    nationality = _nationality(row)
    names = sorted(_name_variants(row))

    return "|".join([
        "fallback",
        birth,
        nationality,
        *names,
    ])


def _stable_player_key(row: pd.Series) -> str:
    """
    Generate the deterministic canonical identity key.

    Important:
    For players with both birth year and nationality available, the
    canonical identity is based primarily on those stable anchors.

    The name is NOT part of the primary key, which allows a player's
    display name to change across seasons without generating a new ID.
    """
    birth, nationality = _identity_anchor(row)

    if birth and nationality:
        return f"identity|{birth}|{nationality}"

    return _fallback_key(row)


def _hash_identity(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def assign_player_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add canonical `player_id` and `identity_confidence`.

    The resolver first identifies whether the stable birth-year +
    nationality anchor is unique to one player identity.

    If the anchor is shared by multiple names, name information is used
    to keep those players separated.

    This two-stage process prevents broad birth-year/nationality
    collisions while still allowing name changes such as:

        L. Messi -> Lionel Messi

    to retain one canonical identity.
    """
    df = df.copy()

    # ------------------------------------------------------------------
    # Build normalized helper columns.
    # ------------------------------------------------------------------
    anchors = df.apply(_identity_anchor, axis=1)

    df["_identity_birth"] = anchors.map(lambda x: x[0])
    df["_identity_nationality"] = anchors.map(lambda x: x[1])

    df["_identity_name"] = df.apply(
        lambda row: _normalize_text(
            row.get("long_name")
            or row.get("short_name")
            or row.get("player")
            or ""
        ),
        axis=1,
    )

    # ------------------------------------------------------------------
    # Determine how many distinct names exist for each stable anchor.
    # ------------------------------------------------------------------
    valid_anchor = (
        (df["_identity_birth"] != "")
        & (df["_identity_nationality"] != "")
    )

    # ------------------------------------------------------------------
    # Build fuzzy name clusters inside each stable identity anchor.
    #
    # Birth year + nationality narrows the candidate pool.
    # Name similarity then handles source spelling/name variations.
    #
    # Example:
    #
    # Lionel Andres Messi Cuccittini
    # Lionel Andres Messi Cuccitini
    #
    # -> same cluster
    #
    # Federico Julian Fazio
    # Gonzalo Gerardo Higuain
    #
    # -> different clusters
    # ------------------------------------------------------------------

    NAME_SIMILARITY_THRESHOLD = 0.90

    anchor_name_clusters: dict[tuple[str, str], list[str]] = {}

    for anchor, group in (
        df.loc[valid_anchor]
        .groupby(
            ["_identity_birth", "_identity_nationality"]
        )
    ):
        names = sorted(
            {
                name
                for name in group["_identity_name"]
                if name
            }
        )

        clusters: list[list[str]] = []

        for name in names:
            matched_cluster = None

            for cluster in clusters:
                similarity = max(
                    _name_similarity(name, existing)
                    for existing in cluster
                )

                if similarity >= NAME_SIMILARITY_THRESHOLD:
                    matched_cluster = cluster
                    break

            if matched_cluster is None:
                clusters.append([name])
            else:
                matched_cluster.append(name)

        anchor_name_clusters[anchor] = clusters

    # ------------------------------------------------------------------
    # Generate canonical keys.
    # ------------------------------------------------------------------
    canonical_keys: list[str] = []
    confidence: list[str] = []

    for _, row in df.iterrows():
        birth = row["_identity_birth"]
        nationality = row["_identity_nationality"]
        name = row["_identity_name"]

        if birth and nationality:
            anchor = (birth, nationality)
            clusters = anchor_name_clusters.get(anchor, [])

            matched_cluster = None

            for cluster in clusters:
                similarity = max(
                    _name_similarity(name, existing)
                    for existing in cluster
                )

                if similarity >= NAME_SIMILARITY_THRESHOLD:
                    matched_cluster = cluster
                    break

            if matched_cluster is None:
                # Defensive fallback when the name cannot be matched
                # to an existing identity cluster.
                key = (
                    f"identity|{birth}|{nationality}"
                    f"|name|{name}"
                )
                conf = "medium"

            else:
                # Use a deterministic representative name for the
                # matched identity cluster.
                representative_name = min(matched_cluster)

                key = (
                    f"identity|{birth}|{nationality}"
                    f"|name_cluster|{representative_name}"
                )

                # If only one identity cluster exists for this
                # birth-year + nationality combination, the identity
                # anchor is effectively unambiguous.
                if len(clusters) == 1:
                    conf = "high"
                else:
                    conf = "medium"

        else:
            # Insufficient stable information.
            key = _fallback_key(row)
            conf = "low"

        canonical_keys.append(key)
        confidence.append(conf)

    df["player_id"] = [
        _hash_identity(key)
        for key in canonical_keys
    ]

    df["identity_confidence"] = confidence

    # Remove implementation columns.
    df = df.drop(
        columns=[
            "_identity_birth",
            "_identity_nationality",
            "_identity_name",
        ],
        errors="ignore",
    )

    return df


def build_player_identity_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one canonical identity row per player_id.

    The most recent observed name is retained for display, while the
    canonical player_id remains stable across seasons.
    """
    if "player_id" not in df.columns:
        df = assign_player_ids(df)

    sort_cols = [
        column
        for column in ["season", "fifa_version"]
        if column in df.columns
    ]

    ordered = (
        df.sort_values(sort_cols)
        if sort_cols
        else df.copy()
    )

    latest = (
        ordered
        .groupby("player_id", as_index=False)
        .tail(1)
    )

    if "season" in df.columns:
        seasons = (
            df.groupby("player_id")["season"]
            .agg(
                first_season="min",
                last_season="max",
                seasons_observed="nunique",
            )
            .reset_index()
        )
    else:
        seasons = None

    cols = [
        "player_id",
        "identity_confidence",
    ]

    for column in [
        "short_name",
        "long_name",
        "nationality_name",
        "born_fifa",
        "preferred_foot",
    ]:
        if column in latest.columns:
            cols.append(column)

    identity = (
        latest[cols]
        .drop_duplicates(subset="player_id")
        .reset_index(drop=True)
    )

    if seasons is not None:
        identity = identity.merge(
            seasons,
            on="player_id",
            how="left",
        )

    return identity


def duplicate_identity_report(df: pd.DataFrame) -> dict:
    """
    Report identity quality before and after canonical resolution.
    """
    if "player_id" not in df.columns:
        df = assign_player_ids(df)

    name_col = (
        "short_name"
        if "short_name" in df.columns
        else None
    )

    result = {
        "total_rows": int(len(df)),
        "unique_player_ids": int(
            df["player_id"].nunique()
        ),
        "low_confidence_identities": int(
            (
                df["identity_confidence"] == "low"
            ).sum()
        ),
    }

    if name_col and "season" in df.columns:
        result[
            "name_season_collisions_before_id_resolution"
        ] = int(
            df.duplicated(
                subset=[name_col, "season"]
            ).sum()
        )

        result[
            "player_id_season_collisions_after_id_resolution"
        ] = int(
            df.duplicated(
                subset=["player_id", "season"]
            ).sum()
        )

    return result