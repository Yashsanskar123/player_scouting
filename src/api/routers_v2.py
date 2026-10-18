from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.services.data_store import store
from src.services.cache import cached, clear as clear_cache
from src.data_quality.quality_score import data_quality_score
from src.features.role_archetypes import ROLE_ARCHETYPES, compute_role_fit, explain_role_fit, recommended_roles_for_position
from src.features.similarity_v2 import find_similar_players_multifacet
from src.features.risk import TOP_LEAGUES
from src.features.squad_audit import audit_squad
from src.features.replacement_finder import find_replacements
from src.features.comparison import compare_players
from src.features.tactical_fit import FORMATION_ROLES, STYLE_PROFILES, score_tactical_fit
from src.features.transfer_intelligence import build_transfer_intelligence
from src.features.advanced_potential import backtest_advanced_horizons, compute_advanced_potential
from src.features.dashboard_intelligence import dashboard_overview
from src.features.search_intelligence import enrich_search_results
from src.features.profile_intelligence import build_profile_intelligence
from src.features.season_context import build_season_catalog
from src.optimization.squad_optimizer import optimize_squad_ilp, simulate_transfer, FORMATIONS
from src.db.session import get_session
from src.db.models import Shortlist, ShortlistEntry, ScoutNote, EntryEvent, RECRUITMENT_STATUSES
from src.db.ingest import full_refresh
from src.utils import to_native as _native
from src.api.schemas import (
    ScoutingSearchRequest, SquadOptimizeRequest, ShortlistCreateRequest,
    ShortlistEntryCreateRequest, ShortlistEntryUpdateRequest, ScoutNoteCreateRequest,
    SquadAuditRequest, TransferSimulateRequest, ClubProfileRequest,
    ReplacementSearchRequest, ComparePlayersRequest,
)
from src.features.profile_intelligence import build_profile_intelligence
from src.features.market_intelligence import build_market_intelligence
from src.features.development_lab import build_development_lab
router = APIRouter()


def _clean_records(df: pd.DataFrame) -> list[dict]:
    """Replace NaN/inf with None so the JSON encoder doesn't choke, and
    convert numpy scalar types to native Python types."""
    records = df.replace([np.inf, -np.inf], np.nan).where(pd.notna(df), None).to_dict(orient="records")
    return records

def _resolve_player_id(player_id: str) -> str:
    """
    Resolve a player_id against the full dataset.

    This provides backward compatibility when an older processed dataset
    contains a season-specific ID that has since been replaced by the
    canonical identity ID.
    """
    df = store.facts

    if df.empty or "player_id" not in df.columns:
        raise HTTPException(
            status_code=404,
            detail="No data loaded. Run /api/admin/reload first.",
        )

    matches = df[df["player_id"] == player_id]

    if not matches.empty:
        return player_id

    raise HTTPException(
        status_code=404,
        detail=f"No player found with player_id '{player_id}'.",
    )


def _latest_row_for_player(player_id: str, season: int | None = None) -> pd.Series:
    df = store.season(season) if season is not None else store.latest_season()
    if df.empty or "player_id" not in df.columns:
        raise HTTPException(status_code=404, detail="No data loaded. Run /api/admin/reload first.")
    matches = df[df["player_id"] == player_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"No player found with player_id '{player_id}'.")
    return matches.sort_values("season").iloc[-1]


# ---------------------------------------------------------------- health --

@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict:
    return {"status": "ready" if not store.facts.empty else "not_ready", "rows_loaded": int(len(store.facts))}


@router.post("/api/admin/reload")
def admin_reload(processed_path: str = "data/cleaned/fifa_fbref_merged_processed_v2.csv") -> dict:
    result = full_refresh(processed_path)
    store.reload()
    clear_cache()
    return {"status": "reloaded", **result}


@router.get("/api/data-quality")
def data_quality() -> dict:
    return data_quality_score(store.facts)

_health_cache: dict = {"key": None, "coverage": {}, "report": None}


def _facts_key() -> tuple:
    facts = store.facts
    return (id(facts), len(facts))


def _season_coverage_cached() -> dict:
    """Per-season coverage, recomputed only when the data store is reloaded. Never blocks the seasons list."""
    try:
        from src.features.data_health import season_coverage
        key = _facts_key()
        if _health_cache["key"] != key:
            _health_cache.update(key=key, coverage=season_coverage(store.facts), report=None)
        return _health_cache["coverage"]
    except Exception:
        return {}


@router.get("/api/data-health")
def data_health() -> dict:
    """Coverage, freshness, missingness, drift alerts, anomalies and identity quality for the platform data."""
    from src.features.data_health import build_data_health
    _season_coverage_cached()
    if _health_cache["report"] is None:
        try:
            quality = data_quality_score(store.facts)
        except Exception:
            quality = None
        _health_cache["report"] = _native(build_data_health(store.facts, quality))
    return _health_cache["report"]


@router.get("/api/data-freshness")
def data_freshness() -> dict:
    """Small payload for the footer shown on every page: when each source was last updated."""
    from src.features.data_health import freshness
    return {"sources": freshness(store.facts), "latest_season": store.current_season()}


@router.get("/api/seasons")
def list_seasons() -> dict:
    """Return the canonical season dimension and the current completed season."""
    seasons = build_season_catalog(store.available_seasons(), store.current_season())
    coverage = _season_coverage_cached()
    return {
        "current_season": store.current_season(),
        "seasons": [{**s.__dict__, "coverage": coverage.get(s.season)} for s in seasons],
    }


_overview_cache: dict = {}


@router.get("/api/dashboard/overview")
def dashboard_overview_endpoint(season: int | None = None) -> dict:
    """Return season-aware recruitment intelligence for the command dashboard."""
    selected = store.current_season() if season is None else season
    if selected not in store.available_seasons():
        raise HTTPException(status_code=404, detail=f"Season {selected} is not available.")

    # Keep the dashboard market count consistent with the market page's
    # canonical opportunity definition. Only the count is needed here.
    market_df = store.season(selected)
    market_df = market_df[
        pd.to_numeric(market_df["performance_score"], errors="coerce") >= 60
    ]
    # Without valuation results there are no opportunities to count (degrade, do not crash).
    if "value_gap_pct" in market_df.columns:
        market_df = market_df[pd.to_numeric(market_df["value_gap_pct"], errors="coerce") > 0]
    else:
        market_df = market_df.iloc[0:0]
    market_total = int(market_df["player_id"].nunique()) if "player_id" in market_df.columns else int(len(market_df))

    # Depends only on the data and the season, so compute once per data version.
    key = (_facts_key(), selected)
    if key not in _overview_cache:
        if len(_overview_cache) > 16:
            _overview_cache.clear()
        _overview_cache[key] = _native(dashboard_overview(store.facts, selected, market_total=market_total))
    return _overview_cache[key]




# ------------------------------------------------------------- players ---

@router.get("/api/players")
def list_players(
    page: int = 1,
    page_size: int = 25,
    canonical_position: str | None = None,
    league_name: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    max_value_eur: float | None = None,
    season: int | None = None,
    search: str | None = None,
    sort_by: str = "performance_score",
    descending: bool = True,
) -> dict:
    df = store.facts
    if df.empty:
        return {"total": 0, "page": page, "page_size": page_size, "results": []}

    if season is not None and "season" in df.columns:
        df = df[df["season"] == season]
    else:
        df = df[df["season"] == df["season"].max()] if "season" in df.columns else df

    if canonical_position:
        df = df[df["canonical_position"] == canonical_position]
    if league_name:
        df = df[df["league_name"] == league_name]
    if min_age is not None:
        df = df[pd.to_numeric(df["age_fifa"], errors="coerce") >= min_age]
    if max_age is not None:
        df = df[pd.to_numeric(df["age_fifa"], errors="coerce") <= max_age]
    if max_value_eur is not None:
        df = df[pd.to_numeric(df["value_eur"], errors="coerce") <= max_value_eur]
    if search:
        name_col = "short_name" if "short_name" in df.columns else "player_name"
        df = df[df[name_col].fillna("").str.lower().str.contains(search.strip().lower())]

    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not descending, na_position="last")

    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start:start + page_size]

    cols = [c for c in [
        "player_id", "short_name", "canonical_position", "club_name", "league_name",
        "age_fifa", "value_eur", "performance_score", "development_potential",
        "recruitment_risk_tier", "fair_value_eur",
    ] if c in page_df.columns]

    return {"total": total, "page": page, "page_size": page_size, "results": _clean_records(page_df[cols])}


@router.get("/api/players/{player_id}")
def get_player(player_id: str, season: int | None = None) -> dict:
    row = _latest_row_for_player(player_id, season)
    return _clean_records(row.to_frame().T)[0]


@router.get("/api/players/{player_id}/profile-intelligence")
def player_profile_intelligence(
    player_id: str,
    season: int | None = None,
) -> dict:
    """Return season-aware longitudinal intelligence for the player profile."""

    selected = (
        store.current_season()
        if season is None
        else season
    )

    if selected not in store.available_seasons():
        raise HTTPException(
            status_code=404,
            detail=f"Season {selected} is not available.",
        )

    result = build_profile_intelligence(
        store.facts,
        player_id,
        selected,
    )

    if not result.get("available"):
        raise HTTPException(
            status_code=404,
            detail=f"No player found with player_id '{player_id}'.",
        )

    return _native(result)


@router.get("/api/players/{player_id}/history")
def player_history(player_id: str) -> dict:
    """Return the player's season-by-season evidence for profile trajectory views."""
    df = store.facts
    if df.empty or "player_id" not in df.columns:
        raise HTTPException(status_code=404, detail="No data loaded. Run /api/admin/reload first.")
    matches = df[df["player_id"] == player_id].copy()
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"No player found with player_id '{player_id}'.")
    matches = matches.sort_values("season").copy()
    cols = [c for c in [
        "season", "short_name", "canonical_position", "club_name", "league_name", "age_fifa",
        "playing_time_min", "performance_score", "expected_performance_12m",
        "development_potential", "value_eur", "fair_value_eur",
        "value_gap_pct", "adjusted_performance_score", "sample_reliability_score",
        "sample_reliability_tier",
    ] if c in matches.columns]
    history = _clean_records(matches[cols])

    # Historical intelligence is deliberately descriptive: it summarizes observed
    # changes and does not turn the short player history into an unvalidated forecast.
    perf = pd.to_numeric(matches.get("performance_score"), errors="coerce") if "performance_score" in matches else pd.Series(dtype=float)
    valid_perf = perf.dropna()
    perf_change = None
    if len(valid_perf) >= 2:
        perf_change = float(valid_perf.iloc[-1] - valid_perf.iloc[0])
    best_idx = int(valid_perf.idxmax()) if len(valid_perf) else None
    worst_idx = int(valid_perf.idxmin()) if len(valid_perf) else None
    best_season = _native(matches.loc[best_idx, "season"]) if best_idx is not None else None
    worst_season = _native(matches.loc[worst_idx, "season"]) if worst_idx is not None else None

    positions = [str(x) for x in matches.get("canonical_position", pd.Series(dtype=object)).dropna().tolist()]
    clubs = [str(x) for x in matches.get("club_name", pd.Series(dtype=object)).dropna().tolist()]
    leagues = [str(x) for x in matches.get("league_name", pd.Series(dtype=object)).dropna().tolist()]
    club_changes = sum(1 for a, b in zip(clubs, clubs[1:]) if a != b)
    league_changes = sum(1 for a, b in zip(leagues, leagues[1:]) if a != b)
    value_change_pct = None
    values = pd.to_numeric(matches.get("value_eur"), errors="coerce") if "value_eur" in matches else pd.Series(dtype=float)
    valid_values = values.dropna()
    if len(valid_values) >= 2 and valid_values.iloc[0] > 0:
        value_change_pct = float((valid_values.iloc[-1] / valid_values.iloc[0] - 1) * 100)

    return {
        "player_id": player_id,
        "history": history,
        "summary": {
            "seasons_observed": len(history),
            "first_season": _native(matches.iloc[0].get("season")),
            "last_season": _native(matches.iloc[-1].get("season")),
            "performance_change": perf_change,
            "best_performance_season": best_season,
            "worst_performance_season": worst_season,
            "positions_observed": list(dict.fromkeys(positions)),
            "clubs_observed": list(dict.fromkeys(clubs)),
            "leagues_observed": list(dict.fromkeys(leagues)),
            "club_changes": club_changes,
            "league_changes": league_changes,
            "value_change_pct": value_change_pct,
        },
    }


@router.get("/api/players/{player_id}/potential")
def player_potential(player_id: str, season: int | None = None) -> dict:
    """Return the advanced potential profile for the latest observed season.

    Compute on demand as a compatibility fallback for datasets generated before
    the advanced-potential pipeline step was introduced.
    """
    row = _latest_row_for_player(player_id, season)
    fields = [
        "current_ability", "expected_performance_12m", "potential_12m", "potential_24m",
        "peak_projection", "development_potential", "development_trajectory",
        "breakout_probability", "decline_probability", "potential_evidence_sample",
        "potential_projection_status", "fifa_potential_benchmark",
    ]
    if "potential_24m" not in row.index:
        advanced = compute_advanced_potential(store.facts)
        advanced = advanced[advanced["player_id"] == player_id]
        if season is not None:
            advanced = advanced[advanced["season"] == season]
        if advanced.empty:
            raise HTTPException(status_code=404, detail=f"No player found with player_id '{player_id}' in season {season}.")
        row = advanced.sort_values("season").iloc[-1]
    payload = {k: _native(row.get(k)) for k in fields if k in row.index}
    payload.update({"player_id": player_id, "season": _native(row.get("season"))})
    return payload

@router.get("/api/players/{player_id}/development-lab")
def player_development_lab(
    player_id: str,
    season: int | None = None,
) -> dict:
    """Return focused development decision intelligence for one player."""

    selected = (
        store.current_season()
        if season is None
        else season
    )

    if selected not in store.available_seasons():
        raise HTTPException(
            status_code=404,
            detail=f"Season {selected} is not available.",
        )

    try:
        return _native(
            build_development_lab(
                store.facts,
                player_id,
                selected,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.get("/api/players/{player_id}/percentiles")
def player_percentiles(player_id: str, season: int | None = None) -> dict:
    row = _latest_row_for_player(player_id, season)
    pctile_cols = [c for c in row.index if c.endswith("_pctile")]
    percentiles = {c.replace("_pctile", ""): _native(row[c]) for c in pctile_cols if pd.notna(row[c])}
    return {"player_id": player_id, "season": _native(row.get("season")), "percentiles": percentiles}


@router.get("/api/players/{player_id}/roles")
def player_roles(player_id: str, season: int | None = None) -> dict:
    row = _latest_row_for_player(player_id, season)
    position = row.get("canonical_position")
    applicable_roles = recommended_roles_for_position(position) if position else list(ROLE_ARCHETYPES.keys())

    df = store.season(season)
    results = []
    for role in applicable_roles:
        scored = compute_role_fit(df, role)
        player_row = scored[scored["player_id"] == player_id]
        if player_row.empty:
            continue
        prow = player_row.iloc[0]
        explanation = explain_role_fit(prow, role)
        results.append({
            "role": role,
            "role_fit_score": prow["role_fit_score"],
            "coverage_pct": prow.get("role_fit_coverage_pct"),
            **explanation,
        })

    results.sort(key=lambda r: r["role_fit_score"] if pd.notna(r["role_fit_score"]) else -1, reverse=True)
    return {"player_id": player_id, "season": _native(row.get("season")), "canonical_position": position, "roles": results}


@router.get("/api/players/{player_id}/tactical-fit")
def player_tactical_fit(
    player_id: str,
    season: int | None = None,
    formation: str = "4-3-3",
    style: str = "Balanced",
    role: str | None = None,
) -> dict:
    """Return transparent formation + style + role compatibility for a player."""
    row = _latest_row_for_player(player_id, season)
    if formation not in FORMATION_ROLES:
        raise HTTPException(status_code=400, detail=f"Unsupported formation. Choose one of: {', '.join(FORMATION_ROLES)}")
    if style not in STYLE_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unsupported tactical style. Choose one of: {', '.join(STYLE_PROFILES)}")
    result = score_tactical_fit(row, formation, style, role)
    return {
        "player_id": player_id,
        "season": _native(row.get("season")),
        "player": {
            "short_name": _native(row.get("short_name")),
            "canonical_position": _native(row.get("canonical_position")),
            "club_name": _native(row.get("club_name")),
        },
        "available_formations": list(FORMATION_ROLES.keys()),
        "available_styles": list(STYLE_PROFILES.keys()),
        **result,
    }


@router.get("/api/players/{player_id}/similar")
def player_similar(player_id: str, season: int | None = None, top_n: int = 10) -> dict:
    df = store.season(season)
    try:
        results = find_similar_players_multifacet(df, player_id=player_id, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cols = [c for c in [
        "player_id", "short_name", "canonical_position", "club_name",
        "statistical_similarity", "physical_similarity", "tactical_similarity",
        "market_similarity", "overall_similarity",
    ] if c in results.columns]
    return {"player_id": player_id, "season": season if season is not None else store.current_season(), "results": _clean_records(results[cols])}


@router.post("/api/players/compare")
def players_compare(req: ComparePlayersRequest) -> dict:
    df = store.season(req.season)
    try:
        from src.api.alias_middleware import canonical_player_id
        result = compare_players(df, [canonical_player_id(p) for p in req.player_ids])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"season": req.season if req.season is not None else store.current_season(), **result}


@router.post("/api/replacement/search")
def replacement_search(req: ReplacementSearchRequest) -> dict:
    df = store.season(req.season)
    from src.api.alias_middleware import canonical_player_id
    try:
        result = find_replacements(
            df,
            outgoing_player_id=canonical_player_id(req.outgoing_player_id),
            budget_eur=req.budget_eur,
            min_age=req.min_age,
            max_age=req.max_age,
            top_n=req.top_n,
            restrict_to_position_group=req.restrict_to_position_group,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    contract_context = {"available": False, "reason": CONTRACT_SNAPSHOT_REASON}
    if _is_latest_season(req.season):
        try:
            from src.features.transfermarkt_context import bulk_contract_info
            info = bulk_contract_info([c["player_id"] for c in result.get("candidates", [])])
            for c in result.get("candidates", []):
                c["contract"] = info.get(c["player_id"])
                months = (c["contract"] or {}).get("contract_months_left")
                if months is not None and 0 <= months <= 12:
                    c.setdefault("advantages", []).append(f"Contract ends in about {round(months)} months (check renewal status)")
            contract_context = {"available": True}
        except Exception:
            contract_context = {"available": False, "reason": "Contract data is unavailable."}
    return {"season": req.season if req.season is not None else store.current_season(), **result, "contract_context": contract_context}


@router.get("/api/players/{player_id}/value")
def player_value(player_id: str, season: int | None = None) -> dict:
    row = _latest_row_for_player(player_id, season)
    return {
        "player_id": player_id,
        "season": _native(row.get("season")),
        "value_eur": _native(row.get("value_eur")),
        "fair_value_eur": _native(row.get("fair_value_eur")),
        "value_gap_eur": _native(row.get("value_gap_eur")),
        "value_gap_pct": _native(row.get("value_gap_pct")),
        "note": "fair_value_eur is a trained-model estimate against this dataset's FIFA in-game valuation, "
                "not a real transfer-market appraisal -- see MODEL_CARD.md.",
    }


@router.get("/api/players/{player_id}/transfermarkt")
def player_transfermarkt(player_id: str) -> dict:
    """Optional Transfermarkt context. Never fails: returns available=False when absent."""
    try:
        from src.features.transfermarkt_context import get_context
        return _native(get_context(player_id))
    except Exception:
        return {"available": False}


@router.get("/api/players/{player_id}/transfer-intelligence")
def player_transfer_intelligence(player_id: str, season: int | None = None) -> dict:
    try:
        # Resolve the requested season explicitly so the endpoint cannot silently
        # fall back to the latest snapshot when the global season is selected.
        if season is not None and int(season) not in store.available_seasons():
            raise HTTPException(status_code=404, detail=f"Season {season} is not available.")
        result = build_transfer_intelligence(store.facts, player_id, season=season)
        return _native(result)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        # Keep the failure as a useful API error instead of letting a secondary
        # profile section make the browser report a misleading generic CORS error.
        raise HTTPException(status_code=500, detail=f"Transfer intelligence failed: {exc}") from exc


@router.get("/api/players/{player_id}/risk")
def player_risk(player_id: str, season: int | None = None) -> dict:
    row = _latest_row_for_player(player_id, season)
    return {
        "player_id": player_id,
        "season": _native(row.get("season")),
        "recruitment_risk_score": _native(row.get("recruitment_risk_score")),
        "recruitment_risk_tier": _native(row.get("recruitment_risk_tier")),
        "components": {
            "age_risk": _native(row.get("age_risk")),
            "availability_risk": _native(row.get("availability_risk")),
            "league_transition_risk": _native(row.get("league_transition_risk")),
            "data_reliability_risk": _native(row.get("data_reliability_risk")),
        },
        "note": "Backtested against 17,851 real season-to-season transitions in this dataset: this tier "
                "predicts OUTCOME VOLATILITY, not direction. HIGH-tier players show much higher variance "
                "in next-season performance (std 22.9 vs 12.6 for LOW) but not a worse average outcome -- "
                "read HIGH as 'could go either much better or much worse than projected,' not 'likely to "
                "underperform.' See docs/VALIDATION.md.",
    }


# ---------------------------------------------------------- scouting -----

@router.post("/api/scouting/search")
def scouting_search(req: ScoutingSearchRequest) -> dict:
    df = store.season(req.season)
    if df.empty:
        return {"total": 0, "results": []}

    if req.canonical_position:
        df = df[df["canonical_position"] == req.canonical_position]
    if req.min_age is not None:
        df = df[pd.to_numeric(df["age_fifa"], errors="coerce") >= req.min_age]
    if req.max_age is not None:
        df = df[pd.to_numeric(df["age_fifa"], errors="coerce") <= req.max_age]
    if req.max_value_eur is not None:
        df = df[pd.to_numeric(df["value_eur"], errors="coerce") <= req.max_value_eur]
    if req.min_performance_score is not None:
        df = df[pd.to_numeric(df["performance_score"], errors="coerce") >= req.min_performance_score]
    if req.min_potential is not None:
        df = df[pd.to_numeric(df["development_potential"], errors="coerce") >= req.min_potential]
    if req.league_name:
        df = df[df["league_name"] == req.league_name]
    if req.max_risk_tier:
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        ceiling = order.get(req.max_risk_tier.upper(), 2)
        df = df[df["recruitment_risk_tier"].map(lambda t: order.get(str(t), 2)) <= ceiling]

    # Longitudinal evidence is calculated against the selected season and
    # joined only after the current-season eligibility filters are applied.
    df = enrich_search_results(df, store.facts, req.season if req.season is not None else store.current_season())
    if req.min_three_year_avg_performance is not None:
        df = df[pd.to_numeric(df["three_year_avg_performance"], errors="coerce") >= req.min_three_year_avg_performance]
    if req.min_five_year_avg_performance is not None:
        df = df[pd.to_numeric(df["five_year_avg_performance"], errors="coerce") >= req.min_five_year_avg_performance]
    if req.min_performance_trend is not None:
        df = df[pd.to_numeric(df["performance_trend_per_season"], errors="coerce") >= req.min_performance_trend]
    if req.max_performance_consistency_std is not None:
        df = df[pd.to_numeric(df["performance_consistency_std"], errors="coerce") <= req.max_performance_consistency_std]
    if req.min_career_minutes is not None:
        df = df[pd.to_numeric(df["career_minutes_to_date"], errors="coerce") >= req.min_career_minutes]
    if req.min_seasons_played is not None:
        df = df[pd.to_numeric(df["seasons_played_to_date"], errors="coerce") >= req.min_seasons_played]

    score_col = "role_fit_score" if req.role else "performance_score"
    if req.role:
        df = compute_role_fit(df, req.role)
        df = df.sort_values("role_fit_score", ascending=False)
    else:
        df = df.sort_values("performance_score", ascending=False)

    total = len(df)
    result_df = df.head(req.top_n)
    cols = [c for c in [
        "player_id", "short_name", "canonical_position", "club_name", "league_name",
        "age_fifa", "value_eur", "performance_score", "development_potential",
        "role_fit_score", "recruitment_risk_tier", "fair_value_eur",
        "three_year_avg_performance", "five_year_avg_performance",
        "performance_trend_per_season", "performance_consistency_std",
        "career_minutes_to_date", "seasons_played_to_date", "career_peak_performance",
    ] if c in result_df.columns]

    records = _clean_records(result_df[cols])
    # Weight sensitivity analysis (src/validation/sensitivity.py, see
    # docs/VALIDATION.md) found that under +-20% weight perturbation, a
    # single player's score typically moves ~0.6-0.8 points (median), up
    # to ~1.7 at the 90th percentile. A gap this small between adjacent
    # ranked candidates means their relative order is not something the
    # weights can actually distinguish reliably -- flag it rather than
    # present a razor-thin ranking as a confident distinction.
    CLOSE_CALL_THRESHOLD = 2.0
    scores = [r.get(score_col) for r in records]
    for i, r in enumerate(records):
        prev_score = scores[i - 1] if i > 0 else None
        r["close_call_with_previous"] = (
            prev_score is not None and r.get(score_col) is not None
            and (prev_score - r[score_col]) < CLOSE_CALL_THRESHOLD
        )

    return {"total": total, "results": records}


CONTRACT_SNAPSHOT_REASON = (
    "Contract and value-trend data is a current Transfermarkt snapshot, so it is only shown "
    "for the latest season; earlier seasons would show today's contract against an old squad."
)


def _is_latest_season(season: int | None) -> bool:
    return season is None or season == store.current_season()


@router.get("/api/market/opportunities")
def market_opportunities(
    top_n: int = 20,
    min_performance_score: float = 60,
    min_value_gap_pct: float = 0,
    min_age: int | None = None,
    max_age: int | None = None,
    canonical_position: str | None = None,
    league_name: str | None = None,
    risk_tier: str | None = None,
    segment: str = "all",
    season: int | None = None,
    min_reliability_tier: str | None = None,
    max_contract_months: float | None = None,
) -> dict:

    df = store.season(season)
    latest = _is_latest_season(season)
    contract_info: dict = {}
    if latest:
        try:
            from src.features.transfermarkt_context import bulk_contract_info
            contract_info = bulk_contract_info(df["player_id"].tolist())
            if max_contract_months is not None:
                keep = {p for p, i in contract_info.items()
                        if i["contract_months_left"] is not None and 0 <= i["contract_months_left"] <= max_contract_months}
                df = df[df["player_id"].isin(keep)]
        except Exception:
            contract_info = {}

    try:
        result = build_market_intelligence(
            df,
            top_n=top_n,
            min_performance_score=min_performance_score,
            min_value_gap_pct=min_value_gap_pct,
            min_age=min_age,
            max_age=max_age,
            canonical_position=canonical_position,
            league_name=league_name,
            risk_tier=risk_tier,
            segment=segment,
            min_reliability_tier=min_reliability_tier,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    native = _native(result)
    for rec in native.get("results", []):
        rec["contract"] = contract_info.get(rec.get("player_id")) if latest else None

    return {
        "season": (
            season
            if season is not None
            else store.current_season()
        ),
        **native,
        "contract_context": (
            {"available": True, "filter_applied": max_contract_months is not None}
            if latest
            else {"available": False, "reason": CONTRACT_SNAPSHOT_REASON}
        ),
    }


def _club_roster(club_name: str, season: int | None) -> pd.DataFrame:
    df = store.facts
    if df.empty:
        raise HTTPException(status_code=404, detail="No data loaded. Run /api/admin/reload first.")
    if season is not None:
        df = df[df["season"] == season]
    else:
        df = df[df["season"] == df["season"].max()]
    roster = df[df["club_name"] == club_name]
    if roster.empty:
        raise HTTPException(status_code=404, detail=f"No roster found for club '{club_name}' in the requested season.")
    return roster


# ------------------------------------------------------------ squads -----

def _audit_insights(roster: pd.DataFrame) -> dict:
    """Additive and failure-safe: wage vs performance, position dependency, ageing outlook."""
    try:
        from src.features.squad_insights import squad_insights
        return _native(squad_insights(roster, store.facts))
    except Exception:
        return {}


def _audit_contract_outlook(roster: pd.DataFrame, season: int | None) -> dict:
    """Additive, failure-safe contract summary for the roster (latest season only)."""
    if not _is_latest_season(season):
        return {"available": False, "reason": CONTRACT_SNAPSHOT_REASON}
    try:
        from src.features.transfermarkt_context import contract_outlook
        cols = [c for c in ("player_id", "short_name", "canonical_position", "performance_score", "age_fifa") if c in roster.columns]
        return _native(contract_outlook(_clean_records(roster[cols])))
    except Exception:
        return {"available": False, "reason": "Contract data is unavailable."}


# ------------------------------------------------- validation / explainability -----

@router.get("/api/admin/security-status")
def security_status() -> dict:
    """Deployment security posture (admin only when login is enabled)."""
    from src.api.hardening import security_posture
    return security_posture()


@router.get("/api/model-validation")
def model_validation() -> dict:
    """Saved backtest results and the evidence-based status of each model output."""
    from src.validation.loader import load_report
    report = load_report()
    if report is None:
        return {"available": False, "reason": "No validation report has been generated yet. Run: python -m src.validation.report"}
    return {"available": True, **report}


@router.get("/api/model-validation/status")
def model_validation_status() -> dict:
    """Light-weight map used for status badges across the app."""
    from src.validation.loader import status_map
    status = status_map()
    return {"available": bool(status), "status": status}


@router.get("/api/players/{player_id}/explain")
def explain_player_endpoint(player_id: str, season: int | None = None) -> dict:
    from src.features.explain import explain_player
    from src.validation.loader import status_map
    player = _native(get_player(player_id, season))  # 404s for unknown player/season
    return _native(explain_player(player, store.season(season), status_map()))


# ---------------------------------------------------------------- exports -----

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _download(content: bytes, media_type: str, filename: str) -> Response:
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def _optional(fn, *args):
    """Optional report sections must never block the report itself."""
    try:
        return fn(*args)
    except HTTPException:
        return None


@router.get("/api/players/{player_id}/report.pdf")
def player_report(player_id: str, season: int | None = None) -> Response:
    from src.reports.common import file_slug, season_label
    from src.reports.pdf_report import player_report_pdf
    player = _native(get_player(player_id, season))  # 404s for unknown player/season
    pct = _optional(player_percentiles, player_id, season)
    hist = _optional(player_history, player_id)
    tm = _optional(player_transfermarkt, player_id)
    pdf = player_report_pdf(player, (pct or {}).get("percentiles"), (hist or {}).get("history"), tm, season or player.get("season"))
    name = f"scoutiq-{file_slug(player.get('short_name'), 'player')}-{file_slug(season_label(season or player.get('season')))}.pdf"
    return _download(pdf, "application/pdf", name)


@router.get("/api/recruitment/shortlists/{shortlist_id}/export.xlsx")
def export_shortlist(shortlist_id: int, season: int | None = None, session: Session = Depends(get_session)) -> Response:
    from src.reports.common import file_slug
    from src.reports.excel_report import shortlist_workbook
    data = _native(get_shortlist(shortlist_id, season, session))  # 404s for unknown shortlist
    return _download(shortlist_workbook(data, season), XLSX_MIME, f"scoutiq-shortlist-{file_slug(data.get('name'), 'shortlist')}.xlsx")


@router.get("/api/market/opportunities/export.xlsx")
def export_opportunities(
    top_n: int = 200,
    min_performance_score: float = 60,
    min_value_gap_pct: float = 0,
    min_age: int | None = None,
    max_age: int | None = None,
    canonical_position: str | None = None,
    league_name: str | None = None,
    risk_tier: str | None = None,
    segment: str = "all",
    season: int | None = None,
    min_reliability_tier: str | None = None,
    max_contract_months: float | None = None,
) -> Response:
    from src.reports.excel_report import opportunities_workbook
    filters = {"Min performance": min_performance_score, "Min value gap %": min_value_gap_pct, "Min age": min_age, "Max age": max_age,
               "Position": canonical_position, "League": league_name, "Risk tier": risk_tier, "Segment": segment,
               "Min reliability": min_reliability_tier, "Contract ends within (months)": max_contract_months}
    payload = market_opportunities(top_n=max(1, min(top_n, 500)), min_performance_score=min_performance_score, min_value_gap_pct=min_value_gap_pct,
                                   min_age=min_age, max_age=max_age, canonical_position=canonical_position, league_name=league_name,
                                   risk_tier=risk_tier, segment=segment, season=season, min_reliability_tier=min_reliability_tier,
                                   max_contract_months=max_contract_months)
    return _download(opportunities_workbook(_native(payload), filters), XLSX_MIME, "scoutiq-market-opportunities.xlsx")


@router.get("/api/club-profile/report.pdf")
def club_report(season: int | None = None) -> Response:
    from src.reports.common import file_slug
    from src.reports.pdf_report import club_report_pdf
    overview = club_profile_overview(season)
    if not overview.get("configured"):
        raise HTTPException(status_code=404, detail="Club profile is not configured.")
    if overview.get("available") is False:
        raise HTTPException(status_code=404, detail=overview.get("reason", "No squad data for this season."))
    return _download(club_report_pdf(overview), "application/pdf", f"scoutiq-{file_slug(overview['profile']['club_name'], 'club')}-squad-report.pdf")


# ------------------------------------------------------- club profile -----

@router.get("/api/dashboard/club")
def club_dashboard(season: int | None = None, session: Session = Depends(get_session)) -> dict:
    """Everything the Dashboard needs for the active club, in one call. Each part degrades independently."""
    from src.features.club_dashboard import affordable_targets, watchlist_movers
    overview = club_profile_overview(season)
    if not overview.get("configured"):
        return {"configured": False}
    profile, resolved = overview["profile"], overview.get("season", season)
    out = {"configured": True, "season": resolved, "profile": profile, "squad": overview if overview.get("available") else None,
           "unavailable_reason": None if overview.get("available") else overview.get("reason")}
    try:
        tasks = recruitment_tasks(None, False, session)
        out["tasks"] = {"total": tasks["total"], "overdue": tasks["overdue"], "next": tasks["tasks"][:5]}
        ids = [e.player_id for e in session.query(ShortlistEntry).filter(ShortlistEntry.status.notin_(list(CLOSED_STATUSES))).all()]
        out["watchlist_movers"] = _native(watchlist_movers(ids, store.facts, resolved))
        out["watchlist_size"] = len(set(ids))
    except Exception:
        out["tasks"], out["watchlist_movers"], out["watchlist_size"] = None, [], 0
    try:
        out["targets"] = _native(affordable_targets(store.season(season), profile["club_name"], (overview.get("recruitment_priorities") or []),
                                                    profile.get("transfer_budget_eur")))
    except Exception:
        out["targets"] = []
    return out


@router.get("/api/clubs")
def list_clubs(season: int | None = None) -> dict:
    df = store.season(season)
    if df.empty or "club_name" not in df.columns:
        return {"season": season, "clubs": []}
    grouped = df.dropna(subset=["club_name"]).groupby("club_name")
    clubs = [
        {"club_name": name, "league_name": (g["league_name"].mode().iloc[0] if "league_name" in g and g["league_name"].notna().any() else None), "players": int(len(g))}
        for name, g in grouped
    ]
    clubs.sort(key=lambda c: (str(c["league_name"]), c["club_name"]))
    return {"season": season if season is not None else store.current_season(), "clubs": clubs}


@router.get("/api/club-profile")
def get_club_profile() -> dict:
    from src.features.club_profile import list_profiles, load_profile, valid_formations
    profile = load_profile()
    saved = list_profiles()
    return {"configured": profile is not None, "profile": profile, "formations": valid_formations(),
            "clubs": saved["clubs"], "active": saved["active"]}


@router.put("/api/club-profile")
def put_club_profile(req: ClubProfileRequest) -> dict:
    """Create or update a club and make it the active one."""
    from src.features.club_profile import save_profile
    valid = set(store.facts["club_name"].dropna().unique()) if not store.facts.empty else None
    try:
        profile = save_profile(req.club_name, req.formation, req.transfer_budget_eur, req.wage_budget_eur, valid_clubs=valid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"configured": True, "profile": profile}


@router.post("/api/club-profile/activate")
def activate_club_profile(club_name: str) -> dict:
    from src.features.club_profile import set_active
    try:
        return {"configured": True, "profile": set_active(club_name)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/club-profile")
def delete_club_profile(club_name: str | None = None) -> dict:
    """Remove one saved club (default: the active one); another saved club becomes active."""
    from src.features.club_profile import delete_profile, list_profiles, load_profile
    delete_profile(club_name)
    profile = load_profile()
    return {"configured": profile is not None, "profile": profile, "clubs": list_profiles()["clubs"]}


def _season_roster(club_name: str, season: int | None) -> pd.DataFrame:
    df = store.season(season)
    return df[df["club_name"] == club_name] if not df.empty else df


@router.get("/api/club-profile/overview")
def club_profile_overview(season: int | None = None) -> dict:
    from src.features.club_profile import load_profile
    from src.features.club_stats import roster_stats
    profile = load_profile()
    if profile is None:
        return {"configured": False}
    roster = _season_roster(profile["club_name"], season)
    resolved = season if season is not None else store.current_season()
    if roster.empty:
        return {"configured": True, "available": False, "season": resolved, "profile": profile,
                "reason": f"{profile['club_name']} has no players in the dataset for this season."}
    priorities = []
    try:
        audit = audit_squad(roster, formation=profile["formation"])
        priorities = _native(audit.get("recruitment_priorities", []))[:3]
    except Exception:
        priorities = []
    return _native({
        "configured": True, "available": True, "season": resolved, "profile": profile,
        "league_name": roster["league_name"].mode().iloc[0] if "league_name" in roster.columns and roster["league_name"].notna().any() else None,
        **roster_stats(roster),
        "recruitment_priorities": priorities,
        "contract_outlook": _audit_contract_outlook(roster, season),
    })


@router.get("/api/clubs/compare")
def compare_clubs(clubs: list[str] = Query(...), season: int | None = None) -> dict:
    """Side-by-side squad statistics for 2-4 clubs in one season (no saved profile needed)."""
    from src.features.club_stats import roster_stats
    names = list(dict.fromkeys(c.strip() for c in clubs if c.strip()))
    if not 2 <= len(names) <= 4:
        raise HTTPException(status_code=400, detail="Provide between 2 and 4 different clubs.")
    out, missing = [], []
    for name in names:
        roster = _season_roster(name, season)
        if roster.empty:
            missing.append(name)
            continue
        league = roster["league_name"].mode().iloc[0] if "league_name" in roster.columns and roster["league_name"].notna().any() else None
        out.append({"club_name": name, "league_name": league, **roster_stats(roster)})
    if missing:
        raise HTTPException(status_code=404, detail=f"No squad data in this season for: {', '.join(missing)}.")
    return _native({"season": season if season is not None else store.current_season(), "clubs": out})


@router.post("/api/squads/audit")
def squad_audit_endpoint(req: SquadAuditRequest) -> dict:
    """The actual entry point of the recruitment workflow: given a real
    club's real roster, find depth/succession/quality gaps and hand back
    a ready-to-use recruitment search filter for each one -- no manual
    translation from "we have a problem" to "here's what to search for."
    """
    roster = _club_roster(req.club_name, req.season)
    result = audit_squad(roster, formation=req.formation)

    findings = result.pop("findings", [])
    depth_chart = result.pop("depth_chart", pd.DataFrame())
    depth_cols = [c for c in [
        "player_id", "short_name", "canonical_position", "depth_role", "performance_score", "age_fifa",
    ] if c in depth_chart.columns]

    return {
        **result,
        "club_name": req.club_name,
        "season": req.season if req.season is not None else store.current_season(),
        "formation": req.formation,
        "findings": findings,
        "depth_chart": _clean_records(depth_chart[depth_cols]) if not depth_chart.empty else [],
        "contract_outlook": _audit_contract_outlook(roster, req.season),
        "insights": _audit_insights(roster),
    }


@router.post("/api/transfers/simulate")
def transfers_simulate(req: TransferSimulateRequest) -> dict:
    """Before/after squad impact of a single signing, computed against
    the CLUB'S ACTUAL roster average -- not an abstract number.
    """
    roster = _club_roster(req.club_name, req.season)
    current_quality = pd.to_numeric(roster["performance_score"], errors="coerce").mean()
    squad_size = len(roster)

    incoming_row = _latest_row_for_player(req.incoming_player_id, req.season)
    incoming_quality = _native(incoming_row.get("performance_score")) or 0

    outgoing_quality = 0.0
    outgoing_name = None
    if req.outgoing_player_id:
        outgoing_rows = roster[roster["player_id"] == req.outgoing_player_id]
        if outgoing_rows.empty:
            raise HTTPException(status_code=404, detail="outgoing_player_id not found on this club's roster.")
        outgoing_quality = _native(pd.to_numeric(outgoing_rows.iloc[0]["performance_score"], errors="coerce"))
        outgoing_name = outgoing_rows.iloc[0].get("short_name")
        squad_size_after = squad_size  # like-for-like swap, headcount unchanged
    else:
        squad_size_after = squad_size + 1  # pure addition, no one leaves

    result = simulate_transfer(
        current_squad_quality=float(current_quality),
        outgoing_quality=float(outgoing_quality) if req.outgoing_player_id else 0.0,
        incoming_quality=float(incoming_quality),
        squad_size_before=squad_size,
        squad_size_after=squad_size_after,
    )

    return {
        "club_name": req.club_name,
        "season": req.season if req.season is not None else store.current_season(),
        "outgoing_player": outgoing_name,
        "incoming_player": incoming_row.get("short_name"),
        "squad_size_before": squad_size,
        "squad_size_after": squad_size_after,
        **result,
    }


@router.post("/api/squads/optimize")
def squads_optimize(req: SquadOptimizeRequest) -> dict:
    df = store.facts

    if req.season is not None:
        df = df[df["season"] == req.season]
    else:
        df = df[df["season"] == df["season"].max()]

    if req.league_name:
        df = df[
            df["league_name"] == req.league_name
        ]

    if req.max_age is not None:
        df = df[
            pd.to_numeric(
                df["age_fifa"],
                errors="coerce",
            ) <= req.max_age
        ]

    if req.formation not in FORMATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported formation. "
                f"Available: {list(FORMATIONS)}"
            ),
        )

    try:
        result = optimize_squad_ilp(
            df,
            formation=req.formation,
            budget_eur=req.budget_eur,
            strategy=req.strategy,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "season": (
            req.season
            if req.season is not None
            else store.current_season()
        ),
        **result,
    }


# ---------------------------------------------------------- shortlists ---

@router.post("/api/recruitment/shortlists")
def create_shortlist(req: ShortlistCreateRequest, session: Session = Depends(get_session)) -> dict:
    shortlist = Shortlist(name=req.name)
    session.add(shortlist)
    session.commit()
    session.refresh(shortlist)
    return {"id": shortlist.id, "name": shortlist.name}


@router.get("/api/recruitment/shortlists")
def list_shortlists(session: Session = Depends(get_session)) -> dict:
    shortlists = session.query(Shortlist).order_by(Shortlist.created_at.desc()).all()
    return {"results": [{"id": s.id, "name": s.name, "entry_count": len(s.entries), "created_at": s.created_at.isoformat() if s.created_at else None} for s in shortlists]}


CLOSED_STATUSES = {"Rejected", "Signed"}


def _actor(request: Request) -> str:
    user = getattr(request.state, "auth_user", None)
    return (user or {}).get("username") or "anonymous"


def _log_event(session: Session, entry_id: int, actor: str, kind: str, detail: str | None) -> None:
    session.add(EntryEvent(entry_id=entry_id, actor=actor, kind=kind, detail=(detail or "")[:255]))


def _workflow_summary(entries: list[dict]) -> dict:
    """Counts that tell a recruitment lead where attention is needed. Closed entries are ignored."""
    today = date.today()
    open_entries = [e for e in entries if e["status"] not in CLOSED_STATUSES]
    due = [(date.fromisoformat(e["due_date"]), e) for e in open_entries if e.get("due_date")]
    return {
        "open": len(open_entries),
        "overdue": sum(1 for d, _ in due if d < today),
        "due_within_7_days": sum(1 for d, _ in due if 0 <= (d - today).days <= 7),
        "unassigned": sum(1 for e in open_entries if not e.get("owner")),
        "no_next_action": sum(1 for e in open_entries if not e.get("next_action")),
    }


@router.get("/api/recruitment/shortlists/{shortlist_id}")
def get_shortlist(shortlist_id: int, season: int | None = None, session: Session = Depends(get_session)) -> dict:
    shortlist = session.get(Shortlist, shortlist_id)
    if not shortlist:
        raise HTTPException(status_code=404, detail="Shortlist not found.")
    rows = store.facts
    results = []
    for entry in sorted(shortlist.entries, key=lambda e: e.added_at or pd.Timestamp.min.to_pydatetime(), reverse=True):
        match = rows[rows["player_id"] == entry.player_id]
        if season is not None:
            match = match[match["season"] == season]
        player = match.sort_values("season").iloc[-1].to_dict() if not match.empty else {}
        if player:
            try:
                ti = build_transfer_intelligence(rows, entry.player_id, season=season)
                player["opportunity_score"] = ti.get("opportunity_score")
                player["wage_to_value_pct"] = ti.get("wage_to_value_pct")
                player["contract_status"] = ti.get("contract_status")
            except ValueError:
                pass
        results.append({
            "id": entry.id,
            "player_id": entry.player_id,
            "status": entry.status,
            "notes": entry.notes,
            "rating": entry.rating,
            "added_at": entry.added_at.isoformat() if entry.added_at else None,
            "owner": entry.owner,
            "due_date": entry.due_date.isoformat() if entry.due_date else None,
            "next_action": entry.next_action,
            "player": _native(player),
        })
    return {"id": shortlist.id, "name": shortlist.name, "created_at": shortlist.created_at.isoformat() if shortlist.created_at else None, "entries": results, "workflow": _workflow_summary(results)}


@router.post("/api/recruitment/shortlists/{shortlist_id}/entries")
def add_shortlist_entry(shortlist_id: int, req: ShortlistEntryCreateRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    shortlist = session.get(Shortlist, shortlist_id)
    if not shortlist:
        raise HTTPException(status_code=404, detail="Shortlist not found.")
    # Validate here so every database gives the same clean answer (PostgreSQL enforces the player foreign key).
    from src.api.alias_middleware import known_player_ids
    from src.identity.aliases import resolve_player_id
    player_id = resolve_player_id(req.player_id)
    if player_id not in known_player_ids():
        raise HTTPException(status_code=404, detail="Player not found.")
    existing = session.query(ShortlistEntry).filter(
        ShortlistEntry.shortlist_id == shortlist_id,
        ShortlistEntry.player_id == player_id,
    ).first()
    if existing:
        return {"id": existing.id, "player_id": existing.player_id, "status": existing.status, "duplicate": True}
    entry = ShortlistEntry(shortlist_id=shortlist_id, player_id=player_id, status=req.status,
                            notes=req.notes, rating=req.rating)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    _log_event(session, entry.id, _actor(request), "added", f"Added as {entry.status}")
    session.commit()
    return {"id": entry.id, "player_id": entry.player_id, "status": entry.status}


@router.patch("/api/recruitment/entries/{entry_id}")
def update_shortlist_entry(entry_id: int, req: ShortlistEntryUpdateRequest, request: Request, session: Session = Depends(get_session)) -> dict:
    entry = session.get(ShortlistEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found.")
    if req.status is not None and req.status not in RECRUITMENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown status '{req.status}'. Allowed: {RECRUITMENT_STATUSES}")
    new_due = None
    if req.due_date is not None and req.due_date.strip():
        try:
            new_due = date.fromisoformat(req.due_date.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="due_date must be YYYY-MM-DD.")
    actor, events = _actor(request), []
    if req.status is not None and req.status != entry.status:
        events.append(("status", f"{entry.status} -> {req.status}"))
        entry.status = req.status
    if req.notes is not None:
        entry.notes = req.notes
    if req.rating is not None and req.rating != entry.rating:
        events.append(("rating", f"{entry.rating if entry.rating is not None else 'none'} -> {req.rating}"))
        entry.rating = req.rating
    if req.owner is not None:
        owner = req.owner.strip()[:64] or None
        if owner != entry.owner:
            events.append(("owner", f"{entry.owner or 'unassigned'} -> {owner or 'unassigned'}"))
            entry.owner = owner
    if req.due_date is not None and new_due != entry.due_date:
        events.append(("due", f"{entry.due_date.isoformat() if entry.due_date else 'none'} -> {new_due.isoformat() if new_due else 'none'}"))
        entry.due_date = new_due
    if req.next_action is not None:
        action = req.next_action.strip()[:255] or None
        if action != entry.next_action:
            events.append(("next_action", action or "cleared"))
            entry.next_action = action
    for kind, detail in events:
        _log_event(session, entry.id, actor, kind, detail)
    session.commit()
    return {"id": entry.id, "status": entry.status, "notes": entry.notes, "rating": entry.rating, "owner": entry.owner,
            "due_date": entry.due_date.isoformat() if entry.due_date else None, "next_action": entry.next_action}


@router.get("/api/recruitment/entries/{entry_id}/events")
def entry_timeline(entry_id: int, session: Session = Depends(get_session)) -> dict:
    """Change history for one entry, merged with scout notes written about the player."""
    entry = session.get(ShortlistEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found.")
    items = [{"ts": e.ts.isoformat() if e.ts else None, "kind": e.kind, "actor": e.actor, "detail": e.detail}
             for e in session.query(EntryEvent).filter(EntryEvent.entry_id == entry_id).all()]
    items += [{"ts": n.created_at.isoformat() if n.created_at else None, "kind": "note", "actor": n.author, "detail": n.note}
              for n in session.query(ScoutNote).filter(ScoutNote.player_id == entry.player_id).all()]
    items.sort(key=lambda i: i["ts"] or "", reverse=True)
    return {"entry_id": entry_id, "player_id": entry.player_id, "events": items}


@router.get("/api/recruitment/tasks")
def recruitment_tasks(owner: str | None = None, include_closed: bool = False, session: Session = Depends(get_session)) -> dict:
    """Open work across all shortlists: overdue first, then by due date; entries without a date last."""
    today = date.today()
    query = session.query(ShortlistEntry, Shortlist.name).join(Shortlist, Shortlist.id == ShortlistEntry.shortlist_id)
    if owner:
        query = query.filter(ShortlistEntry.owner == owner)
    facts = store.facts
    names = (facts.drop_duplicates("player_id").set_index("player_id")["short_name"].to_dict()
             if {"player_id", "short_name"} <= set(facts.columns) else {})
    rows = []
    for entry, shortlist_name in query.all():
        if not include_closed and entry.status in CLOSED_STATUSES:
            continue
        if not (entry.due_date or entry.next_action or entry.owner):
            continue
        days = (entry.due_date - today).days if entry.due_date else None
        rows.append({"entry_id": entry.id, "shortlist_id": entry.shortlist_id, "shortlist": shortlist_name, "player_id": entry.player_id,
                     "player": names.get(entry.player_id), "status": entry.status, "owner": entry.owner, "next_action": entry.next_action,
                     "due_date": entry.due_date.isoformat() if entry.due_date else None, "days_until_due": days, "overdue": days is not None and days < 0})
    rows.sort(key=lambda r: (r["days_until_due"] is None, r["days_until_due"] if r["days_until_due"] is not None else 0))
    return {"total": len(rows), "overdue": sum(r["overdue"] for r in rows), "tasks": rows[:200]}


@router.get("/api/recruitment/players/{player_id}/notes")
def list_scout_notes(player_id: str, session: Session = Depends(get_session)) -> dict:
    notes = session.query(ScoutNote).filter(ScoutNote.player_id == player_id).order_by(ScoutNote.created_at.desc()).all()
    return {"results": [
        {"id": n.id, "player_id": n.player_id, "author": n.author, "note": n.note,
         "created_at": n.created_at.isoformat() if n.created_at else None}
        for n in notes
    ]}


@router.post("/api/recruitment/players/{player_id}/notes")
def create_scout_note(player_id: str, req: ScoutNoteCreateRequest, session: Session = Depends(get_session)) -> dict:
    if req.player_id != player_id:
        raise HTTPException(status_code=400, detail="player_id does not match path parameter.")
    if not req.note.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty.")
    if store.facts.empty or player_id not in set(store.facts["player_id"].astype(str)):
        raise HTTPException(status_code=404, detail="Player not found.")
    note = ScoutNote(player_id=player_id, author=req.author, note=req.note.strip())
    session.add(note)
    session.commit()
    session.refresh(note)
    return {"id": note.id, "player_id": note.player_id, "author": note.author,
            "note": note.note, "created_at": note.created_at.isoformat() if note.created_at else None}
