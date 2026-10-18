"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, formatEur, PlayerSummary } from "@/lib/api";
import { RiskBadge, PlayerLink, LoadingState, EmptyState } from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";

const POSITIONS = ["GK", "CB", "LB", "RB", "LWB", "RWB", "CDM", "CM", "CAM", "LW", "RW", "ST", "CF"];

export default function ScoutingSearchPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <ScoutingSearchInner />
    </Suspense>
  );
}

function ScoutingSearchInner() {
  const searchParams = useSearchParams();
  const { selectedSeason, selectedLabel } = useSeason();
  const [position, setPosition] = useState(searchParams.get("position") || "");
  const [maxAge, setMaxAge] = useState(searchParams.get("maxAge") || "");
  const [maxValue, setMaxValue] = useState("");
  const [minPerformance, setMinPerformance] = useState(searchParams.get("minPerformance") || "");
  const [minThreeYear, setMinThreeYear] = useState("");
  const [minFiveYear, setMinFiveYear] = useState("");
  const [minTrend, setMinTrend] = useState("");
  const [maxConsistency, setMaxConsistency] = useState("");
  const [minCareerMinutes, setMinCareerMinutes] = useState("");
  const [minSeasons, setMinSeasons] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [results, setResults] = useState<PlayerSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [shortlists, setShortlists] = useState<{ id: number; name: string; entry_count: number }[]>([]);
  const [addTarget, setAddTarget] = useState<string | null>(null);
  const [selectedShortlist, setSelectedShortlist] = useState<number | "new" | "">("");
  const [newShortlistName, setNewShortlistName] = useState("");

  useEffect(() => { api.listShortlists().then(r => setShortlists(r.results)).catch(() => {}); }, []);

  async function addPlayerToShortlist(playerId: string) {
    try {
      let shortlistId = typeof selectedShortlist === "number" ? selectedShortlist : undefined;
      if (!shortlistId) {
        const name = newShortlistName.trim() || "New scouting targets";
        const created = await api.createShortlist(name);
        shortlistId = created.id;
        setShortlists(prev => [{ id: created.id, name: created.name, entry_count: 0 }, ...prev]);
        setSelectedShortlist(created.id);
      }
      await api.addToShortlist(shortlistId, { player_id: playerId });
      setAddTarget(null);
      const refreshed = await api.listShortlists();
      setShortlists(refreshed.results);
    } catch { /* keep search usable if persistence is unavailable */ }
  }

  async function runSearch(overrides?: { position?: string; maxAge?: string; minPerformance?: string }) {
    setLoading(true);
    setSearched(true);
    try {
      const body: Record<string, unknown> = { top_n: 30 };
      if (selectedSeason !== null) body.season = selectedSeason;
      const pos = overrides?.position ?? position;
      const age = overrides?.maxAge ?? maxAge;
      const perf = overrides?.minPerformance ?? minPerformance;
      if (pos) body.canonical_position = pos;
      if (age) body.max_age = Number(age);
      if (maxValue) body.max_value_eur = Number(maxValue) * 1_000_000;
      if (perf) body.min_performance_score = Number(perf);
      if (minThreeYear) body.min_three_year_avg_performance = Number(minThreeYear);
      if (minFiveYear) body.min_five_year_avg_performance = Number(minFiveYear);
      if (minTrend) body.min_performance_trend = Number(minTrend);
      if (maxConsistency) body.max_performance_consistency_std = Number(maxConsistency);
      if (minCareerMinutes) body.min_career_minutes = Number(minCareerMinutes);
      if (minSeasons) body.min_seasons_played = Number(minSeasons);
      const res = await api.scoutingSearch(body);
      setResults(res.results);
      setTotal(res.total);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  // Arriving from a squad-audit finding ("Find candidates") pre-fills
  // filters via query params and runs the search immediately, instead of
  // making the user re-enter what the audit already told us.
  useEffect(() => {
    const qPosition = searchParams.get("position");
    const qMaxAge = searchParams.get("maxAge");
    const qMinPerformance = searchParams.get("minPerformance");
    if (selectedSeason !== null && (qPosition || qMaxAge || qMinPerformance)) {
      runSearch({
        position: qPosition || undefined,
        maxAge: qMaxAge || undefined,
        minPerformance: qMinPerformance || undefined,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSeason]);

  useEffect(() => {
    if (selectedSeason !== null && searched) runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSeason]);

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-xl text-ink font-medium">Player search</h1>
        <p className="text-muted text-sm mt-1">
          Filter the {selectedLabel} candidate pool and rank by performance score.
        </p>
      </header>

      <div className="border border-border rounded-sm bg-panel px-4 py-4 mb-6 grid grid-cols-5 gap-3 items-end">
        <Field label="Position">
          <select
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink"
          >
            <option value="">Any</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </Field>
        <Field label="Max age">
          <input
            type="number"
            value={maxAge}
            onChange={(e) => setMaxAge(e.target.value)}
            placeholder="e.g. 26"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </Field>
        <Field label="Max value (€M)">
          <input
            type="number"
            value={maxValue}
            onChange={(e) => setMaxValue(e.target.value)}
            placeholder="e.g. 40"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </Field>
        <Field label="Min performance">
          <input
            type="number"
            value={minPerformance}
            onChange={(e) => setMinPerformance(e.target.value)}
            placeholder="0–100"
            className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
          />
        </Field>
        <button
          onClick={() => runSearch()}
          className="bg-accent text-base font-medium text-sm rounded-sm px-4 py-1.5 hover:bg-accent/90 transition-colors"
        >
          Search
        </button>
      </div>

      <div className="mb-6">
        <button onClick={() => setAdvanced(v => !v)} className="text-xs text-accent hover:text-ink">
          {advanced ? "Hide historical filters" : "Show historical filters"}
        </button>
        {advanced && (
          <div className="mt-3 border border-border rounded-sm bg-panel px-4 py-4 grid grid-cols-3 gap-3">
            <Field label="Min 3Y avg performance">
              <input type="number" value={minThreeYear} onChange={e => setMinThreeYear(e.target.value)} placeholder="e.g. 65" className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint" />
            </Field>
            <Field label="Min 5Y avg performance">
              <input type="number" value={minFiveYear} onChange={e => setMinFiveYear(e.target.value)} placeholder="e.g. 62" className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint" />
            </Field>
            <Field label="Min trend / season">
              <input type="number" step="0.1" value={minTrend} onChange={e => setMinTrend(e.target.value)} placeholder="e.g. 2" className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint" />
            </Field>
            <Field label="Max consistency SD">
              <input type="number" step="0.1" value={maxConsistency} onChange={e => setMaxConsistency(e.target.value)} placeholder="e.g. 8" className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint" />
            </Field>
            <Field label="Min career minutes">
              <input type="number" value={minCareerMinutes} onChange={e => setMinCareerMinutes(e.target.value)} placeholder="e.g. 5000" className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint" />
            </Field>
            <Field label="Min seasons played">
              <input type="number" value={minSeasons} onChange={e => setMinSeasons(e.target.value)} placeholder="e.g. 3" className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint" />
            </Field>
            <div className="col-span-3 text-2xs text-faint">
              Historical filters are calculated through the selected analysis season. Trend uses seasons with at least 900 minutes; consistency is the standard deviation of performance across the last five available seasons.
            </div>
          </div>
        )}
      </div>

      {loading && <LoadingState label="Searching" />}

      {!loading && searched && results.length === 0 && (
        <EmptyState title="No players match these filters" body="Try widening the age or value range." />
      )}

      {!loading && results.length > 0 && (
        <div className="border border-border rounded-sm overflow-hidden">
          <div className="px-3 py-2 text-2xs text-faint border-b border-border">
            {total.toLocaleString()} players matched — showing top {results.length}
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-2xs text-faint text-left">
                <th className="px-3 py-2 font-normal">Player</th>
                <th className="px-3 py-2 font-normal">Pos</th>
                <th className="px-3 py-2 font-normal">Club</th>
                <th className="px-3 py-2 font-normal">League</th>
                <th className="px-3 py-2 font-normal text-right">Age</th>
                <th className="px-3 py-2 font-normal text-right">Value</th>
                <th className="px-3 py-2 font-normal text-right">Performance</th>
                <th className="px-3 py-2 font-normal text-right">Potential</th>
                <th className="px-3 py-2 font-normal text-right">3Y avg</th>
                <th className="px-3 py-2 font-normal text-right">Trend</th>
                <th className="px-3 py-2 font-normal">Risk</th>
                <th className="px-3 py-2 font-normal text-right">Scout</th>
              </tr>
            </thead>
            <tbody>
              {results.map((p) => (
                <tr key={p.player_id} className="border-b border-border last:border-0 hover:bg-panel/60">
                  <td className="px-3 py-2">
                    <PlayerLink playerId={p.player_id} name={p.short_name} />
                  </td>
                  <td className="px-3 py-2 text-muted">{p.canonical_position}</td>
                  <td className="px-3 py-2 text-muted">{p.club_name}</td>
                  <td className="px-3 py-2 text-muted">{p.league_name}</td>
                  <td className="px-3 py-2 text-right tabular text-muted">{p.age_fifa}</td>
                  <td className="px-3 py-2 text-right tabular text-muted">{formatEur(p.value_eur)}</td>
                  <td className="px-3 py-2 text-right tabular text-ink">{p.performance_score?.toFixed(1)}</td>
                  <td className="px-3 py-2 text-right tabular text-muted">{p.development_potential?.toFixed(1)}</td>
                  <td className="px-3 py-2 text-right tabular text-muted">{p.three_year_avg_performance?.toFixed(1) ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular text-muted">{p.performance_trend_per_season != null ? `${p.performance_trend_per_season >= 0 ? "+" : ""}${p.performance_trend_per_season.toFixed(1)}` : "—"}</td>
                  <td className="px-3 py-2"><RiskBadge tier={p.recruitment_risk_tier} /></td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => setAddTarget(p.player_id)} className="text-2xs text-accent hover:text-ink">Add</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {addTarget && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setAddTarget(null)}>
          <div className="w-full max-w-md analytics-panel p-5" onClick={e => e.stopPropagation()}>
            <div className="text-ink font-medium">Add to scout workspace</div>
            <div className="text-xs text-muted mt-1">Choose where to track this player.</div>
            <select value={selectedShortlist} onChange={e => setSelectedShortlist(e.target.value === "new" ? "new" : e.target.value ? Number(e.target.value) : "")} className="w-full mt-4 bg-panelraised border border-border rounded-sm px-3 py-2 text-sm text-ink">
              <option value="">Create new shortlist…</option>
              {shortlists.map(s => <option key={s.id} value={s.id}>{s.name} ({s.entry_count})</option>)}
            </select>
            {!selectedShortlist || selectedShortlist === "new" ? <input value={newShortlistName} onChange={e => setNewShortlistName(e.target.value)} placeholder="Shortlist name" className="w-full mt-2 bg-panelraised border border-border rounded-sm px-3 py-2 text-sm text-ink placeholder:text-faint" /> : null}
            <div className="flex justify-end gap-2 mt-4"><button onClick={() => setAddTarget(null)} className="action-button">Cancel</button><button onClick={() => addPlayerToShortlist(addTarget)} className="action-button action-button-primary">Add player</button></div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-2xs text-faint mb-1">{label}</div>
      {children}
    </label>
  );
}
