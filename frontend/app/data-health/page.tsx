"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui";
import { StatusChip } from "@/components/ValidationBadge";

function Block({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-panel rounded-sm mt-5">
      <div className="px-4 pt-4 pb-2">
        <h2 className="text-sm text-ink font-medium">{title}</h2>
        {note && <p className="text-2xs text-faint mt-1 max-w-3xl">{note}</p>}
      </div>
      <div className="pb-2 overflow-x-auto">{children}</div>
    </section>
  );
}

const th = "px-3 py-2 font-normal text-left";
const cellTone = (v: number) => (v >= 30 ? "text-riskhigh" : v >= 10 ? "text-riskmed" : "text-muted");

export default function DataHealthPage() {
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDataHealth().then(setD).catch((e: any) => setError(e.message || "Could not load the data health report.")).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState label="Checking the data" />;
  if (error) return <ErrorState message={error} />;

  const partial = d.coverage.filter((c: any) => c.status === "partial");
  const id = d.identity;

  return (
    <div className="max-w-[1100px]">
      <h1 className="text-lg text-ink font-medium">Data health</h1>
      <p className="text-xs text-muted mt-1 max-w-3xl">What the platform's data covers, how fresh it is, and where it is thin. Nothing here changes the data; it tells you how far to trust each season.</p>
      <p className="text-sm text-ink mt-3">
        {d.rows.toLocaleString()} player-seasons · {d.players.toLocaleString()} players
        {d.quality_score?.overall_score != null && <span className="text-muted"> · overall quality score {Number(d.quality_score.overall_score).toFixed(1)} / 100</span>}
      </p>

      {partial.map((c: any) => (
        <div key={c.season} className="mt-4 border border-riskmed/50 bg-riskmed/10 rounded-sm px-4 py-3 text-xs">
          <span className="text-ink font-medium">{c.label} is a partial season.</span> <span className="text-muted">{c.note}</span>
        </div>
      ))}

      <Block title="Sources and freshness">
        <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border"><th className={th}>Source</th><th className={th}>Covers</th><th className={th}>Updated</th><th className={th}>Note</th></tr></thead>
          <tbody>{d.freshness.map((s: any) => (
            <tr key={s.source} className="border-b border-border last:border-0 align-top">
              <td className="px-3 py-2 text-ink">{s.source}</td><td className="px-3 py-2 text-muted">{s.covers}</td>
              <td className="px-3 py-2 text-muted tabular whitespace-nowrap">{s.updated || "—"} {s.stale && <StatusChip status="partially_validated" label="stale" />}</td>
              <td className="px-3 py-2 text-faint">{s.note}</td>
            </tr>))}</tbody></table>
      </Block>

      <Block title="Coverage by season" note="A season is partial when leagues that normally appear are missing, or it has under 80% of the previous season's players.">
        <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border">{["Season", "Players", "Clubs", "Leagues", "Advanced stats", "Status"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
          <tbody>{d.coverage.map((c: any) => (
            <tr key={c.season} className="border-b border-border last:border-0">
              <td className="px-3 py-2 text-ink">{c.label}</td><td className="px-3 py-2 text-muted tabular">{c.players.toLocaleString()}</td>
              <td className="px-3 py-2 text-muted tabular">{c.clubs}</td><td className="px-3 py-2 text-muted tabular">{c.leagues} of {c.expected_leagues}</td>
              <td className={`px-3 py-2 tabular ${c.advanced_limited ? "text-riskmed" : "text-muted"}`}>{c.advanced_stats_pct}%</td>
              <td className="px-3 py-2"><StatusChip status={c.status === "partial" ? "not_validated" : "validated"} label={c.status === "partial" ? `Partial · missing ${c.missing_leagues.join(", ") || "players"}` : "Complete"} /></td>
            </tr>))}</tbody></table>
      </Block>

      <Block title="Drift alerts" note="Seasons whose data looks different from the rest (much more missing data, or a clearly shifted average).">
        {d.drift_alerts.length === 0 ? <p className="px-4 pb-3 text-xs text-faint">No unusual shifts between seasons.</p> : (
          <ul className="px-4 pb-3 space-y-1.5">{d.drift_alerts.map((a: any, i: number) => <li key={i} className="text-xs text-muted"><StatusChip status="partially_validated" label={a.label} /> {a.message}</li>)}</ul>
        )}
      </Block>

      <Block title="Missing data by season (% of players)" note="Red: 30% or more missing. Amber: 10% or more.">
        <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border"><th className={th}>Season</th>{d.missingness.columns.map((c: any) => <th key={c.key} className={th}>{c.label}</th>)}</tr></thead>
          <tbody>{d.missingness.by_season.map((r: any) => (
            <tr key={r.season} className="border-b border-border last:border-0"><td className="px-3 py-2 text-ink">{r.label}</td>
              {d.missingness.columns.map((c: any) => <td key={c.key} className={`px-3 py-2 tabular ${cellTone(r[c.key])}`}>{r[c.key]}</td>)}</tr>))}</tbody></table>
      </Block>

      <Block title="Identity and links">
        <ul className="px-4 pb-3 space-y-1.5 text-xs text-muted">
          <li>{id.players.toLocaleString()} distinct players; {id.merged_duplicate_ids ?? "—"} duplicate IDs merged; {id.duplicate_groups_left_for_review ?? "—"} possible duplicates left for review.</li>
          <li>{id.transfermarkt_link_rate_pct ?? "—"}% of players are linked to Transfermarkt (contracts, values, transfers).</li>
          {id.identity_confidence_note && <li className="text-riskmed">{id.identity_confidence_note}</li>}
        </ul>
      </Block>

      <Block title="Rows worth a second look" note="Counts only. Nothing is removed or changed.">
        <table className="w-full text-xs"><thead><tr className="text-faint border-b border-border"><th className={th}>Check</th><th className={th}>Rows</th><th className={th}>Share</th><th className={th}>Why it matters</th></tr></thead>
          <tbody>{d.anomalies.map((a: any) => (
            <tr key={a.key} className="border-b border-border last:border-0"><td className="px-3 py-2 text-ink">{a.title}</td><td className="px-3 py-2 text-muted tabular">{a.rows.toLocaleString()}</td>
              <td className="px-3 py-2 text-muted tabular">{a.share_pct}%</td><td className="px-3 py-2 text-faint">{a.why}</td></tr>))}</tbody></table>
      </Block>
    </div>
  );
}
