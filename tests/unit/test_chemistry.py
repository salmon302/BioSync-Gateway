# SPDX-License-Identifier: MIT
"""
Clinical chemistry generation unit tests — SRS FR-3.12.1–FR-3.12.4.

Pure tests (determinism, ranges, bundle structure, FHIR validation, mocked LIMS
post) run without a database. Wiring/router checks need JWT_SECRET (api.auth
fails closed on import). Persistence and API endpoint tests are gated on
DATABASE_URL (skipped locally, executed in CI against postgres:15).
"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest

from simulation.chemistry import (
    CHEMISTRY_VECTOR_SPEC,
    generate_chemistry_vectors,
    assemble_multimodal_bundle,
    send_lims_bundle,
)

DATABASE_URL = os.getenv("DATABASE_URL")
requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — requires a live PostgreSQL (CI provides it)",
)
requires_app = pytest.mark.skipif(
    not os.getenv("JWT_SECRET"),
    reason="JWT_SECRET not set — api.auth fails closed on import (set in CI)",
)


# ---------------------------------------------------------------------------
# Pure chemistry generation (no DB, no auth)
# ---------------------------------------------------------------------------

def test_vectors_deterministic():
    a = generate_chemistry_vectors(seed=123)
    b = generate_chemistry_vectors(seed=123)
    assert a == b  # FR-3.12.4 reproducible


def test_vectors_differ_by_seed():
    a = generate_chemistry_vectors(seed=1)
    b = generate_chemistry_vectors(seed=2)
    assert a != b


def test_vectors_within_ranges():
    vectors = generate_chemistry_vectors(seed=7)
    for category, analytes in CHEMISTRY_VECTOR_SPEC.items():
        for name, spec in analytes.items():
            value = vectors[category][name]["value"]
            assert spec["min"] <= value <= spec["max"], f"{name} out of range: {value}"


def test_assemble_bundle_structure():
    vectors = generate_chemistry_vectors(seed=7)
    clinvar_data = {"variants": [{"gene": "BRCA1", "clinical_significance": "Pathogenic"}]}
    bundle = assemble_multimodal_bundle(vectors, clinvar_data=clinvar_data)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    # 10 analytes (4 blood gas + 4 electrolytes + 2 metabolic) + 1 genomics entry
    assert len(bundle["entry"]) == 11
    for entry in bundle["entry"]:
        assert entry["resource"]["resourceType"] == "Observation"
        assert entry["request"]["method"] == "POST"


def test_assemble_bundle_fhir_valid():
    from fhir_validator import FHIRValidator

    vectors = generate_chemistry_vectors(seed=7)
    bundle = assemble_multimodal_bundle(vectors)  # validate=True by default
    ok, errors = FHIRValidator().validate_bundle(bundle)
    assert ok, [e.message if hasattr(e, "message") else str(e) for e in errors]


def test_assemble_bundle_without_clinvar_has_ten_entries():
    vectors = generate_chemistry_vectors(seed=3)
    bundle = assemble_multimodal_bundle(vectors)
    assert len(bundle["entry"]) == 10


def test_send_lims_bundle_captures_response():
    fake_response = MagicMock()
    fake_response.is_success = True
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "resourceType": "OperationOutcome",
        "issue": [],
    }
    fake_response.text = json.dumps({"resourceType": "OperationOutcome"})

    bundle = assemble_multimodal_bundle(generate_chemistry_vectors(seed=1))
    with patch("httpx.post", return_value=fake_response) as mock_post:
        result = send_lims_bundle(bundle, "https://lims.example/ingest")
    mock_post.assert_called_once()
    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["body"]["resourceType"] == "OperationOutcome"


def test_send_lims_bundle_handles_transport_error():
    bundle = assemble_multimodal_bundle(generate_chemistry_vectors(seed=1))
    import httpx

    with patch("httpx.post", side_effect=httpx.ConnectError("boom")):
        result = send_lims_bundle(bundle, "https://lims.example/ingest")
    assert result["ok"] is False
    assert "error" in result


# ---------------------------------------------------------------------------
# Wiring (needs JWT_SECRET)
# ---------------------------------------------------------------------------

@requires_app
def test_router_registered():
    from api.routes import chemistry as chemistry_route

    paths = [r.path for r in chemistry_route.router.routes]
    assert "/chemistry/profile" in paths
    assert "/chemistry/profile/{profile_id}" in paths
    assert "/chemistry/profiles" in paths


@requires_app
def test_app_includes_chemistry_routes():
    from api.main import app

    paths = set(app.openapi()["paths"].keys())
    assert "/api/simulation/chemistry/profile" in paths
    assert "/api/simulation/chemistry/profiles" in paths
    assert "/api/simulation/chemistry/profile/{profile_id}" in paths


# ---------------------------------------------------------------------------
# Persistence + API (DB-gated)
# ---------------------------------------------------------------------------

@requires_db
def test_generate_chemistry_profile_persists():
    from database import SessionLocal
    from models import ChemistryProfile

    db = SessionLocal()
    try:
        row = generate_chemistry_profile(
            db, seed=99, patient_id="syn-1", scenario_run_id=None,
        )
        db.commit()
        assert row.id is not None
        assert row.profile_uid is not None
        assert row.chemistry_vectors["blood_gas"]["pH"]["value"] > 0
        fetched = db.query(ChemistryProfile).filter_by(id=row.id).first()
        assert fetched is not None
        assert fetched.fhir_bundle["type"] == "transaction"
    finally:
        db.close()


@requires_db
def test_chemistry_profile_endpoint_roundtrip(authenticated_client):
    body = {
        "seed": 99,
        "patient_id": "syn-1",
        "clinvar_data": {
            "variants": [{"gene": "BRCA1", "clinical_significance": "Pathogenic"}]
        },
    }
    resp = authenticated_client.post("/api/simulation/chemistry/profile", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["profile_uid"] is not None
    assert data["fhir_bundle"]["type"] == "transaction"
    pid = data["profile_id"]

    get_resp = authenticated_client.get(f"/api/simulation/chemistry/profile/{pid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["profile_uid"] == data["profile_uid"]


@requires_db
def test_chemistry_requires_auth(unauthorized_client):
    resp = unauthorized_client.post("/api/simulation/chemistry/profile", json={})
    assert resp.status_code in (401, 403)
