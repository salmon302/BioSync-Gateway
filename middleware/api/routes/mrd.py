# SPDX-License-Identifier: MIT
"""
MRD / cfDNA Sandbox Routes — SRS FR-3.14
Mounted at /api/simulation, alongside the PK/PD, chemistry, and digital-twin routes.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import get_db
from models import CfdnaSandboxRun
from simulation.mrd_sandbox import run_mrd_sandbox, generate_cfdna_sandbox_run

router = APIRouter()


@router.post("/mrd/run")
async def create_mrd_run(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_write")),
):
    """Run an MRD/cfDNA sandbox (FR-3.14.1–FR-3.14.4).

    Body (dict):
      stressor: {type, severity, overrides?} (required; FR-3.14.1)
      baseline: dict (optional physiology baseline; else default healthy adult)
      simulation_id: int (optional linkage to an active Pulse sim)
      cohort_id: int (optional linkage to a synthetic cohort)
      patient_id: str (optional synthetic subject for FHIR/LIMS)
      shedding_params: dict (optional theta_shed — baseline_copies / stress_gain)
      lod_threshold: float (optional copies/mL; FR-3.14.3)
      n_samples: int (default 20; volatility sample count)
      volatility: float (default 0.0; stressor-induced concentration volatility)
      seed: int | dict (optional, for determinism; FR-3.16.4)
      lims_webhook_url: str (optional; FR-3.14.4 LIMS emission + round-trip)
      lims_round_trip_tolerance: float (default 0.05; relative error tolerance)
      include_narrative: bool (default False; optional FR-3.15 LLM note)
      validate: bool (default True; FHIR R4 validation before LIMS emission)
    """
    stressor = body.get("stressor")
    if not isinstance(stressor, dict) or not stressor.get("type"):
        raise HTTPException(status_code=400, detail="stressor.type is required")

    try:
        result = run_mrd_sandbox(
            stressor=stressor,
            baseline=body.get("baseline"),
            simulation_id=body.get("simulation_id"),
            cohort_id=body.get("cohort_id"),
            patient_id=body.get("patient_id"),
            shedding_params=body.get("shedding_params"),
            lod_threshold=body.get("lod_threshold"),
            n_samples=int(body.get("n_samples", 20)),
            volatility=float(body.get("volatility", 0.0)),
            seed=body.get("seed"),
            lims_webhook_url=body.get("lims_webhook_url"),
            lims_round_trip_tolerance=float(body.get("lims_round_trip_tolerance", 0.05)),
            validate=body.get("validate", True),
            include_narrative=body.get("include_narrative", False),
        )
    except ValueError as e:
        # FHIR Observation validation failure -> OperationOutcome-style 422 (FR-3.7.4)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"MRD sandbox run failed: {e}")

    row = generate_cfdna_sandbox_run(
        db,
        result=result,
        stressor=stressor,
        simulation_id=body.get("simulation_id"),
        cohort_id=body.get("cohort_id"),
        lod_threshold=body.get("lod_threshold"),
        seed=body.get("seed"),
        scenario_run_id=body.get("scenario_run_id"),
    )
    db.commit()
    db.refresh(row)
    return {
        "status": "created",
        "run_id": row.id,
        "run_uid": row.run_uid,
        "simulation_id": row.simulation_id,
        "cohort_id": row.cohort_id,
        "patient_id": body.get("patient_id"),
        "scenario_run_id": row.scenario_run_id,
        "detection_result": row.detection_result,
        "baseline_physiology": result["baseline_physiology"],
        "altered_physiology": result["altered_physiology"],
        "cfdna_concentration": result["cfdna_concentration"],
        "lod_result": result["lod_result"],
        "lims_response": row.lims_response,
        "narrative": result.get("narrative"),
        "seed": row.seed,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/mrd/run/{run_id}")
async def get_mrd_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """Retrieve a persisted MRD sandbox run (FR-3.14)."""
    row = db.query(CfdnaSandboxRun).filter(CfdnaSandboxRun.id == run_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="MRD sandbox run not found")
    return {
        "run_id": row.id,
        "run_uid": row.run_uid,
        "simulation_id": row.simulation_id,
        "cohort_id": row.cohort_id,
        "scenario_run_id": row.scenario_run_id,
        "stressor": row.stressor,
        "plasma_volume": row.plasma_volume,
        "cfdna_concentration": row.cfdna_concentration,
        "shedding_params": row.shedding_params,
        "lod_threshold": row.lod_threshold,
        "detection_result": row.detection_result,
        "lims_response": row.lims_response,
        "seed": row.seed,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/mrd/runs")
async def list_mrd_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """List recent MRD sandbox runs (FR-3.14)."""
    rows = (
        db.query(CfdnaSandboxRun)
        .order_by(CfdnaSandboxRun.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "runs": [
            {
                "run_id": r.id,
                "run_uid": r.run_uid,
                "simulation_id": r.simulation_id,
                "cohort_id": r.cohort_id,
                "detection_result": r.detection_result,
                "lod_configured": bool(r.lod_threshold and r.lod_threshold.get("configured")),
                "scenario_run_id": r.scenario_run_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
