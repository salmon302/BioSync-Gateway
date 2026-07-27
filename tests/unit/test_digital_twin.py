# SPDX-License-Identifier: MIT
"""
Digital twin cohort unit tests — SRS FR-3.13.1–FR-3.13.5.

Pure tests (determinism, identity/PHI, timeseries, bundle structure, FHIR
validation, export reproducibility) run without a database. Wiring/router checks
need JWT_SECRET (api.auth fails closed on import). Persistence and API endpoint
tests are gated on DATABASE_URL (skipped locally, executed in CI).
"""
import os
from types import SimpleNamespace

import pytest

from simulation.digital_twin import (
    generate_cohort_members,
    simulate_member_timeseries,
    assemble_cohort_bundle,
    export_cohort_bundle,
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

BASE_SPEC = {
    "size": 4,
    "name": "test-cohort",
    "seed": 42,
    "demographic_distribution": {"age": {"min": 20, "max": 80}, "sex": ["male", "female"]},
    "clinvar_variant_set": [
        {"gene": "BRCA1", "clinical_significance": "Pathogenic"},
        {"gene": "TP53", "clinical_significance": "Uncertain"},
    ],
    "physiological_baseline_ranges": {
        "heart_rate": {"min": 70, "max": 90},
        "spo2": {"min": 96, "max": 99},
    },
}


# ---------------------------------------------------------------------------
# Pure cohort generation (no DB, no auth)
# ---------------------------------------------------------------------------

def test_members_deterministic():
    a = generate_cohort_members(BASE_SPEC, seed=42)
    b = generate_cohort_members(BASE_SPEC, seed=42)
    assert a == b  # FR-3.13.4 / FR-3.16.4 reproducible


def test_members_count_and_identities():
    members = generate_cohort_members(BASE_SPEC, seed=42)
    assert len(members) == BASE_SPEC["size"]
    for m in members:
        assert m["synthetic_id"].startswith("SYN-")  # synthetic, no PHI
        assert "age" in m["demographics"] and "sex" in m["demographics"]
        assert "baseline" in m
        assert m["variant"] is not None  # variant assigned from set


def test_members_different_seed_differs():
    a = generate_cohort_members(BASE_SPEC, seed=1)
    b = generate_cohort_members(BASE_SPEC, seed=2)
    assert a != b


def test_simulate_member_timeseries():
    members = generate_cohort_members(BASE_SPEC, seed=42)
    ts = simulate_member_timeseries(members[0], duration_min=1.0, cadence_sec=10.0, seed=42, index=0)
    n_samples = max(1, int(1.0 * 60 // 10.0))
    assert len(ts) == n_samples * 4  # 4 vital channels
    for obs in ts:
        assert obs["resourceType"] == "Observation"
        assert obs["subject"]["reference"] == f"Patient/{members[0]['synthetic_id']}"
        assert obs["device"]["reference"].startswith("Device/sim-")
        assert obs["valueQuantity"]["value"] is not None


def test_assemble_bundle_structure():
    members = generate_cohort_members(BASE_SPEC, seed=42)
    ts = {
        m["synthetic_id"]: simulate_member_timeseries(
            m, duration_min=0.1, cadence_sec=10.0, seed=42, index=i
        )
        for i, m in enumerate(members)
    }
    bundle = assemble_cohort_bundle(members, ts)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    for entry in bundle["entry"]:
        assert entry["resource"]["resourceType"] == "Observation"
        assert entry["request"]["method"] == "POST"
    # each member has vital obs (1 sample * 4) + 1 genomics = 5; *4 members = 20
    assert len(bundle["entry"]) == BASE_SPEC["size"] * 5


def test_assemble_bundle_fhir_valid():
    from fhir_validator import FHIRValidator

    members = generate_cohort_members(BASE_SPEC, seed=42)
    ts = {
        m["synthetic_id"]: simulate_member_timeseries(
            m, duration_min=0.1, cadence_sec=10.0, seed=42, index=i
        )
        for i, m in enumerate(members)
    }
    bundle = assemble_cohort_bundle(members, ts)  # validate=True by default
    ok, errors = FHIRValidator().validate_bundle(bundle)
    assert ok, [getattr(e, "message", str(e)) for e in errors]


def test_export_reproducible_from_stored_state():
    members = generate_cohort_members(BASE_SPEC, seed=42)
    ts = {
        m["synthetic_id"]: simulate_member_timeseries(
            m, duration_min=0.1, cadence_sec=10.0, seed=42, index=i
        )
        for i, m in enumerate(members)
    }
    original = assemble_cohort_bundle(members, ts, seed=42)
    # Simulate a persisted row and re-export from stored members + seed.
    stub = SimpleNamespace(members=members, seed=42)
    reexported = export_cohort_bundle(stub, duration_min=0.1, cadence_sec=10.0)
    assert reexported == original  # FR-3.16.4 deterministic replay


# ---------------------------------------------------------------------------
# Wiring (needs JWT_SECRET)
# ---------------------------------------------------------------------------

@requires_app
def test_router_registered():
    from api.routes import digital_twin as dt_route

    paths = [r.path for r in dt_route.router.routes]
    assert "/cohort" in paths
    assert "/cohort/{cohort_id}" in paths
    assert "/cohorts" in paths


@requires_app
def test_app_includes_cohort_routes():
    from api.main import app

    paths = set(app.openapi()["paths"].keys())
    assert "/api/simulation/cohort" in paths
    assert "/api/simulation/cohorts" in paths
    assert "/api/simulation/cohort/{cohort_id}" in paths


# ---------------------------------------------------------------------------
# Persistence + API (DB-gated)
# ---------------------------------------------------------------------------

@requires_db
def test_generate_synthetic_cohort_persists():
    from database import SessionLocal
    from models import SyntheticCohort

    db = SessionLocal()
    try:
        row = generate_synthetic_cohort(
            db, spec=BASE_SPEC, duration_min=0.1, cadence_sec=10.0
        )
        db.commit()
        assert row.id is not None
        assert row.is_synthetic is True  # FR-3.13.5
        assert row.size == BASE_SPEC["size"]
        assert isinstance(row.members, list) and len(row.members) == BASE_SPEC["size"]
        fetched = db.query(SyntheticCohort).filter_by(id=row.id).first()
        assert fetched is not None
        assert fetched.is_synthetic is True
    finally:
        db.close()


@requires_db
def test_cohort_endpoint_roundtrip(authenticated_client):
    body = dict(BASE_SPEC)
    body["duration_min"] = 0.1
    body["cadence_sec"] = 10.0
    resp = authenticated_client.post("/api/simulation/cohort", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["cohort_uid"] is not None
    assert data["is_synthetic"] is True
    assert len(data["members"]) == BASE_SPEC["size"]
    assert data["export_bundle"]["type"] == "transaction"

    cid = data["cohort_id"]
    get_resp = authenticated_client.get(f"/api/simulation/cohort/{cid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["cohort_uid"] == data["cohort_uid"]


@requires_db
def test_cohort_requires_auth(unauthorized_client):
    resp = unauthorized_client.post("/api/simulation/cohort", json={"size": 2})
    assert resp.status_code in (401, 403)
