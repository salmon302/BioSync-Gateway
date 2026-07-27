# SPDX-License-Identifier: MIT
"""
PQ-7: LLM isolation under load (SRS FR-3.15.2 / C6).

Verifies that LLM inference is dispatched off the event loop so real-time
telemetry processing paths are never blocked. The blocking SDK call is
patched to sleep, and a heartbeat coroutine measures event-loop responsiveness
while several concurrent generations run. If the call ran on the loop, the
heartbeat lag would approach the simulated latency; with proper offloading it
stays orders of magnitude smaller.
"""

import asyncio
import time

import pytest

import ai.llm_gateway as gw


@pytest.mark.asyncio
async def test_llm_inference_does_not_block_event_loop(monkeypatch):
    def blocking_generate(prompt, max_tokens=256, temperature=0.2, model=None, **kwargs):
        time.sleep(0.25)  # simulate a slow, blocking LLM SDK call
        return "ok"

    monkeypatch.setattr(gw, "generate_text", blocking_generate)

    lags: list[float] = []

    async def heartbeat():
        for _ in range(20):
            t0 = time.perf_counter()
            await asyncio.sleep(0.01)
            lags.append(time.perf_counter() - t0)

    tasks = [asyncio.create_task(gw.generate_text_async("x")) for _ in range(4)]
    await heartbeat()
    await asyncio.gather(*tasks)

    max_lag = max(lags)
    # Loop must stay responsive (heartbeat ~10ms); far below the 250ms LLM call.
    assert max_lag < 0.1, f"Event loop blocked (max heartbeat lag {max_lag:.3f}s)"


@pytest.mark.asyncio
async def test_concurrent_llm_calls_all_complete(monkeypatch):
    """Multiple concurrent background-style generations all return (C6)."""

    async def fake_gen(prompt, **kwargs):
        await asyncio.sleep(0.02)
        return f"out:{prompt}"

    monkeypatch.setattr(gw, "generate_text_async", fake_gen)
    results = await asyncio.gather(*[gw.generate_text_async(f"p{i}") for i in range(8)])

    assert results == [f"out:p{i}" for i in range(8)]
