"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, formatEur, PlayerSummary } from "@/lib/api";
import { PlayerPicker } from "@/components/PlayerPicker";
import { RiskBadge, PlayerLink, LoadingState, ErrorState, EmptyState } from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";

function pct(value: number | null | undefined) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }

  return `${Number(value).toFixed(1)}`;
}

function ScenarioCard({
  scenario,
  candidates,
}: {
  scenario: any;
  candidates: any[];
}) {
  const player = candidates.find(
    (candidate) =>
      candidate.player_id === scenario.player_id
  );

  return (
    <div className="border border-border bg-panel rounded-sm p-4">
      <div className="text-2xs uppercase tracking-wide text-faint">
        {scenario.label}
      </div>

      <div className="text-sm text-ink mt-2">
        {player?.short_name || scenario.player_id}
      </div>

      <div className="text-2xs text-muted mt-2">
        {scenario.description}
      </div>

      {player && (
        <div className="grid grid-cols-2 gap-2 mt-4">
          <div>
            <div className="text-2xs text-faint">Fit</div>
            <div className="text-sm tabular text-ink">
              {pct(player.replacement_fit_score)}
            </div>
          </div>

          <div>
            <div className="text-2xs text-faint">Value</div>
            <div className="text-sm tabular text-ink">
              {formatEur(player.value_eur)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SkillComparison({ candidate }: { candidate: any }) {
  const [open, setOpen] = useState(false);
  const rows: any[] = candidate.component_comparison || [];
  if (rows.length === 0) return null;
  const join = (items: any[]) => items.map((i) => `${i.label} (${i.points > 0 ? "+" : "-"}${Math.abs(i.points)})`).join(", ");
  return (
    <div className="mt-4 border-t border-border pt-3">
      <div className="text-xs text-muted space-y-1">
        {candidate.similar_in?.length > 0 && <div><span className="text-ink">Similar in</span> {candidate.similar_in.join(", ")}</div>}
        {candidate.better_in?.length > 0 && <div><span className="text-risklow">Better in</span> {join(candidate.better_in)}</div>}
        {candidate.weaker_in?.length > 0 && <div><span className="text-riskhigh">Weaker in</span> {join(candidate.weaker_in)}</div>}
        {!candidate.similar_in?.length && !candidate.better_in?.length && !candidate.weaker_in?.length && <div>No clear differences in skill areas.</div>}
      </div>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="mt-2 text-2xs text-accent hover:underline">
        {open ? "Hide skill-by-skill comparison" : "Show skill-by-skill comparison"}
      </button>
      {open && (
        <table className="w-full text-2xs mt-2">
          <thead><tr className="text-faint text-left"><th className="py-1 font-normal">Skill area (0-100)</th><th className="font-normal">Outgoing</th><th className="font-normal">Candidate</th><th className="font-normal">Difference</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-t border-border">
                <td className="py-1 text-ink">{r.label}</td><td className="text-muted tabular">{r.outgoing}</td><td className="text-muted tabular">{r.candidate}</td>
                <td className={`tabular ${r.difference >= 8 ? "text-risklow" : r.difference <= -8 ? "text-riskhigh" : "text-muted"}`}>{r.difference > 0 ? "+" : ""}{r.difference}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {candidate.contract?.contract_expires && (
        <div className="mt-2 text-2xs text-faint">Contract (Transfermarkt, current): {candidate.contract.contract_status} · ends {candidate.contract.contract_expires}</div>
      )}
    </div>
  );
}

function CandidateCard({
  candidate,
}: {
  candidate: any;
}) {
  return (
    <div className="border border-border bg-panel rounded-sm p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <PlayerLink
            playerId={candidate.player_id}
            name={candidate.short_name}
          />

          <div className="text-xs text-muted mt-1">
            {candidate.canonical_position || "—"}
            {" · "}
            {candidate.club_name || "—"}
            {" · "}
            {candidate.league_name || "—"}
          </div>
        </div>

        <div className="text-right shrink-0">
          <div className="text-2xs text-faint">
            Replacement fit
          </div>

          <div className="text-xl tabular text-ink">
            {pct(candidate.replacement_fit_score)}
          </div>

          <RiskBadge tier={candidate.recruitment_risk_tier} />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mt-5">
        <div>
          <div className="text-2xs text-faint">Performance</div>
          <div className="text-sm tabular text-ink">
            {candidate.performance_score ?? "—"}
          </div>
        </div>

        <div>
          <div className="text-2xs text-faint">Potential</div>
          <div className="text-sm tabular text-ink">
            {candidate.development_potential ?? "—"}
          </div>
        </div>

        <div>
          <div className="text-2xs text-faint">12M expected</div>
          <div className="text-sm tabular text-ink">
            {candidate.expected_performance_12m ?? "—"}
          </div>
        </div>

        <div>
          <div className="text-2xs text-faint">Value</div>
          <div className="text-sm tabular text-ink">
            {formatEur(candidate.value_eur)}
          </div>
        </div>

        <div>
          <div className="text-2xs text-faint">Fair value</div>
          <div className="text-sm tabular text-ink">
            {formatEur(candidate.fair_value_eur)}
          </div>
        </div>

        <div>
          <div className="text-2xs text-faint">Minutes</div>
          <div className="text-sm tabular text-ink">
            {candidate.playing_time_min ?? "—"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4 text-2xs">
        {[
          ["Tactical", candidate.tactical_similarity],
          ["Statistical", candidate.statistical_similarity],
          ["Physical", candidate.physical_similarity],
          ["Market", candidate.market_similarity],
        ].map(([label, value]) => (
          <div
            key={label}
            className="border border-border rounded-sm px-2 py-2"
          >
            <span className="text-faint">{label}</span>
            <div className="text-ink tabular mt-0.5">
              {pct(value as number | null)}
            </div>
          </div>
        ))}
      </div>

      {(candidate.advantages?.length > 0 ||
        candidate.watchouts?.length > 0) && (
        <div className="grid md:grid-cols-2 gap-3 mt-4">
          {candidate.advantages?.length > 0 && (
            <div>
              <div className="text-2xs uppercase tracking-wide text-faint mb-1">
                Advantages
              </div>
              <div className="space-y-1">
                {candidate.advantages.map(
                  (item: string, index: number) => (
                    <div
                      key={`${candidate.player_id}-advantage-${index}`}
                      className="text-2xs text-muted"
                    >
                      + {item}
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {candidate.watchouts?.length > 0 && (
            <div>
              <div className="text-2xs uppercase tracking-wide text-faint mb-1">
                Watchouts
              </div>
              <div className="space-y-1">
                {candidate.watchouts.map(
                  (item: string, index: number) => (
                    <div
                      key={`${candidate.player_id}-watchout-${index}`}
                      className="text-2xs text-muted"
                    >
                      {item}
                    </div>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <SkillComparison candidate={candidate} />
    </div>
  );
}

export default function ReplacementPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ReplacementInner />
    </Suspense>
  );
}

function ReplacementInner() {
  const searchParams = useSearchParams();
  const [outgoing, setOutgoing] = useState<PlayerSummary | null>(null);
  const [budget, setBudget] = useState("");
  const [minAge, setMinAge] = useState("");
  const [maxAge, setMaxAge] = useState("");
  const [sameGroup, setSameGroup] = useState(true);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { selectedSeason, selectedLabel } = useSeason();

  const scenarios = useMemo(
    () => result?.scenarios ?? [],
    [result]
  );

  const candidates = useMemo(
    () => result?.candidates ?? [],
    [result]
  );

  async function runSearch(playerId: string) {
    if (selectedSeason === null) return;

    setLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { outgoing_player_id: playerId, top_n: 10, season: selectedSeason };
      if (budget) body.budget_eur = Number(budget) * 1_000_000;
      if (minAge) body.min_age = Number(minAge);
      if (maxAge) body.max_age = Number(maxAge);
      body.restrict_to_position_group = sameGroup;
      const res = await api.findReplacements(body);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Replacement search failed.");
    } finally {
      setLoading(false);
    }
  }

  // Arriving from a player profile's "Find replacement" link.
  useEffect(() => {
    const pid = searchParams.get("for");
    if (pid) {
      api.getPlayer(pid, selectedSeason).then((p) => {
        setOutgoing(p);
        runSearch(pid);
      }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSeason]);

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl text-ink font-medium">Replacement finder</h1>
        <p className="text-muted text-sm mt-1">
          Find who could replace an outgoing player in {selectedLabel} — ranked by tactical and statistical fit,
          constrained by budget and age, with cheaper alternatives called out explicitly.
        </p>
      </header>

      <div className="border border-border rounded-sm bg-panel px-4 py-4 mb-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-[minmax(220px,2fr)_repeat(3,minmax(110px,1fr))_auto] gap-3 items-end">
        <div>
          <div className="text-2xs text-faint mb-1">Outgoing player</div>
          <PlayerPicker season={selectedSeason} onSelect={(p) => { setOutgoing(p); }} placeholder="Search for the player leaving..." />
          {outgoing && <div className="text-xs text-accent mt-1">{outgoing.short_name}</div>}
        </div>
        <label className="block">
          <div className="text-2xs text-faint mb-1">Budget (€M)</div>
          <input
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            placeholder="optional"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </label>
        <label className="block">
          <div className="text-2xs text-faint mb-1">Min age</div>
          <input
            type="number"
            min="0"
            value={minAge}
            onChange={(e) => setMinAge(e.target.value)}
            placeholder="optional"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </label>
        <label className="block">
          <div className="text-2xs text-faint mb-1">Max age</div>
          <input
            type="number"
            min="0"
            value={maxAge}
            onChange={(e) => setMaxAge(e.target.value)}
            placeholder="optional"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </label>
        <button
          onClick={() => outgoing && runSearch(outgoing.player_id)}
          disabled={!outgoing}
          className="bg-accent text-base font-medium text-sm rounded-sm px-4 py-1.5 hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed col-span-1"
        >
          Find replacements
        </button>
      </div>

      <fieldset className="mb-4 text-xs text-muted">
        <legend className="text-2xs text-faint mb-1">Match players who are</legend>
        <label className="mr-5"><input type="radio" name="scope" checked={sameGroup} onChange={() => setSameGroup(true)} className="mr-1.5" />in the same position group (recommended)</label>
        <label><input type="radio" name="scope" checked={!sameGroup} onChange={() => setSameGroup(false)} className="mr-1.5" />similar in style, any position</label>
        {!sameGroup && <p className="mt-1 text-2xs text-riskmed">Cross-position results describe style similarity only. Confirm a candidate can actually play the role before treating him as a replacement.</p>}
      </fieldset>

      {loading && <LoadingState label="Searching" />}
      {error && <ErrorState message={error} />}

      {result && candidates.length === 0 && (
        <EmptyState
          title="No candidates matched"
          body={result.note || "Try widening the age or budget constraints."}
        />
      )}

      {result && candidates.length > 0 && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
            <div className="text-xs text-muted">
              Replacing <span className="text-ink">{result.outgoing_player?.short_name}</span>
              {" · "}
              {formatEur(result.outgoing_player?.value_eur)}
              {" · age "}
              {result.outgoing_player?.age_fifa ?? "—"}
            </div>

            <div className="text-xs text-muted">
              <span className="text-ink tabular">
                {result.candidate_pool_size ?? candidates.length}
              </span>
              {" qualify; showing top "}
              {candidates.length}
            </div>
          </div>

          {scenarios.length > 0 && (
            <section className="mb-6">
              <div className="mb-3">
                <h2 className="text-sm font-medium text-ink">
                  Replacement scenarios
                </h2>
                <p className="text-2xs text-muted mt-1">
                  Different recruitment paths from the same qualifying pool.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {scenarios.map((scenario: any) => (
                  <ScenarioCard
                    key={scenario.key}
                    scenario={scenario}
                    candidates={candidates}
                  />
                ))}
              </div>
            </section>
          )}

          <section className="mb-6">
            <div className="mb-3">
              <h2 className="text-sm font-medium text-ink">
                Candidate intelligence
              </h2>
              <p className="text-2xs text-muted mt-1">
                Candidates are ordered by the transparent replacement-fit blend; facet scores remain visible for review.
              </p>
            </div>

            <div className="space-y-3">
              {candidates.map((candidate: any) => (
                <CandidateCard
                  key={candidate.player_id}
                  candidate={candidate}
                />
              ))}
            </div>
          </section>

          <section className="border border-border bg-panel rounded-sm p-4">
            <h2 className="text-sm font-medium text-ink">
              Methodology
            </h2>

            <div className="grid md:grid-cols-2 gap-4 mt-3 text-2xs text-muted leading-relaxed">
              <div>
                <div>Position constraint</div>
                <div className="text-ink mt-1">
                  {result.methodology?.position_constraint}
                </div>
              </div>

              <div>
                <div>Replacement fit</div>
                <div className="text-ink mt-1">
                  Tactical 35% · Statistical 35% · Physical 15% · Market 15%
                </div>
              </div>

              <div>
                <div>Scenario interpretation</div>
                <div className="text-ink mt-1">
                  {result.methodology?.scenario_note}
                </div>
              </div>

              <div>
                <div>Data boundary</div>
                <div className="text-ink mt-1">
                  The tool identifies profile matches from the selected season. It does not infer contract expiry, transfer availability, or scouting observations absent from the dataset.
                </div>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
