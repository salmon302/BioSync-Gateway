# SPDX-License-Identifier: MIT
"""
Human Factors Metrics API Tests
Implements SRS FR-3.9.1 (passive metrics collection) and FR-3.9.2 (uFMEA JSON export).

Tests:
- POST /api/human-factors/events — auth, scope enforcement, batch ingest persistence
- GET /api/human-factors/export — auth, scope enforcement, JSON shape, aggregation correctness
"""

import pytest
import json
import uuid
from datetime import datetime


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

def _make_event(session_id, event_type, latency_ms=None, steps_count=None,
                component=None, metadata=None):
    """Helper to build a single event dict matching HumanFactorsEventIn."""
    ev = {
        "session_id": session_id,
        "event_type": event_type,
        "timestamp": datetime.utcnow().timestamp() * 1000,
    }
    if latency_ms is not None:
        ev["latency_ms"] = latency_ms
    if steps_count is not None:
        ev["steps_count"] = steps_count
    if component is not None:
        ev["component"] = component
    if metadata is not None:
        ev["metadata"] = metadata
    return ev


# ---------------------------------------------------------------------------
# POST /api/human-factors/events — authentication & scope
# ---------------------------------------------------------------------------

class TestHumanFactorsIngestAuth:
    """Tests for POST /api/human-factors/events authentication and scope."""

    def test_post_events_requires_auth(self, unauthorized_client):
        """POST /events should return 401 without a token."""
        response = unauthorized_client.post(
            "/api/human-factors/events",
            json={"events": [_make_event("s1", "test")]},
        )
        assert response.status_code == 401

    def test_post_events_requires_write_scope(self, unauthorized_client, hf_read_only_token):
        """POST /events should return 403 for a read-only token."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {hf_read_only_token}"
        })
        response = unauthorized_client.post(
            "/api/human-factors/events",
            json={"events": [_make_event("s1", "test")]},
        )
        assert response.status_code == 403

    def test_post_events_rejects_empty_batch(self, authenticated_client):
        """POST /events should reject an empty events array."""
        response = authenticated_client.post(
            "/api/human-factors/events",
            json={"events": []},
        )
        assert response.status_code == 422

    def test_post_events_rejects_missing_events_key(self, authenticated_client):
        """POST /events should reject a body without the events key."""
        response = authenticated_client.post(
            "/api/human-factors/events",
            json={},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/human-factors/events — persistence
# ---------------------------------------------------------------------------

class TestHumanFactorsIngestPersistence:
    """Tests that POST /events actually persists rows to the database."""

    def test_post_single_event_persists(self, authenticated_client):
        """A single POSTed event should be persisted and visible in export."""
        session = f"persist-test-{uuid.uuid4().hex[:8]}"
        response = authenticated_client.post(
            "/api/human-factors/events",
            json={"events": [_make_event(session, "selection_latency", latency_ms=150,
                                        component="TelemetryDashboard")]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        assert len(data["inserted_ids"]) == 1

        # Verify via export
        export = authenticated_client.get(
            f"/api/human-factors/export?session_id={session}"
        )
        assert export.status_code == 200
        export_data = export.json()
        assert export_data["total_events"] == 1
        assert len(export_data["sessions"]) == 1
        assert export_data["sessions"][0]["session_id"] == session
        assert export_data["sessions"][0]["event_count"] == 1

    def test_post_batch_events_persists_all(self, authenticated_client):
        """A batch of POSTed events should all be persisted."""
        session = f"batch-test-{uuid.uuid4().hex[:8]}"
        events = [
            _make_event(session, "selection_latency", latency_ms=120, component="Dashboard"),
            _make_event(session, "selection_latency", latency_ms=200, component="Dashboard"),
            _make_event(session, "input_steps", steps_count=5, component="MicroplateEditor"),
            _make_event(session, "interaction", component="AdminConsole",
                        metadata={"action": "save"}),
        ]
        response = authenticated_client.post(
            "/api/human-factors/events",
            json={"events": events},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 4
        assert len(data["inserted_ids"]) == 4

        # Verify via export
        export = authenticated_client.get(
            f"/api/human-factors/export?session_id={session}"
        )
        assert export.status_code == 200
        export_data = export.json()
        assert export_data["total_events"] == 4
        assert len(export_data["sessions"]) == 1
        assert export_data["sessions"][0]["event_count"] == 4


# ---------------------------------------------------------------------------
# GET /api/human-factors/export — authentication & scope
# ---------------------------------------------------------------------------

class TestHumanFactorsExportAuth:
    """Tests for GET /api/human-factors/export authentication and scope."""

    def test_export_requires_auth(self, unauthorized_client):
        """GET /export should return 401 without a token."""
        response = unauthorized_client.get("/api/human-factors/export")
        assert response.status_code == 401

    def test_export_requires_read_scope(self, unauthorized_client, tech_jwt_token):
        """GET /export should return 403 for a token without human_factors_read."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {tech_jwt_token}"
        })
        response = unauthorized_client.get("/api/human-factors/export")
        assert response.status_code == 403

    def test_export_accepts_read_scope(self, unauthorized_client, hf_read_only_token):
        """GET /export should accept a token with only human_factors_read."""
        unauthorized_client.headers.update({
            "Authorization": f"Bearer {hf_read_only_token}"
        })
        response = unauthorized_client.get("/api/human-factors/export")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/human-factors/export — JSON shape
# ---------------------------------------------------------------------------

class TestHumanFactorsExportShape:
    """Tests for the uFMEA export JSON structure."""

    def test_export_returns_valid_json(self, authenticated_client):
        """Export endpoint should return valid JSON."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_export_has_required_top_level_keys(self, authenticated_client):
        """Export JSON must contain all required top-level keys."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        required_keys = {
            "export_timestamp", "scope", "user", "total_events",
            "sessions", "event_type_counts", "latency_stats",
            "steps_stats", "component_breakdown",
        }
        assert required_keys.issubset(data.keys())

    def test_export_sessions_structure(self, authenticated_client):
        """Each session entry must have the correct fields."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        for sess in data["sessions"]:
            assert "session_id" in sess
            assert "event_count" in sess
            assert "first_event" in sess
            assert "last_event" in sess

    def test_export_event_type_counts_structure(self, authenticated_client):
        """Each event-type count entry must have event_type and count."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        for et in data["event_type_counts"]:
            assert "event_type" in et
            assert "count" in et

    def test_export_latency_stats_structure(self, authenticated_client):
        """Latency stats must contain percentile fields."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        lat = data["latency_stats"]
        for key in ("total_events", "min_ms", "max_ms", "mean_ms",
                     "p50_ms", "p90_ms", "p95_ms", "p99_ms"):
            assert key in lat

    def test_export_steps_stats_structure(self, authenticated_client):
        """Steps stats must contain min/max/mean/median fields."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        steps = data["steps_stats"]
        for key in ("total_events", "min_steps", "max_steps",
                     "mean_steps", "median_steps"):
            assert key in steps

    def test_export_component_breakdown_structure(self, authenticated_client):
        """Each component breakdown entry must have correct fields."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        for comp in data["component_breakdown"]:
            assert "component" in comp
            assert "event_count" in comp
            assert "avg_latency_ms" in comp
            assert "avg_steps" in comp

    def test_export_scope_and_user(self, authenticated_client):
        """Export should include the scope and user from the JWT."""
        response = authenticated_client.get("/api/human-factors/export")
        assert response.status_code == 200
        data = response.json()
        assert data["scope"] == "human_factors_read"
        assert data["user"] == "test-user"


# ---------------------------------------------------------------------------
# GET /api/human-factors/export — aggregation correctness
# ---------------------------------------------------------------------------

class TestHumanFactorsExportAggregation:
    """Tests that the export correctly aggregates seeded data."""

    def test_export_reflects_seeded_data(self, authenticated_client):
        """Export should reflect events POSTed via the ingest endpoint."""
        session = f"agg-test-{uuid.uuid4().hex[:8]}"
        events = [
            _make_event(session, "selection_latency", latency_ms=100, component="Dashboard"),
            _make_event(session, "selection_latency", latency_ms=300, component="Dashboard"),
            _make_event(session, "input_steps", steps_count=3, component="MicroplateEditor"),
            _make_event(session, "input_steps", steps_count=7, component="MicroplateEditor"),
            _make_event(session, "interaction", component="AdminConsole"),
        ]
        post_resp = authenticated_client.post(
            "/api/human-factors/events",
            json={"events": events},
        )
        assert post_resp.status_code == 201

        export_resp = authenticated_client.get(
            f"/api/human-factors/export?session_id={session}"
        )
        assert export_resp.status_code == 200
        data = export_resp.json()

        # Total events
        assert data["total_events"] == 5

        # Sessions
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == session
        assert data["sessions"][0]["event_count"] == 5

        # Event-type counts
        et_counts = {e["event_type"]: e["count"] for e in data["event_type_counts"]}
        assert et_counts.get("selection_latency") == 2
        assert et_counts.get("input_steps") == 2
        assert et_counts.get("interaction") == 1

        # Latency stats (only selection_latency events have latency_ms)
        lat = data["latency_stats"]
        assert lat["total_events"] == 2
        assert lat["min_ms"] == 100.0
        assert lat["max_ms"] == 300.0
        assert lat["mean_ms"] == 200.0

        # Steps stats (only input_steps events have steps_count)
        steps = data["steps_stats"]
        assert steps["total_events"] == 2
        assert steps["min_steps"] == 3
        assert steps["max_steps"] == 7
        assert steps["mean_steps"] == 5.0

        # Component breakdown
        comp_map = {c["component"]: c for c in data["component_breakdown"]}
        assert "Dashboard" in comp_map
        assert comp_map["Dashboard"]["event_count"] == 2
        assert "MicroplateEditor" in comp_map
        assert comp_map["MicroplateEditor"]["event_count"] == 2
        assert "AdminConsole" in comp_map
        assert comp_map["AdminConsole"]["event_count"] == 1

    def test_export_filter_by_session_id(self, authenticated_client):
        """Export should filter by session_id when provided."""
        session_a = f"filter-a-{uuid.uuid4().hex[:8]}"
        session_b = f"filter-b-{uuid.uuid4().hex[:8]}"
        authenticated_client.post(
            "/api/human-factors/events",
            json={"events": [
                _make_event(session_a, "selection_latency", latency_ms=50, component="A"),
                _make_event(session_a, "input_steps", steps_count=2, component="A"),
            ]},
        )
        authenticated_client.post(
            "/api/human-factors/events",
            json={"events": [
                _make_event(session_b, "selection_latency", latency_ms=80, component="B"),
                _make_event(session_b, "interaction", component="B"),
            ]},
        )

        export_a = authenticated_client.get(
            f"/api/human-factors/export?session_id={session_a}"
        )
        assert export_a.status_code == 200
        data_a = export_a.json()
        assert data_a["total_events"] == 2
        assert len(data_a["sessions"]) == 1
        assert data_a["sessions"][0]["session_id"] == session_a

        export_b = authenticated_client.get(
            f"/api/human-factors/export?session_id={session_b}"
        )
        assert export_b.status_code == 200
        data_b = export_b.json()
        assert data_b["total_events"] == 2
        assert len(data_b["sessions"]) == 1
        assert data_b["sessions"][0]["session_id"] == session_b

    def test_export_empty_when_no_data(self, authenticated_client):
        """Export should return zero counts when no data exists for a session."""
        session = f"empty-{uuid.uuid4().hex[:8]}"
        response = authenticated_client.get(
            f"/api/human-factors/export?session_id={session}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] == 0
        assert len(data["sessions"]) == 0
        assert len(data["event_type_counts"]) == 0
        assert data["latency_stats"]["total_events"] == 0
        assert data["steps_stats"]["total_events"] == 0
        assert len(data["component_breakdown"]) == 0
