"""Container health probe: exit 0 when the API process answers HTTP.

A 401 counts as healthy -- it proves the server is up even when SCOUTIQ_API_KEY / login is enforced.
"""
import os
import sys
import urllib.error
import urllib.request

port = os.getenv("PLAYER_SCOUTING_PORT", "8010")
try:
    urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
except urllib.error.HTTPError as exc:
    sys.exit(0 if exc.code == 401 else 1)
except Exception:
    sys.exit(1)
