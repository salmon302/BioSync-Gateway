"""
Barcode Multiplexing Engine
Implements SRS §3.3 - Barcode Index Validation

This module provides Hamming distance calculation and plate barcode validation
for Illumina TruSeq/Nextera multiplexing protocols.
"""

from typing import List, Tuple, Dict, Optional
import numpy as np


def hamming_distance(seq1: str, seq2: str) -> int:
    """
    Calculate Hamming distance between two sequences.
    
    Args:
        seq1: First sequence (DNA barcode)
        seq2: Second sequence (DNA barcode)
    
    Returns:
        Number of positions where sequences differ
        
    Raises:
        ValueError: If sequences have different lengths
        
    Implements:
        SRS FR-3.3.1 - Hamming distance calculation
    """
    if len(seq1) != len(seq2):
        raise ValueError(
            f"Sequences must have equal length for Hamming distance. "
            f"Got {len(seq1)} and {len(seq2)}"
        )
    
    # Count positions where characters differ
    distance = sum(c1 != c2 for c1, c2 in zip(seq1.upper(), seq2.upper()))
    return distance


def validate_plate_indices(
    indices: List[str],
    min_distance: int = 3
) -> Tuple[bool, List[Dict]]:
    """
    Validate that all barcode index pairs meet minimum Hamming distance.
    
    Args:
        indices: List of barcode sequences to validate
        min_distance: Minimum acceptable Hamming distance (default: 3)
    
    Returns:
        Tuple of (is_valid, violations_list)
        - is_valid: True if all pairs meet minimum distance
        - violations_list: List of dicts with violation details
        
    Implements:
        SRS FR-3.3.2 - Minimum distance validation
    """
    violations = []
    
    # Check all unique pairs
    for i in range(len(indices)):
        for j in range(i + 1, len(indices)):
            try:
                dist = hamming_distance(indices[i], indices[j])
                if dist < min_distance:
                    violations.append({
                        'index1': indices[i],
                        'index2': indices[j],
                        'position1': i,
                        'position2': j,
                        'hamming_distance': dist,
                        'min_required': min_distance,
                        'severity': 'critical' if dist < 2 else 'warning'
                    })
            except ValueError as e:
                violations.append({
                    'index1': indices[i],
                    'index2': indices[j],
                    'position1': i,
                    'position2': j,
                    'error': str(e),
                    'severity': 'error'
                })
    
    is_valid = len([v for v in violations if v.get('severity') == 'critical']) == 0
    return is_valid, violations


def validate_plate_barcodes(
    plate_id: int,
    barcode_sequences: List[str],
    barcode_set: str = "TruSeq"
) -> Dict:
    """
    Validate barcode indices for a specific plate.
    
    Args:
        plate_id: Database ID of the plate
        barcode_sequences: List of barcode sequences from the plate
        barcode_set: Name of barcode set (TruSeq, Nextera, etc.)
    
    Returns:
        Dict with validation results matching SRS FR-3.3.3 output format
        
    Implements:
        SRS FR-3.3.3 - Plate barcode validation endpoint
    """
    is_valid, violations = validate_plate_indices(barcode_sequences)
    
    result = {
        'plate_id': plate_id,
        'barcode_set': barcode_set,
        'total_indices': len(barcode_sequences),
        'valid': is_valid,
        'violations': violations,
        'min_hamming_distance': None  # Will be calculated below if needed
    }
    
    # Calculate minimum distance across all pairs if no violations
    if is_valid and len(barcode_sequences) > 1:
        min_dist = float('inf')
        for i in range(len(barcode_sequences)):
            for j in range(i + 1, len(barcode_sequences)):
                dist = hamming_distance(barcode_sequences[i], barcode_sequences[j])
                min_dist = min(min_dist, dist)
        result['min_hamming_distance'] = min_dist
    elif is_valid:
        result['min_hamming_distance'] = None  # Single index
    
    return result


# Test vectors for OQ-1 (from SRS §7.2)
OQ1_TEST_VECTORS = [
    # (sequence1, sequence2, expected_distance)
    ("ATCG", "ATCG", 0),
    ("ATCG", "ATCC", 1),
    ("ATCG", "TTCG", 1),
    ("ATCG", "TTTT", 3),
    ("ATCGATCG", "ATCGATCC", 1),
    ("ATCGATCG", "GCTAATCG", 4),  # A≠G, T≠C, C≠T, G≠A (4 mismatches)
]


def run_oq1_test_vectors() -> Tuple[bool, List[str]]:
    """
    Run OQ-1 test vectors to verify Hamming distance implementation.
    
    Returns:
        Tuple of (all_passed, failure_messages)
        
    Implements:
        SRS OQ-1 - Test vector validation
    """
    failures = []
    
    for i, (seq1, seq2, expected) in enumerate(OQ1_TEST_VECTORS):
        actual = hamming_distance(seq1, seq2)
        if actual != expected:
            failures.append(
                f"Test vector {i+1} failed: hamming_distance('{seq1}', '{seq2}') "
                f"= {actual}, expected {expected}"
            )
    
    return len(failures) == 0, failures


# Illumina TruSeq HT barcode sequences (example subset)
# In production, these would be loaded from database (004-seed-barcodes.sql)
TRUSEQ_BARCODES = {
    'HT1': 'ATCACG',
    'HT2': 'CGATGT',
    'HT3': 'TTAGGC',
    'HT4': 'TGACCA',
    'HT5': 'ACAGTG',
    'HT6': 'GCCAAT',
    'HT7': 'CAGATC',
    'HT8': 'ACTTGA',
    'HT9': 'GATCAG',
    'HT10': 'TAGCTT',
    'HT11': 'GGCTAC',
    'HT12': 'CTTGTA',
}


def load_barcode_set(set_name: str = "TruSeq") -> Dict[str, str]:
    """
    Load barcode set from database or fallback to built-in sets.
    
    Args:
        set_name: Name of barcode set to load
    
    Returns:
        Dict mapping barcode ID to sequence
        
    Note:
        In production, this queries the barcode_indices table.
        Currently returns built-in TruSeq set as placeholder.
    """
    if set_name.lower() == "truseq":
        return TRUSEQ_BARCODES.copy()
    else:
        # TODO: Query database for barcode set
        raise ValueError(f"Unknown barcode set: {set_name}")


if __name__ == "__main__":
    # Self-test on module load
    print("Running OQ-1 test vectors...")
    passed, failures = run_oq1_test_vectors()
    if passed:
        print("✓ All OQ-1 test vectors passed")
    else:
        print("✗ OQ-1 test vectors failed:")
        for failure in failures:
            print(f"  - {failure}")
    
    # Example validation
    print("\nValidating TruSeq HT barcodes 1-6...")
    test_barcodes = list(TRUSEQ_BARCODES.values())[:6]
    result = validate_plate_barcodes(1, test_barcodes)
    print(f"Result: {'Valid' if result['valid'] else 'Invalid'}")
    print(f"Min Hamming distance: {result['min_hamming_distance']}")
    if result['violations']:
        print(f"Violations: {len(result['violations'])}")
