Title: phase4-nfr-hardening
Date: 2026-07-29T00:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: REMAINING_WORK_v1.1.md Phase 4 — NFR hardening (NFR-R reliability, NFR-U4 scenario ≤5 interactions, M2 repo-layout deviation)
Summary: Add end-to-end UI tests exercising NFR-U4 (Scenario Designer ≤5-interaction assembly/execution) and NFR-R (R2 graceful degradation, R4 WS auto-reconnect + replay); confirm the SRS §9 `middleware/src` layout deviation is acceptable for CSV traceability under the flat `middleware/` layout; record ambiguity / human-in-the-loop items.

# Implementation Log — Phase 4 (NFR Hardening)

## 1. Task Reference
- `REMAINING_WORK_v1.1.md` §6 Phase 4 (lower priority):
  - "NFR-R (reliability) and NFR-U4 (scenario ≤5 interactions) should be exercised with end-to-end UI tests."
  - "Confirm `M2` repo-layout deviation from SRS §9 is acceptable for CSV traceability (current `middleware/` flat layout is functional)."
- Companion: `docs/nfr-phase4-traceability.csv` (requirement → test → flat-layout artifact map).

## 2. Specification Summary
- **NFR-U4** (SRS §5.5): "Scenario Designer shall allow a complete scenario (any subset of FR-3.11–FR-3.16) to be assembled and executed in ≤ 5 user interactions from the main console." The `ScenarioDesigner.tsx` UI pre-selects all 5 feature modules by default.
- **NFR-R2** (SRS §5.3): "Graceful degradation: if Pulse Engine is unavailable, the dashboard shall continue to display live device telemetry." UI surface = dashboard must remain usable and render telemetry when the WS source is degraded.
- **NFR-R4** (SRS §5.3): "WebSocket disconnection shall trigger automatic reconnection with message replay for missed data points." Implemented in `frontend/src/hooks/useWebSocket.ts`.
- **M2 deviation**: SRS §9 documents `middleware/src/api/...`, `middleware/src/engine/...`, `middleware/src/db/...`. The actual repo is flat: `middleware/api`, `middleware/engine`, `middleware/simulation`, `middleware/ai`, `middleware/external`, `middleware/database.py`. CSV traceability must remain intact.

## 3. Implementation Notes
### 3.1 New end-to-end UI tests (all PASS; full frontend suite 89/89 green)
- `frontend/tests/nfr_u4_scenario_designer.test.tsx` (4 tests):
  - Minimal path: single click on "Create & Run Scenario" executes the default scenario (1 interaction ≤ 5).
  - Tightest valid custom subset: deselect 4 of 5 modules + click run = **exactly 5 interactions** (mathematically proves the budget holds for every non-empty subset given the all-selected default).
  - From the main console: click the Navigation "Scenario Designer" link + click run = 2 interactions.
  - Full assembly: name + seed + downstream endpoint + run = 4 interactions; asserts the downstream endpoint config is forwarded to `createScenario`.
  - Mocks the API boundary (`createScenario`/`runScenario`) and asserts real end-to-end rendering of results + determinism hashes.
- `frontend/tests/nfr_r_reliability.test.tsx` (5 tests):
  - **NFR-R2 (3 tests)**: dashboard stays usable (controls present, no crash) when the WS never opens and when a start attempt fails; live device telemetry renders on connect (data path independent of Pulse).
  - **NFR-R4 (2 tests)**: auto-reconnect after a server drop is visible at the UI and continues streaming into the same dashboard (Data Points 1 → 2 across the reconnect); message-replay buffer is flushed on reopen (verified via a small `useWebSocket` harness component).
- Methodology note: the repo's established UI harness is **vitest + jsdom + @testing-library/react + user-event** (no browser e2e harness exists). These are component-level integration tests (real components, real DOM, mocked network) — see ambiguity #5.

### 3.2 M2 layout-deviation confirmation (acceptable for CSV traceability)
Evidence gathered:
- `middleware/src` does **not** exist (`Test-Path` = False).
- Repo-wide grep for `middleware/src`, `src/api`, `src/engine`, `src/simulation` across `*.yml,*.yaml,*.py,*.toml,*.cfg,Dockerfile*` returned **0 matches** — the SRS §9 nesting appears nowhere in build/config/code.
- Build uses the flat layout: `middleware/Dockerfile` CMD `uvicorn api.main:app`; `docker-compose.yml` `command: alembic upgrade head && uvicorn api.main:app ...`; build context `./middleware`.
- All §9-enumerated modules exist functionally under the flat layout: `middleware/api/routes/telemetry.py`, `middleware/engine/pulse.py` (+`pulse_bridge.py`), `middleware/simulation/scenarios.py` (+`pkpd/chemistry/digital_twin/mrd_sandbox`), `middleware/ai/llm_gateway.py`/`rag.py`, `middleware/external/clinvar.py`; DB layer at `middleware/database.py` + `middleware/models.py` + `middleware/alembic/`.
- Qualification tests preserve their **IDs** (filenames `test_iq*`, `test_oq*`, `test_pq*`), so requirement→test traceability is by stable identifier, not directory path.
- `tests/` itself also deviates from SRS §9's `tests/IQ|OQ|PQ/` subfolders (flat prefix-named files + `integration/`,`performance/`,`unit/` subfolders) — same conclusion: IDs preserved, traceability intact.

**Conclusion:** The deviation is **documentation-only** (SRS §9 is descriptive, not a normative functional requirement) and does **not** impair CSV traceability. Acceptance is conditional on a formally recorded deviation memo and ideally a future SRS patch reflecting the actual layout (human-in-the-loop — see §4).

## 4. Ambiguity / Human-in-the-Loop (HITL) register
1. **NFR-U4 interaction-count definition (ambiguity).** The "≤5 interactions" bound holds for any *non-empty* module subset given the all-selected default, but is *tight* (exactly 5) when selecting a single module, and would be exceeded if an operator toggles modules back and forth (changes their mind). SRS §5.5 does not state whether "interactions" means net final selections or all clicks. **HITL:** QA/validation lead to ratify the interpretation (net assembly) and, if desired, tighten SRS wording; the tests assert the one-shot assembly path.
2. **NFR-R2 Pulse-specific guarantee not observable at the UI.** The front end cannot distinguish Pulse-originated from device-originated telemetry; it only renders whatever the WS delivers. The UI test verifies graceful degradation (no crash, controls intact, device telemetry renders when connected) but cannot assert, at the presentation layer, "Pulse down → device telemetry continues." **HITL:** confirm the backend data path (`middleware/api/routes/telemetry.py`) serves device telemetry when Pulse is unavailable (C2/C7 synthetic path) via code review or a backend integration test.
3. **NFR-R1 (uptime 99.9%) and NFR-R3 (DB-pool exponential-backoff reconnect) have no UI surface.** They are backend/infrastructure concerns (SQLAlchemy pool, deployment SLO). **HITL:** verify via connection-pool code review + a chaos/disconnect test (R3) and production monitoring/SLO dashboards (R1). Not exercisable by UI tests — by design.
4. **M2 deviation formal closure.** Acceptance for CSV is conditional on a recorded deviation (e.g., `SNDEV/docs/deviation-2026-07-29-repo-layout.md` or equivalent) signed off by the QA/validation lead, mirroring the existing OQ-6 step-bound deviation pattern. **HITL:** QA approval before CSV release.
5. **"End-to-end UI" scope (jsdom vs. real browser).** The repo's only UI harness is vitest+jsdom; there is no Playwright/Cypress browser-e2e. These tests mount real components against a live DOM with the network boundary mocked. For stricter CSV "end-to-end" (real browser driving a live backend), a Playwright suite would be required. **HITL:** decide whether browser-level e2e is in scope for CSV; if so, add a Playwright harness (new dependency, CI browser install) as a follow-up.

## 5. Verification
- `cd frontend && npx vitest run tests/nfr_u4_scenario_designer.test.tsx tests/nfr_r_reliability.test.tsx` → **9 passed**.
- Full frontend suite `npx vitest run` → **89 passed (10 files)**, no regressions.
- M2 evidence: grep (0 hits on `middleware/src`), `Test-Path middleware/src` = False, Dockerfile/compose inspection (flat layout built).

*Linked artifacts: `docs/nfr-phase4-traceability.csv`, `frontend/tests/nfr_u4_scenario_designer.test.tsx`, `frontend/tests/nfr_r_reliability.test.tsx`. Updates `REMAINING_WORK_v1.1.md` §6 Phase 4 to CLOSED.*
