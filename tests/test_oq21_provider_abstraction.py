# SPDX-License-Identifier: MIT
"""
OQ-21: LLM Provider Abstraction (SRS FR-3.15.1 / C8).

Verifies that the gateway selects the OpenAI-compatible backend purely from
configuration (LLM_PROVIDER) with no code changes, including:
  * the default offline 'mock' provider works without network or secrets,
  * OpenRouter requires OPENROUTER_API_KEY (fails closed otherwise),
  * Ollama resolves to its OpenAI-compatible /v1 shim without code change.
"""

import pytest

import ai.llm_gateway as gw


def test_mock_provider_default_offline(monkeypatch):
    """Default provider is 'mock' and produces deterministic offline output."""
    monkeypatch.setattr(gw, "PROVIDER", "mock")
    out = gw.generate_text("Summarize HR=80, SpO2=98", max_tokens=64)
    assert out and "[SIMULATED LLM OUTPUT" in out
    cfg = gw.get_provider_config()
    assert cfg["provider"] == "mock"
    assert cfg["model"] == "mock-model"


def test_provider_selection_openrouter_requires_key(monkeypatch):
    """Switching to openrouter without a key fails closed (C8 config-driven)."""
    monkeypatch.setattr(gw, "PROVIDER", "openrouter")
    monkeypatch.setattr(gw, "OPENROUTER_API_KEY", None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY_FILE", raising=False)
    with pytest.raises(RuntimeError):
        gw.generate_text("x")


def test_provider_selection_openrouter_with_key_resolves(monkeypatch):
    """openrouter with a key resolves a client for the configured model."""
    monkeypatch.setattr(gw, "PROVIDER", "openrouter")
    monkeypatch.setattr(gw, "OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setattr(gw, "OPENROUTER_MODEL", "anthropic/claude-3-sonnet")
    calls = {}

    def fake_build(base_url, api_key):
        calls["base_url"] = base_url
        calls["api_key"] = api_key
        return object()

    monkeypatch.setattr(gw, "_build_openai_client", fake_build)
    client = gw._resolve_client()
    assert client is not None
    assert calls["base_url"] == "https://openrouter.ai/api/v1"
    assert calls["api_key"] == "sk-test"
    assert gw._provider_model() == "anthropic/claude-3-sonnet"


def test_provider_abstraction_ollama_builds_v1_client(monkeypatch):
    """Ollama resolves to its OpenAI-compatible /v1 shim (no code change)."""
    monkeypatch.setattr(gw, "PROVIDER", "ollama")
    monkeypatch.setattr(gw, "OLLAMA_BASE_URL", "http://gpu:11434")
    monkeypatch.setattr(gw, "OLLAMA_MODEL", "llama3:70b")
    calls = {}

    def fake_build(base_url, api_key):
        calls["base_url"] = base_url
        calls["api_key"] = api_key
        return object()

    monkeypatch.setattr(gw, "_build_openai_client", fake_build)
    client = gw._resolve_client()
    assert client is not None
    assert calls["base_url"] == "http://gpu:11434/v1"
    assert gw._provider_model() == "llama3:70b"


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(gw, "PROVIDER", "bedrock")
    with pytest.raises(RuntimeError):
        gw._resolve_client()
