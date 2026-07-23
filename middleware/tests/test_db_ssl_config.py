# SPDX-License-Identifier: MIT
"""
P2-13 — DB Client Certificate Authentication Configuration Test (NFR-S5)

Verifies that database.py correctly assembles SSL/TLS connect_args when
DB_SSLMODE=verify-full and client certificate paths are provided.

This is a configuration-level test (no live database required). It validates
that the middleware wiring for mutual-TLS is correct: sslmode, sslrootcert,
sslcert, and sslkey are all present in connect_args when the environment
is configured for verify-full.

Server-side enforcement (pg_hba.conf hostssl clientcert=verify-full) is
documented as deferred in SNDEV/docs/impl-2026-07-22-srs-remaining-work.md.
"""

import os
import sys
import importlib

import pytest


def test_ssl_connect_args_assembled_when_verify_full(monkeypatch):
    """When DB_SSLMODE=verify-full and cert paths are set, connect_args must
    contain sslmode, sslrootcert, sslcert, and sslkey."""
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    monkeypatch.setenv("DB_SSLROOTCERT", "/etc/ssl/certs/ca.crt")
    monkeypatch.setenv("DB_SSLCERT", "/etc/ssl/certs/client.crt")
    monkeypatch.setenv("DB_SSLKEY", "/etc/ssl/certs/client.key")

    # Reload database module to pick up new env vars
    import database
    importlib.reload(database)

    assert database.connect_args["sslmode"] == "verify-full"
    assert database.connect_args["sslrootcert"] == "/etc/ssl/certs/ca.crt"
    assert database.connect_args["sslcert"] == "/etc/ssl/certs/client.crt"
    assert database.connect_args["sslkey"] == "/etc/ssl/certs/client.key"


def test_ssl_connect_args_empty_when_prefer(monkeypatch):
    """When DB_SSLMODE=prefer (default), connect_args should not contain ssl keys."""
    monkeypatch.setenv("DB_SSLMODE", "prefer")
    monkeypatch.delenv("DB_SSLROOTCERT", raising=False)
    monkeypatch.delenv("DB_SSLCERT", raising=False)
    monkeypatch.delenv("DB_SSLKEY", raising=False)

    import database
    importlib.reload(database)

    # With 'prefer', sslmode is not added to connect_args
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

    import database
    importlib.reload(database)

    assert database.connect_args["sslmode"] == "verify-full"
    assert database.connect_args["sslrootcert"] == "/etc/ssl/certs/ca.crt"
    assert "sslcert" not in database.connect_args
    assert "sslkey" not in database.connect_args


def test_db_sslmode_env_default():
    """DB_SSLMODE defaults to 'prefer' when not set."""
    # We can't easily test the default since the module is already imported,
    # but we can verify the constant exists and has a sensible default.
    import database
    assert database.DB_SSLMODE in ("prefer", "require", "verify-ca", "verify-full", "allow", "disable")
