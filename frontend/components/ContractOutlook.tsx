"use client";

import { formatEur } from "@/lib/api";

/** Contract timing for an audited roster. Renders only a short note when unavailable. */
export default function ContractOutlook({ outlook }: { outlook?: any }) {
  if (!outlook) return null;
  if (!outlook.available) {
    return (
      <section className="border border-border bg-panel rounded-sm p-4">
        <h2 className="text-sm text-ink font-medium">Contract outlook</h2>
        <p className="text-2xs text-faint mt-1">{outlook.reason || "Contract data is not available for this view."}</p>
      </section>
    );
  }
  const b = outlook.buckets || {};
  const cells: [string, number, boolean][] = [
    ["Within 6 months", b.within_6m ?? 0, true],
    ["6-12 months", b.within_12m ?? 0, true],
    ["1-2 years", b.within_24m ?? 0, false],
    ["2+ years", b.longer ?? 0, false],
    ["Expired / unrenewed", b.expired_or_unrenewed ?? 0, true],
    ["No contract data", b.unknown ?? 0, false],
  ];
  const list: any[] = outlook.expiring_within_12m || [];
  return (
    <section className="border border-border bg-panel rounded-sm p-4">
      <h2 className="text-sm text-ink font-medium">Contract outlook</h2>
      <p className="text-2xs text-faint mt-1">
        {outlook.coverage?.with_contract_data ?? 0} of {outlook.coverage?.roster_size ?? 0} players have contract data. {outlook.note}
      </p>
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-4">
        {cells.map(([label, n, warn]) => (
          <div key={label} className="border border-border rounded-sm px-3 py-2">
            <div className="text-2xs text-faint">{label}</div>
            <div className={`text-lg tabular font-medium ${warn && n > 0 ? "text-riskmed" : "text-ink"}`}>{n}</div>
          </div>
        ))}
      </div>
      {list.length > 0 && (
        <div className="mt-4">
          <div className="text-2xs text-faint mb-2">Contracts ending within 12 months (highest performance first within same date)</div>
          <ul className="space-y-1.5">
            {list.map((p) => (
              <li key={p.player_id} className="flex justify-between gap-3 text-xs">
                <span className="text-ink truncate">
                  {p.short_name} <span className="text-muted">· {p.canonical_position || "—"} · perf {p.performance_score != null ? Math.round(p.performance_score) : "—"}</span>
                </span>
                <span className="text-muted tabular shrink-0">
                  {p.contract_expires} · {p.contract_months_left} mo · {formatEur(p.tm_value_eur)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
