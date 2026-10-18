"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ResponsiveContainer,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
} from "recharts";

import { api, formatEur, PlayerSummary } from "@/lib/api";
import { PlayerPicker } from "@/components/PlayerPicker";
import {
  RiskBadge,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";

const PLAYER_COLORS = [
  "#D9A441",
  "#5EA7FF",
  "#6FD08C",
  "#C084FC",
  "#F27C8D",
];

type ViewMode =
  | "overview"
  | "performance"
  | "recruitment"
  | "percentiles";

export default function ComparePage() {
  const [selected, setSelected] = useState<PlayerSummary[]>([]);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [viewMode, setViewMode] =
    useState<ViewMode>("overview");

  const [selectedMetric, setSelectedMetric] =
    useState<string>("performance_score");

  const {
    selectedSeason,
    selectedLabel,
  } = useSeason();

  function addPlayer(p: PlayerSummary) {
    if (selected.length >= 5) return;

    if (
      selected.some(
        (s) => s.player_id === p.player_id
      )
    ) {
      return;
    }

    setSelected([...selected, p]);
    setResult(null);
  }

  function removePlayer(playerId: string) {
    setSelected(
      selected.filter(
        (s) => s.player_id !== playerId
      )
    );

    setResult(null);
  }

  async function runCompare() {
    if (
      selected.length < 2 ||
      selectedSeason === null
    ) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const comparison =
        await api.comparePlayers(
          selected.map(
            (s) => s.player_id
          ),
          selectedSeason
        );

      setResult(comparison);

      const firstMetric =
        buildDecisionMatrix(comparison)[0];

      if (firstMetric) {
        setSelectedMetric(firstMetric.field);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setResult(null);
  }, [selectedSeason]);

  const metricOptions = useMemo(() => {
    return buildDecisionMatrix(result);
  }, [result]);

  const selectedMetricRow = useMemo(() => {
    return metricOptions.find(
      (m: any) =>
        m.field === selectedMetric
    );
  }, [metricOptions, selectedMetric]);

  const radarData = useMemo(() => {
    if (
      !result?.percentile_comparison?.length
    ) {
      return [];
    }

    return result.percentile_comparison.map(
      (row: any) => ({
        metric: formatRadarLabel(
          row.metric
        ),
        ...row.values,
      })
    );
  }, [result]);

  const metricChartData = useMemo(() => {
    if (!selectedMetricRow) {
      return [];
    }

    return result.players.map(
      (player: any) => ({
        name: player.short_name,
        value:
          selectedMetricRow.values[
            player.player_id
          ],
        playerId: player.player_id,
      })
    );
  }, [
    result,
    selectedMetricRow,
  ]);

  const tradeoffData = useMemo(() => {
    if (!result?.players) {
      return [];
    }

    return result.players
      .map((player: any) => ({
        name: player.short_name,
        playerId: player.player_id,
        performance:
          numeric(player.performance_score),
        potential:
          numeric(
            player.development_potential
          ),
        valueGap:
          numeric(player.value_gap_pct),
        minutes:
          numeric(player.playing_time_min),
      }))
      .filter(
        (x: any) =>
          x.performance !== null &&
          x.potential !== null
      );
  }, [result]);

  return (
    <div className="space-y-6">

      {/* ====================================================== */}
      {/* PAGE HEADER */}
      {/* ====================================================== */}

      <header>
        <div className="flex flex-col xl:flex-row xl:items-end xl:justify-between gap-5">

          <div>
            <div className="text-2xs uppercase tracking-[0.18em] text-accent mb-2">
              Recruitment intelligence
            </div>

            <h1 className="text-2xl text-ink font-semibold tracking-tight">
              Player Comparison
            </h1>

            <p className="text-muted text-sm mt-1 max-w-3xl">
              Explore performance, development,
              tactical profile, market value and
              evidence side-by-side for the
              {selectedLabel}.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1.5 rounded-full border border-border bg-panel text-2xs text-muted">
              Analysis season
            </span>

            <span className="px-2.5 py-1.5 rounded-full border border-accent/30 bg-accent/10 text-2xs text-accent font-medium">
              {selectedLabel}
            </span>
          </div>

        </div>
      </header>


      {/* ====================================================== */}
      {/* PLAYER SELECTION */}
      {/* ====================================================== */}

      <section className="analytics-panel">

        <div className="p-5">

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">

            <div>
              <div className="text-xs text-ink font-medium">
                Build comparison set
              </div>

              <div className="text-2xs text-faint mt-1">
                Select 2–5 players from the same
                analysis season.
              </div>
            </div>

            <div className="w-full lg:w-[420px]">
              <PlayerPicker
                season={selectedSeason}
                onSelect={addPlayer}
                placeholder="Search player to add..."
              />
            </div>

          </div>


          {selected.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-5">

              {selected.map(
                (player, index) => (
                  <div
                    key={player.player_id}
                    className="group flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-panelraised"
                  >

                    <span
                      className="w-2 h-2 rounded-full"
                      style={{
                        background:
                          PLAYER_COLORS[
                            index
                          ],
                      }}
                    />

                    <span className="text-xs text-ink">
                      {player.short_name}
                    </span>

                    <button
                      onClick={() =>
                        removePlayer(
                          player.player_id
                        )
                      }
                      className="text-faint hover:text-riskhigh transition-colors"
                    >
                      ×
                    </button>

                  </div>
                )
              )}

            </div>
          )}

          {selected.length === 0 && (
            <div className="mt-5 border border-dashed border-border rounded-lg p-6 text-center">
              <div className="text-sm text-ink">
                Add players to begin
              </div>

              <div className="text-2xs text-faint mt-1">
                Compare up to five players across
                recruitment dimensions.
              </div>
            </div>
          )}


          <div className="flex flex-wrap items-center gap-3 mt-5">

            <button
              onClick={runCompare}
              disabled={
                selected.length < 2 ||
                loading
              }
              className="action-button action-button-primary disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading
                ? "Building comparison…"
                : `Analyse comparison${
                    selected.length >= 2
                      ? ` (${selected.length})`
                      : ""
                  }`}
            </button>

            <span className="text-2xs text-faint">
              {selected.length}/5 players selected
            </span>

          </div>

        </div>

      </section>


      {loading && (
        <LoadingState label="Building recruitment comparison" />
      )}

      {error && (
        <ErrorState message={error} />
      )}


      {/* ====================================================== */}
      {/* RESULTS */}
      {/* ====================================================== */}

      {result && (

        <div className="space-y-6">

          {/* ================================================== */}
          {/* PLAYER IDENTITY CARDS */}
          {/* ================================================== */}

          <section>

            <SectionHeading
              kicker="HEAD-TO-HEAD"
              title="Player profiles"
              subtitle="Start with the player context before diving into the numbers."
            />

            <div
              className="grid gap-3"
              style={{
                gridTemplateColumns:
                  `repeat(${result.players.length}, minmax(0, 1fr))`,
              }}
            >

              {result.players.map(
                (player: any, index: number) => (
                  <PlayerHeroCard
                    key={player.player_id}
                    player={player}
                    index={index}
                  />
                )
              )}

            </div>

          </section>


          {/* ================================================== */}
          {/* KPI STRIP */}
          {/* ================================================== */}

          <section className="analytics-panel">

            <div className="px-5 pt-5 pb-3">

              <div className="text-xs text-ink font-medium">
                Recruitment signal snapshot
              </div>

              <div className="text-2xs text-faint mt-1">
                Current-season evidence across the
                core decision dimensions.
              </div>

            </div>

            <div
              className="grid border-t border-border"
              style={{
                gridTemplateColumns:
                  `repeat(${result.players.length}, minmax(0, 1fr))`,
              }}
            >

              {result.players.map(
                (player: any, index: number) => (
                  <div
                    key={player.player_id}
                    className="p-5 border-r last:border-r-0 border-border"
                  >

                    <div className="flex items-center justify-between mb-4">

                      <span className="text-xs text-ink font-medium">
                        {player.short_name}
                      </span>

                      <span
                        className="w-2 h-2 rounded-full"
                        style={{
                          background:
                            PLAYER_COLORS[
                              index
                            ],
                        }}
                      />

                    </div>

                    <Kpi
                      label="Performance"
                      value={numberOrDash(
                        player.performance_score
                      )}
                    />

                    <Kpi
                      label="12M expected"
                      value={numberOrDash(
                        player.expected_performance_12m
                      )}
                    />

                    <Kpi
                      label="Potential"
                      value={numberOrDash(
                        player.development_potential
                      )}
                    />

                    <Kpi
                      label="Adjusted performance"
                      value={numberOrDash(
                        player.adjusted_performance_score
                      )}
                    />

                  </div>
                )
              )}

            </div>

          </section>


          {/* ================================================== */}
          {/* VIEW NAVIGATION */}
          {/* ================================================== */}

          <div className="flex flex-wrap gap-2">

            <ViewButton
              active={
                viewMode === "overview"
              }
              onClick={() =>
                setViewMode("overview")
              }
            >
              Overview
            </ViewButton>

            <ViewButton
              active={
                viewMode === "performance"
              }
              onClick={() =>
                setViewMode("performance")
              }
            >
              Performance
            </ViewButton>

            <ViewButton
              active={
                viewMode === "recruitment"
              }
              onClick={() =>
                setViewMode("recruitment")
              }
            >
              Recruitment
            </ViewButton>

            <ViewButton
              active={
                viewMode === "percentiles"
              }
              onClick={() =>
                setViewMode("percentiles")
              }
            >
              Player profile
            </ViewButton>

          </div>


          {/* ================================================== */}
          {/* OVERVIEW */}
          {/* ================================================== */}

          {viewMode === "overview" && (

            <div className="space-y-6">

              {/* ---------------------------------------------- */}
              {/* RADAR + METRIC EXPLORER */}
              {/* ---------------------------------------------- */}

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

                <section className="analytics-panel">

                  <div className="p-5 border-b border-border">

                    <div className="text-xs text-ink font-medium">
                      Player profile radar
                    </div>

                    <div className="text-2xs text-faint mt-1">
                      Percentile profile across the
                      shared statistical dimensions.
                    </div>

                  </div>

                  <div className="h-[390px] p-4">

                    {radarData.length ? (

                      <ResponsiveContainer
                        width="100%"
                        height="100%"
                      >

                        <RadarChart
                          data={radarData}
                          outerRadius="72%"
                        >

                          <PolarGrid
                            stroke="#26313D"
                          />

                          <PolarAngleAxis
                            dataKey="metric"
                            tick={{
                              fill: "#AEB7C3",
                              fontSize: 10,
                            }}
                          />

                          <PolarRadiusAxis
                            domain={[0, 100]}
                            tick={{
                              fill: "#596675",
                              fontSize: 9,
                            }}
                          />

                          {result.players.map(
                            (
                              player: any,
                              index: number
                            ) => (
                              <Radar
                                key={
                                  player.player_id
                                }
                                name={
                                  player.short_name
                                }
                                dataKey={
                                  player.player_id
                                }
                                stroke={
                                  PLAYER_COLORS[
                                    index
                                  ]
                                }
                                fill={
                                  PLAYER_COLORS[
                                    index
                                  ]
                                }
                                fillOpacity={0.08}
                                strokeWidth={2}
                              />
                            )
                          )}

                          <Tooltip
                            contentStyle={{
                              background:
                                "#10151C",
                              border:
                                "1px solid #2A3441",
                              borderRadius:
                                8,
                              fontSize: 11,
                            }}
                          />

                        </RadarChart>

                      </ResponsiveContainer>

                    ) : (

                      <EmptyState
                        title="No shared percentile profile"
                        body="The selected players do not have enough common percentile evidence."
                      />

                    )}

                  </div>

                  <div className="px-5 pb-5 flex flex-wrap gap-x-5 gap-y-2">

                    {result.players.map(
                      (
                        player: any,
                        index: number
                      ) => (
                        <div
                          key={
                            player.player_id
                          }
                          className="flex items-center gap-2 text-2xs text-muted"
                        >

                          <span
                            className="w-2 h-2 rounded-full"
                            style={{
                              background:
                                PLAYER_COLORS[
                                  index
                                ],
                            }}
                          />

                          {player.short_name}

                        </div>
                      )
                    )}

                  </div>

                </section>


                {/* METRIC EXPLORER */}

                <section className="analytics-panel">

                  <div className="p-5 border-b border-border">

                    <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">

                      <div>
                        <div className="text-xs text-ink font-medium">
                          Interactive metric explorer
                        </div>

                        <div className="text-2xs text-faint mt-1">
                          Select a recruitment dimension and inspect the
                          relative difference between the selected players.
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-2xs text-faint">
                          Compare
                        </span>

                        <div className="relative">
                          <select
                            value={selectedMetric}
                            onChange={(e) => {
                              setSelectedMetric(e.target.value);
                            }}
                            className="appearance-none min-w-[230px] bg-panelraised border border-border rounded-lg px-3 pr-9 py-2.5 text-xs text-ink outline-none focus:border-accent cursor-pointer"
                          >
                            {metricOptions.map((metric: any) => (
                              <option
                                key={metric.field}
                                value={metric.field}
                              >
                                {metric.metric}
                              </option>
                            ))}
                          </select>

                          <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-faint text-xs">
                            ▾
                          </div>
                        </div>
                      </div>

                    </div>

                  </div>

                  {selectedMetricRow ? (

                    <div className="p-5">

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">

                        {result.players.map(
                          (player: any, index: number) => {
                            const value = numeric(
                              selectedMetricRow.values[
                                player.player_id
                              ]
                            );

                            return (
                              <div
                                key={player.player_id}
                                className="rounded-xl border border-border bg-panelraised/40 p-5"
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className="w-2.5 h-2.5 rounded-full"
                                      style={{
                                        background:
                                          PLAYER_COLORS[index],
                                      }}
                                    />

                                    <span className="text-xs text-ink font-medium">
                                      {player.short_name}
                                    </span>
                                  </div>

                                  <span className="text-2xl text-ink font-semibold tabular">
                                    {formatMetric(
                                      selectedMetricRow.field,
                                      value
                                    )}
                                  </span>
                                </div>

                                <div className="mt-5">
                                  <div className="h-3 rounded-full bg-panel overflow-hidden">
                                    <div
                                      className="h-full rounded-full transition-all duration-500"
                                      style={{
                                        width:
                                          `${Math.max(
                                            4,
                                            Math.min(
                                              100,
                                              normalizeMetricValue(
                                                value,
                                                selectedMetricRow
                                              )
                                            )
                                          )}%`,
                                        background:
                                          PLAYER_COLORS[index],
                                      }}
                                    />
                                  </div>
                                </div>

                                <div className="mt-3 flex justify-between">
                                  <span className="text-2xs text-faint">
                                    {selectedMetricRow.metric}
                                  </span>

                                  <span className="text-2xs text-muted">
                                    {metricPosition(
                                      value,
                                      selectedMetricRow
                                    )}
                                  </span>
                                </div>
                              </div>
                            );
                          }
                        )}

                      </div>

                      <div className="rounded-xl border border-border p-5">

                        <div className="flex items-center justify-between mb-5">
                          <div>
                            <div className="text-xs text-ink font-medium">
                              Relative positioning
                            </div>

                            <div className="text-2xs text-faint mt-1">
                              Players are positioned against the observed
                              range for this metric.
                            </div>
                          </div>

                          <div className="text-2xs text-faint">
                            Observed range:&nbsp;
                            <span className="text-muted">
                              {formatMetric(
                                selectedMetricRow.field,
                                selectedMetricRow.range?.min
                              )}
                              {" — "}
                              {formatMetric(
                                selectedMetricRow.field,
                                selectedMetricRow.range?.max
                              )}
                            </span>
                          </div>
                        </div>

                        <div className="space-y-6">

                          {result.players.map(
                            (player: any, index: number) => {
                              const value = numeric(
                                selectedMetricRow.values[
                                  player.player_id
                                ]
                              );

                              const position = normalizeMetricValue(
                                value,
                                selectedMetricRow
                              );

                              return (
                                <div key={player.player_id}>
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <span
                                        className="w-2 h-2 rounded-full"
                                        style={{
                                          background:
                                            PLAYER_COLORS[index],
                                        }}
                                      />

                                      <Link
                                        href={`/players/${player.player_id}`}
                                        className="text-xs text-ink hover:text-accent"
                                      >
                                        {player.short_name}
                                      </Link>
                                    </div>

                                    <span className="text-xs text-ink tabular">
                                      {formatMetric(
                                        selectedMetricRow.field,
                                        value
                                      )}
                                    </span>
                                  </div>

                                  <div className="relative h-4">
                                    <div className="absolute top-1/2 left-0 right-0 h-1.5 -translate-y-1/2 rounded-full bg-panelraised" />

                                    {[25, 50, 75].map((mark) => (
                                      <div
                                        key={mark}
                                        className="absolute top-0 bottom-0 w-px bg-border"
                                        style={{ left: `${mark}%` }}
                                      />
                                    ))}

                                    <div
                                      className="absolute top-1/2 w-5 h-5 rounded-full border-2 border-panel -translate-y-1/2 -translate-x-1/2 shadow-lg transition-all duration-500"
                                      style={{
                                        left:
                                          `${Math.max(
                                            2,
                                            Math.min(98, position)
                                          )}%`,
                                        background:
                                          PLAYER_COLORS[index],
                                      }}
                                    />
                                  </div>
                                </div>
                              );
                            }
                          )}

                        </div>

                      </div>

                    </div>

                  ) : (

                    <div className="p-8 text-center">
                      <div className="text-sm text-ink">
                        Select a comparison metric
                      </div>

                      <div className="text-2xs text-faint mt-1">
                        Choose a dimension above to explore the
                        selected players.
                      </div>
                    </div>

                  )}

                </section>

              </div>


              {/* ---------------------------------------------- */}
              {/* RECRUITMENT LANDSCAPE */}
              {/* ---------------------------------------------- */}

              <section className="analytics-panel">

                <div className="p-5 border-b border-border">

                  <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">

                    <div>
                      <div className="text-xs text-ink font-medium">
                        Recruitment landscape
                      </div>

                      <div className="text-2xs text-faint mt-1">
                        Compare the selected players across current
                        performance, development outlook and market context.
                      </div>
                    </div>

                    <div className="text-2xs text-faint">
                      Current season · {selectedLabel}
                    </div>

                  </div>

                </div>

                <div className="p-5">

                  <div
                    className="grid gap-4"
                    style={{
                      gridTemplateColumns:
                        `repeat(${result.players.length}, minmax(0, 1fr))`,
                    }}
                  >

                    {result.players.map(
                      (player: any, index: number) => {
                        const performance = numeric(
                          player.performance_score
                        );

                        const potential = numeric(
                          player.development_potential
                        );

                        const expected = numeric(
                          player.expected_performance_12m
                        );

                        const valueGap = numeric(
                          player.value_gap_pct
                        );

                        return (
                          <div
                            key={player.player_id}
                            className="rounded-xl border border-border bg-panelraised/30 p-5"
                          >
                            <div className="flex items-center justify-between mb-5">
                              <div className="flex items-center gap-2 min-w-0">
                                <span
                                  className="w-2.5 h-2.5 rounded-full shrink-0"
                                  style={{
                                    background:
                                      PLAYER_COLORS[index],
                                  }}
                                />

                                <Link
                                  href={`/players/${player.player_id}`}
                                  className="text-sm text-ink font-medium hover:text-accent truncate"
                                >
                                  {player.short_name}
                                </Link>
                              </div>

                              <RiskBadge
                                tier={
                                  player.recruitment_risk_tier
                                }
                              />
                            </div>

                            <LandscapeMetric
                              label="Current performance"
                              value={performance}
                              color={PLAYER_COLORS[index]}
                            />

                            <LandscapeMetric
                              label="Development potential"
                              value={potential}
                              color={PLAYER_COLORS[index]}
                            />

                            <LandscapeMetric
                              label="12M expected performance"
                              value={expected}
                              color={PLAYER_COLORS[index]}
                            />

                            <div className="mt-5 pt-4 border-t border-border">
                              <div className="grid grid-cols-2 gap-3">
                                <div>
                                  <div className="text-2xs text-faint">
                                    Market value
                                  </div>

                                  <div className="text-xs text-ink mt-1 tabular">
                                    {formatEur(player.value_eur)}
                                  </div>
                                </div>

                                <div>
                                  <div className="text-2xs text-faint">
                                    Fair value
                                  </div>

                                  <div className="text-xs text-ink mt-1 tabular">
                                    {formatEur(player.fair_value_eur)}
                                  </div>
                                </div>

                                <div>
                                  <div className="text-2xs text-faint">
                                    Value gap
                                  </div>

                                  <div
                                    className={`text-xs mt-1 tabular ${
                                      valueGap !== null && valueGap > 0
                                        ? "text-risklow"
                                        : "text-ink"
                                    }`}
                                  >
                                    {pct(valueGap)}
                                  </div>
                                </div>

                                <div>
                                  <div className="text-2xs text-faint">
                                    Minutes
                                  </div>

                                  <div className="text-xs text-ink mt-1 tabular">
                                    {integer(player.playing_time_min)}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      }
                    )}

                  </div>

                  <div className="mt-6 rounded-xl border border-border overflow-hidden">

                    <div className="px-5 py-4 border-b border-border">
                      <div className="text-xs text-ink font-medium">
                        Relative recruitment dimensions
                      </div>

                      <div className="text-2xs text-faint mt-1">
                        Each row normalizes the selected players against
                        the observed range for that dimension.
                      </div>
                    </div>

                    <div className="p-5 space-y-5">

                      {[
                        {
                          key: "performance_score",
                          label: "Current performance",
                        },
                        {
                          key: "development_potential",
                          label: "Development potential",
                        },
                        {
                          key: "expected_performance_12m",
                          label: "12M expected performance",
                        },
                        {
                          key: "value_gap_pct",
                          label: "Value opportunity",
                        },
                        {
                          key: "playing_time_min",
                          label: "Playing time",
                        },
                        {
                          key: "sample_reliability_score",
                          label: "Evidence reliability",
                        },
                      ].map((dimension) => {
                        const row = metricOptions.find(
                          (metric: any) =>
                            metric.field === dimension.key
                        );

                        if (!row) {
                          return null;
                        }

                        return (
                          <div key={dimension.key}>
                            <div className="flex items-center justify-between mb-3">
                              <span className="text-xs text-ink">
                                {dimension.label}
                              </span>

                              <span className="text-2xs text-faint">
                                {formatMetric(
                                  dimension.key,
                                  row.range?.min
                                )}
                                {" — "}
                                {formatMetric(
                                  dimension.key,
                                  row.range?.max
                                )}
                              </span>
                            </div>

                            <div className="space-y-2">
                              {result.players.map(
                                (player: any, index: number) => {
                                  const value = numeric(
                                    row.values[player.player_id]
                                  );

                                  const normalized =
                                    normalizeMetricValue(
                                      value,
                                      row
                                    );

                                  return (
                                    <div
                                      key={player.player_id}
                                      className="flex items-center gap-3"
                                    >
                                      <div className="w-20 shrink-0">
                                        <div className="text-2xs text-muted truncate">
                                          {player.short_name}
                                        </div>
                                      </div>

                                      <div className="flex-1 relative h-5">
                                        <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-panelraised rounded-full -translate-y-1/2" />

                                        <div
                                          className="absolute top-1/2 left-0 h-1.5 rounded-full -translate-y-1/2"
                                          style={{
                                            width:
                                              `${Math.max(
                                                2,
                                                normalized
                                              )}%`,
                                            background:
                                              PLAYER_COLORS[index],
                                            opacity: 0.35,
                                          }}
                                        />

                                        <div
                                          className="absolute top-1/2 w-4 h-4 rounded-full border-2 border-panel -translate-y-1/2 -translate-x-1/2"
                                          style={{
                                            left:
                                              `${Math.max(
                                                2,
                                                Math.min(
                                                  98,
                                                  normalized
                                                )
                                              )}%`,
                                            background:
                                              PLAYER_COLORS[index],
                                          }}
                                        />
                                      </div>

                                      <div className="w-16 text-right text-xs text-ink tabular">
                                        {formatMetric(
                                          dimension.key,
                                          value
                                        )}
                                      </div>
                                    </div>
                                  );
                                }
                              )}
                            </div>
                          </div>
                        );
                      })}

                    </div>

                  </div>

                </div>

              </section>

            </div>

          )}


          {/* ================================================== */}
          {/* PERFORMANCE */}
          {/* ================================================== */}

          {viewMode === "performance" && (

            <section className="analytics-panel">

              <div className="p-5 border-b border-border">

                <div className="text-xs text-ink font-medium">
                  Performance comparison
                </div>

                <div className="text-2xs text-faint mt-1">
                  Switch between the available performance
                  dimensions and inspect the magnitude of
                  the differences.
                </div>

              </div>


              <div className="p-5">

                <div className="flex flex-wrap gap-2 mb-6">

                  {metricOptions
                    .filter(
                      (metric: any) =>
                        [
                          "performance_score",
                          "development_potential",
                          "expected_performance_12m",
                          "adjusted_performance_score",
                        ].includes(
                          metric.field
                        )
                    )
                    .map(
                      (metric: any) => (
                        <button
                          key={
                            metric.field
                          }
                          onClick={() =>
                            setSelectedMetric(
                              metric.field
                            )
                          }
                          className={`action-button ${
                            selectedMetric ===
                            metric.field
                              ? "action-button-primary"
                              : ""
                          }`}
                        >
                          {metric.metric}
                        </button>
                      )
                    )}

                </div>


                <div className="space-y-5">

                  {metricChartData.map(
                    (
                      item: any,
                      index: number
                    ) => {

                      const max =
                        Math.max(
                          ...metricChartData.map(
                            (x: any) =>
                              Number(
                                x.value
                              ) || 0
                          ),
                          1
                        );

                      const width =
                        Math.max(
                          2,
                          ((Number(
                            item.value
                          ) || 0) /
                            max) *
                            100
                        );

                      return (
                        <div
                          key={
                            item.playerId
                          }
                        >

                          <div className="flex items-center justify-between mb-2">

                            <div className="flex items-center gap-2">

                              <span
                                className="w-2 h-2 rounded-full"
                                style={{
                                  background:
                                    PLAYER_COLORS[
                                      index
                                    ],
                                }}
                              />

                              <Link
                                href={`/players/${item.playerId}`}
                                className="text-xs text-ink hover:text-accent"
                              >
                                {item.name}
                              </Link>

                            </div>

                            <span className="text-xs text-ink tabular">
                              {formatChartValue(
                                selectedMetric,
                                item.value
                              )}
                            </span>

                          </div>

                          <div className="h-2 bg-panelraised rounded-full overflow-hidden">

                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width:
                                  `${width}%`,
                                background:
                                  PLAYER_COLORS[
                                    index
                                  ],
                              }}
                            />

                          </div>

                        </div>
                      );
                    }
                  )}

                </div>

              </div>

            </section>

          )}


          {/* ================================================== */}
          {/* RECRUITMENT */}
          {/* ================================================== */}

          {viewMode === "recruitment" && (

            <div className="space-y-6">

              <section>

                <SectionHeading
                  kicker="RECRUITMENT CONTEXT"
                  title="Market & evidence comparison"
                  subtitle="Understand the financial and evidence context behind each profile."
                />

                <div
                  className="grid gap-4"
                  style={{
                    gridTemplateColumns:
                      `repeat(${result.players.length}, minmax(0, 1fr))`,
                  }}
                >

                  {result.players.map(
                    (
                      player: any,
                      index: number
                    ) => (

                      <div
                        key={
                          player.player_id
                        }
                        className="analytics-panel"
                      >

                        <div className="p-5">

                          <div className="flex items-center justify-between mb-5">

                            <div className="flex items-center gap-2">

                              <span
                                className="w-2 h-2 rounded-full"
                                style={{
                                  background:
                                    PLAYER_COLORS[
                                      index
                                    ],
                                }}
                              />

                              <span className="text-sm text-ink font-medium">
                                {player.short_name}
                              </span>

                            </div>

                            <RiskBadge
                              tier={
                                player.recruitment_risk_tier
                              }
                            />

                          </div>


                          <MarketStat
                            label="Market value"
                            value={formatEur(
                              player.value_eur
                            )}
                          />

                          <MarketStat
                            label="Fair value"
                            value={formatEur(
                              player.fair_value_eur
                            )}
                          />

                          <MarketStat
                            label="Value gap"
                            value={pct(
                              player.value_gap_pct
                            )}
                            positive={
                              numeric(
                                player.value_gap_pct
                              ) !== null &&
                              numeric(
                                player.value_gap_pct
                              )! > 0
                            }
                          />

                          <MarketStat
                            label="Minutes"
                            value={integer(
                              player.playing_time_min
                            )}
                          />

                          <MarketStat
                            label="Evidence reliability"
                            value={numberOrDash(
                              player.sample_reliability_score
                            )}
                          />

                        </div>

                      </div>

                    )
                  )}

                </div>

              </section>


              {/* DECISION MATRIX AS VISUAL HEATMAP */}

              <section className="analytics-panel">

                <div className="p-5 border-b border-border">

                  <div className="text-xs text-ink font-medium">
                    Decision matrix
                  </div>

                  <div className="text-2xs text-faint mt-1">
                    Relative magnitude of each observed
                    recruitment dimension.
                  </div>

                </div>

                <div className="overflow-x-auto">

                  <table className="w-full min-w-[760px]">

                    <thead>

                      <tr className="border-b border-border">

                        <th className="px-5 py-3 text-left text-2xs uppercase tracking-wider text-faint font-medium">
                          Dimension
                        </th>

                        {result.players.map(
                          (
                            player: any,
                            index: number
                          ) => (
                            <th
                              key={
                                player.player_id
                              }
                              className="px-4 py-3 text-left text-2xs uppercase tracking-wider text-faint font-medium"
                            >

                              <div className="flex items-center gap-2">

                                <span
                                  className="w-2 h-2 rounded-full"
                                  style={{
                                    background:
                                      PLAYER_COLORS[
                                        index
                                      ],
                                  }}
                                />

                                {player.short_name}

                              </div>

                            </th>
                          )
                        )}

                      </tr>

                    </thead>

                    <tbody>

                      {metricOptions.map(
                        (row: any) => {

                          const values =
                            result.players.map(
                              (
                                player: any
                              ) =>
                                numeric(
                                  row.values[
                                    player.player_id
                                  ]
                                )
                            );

                          const max = Math.max(
                            ...values.filter(
                              (
                                x: any
                              ) =>
                                x !== null
                            ),
                            1
                          );

                          const min = Math.min(
                            ...values.filter(
                              (
                                x: any
                              ) =>
                                x !== null
                            ),
                            0
                          );

                          return (
                            <tr
                              key={
                                row.field
                              }
                              className="border-b border-border last:border-0"
                            >

                              <td className="px-5 py-4">

                                <div className="text-xs text-ink">
                                  {row.metric}
                                </div>

                                <div className="text-2xs text-faint mt-1">
                                  Range{" "}
                                  {formatMetric(
                                    row.field,
                                    row.range
                                      ?.min
                                  )}
                                  {" – "}
                                  {formatMetric(
                                    row.field,
                                    row.range
                                      ?.max
                                  )}
                                </div>

                              </td>

                              {result.players.map(
                                (
                                  player: any,
                                  index: number
                                ) => {

                                  const value =
                                    numeric(
                                      row.values[
                                        player.player_id
                                      ]
                                    );

                                  const relative =
                                    value ===
                                      null ||
                                    max === min
                                      ? 0
                                      : ((value -
                                          min) /
                                          (max -
                                            min)) *
                                        100;

                                  return (
                                    <td
                                      key={
                                        player.player_id
                                      }
                                      className="px-4 py-4"
                                    >

                                      <div className="flex items-center gap-3">

                                        <div className="flex-1 h-1.5 bg-panelraised rounded-full overflow-hidden">

                                          <div
                                            className="h-full rounded-full"
                                            style={{
                                              width:
                                                `${Math.max(
                                                  3,
                                                  relative
                                                )}%`,
                                              background:
                                                PLAYER_COLORS[
                                                  index
                                                ],
                                            }}
                                          />

                                        </div>

                                        <span className="w-20 text-right text-xs text-ink tabular">
                                          {formatMetric(
                                            row.field,
                                            value
                                          )}
                                        </span>

                                      </div>

                                    </td>
                                  );
                                }
                              )}

                            </tr>
                          );
                        }
                      )}

                    </tbody>

                  </table>

                </div>

              </section>


              {/* EVIDENCE */}

              <section>

                <SectionHeading
                  kicker="SCOUT EVIDENCE"
                  title="Strengths & investigation areas"
                  subtitle="Deterministic signals from the available dataset."
                />

                {Array.isArray(result.evidence) &&
                result.evidence.length ? (
                  <div
                    className="grid gap-4"
                    style={{
                      gridTemplateColumns:
                        `repeat(${result.evidence.length}, minmax(0, 1fr))`,
                    }}
                  >
                    {result.evidence.map(
                      (evidence: any, index: number) => {
                        const player = result.players.find(
                          (entry: any) =>
                            entry.player_id === evidence.player_id
                        );

                        return (
                          <div
                            key={evidence.player_id}
                            className="analytics-panel"
                          >
                            <div className="p-5">
                              <div className="flex items-center gap-2 mb-5">
                                <span
                                  className="w-2 h-2 rounded-full"
                                  style={{
                                    background:
                                      PLAYER_COLORS[index],
                                  }}
                                />

                                <span className="text-sm text-ink font-medium">
                                  {player?.short_name}
                                </span>
                              </div>

                              <EvidenceGroup
                                title="Strengths"
                                items={evidence.strengths}
                                positive
                              />

                              <div className="h-px bg-border my-5" />

                              <EvidenceGroup
                                title="Investigate"
                                items={evidence.watchouts}
                              />
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                ) : (
                  <EmptyState
                    title="No additional evidence"
                    body="The comparison API did not return separate strengths or investigation notes."
                  />
                )}

              </section>

            </div>

          )}


          {/* ================================================== */}
          {/* PERCENTILES */}
          {/* ================================================== */}

          {viewMode === "percentiles" && (

            <section className="analytics-panel">

              <div className="p-5 border-b border-border">

                <div className="text-xs text-ink font-medium">
                  Statistical profile
                </div>

                <div className="text-2xs text-faint mt-1">
                  Percentile comparison using only
                  dimensions available for every selected
                  player.
                </div>

              </div>


              {result.percentile_comparison?.length ? (

                <div className="overflow-x-auto">

                  <table className="w-full min-w-[760px]">

                    <thead>

                      <tr className="border-b border-border">

                        <th className="px-5 py-3 text-left text-2xs uppercase tracking-wider text-faint font-medium">
                          Metric
                        </th>

                        {result.players.map(
                          (
                            player: any,
                            index: number
                          ) => (
                            <th
                              key={
                                player.player_id
                              }
                              className="px-4 py-3 text-left text-2xs uppercase tracking-wider text-faint font-medium"
                            >

                              <div className="flex items-center gap-2">

                                <span
                                  className="w-2 h-2 rounded-full"
                                  style={{
                                    background:
                                      PLAYER_COLORS[
                                        index
                                      ],
                                  }}
                                />

                                {player.short_name}

                              </div>

                            </th>
                          )
                        )}

                      </tr>

                    </thead>

                    <tbody>

                      {result.percentile_comparison.map(
                        (row: any) => {

                          return (
                            <tr
                              key={
                                row.metric
                              }
                              className="border-b border-border last:border-0"
                            >

                              <td className="px-5 py-4 text-xs text-ink">
                                {formatRadarLabel(
                                  row.metric
                                )}
                              </td>

                              {result.players.map(
                                (
                                  player: any,
                                  index: number
                                ) => {

                                  const value =
                                    numeric(
                                      row.values[
                                        player.player_id
                                      ]
                                    );

                                  return (
                                    <td
                                      key={
                                        player.player_id
                                      }
                                      className="px-4 py-4"
                                    >

                                      <div className="flex items-center gap-3">

                                        <div className="flex-1 h-1.5 bg-panelraised rounded-full overflow-hidden">

                                          <div
                                            className="h-full rounded-full"
                                            style={{
                                              width:
                                                `${Math.max(
                                                  2,
                                                  value ??
                                                    0
                                                )}%`,
                                              background:
                                                PLAYER_COLORS[
                                                  index
                                                ],
                                            }}
                                          />

                                        </div>

                                        <span className="w-8 text-right text-xs text-ink tabular">
                                          {value ===
                                          null
                                            ? "—"
                                            : value.toFixed(
                                                0
                                              )}
                                        </span>

                                      </div>

                                    </td>
                                  );
                                }
                              )}

                            </tr>
                          );
                        }
                      )}

                    </tbody>

                  </table>

                </div>

              ) : (

                <div className="p-5">

                  <EmptyState
                    title="No shared percentile metrics"
                    body="These players do not have enough common percentile evidence."
                  />

                </div>

              )}

            </section>

          )}


          {/* ================================================== */}
          {/* METHODOLOGY */}
          {/* ================================================== */}

          <section className="analytics-panel">

            <div className="p-5">

              <div className="text-2xs uppercase tracking-wider text-faint mb-2">
                Methodology
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

                <MethodologyItem
                  title="Observed evidence"
                  body="The comparison uses the selected season's player-season records rather than synthetic scores."
                />

                <MethodologyItem
                  title="Percentile profile"
                  body="Only percentile dimensions with evidence for every selected player are included."
                />

                <MethodologyItem
                  title="Decision support"
                  body="The dashboard exposes trade-offs rather than forcing a universal recruitment winner."
                />

              </div>

            </div>

          </section>

        </div>
      )}

    </div>
  );
}


/* ============================================================ */
/* COMPONENTS */
/* ============================================================ */

function SectionHeading({
  kicker,
  title,
  subtitle,
}: {
  kicker?: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mb-4">

      {kicker && (
        <div className="text-2xs uppercase tracking-[0.16em] text-accent mb-1">
          {kicker}
        </div>
      )}

      <h2 className="text-sm text-ink font-medium">
        {title}
      </h2>

      <p className="text-2xs text-faint mt-1">
        {subtitle}
      </p>

    </div>
  );
}


function PlayerHeroCard({
  player,
  index,
}: {
  player: any;
  index: number;
}) {
  return (
    <div className="analytics-panel">

      <div
        className="h-1"
        style={{
          background:
            PLAYER_COLORS[index],
        }}
      />

      <div className="p-5">

        <div className="flex items-start justify-between gap-3">

          <div>

            <Link
              href={`/players/${player.player_id}`}
              className="text-base text-ink font-semibold hover:text-accent transition-colors"
            >
              {player.short_name}
            </Link>

            <div className="text-2xs text-muted mt-1">
              {player.canonical_position ||
                "Position —"}
            </div>

          </div>

          <RiskBadge
            tier={
              player.recruitment_risk_tier
            }
          />

        </div>


        <div className="mt-5 grid grid-cols-2 gap-2">

          <MiniStat
            label="Age"
            value={
              player.age_fifa ?? "—"
            }
          />

          <MiniStat
            label="Minutes"
            value={integer(
              player.playing_time_min
            )}
          />

          <MiniStat
            label="Club"
            value={
              player.club_name || "—"
            }
          />

          <MiniStat
            label="League"
            value={
              player.league_name || "—"
            }
          />

        </div>

      </div>

    </div>
  );
}


function MiniStat({
  label,
  value,
}: {
  label: string;
  value: any;
}) {
  return (
    <div className="rounded-md bg-panelraised/70 border border-border px-3 py-2">

      <div className="text-2xs text-faint">
        {label}
      </div>

      <div className="text-xs text-ink mt-1 truncate">
        {value}
      </div>

    </div>
  );
}


function Kpi({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">

      <span className="text-2xs text-faint">
        {label}
      </span>

      <span className="text-sm text-ink tabular font-medium">
        {value}
      </span>

    </div>
  );
}


function MarketStat({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">

      <span className="text-2xs text-faint">
        {label}
      </span>

      <span
        className={`text-xs tabular ${
          positive
            ? "text-risklow"
            : "text-ink"
        }`}
      >
        {value}
      </span>

    </div>
  );
}


function EvidenceGroup({
  title,
  items,
  positive = false,
}: {
  title: string;
  items?: string[];
  positive?: boolean;
}) {
  return (
    <div>

      <div className="text-2xs uppercase tracking-wider text-faint mb-2">
        {title}
      </div>

      {items?.length ? (

        <div className="space-y-2">

          {items.map((item) => (
            <div
              key={item}
              className="flex gap-2 text-xs text-muted leading-5"
            >

              <span
                className={
                  positive
                    ? "text-risklow"
                    : "text-riskmed"
                }
              >
                {positive
                  ? "↗"
                  : "!"
                }
              </span>

              <span>{item}</span>

            </div>
          ))}

        </div>

      ) : (

        <div className="text-xs text-faint">
          No deterministic signal from the
          available fields.
        </div>

      )}

    </div>
  );
}


function ViewButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`action-button ${
        active
          ? "action-button-primary"
          : ""
      }`}
    >
      {children}
    </button>
  );
}


function MethodologyItem({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div>

      <div className="text-xs text-ink font-medium">
        {title}
      </div>

      <div className="text-2xs text-faint leading-5 mt-1">
        {body}
      </div>

    </div>
  );
}


function TradeoffTooltip({
  active,
  payload,
}: any) {
  if (
    !active ||
    !payload?.length
  ) {
    return null;
  }

  const item =
    payload[0]?.payload;

  if (!item) {
    return null;
  }

  return (
    <div className="bg-panel border border-border rounded-lg px-3 py-2 shadow-xl">

      <div className="text-xs text-ink font-medium mb-2">
        {item.name}
      </div>

      <div className="text-2xs text-muted">
        Performance:{" "}
        <span className="text-ink">
          {item.performance?.toFixed(1)}
        </span>
      </div>

      <div className="text-2xs text-muted">
        Potential:{" "}
        <span className="text-ink">
          {item.potential?.toFixed(1)}
        </span>
      </div>

      <div className="text-2xs text-muted">
        Value gap:{" "}
        <span className="text-ink">
          {item.valueGap == null
            ? "—"
            : `${item.valueGap.toFixed(
                1
              )}%`}
        </span>
      </div>

      <div className="text-2xs text-muted">
        Minutes:{" "}
        <span className="text-ink">
          {item.minutes == null
            ? "—"
            : Math.round(
                item.minutes
              ).toLocaleString()}
        </span>
      </div>

    </div>
  );
}


/* ============================================================ */
/* FORMATTERS */
/* ============================================================ */

function numeric(
  value: any
): number | null {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return null;
  }

  const parsed =
    Number(value);

  return Number.isFinite(
    parsed
  )
    ? parsed
    : null;
}


function numberOrDash(
  value: any
): string {
  const n =
    numeric(value);

  return n === null
    ? "—"
    : n.toFixed(1);
}


function integer(
  value: any
): string {
  const n =
    numeric(value);

  return n === null
    ? "—"
    : Math.round(
        n
      ).toLocaleString();
}


function pct(
  value: any
): string {
  const n =
    numeric(value);

  return n === null
    ? "—"
    : `${n.toFixed(1)}%`;
}


function formatRadarLabel(
  value: string
): string {
  return value
    .replaceAll(
      "per 90 minutes",
      "/90"
    )
    .replaceAll(
      "_",
      " "
    )
    .replace(/\b\w/g, (x) =>
      x.toUpperCase()
    );
}


function formatMetric(
  field: string,
  value: any
): string {
  const n =
    numeric(value);

  if (n === null) {
    return "—";
  }

  if (
    field ===
      "value_eur" ||
    field ===
      "fair_value_eur"
  ) {
    return formatEur(n);
  }

  if (
    field ===
    "value_gap_pct"
  ) {
    return `${n.toFixed(1)}%`;
  }

  if (
    field ===
    "playing_time_min"
  ) {
    return Math.round(
      n
    ).toLocaleString();
  }

  return n.toFixed(1);
}


function formatChartValue(
  field: string,
  value: any
): string {
  return formatMetric(
    field,
    value
  );
}


function normalizeMetricValue(
  value: number | null,
  row: any
): number {
  if (
    value === null ||
    !row?.range
  ) {
    return 0;
  }

  const min = numeric(
    row.range.min
  );

  const max = numeric(
    row.range.max
  );

  if (
    min === null ||
    max === null ||
    max === min
  ) {
    return 50;
  }

  return (
    ((value - min) /
      (max - min)) *
    100
  );
}


function metricPosition(
  value: number | null,
  row: any
): string {
  if (
    value === null ||
    !row?.range
  ) {
    return "No data";
  }

  const position =
    normalizeMetricValue(
      value,
      row
    );

  if (position >= 85) {
    return "Top of selected range";
  }

  if (position >= 65) {
    return "Upper range";
  }

  if (position >= 35) {
    return "Middle range";
  }

  if (position >= 15) {
    return "Lower range";
  }

  return "Bottom of selected range";
}


function LandscapeMetric({
  label,
  value,
  color,
}: {
  label: string;
  value: number | null;
  color: string;
}) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xs text-faint">
          {label}
        </span>

        <span className="text-xs text-ink tabular font-medium">
          {value === null
            ? "—"
            : value.toFixed(1)}
        </span>
      </div>

      <div className="h-2 rounded-full bg-panel overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width:
              `${Math.max(
                2,
                Math.min(
                  100,
                  value ?? 0
                )
              )}%`,
            background: color,
          }}
        />
      </div>
    </div>
  );
}


function buildDecisionMatrix(
  comparison: any
): any[] {
  const players = Array.isArray(
    comparison?.players
  )
    ? comparison.players
    : [];

  if (!players.length) {
    return [];
  }

  const providedRows = Array.isArray(
    comparison?.decision_matrix
  )
    ? comparison.decision_matrix.filter(
        (metric: any) =>
          metric?.field &&
          metric?.metric &&
          metric?.values &&
          players.some(
            (player: any) =>
              numeric(
                metric.values[player.player_id]
              ) !== null
          )
      )
    : [];

  if (providedRows.length) {
    return providedRows;
  }

  const dimensions = [
    {
      field: "performance_score",
      metric: "Performance score",
    },
    {
      field: "development_potential",
      metric: "Development potential",
    },
    {
      field: "expected_performance_12m",
      metric: "12M expected performance",
    },
    {
      field: "adjusted_performance_score",
      metric: "Adjusted performance",
    },
    {
      field: "value_eur",
      metric: "Market value",
    },
    {
      field: "fair_value_eur",
      metric: "Fair value",
    },
    {
      field: "value_gap_pct",
      metric: "Value gap",
    },
    {
      field: "playing_time_min",
      metric: "Playing time",
    },
    {
      field: "sample_reliability_score",
      metric: "Evidence reliability",
    },
  ];

  const playerRows = dimensions.flatMap(
    (dimension) => {
      const values: Record<string, number | null> = {};

      for (const player of players) {
        values[player.player_id] = numeric(
          player[dimension.field]
        );
      }

      const observed = Object.values(values).filter(
        (value): value is number => value !== null
      );

      if (!observed.length) {
        return [];
      }

      return [{
        ...dimension,
        values,
        range: {
          min: Math.min(...observed),
          max: Math.max(...observed),
        },
      }];
    }
  );

  const percentileRows = Array.isArray(
    comparison?.percentile_comparison
  )
    ? comparison.percentile_comparison.flatMap(
        (row: any, index: number) => {
          if (!row?.metric || !row.values) {
            return [];
          }

          const values: Record<string, number | null> = {};

          for (const player of players) {
            values[player.player_id] = numeric(
              row.values[player.player_id]
            );
          }

          const observed = Object.values(values).filter(
            (value): value is number => value !== null
          );

          if (!observed.length) {
            return [];
          }

          return [{
            field: `percentile_${index}`,
            metric: `${row.metric} percentile`,
            values,
            range: {
              min: Math.min(...observed),
              max: Math.max(...observed),
            },
          }];
        }
      )
    : [];

  return [...playerRows, ...percentileRows];
}