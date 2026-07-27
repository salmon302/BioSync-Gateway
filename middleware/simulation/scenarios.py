# SPDX-License-Identifier: MIT
"""
Integrated Simulation Scenario Orchestrator - SRS FR-3.16.2 / FR-3.16.4 / FR-3.16.3.

Sequences any subset of the five advanced analytics modules
(FR-3.11 PK/PD, FR-3.12 chemistry, FR-3.13 digital twin, FR-3.14 MRD,
FR-3.15 LLM narrative) into a single reproducible scenario run.

Design:
  * Shared simulated patient/state context. A stable ``patient_id`` is derived
    from the scenario UID and the scenario ``seed`` is propagated to every
    module, so re-running with the same seed reproduces identical deterministic
    outputs (FR-3.16.4). The LLM module is recorded by provider/model for
    provenance rather than hashed for equality (non-deterministic by design).
  * Outputs from each module are collected into a single ``ScenarioRun`` record
    (``aggregated_outputs``) satisfying FR-3.16.2.
  * ``route_downstream_outputs`` implements the downstream validation harness
    (FR-3.16.3): aggregated multi-modal outputs are POSTed to configurable
    LIMS/EHR webhooks and the responses captured into ``downstream_results``.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models import ScenarioRun, SimulationScenario

from simulation.pkpd import PkpdSubstance, generate_pkpd_worklist
from simulation.chemistry import generate_chemistry_profile
from simulation.digital_twin import generate_synthetic_cohort, export_cohort_bundle
from simulation.mrd_sandbox import run_mrd_sandbox, generate_cfdna_sandbox_run

from ai.llm_gateway import generate_text, persist_run, get_provider_config

logger = logging.getLogger(__name__)

# Canonical execution order for deterministic replay (FR-3.16.4).
MODULE_ORDER: List[str] = ["pk_pd", "chemistry", "digital_twin", "mrd", "llm"]
ALL_MODULES = set(MODULE_ORDER)

# Sensible defaults so the UI can stay within NFR-U4 (<=5 interactions) while
# still exercising every module when no per-module config is supplied.
DEFAULT_PKPD_SUBSTANCE: Dict[str, Any] = dict(
    name="Scenario-Agent",
    volume_of_distribution=50.0,
    clearance=5.0,
    elimination_half_life=6.93,
    dose=100.0,
    dose_unit="mg",
    molar_mass=None,
)
DEFAULT_COHORT_SIZE = 5
DEFAULT_STRESSOR: Dict[str, Any] = {"type": "respiratory_distress", "severity": 1.0}


def _hash(obj: Any) -> str:
    """Stable, order-independent sha256 of a JSON-serializable structure."""
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shared_patient_id(scenario_row: SimulationScenario) -> str:
    """Stable patient/state identity shared across modules within a scenario."""
    return f"SCN-{scenario_row.scenario_uid}"


def _build_scenario_prompt(patient_id: str, outputs: Dict[str, Any]) -> str:
    """Summarize the shared scenario context for the LLM narrative module."""
    lines = [f"Integrated simulation scenario summary for patient {patient_id}."]
    if "pk_pd" in outputs:
        lines.append(
            f"- PK/PD: substance {outputs['pk_pd']['substance_name']}, "
            f"{outputs['pk_pd'].get('well_count')} dilution wells."
        )
    if "chemistry" in outputs:
        lines.append(f"- Clinical chemistry: profile {outputs['chemistry']['profile_uid']} generated.")
    if "digital_twin" in outputs:
        lines.append(f"- Digital twin: synthetic cohort of {outputs['digital_twin']['size']} members.")
    if "mrd" in outputs:
        lines.append(f"- MRD/liquid biopsy: detection result = {outputs['mrd']['detection_result']}.")
    lines.append(
        "Compose a concise, simulated clinical summary suitable for downstream "
        "EHR text-ingestion testing (do not invent clinical facts)."
    )
    return "\n".join(lines)


def run_scenario(
    db,
    scenario_row: SimulationScenario,
    run_row: ScenarioRun,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sequence the selected modules for one scenario run (FR-3.16.2 / FR-3.16.4).

    Mutates ``run_row`` in place, setting ``seed``, ``aggregated_outputs`` and
    ``output_hashes``. The caller is responsible for committing the session.

    Returns the collected ``aggregated_outputs`` dict (also stored on run_row).
    """
    config = config or scenario_row.config or {}
    seed = scenario_row.seed if scenario_row.seed is not None else {"default": 1}
    patient_id = _shared_patient_id(scenario_row)
    selected = [m for m in MODULE_ORDER if m in (scenario_row.feature_modules or [])]

    outputs: Dict[str, Any] = {}
    hashes: Dict[str, Any] = {}

    # 1) FR-3.11 PK/PD lab loop ------------------------------------------------
    if "pk_pd" in selected:
        substance_spec = {**DEFAULT_PKPD_SUBSTANCE, **(config.get("pk_pd") or {})}
        substance = PkpdSubstance(**substance_spec)
        c0 = substance.initial_concentration()
        c0_unit = substance.canonical_unit()
        row = generate_pkpd_worklist(
            db,
            substance,
            c0,
            c0_unit,
            plate_format="96-well",
            horizon_h=24.0,
            interval_h=1.0,
            target_total_volume_ul=100.0,
            scenario_run_id=run_row.id,
            seed=seed,
        )
        db.flush()
        outputs["pk_pd"] = {
            "worklist_uid": row.worklist_uid,
            "substance_name": row.substance_name,
            "target_matrix": row.target_matrix,
            "plasma_concentration_series": row.plasma_concentration_series,
            "well_count": (row.steps or {}).get("well_count"),
        }
        hashes["pk_pd"] = _hash([row.target_matrix, row.plasma_concentration_series])

    # 2) FR-3.12 Clinical chemistry --------------------------------------------
    if "chemistry" in selected:
        chem_cfg = config.get("chemistry") or {}
        row = generate_chemistry_profile(
            db,
            seed=seed,
            patient_id=patient_id,
            clinvar_data=chem_cfg.get("clinvar_data"),
            scenario_run_id=run_row.id,
            validate=True,
        )
        db.flush()
        outputs["chemistry"] = {
            "profile_uid": row.profile_uid,
            "patient_id": row.patient_id,
            "chemistry_vectors": row.chemistry_vectors,
            "fhir_bundle": row.fhir_bundle,
            "lims_response": row.lims_response,
        }
        hashes["chemistry"] = _hash([row.chemistry_vectors, row.fhir_bundle])

    # 3) FR-3.13 Digital twin cohort ------------------------------------------
    dt_row = None
    if "digital_twin" in selected:
        dt_cfg = config.get("digital_twin") or {}
        spec: Dict[str, Any] = {
            "name": dt_cfg.get("name", "Scenario Cohort"),
            "seed": seed,
            "size": dt_cfg.get("size", DEFAULT_COHORT_SIZE),
            "demographic_distribution": dt_cfg.get("demographic_distribution"),
            "clinvar_variant_set": dt_cfg.get("clinvar_variant_set"),
            "physiological_baseline_ranges": dt_cfg.get("physiological_baseline_ranges"),
        }
        dt_row = generate_synthetic_cohort(
            db,
            spec,
            scenario_run_id=run_row.id,
            duration_min=dt_cfg.get("duration_min", 1.0),
            cadence_sec=dt_cfg.get("cadence_sec", 10.0),
            validate=True,
        )
        db.flush()
        bundle = export_cohort_bundle(dt_row)
        outputs["digital_twin"] = {
            "cohort_uid": dt_row.cohort_uid,
            "size": dt_row.size,
            "members": dt_row.members,
            "bundle": bundle,
        }
        hashes["digital_twin"] = _hash([dt_row.members, bundle])

    # 4) FR-3.14 MRD / liquid biopsy sandbox ----------------------------------
    if "mrd" in selected:
        mrd_cfg = config.get("mrd") or {}
        stressor = mrd_cfg.get("stressor", DEFAULT_STRESSOR)
        cohort_id = dt_row.id if dt_row is not None else None
        result = run_mrd_sandbox(
            stressor,
            baseline=mrd_cfg.get("baseline"),
            cohort_id=cohort_id,
            patient_id=patient_id,
            shedding_params=mrd_cfg.get("shedding_params"),
            lod_threshold=mrd_cfg.get("lod_threshold"),
            n_samples=mrd_cfg.get("n_samples", 20),
            volatility=mrd_cfg.get("volatility", 0.0),
            seed=seed,
            validate=True,
            include_narrative=False,
        )
        row = generate_cfdna_sandbox_run(
            db,
            result=result,
            stressor=stressor,
            cohort_id=cohort_id,
            lod_threshold=mrd_cfg.get("lod_threshold"),
            seed=seed,
            scenario_run_id=run_row.id,
        )
        db.flush()
        outputs["mrd"] = {
            "run_uid": row.run_uid,
            "cfdna_concentration": result["cfdna_concentration"],
            "detection_result": result["detection_result"],
            "lims_response": result["lims_response"],
        }
        hashes["mrd"] = _hash([result["cfdna_concentration"], result["detection_result"]])

    # 5) FR-3.15 LLM narrative (recorded, not hashed for equality) -----------
    if "llm" in selected:
        llm_cfg = config.get("llm") or {}
        prompt = _build_scenario_prompt(patient_id, outputs)
        provider_cfg = get_provider_config()
        max_tokens = llm_cfg.get("max_tokens", 512)
        text = generate_text(prompt, max_tokens=max_tokens)
        out = persist_run(
            db,
            prompt,
            text,
            text_type="scenario_narrative",
            scenario_run_id=run_row.id,
            max_tokens=max_tokens,
        )
        db.flush()
        outputs["llm"] = {
            "output_uid": out.output_uid,
            "text_type": out.text_type,
            "content": text,
            "provenance": out.provenance,
        }
        hashes["llm"] = {
            "provider": provider_cfg.get("provider"),
            "model": provider_cfg.get("model"),
            "prompt_hash": _hash(prompt),
        }

    # Persist aggregates onto the run record (FR-3.16.2 / FR-3.16.4).
    run_row.seed = seed
    run_row.aggregated_outputs = outputs
    run_row.output_hashes = hashes
    return outputs


def route_downstream_outputs(
    aggregated_outputs: Dict[str, Any],
    endpoints: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Downstream validation harness (FR-3.16.3).

    Routes aggregated multi-modal outputs to configurable LIMS/EHR webhooks and
    captures the responses. LIMS endpoints receive the FHIR Bundle (chemistry
    preferred, digital-twin fallback); EHR endpoints receive the LLM narrative
    text. Failures are captured, never raised, so a scenario run still records
    what the downstream system returned.
    """
    import httpx

    endpoints = endpoints or []
    results: List[Dict[str, Any]] = []
    for i, ep in enumerate(endpoints):
        etype = str((ep.get("type") or "LIMS")).upper()
        url = ep.get("url")
        if not url:
            results.append(
                {"index": i, "type": etype, "url": None, "ok": False,
                 "error": "missing url", "captured_at": _now_iso()}
            )
            continue
        payload = _build_downstream_payload(etype, aggregated_outputs, ep)
        try:
            with httpx.Client(timeout=float(ep.get("timeout", 10.0))) as client:
                resp = client.post(url, json=payload)
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text[:2000]
                results.append(
                    {
                        "index": i,
                        "type": etype,
                        "url": url,
                        "status_code": resp.status_code,
                        "ok": resp.is_success,
                        "response": body,
                        "captured_at": _now_iso(),
                    }
                )
        except Exception as exc:  # network/transport failure is captured, not fatal
            logger.warning("Downstream %s endpoint %s failed: %s", etype, url, exc)
            results.append(
                {"index": i, "type": etype, "url": url, "ok": False,
                 "error": str(exc), "captured_at": _now_iso()}
            )
    return results


def _build_downstream_payload(
    etype: str, aggregated_outputs: Dict[str, Any], ep: Dict[str, Any]
) -> Dict[str, Any]:
    """Shape the payload sent to a downstream endpoint by type."""
    if etype == "EHR":
        llm = aggregated_outputs.get("llm") or {}
        return {
            "text": llm.get("content"),
            "expected_signals": ep.get("expected_signals", []),
        }
    # LIMS (default): FHIR bundle (chemistry preferred, else digital twin).
    bundle = (aggregated_outputs.get("chemistry") or {}).get("fhir_bundle")
    if bundle is None:
        bundle = (aggregated_outputs.get("digital_twin") or {}).get("bundle")
    if bundle is None:
        bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
    return {"bundle": bundle, "source": "biosync-scenario"}
