"use client";

import { formatEur } from "@/lib/api";
import { StatusChip } from "@/components/ValidationBadge";

const n = (v: any, d = 1) => (v == null ? "—" : Number(v).toFixed(d));
const th = "px-3 py-2 font-normal text-left";

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-panel rounded-sm mt-4">
      <div className="px-4 pt-4 pb-2">
        <h3 className="text-sm text-ink font-medium">{title}</h3>
        {note && <p className="text-2xs text-faint mt-1 max-w-3xl">{note}</p>}
      </div>
      <div className="pb-2 overflow-x-auto">{children}</div>
    </section>
  );
}

/** Starter vs backup, wage vs performance and age outlook for an audited squad. Renders nothing without insights. */
export default function SquadInsights({ insights }: { insights?: any }) {
  if (!insights || Object.keys(insights).length === 0) return null;
  const dep = insights.position_dependency, wage = insights.wage_efficiency, age = insights.age_outlook;

  return (
    <div className="mb-6">
      <h2 className="text-sm text-ink font-medium">Squad insights</h2>

      {dep?.available && (
        <Block title="Starters and backups" note={`The top three players supply ${dep.top3_minutes_share_pct}% of the squad's minutes. "Drop" is how many performance points the best alternative at that position is behind the starter.`}>
          <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border">{["Position", "Starter", "Minutes share", "Best backup", "Drop", ""].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>{dep.positions.map((p: any) => (
              <tr key={p.position} className="border-b border-border last:border-0">
                <td className="px-3 py-2 text-ink">{p.position}</td><td className="px-3 py-2 text-muted">{p.starter} <span className="text-faint">{n(p.starter_performance, 0)}</span></td>
                <td className="px-3 py-2 text-muted tabular">{p.starter_minutes_share_pct}%</td>
                <td className="px-3 py-2 text-muted">{p.backup ? <>{p.backup} <span className="text-faint">{n(p.backup_performance, 0)}</span></> : "—"}</td>
                <td className={`px-3 py-2 tabular ${p.starter_to_backup_drop != null && p.starter_to_backup_drop >= 10 ? "text-riskmed" : "text-muted"}`}>{p.starter_to_backup_drop == null ? "—" : p.starter_to_backup_drop < 0 ? `backup +${Math.abs(p.starter_to_backup_drop)}` : n(p.starter_to_backup_drop)}</td>
                <td className="px-3 py-2">
                  {p.single_point_of_failure && <StatusChip status="not_validated" label="Single point of failure" />}
                  {p.no_backup_listed && <StatusChip status="partially_validated" label="No backup at this position" />}
                </td>
              </tr>))}</tbody></table>
        </Block>
      )}

      {wage?.available && (
        <Block title="Wages and performance" note={`${wage.note} Weekly bill ${formatEur(wage.total_wage_eur)} (about ${formatEur(wage.annual_estimate_eur)} a year).`}>
          <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border">{["Position group", "Players", "Weekly wage", "Share of wages", "Average performance"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>{wage.by_group.map((g: any) => (
              <tr key={g.group} className="border-b border-border last:border-0"><td className="px-3 py-2 text-ink">{g.group}</td><td className="px-3 py-2 text-muted tabular">{g.players}</td>
                <td className="px-3 py-2 text-muted tabular">{formatEur(g.wage_eur)}</td><td className="px-3 py-2 text-muted tabular">{g.wage_share_pct}%</td><td className="px-3 py-2 text-muted tabular">{n(g.average_performance)}</td></tr>))}</tbody></table>
          <div className="grid md:grid-cols-2 gap-4 px-4 pt-3 pb-1 text-xs">
            {[["High pay, below-median performance", wage.high_pay_below_median_performance], ["Low pay, top-quartile performance", wage.low_pay_high_performance]].map(([title, list]: any) => (
              <div key={title}><div className="text-2xs text-faint mb-1">{title}</div>
                {list.length === 0 ? <div className="text-faint">None</div> : <ul className="space-y-1">{list.map((p: any) => <li key={p.short_name} className="flex justify-between text-muted"><span className="text-ink">{p.short_name} <span className="text-faint">{p.canonical_position}</span></span><span className="tabular">{formatEur(p.wage_eur)}/wk · {n(p.performance_score, 0)}</span></li>)}</ul>}
              </div>))}
          </div>
        </Block>
      )}

      {age?.available && (
        <Block title="Age outlook" note={`${age.assumption} The age profile is simple arithmetic.`}>
          <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border">{["", "Average age", "Players aged 30+", "Which positions"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>{age.age_profile.map((p: any) => (
              <tr key={p.years_ahead} className="border-b border-border last:border-0"><td className="px-3 py-2 text-ink">{p.years_ahead === 0 ? "Now" : `In ${p.years_ahead} year${p.years_ahead > 1 ? "s" : ""}`}</td>
                <td className="px-3 py-2 text-muted tabular">{p.average_age}</td><td className="px-3 py-2 text-muted tabular">{p.aged_30_plus} ({p.aged_30_plus_pct}%)</td>
                <td className="px-3 py-2 text-faint">{p.aged_30_plus_by_position ? Object.entries(p.aged_30_plus_by_position).map(([k, v]) => `${k} ${v}`).join(", ") : "—"}</td></tr>))}</tbody></table>
          {age.performance_projection && (
            <details className="px-4 pt-2 pb-2">
              <summary className="text-2xs text-faint cursor-pointer">Projected performance (indicative only)</summary>
              <p className="text-2xs text-riskmed mt-1">{age.performance_projection.note}{age.performance_projection.backtest?.n ? ` Tested on ${age.performance_projection.backtest.n.toLocaleString()} cases: error ${age.performance_projection.backtest.mae_age_curve} points against ${age.performance_projection.backtest.mae_no_change} for assuming no change.` : ""}</p>
              <ul className="mt-1 text-xs text-muted">{age.performance_projection.steps.map((st: any) => <li key={st.years_ahead}>In {st.years_ahead} year{st.years_ahead > 1 ? "s" : ""}: average {st.average_performance} ({st.change_vs_now > 0 ? "+" : ""}{st.change_vs_now})</li>)}</ul>
            </details>
          )}
        </Block>
      )}
    </div>
  );
}
