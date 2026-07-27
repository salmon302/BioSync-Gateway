# SPDX-License-Identifier: MIT
"""
Synthetic Digital Twin Cohort Generation
Implements SRS FR-3.13.1–FR-3.13.5.

Generates deterministic, synthetic (no-PHI) digital-twin cohorts: N member
identities paired with ClinVar variant sets and physiological baselines, each
emitting a reactive FHIR Observation vital-trend stream (heart rate, SpO2,
blood pressure). Outputs are assembled into a unified, exportable, FHIR-R4
validated Bundle and flagged ``synthetic=true`` (FR-3.13.5).

Given the currently mocked Pulse Engine, vital trends are synthesized
deterministically (seeded random walk around baselines). The per-member seed
keeps the signature stable so a real Pulse stream can replace the generator
later without changing callers.
"""

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fhir_validator import FHIRValidator

# Vital channels emitted per member (FR-3.13.2): HR, SpO2, systolic/diastolic BP.
CHEM_VITALS_SPEC: Dict[str, Dict[str, Any]] = {
    "heart_rate": {"unit": "/min", "ucum": "/min", "loinc": "8867-4", "min": 60.0, "max": 100.0},
    "spo2": {"unit": "%", "ucum": "%", "loinc": "2708-6", "min": 95.0, "max": 100.0},
    "systolic_bp": {"unit": "mmHg", "ucum": "mm[Hg]", "loinc": "8480-6", "min": 100.0, "max": 140.0},
    "diastolic_bp": {"unit": "mmHg", "ucum": "mm[Hg]", "loinc": "8462-4", "min": 60.0, "max": 90.0},
}

GENOMICS_LOINC = "79711-5"  # Genetic variant (representative LOINC)


def _numeric_seed(seed: Optional[Any]) -> int:
    """Coerce an arbitrary seed (int or dict) into a stable 32-bit int."""
    if seed is None:
        return 0
    if isinstance(seed, int):
        return seed & 0xFFFFFFFF
    payload = json.dumps(seed, sort_keys=True).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest(), 16) & 0xFFFFFFFF


def _synthetic_id(seed: Any, index: int) -> str:
    """Deterministic, non-PHI synthetic member identifier."""
    material = f"{seed!r}:{index}".encode("utf-8")
    return "SYN-" + hashlib.sha256(material).hexdigest()[:12].upper()


def generate_cohort_members(
    spec: Dict[str, Any], seed: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Deterministically generate N synthetic member identities (FR-3.13.1).

    No real patient data is used; identities carry a synthetic id, sampled
    demographics, an assigned ClinVar variant, and physiological baselines.
    """
    rng = random.Random(_numeric_seed(seed))
    size = int(spec.get("size", 10))
    dem = spec.get("demographic_distribution", {}) or {}
    variants = spec.get("clinvar_variant_set", []) or []
    baselines = spec.get("physiological_baseline_ranges", {}) or {}

    age_range = dem.get("age", {})
    age_min = int(age_range.get("min", 18))
    age_max = int(age_range.get("max", 90))
    sexes = dem.get("sex", ["male", "female"])

    members: List[Dict[str, Any]] = []
    for i in range(size):
        age = rng.randint(age_min, age_max)
        sex = rng.choice(sexes)
        variant = variants[i % len(variants)] if variants else None
        baseline = {}
        for ch, sp in CHEM_VITALS_SPEC.items():
            lo = baselines.get(ch, {}).get("min", sp["min"])
            hi = baselines.get(ch, {}).get("max", sp["max"])
            baseline[ch] = round(rng.uniform(lo, hi), 1)
        members.append(
            {
                "synthetic_id": _synthetic_id(seed, i),
                "demographics": {"age": age, "sex": sex},
                "variant": variant,
                "baseline": baseline,
            }
        )
    return members


def _vital_observation(
    channel: str, spec: Dict[str, Any], value: float, synthetic_id: str, dt: str
) -> Dict[str, Any]:
    """Build a FHIR R4 Observation for a single vital sample."""
    return {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": spec["loinc"], "display": channel}],
            "text": channel,
        },
        "valueQuantity": {
            "value": value,
            "unit": spec["unit"],
            "system": "http://unitsofmeasure.org",
            "code": spec["ucum"],
        },
        "effectiveDateTime": dt,
        "subject": {"reference": f"Patient/{synthetic_id}"},
        "device": {"reference": f"Device/sim-{synthetic_id}"},
    }


def _genomics_observation(variant: Dict[str, Any], synthetic_id: str, dt: str) -> Dict[str, Any]:
    """Build a genomics-referenced Observation (validator-compatible shape)."""
    summary = f"{variant.get('gene', variant.get('name', 'variant'))}:{variant.get('clinical_significance', 'unknown')}"
    return {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {"system": "http://loinc.org", "code": GENOMICS_LOINC, "display": "Genetic variant"}
            ],
            "text": summary,
        },
        "valueQuantity": {
            "value": 1,
            "unit": "count",
            "system": "http://unitsofmeasure.org",
            "code": "1",
        },
        "effectiveDateTime": dt,
        "subject": {"reference": f"Patient/{synthetic_id}"},
        "device": {"reference": f"Device/sim-{synthetic_id}"},
        "note": [{"text": json.dumps(variant)}],
    }


def simulate_member_timeseries(
    member: Dict[str, Any],
    duration_min: float = 1.0,
    cadence_sec: float = 10.0,
    seed: Optional[Any] = None,
    index: int = 0,
) -> List[Dict[str, Any]]:
    """Generate a deterministic vital-trend Observation stream for one member.

    Implements FR-3.13.2 — reactive physiological trends emitted at the
    configured cadence. Returns a list of FHIR Observation dicts.
    """
    rng = random.Random(_numeric_seed(seed) + index)
    n_samples = max(1, int((duration_min * 60.0) // cadence_sec))
    start = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(
        seconds=_numeric_seed(seed) % 86400
    )
    base = member["baseline"]
    synthetic_id = member["synthetic_id"]

    observations: List[Dict[str, Any]] = []
    for s in range(n_samples):
        dt = (start + timedelta(seconds=s * cadence_sec)).isoformat()
        for ch, sp in CHEM_VITALS_SPEC.items():
            if ch == "spo2":
                val = base[ch] + rng.uniform(-1.0, 1.0)
                val = max(0.0, min(100.0, val))
            else:
                val = base[ch] + rng.uniform(-3.0, 3.0)
            observations.append(
                _vital_observation(ch, sp, round(val, 1), synthetic_id, dt)
            )
    return observations


def assemble_cohort_bundle(
    members: List[Dict[str, Any]],
    timeseries_by_member: Dict[str, List[Dict[str, Any]]],
    validate: bool = True,
    seed: Optional[Any] = None,
) -> Dict[str, Any]:
    """Assemble the unified, exportable cohort Bundle (FR-3.13.4).

    Combines each member's vital-trend Observations with a genomics
    Observation for its paired ClinVar variant. Validates against FHIR R4
    (FR-3.13.3) and raises ``ValueError`` on failure.

    When ``seed`` is provided, the Bundle timestamp and genomics
    ``effectiveDateTime`` are derived deterministically from it so exports are
    reproducible (FR-3.16.4); otherwise the current time is used.
    """
    if seed is not None:
        ts_base = (
            datetime(2026, 1, 1, tzinfo=timezone.utc)
            + timedelta(seconds=_numeric_seed(seed) % 86400)
        ).isoformat()
    else:
        ts_base = _now_iso()

    entries: List[Dict[str, Any]] = []
    for m in members:
        sid = m["synthetic_id"]
        for obs in timeseries_by_member.get(sid, []):
            entries.append({"resource": obs, "request": {"method": "POST", "url": "Observation"}})
        if m.get("variant"):
            entries.append(
                {
                    "resource": _genomics_observation(m["variant"], sid, ts_base),
                    "request": {"method": "POST", "url": "Observation"},
                }
            )

    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "timestamp": ts_base,
        "entry": entries,
    }

    if validate:
        validator = FHIRValidator()
        ok, errors = validator.validate_bundle(bundle)
        if not ok:
            messages = [getattr(e, "message", str(e)) for e in errors]
            raise ValueError(f"FHIR Bundle validation failed: {messages}")

    return bundle


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_synthetic_cohort(
    db,
    spec: Dict[str, Any],
    scenario_run_id: Optional[int] = None,
    duration_min: float = 1.0,
    cadence_sec: float = 10.0,
    validate: bool = True,
    created_by: Optional[str] = None,
) -> Any:
    """Orchestrate cohort generation and persist a ``SyntheticCohort`` (FR-3.13).

    Returns the persisted ORM instance. The exportable Bundle is regenerable
    later via :func:`export_cohort_bundle` from the stored members + seed.
    """
    import uuid

    from models import SyntheticCohort

    seed = spec.get("seed")
    members = generate_cohort_members(spec, seed)

    # FR-3.13.2 (optional real Pulse Engine): when active, nudge each member's
    # baseline physiology toward a live Pulse simulation. Seed-deterministic
    # synthesis remains the default (C7).
    try:
        from engine.pulse_bridge import real_pulse_available, pulse_baseline

        if real_pulse_available():
            pb = pulse_baseline(spec.get("name", "digital_twin"))
            if pb:
                _pb_map = {
                    "heart_rate": "heart_rate",
                    "spo2": "spo2",
                    "systolic": "blood_pressure_systolic",
                    "diastolic": "blood_pressure_diastolic",
                    "respiratory_rate": "respiratory_rate",
                }
                for m in members:
                    b = m.get("baseline")
                    if isinstance(b, dict):
                        for dst, src in _pb_map.items():
                            if dst in b and src in pb:
                                b[dst] = pb[src]
    except Exception:  # pragma: no cover - only active with real engine
        pass
    timeseries_by_member = {
        m["synthetic_id"]: simulate_member_timeseries(
            m, duration_min=duration_min, cadence_sec=cadence_sec, seed=seed, index=i
        )
        for i, m in enumerate(members)
    }
    # Validate the assembled bundle up-front (FR-3.13.3) but do not persist it.
    assemble_cohort_bundle(members, timeseries_by_member, validate=validate, seed=seed)

    row = SyntheticCohort(
        cohort_uid=str(uuid.uuid4()),
        name=spec.get("name"),
        size=len(members),
        demographic_distribution=spec.get("demographic_distribution"),
        clinvar_variant_set=spec.get("clinvar_variant_set"),
        physiological_baseline_ranges=spec.get("physiological_baseline_ranges"),
        members=members,
        is_synthetic=True,
        seed=seed,
        scenario_run_id=scenario_run_id,
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def export_cohort_bundle(
    cohort_row,
    duration_min: float = 1.0,
    cadence_sec: float = 10.0,
    validate: bool = True,
) -> Dict[str, Any]:
    """Rebuild the exportable cohort Bundle from a stored cohort (FR-3.13.4).

    Reproducible from the persisted members + seed (FR-3.16.4).
    """
    members = cohort_row.members or []
    seed = cohort_row.seed
    timeseries_by_member = {
        m["synthetic_id"]: simulate_member_timeseries(
            m, duration_min=duration_min, cadence_sec=cadence_sec, seed=seed, index=i
        )
        for i, m in enumerate(members)
    }
    return assemble_cohort_bundle(
        members, timeseries_by_member, validate=validate, seed=seed
    )
