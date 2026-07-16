"""
FHIR Routes
Implements SRS §3.7 - FHIR Interoperability
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from typing import Dict, Any, List
from fastapi.responses import JSONResponse

from api.auth import get_current_user, require_scope
from fhir_validator import validate_resource, to_operation_outcome, FHIRValidator

router = APIRouter()


@router.post("/Observation")
async def create_observation(
    observation: Dict[str, Any],
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
    
    # TODO: Store in database
    return JSONResponse(
        content={"status": "created", "id": "placeholder", "resource": observation},
        media_type="application/fhir+json"
    )


@router.get("/Observation/{observation_id}")
async def get_observation(
    observation_id: str,
    current_user=Depends(require_scope("fhir_read"))
):
    """Retrieve FHIR Observation resource"""
    # Placeholder
    return {"resourceType": "Observation", "id": observation_id}


@router.post("/DeviceMetric")
async def create_device_metric(
    device_metric: Dict[str, Any],
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
    
    # TODO: Store in database
    return JSONResponse(
        content={"status": "created", "id": "placeholder", "resource": device_metric},
        media_type="application/fhir+json"
    )


@router.post("/Bundle")
async def process_bundle(
    bundle: dict,
    current_user=Depends(require_scope("fhir_write"))
):
    """
    Process FHIR Bundle (transaction/batch).
    Implements SRS FR-3.7.5
    
    Args:
        bundle: FHIR Bundle resource with entries to process
    
    Returns:
        Bundle response with processed entries or OperationOutcome error
        Implements transaction semantics with rollback on error
    """
    # Validate bundle structure
    is_valid, operation_outcome = validate_resource(bundle)
    
    if not is_valid:
        return JSONResponse(
            content=operation_outcome,
            media_type="application/fhir+json",
            status_code=400
        )
    
    bundle_type = bundle.get("type", "transaction")
    entries = bundle.get("entry", [])
    
    # Process entries with transaction semantics
    processed_entries = []
    errors = []
    
    for i, entry in enumerate(entries):
        request = entry.get("request", {})
        method = request.get("method", "GET")
        url = request.get("url", "")
        resource = entry.get("resource", {})
        
        # Validate each resource
        if resource:
            res_type = resource.get("resourceType")
            is_valid, outcome = validate_resource(resource)
            
            if not is_valid:
                # Add location info to errors
                for issue in outcome.get("issue", []):
                    issue["location"].insert(0, f"entry[{i}]")
                errors.append(outcome)
                continue
        
        # Process based on method
        if method == "POST":
            # Create resource
            processed_entries.append({
                "response": {
                    "status": "201 Created",
                    "location": f"{url}/{i}",
                    "code": "created"
                }
            })
        elif method == "PUT":
            # Update resource
            processed_entries.append({
                "response": {
                    "status": "200 OK",
                    "code": "ok"
                }
            })
        elif method == "DELETE":
            # Delete resource
            processed_entries.append({
                "response": {
                    "status": "200 OK",
                    "code": "ok"
                }
            })
        else:
            processed_entries.append({
                "response": {
                    "status": "200 OK",
                    "code": "ok"
                }
            })
    
    # If any errors, return OperationOutcome (rollback)
    if errors:
        combined_issues = []
        for err in errors:
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
    
    # Return successful bundle response
    response_bundle = {
        "resourceType": "Bundle",
        "type": "transaction-response",
        "entry": processed_entries
    }
    
    return JSONResponse(
        content=response_bundle,
        media_type="application/fhir+json"
    )
