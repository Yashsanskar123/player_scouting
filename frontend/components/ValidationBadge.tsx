"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export const STATUS_STYLE: Record<string, string> = {
  validated: "text-risklow border-risklow/50 bg-risklow/10",
  partially_validated: "text-riskmed border-riskmed/50 bg-riskmed/10",
  exploratory: "text-riskmed border-riskhigh/40 bg-riskhigh/10",
  not_validated: "text-riskhigh border-riskhigh/50 bg-riskhigh/10",
};

let cache: Promise<Record<string, any>> | null = null;

/** One shared request for all badges on a page; resolves to {} when no validation report exists. */
export function useValidationStatus(): Record<string, any> {
  const [status, setStatus] = useState<Record<string, any>>({});
  useEffect(() => {
    let alive = true;
    if (!cache) cache = api.getValidationStatus().then((d: any) => d?.status || {}).catch(() => ({}));
    cache.then((s) => alive && setStatus(s));
    return () => { alive = false; };
  }, []);
  return status;
}

export function StatusChip({ status, label, title }: { status: string; label: string; title?: string }) {
  return (
    <span title={title} className={`inline-block text-2xs px-1.5 py-0.5 border rounded-sm whitespace-nowrap ${STATUS_STYLE[status] || "text-muted border-border"}`}>
      {label}
    </span>
  );
}

/** Small chip for one model output, e.g. <ValidationBadge modelKey="development_potential" />. Renders nothing without a report. */
export default function ValidationBadge({ modelKey }: { modelKey: string }) {
  const item = useValidationStatus()[modelKey];
  if (!item) return null;
  return (
    <Link href="/model-validation" title={`${item.summary} Click for the evidence.`}>
      <StatusChip status={item.status} label={item.status_label} />
    </Link>
  );
}

/** A compact "how far to trust this page" note listing the status of the models it shows. */
export function ValidationNotice({ keys, title = "How far to trust these numbers" }: { keys: string[]; title?: string }) {
  const status = useValidationStatus();
  const items = keys.map((k) => ({ key: k, item: status[k] })).filter((x) => x.item);
  if (items.length === 0) return null;
  return (
    <div className="border border-border bg-panel rounded-sm px-4 py-3 mt-4 max-w-4xl">
      <div className="text-2xs text-faint">{title}</div>
      <ul className="mt-2 space-y-2">
        {items.map(({ key, item }) => (
          <li key={key} className="text-xs text-muted flex gap-2 items-start">
            <StatusChip status={item.status} label={item.status_label} />
            <span>{item.summary}</span>
          </li>
        ))}
      </ul>
      <Link href="/model-validation" className="inline-block mt-2 text-2xs text-accent hover:underline">See the evidence</Link>
    </div>
  );
}
