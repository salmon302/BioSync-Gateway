// SPDX-License-Identifier: MIT
/*
 * PQ-1: Real-Load Performance Qualification (Grafana k6)
 * ---------------------------------------------------------------
 * Implements the revised SRS §7.3 PQ-1 acceptance criteria using a
 * distributed load test instead of the deprecated CI "smoke-only" import
 * micro-benchmark (see tests/performance/test_pq1_websocket_latency.py).
 *
 * Targets (revised D1 plan):
 *   - Ramp to 50 virtual users over ~12 minutes.
 *   - HTTP SLO:  http_req_failed  < 0.01
 *                http_req_duration p(95) < 250 ms   (SRS NFR-P3)
 *   - WS-specific SLO (only evaluated when API_TOKEN is supplied):
 *                ws_connecting p(95) < 250 ms
 *
 * The 50-VU peak exercises both the public HTTP health path and, when a
 * valid JWT is provided via API_TOKEN, the authenticated WebSocket
 * telemetry stream (/api/telemetry/stream). The WebSocket relay
 * threshold is intentionally WS-specific so the HTTP SLO is not masked
 * by unauthenticated handshake rejections.
 *
 * Execution (official grafana/k6 Docker image):
 *   docker run --rm --network host \
 *     -v "$PWD/tests/performance/k6:/scripts" \
 *     grafana/k6 run /scripts/pq1_websocket.js \
 *     -e BASE_URL=http://localhost:8000 \
 *     -e WS_URL=ws://localhost:8000/api/telemetry/stream \
 *     -e API_TOKEN=<valid-jwt> \
 *     -e PEAK_VUS=50 -e RAMP_MIN=12
 *
 * Triggered by .github/workflows/pq.yml (workflow_dispatch + nightly).
 */

import http from 'k6/http';
import ws from 'k6/ws';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const WS_URL = __ENV.WS_URL || 'ws://localhost:8000/api/telemetry/stream';
// Optional. Required for the authenticated WebSocket load path. Without it
// the WS scenario is skipped so http_req_failed stays meaningful.
const API_TOKEN = __ENV.API_TOKEN || '';
const RAMP_MIN = parseInt(__ENV.RAMP_MIN || '12'); // ramp-to-peak duration
const PEAK_VUS = parseInt(__ENV.PEAK_VUS || '50'); // peak concurrent VUs

const WS_CHANNELS = ['pressure', 'flow', 'hr', 'spo2'];

// HTTP SLOs are always active. The WS-specific SLO is only registered
// when we actually open sockets, to avoid evaluating a threshold against
// zero samples.
const thresholds = {
  http_req_failed: ['rate<0.01'],
  http_req_duration: ['p(95)<250'],
};
if (API_TOKEN) {
  thresholds.ws_connecting = ['p(95)<250'];
}

export const options = {
  scenarios: {
    pq1_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      // Linear ramp 0 -> PEAK_VUS over RAMP_MIN, then drain over 1 min.
      stages: [
        { duration: `${RAMP_MIN}m`, target: PEAK_VUS },
        { duration: '1m', target: 0 },
      ],
      exec: 'default',
    },
  },
  thresholds,
};

export function default() {
  // ---- HTTP path (public /api/health; no token required) ----
  const res = http.get(`${BASE_URL}/api/health`);
  check(res, { 'health returns 200': (r) => r.status === 200 });

  // ---- WebSocket path (authenticated; skipped without API_TOKEN) ----
  if (API_TOKEN) {
    const url = `${WS_URL}?token=${API_TOKEN}`;
    const r = ws.connect(url, function (socket) {
      socket.on('open', () => {
        socket.send(
          JSON.stringify({ type: 'subscribe', channels: WS_CHANNELS })
        );
      });
      socket.on('message', () => {
        // Server broadcasts telemetry; we only consume to exercise relay.
      });
      // Exercise the relay with a few frames per VU iteration.
      for (let i = 0; i < 5; i++) {
        socket.send(
          JSON.stringify({ type: 'ping', ts: new Date().toISOString() })
        );
      }
      socket.setTimeout(() => socket.close(), 5000);
    });
    check(r, { 'ws handshake 101': (x) => x && x.status === 101 });
  }

  sleep(1);
}
