"""
Protected Endpoint Tests
Implements SRS FR-3.8.5 — JWT Authentication

Tests:
- Protected endpoints require valid JWT
- Token validation and scope enforcement
- Error responses for invalid credentials
"""

import pytest


class TestProtectedEndpoint:
    """Tests for generic protected endpoint."""

    def test_protected_endpoint_requires_scope(self, unauthorized_client):
        """Protected endpoint should require valid credentials."""
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_protected_endpoint_returns_user_info(self, authenticated_client):
        """Protected endpoint should return authenticated user info."""
        response = authenticated_client.get("/api/protected")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Access granted"
        assert "user" in data
        assert "role" in data
        assert "scopes" in data

    def test_protected_endpoint_returns_correct_username(self, authenticated_client):
        """Protected endpoint should return correct username from token."""
        response = authenticated_client.get("/api/protected")
        data = response.json()
        assert data["user"] == "test-user"

    def test_protected_endpoint_returns_correct_role(self, authenticated_client):
        """Protected endpoint should return correct role from token."""
        response = authenticated_client.get("/api/protected")
        data = response.json()
        assert data["role"] == "admin"

    def test_protected_endpoint_returns_scopes(self, authenticated_client):
        """Protected endpoint should return scopes from token."""
        response = authenticated_client.get("/api/protected")
        data = response.json()
        assert isinstance(data["scopes"], list)
        assert len(data["scopes"]) > 0

    def test_tech_user_sees_limited_scopes(self, unauthorized_client, tech_jwt_token):
        """Technician should see only their assigned scopes."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "tech-user"
        assert data["role"] == "technician"
        assert "telemetry_write" in data["scopes"]
        assert "fhir_read" in data["scopes"]
        assert "plate_write" not in data["scopes"]

    def test_expired_token_returns_401(self, unauthorized_client, expired_jwt_token):
        """Expired token should return 401 Unauthorized."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {expired_jwt_token}"
        })
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, unauthorized_client, invalid_jwt_token):
        """Malformed token should return 401 Unauthorized."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {invalid_jwt_token}"
        })
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_missing_authorization_returns_401(self, unauthorized_client):
        """Request without Authorization header should return 401."""
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_empty_token_returns_401(self, unauthorized_client):
        """Empty Authorization header should return 401."""
        unauthorized_client.headers.update({"Authorization": ""})
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401

    def test_bearer_prefix_required(self, unauthorized_client):
        """Token without Bearer prefix should be rejected."""
        unauthorized_client.headers.update({
            "Authorization": "invalid.token.here"  # No Bearer prefix
        })
        response = unauthorized_client.get("/api/protected")
        assert response.status_code == 401
