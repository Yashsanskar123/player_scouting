"use client";

import { useEffect, useState } from "react";
import { api, PlayerSummary } from "@/lib/api";

export function PlayerPicker({
  onSelect,
  placeholder = "Search for a player...",
  season,
}: {
  onSelect: (player: PlayerSummary) => void;
  placeholder?: string;
  season?: number | null;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlayerSummary[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const handle = setTimeout(() => {
      api
        .listPlayers({ search: query, page_size: 6, season: season ?? undefined })
        .then((res) => setResults(res.results))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [query, season]);

  return (
    <div className="relative">
      <input
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="w-full bg-panelraised border border-border rounded-sm px-2 py-1.5 text-sm text-ink placeholder:text-faint"
      />
      {open && results.length > 0 && (
        <div className="absolute z-10 mt-1 w-full border border-border bg-panelraised rounded-sm shadow-lg max-h-64 overflow-y-auto">
          {results.map((p) => (
            <button
              key={p.player_id}
              onClick={() => {
                onSelect(p);
                setQuery("");
                setResults([]);
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-panel transition-colors flex items-center justify-between"
            >
              <span>{p.short_name}</span>
              <span className="text-2xs text-faint">{p.canonical_position} · {p.club_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
