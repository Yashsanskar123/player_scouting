# Data health

The **Data health** page (and `GET /api/data-health`) reports what the platform's data covers and how fresh it is.
It only measures; it never changes or removes data. Every threshold is a named constant in `src/features/data_health.py`.

## What it checks
| Check | Rule |
|---|---|
| Partial season | A league that appears in at least half of all seasons is missing, **or** the season has under 80% of the previous season's players. The season selector then shows "partial data" and every page shows a dismissible banner naming what is missing. |
| Limited advanced statistics | Under 70% of players have xG-type statistics (the banner says so). |
| Drift: missing data | A key column is missing for 10+ percentage points more players than in other seasons. |
| Drift: shifted average | A season's average is 2+ standard deviations from the other seasons **and** at least 10% away in absolute terms (so tiny wobbles do not alert). |
| Freshness | Dates come from the data files themselves; a source is "stale" after 180 days (the FIFA/FBref file is exempt, because its source cannot be refreshed). |
| Identity | Duplicate IDs merged, groups left for review, Transfermarkt link rate, and a warning when every row has the same identity-confidence level. |
| Rows worth a second look | Counts of floored/capped scores, extreme value gaps, age outliers, tiny samples. |

## Current findings (latest run)
* **2024/25 is a partial season.** Three of the ten usual leagues are absent (Jupiler Pro League, Liga Portugal, Super Lig), so it has 2,808 players against 4,258 in 2023/24. Do not compare its counts, averages or rankings with full seasons, and do not use it to judge Belgian, Portuguese or Turkish players.
* **2017/18 has advanced statistics for only 54% of players** (about 90% in other seasons).
* **Median market value in 2024/25 is about 48% higher** than in other seasons, consistent with only the better-covered leagues being present.
* The processed data's identity-confidence column holds a single value, so it cannot distinguish strong from weak player matches.

## Fixing partial seasons
Add the missing leagues' FIFA and FBref rows for 2024/25 to the source data and re-run the pipeline. The page and banners
update automatically, because they are computed from the data.
