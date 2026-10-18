"use client";

import { useState } from "react";

/** Runs an async download and shows progress / a clear error. Works with login enabled (sends the token). */
export default function DownloadButton({ label, onDownload, className = "" }: { label: string; onDownload: () => Promise<void>; className?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await onDownload();
    } catch (e: any) {
      setError(e?.message || "Download failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <button type="button" onClick={run} disabled={busy}
        className="px-3 py-1.5 text-xs rounded-sm border border-border text-muted hover:text-ink hover:border-accent/50 disabled:opacity-50">
        {busy ? "Preparing…" : label}
      </button>
      {error && <span role="alert" className="text-2xs text-riskhigh">{error}</span>}
    </span>
  );
}
