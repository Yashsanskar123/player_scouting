# ScoutIQ — Football Recruitment Intelligence Platform

This is a rebuild of the original project (kept in `src/` alongside the new
modules -- nothing pre-existing was deleted). See `docs/ARCHITECTURE.md` for
what was audited, kept, and replaced, and `docs/MODEL_CARD.md` for the
valuation model's real (and limited) scope.

## What this is

Given a squad need -- a position, a role, a budget, an age range -- this
answers: who fits, why, what they'd cost, how risky the signing is, and how
the squad would look afterward. Backed by real per-90 football data (FIFA +
FBref merged), not just FIFA attribute ratings.

## Quick start (run it on your own computer)

You need **Python 3.11+** and **Node.js 18+**. The player data is included and already loaded, so there is no
pipeline step to run first. The complete guide, with troubleshooting, is in **[RUN_LOCALLY.md](RUN_LOCALLY.md)**.

**1. Backend**: open a terminal in this folder (the one containing `src` and `requirements.txt`).

Windows (PowerShell):
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.api.app
```
macOS / Linux:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.api.app
```
The API now runs at **http://localhost:8010** (interactive docs at `/docs`). Leave this terminal open.

**2. Frontend**: open a second terminal.
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000**. (`frontend/.env.local` already points the web app at port 8010.)

**3. Optional**
```bash
python -m src.demo.seed        # fills in a demo club, shortlists, owners and deadlines
python -m pytest tests -q      # runs the test suite
```
Sign-in, PostgreSQL, Docker and security settings are covered in `docs/AUTH.md`, `docs/DEPLOY.md` and `docs/SECURITY.md`.

## What's implemented (and verified against the real dataset)

- Stable player identity resolution across seasons (not name matching)
- Canonical position taxonomy, cross-validated against two source systems
- Data dictionary + composite data quality score (93.3/100 on this dataset)
- Position/season-aware percentile engine
- 18 role archetypes with explainable, weighted role-fit scoring
- Position-specific Performance Score (component breakdown, not one formula)
- Potential/trajectory model, **backtested** (see `docs/VALIDATION.md`) --
  the original linear-trend approach was found worse than a naive
  baseline and replaced with a validated recency/historical-mean blend
- Multi-facet similarity engine (statistical / tactical / physical / market)
- Trained valuation model (HistGradientBoostingRegressor, R^2=0.98 in log
  space, MAPE 13.8% -- see the model card for what this number does and
  doesn't mean)
- Risk model, **backtested** against 17,851 real season transitions --
  validated as an outcome-volatility indicator, not a decline predictor
  (see `docs/VALIDATION.md`); reported separately from performance, never
  blended into one score
- Weight sensitivity analysis for role-fit and performance-score weights
  (see `docs/VALIDATION.md`): rank correlation stayed above 0.97 under
  +-20% weight perturbation in every case tested. Two genuine near-ties
  at the top were found (not a flaw -- correctly reflects a real
  statistical toss-up), and `/api/scouting/search` now flags these with
  `close_call_with_previous` so a razor-thin ranking isn't presented as a
  confident distinction.
- League-strength adjustment (`docs/VALIDATION.md` section 5), fit via
  least squares over 2,474 real cross-league transfers in the dataset.
  Directionally sensible but low-confidence (R^2=0.09) -- exposed as an
  `adjusted_performance_score` field, not wired into default rankings.
- Role-fit construct validation against next-season minutes
  (`docs/VALIDATION.md` section 6) -- a genuinely weak result, reported
  honestly rather than spun: this is the single most important open
  validation gap in the project.
- 152 tests (`tests/`) covering identity, taxonomy, percentiles, role fit,
  performance score, potential, risk, similarity, valuation model,
  league adjustment, squad optimizer, squad audit, comparison,
  replacement finder, the full API layer (FastAPI TestClient), and auth.
  Found and fixed 8 real bugs while writing them (see `docs/ROADMAP.md`),
  including a dependency-pinning bug only a clean-venv run surfaced:
  `PuLP>=2.8` with no upper bound resolves to a breaking PuLP 4.0 on a
  fresh install. Run with `pytest tests/ -v`.
- Real squad optimization via integer linear programming (PuLP, pinned
  `<4.0` -- see above), not sorted top-N
- Opt-in API key auth (`SCOUTIQ_API_KEY` / `X-API-Key` header) -- a floor,
  not full RBAC; see `docs/ROADMAP.md`
- CI (`.github/workflows/ci.yml`): backend tests + frontend build +
  Docker build on every push/PR
- FastAPI backend on SQLite/Postgres-ready SQLAlchemy, with an in-memory
  serving cache for sub-second responses
- Shortlist / recruitment-status workflow (API + DB; no frontend UI yet)
- **Squad audit**: given a real club's roster, finds depth/quality/
  succession gaps evaluated against its actual formation, with each
  finding carrying a ready-to-use recruitment search filter. Plus
  transfer simulation against the real squad average. Full chain
  verified live: audit -> finding -> search -> candidate -> simulated
  signing -> new squad rating.
- Next.js + TypeScript + Tailwind frontend: dashboard, player search, player
  360 profile, market opportunities, squad optimizer, squad audit,
  player comparison, replacement finder

## What's intentionally not done

This is not the full 80-section spec -- see `docs/ROADMAP.md` for what's
scoped out and why: authentication/RBAC, CI/CD, Docker production configs,
MLflow experiment tracking, the transfer simulator UI, scouting report PDF
export, and the remaining nav items from the original spec's navigation
tree. The core recruitment workflow (search -> profile -> compare -> value
-> risk -> optimize) is real and working end to end; the enterprise-hardening
layer around it is not.

## Repository layout

```
src/
  data/            cleaning + the v2 pipeline orchestrator
  identity/        player ID resolution
  taxonomy/        position taxonomy
  data_quality/    quality scoring + data dictionary generator
  features/        percentiles, roles, scoring, potential, risk,
                    similarity, valuation model
  optimization/    squad optimizer (ILP)
  db/              SQLAlchemy models, session, ingest
  services/        in-memory data store + cache
  api/             FastAPI app + v2 routers (routers.py / the old
                    src/models/scoring.py are the ORIGINAL pre-audit code,
                    kept for reference -- see docs/ARCHITECTURE.md)
frontend/          Next.js app
docs/              architecture report, model card, data dictionary, roadmap
data/              raw + cleaned + processed CSVs, mapping files
```

## Recruitment improvements — October 2026

- Contract expiry board:
  `/api/contracts/board?within_months=6`
  or `/api/contracts/board?within_months=12`
- Contract board PDF:
  `/api/contracts/board/export.pdf?within_months=12`
- Shortlist meeting pack:
  `/api/recruitment/shortlists/{id}/export.pdf`
- Market signal experiment:
  `/api/model-validation/market-signals`
- Position score diagnostics:
  `/api/model-validation/position-scores`

### Data limitations

The current archive contains season-level FIFA/FBref data and Transfermarkt
player links, valuation history and transfer history.

Do not label season-level appearances as last-10-match form. Do not treat
current Transfermarkt contract snapshots as historical contract information.

The market opportunity score is a recruitment discovery ranking, not a
validated prediction of future performance, transfer price, or undervaluation.

## Recruitment improvements — October 2026

- Contract expiry board:
  `/api/contracts/board?within_months=6`
  or `/api/contracts/board?within_months=12`
- Contract board PDF:
  `/api/contracts/board/export.pdf?within_months=12`
- Shortlist meeting pack:
  `/api/recruitment/shortlists/{id}/export.pdf`
- Market signal experiment:
  `/api/model-validation/market-signals`
- Position score diagnostics:
  `/api/model-validation/position-scores`

### Data limitations

The current archive contains season-level FIFA/FBref data and Transfermarkt
player links, valuation history and transfer history.

Do not label season-level appearances as last-10-match form. Do not treat
current Transfermarkt contract snapshots as historical contract information.

The market opportunity score is a recruitment discovery ranking, not a
validated prediction of future performance, transfer price, or undervaluation.
