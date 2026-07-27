# SPDX-License-Identifier: MIT
"""
PQ-1: Real-Load Performance Qualification — k6 migration note & pointer test.
==========================================================================

This module previously contained the CI "smoke-only" import micro-benchmarks
(JSON serialization / throughput latency). Those tests were NOT a faithful
Performance Qualification of PQ-1 (SRS §7.3): PQ-1 requires a *real*
distributed load test of 50 concurrent WebSocket/HTTP virtual users against a
running BioSync-Gateway stack, with the SLOs below.

The authoritative PQ-1 load test now lives in:

    tests/performance/k6/pq1_websocket.js

and is executed by the `pq.yml` GitHub Actions workflow (workflow_dispatch +
nightly schedule) via the official `grafana/k6` Docker image:

    docker run --rm --network host \
        -v "$PWD/tests/performance/k6:/scripts" \
        grafana/k6 run /scripts/pq1_websocket.js \
        -e BASE_URL=http://localhost:8000 \
        -e WS_URL=ws://localhost:8000/api/telemetry/stream \
        -e API_TOKEN=<valid-jwt> \
        -e PEAK_VUS=50 -e RAMP_MIN=12

Target SLOs (revised D1 plan):
    - http_req_failed    < 0.01
    - http_req_duration p(95) < 250 ms   (SRS NFR-P3)
    - ws_connecting p(95) < 250 ms        (WS-specific, when token supplied)

Fast pytest micro-benchmarks for the algorithmic engines (EMA, Hamming,
dilution) and the unit/integration suites are retained (AGENTS tooling note:
"keep pytest micro-benchmarks"). This file now acts as a deterministic,
fast pointer test so CI retains a signal that the real k6 asset exists.

See also:
    - docs/URS.md, docs/FRS.md (traceability)
    - SRS.md §7.3 (PQ-1), §5.1 (NFR-P3)
"""

import os

import pytest

_K6_SCRIPT = os.path.join(os.path.dirname(__file__), "k6", "pq1_websocket.js")


@pytest.mark.pq1
@pytest.mark.performance
def test_pq1_k6_asset_present():
    """Pointer test: the k6 PQ-1 load script must exist and be non-empty."""
    assert os.path.isfile(_K6_SCRIPT), (
        f"PQ-1 k6 load script missing at {_K6_SCRIPT}. "
        "Real PQ-1 load testing moved to k6 (see module docstring)."
    )
    assert os.path.getsize(_K6_SCRIPT) > 0, "PQ-1 k6 load script is empty."
