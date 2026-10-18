# Validation Report

Everything in this document was produced by backtesting against this
dataset's OWN multi-season history -- no new data was needed. Code lives
in `src/validation/`. This is the honest accounting of what's actually
been checked against real outcomes vs. what's still just a formula that
looks reasonable on paper.

## 1. Potential/trajectory model

**Original approach (now replaced):** fit a linear trend on each player's
`performance_score` history and extrapolate it forward.

**Backtest method:** walk-forward holdout. For every player with >=3
observed seasons, hide the most recent season, fit/compute a prediction
using only the earlier seasons, and compare to the actual (known) held-out
value. Compared against two naive baselines on the same data.

**Result (n=4,328 held-out player-seasons):**

| Model | MAE | Correlation with actual |
|---|---|---|
| Linear trend extrapolation (original) | 13.88 | 0.389 |
| Naive: assume no change from last season | 9.89 | 0.506 |
| Naive: player's own historical mean | 9.50 | 0.508 |
| **Recency/mean blend (0.4 * last + 0.6 * mean) -- shipped** | **9.13** | best of all tested |

**Conclusion:** the original trend model was worse than doing nothing.
Per-player histories here (3-8 seasons) are too short and noisy for slope
extrapolation to add signal over just looking at recent form. Grid search
over blend weights and an EWMA alternative found 0.4/0.6 recency/mean as
the best simple estimator. **This is what's shipped now** in
`src/features/potential.py`. It is a regression-to-the-mean estimator --
it will NOT detect a genuine breakout before it shows up in the stats.
That's a real, stated limitation, not a solved problem.

`development_potential` (as opposed to `expected_performance_12m`) has
**not** been separately backtested -- it still uses an age-curve + FIFA
potential-gap formula. Flagged as unvalidated in the model's docstring.

## 2. Risk model

**Backtest method:** for every real season-to-season transition in the
data (17,851 of them), grouped by the `recruitment_risk_tier` assigned at
the start of the transition, compare the actual next-season outcome.

**Result:**

| Risk tier (at season t) | n | Mean performance delta | Std dev of delta | % declined |
|---|---|---|---|---|
| LOW | 14,402 | -0.44 | 12.6 | 51.7% |
| MEDIUM | 2,861 | -0.38 | 17.2 | 50.3% |
| HIGH | 588 | **+0.76** | **22.9** | 49.3% |

**Conclusion:** the risk tier does **not** predict decline -- HIGH-tier
players' average next-season outcome was not worse than LOW-tier's (if
anything, marginally better), and the "% declined" rate is essentially
flat across tiers (~50% for all three). What it DOES predict, clearly and
monotonically, is **volatility**: HIGH-tier outcome std (22.9) is nearly
double LOW-tier's (12.6). This is structurally explained by the
`age_risk` component, which flags both very young players (real upside
variance) and ageing players (real decline variance) as "risky" --
the two cancel out in the mean but compound in the spread.

**What changed as a result:** the risk score's documentation (docstring
in `src/features/risk.py`, and the `/api/players/{id}/risk` endpoint's
response) was rewritten to describe it honestly as an **outcome
volatility indicator**, not an "underperformance predictor." No component
weights were changed -- the fix here was correcting what we claim the
score means, not the arithmetic, since the arithmetic already produces a
real, validated (variance) signal, just not the one the original
docstring implied.

## 3. Valuation model train/test methodology

**Found:** the original evaluation used a random row-level train/test
split. 85% of rows in this dataset belong to a player with multiple
seasons, so the same player's near-identical stats could appear in both
train and test, inflating reported accuracy without the model actually
generalizing to an unseen player.

**Fixed:** switched to `GroupShuffleSplit` grouped by `player_id`.

**Result:** MAE moved from ~1.23M to ~1.30M EUR; R^2 unchanged at 0.983.
The metric barely moved -- which is itself informative: it confirms the
model's high accuracy is driven by target circularity (see
`docs/MODEL_CARD.md`: `value_eur` is FIFA's own rating-derived valuation,
and `overall`/`potential` alone account for ~90%+ of feature importance),
not by the leakage that was fixed. The leakage fix was correct to make on
methodological grounds regardless of its small effect size here.

## Not yet validated (real gaps, in priority order)

1. **Role-fit archetype weights** -- no backtest exists checking whether
   players scored highly for a role actually succeed when deployed in it.
   The sanity checks so far (Messi/Haaland top "Poacher") are a weak
   standard -- they'd pass almost any reasonable formula.
2. **Performance score component weights** -- position-specific weights
   are my own judgment call, not calibrated against any external
   benchmark (e.g. actual awards voting, transfermarkt ratings, or a
   held-out performance measure).
3. **League-strength adjustment** -- not implemented at all yet (see
   ROADMAP.md); percentiles are position+season aware but not corrected
   for cross-league quality.
4. **Weight sensitivity** -- no test yet of whether role-fit/performance
   rankings are stable under small perturbations of the declared weights.

## 4. Weight sensitivity analysis

**Method** (`src/validation/sensitivity.py`): for 50 trials, perturb each
declared weight (role-fit component weights, performance-score component
weights) by a random factor in [0.8, 1.2], renormalize so the total stays
the same (changes relative emphasis, not overall scale), recompute the
ranking, and compare to the original via Spearman rank correlation,
top-10 overlap, and whether the #1-ranked player changes.

**Result:** the scoring system is, overall, genuinely robust. Rank
correlation stayed above 0.97 in every role/position tested (Poacher,
Deep-Lying Playmaker, Ball-Winning 6, Progressive Centre Back; ST, CB,
CM, CDM, GK performance scores), several above 0.99. This means the
declared weights being "off" by a plausible margin does not meaningfully
scramble the overall ranking.

**Where it's NOT robust -- genuine near-ties at the top, not a scoring
flaw:** two cases showed only 70% top-1 stability (CB performance score,
Ball-Winning 6 role fit). Investigated why: in both cases the #1 and #2
ranked players were separated by a tiny margin to begin with (CB: 74.0 vs
73.3; Ball-Winning 6: 91.8 vs 91.6). A ±20% weight wobble easily flips an
ordering that close -- which is the correct behavior, not a bug. Measured
the actual score movement a single player experiences under this
perturbation: median 0.6, mean 0.78, 90th percentile 1.7 points.

**What changed as a result:** `/api/scouting/search` now flags
`close_call_with_previous: true` on any candidate within 2.0 points of
the one ranked above them (the threshold set from the measured 90th-
percentile movement above). This doesn't change any ranking or score --
it tells the user when the ordering between adjacent candidates isn't
something the weights can actually distinguish reliably, so a "#1 vs #2"
decision that close should be made on scout judgment, not the ranking
order.

## Full list of what's been backtested/validated so far

| Component | Status |
|---|---|
| Potential/trajectory model | Backtested (walk-forward), original approach replaced |
| Risk model | Backtested (17,851 transitions), reframed as volatility not decline |
| Valuation model methodology | Group-split leakage found and fixed |
| Role-fit and performance-score weights | Sensitivity-tested, generally robust, near-ties flagged |
| Role-fit archetype DEFINITIONS (are these the right features/roles at all) | Not validated -- still just plausibility-checked against famous players |
| Similarity engine | Not independently validated (position-restriction bug was found and fixed, but no outcome-based check exists) |
| Squad audit findings | Not validated against real recruitment outcomes (no ground truth available in this dataset) |
| League-strength adjustment | Not implemented at all |

## 5. League-strength adjustment (previously fully unimplemented)

**Method** (`src/features/league_adjustment.py`): data-driven, using the
2,474 real cross-league transfers already present in this dataset (same
`player_id`, different `league_name` between consecutive seasons). This
is a paired-comparison problem (same structure as Bradley-Terry/Elo):
solve via least squares for one latent "strength" value per league that
best explains the observed performance_score deltas, anchored to the
most-observed league.

**Result:**

```
+6.18  Major League Soccer
+6.06  Jupiler Pro League
+5.05  Eredivisie
+4.72  Super Lig
+1.49  Liga Portugal
+1.25  Bundesliga
 0.00  Ligue 1 (anchor)
-1.37  Serie A
-3.87  Premier League
-3.89  La Liga
```

**The ranking is directionally sensible** -- Premier League and La Liga
come out as the toughest leagues to produce raw stats in (largest
discount), MLS/Jupiler Pro League/Eredivisie as the most stat-inflating,
roughly matching conventional football judgment about relative league
strength.

**But R^2 = 0.09.** The league-pair effect explains only 9% of the
variance in individual performance deltas -- the other 91% is
player-level noise (age, role change, injury, team quality, etc.). This
empirically confirms the confound flagged in the module's own docstring:
transfers are not random (players who move to bigger leagues are
disproportionately already-improving players; the model can't separate
"this league is genuinely tougher" from "the kind of player who moves
here is different"). The directional ranking is plausible; the precise
magnitude per league should not be trusted as more than a rough,
directional signal.

**What shipped:** `adjusted_performance_score` and
`league_strength_adjustment` are now computed in the pipeline and exposed
on `/api/players/{id}`. Not yet wired into role-fit, scouting search
default sort, or the squad optimizer -- those still use unadjusted
`performance_score`, so this is available as a queryable field but not
yet the default ranking basis anywhere. Given the low R^2, that's a
deliberate choice: forcing a low-confidence per-league discount into
every ranking by default would overstate how much we actually know.

## 6. Role-fit archetype construct validity

**The standard used so far was weak.** "Messi/Haaland top Poacher" would
pass almost any reasonable scoring formula, since those players are
elite on nearly every metric simultaneously -- it doesn't distinguish a
well-constructed archetype from an arbitrary one.

**Real test** (`src/validation/backtest_role_fit.py`): does a player's
role_fit_score for their position's archetype predict something outside
itself -- specifically, next-season playing time, a genuine real-world
signal (a coach's revealed judgment), not something we computed.
Reported as a PARTIAL correlation controlling for performance_score,
since a raw correlation would mostly just re-detect "better players play
more," which performance_score already explains on its own.

**Result (n=17,851 player-season pairs with a following season):**

| Role | Raw corr (role fit -> future minutes) | Partial corr (controlling for performance) |
|---|---|---|
| Poacher | 0.109 | 0.088 |
| Deep-Lying Playmaker | 0.087 | 0.053 |
| Progressive Centre Back | 0.082 | 0.039 |
| Inside Forward | 0.060 | 0.026 |
| Ball-Winning 6 | 0.029 | 0.006 |
| Creative 10 | 0.039 | -0.006 |

**This is a weak result, and it's reported as one.** Once raw performance
is controlled for, role fit adds little to no incremental predictive
power over next-season minutes for most archetypes tested. "Poacher" --
arguably the single most concretely-defined role in the set (score goals,
little else) -- shows the strongest signal; more abstractly-defined roles
("Creative 10," "Ball-Winning 6") show essentially none.

**Two honest interpretations, and this analysis can't distinguish
between them:**
1. The archetype weight definitions genuinely aren't capturing something
   real about deployment value beyond raw output -- i.e. the "why" behind
   a role-fit score isn't adding information a recruiter doesn't already
   have from the performance score alone.
2. Next-season minutes are driven by squad-context factors this test
   doesn't control for (does THIS specific club need THIS profile, squad
   competition at the position, manager change, injuries) -- a generic
   archetype fit predicting minutes at an unknown, unmodeled club is a
   genuinely hard prediction problem regardless of whether the archetype
   definition itself is sound.

**What this means practically:** role-fit scores and their strengths/
limitations explanations should still be read as "does this player's
statistical profile match this archetype's definition" -- that part is
just arithmetic and is correct by construction. They should NOT currently
be read as "this predicts whether the player will succeed if deployed in
this role," which is what a recruiter actually wants and what has not
been shown here. This is the single most important open validation gap
in the project.


## 5. Automated validation report (added with the validation/explainability work)

`python -m src.validation.report` re-runs every backtest below on the current data and writes
`data/validation/validation_report.json` (about 2 minutes). The app reads that file: the
**Model validation** page shows the evidence, and status badges appear next to each model output.
Each status comes from an explicit, documented rule (see `RULES` in `src/validation/report.py`), so the labels
cannot drift from the measured numbers. Latest run: 28,436 player-seasons, 9,701 players, 8 seasons,
Transfermarkt snapshot as an independent market benchmark.

| Output | Status | Evidence |
|---|---|---|
| Performance score | Partially validated | Year-over-year rank stability 0.556 (players with 900+ minutes in both seasons) |
| League-adjusted performance | Validated | Agreement with market value: 0.276 raw -> 0.418 league-adjusted |
| Expected performance (12 months) | Validated | Error 9.1 points vs 9.95 for 'no change' (8.5% better), n=4446 |
| Projection (24 months) | Partially validated | Walk-forward correlation 0.533, error 8.99 points (n=3081) |
| Development potential | Exploratory | Overstates next-season performance by 14.72 points on average; error 16.0 vs 10.19 for 'no change' |
| Breakout probability | Partially validated | Out-of-time AUC 0.631 (0.5 = no skill); the top 20% of predictions are 1.48x the base rate |
| Decline probability | Partially validated | Out-of-time AUC 0.616 (0.5 = no skill); the top 20% of predictions are 1.46x the base rate |
| Recruitment risk tier | Partially validated | Share of players who declined next season is flat across tiers: LOW 51.6%, MEDIUM 49.98%, HIGH 49.35% |
| Fair value and 'undervalued' signal | Not validated | Forward test (n=25390): rank correlation between value gap and the next 12 months' market-value change = 0.013; positive in 3/8 seasons |
| Role fit | Exploratory | Mean partial correlation with next-season minutes (controlling for performance): 0.052 across 17 roles |

### What the new tests found

* **Expected performance (12 months)** holds up out of time: error 9.1 vs 9.95 for "assume no change" (8.5% better, n=4446).
* **Development potential is an upside ceiling, not a forecast.** It overstates next-season performance by 14.72 points on average (error 16.0 vs 10.19 for "no change"). The UI labels it exploratory.
* **Breakout / decline probabilities** are historical cohort rates. Tested out of time (rates learned only from earlier seasons), AUC is 0.631 (breakout) and 0.616 (decline); the top 20% of predictions are about 1.48x the base rate, but predicted and observed rates differ by up to 7.2 points. Useful for ranking, not as literal percentages.
* **Performance score vs market value** (Spearman within season and position): 0.276 raw, **0.418 league-adjusted** (FIFA overall, for reference: 0.827). The league adjustment is therefore validated, and the adjusted score should be preferred when comparing across leagues. Goalkeeper scores are unstable year to year (rank correlation 0.146) and centre-back scores agree weakly with market value.
* **Fair value / "undervalued" is not validated as a price signal.** Fair value tracks FIFA's own valuation (rank agreement 0.896 vs 0.893 for FIFA value alone) and sits 1.41x above Transfermarkt on the median. In a forward test (n=25,390) the value gap had rank correlation 0.013 with the next 12 months' Transfermarkt value change, positive in 3/8 seasons. Opportunity lists should be read as a screening aid.
* **Role fit** has a weak link to next-season minutes once performance is controlled for (mean partial correlation 0.052); rated exploratory.

### Corrections to earlier validation code

* `src/validation/sensitivity.py` compared the baseline and perturbed rankings by joining on `player_id` alone. Players have several seasons, so this was a many-to-many join that diluted the correlation (strikers showed 0.55). Fixed to join on `(player_id, season)`. The corrected figures confirm the original claim: worst-case rank correlation is **0.963** across positions and roles. A regression test guards it.
* The role-fit check tested every role against every player. It now tests each role on players whose natural position fits it (`NATURAL_POSITIONS` in `report.py`).

### Explainability

`GET /api/players/{id}/explain` returns the breakdown shown in the profile's "Why these numbers" panel: component contributions to the performance score (they add back to it), the league adjustment, the risk components, the development-potential parts, and comparable players for the valuation. `reconciles` is true only when the parts add up to the stored number; a test confirms this for every breakdown on the real dataset.

### Squad ageing projection (Squad Audit)

Players improve until about 22 and decline steadily after 28 on average, and the audit's age profile (how old the squad will be,
and how many players will be 30 or over) is plain arithmetic. But a projection of each player's *performance* from an average
ageing curve did **not** beat assuming no change when tested out of time (curve learned only from earlier seasons: error 8.52 points
against 8.50, n = 8,642). The Squad Audit therefore leads with the age profile and shows the performance projection as indicative only,
with this evidence next to it. The Model validation page lists it as exploratory.
