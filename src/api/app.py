import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers_v2 import router
from src.api.auth import require_api_key
from src.api.alias_middleware import AliasPathMiddleware
from src.api.observability import RequestLogMiddleware, configure_logging
from src.api.audit_middleware import AuditMiddleware
from src.api.hardening import (BodySizeLimitMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware, cors_origins,
                                docs_enabled, log_startup_warnings)
from src.api.auth_routes import router as auth_router
from src.auth.deps import authorize
from src.auth.security import validate_auth_config
from src.auth.service import ensure_auth_tables
from src.config.settings import API_HOST, API_PORT

configure_logging()

def _warm_transfermarkt() -> None:
    from src.features.transfermarkt_context import _bulk_records
    _bulk_records()


def _warm_search_features() -> None:
    from src.features.search_intelligence import cached_longitudinal_features
    from src.services.data_store import store
    if not store.facts.empty:
        cached_longitudinal_features(store.facts, store.current_season())


def _warm_age_curve() -> None:
    from src.features import squad_insights
    from src.services.data_store import store
    if not store.facts.empty:
        squad_insights.squad_insights(store.facts.head(0), store.facts)  # trains and caches the ageing curve


def warm_caches() -> None:
    """Pre-build the Transfermarkt lookup so the first request is fast. Never blocks startup on failure."""
    log = logging.getLogger("scoutiq")
    steps = (
        ("transfermarkt lookup", _warm_transfermarkt),
        ("search history features", _warm_search_features),
        ("squad ageing curve", _warm_age_curve),
    )
    for name, step in steps:
        try:
            step()
        except Exception:
            log.error("cache warm-up failed: %s", name, exc_info=True)


@asynccontextmanager
async def lifespan(_app):
    """Server start-up: make sure the users/audit tables exist in older databases."""
    try:
        ensure_auth_tables()
        from src.db.migrate import ensure_workflow_schema
        from src.db.session import engine as _engine
        ensure_workflow_schema(_engine)
    except Exception:
        logging.getLogger("scoutiq").error("could not ensure database schema", exc_info=True)
    await run_in_threadpool(warm_caches)
    log_startup_warnings()
    yield


app = FastAPI(
    title="ScoutIQ - Football Recruitment Intelligence API",
    description="Player scouting, role-fit, valuation, risk, similarity, and squad optimization service.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if docs_enabled() else None,
    redoc_url="/redoc" if docs_enabled() else None,
    openapi_url="/openapi.json" if docs_enabled() else None,
)

# Permissive CORS for local development against the Next.js frontend
# (tighten allow_origins for production per an environment-specific config).

# Auth is opt-in (see src/api/auth.py): a no-op until SCOUTIQ_API_KEY is
# set in the environment, so local dev and the test suite need no
# configuration. Applied to every route including /health and /ready --
# if you deploy behind an orchestrator that health-checks over plain HTTP
# with no custom headers (e.g. a default k8s liveness probe), either
# configure it to send X-API-Key or switch it to a TCP check instead.
# Order (innermost first): audit -> rate limit -> body limit -> security headers -> CORS -> request log -> alias.
# CORS sits OUTSIDE the limiters so that 413/429 responses still reach the browser as readable errors.
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-ID"],  # lets the browser read the download filename
)

# Outermost: logs every request with a request id (never query strings or secrets).
app.add_middleware(RequestLogMiddleware)

# Old (merged) player ids in URLs keep working: rewritten to the canonical id.
app.add_middleware(AliasPathMiddleware)

validate_auth_config()  # fail fast if SCOUTIQ_AUTH_MODE=on without a proper secret

# Roles/permissions are enforced by `authorize` only when SCOUTIQ_AUTH_MODE=on (default: off).
app.include_router(router, dependencies=[Depends(require_api_key), Depends(authorize)])
app.include_router(auth_router, dependencies=[Depends(require_api_key), Depends(authorize)])


if __name__ == "__main__":
    import uvicorn

    # SCOUTIQ_WORKERS=N runs N worker processes (each loads the data; rate limits are then per worker).
    import os

    uvicorn.run("src.api.app:app", host=API_HOST, port=API_PORT, reload=False, workers=max(1, int(os.getenv("SCOUTIQ_WORKERS", "1"))))
