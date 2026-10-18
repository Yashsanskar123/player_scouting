"use client";

import ClubCommandCenter from "@/components/ClubCommandCenter";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  formatEur,
  PlayerSummary,
  DashboardMover,
  DashboardOverview,
} from "@/lib/api";
import {
  MetricCard,
  RiskBadge,
  PlayerLink,
  LoadingState,
  ErrorState,
} from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";

function formatScore(value?: number | null) {
  return value == null || Number.isNaN(value) ? "—" : value.toFixed(1);
}

function formatDelta(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

function MoverTable({
  rows,
  mode,
}: {
  rows: DashboardMover[];
  mode: "improved" | "declined";
}) {
  return (
    <div className="border border-border rounded-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-2xs text-faint text-left">
            <th className="px-3 py-2 font-normal">Player</th>
            <th className="px-3 py-2 font-normal">Pos</th>
            <th className="px-3 py-2 font-normal">Club</th>
            <th className="px-3 py-2 font-normal text-right">Current</th>
            <th className="px-3 py-2 font-normal text-right">Change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.player_id} className="border-b border-border last:border-0">
              <td className="px-3 py-2">
                <PlayerLink playerId={p.player_id} name={p.short_name || p.player_id} />
              </td>
              <td className="px-3 py-2 text-muted">{p.canonical_position || "—"}</td>
              <td className="px-3 py-2 text-muted">{p.club_name || "—"}</td>
              <td className="px-3 py-2 text-right tabular text-ink">
                {formatScore(p.current_performance)}
              </td>
              <td
                className={`px-3 py-2 text-right tabular ${
                  mode === "improved" ? "text-risklow" : "text-riskhigh"
                }`}
              >
                {formatDelta(p.performance_delta)}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-muted text-sm">
                No eligible players for this season window.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function BreakoutTable({ overview }: { overview: DashboardOverview }) {
  return (
    <div className="border border-border rounded-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-2xs text-faint text-left">
            <th className="px-3 py-2 font-normal">Player</th>
            <th className="px-3 py-2 font-normal">Age</th>
            <th className="px-3 py-2 font-normal text-right">Perf.</th>
            <th className="px-3 py-2 font-normal text-right">Δ</th>
            <th className="px-3 py-2 font-normal text-right">Potential</th>
          </tr>
        </thead>
        <tbody>
          {overview.breakout.results.map((p) => (
            <tr key={p.player_id} className="border-b border-border last:border-0">
              <td className="px-3 py-2">
                <PlayerLink playerId={p.player_id} name={p.short_name || p.player_id} />
              </td>
              <td className="px-3 py-2 text-muted">{formatScore(p.age_fifa)}</td>
              <td className="px-3 py-2 text-right tabular text-ink">{formatScore(p.current_performance)}</td>
              <td className="px-3 py-2 text-right tabular text-risklow">{formatDelta(p.performance_delta)}</td>
              <td className="px-3 py-2 text-right tabular text-ink">{formatScore(p.development_potential)}</td>
            </tr>
          ))}
          {overview.breakout.results.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-muted text-sm">
                No breakout candidates meet the evidence thresholds.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function DashboardPage() {
  const { selectedSeason, selectedLabel } = useSeason();
  const [quality, setQuality] = useState<any>(null);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [opportunities, setOpportunities] = useState<PlayerSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (selectedSeason === null) return;

    setLoading(true);
    setError(null);

    Promise.all([
      api.dataQualitySafe(),
      api.dashboardOverview(selectedSeason),
      api.marketOpportunities({ topN: 6, season: selectedSeason }),
    ])
      .then(([q, dashboard, opp]) => {
        setQuality(q);
        setOverview(dashboard);
        setOpportunities(opp.results || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedSeason]);

  return (
    <div>
      <header className="mb-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl text-ink font-medium">Recruitment Dashboard</h1>
            <p className="text-muted text-sm mt-1">
              Recruitment intelligence and market signals for {selectedLabel}.
            </p>
          </div>
          <div className="text-right text-2xs text-faint">
            <div>ANALYSIS SEASON</div>
            <div className="text-xs text-ink mt-0.5">{selectedLabel}</div>
          </div>
        </div>
      </header>

      <ClubCommandCenter season={selectedSeason} label={selectedLabel} />

      {error && (
        <div className="mb-5">
          <ErrorState
            message={`Dashboard data could not be loaded (${error}). Start the backend and try again.`}
          />
        </div>
      )}

      {loading ? (
        <LoadingState label="Loading recruitment intelligence" />
      ) : (
        <>
          <section className="mb-8">
            <div className="flex items-baseline justify-between mb-3">
              <div>
                <h2 className="text-sm text-ink font-medium">Dataset health</h2>
                <p className="text-2xs text-faint mt-0.5">All available seasons</p>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <MetricCard
                label="Data quality"
                value={quality ? `${quality.overall_score}/100` : "—"}
                sublabel={quality ? `${quality.rows.toLocaleString()} player-seasons` : undefined}
              />
              <MetricCard
                label="Completeness"
                value={quality ? `${quality.breakdown?.completeness?.score}` : "—"}
              />
              <MetricCard
                label="Uniqueness"
                value={quality ? `${quality.breakdown?.uniqueness?.score}` : "—"}
              />
              <MetricCard
                label="Market opportunities"
                value={overview?.market_opportunities_total ?? "—"}
                sublabel="Selected season · performance ≥ 60 · undervalued"
              />
            </div>
          </section>

          <section className="mb-8">
            <div className="mb-3">
              <h2 className="text-sm text-ink font-medium">Season snapshot</h2>
              <p className="text-2xs text-faint mt-0.5">Canonical player-season population for {selectedLabel}</p>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <MetricCard
                label="Player pool"
                value={overview?.snapshot.player_count?.toLocaleString() || "—"}
                sublabel="unique players"
              />
              <MetricCard
                label="Average performance"
                value={formatScore(overview?.snapshot.average_performance)}
                sublabel="performance score"
              />
              <MetricCard
                label="Median market value"
                value={formatEur(overview?.snapshot.median_value_eur)}
                sublabel="player-level median"
              />
              <MetricCard
                label="Average potential"
                value={formatScore(overview?.snapshot.average_potential)}
                sublabel="development potential"
              />
            </div>
          </section>

          <section className="mb-8">
            <div className="mb-3">
              <h2 className="text-sm text-ink font-medium">Recruitment signals</h2>
              <p className="text-2xs text-faint mt-0.5">
                Season-over-season movement and emerging talent signals.
              </p>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <MetricCard
                label="Improving players"
                value={overview?.movers.improved_total ?? "—"}
                sublabel={`top movers · ≥${overview?.movers.method.performance_change_threshold ?? 8} pts improvement`}
              />
              <MetricCard
                label="Declining players"
                value={overview?.movers.declined_total ?? "—"}
                sublabel={`top movers · ≤-${overview?.movers.method.performance_change_threshold ?? 8} pts`}
              />
              <MetricCard
                label="Breakout candidates"
                value={overview?.breakout.total ?? "—"}
                sublabel="U23 · performance · potential · trend"
              />
              <MetricCard
                label="Trend sample"
                value={overview?.movers.eligible_players?.toLocaleString() ?? "—"}
                sublabel="players with ≥900 min in both seasons"
              />
            </div>
          </section>

          <section className="grid grid-cols-2 gap-5 mb-8">
            <div>
              <div className="flex items-baseline justify-between mb-3">
                <div>
                  <h2 className="text-sm text-ink font-medium">Most improved</h2>
                  <p className="text-2xs text-faint mt-0.5">
                    {overview?.movers.previous_season ? `${overview.movers.previous_season} → ${selectedSeason}` : "No prior season"}
                  </p>
                </div>
                <Link href="/scouting/search" className="text-xs text-accent hover:underline">
                  Search players
                </Link>
              </div>
              <MoverTable rows={overview?.movers.improved || []} mode="improved" />
            </div>

            <div>
              <div className="flex items-baseline justify-between mb-3">
                <div>
                  <h2 className="text-sm text-ink font-medium">Performance decline</h2>
                  <p className="text-2xs text-faint mt-0.5">
                    {overview?.movers.previous_season ? `${overview.movers.previous_season} → ${selectedSeason}` : "No prior season"}
                  </p>
                </div>
                <Link href="/scouting/search" className="text-xs text-accent hover:underline">
                  Search players
                </Link>
              </div>
              <MoverTable rows={overview?.movers.declined || []} mode="declined" />
            </div>
          </section>

          <section className="mb-8">
            <div className="flex items-baseline justify-between mb-3">
              <div>
                <h2 className="text-sm text-ink font-medium">Emerging talent</h2>
                <p className="text-2xs text-faint mt-0.5">
                  {overview?.breakout.total || 0} candidates meet the breakout evidence thresholds.
                </p>
              </div>
              <Link href="/scouting/search" className="text-xs text-accent hover:underline">
                Find more
              </Link>
            </div>
            {overview ? (
              <BreakoutTable overview={overview} />
            ) : (
              <div className="border border-dashed border-border rounded-sm px-6 py-10 text-center text-muted text-sm">
                No dashboard data available for this season.
              </div>
            )}
          </section>

          <section>
            <div className="flex items-baseline justify-between mb-3">
              <div>
                <h2 className="text-sm text-ink font-medium">Best market opportunities</h2>
                <p className="text-2xs text-faint mt-0.5">
                  Top 6 by opportunity score within the selected season.
                </p>
              </div>
              <Link href="/market/opportunities" className="text-xs text-accent hover:underline">
                View all
              </Link>
            </div>
            <div className="border border-border rounded-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-2xs text-faint text-left">
                    <th className="px-3 py-2 font-normal">Player</th>
                    <th className="px-3 py-2 font-normal">Pos</th>
                    <th className="px-3 py-2 font-normal">Club</th>
                    <th className="px-3 py-2 font-normal text-right">Value</th>
                    <th className="px-3 py-2 font-normal text-right">Fair value</th>
                    <th className="px-3 py-2 font-normal text-right">Gap</th>
                    <th className="px-3 py-2 font-normal">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {opportunities.map((p) => (
                    <tr key={p.player_id} className="border-b border-border last:border-0">
                      <td className="px-3 py-2">
                        <PlayerLink playerId={p.player_id} name={p.short_name} />
                      </td>
                      <td className="px-3 py-2 text-muted">{p.canonical_position}</td>
                      <td className="px-3 py-2 text-muted">{p.club_name}</td>
                      <td className="px-3 py-2 text-right tabular text-muted">{formatEur(p.value_eur)}</td>
                      <td className="px-3 py-2 text-right tabular text-ink">{formatEur(p.fair_value_eur)}</td>
                      <td className="px-3 py-2 text-right tabular text-risklow">
                        +{p.value_gap_pct?.toFixed(0)}%
                      </td>
                      <td className="px-3 py-2">
                        <RiskBadge tier={p.recruitment_risk_tier} />
                      </td>
                    </tr>
                  ))}
                  {opportunities.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-3 py-6 text-center text-muted text-sm">
                        No qualifying market opportunities for this season.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <div className="mt-6 pt-4 border-t border-border text-2xs text-faint leading-relaxed">
            Trend methodology: players need at least 900 minutes in both the selected and previous season.
            Breakout candidates are U23, have at least 900 minutes in both seasons, current performance ≥60,
            development potential ≥75, and performance improvement ≥5 points. Dashboard player counts use one
            canonical record per player-season to avoid duplicate source rows.
          </div>
        </>
      )}
    </div>
  );
}
