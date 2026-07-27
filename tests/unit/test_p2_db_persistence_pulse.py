"""
P2: DB Persistence Tests for Serialized State
Implements SRS FR-3.6.3 — Store serialized state in simulations table

Verifies:
- SerializedState contains all required fields for JSONB storage
- State hash is computed correctly
- Metrics use SRS-specified names
- Engine state is base64-encoded and GPB-compatible

NOTE: PyPulse is a required dependency. Tests skip when PyPulse is not
installed (e.g., local dev without the multi-stage Docker build).
"""

import pytest
import json
import hashlib
import base64

# Skip all tests if PyPulse is not available
pytest.importorskip("PyPulse")


class TestPulseDBPersistence:
    """Tests for FR-3.6.3 — DB persistence of serialized states."""

    def test_serialized_state_has_all_required_fields(self):
        """SerializedState must contain all fields for JSONB storage."""
        from middleware.engine.pulse import PulseWorker, PatientConfig, SerializedState

        config = PatientConfig(
            patient_id="db-test-001",
            age=45, weight_kg=70.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()
        worker.step(50)
        state = worker.serialize_state()

        # Required fields for JSONB column (SRS §6.1 — simulations table)
        assert state.patient_id == "db-test-001"
        assert state.timestamp > 0
        assert isinstance(state.metrics, dict)
        assert isinstance(state.engine_state, str)
        assert len(state.engine_state) > 0
        assert state.is_valid is True

    def test_engine_state_is_valid_base64(self):
        """Engine state must be valid base64-encoded GPB."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="b64-test-001",
            age=50, weight_kg=65.0, height_cm=165.0, sex="female"
        )
        worker = PulseWorker(config)
        worker.initialize()
        worker.step(10)
        state = worker.serialize_state()

        # Verify base64 encoding (GPB binary, not JSON)
        decoded = base64.b64decode(state.engine_state)
        assert decoded is not None
        assert len(decoded) > 0
        # GPB binary is not JSON — just verify it decodes to non-empty bytes
        assert isinstance(decoded, bytes)

    def test_state_hash_is_valid_sha256(self):
        """State hash must be a valid 64-char hex SHA-256."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="hash-test-001",
            age=35, weight_kg=70.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()
        worker.step(10)
        state = worker.serialize_state()

        # SHA-256 hex digest is 64 characters
        assert len(state.state_hash) == 64
        assert all(c in "0123456789abcdef" for c in state.state_hash)

        # Verify hash matches engine_state
        expected_hash = hashlib.sha256(state.engine_state.encode()).hexdigest()
        assert state.state_hash == expected_hash

    def test_metrics_use_srs_specified_names(self):
        """Metrics must use SRS FR-3.6.4 specified names."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="names-test-001",
            age=40, weight_kg=75.0, height_cm=180.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()
        worker.step(100)
        state = worker.serialize_state()

        # SRS FR-3.6.4 required metric names
        required_names = [
            "HeartRate",
            "SystolicArterialPressure_mmHg",
            "DiastolicArterialPressure_mmHg",
            "RespirationRate",
            "OxygenSaturation",
            "MeanAirwayPressure_cmH2O",
            "ArterialOxygenPartialPressure_mmHg"
        ]

        for name in required_names:
            assert name in state.metrics, f"Missing required metric: {name}"
            assert isinstance(state.metrics[name], (int, float))

    def test_serialization_format_indicates_gpb(self):
        """Serialization format must indicate GPB compatibility."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="fmt-test-001",
            age=30, weight_kg=60.0, height_cm=160.0, sex="female"
        )
        worker = PulseWorker(config)
        worker.initialize()
        worker.step(10)
        state = worker.serialize_state()

        assert "GPB" in state.serialization_format
        assert "v1" in state.serialization_format or "1" in state.serialization_format

    def test_pause_produces_valid_serialized_state(self):
        """Pausing a simulation must produce a valid SerializedState."""
        from middleware.engine.pulse import SimulationManager, PatientConfig

        manager = SimulationManager(max_concurrent=2)
        config = PatientConfig(
            patient_id="pause-persist-001",
            age=55, weight_kg=80.0, height_cm=170.0, sex="male"
        )
        sid = manager.create_simulation(config)
        manager.simulations[sid].step(20)

        state = manager.pause_simulation(sid)

        assert state.patient_id == "pause-persist-001"
        assert state.is_valid
        assert len(state.metrics) == 7  # All 7 required metrics
        assert state.state_hash
        assert state.serialization_format
