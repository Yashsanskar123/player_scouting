from fastapi import APIRouter, HTTPException
import pandas as pd

from src.config.settings import DEFAULT_CLEANED_FILE, DEFAULT_RAW_FILE
from src.data.pipeline import run_pipeline
from src.features.data_quality import data_quality_report
from src.features.role_fit import compute_role_fit_scores, score_team_composition
from src.features.similarity import build_player_scouting_report, find_similar_players, optimize_squad, recommend_team_fit
from src.features.valuation import find_market_opportunities, find_transfer_market_intelligence, score_team_chemistry, segment_players_by_value

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/run-pipeline")
def run_pipeline_endpoint() -> dict[str, str]:
    processed_file = DEFAULT_CLEANED_FILE.replace('_cleaned.csv', '_processed.csv')

    try:
        run_pipeline(
            raw_path=DEFAULT_RAW_FILE,
            cleaned_path=DEFAULT_CLEANED_FILE,
            mapping_path=DEFAULT_CLEANED_FILE.replace('cleaned.csv', 'cleaning_map.csv'),
            processed_path=processed_file,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "success", "processed_file": processed_file}


@router.get("/players/similar")
def similar_players(player_identifier: str, top_n: int = 5) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)

    try:
        results = find_similar_players(df, player_identifier=player_identifier, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"results": results.to_dict(orient='records')}


@router.get("/players/team-fit")
def team_fit(
    min_overall: float = 70,
    max_budget_eur: float | None = None,
    preferred_age: int = 25,
    preferred_foot: str | None = None,
    target_positions: str | None = None,
    top_n: int = 10,
) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)

    target_positions_list = [item.strip() for item in (target_positions or '').split(',') if item.strip()]
    results = recommend_team_fit(
        df,
        target_profile={
            'min_overall': min_overall,
            'max_budget_eur': max_budget_eur,
            'preferred_age': preferred_age,
            'preferred_foot': preferred_foot,
            'target_positions': target_positions_list,
        },
        top_n=top_n,
    )

    return {"results": results.to_dict(orient='records')}


@router.get("/players/role-fit")
def role_fit(target_role: str, top_n: int = 10) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)

    try:
        results = compute_role_fit_scores(df, target_role=target_role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"results": results.head(top_n).to_dict(orient='records')}


@router.get("/teams/composition")
def team_composition(formation: str = '4-3-3') -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    return score_team_composition(df, formation=formation)


@router.get("/players/scouting-report")
def scouting_report(player_identifier: str, target_role: str = 'ST', top_n: int = 5) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)

    try:
        return build_player_scouting_report(df, player_identifier=player_identifier, target_role=target_role, top_n=top_n)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/players/value-segmentation")
def value_segmentation() -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    segmented = segment_players_by_value(df)
    return {"results": segmented.to_dict(orient='records')}


@router.get("/players/market-opportunities")
def market_opportunities(top_n: int = 5) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    opportunities = find_market_opportunities(df, top_n=top_n)
    return {"results": opportunities.to_dict(orient='records')}


@router.get("/players/transfer-market")
def transfer_market(top_n: int = 5) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    transfer = find_transfer_market_intelligence(df, top_n=top_n)
    return {"results": transfer.to_dict(orient='records')}


@router.get("/teams/squad-optimizer")
def squad_optimizer(formation: str = '4-3-3', top_n: int = 5) -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    return optimize_squad(df, formation=formation, top_n=top_n)


@router.get("/teams/chemistry")
def team_chemistry() -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    return score_team_chemistry(df)


@router.get("/data-quality")
def data_quality() -> dict[str, object]:
    df = pd.read_csv(DEFAULT_CLEANED_FILE, low_memory=False)
    return data_quality_report(df)
