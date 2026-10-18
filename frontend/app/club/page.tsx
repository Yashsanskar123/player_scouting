"use client";

import { useEffect, useState } from "react";
import { api, formatEur } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";
import ContractOutlook from "@/components/ContractOutlook";
import DownloadButton from "@/components/DownloadButton";
import ClubSwitcher from "@/components/ClubSwitcher";
import ClubCompare from "@/components/ClubCompare";

const inputClass = "mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none";

export default function ClubProfilePage() {
  const { selectedSeason, selectedLabel } = useSeason();
  const [clubs, setClubs] = useState<any[]>([]);
  const [formations, setFormations] = useState<string[]>(["4-3-3"]);
  const [club, setClub] = useState("");
  const [formation, setFormation] = useState("4-3-3");
  const [transferM, setTransferM] = useState("");
  const [wageM, setWageM] = useState("");
  const [overview, setOverview] = useState<any>(null);
  const [saved, setSaved] = useState(false);
  const [savedClubs, setSavedClubs] = useState<any[]>([]);
  const [activeClub, setActiveClub] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshOverview() {
    try {
      setOverview(await api.getClubOverview(selectedSeason));
    } catch (e: any) {
      setOverview(null);
    }
  }

  // Apply a server profile state (active club + saved list) to the form.
  function applyState(d: any) {
    setSavedClubs(d?.clubs || []);
    setActiveClub(d?.profile?.club_name || null);
    if (d?.formations?.length) setFormations(d.formations);
    if (d?.configured && d.profile) {
      setClub(d.profile.club_name);
      setFormation(d.profile.formation);
      setTransferM(d.profile.transfer_budget_eur != null ? String(Math.round(d.profile.transfer_budget_eur / 1e6)) : "");
      setWageM(d.profile.wage_budget_eur != null ? String(Math.round(d.profile.wage_budget_eur / 1e6)) : "");
      setSaved(true);
    } else {
      setSaved(false);
      setOverview(null);
      setClub("");
      setTransferM("");
      setWageM("");
    }
  }

  // Load saved profiles once.
  useEffect(() => {
    let alive = true;
    api.getClubProfile().then((d: any) => { if (alive) applyState(d); })
      .catch((e: any) => alive && setError(e.message || "Could not load club profile."))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  // Club list and overview follow the global season.
  useEffect(() => {
    api.getClubs(selectedSeason).then((d: any) => setClubs(d?.clubs || [])).catch(() => setClubs([]));
    if (saved) refreshOverview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSeason, saved, activeClub]);

  async function save() {
    setError(null);
    try {
      await api.saveClubProfile({
        club_name: club,
        formation,
        transfer_budget_eur: transferM === "" ? null : Number(transferM) * 1_000_000,
        wage_budget_eur: wageM === "" ? null : Number(wageM) * 1_000_000,
      });
      applyState(await api.getClubProfile());
      await refreshOverview();
    } catch (e: any) {
      setError(e.message || "Could not save club profile.");
    }
  }

  async function reset() {
    if (!activeClub) return;
    await removeClub(activeClub);
  }

  async function removeClub(name: string) {
    setError(null);
    try {
      await api.deleteClubProfile(name);
      applyState(await api.getClubProfile());
    } catch (e: any) {
      setError(e.message || "Could not remove club.");
    }
  }

  async function switchClub(name: string) {
    setError(null);
    try {
      await api.activateClub(name);
      applyState(await api.getClubProfile());
    } catch (e: any) {
      setError(e.message || "Could not switch club.");
    }
  }

  if (loading) return <LoadingState label="Loading club profile" />;

  const leagues = Array.from(new Set(clubs.map((c) => c.league_name || "Other")));
  const priorities: any[] = overview?.recruitment_priorities || [];

  return (
    <div className="p-6 max-w-[1200px]">
      <h1 className="text-lg text-ink font-medium">Club profile</h1>
      <p className="text-xs text-muted mt-1">
        Set your club, formation and budgets once. Squad Audit and Squad Optimizer start from these values. Analysis season: {selectedLabel}.
      </p>

      {error && <div className="mt-4"><ErrorState message={error} /></div>}

      <section className="border border-border bg-panel rounded-sm p-4 mt-5">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <label className="text-2xs text-faint md:col-span-2">
            Club (clubs available in {selectedLabel})
            <select value={club} onChange={(e) => setClub(e.target.value)} className={inputClass}>
              <option value="">Select a club</option>
              {saved && club && !clubs.some((c) => c.club_name === club) && <option value={club}>{club}</option>}
              {leagues.map((lg) => (
                <optgroup key={lg} label={lg}>
                  {clubs.filter((c) => (c.league_name || "Other") === lg).map((c) => (
                    <option key={c.club_name} value={c.club_name}>{c.club_name}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <label className="text-2xs text-faint">
            Formation
            <select value={formation} onChange={(e) => setFormation(e.target.value)} className={inputClass}>
              {formations.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label className="text-2xs text-faint">
            Transfer budget (€ million)
            <input type="number" min="0" value={transferM} onChange={(e) => setTransferM(e.target.value)} className={inputClass} placeholder="e.g. 120" />
          </label>
          <label className="text-2xs text-faint">
            Wage budget (€ million, optional)
            <input type="number" min="0" value={wageM} onChange={(e) => setWageM(e.target.value)} className={inputClass} placeholder="e.g. 200" />
          </label>
        </div>
        <div className="flex gap-3 mt-4">
          <button onClick={save} disabled={!club} className="px-4 py-2 text-xs rounded-sm bg-accent text-black font-medium disabled:opacity-40">
            Save club profile
          </button>
          {saved && <DownloadButton label="Download PDF report" onDownload={() => api.downloadClubReport(selectedSeason)} />}
          {saved && (
            <button onClick={reset} className="px-4 py-2 text-xs rounded-sm border border-border text-muted hover:text-ink">
              Remove this club
            </button>
          )}
        </div>
      </section>

      <ClubSwitcher clubs={savedClubs} active={activeClub} onSwitch={switchClub} onRemove={removeClub} />

      {saved && overview && overview.available === false && (
        <p className="text-xs text-muted mt-5">{overview.reason} Pick another season to see this club's squad.</p>
      )}

      {saved && overview?.available && (
        <>
          <section className="border border-border bg-panel rounded-sm p-4 mt-5">
            <h2 className="text-sm text-ink font-medium">{overview.profile.club_name} · {selectedLabel}</h2>
            <p className="text-2xs text-faint mt-1">{overview.league_name || "League not listed"} · formation {overview.profile.formation}</p>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
              {[
                ["Squad size", String(overview.roster_size)],
                ["Average age", overview.average_age != null ? String(overview.average_age) : "—"],
                ["Average performance", overview.average_performance != null ? String(overview.average_performance) : "—"],
                ["Squad market value", formatEur(overview.squad_market_value_eur)],
                ["Transfer budget", overview.profile.transfer_budget_eur != null ? formatEur(overview.profile.transfer_budget_eur) : "Not set"],
              ].map(([k, v]) => (
                <div key={k} className="border border-border rounded-sm px-3 py-2">
                  <div className="text-2xs text-faint">{k}</div>
                  <div className="text-sm tabular text-ink font-medium">{v}</div>
                </div>
              ))}
            </div>
          </section>

          {priorities.length > 0 && (
            <section className="border border-border bg-panel rounded-sm p-4 mt-5">
              <h2 className="text-sm text-ink font-medium">Top recruitment priorities</h2>
              <ul className="mt-3 space-y-2">
                {priorities.map((p: any, i: number) => (
                  <li key={i} className="text-xs text-muted">
                    <span className="text-ink">{p.severity ? `${p.severity} · ` : ""}{p.category || `Priority ${i + 1}`}</span>
                    {p.need ? ` — ${p.need}` : ""}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="mt-5">
            <ContractOutlook outlook={overview.contract_outlook} />
          </div>

          <ClubCompare activeClub={overview.profile.club_name} clubs={clubs} season={selectedSeason} label={selectedLabel} />
        </>
      )}
    </div>
  );
}
