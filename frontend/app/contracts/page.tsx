"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, formatEur } from "@/lib/api";

type Row = {
  player_id: string;
  short_name: string;
  canonical_position?: string;
  club_name?: string;
  league_name?: string;
  age_fifa?: number;
  value_eur?: number;
  performance_score?: number;
  development_potential?: number;
  recruitment_risk_tier?: string;
  sample_reliability_tier?: string;
  playing_time_min?: number;
  contract_expires?: string;
  contract_months_left?: number;
  contract_status?: string;
  tm_value_eur?: number;
  tm_link_confidence?: string;
};

export default function ContractsPage() {
  const [months, setMonths] = useState("12");
  const [position, setPosition] = useState("");
  const [league, setLeague] = useState("");
  const [perf, setPerf] = useState("0");
  const [minAge, setMinAge] = useState("");
  const [maxAge, setMaxAge] = useState("");
  const [maxValue, setMaxValue] = useState("");

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const params = () => ({
    within_months: Number(months),
    canonical_position: position || undefined,
    league_name: league || undefined,
    min_performance_score:
      perf === "" ? undefined : Number(perf),
    min_age: minAge ? Number(minAge) : undefined,
    max_age: maxAge ? Number(maxAge) : undefined,
    max_value_eur: maxValue ? Number(maxValue) : undefined,
  });

  useEffect(() => {
    let live = true;

    setLoading(true);
    setError("");

    api
      .contractBoard(params())
      .then((v: any) => {
        if (live) setData(v);
      })
      .catch((e: any) => {
        if (live) {
          setError(e.message || "Could not load contract board");
        }
      })
      .finally(() => {
        if (live) setLoading(false);
      });

    return () => {
      live = false;
    };
  }, [months, position, league, perf, minAge, maxAge, maxValue]);

  const rows: Row[] = data?.results || [];

  return (
    <main className="p-6 lg:p-8 space-y-6 max-w-[1500px] mx-auto">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[.18em] text-muted">
            Recruitment intelligence
          </div>
          <h1 className="text-2xl font-semibold mt-2">
            Contract expiry board
          </h1>
          <p className="text-sm text-muted mt-2 max-w-3xl">
            Identify players with recorded contracts expiring in the
            next 6 or 12 months. Combine expiry with age, position,
            performance and budget filters.
          </p>
        </div>

        <button
          onClick={() => api.downloadContractBoardPdf(params())}
          className="bg-accent text-white px-3 py-2 text-sm rounded-sm"
        >
          Export PDF
        </button>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["Matching contracts", data?.total ?? "—"],
          [
            "Within 6 months",
            rows.filter((r) => (r.contract_months_left ?? 99) <= 6).length,
          ],
          [
            "Performance 75+",
            rows.filter((r) => (r.performance_score ?? 0) >= 75).length,
          ],
          [
            "High reliability",
            rows.filter((r) => r.sample_reliability_tier === "High").length,
          ],
        ].map(([k, v]) => (
          <div
            key={String(k)}
            className="border border-border bg-panel p-4"
          >
            <div className="text-xs text-muted">{k}</div>
            <div className="text-2xl font-semibold mt-1">
              {loading ? "—" : v}
            </div>
          </div>
        ))}
      </section>

      <section className="border border-border bg-panel p-4 grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
        <label className="text-xs text-muted">
          Expiry window
          <select
            value={months}
            onChange={(e) => setMonths(e.target.value)}
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          >
            <option value="6">Next 6 months</option>
            <option value="12">Next 12 months</option>
          </select>
        </label>

        <label className="text-xs text-muted">
          Position
          <select
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          >
            <option value="">All positions</option>
            {["GK", "CB", "FB", "WB", "DM", "CM", "AM", "WM", "W", "ST"].map(
              (x) => (
                <option key={x}>{x}</option>
              )
            )}
          </select>
        </label>

        <label className="text-xs text-muted">
          League
          <input
            value={league}
            onChange={(e) => setLeague(e.target.value)}
            placeholder="Exact league name"
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          />
        </label>

        <label className="text-xs text-muted">
          Minimum performance
          <input
            type="number"
            min="0"
            max="100"
            value={perf}
            onChange={(e) => setPerf(e.target.value)}
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          />
        </label>

        <label className="text-xs text-muted">
          Minimum age
          <input
            type="number"
            value={minAge}
            onChange={(e) => setMinAge(e.target.value)}
            placeholder="Any"
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          />
        </label>

        <label className="text-xs text-muted">
          Maximum age
          <input
            type="number"
            value={maxAge}
            onChange={(e) => setMaxAge(e.target.value)}
            placeholder="Any"
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          />
        </label>

        <label className="text-xs text-muted">
          Maximum value (€)
          <input
            type="number"
            value={maxValue}
            onChange={(e) => setMaxValue(e.target.value)}
            placeholder="No cap"
            className="block mt-1 w-full bg-panelraised border border-border p-2 text-sm text-ink"
          />
        </label>
      </section>

      <p className="text-xs text-muted">
        {data?.snapshot_note ||
          "Contract details use a current Transfermarkt snapshot and may not represent historical contract status."}
      </p>

      {error && (
        <div className="border border-red-500/30 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {data?.available === false && (
        <div className="border border-border p-5 text-sm text-muted">
          {data.reason}
        </div>
      )}

      <section className="border border-border bg-panel overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-panelraised text-xs text-muted">
            <tr>
              {[
                "Player",
                "Position / Club",
                "Age",
                "Performance",
                "Minutes",
                "Contract expiry",
                "Months left",
                "Market value",
                "Evidence",
              ].map((h) => (
                <th
                  key={h}
                  className="text-left font-medium px-3 py-3 whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((r) => (
              <tr
                key={r.player_id}
                className="border-t border-border hover:bg-panelraised/40"
              >
                <td className="px-3 py-3 whitespace-nowrap">
                  <Link
                    className="font-medium hover:text-accent"
                    href={`/players/${encodeURIComponent(r.player_id)}`}
                  >
                    {r.short_name}
                  </Link>
                  <div className="text-xs text-muted">
                    {r.league_name || "—"}
                  </div>
                </td>

                <td className="px-3 py-3 whitespace-nowrap">
                  {r.canonical_position || "—"}
                  <div className="text-xs text-muted">
                    {r.club_name || "—"}
                  </div>
                </td>

                <td className="px-3 py-3">{r.age_fifa ?? "—"}</td>

                <td className="px-3 py-3">
                  {r.performance_score == null
                    ? "—"
                    : r.performance_score.toFixed(1)}
                </td>

                <td className="px-3 py-3">
                  {r.playing_time_min == null
                    ? "—"
                    : Math.round(r.playing_time_min).toLocaleString()}
                </td>

                <td className="px-3 py-3 whitespace-nowrap">
                  {r.contract_expires || "—"}
                </td>

                <td className="px-3 py-3">
                  {r.contract_months_left == null
                    ? "—"
                    : r.contract_months_left.toFixed(1)}
                </td>

                <td className="px-3 py-3 whitespace-nowrap">
                  {formatEur(r.tm_value_eur ?? r.value_eur)}
                </td>

                <td className="px-3 py-3 text-xs text-muted">
                  {r.tm_link_confidence || "Unverified"}
                  <div>{r.sample_reliability_tier || "—"}</div>
                </td>
              </tr>
            ))}

            {!loading && !rows.length && (
              <tr>
                <td colSpan={9} className="p-8 text-center text-muted">
                  No matching contracts. Relax a filter or widen the expiry window.
                </td>
              </tr>
            )}

            {loading && (
              <tr>
                <td colSpan={9} className="p-8 text-center text-muted">
                  Loading contract board…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </main>
  );
}