"""Extra Squad Audit views: wage vs performance, minutes dependency, starter vs backup, and an ageing outlook.

All figures come from the roster's own rows. Wages are FIFA's estimates. The ageing curve is the average
year-to-year change in performance score by age, learned from this dataset's own consecutive seasons, and it
is back-tested out of time (see `age_curve_backtest`) so its accuracy is reported next to the projection.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_MINUTES = 900          # both seasons must have this many minutes to count toward the ageing curve
MIN_AGE, MAX_AGE = 17, 38
POINTS_PER_AGE_MIN = 40    # ages with fewer observations borrow from their neighbours
DEPENDENCY_SHARE = 0.75    # a starter with 75%+ of his position's minutes...
DEPENDENCY_DROP = 10.0     # ...and a backup 10+ points worse is a single point of failure


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(frame[col], errors="coerce") if col in frame.columns else pd.Series(np.nan, index=frame.index)


def _transitions(df: pd.DataFrame) -> pd.DataFrame:
    """(age, season, change in performance score) for players with real minutes in two consecutive rows."""
    rows = []
    for _, g in df.sort_values("season").groupby("player_id"):
        perf, age, mins, seas = _num(g, "performance_score").to_numpy(), _num(g, "age_fifa").to_numpy(), _num(g, "playing_time_min").to_numpy(), g["season"].to_numpy()
        for i in range(len(g) - 1):
            if mins[i] >= MIN_MINUTES and mins[i + 1] >= MIN_MINUTES and not (np.isnan(perf[i]) or np.isnan(perf[i + 1]) or np.isnan(age[i])):
                rows.append((int(seas[i]), int(np.clip(age[i], MIN_AGE, MAX_AGE)), float(perf[i + 1] - perf[i])))
    return pd.DataFrame(rows, columns=["season", "age", "delta"])


def _curve_from(trans: pd.DataFrame) -> dict[int, float]:
    """Mean change by age, smoothed: thin ages are blended with their neighbours (weighted by sample size)."""
    by = trans.groupby("age")["delta"].agg(["mean", "size"]).reindex(range(MIN_AGE, MAX_AGE + 1))
    mean, n = by["mean"].fillna(0.0), by["size"].fillna(0.0)
    curve = {}
    for age in range(MIN_AGE, MAX_AGE + 1):
        lo, hi = age, age
        while n.loc[lo:hi].sum() < POINTS_PER_AGE_MIN and (lo > MIN_AGE or hi < MAX_AGE):
            lo, hi = max(MIN_AGE, lo - 1), min(MAX_AGE, hi + 1)
        w = n.loc[lo:hi]
        curve[age] = float((mean.loc[lo:hi] * w).sum() / w.sum()) if w.sum() > 0 else 0.0
    return curve


def empirical_age_curve(df: pd.DataFrame) -> dict[int, float]:
    t = _transitions(df)
    return _curve_from(t) if len(t) >= 200 else {a: 0.0 for a in range(MIN_AGE, MAX_AGE + 1)}


def age_curve_backtest(df: pd.DataFrame) -> dict:
    """Out of time: a curve learned only from earlier seasons predicts each later season's change. Compared with 'no change'."""
    t = _transitions(df)
    errs_curve, errs_naive = [], []
    for s in sorted(t["season"].unique())[2:]:
        train, test = t[t.season < s], t[t.season == s]
        if len(train) < 200 or test.empty:
            continue
        curve = _curve_from(train)
        errs_curve += list((test["delta"] - test["age"].map(curve)).abs())
        errs_naive += list(test["delta"].abs())
    if not errs_curve:
        return {"n": 0}
    mc, mn = float(np.mean(errs_curve)), float(np.mean(errs_naive))
    return {"n": len(errs_curve), "mae_age_curve": round(mc, 2), "mae_no_change": round(mn, 2), "improvement_pct": round((1 - mc / mn) * 100, 1)}


def age_outlook(roster: pd.DataFrame, curve: dict[int, float], backtest: dict | None = None, horizons=(1, 2, 3)) -> dict:
    """If nobody joins or leaves.

    The AGE PROFILE is arithmetic (everyone is a year older each season) and can be relied on. The PERFORMANCE
    PROJECTION uses the average ageing curve; in out-of-time testing it was no better than assuming no change,
    so it is returned with that evidence and the UI treats it as secondary.
    """
    age, perf = _num(roster, "age_fifa"), _num(roster, "performance_score")
    have_age = age.notna()
    if not have_age.any():
        return {"available": False}
    ages = age[have_age].to_numpy()
    pos = roster.loc[have_age, "canonical_position"] if "canonical_position" in roster.columns else pd.Series("", index=roster.index[have_age])
    profile = [{"years_ahead": 0, "average_age": round(float(ages.mean()), 1), "aged_30_plus": int((ages >= 30).sum()), "aged_30_plus_pct": round(float((ages >= 30).mean()) * 100, 0)}]
    for h in horizons:
        older = ages + h
        by_pos = pos[(older >= 30)].value_counts().to_dict()
        profile.append({"years_ahead": h, "average_age": round(float(older.mean()), 1), "aged_30_plus": int((older >= 30).sum()),
                        "aged_30_plus_pct": round(float((older >= 30).mean()) * 100, 0), "aged_30_plus_by_position": by_pos})
    out = {"available": True, "age_profile": profile}
    ok = have_age & perf.notna()
    if ok.any():
        base, a = perf[ok].to_numpy(), age[ok].to_numpy()
        steps = []
        for h in horizons:
            proj = np.array([float(np.clip(b + sum(curve[int(np.clip(x + k, MIN_AGE, MAX_AGE))] for k in range(h)), 0, 100)) for b, x in zip(base, a)])
            steps.append({"years_ahead": h, "average_performance": round(float(proj.mean()), 1), "change_vs_now": round(float(proj.mean() - base.mean()), 1)})
        beats = bool(backtest and backtest.get("n") and backtest["improvement_pct"] >= 5)
        out["performance_projection"] = {"average_performance_now": round(float(base.mean()), 1), "steps": steps, "backtest": backtest,
                                         "status": "validated" if beats else "not_better_than_no_change",
                                         "note": "Average ageing path from this data. In out-of-time testing it did not beat assuming no change, so treat it as indicative only." if not beats else "Beat 'no change' in out-of-time testing."}
    return out


def wage_efficiency(roster: pd.DataFrame) -> dict:
    wage, perf = _num(roster, "wage_eur"), _num(roster, "performance_score")
    if not wage.notna().any() or wage.sum() <= 0:
        return {"available": False}
    total = float(wage.sum())
    groups = []
    if "broad_position_group" in roster.columns:
        for name, g in roster.groupby("broad_position_group"):
            gw = float(_num(g, "wage_eur").sum())
            groups.append({"group": str(name), "players": int(len(g)), "wage_eur": gw, "wage_share_pct": round(gw / total * 100, 1), "average_performance": round(float(_num(g, "performance_score").mean()), 1)})
    median_perf, median_wage = float(perf.median()), float(wage.median())
    cols = [c for c in ("short_name", "canonical_position", "age_fifa", "wage_eur", "performance_score") if c in roster.columns]
    paid = roster[wage.notna() & perf.notna()]
    overpaid = paid[(_num(paid, "wage_eur") >= _num(paid, "wage_eur").quantile(0.75)) & (_num(paid, "performance_score") < median_perf)].sort_values("wage_eur", ascending=False)
    bargains = paid[(_num(paid, "wage_eur") <= median_wage) & (_num(paid, "performance_score") >= _num(paid, "performance_score").quantile(0.75))].sort_values("performance_score", ascending=False)
    rec = lambda f: [{c: (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)) for c, v in row.items()} for row in f[cols].head(5).to_dict("records")]
    return {"available": True, "total_wage_eur": total, "period": "week", "annual_estimate_eur": total * 52, "median_performance": round(median_perf, 1), "by_group": sorted(groups, key=lambda x: -x["wage_eur"]),
            "high_pay_below_median_performance": rec(overpaid), "low_pay_high_performance": rec(bargains),
            "note": "FIFA lists wages per week; these are estimates, not contract figures."}


def position_dependency(roster: pd.DataFrame) -> dict:
    """Who carries each position: his share of the minutes there, and how far the best alternative is behind him."""
    mins, perf = _num(roster, "playing_time_min"), _num(roster, "performance_score")
    if not mins.notna().any() or "canonical_position" not in roster.columns:
        return {"available": False}
    total = float(mins.sum())
    top3 = float(mins.nlargest(3).sum() / total * 100) if total > 0 else None
    rows = []
    for pos, g in roster.assign(_m=mins, _p=perf).groupby("canonical_position"):
        g = g.sort_values("_m", ascending=False)
        gm = float(g["_m"].sum())
        if gm <= 0:
            continue
        starter = g.iloc[0]
        others = g.iloc[1:]
        backup = others.sort_values("_p", ascending=False).iloc[0] if len(others) and others["_p"].notna().any() else None
        share = float(starter["_m"] / gm)
        drop = float(starter["_p"] - backup["_p"]) if backup is not None and pd.notna(starter["_p"]) and pd.notna(backup["_p"]) else None
        rows.append({"position": pos, "players": int(len(g)), "starter": starter.get("short_name"), "starter_minutes_share_pct": round(share * 100, 0),
                     "starter_performance": None if pd.isna(starter["_p"]) else round(float(starter["_p"]), 1),
                     "backup": None if backup is None else backup.get("short_name"), "backup_performance": None if backup is None or pd.isna(backup["_p"]) else round(float(backup["_p"]), 1),
                     "starter_to_backup_drop": None if drop is None else round(drop, 1),
                     "no_backup_listed": backup is None,
                     "single_point_of_failure": bool(share >= DEPENDENCY_SHARE and drop is not None and drop >= DEPENDENCY_DROP)})
    rows.sort(key=lambda r: (not r["single_point_of_failure"], r["no_backup_listed"], -(r["starter_to_backup_drop"] or 0)))
    return {"available": True, "top3_minutes_share_pct": None if top3 is None else round(top3, 0), "positions": rows}


_curve_cache: dict = {"key": None, "curve": None, "backtest": None}


def squad_insights(roster: pd.DataFrame, all_seasons: pd.DataFrame) -> dict:
    """Every view independently failure-safe: one missing column never removes the others."""
    key = (id(all_seasons), len(all_seasons))
    if _curve_cache["key"] != key:
        _curve_cache.update(key=key, curve=empirical_age_curve(all_seasons), backtest=age_curve_backtest(all_seasons))
    out = {}
    for name, fn in (("wage_efficiency", lambda: wage_efficiency(roster)), ("position_dependency", lambda: position_dependency(roster)),
                     ("age_outlook", lambda: {**age_outlook(roster, _curve_cache["curve"], _curve_cache["backtest"]),
                                             "assumption": "Nobody joins or leaves."})):
        try:
            out[name] = fn()
        except Exception:
            out[name] = {"available": False}
    return out
