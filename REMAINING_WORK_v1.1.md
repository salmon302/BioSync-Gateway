# BioSync-Gateway — Remaining Work Gap Analysis (SRS v1.1)

**Project:** BioSync-Gateway — 2D High-Throughput Medical Telemetry & Laboratory Informatics Middleware
**SRS Reference:** `SRS.md` v1.1 (2026-07-24)
**Prior gap doc:** `REMAINING_WORK.md` (2026-07-22, SRS v1.0) — now superseded
**Audit Date:** 2026-07-27
**Prepared by:** Seth Nenninger (tencent/hy3 Agent)
**Classification:** Implementation — Validation/Audit
**Companion log:** `SNDEV/docs/impl-2026-07-27-srs-v1.1-gap-analysis.md`

> **Method note:** This audit re-verified every claim in the v1.0 `REMAINING_WORK.md` against the *current* code and extended coverage to the v1.1 advanced features (FR-3.11–FR-3.16). Findings are evidence-based (`file:line`). Live test execution was **not** possible in the audit environment (the local `.venv`/`.venv-1` lack `numpy` despite `requirements.txt` pinning `numpy==1.26.4`); qualification status below is from static analysis of the test suite plus the previously reported 142-passing baseline. Full qualification requires a provisioned environment + live PostgreSQL + compiled `PyPulse`.

---

## 0. Executive Summary

The repository has advanced well beyond the 2026-07-22 baseline. **All five previously-claimed "First 5 Actions" are genuinely present in code**, and numerous v1.0 gaps have been closed. The system is **demo-complete and broadly code-complete** against SRS v1.1.

**Verdict:** The dominant remaining work is **(1) deploying the real Kitware Pulse Physiology Engine (`PyPulse`) binary** — until then FR-3.6 and all FR-3.11–FR-3.14 emit *deterministic synthetic* physiology, not authentic Pulse output — and **(2) closing a short list of minor correctness/infra items** plus re-running qualification against the real engine. No major v1.0 functional stubs remain except where they depend on Pulse.

### Top remaining items (priority order)
| # | Item | Severity | SRS |
|:--|:------|:---------|:----|
| R1 | Build & deploy real `PyPulse` binary (multi-stage `Dockerfile.pulse`); remove synthetic fallback dependence | **Blocker (fidelity)** | FR-3.6.1–3.6.5, FR-3.11–3.14 |
| R2 | Enforce DB client-cert TLS by default (`sslmode=verify-full` + `pg_hba` `hostssl clientcert=verify-full`) | Major (security) | NFR-S5 |
| R3 | Configure `uvloop` + remove sync DB writes on the WebSocket relay path | Major (perf) | NFR-P1, NFR-P3, PQ-1, PQ-8 |
| R4 | Re-run IQ-4 / OQ-16 / PQ-2 / PQ-6 against the real engine (currently vacuous) | Major (qualification) | IQ-4, OQ-16, PQ-2, PQ-6 |
| R5 | EMA OQ-6 tolerance: enforce ≤4 steps (currently ≤5) | Minor | FR-3.5.1, OQ-6 |
| R6 | Remove duplicated/unreachable dilution unit-conversion branches | Minor | FR-3.4.4 |
| R7 | LLM provider: default `mock` — wire a real `LLM_PROVIDER`+key for production text generation | Minor (config) | FR-3.15.1, C8 |
| R8 | PQ-4 (24 h ingest soak) test still absent; PQ-1 smoke-only; PQ-3 estimated | Minor (qualification) | PQ-1, PQ-3, PQ-4 |

---

## 1. Verification of Prior "First 5 Actions" — CONFIRMED FIXED

| Claim (v1.0 doc) | Status | Evidence |
|:------|:------|:--------|
| A1 — JWT secret from env, fail-closed | ✅ **Confirmed** | `middleware/api/auth.py:35-63` reads `JWT_SECRET` / `JWT_SECRET_FILE`; `RuntimeError` if unset in production |
| A2 — DB-backed authentication | ✅ **Confirmed** | `auth.py:81,88` require `passlib` in prod; `routes/auth.py` queries `users` table (per v1.0 claim, verified present) |
| A4 — Hash-chain `D_prev` + `R_i` | ✅ **Confirmed** | `engine/hash_chain.py:31-61,138`; `database/migrations/003-triggers.sql:168-173,251-256` hash `H_{i-1}‖T‖U‖D_prev‖D_new‖R_i` |
| A5 — Full append-only trigger coverage | ✅ **Confirmed** | `003-triggers.sql:44-140` covers all 11 SRS §6.1 tables (incl. `patients`, `device_metrics`, `dilution_worklists`, `barcode_indices`, `human_factors_metrics`) |
| B1 — Barcode d==2 rejection | ✅ **Confirmed** | `engine/barcode.py:158,161` → `dist < min_distance` is `'critical'` → `is_valid=False` |

### Other v1.0 gaps now CLOSED (verified)
| Prior gap | Status | Evidence |
|:------|:------|:--------|
| B6 — FHIR POST endpoints don't persist | ✅ **Closed** | `api/routes/fhir.py:114-141` (Observation) & `:198-225` (DeviceMetric) perform real DB writes, return `201` |
| M3 — Barcode not vectorized | ✅ **Closed** | `engine/barcode.py:73,142` use numpy vectorized distance matrix |
| M5 — Barcode 6-base (not 8/10) | ✅ **Closed** | `engine/barcode.py:258` "Illumina TruSeq HT 8-base i7 UDI"; dictionary now 8-base |
| M7 — No LTTB downsampling | ✅ **Closed** | `engine/lttb.py`; `api/routes/telemetry.py:321`; `frontend/src/utils/lttb.ts` + `TelemetryDashboard.tsx:5,148-151` |
| M8 — Microplate I/O asymmetric | ✅ **Closed** | `MicroplateEditor.tsx:332` (CSV in), `:385` (JSON out), `:401` (JSON in), `:433` (CSV out) |
| M9 — Well click no backend fetch | ✅ **Closed** | `MicroplateEditor.tsx:113-129` live `fetchObservation(uid)` via `utils/api` |
| m1 — URS.md / FRS.md missing | ✅ **Closed** | `docs/URS.md`, `docs/FRS.md` present |
| m2 — IQ-2/3/6/7 tests missing | ✅ **Closed** | `tests/test_iq2_python_version.py`, `test_iq3_pgcrypto.py`, `test_iq6_triggers_installed.py`, `test_iq7_alembic_upgrade.py` present |
| m8 — JWT claim `scopes` vs `scope` | ✅ **Closed** | `auth.py:215,266,294` accept both `scope` and `scopes` |
| M11 — DB TLS cert wiring | 🟡 **Partial** | Wiring present (`database.py:33-39`, `docker-compose.yml:53-55`, `test_db_ssl_config.py`) but default `DB_SSLMODE=prefer` (see R2) |

---

## 2. Remaining Work by Severity

### 2.1 Blockers / Fidelity (R1)
- **R1 — Real Pulse Engine not deployed.** `middleware/engine/pulse.py:142-153` now *fails hard* (no silent mock) if `PyPulse` is missing, which is correct behavior. However, the binary must be compiled via the multi-stage `middleware/Dockerfile.pulse` and deployed. Until then every simulation path falls back to **deterministic seeded-random synthesis** (see §3). This does not block *code* completeness but blocks **physiological authenticity** required for FR-3.6 and FR-3.11–FR-3.14 to be meaningful. **Acceptance:** `import PyPulse` succeeds in the runtime image; IQ-4/OQ-16/PQ-2/PQ-6 pass against the real engine.

### 2.2 Major (Security / Performance / Qualification)
- **R2 — DB client-cert TLS not enforced by default.** `middleware/database.py:33-39` assembles `sslmode/sslrootcert/sslcert/sslkey` from env; `tests/.../test_db_ssl_config.py` confirms correct assembly. But `DB_SSLMODE` defaults to `prefer` (test asserts ssl keys absent under `prefer`), and server-side `pg_hba.conf hostssl clientcert=verify-full` is not demonstrated. NFR-S5 requires client-cert auth in addition to password.
- **R3 — WebSocket scaling path.** DEVELOPMENT_PLAN risk #4 (uvloop + no sync DB writes in WS path) is unmitigated: `uvloop` is not configured (grep of `middleware/` returns no `uvloop` import), and the real-time relay historically performs synchronous DB writes. Blocks NFR-P1 (≥100k pts/s), NFR-P3 (≤50 ms relay), PQ-1, PQ-8 under load.
- **R4 — Qualification against mock/absent engine.** IQ-4, OQ-16, PQ-2, PQ-6 currently exercise an absent/`mock` engine; their green status is therefore vacuous until R1 lands.

### 2.3 Minor (Correctness / Config / Qualification)
- **R5 — EMA OQ-6 tolerance.** `engine/signal.py:317` accepts `convergence_step <= 5` with comment "SRS says ≤ 4". SRS OQ-6 requires convergence within 4 steps at α=0.5 step input. Relax to spec or justify deviation.
- **R6 — Dilution dead branches.** `engine/dilution.py:315-369` contain duplicated/unreachable `elif from_unit in mass_units` blocks (the first such branch at `:296` already captures all mass units). Main conversion path (`:296-313`) is reachable and likely correct, but the dead/confused derivation (with self-correcting comments) must be removed. OQ-5 may pass via the live path.
- **R7 — LLM default provider = `mock`.** `ai/llm_gateway.py:37,100,139` default to an offline stub; OpenRouter/Ollama/vLLM routing (`llm_gateway.py:91-99,143`) is genuinely implemented (OpenAI-compatible SDK, swappable via `LLM_PROVIDER` env, satisfying FR-3.15.1/C8). Production needs a real provider + key.
- **R8 — Qualification holes.** PQ-4 (24 h ingest soak, NFR-P4) has **no** test (`test_pq4_alarm_response.py` covers alarm response, not the soak); PQ-1 is smoke-only (`tests/performance/test_pq1_websocket_latency.py` imports a locustfile in CI); PQ-3 is extrapolated from 10k rows (`test_pq3_1m_rows.py` / `test_pq2_hash_chain_perf.py` estimate 1M).
- **SciChart** (FR-3.1.3): removed by **approved deviation** (ECharts-only); chart-provider abstraction retained. No action required.

---

## 3. SRS v1.1 Advanced Feature Status (FR-3.11–FR-3.16)

> All five feature families are **code-complete** (modules + API routes + schemas + Alembic `0007_v1_1_advanced_analytics.py` + dedicated tests). Their *physiological/clinical fidelity* depends on R1 (real Pulse). When PyPulse is absent they run a **deterministic, seeded-random** fallback so endpoints, schemas, and determinism tests still pass.

| FR | Feature | Code status | Fidelity caveat | Evidence |
|:---|:--------|:-----------|:----------------|:--------|
| FR-3.11.1–5 | PK/PD lab loop | ✅ Implemented (routes + `simulation/pkpd.py` + `test_pkpd.py`) | Synthetic PK curves unless real Pulse registered | `api/routes/pkpd.py`, `simulation/pkpd.py` |
| FR-3.12.1–4 | Clinical chemistry generation | ✅ Implemented; combines ClinVar (real client) + synthesized vectors | Vectors synthesized when Pulse absent | `simulation/chemistry.py:6,20,73`; `external/clinvar.py` (real) |
| FR-3.13.1–5 | Digital-twin cohorts | ✅ Implemented; FHIR Observation streams, `synthetic=true` | Trends = seeded random walk around baselines | `simulation/digital_twin.py:12,61` |
| FR-3.14.1–4 | MRD / cfDNA sandbox | ✅ Implemented; stressor inject + cfDNA transfer fn + LOD eval | cfDNA model driven by synthesized state | `simulation/mrd_sandbox.py:27,218` |
| FR-3.15.1–7 | LLM/RAG text gateway | ✅ Provider abstraction real; RAG local templates real; provenance captured | Default `mock` provider (R7) | `ai/llm_gateway.py`, `ai/rag.py`, `rag_templates/`, `api/routes/ai.py`, `test_oq21/oq22` |
| FR-3.16.1–5 | Scenario framework + UI | ✅ Orchestrator + `ScenarioDesigner.tsx` | Inherits Pulse caveat (R1) | `simulation/scenarios.py`, `api/routes/scenarios.py`, `frontend/src/ScenarioDesigner/` |

**Acceptance for "fully met":** Land R1, then re-run `test_oq16/oq21/oq22/oq23`, `test_pq7/pq8`, and the unit tests for each simulation module against the real engine. Determinism (FR-3.16.4) for non-LLM modules is already asserted via seed (`test_oq23_scenario_determinism.py`).

---

## 4. Qualification Test Status (SRS §7)

### 4.1 Coverage (test files present)
| Group | IDs | Files present? | Notes |
|:------|:----|:---------------|:------|
| IQ | 1–7 | ✅ All | `test_iq1..iq7_*` present. IQ-4 runs against absent PyPulse (vacuous until R1). |
| OQ | 1–23 | ✅ All | OQ-1..15 real; OQ-16 mock-engine; OQ-17..20 synthetic-engine; OQ-21/22 real LLM/RAG (mock default); OQ-23 determinism real. |
| PQ | 1–8 | 🟡 Mostly | PQ-1 smoke; PQ-2/6 mock-engine; PQ-3 estimated; PQ-4 **absent** (soak); PQ-5 real; PQ-7/8 present (LLM isolation / integrated scenario). |

### 4.2 Tests that must be re-based on the real engine (R4)
`test_iq4_pulse_engine_init.py`, `test_oq16_state_serialization.py`, `test_pq2_concurrent_simulations.py`, `test_pq6_ventilator_stress.py` — currently green only because the engine is mocked/absent.

### 4.3 Missing / weak qualification
- **PQ-4** (24 h ingest, 0 deadlocks, ≤5% memory growth) — no test file.
- **PQ-1** — `test_pq1_websocket_latency.py` only imports a Locust scenario in CI (smoke); needs a real multi-client load assertion.
- **PQ-3** — `test_pq3_1m_rows.py` / `test_pq2_hash_chain_perf.py` extrapolate from 10k rows; assert against a real 1M-row table (NFR-P4 < 60 s).

---

## 5. Coverage Scorecard (FR / NFR)

### 5.1 Functional Requirements
| ID | Requirement | Status | Evidence |
|:--|:--|:--|:--|
| FR-3.1.1 | Canvas/WebGL (not SVG) | ✅ ECharts Canvas | `chart-provider.tsx`, `TelemetryDashboard.tsx` |
| FR-3.1.2 | 60 fps @ 100k pts/s | 🟡 Addressed via LTTB; unverified under load | `lttb.py`, `telemetry.py:321`, `TelemetryDashboard.tsx:148` |
| FR-3.1.3 | Swappable ECharts/SciChart | 🟡 Approved deviation (ECharts-only) | `chart-provider.tsx` |
| FR-3.1.4 | 4 channels | ✅ | `TelemetryDashboard.tsx` |
| FR-3.1.5 | Alarm → red ≤100 ms | 🟡 Backend eval present; frontend timing unverified | `telemetry.py`, `TelemetryDashboard.tsx` |
| FR-3.1.6 | Zoom 5 s / pan | ✅ | `TelemetryDashboard.tsx` |
| FR-3.2.1–4 | CSS Grid plate, state, click, batch | ✅ | `MicroplateEditor.tsx` |
| FR-3.2.5 | Import/export CSV+JSON | ✅ | `MicroplateEditor.tsx:332,385,401,433` |
| FR-3.3.1–5 | Hamming, d≥3, 8/10-base, pre-pool gate | ✅ (gate timing logic present) | `barcode.py` |
| FR-3.4.1–4 | Dilution solve, 0.5 µL, serial, units | 🟡 Logic OK; dead branches (R6) | `dilution.py` |
| FR-3.5.1–4 | EMA, α defaults, raw+filtered, alarm-on-filtered | 🟡 Tolerance (R5) | `signal.py:317` |
| FR-3.6.1–5 | Pulse Engine | 🔴 Needs real binary (R1) | `pulse.py:142-153` |
| FR-3.7.1–5 | FHIR R4, DeviceMetric, Observation, OpOutcome, Bundle | ✅ | `fhir_validator.py`, `fhir.py` |
| FR-3.8.1–5 | Append-only, scope, hash chain, JWT | ✅ | `003-triggers.sql`, `hash_chain.py`, `auth.py` |
| FR-3.9.1–3 | Human factors, uFMEA export, pseudonymized | ✅ | `useHumanFactors.ts`, `human_factors.py` |
| FR-3.10.1–5 | AccessGUDID, ClinVar, cache, LLM route, RAG repo | ✅ (real clients) | `external/`, `ai/` |
| FR-3.11–3.16 | Advanced analytics + scenarios | ✅ code / 🔴 fidelity (R1) | §3 |

### 5.2 Non-Functional Requirements
| ID | Requirement | Status | Note |
|:--|:--|:--|:--|
| NFR-P1 | ≥100k pts/s ingest | 🟡 Unverified (R3) | uvloop missing |
| NFR-P2 | ≥60 fps render | 🟡 LTTB wired; load unverified | |
| NFR-P3 | ≤200/50 ms response | 🟡 WS sync writes (R3) | |
| NFR-P4 | Hash scan ≤60 s / 1M | 🟡 Estimated (R8) | |
| NFR-P5 | ≤50 ms Pulse step | 🔴 Needs real engine (R1) | |
| NFR-P6 | ≥500 WS conns | 🟡 Unverified (R3) | |
| NFR-P7 | LLM isolation | ✅ Code (async) | `ai/` + `test_pq7` |
| NFR-S1–S4 | 21 CFR Part 11, JWT, TLS, certs | 🟡 S5 partial (R2) | |
| NFR-S5 | DB client-cert | 🟡 Wiring OK, default `prefer` (R2) | |
| NFR-S6 | Immutable audit (DB-level) | ✅ | triggers |
| NFR-S7 | Secrets via env | ✅ | `auth.py` |
| NFR-S8 | LLM keys via env | ✅ | `llm_gateway.py` |
| NFR-R1–R4 | Uptime, graceful deg, reconnect | ⚪ Not exercised | |
| NFR-M1–M5 | Docker, swappable chart/LLM, Alembic, pure-Python | ✅ (M2 layout differs but functional) | |
| NFR-U1–U4 | Alarm ≤2 clicks, keyboard nav, responsive, scenario ≤5 clicks | 🟡 Mostly; scenario UI present | |

---

## 6. Prioritized Remediation Roadmap (Future Development)

### Phase 1 — Physiological Fidelity & Security (highest priority)
| # | Action | Effort | Fix |
|:--|:------|:------|:----|
| R1 | Compile & deploy real `PyPulse` (multi-stage `Dockerfile.pulse`); add CI step that asserts `import PyPulse` in image; flip simulation modules to use real engine when available | L | `middleware/Dockerfile.pulse`, `engine/pulse.py`, `simulation/*.py` |
| R2 | Enforce `DB_SSLMODE=verify-full` by default; document `pg_hba.conf hostssl clientcert=verify-full`; ship cert-gen script wired to Postgres | M | `database.py`, `docker-compose.yml`, `nginx/`/certs |
| R4 | Re-base IQ-4/OQ-16/PQ-2/PQ-6 on real engine; mark as `skipif` only when explicitly in mock CI | S (after R1) | test files |

### Phase 2 — Performance & Correctness
| # | Action | Effort | Fix |
|:--|:------|:------|:----|
| R3 | Add `uvloop` to ASGI server; move WS relay DB writes to async/off-thread; load-test PQ-1/PQ-8 | M | `api/main.py`, `telemetry.py` |
| R5 | Enforce EMA ≤4-step convergence (or formally deviate) | S | `signal.py:317` |
| R6 | Delete duplicated/unreachable dilution branches; add focused unit test | S | `dilution.py:315-369` |

### Phase 3 — Qualification & Config
| # | Action | Effort | Fix |
|:--|:------|:------|:----|
| R7 | Document real `LLM_PROVIDER` setup (OpenRouter/Ollama/vLLM) + key injection; add integration test against a local Ollama | S | `ai/llm_gateway.py`, `.env.example` |
| R8 | Add PQ-4 (24 h soak); promote PQ-1 to real Locust run; run PQ-3 against real 1M rows | M | `tests/performance/` |

### Phase 4 — NFR hardening (lower priority)
- NFR-R (reliability) and NFR-U4 (scenario ≤5 interactions) should be exercised with end-to-end UI tests.
- Confirm `M2` repo-layout deviation from SRS §9 is acceptable for CSV traceability (current `middleware/` flat layout is functional).

---

## 7. Traceability & Sign-off

- This document supersedes `REMAINING_WORK.md` (2026-07-22) for SRS v1.1 scope.
- Companion implementation log: `SNDEV/docs/impl-2026-07-27-srs-v1.1-gap-analysis.md`.
- All prior "First 5 Actions" re-verified and confirmed fixed (§1).

*Prepared for Computer System Validation (CSV) under FDA General Principles of Software Validation. This is the working baseline for the next development phase: physiological-fidelity (R1), security enforcement (R2), and performance qualification (R3/R4/R8).*
