# Demo script (about 10 minutes)

## Before you start (once)
```
python -m src.db.migrate_cli upgrade
python -m src.db.ingest                          # loads the player data
python -m src.demo.seed --club Arsenal           # club profile, 3 shortlists, owners, deadlines, history
# optional, to show roles:  SCOUTIQ_AUTH_MODE=on  SCOUTIQ_AUTH_SECRET=...  SCOUTIQ_DEMO_PASSWORD=...  python -m src.demo.seed --users
```
Remove everything the demo created with `python -m src.demo.seed --reset`. Pick **2023/24** in the season selector for the
cleanest data (2024/25 is a partial season, and the app will say so).

## Flow
| Min | Where | Show | Say |
|---|---|---|---|
| 0-1 | Dashboard | The club header and the five numbers | "You choose your club once and the whole platform starts from your squad." |
| 1-3 | Dashboard | Priorities, contracts ending, scouting workload, watchlist movers | "These are Arsenal's real gaps for a 4-3-3, real contract dates, and what moved on our shortlists." |
| 3-4 | Dashboard | Affordable targets | "Candidates who beat our best at that position, within budget. These are screening suggestions, and I'll show you how far to trust them." |
| 4-6 | Player Profile (a target) | Radar and percentiles, then **Why these numbers** | "Every number decomposes: this is the score, these are the pieces, and they add back exactly." Expand a component for the underlying percentiles. |
| 6-7 | Model validation | The status cards, then the "undervalued" test | "We tested every output against what happened next. Breakout probabilities rank players modestly; **'undervalued' did not predict a rise in market value**, and the app says so." |
| 7-8 | Scout Workspace | A shortlist: owners, due dates, overdue strip, one entry's history | "Every change is recorded: who moved him to scout review and when. Overdue work surfaces on the Dashboard." |
| 8-9 | Club Profile | Switch to a second club; compare with a rival | "Multi-club: your squad against rivals, position group by position group." |
| 9-10 | Data health, Audit log, Export | The partial-season finding; an audit entry; one PDF/Excel export | "We tell you which data is incomplete before you rely on it, and every export and change is audited." |

## Questions you will get, and honest answers
* **Is "undervalued" a buy signal?** No. In a forward test it had no relationship with next-year Transfermarkt value change (rank correlation 0.01). Use it to decide who to watch, not to value.
* **Why is development potential so high?** It is an upside ceiling (it overstates next season by about 15 points). The app labels it exploratory.
* **Why does 2024/25 look thin?** It lacks the Belgian, Portuguese and Turkish leagues. The banner and Data health page say so.
* **Where does the data come from?** FIFA ratings and FBref season statistics (FBref stopped publishing advanced statistics in January 2026, so that part cannot be refreshed), plus a Transfermarkt snapshot for contracts and values.
* **Does it use video or tracking data?** Not yet; see Known limitations.
* **Is it secure?** Sign-in with roles, audit trail, rate limiting, size limits, hardened headers; Admin -> Security lists what is on or off. Single sign-on is not included.
