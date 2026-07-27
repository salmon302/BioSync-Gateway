# SPDX-License-Identifier: MIT
"""
Liquid Biopsy / Minimal Residual Disease (MRD) Analytical Sandbox
Implements SRS FR-3.14.1–FR-3.14.4 (backed by table ``cfdna_sandbox_runs``, SRS §6.1).

The sandbox models how acute systemic stressors skew cell-free DNA (cfDNA)
shedding and plasma-volume baselines, then reports assay Limit-of-Detection
(LOD) pass/fail against the simulated plasma cfDNA concentration, and finally
verifies round-trip fidelity by emitting FHIR Observation payloads to a
configurable LIMS ingestion webhook.

Design notes / determinism (SRS C7, FR-3.16.4):
  * The stressor-injection and cfDNA shedding-transfer functions are pure,
    deterministic functions of an input physiology + stressor + (optionally)
    seeded RNG, so identical inputs always reproduce identical outputs. This
    mirrors the other v1.1 analytics modules (pkpd / chemistry / digital_twin)
    and keeps the sandbox reproducible from a stored seed or serialized state.
  * ``simulation_id`` / ``cohort_id`` are stored for provenance/linkage to an
    active Pulse simulation or synthetic cohort but do not make the transfer
    functions non-deterministic. Live Pulse stressor actions are performed by
    the Pulse Engine at the orchestration layer; this module supplies the
    deterministic transfer-function core plus the LOD and LIMS verification.
"""

import hashlib
import json
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from fhir_validator import FHIRValidator

# ---------------------------------------------------------------------------
# Constants & defaults
# ---------------------------------------------------------------------------

# Representative LOINC for a plasma cell-free DNA concentration observation.
# Sandbox data is synthetic — align this to the local LIMS value set if needed.
CFDNA_CONCENTRATION_LOINC = "80326-9"

# Default healthy-adult baseline physiology used when no explicit baseline or
# linked simulation is supplied. Plasma volume in mL; pressures in mmHg.
DEFAULT_BASELINE_PHYSIOLOGY: Dict[str, float] = {
    "plasma_volume_ml": 3000.0,
    "heart_rate": 72.0,
    "systolic_bp": 120.0,
    "diastolic_bp": 80.0,
    "spo2": 98.0,
    # Mean arterial pressure is derived; included for convenience.
    "mean_arterial_pressure": 93.3,
    "temperature_c": 37.0,
}

# Stressor presets (FR-3.14.1). Each maps to a deterministic perturbation of the
# baseline physiology. ``severity`` (0..1) scales the magnitude of the effect.
STRESSOR_PRESETS: Dict[str, Dict[str, Any]] = {
    "baseline": {
        "description": "No stressor — quiescent physiology.",
    },
    "respiratory_distress": {
        "description": (
            "Acute respiratory distress scenario: hypoxemia, compensatory "
            "tachycardia, mild hypotension, and capillary leak (third-spacing) "
            "that reduces effective plasma volume."
        ),
    },
    "fluid_clearance_perturbation": {
        "description": (
            "Erratic fluid-clearance (diuretic/renal) perturbation: volatile "
            "reduction in plasma volume with mild hypotension and tachycardia."
        ),
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _numeric_seed(seed: Optional[Any]) -> int:
    """Coerce an arbitrary seed (int or dict) into a stable 32-bit int."""
    if seed is None:
        return 0
    if isinstance(seed, int):
        return seed & 0xFFFFFFFF
    payload = json.dumps(seed, sort_keys=True).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest(), 16) & 0xFFFFFFFF


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mean_arterial_pressure(systolic: float, diastolic: float) -> float:
    return diastolic + (systolic - diastolic) / 3.0


# ---------------------------------------------------------------------------
# FR-3.14.1 — Stressor injection
# ---------------------------------------------------------------------------

def apply_stressor(
    baseline: Dict[str, float],
    stressor: Dict[str, Any],
) -> Dict[str, float]:
    """Inject an acute systemic stressor into a physiology baseline (FR-3.14.1).

    Returns a *new* physiology dict with plasma volume and hemodynamic baselines
    altered per the stressor type. Deterministic (no RNG) so that a given
    baseline + stressor always yields the same altered state.

    Supported stressor shapes:
      {"type": "respiratory_distress", "severity": 0..1}
      {"type": "fluid_clearance_perturbation", "severity": 0..1}
      {"type": "custom", "overrides": {"plasma_volume_ml": 2500, ...}}
      {"type": "baseline"}  (or severity <= 0) -> unchanged baseline
    """
    if not stressor:
        return dict(baseline)

    stype = stressor.get("type", "baseline")
    severity = float(stressor.get("severity", 0.5))

    if stype == "baseline" or severity <= 0:
        return dict(baseline)

    b = dict(baseline)
    if stype == "respiratory_distress":
        # Hypoxemia + compensatory tachycardia + mild hypotension; capillary
        # leak (third-spacing) reduces effective plasma volume.
        b["spo2"] = _clamp(baseline["spo2"] - 20.0 * severity, 40.0, 100.0)
        b["heart_rate"] = baseline["heart_rate"] + 30.0 * severity
        b["systolic_bp"] = baseline["systolic_bp"] - 10.0 * severity
        b["diastolic_bp"] = baseline["diastolic_bp"] - 5.0 * severity
        b["plasma_volume_ml"] = baseline["plasma_volume_ml"] * (1.0 - 0.15 * severity)
    elif stype == "fluid_clearance_perturbation":
        # Erratic diuresis: plasma volume swings downward; the *volatility* of
        # that reduction is modeled in the shedding step (seeded RNG).
        b["plasma_volume_ml"] = baseline["plasma_volume_ml"] * (1.0 - 0.25 * severity)
        b["heart_rate"] = baseline["heart_rate"] + 10.0 * severity
        b["systolic_bp"] = baseline["systolic_bp"] - 15.0 * severity
        b["diastolic_bp"] = baseline["diastolic_bp"] - 8.0 * severity
        b["spo2"] = baseline["spo2"] - 2.0 * severity
    elif stype == "custom":
        # Explicit overrides win (validated loosely against known keys).
        for k, v in (stressor.get("overrides") or {}).items():
            b[k] = v
    else:
        raise ValueError(
            f"Unknown stressor type '{stype}'. "
            f"Known types: {list(STRESSOR_PRESETS.keys())} + 'custom'."
        )

    b["mean_arterial_pressure"] = _mean_arterial_pressure(
        b["systolic_bp"], b["diastolic_bp"]
    )
    return b


# ---------------------------------------------------------------------------
# FR-3.14.2 — cfDNA shedding transfer function
# ---------------------------------------------------------------------------

def cfdna_shedding(
    plasma_volume_ml: float,
    hemodynamic_state: Dict[str, float],
    theta_shed: Optional[Dict[str, Any]] = None,
    seed: Optional[Any] = None,
    n_samples: int = 1,
    volatility: float = 0.0,
) -> Dict[str, Any]:
    """cfDNA shedding transfer function (FR-3.14.2).

    Maps the (stressor-altered) physiology to a plasma cfDNA concentration:

        C_cfDNA = f(plasma volume, hemodynamic state; theta_shed)

    * ``theta_shed['baseline_copies']`` — total shed cfDNA copies in steady
      state (scaled to plasma volume to yield copies/mL).
    * ``theta_shed['stress_gain']`` — how strongly the hemodynamic stress index
      amplifies shedding.
    * A hemodynamic stress index ``H`` combines hypoxemia, hypotension, and
      tachycardia, then ``total_copies = baseline_copies * (1 + stress_gain*H)``
      and ``C_cfDNA = total_copies / plasma_volume_ml``.

    Returns the deterministic mean plus, when ``volatility`` > 0 and
    ``n_samples`` > 1, a reproducible seeded sample set modeling stressor-
    induced volatility (FR-3.14.3 / FR-3.14.4 extreme-LOD testing).
    """
    theta = dict(theta_shed or {})
    baseline_copies = float(theta.get("baseline_copies", 3000.0))
    stress_gain = float(theta.get("stress_gain", 3.0))

    spo2 = hemodynamic_state.get("spo2", DEFAULT_BASELINE_PHYSIOLOGY["spo2"])
    map_ = hemodynamic_state.get(
        "mean_arterial_pressure", DEFAULT_BASELINE_PHYSIOLOGY["mean_arterial_pressure"]
    )
    hr = hemodynamic_state.get("heart_rate", DEFAULT_BASELINE_PHYSIOLOGY["heart_rate"])

    # Hemodynamic stress index H (0 = quiescent, increasing with distress).
    hypoxia = max(0.0, (98.0 - spo2) / 15.0)
    hypotension = max(0.0, (93.3 - map_) / 20.0)
    tachycardia = max(0.0, (hr - 72.0) / 40.0)
    H = _clamp(hypoxia + hypotension + tachycardia, 0.0, 5.0)

    stress_factor = 1.0 + stress_gain * H
    total_copies = baseline_copies * stress_factor
    mean_conc = total_copies / float(plasma_volume_ml) if plasma_volume_ml > 0 else 0.0

    samples: List[float] = [mean_conc]
    if n_samples > 1 or volatility > 0.0:
        rng = random.Random(_numeric_seed(seed))
        samples = []
        for _ in range(max(1, n_samples)):
            noise = 1.0 + rng.gauss(0.0, volatility) if volatility > 0.0 else 1.0
            samples.append(max(0.0, mean_conc * noise))

    return {
        "mean_copies_per_ml": mean_conc,
        "samples": samples,
        "stress_index": H,
        "stress_factor": stress_factor,
        "total_copies": total_copies,
        "plasma_volume_ml": plasma_volume_ml,
    }


# ---------------------------------------------------------------------------
# FR-3.14.3 — LOD boundary simulation
# ---------------------------------------------------------------------------

def evaluate_lod(
    concentration_samples: List[float],
    lod_threshold: Optional[float],
) -> Dict[str, Any]:
    """Evaluate detection pass/fail against the assay LOD (FR-3.14.3).

    A draw is *detected* (pass) when its concentration >= ``lod_threshold``.
    The aggregate ``detection_result`` is:
      * 'pass'   — mean concentration clears the LOD
      * 'fail'   — mean concentration is below the LOD
      * 'pending'— no LOD configured (threshold is None)
    """
    samples = [float(c) for c in (concentration_samples or [])]
    if lod_threshold is None:
        return {
            "configured": False,
            "lod_threshold": None,
            "detection_result": "pending",
            "mean_concentration": (sum(samples) / len(samples)) if samples else None,
            "detection_rate": None,
            "detected_per_sample": None,
        }

    threshold = float(lod_threshold)
    detected = [c >= threshold for c in samples]
    rate = (sum(detected) / len(detected)) if detected else 0.0
    mean_c = (sum(samples) / len(samples)) if samples else 0.0
    detection_result = "pass" if mean_c >= threshold else "fail"
    return {
        "configured": True,
        "lod_threshold": threshold,
        "detection_result": detection_result,
        "mean_concentration": mean_c,
        "detection_rate": rate,
        "detected_per_sample": detected,
    }


# ---------------------------------------------------------------------------
# FR-3.14.4 — FHIR Observation + LIMS webhook verification
# ---------------------------------------------------------------------------

def build_cfdna_observation(
    concentration: float,
    patient_id: Optional[str] = None,
    lod_result: Optional[Dict[str, Any]] = None,
    loinc: str = CFDNA_CONCENTRATION_LOINC,
    effective_dt: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a FHIR R4 Observation for the simulated cfDNA concentration."""
    resource = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": loinc,
                    "display": "Cell-free DNA concentration (plasma)",
                }
            ],
            "text": "cfDNA concentration",
        },
        "valueQuantity": {
            "value": concentration,
            "unit": "copies/mL",
            "system": "http://unitsofmeasure.org",
            "code": "{copies}/mL",
        },
        "effectiveDateTime": effective_dt or _now_iso(),
    }
    if patient_id:
        resource["subject"] = {"reference": f"Patient/{patient_id}"}
    note_parts: Dict[str, Any] = {}
    if lod_result:
        note_parts["detection_result"] = lod_result.get("detection_result")
        note_parts["lod_threshold"] = lod_result.get("lod_threshold")
    if note_parts:
        resource["note"] = [{"text": json.dumps(note_parts)}]
    return resource


def verify_lims_webhook(
    observation: Dict[str, Any],
    webhook_url: str,
    timeout: float = 10.0,
    round_trip_tolerance: float = 0.05,
) -> Dict[str, Any]:
    """Emit a FHIR Observation to a LIMS webhook and verify round-trip (FR-3.14.4).

    POSTs the Observation, then attempts to extract the returned cfDNA value
    from the LIMS response (a single Observation or a transaction Bundle) and
    compares it to the value that was sent. The ``round_trip`` block reports
    absolute/relative error and a ``verified`` flag within tolerance — the core
    of "verify round-trip accuracy at extreme LOD under stressor-induced
    volatility".
    """
    sent_value = observation.get("valueQuantity", {}).get("value")
    try:
        resp = httpx.post(webhook_url, json=observation, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        result: Dict[str, Any] = {
            "ok": resp.is_success,
            "status_code": resp.status_code,
            "body": body,
        }
    except httpx.HTTPError as e:
        return {
            "ok": False,
            "status_code": None,
            "error": str(e),
            "round_trip": None,
        }

    received = _extract_returned_value(body)
    round_trip = None
    if received is not None and sent_value is not None:
        abs_err = abs(received - sent_value)
        rel_err = (abs_err / sent_value) if sent_value else 0.0
        round_trip = {
            "sent_value": sent_value,
            "received_value": received,
            "abs_error": abs_err,
            "rel_error": rel_err,
            "tolerance": round_trip_tolerance,
            "verified": rel_err <= round_trip_tolerance,
        }
    result["round_trip"] = round_trip
    return result


def _extract_returned_value(body: Any) -> Optional[float]:
    """Best-effort extraction of a returned cfDNA value from a LIMS response."""
    if not isinstance(body, dict):
        return None
    if body.get("resourceType") == "Observation":
        return _value_from_observation(body)
    if body.get("resourceType") == "Bundle" and isinstance(body.get("entry"), list):
        for entry in body["entry"]:
            res = entry.get("resource") if isinstance(entry, dict) else None
            if isinstance(res, dict) and res.get("resourceType") == "Observation":
                v = _value_from_observation(res)
                if v is not None:
                    return v
    if isinstance(body.get("resource"), dict):
        return _value_from_observation(body["resource"])
    if isinstance(body.get("observation"), dict):
        return _value_from_observation(body["observation"])
    return None


def _value_from_observation(res: Dict[str, Any]) -> Optional[float]:
    vq = res.get("valueQuantity")
    if isinstance(vq, dict) and vq.get("value") is not None:
        try:
            return float(vq["value"])
        except (TypeError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------
# Orchestration + persistence
# ---------------------------------------------------------------------------

def run_mrd_sandbox(
    stressor: Dict[str, Any],
    baseline: Optional[Dict[str, float]] = None,
    simulation_id: Optional[int] = None,
    cohort_id: Optional[int] = None,
    patient_id: Optional[str] = None,
    shedding_params: Optional[Dict[str, Any]] = None,
    lod_threshold: Optional[float] = None,
    n_samples: int = 20,
    volatility: float = 0.0,
    seed: Optional[Any] = None,
    lims_webhook_url: Optional[str] = None,
    lims_round_trip_tolerance: float = 0.05,
    validate: bool = True,
    include_narrative: bool = False,
) -> Dict[str, Any]:
    """Orchestrate the MRD/LOD sandbox run (FR-3.14.1–FR-3.14.4).

    Steps: stressor injection -> cfDNA shedding (with volatility samples) ->
    LOD evaluation -> optional FHIR Observation emission + LIMS round-trip
    verification -> optional LLM narrative.

    Returns a structured result consumed by :func:`generate_cfdna_sandbox_run`
    and the API layer.
    """
    # FR-3.14.1 (optional real Pulse Engine): when active and no explicit
    # baseline is supplied, use a live Pulse baseline as the physiology the
    # stressor alters. Seed-deterministic synthesis stays the default (C7).
    if baseline is None:
        try:
            from engine.pulse_bridge import real_pulse_available, pulse_baseline

            if real_pulse_available():
                _live = pulse_baseline(patient_id or "mrd")
                if _live:
                    baseline = {
                        **DEFAULT_BASELINE_PHYSIOLOGY,
                        **{k: _live[k] for k in DEFAULT_BASELINE_PHYSIOLOGY if k in _live},
                    }
        except Exception:  # pragma: no cover - only active with real engine
            pass

    phys = dict(baseline) if baseline else dict(DEFAULT_BASELINE_PHYSIOLOGY)
    altered = apply_stressor(phys, stressor)

    shed = cfdna_shedding(
        altered["plasma_volume_ml"],
        altered,
        theta_shed=shedding_params,
        seed=seed,
        n_samples=n_samples,
        volatility=volatility,
    )

    lod = evaluate_lod(shed["samples"], lod_threshold)

    lims_response = None
    if lims_webhook_url:
        obs = build_cfdna_observation(
            shed["mean_copies_per_ml"], patient_id=patient_id, lod_result=lod
        )
        if validate:
            validator = FHIRValidator()
            ok, errors = validator.validate_observation(obs)
            if not ok:
                messages = [getattr(e, "message", str(e)) for e in errors]
                raise ValueError(f"FHIR Observation validation failed: {messages}")
        lims_response = verify_lims_webhook(
            obs, lims_webhook_url, round_trip_tolerance=lims_round_trip_tolerance
        )

    narrative = None
    if include_narrative:
        narrative = generate_mrd_narrative(
            stressor=stressor,
            altered=altered,
            lod=lod,
            shedding=shed,
            patient_id=patient_id,
        )

    return {
        "baseline_physiology": phys,
        "altered_physiology": altered,
        "cfdna_concentration": {
            "mean_copies_per_ml": shed["mean_copies_per_ml"],
            "samples": shed["samples"],
            "stress_index": shed["stress_index"],
            "stress_factor": shed["stress_factor"],
            "total_copies": shed["total_copies"],
        },
        "lod_result": lod,
        "detection_result": lod["detection_result"],
        "shedding_params": shedding_params or {},
        "lims_response": lims_response,
        "narrative": narrative,
        "patient_id": patient_id,
        "seed": seed,
    }


def generate_mrd_narrative(
    stressor: Dict[str, Any],
    altered: Dict[str, float],
    lod: Dict[str, Any],
    shedding: Dict[str, Any],
    patient_id: Optional[str] = None,
) -> Optional[str]:
    """Optionally synthesize an MRD narrative via the LLM gateway (FR-3.14.4 / FR-3.15).

    Best-effort: returns ``None`` if the LLM gateway is unavailable or fails,
    so an MRD run still succeeds without a narrative. The narrative, when
    produced, is persisted by the gateway into ``clinical_text_outputs``.
    """
    try:
        from ai.llm_gateway import generate_text  # lazy import; optional integration
    except Exception:
        return None
    try:
        prompt = (
            "Summarize the following MRD/cfDNA sandbox result as a brief "
            "clinical pathology note.\n"
            f"Stressor: {stressor.get('type')} (severity={stressor.get('severity')})\n"
            f"Altered physiology: plasma_volume_ml={altered.get('plasma_volume_ml')}, "
            f"spo2={altered.get('spo2')}, "
            f"MAP={altered.get('mean_arterial_pressure')}\n"
            f"Mean cfDNA: {shedding['mean_copies_per_ml']} copies/mL\n"
            f"LOD detection: {lod.get('detection_result')} "
            f"(threshold={lod.get('lod_threshold')})\n"
        )
        return generate_text(prompt=prompt, max_tokens=256)
    except Exception:
        return None


def generate_cfdna_sandbox_run(
    db,
    result: Dict[str, Any],
    stressor: Dict[str, Any],
    simulation_id: Optional[int] = None,
    cohort_id: Optional[int] = None,
    lod_threshold: Optional[float] = None,
    seed: Optional[Any] = None,
    scenario_run_id: Optional[int] = None,
) -> Any:
    """Persist a ``CfdnaSandboxRun`` row (FR-3.14, SRS §6.1 table).

    Returns the persisted ORM instance (with ``id`` populated after flush).
    """
    import uuid

    from models import CfdnaSandboxRun

    altered = result["altered_physiology"]
    baseline = result["baseline_physiology"]
    lod = result["lod_result"]

    row = CfdnaSandboxRun(
        run_uid=str(uuid.uuid4()),
        simulation_id=simulation_id,
        cohort_id=cohort_id,
        stressor=stressor,
        plasma_volume={
            "baseline_ml": baseline.get("plasma_volume_ml"),
            "altered_ml": altered.get("plasma_volume_ml"),
        },
        cfdna_concentration=result["cfdna_concentration"],
        shedding_params=result["shedding_params"],
        lod_threshold={
            "value": lod_threshold,
            "configured": lod.get("configured", False),
            "detection_result": lod.get("detection_result"),
            "detection_rate": lod.get("detection_rate"),
            "mean_concentration": lod.get("mean_concentration"),
        },
        detection_result=result["detection_result"],
        lims_response=result["lims_response"],
        scenario_run_id=scenario_run_id,
    )
    db.add(row)
    db.flush()
    return row
