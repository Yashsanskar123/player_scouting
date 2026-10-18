import numpy as np
import pandas as pd

from src.features import data_health as H


def _frame(seasons=(1819, 1920, 2021, 2122, 2223), leagues=("A", "B", "C"), per_league=40, seed=0, drop_league=None, xg_missing=None):
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        for lg in leagues:
            if drop_league and s == seasons[-1] and lg == drop_league:
                continue
            for i in range(per_league):
                rows.append({"player_id": f"{s}-{lg}-{i}", "season": s, "league_name": lg, "club_name": f"{lg}{i % 10}", "performance_score": rng.normal(55, 8),
                             "age_fifa": rng.normal(26, 3), "value_eur": 1e6 * rng.uniform(1, 9), "playing_time_min": rng.uniform(100, 3000),
                             H.ADVANCED_COLUMN: np.nan if (xg_missing and s in xg_missing and rng.random() < 0.6) else rng.normal(0.2, 0.1)})
    return pd.DataFrame(rows)


def test_a_missing_league_makes_the_season_partial_and_names_it():
    cov = H.season_coverage(_frame(drop_league="C"))
    assert cov[2223]["status"] == "partial" and cov[2223]["missing_leagues"] == ["C"]
    assert "Missing 1 of 3 usual leagues: C" in cov[2223]["note"] and "not comparable" in cov[2223]["note"]
    assert all(cov[s]["status"] == "complete" for s in (1819, 1920, 2021, 2122))


def test_a_big_drop_in_players_makes_the_season_partial_even_with_all_leagues():
    df = _frame()
    last = df[df.season == 2223]
    df = pd.concat([df[df.season != 2223], last.sample(frac=0.5, random_state=1)])
    assert H.season_coverage(df)[2223]["status"] == "partial"


def test_full_seasons_have_no_warning_and_limited_advanced_stats_is_reported():
    cov = H.season_coverage(_frame(xg_missing={1819}))
    assert all(v["status"] == "complete" and v["note"] == "" for k, v in cov.items() if k != 1819)
    assert cov[1819]["advanced_limited"] is True and "Advanced statistics" in cov[1819]["note"]


def test_drift_alerts_flag_real_shifts_and_ignore_noise():
    df = _frame(xg_missing={2021})
    alerts = H.drift_alerts(df)
    assert any(a["kind"] == "missing_data" and a["season"] == 2021 for a in alerts)
    noise = [a for a in H.drift_alerts(_frame(seed=3)) if a["kind"] == "shifted_average"]
    assert noise == []  # tiny random wobble between seasons must not alert
    shifted = _frame()
    shifted.loc[shifted.season == 2223, "value_eur"] *= 2
    assert any(a["kind"] == "shifted_average" and a["season"] == 2223 and "market value" in a["metric"] for a in H.drift_alerts(shifted))
    assert H.drift_alerts(_frame(seasons=(1819, 1920))) == []  # too little history to judge


def test_anomalies_and_identity_notes():
    df = _frame(per_league=10)
    df.loc[0, "adjusted_performance_score"] = 0
    df["adjusted_performance_score"] = df["adjusted_performance_score"].fillna(50)
    df.loc[1, "age_fifa"] = 12
    got = {a["key"]: a["rows"] for a in H.anomalies(df)}
    assert got["score_floor"] == 1 and got["age_outlier"] == 1
    df["identity_confidence"] = "medium"
    assert "cannot tell" in H.identity_quality(df)["identity_confidence_note"]
    df.loc[:10, "identity_confidence"] = "high"
    assert H.identity_quality(df)["identity_confidence_note"] is None


def test_empty_and_minimal_frames_never_raise():
    assert H.season_coverage(pd.DataFrame()) == {}
    minimal = pd.DataFrame({"player_id": ["a", "b"], "season": [2425, 2425]})
    assert H.season_coverage(minimal)[2425]["status"] == "complete"
    assert H.missingness(minimal)["by_season"][0]["season"] == 2425

