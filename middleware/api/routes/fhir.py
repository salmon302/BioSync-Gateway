"""
FHIR Routes
Implements SRS §3.7 - FHIR Interoperability
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, List, Optional, Tuple
from fastapi.responses import JSONResponse
import logging
from uuid import uuid4

from api.auth import get_current_user, require_scope
from fhir_validator import validate_resource, to_operation_outcome, FHIRValidator
from database import get_db
from models import Observation, DeviceMetric

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resource persisters — single source of truth for stored FHIR resource types
# ---------------------------------------------------------------------------
# Both the standalone POST endpoints and the Bundle handler (G9 / FR-3.7.5)
# persist through these helpers. This guarantees (a) identical column mapping
# across code paths and (b) that EVERY supported resource type is durably
# stored inside a transaction/batch Bundle -- not only Observation.
#
# Each persister constructs, adds, and flushes the ORM row (no commit) and
# returns (orm_object, canonical_id) so the caller owns the transaction
# boundary (a single commit wraps an entire Bundle).
def _persist_observation(resource: Dict[str, Any], db: Session):
    """Persist a FHIR Observation to the append-only observations table (FR-3.7.3)."""
    code = resource.get("code", {}) or {}
    coding = code.get("coding") or [{}]
    obs_code = coding[0].get("code") or code.get("text") or "unknown"
    vq = resource.get("valueQuantity", {}) or {}
    db_obs = Observation(
        observation_uid=str(uuid4()),
        observation_code=obs_code,
        value_quantity=vq,
        unit=vq.get("unit") or vq.get("code"),
        raw_data=resource.get("raw_data"),
        filtered_data=resource.get("filtered_data"),
        fhir_resource=resource,
    )
    db.add(db_obs)
    db.flush()
    return db_obs, db_obs.observation_uid


def _persist_device_metric(resource: Dict[str, Any], db: Session):
    """Persist a FHIR DeviceMetric to the device_metrics table (FR-3.7.2)."""
    code = resource.get("code", {}) or {}
    coding = code.get("coding") or [{}]
    metric_name = coding[0].get("code") or code.get("text") or "unknown"
    unit = (resource.get("unit", {}) or {}).get("code") or resource.get("unit")
    db_dm = DeviceMetric(
        device_id=resource.get("device"),
        metric_name=metric_name,
        category=resource.get("category"),
        operational_status=resource.get("operationalStatus"),
        unit=unit,
        measurement_period=(
            resource.get("measurementPeriod")
            if isinstance(resource.get("measurementPeriod"), (int, float))
            else None
        ),
        fhir_resource=resource,
    )
    db.add(db_dm)
    db.flush()
    return db_dm, str(db_dm.id)


# Resource types the FHIR API can durably store. The Bundle handler persists
# every entry whose resourceType is a key here. Registering a new supported,
# persistable type is a one-line addition -- there is no brittle if/elif to
# forget, which is exactly the regression G9 is meant to close.
RESOURCE_PERSISTERS = {
    "Observation": _persist_observation,
    "DeviceMetric": _persist_device_metric,
}


@router.post("/Observation")
async def create_observation(
    observation: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("fhir_write"))
):
    """
    Create FHIR Observation resource.
    Implements SRS FR-3.7.3

    Args:
        observation: FHIR Observation resource

    Returns:
        Created resource or OperationOutcome error with application/fhir+json
    """
    # Validate resource
    is_valid, operation_outcome = validate_resource(observation)

    if not is_valid:
        return JSONResponse(
            content=operation_outcome,
            media_type="application/fhir+json",
            status_code=400
        )

    # Persist to the append-only observations table (SRS FR-3.7.3)
    try:
        db_obs, _ = _persist_observation(observation, db)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to persist Observation: {e}")
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "details": {"text": f"Failed to persist Observation: {str(e)}"}
            }]
        }
        return JSONResponse(
            content=outcome,
            media_type="application/fhir+json",
            status_code=500
        )

    location = f"/api/fhir/Observation/{db_obs.observation_uid}"
    return JSONResponse(
        content={"resourceType": "Observation", "id": db_obs.observation_uid, "resource": observation},
        media_type="application/fhir+json",
        status_code=201,
        headers={"Location": location}
    )


@router.get("/Observation/{observation_id}")
async def get_observation(
    observation_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("fhir_read"))
):
    """Retrieve FHIR Observation resource by UID from the database."""
    db_obs = db.query(Observation).filter(Observation.observation_uid == observation_id).first()
    if not db_obs:
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "not-found",
                "details": {"text": f"Observation {observation_id} not found"}
            }]
        }
        return JSONResponse(
            content=outcome,
            media_type="application/fhir+json",
            status_code=404
        )
    return JSONResponse(
        content=db_obs.fhir_resource or {"resourceType": "Observation", "id": db_obs.observation_uid},
        media_type="application/fhir+json"
    )


@router.post("/DeviceMetric")
async def create_device_metric(
    device_metric: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("fhir_write"))
):
    """
    Create FHIR DeviceMetric resource.
    Implements SRS FR-3.7.2

    Args:
        device_metric: FHIR DeviceMetric resource

    Returns:
        Created resource or OperationOutcome error with application/fhir+json
    """
    # Validate resource
    is_valid, operation_outcome = validate_resource(device_metric)

    if not is_valid:
        return JSONResponse(
            content=operation_outcome,
            media_type="application/fhir+json",
            status_code=400
        )

    # Persist to the device_metrics table (SRS FR-3.7.2)
    try:
        db_dm, _ = _persist_device_metric(device_metric, db)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to persist DeviceMetric: {e}")
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "details": {"text": f"Failed to persist DeviceMetric: {str(e)}"}
            }]
        }
        return JSONResponse(
            content=outcome,
            media_type="application/fhir+json",
            status_code=500
        )

    location = f"/api/fhir/DeviceMetric/{db_dm.id}"
    return JSONResponse(
        content={"resourceType": "DeviceMetric", "id": str(db_dm.id), "resource": device_metric},
        media_type="application/fhir+json",
        status_code=201,
        headers={"Location": location}
    )


@router.post("/Bundle")
async def process_bundle(
    bundle: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("fhir_write"))
):
    """
    Process FHIR Bundle (transaction/batch) with all-or-nothing persistence.
    Implements SRS FR-3.7.5

    Args:
        bundle: FHIR Bundle resource with entries to process

    Returns:
        Bundle response with processed entries or OperationOutcome error.
        For 'transaction' bundles, any validation or persistence error rolls
        back the entire bundle (all-or-nothing). For 'batch' bundles, only the
        failing entries are reported while valid entries are persisted.
    """
    # Validate bundle structure
    is_valid, operation_outcome = validate_resource(bundle)

    if not is_valid:
        return JSONResponse(
            content=operation_outcome,
            media_type="application/fhir+json",
            status_code=400
        )

    bundle_type = (bundle.get("type") or "transaction").lower()
    entries = bundle.get("entry", [])

    # Pass 1: validate every entry and plan persistence
    plan: List[Tuple[int, Dict, str, str, bool, Optional[Dict]]] = []
    for i, entry in enumerate(entries):
        request = entry.get("request", {})
        method = str(request.get("method", "POST")).upper()
        url = request.get("url", "")
        resource = entry.get("resource", {})

        entry_valid = True
        entry_outcome = None
        if resource:
            res_type = resource.get("resourceType")
            entry_valid, outcome = validate_resource(resource)
            if not entry_valid:
                for issue in outcome.get("issue", []):
                    loc = issue.get("location") or []
                    loc.insert(0, f"entry[{i}]")
                    issue["location"] = loc
                entry_outcome = outcome

        plan.append((i, resource, method, url, entry_valid, entry_outcome))

    validation_errors = [p[5] for p in plan if not p[4]]

    # Transaction bundles abort the whole operation on any error
    if bundle_type == "transaction" and validation_errors:
        db.rollback()
        combined_issues = []
        for err in validation_errors:
            combined_issues.extend(err.get("issue", []))
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": combined_issues
        }
        return JSONResponse(
            content=outcome,
            media_type="application/fhir+json",
            status_code=400
        )

    # Pass 2: persist planned entries transactionally
    processed_entries = []
    try:
        for i, resource, method, url, entry_valid, entry_outcome in plan:
            if not entry_valid:
                # Batch mode: report failure, do not persist
                processed_entries.append({
                    "response": {
                        "status": "400 Bad Request",
                        "code": "error",
                        "outcome": entry_outcome
                    }
                })
                continue

            if not resource:
                processed_entries.append({
                    "response": {"status": "200 OK", "code": "ok"}
                })
                continue

            res_type = resource.get("resourceType")
            persister = RESOURCE_PERSISTERS.get(res_type)

            if persister and method in ("POST", "PUT"):
                # G9 (FR-3.7.5): persist EVERY supported resource type inside
                # the Bundle, not only Observation. Dispatch is driven by
                # RESOURCE_PERSISTERS, so any registered type is stored
                # durably -- there is no silent "acknowledge without storage"
                # fall-through for supported types. A persistence failure
                # (e.g. constraint violation) propagates to the outer handler,
                # which rolls back the whole Bundle.
                orm_obj, rid = persister(resource, db)
                location = f"{url}/{rid}"
                processed_entries.append({
                    "response": {
                        "status": "201 Created",
                        "location": location,
                        "code": "created"
                    }
                })
            else:
                # Genuinely unsupported resource types (and non-write methods
                # such as GET/DELETE) are acknowledged without storage.
                status_code = "200 OK" if method == "PUT" else "201 Created"
                processed_entries.append({
                    "response": {
                        "status": status_code,
                        "location": url,
                        "code": "ok"
                    }
                })

        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Bundle transaction failed: {e}")
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{
                "severity": "error",
                "code": "exception",
                "details": {"text": f"Transaction aborted: {str(e)}"}
            }]
        }
        return JSONResponse(
            content=outcome,
            media_type="application/fhir+json",
            status_code=400
        )

    response_bundle = {
        "resourceType": "Bundle",
        "type": "transaction-response" if bundle_type == "transaction" else "batch-response",
        "entry": processed_entries
    }

    return JSONResponse(
        content=response_bundle,
        media_type="application/fhir+json"
    )
