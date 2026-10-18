"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSeason } from "@/components/SeasonContext";

/** Shown above every page when the selected season is incomplete, so numbers are never mistaken for a full season. */
export default function CoverageNotice() {
  const { seasons, selectedSeason, selectedLabel } = useSeason();
  const [hidden, setHidden] = useState<string | null>(null);
  const cov = seasons.find((s) => s.season === selectedSeason)?.coverage;
  const key = `scoutiq:coverage-dismissed:${selectedSeason}`;

  useEffect(() => {
    try { setHidden(window.sessionStorage.getItem(key)); } catch { setHidden(null); }
  }, [key]);

  if (!cov || (cov.status !== "partial" && !cov.advanced_limited) || hidden) return null;

  function dismiss() {
    try { window.sessionStorage.setItem(key, "1"); } catch { /* storage unavailable */ }
    setHidden("1");
  }

  return (
    <div role="status" className="mb-5 border border-riskmed/50 bg-riskmed/10 rounded-sm px-4 py-3 flex items-start justify-between gap-4">
      <div className="text-xs text-ink">
        <span className="font-medium">{selectedLabel} is {cov.status === "partial" ? "a partial season" : "missing advanced statistics for many players"}.</span>{" "}
        <span className="text-muted">{cov.note}</span>{" "}
        <Link href="/data-health" className="text-accent hover:underline whitespace-nowrap">See data health</Link>
      </div>
      <button type="button" onClick={dismiss} aria-label="Dismiss for this session" className="text-faint hover:text-ink text-sm leading-none">×</button>
    </div>
  );
}
