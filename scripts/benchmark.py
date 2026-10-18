"""Measure API latency under load against a RUNNING server. Standard library only.

  python scripts/benchmark.py --base http://127.0.0.1:8010 --concurrency 10 --seconds 15 [--api-key KEY] [--token JWT]

Prints per-endpoint p50 / p95 / max latency, throughput and error rate. Use a server with the rate limiter
off (SCOUTIQ_RATE_LIMIT_PER_MINUTE=0), otherwise the limiter will (correctly) answer 429 and skew the result.
"""
from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request


def call(base, method, path, body, headers, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json", **headers})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    return status, (time.perf_counter() - start) * 1000


def pctl(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))] if values else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--seconds", type=int, default=15)
    ap.add_argument("--api-key")
    ap.add_argument("--token")
    ap.add_argument("--season", type=int, default=2324)
    args = ap.parse_args()
    headers = {}
    if args.api_key:
        headers["X-API-Key"] = args.api_key
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    s = args.season
    req = urllib.request.Request(args.base + f"/api/players?limit=2&season={s}", headers=headers)
    rows = json.loads(urllib.request.urlopen(req, timeout=60).read())
    rows = rows.get("results") or rows.get("players") or []
    pid, club = rows[0]["player_id"], rows[0].get("club_name") or "Arsenal"
    endpoints = [
        ("GET", "/api/seasons", None), ("GET", f"/api/dashboard/overview?season={s}", None),
        ("GET", f"/api/players?limit=20&season={s}", None), ("GET", f"/api/players/{pid}?season={s}", None),
        ("GET", f"/api/players/{pid}/explain?season={s}", None), ("GET", f"/api/market/opportunities?top_n=20&season={s}", None),
        ("GET", "/api/data-health", None), ("POST", "/api/scouting/search", {"season": s, "limit": 20, "min_performance_score": 60}),
        ("POST", "/api/squads/audit", {"club_name": club, "formation": "4-3-3", "season": s}),
        ("POST", "/api/replacement/search", {"outgoing_player_id": pid, "season": s, "top_n": 5}),
    ]
    print(f"{'endpoint':52}{'n':>6}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}{'err':>5}")
    for m, path, body in endpoints:  # single client: first call (cold), then five warm calls
        first = call(args.base, m, path, body, headers)[1]
        warm = [call(args.base, m, path, body, headers)[1] for _ in range(5)]
        print(f"{m + ' ' + path[:46]:52}{'1+5':>6}{statistics.median(warm):9.0f}{max(warm):9.0f}{first:9.0f}{'':>5}  (cold {first:.0f} ms)")
    results = {path: [] for _, path, _ in endpoints}
    errors = {path: 0 for _, path, _ in endpoints}
    stop, lock = time.time() + args.seconds, threading.Lock()

    def worker(offset):
        i = offset
        while time.time() < stop:
            m, path, body = endpoints[i % len(endpoints)]
            status, ms = call(args.base, m, path, body, headers)
            with lock:
                results[path].append(ms)
                if status != 200:
                    errors[path] += 1
            i += 1

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(args.concurrency)]
    t0 = time.time()
    [t.start() for t in threads]
    [t.join() for t in threads]
    wall = time.time() - t0
    total = sum(len(v) for v in results.values())
    print(f"\nUnder load: {args.concurrency} concurrent clients for {wall:.0f}s -> {total} requests, {total / wall:.1f} req/s")
    print(f"{'endpoint':52}{'n':>6}{'p50 ms':>9}{'p95 ms':>9}{'max ms':>9}{'err':>5}")
    for m, path, _ in endpoints:
        v = results[path]
        print(f"{m + ' ' + path[:46]:52}{len(v):6}{pctl(v, .5):9.0f}{pctl(v, .95):9.0f}{max(v) if v else 0:9.0f}{errors[path]:5}")
    print(f"\nerror rate: {sum(errors.values()) / max(total, 1) * 100:.2f}%")


if __name__ == "__main__":
    main()
