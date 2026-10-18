"use client";

import { useEffect } from "react";

/** App-wide error boundary: a page crash shows a clear message and a retry, never a blank screen. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Surfaces in the browser console / any attached error tracker.
    console.error("ScoutIQ UI error:", error);
  }, [error]);

  return (
    <div className="p-6 max-w-[720px]">
      <div className="border border-riskhigh/40 bg-riskhigh/10 rounded-sm px-4 py-4">
        <h1 className="text-sm text-ink font-medium">Something went wrong on this page</h1>
        <p className="text-xs text-muted mt-2">
          The rest of the platform is unaffected. Try again, or switch to another page from the sidebar.
          {error?.digest ? ` Reference: ${error.digest}` : ""}
        </p>
        <button onClick={reset} className="mt-4 px-4 py-2 text-xs rounded-sm border border-border text-ink hover:border-accent/50">
          Try again
        </button>
      </div>
    </div>
  );
}
