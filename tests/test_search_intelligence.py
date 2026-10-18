import pytest
import pandas as pd

from src.features.search_intelligence import canonical_player_season, player_longitudinal_features


def test_canonical_player_season_deduplicates():
    df = pd.DataFrame([
        {"player_id": "p1", "season": 2425, "playing_time_min": 500, "performance_score": 60},
        {"player_id": "p1", "season": 2425, "playing_time_min": 1200, "performance_score": 58},
        {"player_id": "p1", "season": 2324, "playing_time_min": 1100, "performance_score": 55},
    ])
    out = canonical_player_season(df)
    assert len(out) == 2
    assert out.loc[out.season == 2425, "playing_time_min"].iloc[0] == 1200


def test_longitudinal_features_are_season_aware():
    df = pd.DataFrame([
        {"player_id": "p1", "season": 2021, "playing_time_min": 1200, "performance_score": 50},
        {"player_id": "p1", "season": 2122, "playing_time_min": 1300, "performance_score": 60},
        {"player_id": "p1", "season": 2223, "playing_time_min": 1400, "performance_score": 70},
        {"player_id": "p1", "season": 2324, "playing_time_min": 1500, "performance_score": 80},
        {"player_id": "p1", "season": 2425, "playing_time_min": 1600, "performance_score": 90},
    ])
    out = player_longitudinal_features(df, 2425).iloc[0]
    assert out["three_year_avg_performance"] == pytest.approx(80)
    assert out["five_year_avg_performance"] == pytest.approx(70)
    assert out["performance_trend_per_season"] == pytest.approx(10)
    assert out["career_minutes_to_date"] == 7000
    assert out["seasons_played_to_date"] == 5


# ----------------------------------------------------- vectorised == original
def _reference_features(facts, season):
    """The original per-player loop implementation, kept to prove the vectorised version computes the same values."""
    from src.features.search_intelligence import _slope, canonical_player_season
    df = canonical_player_season(facts)
    seasons = sorted(pd.to_numeric(df["season"], errors="coerce").dropna().astype(int).unique())
    prior = [s for s in seasons if s <= season]
    last3, last5 = prior[-3:], prior[-5:]
    scoped = df[df["season"].isin(prior)].copy()
    scoped["_perf"] = pd.to_numeric(scoped.get("performance_score"), errors="coerce")
    scoped["_minutes"] = pd.to_numeric(scoped.get("playing_time_min"), errors="coerce").fillna(0)
    rows = []
    for pid, g in scoped.groupby("player_id", sort=False):
        o = g.sort_values("season")
        r3, r5 = o[o["season"].isin(last3)]["_perf"].dropna(), o[o["season"].isin(last5)]["_perf"].dropna()
        el = o[o["_minutes"] >= 900]["_perf"].dropna()
        rows.append({"player_id": pid, "three_year_avg_performance": float(r3.mean()) if len(r3) else None, "five_year_avg_performance": float(r5.mean()) if len(r5) else None,
                     "performance_consistency_std": float(r5.std(ddof=0)) if len(r5) >= 2 else None, "performance_trend_per_season": _slope(el),
                     "career_minutes_to_date": float(o["_minutes"].sum()), "seasons_played_to_date": int(o["season"].nunique()),
                     "seasons_900m_to_date": int((o["_minutes"] >= 900).sum()), "career_peak_performance": float(o["_perf"].max()) if o["_perf"].notna().any() else None})
    return pd.DataFrame(rows)


def _messy_history(seed=0, n=120):
    rng = __import__("numpy").random.default_rng(seed)
    rows = []
    for i in range(n):
        for s in (1819, 1920, 2021, 2122, 2223, 2324):
            if rng.random() < 0.25:
                continue  # gaps in a career
            for _ in range(2 if rng.random() < 0.05 else 1):  # occasional duplicate player-season rows
                rows.append({"player_id": f"p{i}", "season": s, "performance_score": None if rng.random() < 0.1 else float(rng.uniform(30, 80)),
                             "playing_time_min": float(rng.choice([0, 200, 900, 1500, 2800]))})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("season", [1819, 2021, 2324])
def test_vectorised_features_equal_the_original_implementation(season):
    from src.features.search_intelligence import FEATURE_COLUMNS, player_longitudinal_features
    facts = _messy_history()
    new = player_longitudinal_features(facts, season).set_index("player_id").sort_index()
    ref = _reference_features(facts, season).set_index("player_id").sort_index()
    assert list(new.index) == list(ref.index)
    for col in FEATURE_COLUMNS:
        a, b = pd.to_numeric(new[col], errors="coerce"), pd.to_numeric(ref[col], errors="coerce")
        assert (a.isna() == b.isna()).all(), col
        assert (a - b).abs().max(skipna=True) < 1e-9 or a.notna().sum() == 0, col


def test_features_are_cached_per_data_version_and_season():
    from src.features import search_intelligence as SI
    facts = _messy_history()
    first = SI.cached_longitudinal_features(facts, 2324)
    assert SI.cached_longitudinal_features(facts, 2324) is first  # same data + season: no recomputation
    assert SI.cached_longitudinal_features(facts, 2223) is not first  # a different season has its own entry
    assert SI.cached_longitudinal_features(_messy_history(seed=1), 2324) is not first  # new data object: never serves stale features
