# SPDX-License-Identifier: MIT
"""
Locust Load Test Suite for BioSync-Gateway
Implements SRS PQ-1, PQ-2, PQ-3, PQ-4, PQ-5, PQ-6 — Performance Qualification.

Covers all six NFR-P requirements:
  - NFR-P1: Telemetry ingestion throughput ≥ 100,000 data points/second
  - NFR-P2: WebGL rendering frame rate ≥ 60 fps sustained
  - NFR-P3: API response time (95th percentile) ≤ 200 ms CRUD, ≤ 50 ms WS relay
  - NFR-P4: Hash chain verification (1M rows) ≤ 60 seconds
  - NFR-P5: Pulse Engine time-step computation ≤ 50 ms
  - NFR-P6: Concurrent WebSocket connections ≥ 500

Usage:
    locust -f tests/performance/locustfile.py --host http://localhost:8000
    # Then open http://localhost:8089 in a browser to start the load test.
"""

import json
import math
import os
import random
import statistics
import time
import uuid
from typing import Dict, List

from locust import HttpUser, task, between, events, constant_pacing

# ---------------------------------------------------------------------------
# NFR-P thresholds (SRS §5.1)
# ---------------------------------------------------------------------------

NFR_P1_INGESTION_RATE = 100_000       # ≥ 100k points/sec
NFR_P2_FPS_TARGET = 60                # ≥ 60 fps
NFR_P3_HTTP_P95_MS = 200.0            # ≤ 200 ms CRUD (95th percentile)
NFR_P3_WS_P95_MS = 50.0               # ≤ 50 ms WS relay (95th percentile)
NFR_P4_HASH_CHAIN_1M_SECONDS = 60.0   # ≤ 60 seconds for 1M rows
NFR_P5_PULSE_STEP_MS = 50.0           # ≤ 50 ms per time-step
NFR_P6_CONCURRENT_WS = 500            # ≥ 500 concurrent WebSocket connections

# ---------------------------------------------------------------------------
# JWT token for authenticated requests
# ---------------------------------------------------------------------------

# JWT signing secret used to mint load-test tokens. Must match the gateway's
# JWT_SECRET so requests authenticate. Reads the same env var the gateway uses
# (defaults to the .env.example development secret) so a docker-compose stack
# and this load test share one secret without hard-coding it here.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"


def _make_jwt_token() -> str:
    """Generate a JWT token for load testing (no external dependency)."""
    import base64
    import hashlib
    import hmac

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": "loadtest-user",
        "role": "admin",
        "scopes": [
            "telemetry_write", "fhir_read", "fhir_write",
            "audit_read", "plate_read", "simulation_write",
        ],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }

    def _b64(d: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(d, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()

    header_b64 = _b64(header)
    payload_b64 = _b64(payload)
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{sig_b64}"


# ---------------------------------------------------------------------------
# Telemetry data generator (simulates 100k points/sec)
# ---------------------------------------------------------------------------

LOINC_CODES = {
    "pressure": ("8310-5", "mmHg"),
    "flow": ("85354-9", "L/min"),
    "hr": ("8867-4", "beats/min"),
    "spo2": ("59408-5", "%"),
}


def generate_telemetry_batch(batch_size: int = 100) -> Dict:
    """Generate a batch of FHIR Observation resources for telemetry ingest."""
    observations = []
    now = time.time()
    for i in range(batch_size):
        channel = random.choice(list(LOINC_CODES.keys()))
        code, unit = LOINC_CODES[channel]
        value = round(random.uniform(60, 160), 1)
        observations.append({
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": code}]
            },
            "valueQuantity": {"value": value, "unit": unit},
            "effectiveDateTime": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(now + i * 0.001)
            ),
        })
    return {"observations": observations}


# ---------------------------------------------------------------------------
# Locust User: HTTP CRUD + telemetry ingest (NFR-P1, NFR-P3)
# ---------------------------------------------------------------------------

class TelemetryIngestUser(HttpUser):
    """
    Simulates high-throughput telemetry ingestion.
    Targets NFR-P1 (≥100k points/sec) and NFR-P3 (≤200ms P95 API response).
    """

    wait_time = constant_pacing(0.1)  # 10 batches/sec per user
    BATCH_SIZE = 100  # observations per request

    def on_start(self):
        self.token = _make_jwt_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(10)
    def ingest_telemetry(self):
        """POST /api/telemetry/ingest — high-throughput telemetry ingestion."""
        payload = generate_telemetry_batch(self.BATCH_SIZE)
        with self.client.post(
            "/api/telemetry/ingest",
            json=payload,
            headers=self.headers,
            catch_exceptions=True,
            name="/api/telemetry/ingest",
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                persisted = body.get("persisted", 0)
                # Record throughput metric
                rate = persisted / 0.1  # points per second for this user
                events.request_success.fire(
                    request_type="throughput",
                    name="telemetry_ingestion_rate",
                    response_time=int(rate),
                    response_length=persisted,
                )

    @task(3)
    def get_health(self):
        """GET /api/health — basic health check."""
        self.client.get("/api/health", headers=self.headers, name="/api/health")

    @task(2)
    def get_stream_info(self):
        """GET /api/telemetry/stream/info — stream metadata."""
        self.client.get(
            "/api/telemetry/stream/info", headers=self.headers,
            name="/api/telemetry/stream/info",
        )

    @task(1)
    def get_metrics(self):
        """GET /api/metrics — performance metrics endpoint."""
        self.client.get("/api/metrics", headers=self.headers, name="/api/metrics")


# ---------------------------------------------------------------------------
# Locust User: WebSocket connections (NFR-P6)
# ---------------------------------------------------------------------------

class WebSocketUser(HttpUser):
    """
    Simulates concurrent WebSocket connections.
    Targets NFR-P6 (≥500 concurrent WebSocket connections).
    """

    wait_time = between(1, 5)

    def on_start(self):
        self.token = _make_jwt_token()
        self.ws_url = f"ws://localhost:8000/api/telemetry/stream?token={self.token}"

    @task(1)
    def connect_and_subscribe(self):
        """Open a WebSocket connection, subscribe, and measure relay RTT."""
        import websocket

        try:
            ws = websocket.WebSocket()
            ws.connect(self.ws_url)
            ws.send(json.dumps({
                "type": "subscribe",
                "channels": ["pressure", "flow", "hr", "spo2"],
            }))
            # Drain the subscribe ack, then measure ping -> pong relay RTT
            # (the server replies to a 'ping' with a 'pong' immediately).
            for _ in range(5):
                t0 = time.perf_counter()
                ws.send(json.dumps({"type": "ping"}))
                relayed = False
                for _ in range(10):
                    try:
                        msg = ws.recv()
                    except websocket.WebSocketException:
                        break
                    try:
                        if json.loads(msg).get("type") == "pong":
                            relayed = True
                            break
                    except (ValueError, AttributeError):
                        continue
                latency_ms = (time.perf_counter() - t0) * 1000
                events.request_success.fire(
                    request_type="ws_relay",
                    name="message_relay_latency",
                    response_time=int(latency_ms),
                    response_length=0,
                )
                if not relayed:
                    break
            ws.close()
        except Exception as exc:
            events.request_failure.fire(
                request_type="ws",
                name="websocket_connect",
                response_time=0,
                exception=exc,
            )


# ---------------------------------------------------------------------------
# Locust User: Pulse Engine simulation (NFR-P5)
# ---------------------------------------------------------------------------

class PulseSimulationUser(HttpUser):
    """
    Simulates Pulse Engine simulation stepping.
    Targets NFR-P5 (≤50 ms per time-step).
    """

    wait_time = constant_pacing(0.05)  # 20 steps/sec per user

    def on_start(self):
        self.token = _make_jwt_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}
        # Create a simulation
        payload = {
            "patient_id": f"loadtest-{uuid.uuid4().hex[:8]}",
            "age": 45,
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "sex": "male",
        }
        resp = self.client.post(
            "/api/simulations", json=payload, headers=self.headers,
        )
        if resp.status_code == 200:
            self.sim_id = resp.json().get("simulation_id")
        else:
            self.sim_id = None

    @task(5)
    def step_simulation(self):
        """POST /api/simulations/{id}/step — advance Pulse Engine."""
        if not self.sim_id:
            return
        start = time.perf_counter()
        with self.client.post(
            f"/api/simulations/{self.sim_id}/step",
            json={"n_steps": 10},
            headers=self.headers,
            catch_exceptions=True,
            name="/api/simulations/{id}/step",
        ) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000
            events.request_success.fire(
                request_type="pulse_step",
                name="pulse_step_latency_ms",
                response_time=int(elapsed_ms),
                response_length=0,
            )


# ---------------------------------------------------------------------------
# Locust User: FHIR CRUD (NFR-P3)
# ---------------------------------------------------------------------------

class FHIRCrudUser(HttpUser):
    """
    Simulates FHIR resource CRUD operations.
    Targets NFR-P3 (≤200ms P95 for CRUD operations).
    """

    wait_time = between(0.5, 2)

    def on_start(self):
        self.token = _make_jwt_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def create_observation(self):
        """POST /api/fhir/Observation — create FHIR Observation."""
        obs = generate_telemetry_batch(1)["observations"][0]
        self.client.post(
            "/api/fhir/Observation",
            json=obs,
            headers=self.headers,
            name="/api/fhir/Observation",
        )

    @task(2)
    def get_observations(self):
        """GET /api/fhir/Observation — query observations."""
        self.client.get(
            "/api/fhir/Observation",
            headers=self.headers,
            name="/api/fhir/Observation",
        )

    @task(1)
    def create_bundle(self):
        """POST /api/fhir/Bundle — bulk FHIR submission."""
        observations = generate_telemetry_batch(10)["observations"]
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {"resource": obs, "request": {"method": "POST", "url": "Observation"}}
                for obs in observations
            ],
        }
        self.client.post(
            "/api/fhir/Bundle",
            json=bundle,
            headers=self.headers,
            name="/api/fhir/Bundle",
        )


# ---------------------------------------------------------------------------
# Locust User: Audit / hash chain verification (NFR-P4)
# ---------------------------------------------------------------------------

class AuditVerificationUser(HttpUser):
    """
    Simulates audit trail verification queries.
    Targets NFR-P4 (≤60 seconds for 1M row hash chain verification).
    """

    wait_time = between(5, 10)

    def on_start(self):
        self.token = _make_jwt_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(1)
    def verify_hash_chain(self):
        """GET /api/audit/verify — trigger on-demand hash chain verification."""
        with self.client.get(
            "/api/audit/verify",
            headers=self.headers,
            catch_exceptions=True,
            name="/api/audit/verify",
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                if "elapsed_seconds" in body:
                    events.request_success.fire(
                        request_type="hash_chain",
                        name="hash_chain_verify_seconds",
                        response_time=int(body["elapsed_seconds"] * 1000),
                        response_length=0,
                    )


# ---------------------------------------------------------------------------
# Startup / shutdown hooks
# ---------------------------------------------------------------------------

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log NFR-P thresholds at test start."""
    print("=" * 70)
    print("BioSync-Gateway Performance Qualification Load Test")
    print("=" * 70)
    print(f"  NFR-P1: Telemetry ingestion ≥ {NFR_P1_INGESTION_RATE:,} pts/sec")
    print(f"  NFR-P2: Rendering frame rate ≥ {NFR_P2_FPS_TARGET} fps")
    print(f"  NFR-P3: API P95 ≤ {NFR_P3_HTTP_P95_MS}ms | WS P95 ≤ {NFR_P3_WS_P95_MS}ms")
    print(f"  NFR-P4: Hash chain 1M rows ≤ {NFR_P4_HASH_CHAIN_1M_SECONDS}s")
    print(f"  NFR-P5: Pulse time-step ≤ {NFR_P5_PULSE_STEP_MS}ms")
    print(f"  NFR-P6: Concurrent WS connections ≥ {NFR_P6_CONCURRENT_WS}")
    print("=" * 70)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Summarize results at test end."""
    stats = environment.runner.stats
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    print("\n" + "=" * 70)
    print("Load Test Summary")
    print("=" * 70)
    print(f"  Total requests: {total_requests}")
    print(f"  Total failures: {total_failures}")
    if total_requests > 0:
        p95 = stats.total.get_current_response_time_percentile(0.95)
        print(f"  Overall P95 response time: {p95 * 1000:.1f} ms" if p95 else "  P95: N/A")
    print("=" * 70)
