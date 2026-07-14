"""
Microplate Routes
Implements SRS §3.2 - Microplate Editor
"""

from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from api.auth import get_current_user, require_scope

router = APIRouter()


@router.post("/")
async def create_plate(
    plate_data: dict,
    current_user=Depends(require_scope("plate_write"))
):
    """Create a new microplate"""
    # Placeholder
    return {"status": "created", "plate_id": "placeholder"}


@router.get("/{plate_id}")
async def get_plate(
    plate_id: int,
    current_user=Depends(require_scope("plate_read"))
):
    """Retrieve plate details"""
    # Placeholder
    return {"plate_id": plate_id, "status": "placeholder"}


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
