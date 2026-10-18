import Link from "next/link";

export function RiskBadge({ tier }: { tier?: string | null }) {
  if (!tier) return <span className="text-faint text-2xs">—</span>;
  const map: Record<string, string> = {
    LOW: "text-risklow border-risklow/40 bg-risklow/10",
    MEDIUM: "text-riskmed border-riskmed/40 bg-riskmed/10",
    HIGH: "text-riskhigh border-riskhigh/40 bg-riskhigh/10",
  };
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded-sm text-2xs border ${map[tier] || ""}`}>
      {tier}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
}) {
  return (
    <div className="border border-border bg-panel rounded-sm px-4 py-3">
      <div className="text-2xs text-faint mb-1">{label}</div>
      <div className="text-2xl text-ink tabular font-medium">{value}</div>
      {sublabel && <div className="text-2xs text-muted mt-1">{sublabel}</div>}
    </div>
  );
}

export function PercentileBar({ label, value }: { label: string; value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  const color = clamped >= 70 ? "bg-risklow" : clamped >= 40 ? "bg-riskmed" : "bg-riskhigh";
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="w-40 text-xs text-muted shrink-0 truncate">{label}</div>
      <div className="flex-1 h-1.5 bg-panelraised rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${clamped}%` }} />
      </div>
      <div className="w-9 text-right text-xs tabular text-ink shrink-0">{clamped.toFixed(0)}</div>
    </div>
  );
}

export function PlayerLink({ playerId, name }: { playerId: string; name: string }) {
  return (
    <Link href={`/players/${playerId}`} className="text-ink hover:text-accent transition-colors">
      {name}
    </Link>
  );
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="border border-dashed border-border rounded-sm px-6 py-10 text-center">
      <div className="text-ink text-sm mb-1">{title}</div>
      {body && <div className="text-muted text-xs">{body}</div>}
    </div>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div className="text-muted text-sm py-6">{label}…</div>;
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="border border-riskhigh/40 bg-riskhigh/10 rounded-sm px-4 py-3 text-sm text-ink">
      {message}
    </div>
  );
}
