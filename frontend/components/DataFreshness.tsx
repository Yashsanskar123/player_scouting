"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** One quiet line at the foot of every page: what the data covers and how old it is. Renders nothing on failure. */
export default function DataFreshness() {
  const [sources, setSources] = useState<any[] | null>(null);
  useEffect(() => {
    let alive = true;
    api.getDataFreshness().then((d: any) => alive && setSources(d.sources || [])).catch(() => alive && setSources(null));
    return () => { alive = false; };
  }, []);
  if (!sources || sources.length === 0) return null;
  return (
    <footer className="mt-10 pt-4 border-t border-border text-2xs text-faint flex flex-wrap gap-x-5 gap-y-1">
      {sources.map((s) => (
        <span key={s.source}>
          {s.source}: {s.covers}{s.updated ? ` · updated ${s.updated}` : ""}
          {s.stale && <span className="ml-1 text-riskmed">(over 6 months old)</span>}
        </span>
      ))}
      <Link href="/data-health" className="text-accent hover:underline">Data health</Link>
    </footer>
  );
}
