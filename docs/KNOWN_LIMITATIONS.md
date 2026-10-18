# Known limitations

Collected in one place so nobody is surprised. Each item is either measured (see `VALIDATION.md`, `DATA_HEALTH.md`) or a
deliberate scope boundary.

## Data
* **2024/25 is a partial season** (missing the Jupiler Pro League, Liga Portugal and Super Lig; 2,808 players against 4,258 the season before). Do not compare its counts, averages or rankings with full seasons, or use it for those leagues.
* **Advanced statistics cannot be refreshed.** FBref stopped publishing them in January 2026. 2017/18 has them for only 54% of players.
* **Basis is FIFA ratings plus season totals.** There is no event data (pressures, carries, shot locations), no tracking data, no injury history and no video, so playing style and physical load cannot be assessed.
* **Contracts, values and transfers are a single Transfermarkt snapshot** (current contract, not historical), shown for the latest season only. About 10% of players have no Transfermarkt link.
* **Player identity.** 729 duplicate IDs were merged on strong evidence; 59 possible duplicates were left alone for human review. The stored identity-confidence field is uniform and carries no information.

## Models (statuses are on the Model validation page)
* **"Undervalued" and fair value are not validated** as price predictors; fair value tracks FIFA's own valuation and sits above Transfermarkt levels.
* **Development potential and role fit are exploratory.** Breakout and decline probabilities are modest rankers, not calibrated probabilities. The risk tier measures uncertainty, not decline.
* **Goalkeeper scores are unstable** year to year; centre-back scores agree weakly with market value.
* **Ageing projections do not beat "no change"** at the level of individual players (tested out of time); the audit shows the age profile and labels the performance projection indicative only.
* The performance score's weights are expert-set, not fitted; it is a transparent structured opinion.

## Platform
* **Rate limiting and sign-in lock-out are per server process**; add a gateway limit when running several instances.
* **Tokens are stored in the browser and cannot be revoked before they expire** (disabling a user stops them immediately). No single sign-on (SAML/OIDC), no encryption at rest in the application.
* **Shortlist owners are free text**, not linked to user accounts; there are no reminders or notifications.
* **Moving from SQLite to PostgreSQL** does not copy existing shortlists automatically (see `DEPLOY.md`).
* **The Docker image was not built in the environment where it was authored**; CI builds it, and the first `docker compose up` is the real acceptance test.
* The frontend has been type-checked and production-built but has no automated browser tests yet.

## Not yet built (planned)
Saved searches and role filters in Player Search, a similar-players panel and overlaid radars, wage and contract constraints in the optimizer, event/tracking data, an identity review queue, caching and load testing.

## Recently added
Replacement Finder now explains each candidate skill by skill (similar, better, weaker), shows wage and contract context, and offers a cross-position "style" mode (flagged on every card). Squad Audit gained starter-versus-backup, wage-versus-performance and age-outlook views.
