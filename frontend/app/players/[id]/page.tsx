"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, formatEur } from "@/lib/api";
import { RiskBadge, LoadingState, ErrorState } from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";
import TransfermarktPanel from "@/components/TransfermarktPanel";
import DownloadButton from "@/components/DownloadButton";
import ExplainPanel from "@/components/ExplainPanel";
import ValidationBadge from "@/components/ValidationBadge";

const PERCENTILE_GROUPS: Record<string, string[]> = {
  "Attacking": ["per_90_minutes_gls", "per_90_minutes_x_g", "per_90_minutes_npx_g"],
  "Creation": ["per_90_minutes_ast", "per_90_minutes_expected_x_a", "per_90_minutes_kp", "sca_sca90"],
  "Progression": ["per_90_minutes_prg_c", "per_90_minutes_prg_p", "per_90_minutes_prg_r", "per_90_minutes_1_3"],
  "Passing": ["per_90_minutes_total_cmp", "total_cmppct", "per_90_minutes_ppa"],
  "Defending": ["per_90_minutes_tackles_tkl", "per_90_minutes_int", "per_90_minutes_clr", "per_90_minutes_blocks_blocks"],
};

export default function PlayerProfilePage({ params }: { params: { id: string } }) {
  const [player, setPlayer] = useState<any>(null);
  const [percentiles, setPercentiles] = useState<any>(null);
  const [roles, setRoles] = useState<any>(null);
  const [similar, setSimilar] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [profileIntel, setProfileIntel] = useState<any>(null);
  const [tactical, setTactical] = useState<any>(null);
  const [transferIntel, setTransferIntel] = useState<any>(null);
  const [potential, setPotential] = useState<any>(null);
  const [tacticalFormation, setTacticalFormation] = useState("4-3-3");
  const [tacticalStyle, setTacticalStyle] = useState("Balanced");
  const [error, setError] = useState<string | null>(null);
  const { selectedSeason, selectedLabel } = useSeason();

  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("scoutiq:last-player-id", params.id);
    if (selectedSeason === null) return;
    setError(null);
    Promise.all([
      api.getPlayer(params.id, selectedSeason),
      api.getPercentiles(params.id, selectedSeason),
      api.getRoles(params.id, selectedSeason),
      api.getSimilar(params.id, 6, selectedSeason),
      api.getPlayerHistory(params.id),
      api.getProfileIntelligence(params.id, selectedSeason),
      api.getTransferIntelligence(params.id, selectedSeason).catch(() => null),
      api.getPotential(params.id, selectedSeason),
    ])
      .then(([p, pc, r, s, h, pi, ti, pot]) => {
        setPlayer(p);
        setPercentiles(pc);
        setRoles(r);
        setSimilar(s);
        setHistory(h);
        setProfileIntel(pi);
        setTransferIntel(ti);
        setPotential(pot);
      })
      .catch((e) => setError(e.message));
  }, [params.id, selectedSeason]);

  useEffect(() => {
    if (!params.id) return;
    if (selectedSeason === null) return;
    api.getTacticalFit(params.id, tacticalFormation, tacticalStyle, undefined, selectedSeason)
      .then(setTactical)
      .catch(() => setTactical(null));
  }, [params.id, tacticalFormation, tacticalStyle, selectedSeason]);

  if (error) return <ErrorState message={error} />;
  if (!player) return <LoadingState label="Loading player intelligence" />;

  const topRole = roles?.roles?.[0];
  const trajectory = history?.history ?? [];
  const historySummary = history?.summary ?? {};
  const pct = percentiles?.percentiles ?? {};
  const selectedIndex = trajectory.findIndex((row: any) => Number(row.season) === Number(selectedSeason));
  const selectedHistoryRow = selectedIndex >= 0 ? trajectory[selectedIndex] : null;
  const previous = selectedIndex > 0 ? trajectory[selectedIndex - 1] : null;
  const performanceDelta = selectedHistoryRow && previous && selectedHistoryRow.performance_score != null && previous.performance_score != null
    ? selectedHistoryRow.performance_score - previous.performance_score
    : null;

  const radarData = buildRadarData(pct);
  const strengths = getStrengths(player, pct);
  const concerns = getConcerns(player, pct);

  return (
    <div className="space-y-8 pb-10">
      {/* Identity / decision header */}
      <section className="rounded-xl border border-border bg-panel overflow-hidden">
        <div className="h-1 bg-accent" />
        <div className="p-6 lg:p-7">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex gap-4">
              <PlayerAvatar name={player.short_name} />
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="text-2xs uppercase tracking-[0.18em] text-accent">Player intelligence</span>
                  <span className="badge badge-neutral">Analysis season · {selectedLabel}</span>
                  <RiskBadge tier={player.recruitment_risk_tier} />
                </div>
                <h1 className="text-3xl lg:text-4xl text-ink font-semibold tracking-tight">{player.short_name}</h1>
                <div className="mt-3"><DownloadButton label="Download PDF report" onDownload={() => api.downloadPlayerReport(player.player_id, selectedSeason)} /></div>
                <p className="text-muted text-sm mt-2">
                  {player.canonical_position || "—"} · {player.club_name || "Free agent / unknown club"} · {player.league_name || "—"}
                </p>
                <div className="flex flex-wrap gap-x-5 gap-y-1 mt-3 text-xs text-faint">
                  <span>Age {player.age_fifa ?? "—"}</span>
                  <span>{player.nationality_name || "Nationality unavailable"}</span>
                  <span>{player.preferred_foot ? `${player.preferred_foot} foot` : "Foot unavailable"}</span>
                  {player.height_cm ? <span>{player.height_cm} cm</span> : null}
                </div>
              </div>
            </div>
            <div className="flex gap-2 shrink-0">
              <Link href="/scouting/compare" className="action-button">Compare</Link>
              <Link href={`/scouting/replace?for=${player.player_id}`} className="action-button action-button-primary">Find replacement</Link>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 mt-7">
            <DecisionMetric label="Performance" value={num(player.performance_score)} delta={performanceDelta} />
            <DecisionMetric label="12M expected" value={num(player.expected_performance_12m)} />
            <DecisionMetric label="Potential" value={num(player.development_potential)} />
            <DecisionMetric label="Top role" value={topRole ? num(topRole.role_fit_score) : "—"} sub={topRole?.role} />
            <DecisionMetric label="Market value" value={formatEur(player.value_eur)} />
            <DecisionMetric label="Fair value" value={formatEur(player.fair_value_eur)} />
            <DecisionMetric label="Value gap" value={player.value_gap_pct == null ? "—" : `${player.value_gap_pct >= 0 ? "+" : ""}${player.value_gap_pct.toFixed(0)}%`} sub="model vs market" />
            <DecisionMetric label="Uncertainty" value={player.recruitment_risk_tier || "—"} sub="outcome volatility" />
          </div>
        </div>
      </section>

      {/* Advanced potential */}
      <section className="analytics-panel">
        <PanelHeader title="Development trajectory" subtitle="Current ability, expected progression and exploratory upside signals" />
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 border-b border-border">
          <PotentialStat label="Current" value={num(potential?.current_ability ?? player.performance_score)} />
          <PotentialStat label="12M expected" value={num(potential?.potential_12m ?? player.expected_performance_12m)} />
          <PotentialStat label="24M projection" value={num(potential?.potential_24m)} muted />
          <PotentialStat label="Peak projection" value={num(potential?.peak_projection)} muted />
          <PotentialStat label="Breakout" value={potential?.breakout_probability == null ? "—" : `${Number(potential.breakout_probability).toFixed(0)}%`} muted />
          <PotentialStat label="Decline" value={potential?.decline_probability == null ? "—" : `${Number(potential.decline_probability).toFixed(0)}%`} muted />
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="p-5 border-b xl:border-b-0 xl:border-r border-border">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xs text-ink font-medium">Trajectory interpretation</h3>
                <p className="text-2xs text-faint mt-1">Observed direction plus forward-looking model signals</p>
              </div>
              <span className={`badge ${potential?.development_trajectory === "rising" ? "badge-positive" : potential?.development_trajectory === "falling" ? "badge-negative" : "badge-neutral"}`}>
                {potential?.development_trajectory || "unknown"}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <PotentialInsight title="12M" text="Validated one-season estimator using the existing recency/mean backtest." />
              <PotentialInsight title="24M" text="Exploratory recursive extension; use as directional context until two-step validation is expanded." />
              <PotentialInsight title="Peak" text="Exploratory ceiling signal using age room and the FIFA potential benchmark, not a guaranteed career peak." />
            </div>
          </div>
          <div className="p-5">
            <h3 className="text-xs text-ink font-medium">Evidence quality</h3>
            <p className="text-2xs text-faint mt-1 mb-4">Empirical breakout / decline rates from comparable historical cohorts</p>
            <div className="space-y-3">
              <EvidenceRow label="Cohort sample" value={potential?.potential_evidence_sample ? Number(potential.potential_evidence_sample).toLocaleString() : "—"} />
              <EvidenceRow label="Signal status" value={String(potential?.potential_projection_status || "—").replaceAll("_", " ")} />
              <EvidenceRow label="FIFA benchmark" value={num(potential?.fifa_potential_benchmark)} />
            </div>
            <p className="text-2xs text-faint leading-5 mt-4">Breakout is defined here as a next-season performance increase of at least 5 points; decline is a drop of at least 5 points. These are empirical historical rates, not causal probabilities.</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-2xs text-faint">Model status: development potential <ValidationBadge modelKey="development_potential" /> breakout <ValidationBadge modelKey="breakout_probability" /> decline <ValidationBadge modelKey="decline_probability" /></div>
          </div>
        </div>
      </section>

      {/* Trajectory + peer profile */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.55fr_1fr] gap-6">
        <section className="analytics-panel">
          <PanelHeader title="Performance trajectory" subtitle={`Observed season performance across history · current snapshot ${selectedLabel}`} />
          <div className="h-72 px-2 pt-4">
            {trajectory.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trajectory} margin={{ top: 8, right: 16, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="performanceFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#D9A441" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#D9A441" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1D2530" vertical={false} />
                  <XAxis dataKey="season" tick={{ fill: "#738091", fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fill: "#738091", fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="performance_score" name="Performance" stroke="#D9A441" strokeWidth={2.5} fill="url(#performanceFill)" />
                  <Area type="monotone" dataKey="expected_performance_12m" name="12M expected" stroke="#738091" strokeDasharray="5 5" strokeWidth={1.5} fill="none" connectNulls />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart text="No multi-season history is available for this player." />
            )}
          </div>
          <div className="px-5 pb-5 flex flex-wrap gap-4 text-2xs text-faint">
            <LegendDot color="#D9A441" label="Observed performance" />
            <LegendDot color="#738091" label="12M expected" dashed />
            {selectedHistoryRow?.season ? <span className="ml-auto">Snapshot: {selectedLabel}</span> : null}
          </div>
        </section>

        <section className="analytics-panel">
          <PanelHeader title="Peer percentile profile" subtitle="Position and season-relative output" />
          <div className="h-72 px-2 pt-2">
            {radarData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="68%">
                  <PolarGrid stroke="#2A3441" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: "#AEB7C3", fontSize: 10 }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fill: "#536071", fontSize: 9 }} axisLine={false} />
                  <Radar name="Peer percentile" dataKey="value" stroke="#D9A441" fill="#D9A441" fillOpacity={0.2} strokeWidth={2} />
                  <Tooltip content={<ChartTooltip />} />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart text="Peer percentile data is unavailable." />
            )}
          </div>
          <div className="px-5 pb-5 text-2xs text-faint">100 = top of the player's current peer distribution.</div>
        </section>
      </div>

      {/* "Why these numbers": reconciling breakdowns + model status (renders nothing on failure) */}
      <ExplainPanel playerId={params.id} season={selectedSeason} />

      {/* Optional Transfermarkt context (renders nothing when unavailable) */}
      <TransfermarktPanel playerId={params.id} />

      {/* Historical intelligence */}
      <section className="analytics-panel">
        <PanelHeader title="Historical intelligence" subtitle="What changed across the player's observed seasons" />
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 border-b border-border">
          <HistoryStat label="Seasons" value={String(historySummary.seasons_observed ?? trajectory.length)} />
          <HistoryStat label="Performance change" value={historySummary.performance_change == null ? "—" : `${historySummary.performance_change >= 0 ? "+" : ""}${Number(historySummary.performance_change).toFixed(1)}`} tone={historySummary.performance_change >= 0 ? "positive" : "negative"} />
          <HistoryStat label="Best season" value={historySummary.best_performance_season ?? "—"} />
          <HistoryStat label="Lowest season" value={historySummary.worst_performance_season ?? "—"} />
          <HistoryStat label="Club changes" value={String(historySummary.club_changes ?? 0)} />
          <HistoryStat label="League changes" value={String(historySummary.league_changes ?? 0)} />
          <HistoryStat label="Value change" value={historySummary.value_change_pct == null ? "—" : `${historySummary.value_change_pct >= 0 ? "+" : ""}${Number(historySummary.value_change_pct).toFixed(0)}%`} tone={historySummary.value_change_pct >= 0 ? "positive" : "negative"} />
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[1.25fr_0.75fr] gap-0">
          <div className="p-5 border-b xl:border-b-0 xl:border-r border-border">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs text-ink font-medium">Season-by-season record</h3>
                <p className="text-2xs text-faint mt-1">Role, workload and output context</p>
              </div>
              <TrajectoryLabel summary={historySummary} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="text-2xs text-faint uppercase tracking-wider border-b border-border">
                  <th className="text-left py-2 pr-3">Season</th><th className="text-left py-2 px-2">Club</th><th className="text-left py-2 px-2">Role</th><th className="text-right py-2 px-2">Min</th><th className="text-right py-2 px-2">Perf</th><th className="text-right py-2 pl-2">Value</th>
                </tr></thead>
                <tbody>
                  {trajectory.map((row: any, i: number) => (
                    <tr key={`${row.season}-${i}`} className="border-b border-border/70 last:border-0">
                      <td className="py-3 pr-3 text-ink tabular font-medium">{row.season ?? "—"}</td>
                      <td className="py-3 px-2 text-muted max-w-[150px] truncate">{row.club_name ?? "—"}</td>
                      <td className="py-3 px-2 text-muted">{row.canonical_position ?? "—"}</td>
                      <td className="py-3 px-2 text-right text-muted tabular">{row.playing_time_min == null ? "—" : Number(row.playing_time_min).toLocaleString()}</td>
                      <td className="py-3 px-2 text-right text-ink tabular font-medium">{num(row.performance_score)}</td>
                      <td className="py-3 pl-2 text-right text-muted tabular">{formatEur(row.value_eur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="p-5">
            <h3 className="text-xs text-ink font-medium">Market-value trajectory</h3>
            <p className="text-2xs text-faint mt-1 mb-3">Observed market value by season</p>
            <div className="h-48">
              {trajectory.some((r: any) => r.value_eur != null) ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trajectory} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid stroke="#1D2530" vertical={false} />
                    <XAxis dataKey="season" tick={{ fill: "#738091", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fill: "#738091", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(v) => formatCompactEur(v)} />
                    <Tooltip content={<MarketTooltip />} />
                    <Line type="monotone" dataKey="value_eur" name="Market value" stroke="#D9A441" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                    <Line type="monotone" dataKey="fair_value_eur" name="Fair value" stroke="#738091" strokeWidth={1.5} strokeDasharray="5 5" dot={false} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              ) : <EmptyChart text="No market-value history available." />}
            </div>
            <div className="mt-3 text-2xs text-faint leading-5">Historical value reflects the source dataset. Fair value is the model estimate for each observed season where available.</div>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-5 border-t border-border bg-panelraised/20">
          <HistoryContext label="Positions observed" values={historySummary.positions_observed} fallback="No position history available." />
          <HistoryContext label="Leagues observed" values={historySummary.leagues_observed} fallback="No league history available." />
        </div>
      </section>

      {/* Longitudinal recruitment intelligence */}
      <section className="analytics-panel">
        <PanelHeader title="Longitudinal recruitment intelligence" subtitle="Season-aware evidence for form, consistency, development, role and career context" />
        {profileIntel ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 border-b border-border">
              <HistoryStat label="3Y average" value={profileIntel.windows?.three_year?.average_performance == null ? "—" : Number(profileIntel.windows.three_year.average_performance).toFixed(1)} />
              <HistoryStat label="5Y average" value={profileIntel.windows?.five_year?.average_performance == null ? "—" : Number(profileIntel.windows.five_year.average_performance).toFixed(1)} />
              <HistoryStat label="Consistency" value={profileIntel.windows?.five_year?.consistency_std == null ? "—" : `±${Number(profileIntel.windows.five_year.consistency_std).toFixed(1)}`} />
              <HistoryStat label="Trend / season" value={profileIntel.trend?.performance_slope_per_season == null ? "—" : `${profileIntel.trend.performance_slope_per_season >= 0 ? "+" : ""}${Number(profileIntel.trend.performance_slope_per_season).toFixed(1)}`} tone={profileIntel.trend?.performance_slope_per_season >= 3 ? "positive" : profileIntel.trend?.performance_slope_per_season <= -3 ? "negative" : undefined} />
              <HistoryStat label="Peak performance" value={profileIntel.peak?.performance == null ? "—" : Number(profileIntel.peak.performance).toFixed(1)} />
              <HistoryStat label="Peak season" value={String(profileIntel.peak?.season ?? "—")} />
              <HistoryStat label="Role changes" value={String(profileIntel.role_evolution?.changes ?? 0)} />
              <HistoryStat label="Club changes" value={String(profileIntel.club_league_trajectory?.club_changes ?? 0)} />
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-[1.25fr_0.75fr]">
              <div className="p-5 border-b xl:border-b-0 xl:border-r border-border">
                <div className="flex items-center justify-between mb-3">
                  <div><h3 className="text-xs text-ink font-medium">Performance development curve</h3><p className="text-2xs text-faint mt-1">Observed performance and potential through the selected season</p></div>
                  <span className="badge badge-neutral">{profileIntel.trend?.interpretation?.replaceAll("_", " ") || "unknown"}</span>
                </div>
                <div className="h-64">
                  {profileIntel.trajectory?.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={profileIntel.trajectory} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                        <CartesianGrid stroke="#1D2530" vertical={false} />
                        <XAxis dataKey="season" tick={{ fill: "#738091", fontSize: 10 }} tickLine={false} axisLine={false} />
                        <YAxis domain={[0, 100]} tick={{ fill: "#738091", fontSize: 10 }} tickLine={false} axisLine={false} />
                        <Tooltip content={<ChartTooltip />} />
                        <Line type="monotone" dataKey="performance" name="Performance" stroke="#D9A441" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                        <Line type="monotone" dataKey="potential" name="Potential" stroke="#738091" strokeWidth={1.8} strokeDasharray="5 5" dot={{ r: 2 }} connectNulls />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : <EmptyChart text="No longitudinal performance history available." />}
                </div>
              </div>
              <div className="p-5">
                <h3 className="text-xs text-ink font-medium">Career trajectory</h3>
                <p className="text-2xs text-faint mt-1 mb-4">Context surrounding the performance curve</p>
                <div className="space-y-3">
                  <HistoryContext label="Positions" values={profileIntel.role_evolution?.positions} fallback="No role history." />
                  <HistoryContext label="Clubs" values={profileIntel.club_league_trajectory?.clubs} fallback="No club history." />
                  <HistoryContext label="Leagues" values={profileIntel.club_league_trajectory?.leagues} fallback="No league history." />
                </div>
              </div>
            </div>
            {profileIntel.component_evolution?.length ? (
              <div className="p-5 border-t border-border">
                <div className="mb-4"><h3 className="text-xs text-ink font-medium">Metric-component evolution</h3><p className="text-2xs text-faint mt-1">Change in the existing position-aware percentile component scores across observed seasons</p></div>
                <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
                  {profileIntel.component_evolution.map((item: any) => (
                    <div key={item.component} className="border border-border bg-panelraised/30 rounded-lg p-3">
                      <div className="text-2xs text-faint capitalize truncate">{item.component.replaceAll("_", " ")}</div>
                      <div className="text-lg text-ink tabular font-semibold mt-2">{item.current == null ? "—" : Number(item.current).toFixed(0)}</div>
                      <div className={`text-2xs mt-1 ${Number(item.change) >= 0 ? "text-risklow" : "text-riskhigh"}`}>{item.change == null ? "limited history" : `${Number(item.change) >= 0 ? "+" : ""}${Number(item.change).toFixed(1)} since first observed`}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="px-5 py-4 border-t border-border text-2xs text-faint leading-5">Method: historical data is cut off at the selected analysis season. Trend calculations use seasons with at least 900 minutes; 3Y/5Y averages use the most recent observed seasons. Component evolution uses the existing position- and season-aware percentile component scores where available. These are descriptive recruitment signals, not guaranteed forecasts.</div>
          </>
        ) : <div className="p-5 text-sm text-muted">Longitudinal intelligence is unavailable for this player.</div>}
      </section>

      {/* Longitudinal recruitment intelligence */}
      <section className="analytics-panel">
        <PanelHeader
          title="Longitudinal recruitment intelligence"
          subtitle="Season-aware evidence for form, consistency, development, role and career context"
        />

        {profileIntel ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 border-b border-border">
              <HistoryStat
                label="3Y average"
                value={
                  profileIntel.windows?.three_year?.average_performance == null
                    ? "—"
                    : Number(
                        profileIntel.windows.three_year.average_performance
                      ).toFixed(1)
                }
              />

              <HistoryStat
                label="5Y average"
                value={
                  profileIntel.windows?.five_year?.average_performance == null
                    ? "—"
                    : Number(
                        profileIntel.windows.five_year.average_performance
                      ).toFixed(1)
                }
              />

              <HistoryStat
                label="Consistency"
                value={
                  profileIntel.windows?.five_year?.consistency_std == null
                    ? "—"
                    : `±${Number(
                        profileIntel.windows.five_year.consistency_std
                      ).toFixed(1)}`
                }
              />

              <HistoryStat
                label="Trend / season"
                value={
                  profileIntel.trend?.performance_slope_per_season == null
                    ? "—"
                    : `${
                        profileIntel.trend.performance_slope_per_season >= 0
                          ? "+"
                          : ""
                      }${Number(
                        profileIntel.trend.performance_slope_per_season
                      ).toFixed(1)}`
                }
                tone={
                  profileIntel.trend?.performance_slope_per_season >= 3
                    ? "positive"
                    : profileIntel.trend?.performance_slope_per_season <= -3
                    ? "negative"
                    : undefined
                }
              />

              <HistoryStat
                label="Peak performance"
                value={
                  profileIntel.peak?.performance == null
                    ? "—"
                    : Number(
                        profileIntel.peak.performance
                      ).toFixed(1)
                }
              />

              <HistoryStat
                label="Peak season"
                value={String(
                  profileIntel.peak?.season ?? "—"
                )}
              />

              <HistoryStat
                label="Role changes"
                value={String(
                  profileIntel.role_evolution?.changes ?? 0
                )}
              />

              <HistoryStat
                label="Club changes"
                value={String(
                  profileIntel.club_league_trajectory?.club_changes ?? 0
                )}
              />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[1.25fr_0.75fr]">
              <div className="p-5 border-b xl:border-b-0 xl:border-r border-border">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-xs text-ink font-medium">
                      Performance development curve
                    </h3>

                    <p className="text-2xs text-faint mt-1">
                      Observed performance and potential through the selected season
                    </p>
                  </div>

                  <span className="badge badge-neutral">
                    {profileIntel.trend?.interpretation?.replaceAll("_", " ") ||
                      "unknown"}
                  </span>
                </div>

                <div className="h-64">
                  {profileIntel.trajectory?.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={profileIntel.trajectory}
                        margin={{
                          top: 8,
                          right: 8,
                          left: -18,
                          bottom: 0,
                        }}
                      >
                        <CartesianGrid
                          stroke="#1D2530"
                          vertical={false}
                        />

                        <XAxis
                          dataKey="season"
                          tick={{
                            fill: "#738091",
                            fontSize: 10,
                          }}
                          tickLine={false}
                          axisLine={false}
                        />

                        <YAxis
                          domain={[0, 100]}
                          tick={{
                            fill: "#738091",
                            fontSize: 10,
                          }}
                          tickLine={false}
                          axisLine={false}
                        />

                        <Tooltip content={<ChartTooltip />} />

                        <Line
                          type="monotone"
                          dataKey="performance"
                          name="Performance"
                          stroke="#D9A441"
                          strokeWidth={2.5}
                          dot={{ r: 3 }}
                          connectNulls
                        />

                        <Line
                          type="monotone"
                          dataKey="potential"
                          name="Potential"
                          stroke="#738091"
                          strokeWidth={1.8}
                          strokeDasharray="5 5"
                          dot={{ r: 2 }}
                          connectNulls
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <EmptyChart text="No longitudinal performance history available." />
                  )}
                </div>
              </div>

              <div className="p-5">
                <h3 className="text-xs text-ink font-medium">
                  Career trajectory
                </h3>

                <p className="text-2xs text-faint mt-1 mb-4">
                  Context surrounding the performance curve
                </p>

                <div className="space-y-3">
                  <HistoryContext
                    label="Positions"
                    values={profileIntel.role_evolution?.positions}
                    fallback="No role history."
                  />

                  <HistoryContext
                    label="Clubs"
                    values={profileIntel.club_league_trajectory?.clubs}
                    fallback="No club history."
                  />

                  <HistoryContext
                    label="Leagues"
                    values={profileIntel.club_league_trajectory?.leagues}
                    fallback="No league history."
                  />
                </div>
              </div>
            </div>

            {profileIntel.component_evolution?.length ? (
              <div className="p-5 border-t border-border">
                <div className="mb-4">
                  <h3 className="text-xs text-ink font-medium">
                    Metric-component evolution
                  </h3>

                  <p className="text-2xs text-faint mt-1">
                    Change in the existing position-aware percentile component
                    scores across observed seasons
                  </p>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
                  {profileIntel.component_evolution.map(
                    (item: any) => (
                      <div
                        key={item.component}
                        className="border border-border bg-panelraised/30 rounded-lg p-3"
                      >
                        <div className="text-2xs text-faint capitalize truncate">
                          {item.component.replaceAll("_", " ")}
                        </div>

                        <div className="text-lg text-ink tabular font-semibold mt-2">
                          {item.current == null
                            ? "—"
                            : Number(item.current).toFixed(0)}
                        </div>

                        <div
                          className={`text-2xs mt-1 ${
                            Number(item.change) >= 0
                              ? "text-risklow"
                              : "text-riskhigh"
                          }`}
                        >
                          {item.change == null
                            ? "limited history"
                            : `${
                                Number(item.change) >= 0
                                  ? "+"
                                  : ""
                              }${Number(item.change).toFixed(
                                1
                              )} since first observed`}
                        </div>
                      </div>
                    )
                  )}
                </div>
              </div>
            ) : null}

            <div className="px-5 py-4 border-t border-border text-2xs text-faint leading-5">
              Method: historical data is cut off at the selected analysis
              season. Trend calculations use seasons with at least 900 minutes;
              3Y/5Y averages use the most recent observed seasons. Component
              evolution uses the existing position- and season-aware percentile
              component scores where available. These are descriptive
              recruitment signals, not guaranteed forecasts.
            </div>
          </>
        ) : (
          <div className="p-5 text-sm text-muted">
            Longitudinal intelligence is unavailable for this player.
          </div>
        )}
      </section>

      {/* Tactical / system fit */}
      <section className="analytics-panel">
        <div className="p-5 border-b border-border flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-sm text-ink font-medium">Tactical / system fit</h2>
            <p className="text-2xs text-faint mt-1">Modelled compatibility between the player, formation and selected tactical style.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="text-2xs text-faint">
              <span className="block mb-1">Formation</span>
              <select value={tacticalFormation} onChange={(e) => setTacticalFormation(e.target.value)} className="bg-panelraised border border-border rounded-sm px-2 py-1.5 text-xs text-ink">
                {(["4-3-3", "4-2-3-1", "4-4-2", "3-4-3", "3-5-2"]).map((f) => <option key={f}>{f}</option>)}
              </select>
            </label>
            <label className="text-2xs text-faint">
              <span className="block mb-1">Style</span>
              <select value={tacticalStyle} onChange={(e) => setTacticalStyle(e.target.value)} className="bg-panelraised border border-border rounded-sm px-2 py-1.5 text-xs text-ink">
                {(["Balanced", "Possession", "High Press", "Transition", "Low Block"]).map((f) => <option key={f}>{f}</option>)}
              </select>
            </label>
          </div>
        </div>
        {tactical ? (
          <div className="p-5">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              <ValueBox label="System fit" value={num(tactical.system_fit_score)} accent />
              <ValueBox label="Role" value={tactical.role || player.canonical_position || "—"} />
              <ValueBox label="Evidence coverage" value={`${Number(tactical.evidence_coverage_pct || 0).toFixed(0)}%`} />
              <ValueBox label="Context" value={`${tacticalFormation} · ${tacticalStyle}`} />
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-[1fr_1fr] gap-5">
              <div>
                <div className="text-2xs uppercase tracking-wider text-faint mb-3">Component profile</div>
                <div className="space-y-3">
                  {Object.entries(tactical.component_scores || {}).map(([key, value]: [string, any]) => value != null ? (
                    <div key={key}>
                      <div className="flex justify-between text-xs mb-1"><span className="text-muted capitalize">{key.replaceAll("_", " ")}</span><span className="text-ink tabular">{Number(value).toFixed(0)}</span></div>
                      <div className="h-1.5 bg-panelraised rounded-full overflow-hidden"><div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, Number(value)))}%` }} /></div>
                    </div>
                  ) : null)}
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-border rounded-sm p-4 bg-panelraised/20">
                  <div className="text-2xs uppercase tracking-wider text-faint mb-3">Why it fits</div>
                  {tactical.strengths?.length ? tactical.strengths.map((item: any) => <div key={item.component} className="flex justify-between text-xs py-2 border-b border-border last:border-0"><span className="text-muted capitalize">{item.component.replaceAll("_", " ")}</span><span className="text-risklow tabular">{Number(item.score).toFixed(0)}</span></div>) : <div className="text-xs text-muted">No strong evidence above the current threshold.</div>}
                </div>
                <div className="border border-border rounded-sm p-4 bg-panelraised/20">
                  <div className="text-2xs uppercase tracking-wider text-faint mb-3">What to investigate</div>
                  {tactical.concerns?.length ? tactical.concerns.map((item: any) => <div key={item.component} className="flex justify-between text-xs py-2 border-b border-border last:border-0"><span className="text-muted capitalize">{item.component.replaceAll("_", " ")}</span><span className="text-riskhigh tabular">{Number(item.score).toFixed(0)}</span></div>) : <div className="text-xs text-muted">No major component gaps in available evidence.</div>}
                </div>
              </div>
            </div>
            <div className="mt-5 pt-4 border-t border-border text-2xs text-faint leading-5">{tactical.note}</div>
          </div>
        ) : <div className="p-5 text-sm text-muted">Tactical fit is unavailable for this player.</div>}
      </section>

      {/* Evidence */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EvidencePanel title="What stands out" tone="positive" items={strengths} empty="Not enough percentile evidence to identify clear strengths." />
        <EvidencePanel title="What to investigate" tone="negative" items={concerns} empty="No major statistical concerns identified from the available evidence." />
      </div>

      {/* Role + market context */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.25fr_0.75fr] gap-6">
        <section className="analytics-panel">
          <PanelHeader title="Role suitability" subtitle="Archetype fit with the evidence behind the score" />
          <div className="divide-y divide-border">
            {roles?.roles?.length > 0 ? roles.roles.slice(0, 5).map((r: any) => (
              <div key={r.role} className="p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm text-ink font-medium">{r.role}</div>
                    <div className="text-2xs text-faint mt-1">Coverage {r.coverage_pct == null ? "—" : `${Number(r.coverage_pct).toFixed(0)}%`}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xl text-accent tabular font-semibold">{num(r.role_fit_score)}</div>
                    <div className="text-2xs text-faint">fit</div>
                  </div>
                </div>
                <div className="h-1.5 bg-panelraised rounded-full overflow-hidden mt-3">
                  <div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, Number(r.role_fit_score) || 0))}%` }} />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4 text-xs">
                  <div>
                    <div className="text-2xs uppercase tracking-wider text-faint mb-1">Strengths</div>
                    <div className="text-risklow">{r.strengths?.length ? r.strengths.map((s: any) => s.feature).join(" · ") : "—"}</div>
                  </div>
                  <div>
                    <div className="text-2xs uppercase tracking-wider text-faint mb-1">Limitations</div>
                    <div className="text-riskhigh">{r.limitations?.length ? r.limitations.map((s: any) => s.feature).join(" · ") : "—"}</div>
                  </div>
                </div>
              </div>
            )) : <div className="p-5 text-sm text-muted">No applicable role archetypes for this position.</div>}
          </div>
        </section>

        <section className="analytics-panel">
          <PanelHeader title="Market context" subtitle={`Model evidence for ${selectedLabel}, not a transfer-market appraisal`} />
          <div className="p-5 space-y-5">
            <div className="grid grid-cols-2 gap-3">
              <ValueBox label="Current market" value={formatEur(player.value_eur)} />
              <ValueBox label="Model fair value" value={formatEur(player.fair_value_eur)} accent />
            </div>
            <div>
              <div className="flex justify-between text-xs mb-2"><span className="text-muted">Model value gap</span><span className="text-ink tabular">{player.value_gap_pct == null ? "—" : `${player.value_gap_pct >= 0 ? "+" : ""}${player.value_gap_pct.toFixed(1)}%`}</span></div>
              <div className="h-2 rounded-full bg-panelraised overflow-hidden">
                <div className="h-full bg-accent" style={{ width: `${Math.min(100, Math.max(0, 50 + (Number(player.value_gap_pct) || 0) / 2))}%` }} />
              </div>
            </div>
            <div className="border-t border-border pt-4 text-xs text-muted leading-5">
              Fair value is a trained-model estimate against this dataset&apos;s valuation target. Treat it as a market signal and investigate contract, availability, league context, and live-scouting evidence before acting.
            </div>
          </div>
        </section>
      </div>

      {/* Transfer intelligence */}
      <section className="analytics-panel">
        <PanelHeader title="Transfer intelligence" subtitle={`Observable recruitment economics for ${selectedLabel}`} />
        {transferIntel ? (
          <div className="p-5 space-y-5">
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
              <ValueBox label="Opportunity" value={transferIntel.opportunity_score == null ? "—" : Number(transferIntel.opportunity_score).toFixed(0)} accent />
              <ValueBox label="Market value" value={formatEur(transferIntel.market_value_eur)} />
              <ValueBox label="Fair value" value={formatEur(transferIntel.fair_value_eur)} />
              <ValueBox label="Wage" value={formatEur(transferIntel.wage_eur)} />
              <ValueBox label="Wage / value" value={transferIntel.wage_to_value_pct == null ? "—" : `${Number(transferIntel.wage_to_value_pct).toFixed(1)}%`} />
              <ValueBox label="Club moves" value={String(transferIntel.club_changes ?? 0)} />
              <ValueBox label="League moves" value={String(transferIntel.league_changes ?? 0)} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr_0.8fr] gap-5">
              <div>
                <div className="text-2xs uppercase tracking-wider text-faint mb-3">Opportunity drivers</div>
                <div className="space-y-2">
                  {Object.entries(transferIntel.components || {}).map(([key, value]: [string, any]) => (
                    <div key={key}>
                      <div className="flex justify-between text-xs mb-1"><span className="text-muted capitalize">{key.replaceAll("_", " ")}</span><span className="text-ink tabular">{Number(value).toFixed(0)}</span></div>
                      <div className="h-1.5 bg-panelraised rounded-full overflow-hidden"><div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, Number(value) || 0))}%` }} /></div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-2xs uppercase tracking-wider text-faint mb-3">Recruitment signals</div>
                <div className="space-y-2 text-xs">
                  {(transferIntel.strengths || []).map((x: string) => <div key={x} className="text-risklow">✓ {x}</div>)}
                  {(transferIntel.concerns || []).map((x: string) => <div key={x} className="text-riskhigh">⚠ {x}</div>)}
                  {!transferIntel.strengths?.length && !transferIntel.concerns?.length ? <div className="text-muted">No additional signals available.</div> : null}
                </div>
              </div>
              <div className="rounded-sm border border-border bg-panelraised p-4">
                <div className="text-2xs uppercase tracking-wider text-faint">Contract data</div>
                <div className="text-sm text-ink mt-2">Not available</div>
                <div className="text-2xs text-muted mt-2 leading-5">Contract expiry, release clause and actual transfer-fee history are not present in the FIFA/FBref dataset. They should be verified from a dedicated transfer-data source before a recruitment decision.</div>
                <div className="text-2xs text-faint mt-3">Evidence coverage: {Number(transferIntel.evidence_coverage_pct ?? 0).toFixed(0)}%</div>
              </div>
            </div>
            <div className="pt-4 border-t border-border text-2xs text-faint leading-5">{transferIntel.note}</div>
          </div>
        ) : <div className="p-5 text-sm text-muted">Transfer intelligence is unavailable for this player.</div>}
      </section>

      {/* Detailed evidence */}
      <section className="analytics-panel">
        <PanelHeader title="Detailed percentile evidence" subtitle="The underlying metrics behind the profile" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 divide-y md:divide-y-0 md:divide-x divide-border">
          {Object.entries(PERCENTILE_GROUPS).map(([group, keys]) => (
            <div key={group} className="p-5">
              <h3 className="text-xs text-ink font-medium mb-3">{group}</h3>
              <div className="space-y-3">
                {keys.map((key) => pct[key] != null ? <PercentileEvidence key={key} label={formatLabel(key)} value={Number(pct[key])} /> : null)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Similar players */}
      <section className="analytics-panel">
        <PanelHeader title="Similar players" subtitle="Multifacet similarity across statistical, tactical, physical and market dimensions" />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border">
          {similar?.results?.map((s: any) => (
            <Link key={s.player_id} href={`/players/${s.player_id}`} className="p-5 hover:bg-panelraised/50 transition-colors group">
              <div className="flex items-start justify-between gap-3">
                <div className="flex gap-3 min-w-0">
                  <PlayerAvatar name={s.short_name} small />
                  <div className="min-w-0">
                    <div className="text-sm text-ink font-medium truncate group-hover:text-accent">{s.short_name}</div>
                    <div className="text-2xs text-muted mt-1">{s.canonical_position} · {s.club_name || "—"}</div>
                  </div>
                </div>
                <div className="text-right shrink-0"><div className="text-lg text-accent tabular font-semibold">{num(s.overall_similarity)}</div><div className="text-2xs text-faint">similarity</div></div>
              </div>
              <div className="grid grid-cols-4 gap-2 mt-5">
                <SimilarityMetric label="Stat" value={s.statistical_similarity} />
                <SimilarityMetric label="Tact" value={s.tactical_similarity} />
                <SimilarityMetric label="Phys" value={s.physical_similarity} />
                <SimilarityMetric label="Market" value={s.market_similarity} />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Risk interpretation */}
      <section className="rounded-xl border border-border bg-panel p-5 lg:p-6">
        <div className="flex items-start gap-4">
          <div className="h-9 w-9 rounded-lg border border-riskmed/30 bg-riskmed/10 flex items-center justify-center text-riskmed">!</div>
          <div>
            <h2 className="text-sm text-ink font-medium">How to read recruitment uncertainty</h2>
            <p className="text-xs text-muted leading-5 mt-2 max-w-4xl">
              {player.recruitment_risk_tier || "This"} uncertainty is designed to describe <span className="text-ink">outcome volatility</span>, not the probability that the player will fail. A high tier means the range of plausible next-season outcomes is wider. Review sample reliability, availability, league transition and tactical fit alongside this signal.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function PlayerAvatar({ name, small = false }: { name?: string; small?: boolean }) {
  const initials = (name || "P").split(/\s+/).slice(0, 2).map((x) => x[0]).join("").toUpperCase();
  return <div className={`${small ? "h-10 w-10 text-xs rounded-lg" : "h-16 w-16 text-lg rounded-xl"} shrink-0 border border-accent/30 bg-accent/10 text-accent flex items-center justify-center font-semibold`}>{initials}</div>;
}

function HistoryStat({ label, value, tone }: { label: string; value: string; tone?: "positive" | "negative" }) {
  return <div className="p-4 border-r border-b border-border last:border-r-0 min-h-[78px]"><div className="text-2xs text-faint uppercase tracking-wider truncate">{label}</div><div className={`text-base tabular font-semibold mt-2 ${tone === "positive" ? "text-risklow" : tone === "negative" ? "text-riskhigh" : "text-ink"}`}>{value}</div></div>;
}

function TrajectoryLabel({ summary }: { summary: any }) {
  const change = Number(summary.performance_change);
  if (!Number.isFinite(change) || change === 0) return <span className="text-2xs text-faint border border-border rounded-full px-2 py-1">Stable / limited history</span>;
  return <span className={`text-2xs border rounded-full px-2 py-1 ${change > 0 ? "text-risklow border-risklow/30 bg-risklow/5" : "text-riskhigh border-riskhigh/30 bg-riskhigh/5"}`}>{change > 0 ? "Improving" : "Declining"} · {Math.abs(change).toFixed(1)} pts</span>;
}

function HistoryContext({ label, values, fallback }: { label: string; values?: string[]; fallback: string }) {
  const unique = Array.from(new Set(values || []));
  return <div className="border border-border rounded-lg p-3"><div className="text-2xs text-faint uppercase tracking-wider mb-2">{label}</div>{unique.length ? <div className="flex flex-wrap gap-1.5">{unique.map((v) => <span key={v} className="text-2xs text-muted bg-panelraised border border-border rounded px-2 py-1">{v}</span>)}</div> : <div className="text-xs text-faint">{fallback}</div>}</div>;
}

function formatCompactEur(value: number) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (Math.abs(n) >= 1_000_000) return `€${(n / 1_000_000).toFixed(0)}M`;
  if (Math.abs(n) >= 1_000) return `€${(n / 1_000).toFixed(0)}K`;
  return `€${n.toFixed(0)}`;
}

function MarketTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return <div className="rounded-lg border border-border bg-panel px-3 py-2 shadow-xl"><div className="text-2xs text-faint mb-1">{label}</div>{payload.map((p: any) => <div key={p.dataKey} className="flex gap-3 justify-between text-xs"><span className="text-muted">{p.name}</span><span className="text-ink tabular">{formatCompactEur(p.value)}</span></div>)}</div>;
}


function PotentialStat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return <div className="p-4 border-r border-border last:border-r-0"><div className="text-2xs text-faint uppercase tracking-wider">{label}</div><div className={`text-xl font-semibold tabular mt-1 ${muted ? "text-muted" : "text-ink"}`}>{value}</div></div>;
}

function PotentialInsight({ title, text }: { title: string; text: string }) {
  return <div className="rounded-lg border border-border bg-panelraised/30 p-3"><div className="text-2xs uppercase tracking-wider text-accent">{title}</div><p className="text-xs text-muted leading-5 mt-2">{text}</p></div>;
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-2 last:border-0 last:pb-0"><span className="text-xs text-muted">{label}</span><span className="text-xs text-ink tabular capitalize">{value}</span></div>;
}

function DecisionMetric({ label, value, sub, delta }: { label: string; value: string; sub?: string; delta?: number | null }) {
  return <div className="border border-border bg-panelraised/50 rounded-lg px-3 py-3 min-h-[84px]">
    <div className="text-2xs text-faint uppercase tracking-wider truncate">{label}</div>
    <div className="text-lg text-ink tabular font-semibold mt-2 truncate">{value}</div>
    {delta != null ? <div className={`text-2xs mt-1 ${delta >= 0 ? "text-risklow" : "text-riskhigh"}`}>{delta >= 0 ? "↑" : "↓"} {Math.abs(delta).toFixed(1)} vs prior</div> : sub ? <div className="text-2xs text-muted mt-1 truncate">{sub}</div> : null}
  </div>;
}

function PanelHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return <div className="px-5 pt-5 pb-3 border-b border-border"><h2 className="text-sm text-ink font-medium">{title}</h2>{subtitle && <p className="text-2xs text-faint mt-1">{subtitle}</p>}</div>;
}

function EvidencePanel({ title, tone, items, empty }: { title: string; tone: "positive" | "negative"; items: string[]; empty: string }) {
  return <section className="analytics-panel p-5"><div className="flex items-center gap-2 mb-4"><span className={`h-2 w-2 rounded-full ${tone === "positive" ? "bg-risklow" : "bg-riskhigh"}`} /><h2 className="text-sm text-ink font-medium">{title}</h2></div>{items.length ? <div className="space-y-2">{items.map((item) => <div key={item} className="text-xs text-muted border border-border bg-panelraised/40 rounded-lg px-3 py-2.5">{item}</div>)}</div> : <p className="text-xs text-faint">{empty}</p>}</section>;
}

function ValueBox({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return <div className="border border-border rounded-lg p-4"><div className="text-2xs text-faint">{label}</div><div className={`text-xl tabular font-semibold mt-2 ${accent ? "text-accent" : "text-ink"}`}>{value}</div></div>;
}

function PercentileEvidence({ label, value }: { label: string; value: number }) {
  const v = Math.max(0, Math.min(100, value));
  return <div><div className="flex justify-between text-2xs mb-1.5"><span className="text-muted truncate mr-2">{label}</span><span className="text-ink tabular">{v.toFixed(0)}</span></div><div className="h-1.5 bg-panelraised rounded-full overflow-hidden"><div className={`h-full ${v >= 70 ? "bg-risklow" : v >= 40 ? "bg-riskmed" : "bg-riskhigh"}`} style={{ width: `${v}%` }} /></div></div>;
}

function SimilarityMetric({ label, value }: { label: string; value?: number }) { return <div><div className="text-2xs text-faint">{label}</div><div className="text-xs text-muted tabular mt-1">{value == null ? "—" : value.toFixed(0)}</div></div>; }
function LegendDot({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) { return <span className="flex items-center gap-1.5"><span className={`w-4 border-t-2 ${dashed ? "border-dashed" : ""}`} style={{ borderColor: color }} />{label}</span>; }
function EmptyChart({ text }: { text: string }) { return <div className="h-full flex items-center justify-center text-xs text-faint">{text}</div>; }
function ChartTooltip({ active, payload, label }: any) { if (!active || !payload?.length) return null; return <div className="rounded-lg border border-border bg-panel px-3 py-2 shadow-xl"><div className="text-2xs text-faint mb-1">{label}</div>{payload.map((p: any) => <div key={p.dataKey} className="flex gap-3 justify-between text-xs"><span className="text-muted">{p.name}</span><span className="text-ink tabular">{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</span></div>)}</div>; }

function buildRadarData(percentiles: Record<string, number>) {
  return Object.entries(PERCENTILE_GROUPS).map(([group, keys]) => {
    const values = keys.map((key) => percentiles[key]).filter((v) => typeof v === "number" && Number.isFinite(v));
    return values.length ? { metric: group, value: Math.round(values.reduce((a, b) => a + b, 0) / values.length) } : null;
  }).filter(Boolean) as { metric: string; value: number }[];
}

function getStrengths(player: any, pct: Record<string, number>) {
  const labels = Object.entries(pct).filter(([, v]) => typeof v === "number" && v >= 80).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, 5).map(([key, v]) => `${formatLabel(key)} — ${Number(v).toFixed(0)}th percentile`);
  if (labels.length) return labels;
  if (player.performance_score >= 80) return ["Strong overall performance score in the current dataset."];
  return [];
}

function getConcerns(player: any, pct: Record<string, number>) {
  const labels = Object.entries(pct).filter(([, v]) => typeof v === "number" && v < 30).sort((a, b) => Number(a[1]) - Number(b[1])).slice(0, 5).map(([key, v]) => `${formatLabel(key)} — ${Number(v).toFixed(0)}th percentile`);
  if (player.sample_reliability_tier === "LOW") labels.unshift("Limited sample reliability — interpret performance metrics cautiously.");
  if (player.position_data_conflict) labels.push("Position data conflict detected — verify role manually.");
  return labels.slice(0, 5);
}

function formatLabel(key: string): string { return key.replace("per_90_minutes_", "").replace(/_/g, " "); }
function num(value: any): string { return value == null || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(1); }
