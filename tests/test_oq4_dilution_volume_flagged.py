"""
OQ-4: Dilution Volume Flagged (0.49 µL)
Implements SRS OQ-4 - 0.49 µL transfer volume is flagged
"""

import pytest
from middleware.engine.dilution import DilutionSolver


class TestOQ4DilutionVolumeFlagged:
    """Test suite for OQ-4"""
    
    def test_0_49ul_flagged(self):
        """0.49 µL should be flagged as below limit"""
        solver = DilutionSolver(min_volume=0.5)
        
        # Calculate a dilution that results in 0.49 µL transfer
        # C1 = 204.08, C2 = 1.0, V2 = 100 → V1 = (1 * 100) / 204.08 = 0.49 µL
        c1 = 204.08
        c2 = 1.0
        target_volume = 100.0
        
        v1, v2 = solver.compute_volume(c1, c2, target_volume)
        assert abs(v1 - 0.49) < 0.01, f"Expected ~0.49 µL, got {v1} µL"
        
        # Check if below limit
        is_below, msg = solver.detect_below_limit(v1, threshold=0.5)
        assert is_below, f"0.49 µL should be flagged as below limit"
        assert "WARNING" in msg, f"Should have warning message, got: {msg}"
    
    def test_0_09ul_critical(self):
        """0.09 µL should be flagged as critical (below absolute min 0.1 µL)"""
        solver = DilutionSolver(min_volume=0.5)
        
        # Extremely low volume (below absolute minimum)
        c1 = 1100.0
        c2 = 1.0
        v1, v2 = solver.compute_volume(c1, c2)
        
        is_below, msg = solver.detect_below_limit(v1)
        assert is_below, f"{v1} µL should be below limit"
        assert "CRITICAL" in msg, f"Should have CRITICAL message, got: {msg}"
    
    def test_0_5ul_warning(self):
        """0.5 µL should be flagged as warning (at the limit)"""
        solver = DilutionSolver(min_volume=0.5)
        
        # At the limit
        c1 = 200.0
        c2 = 1.0
        v1, v2 = solver.compute_volume(c1, c2)
        
        is_below, msg = solver.detect_below_limit(v1)
        assert not is_below, f"{v1} µL should NOT be below limit (it's exactly at the limit)"
    
    def test_pre_dilution_generated(self):
        """Pre-dilution chain should be generated for low volumes"""
        solver = DilutionSolver(min_volume=0.5)
        
        # Very low volume scenario
        c1 = 1000.0  # 1000 M
        c2 = 1.0       # 1 M
        
        worklist = solver.generate_pre_dilution(c1, c2)
        
        assert len(worklist.steps) > 1, "Should have multiple steps for pre-dilution"
        assert worklist.steps[0].is_pre_dilution, "First step should be pre-dilution"
    
    def test_run_oq4_test(self):
        """Run the official OQ-4 test"""
        from middleware.engine.dilution import run_oq4_test
        assert run_oq4_test(), "OQ-4 test failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
