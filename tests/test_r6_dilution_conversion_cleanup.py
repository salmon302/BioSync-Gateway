"""
R6: Focused regression tests for DilutionSolver.convert_units after removal of
duplicated / unreachable mass-unit conversion branches (SRS FR-3.4.4).

These tests lock in the single reachable conversion path and guarantee no
regression of conversion correctness across the full unit matrix. They also
assert that the source no longer contains a duplicated
``elif from_unit in mass_units:`` branch (the defect removed by this change).
"""

import os

import pytest

from middleware.engine.dilution import DilutionSolver

_DILUTION_SRC = os.path.join(
    os.path.dirname(__file__), "..", "middleware", "engine", "dilution.py"
)


class TestDilutionUnitConversionMatrix:
    """Full coverage of the single reachable conversion path."""

    def test_identity(self):
        solver = DilutionSolver()
        assert solver.convert_units(5.0, "µM", "µM") == 5.0
        assert solver.convert_units(2.0, "ng/µL", "ng/µL") == 2.0

    def test_molar_to_molar(self):
        solver = DilutionSolver()
        assert abs(solver.convert_units(1.0, "M", "mM") - 1000.0) < 1e-9
        assert abs(solver.convert_units(1.0, "M", "µM") - 1e6) < 1e-3
        assert abs(solver.convert_units(1.0, "M", "nM") - 1e9) < 1e-3
        assert abs(solver.convert_units(1000.0, "mM", "M") - 1.0) < 1e-9

    def test_mass_to_mass(self):
        solver = DilutionSolver()
        # 1 ng/µL -> µg/µL = 1e-3 ; -> mg/µL = 1e-6 ; -> g/µL = 1e-9
        assert abs(solver.convert_units(1.0, "ng/µL", "µg/µL") - 1e-3) < 1e-12
        assert abs(solver.convert_units(1.0, "ng/µL", "mg/µL") - 1e-6) < 1e-12
        assert abs(solver.convert_units(1.0, "ng/µL", "g/µL") - 1e-9) < 1e-15
        assert abs(solver.convert_units(1.0, "g/µL", "ng/µL") - 1e9) < 1e-3
        assert abs(solver.convert_units(1.0, "µg/µL", "ng/µL") - 1000.0) < 1e-9

    def test_molar_to_mass_requires_molar_mass(self):
        solver = DilutionSolver()
        with pytest.raises(ValueError, match="Molar mass required"):
            solver.convert_units(1.0, "M", "ng/µL", molar_mass=None)

    def test_molar_to_mass_dna(self):
        solver = DilutionSolver()
        molar_mass = 66000.0  # g/mol for 100 bp DNA
        # 1 µM -> 66 ng/µL
        result = solver.convert_units(1.0, "µM", "ng/µL", molar_mass=molar_mass)
        assert abs(result - 66.0) < 1e-9

    def test_mass_to_molar_requires_molar_mass(self):
        solver = DilutionSolver()
        with pytest.raises(ValueError, match="Molar mass required"):
            solver.convert_units(66.0, "ng/µL", "µM", molar_mass=None)

    def test_mass_to_molar_dna(self):
        solver = DilutionSolver()
        molar_mass = 66000.0
        # 66 ng/µL -> 1 µM
        result = solver.convert_units(66.0, "ng/µL", "µM", molar_mass=molar_mass)
        assert abs(result - 1.0) < 1e-9
        # 1 g/µL -> 1e6/66000 M
        result2 = solver.convert_units(1.0, "g/µL", "M", molar_mass=molar_mass)
        assert abs(result2 - (1.0 / 66000.0 * 1e6)) < 1e-9

    def test_unsupported_unit_raises(self):
        solver = DilutionSolver()
        with pytest.raises(ValueError, match="Unsupported unit conversion"):
            solver.convert_units(1.0, "frog/µL", "M")


class TestDilutionDeadBranchRemoval:
    """Lock in the R6 cleanup: no duplicated/unreachable conversion branch."""

    def test_no_duplicate_mass_branch(self):
        with open(_DILUTION_SRC, encoding="utf-8") as fh:
            src = fh.read()
        # The reachable branch is the single `elif from_unit in mass_units:`.
        # After R6 there must be exactly ONE such guard in convert_units.
        occurrences = src.count("elif from_unit in mass_units:")
        assert occurrences == 1, (
            f"Expected exactly one `elif from_unit in mass_units:` branch, "
            f"found {occurrences} (duplicated/unreachable branch not removed)"
        )

    def test_convert_units_single_reachable_path(self):
        # Sanity: a representative cross-matrix call must not raise and must be
        # finite, confirming the remaining branch handles every supported unit.
        solver = DilutionSolver()
        units = ["M", "mM", "µM", "nM", "ng/µL", "µg/µL", "mg/µL", "g/µL"]
        molar_units = {"M", "mM", "µM", "nM"}
        molar_mass = 66000.0
        for frm in units:
            for to in units:
                if frm == to:
                    continue
                needs_mm = (frm in molar_units) != (to in molar_units)
                kwargs = {"molar_mass": molar_mass} if needs_mm else {}
                val = solver.convert_units(1.0, frm, to, **kwargs)
                assert val is not None and val == val, f"{frm}->{to} gave {val}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
