"""
O-13: Hash Chain API Integration
Implements SRS FR-3.8.3 — Cryptographic Hash Chain

Verifies hash chain compute and verify operations via API endpoints.
"""

import pytest
from datetime import datetime


class TestHashChainAPI:
    """Tests for FR-3.8.3 — Hash chain API integration."""

    def test_compute_hash_deterministic(self):
        """Hash computation should be deterministic for same inputs."""
        from middleware.engine.hash_chain import compute_hash

        timestamp = datetime(2026, 7, 13, 10, 0, 0)
        data = {"table": "plates", "record_id": 1, "action": "insert"}

        hash1 = compute_hash(
            previous_hash="genesis",
            table_name="plates",
            operation="INSERT",
            record_id=1,
            timestamp=timestamp,
            user_id="test-user",
            data=data
        )

        hash2 = compute_hash(
            previous_hash="genesis",
            table_name="plates",
            operation="INSERT",
            record_id=1,
            timestamp=timestamp,
            user_id="test-user",
            data=data
        )

        assert hash1 == hash2, "Same inputs should produce same hash"
        assert len(hash1) == 64, "SHA-256 hash should be 64 hex characters"

    def test_compute_hash_different_inputs(self):
        """Different inputs should produce different hashes."""
        from middleware.engine.hash_chain import compute_hash

        timestamp = datetime(2026, 7, 13, 10, 0, 0)
        data = {"table": "plates", "record_id": 1, "action": "insert"}

        hash1 = compute_hash(
            previous_hash="genesis",
            table_name="plates",
            operation="INSERT",
            record_id=1,
            timestamp=timestamp,
            user_id="user1",
            data=data
        )

        hash2 = compute_hash(
            previous_hash="genesis",
            table_name="plates",
            operation="INSERT",
            record_id=2,  # Different record_id
            timestamp=timestamp,
            user_id="user1",
            data=data
        )

        assert hash1 != hash2, "Different record_id should produce different hash"

    def test_compute_hash_chain_links(self):
        """Hash chain should link entries via previous_hash."""
        from middleware.engine.hash_chain import compute_hash

        timestamp1 = datetime(2026, 7, 13, 10, 0, 0)
        timestamp2 = datetime(2026, 7, 13, 10, 0, 1)

        hash1 = compute_hash(
            previous_hash="0000000000000000000000000000000000000000000000000000000000000000",
            table_name="plates",
            operation="INSERT",
            record_id=1,
            timestamp=timestamp1,
            user_id="test-user",
            data={"action": "insert"}
        )

        hash2 = compute_hash(
            previous_hash=hash1,  # Links to hash1
            table_name="plates",
            operation="INSERT",
            record_id=2,
            timestamp=timestamp2,
            user_id="test-user",
            data={"action": "insert"}
        )

        assert hash1 != hash2, "Chain-linked hashes should differ"
        assert hash2 != "0" * 64, "Non-genesis hash should not be all zeros"

    def test_verify_chain_valid(self):
        """Valid hash chain should pass verification."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        entries = []
        prev_hash = GENESIS_HASH

        for i in range(5):
            timestamp = datetime(2026, 7, 13, 10, 0, i)
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
            # Store timestamp as datetime object for verify_chain
            entries.append({
                "id": i + 1,
                "previous_hash": prev_hash,
                "current_hash": current_hash,
                "table_name": "plates",
                "operation": "INSERT",
                "record_id": i,
                "timestamp": timestamp,  # Keep as datetime
                "user_id": "test-user",
                "data": data
            })
            prev_hash = current_hash

        is_valid, broken_at = verify_chain(entries)
        assert is_valid is True, "Valid chain should pass verification"
        assert broken_at is None, "No broken entry in valid chain"

    def test_verify_chain_tampered(self):
        """Tampered hash chain should fail verification."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        entries = []
        prev_hash = GENESIS_HASH

        for i in range(5):
            timestamp = datetime(2026, 7, 13, 10, 0, i)
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
                "timestamp": timestamp,  # Keep as datetime
                "user_id": "test-user",
                "data": data
            })
            prev_hash = current_hash

        # Tamper with entry 3
        entries[2]["data"] = {"table": "plates", "record_id": 2, "action": "tampered"}

        is_valid, broken_at = verify_chain(entries)
        assert is_valid is False, "Tampered chain should fail verification"
        assert broken_at is not None, "Should identify broken entry"

    def test_verify_chain_empty(self):
        """Empty chain should be considered valid."""
        from middleware.engine.hash_chain import verify_chain

        is_valid, broken_at = verify_chain([])
        assert is_valid is True
        assert broken_at is None

    def test_verify_chain_single_entry(self):
        """Single-entry chain with correct genesis should be valid."""
        from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH

        timestamp = datetime(2026, 7, 13, 10, 0, 0)
        data = {"table": "plates", "record_id": 1, "action": "insert"}
        current_hash = compute_hash(
            previous_hash=GENESIS_HASH,
            table_name="plates",
            operation="INSERT",
            record_id=1,
            timestamp=timestamp,
            user_id="test-user",
            data=data
        )

        entries = [{
            "id": 1,
            "previous_hash": GENESIS_HASH,
            "current_hash": current_hash,
            "table_name": "plates",
            "operation": "INSERT",
            "record_id": 1,
            "timestamp": timestamp,  # Keep as datetime
            "user_id": "test-user",
            "data": data
        }]

        is_valid, broken_at = verify_chain(entries)
        assert is_valid is True
        assert broken_at is None

    def test_verify_chain_wrong_genesis(self):
        """Chain starting with wrong genesis should fail."""
        from middleware.engine.hash_chain import verify_chain

        entries = [{
            "id": 1,
            "previous_hash": "wrong_genesis_hash",
            "current_hash": "some_hash",
            "table_name": "plates",
            "operation": "INSERT",
            "record_id": 1,
            "timestamp": datetime(2026, 7, 13, 10, 0, 0),
            "user_id": "test-user",
            "data": {}
        }]

        is_valid, broken_at = verify_chain(entries)
        assert is_valid is False
        assert broken_at is not None

    def test_genesis_hash_constant(self):
        """Genesis hash should be constant all zeros."""
        from middleware.engine.hash_chain import GENESIS_HASH

        assert GENESIS_HASH == "0" * 64, "Genesis hash should be 64 zeros"

    def test_hash_length_sha256(self):
        """Hash output should be SHA-256 length (64 hex chars)."""
        from middleware.engine.hash_chain import compute_hash

        timestamp = datetime(2026, 7, 13, 10, 0, 0)
        hash_value = compute_hash(
            previous_hash="genesis",
            table_name="plates",
            operation="INSERT",
            record_id=1,
            timestamp=timestamp,
            user_id="test-user",
            data={}
        )

        assert len(hash_value) == 64, "SHA-256 hash should be 64 characters"
        assert all(c in "0123456789abcdef" for c in hash_value), \
            "Hash should be lowercase hexadecimal"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
