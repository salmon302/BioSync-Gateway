"""
Audit API Tests
Implements SRS FR-3.8.3, FR-3.8.4 — Audit Trail and Hash Chain

Tests:
- Paginated audit log retrieval
- Filtering by table, operation, date range
- Hash chain verification endpoint
"""

import pytest


class TestAuditLogRetrieval:
    """Tests for audit log listing endpoint."""

    def test_audit_logs_require_auth(self, unauthorized_client):
        """Audit log endpoint should require authentication."""
        response = unauthorized_client.get("/api/audit/")
        assert response.status_code == 401

    def test_audit_logs_accept_valid_token(self, authenticated_client):
        """Audit logs should accept valid JWT."""
        response = authenticated_client.get("/api/audit/")
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "limit" in data
        assert "total" in data
        assert "total_pages" in data
        assert "logs" in data

    def test_audit_logs_default_pagination(self, authenticated_client):
        """Audit logs should default to page=1, limit=50."""
        response = authenticated_client.get("/api/audit/")
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 50

    def test_audit_logs_custom_pagination(self, authenticated_client):
        """Audit logs should support custom page and limit."""
        response = authenticated_client.get("/api/audit/?page=2&limit=10")
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10

    def test_audit_logs_reject_invalid_page(self, authenticated_client):
        """Audit logs should reject page < 1."""
        response = authenticated_client.get("/api/audit/?page=0")
        assert response.status_code == 422

    def test_audit_logs_reject_excessive_limit(self, authenticated_client):
        """Audit logs should reject limit > 100."""
        response = authenticated_client.get("/api/audit/?limit=200")
        assert response.status_code == 422


class TestAuditLogFiltering:
    """Tests for audit log filtering."""

    def test_filter_by_table_name(self, authenticated_client):
        """Should filter audit logs by table name."""
        response = authenticated_client.get("/api/audit/?table_name=plates")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_filter_by_operation(self, authenticated_client):
        """Should filter audit logs by operation type."""
        response = authenticated_client.get("/api/audit/?operation=INSERT")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_filter_by_date_range(self, authenticated_client):
        """Should filter audit logs by date range."""
        response = authenticated_client.get(
            "/api/audit/?start_date=2026-01-01&end_date=2026-12-31"
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_combined_filters(self, authenticated_client):
        """Should support combined table + operation filters."""
        response = authenticated_client.get(
            "/api/audit/?table_name=plates&operation=INSERT"
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data


class TestHashChainVerification:
    """Tests for hash chain verification endpoint."""

    def test_verify_chain_requires_auth(self, unauthorized_client):
        """Hash chain verification should require authentication."""
        response = unauthorized_client.get("/api/audit/verify")
        assert response.status_code == 401

    def test_verify_chain_accepts_valid_token(self, authenticated_client):
        """Hash chain verification should accept valid JWT."""
        response = authenticated_client.get("/api/audit/verify")
        assert response.status_code == 200
        data = response.json()
        assert "integrity" in data or "status" in data

    def test_verify_chain_returns_integrity_status(self, authenticated_client):
        """Hash chain verification should return integrity status."""
        response = authenticated_client.get("/api/audit/verify")
        data = response.json()
        # Should contain integrity information
        assert any(key in data for key in ["integrity", "status", "valid", "broken_at"])


class TestAuditScopeEnforcement:
    """Tests for audit_read scope enforcement."""

    def test_tech_cannot_read_audit(self, unauthorized_client, tech_jwt_token):
        """Technician should not have audit_read scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.get("/api/audit/")
        assert response.status_code == 403

    def test_admin_can_read_audit(self, authenticated_client):
        """Admin should have audit_read scope."""
        response = authenticated_client.get("/api/audit/")
        assert response.status_code == 200
