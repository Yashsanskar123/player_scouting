"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, formatEur } from "@/lib/api";
import { ValidationNotice } from "@/components/ValidationBadge";

const n = (v: any, d = 1) => (v == null ? "—" : Number(v).toFixed(d));
const SEVERITY_TONE: Record<string, string> = { HIGH: "text-riskhigh", MEDIUM: "text-riskmed" };

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="border border-border bg-panel rounded-sm p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm text-ink font-medium">{title}</h3>
        {action}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** The club-first top of the Dashboard: what this club needs, who is overdue, who to look at. Renders nothing on failure. */
export default function ClubCommandCenter({ season, label }: { season?: number | null; label: string }) {
  const [d, setD] = useState<any>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setD(null);
    setFailed(false);
    api.clubDashboard(season).then((x: any) => alive && setD(x)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, [season]);

  if (failed || !d) return null;

  if (!d.configured) {
    return (
      <section className="border border-border bg-panel rounded-sm p-4 mb-6">
        <h2 className="text-sm text-ink font-medium">Make this dashboard yours</h2>
        <p className="text-xs text-muted mt-1">Choose your club, formation and budget once and this page will show your squad's needs, contract deadlines, overdue scouting tasks and affordable targets.</p>
        <Link href="/club" className="inline-block mt-3 text-xs text-accent hover:underline">Set up your club</Link>
      </section>
    );
  }

  const sq = d.squad, profile = d.profile, tasks = d.tasks;
  const priorities: any[] = sq?.recruitment_priorities || [];
  const expiring: any[] = sq?.contract_outlook?.available ? sq.contract_outlook.expiring_within_12m || [] : [];

  return (
    <section className="mb-8" aria-label="Your club">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base text-ink font-medium">{profile.club_name} <span className="text-faint text-xs font-normal">· {sq?.league_name || "—"} · {profile.formation} · {label}</span></h2>
        <Link href="/club" className="text-2xs text-accent hover:underline">Manage clubs</Link>
      </div>

      {!sq ? (
        <p className="text-xs text-muted mt-3">{d.unavailable_reason} Choose a season in which {profile.club_name} appears, or manage clubs.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
            {[["Squad size", String(sq.roster_size)], ["Average age", n(sq.average_age)], ["Average performance", n(sq.average_performance)],
              ["Squad value", formatEur(sq.squad_market_value_eur)], ["Transfer budget", profile.transfer_budget_eur != null ? formatEur(profile.transfer_budget_eur) : "Not set"]].map(([k, v]) => (
              <div key={k} className="border border-border bg-panel rounded-sm px-3 py-2">
                <div className="text-2xs text-faint">{k}</div>
                <div className="text-sm tabular text-ink font-medium">{v}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            <Panel title="Recruitment priorities" action={<Link href="/squad/audit" className="text-2xs text-accent hover:underline">Full audit</Link>}>
              {priorities.length === 0 ? <p className="text-xs text-faint">No gaps flagged for this formation.</p> : (
                <ul className="space-y-2">
                  {priorities.map((p, i) => (
                    <li key={i} className="text-xs text-muted"><span className={SEVERITY_TONE[p.severity] || "text-ink"}>{p.severity}</span> · <span className="text-ink">{p.category}</span> — {p.need}</li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Contracts ending within 12 months" action={<span className="text-2xs text-faint">current snapshot</span>}>
              {!sq.contract_outlook?.available ? <p className="text-xs text-faint">{sq.contract_outlook?.reason || "Contract data is shown for the latest season only."}</p>
                : expiring.length === 0 ? <p className="text-xs text-faint">No listed contracts end within 12 months.</p> : (
                <ul className="space-y-1.5">
                  {expiring.slice(0, 6).map((p) => (
                    <li key={p.player_id} className="flex justify-between gap-2 text-xs">
                      <Link href={`/players/${p.player_id}`} className="text-ink hover:underline truncate">{p.short_name} <span className="text-faint">{p.canonical_position}</span></Link>
                      <span className="text-muted tabular whitespace-nowrap">{p.contract_expires} · {p.contract_months_left} mo</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Scouting workload" action={<Link href="/scouting/workspace" className="text-2xs text-accent hover:underline">Open workspace</Link>}>
              {!tasks || tasks.total === 0 ? <p className="text-xs text-faint">No open tasks. Give shortlist entries an owner and due date to track them here.</p> : (
                <>
                  <p className="text-xs text-muted mb-2"><span className={tasks.overdue > 0 ? "text-riskhigh font-medium" : "text-ink"}>{tasks.overdue} overdue</span> of {tasks.total} open tasks</p>
                  <ul className="space-y-1.5">
                    {tasks.next.map((t: any) => (
                      <li key={t.entry_id} className="text-xs flex justify-between gap-2">
                        <span className="text-ink truncate">{t.player || t.player_id}{t.next_action ? <span className="text-faint"> · {t.next_action}</span> : null}</span>
                        <span className={`whitespace-nowrap tabular ${t.overdue ? "text-riskhigh" : "text-muted"}`}>{t.owner || "unassigned"}{t.due_date ? ` · ${t.due_date}` : ""}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Panel>
          </div>

          {d.watchlist_movers?.length > 0 && (
            <div className="mt-4">
              <Panel title={`Watchlist movers (${d.watchlist_size} players on open shortlists)`}>
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5">
                  {d.watchlist_movers.map((m: any) => (
                    <li key={m.player_id} className="flex justify-between gap-2 text-xs">
                      <Link href={`/players/${m.player_id}`} className="text-ink hover:underline truncate">{m.short_name} <span className="text-faint">{m.club_name}</span></Link>
                      <span className={`tabular whitespace-nowrap ${m.direction === "up" ? "text-risklow" : "text-riskhigh"}`}>{m.direction === "up" ? "▲" : "▼"} {m.change > 0 ? "+" : ""}{m.change} ({n(m.performance_before, 0)} → {n(m.performance_now, 0)})</span>
                    </li>
                  ))}
                </ul>
              </Panel>
            </div>
          )}

          {d.targets?.length > 0 && (
            <div className="mt-4">
              <Panel title="Affordable targets for your priorities">
                <p className="text-2xs text-faint -mt-1 mb-3">Screening suggestions for scouts to check, not recommendations. Ranked by league-adjusted performance.</p>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {d.targets.map((t: any) => (
                    <div key={t.position}>
                      <div className="text-xs text-ink font-medium">{t.position} <span className={`font-normal ${SEVERITY_TONE[t.severity] || "text-faint"}`}>{t.severity}</span></div>
                      <div className="text-2xs text-faint mb-1.5">{t.basis}</div>
                      {t.candidates.length === 0 ? <div className="text-xs text-faint">No players meet these conditions.</div> : (
                        <ul className="space-y-1.5">
                          {t.candidates.map((c: any) => (
                            <li key={c.player_id} className="text-xs flex justify-between gap-2">
                              <Link href={`/players/${c.player_id}`} className="text-ink hover:underline truncate">{c.short_name} <span className="text-faint">{c.club_name}</span></Link>
                              <span className="text-muted tabular whitespace-nowrap">{n(c.adjusted_performance_score ?? c.performance_score, 0)} · {formatEur(c.value_eur)}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
                <ValidationNotice keys={["performance_score", "value_gap"]} title="How far to trust these suggestions" />
              </Panel>
            </div>
          )}
        </>
      )}
    </section>
  );
}
