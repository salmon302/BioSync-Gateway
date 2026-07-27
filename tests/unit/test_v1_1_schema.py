# SPDX-License-Identifier: MIT
"""
v1.1 Schema Scaffold — existence + append-only enforcement for FR-3.11–FR-3.16 tables.

Companion to Alembic migration 0007_v1_1_advanced_analytics.py.

Asserts:
  1. All nine v1.1 tables exist in the live schema.
  2. Both append-only rejection triggers (prevent_update / prevent_delete) are
     installed on every v1.1 table (SRS FR-3.8.1).
  3. A representative append-only table (simulation_scenarios) actually rejects
     UPDATE and DELETE at the storage tier (OQ-7 / OQ-8 equivalence for v1.1).

Requires a live PostgreSQL; skipped automatically when DATABASE_URL is unset so
the suite stays green in environments without a database. CI provides a
postgres:15 service so the checks execute there.
"""
import os

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — requires a live PostgreSQL (CI provides it)",
)

V1_1_TABLES = [
    "rag_templates",
    "simulation_scenarios",
    "scenario_runs",
    "synthetic_cohorts",
    "chemistry_profiles",
    "pkpd_worklists",
    "cfdna_sandbox_runs",
    "llm_runs",
    "clinical_text_outputs",
]


def _connect():
    """Create a synchronous engine/connection, skipping the test if PG is down."""
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        return engine, conn
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unavailable for v1.1 schema test: {exc}")


@requires_db
def test_v1_1_tables_exist():
    """All nine v1.1 tables from SRS §6.1 must be present after migration 0007."""
    engine, conn = _connect()
    try:
        rows = conn.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ANY(:tables)
                """
            ),
            {"tables": V1_1_TABLES},
        ).fetchall()
    finally:
        conn.close()
        engine.dispose()

    present = {r[0] for r in rows}
    missing = set(V1_1_TABLES) - present
    assert not missing, f"Missing v1.1 tables after migration 0007: {sorted(missing)}"


@requires_db
def test_v1_1_append_only_triggers_installed():
    """Both BEFORE UPDATE and BEFORE DELETE rejection triggers exist per v1.1 table."""
    engine, conn = _connect()
    try:
        rows = conn.execute(
            text(
                """
                SELECT c.relname AS table_name, t.tgname AS trigger_name
                FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = ANY(:tables)
                  AND t.tgname IN (
                      c.relname || '_prevent_update',
                      c.relname || '_prevent_delete'
                  )
                """
            ),
            {"tables": V1_1_TABLES},
        ).fetchall()
    finally:
        conn.close()
        engine.dispose()

    installed = {(r[0], r[1]) for r in rows}
    for table in V1_1_TABLES:
        assert (table, f"{table}_prevent_update") in installed, (
            f"Missing BEFORE UPDATE rejection trigger on {table} (FR-3.8.1)"
        )
        assert (table, f"{table}_prevent_delete") in installed, (
            f"Missing BEFORE DELETE rejection trigger on {table} (FR-3.8.1)"
        )


@requires_db
def test_simulation_scenarios_append_only_behavior():
    """A representative v1.1 table must reject UPDATE and DELETE at the storage tier."""
    engine, conn = _connect()
    try:
        trans = conn.begin()
        uid = "00000000-0000-0000-0000-0000000000v1"  # 36-char placeholder uid
        conn.execute(
            text(
                """
                INSERT INTO simulation_scenarios (scenario_uid, name, feature_modules, seed)
                VALUES (:uid, 'scaffold_test', '["pk_pd"]'::jsonb, '{"n":1}'::jsonb)
                """
            ),
            {"uid": uid},
        )

        # UPDATE must be rejected (savepoint-isolated so the row survives for the DELETE check).
        sp = conn.begin_nested()
        try:
            conn.execute(
                text("UPDATE simulation_scenarios SET name='mutated' WHERE scenario_uid=:uid"),
                {"uid": uid},
            )
            pytest.fail("UPDATE on append-only simulation_scenarios must be rejected")
        except sa.exc.SQLAlchemyError as exc:
            assert "append-only" in str(exc), f"Unexpected error on UPDATE: {exc}"
            sp.rollback()

        # DELETE must be rejected.
        sp = conn.begin_nested()
        try:
            conn.execute(
                text("DELETE FROM simulation_scenarios WHERE scenario_uid=:uid"),
                {"uid": uid},
            )
            pytest.fail("DELETE on append-only simulation_scenarios must be rejected")
        except sa.exc.SQLAlchemyError as exc:
            assert "append-only" in str(exc), f"Unexpected error on DELETE: {exc}"
            sp.rollback()

        trans.rollback()  # discard the inserted test row (table is append-only)
    finally:
        conn.close()
        engine.dispose()
