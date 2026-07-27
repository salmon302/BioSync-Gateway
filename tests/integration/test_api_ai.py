# SPDX-License-Identifier: MIT
"""
Integration tests for the AI / LLM-RAG routes (SRS FR-3.15).

Covers FR-3.15.4 (Pulse -> narrative), FR-3.15.5 (ClinVar -> pathology report),
FR-3.15.6 (provenance persistence + retrieval), FR-3.15.7 (EHR ingestion
harness), and auth scope enforcement.

Requires a PostgreSQL database (the same one the rest of the integration
suite uses). The module is skipped automatically when no DB is reachable.
"""

import os
import time

import pytest
from sqlalchemy import create_engine, text


def _db_available() -> bool:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://biosync_user:biosync_secure_password@localhost:5432/biosync",
    )
    try:
        eng = create_engine(url, pool_pre_ping=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="requires PostgreSQL database")


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    """Deterministic, offline generation for route tests (C8)."""
    import ai.llm_gateway as gw

    monkeypatch.setattr(gw, "PROVIDER", "mock")
    monkeypatch.setattr(gw, "OPENROUTER_API_KEY", None)


def _wait_for_run(client, run_uid, token, timeout=5.0):
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/ai/runs/{run_uid}", headers=headers)
        if r.status_code == 200:
            body = r.json()
            if body["status"] in ("completed", "failed"):
                return body
        time.sleep(0.1)
    return None


def test_provider_config_endpoint(authenticated_client):
    r = authenticated_client.get("/api/ai/config")
    assert r.status_code == 200
    assert r.json()["provider"] == "mock"


def test_templates_listed(authenticated_client):
    r = authenticated_client.get("/api/ai/templates")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 2
    types = {t["template_type"] for t in data["templates"]}
    assert "cap_clia" in types
    assert "ehr_rubric" in types


def test_clinvar_pathology_report_e2e(authenticated_client, sample_jwt_token):
    body = {
        "variants": [
            {
                "gene": "BRCA1",
                "variantName": "BRCA1 c.68_69delAG",
                "clinicalSignificance": "Pathogenic",
            }
        ],
        "max_tokens": 256,
    }
    r = authenticated_client.post("/api/ai/clinvar/pathology-report", json=body)
    assert r.status_code == 202, r.text
    run_uid = r.json()["run_uid"]

    result = _wait_for_run(authenticated_client, run_uid, sample_jwt_token)
    assert result is not None, "run did not complete in time"
    assert result["status"] == "completed", result
    assert result["text_type"] == "pathology_report"
    assert result["content"] and "BRCA1" in result["content"]
    prov = result["provenance"]
    assert prov["provider"] == "mock"
    assert prov["prompt_hash"]
    assert prov["model_id"] == "mock-model"


def test_pulse_narrative_e2e(authenticated_client, sample_jwt_token):
    body = {
        "telemetry": [
            {"HR": 80, "SpO2": 98, "MAP": 92},
            {"HR": 82, "SpO2": 97, "MAP": 90},
        ],
        "window_seconds": 60,
        "max_tokens": 256,
    }
    r = authenticated_client.post("/api/ai/pulse/narrative", json=body)
    assert r.status_code == 202, r.text
    run_uid = r.json()["run_uid"]

    result = _wait_for_run(authenticated_client, run_uid, sample_jwt_token)
    assert result is not None
    assert result["status"] == "completed"
    assert result["text_type"] == "progress_note"
    assert "[SIMULATED LLM OUTPUT" in result["content"]


def test_ehr_ingest_harness(authenticated_client):
    body = {
        "text": "SIMULATED progress note: HR 80, SpO2 98%, MAP 92. Stable.",
        "expected_signals": ["HR 80", "SpO2 98"],
    }
    r = authenticated_client.post("/api/ai/ehr/ingest", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["passed"] is True
    assert set(data["preserved_signals"]) >= {"HR 80", "SpO2 98"}


def test_ai_routes_require_auth(unauthorized_client, tech_jwt_token):
    # No token -> 401
    r = unauthorized_client.post(
        "/api/ai/clinvar/pathology-report", json={"variants": []}
    )
    assert r.status_code == 401

    # Token without ai_write scope -> 403
    unauthorized_client.headers.update({"Authorization": f"Bearer {tech_jwt_token}"})
    r = unauthorized_client.post(
        "/api/ai/clinvar/pathology-report", json={"variants": []}
    )
    assert r.status_code == 403
