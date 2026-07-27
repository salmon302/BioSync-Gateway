# SPDX-License-Identifier: MIT
"""
Scenario Specification + Orchestration API - SRS FR-3.16.1 / FR-3.16.2 / FR-3.16.3 / FR-3.16.4.

Mounted at /api/scenarios:
  POST /                      create a scenario specification (FR-3.16.1)
  GET  /                      list scenarios
  GET  /runs                  list recent runs
  GET  /runs/{run_uid}        inspect a run
  GET  /{scenario_uid}        inspect a scenario specification
  POST /{scenario_uid}/run    execute the scenario -> ScenarioRun (FR-3.16.2/3.16.3)

Execution is synchronous (per approved plan): run completes in-request and the
full run record is returned. With the default mock LLM provider this is
instant; a real provider would block the request, so background execution can
be adopted later without changing the contract.

NOTE: the static `/runs` routes are declared BEFORE the `/{scenario_uid}`
param routes so that `GET /runs` is not shadowed by `GET /{scenario_uid}`
(capturing scenario_uid="runs").
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import get_db
from models import ScenarioRun, SimulationScenario
from simulation.scenarios import ALL_MODULES, route_downstream_outputs, run_scenario

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MODULES = sorted(ALL_MODULES)


# --------------------------------------------------------------------------
# Request / response models
# --------------------------------------------------------------------------
class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    feature_modules: List[str] = Field(..., min_items=1)
    seed: Dict[str, Any] = Field(default_factory=dict)
    config: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------
# DTO helpers
# --------------------------------------------------------------------------
def _scenario_dto(row: SimulationScenario) -> Dict[str, Any]:
    return {
        "scenario_uid": row.scenario_uid,
        "name": row.name,
        "description": row.description,
        "feature_modules": row.feature_modules,
        "seed": row.seed,
        "config": row.config,
        "is_finalized": row.is_finalized,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by": row.created_by,
    }


def _run_dto(row: ScenarioRun) -> Dict[str, Any]:
    return {
        "run_uid": row.run_uid,
        "scenario_id": row.scenario_id,
        "seed": row.seed,
        "status": row.status,
        "aggregated_outputs": row.aggregated_outputs,
        "output_hashes": row.output_hashes,
        "downstream_results": row.downstream_results,
        "error": row.error,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# --------------------------------------------------------------------------
# Routes (static /runs declared before /{scenario_uid})
# --------------------------------------------------------------------------
@router.post("/", status_code=201, response_model=Dict[str, Any])
def create_scenario(
    body: ScenarioCreate,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("scenario_write")),
):
    """Create a named scenario specification (FR-3.16.1)."""
    invalid = [m for m in body.feature_modules if m not in ALLOWED_MODULES]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown feature_modules: {invalid}; allowed={ALLOWED_MODULES}",
        )
    from uuid import uuid4

    row = SimulationScenario(
        scenario_uid=str(uuid4()),
        name=body.name,
        description=body.description,
        feature_modules=body.feature_modules,
        seed=body.seed if body.seed else {"default": 1},
        config=body.config or {},
        is_finalized=False,
    )
    db.add(row)
    db.flush()
    db.commit()
    db.refresh(row)
    return _scenario_dto(row)


@router.get("/", response_model=Dict[str, Any])
def list_scenarios(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("scenario_read")),
):
    """List recent scenario specifications (FR-3.16.1)."""
    rows = (
        db.query(SimulationScenario)
        .order_by(SimulationScenario.id.desc())
        .limit(limit)
        .all()
    )
    return {"count": len(rows), "scenarios": [_scenario_dto(r) for r in rows]}


@router.get("/runs", response_model=Dict[str, Any])
def list_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("scenario_read")),
):
    """List recent scenario runs (FR-3.16.2/3)."""
    rows = db.query(ScenarioRun).order_by(ScenarioRun.id.desc()).limit(limit).all()
    return {"count": len(rows), "runs": [_run_dto(r) for r in rows]}


@router.get("/runs/{run_uid}", response_model=Dict[str, Any])
def get_run(
    run_uid: str,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("scenario_read")),
):
    """Inspect a single scenario run (FR-3.16.2/3/4)."""
    row = db.query(ScenarioRun).filter_by(run_uid=run_uid).first()
    if not row:
        raise HTTPException(status_code=404, detail="scenario run not found")
    return _run_dto(row)


@router.get("/{scenario_uid}", response_model=Dict[str, Any])
def get_scenario(
    scenario_uid: str,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("scenario_read")),
):
    """Inspect a single scenario specification (FR-3.16.1)."""
    row = (
        db.query(SimulationScenario).filter_by(scenario_uid=scenario_uid).first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="scenario not found")
    return _scenario_dto(row)


@router.post("/{scenario_uid}/run", response_model=Dict[str, Any])
def run_scenario_endpoint(
    scenario_uid: str,
    db: Session = Depends(get_db),
    _: Any = Depends(require_scope("scenario_write")),
):
    """Execute a scenario: orchestrate modules, then route downstream (FR-3.16.2/3)."""
    scenario = (
        db.query(SimulationScenario).filter_by(scenario_uid=scenario_uid).first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario not found")

    from uuid import uuid4

    run_row = ScenarioRun(
        run_uid=str(uuid4()),
        scenario_id=scenario.id,
        seed=scenario.seed,
        status="running",
    )
    db.add(run_row)
    db.flush()  # populate run_row.id for module linkage

    try:
        outputs = run_scenario(db, scenario, run_row)
        # FR-3.16.3 downstream validation harness.
        endpoints = (scenario.config or {}).get("downstream_endpoints", [])
        downstream = route_downstream_outputs(outputs, endpoints)
        run_row.downstream_results = downstream
        run_row.status = "completed"
        run_row.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run_row)
        return _run_dto(run_row)
    except Exception as exc:
        logger.error("Scenario run %s failed: %s", scenario_uid, exc)
        db.rollback()
        # Re-query the (rolled-back) run row and mark it failed for auditability.
        failed = db.query(ScenarioRun).filter_by(id=run_row.id).first()
        if failed is not None:
            failed.status = "failed"
            failed.error = str(exc)
            failed.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(status_code=500, detail=f"scenario run failed: {exc}")
