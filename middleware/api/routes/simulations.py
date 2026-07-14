"""
Pulse Engine Simulation Routes
Implements SRS §3.6 - Pulse Engine Integration
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import csv
import io
import json
import time

from api.auth import get_current_user, require_scope
from engine.pulse import (
    SimulationManager,
    PulseWorker,
    PatientConfig,
    SimulationState,
    SerializedState
)

router = APIRouter()

# Global simulation manager
simulation_manager = SimulationManager(max_concurrent=10)


@router.post("/")
async def create_simulation(
    simulation_config: Dict[str, Any],
    current_user=Depends(require_scope("simulation_write"))
):
    """
    Create new patient simulation.
    Implements SRS FR-3.6.1
    """
    try:
        config = PatientConfig(
            patient_id=simulation_config["patient_id"],
            age=simulation_config["age"],
            weight_kg=simulation_config["weight_kg"],
            height_cm=simulation_config["height_cm"],
            sex=simulation_config["sex"],
            base_heart_rate=simulation_config.get("base_heart_rate", 72.0),
            base_blood_pressure=simulation_config.get("base_blood_pressure", [120.0, 80.0]),
            base_spo2=simulation_config.get("base_spo2", 98.0),
            conditions=simulation_config.get("conditions", [])
        )
        
        simulation_id = simulation_manager.create_simulation(config)
        
        return {
            "simulation_id": simulation_id,
            "status": "created",
            "patient": config.patient_id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create simulation: {str(e)}")


@router.post("/{simulation_id}/step")
async def advance_simulation(
    simulation_id: str,
    steps: int = 1,
    current_user=Depends(require_scope("simulation_write"))
):
    """
    Advance simulation by N time-steps (async, non-blocking).
    Implements SRS FR-3.6.2 + Constraint C1
    """
    try:
        metrics = await simulation_manager.step_simulation(simulation_id, steps)
        return {
            "simulation_id": simulation_id,
            "steps_completed": steps,
            "metrics": metrics
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


@router.post("/{simulation_id}/pause")
async def pause_simulation(
    simulation_id: str,
    current_user=Depends(require_scope("simulation_write"))
):
    """
    Pause a running simulation and persist serialized state.
    Implements SRS FR-3.6.2 / FR-3.6.3
    """
    try:
        state = simulation_manager.pause_simulation(simulation_id)
        return {
            "simulation_id": simulation_id,
            "status": "paused",
            "serialized_state": {
                "patient_id": state.patient_id,
                "timestamp": state.timestamp,
                "metrics": state.metrics,
                "engine_state": state.engine_state,
                "state_hash": state.state_hash,
                "serialization_format": state.serialization_format
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{simulation_id}/resume")
async def resume_simulation(
    simulation_id: str,
    current_user=Depends(require_scope("simulation_write"))
):
    """
    Resume a paused simulation.
    """
    try:
        success = simulation_manager.resume_simulation(simulation_id)
        return {
            "simulation_id": simulation_id,
            "status": "active" if success else "error"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{simulation_id}/stop")
async def stop_simulation(
    simulation_id: str,
    current_user=Depends(require_scope("simulation_write"))
):
    """
    Stop a simulation and return final serialized state.
    Implements SRS FR-3.6.2
    """
    try:
        state = simulation_manager.stop_simulation(simulation_id)
        return {
            "simulation_id": simulation_id,
            "status": "stopped",
            "serialized_state": {
                "patient_id": state.patient_id,
                "timestamp": state.timestamp,
                "metrics": state.metrics,
                "engine_state": state.engine_state,
                "state_hash": state.state_hash,
                "serialization_format": state.serialization_format
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{simulation_id}/status")
async def get_simulation_status(
    simulation_id: str,
    current_user=Depends(require_scope("simulation_read"))
):
    """
    Get simulation status and metrics history length.
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    worker = simulation_manager.simulations[simulation_id]
    
    return {
        "simulation_id": simulation_id,
        "state": worker.state.value,
        "metrics_history_length": len(worker.metrics_history),
        "patient_id": worker.patient_config.patient_id
    }


@router.get("/{simulation_id}/metrics")
async def get_simulation_metrics(
    simulation_id: str,
    limit: int = 100,
    current_user=Depends(require_scope("simulation_read"))
):
    """
    Get simulation metrics history.
    Implements SRS FR-3.6.4
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    worker = simulation_manager.simulations[simulation_id]
    history = worker.metrics_history[-limit:]
    
    return {
        "simulation_id": simulation_id,
        "metrics_count": len(history),
        "metrics": [
            {
                "timestamp": m.timestamp,
                "HeartRate": m.heart_rate,
                "SystolicArterialPressure_mmHg": m.blood_pressure_systolic,
                "DiastolicArterialPressure_mmHg": m.blood_pressure_diastolic,
                "RespirationRate": m.respiratory_rate,
                "OxygenSaturation": m.spo2,
                "MeanAirwayPressure_cmH2O": m.mean_airway_pressure_cm_h2o,
                "ArterialOxygenPartialPressure_mmHg": m.arterial_o2_partial_pressure_mmhg
            }
            for m in history
        ]
    }


@router.get("/{simulation_id}/state")
async def get_simulation_state(
    simulation_id: str,
    current_user=Depends(require_scope("simulation_read"))
):
    """
    Get serialized simulation state.
    Implements SRS FR-3.6.3
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    worker = simulation_manager.simulations[simulation_id]
    state = worker.serialize_state()
    
    return {
        "simulation_id": simulation_id,
        "state": {
            "patient_id": state.patient_id,
            "timestamp": state.timestamp,
            "metrics": state.metrics,
            "engine_state": state.engine_state,
            "state_hash": state.state_hash,
            "serialization_format": state.serialization_format
        }
    }


@router.get("/{simulation_id}/export")
async def export_simulation_metrics(
    simulation_id: str,
    format: str = Query("json", regex="^(json|csv)$"),
    current_user=Depends(require_scope("simulation_read"))
):
    """
    Export simulation metrics as JSON or CSV.
    Implements SRS FR-3.9.2 (FAIR data export) and FR-3.6.4
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    worker = simulation_manager.simulations[simulation_id]
    history = worker.metrics_history
    
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp", "HeartRate", "SystolicArterialPressure_mmHg",
            "DiastolicArterialPressure_mmHg", "RespirationRate",
            "OxygenSaturation", "MeanAirwayPressure_cmH2O",
            "ArterialOxygenPartialPressure_mmHg"
        ])
        for m in history:
            writer.writerow([
                m.timestamp, m.heart_rate, m.blood_pressure_systolic,
                m.blood_pressure_diastolic, m.respiratory_rate,
                m.spo2, m.mean_airway_pressure_cm_h2o,
                m.arterial_o2_partial_pressure_mmhg
            ])
        return PlainTextResponse(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=sim-{simulation_id}-metrics.csv"}
        )
    
    # JSON format (default)
    return {
        "simulation_id": simulation_id,
        "patient_id": worker.patient_config.patient_id,
        "exported_at": datetime.utcnow().isoformat(),
        "format": "json",
        "metrics_count": len(history),
        "metrics": [
            {
                "timestamp": m.timestamp,
                "HeartRate": m.heart_rate,
                "SystolicArterialPressure_mmHg": m.blood_pressure_systolic,
                "DiastolicArterialPressure_mmHg": m.blood_pressure_diastolic,
                "RespirationRate": m.respiratory_rate,
                "OxygenSaturation": m.spo2,
                "MeanAirwayPressure_cmH2O": m.mean_airway_pressure_cm_h2o,
                "ArterialOxygenPartialPressure_mmHg": m.arterial_o2_partial_pressure_mmhg
            }
            for m in history
        ]
    }


@router.post("/purge")
async def purge_old_simulations(
    older_than_days: int = Query(90, ge=1),
    current_user=Depends(require_scope("simulation_write"))
):
    """
    Purge simulation states older than N days.
    Implements SRS §6.3 — 90-day retention policy.
    """
    cutoff = time.time() - (older_than_days * 86400)
    purged = []
    
    for sim_id, worker in list(simulation_manager.simulations.items()):
        if worker.start_time and worker.start_time < cutoff:
            if worker.state not in (SimulationState.RUNNING,):
                del simulation_manager.simulations[sim_id]
                purged.append(sim_id)
    
    return {
        "purged_count": len(purged),
        "purged_simulations": purged,
        "retention_days": older_than_days,
        "remaining_simulations": simulation_manager.get_simulation_count()
    }


@router.get("/{simulation_id}/diff")
async def diff_simulation_state(
    simulation_id: str,
    timestamp1: Optional[float] = None,
    timestamp2: Optional[float] = None,
    current_user=Depends(require_scope("simulation_read"))
):
    """
    Diff two simulation states for audit purposes.
    Implements SRS FR-3.6.3 — State comparison/diffing.
    
    Compares serialized states at two points in time.
    If timestamps not provided, compares initial vs current state.
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    worker = simulation_manager.simulations[simulation_id]
    current_state = worker.serialize_state()
    
    # Find closest historical states
    state1_metrics = current_state.metrics
    state2_metrics = current_state.metrics
    
    if timestamp1 and len(worker.metrics_history) > 1:
        closest = min(worker.metrics_history, key=lambda m: abs(m.timestamp - timestamp1))
        state2_metrics = {
            "HeartRate": closest.heart_rate,
            "SystolicArterialPressure_mmHg": closest.blood_pressure_systolic,
            "DiastolicArterialPressure_mmHg": closest.blood_pressure_diastolic,
            "RespirationRate": closest.respiratory_rate,
            "OxygenSaturation": closest.spo2,
            "MeanAirwayPressure_cmH2O": closest.mean_airway_pressure_cm_h2o,
            "ArterialOxygenPartialPressure_mmHg": closest.arterial_o2_partial_pressure_mmhg
        }
    
    if timestamp2 and len(worker.metrics_history) > 1:
        closest2 = min(worker.metrics_history, key=lambda m: abs(m.timestamp - timestamp2))
        state1_metrics = {
            "HeartRate": closest2.heart_rate,
            "SystolicArterialPressure_mmHg": closest2.blood_pressure_systolic,
            "DiastolicArterialPressure_mmHg": closest2.blood_pressure_diastolic,
            "RespirationRate": closest2.respiratory_rate,
            "OxygenSaturation": closest2.spo2,
            "MeanAirwayPressure_cmH2O": closest2.mean_airway_pressure_cm_h2o,
            "ArterialOxygenPartialPressure_mmHg": closest2.arterial_o2_partial_pressure_mmhg
        }
    
    # Compute diffs
    diffs = {}
    all_keys = set(state1_metrics.keys()) | set(state2_metrics.keys())
    for key in sorted(all_keys):
        v1 = state1_metrics.get(key, 0)
        v2 = state2_metrics.get(key, 0)
        if v1 != v2:
            diffs[key] = {"from": v2, "to": v1, "delta": round(v1 - v2, 4)}
    
    return {
        "simulation_id": simulation_id,
        "patient_id": worker.patient_config.patient_id,
        "diffs": diffs,
        "diff_count": len(diffs),
        "state1_timestamp": timestamp2 or current_state.timestamp,
        "state2_timestamp": timestamp1 or current_state.timestamp
    }


@router.get("/")
async def list_simulations(
    current_user=Depends(require_scope("simulation_read"))
):
    """
    List all active simulations.
    """
    return {
        "active_simulations": simulation_manager.get_simulation_count(),
        "max_concurrent": simulation_manager.max_concurrent,
        "simulation_ids": list(simulation_manager.simulations.keys())
    }
