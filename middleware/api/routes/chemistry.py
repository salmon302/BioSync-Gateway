# SPDX-License-Identifier: MIT
"""
Clinical Chemistry Generation Routes — SRS FR-3.12
Mounted at /api/simulation (singular), alongside the PK/PD routes.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import get_db
from models import ChemistryProfile
from simulation.chemistry import generate_chemistry_profile

router = APIRouter()


@router.post("/chemistry/profile")
async def create_chemistry_profile(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_write")),
):
    """Generate a clinical chemistry profile + multi-modal Bundle (FR-3.12).

    Body (dict):
      seed: int | dict (optional, for deterministic generation; FR-3.12.4)
      simulation_id: int (optional, links to a Pulse simulation)
      patient_id: str (optional, synthetic subject reference)
      clinvar_data: dict (optional, genomics data merged into the Bundle)
      scenario_run_id: int (optional)
      lims_webhook_url: str (optional; POSTs the Bundle to LIMS, FR-3.12.3)
      validate: bool (default True; FHIR R4 validation before persistence)
    """
    try:
        row = generate_chemistry_profile(
            db,
            seed=body.get("seed"),
            simulation_id=body.get("simulation_id"),
            patient_id=body.get("patient_id"),
            clinvar_data=body.get("clinvar_data"),
            scenario_run_id=body.get("scenario_run_id"),
            lims_webhook_url=body.get("lims_webhook_url"),
            validate=body.get("validate", True),
        )
    except ValueError as e:
        # FHIR Bundle validation failure -> OperationOutcome-style 422 (FR-3.7.4)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"Chemistry profile generation failed: {e}"
        )

    db.commit()
    db.refresh(row)
    return {
        "status": "created",
        "profile_id": row.id,
        "profile_uid": row.profile_uid,
        "simulation_id": row.simulation_id,
        "patient_id": row.patient_id,
        "scenario_run_id": row.scenario_run_id,
        "chemistry_vectors": row.chemistry_vectors,
        "clinvar_data": row.clinvar_data,
        "fhir_bundle": row.fhir_bundle,
        "lims_response": row.lims_response,
        "seed": row.seed,
    }


@router.get("/chemistry/profile/{profile_id}")
async def get_chemistry_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """Retrieve a persisted chemistry profile (FR-3.12)."""
    row = db.query(ChemistryProfile).filter(ChemistryProfile.id == profile_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Chemistry profile not found")
    return {
        "profile_id": row.id,
        "profile_uid": row.profile_uid,
        "simulation_id": row.simulation_id,
        "patient_id": row.patient_id,
        "scenario_run_id": row.scenario_run_id,
        "chemistry_vectors": row.chemistry_vectors,
        "clinvar_data": row.clinvar_data,
        "fhir_bundle": row.fhir_bundle,
        "lims_response": row.lims_response,
        "seed": row.seed,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/chemistry/profiles")
async def list_chemistry_profiles(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """List recent chemistry profiles (FR-3.12)."""
    rows = (
        db.query(ChemistryProfile).order_by(ChemistryProfile.id.desc()).limit(limit).all()
    )
    return {
        "count": len(rows),
        "profiles": [
            {
                "profile_id": r.id,
                "profile_uid": r.profile_uid,
                "simulation_id": r.simulation_id,
                "patient_id": r.patient_id,
                "scenario_run_id": r.scenario_run_id,
                "has_clinvar": bool(r.clinvar_data),
                "has_lims_response": bool(r.lims_response),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
