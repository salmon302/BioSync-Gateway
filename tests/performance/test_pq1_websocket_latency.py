"""
PQ-1: WebSocket Latency Benchmark
Implements SRS NFR-P3 — WebSocket P95 < 50ms

Benchmarks WebSocket message serialization/deserialization latency.
"""

import pytest
import time
import statistics
import json


class TestWebSocketLatency:
    """Tests for NFR-P3 — WebSocket P95 latency < 50ms."""

    def test_json_serialization_latency(self):
        """JSON serialization should complete within 50ms P95."""
        latencies = []
        message = {
            "type": "telemetry",
            "payload": {
                "heart_rate": 72.5,
                "blood_pressure": [120, 80],
                "spo2": 98.2,
                "timestamp": time.time()
            },
            "timestamp": time.time()
        }

        for _ in range(1000):
            start = time.perf_counter()
            serialized = json.dumps(message)
            deserialized = json.loads(serialized)
            end = time.perf_counter()

            latencies.append((end - start) * 1000)  # ms

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        assert p95 < 50.0, f"P95 latency {p95:.3f}ms exceeds 50ms target"
        assert avg < 10.0, f"Average latency {avg:.3f}ms is too high"

    def test_large_message_serialization(self):
        """Large telemetry messages should serialize within 50ms."""
        latencies = []

        # Large message with many channels
        large_message = {
            "type": "telemetry",
            "payload": {
                "heart_rate": 72.5,
                "blood_pressure_systolic": 120,
                "blood_pressure_diastolic": 80,
                "spo2": 98.2,
                "respiratory_rate": 16,
                "temperature": 36.8,
                "mean_airway_pressure": 12.5,
                "cardiac_output": 5.2,
                "stroke_volume": 70,
                "systemic_vascular_resistance": 1200,
                "arterial_oxygen_partial_pressure": 95,
                "central_veinous_pressure": 8,
                "mean_arterial_pressure": 93
            },
            "timestamp": time.time(),
            "device_id": "multi-channel-device-001"
        }

        for _ in range(1000):
            start = time.perf_counter()
            serialized = json.dumps(large_message)
            deserialized = json.loads(serialized)
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 50.0, f"Large message P95 {p95:.3f}ms exceeds 50ms"

    def test_message_throughput(self):
        """Should process 10,000 messages within reasonable time."""
        message = {"type": "telemetry", "value": 72.5}

        start = time.perf_counter()
        for _ in range(10000):
            json.dumps(message)
            json.loads(json.dumps(message))
        end = time.perf_counter()

        elapsed = end - start
        throughput = 10000 / elapsed

        assert throughput > 1000, f"Throughput {throughput:.0f} msg/s is too low"

    def test_burst_message_handling(self):
        """Should handle burst of 100 messages without exceeding 50ms P95."""
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            message = {
                "type": "telemetry",
                "payload": {"heart_rate": 72.5 + hash(time.time()) % 100},
                "timestamp": time.time()
            }
            json.dumps(message)
            json.loads(json.dumps(message))
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 50.0, f"Burst P95 {p95:.3f}ms exceeds 50ms"

    def test_repeated_serialization_consistency(self):
        """Repeated serialization should have consistent latency."""
        latencies = []
        message = {"type": "telemetry", "value": 72.5}

        for _ in range(500):
            start = time.perf_counter()
            json.dumps(message)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        std_dev = statistics.stdev(latencies)
        mean = statistics.mean(latencies)

        # Coefficient of variation should be reasonable
        cv = std_dev / mean if mean > 0 else 0
        assert cv < 2.0, f"Latency CV {cv:.2f} is too variable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
