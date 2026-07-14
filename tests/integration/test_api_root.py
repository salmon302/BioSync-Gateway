"""
API Root Endpoint Tests
Implements SRS NFR-R1 — API Information

Tests:
- Root endpoint returns service metadata
- OpenAPI schema accessibility
- API versioning
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

    def test_root_has_swagger_docs(self, client):
        """Swagger UI should be accessible at /docs."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_root_version_matches_srs(self, client):
        """API version should match SRS version."""
        response = client.get("/")
        data = response.json()
        assert data["version"] == "1.0.0"

    def test_root_status_operational(self, client):
        """Root status should indicate operational state."""
        response = client.get("/")
        data = response.json()
        assert data["status"] == "operational"
