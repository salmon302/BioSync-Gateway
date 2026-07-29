# SPDX-License-Identifier: MIT
"""
R7 verification -- real LLM integration test against a local Ollama.

This is the concrete "add integration test against a local Ollama" deliverable
from REMAINING_WORK Phase 3 (R7). It proves that setting LLM_PROVIDER=ollama
against a running Ollama instance returns GENUINE (non-mock) generated text,
closing the gap where the gateway previously only defaulted to `mock`.

The test is SKIPPED unless BIOSYNC_OLLAMA_INTEGRATION=1, and additionally
skips (rather than fails) when no Ollama server is reachable at the configured
base URL, so it never breaks collection or CI on machines without Ollama.

Run manually against a local Ollama (model `llama3` pulled):
    ollama pull llama3
    BIOSYNC_OLLAMA_INTEGRATION=1 pytest tests/test_oq_llm_ollama_integration.py -q
"""

import importlib
import os

import pytest

import ai.llm_gateway as gw


@pytest.mark.integration
@pytest.mark.external
@pytest.mark.ollama
@pytest.mark.skipif(
    not os.getenv("BIOSYNC_OLLAMA_INTEGRATION"),
    reason="Set BIOSYNC_OLLAMA_INTEGRATION=1 to run the real Ollama integration test.",
)
def test_ollama_real_generation():
    """LLM_PROVIDER=ollama must produce real text (not the mock stub)."""
    base_url = (
        os.getenv("BIOSYNC_OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    model = (
        os.getenv("BIOSYNC_OLLAMA_MODEL")
        or os.getenv("OLLAMA_MODEL", "llama3")
    )

    # --- Reachability pre-check: skip gracefully if Ollama is not running. ---
    try:
        import urllib.request

        with urllib.request.urlopen(
            base_url.rstrip("/") + "/api/tags", timeout=5
        ) as resp:
            if resp.status != 200:
                pytest.skip(f"Ollama at {base_url} returned HTTP {resp.status}")
    except Exception as exc:  # network down / server absent
        pytest.skip(f"Ollama not reachable at {base_url}: {exc}")

    # --- Switch provider to ollama at runtime and reload config. ---
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["OLLAMA_BASE_URL"] = base_url
    os.environ["OLLAMA_MODEL"] = model
    importlib.reload(gw)

    # --- Config resolves to the real Ollama provider. ---
    cfg = gw.get_provider_config()
    assert cfg["provider"] == "ollama", cfg
    assert cfg["model"] == model, cfg
    assert cfg["ollama_base_url"].endswith("/v1"), cfg

    # --- A real generation: assert it is non-empty AND not the mock stub. ---
    prompt = (
        "You are a lab instrument. Reply with exactly the single word: PONG"
    )
    out = gw.generate_text(prompt, max_tokens=8, temperature=0)
    assert out is not None and out.strip(), "Ollama returned empty text"
    assert "[SIMULATED LLM OUTPUT" not in out, (
        "Ollama test hit the mock provider instead of the real Ollama backend"
    )
