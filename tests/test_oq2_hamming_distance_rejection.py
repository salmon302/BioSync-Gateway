"""
OQ-2: Hamming Distance Rejection
Implements SRS OQ-2 - Barcode pairs with d < 3 are rejected
"""

import pytest
from middleware.engine.barcode import validate_plate_indices, hamming_distance


class TestOQ2HammingDistanceRejection:
    """Test suite for OQ-2"""
    
    def test_accept_d3_or_higher(self):
        """Barcode pairs with d ≥ 3 should be accepted"""
        # These have d = 3
        indices = ["ATCGAT", "TTAGGC", "CGATGT"]
        is_valid, violations = validate_plate_indices(indices, min_distance=3)
        assert is_valid, f"Should accept d=3 pairs, got violations: {violations}"
    
    def test_reject_d2_pair(self):
        """Barcode pairs with d = 2 should be rejected"""
        # "ATCG" and "ATCC" have d = 1
        # Let's create sequences with d = 2
        indices = ["ATCGAT", "ATCCAT", "TTAGGC"]  # First two have d = 2
        is_valid, violations = validate_plate_indices(indices, min_distance=3)
        assert not is_valid, "Should reject d=2 pairs"
        assert len(violations) > 0, "Should have violations"
    
    def test_reject_d1_pair(self):
        """Barcode pairs with d = 1 should be rejected"""
        indices = ["ATCGAT", "ATCGAC", "TTAGGC"]  # First two have d = 1
        is_valid, violations = validate_plate_indices(indices, min_distance=3)
        assert not is_valid, "Should reject d=1 pairs"
    
    def test_critical_vs_warning_severity(self):
        """d < 2 should be critical, d = 2 should be warning"""
        # d = 1 pair
        indices = ["ATCGAT", "ATCGAC"]
        is_valid, violations = validate_plate_indices(indices, min_distance=3)
        critical_violations = [v for v in violations if v.get('severity') == 'critical']
        assert len(critical_violations) > 0, "d=1 should be critical"
    
    def test_validate_plate_barcodes_helper(self):
        """Test the higher-level validation function"""
        from middleware.engine.barcode import validate_plate_barcodes
        
        # Valid plate (d ≥ 3)
        valid_barcodes = ["ATCACG", "CGATGT", "TTAGGC", "TGACCA"]
        result = validate_plate_barcodes(1, valid_barcodes)
        assert result['valid'], f"Should be valid: {result}"
        assert result['min_hamming_distance'] >= 3
        
        # Invalid plate (d < 3)
        invalid_barcodes = ["ATCGAT", "ATCGAC", "TTAGGC"]  # First two have d = 1
        result = validate_plate_barcodes(2, invalid_barcodes)
        assert not result['valid'], f"Should be invalid: {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
