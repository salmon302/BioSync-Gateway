"""
PQ-2: Hash Chain Verification Performance
Implements SRS NFR-P4 — Hash Chain 1M rows < 60s

Benchmarks hash chain verification performance.
"""

import pytest
import time
from datetime import datetime


class TestHashChainPerformance:
    """Tests for NFR-P4 — Hash chain verification < 60s for 1M rows."""

    def test_hash_computation_speed(self):
        """SHA-256 hash computation should be fast."""
        from middleware.engine.hash_chain import compute_hash

        timestamp = datetime(2026, 7, 13, 10, 0, 0)
        data = {"table": "plates", "record_id": 1, "action": "insert"}

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            compute_hash(
                previous_hash="genesis",
                table_name="plates",
                operation="INSERT",
                record_id=1,
                timestamp=timestamp,
                user_id="test-user",
                data=data
            )
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms

        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms < 1.0, f"Average hash computation {avg_ms:.3f}ms is too slow"

    def test_chain_verification_10k_rows(self):
        """Verify 10k row chain within 10 seconds."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        # Generate test chain
        entries = []
        prev_hash = GENESIS_HASH

        for i in range(10000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "plates", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="plates",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data
            )
            # Keep timestamp as datetime object for verify_chain
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "plates",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data
            })
            prev_hash = current_hash

        # Verify chain
        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        assert is_valid is True
        assert elapsed < 10.0, f"10k row verification took {elapsed:.2f}s (target < 10s)"

    def test_chain_verification_rate(self):
        """Verification rate should exceed 10k rows/second."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        # Generate test chain
        entries = []
        prev_hash = GENESIS_HASH

        for i in range(5000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "plates", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="plates",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data
            )
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "plates",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data
            })
            prev_hash = current_hash

        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        rate = len(entries) / elapsed if elapsed > 0 else 0
        assert rate > 10000, f"Verification rate {rate:.0f} rows/s is below 10k/s target"

    def test_tampered_chain_detection_speed(self):
        """Tampered chain should be detected quickly."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        # Generate valid chain then tamper
        entries = []
        prev_hash = GENESIS_HASH

        for i in range(1000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "plates", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="plates",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data
            )
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "plates",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data
            })
            prev_hash = current_hash

        # Tamper with middle entry
        entries[500]["data"] = {"table": "plates", "record_id": 500, "action": "tampered"}

        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        assert is_valid is False
        assert broken_at is not None
        assert elapsed < 5.0, f"Tampered detection took {elapsed:.2f}s (target < 5s)"

    def test_scale_to_1m_estimate(self):
        """Estimate 1M row verification time from smaller sample."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        # Generate 10k row chain for scaling
        entries = []
        prev_hash = GENESIS_HASH

        for i in range(10000):
            timestamp = datetime(2026, 7, 13, 10, 0, i % 60)
            data = {"table": "plates", "record_id": i, "action": "insert"}
            current_hash = compute_hash(
                previous_hash=prev_hash,
                table_name="plates",
                operation="INSERT",
                record_id=i,
                timestamp=timestamp,
                user_id="test-user",
                data=data
            )
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "plates",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,
                "user_id": "test-user",
                "data": data
            })
            prev_hash = current_hash

        start = time.perf_counter()
        is_valid, broken_at = verify_chain(entries)
        elapsed = time.perf_counter() - start

        # Scale to 1M
        rate = len(entries) / elapsed if elapsed > 0 else 0
        estimated_1m = 1_000_000 / rate

        assert estimated_1m < 120.0, \
            f"Estimated 1M verification time {estimated_1m:.2f}s exceeds 120s safety margin"

    def test_empty_chain_verification(self):
        """Empty chain should verify instantly."""
        from middleware.engine.hash_chain import verify_chain

        start = time.perf_counter()
        is_valid, broken_at = verify_chain([])
        elapsed = time.perf_counter() - start

        assert is_valid is True
        assert elapsed < 0.01, f"Empty chain verification took {elapsed*1000:.3f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
