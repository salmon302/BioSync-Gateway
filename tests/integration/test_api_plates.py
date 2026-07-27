# SPDX-License-Identifier: MIT
"""
Integration tests for plate/well persistence and the FR-3.2.3 well->Observation
link. DB-gated: skipped automatically when DATABASE_URL is not configured
(use the CI postgres:15 service to exercise it).
"""
import os

import pytest

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — requires a live PostgreSQL (CI provides it)",
)


def _make_observation(client):
    obs = {
        "resourceType": "Observation",
        "code": {"text": "Heart rate"},
        "valueQuantity": {"value": 72, "unit": "/min"},
    }
    resp = client.post("/api/fhir/Observation", json=obs)
    assert resp.status_code == 201, resp.text
    return resp.json().get("id")


def test_create_and_get_plate_links_observation(authenticated_client):
    uid = _make_observation(authenticated_client)
    payload = {
        "plate_name": "Test Plate",
        "plate_type": "96-well",
        "wells": [
            {"row": 0, "col": 0, "sample_id": "S1", "status": "processed",
             "observation_uid": uid},
            {"row": 1, "col": 1, "sample_id": "S2", "status": "pending"},
        ],
    }
    r = authenticated_client.post("/api/plates/", json=payload)
    assert r.status_code == 200, r.text
    plate_id = r.json()["plate_id"]

    g = authenticated_client.get(f"/api/plates/{plate_id}")
    assert g.status_code == 200
    data = g.json()
    assert data["plate_type"] == "96-well"
    wells = {(w["row"], w["col"]): w for w in data["wells"]}
    assert wells[(0, 0)]["observationUid"] == uid
    assert wells[(1, 1)]["observationUid"] is None


def test_well_observation_endpoint(authenticated_client):
    uid = _make_observation(authenticated_client)
    payload = {
        "plate_name": "Test Plate 2",
        "plate_type": "96-well",
        "wells": [{"row": 0, "col": 0, "observation_uid": uid}],
    }
    plate_id = authenticated_client.post("/api/plates/", json=payload).json()["plate_id"]
    well_id = authenticated_client.get(f"/api/plates/{plate_id}").json()["wells"][0]["id"]

    resp = authenticated_client.get(f"/api/plates/{plate_id}/wells/{well_id}/observation")
    assert resp.status_code == 200, resp.text
    assert resp.json().get("resourceType") == "Observation"
    assert resp.json().get("valueQuantity", {}).get("value") == 72


def test_get_missing_plate_404(authenticated_client):
    resp = authenticated_client.get("/api/plates/999999")
    assert resp.status_code == 404
