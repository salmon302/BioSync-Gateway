"""
Hash Chain Engine
Implements SRS FR-3.8.3 - Cryptographic hash chain for audit integrity

Provides:
- compute_hash(): Compute SHA-256 hash for audit entry
- verify_chain(): Verify integrity of hash chain
- get_genesis_hash(): Return genesis block hash
"""

import hashlib
import json
from typing import Optional, Tuple, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Genesis block hash (first block in empty chain)
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def compute_hash(
    previous_hash: str,
    table_name: str,
    operation: str,
    record_id: int,
    timestamp: datetime,
    user_id: Optional[str],
    data: dict
) -> str:
    """
    Compute SHA-256 hash for an audit log entry.
    
    Args:
        previous_hash: Hash of previous entry in chain
        table_name: Name of table being audited
        operation: INSERT, UPDATE, or DELETE
        record_id: ID of record being audited
        timestamp: Timestamp of operation
        user_id: User performing operation (optional)
        data: JSON data being audited
    
    Returns:
        SHA-256 hash as hexadecimal string
    """
    # Concatenate all fields in deterministic order
    concat_data = (
        previous_hash +
        table_name +
        operation +
        str(record_id) +
        timestamp.isoformat() +
        (user_id or "") +
        json.dumps(data, sort_keys=True)
    )
    
    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(concat_data.encode('utf-8'))
    return hash_obj.hexdigest()


def verify_chain(audit_entries: List[dict]) -> Tuple[bool, Optional[int]]:
    """
    Verify the integrity of a hash chain.
    
    Args:
        audit_entries: List of audit log entries in chronological order
            Each entry should have: id, previous_hash, current_hash, 
            table_name, operation, record_id, timestamp, user_id, data
    
    Returns:
        Tuple of (is_valid, broken_at_id)
        - is_valid: True if chain is intact
        - broken_at_id: ID of first broken entry (None if valid)
    """
    if not audit_entries:
        return True, None
    
    # Check genesis block
    first_entry = audit_entries[0]
    if first_entry.get('previous_hash') != GENESIS_HASH:
        if first_entry.get('id'):
            return False, first_entry['id']
        return False, 0
    
    # Verify chain links
    for i, entry in enumerate(audit_entries):
        # Compute expected hash
        expected_hash = compute_hash(
            previous_hash=entry.get('previous_hash', ''),
            table_name=entry.get('table_name', ''),
            operation=entry.get('operation', ''),
            record_id=entry.get('record_id', 0),
            timestamp=entry.get('timestamp'),
            user_id=entry.get('user_id'),
            data=entry.get('data', {})
        )
        
        # Compare with stored hash
        if expected_hash != entry.get('current_hash'):
            logger.warning(
                f"Hash chain broken at entry ID {entry.get('id')}. "
                f"Expected: {expected_hash}, Got: {entry.get('current_hash')}"
            )
            return False, entry.get('id')
    
    return True, None


def get_genesis_hash() -> str:
    """
    Return the genesis block hash.
    
    Returns:
        Genesis hash string
    """
    return GENESIS_HASH


def compute_test_vector() -> dict:
    """
    Compute a test vector for hash chain verification.
    Useful for OQ-9 tamper detection testing.
    
    Returns:
        Dict with test data and expected hash
    """
    test_data = {
        "table_name": "test_table",
        "operation": "INSERT",
        "record_id": 1,
        "timestamp": datetime(2026, 1, 1, 12, 0, 0),
        "user_id": "test_user",
        "data": {"field": "value"}
    }
    
    test_hash = compute_hash(
        previous_hash=GENESIS_HASH,
        **test_data
    )
    
    return {
        "input": test_data,
        "expected_hash": test_hash
    }


if __name__ == "__main__":
    # Self-test: Verify hash computation
    print("Hash Chain Engine Self-Test")
    print("=" * 50)
    
    # Test 1: Genesis hash
    print(f"Genesis Hash: {GENESIS_HASH}")
    
    # Test 2: Compute hash
    test_vector = compute_test_vector()
    print(f"\nTest Vector Hash: {test_vector['expected_hash']}")
    
    # Test 3: Verify chain
    mock_entries = [{
        'id': 1,
        'previous_hash': GENESIS_HASH,
        'current_hash': test_vector['expected_hash'],
        'table_name': 'test_table',
        'operation': 'INSERT',
        'record_id': 1,
        'timestamp': datetime(2026, 1, 1, 12, 0, 0),
        'user_id': 'test_user',
        'data': {'field': 'value'}
    }]
    
    is_valid, broken_id = verify_chain(mock_entries)
    print(f"\nChain Verification: {'PASS' if is_valid else 'FAIL'}")
    if not is_valid:
        print(f"Broken at ID: {broken_id}")
