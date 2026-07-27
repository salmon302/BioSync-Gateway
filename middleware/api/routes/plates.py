"""
Microplate Routes
Implements SRS §3.2 - Microplate Editor
"""

import csv
import io
import json
import uuid
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional

from api.auth import get_current_user, require_scope
from database import get_db
from models import Plate, PlateWell, Observation
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/")
async def create_plate(
    plate_data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("plate_write"))
):
    """Create a new microplate with its wells (SRS FR-3.2).

    Accepts:
        - plate_name, plate_type ('96-well'|'384-well'), barcode_set (optional)
        - wells: list of {row, col, sample_id?, concentration?, volume?,
          status?, observation_uid?, metadata?}

    Persists the plate and wells, returning the new plate id/uid.
    """
    plate_name = plate_data.get("plate_name") or plate_data.get("name")
    if not plate_name:
        raise HTTPException(status_code=400, detail="plate_name is required")
    plate_type = plate_data.get("plate_type")
    if plate_type not in ("96-well", "384-well"):
        raise HTTPException(
            status_code=400,
            detail="plate_type must be '96-well' or '384-well'",
        )

    cols = 12 if plate_type == "96-well" else 24
    rows = 8 if plate_type == "96-well" else 16

    plate = Plate(
        plate_uid=str(uuid.uuid4()),
        plate_name=plate_name,
        plate_type=plate_type,
        barcode_set=plate_data.get("barcode_set"),
        created_by=getattr(current_user, "username", None),
        meta=plate_data.get("metadata"),
    )
    db.add(plate)
    db.flush()

    wells_in = plate_data.get("wells", [])
    for w in wells_in:
        row = w.get("row")
        col = w.get("col")
        if row is None or col is None:
            raise HTTPException(
                status_code=400, detail="each well requires row and col"
            )
        if not (0 <= row < rows and 0 <= col < cols):
            raise HTTPException(
                status_code=400,
                detail=f"well ({row},{col}) out of range for {plate_type}",
            )
        meta = dict(w.get("metadata") or {})
        if w.get("observation_uid"):
            meta["observation_uid"] = w["observation_uid"]
        db.add(
            PlateWell(
                plate_id=plate.id,
                well_row=row,
                well_column=col,
                well_index=row * cols + col,
                sample_id=w.get("sample_id"),
                concentration=w.get("concentration"),
                volume=w.get("volume"),
                status=w.get("status", "pending"),
                meta=meta,
            )
        )

    db.commit()
    db.refresh(plate)
    return {"status": "created", "plate_id": plate.id, "plate_uid": plate.plate_uid}


@router.get("/{plate_id}")
async def get_plate(
    plate_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("plate_read"))
):
    """Retrieve plate details including wells (SRS FR-3.2 / FR-3.2.3).

    Each well includes ``observationUid`` (from ``metadata['observation_uid']``)
    so the frontend can fetch the associated FHIR Observation on click.
    """
    plate = db.query(Plate).filter(Plate.id == plate_id).first()
    if not plate:
        raise HTTPException(status_code=404, detail="plate not found")

    wells = []
    for w in db.query(PlateWell).filter(PlateWell.plate_id == plate.id).all():
        meta = w.meta or {}
        wells.append({
            "id": w.id,
            "row": w.well_row,
            "col": w.well_column,
            "well_index": w.well_index,
            "sample_id": w.sample_id,
            "concentration": w.concentration,
            "volume": w.volume,
            "status": w.status,
            "observationUid": meta.get("observation_uid"),
            "metadata": meta,
        })

    return {
        "id": plate.id,
        "plate_uid": str(plate.plate_uid),
        "plate_name": plate.plate_name,
        "plate_type": plate.plate_type,
        "barcode_set": plate.barcode_set,
        "created_at": plate.created_at.isoformat() if plate.created_at else None,
        "wells": wells,
    }


@router.get("/{plate_id}/wells/{well_id}/observation")
async def get_well_observation(
    plate_id: int,
    well_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("plate_read"))
):
    """Resolve the FHIR Observation associated with a well (SRS FR-3.2.3).

    Looks up the well's ``observation_uid`` and returns the stored FHIR
    Observation resource. Returns 404 if the well or its Observation is absent.
    """
    well = (
        db.query(PlateWell)
        .filter(PlateWell.id == well_id, PlateWell.plate_id == plate_id)
        .first()
    )
    if not well:
        raise HTTPException(status_code=404, detail="well not found")
    observation_uid = (well.metadata or {}).get("observation_uid")
    if not observation_uid:
        raise HTTPException(status_code=404, detail="well has no linked observation")

    obs = (
        db.query(Observation)
        .filter(Observation.observation_uid == observation_uid)
        .first()
    )
    if not obs:
        raise HTTPException(status_code=404, detail="linked observation not found")
    return obs.fhir_resource


@router.post("/{plate_id}/validate-barcodes")
async def validate_barcodes(
    plate_id: int,
    barcode_data: dict,
    current_user=Depends(require_scope("plate_write"))
):
    """
    Validate barcode indices for a plate.
    Implements SRS FR-3.3.1, FR-3.3.2, FR-3.3.3
    
    Args:
        plate_id: Database ID of the plate
        barcode_data: Dict with 'barcodes' list and optional 'min_distance'
    
    Returns:
        Validation result with violations if any
    """
    from engine.barcode import validate_plate_barcodes, hamming_distance
    
    # Extract barcode sequences from request
    barcodes = barcode_data.get('barcodes', [])
    min_distance = barcode_data.get('min_distance', 3)
    
    if not barcodes:
        raise HTTPException(status_code=400, detail="No barcodes provided")
    
    # Validate barcodes
    result = validate_plate_barcodes(
        plate_id=plate_id,
        barcode_sequences=barcodes,
        barcode_set=barcode_data.get('barcode_set', 'TruSeq')
    )
    
    return result


@router.post("/{plate_id}/dilution-worklist")
async def generate_dilution_worklist(
    plate_id: int,
    dilution_request: dict,
    current_user=Depends(require_scope("plate_write"))
):
    """
    Generate dilution worklist for a plate.
    Implements SRS FR-3.4.1, FR-3.4.2, FR-3.4.3, FR-3.4.4
    
    Args:
        plate_id: Database ID of the plate
        dilution_request: Dict with:
            - initial_concentration: float
            - initial_unit: str (M, mM, µM, nM, ng/µL, etc.)
            - target_concentration: float
            - target_unit: str
            - molar_mass: float (optional, for unit conversion)
            - min_volume: float (optional, default 0.5 µL)
    
    Returns:
        Dilution worklist with steps
    """
    from engine.dilution import DilutionSolver
    
    # Extract parameters
    c1 = dilution_request.get('initial_concentration')
    unit1 = dilution_request.get('initial_unit')
    c2 = dilution_request.get('target_concentration')
    unit2 = dilution_request.get('target_unit')
    molar_mass = dilution_request.get('molar_mass')
    min_volume = dilution_request.get('min_volume', 0.5)
    
    if not all([c1 is not None, unit1, c2 is not None, unit2]):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: initial_concentration, initial_unit, target_concentration, target_unit"
        )
    
    # Initialize solver
    solver = DilutionSolver(min_volume=min_volume)
    
    # Convert units if needed
    if unit1 != unit2:
        try:
            c1_converted = solver.convert_units(c1, unit1, unit2, molar_mass)
            c1 = c1_converted
            unit1 = unit2
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Check if volume is below limit
    v1, v2 = solver.compute_volume(c1, c2)
    is_below, warning = solver.detect_below_limit(v1)
    
    # Generate worklist (with pre-dilution if needed)
    if is_below:
        worklist_obj = solver.generate_pre_dilution(c1, c2, molar_mass)
        worklist = {
            'sample_id': f"plate_{plate_id}",
            'initial_concentration': worklist_obj.initial_concentration,
            'initial_unit': worklist_obj.initial_unit,
            'target_concentration': worklist_obj.target_concentration,
            'target_unit': worklist_obj.target_unit,
            'steps': [step.__dict__ for step in worklist_obj.steps],
            'total_volume_needed': worklist_obj.total_volume_needed,
            'molar_mass': worklist_obj.molar_mass,
            'warning': warning
        }
    else:
        # Single step dilution
        step = {
            'step_number': 1,
            'source_concentration': c1,
            'source_unit': unit1,
            'target_concentration': c2,
            'target_unit': unit2,
            'volume_to_transfer': v1,
            'diluent_volume': v2,
            'total_volume': v1 + v2,
            'is_pre_dilution': False,
            'notes': 'Single-step dilution'
        }
        worklist = {
            'sample_id': f"plate_{plate_id}",
            'initial_concentration': c1,
            'initial_unit': unit1,
            'target_concentration': c2,
            'target_unit': unit2,
            'steps': [step],
            'total_volume_needed': v1 + v2,
            'molar_mass': molar_mass,
            'warning': None
        }
    
    return worklist


@router.post("/{plate_id}/import")
async def import_plate(
    plate_id: int,
    file: UploadFile = File(...),
    current_user=Depends(require_scope("plate_write"))
):
    """
    Import plate layout from CSV or JSON file.
    Implements SRS FR-3.2.5 (Import/Export)
    
    Args:
        plate_id: Database ID of the plate
        file: Uploaded CSV or JSON file
    
    Returns:
        Parsed plate layout data
    """
    content = await file.read()
    filename = file.filename or ""
    
    try:
        if filename.lower().endswith('.json'):
            data = json.loads(content.decode('utf-8'))
            # Expect format: {"rows": 8, "cols": 12, "wells": {"A1": {...}}}
            if not isinstance(data, dict) or 'wells' not in data:
                raise ValueError("Invalid JSON format: expected 'wells' key")
            wells = data['wells']
        elif filename.lower().endswith('.csv'):
            text = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(text))
            wells = {}
            for row in reader:
                well_id = row.get('well') or row.get('Well') or row.get('position')
                if not well_id:
                    continue
                wells[well_id] = {k: v for k, v in row.items() if k not in ('well', 'Well', 'position')}
        else:
            raise ValueError("Unsupported file format. Use .csv or .json")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")
    
    return {
        "plate_id": plate_id,
        "imported_wells": len(wells),
        "wells": wells,
        "format": "json" if filename.lower().endswith('.json') else "csv"
    }


@router.get("/{plate_id}/export")
async def export_plate(
    plate_id: int,
    format: str = Query("json", pattern="^(json|csv)$"),
    current_user=Depends(require_scope("plate_read"))
):
    """
    Export plate layout as CSV or JSON.
    Implements SRS FR-3.2.5 (Import/Export)
    
    Args:
        plate_id: Database ID of the plate
        format: Output format ('json' or 'csv')
    
    Returns:
        Streaming file response with plate data
    """
    # Placeholder data - in production, query database for plate layout
    placeholder_wells = {
        "A1": {"sample_id": "S001", "barcode": "ATCACG", "concentration": "10µM"},
        "A2": {"sample_id": "S002", "barcode": "CGATGT", "concentration": "10µM"},
        "B1": {"sample_id": "S003", "barcode": "TTCCGA", "concentration": "5µM"},
    }
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["well", "sample_id", "barcode", "concentration"])
        for well_id, data in placeholder_wells.items():
            writer.writerow([
                well_id,
                data.get("sample_id", ""),
                data.get("barcode", ""),
                data.get("concentration", "")
            ])
        media_type = "text/csv"
        filename = f"plate_{plate_id}.csv"
    else:
        output = io.StringIO()
        json.dump({
            "plate_id": plate_id,
            "rows": 8,
            "cols": 12,
            "wells": placeholder_wells
        }, output, indent=2)
        media_type = "application/json"
        filename = f"plate_{plate_id}.json"
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
