# SPDX-License-Identifier: MIT
"""
Digital Twin Cohort Routes — SRS FR-3.13
Mounted at /api/simulation (singular), alongside the PK/PD and chemistry routes.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import get_db
from models import SyntheticCohort
from simulation.digital_twin import generate_synthetic_cohort, export_cohort_bundle

router = APIRouter()


@router.post("/cohort")
async def create_cohort(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_write")),
):
    """Generate a synthetic digital-twin cohort (FR-3.13.1–FR-3.13.5).

    Body (dict):
      name: str (optional)
      size: int (number of twins)
      demographic_distribution: dict (optional age/sex ranges)
      clinvar_variant_set: list[dict] (optional variant definitions)
      physiological_baseline_ranges: dict (optional per-vital ranges)
      seed: int | dict (optional, for deterministic generation; FR-3.13.4/3.16.4)
      duration_min: float (default 1.0)  — trend horizon per member
      cadence_sec: float (default 10.0) — sampling interval
      scenario_run_id: int (optional)
      validate: bool (default True; FHIR R4 validation before persistence)
    """
    if not body.get("size"):
        raise HTTPException(status_code=400, detail="size is required")
    try:
        row = generate_synthetic_cohort(
            db,
            spec=body,
            scenario_run_id=body.get("scenario_run_id"),
            duration_min=float(body.get("duration_min", 1.0)),
            cadence_sec=float(body.get("cadence_sec", 10.0)),
            validate=body.get("validate", True),
            created_by=getattr(current_user, "username", None),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Cohort generation failed: {e}")

    db.commit()
    db.refresh(row)
    bundle = export_cohort_bundle(
        row,
        duration_min=float(body.get("duration_min", 1.0)),
        cadence_sec=float(body.get("cadence_sec", 10.0)),
        validate=body.get("validate", True),
    )
    return {
        "status": "created",
        "cohort_id": row.id,
        "cohort_uid": row.cohort_uid,
        "name": row.name,
        "size": row.size,
        "is_synthetic": row.is_synthetic,
        "scenario_run_id": row.scenario_run_id,
        "members": row.members,
        "export_bundle": bundle,
        "seed": row.seed,
    }


@router.get("/cohort/{cohort_id}")
async def get_cohort(
    cohort_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """Retrieve a persisted cohort and its exportable Bundle (FR-3.13.4)."""
    row = db.query(SyntheticCohort).filter(SyntheticCohort.id == cohort_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cohort not found")
    bundle = export_cohort_bundle(row)
    return {
        "cohort_id": row.id,
        "cohort_uid": row.cohort_uid,
        "name": row.name,
        "size": row.size,
        "is_synthetic": row.is_synthetic,
        "scenario_run_id": row.scenario_run_id,
        "demographic_distribution": row.demographic_distribution,
        "clinvar_variant_set": row.clinvar_variant_set,
        "members": row.members,
        "seed": row.seed,
        "export_bundle": bundle,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/cohorts")
async def list_cohorts(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """List recent synthetic cohorts (FR-3.13)."""
    rows = db.query(SyntheticCohort).order_by(SyntheticCohort.id.desc()).limit(limit).all()
    return {
        "count": len(rows),
        "cohorts": [
            {
                "cohort_id": r.id,
                "cohort_uid": r.cohort_uid,
                "name": r.name,
                "size": r.size,
                "is_synthetic": r.is_synthetic,
                "scenario_run_id": r.scenario_run_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
