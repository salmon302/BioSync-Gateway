# SPDX-License-Identifier: MIT
"""
PQ-8 - Integrated multi-feature scenario to LIMS webhook (SRS FR-3.16.2/3.16.3).

End-to-end scenario with all five modules (FR-3.11-3.15) completes, all
downstream ingestion responses are captured, and the scenario execution path
sustains concurrent load.

NOTE on SRS PQ-8 '>=55 fps dashboard under concurrent load': the scenario
completion + downstream LIMS capture is implemented and asserted here. The
'>=55 fps dashboard' sub-clause is a frontend telemetry-dashboard performance
metric already covered by existing NFR-P1/P3 telemetry tests; this file adds a
concurrent-load smoke assertion on the scenario execution path rather than
fabricating a dashboard fps measurement.

DB-gated (runs in CI against postgres:15). Offline: the default mock LLM
provider requires no network; the LIMS endpoint is a throwaway local server.
"""
import os
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

DATABASE_URL = os.getenv("DATABASE_URL")
requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set - requires a live PostgreSQL (CI provides it)",
)

JWT_SECRET = os.getenv("JWT_SECRET")
requires_app = pytest.mark.skipif(
    not JWT_SECRET,
    reason="JWT_SECRET not set - api.auth fails closed on import (set in CI)",
)

ALL_FIVE = ["pk_pd", "chemistry", "digital_twin", "mrd", "llm"]


class _LimsHandler(BaseHTTPRequestHandler):
    received: list = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        _LimsHandler.received.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "received"}).encode())

    def log_message(self, *args):
        pass


def _start_lims():
    _LimsHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _LimsHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


@requires_db
def test_pq8_integrated_scenario_to_lims():
    """Full 5-module scenario routes aggregated outputs to a LIMS webhook."""
    from database import SessionLocal
    from models import ScenarioRun, SimulationScenario
    from simulation.scenarios import route_downstream_outputs, run_scenario
    from uuid import uuid4

    server, port = _start_lims()
    try:
        db = SessionLocal()
        try:
            scenario = SimulationScenario(
                scenario_uid=str(uuid4()),
                name="PQ-8 integrated",
                feature_modules=ALL_FIVE,
                seed={"pq8": 1},
                config={
                    "downstream_endpoints": [
                        {"type": "LIMS", "url": f"http://127.0.0.1:{port}/ingest"}
                    ]
                },
                is_finalized=False,
            )
            db.add(scenario)
            db.commit()
            db.refresh(scenario)

            run_row = ScenarioRun(
                run_uid=str(uuid4()),
                scenario_id=scenario.id,
                seed=scenario.seed,
                status="running",
            )
            db.add(run_row)
            db.flush()
            outputs = run_scenario(db, scenario, run_row)
            downstream = route_downstream_outputs(
                outputs, scenario.config["downstream_endpoints"]
            )
            run_row.downstream_results = downstream
            run_row.status = "completed"
            db.commit()
            db.refresh(run_row)

            # All five module outputs present in the aggregated record.
            for mod in ALL_FIVE:
                assert mod in outputs, f"missing module output: {mod}"

            # Downstream LIMS response captured.
            assert len(downstream) == 1
            assert downstream[0]["ok"] is True
            assert downstream[0]["status_code"] == 200
            assert len(_LimsHandler.received) == 1

            # The LIMS received a FHIR bundle.
            payload = json.loads(_LimsHandler.received[0])
            assert "bundle" in payload
            assert payload["source"] == "biosync-scenario"

            # LLM provenance recorded for reproducibility.
            assert "provenance" in outputs["llm"]
            assert outputs["llm"]["provenance"]["provider"] is not None
        finally:
            db.close()
    finally:
        server.shutdown()


@requires_db
def test_pq8_concurrent_load():
    """Concurrent scenario executions must all complete and capture downstream."""
    from database import SessionLocal
    from models import ScenarioRun, SimulationScenario
    from simulation.scenarios import route_downstream_outputs, run_scenario
    from uuid import uuid4

    server, port = _start_lims()
    try:
        # Seed one shared scenario.
        db0 = SessionLocal()
        try:
            scenario = SimulationScenario(
                scenario_uid=str(uuid4()),
                name="PQ-8 concurrent",
                feature_modules=ALL_FIVE,
                seed={"pq8": 2},
                config={
                    "downstream_endpoints": [
                        {"type": "LIMS", "url": f"http://127.0.0.1:{port}/ingest"}
                    ]
                },
                is_finalized=False,
            )
            db0.add(scenario)
            db0.commit()
            db0.refresh(scenario)
            scenario_id = scenario.id
            seed = scenario.seed
            config = scenario.config
        finally:
            db0.close()

        errors: list = []

        def worker():
            try:
                db = SessionLocal()
                try:
                    sc = db.query(SimulationScenario).filter_by(id=scenario_id).first()
                    run_row = ScenarioRun(
                        run_uid=str(uuid4()),
                        scenario_id=scenario_id,
                        seed=seed,
                        status="running",
                    )
                    db.add(run_row)
                    db.flush()
                    outputs = run_scenario(db, sc, run_row)
                    downstream = route_downstream_outputs(
                        outputs, config["downstream_endpoints"]
                    )
                    run_row.downstream_results = downstream
                    run_row.status = "completed"
                    db.commit()
                finally:
                    db.close()
            except Exception as exc:  # pragma: no cover - surfaced as test failure
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"concurrent scenario runs failed: {errors}"
        assert len(_LimsHandler.received) == 5
    finally:
        server.shutdown()


@requires_db
@requires_app
def test_pq8_api_end_to_end(client):
    """FR-3.16.1/2/3 via HTTP: create spec, run, downstream captured (HTTP)."""
    from api.auth import create_access_token

    token = create_access_token(
        {
            "sub": "pq8-user",
            "role": "admin",
            "scopes": ["scenario_read", "scenario_write"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        expires_delta=1,
    )
    client.headers.update({"Authorization": f"Bearer {token}"})

    server, port = _start_lims()
    try:
        body = {
            "name": "PQ-8 API",
            "feature_modules": ALL_FIVE,
            "seed": {"pq8": 3},
            "config": {
                "downstream_endpoints": [
                    {"type": "LIMS", "url": f"http://127.0.0.1:{port}/ingest"}
                ]
            },
        }
        r = client.post("/api/scenarios", json=body)
        assert r.status_code == 201, r.text
        uid = r.json()["scenario_uid"]

        run = client.post(f"/api/scenarios/{uid}/run")
        assert run.status_code == 200, run.text
        data = run.json()
        assert data["status"] == "completed"
        assert len(data["downstream_results"]) == 1
        assert data["downstream_results"][0]["ok"] is True
        assert data["output_hashes"] is not None
    finally:
        server.shutdown()
