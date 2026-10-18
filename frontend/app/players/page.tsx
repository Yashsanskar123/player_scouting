"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PlayerPicker } from "@/components/PlayerPicker";
import { useSeason } from "@/components/SeasonContext";
import { PlayerSummary } from "@/lib/api";

export default function PlayersIndexPage() {
  const router = useRouter();
  const { selectedLabel, selectedSeason } = useSeason();
  const [player, setPlayer] = useState<PlayerSummary | null>(null);

  function openProfile(p: PlayerSummary) {
    setPlayer(p);
    if (typeof window !== "undefined") localStorage.setItem("scoutiq:last-player-id", p.player_id);
    router.push(`/players/${p.player_id}`);
  }

  return (
    <div className="max-w-3xl">
      <header className="mb-7">
        <div className="text-2xs uppercase tracking-[0.18em] text-accent mb-2">Player intelligence</div>
        <h1 className="text-2xl text-ink font-semibold tracking-tight">Player Profile</h1>
        <p className="text-muted text-sm mt-1">Select a player to open the full recruitment intelligence profile for the {selectedLabel} analysis snapshot.</p>
      </header>
      <div className="analytics-panel p-5">
        <div className="text-2xs text-faint mb-2">Analysis season</div>
        <div className="text-sm text-ink mb-4">{selectedLabel} {selectedSeason ? `(${selectedSeason})` : ""}</div>
        <PlayerPicker season={selectedSeason} onSelect={openProfile} placeholder="Search for a player..." />
        {player && <div className="text-xs text-muted mt-3">Opening {player.short_name}…</div>}
      </div>
    </div>
  );
}
