"""
OQ-5: Unit Conversion (M ↔ ng/µL)
Implements SRS OQ-5 - Unit conversion works correctly
"""

import pytest
from middleware.engine.dilution import DilutionSolver


class TestOQ5UnitConversion:
    """Test suite for OQ-5"""
    
    def test_m_to_ng_ul(self):
        """Convert M to ng/µL using molar mass"""
        solver = DilutionSolver()
        
        # DNA example: 100 bp DNA has ~66,000 g/mol
        molar_mass = 66000.0  # g/mol
        
        # 1 µM DNA = 1e-6 M
        # Mass concentration = 1e-6 M * 66000 g/mol = 0.066 g/L
        # = 0.066 ng/µL
        result = solver.convert_units(1.0, 'µM', 'ng/µL', molar_mass=molar_mass)
        
        expected = 1e-6 * molar_mass * 1e-6 * 1e9  # Convert to ng/µL
        assert abs(result - expected) < 0.01, f"Expected {expected:.2f} ng/µL, got {result:.2f}"
    
    def test_ng_ul_to_m(self):
        """Convert ng/µL to M using molar mass"""
        solver = DilutionSolver()
        
        molar_mass = 66000.0  # g/mol
        
        # 66 ng/µL DNA = 66e-9 g/µL
        # Convert to g/L: 66e-9 g/µL * 1e6 µL/L = 66e-3 g/L = 0.066 g/L
        # Molar concentration = 0.066 g/L / 66000 g/mol = 1e-6 M = 1 µM
        result = solver.convert_units(66.0, 'ng/µL', 'µM', molar_mass=molar_mass)
        
        assert abs(result - 1.0) < 0.01, f"Expected 1.0 µM, got {result:.6f} µM"
    
    def test_molar_unit_conversion(self):
        """Convert between molar units"""
        solver = DilutionSolver()
        
        # 1 M = 1000 mM = 1e6 µM = 1e9 nM
        assert abs(solver.convert_units(1.0, 'M', 'mM') - 1000.0) < 0.01
        assert abs(solver.convert_units(1.0, 'M', 'µM') - 1e6) < 0.01
        assert abs(solver.convert_units(1.0, 'M', 'nM') - 1e9) < 0.01
        
        # Reverse
        assert abs(solver.convert_units(1000.0, 'mM', 'M') - 1.0) < 0.01
    
    def test_missing_molar_mass_error(self):
        """Should raise error if molar mass needed but not provided"""
        solver = DilutionSolver()
        
        with pytest.raises(ValueError, match="Molar mass required"):
            solver.convert_units(1.0, 'M', 'ng/µL', molar_mass=None)
    
    def test_run_oq5_test(self):
        """Run the official OQ-5 test"""
        from middleware.engine.dilution import run_oq5_test
        assert run_oq5_test(), "OQ-5 test failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
