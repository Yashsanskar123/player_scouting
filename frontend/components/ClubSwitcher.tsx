"use client";

/** Saved clubs with one active. Switching changes the defaults used by the Dashboard, Squad Audit and Optimizer. */
export default function ClubSwitcher({ clubs, active, onSwitch, onRemove }: { clubs: any[]; active: string | null; onSwitch: (name: string) => void; onRemove: (name: string) => void }) {
  if (!clubs || clubs.length === 0) return null;
  return (
    <section className="border border-border bg-panel rounded-sm p-4 mt-5">
      <h2 className="text-sm text-ink font-medium">My clubs</h2>
      <ul className="mt-3 divide-y divide-border">
        {clubs.map((c) => (
          <li key={c.club_name} className="flex items-center justify-between gap-3 py-2 text-xs">
            <span className="text-ink">
              {c.club_name} <span className="text-faint">· {c.formation}{c.transfer_budget_eur != null ? ` · budget €${Math.round(c.transfer_budget_eur / 1e6)}M` : ""}</span>
              {c.club_name === active && <span className="ml-2 text-2xs px-1.5 py-0.5 border border-accent/50 text-accent rounded-sm">Active</span>}
            </span>
            <span className="whitespace-nowrap">
              {c.club_name !== active && <button type="button" onClick={() => onSwitch(c.club_name)} className="text-accent hover:underline mr-3">Make active</button>}
              <button type="button" onClick={() => onRemove(c.club_name)} className="text-muted hover:text-ink underline">Remove</button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
