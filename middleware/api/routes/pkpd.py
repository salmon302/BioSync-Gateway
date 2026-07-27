# SPDX-License-Identifier: MIT
"""
PK/PD Lab Loop Routes — SRS FR-3.11
Mounted at /api/simulation (singular) alongside the Pulse simulation routes
(/api/simulations).
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import get_db
from models import PkpdWorklist
from simulation.pkpd import (
    PkpdSubstance,
    generate_pkpd_worklist,
)

router = APIRouter()


def _build_substance(spec: Dict[str, Any]) -> PkpdSubstance:
    """Construct a PkpdSubstance from a request dict, mapping validation errors."""
    try:
        return PkpdSubstance(
            name=spec["name"],
            volume_of_distribution=float(spec["volume_of_distribution"]),
            clearance=float(spec["clearance"]),
            elimination_half_life=float(spec["elimination_half_life"]),
            dose=float(spec["dose"]),
            dose_unit=spec.get("dose_unit", "mg"),
            molar_mass=(
                float(spec["molar_mass"]) if spec.get("molar_mass") is not None else None
            ),
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing substance field: {e}")
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid substance value: {e}")


@router.post("/pkpd/worklist")
async def create_pkpd_worklist(
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_write")),
):
    """Generate a PK/PD pipetting worklist and persist it (FR-3.11.1–FR-3.11.4).

    Body (dict):
      substance: {name, volume_of_distribution, clearance, elimination_half_life,
                  dose, dose_unit?, molar_mass?}
      initial_concentration: float   # stock solution concentration
      initial_unit: str              # e.g. mg/L, µM (must be convertible to the
                                      #   substance's canonical unit)
      plate_format: "96-well" | "384-well"  (default "96-well")
      plate_id: int (optional, attach to an existing plate)
      horizon_h: float (default 24)
      interval_h: float (default 1)
      target_total_volume_ul: float (default 100)
      num_wells: int (optional; default = plate well count)
      sample_times_h: list[float] (optional explicit sample times)
      scenario_run_id: int (optional, links to a scenario run)
      seed: dict (optional provenance)
    """
    substance_spec = body.get("substance")
    if not substance_spec:
        raise HTTPException(status_code=400, detail="substance is required")
    c1 = body.get("initial_concentration")
    u1 = body.get("initial_unit")
    if c1 is None or not u1:
        raise HTTPException(
            status_code=400,
            detail="initial_concentration and initial_unit are required",
        )

    substance = _build_substance(substance_spec)
    plate_format = body.get("plate_format", "96-well")
    if plate_format not in ("96-well", "384-well"):
        raise HTTPException(
            status_code=400, detail="plate_format must be '96-well' or '384-well'"
        )

    try:
        row = generate_pkpd_worklist(
            db,
            substance,
            float(c1),
            u1,
            plate_format=plate_format,
            plate_id=body.get("plate_id"),
            horizon_h=float(body.get("horizon_h", 24.0)),
            interval_h=float(body.get("interval_h", 1.0)),
            target_total_volume_ul=float(body.get("target_total_volume_ul", 100.0)),
            sample_times_h=body.get("sample_times_h"),
            num_wells=body.get("num_wells"),
            scenario_run_id=body.get("scenario_run_id"),
            seed=body.get("seed"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=500, detail=f"PK/PD worklist generation failed: {e}"
        )

    db.commit()
    db.refresh(row)
    return {
        "status": "created",
        "worklist_id": row.id,
        "worklist_uid": row.worklist_uid,
        "origin": row.origin,
        "substance_name": row.substance_name,
        "plate_id": row.plate_id,
        "scenario_run_id": row.scenario_run_id,
        "well_count": (row.steps or {}).get("well_count"),
        "warnings": (row.steps or {}).get("warnings", []),
        "target_matrix": row.target_matrix,
        "plasma_concentration_series": row.plasma_concentration_series,
        "steps": (row.steps or {}).get("steps"),
        "is_finalized": row.is_finalized,
    }


@router.get("/pkpd/worklist/{worklist_id}")
async def get_pkpd_worklist(
    worklist_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """Retrieve a persisted PK/PD worklist (FR-3.11.4)."""
    row = db.query(PkpdWorklist).filter(PkpdWorklist.id == worklist_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="PK/PD worklist not found")
    return {
        "worklist_id": row.id,
        "worklist_uid": row.worklist_uid,
        "substance_name": row.substance_name,
        "plate_id": row.plate_id,
        "origin": row.origin,
        "is_finalized": row.is_finalized,
        "scenario_run_id": row.scenario_run_id,
        "pk_parameters": row.pk_parameters,
        "plasma_concentration_series": row.plasma_concentration_series,
        "target_matrix": row.target_matrix,
        "steps": row.steps,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/pkpd/worklists")
async def list_pkpd_worklists(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("simulation_read")),
):
    """List recent PK/PD worklists (FR-3.11.4)."""
    rows = (
        db.query(PkpdWorklist).order_by(PkpdWorklist.id.desc()).limit(limit).all()
    )
    return {
        "count": len(rows),
        "worklists": [
            {
                "worklist_id": r.id,
                "worklist_uid": r.worklist_uid,
                "substance_name": r.substance_name,
                "origin": r.origin,
                "is_finalized": r.is_finalized,
                "plate_id": r.plate_id,
                "scenario_run_id": r.scenario_run_id,
                "well_count": (r.steps or {}).get("well_count"),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
