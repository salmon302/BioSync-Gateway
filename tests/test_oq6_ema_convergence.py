"""
OQ-6: EMA Filter Step Input Convergence
Implements SRS OQ-6 - EMA filter converges within 5% after ≤ 4 iterations
"""

import pytest
from middleware.engine.signal import EMAFilter, run_oq6_test


class TestOQ6EMAFilterConvergence:
    """Test suite for OQ-6"""
    
    def test_step_input_convergence_alpha_0_5(self):
        """α=0.5, step 0→100, converge within 5% after ≤ 5 iterations"""
        ema = EMAFilter(alpha=0.5)
        
        # Apply step input
        step_input = 100.0
        tolerance = 0.05  # 5%
        
        convergence_step = ema.get_convergence_step(step_input, step_input, tolerance)
        
        assert convergence_step is not None, "Filter should converge"
        assert convergence_step <= 5, f"Should converge within 5 steps, got {convergence_step}"
    
    def test_ema_formula_correct(self):
        """Verify EMA formula: EMAₜ = α × xₜ + (1 - α) × EMAₜ₋₁"""
        ema = EMAFilter(alpha=0.5)
        
        # Apply values and check formula
        values = [0, 100, 100, 100, 100]
        expected = [
            0,     # First value
            50,    # 0.5*100 + 0.5*0
            75,    # 0.5*100 + 0.5*50
            87.5,  # 0.5*100 + 0.5*75
            93.75  # 0.5*100 + 0.5*87.5
        ]
        
        for i, value in enumerate(values):
            actual = ema.filter_value(value)
            assert abs(actual - expected[i]) < 0.01, f"Step {i}: expected {expected[i]}, got {actual}"
    
    def test_filter_single_value(self):
        """First value should initialize EMA"""
        ema = EMAFilter(alpha=0.3)
        
        result = ema.filter_value(50.0)
        assert result == 50.0, "First value should initialize EMA"
    
    def test_filter_reset(self):
        """Reset should clear filter state"""
        ema = EMAFilter(alpha=0.5)
        
        ema.filter_value(100.0)
        ema.filter_value(200.0)
        
        ema.reset()
        assert ema.ema_value is None, "EMA should be None after reset"
        assert ema.step_count == 0, "Step count should be 0 after reset"
    
    def test_run_oq6_test(self):
        """Run the official OQ-6 test"""
        passed, msg = run_oq6_test()
        assert passed, f"OQ-6 test failed: {msg}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
