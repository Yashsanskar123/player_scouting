# ScoutIQ: product brief

**ScoutIQ is a recruitment-intelligence platform for football clubs.** It turns 8 seasons of player data across 10 leagues
(28,000+ player-seasons, 9,700 players) into a workflow a recruitment team can run: find players, understand them, compare
them with what the club already has, track them, and decide, while being honest about how far each number can be trusted.

## Who it is for
Heads of recruitment and sporting directors (what does my squad need, and who is affordable?), analysts (find, compare and
explain players), scouts (own a shortlist, deadlines and notes), and administrators (users, audit, data health).

## What it does
| Area | Capability |
|---|---|
| Club first | Choose your club once; the Dashboard shows squad needs, contracts ending within 12 months, overdue scouting tasks, watchlist movers and affordable targets for each need. Several clubs can be saved and compared with rivals. |
| Find and understand | Filterable player search; player profiles with a performance profile, peer percentiles, history, contract and market-value context, and a "why these numbers" breakdown that adds back to every score. |
| Compare and replace | Side-by-side comparison; a replacement finder that says in which skills each candidate is similar, better or weaker, with wage and contract context; market opportunities with reliability and contract filters. |
| Squad | Squad audit (depth, starters versus backups, minutes dependency, wage versus performance, age profile, contract outlook) and a budget-constrained lineup optimizer. |
| Run the process | Shortlists with owners, due dates, next actions, a change timeline and scout notes; Excel and PDF exports; an audit trail of who did what. |
| Trust | A **Model validation** page tests every model output against what happened next; a **Data health** page shows coverage, freshness and drift; partial seasons are labelled everywhere. |

## What makes it different
1. **It shows its evidence.** Each model output carries a status (validated, partially validated, exploratory, not validated)
   derived from backtests, with the numbers one click away. Weak spots are stated, not hidden.
2. **Every score can be explained** to the digit, and the explanations are checked against the stored numbers on every row.
3. **It is built to be run by a team:** sign-in with four roles, an audit trail, rate limiting, security headers, PostgreSQL
   with migrations, CI, and a health-checked container.

## How far to trust it (measured)
| Output | Status |
|---|---|
| League-adjusted performance; expected performance next season | Validated (agreement with market value 0.28 -> 0.42 after league adjustment; 8.5% less error than "no change") |
| Performance score, 24-month projection, breakout/decline probability, risk tier | Partially validated (useful for ranking; not literal probabilities; risk tier measures uncertainty, not decline) |
| Development potential, role fit | Exploratory (an upside ceiling, not a forecast; weak link to future minutes) |
| "Undervalued" / fair value | **Not validated** as a price signal; treat opportunity lists as a screening aid |

## Technology
FastAPI + pandas/scikit-learn backend, Next.js + TypeScript frontend, SQLite for local use or PostgreSQL for shared use,
Alembic migrations, Docker Compose, GitHub Actions CI. About 300 automated tests.

## Where it is today
A strong proof of concept: complete workflow, honest validation, production-style engineering. It is built on public-style
data (FIFA ratings, FBref season statistics, Transfermarkt snapshot). The largest gaps are data, not software: no event or
tracking data, no injury history, and the latest season is missing three leagues. See `KNOWN_LIMITATIONS.md`.
