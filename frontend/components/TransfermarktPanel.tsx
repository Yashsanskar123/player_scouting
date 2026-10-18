"use client";

import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, formatEur } from "@/lib/api";

/**
 * Optional Transfermarkt context for the Player Profile.
 * Self-contained: it fetches its own data and renders nothing if the data is
 * missing or the request fails, so it can never break the profile page.
 */
export default function TransfermarktPanel({ playerId }: { playerId: string }) {
  const [ctx, setCtx] = useState<any>(null);

  useEffect(() => {
    let alive = true;
    setCtx(null);
    api.getTransfermarkt(playerId).then((d: any) => { if (alive) setCtx(d); }).catch(() => { if (alive) setCtx(null); });
    return () => { alive = false; };
  }, [playerId]);

  if (!ctx || !ctx.available) return null;

  const c = ctx.contract || {};
  const m = ctx.market || {};
  const p = ctx.profile || {};
  const history = (ctx.valuation_history || []).map((h: any) => ({ date: h.date, value: h.value_eur }));
  const urgent = typeof c.months_remaining === "number" && c.months_remaining <= 12;
  const statusClass = urgent ? "text-riskmed" : "text-ink";
  const change = m.change_12m_pct;

  return (
    <section className="analytics-panel">
      <div className="px-5 pt-5 pb-3 border-b border-border">
        <h2 className="text-sm text-ink font-medium">Contract & market context</h2>
        <p className="text-2xs text-faint mt-1">
          {ctx.snapshot_note}
          {ctx.match?.confidence === "Medium" ? " Player link confidence: Medium — verify identity before relying on it." : ""}
          {ctx.match?.shared_with_other_scoutiq_id ? " Note: this player appears under more than one ScoutIQ ID." : ""}
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 border-b border-border">
        <Stat label="Contract ends" value={c.expires || "—"} sub={c.months_remaining != null ? `${c.months_remaining} months left` : "Not listed"} valueClass={statusClass} />
        <Stat label="Contract status" value={c.status || "Unknown"} valueClass={statusClass} />
        <Stat label="Market value (TM)" value={formatEur(m.current_value_eur)} sub={m.pct_of_peak != null ? `${m.pct_of_peak}% of peak ${formatEur(m.peak_value_eur)}` : undefined} />
        <Stat
          label="12-month value change"
          value={change == null ? "—" : `${change >= 0 ? "+" : ""}${change}%`}
          sub={m.last_valuation_date ? `Last valuation ${m.last_valuation_date}` : undefined}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-0">
        <div className="p-5 border-b xl:border-b-0 xl:border-r border-border">
          <div className="text-2xs text-faint mb-2">Market value history</div>
          <div className="h-48">
            {history.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6B7787" }} tickFormatter={(v: string) => v.slice(0, 4)} minTickGap={40} />
                  <YAxis tick={{ fontSize: 10, fill: "#6B7787" }} tickFormatter={(v: number) => formatEur(v)} width={52} />
                  <Tooltip formatter={(v: any) => formatEur(Number(v))} labelFormatter={(l: any) => String(l)} contentStyle={{ background: "#10151C", border: "1px solid #1D2530", fontSize: 12 }} />
                  <Area type="monotone" dataKey="value" stroke="#4F9DFF" fill="#4F9DFF" fillOpacity={0.12} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-faint">Not enough valuation history.</div>
            )}
          </div>
        </div>

        <div className="p-5 space-y-5">
          <div>
            <div className="text-2xs text-faint mb-2">Profile details</div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <Row k="Date of birth" v={p.date_of_birth} />
              <Row k="Citizenship" v={p.citizenship} />
              <Row k="Preferred foot" v={p.foot ? String(p.foot) : null} />
              <Row k="Height" v={p.height_cm ? `${Math.round(p.height_cm)} cm` : null} />
              <Row k="Current club (TM)" v={p.current_club} />
              <Row k="Agent" v={p.agent} />
            </dl>
          </div>
          <div>
            <div className="text-2xs text-faint mb-2">Recent transfers</div>
            {ctx.transfers?.length ? (
              <ul className="space-y-1.5">
                {ctx.transfers.slice(0, 5).map((t: any, i: number) => (
                  <li key={i} className="text-xs text-muted flex justify-between gap-3">
                    <span className="truncate">{t.date?.slice(0, 7)} · {t.from_club || "—"} → {t.to_club || "—"}</span>
                    <span className="text-ink tabular shrink-0">{t.fee_eur == null ? "—" : t.fee_eur === 0 ? "Free / loan / undisclosed" : formatEur(t.fee_eur)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-faint">No transfer history listed.</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, sub, valueClass }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <div className="px-5 py-4 border-r border-border last:border-r-0">
      <div className="text-2xs text-faint">{label}</div>
      <div className={`text-sm font-medium tabular mt-1 ${valueClass || "text-ink"}`}>{value}</div>
      {sub && <div className="text-2xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

function Row({ k, v }: { k: string; v?: string | null }) {
  return (
    <>
      <dt className="text-faint">{k}</dt>
      <dd className="text-ink truncate">{v || "—"}</dd>
    </>
  );
}
