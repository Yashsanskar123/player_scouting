# Model Card: Valuation Model

## Purpose

Predict a player's `fair_value_eur` from performance, physical, and
contextual features, and surface the gap against their current listed
value_eur as a market-opportunity signal.

## Important: what the target variable actually is

`value_eur` in this dataset is **FIFA's in-game valuation**, assigned by EA
using (undisclosed, but known to be largely) overall rating, potential,
age, and reputation. It is **not observed real-world transfer fees**.

This matters directly for interpreting the model's results:

- The very high R^2 (0.98, in log space) is expected and should not be
  read as "we've solved football valuation" -- it largely reflects the
  model successfully reverse-engineering EA's rating-based formula, which
  is a much easier problem than predicting real transfer prices.
- Feature importance is dominated by `overall` and `potential` for the
  same reason.
- Treat `fair_value_eur` and the "market opportunity" outputs derived from
  it as **a value-vs-FIFA-rating discrepancy signal**, not a real
  transfer-market appraisal. A genuine market-value model would need
  actual transfer fee data (not present in this dataset) as the target.

This is stated plainly rather than omitted because presenting model
predictions as unqualified facts is exactly what the project's own
modeling principles rule out.

## Training data

- Source: `data/cleaned/fifa_fbref_merged_processed_v2.csv`, all seasons
  (17/18-24/25), rows with `value_eur > 0` (28k+ rows before this filter).
- Split: grouped by `player_id` (GroupShuffleSplit, 80/20, random_state=42)
  -- NOT a plain random row split. 85% of rows in this dataset belong to a
  player with multiple seasons, and a season-to-season player's stats are
  highly autocorrelated, so a random split would let the same player leak
  across train/test and inflate accuracy metrics without the model
  actually generalizing to a player it hasn't seen. This was caught and
  fixed after the first version of this model card was written; re-running
  with the corrected split changed the metrics only marginally (MAE moved
  from ~€1.23M to ~€1.30M, R^2 unchanged at 0.983) -- which is itself an
  informative result: it confirms the target-circularity issue below, not
  train/test leakage, is what's driving the high accuracy.

## Features

Age, FIFA attribute ratings (overall/potential/pace/shooting/passing/
dribbling/defending/physic/international_reputation/skill_moves/
weak_foot), performance score and its components, sample reliability
score, positional versatility score, canonical position, league.

**Excluded deliberately** (leakage guard): `wage_eur` (typically set with
knowledge of market value) and anything derived from `value_eur` itself.

## Algorithm

`sklearn.ensemble.HistGradientBoostingRegressor`, trained on
`log1p(value_eur)` (transfer/rating values are heavily right-skewed).
300 iterations, max_depth=6, learning_rate=0.08.

## Evaluation (holdout test set, n=5,688)

| Metric | Value |
|---|---|
| MAE | ~€1.23M |
| RMSE | ~€3.35M |
| R^2 (log space) | 0.983 |
| MAPE | 13.8% |

## Known limitations

- Target is FIFA's in-game rating-based valuation, not real transfer fees
  (see above -- this is the main limitation).
- No transfer-history, contract-length, or release-clause data exists in
  this dataset to model real deal dynamics.
- Feature importance and predictions will look artificially strong because
  of target-feature circularity (overall/potential heavily determine
  value_eur by EA's own design).
- Category encoding (`canonical_position`, `league_name`) is fit once on
  the full dataset at training time and reused at inference -- a category
  unseen at training time (a new league added later) will be encoded as
  missing, not crash, but its contribution won't be learned.

## Expected usage

Use `value_gap_pct` as a relative signal for further human investigation
("why is this player rated lower than their attributes/performance would
suggest"), not as a transfer-fee recommendation.
