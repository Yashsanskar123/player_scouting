# Roadmap / Scope Notes

This session rebuilt the data-science core and shipped a working API +
frontend for the primary recruitment workflow. The original master prompt
specs an 80-section enterprise platform; this document is the honest
accounting of what's in this delivery vs. what's next.

## Delivered this session

Phase 0 (audit), Phase 1 (data foundation), Phase 2 (player intelligence:
roles, percentiles, similarity, scoring, potential), most of Phase 3
(recruitment: scouting search, role fit, shortlists -- API only), most of
Phase 4 (market: valuation model, opportunities), part of Phase 5/6 (squad
optimizer via real ILP), and a working slice of Phase 7 (Next.js frontend:
dashboard, search, player profile, market opportunities, squad optimizer).

## Explicitly not done, and why

- **League-strength adjustment -- now built.**
  `src/features/league_adjustment.py`: data-driven, fit via least squares
  over 2,474 real cross-league transfers in the dataset. Directionally
  sensible (Premier League/La Liga rank toughest) but R^2=0.09 -- honestly
  documented as a low-confidence directional signal, not wired into any
  default ranking (see `docs/VALIDATION.md` section 5).
- **Role-fit archetype construct validation -- now done, result is
  weak.** Tested whether role_fit predicts next-season minutes beyond
  what performance_score already explains (partial correlation,
  controlling for performance). Result: mostly weak-to-negligible
  (0.00-0.09) except "Poacher" (the most concretely-defined role). This
  is reported honestly as the single most important open validation gap,
  not spun positively -- see `docs/VALIDATION.md` section 6.
- **Auth -- minimal version now built, RBAC still not.**
  `src/api/auth.py`: a single shared API key via the `X-API-Key` header,
  read from `SCOUTIQ_API_KEY`. Deliberately opt-in -- unset by default so
  local dev and the test suite need zero configuration; set it before
  deploying anywhere reachable outside localhost. This is NOT the spec's
  role-based access control (Admin/Sporting Director/Analyst/Scout/
  Viewer) -- that needs real user identity and a permissions model, which
  is real, unattempted work. Verified against a live running server (not
  just TestClient): no key configured -> 200, key configured + no header
  -> 401, key configured + wrong header -> 401, key configured + correct
  header -> 200.
- **CI -- now built.** `.github/workflows/ci.yml`: runs the backend test
  suite, a frontend production build, and a Docker image build on every
  push/PR. Finding this genuinely useful to build: verifying
  `requirements.txt` in a clean venv (not the dev sandbox's
  already-populated Python environment) surfaced a REAL reproducibility
  bug -- `PuLP>=2.8` with no upper bound resolves to PuLP 4.0 in a fresh
  install, which renamed/removed the `cat` keyword argument on
  `LpVariable` and broke the squad optimizer entirely (`TypeError:
  LpVariable.__init__() got an unexpected keyword argument 'cat'`). Fixed
  by pinning `PuLP>=2.8,<4.0`; re-verified 152/152 tests passing from a
  completely fresh virtual environment afterward. This is exactly the
  kind of bug a CI pipeline exists to catch before it reaches anyone
  else's machine.
- **Docker**: `Dockerfile` + `docker-compose.yml` exist and run the API
  correctly (verified: `python -m src.api.app` inside the container
  works; the original project's `python src/api/app.py` did not, and has
  been fixed), but it's a single dev-oriented container -- no reverse
  proxy, no separate frontend container, no Postgres service wired in,
  and it does not run the data pipeline/ingest automatically (run those
  locally first and mount `./data`). CI now builds the image on every
  push/PR (catches Dockerfile breakage) but does not deploy it anywhere.
- **MLflow / experiment tracking (section 54)**: the valuation model is
  trained fresh on each pipeline run with no run history or comparison.
- **Transfer simulator, scouting report PDF export, scout notes UI**: the
  API/DB layer supports scout notes and shortlists; there's no frontend
  for them yet.
- **League-strength adjustment (section 29)**: percentiles are peer-group
  aware (position + season) but not cross-league-strength corrected.
- **Squad audit -- now built.** `src/features/squad_audit.py` +
  `/api/squads/audit` + `/api/transfers/simulate` + the Squad Audit
  frontend page. Given a real club's roster, it finds depth/quality/
  succession gaps evaluated against the formation the club actually
  plays (not a universal checklist -- see docs/ARCHITECTURE.md for the
  two real bugs found and fixed while building this: a false-CRITICAL
  for formations without wingbacks, and FIFA's data tagging real-world
  wingbacks as plain LB/RB with no secondary position). Each finding
  carries a ready-to-use recruitment search filter. Tactical pitch
  visualization (the spec's literal drag-and-drop pitch UI) is still not
  built -- the depth chart is a table, not a pitch graphic.
- **Player Comparison and Replacement Finder -- now built.**
  `src/features/comparison.py`, `src/features/replacement_finder.py`,
  `/api/players/compare`, `/api/replacement/search`, plus Compare and
  Replacement Finder frontend pages linked from the player profile. The
  replacement finder is built on top of the existing similarity engine
  (not a separate model) with budget/age constraints, plain-language
  advantages per candidate, and an explicit "best value alternative"
  flag. A real serialization bug (numpy scalars breaking JSON encoding)
  was found in both new endpoints during testing and fixed via a shared
  `src/utils.py` helper -- the same bug had already bitten two other
  endpoints earlier in the project, so it's now centralized instead of
  copy-pasted a fourth time.
- **Player trajectory charts, radar charts in the UI**: the API exposes
  percentiles and role-fit breakdowns; the frontend renders them as bars,
  not the spec's radar chart visualization.
- **Tests -- now substantially built.** 99 tests across 11 files
  (`tests/test_identity.py`, `test_taxonomy.py`, `test_percentiles.py`,
  `test_role_archetypes.py`, `test_performance_score.py`,
  `test_potential.py`, `test_risk.py`, `test_squad_optimizer.py`,
  `test_squad_audit.py`, `test_comparison.py`,
  `test_replacement_finder.py`, `test_utils.py`), run against a small
  deterministic synthetic dataset (`tests/conftest.py`) pushed through
  the real pipeline stages, not hand-mocked inputs. Found and fixed 3 new
  real bugs while writing them: `compute_risk` crashed if called without
  `sample_reliability_score` already present; `_component_score` and two
  separate copies of a renormalization step (`performance_score.py` AND
  `role_archetypes.py`) used `pd.NA` instead of float `NaN`, which forces
  object dtype and crashes `.round()` the moment a row has zero available
  weighted features -- unreachable with the full real dataset (always has
  every column) but a real crash risk for any partial input. NOT covered:
  the API layer itself (`routers_v2.py`), `similarity_v2.py`,
  `valuation_model.py`, `league_adjustment.py`, and the `data_quality`/
  `data_dictionary` modules have no dedicated test file yet -- validated
  so far only by the manual live-API testing and backtest scripts
  documented throughout this session and in `docs/VALIDATION.md`.

## Suggested next priorities

1. Follow up on the role-fit construct-validity gap: the weak result
   (section 6, VALIDATION.md) is the most important open question in the
   project -- worth either redesigning the archetype weights or sourcing
   real deployment/success data to test against.
2. Real RBAC (Admin/Sporting Director/Analyst/Scout/Viewer per spec
   section 56) -- the shared API key is a floor, not this.
3. A production Docker Compose (reverse proxy, separate frontend
   container, Postgres service, automatic pipeline/ingest on startup)
   -- what exists today is dev-oriented.
4. Coverage for `data_quality.py`/`data_dictionary.py` and the
   validation/backtest scripts themselves (`src/validation/`) -- the last
   modules with no dedicated test file.
