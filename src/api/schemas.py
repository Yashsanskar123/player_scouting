from __future__ import annotations

from pydantic import BaseModel, Field


class ScoutingSearchRequest(BaseModel):
    season: int | None = None
    canonical_position: str | None = None
    role: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    max_value_eur: float | None = None
    min_performance_score: float | None = None
    min_potential: float | None = None
    league_name: str | None = None
    max_risk_tier: str | None = Field(default=None, description="LOW, MEDIUM, or HIGH ceiling")
    min_three_year_avg_performance: float | None = None
    min_five_year_avg_performance: float | None = None
    min_performance_trend: float | None = None
    max_performance_consistency_std: float | None = None
    min_career_minutes: float | None = None
    min_seasons_played: int | None = None
    top_n: int = 20


class SquadOptimizeRequest(BaseModel):
    formation: str = "4-3-3"
    budget_eur: float | None = None
    league_name: str | None = None
    season: int | None = None
    max_age: int | None = None
    strategy: str = "balanced"

class SquadAuditRequest(BaseModel):
    club_name: str
    season: int | None = None
    formation: str = "4-3-3"


class TransferSimulateRequest(BaseModel):
    club_name: str
    season: int | None = None
    outgoing_player_id: str | None = None
    incoming_player_id: str


class ReplacementSearchRequest(BaseModel):
    season: int | None = None
    outgoing_player_id: str
    budget_eur: float | None = None
    min_age: int | None = None
    max_age: int | None = None
    top_n: int = 10
    restrict_to_position_group: bool = True   # False = style match across positions


class ComparePlayersRequest(BaseModel):
    season: int | None = None
    player_ids: list[str]


class ShortlistCreateRequest(BaseModel):
    name: str = Field(max_length=128)


class ShortlistEntryCreateRequest(BaseModel):
    player_id: str = Field(max_length=32)
    status: str = Field(default="Discovery", max_length=32)
    notes: str | None = Field(default=None, max_length=10000)
    rating: int | None = None


class ShortlistEntryUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=10000)
    rating: int | None = None
    owner: str | None = Field(default=None, max_length=64)           # "" clears
    due_date: str | None = Field(default=None, max_length=10)        # YYYY-MM-DD, "" clears
    next_action: str | None = Field(default=None, max_length=255)    # "" clears


class ScoutNoteCreateRequest(BaseModel):
    player_id: str = Field(max_length=32)
    note: str = Field(max_length=10000)
    author: str | None = Field(default=None, max_length=64)


class ClubProfileRequest(BaseModel):
    club_name: str = Field(max_length=128)
    formation: str = "4-3-3"
    transfer_budget_eur: float | None = None
    wage_budget_eur: float | None = None
