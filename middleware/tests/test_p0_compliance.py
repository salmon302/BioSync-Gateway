# SPDX-License-Identifier: MIT
"""
P0 Compliance/security certification tests.

P0-3 (FR-3.5.1 / FR-3.5.3 / FR-3.5.4): EMA wiring into telemetry pipeline.
P0-6 (FR-3.7.5): FHIR Bundle transaction persistence with rollback.

Unit tests (no DB) validate channel resolution, EMA application and alarm
evaluation. API tests (require a PostgreSQL test database via conftest) validate
durable persistence of raw+filtered observations and all-or-nothing Bundle
transactions.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from engine.signal import MultiChannelEMAFilter
from api.routes.telemetry import evaluate_alarm
from api.auth import create_access_token


# ---------------------------------------------------------------------------
# Unit tests (no database required)
# ---------------------------------------------------------------------------

def test_resolve_channel_from_loinc_code():
    obs = {"code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]}}
    assert MultiChannelEMAFilter.resolve_channel(obs) == "hr"


def test_resolve_channel_falls_back_to_text():
    obs = {"code": {"text": "flow"}}
    assert MultiChannelEMAFilter.resolve_channel(obs) == "flow"


def test_resolve_channel_unknown():
    obs = {"code": {"coding": [{"code": "9999-9"}]}}
    assert MultiChannelEMAFilter.resolve_channel(obs) == "unknown"


def test_ema_filter_applies_with_per_channel_alpha():
    f = MultiChannelEMAFilter()
    obs = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "8310-5"}]},
        "valueQuantity": {"value": 140.0, "unit": "mmHg"},
    }
    out = f.filter_observation(obs)
    assert out["filtered_data"]["value"] == 140.0
    assert out["filtered_data"]["alpha"] == 0.2  # pressure default

    # Second sample should be smoothed, not equal to raw
    obs2 = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "8310-5"}]},
        "valueQuantity": {"value": 200.0, "unit": "mmHg"},
    }
    out2 = f.filter_observation(obs2)
    assert out2["filtered_data"]["value"] < 200.0
    assert out2["filtered_data"]["value"] > 140.0


def test_evaluate_alarm_pressure_high():
    # 160 mmHg exceeds the 150 mmHg arthroscopic-pump limit (SRS §3.1.5)
    alarm = evaluate_alarm("pressure", 160.0)
    assert alarm is not None and alarm["active"] is True
    assert alarm["direction"] == "high"


def test_evaluate_alarm_no_false_positive():
    # 20 mmHg value for pressure would be absurd, but confirm low side is safe
    assert evaluate_alarm("pressure", 120.0)["active"] is False
    # spo2 within range
    assert evaluate_alarm("spo2", 98.0)["active"] is False


# ---------------------------------------------------------------------------
# API tests (require PostgreSQL test database, see conftest)
# ---------------------------------------------------------------------------

def _auth_headers(scopes):
    token = create_access_token(
        {"sub": "tester", "role": "user", "scopes": scopes}, expires_delta=1
    )
    return {"Authorization": f"Bearer {token}"}


def test_ingest_persists_raw_and_filtered_with_alarm(client):
    headers = _auth_headers(["telemetry_write"])
    payload = {
        "observations": [
            {
                "resourceType": "Observation",
                "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
                "valueQuantity": {"value": 160.0, "unit": "mmHg"},
            }
        ]
    }
    resp = client.post("/api/telemetry/ingest", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["persisted"] == 1
    assert body["alarms"][0]["channel"] == "pressure"

    # Verify durable persistence in the observations table
    from database import get_db
    from models import Observation

    db = next(get_db())
    try:
        row = db.query(Observation).filter_by(observation_code="8310-5").first()
        assert row is not None
        assert row.raw_data["value"] == 160.0
        assert row.filtered_data is not None
        assert "alarm" in row.fhir_resource
    finally:
        db.close()


def test_bundle_transaction_persists_and_rolls_back(client):
    headers = _auth_headers(["fhir_write"])

    valid_bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"code": "8867-4"}]},
                    "valueQuantity": {"value": 72.0, "unit": "beats/min"},
                },
                "request": {"method": "POST", "url": "Observation"},
            }
        ],
    }
    resp = client.post("/api/fhir/Bundle", json=valid_bundle, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "transaction-response"
    assert len(body["entry"]) == 1

    # Invalid entry inside a transaction must abort the whole bundle (no rows)
    bad_bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "valueQuantity": {"value": 1.0},  # missing code -> invalid
                },
                "request": {"method": "POST", "url": "Observation"},
            }
        ],
    }
    resp2 = client.post("/api/fhir/Bundle", json=bad_bundle, headers=headers)
    assert resp2.status_code == 400
    assert resp2.headers["content-type"].startswith("application/fhir+json")

    # No partial persistence: only the first valid bundle's rows exist
    from database import get_db
    from models import Observation

    db = next(get_db())
    try:
        count = db.query(Observation).count()
        assert count == 1
    finally:
        db.close()
