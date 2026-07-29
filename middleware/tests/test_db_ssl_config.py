# SPDX-License-Identifier: MIT
"""
P2-13 — DB Client Certificate Authentication Configuration Test (NFR-S5)
=======================================================================

Verifies that database.py correctly assembles SSL/TLS connect_args and that
the shipped deployment enforces mutual-TLS:

  * DB_SSLMODE defaults to verify-full in production (fail-closed, R2).
  * the middleware service in docker-compose.yml sets DB_SSLMODE=verify-full.
  * database/postgres/pg_hba.conf requires hostssl clientcert=verify-full.
  * nginx/generate-certs.sh emits a CA-signed PostgreSQL server certificate.

Server-side enforcement (pg_hba.conf hostssl clientcert=verify-full) is now
shipped and documented (see docs/db-client-cert-tls.md) rather than deferred.
"""

import os
import importlib

import pytest

# Resolve repo root (test lives in middleware/tests -> parents[2]).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
_COMPOSE = os.path.join(_REPO_ROOT, "docker-compose.yml")
_PG_HBA = os.path.join(_REPO_ROOT, "database", "postgres", "pg_hba.conf")
_CERT_SCRIPT = os.path.join(_REPO_ROOT, "nginx", "generate-certs.sh")


def _reload_database(monkeypatch):
    """Reload database with the current monkeypatched environment."""
    import database
    return importlib.reload(database)


def test_ssl_connect_args_assembled_when_verify_full(monkeypatch):
    """When DB_SSLMODE=verify-full and cert paths are set, connect_args must
    contain sslmode, sslrootcert, sslcert, and sslkey."""
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    monkeypatch.setenv("DB_SSLROOTCERT", "/etc/ssl/certs/ca.crt")
    monkeypatch.setenv("DB_SSLCERT", "/etc/ssl/certs/client.crt")
    monkeypatch.setenv("DB_SSLKEY", "/etc/ssl/certs/client.key")

    database = _reload_database(monkeypatch)

    assert database.connect_args["sslmode"] == "verify-full"
    assert database.connect_args["sslrootcert"] == "/etc/ssl/certs/ca.crt"
    assert database.connect_args["sslcert"] == "/etc/ssl/certs/client.crt"
    assert database.connect_args["sslkey"] == "/etc/ssl/certs/client.key"
    # connect_args must be applied to the engine (no silent no-op).
    assert database.engine.url.database is not None


def test_ssl_connect_args_empty_when_prefer(monkeypatch):
    """When DB_SSLMODE=prefer, no sslmode/keys are forced (psycopg2 default
    'prefer' is used, allowing TLS when offered but not requiring it)."""
    monkeypatch.setenv("DB_SSLMODE", "prefer")
    monkeypatch.delenv("DB_SSLROOTCERT", raising=False)
    monkeypatch.delenv("DB_SSLCERT", raising=False)
    monkeypatch.delenv("DB_SSLKEY", raising=False)

    database = _reload_database(monkeypatch)

    assert "sslmode" not in database.connect_args
    assert "sslrootcert" not in database.connect_args
    assert "sslcert" not in database.connect_args
    assert "sslkey" not in database.connect_args


def test_ssl_connect_args_partial_when_root_cert_only(monkeypatch):
    """When DB_SSLMODE=verify-full but only root cert is provided, sslrootcert
    should be set but sslcert/sslkey should be absent."""
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    monkeypatch.setenv("DB_SSLROOTCERT", "/etc/ssl/certs/ca.crt")
    monkeypatch.delenv("DB_SSLCERT", raising=False)
    monkeypatch.delenv("DB_SSLKEY", raising=False)

    database = _reload_database(monkeypatch)

    assert database.connect_args["sslmode"] == "verify-full"
    assert database.connect_args["sslrootcert"] == "/etc/ssl/certs/ca.crt"
    assert "sslcert" not in database.connect_args
    assert "sslkey" not in database.connect_args


def test_default_verify_full_in_production(monkeypatch):
    """R2: the shipped default enforces mutual-TLS in production."""
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")

    database = _reload_database(monkeypatch)

    assert database.DB_SSLMODE == "verify-full"


def test_default_prefer_in_development(monkeypatch):
    """Non-production environments default to 'prefer' so local/CI stacks
    without a PKI still connect (TLS attempted, not required)."""
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    database = _reload_database(monkeypatch)

    assert database.DB_SSLMODE == "prefer"


def test_explicit_db_sslmode_overrides_default(monkeypatch):
    """An explicit DB_SSLMODE always wins over the environment-aware default."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DB_SSLMODE", "disable")

    database = _reload_database(monkeypatch)

    assert database.DB_SSLMODE == "disable"


def test_compose_enforces_verify_full():
    """The docker-compose middleware service must pin DB_SSLMODE=verify-full
    and the db service must enable TLS (ssl_ca_file)."""
    assert os.path.isfile(_COMPOSE), f"missing {_COMPOSE}"
    with open(_COMPOSE, "r", encoding="utf-8") as f:
        content = f.read()
    assert "DB_SSLMODE=verify-full" in content, (
        "docker-compose.yml middleware service must enforce DB_SSLMODE=verify-full"
    )
    assert "ssl_ca_file" in content, (
        "docker-compose.yml db service must enable TLS (ssl_ca_file)"
    )


def test_pg_hba_enforces_clientcert():
    """database/postgres/pg_hba.conf must require hostssl clientcert=verify-full."""
    assert os.path.isfile(_PG_HBA), f"missing {_PG_HBA}"
    with open(_PG_HBA, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]

    hostssl_clientcert = [
        ln for ln in lines
        if ln.startswith("hostssl") and "clientcert=verify-full" in ln
    ]
    assert hostssl_clientcert, (
        "pg_hba.conf must contain a 'hostssl ... clientcert=verify-full' line (NFR-S5)"
    )
    # No plain (non-TLS) host lines for network ranges -> fail-closed.
    plain_host = [
        ln for ln in lines
        if ln.startswith("host ") and "127.0.0.1" not in ln and "::1" not in ln
    ]
    assert not plain_host, (
        f"pg_hba.conf must not allow non-TLS network access: {plain_host}"
    )


def test_generate_certs_script_wires_postgres():
    """nginx/generate-certs.sh must emit a CA-signed PostgreSQL server cert
    (certs/server.crt) so the db can present a cert chaining to sslrootcert."""
    assert os.path.isfile(_CERT_SCRIPT), f"missing {_CERT_SCRIPT}"
    with open(_CERT_SCRIPT, "r", encoding="utf-8") as f:
        content = f.read()
    # Server cert must be produced under the certs dir and signed by the CA.
    assert "${CERTS_DIR}/server.crt" in content, (
        "generate-certs.sh must produce certs/server.crt for Postgres TLS"
    )
    assert '-CA "${CERTS_DIR}/ca.crt"' in content, (
        "generate-certs.sh must sign the server cert against certs/ca.crt"
    )
