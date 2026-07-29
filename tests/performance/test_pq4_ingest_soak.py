# SPDX-License-Identifier: MIT
"""
PQ-4: 24-hour ingest soak (SRS NFR-P4 soak; REMAINING_WORK R8).

Gated, heavy test. Skipped unless ``BIOSYNC_PQ4_DATABASE_URL`` is set (point it
at a dedicated/throwaway Postgres). Imports the canonical runner from
``SNDEV/scripts/pq4_24h_ingest.py`` and asserts the qualification SLOs:

  * ``deadlocks == 0``
  * ``memory_growth_pct <= 5.0``

The soak duration defaults to the full 24h (86400 s) to match SRS. CI passes a
shorter ``BIOSYNC_PQ4_SOAK_SECONDS`` (the GitHub job limit is 6h, so routine CI
uses ~3600s); run the full 24h qualification on a self-hosted/long runner.

Example (local, 10-minute smoke):
    BIOSYNC_PQ4_DATABASE_URL=postgresql://biosync_user:PASSWORD@localhost:5432/biosync \
    BIOSYNC_PQ4_SOAK_SECONDS=600 \
        pytest tests/performance/test_pq4_ingest_soak.py -v -s
"""

import os
import sys

import pytest

# Make SNDEV/scripts importable regardless of cwd.
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "SNDEV",
    "scripts",
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

PQ4_DATABASE_URL = os.environ.get("BIOSYNC_PQ4_DATABASE_URL", "")
SOAK_SECONDS = int(os.environ.get("BIOSYNC_PQ4_SOAK_SECONDS", 24 * 3600))
WORKERS = int(os.environ.get("BIOSYNC_PQ4_WORKERS", 8))


@pytest.mark.skipif(
    not PQ4_DATABASE_URL,
    reason="Set BIOSYNC_PQ4_DATABASE_URL to run PQ-4 (24h ingest soak).",
)
@pytest.mark.pq4
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.db
def test_pq4_ingest_soak_24h():
    """PQ-4 soak: 0 deadlocks and <=5% memory growth over the soak window."""
    from pq4_24h_ingest import run_soak

    summary = run_soak(PQ4_DATABASE_URL, duration_s=SOAK_SECONDS, workers=WORKERS)
    print("PQ-4 soak summary:", summary)

    assert summary["deadlocks"] == 0, (
        f"PQ-4 soak detected {summary['deadlocks']} deadlock(s) (SLO: 0)."
    )

    if summary["memory_growth_pct"] is not None:
        assert summary["memory_growth_pct"] <= 5.0, (
            f"PQ-4 soak memory growth {summary['memory_growth_pct']}% exceeds "
            "the 5% SLO (NFR-P4 soak)."
        )
    else:
        pytest.skip(
            "RSS measurement unavailable on this platform; memory SLO not asserted."
        )
