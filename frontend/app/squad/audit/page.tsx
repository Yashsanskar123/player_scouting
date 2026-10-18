"use client";

import { useEffect, useState } from "react";
import ContractOutlook from "@/components/ContractOutlook";
import SquadInsights from "@/components/SquadInsights";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

import {
  MetricCard,
  LoadingState,
  ErrorState,
  EmptyState,
} from "@/components/ui";

import { useSeason } from "@/components/SeasonContext";

import TacticalPitch from "@/components/TacticalPitch";


const FORMATIONS = [
  "4-3-3",
  "4-2-3-1",
  "4-4-2",
  "3-4-3",
  "3-5-2",
];


const SEVERITY_STYLE: Record<
  string,
  string
> = {
  CRITICAL:
    "border-riskhigh/50 bg-riskhigh/10 text-riskhigh",

  HIGH:
    "border-riskhigh/30 bg-riskhigh/5 text-ink",

  MEDIUM:
    "border-riskmed/30 bg-riskmed/5 text-ink",

  LOW:
    "border-border bg-panel text-muted",
};


function Bar({
  value,
  max = 100,
}: {
  value:
    | number
    | null
    | undefined;

  max?: number;
}) {

  const n = Number(
    value ?? 0
  );

  const width = Math.max(
    0,
    Math.min(
      100,
      (n / max) * 100
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


function Readout({
  label,
  value,
  suffix = "",
}: {
  label: string;
  value: any;
  suffix?: string;
}) {

  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">

      <span className="text-2xs text-faint">
        {label}
      </span>

      <span className="text-sm text-ink tabular">
        {value ?? "—"}
        {suffix}
      </span>

    </div>
  );
}


export default function SquadAuditPage() {

  const router = useRouter();

  const [clubName, setClubName] =
    useState("Manchester City");

  const [formation, setFormation] =
    useState("4-3-3");

  const [result, setResult] =
    useState<any>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const {
    selectedSeason,
    selectedLabel,
  } = useSeason();

  // Initial defaults from the saved club profile (never overrides later edits).
  useEffect(() => {
    let alive = true;
    api.getClubProfile().then((d: any) => {
      if (alive && d?.configured && d.profile) {
        setClubName(d.profile.club_name);
        setFormation(d.profile.formation);
      }
    }).catch(() => {});
    return () => { alive = false; };
  }, []);


  async function runAudit() {

    setLoading(true);
    setError(null);
    setResult(null);

    try {

      const res =
        await api.auditSquad({
          club_name: clubName,
          formation,
          season: selectedSeason,
        });

      setResult(res);

    } catch (e: any) {

      setError(
        e.message ||
        "Squad audit failed."
      );

    } finally {

      setLoading(false);

    }
  }


  function searchForFinding(
    filter: Record<string, unknown>
  ) {

    const qs =
      new URLSearchParams();

    if (
      filter.canonical_position
    ) {
      qs.set(
        "position",
        String(
          filter.canonical_position
        )
      );
    }

    if (filter.max_age) {

      qs.set(
        "maxAge",
        String(
          filter.max_age
        )
      );

    }

    if (
      filter.min_performance_score
    ) {

      qs.set(
        "minPerformance",
        String(
          filter.min_performance_score
        )
      );

    }

    router.push(
      `/scouting/search?${qs.toString()}`
    );
  }


  const priorities =
    result?.recruitment_priorities
    ?? [];

  const positions =
    result?.position_summary
    ?? [];

  const age =
    result?.age_profile
    ?? {};

  const performance =
    result?.performance_profile
    ?? {};

  const findings =
    result?.findings
    ?? [];

  const depth =
    result?.depth_chart
    ?? [];


  return (

    <div className="max-w-[1500px]">

      {/* HEADER */}

      <header className="mb-6">

        <div className="flex items-start justify-between gap-6">

          <div>

            <h1 className="text-xl text-ink font-medium">
              Squad audit
            </h1>

            <p className="text-muted text-sm mt-1 max-w-4xl">

              Structural squad intelligence for{" "}
              {selectedLabel}:

              formation coverage,
              depth, quality, age profile,
              succession exposure and
              recruitment needs.

            </p>

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


      {/* CONTROLS */}

      <div className="border border-border rounded-sm bg-panel px-4 py-4 mb-6 grid grid-cols-1 md:grid-cols-3 gap-3 items-end">

        <label className="block">

          <div className="text-2xs text-faint mb-1">
            Club · {selectedLabel}
          </div>

          <input
            value={clubName}
            onChange={(e) =>
              setClubName(
                e.target.value
              )
            }
            placeholder="e.g. Manchester City"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />

        </label>


        <label className="block">

          <div className="text-2xs text-faint mb-1">
            Formation
          </div>

          <select
            value={formation}
            onChange={(e) =>
              setFormation(
                e.target.value
              )
            }
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink"
          >

            {FORMATIONS.map(
              (f) => (
                <option
                  key={f}
                  value={f}
                >
                  {f}
                </option>
              )
            )}

          </select>

        </label>


        <button
          onClick={runAudit}
          disabled={
            loading ||
            !clubName.trim()
          }
          className="bg-accent text-base font-medium text-sm rounded-sm px-4 py-1.5 hover:bg-accent/90 transition-colors disabled:opacity-50"
        >

          {loading
            ? "Auditing…"
            : "Run audit"}

        </button>

      </div>


      {loading && (
        <LoadingState
          label="Auditing squad"
        />
      )}


      {error && (
        <ErrorState
          message={error}
        />
      )}


      {result && (
        <>

          {/* SUMMARY */}

          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-6">

            <MetricCard
              label="Squad health"
              value={
                result.squad_health
              }
            />

            <MetricCard
              label="Depth coverage"
              value={`${result.depth_score}%`}
            />

            <MetricCard
              label="Age balance"
              value={
                result.age_score
              }
            />

            <MetricCard
              label="Avg performance"
              value={
                result.average_performance_score
              }
            />

            <MetricCard
              label="Median age"
              value={
                result.median_age
              }
            />

            <MetricCard
              label="Squad size"
              value={
                result.squad_size
              }
            />

          </div>


          {/* PITCH + READOUT */}

          <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_.65fr] gap-4 mb-6">

            <TacticalPitch
              formation={formation}
              players={depth}
              title="Formation view"
              subtitle="Formation-specific view of the available squad depth. Coverage remains separate from tactical role-fit scoring."
            />


            <div className="analytics-panel p-4">

              <h2 className="text-sm text-ink font-medium">
                Squad readout
              </h2>

              <p className="text-2xs text-muted mt-1 mb-3">
                A compact view of the structural signals behind the audit.
              </p>

              <Readout
                label="Squad health"
                value={
                  result.squad_health
                }
                suffix=" / 100"
              />

              <Readout
                label="Formation depth"
                value={
                  result.depth_score
                }
                suffix="%"
              />

              <Readout
                label="Age balance"
                value={
                  result.age_score
                }
                suffix=" / 100"
              />

              <Readout
                label="Average performance"
                value={
                  result.average_performance_score
                }
              />

              <Readout
                label="Median age"
                value={
                  result.median_age
                }
              />

              <Readout
                label="Formation"
                value={
                  formation
                }
              />

            </div>

          </div>


          {/* RECRUITMENT PRIORITIES */}

          <section className="mb-6">

            <div className="mb-3">

              <h2 className="text-sm text-ink font-medium">
                Recruitment priorities
              </h2>

              <p className="text-2xs text-muted mt-1">
                Directly derived from the audit findings. Each priority retains the underlying search filter.
              </p>

            </div>


            {priorities.length === 0 ? (

              <EmptyState
                title="No recruitment priorities"
                body="No structural, quality or succession gaps were flagged for this formation."
              />

            ) : (

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">

                {priorities
                  .slice(0, 6)
                  .map(
                    (item: any) => (

                      <div
                        key={`${item.priority}-${item.category}`}
                        className="border border-border bg-panel rounded-sm p-4"
                      >

                        <div className="flex items-start justify-between gap-3">

                          <div className="flex items-center gap-2">

                            <span className="text-xs tabular text-ink">
                              #{item.priority}
                            </span>

                            <span
                              className={`text-2xs rounded-full border px-2 py-1 ${
                                SEVERITY_STYLE[
                                  item.severity
                                ] ||
                                "border-border text-muted"
                              }`}
                            >
                              {item.severity}
                            </span>

                          </div>

                          <span className="text-2xs uppercase tracking-wide text-faint">
                            {item.category}
                          </span>

                        </div>


                        <div className="text-sm text-ink mt-3 leading-relaxed">
                          {item.need}
                        </div>


                        {Object.keys(
                          item.recruitment_filter ||
                          {}
                        ).length > 0 && (

                          <button
                            onClick={() =>
                              searchForFinding(
                                item.recruitment_filter
                              )
                            }
                            className="mt-4 text-2xs border border-border rounded-sm px-2 py-1.5 text-ink hover:border-accent hover:text-accent transition-colors"
                          >
                            Find candidates →
                          </button>

                        )}

                      </div>

                    )
                  )}

              </div>

            )}

          </section>


          {/* POSITION + COMPOSITION */}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">

            {/* POSITION COVERAGE */}

            <section className="border border-border bg-panel rounded-sm p-4">

              <h2 className="text-sm text-ink font-medium">
                Position coverage
              </h2>

              <p className="text-2xs text-muted mt-1 mb-4">
                Required starters and target depth are formation-specific.
              </p>


              <div className="space-y-4">

                {positions.map(
                  (item: any) => (

                    <div
                      key={
                        item.position
                      }
                    >

                      <div className="flex items-center justify-between gap-3 text-2xs mb-1">

                        <div className="flex items-center gap-2">

                          <span className="text-ink font-medium">
                            {item.position}
                          </span>

                          <span className="text-faint">
                            {item.players} players
                          </span>

                        </div>

                        <span className="text-muted tabular">
                          {item.coverage_pct}%
                        </span>

                      </div>


                      <Bar
                        value={
                          item.coverage_pct
                        }
                      />


                      <div className="grid grid-cols-3 gap-2 mt-2 text-2xs">

                        <span className="text-faint">
                          Need{" "}
                          {item.required_starters}
                        </span>

                        <span className="text-faint">
                          Target{" "}
                          {item.target_depth ||
                            "—"}
                        </span>

                        <span className="text-right text-muted">
                          Best{" "}
                          {item.best_performance ??
                            "—"}
                        </span>

                      </div>

                    </div>

                  )
                )}

              </div>

            </section>


            {/* SQUAD COMPOSITION */}

            <section className="border border-border bg-panel rounded-sm p-4">

              <h2 className="text-sm text-ink font-medium">
                Squad composition
              </h2>

              <p className="text-2xs text-muted mt-1 mb-4">
                Distribution of age and performance signals in the audited roster.
              </p>


              {/* AGE */}

              <div className="mb-5">

                <div className="text-2xs uppercase tracking-wide text-faint mb-3">
                  Age profile
                </div>


                <div className="grid grid-cols-5 gap-2">

                  {[
                    ["U21", age.u21],
                    ["21–22", age.u23],
                    ["23–27", age["23_27"]],
                    ["28–30", age["28_30"]],
                    ["31+", age["31_plus"]],
                  ].map(
                    ([label, value]) => (

                      <div
                        key={
                          String(label)
                        }
                        className="border border-border rounded-sm p-2"
                      >

                        <div className="text-2xs text-faint">
                          {label}
                        </div>

                        <div className="text-lg tabular text-ink mt-1">
                          {value}
                        </div>

                      </div>

                    )
                  )}

                </div>

              </div>


              {/* PERFORMANCE */}

              <div>

                <div className="text-2xs uppercase tracking-wide text-faint mb-3">
                  Performance profile
                </div>


                <div className="space-y-3">

                  {[
                    [
                      "75+",
                      performance.elite_75_plus,
                    ],

                    [
                      "65–74",
                      performance.strong_65_74,
                    ],

                    [
                      "55–64",
                      performance.development_55_64,
                    ],

                    [
                      "<55",
                      performance.below_55,
                    ],
                  ].map(
                    ([label, value]) => (

                      <div
                        key={
                          String(label)
                        }
                      >

                        <div className="flex justify-between text-2xs mb-1">

                          <span className="text-faint">
                            {label}
                          </span>

                          <span className="text-muted tabular">
                            {value}
                          </span>

                        </div>

                        <Bar
                          value={
                            Number(value)
                          }
                          max={
                            Math.max(
                              1,
                              result.squad_size
                            )
                          }
                        />

                      </div>

                    )
                  )}

                </div>

              </div>

            </section>

          </div>


          {/* FINDINGS */}

          <section className="mb-6">

            <h2 className="text-sm text-ink font-medium mb-3">
              Audit findings
            </h2>


            {findings.length === 0 ? (

              <EmptyState
                title="No significant gaps"
                body="The selected formation has no flagged depth, quality or succession findings."
              />

            ) : (

              <div className="space-y-2">

                {findings.map(
                  (
                    f: any,
                    i: number
                  ) => (

                    <div
                      key={i}
                      className={`border rounded-sm px-4 py-3 flex items-center justify-between gap-4 ${
                        SEVERITY_STYLE[
                          f.severity
                        ] || ""
                      }`}
                    >

                      <div>

                        <span className="text-2xs font-medium mr-2">
                          {f.severity}
                        </span>

                        <span className="text-2xs uppercase tracking-wide text-faint mr-3">
                          {f.category}
                        </span>

                        <span className="text-sm">
                          {f.message}
                        </span>

                      </div>


                      {Object.keys(
                        f.recruitment_filter ||
                        {}
                      ).length > 0 && (

                        <button
                          onClick={() =>
                            searchForFinding(
                              f.recruitment_filter
                            )
                          }
                          className="shrink-0 text-2xs border border-border rounded-sm px-2 py-1 text-ink hover:border-accent hover:text-accent transition-colors"
                        >
                          Find candidates
                        </button>

                      )}

                    </div>

                  )
                )}

              </div>

            )}

          </section>


          {/* CONTRACT OUTLOOK (additive; latest season only) */}

          <div className="mb-6">
            <ContractOutlook outlook={result?.contract_outlook} />
          </div>

          {/* SQUAD INSIGHTS: starters/backups, wages, age outlook (additive) */}

          <SquadInsights insights={result?.insights} />

          {/* DEPTH CHART */}

          <section className="mb-6">

            <h2 className="text-sm text-ink font-medium mb-3">
              Depth chart
            </h2>


            <div className="border border-border rounded-sm overflow-hidden bg-panel">

              <div className="overflow-x-auto">

                <table className="w-full text-sm">

                  <thead>

                    <tr className="border-b border-border text-2xs text-faint text-left">

                      <th className="px-3 py-2 font-normal">
                        Player
                      </th>

                      <th className="px-3 py-2 font-normal">
                        Position
                      </th>

                      <th className="px-3 py-2 font-normal">
                        Depth role
                      </th>

                      <th className="px-3 py-2 font-normal text-right">
                        Performance
                      </th>

                      <th className="px-3 py-2 font-normal text-right">
                        Age
                      </th>

                    </tr>

                  </thead>


                  <tbody>

                    {depth.map(
                      (p: any) => (

                        <tr
                          key={
                            p.player_id
                          }
                          className="border-b border-border last:border-0"
                        >

                          <td className="px-3 py-2 text-ink">
                            {p.short_name}
                          </td>

                          <td className="px-3 py-2 text-muted">
                            {p.canonical_position}
                          </td>

                          <td className="px-3 py-2 text-muted capitalize">
                            {p.depth_role}
                          </td>

                          <td className="px-3 py-2 text-right tabular text-ink">

                            {p.performance_score ==
                            null
                              ? "—"
                              : Number(
                                  p.performance_score
                                ).toFixed(1)}

                          </td>

                          <td className="px-3 py-2 text-right tabular text-muted">
                            {p.age_fifa ??
                              "—"}
                          </td>

                        </tr>

                      )
                    )}

                  </tbody>

                </table>

              </div>

            </div>

          </section>


          {/* METHODOLOGY */}

          <section className="border border-border bg-panel rounded-sm p-4">

            <h2 className="text-sm text-ink font-medium">
              Methodology & data boundary
            </h2>


            <div className="grid md:grid-cols-3 gap-5 mt-3 text-2xs leading-relaxed">

              <div>

                <div className="text-faint">
                  Depth
                </div>

                <div className="text-muted mt-1">
                  {result.methodology?.depth}
                </div>

              </div>


              <div>

                <div className="text-faint">
                  Succession
                </div>

                <div className="text-muted mt-1">
                  {result.methodology?.succession}
                </div>

              </div>


              <div>

                <div className="text-faint">
                  Quality / age
                </div>

                <div className="text-muted mt-1">

                  {result.methodology?.quality}

                  {" "}

                  {result.methodology?.age_balance}

                </div>

              </div>

            </div>

          </section>

        </>

      )}

    </div>
  );
}