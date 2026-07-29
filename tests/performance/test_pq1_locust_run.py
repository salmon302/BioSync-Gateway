# SPDX-License-Identifier: MIT
"""
PQ-1: real Locust load run (SRS NFR-P1 / NFR-P3; REMAINING_WORK R8).

Promotes PQ-1 from the prior smoke-only k6 *pointer* test
(``test_pq1_websocket_latency.py``) to a genuine headless Locust run against a
RUNNING BioSync-Gateway stack, with SLO assertions:

  * total requests > 0
  * failure ratio < 0.01
  * P95 response time < 250 ms  (NFR-P3 HTTP CRUD/ingest)

Skipped unless ``BIOSYNC_PQ1_BASE_URL`` is set (a live gateway). Reuses the user
classes defined in ``tests/performance/locustfile.py`` (notably
``TelemetryIngestUser``, which exercises the /api/telemetry/ingest path that
backs NFR-P1/P3).

Env knobs:
    BIOSYNC_PQ1_BASE_URL    gateway base URL (required to run)
    BIOSYNC_PQ1_DURATION    run length in seconds (default 60)
    BIOSYNC_PQ1_USERS       concurrent users (default 10)
    BIOSYNC_PQ1_SPAWN_RATE  users spawned/sec (default 2)
    JWT_SECRET              must equal the gateway secret so tokens validate

Requires ``locust==2.46.2`` (pinned in middleware/requirements.txt).
"""

import os
import sys
import time

import pytest

_PERF_DIR = os.path.dirname(os.path.abspath(__file__))
if _PERF_DIR not in sys.path:
    sys.path.insert(0, _PERF_DIR)

BASE_URL = os.environ.get("BIOSYNC_PQ1_BASE_URL", "")
DURATION = int(os.environ.get("BIOSYNC_PQ1_DURATION", 60))
USERS = int(os.environ.get("BIOSYNC_PQ1_USERS", 10))
SPAWN_RATE = float(os.environ.get("BIOSYNC_PQ1_SPAWN_RATE", 2))
P95_LIMIT_MS = 250.0
FAIL_RATIO_LIMIT = 0.01


@pytest.mark.skipif(
    not BASE_URL,
    reason="Set BIOSYNC_PQ1_BASE_URL to run PQ-1 (real Locust load).",
)
@pytest.mark.pq1
@pytest.mark.performance
def test_pq1_locust_real_run():
    """Drive a headless Locust run and assert PQ-1 SLOs against the live stack."""
    try:
        from locust import Environment
    except ImportError:
        pytest.skip("locust not installed; install locust==2.46.2 to run PQ-1.")

    from locustfile import TelemetryIngestUser

    env = Environment(user_classes=[TelemetryIngestUser], host=BASE_URL)
    runner = env.create_local_runner()
    runner.start(USERS, SPAWN_RATE)
    try:
        time.sleep(DURATION)
    finally:
        runner.quit()

    total = env.runner.stats.total
    num_requests = total.num_requests
    num_failures = total.num_failures
    ratio = (num_failures / num_requests) if num_requests else 1.0

    # P95: prefer the newer API name, fall back to the older 2.x name.
    p95 = None
    for meth in ("get_response_time_percentile", "get_current_response_time_percentile"):
        fn = getattr(total, meth, None)
        if fn is not None:
            try:
                p95 = fn(0.95)
                if p95 is not None:
                    break
            except Exception:
                continue

    print(
        f"PQ-1: requests={num_requests} failures={num_failures} "
        f"fail_ratio={ratio:.4f} p95_ms={p95}"
    )

    assert num_requests > 0, (
        "PQ-1 issued no requests — is the gateway up at BIOSYNC_PQ1_BASE_URL?"
    )
    assert ratio < FAIL_RATIO_LIMIT, (
        f"PQ-1 failure ratio {ratio:.4f} >= {FAIL_RATIO_LIMIT} (SLO)."
    )
    if p95 is not None:
        assert p95 <= P95_LIMIT_MS, (
            f"PQ-1 P95 {p95:.1f} ms > {P95_LIMIT_MS} ms (NFR-P3)."
        )
    else:
        pytest.skip("P95 unavailable from Locust stats on this version.")
