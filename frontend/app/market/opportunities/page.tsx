"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  api,
  formatEur,
  type OpportunityParams,
} from "@/lib/api";

import DownloadButton from "@/components/DownloadButton";
import { ValidationNotice } from "@/components/ValidationBadge";

import {
  ErrorState,
  EmptyState,
  LoadingState,
  PlayerLink,
  RiskBadge,
} from "@/components/ui";

import { useSeason } from "@/components/SeasonContext";


function NumberValue({
  value,
  suffix = "",
}: {
  value: number | null | undefined;
  suffix?: string;
}) {
  return (
    <>
      {value == null
        ? "—"
        : `${Number(value).toFixed(1)}${suffix}`}
    </>
  );
}


function SignalBar({
  value,
  max = 100,
}: {
  value: number | null | undefined;
  max?: number;
}) {

  const numeric = Number(
    value ?? 0
  );

  const width = Math.max(
    0,
    Math.min(
      100,
      (numeric / max) * 100
    )
  );

  return (
    <div className="h-1.5 bg-panelraised rounded-full overflow-hidden">
      <div
        className="h-full bg-accent"
        style={{
          width: `${width}%`,
        }}
      />
    </div>
  );
}


function OpportunityCard({
  player,
}: {
  player: any;
}) {

  return (
    <div className="border border-border bg-panel rounded-sm p-4 hover:border-accent/40 transition-colors">

      <div className="flex items-start justify-between gap-4">

        <div className="min-w-0">

          <PlayerLink
            playerId={player.player_id}
            name={player.short_name}
          />

          <div className="text-2xs text-muted mt-1 truncate">
            {player.canonical_position || "—"}
            {" · "}
            {player.club_name || "—"}
            {" · "}
            {player.league_name || "—"}
          </div>

        </div>

        <div className="text-right shrink-0">

          <div className="text-2xs text-faint">
            Opportunity
          </div>

          <div className="text-xl tabular text-ink font-medium">
            <NumberValue
              value={
                player.opportunity_score
              }
            />
          </div>

        </div>

      </div>


      {player.contract && (
        <div className="text-2xs text-muted mt-3">
          Contract: {player.contract.contract_status}
          {player.contract.contract_expires ? ` (${player.contract.contract_expires})` : ""}
          {player.contract.tm_value_change_12m_pct != null
            ? ` · value ${player.contract.tm_value_change_12m_pct >= 0 ? "+" : ""}${player.contract.tm_value_change_12m_pct}% in 12 months`
            : ""}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">

        <div>
          <div className="text-2xs text-faint">
            Value
          </div>

          <div className="text-sm tabular text-ink">
            {formatEur(
              player.value_eur
            )}
          </div>
        </div>


        <div>
          <div className="text-2xs text-faint">
            Fair value
          </div>

          <div className="text-sm tabular text-ink">
            {formatEur(
              player.fair_value_eur
            )}
          </div>
        </div>


        <div>
          <div className="text-2xs text-faint">
            Value gap
          </div>

          <div className="text-sm tabular text-risklow">
            +
            {Number(
              player.value_gap_pct ?? 0
            ).toFixed(0)}
            %
          </div>
        </div>


        <div>
          <div className="text-2xs text-faint">
            Performance
          </div>

          <div className="text-sm tabular text-ink">
            <NumberValue
              value={
                player.performance_score
              }
            />
          </div>
        </div>


        <div>
          <div className="text-2xs text-faint">
            Potential
          </div>

          <div className="text-sm tabular text-ink">
            <NumberValue
              value={
                player.development_potential
              }
            />
          </div>
        </div>

      </div>


      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">

        <div>

          <div className="flex justify-between text-2xs mb-1">

            <span className="text-faint">
              Performance
            </span>

            <span className="text-muted tabular">
              <NumberValue
                value={
                  player.performance_score
                }
              />
            </span>

          </div>

          <SignalBar
            value={
              player.performance_score
            }
          />

        </div>


        <div>

          <div className="flex justify-between text-2xs mb-1">

            <span className="text-faint">
              Potential
            </span>

            <span className="text-muted tabular">
              <NumberValue
                value={
                  player.development_potential
                }
              />
            </span>

          </div>

          <SignalBar
            value={
              player.development_potential
            }
          />

        </div>


        <div>

          <div className="flex justify-between text-2xs mb-1">

            <span className="text-faint">
              Wage / value
            </span>

            <span className="text-muted tabular">
              <NumberValue
                value={
                  player.wage_to_value_pct
                }
                suffix="%"
              />
            </span>

          </div>

          <SignalBar
            value={
              player.wage_to_value_pct
            }
            max={10}
          />

        </div>

      </div>


      <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-border">

        <div className="text-2xs text-muted">

          {player.age_fifa != null
            ? `${player.age_fifa} years`
            : "Age —"}

          {player.playing_time_min != null
            ? ` · ${Number(
                player.playing_time_min
              ).toLocaleString()} min`
            : ""}

        </div>

        <RiskBadge
          tier={
            player.recruitment_risk_tier
          }
        />

      </div>

    </div>
  );
}


export default function MarketOpportunitiesPage() {

  const {
    selectedSeason,
    selectedLabel,
  } = useSeason();

  const [data, setData] =
    useState<any>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);


  const [segment, setSegment] =
    useState("all");

  const [position, setPosition] =
    useState("");

  const [league, setLeague] =
    useState("");

  const [risk, setRisk] =
    useState("");

  const [minReliability, setMinReliability] =
    useState("");

  const [maxContract, setMaxContract] =
    useState("");

  const [minPerformance,
    setMinPerformance] =
    useState("60");

  const [minGap, setMinGap] = useState("");

  const [minAge, setMinAge] =
    useState("");

  const [maxAge, setMaxAge] =
    useState("");


  // Single source of truth for the filters: used by the on-screen query and the Excel export.
  const buildParams = (): OpportunityParams => ({

      topN: 20,

      minPerformanceScore:
        Number(
          minPerformance || 60
        ),

      minValueGapPct:
        Number(
          minGap || -100
        ),

      minAge:
        minAge
          ? Number(minAge)
          : undefined,

      maxAge:
        maxAge
          ? Number(maxAge)
          : undefined,

      canonicalPosition:
        position || undefined,

      leagueName:
        league || undefined,

      riskTier:
        risk || undefined,

      minReliabilityTier:
        minReliability || undefined,

      maxContractMonths:
        maxContract || undefined,

      segment,

      season:
        selectedSeason,

    });

  useEffect(() => {

    if (selectedSeason === null)
      return;

    setLoading(true);
    setError(null);

    api.marketOpportunities(buildParams())

      .then(setData)

      .catch((e) => {

        setData(null);

        setError(
          e.message ||
          "Unable to load market opportunities."
        );

      })

      .finally(() =>
        setLoading(false)
      );

  }, [
    selectedSeason,
    segment,
    position,
    league,
    risk,
    minReliability,
    maxContract,
    minPerformance,
    minGap,
    minAge,
    maxAge,
  ]);


  const segments =
    useMemo(
      () => data?.segments ?? [],
      [data]
    );

  const positions =
    data?.filter_options?.positions
    ?? [];

  const leagues =
    data?.filter_options?.leagues
    ?? [];

  const results =
    data?.results ?? [];


  function resetFilters() {

    setSegment("all");
    setPosition("");
    setLeague("");
    setRisk("");
    setMinReliability("");
    setMaxContract("");

    setMinPerformance("60");
    setMinGap("");

    setMinAge("");
    setMaxAge("");
  }


  return (

    <div className="max-w-[1500px]">

      <header className="mb-6">

        <div className="flex items-start justify-between gap-6">

          <div>

            <h1 className="text-xl text-ink font-medium">
              Market opportunities
            </h1>

            <p className="text-muted text-sm mt-1 max-w-4xl">
              The discovery score no longer uses the failed fair-value gap signal.
              Add a minimum gap only when you explicitly want that filter.
            </p>

            <ValidationNotice keys={["value_gap", "performance_score"]} />

          </div>


          <div className="text-right shrink-0">

            <div className="text-2xs uppercase tracking-wide text-faint">
              Analysis season
            </div>

            <div className="text-sm text-ink mt-1">
              {selectedLabel}
            </div>

          </div>

        </div>

      </header>


      {loading && (
        <LoadingState
          label="Building market intelligence"
        />
      )}


      {!loading && error && (
        <ErrorState
          message={error}
        />
      )}


      {!loading &&
        !error &&
        data && (

        <>

          {/* SUMMARY */}

          <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">

            <div className="border border-border bg-panel rounded-sm px-4 py-3">

              <div className="text-2xs text-faint">
                Opportunity pool
              </div>

              <div className="text-2xl text-ink tabular font-medium mt-1">
                {data.summary?.total_opportunities ?? 0}
              </div>

              <div className="text-2xs text-muted mt-1">
                after active filters
              </div>

            </div>


            <div className="border border-border bg-panel rounded-sm px-4 py-3">

              <div className="text-2xs text-faint">
                Average gap
              </div>

              <div className="text-2xl text-ink tabular font-medium mt-1">

                +

                <NumberValue
                  value={
                    data.summary?.average_gap_pct
                  }
                  suffix="%"
                />

              </div>

              <div className="text-2xs text-muted mt-1">
                model vs market signal
              </div>

            </div>


            <div className="border border-border bg-panel rounded-sm px-4 py-3">

              <div className="text-2xs text-faint">
                Median value
              </div>

              <div className="text-2xl text-ink tabular font-medium mt-1">
                {formatEur(
                  data.summary?.median_market_value_eur
                )}
              </div>

              <div className="text-2xs text-muted mt-1">
                qualifying players
              </div>

            </div>


            <div className="border border-border bg-panel rounded-sm px-4 py-3">

              <div className="text-2xs text-faint">
                High performance
              </div>

              <div className="text-2xl text-ink tabular font-medium mt-1">
                {data.summary?.high_performance_count ?? 0}
              </div>

              <div className="text-2xs text-muted mt-1">
                performance ≥ 75
              </div>

            </div>


            <div className="border border-border bg-panel rounded-sm px-4 py-3">

              <div className="text-2xs text-faint">
                High potential
              </div>

              <div className="text-2xl text-ink tabular font-medium mt-1">
                {data.summary?.high_potential_count ?? 0}
              </div>

              <div className="text-2xs text-muted mt-1">
                age ≤ 23, potential ≥ 75
              </div>

            </div>


            <div className="border border-border bg-panel rounded-sm px-4 py-3">

              <div className="text-2xs text-faint">
                Low risk
              </div>

              <div className="text-2xl text-ink tabular font-medium mt-1">
                {data.summary?.low_risk_count ?? 0}
              </div>

              <div className="text-2xs text-muted mt-1">
                LOW risk tier
              </div>

            </div>

          </section>


          {/* FILTERS */}

          <section className="border border-border bg-panel rounded-sm p-4 mb-6">

            <div className="flex items-center justify-between gap-4 mb-4">

              <div>

                <h2 className="text-sm text-ink font-medium">
                  Recruitment filters
                </h2>

                <p className="text-2xs text-muted mt-1">
                  All filters are applied by the backend
                  to the selected season.
                </p>

              </div>


              <DownloadButton label="Export to Excel" onDownload={() => api.downloadOpportunitiesExcel(buildParams())} />

              <button
                onClick={resetFilters}
                className="text-2xs text-muted hover:text-ink border border-border rounded-sm px-3 py-2"
              >
                Reset
              </button>

            </div>


            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">

              <label className="text-2xs text-faint">

                Min performance

                <input
                  value={minPerformance}
                  onChange={(e) =>
                    setMinPerformance(
                      e.target.value
                    )
                  }
                  type="number"
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                />

              </label>


              <label className="text-2xs text-faint">

                Optional min value gap %

                <input
                  value={minGap}
                  onChange={(e) =>
                    setMinGap(
                      e.target.value
                    )
                  }
                  type="number"
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                />

              </label>


              <label className="text-2xs text-faint">

                Min age

                <input
                  value={minAge}
                  onChange={(e) =>
                    setMinAge(
                      e.target.value
                    )
                  }
                  type="number"
                  placeholder="Any"
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                />

              </label>


              <label className="text-2xs text-faint">

                Max age

                <input
                  value={maxAge}
                  onChange={(e) =>
                    setMaxAge(
                      e.target.value
                    )
                  }
                  type="number"
                  placeholder="Any"
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                />

              </label>


              <label className="text-2xs text-faint">

                Position

                <select
                  value={position}
                  onChange={(e) =>
                    setPosition(
                      e.target.value
                    )
                  }
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                >

                  <option value="">
                    All positions
                  </option>

                  {positions.map(
                    (x: string) => (
                      <option
                        key={x}
                        value={x}
                      >
                        {x}
                      </option>
                    )
                  )}

                </select>

              </label>


              <label className="text-2xs text-faint">

                League

                <select
                  value={league}
                  onChange={(e) =>
                    setLeague(
                      e.target.value
                    )
                  }
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                >

                  <option value="">
                    All leagues
                  </option>

                  {leagues.map(
                    (x: string) => (
                      <option
                        key={x}
                        value={x}
                      >
                        {x}
                      </option>
                    )
                  )}

                </select>

              </label>


              <label className="text-2xs text-faint">

                Risk

                <select
                  value={risk}
                  onChange={(e) =>
                    setRisk(
                      e.target.value
                    )
                  }
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                >

                  <option value="">
                    All risk
                  </option>

                  <option value="LOW">
                    LOW
                  </option>

                  <option value="MEDIUM">
                    MEDIUM
                  </option>

                  <option value="HIGH">
                    HIGH
                  </option>

                </select>

              </label>


              <label className="text-2xs text-faint">

                Min sample reliability

                <select
                  value={minReliability}
                  onChange={(e) =>
                    setMinReliability(
                      e.target.value
                    )
                  }
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                >

                  <option value="">
                    Any sample size
                  </option>

                  <option value="Moderate">
                    Moderate or better
                  </option>

                  <option value="High">
                    High only
                  </option>

                </select>

              </label>


              <label className="text-2xs text-faint">

                Contract ends within

                <select
                  value={maxContract}
                  onChange={(e) =>
                    setMaxContract(
                      e.target.value
                    )
                  }
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                >

                  <option value="">
                    Any
                  </option>

                  <option value="6">
                    6 months
                  </option>

                  <option value="12">
                    12 months
                  </option>

                  <option value="24">
                    24 months
                  </option>

                </select>

                {data?.contract_context?.available === false && (
                  <span className="block mt-1 text-2xs text-faint">
                    Latest season only (current contracts).
                  </span>
                )}

              </label>


              <label className="text-2xs text-faint">

                Segment

                <select
                  value={segment}
                  onChange={(e) =>
                    setSegment(
                      e.target.value
                    )
                  }
                  className="mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none"
                >

                  {segments.map(
                    (x: any) => (
                      <option
                        key={x.key}
                        value={x.key}
                      >
                        {x.label}
                      </option>
                    )
                  )}

                </select>

              </label>

            </div>

          </section>


          {/* SEGMENTS */}

          <section className="mb-6">

            <div className="flex items-end justify-between gap-4 mb-3">

              <div>

                <h2 className="text-sm text-ink font-medium">
                  Opportunity segments
                </h2>

                <p className="text-2xs text-muted mt-1">
                  Use these as recruitment lenses,
                  not universal player rankings.
                </p>

              </div>

            </div>


            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">

              {segments.map(
                (item: any) => (

                  <button
                    key={item.key}
                    onClick={() =>
                      setSegment(
                        item.key
                      )
                    }
                    className={`text-left border rounded-sm p-3 transition-colors ${
                      segment === item.key
                        ? "border-accent bg-accent/5"
                        : "border-border bg-panel hover:border-accent/40"
                    }`}
                  >

                    <div className="text-2xs uppercase tracking-wide text-faint">
                      {item.label}
                    </div>

                    <div className="text-xl tabular text-ink font-medium mt-2">
                      {item.count}
                    </div>

                    <div className="text-2xs text-muted mt-1 leading-relaxed">
                      {item.description}
                    </div>

                  </button>

                )
              )}

            </div>

          </section>


          {/* MAIN */}

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">

            <section className="xl:col-span-2">

              <div className="flex items-end justify-between gap-4 mb-3">

                <div>

                  <h2 className="text-sm text-ink font-medium">
                    Top recruitment opportunities
                  </h2>

                  <p className="text-2xs text-muted mt-1">
                    Showing {results.length} of{" "}
                    {data.selected_total ??
                      data.total}{" "}
                    qualifying players.
                  </p>

                </div>

              </div>


              {results.length === 0 ? (

                <EmptyState
                  title="No players match these filters"
                  body="Relax the performance, value-gap, age, position, league or risk constraints."
                />

              ) : (

                <div className="space-y-3">

                  {results.map(
                    (player: any) => (
                      <OpportunityCard
                        key={
                          player.player_id
                        }
                        player={player}
                      />
                    )
                  )}

                </div>

              )}

            </section>


            {/* POSITION / LEAGUE */}

            <aside className="space-y-6">

              <section className="border border-border bg-panel rounded-sm p-4">

                <h2 className="text-sm text-ink font-medium">
                  Position distribution
                </h2>

                <div className="space-y-3 mt-4">

                  {(data.position_breakdown ?? [])
                    .map((item: any) => (

                      <button
                        key={item.name}
                        onClick={() =>
                          setPosition(
                            item.name
                          )
                        }
                        className="w-full text-left"
                      >

                        <div className="flex justify-between text-2xs mb-1">

                          <span className="text-muted">
                            {item.name}
                          </span>

                          <span className="text-ink tabular">
                            {item.opportunities}
                          </span>

                        </div>

                        <SignalBar
                          value={
                            item.opportunities
                          }
                          max={Math.max(
                            1,
                            data.total
                          )}
                        />

                      </button>

                    ))}

                </div>

              </section>


              <section className="border border-border bg-panel rounded-sm p-4">

                <h2 className="text-sm text-ink font-medium">
                  League distribution
                </h2>

                <div className="space-y-3 mt-4">

                  {(data.league_breakdown ?? [])
                    .map((item: any) => (

                      <button
                        key={item.name}
                        onClick={() =>
                          setLeague(
                            item.name
                          )
                        }
                        className="w-full text-left"
                      >

                        <div className="flex justify-between text-2xs mb-1">

                          <span className="text-muted truncate pr-2">
                            {item.name}
                          </span>

                          <span className="text-ink tabular">
                            {item.opportunities}
                          </span>

                        </div>

                        <SignalBar
                          value={
                            item.opportunities
                          }
                          max={Math.max(
                            1,
                            data.total
                          )}
                        />

                        <div className="text-2xs text-faint mt-1">

                          Avg gap +
                          {item.avg_gap ?? "—"}%

                          {" · "}

                          Perf{" "}
                          {item.avg_performance ??
                            "—"}

                        </div>

                      </button>

                    ))}

                </div>

              </section>

            </aside>

          </div>


          {/* METHODOLOGY */}

          <section className="border border-border bg-panel rounded-sm p-4">

            <h2 className="text-sm text-ink font-medium">
              Methodology & data boundary
            </h2>

            <div className="grid md:grid-cols-3 gap-5 mt-3 text-2xs leading-relaxed">

              <div>

                <div className="text-faint">
                  Base opportunity
                </div>

                <div className="text-muted mt-1">
                  {data.methodology?.base_definition}
                </div>

              </div>


              <div>

                <div className="text-faint">
                  Opportunity score
                </div>

                <div className="text-muted mt-1">
                  {data.methodology?.opportunity_score}
                </div>

              </div>


              <div>

                <div className="text-faint">
                  Data boundary
                </div>

                <div className="text-muted mt-1">
                  {data.methodology?.data_boundary}
                </div>

              </div>

            </div>


            <div className="text-2xs text-faint mt-4 pt-3 border-t border-border">

              {data.methodology?.fair_value_note}

            </div>

          </section>

        </>

      )}

    </div>
  );
}