Title: srs-status-and-remaining-work-2026-07-29
Date: 2026-07-29T19:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: User request "Determine what work remains against the SRS and actual implementation, then update documentation to properly reflect the current status. Be especially investigative when it comes to the frontend." This log re-baselines project status against SRS v1.1 with emphasis on the frontend, and supersedes the deleted `REMAINING_WORK.md` / `REMAINING_WORK_v1.1.md`.
Summary: Verified the system is broadly code-complete and demo-complete vs SRS v1.1. The README was materially stale: FR-3.15 (LLM/RAG) and FR-3.16 (Scenario Orchestrator + Designer UI) are in fact implemented (backend routes + working ScenarioDesigner + 89 green frontend tests), not "schema only." Frontend investigation surfaced 9 residual gaps (2 partial-implementation, 6 open, 1 measurement-fidelity) plus 2 formal deviations (FR-3.1.3 SciChart, SRS §9 layout). All findings carry file:line evidence.

## 1. Task Reference
User instruction (2026-07-29): reconcile SRS v1.1 against the actual implementation, with particular scrutiny of the React/TypeScript frontend, and update documentation to reflect true status.

## 2. Specification Summary
SRS v1.1 enumerates 8 capability domains and ~50 functional requirements (FR-3.1–FR-3.16), plus NFR-P/M/R/S/U families. The prior `REMAINING_WORK*.md` files were deleted; this document is the authoritative replacement. Backend status is taken from the v1.1 phase logs (`impl-2026-07-29-phase1..phase4-*`, `impl-2026-07-28-pulse-segfault-*`, `impl-2026-07-28-remaining-work-v1.1-reeval`). Frontend status was established by direct source inspection of `frontend/src/**`.

## 3. Methodology
- Read SRS v1.1 in full (731 lines).
- Inspected all frontend source under `frontend/src/` (pages, components, providers, hooks, ScenarioDesigner, AnalyticsResults, App, main, types).
- Grepped the middleware for FR-3.15/FR-3.16 routes (confirmed `api/routes/ai.py`, `api/routes/scenarios.py`, `ai/llm_gateway.py`, `ai/rag.py` are real implementations, not stubs).
- Cross-checked against prior SNDEV impl logs and `git log` (commit `cc512ba` "demo-complete and broadly code-complete against SRS v1.1").
- Referenced `frontend/package.json` dependency set to confirm charting/state libraries.

## 4. Overall Status (Executive Summary)
**BROADLY CODE-COMPLETE & DEMO-COMPLETE against SRS v1.1.**
- Baseline (v1.0) capabilities: implemented & tested.
- Pulse Engine (FR-3.6): real `PyPulse` built, runs, qualified 19/19 IQ/OQ/PQ (R1 closed).
- Advanced modules FR-3.11–FR-3.14: backend implemented, routed, unit-tested.
- **FR-3.15 (LLM/RAG) — IMPLEMENTED** (backend `api/routes/ai.py` + `ai/llm_gateway.py` + `ai/rag.py`; provider abstraction with OpenRouter/Ollama/vLLM; default provider `mock` for safe no-key startup). The README's "🟡 Schema only" row is **WRONG and has been corrected**.
- **FR-3.16 (Scenario Orchestrator + Scenario Designer UI) — IMPLEMENTED** (`api/routes/scenarios.py` + `frontend/src/ScenarioDesigner/ScenarioDesigner.tsx`; NFR-U4 assembly ≤5 interactions verified by `frontend/tests/nfr_u4_scenario_designer.test.tsx`). The README's "🟡 Schema only" row is **WRONG and has been corrected**.
- Frontend: 5 primary surfaces (Telemetry, Microplate, Audit, Admin, Scenario Designer) + Analytics Results viewer; full suite **89/89 vitest tests green** (per `impl-2026-07-29-phase4-nfr-hardening.md`).

### Residual work is frontend-weighted and mostly non-blocking
- 2 items are **partial implementations** of a requirement (FR-3.1.5 trace color; FR-3.9.1 alarm-ack latency).
- 6 items are **open** (mostly minor: a missing well state, a hardcoded non-TLS WS URL, a UI field exceeding an NFR cap, a missing TS types file, limited LLM-output frontend visibility, a measurement-fidelity note).
- 1 item is a **measurement-fidelity observation** (FPS counter measures browser rAF, not chart throughput).
- 2 **formal deviations** recorded separately (see §6).

## 5. Capability / Requirement Status Matrix (frontend emphasis)

| Requirement | Status | Evidence (file:line) | Notes |
|---|---|---|---|
| FR-3.1.1 Canvas/WebGL | ✅ Met | `TelemetryDashboard.tsx:101-113`, `chart-provider.tsx:45` | ECharts Canvas (non-SVG); acceptable per FR-3.1.1 "Canvas or WebGL" |
| FR-3.1.2 60 fps | ⚠️ Partial | `FPSCounter.tsx`, `TelemetryDashboard.tsx:148-152` | LTTB downsampling + rAF FPS readout; see GAP-8 (counter measures rAF, not chart) |
| FR-3.1.3 ECharts+SciChart swappable | ⛔ Deviation | `chart-provider.tsx:15-18` | SciChart removed — see `deviation-2026-07-29-fr-3-1-3-scichart.md` |
| FR-3.1.4 4 channels | ✅ Met | `TelemetryDashboard.tsx:21-28,126-136,255-291` | pressure, flow, HR, SpO₂ |
| FR-3.1.5 alarm visualization | ⚠️ Partial | `TelemetryDashboard.tsx:385-400` | Banner + ack button only; **trace color does NOT change to red** — GAP-1 |
| FR-3.1.6 zoom/pan 5s | ✅ Met | `TelemetryDashboard.tsx:224,293-304` | `dataZoom` `minSpan:5000` |
| FR-3.2.1 CSS Grid 96/384 | ✅ Met | `MicroplateEditor.css:57-63` | `repeat(12,1fr)` / `repeat(24,1fr)` exact per SRS |
| FR-3.2.2 well state binding | ⚠️ Partial | `MicroplateEditor.tsx:21`, `MicroplateEditor.css:90-100` | empty/pending/processed/error only; **'concentration gradient' state missing** — GAP-3 |
| FR-3.2.3 click→FHIR | ✅ Met | `MicroplateEditor.tsx:100-145,542-553` | `fetchObservation(uid)` overlay |
| FR-3.2.4 batch ops | ✅ Met | `MicroplateEditor.tsx:147-294` | drag-select + coordinate parser `A-D, 1-6` |
| FR-3.2.5 import/export | ✅ Met | `MicroplateEditor.tsx:331-460` | CSV + JSON both directions |
| FR-3.9.1 human-factors | ⚠️ Partial | `useHumanFactors.ts:188-245`, `TelemetryDashboard.tsx:90-93` | **Alarm-trigger→ack selection latency NOT emitted by dashboard** (uses `trackInteraction`, not `trackSelectionLatency`); Microplate emits it — GAP-2 |
| FR-3.9.2 uFMEA JSON export | ✅ Met | `useHumanFactors.ts:251-272` | `exportMetrics`/`downloadMetrics` |
| FR-3.9.3 privacy | ✅ Backend | `api/routes/human_factors.py` | endpoint present; pseudonymized storage assumed per route |
| FR-3.15 LLM/RAG | ✅ Met (backend) | `api/routes/ai.py:1-16`, `ai/llm_gateway.py:64` | See GAP-7 for frontend visibility |
| FR-3.16 scenario framework | ✅ Met | `api/routes/scenarios.py`, `ScenarioDesigner.tsx` | Orchestrator + UI implemented |
| FR-3.16.5 Scenario UI | ✅ Met | `ScenarioDesigner.tsx`, `tests/nfr_u4_scenario_designer.test.tsx` | ≤5-interaction assembly verified |
| NFR-U1 alarm ack ≤2 clicks | ✅ Met | `TelemetryDashboard.tsx:392-398` | 1-click acknowledge |
| NFR-U2 keyboard nav | ✅ Met | `MicroplateEditor.tsx:296-329,260-264` | arrow-key well traversal + focus ring |
| NFR-U3 responsive 13–27" | ✅ Met | `MicroplateEditor.css:272-326` | responsive breakpoints |
| NFR-U4 scenario ≤5 interactions | ✅ Met | `tests/nfr_u4_scenario_designer.test.tsx` | verified (exact-5 tightest case) |
| NFR-M2 chart swappable | ⛔ Deviation | `chart-provider.tsx` | interface retained, SciChart absent — see deviation doc |
| NFR-P2 60 fps | ⚠️ Partial | `FPSCounter.tsx` | see GAP-8 |
| NFR-R2 graceful degradation | ✅ Met (UI) | `tests/nfr_r_reliability.test.tsx` | dashboard stays usable w/o Pulse; device telemetry independent |
| NFR-R3 DB reconnect backoff | ✅ Backend | `impl-2026-07-29-phase1-r2-r3.md` | exponential backoff (DB pool) |
| NFR-R4 WS auto-reconnect+replay | ⚠️ Partial | `useWebSocket.ts:80-89,106-113` | **linear backoff, capped at 5 attempts** — GAP-9; replay buffer present |
| NFR-S3 JWT max 1h | ⚠️ UI allows violation | `AdminConsole.tsx:116-124` | **UI permits expiry up to 168h** — GAP-5 (verify backend enforcement) |
| NFR-S4 TLS 1.3 / WSS | ⚠️ Open | `TelemetryDashboard.tsx:96` | **WS URL hardcoded `ws://localhost:8000` (non-TLS, non-configurable)** — GAP-4 |
| SRS §9 `frontend/src/types/fhir.ts` | ⛔ Missing | (file not found) | FHIR parsed inline; TS types module absent — GAP-6 |
| SRS §9 `middleware/src/...` | ⛔ Deviation | (flat layout) | see `deviation-2026-07-29-srs-9-repo-layout.md` |

## 6. Formal Deviations (recorded separately)
- **D-FR-3.1.3** — SciChart.js backend removed; ECharts-only. `SNDEV/docs/deviation-2026-07-29-fr-3-1-3-scichart.md`.
- **D-SRS-9** — flat `middleware/` & `tests/` layout vs nested SRS §9 tree. `SNDEV/docs/deviation-2026-07-29-srs-9-repo-layout.md`.
- (Prior) **D-OQ-6** — EMA step-bound ≤4 → ≤5; `SNDEV/docs/deviation-2026-07-29-oq6-step-bound.md`.

## 7. Open / Partial Frontend Gaps (prioritized)

### GAP-1 (Partial, FR-3.1.5) — alarm trace color not changed to red
`TelemetryDashboard.tsx:385-400` shows an alarm *banner* + *Acknowledge* button, but `checkAlarms()`/`getChartOptions()` never alter the series `lineStyle` color. SRS FR-3.1.5 requires "trace color change to red, optional auditory alert." The banner satisfies the *state* requirement; the *trace* requirement is unmet.
- Fix: in `checkAlarms`, set a red `lineStyle`/`itemStyle` on the offending series via `chartInstance.current.setOption({ series:[{name, lineStyle:{color:'red'}}] })`, and reset on clear.

### GAP-2 (Partial, FR-3.9.1) — alarm-ack selection latency not captured
`TelemetryDashboard.tsx:90-93` `handleAcknowledgeAlarms` calls `trackInteraction('alarm_ack',...)` only. `trackSelectionLatency(startTime, component)` exists (`useHumanFactors.ts:188-207`) and is used by Microplate (`MicroplateEditor.tsx:107-110`), but the dashboard never records the alarm *trigger* timestamp nor emits `trackSelectionLatency` on acknowledge. The primary uFMEA metric (trigger→ack ms) is therefore not collected on the telemetry surface.
- Fix: record `alarmTriggerTimeRef` when `checkAlarms` transitions a channel into alarm; pass it to `trackSelectionLatency` inside `handleAcknowledgeAlarms`.

### GAP-3 (Open, minor, FR-3.2.2) — 'concentration gradient' well state absent
`MicroplateEditor.tsx:21` `WellData.state` is `'empty'|'pending'|'processed'|'error'`; SRS FR-3.2.2 lists "processed, pending, reagent-error, concentration gradient." Add `'concentration_gradient'` with a CSS color (e.g., blue gradient) and import/export handling.

### GAP-4 (Open, NFR-S4) — hardcoded non-TLS WebSocket URL
`TelemetryDashboard.tsx:96` `const wsUrl = 'ws://localhost:8000/api/telemetry/stream'`. For production this violates NFR-S4 (TLS 1.3 / WSS) and is not environment-configurable.
- Fix: derive from `import.meta.env.VITE_WS_URL` (default `wss://<host>/api/telemetry/stream`); mirror the existing `.env.example` pattern.

### GAP-5 (Open, NFR-S3) — Admin UI permits JWT expiry > SRS cap
`AdminConsole.tsx:116-124` `tokenExpiry` range `min=1 max=168` hours; SRS NFR-S3 caps access tokens at 1h (refresh 24h). If the backend enforces the cap this is only a UX inconsistency; if not, it is a compliance gap.
- Fix: clamp UI to ≤24h (and warn if >1h access token), and confirm `api/auth.py` enforces NFR-S3 server-side.

### GAP-6 (Open, minor, SRS §9) — `frontend/src/types/fhir.ts` missing
SRS §9 lists `frontend/src/types/fhir.ts` (FHIR TS types). It does not exist; FHIR is parsed inline (`TelemetryDashboard.tsx:309-337`, `MicroplateEditor.tsx:547-550`). Low risk but breaks the documented structure.
- Fix: extract a `types/fhir.ts` with `Observation`/`DeviceMetric` interfaces and import it in the two consumers.

### GAP-7 (Open, minor, FR-3.15 frontend visibility) — no dedicated LLM-output viewer
FR-3.15.6 requires provenance metadata on stored clinical text. The backend persists it (`api/routes/ai.py` `GET /runs/{run_uid}`), but the frontend surfaces advanced outputs only via `AnalyticsResults.tsx` (FR-3.11–3.14) and embedded in Scenario Designer `aggregated_outputs`. There is no dedicated viewer for `clinical_text_outputs` / `llm_runs` provenance.
- Fix (optional): extend `AnalyticsResults.tsx` (or add a tab) to list `clinical_text_outputs` with provenance (model id, provider, prompt hash, template id, source hash).

### GAP-8 (Observation, NFR-P2) — FPS counter measures browser rAF, not chart throughput
`FPSCounter.tsx:44-131` runs its own `requestAnimationFrame` loop independent of the ECharts render. It reports the browser's animation cadence (≈60 fps even if the chart update is throttled). It is a useful liveness signal but does **not** prove "60 fps WebGL/Canvas rendering of the telemetry chart" (NFR-P2). True verification requires either instrumenting the chart's `setOption` cadence or a browser-level e2e (see GAP-10/HITL-5 in phase4).
- Action: annotate the counter as "UI frame cadence" and rely on PQ-1/PQ-6 (browser/load) for the NFR-P2 claim.

### GAP-9 (Open, minor, NFR-R4) — WS reconnect is linear & capped
`useWebSocket.ts:35,85-88` uses `maxReconnectAttempts=5` and delay `1000 * reconnectAttempts.current` (linear 1s→5s). SRS NFR-R4 says "automatic reconnection" (exponential backoff is specified for the DB pool, NFR-R3, not the WS). After 5 failures the hook gives up silently. For a persistent telemetry link this is weak.
- Fix (recommended): use exponential backoff (`min(30000, 1000*2**n)`) and either remove the attempt cap or make it configurable; surface a persistent "reconnecting…" state.

## 8. Backend Residual (carried from prior phase logs, for completeness)
- FR-3.15 default provider is `mock` (`llm_gateway.py:64`); production requires explicit `LLM_PROVIDER` + key injection (documented; gated Ollama integration test exists).
- PQ-4 (24h soak), PQ-1 (real Locust), PQ-3 (1M rows) are implemented but gated to CI/long-runner (`BIOSYNC_PQ*_DATABASE_URL` / `BASE_URL`), not in the default fast suite — by design.
- R1–R8 roadmap items from `REMAINING_WORK_v1.1.md` are CLOSED per phase1–phase4 impl logs.

## 9. Verification / Evidence
- Frontend source inspection: `frontend/src/**` (all pages/components/providers/hooks read).
- Dependency audit: `frontend/package.json` (echarts only; no scichart).
- Route audit: `middleware/api/routes/{ai,scenarios}.py`, `middleware/ai/{llm_gateway,rag}.py` — real implementations.
- Prior logs: `impl-2026-07-29-phase1-r2-r3.md`, `-phase2-r5-r6.md`, `-phase3-R7-R8.md`, `-phase4-nfr-hardening.md`, `impl-2026-07-28-remaining-work-v1.1-reeval.md`, `deviation-2026-07-29-oq6-step-bound.md`.
- `git log` HEAD: `cc512ba` "demo-complete and broadly code-complete against SRS v1.1"; `8f34504` README Pulse fixes.
- Frontend test suite reported 89/89 green (`impl-2026-07-29-phase4-nfr-hardening.md` §5).

## 10. Recommended Documentation Actions (executed alongside this log)
1. README.md status table: promote FR-3.15 and FR-3.16 from "🟡 Schema only" to "✅ Implemented"; remove `SD/AI/SCN` from the architecture diagram's `planned` class; rewrite "Next priorities" to the residual frontend gaps (GAP-1..GAP-9).
2. `frontend/src/providers/chart-provider.tsx` header comment: repoint the SciChart deviation citation from deleted `REMAINING_WORK.md` to `SNDEV/docs/deviation-2026-07-29-fr-3-1-3-scichart.md`.
3. `DEVELOPMENT_PLAN.md` §2/§3.1/§7.1: repoint "REMAINING_WORK.md §0" references to the new deviation doc.

(No secrets/tokens recorded.)
