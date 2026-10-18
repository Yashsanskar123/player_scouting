"use client";

import { useEffect, useState } from "react";
import { api, formatEur } from "@/lib/api";
import ValidationBadge from "@/components/ValidationBadge";

const n = (v: any, d = 1) => (v == null ? "—" : Number(v).toFixed(d));

function Bar({ value, tone }: { value: number | null; tone?: string }) {
  const w = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="h-1.5 bg-panelraised rounded-sm w-full">
      <div className={`h-1.5 rounded-sm ${tone || "bg-accent"}`} style={{ width: `${w}%` }} />
    </div>
  );
}

/** "Why this score": every breakdown adds back up to the number shown elsewhere on the page. */
export default function ExplainPanel({ playerId, season }: { playerId: string; season?: number | null }) {
  const [ex, setEx] = useState<any>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setEx(null);
    api.explainPlayer(playerId, season).then((d: any) => alive && setEx(d)).catch(() => alive && setEx(null));
    return () => { alive = false; };
  }, [playerId, season]);

  if (!ex || !ex.performance?.available) return null;
  const p = ex.performance, r = ex.risk, pot = ex.potential, val = ex.value;

  return (
    <section className="analytics-panel">
      <div className="px-5 pt-5 pb-3 border-b border-border">
        <h2 className="text-sm text-ink font-medium">Why these numbers</h2>
        <p className="text-2xs text-faint mt-1">Each breakdown below adds back up to the score shown for this player.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2">
        <div className="p-5 border-b xl:border-r border-border">
          <div className="flex items-center justify-between">
            <div className="text-xs text-ink font-medium">Performance score {n(p.score)} <span className="text-faint font-normal">({p.position})</span></div>
            <ValidationBadge modelKey="performance_score" />
          </div>
          <ul className="mt-3 space-y-3">
            {p.components.map((c: any) => (
              <li key={c.key}>
                <button className="w-full text-left" onClick={() => setOpen(open === c.key ? null : c.key)} aria-expanded={open === c.key}>
                  <div className="flex justify-between text-xs">
                    <span className="text-ink">{c.label} <span className="text-faint">· score {n(c.value, 0)} × weight {Math.round(c.effective_weight * 100)}%</span></span>
                    <span className="text-muted tabular">+{n(c.contribution)} pts</span>
                  </div>
                  <div className="mt-1"><Bar value={c.value} tone={c.value < 50 ? "bg-riskmed" : undefined} /></div>
                </button>
                {open === c.key && c.evidence.length > 0 && (
                  <ul className="mt-2 ml-2 text-2xs text-muted space-y-0.5">
                    {c.evidence.map((e: any) => <li key={e.label}>{e.label}: {n(e.percentile, 0)}th percentile among {p.position}s</li>)}
                  </ul>
                )}
              </li>
            ))}
          </ul>
          {p.missing_components.length > 0 && <p className="text-2xs text-faint mt-3">Not scored (no data): {p.missing_components.join(", ")}. Weights are rescaled over the rest.</p>}
          <div className="mt-4 text-xs text-muted space-y-1">
            {p.versus_peers && <div>{n(p.versus_peers.difference)} points {p.versus_peers.difference >= 0 ? "above" : "below"} the average {p.position} ({n(p.versus_peers.position_average)}); better than {n(p.versus_peers.percentile, 0)}% of {p.versus_peers.n} peers.</div>}
            {p.league?.adjusted_score != null && <div>League adjustment ({p.league.league_name}): {p.league.adjustment_points >= 0 ? "+" : ""}{n(p.league.adjustment_points, 1)} → adjusted score {n(p.league.adjusted_score)}.</div>}
            {p.strengths.length > 0 && <div>Strongest areas: {p.strengths.join(", ")}.</div>}
            {p.weak_spots.length > 0 && <div>Weakest areas: {p.weak_spots.join(", ")}.</div>}
          </div>
        </div>

        <div className="p-5 border-b border-border space-y-6">
          {r?.available && (
            <div>
              <div className="flex items-center justify-between">
                <div className="text-xs text-ink font-medium">Recruitment risk {n(r.score)} · {r.tier}</div>
                <ValidationBadge modelKey="recruitment_risk" />
              </div>
              <ul className="mt-2 space-y-1">
                {r.components.map((c: any) => (
                  <li key={c.key} className="flex justify-between text-xs text-muted"><span>{c.label}</span><span className="tabular">{n(c.contribution)} pts</span></li>
                ))}
              </ul>
              <p className="text-2xs text-faint mt-2">{r.meaning}</p>
            </div>
          )}
          {pot?.available && (
            <div>
              <div className="flex items-center justify-between">
                <div className="text-xs text-ink font-medium">Development potential {n(pot.development_potential)}</div>
                <ValidationBadge modelKey="development_potential" />
              </div>
              <ul className="mt-2 space-y-1">
                {pot.components.map((c: any) => (
                  <li key={c.label} className="flex justify-between text-xs text-muted"><span>{c.label}</span><span className="tabular">{n(c.points)}</span></li>
                ))}
              </ul>
              <p className="text-2xs text-faint mt-2">{pot.note}</p>
              <div className="text-xs text-muted mt-2 flex items-center gap-2">
                Expected next season: {n(pot.expected_12m)} <ValidationBadge modelKey="expected_performance_12m" />
              </div>
              {pot.breakout_probability != null && (
                <div className="text-xs text-muted mt-1 flex items-center gap-2">
                  Breakout {n(pot.breakout_probability, 0)}% · decline {n(pot.decline_probability, 0)}% (similar players, n={pot.cohort_sample}) <ValidationBadge modelKey="breakout_probability" />
                </div>
              )}
            </div>
          )}
          {val?.available && (
            <div>
              <div className="flex items-center justify-between">
                <div className="text-xs text-ink font-medium">Value: {formatEur(val.market_value_eur)} market vs {formatEur(val.fair_value_eur)} fair</div>
                <ValidationBadge modelKey="value_gap" />
              </div>
              {val.comparable_players && (
                <p className="text-xs text-muted mt-2">Comparable players (n={val.comparable_players.n}) are valued {formatEur(val.comparable_players.low_eur)}–{formatEur(val.comparable_players.high_eur)}, median {formatEur(val.comparable_players.median_value_eur)}.</p>
              )}
              <p className="text-2xs text-faint mt-2">{val.how}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
