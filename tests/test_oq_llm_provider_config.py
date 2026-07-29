# SPDX-License-Identifier: MIT
"""
R7 config verification -- LLM key injection (SRS NFR-S7).

Unit tests (no network) proving that the OpenRouter API key is resolved from
the environment or a Docker secret file, and that the gateway fails closed
when neither is present. Mirrors the JWT_SECRET_FILE injection pattern in
middleware/api/auth.py.
"""

import os

import pytest

import ai.llm_gateway as gw


@pytest.fixture
def clean_openrouter_env(monkeypatch):
    """Ensure both key sources are unset and the module constant is None."""
    monkeypatch.setattr(gw, "OPENROUTER_API_KEY", None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_FILE", raising=False)
    yield


def test_key_from_env(clean_openrouter_env, monkeypatch):
    """OPENROUTER_API_KEY env value is resolved at call time (C8 runtime switch)."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-123")
    assert gw._resolve_openrouter_key() == "sk-env-123"


def test_key_from_secret_file(clean_openrouter_env, monkeypatch, tmp_path):
    """OPENROUTER_API_KEY_FILE (Docker secret mount) is read when env is absent."""
    secret = tmp_path / "openrouter_key"
    secret.write_text("sk-file-456\n")
    monkeypatch.setenv("OPENROUTER_API_KEY_FILE", str(secret))
    assert gw._resolve_openrouter_key() == "sk-file-456"


def test_env_precedence_over_file(clean_openrouter_env, monkeypatch, tmp_path):
    """Live env value wins over the secret file (matches .env.example docs)."""
    secret = tmp_path / "openrouter_key"
    secret.write_text("sk-file-456")
    monkeypatch.setenv("OPENROUTER_API_KEY_FILE", str(secret))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-123")
    assert gw._resolve_openrouter_key() == "sk-env-123"


def test_no_key_resolves_none(clean_openrouter_env):
    """No key source -> None, which makes the openrouter provider fail closed."""
    assert gw._resolve_openrouter_key() is None


def test_config_reports_key_presence(clean_openrouter_env, monkeypatch):
    """get_provider_config() reflects whether a key is injected (no secret leak)."""
    monkeypatch.setattr(gw, "PROVIDER", "openrouter")
    assert gw.get_provider_config()["has_openrouter_key"] is False
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-123")
    assert gw.get_provider_config()["has_openrouter_key"] is True
