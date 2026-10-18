"use client";

import { useEffect, useState } from "react";
import { api, formatEur } from "@/lib/api";

const n = (v: any, d = 1) => (v == null ? "—" : Number(v).toFixed(d));

/** Side-by-side squad statistics for the active club and up to 3 rivals, in the selected season. */
export default function ClubCompare({ activeClub, clubs, season, label }: { activeClub: string; clubs: { club_name: string; league_name?: string | null }[]; season?: number | null; label: string }) {
  const [rivals, setRivals] = useState<string[]>([]);
  const [data, setData] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // A new active club or season invalidates the previous comparison.
  useEffect(() => { setData(null); setError(null); setRivals((r) => r.filter((x) => x !== activeClub)); }, [activeClub, season]);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.compareClubs([activeClub, ...rivals], season);
      setData(res.clubs);
    } catch (e: any) {
      setData(null);
      setError(String(e?.message || "").includes("404") ? "One of these clubs has no squad data in the selected season. Pick another season or club." : e.message || "Comparison failed.");
    } finally {
      setLoading(false);
    }
  }

  const options = clubs.filter((c) => c.club_name !== activeClub && !rivals.includes(c.club_name));
  const best = (key: string, higher = true) => {
    if (!data) return null;
    const vals = data.map((c) => c[key]).filter((v) => v != null);
    return vals.length ? (higher ? Math.max(...vals) : Math.min(...vals)) : null;
  };
  const rows: [string, (c: any) => string, string, boolean][] = [
    ["Squad size", (c) => String(c.roster_size), "roster_size", true],
    ["Average age", (c) => n(c.average_age), "average_age", false],
    ["Average performance", (c) => n(c.average_performance), "average_performance", true],
    ["Squad market value", (c) => formatEur(c.squad_market_value_eur), "squad_market_value_eur", true],
    ["Players aged 23 or under", (c) => (c.young_players_share == null ? "—" : `${c.young_players_share}%`), "young_players_share", true],
  ];
  const groups = Array.from(new Set((data || []).flatMap((c) => Object.keys(c.by_position_group || {})))).sort();

  return (
    <section className="border border-border bg-panel rounded-sm p-4 mt-5">
      <h2 className="text-sm text-ink font-medium">Compare with rivals · {label}</h2>
      <p className="text-2xs text-faint mt-1">Pick up to three clubs to set against {activeClub}. The best value in each row is highlighted.</p>
      <div className="flex flex-wrap items-end gap-3 mt-3">
        {rivals.map((r) => (
          <span key={r} className="inline-flex items-center gap-1 text-xs border border-border rounded-sm px-2 py-1 text-ink">
            {r}<button type="button" aria-label={`Remove ${r}`} onClick={() => setRivals(rivals.filter((x) => x !== r))} className="text-faint hover:text-ink">×</button>
          </span>
        ))}
        {rivals.length < 3 && (
          <label className="text-2xs text-faint">Add a rival
            <select value="" onChange={(e) => e.target.value && setRivals([...rivals, e.target.value])} className="mt-1 block bg-panelraised border border-border rounded-sm px-2 py-1.5 text-xs text-ink">
              <option value="">Select a club</option>
              {options.map((c) => <option key={c.club_name} value={c.club_name}>{c.club_name}{c.league_name ? ` (${c.league_name})` : ""}</option>)}
            </select>
          </label>
        )}
        <button type="button" onClick={run} disabled={rivals.length === 0 || loading} className="px-3 py-1.5 text-xs rounded-sm bg-accent text-black font-medium disabled:opacity-40">{loading ? "Comparing…" : "Compare"}</button>
      </div>
      {error && <p role="alert" className="text-xs text-riskhigh mt-3">{error}</p>}
      {data && (
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-xs">
            <thead><tr className="text-faint text-left border-b border-border"><th className="px-3 py-2 font-normal" />{data.map((c) => <th key={c.club_name} className="px-3 py-2 font-normal text-ink">{c.club_name}<div className="text-2xs text-faint">{c.league_name}</div></th>)}</tr></thead>
            <tbody>
              {rows.map(([title, fmt, key, higher]) => {
                const top = best(key, higher);
                return (
                  <tr key={key} className="border-b border-border">
                    <td className="px-3 py-2 text-muted">{title}</td>
                    {data.map((c) => <td key={c.club_name} className={`px-3 py-2 tabular ${top != null && c[key] === top && data.length > 1 ? "text-risklow font-medium" : "text-ink"}`}>{fmt(c)}</td>)}
                  </tr>
                );
              })}
              {groups.length > 0 && <tr><td colSpan={data.length + 1} className="px-3 pt-4 pb-1 text-2xs text-faint">Average performance by position group</td></tr>}
              {groups.map((g) => {
                const vals = data.map((c) => c.by_position_group?.[g]?.average_performance).filter((v: any) => v != null);
                const top = vals.length ? Math.max(...vals) : null;
                return (
                  <tr key={g} className="border-b border-border last:border-0">
                    <td className="px-3 py-2 text-muted">{g}</td>
                    {data.map((c) => { const v = c.by_position_group?.[g]?.average_performance; return <td key={c.club_name} className={`px-3 py-2 tabular ${v != null && v === top && data.length > 1 ? "text-risklow font-medium" : "text-ink"}`}>{n(v)}</td>; })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
