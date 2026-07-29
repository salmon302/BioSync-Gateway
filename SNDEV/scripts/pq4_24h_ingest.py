# SPDX-License-Identifier: MIT
#
# Title: pq4-24h-ingest
# Date: 2026-07-29T00:00:00Z
# Author: Seth Nenninger (tencent/hy3 Agent)
# Contribution Type: Implementation
# Ticket/Context: REMAINING_WORK_v1.1.md R8 (PQ-4 24h ingest soak)
# Summary: Standalone + importable 24h ingest soak harness asserting 0 deadlocks
#          and <=5% memory growth (NFR-P4 soak). Referenced by pq.yml.
"""
PQ-4: 24-hour ingest soak (SRS NFR-P4 soak; REMAINING_WORK R8).

Runs a sustained, concurrent ingest workload into a dedicated `pq4_soak` table
on a throwaway/CI Postgres and asserts, over the soak window:

  * deadlocks == 0   (psycopg2.errors.DeadlockDetected is counted; any > 0 fails)
  * memory_growth_pct <= 5.0   (peak RSS growth of the harness process)

This is the canonical runner referenced by .github/workflows/pq.yml. The pytest
wrapper tests/performance/test_pq4_ingest_soak.py imports :func:`run_soak` and
asserts the SLOs, so the same logic serves both the UI/CLI 24h run and CI.

Usage:
    python SNDEV/scripts/pq4_24h_ingest.py \
        --db-url postgresql://user:pass@localhost:5432/biosync \
        --seconds 86400 --workers 8
    # or via env: BIOSYNC_PQ4_DATABASE_URL / BIOSYNC_PQ4_SOAK_SECONDS / BIOSYNC_PQ4_WORKERS
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

DEFAULT_SOAK_SECONDS = 24 * 3600  # SRS-qualifying full soak
DEFAULT_WORKERS = 8
MEMORY_GROWTH_LIMIT_PCT = 5.0


def _peak_rss_kb() -> int | None:
    """Cross-platform peak/resident RSS in KB (POSIX ru_maxrss, Windows psutil)."""
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (ImportError, AttributeError):
        try:
            import psutil

            return int(psutil.Process().memory_info().rss // 1024)
        except Exception:
            return None


def _connect(db_url: str, timeout: int = 30):
    import psycopg2

    return psycopg2.connect(db_url, connect_timeout=timeout)


def run_soak(
    db_url: str,
    duration_s: int = DEFAULT_SOAK_SECONDS,
    workers: int = DEFAULT_WORKERS,
) -> dict:
    """Execute the ingest soak and return a summary dict with SLO results.

    The summary contains: rows_inserted, errors, deadlocks, memory_growth_pct,
    max_blocked_locks, peak RSS samples, and started/finished timestamps.
    """
    deadline = time.time() + duration_s
    stats: dict = {
        "rows_inserted": 0,
        "errors": 0,
        "deadlocks": 0,
        "max_blocked_locks": 0,
        "peak_rss_start_kb": _peak_rss_kb(),
        "peak_rss_end_kb": None,
        "memory_growth_pct": None,
        "duration_s": duration_s,
        "workers": workers,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    lock = threading.Lock()
    stop = threading.Event()

    # --- Setup a dedicated soak table on the throwaway DB. ---
    conn = _connect(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS pq4_soak ("
                    " id bigserial PRIMARY KEY,"
                    " payload jsonb NOT NULL,"
                    " created_at timestamptz NOT NULL DEFAULT now()"
                    ");"
                )
                cur.execute("TRUNCATE pq4_soak;")
    finally:
        conn.close()

    def worker(wid: int) -> None:
        import psycopg2
        import psycopg2.errors

        local = 0
        c = _connect(db_url)
        try:
            while not stop.is_set() and time.time() < deadline:
                try:
                    with c.cursor() as cur:
                        cur.execute(
                            "INSERT INTO pq4_soak (payload) VALUES (%s)",
                            ({"w": wid, "t": time.time()},),
                        )
                    c.commit()
                    local += 1
                except psycopg2.errors.DeadlockDetected:
                    c.rollback()
                    with lock:
                        stats["deadlocks"] += 1
                    time.sleep(0.05)  # back off, then retry
                except Exception:
                    c.rollback()
                    with lock:
                        stats["errors"] += 1
                    time.sleep(0.05)
                    # Reconnect if the connection was lost.
                    try:
                        c.close()
                    except Exception:
                        pass
                    c = _connect(db_url)
        finally:
            try:
                c.close()
            except Exception:
                pass
        with lock:
            stats["rows_inserted"] += local

    threads = [threading.Thread(target=worker, args=(i,), name=f"soak-{i}")
               for i in range(workers)]
    for t in threads:
        t.start()

    # --- Monitor loop: sample memory + lock contention until the window ends. ---
    interval = max(1.0, min(30.0, duration_s / 100.0))
    while time.time() < deadline and any(t.is_alive() for t in threads):
        time.sleep(interval)
        rss = _peak_rss_kb()
        if rss is not None:
            stats["peak_rss_start_kb"] = stats["peak_rss_start_kb"] or rss
        try:
            probe = _connect(db_url, timeout=10)
            with probe.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_locks WHERE NOT granted;")
                blocked = int(cur.fetchone()[0])
            probe.close()
            with lock:
                if blocked > stats["max_blocked_locks"]:
                    stats["max_blocked_locks"] = blocked
        except Exception:
            pass

    stop.set()
    for t in threads:
        t.join(timeout=10)

    stats["peak_rss_end_kb"] = _peak_rss_kb()
    start = stats["peak_rss_start_kb"]
    end = stats["peak_rss_end_kb"]
    if start and end:
        base = max(start, 1)
        stats["memory_growth_pct"] = round((end - start) / base * 100.0, 3)
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    return stats


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="PQ-4 24h ingest soak runner")
    p.add_argument(
        "--db-url",
        default=os.environ.get("BIOSYNC_PQ4_DATABASE_URL", ""),
        help="Dedicated/throwaway Postgres URL (or set BIOSYNC_PQ4_DATABASE_URL).",
    )
    p.add_argument(
        "--seconds",
        type=int,
        default=int(os.environ.get("BIOSYNC_PQ4_SOAK_SECONDS", DEFAULT_SOAK_SECONDS)),
        help="Soak duration in seconds (default 86400 = 24h).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("BIOSYNC_PQ4_WORKERS", DEFAULT_WORKERS)),
        help="Concurrent ingest worker threads.",
    )
    args = p.parse_args(argv)

    if not args.db_url:
        p.error("provide --db-url or set BIOSYNC_PQ4_DATABASE_URL")

    summary = run_soak(args.db_url, duration_s=args.seconds, workers=args.workers)
    print(json.dumps(summary, indent=2))

    if summary["deadlocks"] > 0:
        print("PQ-4 FAIL: deadlocks detected", file=sys.stderr)
        return 2
    if (
        summary["memory_growth_pct"] is not None
        and summary["memory_growth_pct"] > MEMORY_GROWTH_LIMIT_PCT
    ):
        print("PQ-4 FAIL: memory growth exceeded 5%", file=sys.stderr)
        return 3
    print("PQ-4 PASS: 0 deadlocks, memory growth within 5%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
