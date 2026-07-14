"""
OQ-1: Barcode Test Vectors
Implements SRS OQ-1 - Hamming distance test vector validation
"""

import pytest
from middleware.engine.barcode import hamming_distance, run_oq1_test_vectors


class TestOQ1TestVectors:
    """Test suite for OQ-1"""
    
    def test_hamming_distance_identical(self):
        """Identical sequences should have distance 0"""
        assert hamming_distance("ATCG", "ATCG") == 0
        assert hamming_distance("GATTACA", "GATTACA") == 0
    
    def test_hamming_distance_single_mismatch(self):
        """Single mismatch should have distance 1"""
        assert hamming_distance("ATCG", "ATCC") == 1
        assert hamming_distance("ATCG", "TTCG") == 1
    
    def test_hamming_distance_multiple_mismatches(self):
        """Multiple mismatches should count correctly"""
        assert hamming_distance("ATCG", "TTTT") == 3
        assert hamming_distance("ATCGATCG", "ATCGATCC") == 1
        assert hamming_distance("ATCGATCG", "GCTAATCG") == 4  # A≠G, T≠C, C≠T, G≠A
    
    def test_hamming_distance_case_insensitive(self):
        """Should be case-insensitive"""
        assert hamming_distance("atcg", "ATCG") == 0
        assert hamming_distance("AtCg", "aTcG") == 0
    
    def test_hamming_distance_unequal_length(self):
        """Should raise ValueError for unequal lengths"""
        with pytest.raises(ValueError, match="Sequences must have equal length"):
            hamming_distance("ATCG", "ATC")
    
    def test_run_oq1_test_vectors(self):
        """Run the official OQ-1 test vectors"""
        passed, failures = run_oq1_test_vectors()
        assert passed, f"OQ-1 test vectors failed: {failures}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
