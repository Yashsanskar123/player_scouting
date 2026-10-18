"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSeason } from "@/components/SeasonContext";
import { useAuth } from "@/components/AuthGate";

const NAV = [
  { section: "", items: [{ label: "Dashboard", href: "/" }] },
  {
    section: "Scouting",
    items: [
      { label: "Player Search", href: "/scouting/search" },
      { label: "Player Profile", href: "/players" },
      { label: "Development Lab", href: "/development" },

      { label: "Scout Workspace", href: "/scouting/workspace" },
      { label: "Compare", href: "/scouting/compare" },
      { label: "Replacement Finder", href: "/scouting/replace" },
      { label: "Market Opportunities", href: "/market/opportunities" },
    ],
  },
  {
    section: "Squad",
    items: [
      { label: "Club Profile", href: "/club" },
      { label: "Squad Audit", href: "/squad/audit" },
      { label: "Squad Optimizer", href: "/squad/optimizer" },
    ],
  },
  { section: "Platform", items: [{ label: "Data health", href: "/data-health" }, { label: "Model validation", href: "/model-validation" }] },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { enabled, user, logout } = useAuth();
  const nav = user?.role === "admin"
    ? [...NAV, { section: "Admin", items: [{ label: "Users", href: "/admin/users" }, { label: "Audit log", href: "/admin/audit" }, { label: "Security", href: "/admin/security" }] }]
    : NAV;
  const { seasons, selectedSeason, selectedLabel, setSelectedSeason, loading } = useSeason();

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-panel min-h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-border">
        <div className="text-ink font-semibold tracking-tight text-[15px]">ScoutIQ</div>
        <div className="text-faint text-2xs mt-0.5">Recruitment Intelligence</div>
      </div>
      <div className="px-4 py-3 border-b border-border">
        <div className="text-2xs text-faint mb-1">Analysis season</div>
        <select
          value={selectedSeason ?? ""}
          disabled={loading || seasons.length === 0}
          onChange={(e) => setSelectedSeason(Number(e.target.value))}
          aria-label="Analysis season"
          className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-xs text-ink disabled:opacity-60"
        >
          {seasons.map((s) => (
            <option key={s.season} value={s.season}>{s.label}{s.status === "current" ? " · current" : ""}{s.coverage?.status === "partial" ? " · partial data" : ""}</option>
          ))}
        </select>
        <div className="text-2xs text-faint mt-1">Current context: {selectedLabel}</div>
      </div>
      <nav className="px-3 py-4">
        {nav.map((group, i) => (
          <div key={i} className="mb-5">
            {group.section && (
              <div className="px-2 mb-1.5 text-2xs text-faint">{group.section}</div>
            )}
            {group.items.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block px-2 py-1.5 rounded-sm text-sm mb-0.5 transition-colors ${
                    active
                      ? "bg-panelraised text-ink border-l-2 border-accent -ml-px pl-[7px]"
                      : "text-muted hover:text-ink hover:bg-panelraised/60"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      {enabled && user && (
        <div className="px-4 py-3 border-t border-border">
          <div className="text-xs text-ink truncate">{user.display_name || user.username}</div>
          <div className="text-2xs text-faint capitalize">{user.role}</div>
          <button onClick={logout} className="mt-2 text-2xs text-muted hover:text-ink underline">Sign out</button>
        </div>
      )}
    </aside>
  );
}
