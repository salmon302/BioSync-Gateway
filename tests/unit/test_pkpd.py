# SPDX-License-Identifier: MIT
"""
PK/PD Lab Loop unit tests — SRS FR-3.11.1–FR-3.11.4.

Pure-math tests run without a database. Wiring/router checks run without a DB.
Persistence and API endpoint tests are gated on DATABASE_URL (skipped locally,
executed in CI against postgres:15 via the existing test fixtures).
"""
import math
import os

import pytest

from simulation.pkpd import (
    PkpdSubstance,
    simulate_clearance,
    derive_target_matrix,
    build_pkpd_worklist_steps,
)

DATABASE_URL = os.getenv("DATABASE_URL")
requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — requires a live PostgreSQL (CI provides it)",
)

# api.auth fails closed at import time when JWT_SECRET is unset (NFR-S7),
# so any test that imports the API app/router needs the secret configured.
requires_app = pytest.mark.skipif(
    not os.getenv("JWT_SECRET"),
    reason="JWT_SECRET not set — api.auth fails closed on import (set in CI)",
)


# ---------------------------------------------------------------------------
# Pure PK/PD math (no DB)
# ---------------------------------------------------------------------------

def _substance(**kw):
    base = dict(
        name="test-drug",
        volume_of_distribution=10.0,
        clearance=1.0,
        elimination_half_life=6.93,
        dose=100.0,
        dose_unit="mg",
    )
    base.update(kw)
    return PkpdSubstance(**base)


def test_elimination_rate_constant():
    s = _substance(clearance=1.0, volume_of_distribution=10.0)
    assert math.isclose(s.elimination_rate_constant, 0.1, rel_tol=1e-9)


def test_clearance_curve_half_life():
    s = _substance(elimination_half_life=6.93, dose=100.0, volume_of_distribution=10.0)
    # C0 = dose/Vd = 10 mg/L; k = 0.1 /h -> half-life ~6.93 h -> C ~= 5 mg/L.
    series = simulate_clearance(s, horizon_h=10, interval_h=0.01)
    c = series[int(round(6.93 / 0.01))]["concentration"]
    assert math.isclose(c, 5.0, rel_tol=1e-2)


def test_clearance_deterministic():
    s = _substance()
    a = simulate_clearance(s, horizon_h=24, interval_h=1.0)
    b = simulate_clearance(s, horizon_h=24, interval_h=1.0)
    assert a == b  # no RNG; reproducible (FR-3.16.4)


def test_derive_target_matrix_interpolates():
    s = _substance()
    series = simulate_clearance(s, horizon_h=10, interval_h=1.0)
    targets = derive_target_matrix(series, [2.5, 5.0])
    c2 = series[2]["concentration"]
    c3 = series[3]["concentration"]
    expected = c2 + (c3 - c2) * 0.5
    assert math.isclose(targets[0]["target_concentration"], expected, rel_tol=1e-9)
    assert targets[0]["unit"] == "mg/L"


def test_canonical_unit_molar_when_molar_mass():
    s = _substance(molar_mass=200.0)
    assert s.canonical_unit() == "µM"
    # C0 = 100 mg / 10 L = 10 mg/L -> µM = 10*1000/200 = 50 µM
    assert math.isclose(s.initial_concentration(), 50.0, rel_tol=1e-9)


def test_worklist_steps_simple_volume():
    s = _substance()  # C0 = 10 mg/L
    target_matrix = [{"time_h": 5.0, "target_concentration": 5.0, "unit": "mg/L"}]
    wl = build_pkpd_worklist_steps(
        s, target_matrix, initial_concentration=10.0, initial_unit="mg/L",
        target_total_volume_ul=100.0,
    )
    step = wl["steps"][0]
    # C1V1=C2V2 -> V1 = 5*100/10 = 50 µL; diluent 50 µL
    assert math.isclose(step["transfer_volume_ul"], 50.0, rel_tol=1e-6)
    assert math.isclose(step["diluent_volume_ul"], 50.0, rel_tol=1e-6)
    assert math.isclose(step["total_volume_ul"], 100.0, rel_tol=1e-6)
    assert step["warning"] is None
    assert wl["origin"] == "pk_pd_loop"


def test_worklist_below_limit_triggers_predilution():
    s = _substance()  # C0 = 10 mg/L
    # target 0.01 mg/L from 10 mg/L, 100 µL total -> V1 = 0.1 µL < 0.5 -> pre-dilution
    target_matrix = [{"time_h": 5.0, "target_concentration": 0.01, "unit": "mg/L"}]
    wl = build_pkpd_worklist_steps(
        s, target_matrix, initial_concentration=10.0, initial_unit="mg/L",
        target_total_volume_ul=100.0, min_volume_ul=0.5,
    )
    step = wl["steps"][0]
    assert step["warning"] is not None
    assert len(step["pre_dilution"]) >= 1
    assert any("pre-dilution" in (p.get("notes") or "") for p in step["pre_dilution"])


def test_worklist_target_ge_stock_flagged():
    s = _substance()  # C0 = 10 mg/L
    target_matrix = [{"time_h": 1.0, "target_concentration": 20.0, "unit": "mg/L"}]
    wl = build_pkpd_worklist_steps(
        s, target_matrix, initial_concentration=10.0, initial_unit="mg/L",
    )
    step = wl["steps"][0]
    assert step["warning"] is not None
    assert "target >= stock" in step["warning"]


# ---------------------------------------------------------------------------
# Wiring (no DB)
# ---------------------------------------------------------------------------

@requires_app
def test_router_registered():
    from api.routes import pkpd as pkpd_route

    paths = [r.path for r in pkpd_route.router.routes]
    assert "/pkpd/worklist" in paths
    assert "/pkpd/worklist/{worklist_id}" in paths
    assert "/pkpd/worklists" in paths


@requires_app
def test_app_includes_pkpd_routes():
    from api.main import app

    # openapi() is the authoritative source of registered paths (includes the
    # router prefix); app.routes only exposes sub-route .path without prefix.
    paths = set(app.openapi()["paths"].keys())
    assert "/api/simulation/pkpd/worklist" in paths
    assert "/api/simulation/pkpd/worklists" in paths
    assert "/api/simulation/pkpd/worklist/{worklist_id}" in paths


# ---------------------------------------------------------------------------
# Persistence + API (DB-gated)
# ---------------------------------------------------------------------------

@requires_db
def test_generate_pkpd_worklist_persists():
    from database import SessionLocal
    from models import PkpdWorklist

    s = PkpdSubstance(
        name="db-drug", volume_of_distribution=10.0, clearance=1.0,
        elimination_half_life=6.93, dose=100.0,
    )
    db = SessionLocal()
    try:
        row = generate_pkpd_worklist(
            db, s, initial_concentration=10.0, initial_unit="mg/L",
            plate_format="96-well", horizon_h=12, interval_h=1.0,
        )
        db.commit()
        assert row.id is not None
        assert row.origin == "pk_pd_loop"
        assert row.steps["well_count"] == 96
        fetched = db.query(PkpdWorklist).filter_by(id=row.id).first()
        assert fetched is not None
        assert fetched.substance_name == "db-drug"
        assert fetched.plate_id is None
        assert fetched.steps["origin"] == "pk_pd_loop"
    finally:
        db.close()


@requires_db
def test_pkpd_worklist_endpoint_roundtrip(authenticated_client):
    body = {
        "substance": {
            "name": "endpoint-drug",
            "volume_of_distribution": 10.0,
            "clearance": 1.0,
            "elimination_half_life": 6.93,
            "dose": 100.0,
        },
        "initial_concentration": 10.0,
        "initial_unit": "mg/L",
        "plate_format": "96-well",
        "horizon_h": 12,
        "interval_h": 1.0,
    }
    resp = authenticated_client.post("/api/simulation/pkpd/worklist", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["origin"] == "pk_pd_loop"
    assert data["well_count"] == 96
    wid = data["worklist_id"]

    get_resp = authenticated_client.get(f"/api/simulation/pkpd/worklist/{wid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["worklist_uid"] == data["worklist_uid"]


@requires_db
def test_pkpd_worklist_requires_auth(unauthorized_client):
    resp = unauthorized_client.post("/api/simulation/pkpd/worklist", json={})
    assert resp.status_code in (401, 403)
