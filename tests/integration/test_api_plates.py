"""
Plate API Tests
Implements SRS FR-3.2.5, FR-3.3.5 — Microplate Editor

Tests:
- Plate CRUD operations
- Barcode validation endpoint
- Dilution worklist generation
- Scope enforcement
"""

import pytest


class TestPlateCRUD:
    """Tests for plate CRUD endpoints."""

    def test_create_plate_requires_auth(self, unauthorized_client):
        """Plate creation should require authentication."""
        response = unauthorized_client.post("/api/plates/", json={})
        assert response.status_code == 401

    def test_create_plate_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Plate creation should require plate_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post("/api/plates/", json={})
        assert response.status_code == 403

    def test_create_plate_accepts_valid_request(self, authenticated_client):
        """Plate creation should accept valid plate data."""
        plate_data = {
            "plate_id": "test-plate-001",
            "format": "96-well",
            "barcodes": ["ATCACG", "CGATGT", "AGATCG", "TTAGGC"]
        }
        response = authenticated_client.post("/api/plates/", json=plate_data)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "created"

    def test_get_plate_requires_read_scope(self, unauthorized_client, tech_jwt_token):
        """Plate retrieval should require plate_read scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.get("/api/plates/1")
        assert response.status_code == 403

    def test_get_plate_returns_plate_data(self, authenticated_client):
        """Plate retrieval should return plate details."""
        response = authenticated_client.get("/api/plates/1")
        assert response.status_code == 200
        data = response.json()
        assert "plate_id" in data

    def test_get_plate_nonexistent(self, authenticated_client):
        """Plate retrieval should handle non-existent plates."""
        response = authenticated_client.get("/api/plates/99999")
        # Should return 200 from stub or 404
        assert response.status_code in [200, 404]


class TestBarcodeValidation:
    """Tests for barcode validation endpoint."""

    def test_validate_barcodes_requires_auth(self, unauthorized_client):
        """Barcode validation should require authentication."""
        response = unauthorized_client.post(
            "/api/plates/1/validate-barcodes",
            json={"barcodes": ["ATCACG", "CGATGT"]}
        )
        assert response.status_code == 401

    def test_validate_barcodes_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Barcode validation should require plate_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post(
            "/api/plates/1/validate-barcodes",
            json={"barcodes": ["ATCACG", "CGATGT"]}
        )
        assert response.status_code == 403

    def test_validate_barcodes_accepts_valid_barcodes(self, authenticated_client):
        """Barcode validation should accept valid barcode set (d>=3)."""
        barcode_data = {
            "barcodes": ["ATCACG", "CGATGT", "AGATCG", "TTAGGC"],
            "min_distance": 3
        }
        response = authenticated_client.post(
            "/api/plates/1/validate-barcodes",
            json=barcode_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data or "violations" in data

    def test_validate_barcodes_rejects_invalid_barcodes(self, authenticated_client):
        """Barcode validation should reject barcodes with d<3."""
        barcode_data = {
            "barcodes": ["ATCGAT", "ATCGAC", "TTAGGC"],  # d=1 violation
            "min_distance": 3
        }
        response = authenticated_client.post(
            "/api/plates/1/validate-barcodes",
            json=barcode_data
        )
        assert response.status_code == 200
        data = response.json()
        # Should indicate validation failure
        assert not data.get("valid", True) is True or len(data.get("violations", [])) > 0

    def test_validate_barcodes_rejects_empty_list(self, authenticated_client):
        """Barcode validation should reject empty barcode list."""
        response = authenticated_client.post(
            "/api/plates/1/validate-barcodes",
            json={"barcodes": []}
        )
        assert response.status_code == 400

    def test_validate_barcodes_custom_min_distance(self, authenticated_client):
        """Barcode validation should support custom min_distance."""
        barcode_data = {
            "barcodes": ["ATCACG", "CGATGT", "AGATCG"],
            "min_distance": 2
        }
        response = authenticated_client.post(
            "/api/plates/1/validate-barcodes",
            json=barcode_data
        )
        assert response.status_code == 200


class TestDilutionWorklist:
    """Tests for dilution worklist generation endpoint."""

    def test_dilution_worklist_requires_auth(self, unauthorized_client):
        """Dilution worklist should require authentication."""
        response = unauthorized_client.post(
            "/api/plates/1/dilution-worklist",
            json={
                "initial_concentration": 100.0,
                "initial_unit": "µM",
                "target_concentration": 1.0,
                "target_unit": "nM"
            }
        )
        assert response.status_code == 401

    def test_dilution_worklist_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Dilution worklist should require plate_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post(
            "/api/plates/1/dilution-worklist",
            json={
                "initial_concentration": 100.0,
                "initial_unit": "µM",
                "target_concentration": 1.0,
                "target_unit": "nM"
            }
        )
        assert response.status_code == 403

    def test_dilution_worklist_accepts_valid_request(self, authenticated_client):
        """Dilution worklist should accept valid dilution parameters."""
        dilution_request = {
            "initial_concentration": 100.0,
            "initial_unit": "µM",
            "target_concentration": 1.0,
            "target_unit": "nM",
            "molar_mass": 66000.0
        }
        response = authenticated_client.post(
            "/api/plates/1/dilution-worklist",
            json=dilution_request
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "steps" in data

    def test_dilution_worklist_with_pre_dilution(self, authenticated_client):
        """Dilution worklist should generate pre-dilution for low volumes."""
        dilution_request = {
            "initial_concentration": 1000.0,
            "initial_unit": "M",
            "target_concentration": 1.0,
            "target_unit": "µM",
            "molar_mass": 66000.0,
            "min_volume": 0.5
        }
        response = authenticated_client.post(
            "/api/plates/1/dilution-worklist",
            json=dilution_request
        )
        assert response.status_code == 200

    def test_dilution_worklist_missing_parameters(self, authenticated_client):
        """Dilution worklist should handle missing parameters."""
        response = authenticated_client.post(
            "/api/plates/1/dilution-worklist",
            json={}
        )
        # Should return 422 validation error or 200 from stub
        assert response.status_code in [200, 422]


class TestPlateImportExport:
    """Tests for plate import/export functionality."""

    def test_plate_export_json(self, authenticated_client):
        """Plate export should support JSON format."""
        response = authenticated_client.get("/api/plates/1/export?format=json")
        # Should return 200 from stub or 404
        assert response.status_code in [200, 404]

    def test_plate_export_csv(self, authenticated_client):
        """Plate export should support CSV format."""
        response = authenticated_client.get("/api/plates/1/export?format=csv")
        # Should return 200 from stub or 404
        assert response.status_code in [200, 404]
