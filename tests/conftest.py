"""
BioSync-Gateway Test Configuration & Shared Fixtures
Implements SRS §3.0 — Test Foundation (P1)

Provides shared pytest fixtures for:
- FastAPI TestClient with JWT authentication
- Sample data (patients, barcodes, FHIR resources)
- Engine instances (EMA, DilutionSolver, barcode sets)
- Mock database sessions
"""

import sys
import os

# Add middleware directory to sys.path for imports
_MIDDLEWARE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "middleware")
if _MIDDLEWARE_DIR not in sys.path:
    sys.path.insert(0, _MIDDLEWARE_DIR)

import pytest
import time
import hashlib
import json
from typing import Generator, List, Dict, Any, Optional
from unittest.mock import MagicMock, patch


# =============================================================================
# Lazy imports — FastAPI may not be installed in all test environments
# =============================================================================

def _import_fastapi():
    """Lazy import FastAPI components."""
    from fastapi.testclient import TestClient
    from middleware.api.main import app
    return TestClient, app


def _import_auth():
    """Lazy import auth module."""
    from middleware.api.auth import create_access_token, JWT_SECRET, JWT_ALGORITHM
    return create_access_token, JWT_SECRET, JWT_ALGORITHM


def _import_engines():
    """Lazy import engine modules."""
    from middleware.engine.pulse import PulseWorker, PatientConfig, SimulationManager, SimulationState
    from middleware.engine.barcode import hamming_distance, validate_plate_indices, validate_plate_barcodes
    from middleware.engine.dilution import DilutionSolver, DilutionWorklist, DilutionStep
    from middleware.engine.signal import EMAFilter
    from middleware.engine.hash_chain import compute_hash, verify_chain, GENESIS_HASH
    return (PulseWorker, PatientConfig, SimulationManager, SimulationState,
            hamming_distance, validate_plate_indices, validate_plate_barcodes,
            DilutionSolver, DilutionWorklist, DilutionStep,
            EMAFilter, compute_hash, verify_chain, GENESIS_HASH)


def _import_fhir():
    """Lazy import FHIR validator."""
    from middleware.fhir_validator import FHIRValidator, ValidationError
    return FHIRValidator, ValidationError


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: API integration tests")
    config.addinivalue_line("markers", "performance: performance benchmarks")
    config.addinivalue_line("markers", "external: external API tests")
    config.addinivalue_line("markers", "e2e: end-to-end workflow tests")
    config.addinivalue_line("markers", "db: database-level tests")
    config.addinivalue_line("markers", "hf: human factors tests")
    config.addinivalue_line("markers", "slow: slow-running tests")


# =============================================================================
# FastAPI Application & Client Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def app_factory():
    """Return the FastAPI application instance."""
    _, app = _import_fastapi()
    return app


@pytest.fixture
def client(app_factory) -> Generator:
    """FastAPI TestClient for API testing."""
    TestClient, _ = _import_fastapi()
    with TestClient(app_factory) as c:
        yield c


# =============================================================================
# JWT Authentication Fixtures
# =============================================================================

@pytest.fixture
def sample_jwt_token() -> str:
    """Generate a valid JWT token for testing."""
    create_access_token, _, _ = _import_auth()
    payload = {
        "sub": "test-user",
        "role": "admin",
        "scopes": ["plate_read", "plate_write", "fhir_read", "fhir_write",
                    "audit_read", "telemetry_write", "simulation_write"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600  # 1 hour expiry
    }
    return create_access_token(payload, expires_delta=3600)


@pytest.fixture
def admin_jwt_token() -> str:
    """Generate an admin-level JWT token."""
    create_access_token, _, _ = _import_auth()
    payload = {
        "sub": "admin-user",
        "role": "admin",
        "scopes": ["plate_read", "plate_write", "fhir_read", "fhir_write",
                    "audit_read", "telemetry_write", "simulation_write"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    return create_access_token(payload, expires_delta=3600)


@pytest.fixture
def tech_jwt_token() -> str:
    """Generate a clinical technician JWT token (limited scopes)."""
    create_access_token, _, _ = _import_auth()
    payload = {
        "sub": "tech-user",
        "role": "technician",
        "scopes": ["telemetry_write", "fhir_read"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    return create_access_token(payload, expires_delta=3600)


@pytest.fixture
def expired_jwt_token() -> str:
    """Generate an expired JWT token for testing rejection."""
    create_access_token, _, _ = _import_auth()
    payload = {
        "sub": "test-user",
        "role": "admin",
        "scopes": ["plate_read"],
        "iat": int(time.time()) - 7200,  # issued 2 hours ago
        "exp": int(time.time()) - 3600   # expired 1 hour ago
    }
    return create_access_token(payload, expires_delta=-1)


@pytest.fixture
def invalid_jwt_token() -> str:
    """Generate an invalid JWT token."""
    return "invalid.token.here"


@pytest.fixture
def authenticated_client(client, sample_jwt_token) -> Generator:
    """TestClient with valid JWT token attached via Authorization header."""
    client.headers.update({
        "Authorization": f"Bearer {sample_jwt_token}"
    })
    yield client


@pytest.fixture
def unauthorized_client(client) -> Generator:
    """TestClient without any JWT token."""
    yield client


# =============================================================================
# Patient Configuration Fixtures
# =============================================================================

@pytest.fixture
def sample_patient_config():
    """Standard PatientConfig for simulation tests."""
    PulseWorker, PatientConfig, _, _ = _import_engines()
    return PatientConfig(
        patient_id="test-patient-001",
        age=45,
        weight_kg=70.0,
        height_cm=175.0,
        sex="male",
        base_heart_rate=72.0,
        base_blood_pressure=[120.0, 80.0],
        base_spo2=98.0,
        conditions=[]
    )


@pytest.fixture
def patient_configs_small():
    """Small set of diverse patient configs (3 patients)."""
    _, PatientConfig, _, _ = _import_engines()
    return [
        PatientConfig(patient_id="p1", age=25, weight_kg=60.0, height_cm=160.0, sex="female"),
        PatientConfig(patient_id="p2", age=65, weight_kg=85.0, height_cm=180.0, sex="male"),
        PatientConfig(patient_id="p3", age=50, weight_kg=70.0, height_cm=170.0, sex="other"),
    ]


@pytest.fixture
def patient_configs_ten():
    """Set of 10 patient configs for concurrent simulation tests."""
    _, PatientConfig, _, _ = _import_engines()
    configs = []
    for i in range(10):
        configs.append(PatientConfig(
            patient_id=f"patient-{i}",
            age=30 + i,
            weight_kg=60 + i * 2,
            height_cm=160 + i * 2,
            sex="male" if i % 2 == 0 else "female",
            base_heart_rate=70.0 + i,
            conditions=["respiratory_distress"] if i < 3 else []
        ))
    return configs


# =============================================================================
# Barcode Test Vector Fixtures
# =============================================================================

@pytest.fixture
def truseq_8bit_barcodes() -> List[str]:
    """Illumina TruSeq 8-base UDI barcodes (from Illumina doc 1000000002694)."""
    return [
        "ATCACG", "CGATGT", "AGATCG", "TTAGGC",
        "AATGAT", "TGGAAA", "CCTAGA", "GCTACC"
    ]


@pytest.fixture
def truseq_10bit_barcodes() -> List[str]:
    """Illumina TruSeq 10-base UDI barcodes."""
    return [
        "ATCACGATCG", "CGATGTAGCT", "AGATCGATTA", "TTAGGCTAGC",
        "AATGATCGAT", "TGGAACTAGC", "CCTAGATCGA", "GCTACCATCG",
        "TAGCTAGCAT", "GCATCGATCG"
    ]


@pytest.fixture
def invalid_barcodes_d1() -> List[str]:
    """Barcode set with d=1 violations (should be rejected)."""
    return ["ATCGAT", "ATCGAC", "TTAGGC"]  # First two have Hamming distance 1


@pytest.fixture
def invalid_barcodes_d2() -> List[str]:
    """Barcode set with d=2 violations (should be rejected)."""
    return ["ATCGAT", "ATCCAT", "TTAGGC"]  # First two have Hamming distance 2


@pytest.fixture
def valid_barcodes_d3() -> List[str]:
    """Barcode set meeting d>=3 requirement (should be accepted)."""
    return ["ATCACG", "CGATGT", "TTAGGC", "TGACCA"]


# =============================================================================
# FHIR Resource Fixtures
# =============================================================================

@pytest.fixture
def valid_observation() -> Dict[str, Any]:
    """Valid FHIR Observation resource."""
    return {
        "resourceType": "Observation",
        "id": "test-obs-001",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8310-5",
                "display": "Body temperature"
            }]
        },
        "valueQuantity": {
            "value": 36.5,
            "unit": "Celsius",
            "system": "http://unitsofmeasure.org",
            "code": "Cel"
        },
        "effectiveDateTime": "2026-07-13T10:00:00Z"
    }


@pytest.fixture
def minimal_observation() -> Dict[str, Any]:
    """Minimal valid Observation (only required fields)."""
    return {
        "resourceType": "Observation",
        "code": {"text": "Body temperature"},
        "valueQuantity": {"value": 98.6, "unit": "Fahrenheit"}
    }


@pytest.fixture
def observation_missing_value() -> Dict[str, Any]:
    """Observation missing required valueQuantity (should fail validation)."""
    return {
        "resourceType": "Observation",
        "id": "obs-no-value",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8310-5"
            }]
        }
    }


@pytest.fixture
def observation_missing_code() -> Dict[str, Any]:
    """Observation missing required code (should fail validation)."""
    return {
        "resourceType": "Observation",
        "id": "obs-no-code",
        "status": "final",
        "valueQuantity": {"value": 36.5, "unit": "Celsius"}
    }


@pytest.fixture
def valid_device_metric() -> Dict[str, Any]:
    """Valid FHIR DeviceMetric resource."""
    return {
        "resourceType": "DeviceMetric",
        "id": "test-dm-001",
        "operationalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/metric-operational-status",
                "code": "on"
            }]
        },
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/metric-type",
                "code": "temperature"
            }]
        },
        "unit": {
            "coding": [{
                "system": "http://unitsofmeasure.org",
                "code": "Cel"
            }]
        }
    }


@pytest.fixture
def device_metric_missing_status() -> Dict[str, Any]:
    """DeviceMetric missing required operationalStatus (should fail validation)."""
    return {
        "resourceType": "DeviceMetric",
        "id": "dm-no-status",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/metric-type",
                "code": "temperature"
            }]
        },
        "unit": {
            "coding": [{
                "system": "http://unitsofmeasure.org",
                "code": "Cel"
            }]
        }
    }


@pytest.fixture
def valid_fhir_bundle() -> Dict[str, Any]:
    """Valid FHIR Bundle (transaction type)."""
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "request": {
                    "method": "POST",
                    "url": "Observation"
                },
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": "Heart rate"},
                    "valueQuantity": {"value": 72, "unit": "/min"}
                }
            },
            {
                "request": {
                    "method": "POST",
                    "url": "Observation"
                },
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": "Blood pressure"},
                    "valueQuantity": {"value": 120, "unit": "mmHg"}
                }
            }
        ]
    }


# =============================================================================
# Engine Instance Fixtures
# =============================================================================

@pytest.fixture
def ema_filter_alpha_05():
    """EMA filter with alpha=0.5 (default)."""
    _, _, _, _, _, _, _, _, _, _, EMAFilter, _, _, _ = _import_engines()
    return EMAFilter(alpha=0.5)


@pytest.fixture
def ema_filter_alpha_02():
    """EMA filter with alpha=0.2 (pressure channel default per FR-3.5.2)."""
    _, _, _, _, _, _, _, _, _, _, EMAFilter, _, _, _ = _import_engines()
    return EMAFilter(alpha=0.2)


@pytest.fixture
def ema_filter_alpha_01():
    """EMA filter with alpha=0.1 (flow-rate channel default per FR-3.5.2)."""
    _, _, _, _, _, _, _, _, _, _, EMAFilter, _, _, _ = _import_engines()
    return EMAFilter(alpha=0.1)


@pytest.fixture
def dilution_solver():
    """DilutionSolver with default min_volume=0.5 µL."""
    DilutionSolver, _, _, _ = _import_engines()
    return DilutionSolver(min_volume=0.5)


@pytest.fixture
def dilution_solver_strict():
    """DilutionSolver with strict min_volume=1.0 µL."""
    DilutionSolver, _, _, _ = _import_engines()
    return DilutionSolver(min_volume=1.0)


@pytest.fixture
def pulse_worker(sample_patient_config):
    """Initialized PulseWorker for testing."""
    PulseWorker, _, _, _ = _import_engines()
    worker = PulseWorker(sample_patient_config)
    worker.initialize()
    return worker


@pytest.fixture
def simulation_manager(patient_configs_ten):
    """SimulationManager pre-loaded with 10 patient simulations."""
    _, _, SimulationManager, _ = _import_engines()
    manager = SimulationManager(max_concurrent=10)
    for config in patient_configs_ten:
        manager.create_simulation(config)
    return manager


# =============================================================================
# Hash Chain Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_audit_entries() -> List[Dict[str, Any]]:
    """Sample valid hash chain audit entries."""
    from datetime import datetime
    _, _, _, _, _, _, _, _, _, _, _, compute_hash, _, GENESIS_HASH = _import_engines()

    entries = []
    prev_hash = GENESIS_HASH

    for i in range(5):
        timestamp = datetime(2026, 7, 13, 10, 0, i)
        data = {"table": "plates", "record_id": i, "action": "insert"}
        current_hash = compute_hash(
            previous_hash=prev_hash,
            table_name="plates",
            operation="INSERT",
            record_id=i,
            timestamp=timestamp,
            user_id="test-user",
            data=data
        )
        entries.append({
            "id": i + 1,
            "previous_hash": prev_hash,
            "current_hash": current_hash,
            "table_name": "plates",
            "operation": "INSERT",
            "record_id": i,
            "timestamp": timestamp.isoformat(),
            "user_id": "test-user",
            "data": data
        })
        prev_hash = current_hash

    return entries


@pytest.fixture
def tampered_audit_entries(sample_audit_entries) -> List[Dict[str, Any]]:
    """Audit entries with the 3rd entry's data modified (chain break)."""
    tampered = sample_audit_entries.copy()
    tampered[2]["data"] = {"table": "plates", "record_id": 2, "action": "tampered"}
    return tampered


# =============================================================================
# Mock Database Session Fixture
# =============================================================================

@pytest.fixture
def mock_db_session() -> MagicMock:
    """Mock SQLAlchemy session for DB-dependent tests."""
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar.return_value = 1
    result_mock._mapping = {"col": "value"}
    session.execute.return_value = result_mock
    return session


# =============================================================================
# FHIR Validator Fixture
# =============================================================================

@pytest.fixture
def fhir_validator():
    """FHIRValidator instance."""
    FHIRValidator, _ = _import_fhir()
    return FHIRValidator()


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def test_timestamp() -> float:
    """Current timestamp for test data."""
    return time.time()


@pytest.fixture
def temp_directory(tmp_path) -> str:
    """Temporary directory for file-based tests."""
    return str(tmp_path)


# =============================================================================
# Conftest Documentation
# =============================================================================

"""
Usage examples:

    # API testing with JWT
    def test_protected_endpoint(authenticated_client):
        response = authenticated_client.get("/api/protected")
        assert response.status_code == 200

    # API testing without JWT
    def test_unauthorized_access(unauthorized_client):
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    # Barcode validation
    def test_valid_barcodes(valid_barcodes_d3):
        is_valid, violations = validate_plate_indices(valid_barcodes_d3, min_distance=3)
        assert is_valid

    # FHIR validation
    def test_valid_observation(valid_observation, fhir_validator):
        is_valid, outcome = fhir_validator.validate_observation(valid_observation)
        assert is_valid

    # EMA filtering
    def test_ema_convergence(ema_filter_alpha_05):
        convergence = ema_filter_alpha_05.get_convergence_step(0, 100, 0.05)
        assert convergence is not None and convergence <= 5

    # Dilution calculation
    def test_dilution_volume(dilution_solver):
        v1, v2 = dilution_solver.compute_volume(200.0, 1.0, 100.0)
        assert abs(v1 - 0.5) < 0.001

    # Hash chain verification
    def test_hash_chain(sample_audit_entries):
        is_valid, broken_at = verify_chain(sample_audit_entries)
        assert is_valid is True
        assert broken_at is None

    # Pulse simulation
    def test_pulse_step(pulse_worker):
        metrics = pulse_worker.step(100)
        assert metrics is not None
"""
