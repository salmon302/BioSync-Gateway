# SPDX-License-Identifier: MIT
"""
In Silico Pharmacokinetics / Pharmacodynamics (PK/PD) Lab Loop
Implements SRS FR-3.11.1–FR-3.11.4.

Connects a substance's PK parameters to BioSync's Automated Dilution Solver
(``engine.dilution.DilutionSolver``) to emit validated microplate pipetting
worklists (FR-3.2.5) tagged ``origin=pk_pd_loop``.

The plasma concentration time-series is derived from a standard one-compartment
IV-bolus model so the loop is fully deterministic and reproducible from the
substance's PK parameters (supports FR-3.16.4 deterministic replay). No RNG is
used; the optional ``seed`` is stored only for provenance/auditability.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

import math

from engine.dilution import DilutionSolver


@dataclass
class PkpdSubstance:
    """A pharmacologic agent registered into the simulation with PK parameters.

    Implements SRS FR-3.11.1. All concentrations are derived from these values.
    """

    name: str
    volume_of_distribution: float  # Vd, liters
    clearance: float               # CL, L/h
    elimination_half_life: float   # hours
    dose: float                    # administered amount (per ``dose_unit``)
    dose_unit: str = "mg"          # e.g. mg, µg, g
    molar_mass: Optional[float] = None  # g/mol; enables molar-unit targets

    @property
    def elimination_rate_constant(self) -> float:
        """First-order elimination rate constant k (1/h): k = CL / Vd."""
        if self.volume_of_distribution <= 0:
            raise ValueError("volume_of_distribution must be positive")
        if self.clearance <= 0:
            raise ValueError("clearance must be positive")
        return self.clearance / self.volume_of_distribution

    def canonical_unit(self) -> str:
        """Concentration unit used for the simulated plasma curve.

        ``mg/L`` when no molar mass is known; ``µM`` when ``molar_mass`` is set.
        """
        return "µM" if self.molar_mass else "mg/L"

    def initial_concentration(self) -> float:
        """C0 after an IV bolus: dose / Vd, expressed in :meth:`canonical_unit`."""
        if self.dose <= 0:
            raise ValueError("dose must be positive")
        if self.volume_of_distribution <= 0:
            raise ValueError("volume_of_distribution must be positive")
        c0_mg_per_l = self.dose / self.volume_of_distribution  # dose assumed mg
        if self.molar_mass:
            # mg/L -> µM:  C(µM) = C(mg/L) * 1000 / molar_mass
            return c0_mg_per_l * 1000.0 / self.molar_mass
        return c0_mg_per_l


def simulate_clearance(
    substance: PkpdSubstance,
    horizon_h: float = 24.0,
    interval_h: float = 1.0,
    t0: float = 0.0,
) -> List[Dict[str, float]]:
    """Sample the simulated plasma concentration time-series (FR-3.11.2).

    One-compartment IV-bolus model:  C(t) = C0 · exp(−k·t).

    Deterministic and reproducible from ``substance`` parameters.

    Returns a list of ``{"time_h": float, "concentration": float, "unit": str}``.
    """
    if horizon_h <= 0 or interval_h <= 0:
        raise ValueError("horizon_h and interval_h must be positive")
    k = substance.elimination_rate_constant
    c0 = substance.initial_concentration()
    unit = substance.canonical_unit()
    series: List[Dict[str, float]] = []
    t = t0
    while t <= horizon_h + 1e-9:
        concentration = c0 * math.exp(-k * t)
        series.append(
            {"time_h": round(t, 6), "concentration": concentration, "unit": unit}
        )
        t += interval_h
    return series


def derive_target_matrix(
    series: List[Dict[str, float]],
    sample_times_h: List[float],
) -> List[Dict[str, Any]]:
    """Derive target concentration matrix at requested times (FR-3.11.3).

    Linearly interpolates the simulated curve at each requested sample time.
    Returns a list of ``{"time_h", "target_concentration", "unit"}``.
    """
    if not series:
        raise ValueError("concentration series is empty")
    unit = series[0]["unit"]
    xs = [pt["time_h"] for pt in series]
    ys = [pt["concentration"] for pt in series]
    targets: List[Dict[str, Any]] = []
    for st in sample_times_h:
        targets.append(
            {
                "time_h": st,
                "target_concentration": _interpolate(xs, ys, st),
                "unit": unit,
            }
        )
    return targets


def _interpolate(xs: List[float], ys: List[float], x: float) -> float:
    """Linear interpolation of (xs, ys) at x, clamped to the endpoints."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if xs[i] >= x:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return ys[-1]


def build_pkpd_worklist_steps(
    substance: PkpdSubstance,
    target_matrix: List[Dict[str, Any]],
    initial_concentration: float,
    initial_unit: str,
    target_total_volume_ul: float = 100.0,
    min_volume_ul: float = 0.5,
) -> Dict[str, Any]:
    """Compute per-well pipetting instructions feeding the Dilution Solver.

    Implements SRS FR-3.11.4 — converts each derived target concentration into a
    per-well transfer volume (and a pre-dilution chain when below the pipetting
    limit), then assembles the validated worklist tagged ``origin=pk_pd_loop``.

    Returns a dict with ``steps`` (per-well), ``warnings`` and aggregate info.
    """
    solver = DilutionSolver(min_volume=min_volume_ul)
    canonical_unit = substance.canonical_unit()

    # Normalize the stock/initial concentration into the canonical unit so we
    # compute volumes against the (same-unit) target concentrations.
    c_stock = initial_concentration
    if initial_unit != canonical_unit:
        try:
            c_stock = solver.convert_units(
                initial_concentration, initial_unit, canonical_unit, substance.molar_mass
            )
        except ValueError as e:
            raise ValueError(
                f"Cannot convert initial concentration from {initial_unit} to "
                f"{canonical_unit} (missing molar_mass?): {e}"
            )

    well_count = len(target_matrix)
    cols = 12 if well_count <= 96 else 24

    steps: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for idx, target in enumerate(target_matrix):
        target_conc = target["target_concentration"]
        target_unit = target["unit"]

        if target_conc <= 0:
            # Negligible target — no transfer required.
            steps.append(
                {
                    "well_index": idx,
                    "row": idx // cols,
                    "col": idx % cols,
                    "time_h": target["time_h"],
                    "target_concentration": target_conc,
                    "target_unit": target_unit,
                    "transfer_volume_ul": 0.0,
                    "diluent_volume_ul": target_total_volume_ul,
                    "total_volume_ul": target_total_volume_ul,
                    "pre_dilution": [],
                    "warning": "target concentration ~0; no transfer computed",
                }
            )
            continue

        if target_conc >= c_stock:
            warnings.append(
                f"Well {idx}: target {target_conc} {target_unit} >= stock "
                f"{c_stock} {canonical_unit}; dilution upward not supported."
            )
            steps.append(
                {
                    "well_index": idx,
                    "row": idx // cols,
                    "col": idx % cols,
                    "time_h": target["time_h"],
                    "target_concentration": target_conc,
                    "target_unit": target_unit,
                    "transfer_volume_ul": None,
                    "diluent_volume_ul": None,
                    "total_volume_ul": None,
                    "pre_dilution": [],
                    "warning": "target >= stock; no transfer computed",
                }
            )
            continue

        v1, v2 = solver.compute_volume(c_stock, target_conc, target_total_volume_ul)
        is_below, msg = solver.detect_below_limit(v1)
        pre_dilution: List[Dict[str, Any]] = []
        warning = None
        if is_below:
            wl = solver.generate_pre_dilution(c_stock, target_conc, substance.molar_mass)
            pre_dilution = [s.__dict__ for s in wl.steps]
            warning = msg
            warnings.append(f"Well {idx}: {msg}")

        steps.append(
            {
                "well_index": idx,
                "row": idx // cols,
                "col": idx % cols,
                "time_h": target["time_h"],
                "target_concentration": target_conc,
                "target_unit": target_unit,
                "transfer_volume_ul": round(v1, 4),
                "diluent_volume_ul": round(v2, 4),
                "total_volume_ul": round(v1 + v2, 4),
                "pre_dilution": pre_dilution,
                "warning": warning,
            }
        )

    return {
        "origin": "pk_pd_loop",
        "stock_concentration": c_stock,
        "stock_unit": canonical_unit,
        "target_total_volume_ul": target_total_volume_ul,
        "well_count": well_count,
        "steps": steps,
        "warnings": warnings,
    }


def generate_pkpd_worklist(
    db,
    substance: PkpdSubstance,
    initial_concentration: float,
    initial_unit: str,
    plate_format: str = "96-well",
    plate_id: Optional[int] = None,
    horizon_h: float = 24.0,
    interval_h: float = 1.0,
    target_total_volume_ul: float = 100.0,
    sample_times_h: Optional[List[float]] = None,
    num_wells: Optional[int] = None,
    scenario_run_id: Optional[int] = None,
    seed: Optional[Dict[str, Any]] = None,
    min_volume_ul: float = 0.5,
) -> Any:
    """Orchestrate the PK/PD loop and persist a ``PkpdWorklist`` row (FR-3.11.4).

    Returns the persisted ORM instance (with ``id`` populated after flush).
    """
    from models import PkpdWorklist
    import uuid

    # Determine the target sample times / well count.
    if sample_times_h is None:
        n = num_wells or (96 if plate_format == "96-well" else 384)
        # Spread n sample points evenly across the horizon (excluding t=0,
        # where the concentration equals C0 — not a useful replication target).
        sample_times_h = [
            round(horizon_h * (i + 1) / (n + 1), 4) for i in range(n)
        ]

    series = simulate_clearance(substance, horizon_h=horizon_h, interval_h=interval_h)
    target_matrix = derive_target_matrix(series, sample_times_h)
    worklist = build_pkpd_worklist_steps(
        substance,
        target_matrix,
        initial_concentration,
        initial_unit,
        target_total_volume_ul=target_total_volume_ul,
        min_volume_ul=min_volume_ul,
    )

    row = PkpdWorklist(
        worklist_uid=str(uuid.uuid4()),
        plate_id=plate_id,
        substance_name=substance.name,
        pk_parameters=asdict(substance),
        plasma_concentration_series=series,
        target_matrix=target_matrix,
        steps=worklist,
        origin="pk_pd_loop",
        is_finalized=False,
        scenario_run_id=scenario_run_id,
    )
    db.add(row)
    db.flush()

    # FR-3.11.1 (optional real Pulse Engine): register the substance into an
    # active Pulse simulation when the bridge is enabled. Synthesis is unchanged
    # (C7).
    try:
        from engine.pulse_bridge import register_pulse_substance

        register_pulse_substance(substance, "pk_pd_loop")
    except Exception:  # pragma: no cover - only active with real engine
        pass
    return row
