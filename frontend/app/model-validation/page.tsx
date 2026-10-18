"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui";
import { StatusChip } from "@/components/ValidationBadge";

const n = (v: any, d = 2) => (v == null ? "—" : Number(v).toFixed(d));
const pct = (v: any, d = 0) => (v == null ? "—" : `${(Number(v) * 100).toFixed(d)}%`);

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead><tr className="text-faint text-left border-b border-border">{head.map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border last:border-0">{r.map((c, j) => <td key={j} className={`px-3 py-2 ${j === 0 ? "text-ink" : "text-muted tabular"}`}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-panel rounded-sm mt-5">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-sm text-ink font-medium">{title}</h2>
        {note && <p className="text-2xs text-faint mt-1 max-w-3xl">{note}</p>}
      </div>
      <div className="pb-2">{children}</div>
    </section>
  );
}

export default function ModelValidationPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getModelValidation().then(setData).catch((e: any) => setError(e.message || "Could not load the validation report.")).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState label="Loading validation report" />;
  if (error) return <ErrorState message={error} />;
  if (!data?.available) {
    return (
      <div className="max-w-[800px]">
        <h1 className="text-lg text-ink font-medium">Model validation</h1>
        <p className="text-sm text-muted mt-2">{data?.reason || "No validation report yet."}</p>
      </div>
    );
  }

  const { meta, registry, status_counts: counts, sections: S } = data;
  const e12 = S.expected_12m, ev = S.events, gv = S.market?.value_gap_forward, stab = S.score_stability;
  const mktPos: Record<string, number> = Object.fromEntries((S.market?.score_vs_market_by_position || []).map((x: any) => [x.position, x.spearman]));
  const sensPos: Record<string, number> = Object.fromEntries((S.sensitivity?.performance_score_by_position || []).map((x: any) => [x.position, x.mean_rank_correlation]));

  return (
    <div className="max-w-[1100px]">
      <h1 className="text-lg text-ink font-medium">Model validation</h1>
      <p className="text-xs text-muted mt-1 max-w-3xl">
        Every model output in ScoutIQ was tested against what actually happened next, using this dataset's own history{meta.market_benchmark !== "not available" ? " and Transfermarkt as an independent benchmark" : ""}.
        The status of each output comes from the measured results below, not from opinion.
      </p>
      <p className="text-2xs text-faint mt-1">
        Generated {meta.generated_at.slice(0, 10)} · {meta.rows.toLocaleString()} player-seasons · {meta.players.toLocaleString()} players · {meta.seasons.length} seasons · regenerate with <code>python -m src.validation.report</code>
      </p>

      <div className="flex flex-wrap gap-3 mt-4">
        {Object.entries(counts).map(([k, v]) => (
          <div key={k} className="border border-border bg-panel rounded-sm px-3 py-2">
            <StatusChip status={k} label={k.replace("_", " ").replace("_", " ")} />
            <div className="text-lg tabular text-ink font-medium mt-1">{String(v)}</div>
          </div>
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {registry.map((i: any) => (
          <article key={i.key} className="border border-border bg-panel rounded-sm p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm text-ink font-medium">{i.label}</h3>
              <StatusChip status={i.status} label={i.status_label} />
            </div>
            <p className="text-xs text-muted mt-2">{i.summary}</p>
            <ul className="mt-2 space-y-1">{i.evidence.map((e: string, k: number) => <li key={k} className="text-2xs text-faint">• {e}</li>)}</ul>
            {i.limits && <p className="text-2xs text-riskmed mt-2">{i.limits}</p>}
            <details className="mt-2"><summary className="text-2xs text-faint cursor-pointer">How this status is decided</summary><p className="text-2xs text-faint mt-1">{i.rule}</p></details>
          </article>
        ))}
      </div>

      <Block title="Expected performance next season" note={`Walk-forward test: hide each player's latest season, predict it from earlier ones (n=${e12.n}). Lower error is better.`}>
        <Table head={["Method", "Average error (points)", "Correlation with actual"]} rows={[
          ["Recency / mean blend (used)", n(e12.blend.mae), n(e12.blend.correlation)],
          ["Assume no change", n(e12.naive_last.mae), n(e12.naive_last.correlation)],
          ["Player's own historical mean", n(e12.history_mean.mae), n(e12.history_mean.correlation)]]} />
      </Block>

      {["breakout", "decline"].map((k) => ev[k] && (
        <Block key={k} title={`${k === "breakout" ? "Breakout" : "Decline"} probability: predicted vs observed`}
          note={`Out-of-time: rates learned only from earlier seasons predict each later season (n=${ev.n}). AUC ${n(ev[k].auc)} (0.5 = no skill); the top 20% of predictions are ${n(ev[k].top_quintile_lift)}x the average rate.`}>
          <Table head={["Predicted group (low to high)", "Players", "Mean predicted", "Actually happened"]} rows={ev[k].calibration.map((c: any) => [`Group ${c.bin}`, c.n.toLocaleString(), pct(c.mean_predicted), pct(c.observed_rate)])} />
        </Block>
      ))}

      {gv && (
        <Block title="Does 'undervalued' predict a rise in market value?"
          note={`Forward test (n=${gv.n.toLocaleString()}): players grouped by the model's value gap, then compared with their Transfermarkt value 12 months later. Rank correlation within season and age band: ${n(gv.spearman_within_season_and_age_band, 3)} (0 = no relationship), positive in ${gv.seasons_with_positive_relationship} seasons.`}>
          <Table head={["Model said", "Players", "Median 12-month change", "Average 12-month change"]} rows={gv.buckets.map((b: any) => [b.bucket, b.n.toLocaleString(), `${n(b.median_12m_change_pct, 1)}%`, `${n(b.mean_12m_change_pct, 1)}%`])} />
        </Block>
      )}

      <Block title="Performance score reliability by position"
        note="Year-over-year stability: do players keep their rank among positional peers next season? Market agreement: does the score rank players like Transfermarkt values do? Weight stability: does the ranking survive +/-20% changes to the weights?">
        <Table head={["Position", "Stability", "Market agreement", "Weight stability"]} rows={(stab.by_position || []).map((x: any) => [x.position, n(x.spearman), n(mktPos[x.position]), n(sensPos[x.position], 3)])} />
      </Block>

      {S.risk?.summary_by_risk_tier && (
        <Block title="Recruitment risk tier: what happened next" note="The share declining is flat across tiers: the tier measures uncertainty, not likelihood of decline.">
          <Table head={["Tier", "Transitions", "Average change", "Declined"]} rows={S.risk.summary_by_risk_tier.map((t: any) => [t.tier, Number(t.n).toLocaleString(), n(t.mean_performance_delta), `${n(t.pct_declined, 1)}%`])} />
        </Block>
      )}
    </div>
  );
}
