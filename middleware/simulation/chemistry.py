# SPDX-License-Identifier: MIT
"""
Closed-Loop Clinical Chemistry Data Generation
Implements SRS FR-3.12.1–FR-3.12.4.

Extracts (or, given the currently mocked Pulse Engine, synthesizes
deterministically) a defined set of clinical chemistry vectors — blood gas
fractions (pO2, pCO2, pH, HCO3-), electrolytes (Na+, K+, Cl-, Ca2+), and
metabolic substrates (glucose, lactate) — then assembles them with ClinVar
genomic variant data into a unified multi-modal FHIR Bundle (type: transaction)
and optionally stress-tests a downstream LIMS ingestion webhook.

The generator is fully deterministic from a seed (FR-3.12.4 / FR-3.16.4):
the same seed always reproduces the identical vectors and Bundle, enabling
regression testing of downstream ingestion schemas.
"""

import hashlib
import json
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from fhir_validator import FHIRValidator, ValidationError

# ---------------------------------------------------------------------------
# Vector specification: analyte -> (UCUM display, UCUM code, loinc, min, max)
# ---------------------------------------------------------------------------
CHEMISTRY_VECTOR_SPEC: Dict[str, Dict[str, Dict[str, Any]]] = {
    "blood_gas": {
        "pO2":  {"unit": "mmHg", "ucum": "mm[Hg]", "loinc": "2703-1", "min": 70.0,  "max": 100.0},
        "pCO2": {"unit": "mmHg", "ucum": "mm[Hg]", "loinc": "11557-2", "min": 35.0, "max": 45.0},
        "pH":   {"unit": "pH",   "ucum": "1",      "loinc": "2747-8", "min": 7.35,  "max": 7.45},
        "HCO3": {"unit": "mmol/L", "ucum": "mmol/L", "loinc": "33021-2", "min": 22.0, "max": 26.0},
    },
    "electrolytes": {
        "Na": {"unit": "mmol/L", "ucum": "mmol/L", "loinc": "2947-0", "min": 135.0, "max": 145.0},
        "K":  {"unit": "mmol/L", "ucum": "mmol/L", "loinc": "2823-3", "min": 3.5,   "max": 5.0},
        "Cl": {"unit": "mmol/L", "ucum": "mmol/L", "loinc": "2075-0", "min": 98.0,  "max": 106.0},
        "Ca": {"unit": "mmol/L", "ucum": "mmol/L", "loinc": "17861-3", "min": 2.1,  "max": 2.6},
    },
    "metabolic": {
        "glucose":  {"unit": "mg/dL", "ucum": "mg/dL", "loinc": "2339-0", "min": 70.0,  "max": 110.0},
        "lactate": {"unit": "mmol/L", "ucum": "mmol/L", "loinc": "15310-0", "min": 0.5, "max": 2.0},
    },
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


def generate_chemistry_vectors(
    seed: Optional[Any] = None,
    simulation_id: Optional[int] = None,
    patient_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a deterministic set of clinical chemistry vectors (FR-3.12.1).

    Values are sampled within physiological ranges using a seed-derived PRNG,
    so identical seeds reproduce identical output (FR-3.12.4).
    """
    rng = random.Random(_numeric_seed(seed))
    vectors: Dict[str, Any] = {"simulation_id": simulation_id, "patient_id": patient_id}
    for category, analytes in CHEMISTRY_VECTOR_SPEC.items():
        cat_out = {}
        for name, spec in analytes.items():
            value = rng.uniform(spec["min"], spec["max"])
            decimals = 2 if spec["ucum"] != "1" else 3  # pH needs more precision
            cat_out[name] = {
                "value": round(value, decimals),
                "unit": spec["unit"],
                "ucum": spec["ucum"],
                "loinc": spec["loinc"],
            }
        vectors[category] = cat_out
    return vectors


def _observation_resource(
    name: str,
    spec: Dict[str, Any],
    value: float,
    patient_id: Optional[str],
    effective_dt: str,
) -> Dict[str, Any]:
    """Build a FHIR R4 Observation resource for a single chemistry analyte."""
    resource = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": spec["loinc"],
                    "display": name,
                }
            ],
            "text": name,
        },
        "valueQuantity": {
            "value": value,
            "unit": spec["unit"],
            "system": "http://unitsofmeasure.org",
            "code": spec["ucum"],
        },
        "effectiveDateTime": effective_dt,
    }
    if patient_id:
        resource["subject"] = {"reference": f"Patient/{patient_id}"}
    return resource


def _genomics_resource(
    clinvar_data: Dict[str, Any], patient_id: Optional[str], effective_dt: str
) -> Dict[str, Any]:
    """Build a genomics-referenced Observation from ClinVar variant data.

    The project FHIR validator requires ``valueQuantity`` on every Observation
    (telemetry-focused), so the genomics entry carries the variant count as a
    quantity and the full variant detail in ``note``.
    """
    variants = clinvar_data.get("variants")
    if not variants:
        variants = [clinvar_data] if clinvar_data else []
    summary = "; ".join(
        f"{v.get('gene', v.get('name', 'variant'))}:{v.get('clinical_significance', 'unknown')}"
        for v in variants
    )
    resource = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": GENOMICS_LOINC,
                    "display": "Genetic variant",
                }
            ],
            "text": summary or "no variant data",
        },
        "valueQuantity": {
            "value": len(variants),
            "unit": "count",
            "system": "http://unitsofmeasure.org",
            "code": "1",
        },
        "effectiveDateTime": effective_dt,
        "note": [{"text": json.dumps(clinvar_data)}],
    }
    if patient_id:
        resource["subject"] = {"reference": f"Patient/{patient_id}"}
    return resource


def assemble_multimodal_bundle(
    chemistry_vectors: Dict[str, Any],
    clinvar_data: Optional[Dict[str, Any]] = None,
    patient_id: Optional[str] = None,
    validate: bool = True,
) -> Dict[str, Any]:
    """Assemble chemistry + genomics into a FHIR transaction Bundle (FR-3.12.2).

    Validates the Bundle against FHIR R4 (FR-3.7.1) and raises ``ValueError``
    listing any validation errors when ``validate`` is True.
    """
    effective_dt = datetime.now(timezone.utc).isoformat()

    entries: List[Dict[str, Any]] = []
    for category, analytes in CHEMISTRY_VECTOR_SPEC.items():
        cat = chemistry_vectors.get(category, {})
        for name, spec in analytes.items():
            value = cat.get(name, {}).get("value")
            if value is None:
                continue
            obs = _observation_resource(name, spec, value, patient_id, effective_dt)
            entries.append(
                {
                    "resource": obs,
                    "request": {"method": "POST", "url": "Observation"},
                }
            )

    if clinvar_data:
        entries.append(
            {
                "resource": _genomics_resource(clinvar_data, patient_id, effective_dt),
                "request": {"method": "POST", "url": "Observation"},
            }
        )

    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "timestamp": effective_dt,
        "entry": entries,
    }

    if validate:
        validator = FHIRValidator()
        ok, errors = validator.validate_bundle(bundle)
        if not ok:
            messages = [e.message if hasattr(e, "message") else str(e) for e in errors]
            raise ValueError(f"FHIR Bundle validation failed: {messages}")

    return bundle


def send_lims_bundle(bundle: Dict[str, Any], webhook_url: str, timeout: float = 10.0) -> Dict[str, Any]:
    """POST the Bundle to a downstream LIMS ingestion webhook (FR-3.12.3).

    Captures the HTTP status and body (including any OperationOutcome) for
    audit. Resilient to transport errors.
    """
    try:
        resp = httpx.post(webhook_url, json=bundle, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {
            "ok": resp.is_success,
            "status_code": resp.status_code,
            "body": body,
        }
    except httpx.HTTPError as e:
        return {"ok": False, "status_code": None, "error": str(e)}


def generate_chemistry_profile(
    db,
    seed: Optional[Any] = None,
    simulation_id: Optional[int] = None,
    patient_id: Optional[str] = None,
    clinvar_data: Optional[Dict[str, Any]] = None,
    scenario_run_id: Optional[int] = None,
    lims_webhook_url: Optional[str] = None,
    validate: bool = True,
) -> Any:
    """Orchestrate chemistry generation and persist a ``ChemistryProfile`` (FR-3.12).

    Returns the persisted ORM instance (with ``id`` populated after flush).
    """
    import uuid

    from models import ChemistryProfile

    vectors = generate_chemistry_vectors(
        seed, simulation_id=simulation_id, patient_id=patient_id
    )
    bundle = assemble_multimodal_bundle(
        vectors, clinvar_data=clinvar_data, patient_id=patient_id, validate=validate
    )
    lims_response = None
    if lims_webhook_url:
        lims_response = send_lims_bundle(bundle, lims_webhook_url)

    row = ChemistryProfile(
        profile_uid=str(uuid.uuid4()),
        simulation_id=simulation_id,
        patient_id=patient_id,
        chemistry_vectors=vectors,
        clinvar_data=clinvar_data,
        fhir_bundle=bundle,
        lims_response=lims_response,
        seed=seed,
        scenario_run_id=scenario_run_id,
    )
    db.add(row)
    db.flush()
    return row
