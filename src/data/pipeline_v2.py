"""Unified analytics pipeline (spec section 58): raw -> validated -> clean
-> normalized -> feature-engineered -> analytics tables -> model scoring.

This replaces the old 4-line `run_pipeline` (clean -> 2 feature functions
-> 1 score) with the full chain built out in this session. Every step is
a pure function on a DataFrame, so the pipeline itself stays a thin,
readable sequence -- the logic lives in src/features, src/identity,
src/taxonomy, not here.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from src.data.clean_dataset import clean_dataset
from src.identity.resolve_identity import assign_player_ids, duplicate_identity_report
from src.identity.aliases import apply_aliases
from src.taxonomy.positions import assign_position_taxonomy
from src.features.reliability import compute_reliability_score
from src.features.percentiles import compute_percentiles
from src.features.performance_score import compute_performance_score
from src.features.potential import compute_potential
from src.features.advanced_potential import compute_advanced_potential
from src.features.risk import compute_risk
from src.features.league_adjustment import fit_league_strength, apply_league_adjustment
from src.features.valuation_model import train_valuation_model, predict_fair_value
from src.data_quality.quality_score import data_quality_score
from src.data_quality.data_dictionary import write_data_dictionary


def run_pipeline_v2(
    raw_path: str,
    cleaned_path: str,
    mapping_path: str,
    processed_path: str,
    data_dictionary_path: str | None = None,
) -> dict:
    """Runs the full pipeline and returns the processed DataFrame plus a
    report dict summarizing what happened at each stage -- this report is
    what should be surfaced on an admin/data-quality page, not buried in
    logs.
    """
    timings = {}
    t0 = time.time()

    clean_dataset(raw_path=raw_path, cleaned_path=cleaned_path, mapping_path=mapping_path)
    timings["clean_dataset"] = round(time.time() - t0, 2)

    t1 = time.time()
    df = pd.read_csv(cleaned_path, low_memory=False)

    df = assign_player_ids(df)
    df = apply_aliases(df)  # merge verified duplicate ids (no-op if no alias file)
    identity_report = duplicate_identity_report(df)

    df = assign_position_taxonomy(df)
    df = compute_reliability_score(df)
    df = compute_percentiles(df)
    df = compute_performance_score(df)
    df = compute_potential(df)
    df = compute_advanced_potential(df)
    df = compute_risk(df)
    timings["feature_engineering"] = round(time.time() - t1, 2)

    t1b = time.time()
    league_strength_result = fit_league_strength(df, min_transitions=15)
    df = apply_league_adjustment(df, league_strength_result["strengths"])
    timings["league_strength_adjustment"] = round(time.time() - t1b, 2)

    t2 = time.time()
    quality_report = data_quality_score(df)
    timings["data_quality_scoring"] = round(time.time() - t2, 2)

    if data_dictionary_path:
        write_data_dictionary(df, data_dictionary_path)

    t3 = time.time()
    model_bundle = train_valuation_model(df)
    df = predict_fair_value(model_bundle, df)
    timings["valuation_model_train_and_score"] = round(time.time() - t3, 2)

    processed_file = Path(processed_path)
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(processed_file, index=False)
    timings["total"] = round(time.time() - t0, 2)

    return {
        "processed_path": processed_path,
        "rows": len(df),
        "columns": df.shape[1],
        "identity_report": identity_report,
        "data_quality": quality_report,
        "league_strength": {k: v for k, v in league_strength_result.items() if k != "strengths"} | {
            "strengths": league_strength_result["strengths"]
        },
        "valuation_model_metrics": model_bundle["metrics"],
        "timings_sec": timings,
    }


if __name__ == "__main__":
    # CLI entry point used by the documented local setup command.
    # Keep paths centralized in settings so the pipeline can be run from
    # the project root without manually passing four arguments.
    from src.config.settings import (
        DEFAULT_RAW_FILE,
        DEFAULT_CLEANED_FILE,
        DEFAULT_MAPPING_FILE,
    )

    project_root = Path(__file__).resolve().parents[2]
    processed_file = project_root / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"
    data_dictionary_file = project_root / "docs" / "DATA_DICTIONARY_PREVIEW.md"

    print("Running ScoutIQ analytics pipeline v2...")
    print(f"Raw input: {DEFAULT_RAW_FILE}")
    print(f"Cleaned output: {DEFAULT_CLEANED_FILE}")
    print(f"Processed output: {processed_file}")

    report = run_pipeline_v2(
        raw_path=str(DEFAULT_RAW_FILE),
        cleaned_path=str(DEFAULT_CLEANED_FILE),
        mapping_path=str(DEFAULT_MAPPING_FILE),
        processed_path=str(processed_file),
        data_dictionary_path=str(data_dictionary_file),
    )

    print("Pipeline completed successfully.")
    print(f"Rows: {report['rows']:,}")
    print(f"Columns: {report['columns']:,}")
    print(f"Processed file: {report['processed_path']}")
    print(f"Total time: {report['timings_sec']['total']}s")
