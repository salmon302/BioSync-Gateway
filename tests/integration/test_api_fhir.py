"""
FHIR API Tests
Implements SRS FR-3.7.1–3.7.5 — FHIR Interoperability

Tests:
- Observation CRUD with validation
- DeviceMetric CRUD with validation
- Bundle (transaction/batch) processing
- Scope enforcement
"""

import pytest


class TestObservationCRUD:
    """Tests for FHIR Observation endpoints."""

    def test_create_observation_requires_auth(self, unauthorized_client):
        """Observation creation should require authentication."""
        response = unauthorized_client.post(
            "/api/fhir/Observation",
            json={"resourceType": "Observation"}
        )
        assert response.status_code == 401

    def test_create_observation_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Observation creation should require fhir_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post(
            "/api/fhir/Observation",
            json={"resourceType": "Observation"}
        )
        assert response.status_code == 403

    def test_create_valid_observation_accepted(self, authenticated_client, valid_observation):
        """Valid Observation should be accepted."""
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json=valid_observation
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "created"

    def test_create_minimal_observation_accepted(self, authenticated_client, minimal_observation):
        """Minimal valid Observation should be accepted."""
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json=minimal_observation
        )
        assert response.status_code == 200

    def test_create_observation_missing_value_rejected(self, authenticated_client, observation_missing_value):
        """Observation without valueQuantity should be rejected with 400."""
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json=observation_missing_value
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_create_observation_missing_code_rejected(self, authenticated_client, observation_missing_code):
        """Observation without code should be rejected with 400."""
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json=observation_missing_code
        )
        assert response.status_code == 400

    def test_get_observation_returns_resource(self, authenticated_client):
        """Observation retrieval should return the resource."""
        response = authenticated_client.get("/api/fhir/Observation/test-obs-001")
        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Observation"
        assert data["id"] == "test-obs-001"


class TestDeviceMetricCRUD:
    """Tests for FHIR DeviceMetric endpoints."""

    def test_create_device_metric_requires_auth(self, unauthorized_client):
        """DeviceMetric creation should require authentication."""
        response = unauthorized_client.post(
            "/api/fhir/DeviceMetric",
            json={"resourceType": "DeviceMetric"}
        )
        assert response.status_code == 401

    def test_create_device_metric_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """DeviceMetric creation should require fhir_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post(
            "/api/fhir/DeviceMetric",
            json={"resourceType": "DeviceMetric"}
        )
        assert response.status_code == 403

    def test_create_valid_device_metric_accepted(self, authenticated_client, valid_device_metric):
        """Valid DeviceMetric should be accepted."""
        response = authenticated_client.post(
            "/api/fhir/DeviceMetric",
            json=valid_device_metric
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "created"

    def test_create_device_metric_missing_status_rejected(self, authenticated_client, device_metric_missing_status):
        """DeviceMetric without operationalStatus should be rejected."""
        response = authenticated_client.post(
            "/api/fhir/DeviceMetric",
            json=device_metric_missing_status
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


class TestBundleProcessing:
    """Tests for FHIR Bundle (transaction/batch) endpoints."""

    def test_process_bundle_requires_auth(self, unauthorized_client):
        """Bundle processing should require authentication."""
        response = unauthorized_client.post(
            "/api/fhir/Bundle",
            json={"resourceType": "Bundle"}
        )
        assert response.status_code == 401

    def test_process_bundle_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Bundle processing should require fhir_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post(
            "/api/fhir/Bundle",
            json={"resourceType": "Bundle"}
        )
        assert response.status_code == 403

    def test_process_valid_transaction_bundle(self, authenticated_client, valid_fhir_bundle):
        """Valid transaction Bundle should be accepted."""
        response = authenticated_client.post(
            "/api/fhir/Bundle",
            json=valid_fhir_bundle
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "processed"

    def test_process_bundle_with_invalid_entry(self, authenticated_client):
        """Bundle with invalid entry should be rejected."""
        invalid_bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Observation"},
                    "resource": {
                        "resourceType": "Observation",
                        # Missing required code and valueQuantity
                    }
                }
            ]
        }
        response = authenticated_client.post(
            "/api/fhir/Bundle",
            json=invalid_bundle
        )
        # Should return 400 due to invalid Observation in bundle
        assert response.status_code == 400

    def test_process_batch_bundle(self, authenticated_client):
        """Batch Bundle should be accepted."""
        batch_bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "request": {"method": "GET", "url": "Observation/1"}
                },
                {
                    "request": {"method": "GET", "url": "Observation/2"}
                }
            ]
        }
        response = authenticated_client.post(
            "/api/fhir/Bundle",
            json=batch_bundle
        )
        assert response.status_code == 200


class TestFHIRValidationErrors:
    """Tests for FHIR validation error responses."""

    def test_validation_error_returns_operation_outcome(self, authenticated_client):
        """Validation failure should return OperationOutcome detail."""
        invalid_obs = {
            "resourceType": "Observation",
            "status": "final",
            # Missing both code and valueQuantity
        }
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json=invalid_obs
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_validation_error_has_issue_details(self, authenticated_client):
        """Validation error should include issue details."""
        invalid_obs = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"text": "test"}
            # Missing valueQuantity
        }
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json=invalid_obs
        )
        data = response.json()
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            assert "issue" in detail or "issues" in detail or "location" in detail
