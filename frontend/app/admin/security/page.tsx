"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LoadingState, ErrorState } from "@/components/ui";
import { StatusChip } from "@/components/ValidationBadge";

export default function SecurityPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSecurityStatus().then(setData)
      .catch((e: any) => setError(String(e?.message || "").includes("403") ? "Only administrators can view the security status." : e.message || "Could not load the security status."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState label="Checking security settings" />;
  if (error) return <ErrorState message={error} />;

  const { checks, summary } = data;
  const tone = (c: any) => (c.ok ? "validated" : c.severity === "high" ? "not_validated" : "partially_validated");

  return (
    <div className="max-w-[900px]">
      <h1 className="text-lg text-ink font-medium">Security status</h1>
      <p className="text-xs text-muted mt-1 max-w-2xl">
        What this deployment is, and is not, protected against right now. Settings are changed through environment variables; see docs/SECURITY.md.
      </p>
      <p className="text-sm text-ink mt-4">
        {summary.passed} of {summary.total} checks pass
        {summary.high_failing > 0 && <span className="text-riskhigh"> · {summary.high_failing} high-priority issue{summary.high_failing === 1 ? "" : "s"}</span>}
        {summary.medium_failing > 0 && <span className="text-riskmed"> · {summary.medium_failing} medium</span>}
      </p>
      <ul className="mt-4 space-y-3">
        {checks.map((c: any) => (
          <li key={c.key} className="border border-border bg-panel rounded-sm p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm text-ink font-medium">{c.title}</h2>
              <StatusChip status={tone(c)} label={c.ok ? "OK" : `Needs attention (${c.severity})`} />
            </div>
            <p className="text-xs text-muted mt-2">{c.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
