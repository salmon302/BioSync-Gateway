"""
OQ-3: Dilution Volume Accepted (0.5 µL)
Implements SRS OQ-3 - 0.5 µL transfer volume is accepted
"""

import pytest
from middleware.engine.dilution import DilutionSolver


class TestOQ3DilutionVolumeAccepted:
    """Test suite for OQ-3"""
    
    def test_0_5ul_accepted(self):
        """0.5 µL should be accepted as valid"""
        solver = DilutionSolver(min_volume=0.5)
        
        # Calculate a dilution that results in exactly 0.5 µL transfer
        # C1V1 = C2V2 → V1 = (C2 * V2) / C1
        # If C1 = 100, C2 = 1, V2 = 100 → V1 = (1 * 100) / 100 = 1.0 µL
        # If C1 = 200, C2 = 1, V2 = 100 → V1 = (1 * 100) / 200 = 0.5 µL
        c1 = 200.0
        c2 = 1.0
        target_volume = 100.0
        
        v1, v2 = solver.compute_volume(c1, c2, target_volume)
        assert abs(v1 - 0.5) < 0.001, f"Expected 0.5 µL, got {v1} µL"
        
        # Check if below limit
        is_below, msg = solver.detect_below_limit(v1)
        assert not is_below, f"0.5 µL should be accepted, got: {msg}"
    
    def test_1_0ul_accepted(self):
        """1.0 µL should be accepted"""
        solver = DilutionSolver(min_volume=0.5)
        
        c1 = 100.0
        c2 = 1.0
        v1, v2 = solver.compute_volume(c1, c2)
        
        is_below, msg = solver.detect_below_limit(v1)
        assert not is_below, f"1.0 µL should be accepted, got: {msg}"
    
    def test_compute_volume_formula(self):
        """Verify C1V1 = C2V2 formula"""
        solver = DilutionSolver()
        
        # Test various concentrations
        # C1=100, C2=1, V2=100 → V1 = (1*100)/100 = 1.0, V2_diluent = 99.0
        # C1=50, C2=10, V2=100 → V1 = (10*100)/50 = 20.0, V2_diluent = 80.0
        # C1=200, C2=2, V2=100 → V1 = (2*100)/200 = 1.0, V2_diluent = 99.0
        test_cases = [
            (100.0, 1.0, 1.0, 99.0),
            (50.0, 10.0, 20.0, 80.0),
            (200.0, 2.0, 1.0, 99.0),
        ]
        
        for c1, c2, expected_v1, expected_v2 in test_cases:
            v1, v2 = solver.compute_volume(c1, c2, 100.0)
            assert abs(v1 - expected_v1) < 0.01, f"C1={c1}, C2={c2}: expected V1={expected_v1}, got {v1}"
            assert abs(v2 - expected_v2) < 0.01, f"C1={c1}, C2={c2}: expected V2={expected_v2}, got {v2}"
    
    def test_run_oq3_test(self):
        """Run the official OQ-3 test"""
        from middleware.engine.dilution import run_oq3_test
        assert run_oq3_test(), "OQ-3 test failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
