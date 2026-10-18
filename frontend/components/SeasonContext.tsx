"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export type SeasonCoverage = {
  status: "complete" | "partial"; note: string; players: number; leagues: number; expected_leagues: number;
  missing_leagues: string[]; advanced_limited: boolean; advanced_stats_pct: number;
};
export type SeasonOption = { season: number; label: string; short_label: string; status: string; coverage?: SeasonCoverage | null };

type SeasonContextValue = {
  seasons: SeasonOption[];
  selectedSeason: number | null;
  selectedLabel: string;
  setSelectedSeason: (season: number) => void;
  loading: boolean;
};

const SeasonContext = createContext<SeasonContextValue | null>(null);
const STORAGE_KEY = "scoutiq:selected-season";

export function SeasonProvider({ children }: { children: React.ReactNode }) {
  const [seasons, setSeasons] = useState<SeasonOption[]>([]);
  const [selectedSeason, setSelectedSeasonState] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.seasons()
      .then((payload) => {
        setSeasons(payload.seasons);
        const stored = Number(window.localStorage.getItem(STORAGE_KEY));
        const validStored = payload.seasons.some((s) => s.season === stored);
        setSelectedSeasonState(validStored ? stored : payload.current_season);
      })
      .catch(() => setSeasons([]))
      .finally(() => setLoading(false));
  }, []);

  function setSelectedSeason(season: number) {
    setSelectedSeasonState(season);
    window.localStorage.setItem(STORAGE_KEY, String(season));
  }

  const selectedLabel = useMemo(
    () => seasons.find((s) => s.season === selectedSeason)?.label || "Season",
    [seasons, selectedSeason]
  );

  return (
    <SeasonContext.Provider value={{ seasons, selectedSeason, selectedLabel, setSelectedSeason, loading }}>
      {children}
    </SeasonContext.Provider>
  );
}

export function useSeason() {
  const context = useContext(SeasonContext);
  if (!context) throw new Error("useSeason must be used inside SeasonProvider");
  return context;
}
