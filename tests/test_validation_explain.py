import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features.explain import explain_performance, explain_player, explain_potential, explain_risk, explain_value
from src.features.performance_score import COMPONENT_FEATURES, POSITION_COMPONENT_WEIGHTS, compute_performance_score
from src.features.potential import compute_potential
from src.features.risk import compute_risk
from src.validation import loader, report as R
from src.validation.sensitivity import performance_score_sensitivity

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"


def _players(n=60, seasons=(1920, 2021, 2122, 2223), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        base = rng.uniform(30, 80)
        for k, s in enumerate(seasons):
            rows.append({"player_id": f"p{i}", "season": s, "canonical_position": "ST", "age_fifa": 20 + k + (i % 8),
                         "performance_score": float(np.clip(base + rng.normal(0, 5), 0, 100)), "playing_time_min": 1500,
                         "value_eur": 1e6 * rng.uniform(1, 50), "fair_value_eur": 1e6 * rng.uniform(1, 50), "value_gap_pct": rng.normal(0, 30),
                         "development_potential": 60.0, "league_name": "Premier League", "broad_position_group": "Forward"})
    return pd.DataFrame(rows)


# ------------------------------------------------------------- explanations
def test_explanations_reconcile_with_the_pipeline_on_synthetic_rows():
    rng = np.random.default_rng(1)
    feats = {f: rng.uniform(0, 100, 40) for fs in COMPONENT_FEATURES.values() for f in fs}
    df = pd.DataFrame({"canonical_position": ["ST"] * 20 + ["CB"] * 20, **feats})
    df.loc[3, ["per_90_minutes_gls_pctile", "per_90_minutes_x_g_pctile", "per_90_minutes_npx_g_pctile"]] = np.nan  # a missing component
    df["age_fifa"], df["potential"] = 24, 80.0
    df["league_name"], df["playing_time_min"], df["season"], df["player_id"] = "Serie B", 1800, 2425, [f"x{i}" for i in range(40)]
    df["per_90_minutes_gls"], df["per_90_minutes_ast"], df["per_90_minutes_prg_c"] = 0.3, 0.2, 3.0
    df["per_90_minutes_tackles_tkl"], df["value_eur"] = 2.0, 1e6
    df["sample_reliability_score"] = 70.0
    df = compute_risk(compute_potential(compute_performance_score(df)))
    for row in df.to_dict("records"):
        p = explain_performance(row, None)
        assert p["available"] and p["reconciles"], row["canonical_position"]
        assert explain_risk(row)["reconciles"] and explain_potential(row)["reconciles"]
    missing = explain_performance(df.iloc[3].to_dict(), None)
    assert "Attacking" in missing["missing_components"]
    assert abs(sum(c["effective_weight"] for c in missing["components"]) - 1.0) < 0.01  # weights rescale over what exists


@pytest.mark.skipif(not PROCESSED.exists(), reason="processed dataset not present")
def test_every_breakdown_matches_the_stored_numbers_on_real_data():
    df = pd.read_csv(PROCESSED, low_memory=False).sample(4000, random_state=3)
    bad = 0
    for row in df.to_dict("records"):
        for part in (explain_performance(row, None), explain_risk(row), explain_potential(row)):
            if part.get("available") and not part["reconciles"]:
                bad += 1
        league = explain_performance(row, None).get("league", {})
        if league.get("reconciles") is False:
            bad += 1
    assert bad == 0


def test_explain_handles_missing_data_without_failing():
    out = explain_player({"player_id": "x", "short_name": "Nobody", "canonical_position": "ST"}, None, {})
    assert out["performance"]["available"] is False and out["risk"]["available"] is False
    assert explain_value({"value_eur": 1e6}, None)["available"] is False


def test_value_explanation_finds_comparable_players():
    peers = pd.DataFrame({"player_id": [f"q{i}" for i in range(12)], "age_fifa": 24, "performance_score": 60.0, "value_eur": np.arange(1, 13) * 1e6})
    v = explain_value({"player_id": "me", "age_fifa": 25, "performance_score": 62.0, "value_eur": 5e6, "fair_value_eur": 6e6, "value_gap_pct": 20}, peers)
    assert v["comparable_players"]["n"] == 12 and v["comparable_players"]["median_value_eur"] == 6.5e6


# ------------------------------------------------------ validation runner
def test_sensitivity_compares_rows_not_a_many_to_many_join():
    """Regression: players have several seasons; joining on player_id alone diluted rank correlation (0.55 vs 0.999)."""
    rng = np.random.default_rng(5)
    n = 80
    cols = {f: rng.uniform(0, 100, n * 3) for fs in COMPONENT_FEATURES.values() for f in fs}
    df = pd.DataFrame({"player_id": np.repeat([f"p{i}" for i in range(n)], 3), "season": np.tile([1920, 2021, 2122], n),
                       "canonical_position": "ST", **cols})
    res = performance_score_sensitivity(df, "ST", n_trials=8)
    assert res["mean_rank_correlation"] > 0.95


def test_blend_backtest_beats_naive_on_mean_reverting_data():
    r = R.backtest_expected_12m(_players())
    assert r["n"] > 0 and r["blend"]["mae"] < r["naive_last"]["mae"] and r["improvement_vs_naive_pct"] > 0


def test_event_backtest_only_learns_from_earlier_seasons_and_reports_calibration():
    out = R.backtest_events(_players(n=150))
    assert out["n"] > 0 and 0 <= out["breakout"]["auc"] <= 1
    assert len(out["breakout"]["calibration"]) == 5
    assert all(0 <= c["mean_predicted"] <= 1 and 0 <= c["observed_rate"] <= 1 for c in out["decline"]["calibration"])


def test_stability_and_development_potential_backtests_run():
    df = _players()
    assert R.score_stability(df)["n"] > 0
    dp = R.backtest_development_potential(df)
    assert dp["mean_bias_points"] == pytest.approx(60.0 - df.performance_score.mean(), abs=8)


def _sections(**over):
    s = {"score_stability": {"overall_spearman": 0.56, "by_position": [{"position": "GK", "spearman": 0.15}]},
         "market": {"score_vs_market": [{"measure": "performance_score", "spearman_vs_market_value": 0.28},
                                        {"measure": "adjusted_performance_score", "spearman_vs_market_value": 0.42}],
                    "score_vs_market_by_position": [], "fair_value_vs_market": {},
                    "value_gap_forward": {"n": 100, "spearman_within_season_and_age_band": 0.01, "seasons_with_positive_relationship": "3/8"}},
         "sensitivity": {"worst_rank_correlation": 0.96},
         "expected_12m": {"n": 10, "blend": {"mae": 9.1}, "naive_last": {"mae": 9.9}, "history_mean": {"mae": 9.4}, "improvement_vs_naive_pct": 8.0},
         "horizons": {"2m_season": {"correlation": 0.53, "MAE": 9.0, "n": 5}},
         "development_potential": {"mean_bias_points": 14.7, "mae_development_potential": 16.0, "mae_naive_current": 10.2},
         "events": {"n": 100, "breakout": {"auc": 0.63, "max_calibration_gap": 0.07, "top_quintile_lift": 1.5},
                    "decline": {"auc": 0.52, "max_calibration_gap": 0.02, "top_quintile_lift": 1.1}},
         "risk": {"summary_by_risk_tier": [{"tier": t, "pct_declined": 50.0} for t in ("LOW", "MEDIUM", "HIGH")]},
         "role_fit": [{"role": "r", "partial_correlation_role_fit_vs_future_minutes_controlling_for_performance": 0.05}]}
    s.update(over)
    return s


def test_status_rules_follow_the_measured_numbers():
    by = {i["key"]: i["status"] for i in R.build_registry(_sections())}
    assert by["value_gap"] == "not_validated" and by["development_potential"] == "exploratory"
    assert by["expected_performance_12m"] == "validated" and by["breakout_probability"] == "partially_validated"
    assert by["decline_probability"] == "exploratory" and by["role_fit"] == "exploratory"
    good = _sections()
    good["market"]["value_gap_forward"] = {"n": 100, "spearman_within_season_and_age_band": 0.2, "seasons_with_positive_relationship": "7/8"}
    assert {i["key"]: i["status"] for i in R.build_registry(good)}["value_gap"] == "validated"


def test_age_outlook_status_follows_its_backtest():
    weak = _sections(age_curve={"n": 100, "mae_age_curve": 8.52, "mae_no_change": 8.5, "improvement_pct": -0.3})
    assert {i["key"]: i["status"] for i in R.build_registry(weak)}["age_outlook"] == "exploratory"
    strong = _sections(age_curve={"n": 100, "mae_age_curve": 7.0, "mae_no_change": 8.5, "improvement_pct": 17.6})
    assert {i["key"]: i["status"] for i in R.build_registry(strong)}["age_outlook"] == "partially_validated"
    assert "age_outlook" not in {i["key"] for i in R.build_registry(_sections())}  # older reports without it still build


def test_registry_never_rates_the_performance_score_fully_validated():
    by = {i["key"]: i["status"] for i in R.build_registry(_sections())}
    assert by["performance_score"] == "partially_validated"


def test_report_loader_handles_missing_and_cached_files(tmp_path, monkeypatch):
    path = tmp_path / "validation_report.json"
    monkeypatch.setattr(loader, "REPORT_PATH", path)
    loader._cache.update(mtime=None, data=None)
    assert loader.load_report() is None and loader.status_map() == {}
    path.write_text(json.dumps({"registry": [{"key": "k", "status": "validated", "status_label": "Validated", "summary": "s"}]}))
    assert loader.status_map()["k"]["status"] == "validated"
    path.write_text("{ not json")
    loader._cache.update(mtime=None, data=None)
    assert loader.load_report() is None  # a corrupt file never raises


def test_market_validation_is_skipped_cleanly_without_transfermarkt(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "EXTERNAL", tmp_path)
    assert R.market_validation(_players()) == {"available": False}
