"""API-layer tests. Unlike the module-level tests, these exercise the
actual FastAPI routes (request validation, serialization, HTTP status
codes) via TestClient -- the layer that was, until now, only checked by
manual `curl` calls during development.

Data setup: the analytics endpoints read from the in-memory `store`
singleton (src/services/data_store.py), which is monkeypatched here to
the small synthetic pipeline_df fixture instead of hitting the real
database -- fast and deterministic. The shortlist endpoints use a real
SQLAlchemy session via dependency injection, overridden here to a
throwaway in-memory SQLite database so shortlist tests don't touch
data/scoutiq.db.
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.app import app
from src.services import data_store
from src.services.cache import clear as clear_cache
from src.db.session import Base, get_session


@pytest.fixture(scope="module")
def api_test_df(pipeline_df) -> pd.DataFrame:
    """The synthetic pipeline fixture, with a few extra columns some API
    endpoints read directly (club_name is already present via conftest;
    fair_value/value_gap are left absent on purpose to verify those
    endpoints degrade gracefully rather than crash when the valuation
    model hasn't been run)."""
    return pipeline_df


@pytest.fixture(scope="module", autouse=True)
def patched_store(api_test_df):
    data_store.store._facts = api_test_df
    data_store.store._loaded_at = 1.0  # nonzero so .facts doesn't try to reload from the (real) DB
    clear_cache()
    yield
    data_store.store._facts = pd.DataFrame()
    data_store.store._loaded_at = None


@pytest.fixture(scope="module")
def test_db_session_override():
    # StaticPool is required for an in-memory SQLite DB used across
    # multiple requests/connections in a test -- without it, each new
    # connection gets its own FRESH empty in-memory database and every
    # table-creation gets silently lost the moment a second request opens
    # a new connection (found the hard way: 3 shortlist tests failed with
    # "no such table" on first run of this file).
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def _override():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client(test_db_session_override):
    return TestClient(app)


def _any_player_id(api_test_df: pd.DataFrame) -> str:
    return api_test_df.iloc[0]["player_id"]


# ------------------------------------------------------------- health ---

def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_endpoint_reports_rows_loaded(client, api_test_df):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["rows_loaded"] == len(api_test_df)


# ------------------------------------------------------------- players --

def test_list_players_returns_paginated_results(client):
    resp = client.get("/api/players?page_size=3")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) <= 3
    assert body["page_size"] == 3


def test_list_players_search_filters_by_name(client):
    resp = client.get("/api/players?search=steady")
    assert resp.status_code == 200
    body = resp.json()
    assert all("steady" in r["short_name"].lower() for r in body["results"])


def test_list_players_position_filter(client):
    resp = client.get("/api/players?canonical_position=ST")
    assert resp.status_code == 200
    body = resp.json()
    assert all(r["canonical_position"] == "ST" for r in body["results"])


def test_get_player_detail(client, api_test_df):
    pid = _any_player_id(api_test_df)
    resp = client.get(f"/api/players/{pid}")
    assert resp.status_code == 200
    assert resp.json()["player_id"] == pid


def test_get_player_detail_unknown_id_returns_404(client):
    resp = client.get("/api/players/does-not-exist")
    assert resp.status_code == 404


def test_player_percentiles_endpoint(client, api_test_df):
    st_id = api_test_df[api_test_df["canonical_position"] == "ST"].iloc[0]["player_id"]
    resp = client.get(f"/api/players/{st_id}/percentiles")
    assert resp.status_code == 200
    assert "percentiles" in resp.json()


def test_player_roles_endpoint_returns_applicable_roles_only(client, api_test_df):
    st_id = api_test_df[api_test_df["canonical_position"] == "ST"].iloc[0]["player_id"]
    resp = client.get(f"/api/players/{st_id}/roles")
    assert resp.status_code == 200
    roles = [r["role"] for r in resp.json()["roles"]]
    assert "Poacher" in roles
    assert "Deep-Lying Playmaker" not in roles


def test_player_similar_endpoint(client, api_test_df):
    st_id = api_test_df[api_test_df["canonical_position"] == "ST"].iloc[0]["player_id"]
    resp = client.get(f"/api/players/{st_id}/similar?top_n=3")
    assert resp.status_code == 200
    assert isinstance(resp.json()["results"], list)


def test_player_value_endpoint_degrades_gracefully_without_valuation_model(client, api_test_df):
    # fair_value_eur was never computed for this fixture (no valuation
    # model trained) -- the endpoint should return null fields, not 500.
    pid = _any_player_id(api_test_df)
    resp = client.get(f"/api/players/{pid}/value")
    assert resp.status_code == 200
    assert "note" in resp.json()


def test_player_risk_endpoint_is_json_serializable(client, api_test_df):
    pid = _any_player_id(api_test_df)
    resp = client.get(f"/api/players/{pid}/risk")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recruitment_risk_tier"] in ("LOW", "MEDIUM", "HIGH")


# ---------------------------------------------------------- scouting ----

def test_scouting_search_by_position(client):
    resp = client.post("/api/scouting/search", json={"canonical_position": "CB", "top_n": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert all(r["canonical_position"] == "CB" for r in body["results"])


def test_scouting_search_flags_close_calls(client):
    resp = client.post("/api/scouting/search", json={"canonical_position": "CB", "top_n": 10})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any("close_call_with_previous" in r for r in results)


def test_scouting_search_with_role_ranks_by_role_fit(client):
    resp = client.post("/api/scouting/search", json={"canonical_position": "ST", "role": "Poacher", "top_n": 5})
    assert resp.status_code == 200
    results = resp.json()["results"]
    scores = [r["role_fit_score"] for r in results if r.get("role_fit_score") is not None]
    assert scores == sorted(scores, reverse=True)


# ------------------------------------------------------------- compare --

def test_compare_players_endpoint(client, api_test_df):
    ids = api_test_df[api_test_df["canonical_position"] == "CB"]["player_id"].unique()[:2].tolist()
    resp = client.post("/api/players/compare", json={"player_ids": ids})
    assert resp.status_code == 200
    assert len(resp.json()["players"]) == 2


def test_compare_players_rejects_single_player(client, api_test_df):
    pid = _any_player_id(api_test_df)
    resp = client.post("/api/players/compare", json={"player_ids": [pid]})
    assert resp.status_code == 400


# ------------------------------------------------------------- squads ---

def test_squad_audit_endpoint(client):
    resp = client.post("/api/squads/audit", json={"club_name": "Test United", "formation": "4-3-3"})
    assert resp.status_code == 200
    body = resp.json()
    assert "findings" in body
    assert "squad_health" in body


def test_squad_audit_unknown_club_returns_404(client):
    resp = client.post("/api/squads/audit", json={"club_name": "Does Not Exist FC"})
    assert resp.status_code == 404


def test_squads_optimize_endpoint(client):
    resp = client.post("/api/squads/optimize", json={"formation": "4-3-3", "budget_eur": 1_000_000_000})
    assert resp.status_code == 200
    assert resp.json()["status"] in ("optimal", "infeasible")


def test_transfer_simulate_endpoint(client, api_test_df):
    incoming = api_test_df[api_test_df["canonical_position"] == "ST"].iloc[0]["player_id"]
    resp = client.post("/api/transfers/simulate", json={"club_name": "Test United", "incoming_player_id": incoming})
    assert resp.status_code == 200
    body = resp.json()
    assert "before_squad_rating" in body
    assert "after_squad_rating" in body


# ---------------------------------------------------------- shortlists --

def test_create_and_list_shortlist(client):
    create_resp = client.post("/api/recruitment/shortlists", json={"name": "Test Shortlist"})
    assert create_resp.status_code == 200
    shortlist_id = create_resp.json()["id"]

    list_resp = client.get("/api/recruitment/shortlists")
    assert list_resp.status_code == 200
    assert any(s["id"] == shortlist_id for s in list_resp.json()["results"])


def test_add_and_update_shortlist_entry(client, api_test_df):
    shortlist_id = client.post("/api/recruitment/shortlists", json={"name": "Another List"}).json()["id"]
    pid = _any_player_id(api_test_df)

    add_resp = client.post(
        f"/api/recruitment/shortlists/{shortlist_id}/entries",
        json={"player_id": pid, "status": "Discovery"},
    )
    assert add_resp.status_code == 200
    entry_id = add_resp.json()["id"]

    update_resp = client.patch(f"/api/recruitment/entries/{entry_id}", json={"status": "Shortlisted", "rating": 4})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "Shortlisted"


def test_add_entry_to_unknown_shortlist_returns_404(client, api_test_df):
    pid = _any_player_id(api_test_df)
    resp = client.post("/api/recruitment/shortlists/99999/entries", json={"player_id": pid})
    assert resp.status_code == 404


# ------------------------------------------------------------- exports ---

def test_player_report_pdf_download(client, api_test_df):
    pid = _any_player_id(api_test_df)
    resp = client.get(f"/api/players/{pid}/report.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].startswith("attachment; filename=\"scoutiq-")
    assert resp.content[:5] == b"%PDF-"


def test_player_report_unknown_player_is_404(client):
    assert client.get("/api/players/does-not-exist/report.pdf").status_code == 404


def test_shortlist_excel_export_contains_player(client, api_test_df):
    from io import BytesIO
    from openpyxl import load_workbook
    pid = _any_player_id(api_test_df)
    sl = client.post("/api/recruitment/shortlists", json={"name": "Export test"}).json()
    client.post(f"/api/recruitment/shortlists/{sl['id']}/entries", json={"player_id": pid, "status": "Tracked"})
    resp = client.get(f"/api/recruitment/shortlists/{sl['id']}/export.xlsx")
    assert resp.status_code == 200 and "spreadsheetml" in resp.headers["content-type"]
    ws = load_workbook(BytesIO(resp.content))["Players"]
    assert ws.max_row == 2 and ws["F2"].value == "Tracked"
    assert client.get("/api/recruitment/shortlists/99999/export.xlsx").status_code == 404


def test_opportunities_excel_export_is_valid(client):
    from io import BytesIO
    from openpyxl import load_workbook
    resp = client.get("/api/market/opportunities/export.xlsx?min_performance_score=0&min_value_gap_pct=-100")
    assert resp.status_code == 200
    assert load_workbook(BytesIO(resp.content)).sheetnames == ["Summary", "Opportunities"]


def test_contract_board_filters_and_sorts_expiring_players(client, api_test_df, monkeypatch):
    from src.features import transfermarkt_context

    current = api_test_df[api_test_df["season"] == api_test_df["season"].max()]
    first, second = current.iloc[:2].to_dict(orient="records")
    first_id, second_id = str(first["player_id"]), str(second["player_id"])

    def fake_contract_info(player_ids):
        records = {
            first_id: {"contract_expires": "2027-01-01", "contract_months_left": 3, "contract_status": "Expiring within 6 months", "tm_value_eur": 1_000_000, "tm_link_confidence": "High"},
            second_id: {"contract_expires": "2027-07-01", "contract_months_left": 9, "contract_status": "Expiring within 12 months", "tm_value_eur": 4_000_000, "tm_link_confidence": "Moderate"},
        }
        return {pid: records[pid] for pid in player_ids if pid in records}

    monkeypatch.setattr(transfermarkt_context, "bulk_contract_info", fake_contract_info)
    resp = client.get("/api/contracts/board", params={"within_months": 12, "max_value_eur": 2_000_000})

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["total"] == 1
    assert body["results"][0]["player_id"] == first_id
    assert body["results"][0]["contract_months_left"] == 3
    assert body["coverage"]["players_with_expiry"] == 2


def test_contract_board_pdf_download(client, api_test_df, monkeypatch):
    from src.features import transfermarkt_context

    player = api_test_df[api_test_df["season"] == api_test_df["season"].max()].iloc[0]
    player_id = str(player["player_id"])
    monkeypatch.setattr(transfermarkt_context, "bulk_contract_info", lambda player_ids: {
        player_id: {"contract_expires": "2027-01-01", "contract_months_left": 3, "contract_status": "Expiring within 6 months", "tm_value_eur": 1_000_000, "tm_link_confidence": "High"}
    } if player_id in player_ids else {})

    resp = client.get("/api/contracts/board/export.pdf?within_months=6")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_shortlist_pdf_export_contains_a_valid_pdf(client, api_test_df):
    player_id = _any_player_id(api_test_df)
    shortlist = client.post("/api/recruitment/shortlists", json={"name": "PDF pack test"}).json()
    client.post(f"/api/recruitment/shortlists/{shortlist['id']}/entries", json={"player_id": player_id, "status": "Discovery"})

    resp = client.get(f"/api/recruitment/shortlists/{shortlist['id']}/export.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_club_report_requires_a_configured_profile(client, tmp_path, monkeypatch):
    from src.features import club_profile
    monkeypatch.setattr(club_profile, "PROFILE_PATH", tmp_path / "none.json")
    assert client.get("/api/club-profile/report.pdf").status_code == 404


# ----------------------------------------------- validation + explainability

def test_model_validation_endpoints_without_a_report(client, tmp_path, monkeypatch):
    from src.validation import loader
    monkeypatch.setattr(loader, "REPORT_PATH", tmp_path / "missing.json")
    loader._cache.update(mtime=None, data=None)
    assert client.get("/api/model-validation").json()["available"] is False
    assert client.get("/api/model-validation/status").json() == {"available": False, "status": {}}


def test_market_signal_validation_endpoint_uses_loaded_facts(client):
    response = client.get("/api/model-validation/market-signals")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert {row["signal"] for row in payload["results"]} == {
        "performance_baseline",
        "performance_value_efficiency",
        "age_adjusted_performance",
    }


def test_position_score_validation_endpoint_reports_goalkeeper_and_cb(client):
    response = client.get("/api/model-validation/position-scores")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert {row["position"] for row in payload["positions"]} == {"GK", "CB"}


def test_model_validation_endpoints_with_a_report(client, tmp_path, monkeypatch):
    import json
    from src.validation import loader
    path = tmp_path / "validation_report.json"
    path.write_text(json.dumps({"meta": {}, "registry": [{"key": "role_fit", "status": "exploratory", "status_label": "Exploratory", "summary": "x"}], "sections": {}}))
    monkeypatch.setattr(loader, "REPORT_PATH", path)
    loader._cache.update(mtime=None, data=None)
    assert client.get("/api/model-validation").json()["available"] is True
    assert client.get("/api/model-validation/status").json()["status"]["role_fit"]["status"] == "exploratory"


def test_explain_endpoint(client, api_test_df):
    pid = _any_player_id(api_test_df)
    resp = client.get(f"/api/players/{pid}/explain")
    assert resp.status_code == 200
    body = resp.json()
    assert {"performance", "value", "risk", "potential", "reliability", "validation"} <= set(body)
    assert client.get("/api/players/does-not-exist/explain").status_code == 404


# ------------------------------------------------ scout workspace workflow

def _entry(client, api_test_df, name="Workflow"):
    pid = _any_player_id(api_test_df)
    sl = client.post("/api/recruitment/shortlists", json={"name": name}).json()
    entry = client.post(f"/api/recruitment/shortlists/{sl['id']}/entries", json={"player_id": pid, "status": "Monitoring"}).json()
    return sl["id"], entry["id"], pid


def test_entry_workflow_fields_and_timeline(client, api_test_df):
    from datetime import date, timedelta
    sid, eid, pid = _entry(client, api_test_df)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = client.patch(f"/api/recruitment/entries/{eid}", json={"owner": "Sam", "due_date": yesterday, "next_action": "Watch Saturday match", "status": "Scout Review", "rating": 4})
    assert r.status_code == 200 and r.json()["owner"] == "Sam" and r.json()["due_date"] == yesterday
    client.post(f"/api/recruitment/players/{pid}/notes", json={"player_id": pid, "note": "Great movement", "author": "Sam"})
    events = client.get(f"/api/recruitment/entries/{eid}/events").json()["events"]
    kinds = [e["kind"] for e in events]
    assert {"added", "status", "rating", "owner", "due", "next_action", "note"} <= set(kinds)
    assert any(e["kind"] == "status" and "Monitoring -> Scout Review" in e["detail"] for e in events)
    detail = client.get(f"/api/recruitment/shortlists/{sid}").json()
    assert detail["entries"][0]["owner"] == "Sam" and detail["workflow"]["overdue"] == 1 and detail["workflow"]["unassigned"] == 0
    # unchanged values create no new events; clearing works
    before = len(events)
    client.patch(f"/api/recruitment/entries/{eid}", json={"owner": "Sam", "status": "Scout Review"})
    assert len(client.get(f"/api/recruitment/entries/{eid}/events").json()["events"]) == before
    cleared = client.patch(f"/api/recruitment/entries/{eid}", json={"owner": "", "due_date": "", "next_action": ""}).json()
    assert cleared["owner"] is None and cleared["due_date"] is None and cleared["next_action"] is None


def test_entry_workflow_validation(client, api_test_df):
    _, eid, _ = _entry(client, api_test_df, "Validation")
    assert client.patch(f"/api/recruitment/entries/{eid}", json={"status": "Bogus"}).status_code == 400
    assert client.patch(f"/api/recruitment/entries/{eid}", json={"due_date": "31/12/2026"}).status_code == 400
    assert client.patch("/api/recruitment/entries/999999", json={"owner": "x"}).status_code == 404
    assert client.get("/api/recruitment/entries/999999/events").status_code == 404


def test_recruitment_tasks_are_ordered_filtered_and_skip_closed(client, api_test_df):
    from datetime import date, timedelta
    _, e1, _ = _entry(client, api_test_df, "T1")
    _, e2, _ = _entry(client, api_test_df, "T2")
    _, e3, _ = _entry(client, api_test_df, "T3")
    d = lambda n: (date.today() + timedelta(days=n)).isoformat()
    client.patch(f"/api/recruitment/entries/{e1}", json={"owner": "Ann", "due_date": d(5)})
    client.patch(f"/api/recruitment/entries/{e2}", json={"owner": "Bob", "due_date": d(-2), "next_action": "Call agent"})
    client.patch(f"/api/recruitment/entries/{e3}", json={"owner": "Ann", "due_date": d(-9), "status": "Rejected"})  # closed: ignored
    tasks = client.get("/api/recruitment/tasks").json()
    assert [t["entry_id"] for t in tasks["tasks"]] == [e2, e1] and tasks["overdue"] == 1
    assert [t["entry_id"] for t in client.get("/api/recruitment/tasks?owner=Ann").json()["tasks"]] == [e1]
    assert client.get("/api/recruitment/tasks?include_closed=true").json()["total"] == 3


# ------------------------------------------------ multi-club + dashboard

def test_club_switching_compare_and_dashboard_api(client, api_test_df, tmp_path, monkeypatch):
    from src.features import club_profile
    monkeypatch.setattr(club_profile, "PROFILE_PATH", tmp_path / "clubs.json")
    assert client.get("/api/dashboard/club").json() == {"configured": False}
    clubs = sorted(api_test_df["club_name"].dropna().unique())[:2]
    assert len(clubs) == 2
    for c in clubs:
        assert client.put("/api/club-profile", json={"club_name": c, "formation": "4-3-3"}).status_code == 200
    state = client.get("/api/club-profile").json()
    assert state["active"] == clubs[1] and [x["club_name"] for x in state["clubs"]] == clubs
    assert client.post(f"/api/club-profile/activate?club_name={clubs[0]}").status_code == 200
    assert client.post("/api/club-profile/activate?club_name=Nobody").status_code == 404
    dash = client.get("/api/dashboard/club").json()
    assert dash["configured"] is True and dash["profile"]["club_name"] == clubs[0] and dash["tasks"]["total"] == client.get("/api/recruitment/tasks").json()["total"]
    cmp_ = client.get("/api/clubs/compare", params={"clubs": clubs})
    assert cmp_.status_code == 200 and [x["club_name"] for x in cmp_.json()["clubs"]] == clubs
    assert client.get("/api/clubs/compare", params={"clubs": clubs[:1]}).status_code == 400
    assert client.get("/api/clubs/compare", params={"clubs": [clubs[0], "Nowhere"]}).status_code == 404
    assert client.delete(f"/api/club-profile?club_name={clubs[0]}").json()["profile"]["club_name"] == clubs[1]


def test_adding_an_unknown_player_to_a_shortlist_is_a_clean_404(client):
    sl = client.post("/api/recruitment/shortlists", json={"name": "Ghosts"}).json()
    assert client.post(f"/api/recruitment/shortlists/{sl['id']}/entries", json={"player_id": "nobody", "status": "Discovery"}).status_code == 404


# ------------------------------------------------------ data health

def test_seasons_carry_coverage_and_data_health_endpoints_work(client):
    seasons = client.get("/api/seasons").json()["seasons"]
    assert seasons and all("coverage" in s for s in seasons)
    health = client.get("/api/data-health")
    assert health.status_code == 200
    body = health.json()
    assert {"coverage", "freshness", "missingness", "drift_alerts", "anomalies", "identity"} <= set(body)
    fresh = client.get("/api/data-freshness").json()
    assert "sources" in fresh and "latest_season" in fresh


def test_squad_audit_includes_insights_and_replacement_includes_comparison(client, api_test_df):
    club = api_test_df["club_name"].dropna().iloc[0]
    audit = client.post("/api/squads/audit", json={"club_name": club, "formation": "4-3-3"})
    assert audit.status_code == 200
    ins = audit.json()["insights"]
    assert {"wage_efficiency", "position_dependency", "age_outlook"} <= set(ins)
    pid = _any_player_id(api_test_df)
    rep = client.post("/api/replacement/search", json={"outgoing_player_id": pid, "top_n": 2})
    assert rep.status_code == 200 and "contract_context" in rep.json()
    for cand in rep.json()["candidates"]:
        assert "component_comparison" in cand and "different_position_group" in cand


def test_dashboard_overview_is_cached_per_data_version_and_season(client, api_test_df):
    from src.api import routers_v2
    routers_v2._overview_cache.clear()
    s = client.get("/api/seasons").json()["seasons"][-1]["season"]
    first = client.get(f"/api/dashboard/overview?season={s}")
    assert first.status_code == 200 and len(routers_v2._overview_cache) == 1
    assert client.get(f"/api/dashboard/overview?season={s}").json() == first.json()
    assert len(routers_v2._overview_cache) == 1  # the second call was served from the cache
    key = next(iter(routers_v2._overview_cache))
    assert key[0] == routers_v2._facts_key() and key[1] == s  # tied to the data version, so a reload can never serve stale numbers
