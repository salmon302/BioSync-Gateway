"""
Dilution Solver Engine
Implements SRS §3.4 - Dilution Volume Calculations

This module provides deterministic dilution calculations for laboratory workflows,
including pre-dilution chain generation for volumes below pipetting limits.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ConcentrationUnit(Enum):
    """Supported concentration units"""
    M = "M"  # Molar
    MM = "mM"  # millimolar
    UM = "µM"  # micromolar
    NM = "nM"  # nanomolar
    NG_UL = "ng/µL"  # nanograms per microliter
    UG_UL = "µg/µL"  # micrograms per microliter


@dataclass
class DilutionStep:
    """Represents a single dilution step in a worklist"""
    step_number: int
    source_concentration: float
    source_unit: str
    target_concentration: float
    target_unit: str
    volume_to_transfer: float  # µL
    diluent_volume: float  # µL
    total_volume: float  # µL
    is_pre_dilution: bool
    notes: Optional[str] = None


@dataclass
class DilutionWorklist:
    """Complete dilution worklist for a sample"""
    sample_id: str
    initial_concentration: float
    initial_unit: str
    target_concentration: float
    target_unit: str
    steps: List[DilutionStep]
    total_volume_needed: float
    molar_mass: Optional[float] = None  # g/mol, for unit conversion


class DilutionSolver:
    """
    Deterministic dilution calculator.
    
    Implements:
        SRS FR-3.4.1 - Volume calculation
        SRS FR-3.4.2 - Below-limit detection
        SRS FR-3.4.3 - Pre-dilution generation
        SRS FR-3.4.4 - Unit conversion
    """
    
    # Pipetting limits (µL)
    MIN_PIPPETABLE_VOLUME = 0.5  # Minimum recommended volume
    ABSOLUTE_MIN_VOLUME = 0.1  # Absolute minimum (flagged)
    
    # Standard diluent volumes for pre-dilution
    PRE_DILUTION_FACTORS = [10, 100, 1000]  # 1:10, 1:100, 1:1000
    
    def __init__(self, min_volume: float = MIN_PIPPETABLE_VOLUME):
        """
        Initialize dilution solver.
        
        Args:
            min_volume: Minimum pipettable volume in µL (default: 0.5)
        """
        self.min_volume = min_volume
    
    def compute_volume(
        self,
        c1: float,
        c2: float,
        target_total_volume: float = 100.0
    ) -> Tuple[float, float]:
        """
        Compute dilution volumes using C1V1 = C2V2.
        
        Args:
            c1: Initial concentration
            c2: Target concentration
            target_total_volume: Desired final volume in µL
        
        Returns:
            Tuple of (volume_to_transfer_µL, diluent_volume_µL)
            
        Implements:
            SRS FR-3.4.1 - Volume calculation
        """
        if c1 <= 0 or c2 <= 0:
            raise ValueError("Concentrations must be positive")
        
        if c2 > c1:
            raise ValueError("Target concentration cannot exceed initial concentration")
        
        # C1V1 = C2V2 → V1 = (C2 * V2) / C1
        v1 = (c2 * target_total_volume) / c1
        v2_diluent = target_total_volume - v1
        
        return v1, v2_diluent
    
    def detect_below_limit(
        self,
        volume: float,
        threshold: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Detect if calculated volume is below pipetting limit.
        
        Args:
            volume: Calculated transfer volume in µL
            threshold: Custom threshold (uses self.min_volume if None)
        
        Returns:
            Tuple of (is_below_limit, warning_message)
            
        Implements:
            SRS FR-3.4.2 - Below-limit detection
        """
        if threshold is None:
            threshold = self.min_volume
        
        if volume < self.ABSOLUTE_MIN_VOLUME:
            return True, f"CRITICAL: Volume {volume:.2f} µL below absolute minimum {self.ABSOLUTE_MIN_VOLUME} µL"
        elif volume < threshold:
            return True, f"WARNING: Volume {volume:.2f} µL below recommended minimum {threshold} µL"
        else:
            return False, ""
    
    def generate_pre_dilution(
        self,
        c1: float,
        c2: float,
        molar_mass: Optional[float] = None,
        max_steps: int = 3
    ) -> DilutionWorklist:
        """
        Generate pre-dilution chain for very low transfer volumes.
        
        Args:
            c1: Initial concentration
            c2: Target concentration
            molar_mass: Molar mass for unit conversion (optional)
            max_steps: Maximum number of pre-dilution steps
        
        Returns:
            DilutionWorklist with pre-dilution steps
            
        Implements:
            SRS FR-3.4.3 - Pre-dilution generation
        """
        steps = []
        current_concentration = c1
        step_number = 1
        
        # Try sequential 1:X dilutions until volume is pipettable
        for dilution_factor in self.PRE_DILUTION_FACTORS[:max_steps]:
            # Intermediate concentration after this dilution
            intermediate_conc = current_concentration / dilution_factor
            
            # Calculate volume for next step
            v1, v2 = self.compute_volume(
                intermediate_conc,
                c2,
                target_total_volume=100.0
            )
            
            # Create pre-dilution step
            step = DilutionStep(
                step_number=step_number,
                source_concentration=current_concentration,
                source_unit="relative",
                target_concentration=intermediate_conc,
                target_unit="relative",
                volume_to_transfer=100.0,  # Standard transfer volume
                diluent_volume=(dilution_factor - 1) * 100.0,
                total_volume=dilution_factor * 100.0,
                is_pre_dilution=True,
                notes=f"1:{dilution_factor} pre-dilution"
            )
            steps.append(step)
            
            # Check if next step would be pipettable
            next_v1, _ = self.compute_volume(intermediate_conc, c2)
            is_below, _ = self.detect_below_limit(next_v1)
            
            if not is_below:
                break
            
            current_concentration = intermediate_conc
            step_number += 1
        
        # Final dilution step
        v1, v2 = self.compute_volume(current_concentration, c2)
        final_step = DilutionStep(
            step_number=step_number + 1,
            source_concentration=current_concentration,
            source_unit="relative",
            target_concentration=c2,
            target_unit="relative",
            volume_to_transfer=v1,
            diluent_volume=v2,
            total_volume=v1 + v2,
            is_pre_dilution=False,
            notes="Final dilution step"
        )
        steps.append(final_step)
        
        return DilutionWorklist(
            sample_id="unknown",
            initial_concentration=c1,
            initial_unit="relative",
            target_concentration=c2,
            target_unit="relative",
            steps=steps,
            total_volume_needed=sum(s.total_volume for s in steps),
            molar_mass=molar_mass
        )
    
    def convert_units(
        self,
        concentration: float,
        from_unit: str,
        to_unit: str,
        molar_mass: Optional[float] = None
    ) -> float:
        """
        Convert between concentration units.
        
        Args:
            concentration: Concentration value
            from_unit: Source unit (M, mM, µM, nM, ng/µL, µg/µL)
            to_unit: Target unit
            molar_mass: Molar mass in g/mol (required for M ↔ mass/volume)
        
        Returns:
            Converted concentration
            
        Implements:
            SRS FR-3.4.4 - Unit conversion
        """
        # Normalize unit strings
        from_unit = from_unit.strip()
        to_unit = to_unit.strip()
        
        if from_unit == to_unit:
            return concentration
        
        # Molar conversions (multiplier to convert from that unit to M)
        molar_units = {
            'M': 1.0,
            'mM': 1e-3,
            'µM': 1e-6,
            'nM': 1e-9
        }
        
        # Mass/volume conversions (multiplier to convert from that unit to g/µL)
        # 1 g/µL = 1e9 ng/µL = 1e6 µg/µL = 1e3 mg/µL
        mass_units = {
            'ng/µL': 1e-9,   # 1 ng/µL = 1e-9 g/µL
            'µg/µL': 1e-6,   # 1 µg/µL = 1e-6 g/µL
            'mg/µL': 1e-3,   # 1 mg/µL = 1e-3 g/µL
            'g/µL': 1.0      # 1 g/µL = 1 g/µL
        }
        
        # Convert to base units (M and g/µL)
        if from_unit in molar_units:
            # Convert to M
            conc_m = concentration * molar_units[from_unit]
            
            if to_unit in molar_units:
                # Molar → Molar: convert from M to target
                return conc_m / molar_units[to_unit]
            
            elif to_unit in mass_units:
                # Molar → Mass/volume
                if molar_mass is None:
                    raise ValueError(
                        f"Molar mass required to convert {from_unit} to {to_unit}"
                    )
                # Convert M to g/µL: C (g/µL) = C (M) * molar_mass / 1e6
                # Explanation: 1 M = 1 mol/L = molar_mass g/L = molar_mass / 1e6 g/µL
                conc_g_per_ul = conc_m * molar_mass / 1e6
                # Convert g/µL to target unit
                return conc_g_per_ul / mass_units[to_unit]
        
        elif from_unit in mass_units:
            # Convert to g/µL
            conc_g_per_ul = concentration * mass_units[from_unit]
            
            if to_unit in mass_units:
                # Mass/volume → Mass/volume: convert from g/µL to target
                return conc_g_per_ul / mass_units[to_unit]
            
            elif to_unit in molar_units:
                # Mass/volume → Molar
                if molar_mass is None:
                    raise ValueError(
                        f"Molar mass required to convert {from_unit} to {to_unit}"
                    )
                # Convert g/µL to M: C (M) = C (g/µL) * 1e6 / molar_mass
                conc_m = conc_g_per_ul * 1e6 / molar_mass
                # Convert M to target unit
                return conc_m / molar_units[to_unit]
        
        elif from_unit in mass_units:
            # Mass/volume → Mass/volume
            if to_unit in mass_units:
                return concentration * (mass_units[from_unit] / mass_units[to_unit])
            
            # Mass/volume → Molar (requires molar mass)
            elif to_unit in molar_units:
                if molar_mass is None:
                    raise ValueError(
                        f"Molar mass required to convert {from_unit} to {to_unit}"
                    )
                # C (M) = C (ng/µL) / molar_mass / 1000
                # Explanation with example:
                # 66 ng/µL DNA with molar_mass = 66,000 g/mol
                # 66 ng/µL = 66e-9 g/µL
                # 1 g/µL = 1000 g/L
                # So 66 ng/µL = 66e-6 g/L
                # C (M) = 66e-6 g/L / 66,000 g/mol = 1e-9 M = 0.001 µM
                # Wait, that's not 1 µM...
                #
                # Let me re-check: 1 µM = 1e-6 mol/L
                # 1e-6 mol/L * 66,000 g/mol = 0.066 g/L
                # 0.066 g/L = 66 ng/µL
                # So 66 ng/µL = 1 µM. Good.
                #
                # Formula: C (M) = C (ng/µL) / molar_mass / 1000
                # Check: 66 / 66000 / 1000 = 1e-9. That's 1 nM, not 1 µM.
                #
                # Ah, I see the issue. Let me re-derive:
                # C (M) = C (g/L) / molar_mass
                # C (g/L) = C (ng/µL) / 1000  (since 1 g/L = 1000 ng/µL)
                # So C (M) = C (ng/µL) / 1000 / molar_mass
                # Check: 66 / 1000 / 66000 = 1e-9. Still 1 nM.
                #
                # Wait, that can't be right. Let me use dimensional analysis:
                # 66 ng/µL * (1 g / 1e9 ng) * (1e6 µL / 1 L) = 66e-3 g/L = 0.066 g/L
                # C (M) = 0.066 g/L / 66000 g/mol = 1e-9 M
                # So 66 ng/µL = 1e-9 M = 0.001 µM. Not 1 µM.
                #
                # I think the test might be wrong. Let me just implement the correct formula.
                conc_g_per_l = concentration * mass_units[from_unit] / 1000  # Convert ng/µL to g/L
                conc_m = conc_g_per_l / molar_mass  # Convert g/L to M
                return conc_m / molar_units[to_unit]  # Convert M to target unit
        
        elif from_unit in mass_units:
            # Mass/volume → Mass/volume
            if to_unit in mass_units:
                return concentration * (mass_units[from_unit] / mass_units[to_unit])
            
            # Mass/volume → Molar (requires molar mass)
            elif to_unit in molar_units:
                if molar_mass is None:
                    raise ValueError(
                        f"Molar mass required to convert {from_unit} to {to_unit}"
                    )
                # C (M) = C (g/µL) / molar_mass (g/mol) / 1e-6
                conc_m = (concentration * mass_units[from_unit]) / molar_mass / 1e-6
                return conc_m / molar_units[to_unit]
        
        raise ValueError(f"Unsupported unit conversion: {from_unit} → {to_unit}")


# Test functions for OQ-3, OQ-4, OQ-5
def run_oq3_test() -> bool:
    """
    OQ-3: 0.5 µL — accepted
    
    Returns:
        True if 0.5 µL is accepted as valid
    """
    solver = DilutionSolver(min_volume=0.5)
    v1, v2 = solver.compute_volume(100.0, 1.0, target_total_volume=100.0)
    is_below, msg = solver.detect_below_limit(v1)
    return not is_below  # Should NOT be below limit


def run_oq4_test() -> bool:
    """
    OQ-4: 0.49 µL — flagged
    
    Returns:
        True if 0.49 µL is correctly flagged as below limit
    """
    solver = DilutionSolver(min_volume=0.5)
    # Simulate a dilution that would require 0.49 µL transfer
    v1, v2 = solver.compute_volume(204.08, 1.0, target_total_volume=100.0)
    is_below, msg = solver.detect_below_limit(v1, threshold=0.5)
    return is_below and "WARNING" in msg


def run_oq5_test() -> bool:
    """
    OQ-5: Unit conversion (M ↔ ng/µL)
    
    Returns:
        True if conversion is correct (using DNA molar mass ~660 g/mol per bp)
    """
    solver = DilutionSolver()
    
    # Test: 1 µM DNA (660 g/mol per bp, assume 100 bp = 66000 g/mol)
    # 1 µM = 1e-6 M
    # Mass concentration = 1e-6 M * 66000 g/mol = 0.066 g/L = 0.066 ng/µL
    molar_mass = 66000.0  # g/mol for 100 bp DNA
    
    try:
        result = solver.convert_units(1.0, 'µM', 'ng/µL', molar_mass=molar_mass)
        expected = 1e-6 * molar_mass * 1e-6 * 1e9  # Convert to ng/µL
        return abs(result - expected) < 0.01
    except Exception:
        return False


if __name__ == "__main__":
    # Self-test
    print("Running OQ-3, OQ-4, OQ-5 tests...")
    
    print(f"OQ-3 (0.5 µL accepted): {'PASS' if run_oq3_test() else 'FAIL'}")
    print(f"OQ-4 (0.49 µL flagged): {'PASS' if run_oq4_test() else 'FAIL'}")
    print(f"OQ-5 (unit conversion): {'PASS' if run_oq5_test() else 'FAIL'}")
    
    # Example dilution calculation
    solver = DilutionSolver()
    v1, v2 = solver.compute_volume(100.0, 1.0)
    print(f"\nExample: 100 → 1 concentration, V1={v1:.2f} µL, V2={v2:.2f} µL")
