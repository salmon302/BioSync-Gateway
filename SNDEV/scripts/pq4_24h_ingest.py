# SPDX-License-Identifier: MIT
"""
PQ-4: Sustained 24-hour Telemetry Ingestion — SOAK TEST SKELETON
==================================================================

Implements SRS §7.3 PQ-4 / NFR-P1:
    "Sustained 24-hour telemetry ingestion at 100,000 points/sec
     -> Zero database deadlocks; memory growth <= 5%;
        audit log grows linearly without insert degradation."

STATUS: DEFERRED per user direction (2026-07). This file is a SKELETON.
- `--mode smoke` (DEFAULT): runs a short, bounded ingestion burst so the
  harness can be validated manually against a local docker-compose stack.
- The full 24h soak section is present but COMMENTED / DISABLED and is NOT
  executed in CI. It is provided for the eventual disposable-cloud soak run.

Usage
------
    python SNDEV/scripts/pq4_24h_ingest.py --mode smoke --duration 60 \
        --rate 1000 --base-url http://localhost:8000 --token <JWT>

Environment fallbacks: BASE_URL, BIOSYNC_API_TOKEN.

NOTE: This script never runs in CI. It is a manual / cloud-soak tool only.
"""

import argparse
import json
import os
import sys
import time

try:
    import httpx
except ImportError:  # pragma: no cover - httpx is a middleware dep
    httpx = None


LOINC_CODES = {
    "pressure": ("8310-5", "mmHg"),
    "flow": ("85354-9", "L/min"),
    "hr": ("8867-4", "beats/min"),
    "spo2": ("59408-5", "%"),
}


def _make_batch(batch_size: int) -> dict:
    """Build a fake telemetry Observation batch (mirrors locustfile)."""
    observations = []
    now = time.time()
    for i in range(batch_size):
        channel = list(LOINC_CODES.keys())[i % len(LOINC_CODES)]
        code, unit = LOINC_CODES[channel]
        value = round(60.0 + (i % 100), 1)
        observations.append(
            {
                "resourceType": "Observation",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
                "valueQuantity": {"value": value, "unit": unit},
                "effectiveDateTime": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(now + i * 0.001)
                ),
            }
        )
    return {"observations": observations}


def _ingest(base_url: str, token: str, batch: dict) -> int:
    """POST one telemetry batch; return persisted count (best-effort)."""
    if httpx is None:
        raise RuntimeError("httpx is required (middleware dependency).")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = httpx.post(
        f"{base_url}/api/telemetry/ingest",
        json=batch,
        headers=headers,
        timeout=30.0,
    )
    if resp.status_code != 200:
        return 0
    try:
        return int(resp.json().get("persisted", 0))
    except Exception:
        return 0


def run_smoke(duration_s: int, rate_per_s: int, base_url: str, token: str) -> None:
    """Short, bounded ingestion burst for manual harness validation."""
    batch_size = max(1, rate_per_s // 10)  # ~10 batches/sec equivalent
    print(
        f"[PQ-4 smoke] base_url={base_url} duration={duration_s}s "
        f"rate~{rate_per_s}/s batch={batch_size}"
    )
    start = time.perf_counter()
    total = 0
    errors = 0
    while time.perf_counter() - start < duration_s:
        batch = _make_batch(batch_size)
        try:
            persisted = _ingest(base_url, token, batch)
            total += persisted
        except Exception as exc:  # pragma: no cover - network paths
            errors += 1
            print(f"[PQ-4 smoke] ingest error: {exc}")
        time.sleep(max(0.0, 1.0 / max(1, rate_per_s / batch_size)))
    elapsed = time.perf_counter() - start
    achieved = total / elapsed if elapsed > 0 else 0
    print(
        f"[PQ-4 smoke] done: persisted={total} elapsed={elapsed:.1f}s "
        f"achieved~{achieved:.0f} pts/s errors={errors}"
    )
    print("[PQ-4 smoke] Smoke mode only. The 24h soak is DISABLED (deferred).")


# ---------------------------------------------------------------------------
# 24-HOUR SOAK SECTION — COMMENTED / DISABLED (deferred per user direction)
# ---------------------------------------------------------------------------
#
# The full soak must NOT run in CI. It is provided as a reference for the
# eventual disposable-cloud run. To enable, uncomment run_24h_soak() and
# wire it to `--mode soak` once the soak infrastructure is approved.
#
# def run_24h_soak(base_url: str, token: str, target_pps: int = 100_000) -> None:
#     """Sustained 24h ingestion at >= 100k points/sec (NFR-P1 / PQ-4)."""
#     duration_s = 24 * 60 * 60
#     batch_size = 1000
#     batches_per_s = max(1, target_pps // batch_size)
#     sleep_per_loop = 1.0 / batches_per_s
#     print(f"[PQ-4 soak] START 24h soak target={target_pps} pts/s")
#     start = time.perf_counter()
#     total = 0
#     peak_rss_mb = 0.0
#     while time.perf_counter() - start < duration_s:
#         batch = _make_batch(batch_size)
#         total += _ingest(base_url, token, batch)
#         # Memory growth guard (<= 5%): sample process RSS periodically and
#         # alert if it exceeds the 5% budget relative to the baseline.
#         # (Left as an exercise for the soak harness / external monitor.)
#         time.sleep(sleep_per_loop)
#     elapsed = time.perf_counter() - start
#     print(f"[PQ-4 soak] DONE persisted={total} elapsed={elapsed:.0f}s "
#           f"avg={total/elapsed:.0f} pts/s")
#     # Acceptance (manual review): zero DB deadlocks, memory growth <= 5%,
#     # audit log grows linearly without insert degradation.


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PQ-4 24h ingestion soak skeleton")
    parser.add_argument(
        "--mode",
        choices=["smoke", "soak"],
        default="smoke",
        help="smoke = short burst (default); soak = 24h (DISABLED/deferred)",
    )
    parser.add_argument("--duration", type=int, default=60, help="smoke duration (s)")
    parser.add_argument("--rate", type=int, default=1000, help="approx points/sec")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:8000"),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("BIOSYNC_API_TOKEN", ""),
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.mode == "smoke":
        run_smoke(args.duration, args.rate, args.base_url, args.token)
        return 0
    # Soak requested: intentionally blocked until the deferred soak
    # infrastructure is approved. See the commented run_24h_soak() above.
    print(
        "[PQ-4] '--mode soak' (24h) is DEFERRED per user direction and is "
        "disabled in this skeleton. Run '--mode smoke' for harness validation, "
        "or schedule the full soak manually on a disposable cloud instance."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
