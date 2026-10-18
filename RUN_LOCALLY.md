# Running ScoutIQ on your computer

This is the **complete** project: source code, the player data (already processed and loaded into the database),
tests and documentation. Nothing else needs to be downloaded except the Python and Node packages in steps 2 and 4.

## What you need
| | Version | Check |
|---|---|---|
| Python | 3.11 or newer | `python --version` (Windows: `py --version`) |
| Node.js | 18 or newer (20 recommended) | `node --version` |
| Disk | about 1 GB free (including packages) | |

## Step by step

**1. Open a terminal in the project folder.** It is the folder that contains `src`, `frontend`, `data` and `requirements.txt`.
(Windows: open the folder in File Explorer, click the address bar, type `powershell`, press Enter.)

**2. Create a virtual environment and install the backend** (once):

Windows (PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
If PowerShell refuses to run the activation script, run `Set-ExecutionPolicy -Scope Process Bypass` first and try again.
If you copied this project over an older one, delete the old `.venv` folder first so it is rebuilt cleanly.

**3. Start the backend:**
```
python -m src.api.app
```
Wait until it says the application has started (the first start takes about 20-40 seconds while it warms up).
Check it: open **http://localhost:8010/health** (it shows `{"status": "ok"}`) and **http://localhost:8010/docs**.
Leave this terminal open.

**4. Start the web app** (a *second* terminal, in the same project folder):
```
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000**. You should see the Dashboard with data. Pick a season in the left panel
(2023/24 is the most complete; 2024/25 is missing three leagues and the app says so).

## Optional extras
| What | Command |
|---|---|
| Demo club, shortlists, deadlines, history | `python -m src.demo.seed` (remove with `python -m src.demo.seed --reset`) |
| Run the tests | `python -m pytest tests -q` |
| Refresh the model-validation report | `python -m src.validation.report` (about 2 minutes) |
| Turn on sign-in with roles | see `docs/AUTH.md` |
| PostgreSQL / Docker | see `docs/DEPLOY.md` |
| Measure speed | start the backend, then `python scripts/benchmark.py` |

## If something goes wrong
| You see | Cause and fix |
|---|---|
| `No module named 'src'` | You are not in the project folder, or you ran a file directly. Run commands from the folder containing `src`, and use `python -m ...` exactly as shown. |
| `No module named 'src.config.settings'` or `'src.db.ingest'` | The folder is incomplete (for example, only a patch zip was unpacked). Use the **full** project zip. |
| `No module named 'fastapi'` (or pandas, uvicorn...) | The virtual environment is not active, or step 2 did not finish. Activate it and run `pip install -r requirements.txt` again. |
| The web app shows "Failed to fetch" / no data | The backend is not running, or is on a different port. The web app expects **http://localhost:8010**. To use another port, set `PLAYER_SCOUTING_PORT` for the backend **and** `NEXT_PUBLIC_API_URL` in `frontend/.env.local`. |
| `address already in use` | Something else uses the port. Close it, or choose another port as in the row above. |
| Browser console says CORS blocked | Open the app at exactly `http://localhost:3000`. For another address, set `SCOUTIQ_CORS_ORIGINS=http://that-address` for the backend. |
| The pages load but lists are empty | The database has no data. Rebuild it: `python -m src.data.pipeline_v2` and then `python -m src.db.ingest data/cleaned/fifa_fbref_merged_processed_v2.csv` |
| `npm install` fails | Check `node --version` is 18 or newer. Delete the `frontend/node_modules` folder and run `npm install` again, on a stable connection. |
| Windows: `python` opens the Microsoft Store | Use `py` instead of `python` to create the environment (step 2); after activation, `python` works. |

## What is in the folder
`src/` backend code  ·  `frontend/` web app  ·  `data/` raw sources, processed data, the database (`scoutiq.db`),
Transfermarkt extracts, validation report  ·  `tests/`  ·  `docs/` (start with `docs/INDEX.md`)  ·  `migrations/` database upgrades  ·  `scripts/` tools.
