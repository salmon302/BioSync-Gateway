"""
API Root & Health Endpoint Tests
Implements SRS NFR-R1 — HTTPS API

Tests:
- Root endpoint returns API info
- Health check (public)
- Protected health check (requires JWT)
"""

import pytest


class TestAPIRoot:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, client):
        """Root should return service metadata."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "BioSync-Gateway"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"
        assert "/docs" in data["documentation"]

    def test_root_openapi_available(self, client):
        """OpenAPI schema should be accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data or "openapi" in data
        # WebSocket routes don't appear in OpenAPI schema
        # Check for at least some API routes
        assert any("/api/" in path for path in data.get("paths", {}))


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_public_health_check(self, client):
        """Public health check should return response (may be unhealthy without DB)."""
        response = client.get("/api/health")
        # Should return 200 or 503 (unhealthy without DB)
        assert response.status_code in [200, 503]
        data = response.json()
        # When DB is down, health endpoint returns tuple (data, 503)
        # TestClient serializes this as a list [data_dict, 503]
        if isinstance(data, list) and len(data) == 2:
            data = data[0]
        assert "status" in data

    def test_health_returns_service_status(self, client):
        """Health should report status (database may be disconnected in test env)."""
        response = client.get("/api/health")
        data = response.json()
        # When DB is down, health endpoint returns tuple (data, 503)
        if isinstance(data, list) and len(data) == 2:
            data = data[0]
        # Database may or may not be connected in test env
        assert "status" in data
        if response.status_code == 200 and "services" in data:
            assert "database" in data["services"]
            assert "middleware" in data["services"]

    def test_protected_health_requires_auth(self, unauthorized_client):
        """Protected health should reject unauthenticated requests."""
        response = unauthorized_client.get("/api/health/protected")
        assert response.status_code == 401

    def test_protected_health_accepts_valid_jwt(self, authenticated_client):
        """Protected health should accept valid JWT."""
        response = authenticated_client.get("/api/health/protected")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["authenticated"] is True
        assert "user" in data

    def test_protected_health_rejects_expired_jwt(self, unauthorized_client, expired_jwt_token):
        """Protected health should reject expired JWT."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {expired_jwt_token}"
        })
        response = unauthorized_client.get("/api/health/protected")
        assert response.status_code == 401

    def test_protected_health_rejects_invalid_jwt(self, unauthorized_client, invalid_jwt_token):
        """Protected health should reject malformed JWT."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {invalid_jwt_token}"
        })
        response = unauthorized_client.get("/api/health/protected")
        assert response.status_code == 401


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
