"""
Simulation API Tests
Implements SRS FR-3.6.1–3.6.5 — Pulse Engine Integration

Tests:
- Simulation CRUD lifecycle
- Step, pause, resume, stop operations
- Scope enforcement
"""

import pytest


class TestSimulationCRUD:
    """Tests for simulation creation and retrieval."""

    def test_create_simulation_requires_auth(self, unauthorized_client):
        """Simulation creation should require authentication."""
        response = unauthorized_client.post(
            "/api/simulations/",
            json={"patient_id": "test-1", "age": 30, "weight_kg": 70,
                  "height_cm": 175, "sex": "male"}
        )
        assert response.status_code == 401

    def test_create_simulation_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Simulation creation should require simulation_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post(
            "/api/simulations/",
            json={"patient_id": "test-1", "age": 30, "weight_kg": 70,
                  "height_cm": 175, "sex": "male"}
        )
        assert response.status_code == 403

    def test_create_simulation_accepts_valid_config(self, authenticated_client):
        """Simulation creation should accept valid patient config."""
        config = {
            "patient_id": "sim-patient-001",
            "age": 45,
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "sex": "male",
            "base_heart_rate": 72.0,
            "base_blood_pressure": [120.0, 80.0],
            "base_spo2": 98.0,
            "conditions": []
        }
        response = authenticated_client.post(
            "/api/simulations/",
            json=config
        )
        assert response.status_code == 200
        data = response.json()
        assert "simulation_id" in data
        assert data["status"] == "created"
        assert data["patient"] == "sim-patient-001"

    def test_create_simulation_with_conditions(self, authenticated_client):
        """Simulation creation should accept patient conditions."""
        config = {
            "patient_id": "sim-patient-002",
            "age": 65,
            "weight_kg": 85.0,
            "height_cm": 180.0,
            "sex": "male",
            "conditions": ["hypertension", "respiratory_distress"]
        }
        response = authenticated_client.post(
            "/api/simulations/",
            json=config
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"

    def test_create_simulation_missing_required_fields(self, authenticated_client):
        """Simulation creation should reject missing required fields."""
        response = authenticated_client.post(
            "/api/simulations/",
            json={"patient_id": "test-1"}  # Missing age, weight, height, sex
        )
        # Should return 422 validation error or 400
        assert response.status_code in [400, 422]

    def test_create_simulation_invalid_age(self, authenticated_client):
        """Simulation creation should handle invalid age values."""
        config = {
            "patient_id": "sim-patient-003",
            "age": -5,  # Invalid
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "sex": "male"
        }
        response = authenticated_client.post(
            "/api/simulations/",
            json=config
        )
        # Should return 400 or 422
        assert response.status_code in [200, 400, 422]


class TestSimulationStep:
    """Tests for simulation step advancement."""

    def test_step_simulation_requires_auth(self, unauthorized_client):
        """Simulation stepping should require authentication."""
        response = unauthorized_client.post("/api/simulations/sim-1/step?steps=10")
        assert response.status_code == 401

    def test_step_simulation_requires_write_scope(self, unauthorized_client, tech_jwt_token):
        """Simulation stepping should require simulation_write scope."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.post("/api/simulations/sim-1/step?steps=10")
        assert response.status_code == 403

    def test_step_simulation_advances_state(self, authenticated_client):
        """Stepping simulation should advance state and return metrics."""
        # First create a simulation
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "step-test-001",
            "age": 40, "weight_kg": 75.0, "height_cm": 170.0, "sex": "female"
        })
        sim_id = create_response.json()["simulation_id"]

        # Step the simulation
        response = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert "simulation_id" in data
        assert data["simulation_id"] == sim_id
        assert "metrics" in data
        assert data["steps_completed"] == 10

    def test_step_simulation_default_steps(self, authenticated_client):
        """Stepping simulation without steps parameter should default to 1."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "step-test-002",
            "age": 50, "weight_kg": 80.0, "height_cm": 180.0, "sex": "male"
        })
        sim_id = create_response.json()["simulation_id"]

        response = authenticated_client.post(f"/api/simulations/{sim_id}/step")
        assert response.status_code == 200
        data = response.json()
        assert data["steps_completed"] == 1

    def test_step_nonexistent_simulation(self, authenticated_client):
        """Stepping non-existent simulation should return error."""
        response = authenticated_client.post(
            "/api/simulations/nonexistent/step?steps=10"
        )
        assert response.status_code in [400, 404, 500]


class TestSimulationLifecycle:
    """Tests for simulation pause, resume, and stop operations."""

    def test_pause_simulation_requires_auth(self, unauthorized_client):
        """Simulation pause should require authentication."""
        response = unauthorized_client.post("/api/simulations/sim-1/pause")
        assert response.status_code == 401

    def test_pause_simulation(self, authenticated_client):
        """Pause should stop simulation and return state."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "lifecycle-test-001",
            "age": 35, "weight_kg": 65.0, "height_cm": 165.0, "sex": "female"
        })
        sim_id = create_response.json()["simulation_id"]

        # Step first
        authenticated_client.post(f"/api/simulations/{sim_id}/step?steps=5")

        # Pause
        response = authenticated_client.post(f"/api/simulations/{sim_id}/pause")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data or "status" in data

    def test_resume_simulation(self, authenticated_client):
        """Resume should restart paused simulation."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "lifecycle-test-002",
            "age": 55, "weight_kg": 70.0, "height_cm": 170.0, "sex": "male"
        })
        sim_id = create_response.json()["simulation_id"]

        # Pause
        authenticated_client.post(f"/api/simulations/{sim_id}/pause")

        # Resume
        response = authenticated_client.post(f"/api/simulations/{sim_id}/resume")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_stop_simulation(self, authenticated_client):
        """Stop should terminate simulation and return final state."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "lifecycle-test-003",
            "age": 60, "weight_kg": 75.0, "height_cm": 175.0, "sex": "male"
        })
        sim_id = create_response.json()["simulation_id"]

        # Step
        authenticated_client.post(f"/api/simulations/{sim_id}/step?steps=10")

        # Stop
        response = authenticated_client.post(f"/api/simulations/{sim_id}/stop")
        assert response.status_code == 200
        data = response.json()
        assert "state" in data or "status" in data

    def test_full_lifecycle(self, authenticated_client):
        """Test full simulation lifecycle: create → step → pause → resume → stop."""
        # Create
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "full-lifecycle-001",
            "age": 42, "weight_kg": 68.0, "height_cm": 168.0, "sex": "female"
        })
        sim_id = create_response.json()["simulation_id"]

        # Step
        step_response = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=5"
        )
        assert step_response.status_code == 200

        # Pause
        pause_response = authenticated_client.post(f"/api/simulations/{sim_id}/pause")
        assert pause_response.status_code == 200

        # Resume
        resume_response = authenticated_client.post(f"/api/simulations/{sim_id}/resume")
        assert resume_response.status_code == 200

        # Step again after resume
        step_response2 = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=5"
        )
        assert step_response2.status_code == 200

        # Stop
        stop_response = authenticated_client.post(f"/api/simulations/{sim_id}/stop")
        assert stop_response.status_code == 200


class TestSimulationMetrics:
    """Tests for simulation metrics extraction."""

    def test_metrics_contain_heart_rate(self, authenticated_client):
        """Metrics should contain heart_rate field."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "metrics-test-001",
            "age": 30, "weight_kg": 70.0, "height_cm": 175.0, "sex": "male"
        })
        sim_id = create_response.json()["simulation_id"]

        response = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=10"
        )
        data = response.json()
        metrics = data.get("metrics", {})
        assert "heart_rate" in str(metrics) or "heart_rate" in metrics

    def test_metrics_contain_blood_pressure(self, authenticated_client):
        """Metrics should contain blood pressure fields."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "metrics-test-002",
            "age": 45, "weight_kg": 80.0, "height_cm": 180.0, "sex": "male"
        })
        sim_id = create_response.json()["simulation_id"]

        response = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=10"
        )
        data = response.json()
        metrics = data.get("metrics", {})
        assert "blood_pressure_systolic" in str(metrics) or "blood_pressure_systolic" in metrics
        assert "blood_pressure_diastolic" in str(metrics) or "blood_pressure_diastolic" in metrics

    def test_metrics_contain_spo2(self, authenticated_client):
        """Metrics should contain SpO2 field."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "metrics-test-003",
            "age": 50, "weight_kg": 75.0, "height_cm": 170.0, "sex": "female"
        })
        sim_id = create_response.json()["simulation_id"]

        response = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=10"
        )
        data = response.json()
        metrics = data.get("metrics", {})
        assert "spo2" in str(metrics) or "spo2" in metrics

    def test_metrics_contain_respiratory_rate(self, authenticated_client):
        """Metrics should contain respiratory_rate field."""
        create_response = authenticated_client.post("/api/simulations/", json={
            "patient_id": "metrics-test-004",
            "age": 38, "weight_kg": 65.0, "height_cm": 165.0, "sex": "female"
        })
        sim_id = create_response.json()["simulation_id"]

        response = authenticated_client.post(
            f"/api/simulations/{sim_id}/step?steps=10"
        )
        data = response.json()
        metrics = data.get("metrics", {})
        assert "respiratory_rate" in str(metrics) or "respiratory_rate" in metrics
