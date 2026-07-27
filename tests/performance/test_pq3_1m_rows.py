# SPDX-License-Identifier: MIT
"""
PQ-3: 1,000,000-row Hash Chain Verification (SRS NFR-P4)
=================================================================

Implements SRS §7.3 PQ-3 and NFR-P4:

    "Hash chain verification: 1 million audit_log rows
     -> Recompute-and-compare query completes within 60 seconds."

Approach
--------
1. Connect to a DEDICATED Postgres (NOT the shared CI database).
2. Reset the `audit_log` fixture (TRUNCATE ... RESTART IDENTITY so the
   genesis-row check in hash-chain-check.sql stays valid).
3. Insert 1,000,000 rows via `generate_series` so the existing
   `audit_log_hash_chain` BEFORE INSERT trigger computes the SHA-256
   hash chain (FR-3.8.3).

   NOTE: the insert is performed as a PL/pgSQL loop of single-row
   INSERTs rather than a single `INSERT ... SELECT generate_series(...)`.
   The trigger derives `previous_hash` from the *latest committed row*
   (`SELECT current_hash ... ORDER BY id DESC LIMIT 1`). Within one
   multi-row statement the not-yet-committed rows are mutually invisible,
   so a bulk INSERT would produce a broken chain. The loop keeps each
   INSERT in its own statement within a single transaction, so the trigger
   sees the prior row and chains correctly.
4. Run the canonical nightly verification SQL (`database/migrations/
   hash-chain-check.sql`) and assert it completes in < 60 s.
5. Independently assert integrity via `verify_hash_chain()` == 'ok'.

Gating
-------
This is a HEAVY test. It is skipped unless `BIOSYNC_PQ3_DATABASE_URL`
is set, so it never runs against the shared CI Postgres. Point it at a
throwaway/CI Postgres (e.g. a docker-compose stack or a disposable
cloud instance). Executed by `.github/workflows/pq.yml`.

Example:
    BIOSYNC_PQ3_DATABASE_URL=postgresql://biosync_user:PASSWORD@localhost:5432/biosync \
        pytest tests/performance/test_pq3_1m_rows.py -v -s
"""

import os
import sys
import time

import pytest

# The psycopg2 driver is a middleware dependency. Import it lazily inside
# the connection helper so this (gated) test still *collects* cleanly on
# machines where the driver is not installed (the test is skipped there).
_MIDDLEWARE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "middleware",
)
if _MIDDLEWARE_DIR not in sys.path:
    sys.path.insert(0, _MIDDLEWARE_DIR)

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
HASH_CHECK_SQL = os.path.join(REPO_ROOT, "database", "migrations", "hash-chain-check.sql")

NFR_P4_SECONDS = 60.0
ROWS = 1_000_000

# Dedicated Postgres URL. Empty by default -> test is skipped.
PQ3_DATABASE_URL = os.environ.get("BIOSYNC_PQ3_DATABASE_URL", "")


@pytest.mark.skipif(
    not PQ3_DATABASE_URL,
    reason="Set BIOSYNC_PQ3_DATABASE_URL to a dedicated Postgres to run PQ-3 (1M rows).",
)
@pytest.mark.pq3
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.db
class TestPQ3HashChain1M:
    @staticmethod
    def _connect():
        import psycopg2  # lazy: only needed when the test actually runs

        return psycopg2.connect(PQ3_DATABASE_URL, connect_timeout=30)

    def test_1m_rows_hash_chain_under_60s(self):
        # 1) Reset the audit_log fixture on the dedicated DB.
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    # RESTART IDENTITY so the first row is id=1 and the
                    # genesis-row branch of hash-chain-check.sql holds.
                    cur.execute("TRUNCATE audit_log RESTART IDENTITY;")
        finally:
            conn.close()

        # 2) Insert 1M rows; the trigger computes the hash chain.
        generate_sql = """
        DO $$
        DECLARE
            i INT;
            v_table CONSTANT VARCHAR := 'pq3_stress';
            v_op CONSTANT VARCHAR := 'INSERT';
            v_uid CONSTANT VARCHAR := 'pq3-loader';
            v_reason CONSTANT TEXT := 'PQ-3 1M-row load generation';
            v_data JSONB;
        BEGIN
            FOR i IN SELECT generate_series(1, %d) LOOP
                v_data := jsonb_build_object(
                    'row', i,
                    'table', v_table,
                    'record_id', i,
                    'action', 'insert'
                );
                INSERT INTO audit_log
                    (table_name, operation, record_id, user_id, data, previous_state, reason)
                VALUES
                    (v_table, v_op, i, v_uid, v_data, NULL, v_reason);
            END LOOP;
        END $$;
        """ % ROWS

        conn = self._connect()
        try:
            insert_start = time.perf_counter()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(generate_sql)
            insert_elapsed = time.perf_counter() - insert_start
            print(f"PQ-3: inserted {ROWS:,} rows in {insert_elapsed:.2f}s")
        finally:
            conn.close()

        # 3) Run the canonical nightly hash-chain verification SQL and
        #    assert it completes within NFR-P4 (<= 60 s for 1M rows).
        assert os.path.isfile(HASH_CHECK_SQL), f"Missing {HASH_CHECK_SQL}"
        with open(HASH_CHECK_SQL, "r", encoding="utf-8") as f:
            hash_check_sql = f.read()

        conn = self._connect()
        try:
            verify_start = time.perf_counter()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(hash_check_sql)
                    # Fully drain all result sets emitted by the script.
                    while True:
                        cur.fetchall()
                        if not cur.nextset():
                            break
            verify_elapsed = time.perf_counter() - verify_start
        finally:
            conn.close()

        print(
            f"PQ-3: hash-chain-check.sql completed in {verify_elapsed:.2f}s "
            f"(NFR-P4 limit {NFR_P4_SECONDS:.0f}s)"
        )
        assert verify_elapsed < NFR_P4_SECONDS, (
            f"Hash chain verification took {verify_elapsed:.2f}s, "
            f"exceeds NFR-P4 limit of {NFR_P4_SECONDS:.0f}s"
        )

        # 4) Independent integrity assertion via verify_hash_chain(): the
        #    chain must be intact (correct genesis linkage, no tampering).
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT integrity_status, broken_at_row_id "
                        "FROM verify_hash_chain();"
                    )
                    status, broken_at = cur.fetchone()
            assert status == "ok", (
                f"Hash chain integrity = {status}; broken at row {broken_at}"
            )
        finally:
            conn.close()
