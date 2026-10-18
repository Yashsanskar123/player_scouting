"use client";

import { ValidationNotice } from "@/components/ValidationBadge";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  AreaChart,
  Area,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";


function num(v: any, digits = 0) {
  return v == null || Number.isNaN(Number(v))
    ? "—"
    : Number(v).toFixed(digits);
}


function pct(v: any) {
  return v == null || Number.isNaN(Number(v))
    ? "—"
    : `${Number(v).toFixed(0)}%`;
}


function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "positive" | "negative";
}) {
  const cls =
    tone === "positive"
      ? "text-risklow border-risklow/40 bg-risklow/10"
      : tone === "negative"
      ? "text-riskhigh border-riskhigh/40 bg-riskhigh/10"
      : "text-muted border-border bg-panelraised";

  return (
    <span
      className={`inline-block px-2 py-1 rounded-sm text-2xs border ${cls}`}
    >
      {children}
    </span>
  );
}


function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="border-r last:border-r-0 border-border px-4 py-3">
      <div className="text-2xs text-faint mb-1">
        {label}
      </div>

      <div className="text-xl text-ink tabular font-medium">
        {value}
      </div>

      {sub && (
        <div className="text-2xs text-faint mt-1">
          {sub}
        </div>
      )}
    </div>
  );
}


function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="analytics-panel">
      <div className="px-5 py-4 border-b border-border">
        <h2 className="text-sm text-ink font-medium">
          {title}
        </h2>

        {subtitle && (
          <p className="text-2xs text-faint mt-1">
            {subtitle}
          </p>
        )}
      </div>

      {children}
    </section>
  );
}


export default function DevelopmentLabPage() {
  const {
    selectedSeason,
    selectedLabel,
  } = useSeason();

  const [query, setQuery] = useState("");
  const [players, setPlayers] = useState<any[]>([]);
  const [playerId, setPlayerId] = useState("");

  const [data, setData] = useState<any>(null);

  const [loadingPlayers, setLoadingPlayers] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] = useState("");


  useEffect(() => {
    if (selectedSeason == null) return;

    setLoadingPlayers(true);

    api
      .listPlayers({
        page: 1,
        page_size: 20,
        season: selectedSeason,
        search: query,
        sort_by: "performance_score",
        descending: 1,
      })
      .then((r) => setPlayers(r.results || []))
      .catch(() => setPlayers([]))
      .finally(() => setLoadingPlayers(false));
  }, [selectedSeason, query]);


  useEffect(() => {
    if (!playerId || selectedSeason == null) {
      return;
    }

    setLoading(true);
    setError("");

    api
      .getDevelopmentLab(
        playerId,
        selectedSeason
      )
      .then(setData)
      .catch((e) => {
        setData(null);

        setError(
          e instanceof Error
            ? e.message
            : "Development analysis failed."
        );
      })
      .finally(() => setLoading(false));
  }, [playerId, selectedSeason]);


  const outlook = data?.outlook;

  const directionTone =
    outlook?.trajectory === "rising"
      ? "positive"
      : outlook?.trajectory === "falling"
      ? "negative"
      : "neutral";


  const chartData = useMemo(
    () =>
      (data?.trajectory || []).map((r: any) => ({
        season: String(r.season),
        observed: r.performance,
        expected: r.expected_12m,
      })),
    [data]
  );


  return (
    <div className="space-y-6 pb-10">

      {/* Header */}

      <header>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">

          <div>
            <div className="text-2xs uppercase tracking-[0.18em] text-accent">
              Development intelligence
            </div>

            <h1 className="text-2xl text-ink font-medium mt-1">
              Development Lab
            </h1>

            <p className="text-muted text-sm mt-1">
              Understand the player's development path,
              intervention priorities and evidence quality.
            </p>

            <ValidationNotice keys={["development_potential", "expected_performance_12m", "potential_24m", "breakout_probability", "decline_probability"]} />
          </div>

          <div className="text-xs text-faint">
            Analysis season · {selectedLabel}
          </div>

        </div>
      </header>


      {/* Player selector */}

      <section className="border border-border rounded-sm bg-panel p-4">

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-3">

          <div>
            <label className="text-2xs text-faint block mb-1">
              Find player
            </label>

            <input
              value={query}
              onChange={(e) =>
                setQuery(e.target.value)
              }
              placeholder="Search player name..."
              className="w-full bg-panelraised border border-border rounded-sm px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            />
          </div>


          <div>
            <label className="text-2xs text-faint block mb-1">
              Player
            </label>

            <select
              value={playerId}
              onChange={(e) =>
                setPlayerId(e.target.value)
              }
              className="w-full bg-panelraised border border-border rounded-sm px-3 py-2 text-sm text-ink"
            >
              <option value="">
                {loadingPlayers
                  ? "Loading players…"
                  : "Select a player"}
              </option>

              {players.map((p) => (
                <option
                  key={p.player_id}
                  value={p.player_id}
                >
                  {p.short_name} ·{" "}
                  {p.canonical_position || "—"} ·{" "}
                  {p.club_name || "—"}
                </option>
              ))}
            </select>
          </div>

        </div>

      </section>


      {error && <ErrorState message={error} />}

      {loading && (
        <LoadingState label="Building development intelligence" />
      )}


      {!data && !loading && !error && (
        <div className="border border-dashed border-border rounded-sm p-12 text-center">

          <div className="text-ink text-sm">
            Select a player to open the Development Lab
          </div>

          <div className="text-muted text-xs mt-2">
            This page intentionally focuses on development
            decisions rather than repeating the Player Profile.
          </div>

        </div>
      )}


      {data && !loading && (

        <div className="space-y-6">

          {/* Development Outlook */}

          <section className="rounded-xl border border-border bg-panel overflow-hidden">

            <div className="h-1 bg-accent" />

            <div className="p-5">

              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">

                <div>

                  <div className="flex items-center gap-2 mb-2">

                    <span className="text-2xs uppercase tracking-[0.16em] text-accent">
                      Development case
                    </span>

                    <Badge tone={directionTone}>
                      {outlook?.trajectory || "unknown"}
                    </Badge>

                  </div>

                  <h2 className="text-2xl text-ink font-semibold">
                    {data.player?.short_name}
                  </h2>

                  <p className="text-muted text-sm mt-1">
                    {data.player?.canonical_position || "—"}
                    {" · "}
                    {data.player?.club_name || "—"}
                    {" · Age "}
                    {data.player?.age_fifa ?? "—"}
                  </p>

                </div>

                <div className="text-right text-xs text-faint">
                  Evidence:{" "}
                  {outlook?.projection_status?.replaceAll(
                    "_",
                    " "
                  ) || "—"}
                </div>

              </div>


              <div className="grid grid-cols-2 md:grid-cols-4 border border-border mt-5">

                <Stat
                  label="Current level"
                  value={num(outlook?.current, 1)}
                />

                <Stat
                  label="12M expected"
                  value={num(outlook?.expected_12m, 1)}
                  sub="validated estimator"
                />

                <Stat
                  label="24M projection"
                  value={num(outlook?.projection_24m, 1)}
                  sub="exploratory"
                />

                <Stat
                  label="Development potential"
                  value={num(
                    outlook?.development_potential,
                    1
                  )}
                />

              </div>

            </div>

          </section>


          {/* Trajectory */}

          <Section
            title="Development trajectory"
            subtitle="Observed performance is separated from forward-looking signals."
          >

            <div className="p-5">

              <div className="h-72">

                <ResponsiveContainer
                  width="100%"
                  height="100%"
                >

                  <AreaChart
                    data={chartData}
                    margin={{
                      top: 8,
                      right: 12,
                      left: -20,
                      bottom: 0,
                    }}
                  >

                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="currentColor"
                      opacity={0.08}
                    />

                    <XAxis
                      dataKey="season"
                      tick={{ fontSize: 11 }}
                    />

                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 11 }}
                    />

                    <Tooltip />

                    <Area
                      type="monotone"
                      dataKey="observed"
                      name="Observed performance"
                      stroke="currentColor"
                      fill="currentColor"
                      fillOpacity={0.08}
                    />

                    <Area
                      type="monotone"
                      dataKey="expected"
                      name="12M expected"
                      stroke="currentColor"
                      strokeDasharray="5 5"
                      fill="none"
                    />

                  </AreaChart>

                </ResponsiveContainer>

              </div>


              <div className="flex flex-wrap gap-5 text-2xs text-faint mt-3">

                <span>
                  Observed change vs previous season:{" "}
                  <b className="text-ink">
                    {data.observed_change == null
                      ? "—"
                      : `${
                          data.observed_change > 0
                            ? "+"
                            : ""
                        }${data.observed_change}`}
                  </b>
                </span>

                <span>
                  Seasons observed:{" "}
                  <b className="text-ink">
                    {data.evidence?.seasons_observed ?? "—"}
                  </b>
                </span>

              </div>

            </div>

          </Section>


          {/* Priorities + Strengths */}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

            <Section
              title="Development priorities"
              subtitle="Lowest relevant positional peer percentiles — these are investigation priorities, not prescriptions."
            >

              <div className="divide-y divide-border">

                {(data.development_priorities || []).length === 0 ? (

                  <div className="p-5 text-sm text-muted">
                    No sufficiently supported development
                    priority is available.
                  </div>

                ) : (

                  data.development_priorities.map(
                    (x: any, i: number) => (

                      <div
                        key={x.metric}
                        className="p-4 flex items-center justify-between gap-4"
                      >

                        <div>

                          <div className="text-xs text-ink">
                            {i + 1}. {x.label}
                          </div>

                          <div className="text-2xs text-faint mt-1 capitalize">
                            {x.group}
                          </div>

                        </div>

                        <div className="text-right">

                          <div className="text-sm tabular text-ink">
                            {num(x.percentile)}
                          </div>

                          <div className="text-2xs text-faint">
                            peer percentile
                          </div>

                        </div>

                      </div>

                    )
                  )

                )}

              </div>

            </Section>


            <Section
              title="Strengths to preserve"
              subtitle="Strongest relevant peer-percentile evidence worth protecting during development."
            >

              <div className="divide-y divide-border">

                {(data.strengths_to_preserve || []).map(
                  (x: any) => (

                    <div
                      key={x.metric}
                      className="p-4 flex items-center justify-between gap-4"
                    >

                      <div>

                        <div className="text-xs text-ink">
                          {x.label}
                        </div>

                        <div className="text-2xs text-faint mt-1 capitalize">
                          {x.group}
                        </div>

                      </div>

                      <div className="text-sm tabular text-ink">
                        {num(x.percentile)}
                        <span className="text-2xs text-faint ml-1">
                          pct
                        </span>
                      </div>

                    </div>

                  )
                )}

              </div>

            </Section>

          </div>


          {/* Role Evolution */}

          <Section
            title="Role evolution"
            subtitle="Current position and the existing role-fit evidence; no tracking-data assumptions."
          >

            <div className="p-5">

              <div className="mb-4 text-xs text-muted">

                Current position ·{" "}

                <span className="text-ink">
                  {data.role_evolution?.current_position ||
                    "—"}
                </span>

              </div>


              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">

                {(data.role_evolution?.roles || []).map(
                  (r: any) => (

                    <div
                      key={r.role}
                      className="border border-border bg-panelraised rounded-sm p-4"
                    >

                      <div className="text-xs text-ink">
                        {r.role}
                      </div>

                      <div className="text-2xl text-ink tabular mt-2">
                        {num(r.role_fit_score, 1)}
                      </div>

                      <div className="text-2xs text-faint mt-1">
                        role fit ·{" "}
                        {num(r.coverage_pct)}%
                        {" "}
                        coverage
                      </div>

                      {r.strengths?.length ? (
                        <div className="text-2xs text-muted mt-3">
                          {r.strengths
                            .slice(0, 2)
                            .join(" · ")}
                        </div>
                      ) : null}

                    </div>

                  )
                )}

              </div>

            </div>

          </Section>


          {/* Investment + Risks */}

          <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">

            <Section
              title="Investment case"
              subtitle="Evidence-led context for deciding whether development resources are warranted."
            >

              <div className="p-5 space-y-3">

                {(data.development_case || []).map(
                  (x: string, i: number) => (

                    <div
                      key={i}
                      className="flex gap-3 text-sm text-muted"
                    >
                      <span className="text-accent">
                        •
                      </span>

                      <span>{x}</span>
                    </div>

                  )
                )}


                <div className="pt-3 border-t border-border flex flex-wrap gap-2">

                  <Link
                    href={`/players/${data.player?.player_id}`}
                    className="action-button"
                  >
                    Open full profile
                  </Link>

                  <Link
                    href={`/scouting/compare?player=${data.player?.player_id}`}
                    className="action-button"
                  >
                    Compare player
                  </Link>

                </div>

              </div>

            </Section>


            <Section
              title="Development risks"
              subtitle="Only risks that can materially affect the development decision."
            >

              <div className="p-5 space-y-2">

                {(data.risks || []).length === 0 ? (

                  <Badge tone="positive">
                    No material development risk signal surfaced
                  </Badge>

                ) : (

                  data.risks.map((x: string) => (

                    <div
                      key={x}
                      className="text-xs text-muted border border-border bg-panelraised rounded-sm px-3 py-2"
                    >
                      {x}
                    </div>

                  ))

                )}

              </div>

            </Section>

          </div>


          {/* Evidence */}

          <Section title="Evidence & model boundary">

            <div className="grid grid-cols-2 md:grid-cols-4 border-b border-border">

              <Stat
                label="Evidence seasons"
                value={
                  data.evidence?.seasons_observed ?? "—"
                }
              />

              <Stat
                label="Reliability"
                value={num(
                  data.evidence?.sample_reliability_score,
                  0
                )}
                sub={
                  data.evidence
                    ?.sample_reliability_tier || "—"
                }
              />

              <Stat
                label="Breakout rate"
                value={pct(
                  outlook?.breakout_probability
                )}
                sub="historical cohort"
              />

              <Stat
                label="Decline rate"
                value={pct(
                  outlook?.decline_probability
                )}
                sub="historical cohort"
              />

            </div>


            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-3 text-2xs text-faint leading-5">

              {Object.values(
                data.methodology || {}
              ).map(
                (x: any, i: number) => (
                  <div key={i}>
                    • {x}
                  </div>
                )
              )}

            </div>

          </Section>

        </div>

      )}

    </div>
  );
}