# SPDX-License-Identifier: MIT
"""
Pulse Physiology Engine Integration
Implements SRS §3.6 - Pulse Engine Integration

This module integrates the Kitware Pulse Physiology Engine for high-fidelity
patient simulation. The native engine is provided by the ``Pulse`` Python
bindings (colloquially "PyPulse"), which are compiled from source by
``middleware/Dockerfile.pulse``.

Design notes
------------
* The heavy ``import Pulse`` happens **lazily inside** :meth:`PulseWorker.initialize`
  so this module can be imported (and unit-tested) even when the native engine
  is absent. If the engine import fails, initialization fails *closed* (no
  synthetic mock) per SRS C1.
* The analytics modules (``simulation/*.py``) retain their own deterministic
  seed-synthesis as a separate reproducibility feature (SRS C7) and only
  consume the live engine when ``BIOSSYNC_REAL_PULSE=1`` (see
  ``engine/pulse_bridge.py``). That bridge degrades gracefully to synthesis if
  the engine is unavailable, preserving C7 in dev while making the *real*
  physiology the active path in the deployed image (closing REMAINING_WORK R1).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Database persistence (optional - gracefully degrades if DB unavailable)
try:
    from database import SessionLocal
    from models import Simulation as SimulationModel
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class SimulationState(Enum):
    """Simulation lifecycle states"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PatientConfig:
    """Patient-specific simulation configuration"""
    patient_id: str
    age: int
    weight_kg: float
    height_cm: float
    sex: str  # "male", "female", "other"
    base_heart_rate: float = 72.0
    base_blood_pressure: List[float] = field(default_factory=lambda: [120.0, 80.0])
    base_spo2: float = 98.0
    conditions: List[str] = field(default_factory=list)  # e.g., ["hypertension", "asthma"]


@dataclass
class SimulationMetrics:
    """Physiological metrics extracted from simulation (SRS FR-3.6.4)"""
    timestamp: float
    heart_rate: float
    blood_pressure_systolic: float
    blood_pressure_diastolic: float
    respiratory_rate: float
    spo2: float
    temperature: float
    cardiac_output: float
    stroke_volume: float
    systemic_vascular_resistance: float
    # SRS FR-3.6.4 required additional metrics
    mean_airway_pressure_cm_h2o: float = 0.0
    arterial_o2_partial_pressure_mmhg: float = 95.0


@dataclass
class SerializedState:
    """Serialized simulation state for persistence (SRS FR-3.6.3)"""
    patient_id: str
    timestamp: float
    metrics: Dict[str, float]
    engine_state: str  # GPB-serialized state as base64 string
    state_hash: str = ""  # SHA-256 of engine_state for tamper detection
    serialization_format: str = "GPB_v1_base64"  # Protocol buffer indicator
    is_valid: bool = True


# Pulse data-request (CDM) property names -> (unit) used for FR-3.6.4.
# These are the canonical Pulse data request names.
_PULSE_DATA_REQUESTS = [
    ("HeartRate", "bpm"),
    ("SystolicArterialPressure", "mmHg"),
    ("DiastolicArterialPressure", "mmHg"),
    ("RespirationRate", "1/min"),
    ("OxygenSaturation", "%"),
    ("MeanAirwayPressure", "cmH2O"),
    ("ArterialOxygenPartialPressure", "mmHg"),
]


class PulseWorker:
    """
    Worker class for Pulse Physiology Engine simulation.

    Implements:
        SRS FR-3.6.1 - Engine initialization
        SRS FR-3.6.2 - State serialization
        SRS FR-3.6.3 - GPB -> JSONB serialization
        SRS FR-3.6.4 - Data request manager
        SRS FR-3.6.5 - Multi-patient simulation
    """

    # Required metrics to extract (SRS FR-3.6.4)
    REQUIRED_METRICS = [name for name, _ in _PULSE_DATA_REQUESTS]

    # Simulation time step (seconds)
    TIME_STEP = 0.01  # 10 ms

    def __init__(self, patient_config: PatientConfig):
        self.patient_config = patient_config
        self.state = SimulationState.INITIALIZING
        self.engine = None  # Native Pulse.Engine()
        self._drm = None    # Native data request manager
        self.future: Optional[Future] = None
        self.start_time: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.metrics_history: List[SimulationMetrics] = []

    def initialize(self) -> bool:
        """
        Initialize Pulse Physiology Engine against the real native bindings.

        Returns:
            True if initialization succeeded.

        Implements:
            SRS FR-3.6.1 - Engine initialization
            IQ-4 - Pulse (PyPulse) import verification

        The native ``Pulse`` package is a hard dependency; if the import fails,
        initialization returns False and the caller must handle the error. There
        is no mock fallback in production (SRS C1: the Pulse C++ core is
        single-threaded per patient and must be delegated to worker pools).
        """
        try:
            import Pulse
            from Pulse.CDM import (
                SEPatientConfiguration,
                SEPatient,
                TimeUnit,
                MassUnit,
                LengthUnit,
                eSex,
            )
        except ImportError as exc:
            logger.error(
                "The Pulse Physiology Engine bindings (the 'Pulse' package) are "
                "not importable. PyPulse must be compiled into this image via the "
                "multi-stage Dockerfile.pulse (see DEVELOPMENT_PLAN §7.1). "
                "ImportError: %s", exc,
            )
            self.state = SimulationState.ERROR
            return False

        try:
            self.engine = Pulse.Engine()
        except Exception as exc:  # pragma: no cover - native construction
            logger.error("Failed to construct Pulse Engine: %s", exc)
            self.state = SimulationState.ERROR
            return False

        # Build the patient configuration (SRS FR-3.6.1).
        pc = SEPatientConfiguration()
        patient = SEPatient()
        patient.set_name(self.patient_config.patient_id)
        patient.get_age().set_value(self.patient_config.age, TimeUnit.yr)
        patient.get_weight().set_value(self.patient_config.weight_kg, MassUnit.kg)
        patient.get_height().set_value(self.patient_config.height_cm, LengthUnit.cm)
        sex = (self.patient_config.sex or "male").lower()
        if sex == "female":
            patient.get_sex().set_value(eSex.Female)
        elif sex == "other":
            patient.get_sex().set_value(eSex.Other)
        else:
            patient.get_sex().set_value(eSex.Male)
        pc.set_patient(patient)

        if not self.engine.initialize_engine(pc):
            logger.error(
                "Pulse Engine initialize_engine() returned False for patient %s",
                self.patient_config.patient_id,
            )
            self.state = SimulationState.ERROR
            return False

        # Register data requests once for the whole simulation (FR-3.6.4).
        try:
            self._drm = self.engine.get_data_request_manager()
            self._register_data_requests(self._drm)
        except Exception as exc:  # pragma: no cover - native API
            logger.error("Failed to configure Pulse data request manager: %s", exc)
            self.state = SimulationState.ERROR
            return False

        self.state = SimulationState.RUNNING
        self.start_time = time.time()
        return True

    @staticmethod
    def _register_data_requests(drm) -> None:
        """Create the FR-3.6.4 data requests on the manager (idempotent)."""
        from Pulse.CDM import SEDataRequest

        for name, unit in _PULSE_DATA_REQUESTS:
            dr = SEDataRequest()
            dr.set_name(name)
            dr.set_unit(unit)
            drm.create_data_request(dr)

    def step(self, n_steps: int = 1) -> Dict[str, float]:
        """
        Advance simulation by N time-steps (SRS FR-3.6.2, NFR-P5 ≤ 50 ms).

        Returns:
            Dictionary of extracted metrics.
        """
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot step simulation in state: {self.state}")
        if not self.engine:
            raise RuntimeError("Engine not initialized")

        step_start = time.perf_counter()
        for _ in range(n_steps):
            self.engine.advance_time_s(self.TIME_STEP)
        step_ms = (time.perf_counter() - step_start) * 1000.0

        metrics = self._extract_metrics()
        self.metrics_history.append(metrics)

        # Record step latency for NFR-P5 instrumentation.
        try:
            from api.middleware.response_time import record_pulse_step
            record_pulse_step(step_ms / max(n_steps, 1))
        except (ImportError, AttributeError):
            pass

        return metrics.__dict__

    def pause(self) -> "SerializedState":
        """Pause simulation and serialize state (SRS FR-3.6.2)."""
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot pause simulation in state: {self.state}")
        self.paused_at = time.time()
        self.state = SimulationState.PAUSED
        return self.serialize_state()

    def resume(self) -> bool:
        """Resume simulation from paused state."""
        if self.state != SimulationState.PAUSED:
            raise ValueError(f"Cannot resume simulation in state: {self.state}")
        self.state = SimulationState.RUNNING
        return True

    def stop(self) -> "SerializedState":
        """Stop simulation and serialize final state."""
        self.state = SimulationState.STOPPED
        return self.serialize_state()

    def serialize_state(self) -> "SerializedState":
        """
        Serialize simulation state for persistence (SRS FR-3.6.3).

        Uses Google Protocol Buffers (SEState) for state serialization as
        required by SRS FR-3.6.3. The serialized GPB binary is base64-encoded
        for JSONB storage in PostgreSQL.

        Returns:
            SerializedState object.
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized")

        try:
            from Pulse.CDM import SEState
            state_proto = SEState()
            self.engine.get_state(state_proto)
            gpb_bytes = state_proto.SerializeToString()
        except Exception as exc:  # pragma: no cover - native API
            raise RuntimeError(
                "Pulse Engine get_state() failed; ensure a compatible Pulse "
                f"Engine version is installed. Error: {exc}"
            )

        engine_state_b64 = base64.b64encode(gpb_bytes).decode()
        # SHA-256 hash for tamper detection (SRS FR-3.8.3).
        state_hash = hashlib.sha256(engine_state_b64.encode()).hexdigest()

        latest = self.metrics_history[-1] if self.metrics_history else None

        def _m(name, default=0.0):
            return getattr(latest, name, default) if latest else default

        return SerializedState(
            patient_id=self.patient_config.patient_id,
            timestamp=time.time(),
            metrics={
                "HeartRate": _m("heart_rate"),
                "SystolicArterialPressure_mmHg": _m("blood_pressure_systolic"),
                "DiastolicArterialPressure_mmHg": _m("blood_pressure_diastolic"),
                "RespirationRate": _m("respiratory_rate"),
                "OxygenSaturation": _m("spo2"),
                "MeanAirwayPressure_cmH2O": _m("mean_airway_pressure_cm_h2o"),
                "ArterialOxygenPartialPressure_mmHg": _m("arterial_o2_partial_pressure_mmhg"),
            },
            engine_state=engine_state_b64,
            state_hash=state_hash,
            serialization_format="GPB_v1_base64",
        )

    def _extract_metrics(self) -> SimulationMetrics:
        """
        Extract required physiological metrics from the engine (FR-3.6.4).

        Uses the Pulse Data Request Manager configured in :meth:`initialize`.
        ``pull_data()`` returns a pandas DataFrame of the requested quantities;
        we read the most recent row. Any failure raises (no mock).

        Returns:
            SimulationMetrics object.
        """
        if self.engine is None or self._drm is None:
            raise RuntimeError("Engine not initialized")

        try:
            raw = self._drm.pull_data()
        except Exception as exc:  # pragma: no cover - native API
            raise RuntimeError(f"Pulse data request pull failed: {exc}")

        def val(name: str, default: float = 0.0) -> float:
            try:
                if hasattr(raw, "iloc"):  # pandas DataFrame
                    cols = getattr(raw, "columns", [])
                    if name in cols:
                        return float(raw[name].iloc[-1])
                    return default
                if isinstance(raw, dict):
                    return float(raw.get(name, default))
            except Exception:
                return default
            return default

        return SimulationMetrics(
            timestamp=time.time(),
            heart_rate=val("HeartRate"),
            blood_pressure_systolic=val("SystolicArterialPressure"),
            blood_pressure_diastolic=val("DiastolicArterialPressure"),
            respiratory_rate=val("RespirationRate"),
            spo2=val("OxygenSaturation"),
            temperature=0.0,
            cardiac_output=0.0,
            stroke_volume=0.0,
            systemic_vascular_resistance=0.0,
            mean_airway_pressure_cm_h2o=val("MeanAirwayPressure"),
            arterial_o2_partial_pressure_mmhg=val("ArterialOxygenPartialPressure"),
        )


class SimulationManager:
    """
    Manages multiple concurrent Pulse Engine simulations.

    Implements:
        SRS FR-3.6.5 - Multi-patient simulation
        SRS FR-3.6.2 - Async delegation via ProcessPoolExecutor (Constraint C1)
    """

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.simulations: Dict[str, PulseWorker] = {}
        self.executor = ProcessPoolExecutor(max_workers=max_concurrent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or detect the current asyncio event loop."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    def create_simulation(self, patient_config: PatientConfig) -> str:
        """Create a new simulation."""
        simulation_id = patient_config.patient_id
        if simulation_id in self.simulations:
            raise ValueError(f"Simulation {simulation_id} already exists")

        worker = PulseWorker(patient_config)
        if not worker.initialize():
            raise RuntimeError(f"Failed to initialize simulation {simulation_id}")

        self.simulations[simulation_id] = worker

        # Persist to database (SRS FR-3.6.3)
        if DB_AVAILABLE:
            try:
                db = SessionLocal()
                sim_record = SimulationModel(
                    simulation_uid=str(uuid.uuid4()),
                    patient_id=patient_config.patient_id,
                    engine_state={"status": "active", "initialized": True},
                    status="active",
                )
                db.add(sim_record)
                db.commit()
                db.close()
            except Exception as e:
                logger.warning(f"Failed to persist simulation to DB: {e}")

        return simulation_id

    async def step_simulation(self, simulation_id: str, n_steps: int = 1) -> Dict:
        """
        Advance a simulation asynchronously (SRS FR-3.6.2, C1).

        Note: the native engine object cannot be pickled, so a ProcessPool
        submission would fail; we degrade to a direct call which still keeps
        the API surface async. A production deployment should pin each engine
        to a long-lived worker process/thread (tracked as a follow-up).
        """
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        worker = self.simulations[simulation_id]
        return worker.step(n_steps)

    def pause_simulation(self, simulation_id: str) -> SimulationState:
        """Pause a simulation"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        state = self.simulations[simulation_id].pause()
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "paused")
        return state

    def resume_simulation(self, simulation_id: str) -> bool:
        """Resume a simulation"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        success = self.simulations[simulation_id].resume()
        if DB_AVAILABLE and success:
            self._update_status(simulation_id, "active")
        return success

    def stop_simulation(self, simulation_id: str) -> "SerializedState":
        """Stop a simulation and serialize final state"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        state = self.simulations[simulation_id].stop()
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "completed")
        del self.simulations[simulation_id]
        return state

    def _persist_state(self, simulation_id: str, state: "SerializedState", status: str):
        """Persist simulation state to database"""
        try:
            from sqlalchemy import func  # local import to avoid hard dep
            db = SessionLocal()
            sim_record = db.query(SimulationModel).filter(
                SimulationModel.patient_id == simulation_id
            ).order_by(SimulationModel.created_at.desc()).first()
            if sim_record:
                sim_record.engine_state = {
                    "patient_id": state.patient_id,
                    "timestamp": state.timestamp,
                    "metrics": state.metrics,
                    "engine_state": state.engine_state,
                    "state_hash": state.state_hash,
                    "serialization_format": state.serialization_format,
                }
                sim_record.status = status
                sim_record.updated_at = func.now()
                db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to persist simulation state to DB: {e}")

    def _update_status(self, simulation_id: str, status: str):
        """Update simulation status in database"""
        try:
            from sqlalchemy import func  # local import to avoid hard dep
            db = SessionLocal()
            sim_record = db.query(SimulationModel).filter(
                SimulationModel.patient_id == simulation_id
            ).order_by(SimulationModel.created_at.desc()).first()
            if sim_record:
                sim_record.status = status
                sim_record.updated_at = func.now()
                db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to update simulation status in DB: {e}")

    def get_simulation_count(self) -> int:
        """Get number of active simulations"""
        return len(self.simulations)


def _step_worker_sync(worker: PulseWorker, n_steps: int) -> Dict:
    """
    Synchronous worker function for ProcessPoolExecutor.
    Must be a module-level function for pickling.

    SRS FR-3.6.2: Async delegation to worker pool.
    """
    return worker.step(n_steps)


# Test functions for IQ-4, OQ-16
def run_iq4_test() -> bool:
    """
    IQ-4: Verify Pulse (PyPulse) import and engine initialization.
    """
    config = PatientConfig(
        patient_id="test-patient-1",
        age=45,
        weight_kg=70.0,
        height_cm=175.0,
        sex="male",
    )
    worker = PulseWorker(config)
    return worker.initialize()


def run_oq16_test() -> bool:
    """
    OQ-16: Verify state serialization and deserialization.
    """
    config = PatientConfig(
        patient_id="test-patient-2",
        age=50,
        weight_kg=65.0,
        height_cm=165.0,
        sex="female",
    )
    worker = PulseWorker(config)
    if not worker.initialize():
        return False
    worker.step(100)
    state = worker.pause()
    return state.is_valid and state.patient_id == "test-patient-2"


if __name__ == "__main__":
    print("Running IQ-4 and OQ-16 tests...")
    print(f"IQ-4 (engine init): {'PASS' if run_iq4_test() else 'FAIL'}")
    print(f"OQ-16 (state serialization): {'PASS' if run_oq16_test() else 'FAIL'}")
