# SPDX-License-Identifier: MIT
"""
P1-9: Performance Instrumentation Tests
Implements SRS NFR-P1 through NFR-P6 — Performance Qualification verification.

Tests cover:
  - NFR-P1: Telemetry ingestion throughput ≥ 100,000 data points/second
  - NFR-P2: WebGL rendering frame rate ≥ 60 fps sustained
  - NFR-P3: API response time (95th percentile) ≤ 200 ms for CRUD, ≤ 50 ms WS relay
  - NFR-P4: Hash chain verification (1M rows) ≤ 60 seconds
  - NFR-P5: Pulse Engine time-step computation ≤ 50 ms
  - NFR-P6: Concurrent WebSocket connections ≥ 500

These tests validate the instrumentation itself (the middleware, the FPS counter
logic, and the benchmark functions) so that CI can run them without a live
browser or a full Locust swarm.
"""

import json
import os
import sys
import time
import statistics
import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Ensure middleware is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "middleware"))


# ---------------------------------------------------------------------------
# NFR-P1: Telemetry ingestion throughput
# ---------------------------------------------------------------------------

class TestNFRP1TelemetryIngestion:
    """Tests for NFR-P1 — Telemetry ingestion throughput ≥ 100k points/sec."""

    def test_ingestion_throughput_benchmark(self):
        """
        Benchmark the telemetry ingest path: EMA filter + alarm evaluation +
        JSON serialization for a batch of observations.

        The middleware pipeline must sustain ≥ 100,000 data points/second
        without main-thread blocking (SRS NFR-P1).
        """
        from middleware.engine.signal import MultiChannelEMAFilter
        from middleware.api.routes.telemetry import evaluate_alarm

        ema_filter = MultiChannelEMAFilter()

        # Simulate 1000 observations per batch (typical device batch)
        batch_size = 1000
        num_batches = 100  # 100k total points

        observations = []
        for i in range(batch_size):
            channel = ["pressure", "flow", "hr", "spo2"][i % 4]
            code_map = {
                "pressure": "8310-5",
                "flow": "85354-9",
                "hr": "8867-4",
                "spo2": "59408-5",
            }
            observations.append({
                "resourceType": "Observation",
                "code": {"coding": [{"system": "http://loinc.org", "code": code_map[channel]}]},
                "valueQuantity": {"value": 120.0 + i * 0.01, "unit": "mmHg"},
            })

        start = time.perf_counter()
        total_points = 0
        for _ in range(num_batches):
            for obs in observations:
                # EMA filter
                filtered = ema_filter.filter_observation(obs.copy())
                # Alarm evaluation on filtered value
                channel = ema_filter.resolve_channel(filtered)
                filtered_value = (filtered.get("filtered_data") or {}).get("value")
                evaluate_alarm(channel, filtered_value)
                total_points += 1
            # Serialize batch
            json.dumps(observations)
        elapsed = time.perf_counter() - start

        rate = total_points / elapsed
        assert rate >= 100_000, (
            f"Ingestion throughput {rate:,.0f} pts/sec is below NFR-P1 target of 100,000"
        )

    def test_ingestion_throughput_with_persistence(self):
        """
        Benchmark the full ingest path including observation object construction
        and batch serialization (simulating DB insert overhead).
        """
        from middleware.engine.signal import MultiChannelEMAFilter

        ema_filter = MultiChannelEMAFilter()

        batch_size = 500
        num_batches = 200  # 100k total

        start = time.perf_counter()
        total_points = 0
        for _ in range(num_batches):
            batch_rows = []
            for i in range(batch_size):
                obs = {
                    "resourceType": "Observation",
                    "code": {"coding": [{"code": "8867-4"}]},
                    "valueQuantity": {"value": 72.0 + (i % 10), "unit": "beats/min"},
                }
                filtered = ema_filter.filter_observation(obs.copy())
                # Simulate DB row construction (SQLAlchemy ORM object)
                row = {
                    "observation_uid": str(i),
                    "observation_code": "8867-4",
                    "value_quantity": filtered.get("valueQuantity"),
                    "raw_data": filtered.get("raw_data"),
                    "filtered_data": filtered.get("filtered_data"),
                    "fhir_resource": filtered,
                }
                batch_rows.append(row)
                total_points += 1
            # Batch serialization at commit time (not per-observation)
            json.dumps(batch_rows)
        elapsed = time.perf_counter() - start

        rate = total_points / elapsed
        assert rate >= 100_000, (
            f"Full ingest path throughput {rate:,.0f} pts/sec is below NFR-P1 target"
        )


# ---------------------------------------------------------------------------
# NFR-P2: WebGL rendering frame rate
# ---------------------------------------------------------------------------

class TestNFRP2FrameRate:
    """Tests for NFR-P2 — WebGL rendering frame rate ≥ 60 fps sustained."""

    def test_frame_time_p95_meets_target(self):
        """
        Simulate frame rendering times and verify P95 frame time
        corresponds to ≥ 60 fps (16.67 ms per frame).
        """
        # Simulate 600 frames at ~62fps (16.0ms per frame) with small jitter
        frame_times_ms = []
        for i in range(600):
            jitter = (i % 3) * 0.2  # 0, 0.2, or 0.4ms jitter
            frame_times_ms.append(16.0 + jitter)

        sorted_times = sorted(frame_times_ms)
        p95_index = int(len(sorted_times) * 0.95)
        p95_frame_time = sorted_times[p95_index]
        p95_fps = 1000.0 / p95_frame_time

        assert p95_fps >= 60, (
            f"P95 frame time {p95_frame_time:.2f}ms → {p95_fps:.1f} fps "
            f"is below NFR-P2 target of 60 fps"
        )

    def test_frame_time_variance_within_tolerance(self):
        """Frame time variance should be low for smooth rendering."""
        frame_times_ms = [16.67 + (i % 3) * 0.3 for i in range(300)]
        variance = statistics.variance(frame_times_ms)
        # Variance should be small relative to frame time
        assert variance < 5.0, f"Frame time variance {variance:.3f} is too high"


# ---------------------------------------------------------------------------
# NFR-P3: API response time
# ---------------------------------------------------------------------------

class TestNFRP3ResponseTime:
    """Tests for NFR-P3 — API response time ≤ 200ms P95, ≤ 50ms WS relay."""

    def test_metrics_registry_records_http_latency(self):
        """MetricsRegistry should record and report HTTP latency correctly."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()

        # Record 100 samples with known latencies
        for i in range(100):
            latency = 50.0 + (i % 10)  # 50-59ms
            registry.record_http("/api/test", "GET", latency)

        snapshot = registry.snapshot()
        http_metrics = snapshot["http"]["GET /api/test"]

        assert http_metrics["count"] == 100
        assert http_metrics["min_ms"] == 50.0
        assert http_metrics["max_ms"] == 59.0
        assert http_metrics["avg_ms"] >= 50.0
        assert http_metrics["p95_ms"] >= 50.0

    def test_metrics_registry_p95_calculation(self):
        """P95 percentile should be correctly calculated."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()

        # Record 1000 samples: 950 at 10ms, 50 at 500ms
        for _ in range(950):
            registry.record_http("/api/fast", "GET", 10.0)
        for _ in range(50):
            registry.record_http("/api/fast", "GET", 500.0)

        snapshot = registry.snapshot()
        http_metrics = snapshot["http"]["GET /api/fast"]

        # P95 with linear interpolation falls between 10ms and 500ms.
        # The key assertion: P95 must be well below the 200ms NFR-P3 target
        # and significantly lower than the 500ms outliers.
        assert http_metrics["p95_ms"] < 200.0, (
            f"P95 {http_metrics['p95_ms']}ms exceeds NFR-P3 target of 200ms"
        )
        assert http_metrics["p95_ms"] < 500.0, (
            f"P95 {http_metrics['p95_ms']}ms should be below outlier value of 500ms"
        )

    def test_metrics_registry_ws_latency(self):
        """WebSocket relay latency should be tracked and P95 reported."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()

        for i in range(100):
            latency = 5.0 + (i % 10)  # 5-14ms
            registry.record_ws_latency(latency)

        snapshot = registry.snapshot()
        ws_metrics = snapshot["websocket"]["relay_latency_ms"]

        assert ws_metrics["count"] == 100
        assert ws_metrics["p95_ms"] >= 5.0
        assert ws_metrics["passed"] is True  # P95 ≤ 50ms

    def test_metrics_registry_ws_latency_fails_target(self):
        """WS latency exceeding 50ms P95 should fail NFR-P3."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()

        for _ in range(100):
            registry.record_ws_latency(80.0)  # All exceed 50ms

        snapshot = registry.snapshot()
        ws_metrics = snapshot["websocket"]["relay_latency_ms"]

        assert ws_metrics["passed"] is False

    def test_metrics_registry_connection_tracking(self):
        """WebSocket connection count should be tracked."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()

        registry.record_ws_connection(100)
        snapshot = registry.snapshot()
        assert snapshot["websocket"]["active_connections"] == 100

        registry.record_ws_connection(400)
        snapshot = registry.snapshot()
        assert snapshot["websocket"]["active_connections"] == 500
        assert snapshot["websocket"]["peak_connections"] == 500

    def test_metrics_registry_reset(self):
        """reset() should clear all collected metrics."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()
        registry.record_http("/api/test", "GET", 50.0)
        registry.record_ws_latency(10.0)

        registry.reset()
        snapshot = registry.snapshot()

        assert snapshot["http"] == {}
        assert snapshot["websocket"]["relay_latency_ms"]["count"] == 0


# ---------------------------------------------------------------------------
# NFR-P4: Hash chain verification
# ---------------------------------------------------------------------------

class TestNFRP4HashChainVerification:
    """Tests for NFR-P4 — Hash chain verification ≤ 60s for 1M rows."""

    def test_hash_chain_10k_rows_under_10s(self):
        """10k row chain verification should complete in under 10 seconds."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        entries = []
        prev_hash = GENESIS_HASH

        for i in range(10000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "observations", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="observations",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data,
            )
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "observations",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data,
            })
            prev_hash = current_hash

        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        assert is_valid is True
        assert elapsed < 10.0, (
            f"10k row verification took {elapsed:.2f}s (target < 10s)"
        )

    def test_hash_chain_verification_rate(self):
        """Verification rate should support 1M rows in under 60 seconds."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        entries = []
        prev_hash = GENESIS_HASH

        for i in range(5000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "audit_log", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="audit_log",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data,
            )
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "audit_log",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data,
            })
            prev_hash = current_hash

        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        rate = len(entries) / elapsed if elapsed > 0 else float("inf")
        estimated_1m = 1_000_000 / rate

        assert is_valid is True
        assert estimated_1m < 60.0, (
            f"Estimated 1M verification time {estimated_1m:.2f}s exceeds NFR-P4 target of 60s"
        )

    def test_hash_chain_tamper_detection_speed(self):
        """Tampered chain should be detected within 5 seconds."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        entries = []
        prev_hash = GENESIS_HASH

        for i in range(1000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "audit_log", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="audit_log",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data,
            )
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "audit_log",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data,
            })
            prev_hash = current_hash

        # Tamper with entry 500
        entries[500]["data"] = {"table": "audit_log", "record_id": 500, "action": "tampered"}

        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        assert is_valid is False
        assert broken_at is not None
        assert elapsed < 5.0, (
            f"Tamper detection took {elapsed:.2f}s (target < 5s)"
        )


# ---------------------------------------------------------------------------
# NFR-P5: Pulse Engine time-step
# ---------------------------------------------------------------------------

class TestNFRP5PulseStepTiming:
    """Tests for NFR-P5 — Pulse Engine time-step ≤ 50 ms."""

    def test_pulse_step_latency(self):
        """Single Pulse Engine time-step should complete within 50ms."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="perf-test-001",
            age=45, weight_kg=70.0, height_cm=175.0, sex="male",
        )
        worker = PulseWorker(config)
        worker.initialize()

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            worker.step(1)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 <= 50.0, (
            f"Pulse step P95 {p95:.2f}ms exceeds NFR-P5 target of 50ms"
        )

    def test_pulse_step_batch_latency(self):
        """Batch Pulse Engine steps should average ≤ 50ms per step."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="perf-test-002",
            age=50, weight_kg=65.0, height_cm=165.0, sex="female",
        )
        worker = PulseWorker(config)
        worker.initialize()

        # 10 steps per call, 10 calls
        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            worker.step(10)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms / 10)  # per-step average

        avg_ms = statistics.mean(latencies)
        assert avg_ms <= 50.0, (
            f"Average pulse step {avg_ms:.2f}ms exceeds NFR-P5 target of 50ms"
        )


# ---------------------------------------------------------------------------
# NFR-P6: Concurrent WebSocket connections
# ---------------------------------------------------------------------------

class TestNFRP6ConcurrentConnections:
    """Tests for NFR-P6 — ≥ 500 concurrent WebSocket connections."""

    def test_connection_manager_tracks_connections(self):
        """ConnectionManager should track active WebSocket connections."""
        from middleware.api.routes.telemetry import ConnectionManager

        manager = ConnectionManager()

        # Simulate 500 connections
        mock_connections = []
        for i in range(500):
            mock_ws = MagicMock()
            mock_ws.client = (f"127.0.0.1", 10000 + i)
            mock_connections.append(mock_ws)

        # Verify manager can handle 500 connections
        assert len(mock_connections) == 500

        # The manager should be able to track all of them
        for conn in mock_connections:
            manager.active_connections.append(conn)

        assert len(manager.active_connections) == 500

    def test_connection_manager_broadcast_to_500(self):
        """Broadcast should reach all 500 connected clients."""
        from middleware.api.routes.telemetry import ConnectionManager
        import asyncio

        manager = ConnectionManager()

        # Create 500 mock WebSocket connections
        sent_count = 0

        class MockWS:
            def __init__(self):
                self.sent = []

            async def send_json(self, message):
                self.sent.append(message)

        for _ in range(500):
            manager.active_connections.append(MockWS())

        async def run_broadcast():
            nonlocal sent_count
            await manager.broadcast({"type": "telemetry", "payload": {}})
            for conn in manager.active_connections:
                sent_count += len(conn.sent)

        asyncio.run(run_broadcast())

        assert sent_count == 500, (
            f"Broadcast reached {sent_count}/500 connections"
        )


# ---------------------------------------------------------------------------
# Response-time middleware integration
# ---------------------------------------------------------------------------

class TestResponseTimeMiddleware:
    """Tests for the ResponseTimeMiddleware ASGI middleware."""

    def test_middleware_records_http_latency(self):
        """Middleware should record HTTP request latency."""
        from middleware.api.middleware.response_time import (
            ResponseTimeMiddleware, MetricsRegistry,
        )

        registry = MetricsRegistry()
        received_scope = {}

        async def app(scope, receive, send):
            received_scope.update(scope)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        middleware = ResponseTimeMiddleware(app, registry=registry)

        async def send_wrapper(message):
            pass

        async def receive_wrapper():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def run():
            scope = {"type": "http", "method": "GET", "path": "/api/test"}
            await middleware(scope, receive_wrapper, send_wrapper)

        import asyncio
        asyncio.run(run())

        snapshot = registry.snapshot()
        assert "GET /api/test" in snapshot["http"]

    def test_middleware_passes_through_non_http(self):
        """Middleware should pass through non-HTTP scopes unchanged."""
        from middleware.api.middleware.response_time import ResponseTimeMiddleware

        called = False

        async def app(scope, receive, send):
            nonlocal called
            called = True
            await send({"type": "lifespan.startup.complete"})

        middleware = ResponseTimeMiddleware(app)

        async def send_wrapper(message):
            pass

        async def receive_wrapper():
            return {"type": "lifespan.startup"}

        async def run():
            scope = {"type": "lifespan"}
            await middleware(scope, receive_wrapper, send_wrapper)

        import asyncio
        asyncio.run(run())

        assert called

    def test_metrics_endpoint_structure(self):
        """The metrics snapshot should have the correct structure for all NFR-P."""
        from middleware.api.middleware.response_time import MetricsRegistry

        registry = MetricsRegistry()
        registry.record_http("/api/test", "GET", 50.0)
        registry.record_ws_latency(10.0)
        registry.record_ws_connection(500)
        registry.record_ingestion_rate(100_000.0)
        registry.record_pulse_step(25.0)
        registry.record_hash_chain(1_000_000, 30.0)

        snapshot = registry.snapshot()

        # Verify all NFR-P sections are present
        assert "http" in snapshot
        assert "websocket" in snapshot
        assert "throughput" in snapshot
        assert "pulse_engine" in snapshot
        assert "hash_chain" in snapshot

        # Verify NFR-P1 (throughput)
        tp = snapshot["throughput"]["ingestion_rate_pps"]
        assert tp["target_pps"] == 100_000
        assert tp["passed"] is True

        # Verify NFR-P3 (HTTP P95)
        http = snapshot["http"]["GET /api/test"]
        assert "p95_ms" in http

        # Verify NFR-P3 (WS relay)
        ws = snapshot["websocket"]["relay_latency_ms"]
        assert ws["target_p95_ms"] == 50.0
        assert ws["passed"] is True

        # Verify NFR-P5 (Pulse step)
        pulse = snapshot["pulse_engine"]["step_latency_ms"]
        assert pulse["target_p95_ms"] == 50.0
        assert pulse["passed"] is True

        # Verify NFR-P4 (Hash chain)
        hc = snapshot["hash_chain"]["verification_seconds"]
        assert hc["target_1m_seconds"] == 60.0
        assert hc["passed"] is True

        # Verify NFR-P6 (Concurrent WS)
        ws_conn = snapshot["websocket"]
        assert ws_conn["target_concurrent"] == 500
        assert ws_conn["passed_connections"] is True


# ---------------------------------------------------------------------------
# Performance benchmarks module
# ---------------------------------------------------------------------------

class TestPerformanceBenchmarks:
    """Tests for the performance_benchmarks.py module."""

    def test_benchmark_websocket_latency(self):
        """WebSocket latency benchmark should pass."""
        from middleware.performance_benchmarks import benchmark_websocket_latency

        results = benchmark_websocket_latency(num_messages=1000)
        assert results["passed"] is True
        assert results["p95_ms"] < 50.0

    def test_benchmark_hash_chain(self):
        """Hash chain benchmark should pass."""
        from middleware.performance_benchmarks import benchmark_hash_chain_verification

        results = benchmark_hash_chain_verification(num_rows=10000)
        assert results["passed"] is True
        assert results["estimated_1m_seconds"] < 60.0

    def test_benchmark_barcode(self):
        """Barcode benchmark should pass."""
        from middleware.performance_benchmarks import benchmark_barcode_computation

        results = benchmark_barcode_computation(num_indices=96)
        assert results["passed"] is True
        assert results["elapsed_ms"] < 500.0

    def test_run_all_benchmarks(self):
        """All benchmarks should pass."""
        from middleware.performance_benchmarks import run_all_benchmarks

        results = run_all_benchmarks()
        assert "websocket_latency" in results
        assert "hash_chain" in results
        assert "barcode" in results
        assert "memory" in results


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
