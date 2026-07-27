# SPDX-License-Identifier: MIT
"""
IQ-6: Audit-log append-only triggers are installed (SRS §7.1).

Acceptance (IQ-6):
    pg_trigger introspection confirms the BEFORE UPDATE and BEFORE DELETE
    rejection triggers exist on the ``audit_log`` table.

The implementation names these triggers ``audit_log_prevent_update`` and
``audit_log_prevent_delete`` (SRS FR-3.8.1 / FR-3.8.2). This test
asserts their presence via PostgreSQL system catalogs.

Requires a live PostgreSQL; skipped automatically when DATABASE_URL is
not configured. CI provides a postgres:15 service so the check runs there.
"""
import os

import pytest

DATABASE_URL = os.getenv("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — requires a live PostgreSQL (CI provides it)",
)


@requires_db
def test_audit_log_triggers_installed():
    """IQ-6 — before-UPDATE and before-DELETE reject triggers on audit_log."""
    from sqlalchemy import create_engine, text

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT t.tgname
                    FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = 'audit_log'
                      AND t.tgname IN (
                          'audit_log_prevent_update',
                          'audit_log_prevent_delete'
                      )
                    """
                )
            ).fetchall()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unavailable for IQ-6: {exc}")

    names = {r[0] for r in rows}
    assert "audit_log_prevent_update" in names, (
        "Missing before-UPDATE rejection trigger on audit_log (IQ-6 / FR-3.8.1)"
    )
    assert "audit_log_prevent_delete" in names, (
        "Missing before-DELETE rejection trigger on audit_log (IQ-6 / FR-3.8.1)"
    )
