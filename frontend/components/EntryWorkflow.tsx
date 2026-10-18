"use client";

import { useEffect, useState } from "react";
import { api, type EntryUpdate, type ShortlistEntry } from "@/lib/api";

const CLOSED = new Set(["Rejected", "Signed"]);
const KIND_LABEL: Record<string, string> = { added: "Added", status: "Status", rating: "Rating", owner: "Owner", due: "Due date", next_action: "Next action", note: "Scout note" };

function dueState(due?: string | null, status?: string) {
  if (!due || (status && CLOSED.has(status))) return { text: due || "No due date", tone: "text-muted" };
  const days = Math.round((new Date(due + "T00:00:00").getTime() - new Date(new Date().toDateString()).getTime()) / 86400000);
  if (days < 0) return { text: `${due} · ${-days} day${days === -1 ? "" : "s"} overdue`, tone: "text-riskhigh" };
  if (days <= 7) return { text: `${due} · due in ${days} day${days === 1 ? "" : "s"}`, tone: "text-riskmed" };
  return { text: due, tone: "text-muted" };
}

/** Owner, due date, next action and change history for one shortlist entry. Sits under the candidate card. */
export default function EntryWorkflow({ entry, onUpdate }: { entry: ShortlistEntry; onUpdate: (id: number, body: EntryUpdate) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState(entry.owner || "");
  const [due, setDue] = useState(entry.due_date || "");
  const [action, setAction] = useState(entry.next_action || "");
  const [events, setEvents] = useState<any[] | null>(null);
  const [saving, setSaving] = useState(false);

  // Keep the form in step with the saved entry (e.g. after a status change elsewhere on the card).
  useEffect(() => { setOwner(entry.owner || ""); setDue(entry.due_date || ""); setAction(entry.next_action || ""); }, [entry.owner, entry.due_date, entry.next_action]);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    api.entryEvents(entry.id).then((d: any) => alive && setEvents(d.events || [])).catch(() => alive && setEvents([]));
    return () => { alive = false; };
  }, [open, entry.id, entry.status, entry.rating, entry.owner, entry.due_date, entry.next_action]);

  async function save() {
    setSaving(true);
    try { await onUpdate(entry.id, { owner, due_date: due, next_action: action }); } finally { setSaving(false); }
  }

  const d = dueState(entry.due_date, entry.status);
  const input = "mt-1 w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-xs text-ink outline-none";

  return (
    <div className="border border-t-0 border-border bg-panel rounded-b-sm px-4 py-2 -mt-px">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-2xs">
        <span className="text-faint">Owner <span className={entry.owner ? "text-ink" : "text-riskmed"}>{entry.owner || "Unassigned"}</span></span>
        <span className="text-faint">Due <span className={d.tone}>{d.text}</span></span>
        <span className="text-faint min-w-0 truncate">Next <span className="text-muted">{entry.next_action || "none set"}</span></span>
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="ml-auto text-accent hover:underline">
          {open ? "Hide workflow" : "Workflow and history"}
        </button>
      </div>

      {open && (
        <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-5 pb-2">
          <div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-2xs text-faint">Owner<input value={owner} onChange={(e) => setOwner(e.target.value)} maxLength={64} placeholder="Who is responsible" className={input} /></label>
              <label className="text-2xs text-faint">Due date<input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={input} /></label>
            </div>
            <label className="block text-2xs text-faint mt-3">Next action<input value={action} onChange={(e) => setAction(e.target.value)} maxLength={255} placeholder="e.g. Watch Saturday's match" className={input} /></label>
            <button type="button" onClick={save} disabled={saving} className="mt-3 px-3 py-1.5 text-xs rounded-sm bg-accent text-black font-medium disabled:opacity-50">{saving ? "Saving…" : "Save workflow"}</button>
          </div>
          <div>
            <div className="text-2xs text-faint mb-2">History</div>
            {events === null ? <div className="text-xs text-faint">Loading…</div> : events.length === 0 ? <div className="text-xs text-faint">No history yet.</div> : (
              <ul className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {events.map((e, i) => (
                  <li key={i} className="text-xs text-muted">
                    <span className="text-faint tabular">{(e.ts || "").slice(0, 16).replace("T", " ")}</span>{" "}
                    <span className="text-ink">{KIND_LABEL[e.kind] || e.kind}</span>{e.actor ? <span className="text-faint"> · {e.actor}</span> : null}
                    <div className="text-muted break-words">{e.detail}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
