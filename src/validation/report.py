"""Run every model backtest and write one reproducible validation report.

  python -m src.validation.report            ->  data/validation/validation_report.json

Everything is computed from this project's own multi-season history (plus the
Transfermarkt snapshot, when present, as an INDEPENDENT market benchmark).
Each model output gets a status from explicit rules (see build_registry), so
what the UI shows is derived from measured numbers, not hand-written.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from src.features.advanced_potential import (BREAKOUT_DELTA, DECLINE_DELTA, MIN_COHORT, _age_band, _direction,
                                             backtest_advanced_horizons)
from src.features.performance_score import POSITION_COMPONENT_WEIGHTS
from src.features.potential import RECENCY_WEIGHT
from src.identity.aliases import apply_aliases
from src.features.squad_insights import age_curve_backtest
from src.validation.backtest_risk import backtest_risk_tiers

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "cleaned" / "fifa_fbref_merged_processed_v2.csv"
EXTERNAL = ROOT / "data" / "external"
REPORT_PATH = ROOT / "data" / "validation" / "validation_report.json"


def _r(x, d=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def _rho(a, b):
    a, b = pd.Series(a).astype(float), pd.Series(b).astype(float)
    ok = a.notna() & b.notna()
    return float(spearmanr(a[ok], b[ok])[0]) if ok.sum() >= 5 else float("nan")


def _season_start(code) -> pd.Timestamp:
    return pd.Timestamp(year=2000 + int(code) // 100, month=8, day=1)


# ------------------------------------------------------------------ potential
def backtest_expected_12m(df: pd.DataFrame, min_seasons: int = 3) -> dict:
    recs = []
    for _, g in df.sort_values("season").groupby("player_id"):
        y = pd.to_numeric(g["performance_score"], errors="coerce").dropna().to_numpy()
        if len(y) < min_seasons:
            continue
        train, actual = y[:-1], y[-1]
        recs.append({"actual": actual, "blend": RECENCY_WEIGHT * train[-1] + (1 - RECENCY_WEIGHT) * train.mean(),
                     "naive_last": train[-1], "history_mean": train.mean()})
    if not recs:
        return {"n": 0}
    r = pd.DataFrame(recs)
    out = {"n": int(len(r))}
    for m in ("blend", "naive_last", "history_mean"):
        out[m] = {"mae": _r((r.actual - r[m]).abs().mean(), 2), "correlation": _r(r.actual.corr(r[m]))}
    out["improvement_vs_naive_pct"] = _r((1 - out["blend"]["mae"] / out["naive_last"]["mae"]) * 100, 1)
    return out


def backtest_development_potential(df: pd.DataFrame) -> dict:
    recs = []
    for _, g in df.sort_values("season").groupby("player_id"):
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        d = pd.to_numeric(g["development_potential"], errors="coerce").to_numpy()
        for i in range(len(g) - 1):
            if not (np.isnan(y[i]) or np.isnan(y[i + 1]) or np.isnan(d[i])):
                recs.append((y[i + 1], y[i], d[i]))
    r = pd.DataFrame(recs, columns=["actual", "current", "dev_potential"])
    if r.empty:
        return {"n": 0}
    return {"n": int(len(r)),
            "mae_development_potential": _r((r.actual - r.dev_potential).abs().mean(), 2),
            "mae_naive_current": _r((r.actual - r.current).abs().mean(), 2),
            "mean_bias_points": _r((r.dev_potential - r.actual).mean(), 2),
            "correlation": _r(r.actual.corr(r.dev_potential))}


def _event_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, g in df.sort_values("season").groupby("player_id"):
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        ages = pd.to_numeric(g["age_fifa"], errors="coerce").to_numpy()
        seasons = g["season"].to_numpy()
        for i in range(len(g) - 1):
            if np.isnan(y[i]) or np.isnan(y[i + 1]):
                continue
            rows.append({"season": int(seasons[i]), "band": _age_band(ages[i]), "direction": _direction(y[: i + 1]),
                         "breakout": float(y[i + 1] - y[i] >= BREAKOUT_DELTA), "decline": float(y[i + 1] - y[i] <= DECLINE_DELTA)})
    return pd.DataFrame(rows)


def backtest_events(df: pd.DataFrame) -> dict:
    """Out-of-time test: rates learned ONLY from earlier seasons predict each later season's transitions."""
    T = _event_rows(df)
    seasons = sorted(T["season"].unique())
    preds = []
    for s in seasons[1:]:
        train, test = T[T.season < s], T[T.season == s]
        if len(train) < 200 or test.empty:
            continue
        grp = train.groupby(["band", "direction"]).agg(b=("breakout", "mean"), d=("decline", "mean"), n=("breakout", "size"))
        stable = {k[0]: v for k, v in grp.iterrows() if k[1] == "stable"}
        t = test.copy()
        pb, pd_, ns = [], [], []
        for band, direction in zip(t.band, t.direction):
            hit = grp.loc[(band, direction)] if (band, direction) in grp.index else stable.get(band)
            if hit is None:
                pb.append(train.breakout.mean()); pd_.append(train.decline.mean()); ns.append(0)
            else:
                pb.append(hit["b"]); pd_.append(hit["d"]); ns.append(int(hit["n"]))
        t["p_breakout"], t["p_decline"], t["cohort_n"] = pb, pd_, ns
        t["base_breakout"], t["base_decline"] = train.breakout.mean(), train.decline.mean()
        preds.append(t)
    if not preds:
        return {"n": 0}
    P = pd.concat(preds, ignore_index=True)
    out = {"n": int(len(P)), "test_seasons": int(P.season.nunique()), "low_evidence_share": _r((P.cohort_n < MIN_COHORT).mean())}
    for ev, p, base in (("breakout", "p_breakout", "base_breakout"), ("decline", "p_decline", "base_decline")):
        y = P[ev]
        auc = roc_auc_score(y, P[p]) if y.nunique() > 1 else float("nan")
        bins = pd.qcut(P[p].rank(method="first"), 5, labels=False)
        cal = [{"bin": int(b) + 1, "n": int((bins == b).sum()), "mean_predicted": _r(P.loc[bins == b, p].mean()),
                "observed_rate": _r(y[bins == b].mean())} for b in sorted(bins.unique())]
        out[ev] = {"observed_base_rate": _r(y.mean()), "auc": _r(auc),
                   "brier_model": _r(((P[p] - y) ** 2).mean(), 4), "brier_baseline": _r(((P[base] - y) ** 2).mean(), 4),
                   "top_quintile_lift": _r(cal[-1]["observed_rate"] / y.mean(), 2) if y.mean() else None,
                   "max_calibration_gap": _r(max(abs(c["mean_predicted"] - c["observed_rate"]) for c in cal)),
                   "calibration": cal}
    return out


# ---------------------------------------------------------------- performance
def score_stability(df: pd.DataFrame, min_minutes: int = 900) -> dict:
    recs = []
    for _, g in df.sort_values("season").groupby("player_id"):
        y = pd.to_numeric(g["performance_score"], errors="coerce").to_numpy()
        m = pd.to_numeric(g["playing_time_min"], errors="coerce").to_numpy()
        pos, lg = g["canonical_position"].to_numpy(), g["league_name"].to_numpy()
        for i in range(len(g) - 1):
            if m[i] >= min_minutes and m[i + 1] >= min_minutes and not (np.isnan(y[i]) or np.isnan(y[i + 1])):
                recs.append((pos[i], lg[i], y[i], y[i + 1]))
    r = pd.DataFrame(recs, columns=["position", "league", "a", "b"])
    if r.empty:
        return {"n": 0}
    by = lambda col: [{col: k, "n": int(len(g)), "spearman": _r(_rho(g.a, g.b))} for k, g in r.groupby(col) if len(g) >= 100]
    return {"n": int(len(r)), "min_minutes": min_minutes, "overall_spearman": _r(_rho(r.a, r.b)),
            "by_position": sorted(by("position"), key=lambda x: -x["n"]), "by_league": sorted(by("league"), key=lambda x: -x["n"])}


def _tm_frame(df: pd.DataFrame) -> pd.DataFrame | None:
    link_p, val_p = EXTERNAL / "tm_player_link.csv", EXTERNAL / "tm_valuations.csv"
    if not (link_p.exists() and val_p.exists()):
        return None
    link = pd.read_csv(link_p, dtype={"player_id": str})[["player_id", "tm_player_id"]].drop_duplicates("player_id")
    val = pd.read_csv(val_p, parse_dates=["date"])[["tm_player_id", "date", "market_value_in_eur"]].dropna().sort_values("date")
    base = apply_aliases(link).drop_duplicates("player_id")
    f = df.merge(base, on="player_id", how="inner")
    f["t0"] = f["season"].map(_season_start)
    f["t1"] = f["t0"] + pd.DateOffset(years=1)
    out = f.copy()
    for col, tol, name in (("t0", 200, "tm0"), ("t1", 120, "tm1")):
        m = pd.merge_asof(out.sort_values(col)[["player_id", "season", col, "tm_player_id"]], val.rename(columns={"date": "vd"}),
                          left_on=col, right_on="vd", by="tm_player_id", direction="nearest", tolerance=pd.Timedelta(days=tol))
        out = out.merge(m[["player_id", "season", "market_value_in_eur"]].rename(columns={"market_value_in_eur": name}).drop_duplicates(["player_id", "season"]),
                        on=["player_id", "season"], how="left")
    return out


def _cell_rho(frame: pd.DataFrame, x: str, y: str, keys: list[str], min_n: int = 30) -> tuple[float, int]:
    rhos, ns = [], []
    for _, g in frame.groupby(keys):
        if len(g) >= min_n:
            rho = _rho(g[x], g[y])
            if not np.isnan(rho):
                rhos.append(rho); ns.append(len(g))
    return (float(np.average(rhos, weights=ns)), int(sum(ns))) if rhos else (float("nan"), 0)


def market_validation(df: pd.DataFrame) -> dict:
    f = _tm_frame(df)
    if f is None:
        return {"available": False}
    f = f[f.tm0 > 0].copy()
    f["log_tm0"] = np.log(f.tm0)
    out = {"available": True, "n": int(len(f))}
    # (1) does the performance score agree with an independent market valuation, within season and position?
    rows = []
    for name, col in (("performance_score", "performance_score"), ("adjusted_performance_score", "adjusted_performance_score"), ("fifa_overall_reference", "overall")):
        if col in f.columns:
            rho, n = _cell_rho(f, col, "log_tm0", ["season", "canonical_position"])
            rows.append({"measure": name, "spearman_vs_market_value": _r(rho), "n": n})
    out["score_vs_market"] = rows
    by_pos = []
    for pos, g in f.groupby("canonical_position"):
        rho, n = _cell_rho(g, "performance_score", "log_tm0", ["season"])
        if n >= 100:
            by_pos.append({"position": pos, "spearman": _r(rho), "n": n})
    out["score_vs_market_by_position"] = sorted(by_pos, key=lambda x: -x["n"])
    # (2) fair value vs market value
    g = f[(f.fair_value_eur > 0) & (f.value_eur > 0)]
    ratio = g.fair_value_eur / g.tm0
    out["fair_value_vs_market"] = {
        "n": int(len(g)), "spearman_fair_value": _r(_rho(g.fair_value_eur, g.tm0)), "spearman_fifa_value": _r(_rho(g.value_eur, g.tm0)),
        "median_fair_to_market_ratio": _r(ratio.median(), 2),
        "median_abs_pct_error_fair": _r(((g.fair_value_eur - g.tm0).abs() / g.tm0).median() * 100, 1),
        "median_abs_pct_error_fifa": _r(((g.value_eur - g.tm0).abs() / g.tm0).median() * 100, 1)}
    # (3) FORWARD test: do players the model calls undervalued gain market value over the next 12 months?
    h = f[(f.tm1 > 0) & f.value_gap_pct.notna()].copy()
    h["fwd_pct"] = (h.tm1 / h.tm0 - 1) * 100
    h["age_band"] = pd.cut(pd.to_numeric(h.age_fifa, errors="coerce"), [0, 21, 25, 29, 99], labels=["u22", "22-25", "26-29", "30+"])
    h["bucket"] = pd.cut(h.value_gap_pct, [-1e9, -20, 20, 1e9], labels=["Overvalued (gap < -20%)", "Fairly valued", "Undervalued (gap > +20%)"])
    buckets = [{"bucket": str(k), "n": int(len(g)), "median_12m_change_pct": _r(g.fwd_pct.median(), 1), "mean_12m_change_pct": _r(g.fwd_pct.clip(-90, 300).mean(), 1)}
               for k, g in h.groupby("bucket", observed=True)]
    rho_age, n_age = _cell_rho(h, "value_gap_pct", "fwd_pct", ["season", "age_band"], 50)
    reliable = h[h.sample_reliability_tier.isin(["Moderate", "High"])] if "sample_reliability_tier" in h.columns else h.iloc[0:0]
    rho_rel, n_rel = _cell_rho(reliable, "value_gap_pct", "fwd_pct", ["season", "age_band"], 50) if len(reliable) else (float("nan"), 0)
    per_season = [_rho(g.value_gap_pct, g.fwd_pct) for _, g in h.groupby("season") if len(g) >= 100]
    out["value_gap_forward"] = {
        "n": int(len(h)), "buckets": buckets, "spearman_within_season_and_age_band": _r(rho_age), "n_cells": n_age,
        "spearman_reliable_samples_only": _r(rho_rel), "seasons_with_positive_relationship": f"{sum(r > 0 for r in per_season)}/{len(per_season)}"}
    return out


# ------------------------------------------------------------------ role fit
NATURAL_POSITIONS = {  # roles with no single position in ROLE_ARCHETYPES
    "Attacking Fullback": ["LB", "RB", "LWB", "RWB"], "Defensive Fullback": ["LB", "RB", "LWB", "RWB"],
    "Inside Forward": ["LW", "RW"], "Wide Playmaker": ["LW", "RW", "CAM"],
}


def role_fit_validation(df: pd.DataFrame) -> list[dict]:
    """Does role fit predict next-season minutes, among players whose natural position fits the role?"""
    from src.features.role_archetypes import ROLE_ARCHETYPES
    from src.validation.backtest_role_fit import validate_role_fit_against_future_minutes as v
    out = []
    for role, cfg in ROLE_ARCHETYPES.items():
        positions = NATURAL_POSITIONS.get(role) or [cfg.get("position_group")]
        try:
            res = v(df[df["canonical_position"].isin(positions)], role)
            res["tested_positions"] = positions
        except Exception as exc:  # keep the report complete even if one role cannot be scored
            res = {"role": role, "note": f"not computed: {type(exc).__name__}"}
        out.append(res)
    return out


def sensitivity_validation(df: pd.DataFrame, trials: int = 30) -> dict:
    from src.features.role_archetypes import ROLE_ARCHETYPES
    from src.validation.sensitivity import performance_score_sensitivity as ps, role_fit_sensitivity as rs
    pos = [ps(df, p, n_trials=trials) for p in POSITION_COMPONENT_WEIGHTS if (df.canonical_position == p).sum() > 50]
    roles = [rs(df, r, n_trials=max(10, trials // 2)) for r in ROLE_ARCHETYPES]
    keep = lambda rows, key: [{key: x[key], "mean_rank_correlation": x["mean_rank_correlation"], "min_rank_correlation": x["min_rank_correlation"], "top1_stability_rate": x["top1_stability_rate"]} for x in rows]
    return {"performance_score_by_position": keep(pos, "position"), "role_fit_by_role": keep(roles, "role"),
            "worst_rank_correlation": _r(min(x["min_rank_correlation"] for x in pos + roles))}


def risk_validation(df: pd.DataFrame) -> dict:
    res = backtest_risk_tiers(df)
    tbl = res.get("summary_by_risk_tier")
    if isinstance(tbl, pd.DataFrame):
        res["summary_by_risk_tier"] = [{"tier": str(k), **{c: _r(v, 2) for c, v in row.items()}} for k, row in tbl.iterrows()]
    return res


# ------------------------------------------------------------------- registry
STATUS_LABELS = {"validated": "Validated", "partially_validated": "Partially validated",
                 "exploratory": "Exploratory", "not_validated": "Not validated"}
RULES = {
    "performance_score": "3 checks: year-over-year rank stability >= 0.50, league-adjusted agreement with market value >= 0.35, worst-case weight-sensitivity rank correlation >= 0.95. 2 or 3 pass = partially validated (weights are expert-set and there is no external ground truth, so it is never rated fully validated); fewer = exploratory.",
    "adjusted_performance_score": "Validated if league adjustment raises agreement with market value by >= 0.05 versus the raw score.",
    "expected_performance_12m": "Validated if the out-of-time blend beats both 'no change' and 'historical mean' baselines on MAE, and beats 'no change' by >= 5%.",
    "potential_24m": "Partially validated if the 2-season walk-forward correlation with actual >= 0.50.",
    "development_potential": "Exploratory if it is not an unbiased forecast (|mean bias| > 3 points or worse MAE than 'no change').",
    "breakout_probability": "Out-of-time AUC >= 0.65 and calibration gap <= 5 points = validated; AUC >= 0.58 = partially validated; else exploratory.",
    "decline_probability": "Same rule as breakout probability.",
    "recruitment_risk": "Partially validated as a volatility indicator only -- never claimed to predict decline.",
    "value_gap": "Forward test against Transfermarkt: validated if rank correlation >= 0.10 and positive in >= 6 seasons; partially validated if >= 0.05; else not validated.",
    "age_outlook": "Partially validated if an age curve learned only from earlier seasons beats 'no change' on next-season error by >= 5%; otherwise exploratory.",
    "role_fit": "Partially validated if the mean partial correlation with next-season minutes (controlling for performance) >= 0.15; else exploratory.",
}


def _item(key, label, status, summary, evidence, limits=""):
    return {"key": key, "label": label, "status": status, "status_label": STATUS_LABELS[status], "summary": summary,
            "evidence": evidence, "limits": limits, "rule": RULES.get(key, "")}


def build_registry(S: dict) -> list[dict]:
    items = []
    stab, mkt, sens = S["score_stability"], S.get("market", {}), S["sensitivity"]
    sv = {x["measure"]: x["spearman_vs_market_value"] for x in mkt.get("score_vs_market", [])}
    adj, raw = sv.get("adjusted_performance_score"), sv.get("performance_score")
    passed = sum([(stab.get("overall_spearman") or 0) >= 0.5, (adj or 0) >= 0.35, (sens["worst_rank_correlation"] or 0) >= 0.95])
    weak = [f"{x['position']} (year-over-year stability {x['spearman']})" for x in stab.get("by_position", []) if (x["spearman"] or 1) < 0.3]
    weak += [f"{x['position']} (market agreement {x['spearman']})" for x in mkt.get("score_vs_market_by_position", []) if (x["spearman"] or 1) < 0.15]
    items.append(_item("performance_score", "Performance score", "partially_validated" if passed >= 2 else "exploratory",
        "A stable, robust ranking that agrees moderately with market judgement. Weights are expert-set, so it is a structured opinion, not a measured truth.",
        [f"Year-over-year rank stability {stab.get('overall_spearman')} (players with 900+ minutes in both seasons)",
         f"League-adjusted agreement with Transfermarkt value {adj} (FIFA overall, for reference: {sv.get('fifa_overall_reference')})",
         f"Ranking barely moves when weights change by +/-20% (worst case {sens['worst_rank_correlation']})"],
        ("Weaker for: " + ", ".join(weak)) if weak else ""))
    if adj is not None and raw is not None:
        items.append(_item("adjusted_performance_score", "League-adjusted performance", "validated" if adj - raw >= 0.05 else "exploratory",
            "Adjusting for league strength brings scores clearly closer to how the market values players.",
            [f"Agreement with market value: {raw} raw -> {adj} league-adjusted"]))
    e12 = S["expected_12m"]
    items.append(_item("expected_performance_12m", "Expected performance (12 months)",
        "validated" if e12["blend"]["mae"] < e12["naive_last"]["mae"] and e12["blend"]["mae"] < e12["history_mean"]["mae"] and e12["improvement_vs_naive_pct"] >= 5 else "exploratory",
        "A modest but real improvement over assuming no change. It pulls players toward their own average; it cannot spot a breakout before it appears in the stats.",
        [f"Error {e12['blend']['mae']} points vs {e12['naive_last']['mae']} for 'no change' ({e12['improvement_vs_naive_pct']}% better), n={e12['n']}"]))
    h2 = S["horizons"].get("2m_season") or {}
    items.append(_item("potential_24m", "Projection (24 months)", "partially_validated" if (h2.get("correlation") or 0) >= 0.5 else "exploratory",
        "Two-season-ahead projection tested with the same walk-forward method; accuracy is similar to the 12-month estimate.",
        [f"Walk-forward correlation {h2.get('correlation')}, error {h2.get('MAE')} points (n={h2.get('n')})"]))
    dp = S["development_potential"]
    biased = abs(dp["mean_bias_points"]) > 3 or dp["mae_development_potential"] > dp["mae_naive_current"]
    items.append(_item("development_potential", "Development potential", "exploratory" if biased else "partially_validated",
        "An upside ceiling (current ability + age room + FIFA potential gap), not a forecast. Read it as 'how high this could go', never as 'what to expect next season'.",
        [f"Overstates next-season performance by {dp['mean_bias_points']} points on average; error {dp['mae_development_potential']} vs {dp['mae_naive_current']} for 'no change'"]))
    ev = S["events"]
    for key, label in (("breakout", "Breakout probability"), ("decline", "Decline probability")):
        e = ev.get(key, {})
        auc, gap = e.get("auc") or 0, e.get("max_calibration_gap") or 1
        status = "validated" if auc >= 0.65 and gap <= 0.05 else "partially_validated" if auc >= 0.58 else "exploratory"
        items.append(_item(f"{key}_probability", label, status,
            "Historical rates for similar players (age band and recent direction). They separate likelier from less likely cases only modestly, so use them to rank, not as literal percentages.",
            [f"Out-of-time AUC {e.get('auc')} (0.5 = no skill); the top 20% of predictions are {e.get('top_quintile_lift')}x the base rate",
             f"Largest gap between predicted and observed rate: {round(gap * 100, 1)} points (n={ev.get('n')} transitions)"],
            "Probabilities are shown with their cohort sample size; thin cohorts are marked low-evidence."))
    tiers = {t["tier"]: t for t in S["risk"].get("summary_by_risk_tier", [])}
    items.append(_item("recruitment_risk", "Recruitment risk tier", "partially_validated",
        "Measures how uncertain a player's next season is (volatility), not whether he will decline.",
        [f"Share of players who declined next season is flat across tiers: LOW {tiers['LOW']['pct_declined']}%, MEDIUM {tiers['MEDIUM']['pct_declined']}%, HIGH {tiers['HIGH']['pct_declined']}%"] if tiers else [],
        "Do not read HIGH risk as 'likely to get worse'."))
    gv = mkt.get("value_gap_forward") or {}
    rho, pos = gv.get("spearman_within_season_and_age_band"), gv.get("seasons_with_positive_relationship", "0/0")
    npos = int(str(pos).split("/")[0]) if pos else 0
    status = "validated" if (rho or 0) >= 0.10 and npos >= 6 else "partially_validated" if (rho or 0) >= 0.05 else "not_validated"
    fv = mkt.get("fair_value_vs_market") or {}
    items.append(_item("value_gap", "Fair value and 'undervalued' signal", status,
        "Fair value tracks FIFA's own valuation closely and sits well above Transfermarkt levels. Being flagged undervalued has not been shown to predict a rise in market value.",
        [f"Forward test (n={gv.get('n')}): rank correlation between value gap and the next 12 months' market-value change = {rho}; positive in {pos} seasons",
         f"Fair value is {fv.get('median_fair_to_market_ratio')}x Transfermarkt value on the median; rank agreement {fv.get('spearman_fair_value')} (FIFA value alone: {fv.get('spearman_fifa_value')})"],
        "Treat opportunity lists as a screening aid for scouts to check, not as evidence of mispricing."))
    ac = S.get("age_curve") or {}
    if ac.get("n"):
        better = ac["improvement_pct"] >= 5
        items.append(_item("age_outlook", "Squad ageing projection", "partially_validated" if better else "exploratory",
            "Players improve until about 22 and decline steadily after 28 on average, but at the level of one player the noise is far larger than that trend.",
            [f"Out-of-time error {ac['mae_age_curve']} points vs {ac['mae_no_change']} for assuming no change ({ac['improvement_pct']}% difference, n={ac['n']:,})"],
            "The Squad Audit age profile (how old the squad will be) is arithmetic and reliable; the performance projection is shown as indicative only."))
    pcs = [r.get("partial_correlation_role_fit_vs_future_minutes_controlling_for_performance") for r in S["role_fit"]]
    pcs = [x for x in pcs if x is not None]
    mean_pc = float(np.mean(pcs)) if pcs else 0.0
    items.append(_item("role_fit", "Role fit", "partially_validated" if mean_pc >= 0.15 else "exploratory",
        "Describes how closely a player's profile matches a role template. It has not been shown to predict how much a player plays once his overall level is accounted for.",
        [f"Mean partial correlation with next-season minutes (controlling for performance): {round(mean_pc, 3)} across {len(pcs)} roles"]))
    return items


def build_report() -> dict:
    t0 = time.time()
    df = apply_aliases(pd.read_csv(PROCESSED, low_memory=False))
    S = {"expected_12m": backtest_expected_12m(df), "horizons": backtest_advanced_horizons(df),
         "development_potential": backtest_development_potential(df), "events": backtest_events(df),
         "score_stability": score_stability(df), "market": market_validation(df), "risk": risk_validation(df),
         "role_fit": role_fit_validation(df), "sensitivity": sensitivity_validation(df), "age_curve": age_curve_backtest(df)}
    registry = build_registry(S)
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "runtime_seconds": round(time.time() - t0, 1),
            "rows": int(len(df)), "players": int(df["player_id"].nunique()), "seasons": sorted(int(s) for s in df["season"].unique()),
            "market_benchmark": "Transfermarkt snapshot" if S["market"].get("available") else "not available",
            "fingerprint": hashlib.sha1(f"{len(df)}-{df['player_id'].nunique()}-{df['season'].max()}".encode()).hexdigest()[:10]}
    clean = lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o)
    return {"meta": meta, "registry": registry, "status_counts": {k: sum(i["status"] == k for i in registry) for k in STATUS_LABELS},
            "sections": json.loads(json.dumps(S, default=clean))}


def main() -> None:
    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"validation report written to {REPORT_PATH} in {report['meta']['runtime_seconds']}s")
    for i in report["registry"]:
        print(f"  {i['status_label']:20} {i['label']}")


if __name__ == "__main__":
    main()
