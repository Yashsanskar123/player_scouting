import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from src.identity import aliases


@pytest.fixture()
def alias_file(tmp_path, monkeypatch):
    path = tmp_path / "aliases.csv"
    pd.DataFrame([{"alias_id": "old1", "canonical_id": "new1", "tm_player_id": 1, "reason": "x"}]).to_csv(path, index=False)
    monkeypatch.setattr(aliases, "ALIAS_PATH", path)
    aliases.reload_aliases()
    yield
    aliases.reload_aliases()


def test_apply_and_resolve(alias_file):
    df = pd.DataFrame({"player_id": ["old1", "other"], "season": [1920, 2021]})
    out = aliases.apply_aliases(df)
    assert list(out["player_id"]) == ["new1", "other"]
    assert list(df["player_id"]) == ["old1", "other"]  # input untouched
    assert aliases.resolve_player_id("old1") == "new1"
    assert aliases.resolve_player_id("zzz") == "zzz"


def test_noop_without_file(tmp_path, monkeypatch):
    monkeypatch.setattr(aliases, "ALIAS_PATH", tmp_path / "missing.csv")
    aliases.reload_aliases()
    df = pd.DataFrame({"player_id": ["a"]})
    assert aliases.apply_aliases(df).equals(df)
    aliases.reload_aliases()


def test_remap_database_moves_rows_and_is_idempotent(alias_file):
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("create table shortlist_entries (id integer primary key, shortlist_id int, player_id text)"))
        c.execute(text("create table squad_players (id integer primary key, squad_id int, player_id text)"))
        c.execute(text("create table scout_notes (id integer primary key, player_id text, note text)"))
        c.execute(text("create table player_season_facts (id integer primary key, player_id text, season int)"))
        c.execute(text("create table player_identity (player_id text primary key)"))
        c.execute(text("insert into shortlist_entries values (1,10,'old1'),(2,11,'old1'),(3,11,'new1')"))
        c.execute(text("insert into squad_players values (1,5,'old1')"))
        c.execute(text("insert into scout_notes values (1,'old1','good')"))
        c.execute(text("insert into player_season_facts values (1,'old1',1920),(2,'new1',2021)"))
        c.execute(text("insert into player_identity values ('old1'),('new1')"))
    aliases.remap_database(eng)
    aliases.remap_database(eng)  # second run changes nothing
    with eng.connect() as c:
        entries = sorted(c.execute(text("select shortlist_id, player_id from shortlist_entries")).fetchall())
        assert entries == [(10, "new1"), (11, "new1")]  # list 11 keeps one canonical row, no duplicate
        assert c.execute(text("select player_id from squad_players")).scalar() == "new1"
        assert c.execute(text("select player_id from scout_notes")).scalar() == "new1"
        assert {r[0] for r in c.execute(text("select player_id from player_season_facts"))} == {"new1"}
        assert [r[0] for r in c.execute(text("select player_id from player_identity"))] == ["new1"]


def test_path_rewrite_only_when_the_old_id_is_gone_from_the_data(alias_file, monkeypatch):
    import asyncio
    from src.api import alias_middleware as am

    seen = []

    async def downstream(scope, receive, send):
        seen.append(scope["path"])

    async def call(path):
        await am.AliasPathMiddleware(downstream)({"type": "http", "path": path}, None, None)

    monkeypatch.setattr(am, "known_player_ids", lambda: frozenset({"old1", "new1"}))  # merge not applied yet
    asyncio.run(call("/api/players/old1/history"))
    monkeypatch.setattr(am, "known_player_ids", lambda: frozenset({"new1"}))  # merge applied: old id is gone
    asyncio.run(call("/api/players/old1/history"))
    asyncio.run(call("/api/recruitment/players/old1/notes"))
    asyncio.run(call("/api/market/opportunities"))
    assert seen == ["/api/players/old1/history", "/api/players/new1/history", "/api/recruitment/players/new1/notes", "/api/market/opportunities"]


def test_ids_in_request_bodies_are_resolved_only_when_the_old_id_is_gone(alias_file, monkeypatch):
    from src.api import alias_middleware as am
    monkeypatch.setattr(am, "known_player_ids", lambda: frozenset({"old1", "new1"}))  # merge not applied: both exist
    assert am.canonical_player_id("old1") == "old1"
    monkeypatch.setattr(am, "known_player_ids", lambda: frozenset({"new1"}))  # merge applied: old id is gone
    assert am.canonical_player_id("old1") == "new1"
    assert am.canonical_player_id("new1") == "new1" and am.canonical_player_id("unrelated") == "unrelated"
