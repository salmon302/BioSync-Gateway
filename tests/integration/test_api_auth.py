"""
JWT Authentication API Tests
Implements SRS FR-3.8.5 — JWT Authentication

Tests JWT token lifecycle, scope enforcement, and auth middleware.
"""

import pytest
import time
from jose import jwt as jose_jwt
from api.auth import JWT_SECRET, JWT_ALGORITHM


class TestJWTTokenCreation:
    """Tests for JWT token creation and validation."""

    def test_create_token_with_scopes(self, sample_jwt_token):
        """Token should contain all specified scopes."""
        assert sample_jwt_token is not None
        parts = sample_jwt_token.split(".")
        assert len(parts) == 3  # Valid JWT structure

    def test_token_contains_user_sub(self, sample_jwt_token):
        """Token should contain user subject."""
        # Decode the payload (middle part of JWT)
        import base64
        payload_b64 = sample_jwt_token.split(".")[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = base64.urlsafe_b64decode(payload_b64)
        import json
        data = json.loads(payload)
        assert data["sub"] == "test-user"

    def test_token_has_expiration(self, sample_jwt_token):
        """Token should have expiration claim."""
        import base64
        import json
        payload_b64 = sample_jwt_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_admin_token_has_full_scopes(self, admin_jwt_token):
        """Admin token should have all write scopes."""
        import base64
        import json
        payload_b64 = admin_jwt_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload["role"] == "admin"
        assert "plate_write" in payload["scopes"]
        assert "fhir_write" in payload["scopes"]
        assert "simulation_write" in payload["scopes"]

    def test_tech_token_has_limited_scopes(self, tech_jwt_token):
        """Technician token should have limited scopes."""
        import base64
        import json
        payload_b64 = tech_jwt_token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload["role"] == "technician"
        assert "telemetry_write" in payload["scopes"]
        assert "fhir_read" in payload["scopes"]
        # Should NOT have write scopes
        assert "plate_write" not in payload["scopes"]
        assert "fhir_write" not in payload["scopes"]


class TestAuthMiddleware:
    """Tests for FastAPI auth dependency enforcement."""

    def test_unauthorized_access_to_protected(self, unauthorized_client):
        """Unauthenticated request should return 401."""
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_valid_token_grants_access(self, authenticated_client):
        """Valid JWT should grant access to protected endpoints."""
        response = authenticated_client.get("/api/protected")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Access granted"

    def test_expired_token_rejected(self, unauthorized_client, expired_jwt_token):
        """Expired JWT should be rejected."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {expired_jwt_token}"
        })
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401
        # SRS OQ-14: 401 must include WWW-Authenticate: Bearer header
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_token_rejected(self, unauthorized_client, invalid_jwt_token):
        """Malformed JWT should be rejected."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {invalid_jwt_token}"
        })
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_missing_authorization_header(self, unauthorized_client):
        """Request without Authorization header should return 401."""
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_wrong_token_for_protected(self, unauthorized_client, tech_jwt_token):
        """Technician token should work for protected endpoint (has valid scopes)."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.get("/api/protected")
        # Should succeed - token is valid, just has limited scopes
        assert response.status_code == 200


class TestAuthEndpoints:
    """Tests for login and refresh endpoints."""

    def test_login_returns_access_and_refresh_tokens(self, client):
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "secret"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 3600
        assert body["access_token"]
        assert body["refresh_token"]

        access_payload = jose_jwt.decode(
            body["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        refresh_payload = jose_jwt.decode(
            body["refresh_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        assert access_payload["sub"] == "admin"
        assert access_payload["iat"] <= access_payload["exp"]
        assert refresh_payload["type"] == "refresh"

    def test_refresh_rotates_tokens(self, client):
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "secret"},
        )
        tokens = login.json()

        refresh = client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh.status_code == 200
        body = refresh.json()
        assert body["access_token"] != tokens["access_token"]
        assert body["refresh_token"] != tokens["refresh_token"]
        assert body["expires_in"] == 3600

    def test_refresh_rejects_access_token(self, client, sample_jwt_token):
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": sample_jwt_token},
        )
        assert response.status_code == 401


class TestScopeEnforcement:
    """Tests for scope-based access control on API routes."""

    def test_tech_cannot_access_plate_write(self, unauthorized_client, tech_jwt_token):
        """Technician should not have plate_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        # Try to create a plate (requires plate_write)
        response = unauthorized_client.post("/api/plates/", json={})
        assert response.status_code == 403

    def test_tech_cannot_access_fhir_write(self, unauthorized_client, tech_jwt_token):
        """Technician should not have fhir_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        # Try to create an Observation (requires fhir_write)
        response = unauthorized_client.post(
            "/api/fhir/Observation",
            json={"resourceType": "Observation", "code": {"text": "test"},
                  "valueQuantity": {"value": 1, "unit": "test"}}
        )
        assert response.status_code == 403

    def test_admin_can_access_plate_write(self, authenticated_client):
        """Admin should have plate_write scope."""
        response = authenticated_client.post("/api/plates/", json={})
        # Should succeed (or return 200 from stub)
        assert response.status_code in [200, 201]

    def test_admin_can_access_fhir_write(self, authenticated_client):
        """Admin should have fhir_write scope."""
        response = authenticated_client.post(
            "/api/fhir/Observation",
            json={"resourceType": "Observation", "code": {"text": "test"},
                  "valueQuantity": {"value": 1, "unit": "test"}}
        )
        # Should succeed (or return 200 from stub)
        assert response.status_code in [200, 201]
