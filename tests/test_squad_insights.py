import numpy as np
import pandas as pd
import pytest

from src.features import squad_insights as Q
from src.features.replacement_finder import SIMILAR_WITHIN, compare_components, find_replacements


def _history(n=200, seed=0):
    """Players whose performance falls 1.5 points a year after 28 and rises 2 before 23, with noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        age0, perf = int(rng.integers(18, 34)), rng.uniform(40, 70)
        for k, season in enumerate((1819, 1920, 2021, 2122, 2223)):
            age = age0 + k
            rows.append({"player_id": f"p{i}", "season": season, "age_fifa": age, "performance_score": perf, "playing_time_min": 1800})
            perf += (2.0 if age < 23 else -1.5 if age > 28 else 0.0) + rng.normal(0, 3)
    return pd.DataFrame(rows)


def _roster():
    return pd.DataFrame({"short_name": list("ABCDEF"), "canonical_position": ["CB", "CB", "ST", "ST", "GK", "GK"], "broad_position_group": ["Defender"] * 2 + ["Forward"] * 2 + ["Goalkeeper"] * 2,
                         "age_fifa": [29, 24, 31, 22, 33, 20], "performance_score": [70.0, 55.0, 60.0, 62.0, 65.0, 40.0],
                         "playing_time_min": [3000, 400, 2800, 1500, 3200, 100], "wage_eur": [200e3, 20e3, 150e3, 30e3, 40e3, 5e3]})


def test_age_curve_has_the_right_shape_and_never_fails_on_thin_data():
    curve = Q.empirical_age_curve(_history())
    assert curve[20] > 0.8 and curve[32] < -0.5 and curve[20] > curve[26] > curve[32]
    flat = Q.empirical_age_curve(_history(n=3))
    assert set(flat.values()) == {0.0}  # too little data: no invented ageing


def test_backtest_reports_honestly_whether_the_curve_beats_no_change():
    bt = Q.age_curve_backtest(_history(n=600))
    assert bt["n"] > 0 and bt["mae_age_curve"] < bt["mae_no_change"]  # here the ageing signal is real, so it must show
    assert Q.age_curve_backtest(_history(n=2)) == {"n": 0}


def test_age_profile_is_arithmetic_and_projection_is_labelled_by_its_evidence():
    out = Q.age_outlook(_roster(), Q.empirical_age_curve(_history()), {"n": 10, "improvement_pct": -0.3})
    prof = {p["years_ahead"]: p for p in out["age_profile"]}
    assert prof[0]["aged_30_plus"] == 2 and prof[1]["aged_30_plus"] == 3 and prof[3]["aged_30_plus"] == 3  # ages 29,24,31,22,33,20
    assert prof[2]["average_age"] == pytest.approx(prof[0]["average_age"] + 2)
    assert out["performance_projection"]["status"] == "not_better_than_no_change"
    good = Q.age_outlook(_roster(), Q.empirical_age_curve(_history()), {"n": 10, "improvement_pct": 9.0})
    assert good["performance_projection"]["status"] == "validated"


def test_wage_efficiency_flags_pay_that_outruns_performance():
    w = Q.wage_efficiency(_roster())
    assert w["period"] == "week" and w["annual_estimate_eur"] == pytest.approx(445e3 * 52)
    assert w["by_group"][0]["group"] == "Defender"
    assert [p["short_name"] for p in w["high_pay_below_median_performance"]] == ["C"]  # 150k for a 60 when the median is 61
    assert Q.wage_efficiency(_roster().assign(wage_eur=np.nan)) == {"available": False}


def test_position_dependency_separates_a_weak_backup_from_no_backup():
    d = {p["position"]: p for p in Q.position_dependency(_roster())["positions"]}
    assert d["CB"]["single_point_of_failure"] is True and d["CB"]["starter"] == "A" and d["CB"]["starter_to_backup_drop"] == 15.0
    assert d["ST"]["single_point_of_failure"] is False  # a decent backup, shared minutes
    solo = Q.position_dependency(_roster().iloc[[0, 2, 3]])
    assert {p["position"]: p["no_backup_listed"] for p in solo["positions"]}["CB"] is True
    assert Q.position_dependency(_roster().drop(columns=["playing_time_min"])) == {"available": False}


def test_insights_survive_missing_columns():
    out = Q.squad_insights(_roster()[["short_name", "canonical_position"]], _history())
    assert set(out) == {"wage_efficiency", "position_dependency", "age_outlook"} and all(isinstance(v, dict) for v in out.values())


# ---------------------------------------------------------------- replacement finder
def test_component_comparison_names_what_is_similar_better_and_weaker():
    out = {f"component_{k}": v for k, v in (("attacking", 70), ("passing", 60), ("defending", 80), ("physical", 50))}
    cand = {f"component_{k}": v for k, v in (("attacking", 72), ("passing", 75), ("defending", 60), ("physical", 54))}
    c = compare_components(out, cand)
    assert c["similar_in"] == ["Attacking", "Physical"] and SIMILAR_WITHIN == 5.0
    assert c["better_in"] == [{"label": "Passing", "points": 15.0}] and c["weaker_in"] == [{"label": "Defending", "points": 20.0}]
    assert [r["label"] for r in c["component_comparison"]] == ["Attacking", "Passing", "Defending", "Physical"]
    assert compare_components({}, {}) == {"component_comparison": [], "similar_in": [], "better_in": [], "weaker_in": []}


def test_replacements_carry_skill_comparison_wage_and_scope(pipeline_df):
    latest = pipeline_df.sort_values("season").drop_duplicates("player_id", keep="last")
    pid = latest[latest["broad_position_group"].map(latest["broad_position_group"].value_counts()) >= 4].iloc[0]["player_id"]
    res = find_replacements(latest, pid, top_n=3)
    assert res["candidates"], "synthetic data should contain same-position candidates"
    for c in res["candidates"]:
        assert {"component_comparison", "similar_in", "better_in", "weaker_in", "wage_vs_outgoing_pct", "different_position_group"} <= set(c)
        assert c["different_position_group"] is False
    wide = find_replacements(latest, pid, top_n=50, restrict_to_position_group=False)
    assert any(c["different_position_group"] for c in wide["candidates"]) or len(wide["candidates"]) >= len(res["candidates"])
