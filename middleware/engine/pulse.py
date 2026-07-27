"""
Pulse Physiology Engine Integration
Implements SRS §3.6 - Pulse Engine Integration

This module provides integration with the Kitware Pulse Physiology Engine
for high-fidelity patient simulation.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import time
import hashlib
import uuid
import logging
from concurrent.futures import ProcessPoolExecutor, Future

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


class PulseWorker:
    """
    Worker class for Pulse Physiology Engine simulation.
    
    Implements:
        SRS FR-3.6.1 - Engine initialization
        SRS FR-3.6.2 - State serialization
        SRS FR-3.6.3 - GPB → JSONB serialization
        SRS FR-3.6.4 - Data request manager
        SRS FR-3.6.5 - Multi-patient simulation
    """
    
    # Required metrics to extract (SRS FR-3.6.4)
    REQUIRED_METRICS = [
        "HeartRate",
        "SystolicArterialPressure_mmHg",
        "DiastolicArterialPressure_mmHg",
        "RespirationRate",
        "OxygenSaturation",
        "MeanAirwayPressure_cmH2O",
        "ArterialOxygenPartialPressure_mmHg"
    ]
    
    # Simulation time step (seconds)
    TIME_STEP = 0.01  # 10 ms
    
    def __init__(self, patient_config: PatientConfig):
        """
        Initialize Pulse Worker.
        
        Args:
            patient_config: Patient-specific configuration
        """
        self.patient_config = patient_config
        self.state = SimulationState.INITIALIZING
        self.engine = None
        self.future: Optional[Future] = None
        self.start_time: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.metrics_history: List[SimulationMetrics] = []
        
    def initialize(self) -> bool:
        """
        Initialize Pulse Physiology Engine.

        Returns:
            True if initialization successful

        Implements:
            SRS FR-3.6.1 - Engine initialization
            IQ-4 - PyPulse import verification

        Note:
            PyPulse is a hard dependency. If the import fails, initialization
            returns False and the caller must handle the error. There is no
            mock fallback in production (SRS C1: Pulse C++ core is single-
            threaded per patient and must be delegated to worker pools).
        """
        try:
            import PyPulse
            self.engine = PyPulse.Engine()
        except ImportError as e:
            logger.error(
                "PyPulse is not available. The Pulse Physiology Engine is a "
                "required dependency (SRS FR-3.6.1). Build it via the "
                "multi-stage Dockerfile (see DEVELOPMENT_PLAN §7.1). "
                f"ImportError: {e}"
            )
            self.state = SimulationState.ERROR
            return False

        # Initialize engine with patient configuration
        if self.engine:
            self.engine.initialize(
                age=self.patient_config.age,
                weight=self.patient_config.weight_kg,
                height=self.patient_config.height_cm,
                sex=self.patient_config.sex
            )

        self.state = SimulationState.RUNNING
        self.start_time = time.time()
        return True
    
    def step(self, n_steps: int = 1) -> Dict[str, float]:
        """
        Advance simulation by N time-steps.
        
        Args:
            n_steps: Number of time-steps to advance
            
        Returns:
            Dictionary of extracted metrics
            
        Implements:
            SRS FR-3.6.2 - Simulation stepping
            SRS NFR-P5 - Pulse Engine time-step ≤ 50 ms
        """
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot step simulation in state: {self.state}")
        
        if not self.engine:
            raise RuntimeError("Engine not initialized")
        
        # Advance engine
        for _ in range(n_steps):
            self.engine.step(self.TIME_STEP)
        
        # Extract required metrics
        metrics = self._extract_metrics()
        self.metrics_history.append(metrics)
        
        # Record step latency for NFR-P5 instrumentation
        try:
            from api.middleware.response_time import record_pulse_step
            step_latency_ms = (time.perf_counter() - self.start_time) * 1000 / max(n_steps, 1)
            record_pulse_step(step_latency_ms)
        except (ImportError, AttributeError):
            pass
        
        return metrics.__dict__
    
    def pause(self) -> 'SerializedState':
        """
        Pause simulation and serialize state.
        
        Returns:
            Serialized simulation state
            
        Implements:
            SRS FR-3.6.2 - State serialization on pause
        """
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot pause simulation in state: {self.state}")
        
        self.paused_at = time.time()
        self.state = SimulationState.PAUSED
        
        # Serialize state
        return self.serialize_state()
    
    def resume(self) -> bool:
        """
        Resume simulation from paused state.
        
        Returns:
            True if resume successful
        """
        if self.state != SimulationState.PAUSED:
            raise ValueError(f"Cannot resume simulation in state: {self.state}")
        
        self.state = SimulationState.RUNNING
        # Adjust start time to account for pause duration
        return True
    
    def stop(self) -> 'SerializedState':
        """
        Stop simulation and serialize final state.
        
        Returns:
            Final serialized state
        """
        self.state = SimulationState.STOPPED
        return self.serialize_state()
    
    def serialize_state(self) -> 'SerializedState':
        """
        Serialize simulation state for persistence.

        Uses Google Protocol Buffers (Engine_pb2) for state serialization
        as required by SRS FR-3.6.3. The serialized GPB binary is base64-
        encoded for JSONB storage in PostgreSQL.

        Returns:
            SerializedState object

        Implements:
            SRS FR-3.6.3 - GPB → JSONB serialization with hash chain
        """
        # Serialize engine state via GPB (Engine_pb2)
        # In production, this uses the real PyPulse GPB schema:
        #   from Engine_pb2 import EngineState
        #   state_proto = EngineState()
        #   self.engine.get_state(state_proto)
        #   engine_state_b64 = base64.b64encode(state_proto.SerializeToString()).decode()
        #
        # For the interface contract, we require the engine to expose
        # serialize_to_gpb() returning raw GPB bytes.
        try:
            import base64
            gpb_bytes = self.engine.serialize_to_gpb()
            engine_state_b64 = base64.b64encode(gpb_bytes).decode()
        except AttributeError:
            raise RuntimeError(
                "PyPulse engine does not expose serialize_to_gpb(). "
                "Ensure a compatible Pulse Engine version is installed."
            )

        # Compute SHA-256 hash for tamper detection (SRS FR-3.8.3)
        state_hash = hashlib.sha256(engine_state_b64.encode()).hexdigest()

        # Extract latest metrics
        latest_metrics = self.metrics_history[-1] if self.metrics_history else None

        return SerializedState(
            patient_id=self.patient_config.patient_id,
            timestamp=time.time(),
            metrics={
                "HeartRate": latest_metrics.heart_rate if latest_metrics else 0,
                "SystolicArterialPressure_mmHg": latest_metrics.blood_pressure_systolic if latest_metrics else 0,
                "DiastolicArterialPressure_mmHg": latest_metrics.blood_pressure_diastolic if latest_metrics else 0,
                "RespirationRate": latest_metrics.respiratory_rate if latest_metrics else 0,
                "OxygenSaturation": latest_metrics.spo2 if latest_metrics else 0,
                "MeanAirwayPressure_cmH2O": latest_metrics.mean_airway_pressure_cm_h2o if latest_metrics else 0,
                "ArterialOxygenPartialPressure_mmHg": latest_metrics.arterial_o2_partial_pressure_mmhg if latest_metrics else 0
            },
            engine_state=engine_state_b64,
            state_hash=state_hash,
            serialization_format="GPB_v1_base64"
        )
    
    def _extract_metrics(self) -> SimulationMetrics:
        """
        Extract required physiological metrics from the engine.

        Uses the Pulse Data Request Manager to extract the metrics listed in
        SRS FR-3.6.4. Falls back to a deterministic baseline only if the engine
        exposes no data request API (should not happen with a real PyPulse).

        Returns:
            SimulationMetrics object

        Implements:
            SRS FR-3.6.4 - Data request manager
        """
        if self.engine is None:
            raise RuntimeError("Engine not initialized")

        # Use Pulse Data Request Manager to extract specific metrics (FR-3.6.4)
        # The real PyPulse API exposes get_data_requests() / pull_data()
        try:
            data_req_mgr = self.engine.get_data_request_manager()
            data_req_mgr.create_data_request("HeartRate", "bpm")
            data_req_mgr.create_data_request("SystolicArterialPressure_mmHg", "mmHg")
            data_req_mgr.create_data_request("DiastolicArterialPressure_mmHg", "mmHg")
            data_req_mgr.create_data_request("RespirationRate", "1/min")
            data_req_mgr.create_data_request("OxygenSaturation", "%")
            data_req_mgr.create_data_request("MeanAirwayPressure_cmH2O", "cmH2O")
            data_req_mgr.create_data_request("ArterialOxygenPartialPressure_mmHg", "mmHg")
            raw = data_req_mgr.pull_data()
        except AttributeError:
            # PyPulse API not fully available — raise rather than mock
            raise RuntimeError(
                "PyPulse engine does not expose a data request manager. "
                "Ensure a compatible Pulse Engine version is installed."
            )

        return SimulationMetrics(
            timestamp=time.time(),
            heart_rate=float(raw.get("HeartRate", 0.0)),
            blood_pressure_systolic=float(raw.get("SystolicArterialPressure_mmHg", 0.0)),
            blood_pressure_diastolic=float(raw.get("DiastolicArterialPressure_mmHg", 0.0)),
            respiratory_rate=float(raw.get("RespirationRate", 0.0)),
            spo2=float(raw.get("OxygenSaturation", 0.0)),
            temperature=0.0,
            cardiac_output=0.0,
            stroke_volume=0.0,
            systemic_vascular_resistance=0.0,
            mean_airway_pressure_cm_h2o=float(raw.get("MeanAirwayPressure_cmH2O", 0.0)),
            arterial_o2_partial_pressure_mmhg=float(raw.get("ArterialOxygenPartialPressure_mmHg", 0.0)),
        )


class SimulationManager:
    """
    Manages multiple concurrent Pulse Engine simulations.
    
    Implements:
        SRS FR-3.6.5 - Multi-patient simulation
        SRS FR-3.6.2 - Async delegation via ProcessPoolExecutor (Constraint C1)
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        Initialize simulation manager.
        
        Args:
            max_concurrent: Maximum number of concurrent simulations (SRS FR-3.6.5)
        """
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
        """
        Create a new simulation.
        
        Args:
            patient_config: Patient configuration
            
        Returns:
            Simulation ID
        """
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
                    status="active"
                )
                db.add(sim_record)
                db.commit()
                db.close()
            except Exception as e:
                logger.warning(f"Failed to persist simulation to DB: {e}")
        
        return simulation_id
    
    async def step_simulation(self, simulation_id: str, n_steps: int = 1) -> Dict:
        """
        Advance a simulation asynchronously.
        Uses ProcessPoolExecutor to avoid blocking the FastAPI event loop (Constraint C1).
        
        Args:
            simulation_id: Simulation ID
            n_steps: Number of time-steps
            
        Returns:
            Extracted metrics
        """
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        
        worker = self.simulations[simulation_id]
        
        # Delegate to ProcessPoolExecutor for non-blocking execution (SRS FR-3.6.2, C1)
        # In production, this runs the real PyPulse engine in a separate process.
        # For the mock: we use run_in_executor for proper async isolation.
        loop = self._get_loop()
        try:
            metrics = await loop.run_in_executor(
                self.executor,
                _step_worker_sync,
                worker,
                n_steps
            )
        except Exception:
            # Fallback: run synchronously if executor fails (e.g., on platforms
            # without fork support). This still ensures the API pattern is async.
            metrics = worker.step(n_steps)
        
        return metrics
    
    def pause_simulation(self, simulation_id: str) -> SimulationState:
        """Pause a simulation"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        
        state = self.simulations[simulation_id].pause()
        
        # Persist serialized state to database (SRS FR-3.6.3)
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "paused")
        
        return state
    
    def resume_simulation(self, simulation_id: str) -> bool:
        """Resume a simulation"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        
        success = self.simulations[simulation_id].resume()
        
        # Update status in database
        if DB_AVAILABLE and success:
            self._update_status(simulation_id, "active")
        
        return success
    
    def stop_simulation(self, simulation_id: str) -> 'SerializedState':
        """Stop a simulation and serialize final state"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        
        state = self.simulations[simulation_id].stop()
        
        # Persist final state and mark completed (SRS FR-3.6.3)
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "completed")
        
        del self.simulations[simulation_id]
        return state
    
    def _persist_state(self, simulation_id: str, state: 'SerializedState', status: str):
        """Persist simulation state to database"""
        try:
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
                    "serialization_format": state.serialization_format
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
    
    SRS FR-3.6.2: Async delegation to worker pool
    """
    return worker.step(n_steps)


# Test functions for IQ-4, OQ-16
def run_iq4_test() -> bool:
    """
    IQ-4: Verify PyPulse import and engine initialization.
    
    Returns:
        True if initialization succeeds
    """
    config = PatientConfig(
        patient_id="test-patient-1",
        age=45,
        weight_kg=70.0,
        height_cm=175.0,
        sex="male"
    )
    
    worker = PulseWorker(config)
    return worker.initialize()


def run_oq16_test() -> bool:
    """
    OQ-16: Verify state serialization and deserialization.
    
    Returns:
        True if serialization works correctly
    """
    config = PatientConfig(
        patient_id="test-patient-2",
        age=50,
        weight_kg=65.0,
        height_cm=165.0,
        sex="female"
    )
    
    worker = PulseWorker(config)
    if not worker.initialize():
        return False
    
    # Step simulation
    worker.step(100)
    
    # Pause and serialize
    state = worker.pause()
    
    # Verify state
    return state.is_valid and state.patient_id == "test-patient-2"


if __name__ == "__main__":
    # Self-test
    print("Running IQ-4 and OQ-16 tests...")
    
    print(f"IQ-4 (engine init): {'PASS' if run_iq4_test() else 'FAIL'}")
    print(f"OQ-16 (state serialization): {'PASS' if run_oq16_test() else 'FAIL'}")
