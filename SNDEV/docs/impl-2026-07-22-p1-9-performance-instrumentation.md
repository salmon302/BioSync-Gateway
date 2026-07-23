Title: p1-9-performance-instrumentation
Date: 2026-07-22T21:00:00Z
Author: Seth Nenninger (OpenCode Agent)
Contribution Type: Implementation
Ticket/Context: SRS Gap Analysis P1-9 — Performance instrumentation (NFR-P1–P6)
Summary: Add comprehensive performance instrumentation: response-time middleware with metrics endpoint, FPS counter component with P95 frame-time tracking, Locust load test suite, and PQ tests covering all six NFR-P requirements.

---

## 1. Task Reference
Implements P1-9 from the SRS gap analysis: "Performance instrumentation" covering NFR-P1 through NFR-P6.

## 2. Specification Summary
Per the gap analysis, all six NFR-P requirements are currently unmeasured:

| NFR-P | Requirement | Metric |
|-------|-------------|--------|
| NFR-P1 | Telemetry ingestion throughput | ≥ 100,000 data points/second |
| NFR-P2 | WebGL rendering frame rate | ≥ 60 fps sustained |
| NFR-P3 | API response time (95th percentile) | ≤ 200 ms CRUD, ≤ 50 ms WS relay |
| NFR-P4 | Hash chain verification (1M rows) | ≤ 60 seconds |
| NFR-P5 | Pulse Engine time-step computation | ≤ 50 ms per time-step |
| NFR-P6 | Concurrent WebSocket connections | ≥ 500 simultaneous sessions |

## 3. Implementation Notes

### 3.1 Response-Time Middleware (`middleware/api/middleware/response_time.py`)
- Replaces the inline `PerformanceMiddleware` in `main.py` with a comprehensive module.
- Collects per-endpoint metrics: request count, average, P95, min, max response time.
- Tracks WebSocket message relay latency via a `record_ws_latency()` function.
- Exposes `/api/metrics` endpoint returning JSON with all collected metrics.
- Configurable slow-request threshold (default 100ms for HTTP, 50ms for WS).
- Thread-safe metrics storage using `threading.Lock`.

### 3.2 FPS Counter Component (`frontend/src/components/TelemetryDashboard/FPSCounter.tsx`)
- Standalone React component for measuring and displaying FPS.
- Uses `requestAnimationFrame` for accurate frame timing.
- Tracks frame time variance and P95 frame time.
- Color-coded status: green (≥60 fps), yellow (55–59 fps), red (<55 fps).
- Integrates into `TelemetryDashboard.tsx` as an overlay.

### 3.3 Locust Load Test (`tests/performance/locustfile.py`)
- `TelemetryUser` simulates 500 concurrent WebSocket connections (NFR-P6).
- `TelemetryIngestUser` simulates 100k points/sec ingestion (NFR-P1).
- HTTP user tasks measure API response time P95 (NFR-P3).
- Includes hash chain verification benchmark (NFR-P4).
- Includes Pulse Engine time-step benchmark (NFR-P5).

### 3.4 Performance Instrumentation Tests (`tests/performance/test_p1_9_performance_instrumentation.py`)
- Unit tests for `ResponseTimeMiddleware` metrics collection.
- Unit tests for `FPSCounter` frame timing logic.
- Integration tests for telemetry ingestion throughput (NFR-P1).
- Integration tests for API response time tracking (NFR-P3).
- Integration tests for hash chain verification performance (NFR-P4).
- Integration tests for Pulse Engine time-step performance (NFR-P5).

### 3.5 Frontend FPS Counter Tests (`frontend/tests/fps_counter.test.tsx`)
- Tests FPS counter rendering and threshold display.
- Tests color-coding logic.
- Tests P95 frame time calculation.

## 4. Verification
- `python -m py_compile` PASS on all new and modified Python modules.
- `npx tsc --noEmit` PASS on all TypeScript files (zero errors).
- `pytest tests/performance/test_p1_9_performance_instrumentation.py` — **24 passed**.
- `npx vitest run tests/fps_counter.test.tsx` — **9 passed**.
- `npx vitest run` (all frontend tests) — **75 passed, 1 skipped**.
- `pytest tests/unit/` — **119 passed, 3 skipped** (no regressions).
- `pytest tests/performance/` — **50 passed** (no regressions).
- Pre-existing failure in `tests/test_iq1_docker_health.py::test_health_endpoint_response_structure` is unrelated (missing `python-multipart` dependency).

## 5. Files Changed
- `middleware/api/middleware/__init__.py` (new)
- `middleware/api/middleware/response_time.py` (new)
- `frontend/src/components/TelemetryDashboard/FPSCounter.tsx` (new)
- `tests/performance/locustfile.py` (new)
- `tests/performance/test_p1_9_performance_instrumentation.py` (new)
- `frontend/tests/fps_counter.test.tsx` (new)
- `middleware/api/main.py` (modified — register metrics endpoint, use new middleware)
- `middleware/api/routes/telemetry.py` (modified — WS relay latency tracking, ingestion rate recording, new `/ingestion/stats` endpoint)
- `middleware/engine/pulse.py` (modified — record Pulse step latency for NFR-P5)
- `frontend/src/pages/TelemetryDashboard.tsx` (modified — integrate FPSCounter component)
- `frontend/src/pages/TelemetryDashboard.css` (modified — position: relative for FPS counter overlay)
- `frontend/src/pages/TelemetryDashboard.tsx` (modified — integrate FPSCounter component)
