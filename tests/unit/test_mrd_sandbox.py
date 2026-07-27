# SPDX-License-Identifier: MIT
"""
MRD / cfDNA Sandbox unit tests — SRS FR-3.14.1–FR-3.14.4 (OQ-20).

Pure tests (determinism, transfer function, LOD pass/fail, FHIR validation,
mocked LIMS round-trip) run without a database. Wiring/router checks run
without a DB. Persistence and API endpoint tests are gated on DATABASE_URL
(skipped locally, executed in CI against postgres:15). JWT-gated wiring checks
follow the same JWT_SECRET gating used by the other advanced-analytics tests.
"""
import json
import os
from unittest.mock import patch, MagicMock

import pytest

from simulation.mrd_sandbox import (
    DEFAULT_BASELINE_PHYSIOLOGY,
    STRESSOR_PRESETS,
    apply_stressor,
    cfdna_shedding,
    evaluate_lod,
    build_cfdna_observation,
    verify_lims_webhook,
    run_mrd_sandbox,
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
# FR-3.14.1 — Stressor injection (deterministic)
# ---------------------------------------------------------------------------

def test_apply_stressor_baseline_unchanged():
    out = apply_stressor(DEFAULT_BASELINE_PHYSIOLOGY, {"type": "baseline"})
    assert out == DEFAULT_BASELINE_PHYSIOLOGY
    out2 = apply_stressor(DEFAULT_BASELINE_PHYSIOLOGY, {"type": "respiratory_distress", "severity": 0})
    assert out2 == DEFAULT_BASELINE_PHYSIOLOGY


def test_apply_stressor_respiratory_distress_lowers_volume_and_spo2():
    out = apply_stressor(
        DEFAULT_BASELINE_PHYSIOLOGY, {"type": "respiratory_distress", "severity": 1.0}
    )
    # capillary leak reduces effective plasma volume
    assert out["plasma_volume_ml"] < DEFAULT_BASELINE_PHYSIOLOGY["plasma_volume_ml"]
    # hypoxemia
    assert out["spo2"] < DEFAULT_BASELINE_PHYSIOLOGY["spo2"]
    # compensatory tachycardia + mild hypotension
    assert out["heart_rate"] > DEFAULT_BASELINE_PHYSIOLOGY["heart_rate"]
    # MAP recomputed consistently
    assert out["mean_arterial_pressure"] == pytest.approx(
        out["diastolic_bp"] + (out["systolic_bp"] - out["diastolic_bp"]) / 3.0
    )


def test_apply_stressor_fluid_clearance_lowers_volume():
    out = apply_stressor(
        DEFAULT_BASELINE_PHYSIOLOGY,
        {"type": "fluid_clearance_perturbation", "severity": 1.0},
    )
    assert out["plasma_volume_ml"] < DEFAULT_BASELINE_PHYSIOLOGY["plasma_volume_ml"]


def test_apply_stressor_deterministic():
    a = apply_stressor(
        DEFAULT_BASELINE_PHYSIOLOGY, {"type": "respiratory_distress", "severity": 0.7}
    )
    b = apply_stressor(
        DEFAULT_BASELINE_PHYSIOLOGY, {"type": "respiratory_distress", "severity": 0.7}
    )
    assert a == b


def test_apply_stressor_custom_overrides():
    out = apply_stressor(
        DEFAULT_BASELINE_PHYSIOLOGY,
        {"type": "custom", "overrides": {"plasma_volume_ml": 2500.0, "spo2": 90.0}},
    )
    assert out["plasma_volume_ml"] == 2500.0
    assert out["spo2"] == 90.0


def test_apply_stressor_unknown_type_raises():
    with pytest.raises(ValueError):
        apply_stressor(DEFAULT_BASELINE_PHYSIOLOGY, {"type": "nope"})


# ---------------------------------------------------------------------------
# FR-3.14.2 — cfDNA shedding transfer function
# ---------------------------------------------------------------------------

def test_shedding_deterministic_with_seed():
    a = cfdna_shedding(
        2550.0, {"spo2": 78.0, "mean_arterial_pressure": 86.0, "heart_rate": 102.0},
        seed=42, n_samples=20, volatility=0.1,
    )
    b = cfdna_shedding(
        2550.0, {"spo2": 78.0, "mean_arterial_pressure": 86.0, "heart_rate": 102.0},
        seed=42, n_samples=20, volatility=0.1,
    )
    assert a["samples"] == b["samples"]  # reproducible (FR-3.16.4)
    assert a["mean_copies_per_ml"] == b["mean_copies_per_ml"]


def test_shedding_stress_raises_concentration():
    calm = cfdna_shedding(
        DEFAULT_BASELINE_PHYSIOLOGY["plasma_volume_ml"], DEFAULT_BASELINE_PHYSIOLOGY,
        seed=1,
    )
    stressed = cfdna_shedding(
        2550.0, {"spo2": 78.0, "mean_arterial_pressure": 86.0, "heart_rate": 102.0},
        seed=1,
    )
    # stress index > 0 and concentration higher than the quiescent baseline
    assert stressed["stress_index"] > calm["stress_index"]
    assert stressed["mean_copies_per_ml"] > calm["mean_copies_per_ml"]


def test_shedding_respects_inverse_volume():
    # same physiology, smaller plasma volume -> higher concentration
    hi_vol = cfdna_shedding(3500.0, DEFAULT_BASELINE_PHYSIOLOGY, seed=1)
    lo_vol = cfdna_shedding(2500.0, DEFAULT_BASELINE_PHYSIOLOGY, seed=1)
    assert lo_vol["mean_copies_per_ml"] > hi_vol["mean_copies_per_ml"]


def test_shedding_volatility_increases_spread():
    flat = cfdna_shedding(3000.0, DEFAULT_BASELINE_PHYSIOLOGY, seed=7, n_samples=200, volatility=0.0)
    jitter = cfdna_shedding(3000.0, DEFAULT_BASELINE_PHYSIOLOGY, seed=7, n_samples=200, volatility=0.3)
    flat_spread = max(flat["samples"]) - min(flat["samples"])
    jitter_spread = max(jitter["samples"]) - min(jitter["samples"])
    assert jitter_spread > flat_spread


# ---------------------------------------------------------------------------
# FR-3.14.3 — LOD boundary simulation
# ---------------------------------------------------------------------------

def test_lod_pending_without_threshold():
    lod = evaluate_lod([5.0, 6.0, 4.0], None)
    assert lod["detection_result"] == "pending"
    assert lod["configured"] is False


def test_lod_pass_when_mean_clears_threshold():
    lod = evaluate_lod([9.0, 11.0, 10.0], 5.0)
    assert lod["detection_result"] == "pass"
    assert lod["detection_rate"] == 1.0
    assert lod["mean_concentration"] == pytest.approx(10.0)


def test_lod_fail_when_mean_below_threshold():
    # Healthy baseline ~1 copy/mL; below a 5 copies/mL LOD -> fail (FR-3.14.3)
    lod = evaluate_lod([1.0, 1.2, 0.9], 5.0)
    assert lod["detection_result"] == "fail"
    assert lod["detection_rate"] == 0.0


def test_lod_full_run_stressor_flips_to_pass():
    # End-to-end: no stressor stays below LOD; respiratory distress clears it.
    calm = run_mrd_sandbox({"type": "baseline"}, lod_threshold=5.0)
    stressed = run_mrd_sandbox(
        {"type": "respiratory_distress", "severity": 1.0}, lod_threshold=5.0
    )
    assert calm["detection_result"] == "fail"
    assert stressed["detection_result"] == "pass"


# ---------------------------------------------------------------------------
# FR-3.14.4 — FHIR Observation + LIMS webhook round-trip
# ---------------------------------------------------------------------------

def test_build_observation_structure():
    obs = build_cfdna_observation(9.7, patient_id="syn-1", lod_result={"detection_result": "pass", "lod_threshold": 5.0})
    assert obs["resourceType"] == "Observation"
    assert obs["valueQuantity"]["value"] == 9.7
    assert obs["valueQuantity"]["code"] == "{copies}/mL"
    assert obs["subject"]["reference"] == "Patient/syn-1"
    assert obs["note"][0]["text"]  # lod info carried


def test_observation_fhir_valid():
    from fhir_validator import FHIRValidator

    obs = build_cfdna_observation(9.7, patient_id="syn-1")
    ok, errors = FHIRValidator().validate_observation(obs)
    assert ok, [getattr(e, "message", str(e)) for e in errors]


def test_verify_lims_webhook_roundtrip_verified():
    sent = build_cfdna_observation(10.0, patient_id="syn-1")
    fake = MagicMock()
    fake.is_success = True
    fake.status_code = 200
    fake.json.return_value = sent  # LIMS echoes the observation back
    with patch("simulation.mrd_sandbox.httpx.post", return_value=fake) as mock_post:
        res = verify_lims_webhook(sent, "https://lims.example/ingest", round_trip_tolerance=0.05)
    mock_post.assert_called_once()
    assert res["ok"] is True
    assert res["round_trip"]["verified"] is True
    assert res["round_trip"]["abs_error"] == pytest.approx(0.0)


def test_verify_lims_webhook_roundtrip_from_bundle():
    sent = build_cfdna_observation(8.0, patient_id="syn-1")
    echoed = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{"resource": sent}],
    }
    fake = MagicMock()
    fake.is_success = True
    fake.status_code = 200
    fake.json.return_value = echoed
    with patch("simulation.mrd_sandbox.httpx.post", return_value=fake):
        res = verify_lims_webhook(sent, "https://lims.example/ingest")
    assert res["round_trip"]["received_value"] == pytest.approx(8.0)
    assert res["round_trip"]["verified"] is True


def test_verify_lims_webhook_roundtrip_mismatch_flagged():
    sent = build_cfdna_observation(10.0, patient_id="syn-1")
    echoed = build_cfdna_observation(12.0, patient_id="syn-1")  # 20% off
    fake = MagicMock()
    fake.is_success = True
    fake.status_code = 200
    fake.json.return_value = echoed
    with patch("simulation.mrd_sandbox.httpx.post", return_value=fake):
        res = verify_lims_webhook(sent, "https://lims.example/ingest", round_trip_tolerance=0.05)
    assert res["round_trip"]["verified"] is False
    assert res["round_trip"]["rel_error"] == pytest.approx(0.2, abs=1e-6)


def test_verify_lims_webhook_transport_error():
    import httpx

    sent = build_cfdna_observation(10.0, patient_id="syn-1")
    with patch("simulation.mrd_sandbox.httpx.post", side_effect=httpx.ConnectError("boom")):
        res = verify_lims_webhook(sent, "https://lims.example/ingest")
    assert res["ok"] is False
    assert "error" in res


def test_run_mrd_sandbox_captures_lims_response():
    sent = build_cfdna_observation(10.0, patient_id="syn-1")
    fake = MagicMock()
    fake.is_success = True
    fake.status_code = 200
    fake.json.return_value = sent
    with patch("simulation.mrd_sandbox.httpx.post", return_value=fake):
        result = run_mrd_sandbox(
            {"type": "respiratory_distress", "severity": 1.0},
            lod_threshold=5.0,
            lims_webhook_url="https://lims.example/ingest",
            seed=123,
        )
    assert result["lims_response"]["ok"] is True
    assert result["detection_result"] == "pass"
    assert result["lims_response"]["round_trip"]["verified"] is True


def test_run_mrd_sandbox_no_lims_when_url_absent():
    result = run_mrd_sandbox({"type": "baseline"}, lod_threshold=5.0, seed=1)
    assert result["lims_response"] is None
    assert result["detection_result"] == "fail"


# ---------------------------------------------------------------------------
# Wiring (needs JWT_SECRET)
# ---------------------------------------------------------------------------

@requires_app
def test_router_registered():
    from api.routes import mrd as mrd_route

    paths = [r.path for r in mrd_route.router.routes]
    assert "/mrd/run" in paths
    assert "/mrd/run/{run_id}" in paths
    assert "/mrd/runs" in paths


@requires_app
def test_app_includes_mrd_routes():
    from api.main import app

    paths = set(app.openapi()["paths"].keys())
    assert "/api/simulation/mrd/run" in paths
    assert "/api/simulation/mrd/runs" in paths
    assert "/api/simulation/mrd/run/{run_id}" in paths


# ---------------------------------------------------------------------------
# Persistence + API (DB-gated)
# ---------------------------------------------------------------------------

@requires_db
def test_generate_cfdna_sandbox_run_persists():
    from database import SessionLocal
    from models import CfdnaSandboxRun

    db = SessionLocal()
    try:
        result = run_mrd_sandbox(
            {"type": "respiratory_distress", "severity": 1.0},
            lod_threshold=5.0,
            seed=99,
            patient_id="syn-1",
        )
        row = generate_cfdna_sandbox_run(
            db, result=result, stressor={"type": "respiratory_distress", "severity": 1.0},
            lod_threshold=5.0, seed=99, scenario_run_id=None,
        )
        db.commit()
        assert row.id is not None
        assert row.run_uid is not None
        assert row.detection_result == "pass"
        fetched = db.query(CfdnaSandboxRun).filter_by(id=row.id).first()
        assert fetched is not None
        assert fetched.cfdna_concentration["mean_copies_per_ml"] > 0
        assert fetched.plasma_volume["altered_ml"] < fetched.plasma_volume["baseline_ml"]
    finally:
        db.close()


@requires_db
def test_mrd_run_endpoint_roundtrip(authenticated_client):
    body = {
        "stressor": {"type": "respiratory_distress", "severity": 1.0},
        "lod_threshold": 5.0,
        "seed": 99,
        "patient_id": "syn-1",
    }
    resp = authenticated_client.post("/api/simulation/mrd/run", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["run_uid"] is not None
    assert data["detection_result"] == "pass"
    assert data["cfdna_concentration"]["mean_copies_per_ml"] > 0
    rid = data["run_id"]

    get_resp = authenticated_client.get(f"/api/simulation/mrd/run/{rid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["run_uid"] == data["run_uid"]


@requires_db
def test_mrd_run_requires_auth(unauthorized_client):
    resp = unauthorized_client.post("/api/simulation/mrd/run", json={})
    assert resp.status_code in (401, 403)
