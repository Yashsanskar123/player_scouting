"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  api,
  formatEur,
  Shortlist,
  ShortlistDetail,
  ShortlistEntry,
  type EntryUpdate,
} from "@/lib/api";

import EntryWorkflow from "@/components/EntryWorkflow";
import WorkflowStrip from "@/components/WorkflowStrip";

import DownloadButton from "@/components/DownloadButton";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PlayerLink,
  RiskBadge,
} from "@/components/ui";
import { useSeason } from "@/components/SeasonContext";

const STATUSES = [
  "Discovery",
  "Monitoring",
  "Shortlisted",
  "Analyst Review",
  "Scout Review",
  "Final Target",
  "Negotiation",
  "Rejected",
  "Signed",
];

const ACTIVE_STATUSES = [
  "Discovery",
  "Monitoring",
  "Shortlisted",
  "Analyst Review",
  "Scout Review",
  "Final Target",
  "Negotiation",
];

const STATUS_STYLES: Record<string, string> = {
  Discovery:
    "text-muted border-border bg-panelraised",
  Monitoring:
    "text-accent border-accent/30 bg-accent/5",
  Shortlisted:
    "text-accent border-accent/40 bg-accent/10",
  "Analyst Review":
    "text-riskmed border-riskmed/30 bg-riskmed/5",
  "Scout Review":
    "text-riskmed border-riskmed/40 bg-riskmed/10",
  "Final Target":
    "text-risklow border-risklow/40 bg-risklow/10",
  Negotiation:
    "text-risklow border-risklow/50 bg-risklow/10",
  Signed:
    "text-risklow border-risklow/50 bg-risklow/15",
  Rejected:
    "text-riskhigh border-riskhigh/30 bg-riskhigh/5",
};

function playerField(
  player: Record<string, any> | undefined,
  ...keys: string[]
) {
  for (const key of keys) {
    if (
      player?.[key] !== undefined &&
      player?.[key] !== null
    ) {
      return player[key];
    }
  }

  return undefined;
}

function numeric(value: any): number | null {
  const n = Number(value);

  return Number.isFinite(n) ? n : null;
}

function pct(
  value: any,
  decimals = 1
): string {
  const n = numeric(value);

  return n === null
    ? "—"
    : `${n.toFixed(decimals)}%`;
}

function score(
  value: any
): string {
  const n = numeric(value);

  return n === null
    ? "—"
    : n.toFixed(1);
}

function calculateDecisionSignals(
  entry: ShortlistEntry
) {
  const p = entry.player || {};

  const performance =
    numeric(
      playerField(
        p,
        "performance_score"
      )
    ) ?? 0;

  const potential =
    numeric(
      playerField(
        p,
        "development_potential"
      )
    ) ?? 0;

  const expected12m =
    numeric(
      playerField(
        p,
        "expected_performance_12m"
      )
    ) ?? performance;

  const opportunity =
    numeric(
      playerField(
        p,
        "opportunity_score"
      )
    );

  const reliability =
    numeric(
      playerField(
        p,
        "sample_reliability_score"
      )
    );

  const rating =
    numeric(entry.rating);

  /*
   * This is intentionally not presented as a universal player ranking.
   * It is only a workspace signal for deciding what needs attention.
   */
  const attentionScore =
    (rating !== null
      ? rating * 10
      : performance) *
      0.35 +
    performance * 0.20 +
    potential * 0.15 +
    expected12m * 0.15 +
    (opportunity ?? 50) * 0.10 +
    (reliability ?? 50) * 0.05;

  let label = "Review";

  if (
    entry.status === "Final Target" ||
    entry.status === "Negotiation"
  ) {
    label = "Priority";
  } else if (
    attentionScore >= 75
  ) {
    label = "High attention";
  } else if (
    attentionScore >= 60
  ) {
    label = "Monitor";
  }

  return {
    attentionScore,
    label,
  };
}

export default function ScoutWorkspacePage() {
  const {
    selectedSeason,
    selectedLabel,
  } = useSeason();

  const [
    shortlists,
    setShortlists,
  ] = useState<Shortlist[]>([]);

  const [
    selectedId,
    setSelectedId,
  ] = useState<number | null>(null);

  const [
    detail,
    setDetail,
  ] = useState<ShortlistDetail | null>(
    null
  );

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    detailLoading,
    setDetailLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");

  const [
    newName,
    setNewName,
  ] = useState("");

  const [
    statusFilter,
    setStatusFilter,
  ] = useState("All");

  const [
    riskFilter,
    setRiskFilter,
  ] = useState("All");

  const [
    positionFilter,
    setPositionFilter,
  ] = useState("All");

  const [
    search,
    setSearch,
  ] = useState("");

  const [
    sortBy,
    setSortBy,
  ] = useState("attention");

  async function loadShortlists(
    selectFirst = true
  ) {
    try {
      setError("");

      const res =
        await api.listShortlists();

      setShortlists(res.results);

      if (
        selectFirst &&
        res.results.length &&
        selectedId === null
      ) {
        setSelectedId(
          res.results[0].id
        );
      }
    } catch (e: any) {
      setError(
        e.message ||
          "Could not load shortlists."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(
    id: number
  ) {
    setDetailLoading(true);

    try {
      setError("");

      const result =
        await api.getShortlist(
          id,
          selectedSeason
        );

      setDetail(result);
    } catch (e: any) {
      setError(
        e.message ||
          "Could not load shortlist."
      );
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    loadShortlists();
  }, []);

  useEffect(() => {
    if (selectedId !== null) {
      loadDetail(selectedId);
    }
  }, [
    selectedId,
    selectedSeason,
  ]);

  async function createShortlist() {
    const name =
      newName.trim();

    if (!name) {
      return;
    }

    try {
      setError("");

      const created =
        await api.createShortlist(
          name
        );

      setNewName("");

      await loadShortlists(
        false
      );

      setSelectedId(
        created.id
      );
    } catch (e: any) {
      setError(
        e.message ||
          "Could not create shortlist."
      );
    }
  }

  async function updateEntry(
    entryId: number,
    body: EntryUpdate
  ) {
    try {
      setError("");

      await api.updateShortlistEntry(
        entryId,
        body
      );

      if (
        selectedId !== null
      ) {
        await loadDetail(
          selectedId
        );
      }

      await loadShortlists(
        false
      );
    } catch (e: any) {
      setError(
        e.message ||
          "Could not update entry."
      );
    }
  }

  const activeEntries =
    detail?.entries ?? [];

  const positions = useMemo(() => {
    const values =
      activeEntries
        .map((entry) =>
          playerField(
            entry.player,
            "canonical_position"
          )
        )
        .filter(Boolean);

    return Array.from(
      new Set(values)
    ).sort();
  }, [activeEntries]);

  const filteredEntries =
    useMemo(() => {
      const query =
        search
          .trim()
          .toLowerCase();

      const filtered =
        activeEntries.filter(
          (entry) => {
            const p =
              entry.player ||
              {};

            const name =
              String(
                playerField(
                  p,
                  "short_name",
                  "player_name"
                ) ||
                  entry.player_id
              );

            const club =
              String(
                playerField(
                  p,
                  "club_name"
                ) || ""
              );

            const position =
              playerField(
                p,
                "canonical_position"
              );

            const risk =
              playerField(
                p,
                "recruitment_risk_tier"
              );

            if (
              statusFilter !==
                "All" &&
              entry.status !==
                statusFilter
            ) {
              return false;
            }

            if (
              riskFilter !==
                "All" &&
              risk !== riskFilter
            ) {
              return false;
            }

            if (
              positionFilter !==
                "All" &&
              position !==
                positionFilter
            ) {
              return false;
            }

            if (
              query &&
              !name
                .toLowerCase()
                .includes(query) &&
              !club
                .toLowerCase()
                .includes(query)
            ) {
              return false;
            }

            return true;
          }
        );

      return [...filtered].sort(
        (a, b) => {
          if (
            sortBy === "performance"
          ) {
            return (
              (numeric(
                playerField(
                  b.player,
                  "performance_score"
                )
              ) ?? -1) -
              (numeric(
                playerField(
                  a.player,
                  "performance_score"
                )
              ) ?? -1)
            );
          }

          if (
            sortBy === "potential"
          ) {
            return (
              (numeric(
                playerField(
                  b.player,
                  "development_potential"
                )
              ) ?? -1) -
              (numeric(
                playerField(
                  a.player,
                  "development_potential"
                )
              ) ?? -1)
            );
          }

          if (
            sortBy === "value_gap"
          ) {
            return (
              (numeric(
                playerField(
                  b.player,
                  "value_gap_pct"
                )
              ) ?? -999) -
              (numeric(
                playerField(
                  a.player,
                  "value_gap_pct"
                )
              ) ?? -999)
            );
          }

          if (
            sortBy === "rating"
          ) {
            return (
              (numeric(b.rating) ??
                -1) -
              (numeric(a.rating) ??
                -1)
            );
          }

          const aSignal =
            calculateDecisionSignals(
              a
            ).attentionScore;

          const bSignal =
            calculateDecisionSignals(
              b
            ).attentionScore;

          return (
            bSignal -
            aSignal
          );
        }
      );
    }, [
      activeEntries,
      search,
      statusFilter,
      riskFilter,
      positionFilter,
      sortBy,
    ]);

  const statusCounts =
    useMemo(
      () =>
        STATUSES.map(
          (status) => ({
            status,
            count:
              activeEntries.filter(
                (entry) =>
                  entry.status ===
                  status
              ).length,
          })
        ),
      [activeEntries]
    );

  const activeCount =
    activeEntries.filter(
      (entry) =>
        ACTIVE_STATUSES.includes(
          entry.status
        )
    ).length;

  const finalTargetCount =
    activeEntries.filter(
      (entry) =>
        entry.status ===
          "Final Target" ||
        entry.status ===
          "Negotiation"
    ).length;

  const signedCount =
    activeEntries.filter(
      (entry) =>
        entry.status ===
        "Signed"
    ).length;

  const rejectedCount =
    activeEntries.filter(
      (entry) =>
        entry.status ===
        "Rejected"
    ).length;

  const ratedEntries =
    activeEntries.filter(
      (entry) =>
        numeric(entry.rating) !==
        null
    );

  const averageRating =
    ratedEntries.length
      ? ratedEntries.reduce(
          (sum, entry) =>
            sum +
            (numeric(
              entry.rating
            ) ?? 0),
          0
        ) /
        ratedEntries.length
      : null;

  const highRiskCount =
    activeEntries.filter(
      (entry) =>
        playerField(
          entry.player,
          "recruitment_risk_tier"
        ) === "HIGH"
    ).length;

  if (loading) {
    return (
      <LoadingState label="Loading scout workspace" />
    );
  }

  return (
    <div className="space-y-6 pb-10">

      {/* -------------------------------------------------------
          HEADER
      ------------------------------------------------------- */}

      <header className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">

        <div>

          <div className="text-2xs uppercase tracking-[0.18em] text-accent mb-2">
            Recruitment workflow
          </div>

          <h1 className="text-2xl text-ink font-semibold tracking-tight">
            Scout workspace
          </h1>

          <p className="text-muted text-sm mt-1 max-w-3xl">
            Manage candidate progression from discovery
            through recruitment decision, with the selected
            analysis season kept separate from workflow state.
          </p>

          {selectedId !== null && (
            <div className="mt-3 flex flex-wrap gap-2">
              <DownloadButton label="Export shortlist to Excel" onDownload={() => api.downloadShortlistExcel(selectedId, selectedSeason)} />
              <DownloadButton label="Export shortlist meeting pack (PDF)" onDownload={() => api.downloadShortlistPdf(selectedId, selectedSeason)} />
            </div>
          )}

        </div>

        <div className="flex items-center gap-3">

          <div className="text-right">

            <div className="text-2xs uppercase tracking-wider text-faint">
              Analysis season
            </div>

            <div className="text-sm text-ink mt-0.5">
              {selectedLabel}
            </div>

          </div>

          <Link
            href="/scouting/search"
            className="action-button action-button-primary"
          >
            Find players
          </Link>

        </div>

      </header>


      {error && (
        <ErrorState message={error} />
      )}


      {/* -------------------------------------------------------
          WORKSPACE KPIs
      ------------------------------------------------------- */}

      <section className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">

        <Metric
          label="Tracked"
          value={activeEntries.length}
          sublabel="in selected shortlist"
        />

        <Metric
          label="Active pipeline"
          value={activeCount}
          sublabel="not signed/rejected"
        />

        <Metric
          label="Final / negotiation"
          value={finalTargetCount}
          sublabel="decision-stage targets"
        />

        <Metric
          label="Average rating"
          value={
            averageRating === null
              ? "—"
              : averageRating.toFixed(1)
          }
          sublabel={`${ratedEntries.length} rated`}
        />

        <Metric
          label="High risk"
          value={highRiskCount}
          sublabel="requires scrutiny"
        />

        <Metric
          label="Closed"
          value={
            signedCount +
            rejectedCount
          }
          sublabel={`${signedCount} signed · ${rejectedCount} rejected`}
        />

      </section>


      {/* -------------------------------------------------------
          MAIN WORKSPACE
      ------------------------------------------------------- */}

      <section className="grid grid-cols-1 xl:grid-cols-[260px_1fr] gap-5">

        {/* -----------------------------------------------------
            SHORTLIST SIDEBAR
        ----------------------------------------------------- */}

        <aside className="analytics-panel p-4 h-fit">

          <div className="text-2xs uppercase tracking-wider text-faint mb-3">
            Shortlists
          </div>

          <div className="flex gap-2 mb-4">

            <input
              value={newName}
              onChange={(e) =>
                setNewName(
                  e.target.value
                )
              }
              onKeyDown={(e) => {
                if (
                  e.key ===
                  "Enter"
                ) {
                  createShortlist();
                }
              }}
              placeholder="New shortlist"
              className="flex-1 min-w-0 bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink placeholder:text-faint"
            />

            <button
              onClick={
                createShortlist
              }
              className="action-button action-button-primary px-3"
              title="Create shortlist"
            >
              +
            </button>

          </div>


          <div className="space-y-1">

            {shortlists.map(
              (shortlist) => (
                <button
                  key={
                    shortlist.id
                  }
                  onClick={() =>
                    setSelectedId(
                      shortlist.id
                    )
                  }
                  className={`w-full text-left px-3 py-2.5 rounded-sm border transition-colors ${
                    selectedId ===
                    shortlist.id
                      ? "bg-panelraised border-accent/50"
                      : "border-transparent hover:bg-panelraised/60"
                  }`}
                >

                  <div className="flex items-center justify-between gap-2">

                    <span className="text-sm text-ink truncate">
                      {shortlist.name}
                    </span>

                    <span className="text-2xs text-faint tabular">
                      {shortlist.entry_count}
                    </span>

                  </div>

                </button>
              )
            )}

          </div>


          {shortlists.length ===
            0 && (
            <div className="text-xs text-faint py-5">
              Create a shortlist to start tracking targets.
            </div>
          )}

        </aside>


        {/* -----------------------------------------------------
            SELECTED SHORTLIST
        ----------------------------------------------------- */}

        <main className="min-w-0">

          {!selectedId && (
            <EmptyState
              title="No shortlist selected"
              body="Create a shortlist, then add candidates from Player Search."
            />
          )}


          {selectedId !== null &&
            detailLoading && (
              <LoadingState
                label="Loading shortlist"
              />
            )}


          {selectedId !== null &&
            !detailLoading &&
            detail && (
              <>

                {/* ---------------------------------------------
                    SHORTLIST HEADER
                --------------------------------------------- */}

                <section className="analytics-panel p-5 mb-5">

                  <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">

                    <div>

                      <div className="flex items-center gap-2">

                        <h2 className="text-lg text-ink font-medium">
                          {detail.name}
                        </h2>

                        <span className="text-2xs border border-border bg-panelraised px-2 py-1 rounded-sm text-faint">
                          {selectedLabel}
                        </span>

                      </div>

                      <div className="text-xs text-muted mt-1">
                        {activeEntries.length} tracked candidates
                      </div>

                    </div>


                    <div className="flex flex-wrap gap-1.5">

                      {statusCounts
                        .filter(
                          (item) =>
                            item.count >
                            0
                        )
                        .map(
                          (item) => (
                            <span
                              key={
                                item.status
                              }
                              className={`px-2 py-1 rounded-sm border text-2xs ${
                                STATUS_STYLES[
                                  item.status
                                ] ||
                                "border-border text-muted"
                              }`}
                            >
                              {
                                item.status
                              }{" "}
                              <b className="text-ink">
                                {
                                  item.count
                                }
                              </b>
                            </span>
                          )
                        )}

                    </div>

                  </div>

                </section>


                {/* ---------------------------------------------
                    PIPELINE
                --------------------------------------------- */}

                <section className="analytics-panel p-5 mb-5">

                  <div className="flex items-center justify-between gap-4 mb-4">

                    <div>

                      <h2 className="text-sm text-ink font-medium">
                        Recruitment pipeline
                      </h2>

                      <p className="text-2xs text-muted mt-1">
                        Candidate progression inside this shortlist.
                      </p>

                    </div>

                  </div>


                  <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-9 gap-2">

                    {STATUSES.map(
                      (status) => {

                        const count =
                          statusCounts.find(
                            (item) =>
                              item.status ===
                              status
                          )?.count ??
                          0;

                        return (
                          <button
                            key={status}
                            onClick={() =>
                              setStatusFilter(
                                status
                              )
                            }
                            className={`text-left border rounded-sm px-3 py-3 transition-colors ${
                              statusFilter ===
                              status
                                ? "border-accent bg-accent/5"
                                : "border-border bg-panel hover:bg-panelraised"
                            }`}
                          >

                            <div className="text-2xs text-faint truncate">
                              {status}
                            </div>

                            <div className="text-xl text-ink tabular font-medium mt-1">
                              {count}
                            </div>

                          </button>
                        );
                      }
                    )}

                  </div>


                  {statusFilter !==
                    "All" && (
                    <button
                      onClick={() =>
                        setStatusFilter(
                          "All"
                        )
                      }
                      className="text-2xs text-accent mt-3 hover:underline"
                    >
                      Clear pipeline filter
                    </button>
                  )}

                </section>


                {/* ---------------------------------------------
                    FILTERS
                --------------------------------------------- */}

                <section className="border border-border bg-panel rounded-sm p-4 mb-5">

                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">

                    <FilterField label="Search">

                      <input
                        value={search}
                        onChange={(e) =>
                          setSearch(
                            e.target.value
                          )
                        }
                        placeholder="Player or club"
                        className="w-full bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink placeholder:text-faint"
                      />

                    </FilterField>


                    <FilterField label="Status">

                      <select
                        value={
                          statusFilter
                        }
                        onChange={(e) =>
                          setStatusFilter(
                            e.target.value
                          )
                        }
                        className="w-full bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink"
                      >

                        <option value="All">
                          All statuses
                        </option>

                        {STATUSES.map(
                          (status) => (
                            <option
                              key={
                                status
                              }
                              value={
                                status
                              }
                            >
                              {status}
                            </option>
                          )
                        )}

                      </select>

                    </FilterField>


                    <FilterField label="Position">

                      <select
                        value={
                          positionFilter
                        }
                        onChange={(e) =>
                          setPositionFilter(
                            e.target.value
                          )
                        }
                        className="w-full bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink"
                      >

                        <option value="All">
                          All positions
                        </option>

                        {positions.map(
                          (position) => (
                            <option
                              key={
                                position
                              }
                              value={
                                position
                              }
                            >
                              {position}
                            </option>
                          )
                        )}

                      </select>

                    </FilterField>


                    <FilterField label="Risk">

                      <select
                        value={
                          riskFilter
                        }
                        onChange={(e) =>
                          setRiskFilter(
                            e.target.value
                          )
                        }
                        className="w-full bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink"
                      >

                        <option value="All">
                          All risk tiers
                        </option>

                        <option value="LOW">
                          LOW
                        </option>

                        <option value="MEDIUM">
                          MEDIUM
                        </option>

                        <option value="HIGH">
                          HIGH
                        </option>

                      </select>

                    </FilterField>


                    <FilterField label="Sort">

                      <select
                        value={
                          sortBy
                        }
                        onChange={(e) =>
                          setSortBy(
                            e.target.value
                          )
                        }
                        className="w-full bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink"
                      >

                        <option value="attention">
                          Decision attention
                        </option>

                        <option value="performance">
                          Performance
                        </option>

                        <option value="potential">
                          Potential
                        </option>

                        <option value="value_gap">
                          Value gap
                        </option>

                        <option value="rating">
                          Scout rating
                        </option>

                      </select>

                    </FilterField>

                  </div>


                  <div className="flex items-center justify-between gap-3 mt-3">

                    <div className="text-2xs text-muted">
                      Showing{" "}
                      <span className="text-ink">
                        {
                          filteredEntries.length
                        }
                      </span>{" "}
                      of{" "}
                      <span className="text-ink">
                        {
                          activeEntries.length
                        }
                      </span>{" "}
                      candidates
                    </div>

                    <button
                      onClick={() => {
                        setSearch("");
                        setStatusFilter(
                          "All"
                        );
                        setRiskFilter(
                          "All"
                        );
                        setPositionFilter(
                          "All"
                        );
                        setSortBy(
                          "attention"
                        );
                      }}
                      className="text-2xs text-accent hover:underline"
                    >
                      Reset filters
                    </button>

                  </div>

                </section>


                {/* ---------------------------------------------
                    CANDIDATES
                --------------------------------------------- */}

                {activeEntries.length ===
                  0 ? (
                  <EmptyState
                    title="Your shortlist is empty"
                    body="Go to Player Search and add candidates as you discover them."
                  />
                ) : filteredEntries.length ===
                  0 ? (
                  <EmptyState
                    title="No candidates match these filters"
                    body="Reset the filters or broaden the search."
                  />
                ) : (
                  <div className="space-y-3">

                    <WorkflowStrip workflow={detail?.workflow} />

                    {filteredEntries.map(
                      (entry) => (
                        <div key={entry.id}>
                          <CandidateCard
                            entry={entry}
                            onUpdate={
                              updateEntry
                            }
                          />
                          <EntryWorkflow
                            entry={entry}
                            onUpdate={
                              updateEntry
                            }
                          />
                        </div>
                      )
                    )}

                  </div>
                )}


                {/* ---------------------------------------------
                    WORKFLOW NOTE
                --------------------------------------------- */}

                <section className="border border-border bg-panel rounded-sm p-4 mt-6">

                  <h2 className="text-sm text-ink font-medium">
                    Workspace methodology
                  </h2>

                  <div className="grid md:grid-cols-3 gap-5 mt-3 text-2xs leading-relaxed">

                    <div>

                      <div className="text-faint">
                        Workflow state
                      </div>

                      <div className="text-muted mt-1">
                        Status, scout rating and notes are
                        transactional shortlist data stored
                        independently from player-season facts.
                      </div>

                    </div>


                    <div>

                      <div className="text-faint">
                        Decision signals
                      </div>

                      <div className="text-muted mt-1">
                        Candidate cards surface performance,
                        potential, expected 12-month output,
                        value, risk and evidence where those
                        fields exist in the selected season.
                      </div>

                    </div>


                    <div>

                      <div className="text-faint">
                        Data boundary
                      </div>

                      <div className="text-muted mt-1">
                        Market value and model-derived signals
                        are analytical evidence, not contract
                        terms, transfer fees or guarantees.
                      </div>

                    </div>

                  </div>

                </section>

              </>
            )}

        </main>

      </section>

    </div>
  );
}


function CandidateCard({
  entry,
  onUpdate,
}: {
  entry: ShortlistEntry;
  onUpdate: (
    id: number,
    body: {
      status?: string;
      notes?: string;
      rating?: number;
    }
  ) => Promise<void>;
}) {
  const p =
    entry.player || {};

  const name =
    playerField(
      p,
      "short_name",
      "player_name"
    ) ||
    entry.player_id;

  const position =
    playerField(
      p,
      "canonical_position"
    );

  const club =
    playerField(
      p,
      "club_name"
    );

  const league =
    playerField(
      p,
      "league_name"
    );

  const performance =
    playerField(
      p,
      "performance_score"
    );

  const potential =
    playerField(
      p,
      "development_potential"
    );

  const expected12m =
    playerField(
      p,
      "expected_performance_12m"
    );

  const value =
    playerField(
      p,
      "value_eur"
    );

  const fairValue =
    playerField(
      p,
      "fair_value_eur"
    );

  const valueGap =
    playerField(
      p,
      "value_gap_pct"
    );

  const opportunity =
    playerField(
      p,
      "opportunity_score"
    );

  const minutes =
    playerField(
      p,
      "playing_time_min"
    );

  const reliability =
    playerField(
      p,
      "sample_reliability_score"
    );

  const risk =
    playerField(
      p,
      "recruitment_risk_tier"
    );

  const age =
    playerField(
      p,
      "age_fifa"
    );

  const signal =
    calculateDecisionSignals(
      entry
    );

  const [
    notes,
    setNotes,
  ] = useState(
    entry.notes || ""
  );

  const [
    rating,
    setRating,
  ] = useState(
    entry.rating?.toString() ||
      ""
  );

  const [
    saving,
    setSaving,
  ] = useState(false);

  async function save() {
    setSaving(true);

    try {
      await onUpdate(
        entry.id,
        {
          notes,
          rating: rating
            ? Number(rating)
            : undefined,
        }
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="analytics-panel p-5">

      <div className="flex flex-col 2xl:flex-row gap-5">

        {/* -----------------------------------------------
            PLAYER INFORMATION
        ------------------------------------------------ */}

        <div className="flex-1 min-w-0">

          <div className="flex flex-wrap items-center gap-2">

            <PlayerLink
              playerId={
                entry.player_id
              }
              name={String(name)}
            />

            {position && (
              <span className="text-2xs border border-border px-1.5 py-0.5 rounded-sm text-muted">
                {position}
              </span>
            )}

            {risk && (
              <RiskBadge
                tier={risk}
              />
            )}

            <span
              className={`px-1.5 py-0.5 rounded-sm text-2xs border ${
                STATUS_STYLES[
                  entry.status
                ] ||
                "border-border text-muted"
              }`}
            >
              {entry.status}
            </span>

          </div>


          <div className="text-xs text-muted mt-1">
            {club || "—"}
            {league
              ? ` · ${league}`
              : ""}
            {age !== undefined &&
              age !== null
              ? ` · ${age} yrs`
              : ""}
          </div>


          {/* Decision signal */}

          <div className="mt-4 border border-border bg-panelraised rounded-sm p-3">

            <div className="flex items-center justify-between gap-3">

              <div>

                <div className="text-2xs uppercase tracking-wider text-faint">
                  Decision signal
                </div>

                <div className="text-sm text-ink mt-0.5">
                  {signal.label}
                </div>

              </div>

              <div className="text-right">

                <div className="text-2xs text-faint">
                  Attention signal
                </div>

                <div className="text-sm text-ink tabular">
                  {signal.attentionScore.toFixed(
                    0
                  )}
                </div>

              </div>

            </div>

          </div>


          {/* Metrics */}

          <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-x-4 gap-y-4 mt-4">

            <MiniMetric
              label="Performance"
              value={score(
                performance
              )}
            />

            <MiniMetric
              label="Potential"
              value={score(
                potential
              )}
            />

            <MiniMetric
              label="12M expected"
              value={score(
                expected12m
              )}
            />

            <MiniMetric
              label="Market value"
              value={formatEur(
                numeric(value)
              )}
            />

            <MiniMetric
              label="Fair value"
              value={formatEur(
                numeric(
                  fairValue
                )
              )}
            />

            <MiniMetric
              label="Value gap"
              value={pct(
                valueGap
              )}
            />

            <MiniMetric
              label="Minutes"
              value={
                minutes == null
                  ? "—"
                  : Number(
                      minutes
                    ).toLocaleString()
              }
            />

            <MiniMetric
              label="Reliability"
              value={score(
                reliability
              )}
            />

          </div>


          {/* Recruitment evidence */}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-5">

            <EvidenceCard
              label="Opportunity"
              value={score(
                opportunity
              )}
              description="Transfer-intelligence signal"
            />

            <EvidenceCard
              label="Value position"
              value={pct(
                valueGap
              )}
              description="Modelled fair-value gap"
            />

            <EvidenceCard
              label="Scout assessment"
              value={
                entry.rating == null
                  ? "Not rated"
                  : `${entry.rating}/10`
              }
              description="Human scout input"
            />

          </div>


          {/* Quick actions */}

          <div className="flex flex-wrap gap-2 mt-5">

            <Link
              href={`/players/${entry.player_id}`}
              className="action-button"
            >
              Open profile
            </Link>

            <Link
              href={`/scouting/compare?players=${entry.player_id}`}
              className="action-button"
            >
              Compare
            </Link>

            <Link
              href={`/scouting/replace?for=${entry.player_id}`}
              className="action-button"
            >
              Find replacements
            </Link>

          </div>

        </div>


        {/* -----------------------------------------------
            WORKFLOW CONTROLS
        ------------------------------------------------ */}

        <div className="w-full 2xl:w-72 space-y-3">

          <label className="block">

            <div className="text-2xs text-faint mb-1">
              Recruitment status
            </div>

            <select
              value={
                entry.status
              }
              onChange={(e) =>
                onUpdate(
                  entry.id,
                  {
                    status:
                      e.target
                        .value,
                  }
                )
              }
              className="w-full bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink"
            >

              {STATUSES.map(
                (status) => (
                  <option
                    key={status}
                    value={status}
                  >
                    {status}
                  </option>
                )
              )}

            </select>

          </label>


          <div className="grid grid-cols-[1fr_72px] gap-2">

            <input
              value={notes}
              onChange={(e) =>
                setNotes(
                  e.target.value
                )
              }
              placeholder="Scout note…"
              className="bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink placeholder:text-faint"
            />

            <input
              value={rating}
              onChange={(e) =>
                setRating(
                  e.target.value
                    .replace(
                      /[^0-9]/g,
                      ""
                    )
                    .slice(
                      0,
                      2
                    )
                )
              }
              placeholder="/10"
              inputMode="numeric"
              className="bg-panelraised border border-border rounded-sm px-2.5 py-2 text-xs text-ink"
            />

          </div>


          <button
            disabled={saving}
            onClick={save}
            className="action-button w-full"
          >
            {saving
              ? "Saving…"
              : "Save assessment"}
          </button>


          <div className="border-t border-border pt-3 mt-3">

            <div className="text-2xs text-faint mb-2">
              Current assessment
            </div>

            <div className="text-xs text-muted leading-relaxed min-h-[42px]">
              {entry.notes ||
                "No scout note recorded yet."}
            </div>

          </div>

        </div>

      </div>

    </article>
  );
}


function Metric({
  label,
  value,
  sublabel,
}: {
  label: string;
  value: string | number;
  sublabel: string;
}) {
  return (
    <div className="border border-border bg-panel rounded-sm px-4 py-3">

      <div className="text-2xs text-faint">
        {label}
      </div>

      <div className="text-xl text-ink tabular font-medium mt-1">
        {value}
      </div>

      <div className="text-2xs text-muted mt-1">
        {sublabel}
      </div>

    </div>
  );
}


function MiniMetric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div>

      <div className="text-2xs text-faint">
        {label}
      </div>

      <div className="text-sm text-ink tabular mt-0.5">
        {value}
      </div>

    </div>
  );
}


function EvidenceCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div className="border border-border rounded-sm bg-panelraised px-3 py-3">

      <div className="text-2xs text-faint">
        {label}
      </div>

      <div className="text-sm text-ink tabular mt-1">
        {value}
      </div>

      <div className="text-2xs text-muted mt-1 leading-relaxed">
        {description}
      </div>

    </div>
  );
}


function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">

      <div className="text-2xs text-faint mb-1">
        {label}
      </div>

      {children}

    </label>
  );
}