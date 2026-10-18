"use client";

import Link from "next/link";

export type PitchPlayer = {
  player_id?: string;
  short_name?: string;
  canonical_position?: string;
  depth_role?: string;
  performance_score?: number;
  age_fifa?: number;
};

type Slot = { x: number; y: number; positions: string[]; label: string };

const FORMATION_SLOTS: Record<string, Slot[]> = {
  "4-3-3": [
    { x: 50, y: 91, positions: ["GK"], label: "GK" },
    { x: 16, y: 72, positions: ["LB"], label: "LB" },
    { x: 38, y: 76, positions: ["CB"], label: "CB" },
    { x: 62, y: 76, positions: ["CB"], label: "CB" },
    { x: 84, y: 72, positions: ["RB"], label: "RB" },
    { x: 30, y: 54, positions: ["CM"], label: "CM" },
    { x: 50, y: 59, positions: ["CDM", "CM"], label: "6" },
    { x: 70, y: 54, positions: ["CM"], label: "CM" },
    { x: 15, y: 31, positions: ["LW"], label: "LW" },
    { x: 50, y: 25, positions: ["ST"], label: "ST" },
    { x: 85, y: 31, positions: ["RW"], label: "RW" },
  ],
  "4-2-3-1": [
    { x: 50, y: 91, positions: ["GK"], label: "GK" },
    { x: 16, y: 72, positions: ["LB"], label: "LB" },
    { x: 38, y: 76, positions: ["CB"], label: "CB" },
    { x: 62, y: 76, positions: ["CB"], label: "CB" },
    { x: 84, y: 72, positions: ["RB"], label: "RB" },
    { x: 38, y: 57, positions: ["CDM"], label: "6" },
    { x: 62, y: 57, positions: ["CDM"], label: "6" },
    { x: 16, y: 36, positions: ["LW"], label: "LW" },
    { x: 50, y: 39, positions: ["CAM"], label: "10" },
    { x: 84, y: 36, positions: ["RW"], label: "RW" },
    { x: 50, y: 20, positions: ["ST"], label: "9" },
  ],
  "4-4-2": [
    { x: 50, y: 91, positions: ["GK"], label: "GK" },
    { x: 16, y: 72, positions: ["LB"], label: "LB" },
    { x: 38, y: 76, positions: ["CB"], label: "CB" },
    { x: 62, y: 76, positions: ["CB"], label: "CB" },
    { x: 84, y: 72, positions: ["RB"], label: "RB" },
    { x: 15, y: 49, positions: ["LW"], label: "LM" },
    { x: 38, y: 53, positions: ["CM"], label: "CM" },
    { x: 62, y: 53, positions: ["CM"], label: "CM" },
    { x: 85, y: 49, positions: ["RW"], label: "RM" },
    { x: 42, y: 25, positions: ["ST"], label: "ST" },
    { x: 58, y: 25, positions: ["ST"], label: "ST" },
  ],
  "3-4-3": [
    { x: 50, y: 91, positions: ["GK"], label: "GK" },
    { x: 27, y: 76, positions: ["CB"], label: "CB" },
    { x: 50, y: 79, positions: ["CB"], label: "CB" },
    { x: 73, y: 76, positions: ["CB"], label: "CB" },
    { x: 14, y: 51, positions: ["LWB", "LB"], label: "LWB" },
    { x: 37, y: 56, positions: ["CM"], label: "CM" },
    { x: 63, y: 56, positions: ["CM"], label: "CM" },
    { x: 86, y: 51, positions: ["RWB", "RB"], label: "RWB" },
    { x: 16, y: 28, positions: ["LW"], label: "LW" },
    { x: 50, y: 21, positions: ["ST"], label: "ST" },
    { x: 84, y: 28, positions: ["RW"], label: "RW" },
  ],
  "3-5-2": [
    { x: 50, y: 91, positions: ["GK"], label: "GK" },
    { x: 27, y: 76, positions: ["CB"], label: "CB" },
    { x: 50, y: 79, positions: ["CB"], label: "CB" },
    { x: 73, y: 76, positions: ["CB"], label: "CB" },
    { x: 14, y: 52, positions: ["LWB", "LB"], label: "LWB" },
    { x: 36, y: 58, positions: ["CM"], label: "CM" },
    { x: 50, y: 48, positions: ["CAM"], label: "10" },
    { x: 64, y: 58, positions: ["CM"], label: "CM" },
    { x: 86, y: 52, positions: ["RWB", "RB"], label: "RWB" },
    { x: 43, y: 25, positions: ["ST"], label: "ST" },
    { x: 57, y: 25, positions: ["ST"], label: "ST" },
  ],
};

function initials(name: string) {
  return name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function slotPlayers(players: PitchPlayer[], slot: Slot, used: Set<string>) {
  const candidates = players.filter((p) => slot.positions.includes(p.canonical_position || ""));
  const found = candidates.find((p) => {
    const key = p.player_id || p.short_name || "";
    return Boolean(key) && !used.has(key);
  });
  if (found) used.add(found.player_id || found.short_name || "");
  return found;
}

export default function TacticalPitch({
  formation,
  players,
  title,
  subtitle,
  emptyMessage = "No player available",
  linkPlayers = true,
}: {
  formation: string;
  players: PitchPlayer[];
  title?: string;
  subtitle?: string;
  emptyMessage?: string;
  linkPlayers?: boolean;
}) {
  const slots = FORMATION_SLOTS[formation] || FORMATION_SLOTS["4-3-3"];
  const used = new Set<string>();

  return (
    <section className="analytics-panel p-4">
      {(title || subtitle) && (
        <div className="flex items-end justify-between mb-3">
          <div>
            {title && <h2 className="text-sm text-ink font-medium">{title}</h2>}
            {subtitle && <p className="text-2xs text-muted mt-1">{subtitle}</p>}
          </div>
          <span className="text-2xs text-accent border border-accent/30 bg-accent/5 rounded-full px-2 py-1">{formation}</span>
        </div>
      )}

      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-[#10251f] aspect-[1.45/1] min-h-[430px]">
        <div className="absolute inset-0 pitch-grass" />
        <div className="absolute inset-[4%] border border-white/35 rounded-sm" />
        <div className="absolute left-[4%] right-[4%] top-1/2 border-t border-white/30" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[16%] aspect-square border border-white/30 rounded-full" />
        <div className="absolute left-[4%] right-[4%] top-[4%] h-[17%] border border-white/30 border-t-0" />
        <div className="absolute left-[4%] right-[4%] bottom-[4%] h-[17%] border border-white/30 border-b-0" />
        <div className="absolute left-1/2 top-[4%] -translate-x-1/2 w-[7%] h-[4%] border border-white/30 border-t-0" />
        <div className="absolute left-1/2 bottom-[4%] -translate-x-1/2 w-[7%] h-[4%] border border-white/30 border-b-0" />

        {slots.map((slot, index) => {
          const player = slotPlayers(players, slot, used);
          const name = player?.short_name || emptyMessage;
          const score = player?.performance_score;
          const risk = player?.depth_role === "prospect" ? "prospect" : player?.depth_role;
          const key = `${slot.label}-${index}`;

          const card = (
            <div className={`pitch-player ${player ? "pitch-player-filled" : "pitch-player-empty"}`}>
              <div className="pitch-avatar">{player ? initials(name) : "?"}</div>
              <div className="min-w-0">
                <div className="truncate text-[10px] font-semibold text-white">{name}</div>
                <div className="flex items-center gap-1 text-[9px] text-white/60">
                  <span>{slot.label}</span>
                  {score != null && <><span>·</span><span>{Number(score).toFixed(0)}</span></>}
                </div>
              </div>
              {risk && <span className="ml-auto text-[8px] uppercase text-white/50">{risk}</span>}
            </div>
          );

          return (
            <div key={key} className="absolute -translate-x-1/2 -translate-y-1/2 w-[18%] min-w-[116px] max-w-[190px]" style={{ left: `${slot.x}%`, top: `${slot.y}%` }}>
              {linkPlayers && player?.player_id ? (
                <Link href={`/players/${player.player_id}`} className="block hover:scale-[1.03] transition-transform">
                  {card}
                </Link>
              ) : card}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-4 mt-3 text-2xs text-muted">
        <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-full bg-accent" /> Player selected</span>
        <span className="inline-flex items-center gap-1.5"><i className="w-2 h-2 rounded-full bg-white/20" /> Position gap</span>
        <span>Player cards link to profile</span>
      </div>
    </section>
  );
}
