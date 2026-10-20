const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010";

const TOKEN_KEY = "scoutiq:token";

export function getToken(): string | null {
  try { return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string): void {
  try { window.localStorage.setItem(TOKEN_KEY, token); } catch { /* storage unavailable */ }
}
export function clearToken(): void {
  try { window.localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (res.status === 401 && token && typeof window !== "undefined" && window.location.pathname !== "/login") {
    // Session expired or account disabled: drop the token and ask the user to sign in again.
    clearToken();
    window.location.replace("/login");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export type PlayerSummary = {
  player_id: string;
  short_name: string;
  canonical_position: string;
  club_name?: string;
  league_name?: string;
  age_fifa?: number;
  value_eur?: number;
  performance_score?: number;
  development_potential?: number;
  role_fit_score?: number;
  recruitment_risk_tier?: "LOW" | "MEDIUM" | "HIGH";
  fair_value_eur?: number;
  value_gap_pct?: number;
  opportunity_score?: number;
  wage_eur?: number;
  wage_to_value_pct?: number;
  contract_status?: string;
  evidence_coverage_pct?: number;
  three_year_avg_performance?: number;
  five_year_avg_performance?: number;
  performance_trend_per_season?: number;
  performance_consistency_std?: number;
  career_minutes_to_date?: number;
  seasons_played_to_date?: number;
  career_peak_performance?: number;
};

export type Shortlist = { id: number; name: string; entry_count: number; created_at?: string | null };
export type ScoutNote = { id: number; player_id: string; author?: string | null; note: string; created_at?: string | null };
export type ShortlistEntry = {
  id: number; player_id: string; status: string; notes?: string | null; rating?: number | null;
  added_at?: string | null; player?: Record<string, any>;
  owner?: string | null; due_date?: string | null; next_action?: string | null;
};
export type WorkflowSummary = { open: number; overdue: number; due_within_7_days: number; unassigned: number; no_next_action: number };
export type ShortlistDetail = { id: number; name: string; created_at?: string | null; entries: ShortlistEntry[]; workflow?: WorkflowSummary };
export type EntryUpdate = { status?: string; notes?: string; rating?: number; owner?: string; due_date?: string; next_action?: string };


export type DashboardMover = {
  player_id: string;
  short_name?: string;
  canonical_position?: string;
  club_name?: string;
  age_fifa?: number;
  current_performance?: number;
  previous_performance?: number;
  performance_delta?: number;
  current_minutes?: number;
  development_potential?: number;
  value_eur?: number;
};

export type DashboardOverview = {
  season: number;
  snapshot: {
    season: number;
    player_count: number;
    average_performance?: number | null;
    median_value_eur?: number | null;
    average_potential?: number | null;
    median_minutes?: number | null;
  };
  movers: {
    season: number;
    previous_season?: number | null;
    eligible_players: number;
    improved_total: number;
    declined_total: number;
    improved: DashboardMover[];
    declined: DashboardMover[];
    method: {
      min_minutes_each_season: number;
      performance_change_threshold: number;
    };
  };
  breakout: {
    season: number;
    previous_season?: number | null;
    total: number;
    results: Array<DashboardMover & { breakout_score?: number }>;
    method: {
      max_age?: number;
      min_minutes_each_season?: number;
      min_current_performance?: number;
      min_potential?: number;
      min_performance_delta?: number;
    };
  };
  market_opportunities_total?: number | null;
};

export type PlayersListResponse = {
  total: number;
  page: number;
  page_size: number;
  results: PlayerSummary[];
};

export type OpportunityParams = {
    topN?: number;
    minPerformanceScore?: number;
    minValueGapPct?: number;
    minAge?: number;
    maxAge?: number;
    canonicalPosition?: string;
    leagueName?: string;
    riskTier?: string;
    segment?: string;
    season?: number | null;
    minReliabilityTier?: string;
    maxContractMonths?: string;
  };

function buildOpportunityQuery(params: OpportunityParams): URLSearchParams {
    const qs = new URLSearchParams({
      top_n: String(params.topN ?? 20),
      min_performance_score:
        String(params.minPerformanceScore ?? 60),
      min_value_gap_pct:
        String(params.minValueGapPct ?? -100),
      segment:
        params.segment ?? "all",
    });

    if (params.minAge != null) {
      qs.set(
        "min_age",
        String(params.minAge)
      );
    }

    if (params.maxAge != null) {
      qs.set(
        "max_age",
        String(params.maxAge)
      );
    }

    if (params.canonicalPosition) {
      qs.set(
        "canonical_position",
        params.canonicalPosition
      );
    }

    if (params.leagueName) {
      qs.set(
        "league_name",
        params.leagueName
      );
    }

    if (params.riskTier) {
      qs.set(
        "risk_tier",
        params.riskTier
      );
    }

    if (params.maxContractMonths) {
      qs.set(
        "max_contract_months",
        params.maxContractMonths
      );
    }

    if (params.minReliabilityTier) {
      qs.set(
        "min_reliability_tier",
        params.minReliabilityTier
      );
    }

    if (params.season != null) {
      qs.set(
        "season",
        String(params.season)
      );
    }

    return qs;
}

export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, cache: "no-store" });
  if (res.status === 401 && token && typeof window !== "undefined" && window.location.pathname !== "/login") {
    clearToken();
    window.location.replace("/login");
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail; } catch { /* not JSON */ }
    throw new Error(detail || `Download failed (${res.status})`);
  }
  const match = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") || "");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  seasons: () => request<{ current_season: number | null; seasons: { season: number; label: string; short_label: string; status: string }[] }>("/api/seasons"),
  dataQuality: () => request<any>("/api/data-quality"),
  dashboardOverview: (season?: number | null) =>
    request<DashboardOverview>(`/api/dashboard/overview${season == null ? "" : `?season=${season}`}`),
  listPlayers: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== "") as [string, string][]
    ).toString();
    return request<PlayersListResponse>(`/api/players?${qs}`);
  },
  getPlayer: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}${season == null ? "" : `?season=${season}`}`),
  getPercentiles: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/percentiles${season == null ? "" : `?season=${season}`}`),
  getRoles: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/roles${season == null ? "" : `?season=${season}`}`),
  getSimilar: (playerId: string, topN = 8, season?: number | null) => {
    const qs = new URLSearchParams({ top_n: String(topN) });
    if (season != null) qs.set("season", String(season));
    return request<any>(`/api/players/${playerId}/similar?${qs.toString()}`);
  },
  getValue: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/value${season == null ? "" : `?season=${season}`}`),
  getRisk: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/risk${season == null ? "" : `?season=${season}`}`),
  getTransferIntelligence: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/transfer-intelligence${season == null ? "" : `?season=${season}`}`),
  getTacticalFit: (playerId: string, formation = "4-3-3", style = "Balanced", role?: string, season?: number | null) => {
    const qs = new URLSearchParams({ formation, style });
    if (role) qs.set("role", role);
    if (season != null) qs.set("season", String(season));
    return request<any>(`/api/players/${playerId}/tactical-fit?${qs.toString()}`);
  },
  getTransfermarkt: (playerId: string) => request<any>(`/api/players/${playerId}/transfermarkt`),
  getPlayerHistory: (playerId: string) => request<any>(`/api/players/${playerId}/history`),
  getProfileIntelligence: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/profile-intelligence${season == null ? "" : `?season=${season}`}`),
  getPotential: (playerId: string, season?: number | null) => request<any>(`/api/players/${playerId}/potential${season == null ? "" : `?season=${season}`}`),
  getDevelopmentLab: (
    playerId: string,
    season?: number | null
  ) =>
    request<any>(
      `/api/players/${playerId}/development-lab${
        season == null ? "" : `?season=${season}`
      }`
    ),
  scoutingSearch: (body: Record<string, unknown>) =>
    request<{ total: number; results: PlayerSummary[] }>("/api/scouting/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listShortlists: () => request<{ results: Shortlist[] }>("/api/recruitment/shortlists"),
  getShortlist: (id: number, season?: number | null) => request<ShortlistDetail>(`/api/recruitment/shortlists/${id}${season == null ? "" : `?season=${season}`}`),
  createShortlist: (name: string) => request<{ id: number; name: string }>("/api/recruitment/shortlists", {
    method: "POST", body: JSON.stringify({ name }),
  }),
  addToShortlist: (shortlistId: number, body: { player_id: string; status?: string; notes?: string; rating?: number }) =>
    request<any>(`/api/recruitment/shortlists/${shortlistId}/entries`, { method: "POST", body: JSON.stringify(body) }),
  updateShortlistEntry: (entryId: number, body: EntryUpdate) =>
    request<any>(`/api/recruitment/entries/${entryId}`, { method: "PATCH", body: JSON.stringify(body) }),
  listScoutNotes: (playerId: string) => request<{ results: ScoutNote[] }>(`/api/recruitment/players/${playerId}/notes`),
  createScoutNote: (playerId: string, note: string, author?: string) =>
    request<ScoutNote>(`/api/recruitment/players/${playerId}/notes`, {
      method: "POST", body: JSON.stringify({ player_id: playerId, note, author: author || null }),
    }),
  marketOpportunities: (params: OpportunityParams = {}) =>
    request<any>(`/api/market/opportunities?${buildOpportunityQuery(params).toString()}`),
  contractBoard: (
    params: Record<string, string | number | undefined> = {}
  ) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(
        ([, v]) => v !== undefined && v !== ""
      ) as [string, string][]
    ).toString();

    return request<any>(`/api/contracts/board?${qs}`);
  },
  downloadContractBoardPdf: (
    params: Record<string, string | number | undefined> = {}
  ) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(
        ([, v]) => v !== undefined && v !== ""
      ) as [string, string][]
    ).toString();

    return downloadFile(
      `/api/contracts/board/export.pdf?${qs}`,
      "scoutiq-contract-expiry-board.pdf"
    );
  },
  downloadOpportunitiesExcel: (params: OpportunityParams = {}) =>
    downloadFile(`/api/market/opportunities/export.xlsx?${buildOpportunityQuery({ ...params, topN: 200 }).toString()}`, "scoutiq-market-opportunities.xlsx"),

  authStatus: () => request<any>("/api/auth/status"),
  login: (username: string, password: string) =>
    request<any>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request<any>("/api/auth/me"),
  listUsers: () => request<any>("/api/users"),
  createUser: (body: Record<string, unknown>) =>
    request<any>("/api/users", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (username: string, body: Record<string, unknown>) =>
    request<any>(`/api/users/${encodeURIComponent(username)}`, { method: "PATCH", body: JSON.stringify(body) }),
  auditLog: (params: { limit?: number; offset?: number; username?: string; action?: string } = {}) => {
    const qs = new URLSearchParams();
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    if (params.username) qs.set("username", params.username);
    if (params.action) qs.set("action", params.action);
    return request<any>(`/api/audit-log?${qs.toString()}`);
  },
  downloadPlayerReport: (playerId: string, season?: number | null) =>
    downloadFile(`/api/players/${playerId}/report.pdf${season != null ? `?season=${season}` : ""}`, "scoutiq-player-report.pdf"),
  downloadShortlistExcel: (shortlistId: number, season?: number | null) =>
    downloadFile(`/api/recruitment/shortlists/${shortlistId}/export.xlsx${season != null ? `?season=${season}` : ""}`, "scoutiq-shortlist.xlsx"),
  downloadShortlistPdf: (
    shortlistId: number,
    season?: number | null
  ) =>
    downloadFile(
      `/api/recruitment/shortlists/${shortlistId}/export.pdf${
        season != null ? `?season=${season}` : ""
      }`,
      "scoutiq-shortlist-pack.pdf"
    ),
  downloadClubReport: (season?: number | null) =>
    downloadFile(`/api/club-profile/report.pdf${season != null ? `?season=${season}` : ""}`, "scoutiq-club-report.pdf"),
  getSecurityStatus: () => request<any>("/api/admin/security-status"),
  getDataHealth: () => request<any>("/api/data-health"),
  getDataFreshness: () => request<any>("/api/data-freshness"),
  getModelValidation: () => request<any>("/api/model-validation"),
  getValidationStatus: () => request<any>("/api/model-validation/status"),
  explainPlayer: (playerId: string, season?: number | null) =>
    request<any>(`/api/players/${playerId}/explain${season != null ? `?season=${season}` : ""}`),
  getClubs: (season?: number | null) =>
    request<any>(`/api/clubs${season != null ? `?season=${season}` : ""}`),
  getClubProfile: () => request<any>("/api/club-profile"),
  saveClubProfile: (body: Record<string, unknown>) =>
    request<any>("/api/club-profile", { method: "PUT", body: JSON.stringify(body) }),
  deleteClubProfile: (clubName?: string) =>
    request<any>(`/api/club-profile${clubName ? `?club_name=${encodeURIComponent(clubName)}` : ""}`, { method: "DELETE" }),
  activateClub: (clubName: string) =>
    request<any>(`/api/club-profile/activate?club_name=${encodeURIComponent(clubName)}`, { method: "POST" }),
  compareClubs: (clubs: string[], season?: number | null) =>
    request<any>(`/api/clubs/compare?${clubs.map((c) => `clubs=${encodeURIComponent(c)}`).join("&")}${season != null ? `&season=${season}` : ""}`),
  clubDashboard: (season?: number | null) =>
    request<any>(`/api/dashboard/club${season != null ? `?season=${season}` : ""}`),
  recruitmentTasks: (owner?: string) =>
    request<any>(`/api/recruitment/tasks${owner ? `?owner=${encodeURIComponent(owner)}` : ""}`),
  entryEvents: (entryId: number) => request<any>(`/api/recruitment/entries/${entryId}/events`),
  getClubOverview: (season?: number | null) =>
    request<any>(`/api/club-profile/overview${season != null ? `?season=${season}` : ""}`),
  optimizeSquad: (body: Record<string, unknown>) =>
    request<any>("/api/squads/optimize", { method: "POST", body: JSON.stringify(body) }),
  auditSquad: (body: Record<string, unknown>) =>
    request<any>("/api/squads/audit", { method: "POST", body: JSON.stringify(body) }),
  simulateTransfer: (body: Record<string, unknown>) =>
    request<any>("/api/transfers/simulate", { method: "POST", body: JSON.stringify(body) }),
  comparePlayers: (playerIds: string[], season?: number | null) =>
    request<any>("/api/players/compare", { method: "POST", body: JSON.stringify({ player_ids: playerIds, season: season ?? undefined }) }),
  findReplacements: (body: Record<string, unknown>) =>
    request<any>("/api/replacement/search", { method: "POST", body: JSON.stringify(body) }),
  dataQualitySafe: async () => {
    try {
      return await request<any>("/api/data-quality");
    } catch {
      return null;
    }
  },
};

export function formatEur(value?: number | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `€${(value / 1_000).toFixed(0)}K`;
  return `€${value.toFixed(0)}`;
}
