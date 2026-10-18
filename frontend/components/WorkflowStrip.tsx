"use client";

import type { WorkflowSummary } from "@/lib/api";

/** One-line health check for a shortlist: where attention is needed. */
export default function WorkflowStrip({ workflow }: { workflow?: WorkflowSummary }) {
  if (!workflow) return null;
  const cells: [string, number, boolean][] = [
    ["Open", workflow.open, false], ["Overdue", workflow.overdue, true], ["Due in 7 days", workflow.due_within_7_days, true],
    ["Unassigned", workflow.unassigned, true], ["No next action", workflow.no_next_action, false],
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3" role="status" aria-label="Shortlist workflow summary">
      {cells.map(([label, n, warn]) => (
        <div key={label} className="border border-border bg-panel rounded-sm px-3 py-2">
          <div className="text-2xs text-faint">{label}</div>
          <div className={`text-lg tabular font-medium ${warn && n > 0 ? "text-riskmed" : "text-ink"}`}>{n}</div>
        </div>
      ))}
    </div>
  );
}
