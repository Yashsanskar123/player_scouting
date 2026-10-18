"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui";

const PAGE = 50;
const input = "mt-1 bg-panelraised border border-border rounded-sm px-2 py-2 text-xs text-ink outline-none";

export default function AuditPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [username, setUsername] = useState("");
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api.auditLog({ limit: PAGE, offset, username: username || undefined, action: action || undefined })
      .then((d: any) => { if (alive) { setItems(d.items || []); setTotal(d.total || 0); setError(null); } })
      .catch((e: any) => alive && setError(String(e?.message || "").includes("403") ? "Only administrators can view the audit log." : e.message || "Could not load the audit log."))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [offset, username, action]);

  return (
    <div className="max-w-[1200px]">
      <h1 className="text-lg text-ink font-medium">Audit log</h1>
      <p className="text-xs text-muted mt-1">Who changed what and when. Request contents and passwords are never recorded.</p>
      {error && <div className="mt-4"><ErrorState message={error} /></div>}

      <div className="flex gap-3 mt-5">
        <label className="text-2xs text-faint">User<br /><input value={username} onChange={(e) => { setOffset(0); setUsername(e.target.value); }} placeholder="any" className={input} /></label>
        <label className="text-2xs text-faint">Action<br /><input value={action} onChange={(e) => { setOffset(0); setAction(e.target.value); }} placeholder="e.g. shortlist.create" className={input} /></label>
      </div>

      {loading ? <LoadingState label="Loading audit log" /> : (
        <section className="border border-border bg-panel rounded-sm mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-faint text-left border-b border-border">
                {["Time (UTC)", "User", "Role", "Action", "Target", "Status", "Request"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} className="border-b border-border last:border-0">
                  <td className="px-3 py-2 text-muted tabular whitespace-nowrap">{r.ts ? r.ts.slice(0, 19).replace("T", " ") : "—"}</td>
                  <td className="px-3 py-2 text-ink">{r.username}</td>
                  <td className="px-3 py-2 text-muted">{r.role || "—"}</td>
                  <td className="px-3 py-2 text-ink">{r.action}</td>
                  <td className="px-3 py-2 text-muted">{r.entity || "—"}</td>
                  <td className={`px-3 py-2 tabular ${r.status >= 400 ? "text-riskhigh" : "text-muted"}`}>{r.status ?? "—"}</td>
                  <td className="px-3 py-2 text-faint tabular">{r.request_id || "—"}</td>
                </tr>
              ))}
              {items.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-faint">No matching entries.</td></tr>}
            </tbody>
          </table>
        </section>
      )}

      <div className="flex items-center gap-3 mt-3 text-xs text-muted">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} className="px-3 py-1.5 border border-border rounded-sm disabled:opacity-40">Previous</button>
        <span>{total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE, total)} of {total}</span>
        <button disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)} className="px-3 py-1.5 border border-border rounded-sm disabled:opacity-40">Next</button>
      </div>
    </div>
  );
}
