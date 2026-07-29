# SPDX-License-Identifier: MIT
"""
LLM/RAG Gateway - OpenAI-compatible provider abstraction (FR-3.15.1, C8).

Supports runtime selection between:
  * ``openrouter`` - remote OpenRouter API (OpenAI-compatible)
  * ``ollama``     - local Ollama OpenAI-compatible shim (``/v1``)
  * ``vllm``       - local/remote vLLM OpenAI-compatible server
  * ``mock``       - offline deterministic stub (DEFAULT; no network, for
                     qualification, CI, and air-gapped deployments)

Provider selection is configuration-driven (``LLM_PROVIDER``); switching
providers requires NO code changes (C8). The ``openai`` SDK is only imported
lazily when a real provider is selected, so this module is import-safe even
when the dependency is not installed (enables offline unit qualification).

Provider setup & key injection (NFR-S7 — secrets via env / Docker secrets)
--------------------------------------------------------------------------
OpenRouter (remote, requires a key)
    LLM_PROVIDER=openrouter
    OPENROUTER_API_KEY=sk-or-...            # direct env injection (local dev)
    # OR mount a Docker secret and point at the file (production, preferred):
    OPENROUTER_API_KEY_FILE=/run/secrets/openrouter_key
    OPENROUTER_MODEL=openai/gpt-4o-mini    # any OpenAI-compatible model id
    The key is resolved at call time: env value wins, then the secret file.
    Missing key -> RuntimeError (fail closed, C8).

Ollama (local, no key required)
    LLM_PROVIDER=ollama
    OLLAMA_BASE_URL=http://localhost:11434  # OpenAI-compatible /v1 shim
    OLLAMA_MODEL=llama3                     # any pulled Ollama model
    Ollama's shim accepts any non-empty key, so no secret is needed.

vLLM (local/remote, no key required)
    LLM_PROVIDER=vllm
    LLM_VLLM_BASE_URL=http://localhost:8000/v1
    LLM_VLLM_MODEL=meta-llama/Llama-3-8b-instruct
    Point at any OpenAI-compatible vLLM server you operate.

Regardless of provider, all inference is offloaded off the event loop via
:func:`generate_text_async` (FR-3.15.2 / C6) and persisted with full
provenance by :func:`persist_run` (FR-3.15.6).

Implements:
  SRS FR-3.15.1 - Provider abstraction (C8)
  SRS FR-3.15.2 - async isolation is provided by :func:`generate_text_async`
                  which offloads the blocking SDK call to a worker thread.
  SRS FR-3.15.6 - :func:`persist_run` stores full provenance to the
                  append-only ``llm_runs`` / ``clinical_text_outputs`` tables.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# --- Configuration (FR-3.15.1 / C8) -------------------------------------------
PROVIDER: str = os.getenv("LLM_PROVIDER", "mock").strip().lower()

OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY") or None
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

VLLM_BASE_URL: Optional[str] = os.getenv("LLM_VLLM_BASE_URL") or None
VLLM_MODEL: str = os.getenv("LLM_VLLM_MODEL", "meta-llama/Llama-3-8b-instruct")


def _resolve_openrouter_key() -> Optional[str]:
    """
    Resolve the OpenRouter API key from the environment or a Docker secret
    file (NFR-S7: secrets injected, never hard-coded).

    Precedence:
      1. The module-level ``OPENROUTER_API_KEY`` constant (captured at import
         and still settable by tests via monkeypatch — preserves prior API).
      2. The live ``OPENROUTER_API_KEY`` env var (call-time, so runtime
         provider switching works without a module reload).
      3. The file referenced by ``OPENROUTER_API_KEY_FILE`` (Docker secret
         mount — the production-preferred injection path).

    Returns ``None`` when none is set, which makes :func:`_resolve_client`
    fail closed for the ``openrouter`` provider (C8).
    """
    key = OPENROUTER_API_KEY
    if key:
        return key
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key
    key_file = os.getenv("OPENROUTER_API_KEY_FILE")
    if key_file:
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError as exc:
            logger.error("OPENROUTER_API_KEY_FILE set but unreadable: %s", exc)
    return None


def get_provider_config() -> Dict[str, Any]:
    """Return the resolved provider configuration (non-secret)."""
    return {
        "provider": PROVIDER,
        "model": _provider_model(),
        "openrouter_base_url": "https://openrouter.ai/api/v1" if PROVIDER == "openrouter" else None,
        "ollama_base_url": (OLLAMA_BASE_URL.rstrip("/") + "/v1") if PROVIDER == "ollama" else None,
        "vllm_base_url": VLLM_BASE_URL,
        "has_openrouter_key": bool(_resolve_openrouter_key()),
    }


def _provider_model() -> str:
    if PROVIDER == "openrouter":
        return OPENROUTER_MODEL
    if PROVIDER == "ollama":
        return OLLAMA_MODEL
    if PROVIDER == "vllm":
        return VLLM_MODEL
    return "mock-model"


def _build_openai_client(base_url: str, api_key: str):
    """Build an OpenAI-compatible client (lazy import of the SDK)."""
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError(
            "The 'openai' package is required for OpenAI-compatible providers. "
            "Install it with: pip install openai==1.55.0"
        ) from exc
    return OpenAI(base_url=base_url, api_key=api_key, timeout=60)


def _resolve_client():
    """Return an OpenAI-compatible client for the configured provider."""
    if PROVIDER == "openrouter":
        key = _resolve_openrouter_key()
        if not key:
            raise RuntimeError(
                "LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY (or "
                "OPENROUTER_API_KEY_FILE) (FR-3.15.1)."
            )
        return _build_openai_client("https://openrouter.ai/api/v1", key)
    if PROVIDER == "ollama":
        # Ollama's OpenAI-compatible shim accepts any non-empty key.
        return _build_openai_client(OLLAMA_BASE_URL.rstrip("/") + "/v1", "ollama")
    if PROVIDER == "vllm":
        if not VLLM_BASE_URL:
            raise RuntimeError(
                "LLM_PROVIDER=vllm requires LLM_VLLM_BASE_URL (FR-3.15.1)."
            )
        return _build_openai_client(VLLM_BASE_URL.rstrip("/"), "vllm")
    if PROVIDER == "mock":
        return None
    raise RuntimeError(
        f"Unknown LLM_PROVIDER '{PROVIDER}'. Expected one of: "
        "openrouter | ollama | vllm | mock."
    )


def _mock_generate(prompt: str, max_tokens: int = 256) -> str:
    """Deterministic, offline synthesis stub (no network)."""
    summary = " ".join(prompt.split())[:160]
    return (
        "[SIMULATED LLM OUTPUT - provider=mock]\n"
        f"requested_max_tokens={max_tokens}\n"
        f"prompt_summary: {summary}\n"
        "Synthesized clinical narrative (simulated): patient physiologically "
        "stable within expected bounds; no acute intervention indicated; "
        "continue routine monitoring."
    )


def generate_text(
    prompt: str,
    max_tokens: int = 256,
    temperature: float = 0.2,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """
    Generate text from ``prompt`` using the configured provider.

    Returns the generated string, or raises on provider/transport failure.
    The signature is intentionally compatible with the lazy import in
    ``simulation/mrd_sandbox.py`` (FR-3.15 / FR-3.14.4), which treats any
    error as "narrative unavailable" and returns ``None``.

    Implements SRS FR-3.15.1 (provider abstraction).
    """
    provider_model = model or _provider_model()
    if PROVIDER == "mock":
        return _mock_generate(prompt, max_tokens=max_tokens)
    client = _resolve_client()
    try:
        resp = client.chat.completions.create(
            model=provider_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        content = resp.choices[0].message.content
        return content.strip() if isinstance(content, str) else content
    except Exception as exc:  # transport/provider errors surface to caller
        logger.error("LLM generation failed (provider=%s): %s", PROVIDER, exc)
        raise


async def generate_text_async(
    prompt: str,
    max_tokens: int = 256,
    temperature: float = 0.2,
    model: Optional[str] = None,
    **kwargs: Any,
) -> Optional[str]:
    """
    Async wrapper that offloads the (blocking) SDK call to a worker thread so
    the FastAPI event loop is never blocked (FR-3.15.2 / C6).

    Used by the AI route BackgroundTasks.
    """
    return await asyncio.to_thread(
        generate_text, prompt, max_tokens, temperature, model, **kwargs
    )


def persist_run(
    db,
    prompt: str,
    text: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    template_id: Optional[str] = None,
    source_data: Optional[Any] = None,
    text_type: Optional[str] = None,
    scenario_run_id: Optional[int] = None,
    max_tokens: int = 256,
    temperature: float = 0.2,
) -> Any:
    """
    Persist an LLM run and its generated text with full provenance to the
    append-only ``llm_runs`` and ``clinical_text_outputs`` tables (FR-3.15.6).

    Returns the persisted ``ClinicalTextOutput`` ORM instance.

    Note: both tables are append-only (BEFORE UPDATE/DELETE triggers); this
    helper only ever INSERTs.
    """
    from uuid import uuid4

    from models import ClinicalTextOutput, LlmRun

    prov = provider or PROVIDER
    prov_model = model or _provider_model()

    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    source_data_hash = None
    if source_data is not None:
        try:
            serialized = json.dumps(source_data, sort_keys=True, default=str)
        except TypeError:
            serialized = str(source_data)
        source_data_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    llm_run = LlmRun(
        run_uid=str(uuid4()),
        provider=prov,
        model_id=prov_model,
        prompt_hash=prompt_hash,
        template_id=template_id,
        source_data_hash=source_data_hash,
        request_payload={"max_tokens": max_tokens, "temperature": temperature},
        response_metadata={"chars": len(text), "provider": prov},
        scenario_run_id=scenario_run_id,
    )
    db.add(llm_run)
    db.flush()  # populate llm_run.id for FK from clinical_text_outputs

    output = ClinicalTextOutput(
        output_uid=str(uuid4()),
        scenario_run_id=scenario_run_id,
        llm_run_id=llm_run.id,
        text_type=text_type or "narrative",
        content=text,
        provenance={
            "model_id": prov_model,
            "provider": prov,
            "prompt_hash": prompt_hash,
            "template_id": template_id,
            "source_data_hash": source_data_hash,
        },
    )
    db.add(output)
    db.flush()
    return output
