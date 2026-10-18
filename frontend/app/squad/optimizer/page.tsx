"use client";

import { useEffect, useState } from "react";
import { api, formatEur } from "@/lib/api";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";
import TacticalPitch from "@/components/TacticalPitch";

const FORMATIONS = [
  "4-3-3",
  "4-2-3-1",
  "4-4-2",
  "3-4-3",
  "3-5-2",
];

const LEAGUES = [
  "Premier League",
  "La Liga",
  "Serie A",
  "Bundesliga",
  "Ligue 1",
  "Eredivisie",
];

const STRATEGIES = [
  {
    key: "balanced",
    label: "Balanced",
    description:
      "Current output + near-term projection + upside + value + evidence.",
  },
  {
    key: "performance",
    label: "Performance first",
    description:
      "Prioritizes current on-pitch production.",
  },
  {
    key: "development",
    label: "Development",
    description:
      "Prioritizes potential and 12-month expectation.",
  },
  {
    key: "value",
    label: "Value efficiency",
    description:
      "Prioritizes output relative to market value.",
  },
];

export default function SquadOptimizerPage() {
  const [formation, setFormation] = useState("4-3-3");
  const [budget, setBudget] = useState("300");
  const [league, setLeague] = useState("Premier League");

  // Initial defaults from the saved club profile (never overrides later edits).
  useEffect(() => {
    let alive = true;
    api.getClubProfile().then((d: any) => {
      if (!alive || !d?.configured || !d.profile) return;
      setFormation(d.profile.formation);
      if (d.profile.transfer_budget_eur != null) setBudget(String(Math.round(d.profile.transfer_budget_eur / 1_000_000)));
    }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const [maxAge, setMaxAge] = useState("");
  const [strategy, setStrategy] = useState("balanced");

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    selectedSeason,
    selectedLabel,
  } = useSeason();

  async function run() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.optimizeSquad({
        formation,
        budget_eur:
          Number(budget) * 1_000_000,
        league_name:
          league || undefined,
        max_age:
          maxAge
            ? Number(maxAge)
            : undefined,
        strategy,
        season: selectedSeason,
      });

      setResult(res);
    } catch (e: any) {
      setError(
        e.message ||
          "Optimization failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-[1500px]">

      <header className="mb-6">
        <div className="flex items-start justify-between gap-6">

          <div>
            <h1 className="text-xl text-ink font-medium">
              Squad optimizer
            </h1>

            <p className="text-muted text-sm mt-1 max-w-4xl">
              Build a legal XI under a hard budget using
              integer linear programming. Strategy changes
              the transparent objective weights; formation
              and budget remain hard constraints.
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


      <div className="border border-border rounded-sm bg-panel px-4 py-4 mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3 items-end">

        <Field label="Formation">
          <select
            value={formation}
            onChange={(e) =>
              setFormation(e.target.value)
            }
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink"
          >
            {FORMATIONS.map((f) => (
              <option
                key={f}
                value={f}
              >
                {f}
              </option>
            ))}
          </select>
        </Field>


        <Field label="Budget (€M)">
          <input
            type="number"
            min="0"
            value={budget}
            onChange={(e) =>
              setBudget(e.target.value)
            }
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink"
          />
        </Field>


        <Field label="Candidate pool (league)">
          <select
            value={league}
            onChange={(e) =>
              setLeague(e.target.value)
            }
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink"
          >
            {LEAGUES.map((l) => (
              <option
                key={l}
                value={l}
              >
                {l}
              </option>
            ))}
          </select>
        </Field>


        <Field label="Maximum age (optional)">
          <input
            type="number"
            min="15"
            max="45"
            value={maxAge}
            onChange={(e) =>
              setMaxAge(e.target.value)
            }
            placeholder="No limit"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </Field>


        <button
          onClick={run}
          disabled={
            loading ||
            !budget
          }
          className="bg-accent text-base font-medium text-sm rounded-sm px-4 py-1.5 hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {loading
            ? "Optimizing…"
            : "Optimize squad"}
        </button>

      </div>


      <section className="mb-6">

        <div className="flex items-end justify-between gap-4 mb-3">

          <div>
            <h2 className="text-sm text-ink font-medium">
              Optimization strategy
            </h2>

            <p className="text-2xs text-muted mt-1">
              Choose what the objective function emphasizes.
              There is no universal strategy winner.
            </p>
          </div>

        </div>


        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">

          {STRATEGIES.map(
            (item) => {

              const active =
                strategy === item.key;

              return (
                <button
                  key={item.key}
                  onClick={() =>
                    setStrategy(
                      item.key
                    )
                  }
                  className={`text-left border rounded-sm p-4 transition-colors ${
                    active
                      ? "border-accent bg-accent/5"
                      : "border-border bg-panel hover:border-muted"
                  }`}
                >

                  <div className="flex items-center justify-between gap-2">

                    <span className="text-sm text-ink font-medium">
                      {item.label}
                    </span>

                    {active && (
                      <span className="text-2xs text-accent">
                        Selected
                      </span>
                    )}

                  </div>

                  <p className="text-2xs text-muted mt-2 leading-relaxed">
                    {item.description}
                  </p>

                </button>
              );
            }
          )}

        </div>
      </section>


      {loading && (
        <LoadingState
          label="Solving formation and budget constraints"
        />
      )}

      {error && (
        <ErrorState
          message={error}
        />
      )}


      {result &&
        result.status !==
          "optimal" && (

          <div className="mb-6">

            <ErrorState
              message={
                result.reason ||
                `Solver status: ${result.status}`
              }
            />

            {result.candidate_pool_size !=
              null && (
              <div className="text-2xs text-muted mt-2">
                Candidate pool after filters:{" "}
                {result.candidate_pool_size}
              </div>
            )}

          </div>
        )}


      {result &&
        result.status ===
          "optimal" && (
        <>

          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-7 gap-3 mb-6">

            <Stat
              label="Total cost"
              value={formatEur(
                result.total_cost_eur
              )}
            />

            <Stat
              label="Budget remaining"
              value={formatEur(
                result.budget_remaining_eur
              )}
            />

            <Stat
              label="Budget used"
              value={
                result.budget_utilization_pct ==
                null
                  ? "—"
                  : `${result.budget_utilization_pct}%`
              }
            />

            <Stat
              label="Performance"
              value={
                result.projected_squad_quality
              }
            />

            <Stat
              label="Avg potential"
              value={
                result.average_potential ??
                "—"
              }
            />

            <Stat
              label="12M expected"
              value={
                result.average_expected_performance_12m ??
                "—"
              }
            />

            <Stat
              label="Avg age"
              value={
                result.average_age ??
                "—"
              }
            />

          </div>


          <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_.65fr] gap-4 mb-6">

            <TacticalPitch
              formation={
                formation
              }
              players={
                result.selected_players ||
                []
              }
              title="Optimized XI"
              subtitle="The ILP-selected XI mapped directly onto the requested formation."
              linkPlayers={false}
            />


            <div className="border border-border rounded-sm bg-panel p-4">

              <h2 className="text-sm text-ink font-medium">
                Optimization readout
              </h2>

              <p className="text-2xs text-muted mt-1 mb-3">
                Transparent context for the selected solution.
              </p>

              <Readout
                label="Strategy"
                value={
                  result.strategy_label
                }
              />

              <Readout
                label="Candidate pool"
                value={
                  result.candidate_pool_size
                }
              />

              <Readout
                label="Evidence reliability"
                value={
                  result.average_reliability ??
                  "—"
                }
              />

              <Readout
                label="Average value gap"
                value={
                  result.average_value_gap_pct ==
                  null
                    ? "—"
                    : `${result.average_value_gap_pct}%`
                }
              />

              <Readout
                label="Objective score"
                value={
                  result.objective_score
                }
              />

              <Readout
                label="Players selected"
                value={
                  result.selected_count
                }
              />

            </div>

          </div>


          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">

            <section className="border border-border bg-panel rounded-sm p-4">

              <h2 className="text-sm text-ink font-medium">
                Selected XI decision matrix
              </h2>

              <p className="text-2xs text-muted mt-1 mb-4">
                Player-level evidence used by the objective function.
              </p>


              <div className="overflow-x-auto">

                <table className="w-full text-sm">

                  <thead>
                    <tr className="border-b border-border text-2xs text-faint text-left">

                      <th className="px-3 py-2 font-normal">
                        Player
                      </th>

                      <th className="px-3 py-2 font-normal">
                        Pos
                      </th>

                      <th className="px-3 py-2 font-normal text-right">
                        Perf
                      </th>

                      <th className="px-3 py-2 font-normal text-right">
                        Potential
                      </th>

                      <th className="px-3 py-2 font-normal text-right">
                        12M
                      </th>

                      <th className="px-3 py-2 font-normal text-right">
                        Value
                      </th>

                    </tr>
                  </thead>


                  <tbody>

                    {result.selected_players?.map(
                      (
                        p: any,
                        i: number
                      ) => (

                        <tr
                          key={
                            p.player_id ||
                            i
                          }
                          className="border-b border-border last:border-0"
                        >

                          <td className="px-3 py-2 text-ink">
                            {p.short_name}
                          </td>

                          <td className="px-3 py-2 text-muted">
                            {p.canonical_position}
                          </td>

                          <td className="px-3 py-2 text-right tabular text-ink">
                            {num(
                              p.performance_score
                            )}
                          </td>

                          <td className="px-3 py-2 text-right tabular text-muted">
                            {num(
                              p.development_potential
                            )}
                          </td>

                          <td className="px-3 py-2 text-right tabular text-muted">
                            {num(
                              p.expected_performance_12m
                            )}
                          </td>

                          <td className="px-3 py-2 text-right tabular text-muted">
                            {formatEur(
                              p.value_eur
                            )}
                          </td>

                        </tr>
                      )
                    )}

                  </tbody>

                </table>

              </div>

            </section>


            <section className="border border-border bg-panel rounded-sm p-4">

              <h2 className="text-sm text-ink font-medium">
                Objective weights
              </h2>

              <p className="text-2xs text-muted mt-1 mb-4">
                Normalized inputs used in this run.
              </p>

              <Weight
                label="Current performance"
                value={
                  result.strategy_weights
                    ?.performance
                }
              />

              <Weight
                label="12-month expectation"
                value={
                  result.strategy_weights
                    ?.expected_12m
                }
              />

              <Weight
                label="Development potential"
                value={
                  result.strategy_weights
                    ?.potential
                }
              />

              <Weight
                label="Value efficiency"
                value={
                  result.strategy_weights
                    ?.value
                }
              />

              <Weight
                label="Evidence reliability"
                value={
                  result.strategy_weights
                    ?.reliability
                }
              />

              <p className="text-2xs text-faint mt-4 leading-relaxed">
                {result.strategy_description}
              </p>

            </section>

          </div>


          <section className="border border-border bg-panel rounded-sm p-4 mb-6">

            <h2 className="text-sm text-ink font-medium">
              Methodology & data boundary
            </h2>

            <div className="grid md:grid-cols-3 gap-5 mt-3 text-2xs leading-relaxed">

              <div>
                <div className="text-faint">
                  Optimization
                </div>

                <div className="text-muted mt-1">
                  {result.methodology
                    ?.optimization}
                </div>
              </div>


              <div>
                <div className="text-faint">
                  Objective
                </div>

                <div className="text-muted mt-1">
                  {result.methodology
                    ?.objective}
                </div>
              </div>


              <div>
                <div className="text-faint">
                  Market data
                </div>

                <div className="text-muted mt-1">
                  {result.methodology
                    ?.value_boundary}
                </div>
              </div>

            </div>

          </section>

        </>
      )}


      {!result &&
        !loading &&
        !error && (
          <EmptyState
            title="Ready to optimize"
            body="Choose the formation, budget, candidate pool and strategy, then run the ILP."
          />
        )}

    </div>
  );
}


function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">

      <div className="text-2xs text-faint mb-1">
        {label}
      </div>

      {children}

    </label>
  );
}


function Stat({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="border border-border bg-panel rounded-sm px-4 py-3">

      <div className="text-2xs text-faint mb-1">
        {label}
      </div>

      <div className="text-xl text-ink tabular font-medium">
        {value}
      </div>

    </div>
  );
}


function Readout({
  label,
  value,
}: {
  label: string;
  value: any;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">

      <span className="text-2xs text-faint">
        {label}
      </span>

      <span className="text-sm text-ink tabular">
        {value ?? "—"}
      </span>

    </div>
  );
}


function Weight({
  label,
  value,
}: {
  label: string;
  value: number | undefined;
}) {
  const pct = Math.round(
    (value ?? 0) * 100
  );

  return (
    <div className="mb-3">

      <div className="flex justify-between text-2xs mb-1">

        <span className="text-muted">
          {label}
        </span>

        <span className="text-ink tabular">
          {pct}%
        </span>

      </div>

      <div className="h-1.5 bg-panelraised rounded-full overflow-hidden">

        <div
          className="h-full bg-accent"
          style={{
            width: `${pct}%`,
          }}
        />

      </div>

    </div>
  );
}


function num(value: any) {
  return value == null ||
    Number.isNaN(Number(value))
    ? "—"
    : Number(value).toFixed(1);
}