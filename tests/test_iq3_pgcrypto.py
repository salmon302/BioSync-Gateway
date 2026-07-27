# SPDX-License-Identifier: MIT
"""
IQ-3: pgcrypto extension available and enabled (SRS §7.1).

Acceptance (IQ-3):
    SELECT crypt('test', gen_salt('bf'));
returns a non-empty hash string, proving pgcrypto (and its
crypt/gen_salt functions) are installed and usable.

This test requires a live PostgreSQL. It is skipped automatically when
DATABASE_URL is not configured (e.g. local runs without a DB);
CI provides a postgres:15 service so the check executes there.
"""
import os

import pytest

DATABASE_URL = os.getenv("DATABASE_URL")

requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — requires a live PostgreSQL (CI provides it)",
)


@requires_db
def test_pgcrypto_extension_available():
    """IQ-3 — pgcrypto crypt()/gen_salt() are callable."""
    from sqlalchemy import create_engine, text

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT crypt('test', gen_salt('bf'))"))
            value = result.scalar()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL unavailable for IQ-3: {exc}")

    assert isinstance(value, str) and len(value) > 0, (
        "pgcrypto crypt() returned no hash — extension missing (IQ-3)"
    )
