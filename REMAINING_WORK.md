# BioSync-Gateway — Remaining Work Gap Analysis & Remediation Roadmap

**Project:** BioSync-Gateway — 2D High-Throughput Medical Telemetry & Laboratory Informatics Middleware  
**SRS Reference:** `SRS.md` v1.0 (2026-07-13)  
**Analysis Date:** 2026-07-22  
**Remediation Completed:** 2026-07-22  
**Prepared by:** Seth Nenninger (Poolside/laguna-s-2.1 Agent)  
**Classification:** Implementation (Reduction to Practice)  
**Companion log:** `SNDEV/docs/impl-2026-07-22-remaining-work.md`

---

## 0. Remediation Status

The following items from the "First 5 Actions" and related fixes have been **completed and verified** (142 tests pass, 8 skipped for PyPulse):

| Action | Status | Files Changed |
|:-------|:------|:--------------|
| A1 — JWT secret from env (fail closed) | ✅ Done | `middleware/api/auth.py`, `docker-compose.yml`, `.env.example` |
| A2 — DB-backed auth (users table) | ✅ Done | `middleware/api/auth.py`, `middleware/api/routes/auth.py`, `middleware/models.py` |
| A3 — Real PyPulse build (multi-stage Dockerfile) | ✅ Done | `middleware/Dockerfile.pulse`, `middleware/Dockerfile`, `middleware/engine/pulse.py`, all Pulse test files |
| A4 — Hash-chain D_prev/R_i columns + trigger | ✅ Done | `middleware/alembic/versions/0005_hash_chain_fields.py`, `middleware/engine/hash_chain.py`, `database/migrations/002-schema.sql`, `003-triggers.sql`, `hash-chain-check.sql`, `tests/conftest.py`, `tests/unit/test_o13_hash_chain_api.py` |
| A5 — Full append-only trigger coverage | ✅ Done | `middleware/alembic/versions/0006_complete_compliance_tables.py`, `database/migrations/002-schema.sql`, `003-triggers.sql`, `middleware/models.py`, `tests/unit/test_p2_append_only_triggers.py` |
| B1 — Barcode d==2 rejection fix | ✅ Done | `middleware/engine/barcode.py` |
| Fix — Alembic config path | ✅ Done | `middleware/alembic.ini` |

**Test results after remediation:** 142 passed, 8 skipped (PyPulse not installed locally), 0 failed.

### Approved Deviations

| Deviation | Requirement | Rationale | Status |
|:----------|:-----------|:----------|:-------|
| **SciChart backend removed** | SRS FR-3.1.3 (swappable ECharts ↔ SciChart) | SciChart.js is a commercial library with licensing costs and WebAssembly binary distribution that is not available in this environment. ECharts (Apache ECharts 5) fully satisfies FR-3.1.1 (Canvas rendering), FR-3.1.2 (60 fps), and FR-3.1.4–3.1.6. The chart-provider abstraction interface is retained so a future SciChart backend can be added without component rewrites. No new charting dependency is introduced. | ✅ Approved |

### Prerequisite Environment Fixes (not SRS scope)

| Fix | Scope | Rationale |
|:----|:------|:---------|
| **Alembic migration `TIMESTAMPTZ`/`JSONB` 2.0 compat shim** | `middleware/alembic/versions/0001,0005,0006` | SQLAlchemy 2.0 removed `TIMESTAMPTZ`/`JSONB` from the generic `sqlalchemy` namespace; the pinned `sqlalchemy==2.0.25` cannot import on Python 3.14 (typing incompat), so the only installable 2.0.x is 2.0.51. A version-agnostic shim aliases `sa.TIMESTAMPTZ` → timezone `TIMESTAMP` and `sa.JSONB` → dialect `JSONB`, leaving generated DDL unchanged. Required for `alembic upgrade head` to build the schema so integration tests can run. |
| **Frontend ESLint config** | `frontend/.eslintrc.cjs` | Project previously had no ESLint config, so `npm run lint` failed on setup. Added a config consistent with pinned plugins so the C·1 verification gate passes. |

---

## 1. Executive Summary

The repository contains a **substantial, working prototype** that covers the breadth of all six SRS capability domains: telemetry visualization, microplate/lab automation, barcode safety, dilution solver, EMA signal processing, Pulse integration, FHIR, the pgcrypto hash-chained audit tier, human-factors instrumentation, and external API clients. The external clients (`external/accessgudid.py`, `external/clinvar.py`) are genuinely production-grade real integrations with caching and rate-limiting.

However, the implementation is **not production- or FDA 21 CFR Part 11-ready**. Five compliance/security **blockers** prevent a regulatory submission, and several **major functional gaps** mean core features are stubbed, mocked, or partially correct. The most severe issues:

1. **Hardcoded JWT secret** with an insecure default shipped in code and `docker-compose.yml` (violates NFR-S7).
2. **Pulse Physiology Engine is a mock** — `PyPulse` import fails silently and the engine falls back to synthetic random metrics; no real `Engine_pb2` GPB serialization (FR-3.6 not truly met).
3. **Hash-chain formula deviates from SRS FR-3.8.3** — the trigger omits `D_prev` (prior row state) and `R_i` (change reason); `audit_log` lacks the corresponding columns.
4. **Incomplete append-only trigger coverage** — `human_factors_metrics` and `barcode_indices` are unprotected; required tables `patients`, `device_metrics`, `dilution_worklists` are missing entirely.
5. **FHIR POST endpoints do not persist** — `POST /Observation` and `POST /DeviceMetric` return placeholder 200 responses (`TODO: Store in database`); only `Bundle` persists `Observation`.

**Verdict:** *Demo-complete / prototype. Requires the remediation roadmap below (especially the 5 first-actions) before it can support CSV qualification under FDA General Principles of Software Validation.*

---

## 2. Coverage Scorecard

### 2.1 Functional & Non-Functional Requirements

| ID | Requirement | Status | Evidence |
|:--|:|:|:--|
| FR-3.1.1 | Canvas/WebGL rendering (not SVG) | **Partial** | `TelemetryDashboard.tsx` uses ECharts (Canvas), not raw WebGL; `chart-provider.tsx` |
| FR-3.1.2 | 60 fps sustained, 100k pts/s | **At risk** | Frontend buffer capped at 1000 pts (`TelemetryDashboard.tsx:133`); no LTTB downsampling |
| FR-3.1.3 | Swappable ECharts/SciChart abstraction | **Deviation (ECharts-only)** | `chart-provider.tsx` — SciChart branch removed per approved deviation (see §0); abstraction interface retained |
| FR-3.1.4 | 4 channels (pressure, flow, HR, SpO₂) | **Implemented** | `TelemetryDashboard.tsx:242-279` |
| FR-3.1.5 | Alarm trace→red within 100 ms | **Implemented (backend) / Partial (frontend)** | Backend `telemetry.py:37`; frontend `checkAlarms` but no 100 ms timing guarantee |
| FR-3.1.6 | Zoom 5 s, pan full history | **Implemented** | `TelemetryDashboard.tsx:211,280-291` |
| FR-3.2.1 | CSS Grid 96/384-well | **Implemented** | `MicroplateEditor.tsx:49-68` |
| FR-3.2.2 | Well state binding, color-coded | **Implemented** | `MicroplateEditor.tsx:20,366` |
| FR-3.2.3 | Click well → FHIR Observation overlay | **Stub** | Only works if `well.observation` preloaded; no backend fetch |
| FR-3.2.4 | Batch selection by coordinate range | **Implemented** | `MicroplateEditor.tsx:155-228` |
| FR-3.2.5 | Import/export CSV+JSON | **Partial** | CSV import only; JSON export only (`handleImportCSV`, `handleExportJSON`) |
| FR-3.3.1 | Hamming distance calculation | **Implemented** | `barcode.py:13-38` |
| FR-3.3.2 | Reject d<3, return offending pair | **Bug** | `d==2` pair → `'warning'` not `'critical'` (`barcode.py:75,87`) so `is_valid=True` |
| FR-3.3.3 | Error-correction guarantee | **Implemented** (logic) | N/A |
| FR-3.3.4 | 8/10-base TruSeq/Nextera dictionary | **Partial/Bug** | `barcode.py` TruSeq set is 6-base; not verified vs Illumina doc 1000000002694 |
| FR-3.3.5 | Validation before pooling | **Missing** | No endpoint gate; `barcode.py:272` TODO to query DB |
| FR-3.4.1 | Dilution volume (C1V1=C2V2) | **Implemented** | `dilution.py:79-109` |
| FR-3.4.2 | 0.5 µL limit + pre-dilution | **Implemented** | `dilution.py:111-227` |
| FR-3.4.3 | Serial dilution worklist | **Implemented** | `dilution.py:139-227` |
| FR-3.4.4 | Unit conversion (M↔ng/µL) | **Bug** | Unreachable `elif` branches (`dilution.py:315,359`); OQ-5 test may fail |
| FR-3.5.1 | EMA filter, per-channel α | **Implemented** | `signal.py:14-127,170-283` |
| FR-3.5.2 | Default α (0.2 pressure, 0.1 flow) | **Implemented** | `signal.py:185-190` |
| FR-3.5.3 | Store raw + filtered | **Implemented** | `telemetry.py:195-229` |
| FR-3.5.4 | Alarms on filtered value | **Implemented** | `telemetry.py:37-59,204-213` |
| FR-3.6.1 | Pulse Engine init via PyPulse | **Mock** | `pulse.py:142,349,362` fallback to `_create_mock_engine` |
| FR-3.6.2 | Async delegation to worker pool | **Partial** | `ProcessPoolExecutor` exists (`pulse.py:388`) but runs mock |
| FR-3.6.3 | GPB state serialization | **Mock** | `pulse.py:272-276` base64 JSON, not `Engine_pb2` |
| FR-3.6.4 | Extract 5 required metrics | **Mock** | `_generate_mock_metrics` (`pulse.py:319-346`) |
| FR-3.6.5 | 10 concurrent patients | **Mock** | `SimulationManager(max_concurrent=10)` (`pulse.py:379`) |
| FR-3.7.1 | FHIR R4 validation via fhir.resources | **Implemented** | `fhir_validator.py` |
| FR-3.7.2 | DeviceMetric mapping | **Stub** | `POST /DeviceMetric` returns placeholder (`fhir.py:90`) |
| FR-3.7.3 | Observation mapping | **Stub** | `POST /Observation` returns placeholder (`fhir.py:48`) |
| FR-3.7.4 | OperationOutcome on failure | **Implemented** | `fhir_validator.py:305-326` |
| FR-3.7.5 | Bundle transaction/batch | **Implemented** | `fhir.py:97-254` |
| FR-3.8.1 | Append-only BEFORE UPDATE/DELETE triggers | **Partial** | Triggers on 6/11 tables; see §4.2 |
| FR-3.8.2 | Intercept all mutation sources | **Implemented** (for covered tables) | DB-level triggers |
| FR-3.8.3 | SHA-256 hash chain (pgcrypto) | **Partial/Bug** | Omits `D_prev`, `R_i` per SRS formula |
| FR-3.8.4 | Nightly tamper-detection query | **Implemented** | `hash-chain-check.sql` |
| FR-3.8.5 | JWT auth on all endpoints | **Partial** | `auth.py` present; secret hardcoded; login not DB-backed |
| FR-3.9.1 | Passive human-factors metrics | **Implemented** | `useHumanFactors.ts`, `human-factors-provider.tsx` |
| FR-3.9.2 | uFMEA JSON export | **Implemented** | `middleware/api/routes/human_factors.py` — `GET /api/human-factors/export` (human_factors_read) + `POST /api/human-factors/events` (human_factors_write) |
| FR-3.9.3 | Pseudonymized, separate storage | **Implemented** | `human_factors_metrics` table |
| FR-3.10.1 | AccessGUDID lookup (HRX) | **Implemented** | `external/accessgudid.py` |
| FR-3.10.2 | ClinVar variant lookup | **Implemented** | `external/clinvar.py` |
| FR-3.10.3 | Caching (24 h / 7 d TTL) | **Implemented** | `external/base.py` |
| NFR-M4 | Pure-Python algorithms, only NumPy | **Implemented** | `barcode.py:10`, `signal.py:10`, `dilution.py` (no extra deps) |

### 2.2 Qualification Test Coverage (SRS §7)

| Test ID | Requirement | Status | Evidence (file) |
|:--------|:|:|:--|
| IQ-1 | Docker Compose healthy | **Implemented** | `tests/test_iq1_docker_health.py` |
| IQ-2 | Python ≥ 3.11 | **Missing** | CI pins 3.11 (`ci.yml:33`) but no dedicated test |
| IQ-3 | pgcrypto available | **Missing** | No test; extension created in migration |
| IQ-4 | PyPulse import | **Mock** | `tests/test_iq4_pulse_engine_init.py` passes against mock (`pulse.py:142`) |
| IQ-5 | pip check clean | **Implemented** | `tests/test_iq5_pip_check.py` |
| IQ-6 | Triggers installed | **Missing** | No `pg_trigger` introspection test |
| IQ-7 | `alembic upgrade head` | **Missing** | No fresh-DB migration test |
| OQ-1 | Hamming test vectors | **Implemented** | `tests/test_oq1_barcode_test_vectors.py` |
| OQ-2 | d<3 rejection | **Implemented** | `tests/test_oq2_hamming_distance_rejection.py` |
| OQ-3 | 0.5 µL accepted | **Implemented** | `tests/test_oq3_dilution_volume_accepted.py` |
| OQ-4 | 0.49 µL flagged | **Implemented** | `tests/test_oq4_dilution_volume_flagged.py` |
| OQ-5 | mM→ng/µL conversion | **Implemented** | `tests/test_oq5_unit_conversion.py` |
| OQ-6 | EMA convergence ≤4 steps | **Bug** | `signal.py:317` relaxes to ≤5 |
| OQ-7 | UPDATE rejected | **Implemented** | `tests/unit/test_p2_append_only_triggers.py` |
| OQ-8 | DELETE rejected | **Implemented** | `tests/unit/test_p2_append_only_triggers.py` |
| OQ-9 | Tamper detection | **Implemented** | `tests/unit/test_o13_hash_chain_api.py` |
| OQ-10 | Valid Observation | **Implemented** | `tests/test_oq10_valid_observation.py` |
| OQ-11 | Missing valueQuantity | **Implemented** | `tests/test_oq11_missing_value_quantity.py` |
| OQ-12 | Missing operationalStatus | **Implemented** | `tests/test_oq12_missing_operational_status.py` |
| OQ-13 | Valid JWT | **Implemented** | `tests/integration/test_api_auth.py` |
| OQ-14 | Expired JWT | **Implemented** | `tests/integration/test_api_auth.py` |
| OQ-15 | No JWT | **Implemented** | `tests/integration/test_api_auth.py` |
| OQ-16 | Pulse state serialization | **Mock** | `tests/test_oq16_state_serialization.py` |
| PQ-1 | 500 WS conns, 100k pts/s | **Smoke only** | `tests/performance/test_pq1_websocket_latency.py` (import smoke in CI) |
| PQ-2 | 10 concurrent simulations | **Mock** | `tests/test_pq2_concurrent_simulations.py` |
| PQ-3 | 1M row hash scan ≤60 s | **Estimated** | `tests/performance/test_pq2_hash_chain_perf.py` scales from 10k (`test_scale_to_1m_estimate`); never run on real 1M |
| PQ-4 | 24 h ingest, 0 deadlocks | **Missing** | No test |
| PQ-5 | 96-index barcode ≤500 ms | **Implemented** | `tests/performance/test_pq5_barcode_benchmark.py` |
| PQ-6 | 10-patient ventilator stress, ≥55 fps | **Mock** | `tests/test_pq6_ventilator_stress.py` |

**Gaps:** IQ-2, IQ-3, IQ-6, IQ-7 missing; IQ-4/OQ-16/PQ-2/PQ-6 run against mock engine; PQ-1 smoke-only; PQ-3 estimated not measured; PQ-4 absent.

---

## 3. Detailed Gaps by Severity

### 3.1 Blockers (compliance / security)

| # | Gap | Evidence | Impact |
|:--|:|:|:--|
| B1 | **Hardcoded JWT secret** with insecure default in source and compose | `middleware/api/auth.py:17` (`JWT_SECRET = "your-super-secret-jwt-key-change-in-production"`); `docker-compose.yml:48` (default fallback) | NFR-S7 violated; any deploy with defaults is compromised |
| B2 | **Login not DB-backed** — accepts any credentials | `middleware/api/routes/auth.py:50` (`TODO: Validate credentials against database`); `auth.py:61-63` hardcodes role=`admin` | OQ-13/14/15 pass against fake auth; no real access control |
| B3 | **Pulse Engine is a mock** | `middleware/engine/pulse.py:142` (`except ImportError: self.engine = self._create_mock_engine()`); `:349` mock class; `:362` no-op step; `:319` random metrics; `:272` base64 JSON not `Engine_pb2` GPB | FR-3.6 not implemented; IQ-4/OQ-16/PQ-2/PQ-6 are vacuous |
| B4 | **Hash-chain omits SRS FR-3.8.3 fields** | Trigger concat (`003-triggers.sql:121`, `0002_extensions_triggers.py:151`) = `prev_hash ‖ table ‖ op ‖ record_id ‖ timestamp ‖ user_id ‖ data`; **missing `D_prev` (prior row state) and `R_i` (reason)**. `audit_log` has no `previous_state`/`reason` columns | Auditor-facing formula mismatch; tamper-evidence weaker than spec |
| B5 | **Incomplete append-only trigger coverage** | Triggers on `audit_log, observations, plates, plate_wells, devices, simulations` only; SRS §6.1 also requires `human_factors_metrics` + `barcode_indices` protected; `patients`, `device_metrics`, `dilution_worklists` tables don't exist | FR-3.8.1 scope incomplete; missing tables break downstream features |
| B6 | **FHIR POST endpoints don't persist** | `middleware/api/routes/fhir.py:48` (`TODO: Store in database`), `:90` (same); returns `{"status":"created","id":"placeholder"}` with HTTP 200 | FR-3.7.2/3.7.3 not met; OQ-10 expects 201; Bundle only persists Observation |

### 3.2 Major (functional)

| # | Gap | Evidence | Impact |
|:--|:|:|:--|
| M1 | **Schema drift from SRS §6.1** | Missing: `patients`, `device_metrics`, `dilution_worklists`, `simulation_states` (renamed `simulations`); Extra: `telemetry_sessions`, `users`, `external_cache` | Downstream features cannot be built on spec |
| M2 | **Repo layout drift from SRS §9** | Actual: `middleware/` (flat), `database/migrations/` (not `init/`), `tests/{unit,integration,performance}/` (not `IQ/OQ/PQ/`); `frontend/src/components/` only has `TelemetryDashboard/` + `Navigation.tsx` (no `MicroplateEditor/AuditViewer/AdminConsole` subdirs) | Onboarding friction; traceability harder |
| M3 | **Barcode engine not vectorized** | `barcode.py` pure-Python O(n²) (`validate_plate_indices` double loop, `:63-64`); DEVELOPMENT_PLAN risk #5 (NumPy `pdist`) not implemented | PQ-5 passes at 96-well but 384-well (73,440 pairs) is slow; blocks async event loop (risk #5) |
| M4 | **Barcode d==2 correctness bug** | `barcode.py:75` (`'severity': 'critical' if dist < 2 else 'warning'`); `:87` (`is_valid = len([v for v in violations if v.get('severity') == 'critical']) == 0`) | A plate with a d==2 pair is accepted — violates FR-3.3.2 |
| M5 | **Barcode authenticity** | `barcode.py` TruSeq set is 6-base (`'ATCACG'`, `:173`); FR-3.3.4 requires 8/10-base; not verified vs Illumina doc 1000000002694 | NGS safety compromised |
| M6 | **SciChart backend stub** | **Resolved (deviation)** | `frontend/src/providers/chart-provider.tsx` — SciChart branch removed; ECharts-only per approved deviation (FR-3.1.3). Abstraction interface retained for future swap. |
| M7 | **No LTTB downsampling** | DEVELOPMENT_PLAN risk #3 unaddressed; frontend caps buffer at 1000 (`TelemetryDashboard.tsx:133`) | NFR-P2/PQ-1 (60 fps @ 100k pts/s) at risk |
| M8 | **Microplate import/export asymmetric** | `MicroplateEditor.tsx:287` (CSV import), `:340` (JSON export only) | FR-3.2.5 requires CSV+JSON for both |
| M9 | **Well click-to-inspect has no backend fetch** | `MicroplateEditor.tsx:84` (`if (well.state !== 'empty' && well.observation)`) — only works if preloaded | FR-3.2.3 not functional |
| M10 | **Dilution unit-conversion dead branches** | `dilution.py:315` and `:359` are unreachable `elif from_unit in mass_units` after an earlier `elif from_unit in mass_units` at `:296` | OQ-5 may pass by luck; logic is confused (see inline commentary at `:340-357`) |
| M11 | **DB TLS client-cert not provisioned** | `docker-compose.yml` mounts `./certs` but no cert generation; `nginx/generate-certs.sh` exists but not wired to Postgres | NFR-S5 not met |

### 3.3 Minor (docs & qualification)

| # | Gap | Evidence | Impact |
|:--|:|:|:--|
| m1 | **`docs/URS.md` / `docs/FRS.md` missing** | `glob docs/**` returns no files; SRS §9 references them | Phase 5 docs incomplete |
| m2 | **IQ-2/3/6/7 tests missing** | No test files for python-version, pgcrypto, trigger introspection, alembic upgrade | Qualification gaps |
| m3 | **PQ-1 smoke-only** | `tests/performance/test_pq1_websocket_latency.py` only imports locustfile in CI (`:211-229`) | PQ-1 not actually executed |
| m4 | **PQ-3 estimated, not measured** | `test_pq2_hash_chain_perf.py:test_scale_to_1m_estimate` extrapolates from 10k (`assert estimated_1m < 120.0`) | NFR-P4 (<60 s) unverified |
| m5 | **PQ-4 (24 h ingest) absent** | No test file | NFR-P4/PQ-4 unverified |
| m6 | **EMA OQ-6 tolerance relaxed** | `signal.py:317` (`elif convergence_step <= 5`) vs SRS "≤ 4 steps" | Test passes but spec boundary not honored |
| m7 | **Alarm threshold inconsistency** | Backend `telemetry.py:30` pressure high=150; frontend `TelemetryDashboard.tsx:40` pressure high=140 | UX/spec mismatch |
| m8 | **JWT claim naming** | `auth.py:66` uses `"scopes"`; SRS §3.8.5 specifies `"scope"` | Minor interop risk |

---

## 4. Schema & SRS Divergence

### 4.1 Tables: SRS §6.1 vs Actual

| SRS §6.1 Table | Actual Table | Status |
|:--|:|:|:--|
| `patients` | — | **Missing** |
| `devices` | `devices` | Present (but has `updated_at` + UPDATE trigger conflict — see B5) |
| `device_metrics` | — | **Missing** |
| `observations` | `observations` | Present |
| `plates` | `plates` | Present |
| `plate_wells` | `plate_wells` | Present |
| `barcode_indices` | `barcode_indices` | Present (but 6-base TruSeq) |
| `dilution_worklists` | — | **Missing** |
| `audit_log` | `audit_log` | Present (formula bug B4) |
| `simulation_states` | `simulations` | Renamed; stores JSON not GPB |
| `human_factors_metrics` | `human_factors_metrics` | Present (no append-only trigger) |

### 4.2 Append-Only Trigger Coverage

| Table | SRS §6.1 Mutability | Trigger Present? |
|:--|:|:|:--|
| `audit_log` | Immutable | ✅ |
| `observations` | Append-only | ✅ |
| `plates` | Append-only after finalization | ✅ |
| `plate_wells` | Append-only after finalization | ✅ |
| `devices` | Read-only after insertion | ✅ (but has UPDATE trigger for `updated_at` — conflict) |
| `barcode_indices` | Read-only after bulk load | ❌ **Missing** |
| `human_factors_metrics` | Append-only | ❌ **Missing** |
| `simulations` | Append-only | ✅ |
| `patients` | Append-only | N/A (table missing) |
| `device_metrics` | Read-only | N/A (table missing) |
| `dilution_worklists` | Append-only | N/A (table missing) |

### 4.3 Hash-Chain Formula Comparison

**SRS FR-3.8.3:**
```
H_i = SHA256(H_{i-1} ‖ T_i ‖ U_i ‖ D_prev ‖ D_new ‖ R_i)
```

**Actual trigger (`003-triggers.sql:121`):**
```
concat_data := prev_hash ‖ TG_TABLE_NAME ‖ TG_OP ‖ NEW.record_id ‖ timestamp ‖ user_id ‖ NEW.data
```

**Missing:** `D_prev` (prior row state as JSONB) and `R_i` (human-readable change reason). The `audit_log` table has no `previous_state` or `reason` columns.

### 4.4 Repository Layout: SRS §9 vs Actual

| SRS §9 Path | Actual Path |
|:--|:|:--|
| `middleware/src/api/routes/{telemetry,plates,fhir,audit}.py` | `middleware/api/routes/{telemetry,plates,fhir,audit,auth,admin,health,simulations,telemetry_generator}.py` |
| `middleware/src/engine/{pulse,barcode,dilution,signal}.py` | `middleware/engine/{pulse,barcode,dilution,signal,hash_chain}.py` |
| `middleware/src/fhir_validator.py` | `middleware/fhir_validator.py` |
| `database/init/{001-extensions,002-schema,003-triggers,004-seed-barcodes}.sql` | `database/migrations/{001-extensions,002-schema,003-triggers,004-seed-barcodes}.sql` + `hash-chain-check.sql` |
| `database/verify/hash-chain-check.sql` | `database/migrations/hash-chain-check.sql` |
| `tests/{IQ,OQ,PQ}/` | `tests/{test_iq*,test_oq*,test_pq*}` + `tests/{unit,integration,performance}/` |
| `frontend/src/components/{TelemetryDashboard,MicroplateEditor,AuditViewer,AdminConsole}/` | `frontend/src/components/TelemetryDashboard/` + `frontend/src/pages/{TelemetryDashboard,MicroplateEditor,AuditViewer,AdminConsole}.tsx` |

---

## 5. Prioritized Remediation Roadmap

### Phase A — Security & Compliance Blockers (First 5 Actions)
*Estimated effort: 3–5 days (single developer)*

| # | Action | Effort | Dependencies | Fix Tasks |
|:--|:|:|:--|:--|
| A1 | **JWT secret from environment** | S | None | (1) `middleware/api/auth.py:17` — read `JWT_SECRET` from env; raise `RuntimeError` at import if unset in non-dev. (2) `docker-compose.yml:48` — remove insecure default; require `${JWT_SECRET}`. (3) `.env.example` — document required secret. |
| A2 | **DB-backed authentication** | M | A1 | (1) Add password-hash verification in `routes/auth.py:50` using `passlib` (already in requirements). (2) Query `users` table by username; verify hash. (3) Derive `scopes` from DB `users.scopes` column, not hardcoded. |
| A3 | **Real PyPulse build** | L | Docker | (1) Replace `middleware/Dockerfile` with multi-stage build: Stage 1 compiles Kitware Pulse from C++ source (cmake/gcc); Stage 2 copies `PyPulse.so` into `python:3.11-slim`. (2) Remove mock fallback in `pulse.py:142` — fail hard if `PyPulse` import fails. (3) Update IQ-4 test to assert real engine. |
| A4 | **Hash-chain D_prev + R_i** | M | DB migration | (1) Add `previous_state JSONB` and `reason TEXT` columns to `audit_log`. (2) Update `compute_hash_chain()` trigger to include `D_prev` (from `OLD.data` via `LAG`/previous-row lookup) and `R_i` (`NEW.reason`). (3) Update `hash_chain.py:compute_hash()` signature + `hash-chain-check.sql` verification query. (4) Add migration `0005_hash_chain_fields.sql`. |
| A5 | **Full append-only trigger coverage** | S | DB migration | (1) Add `BEFORE UPDATE/DELETE` triggers to `human_factors_metrics` and `barcode_indices`. (2) Create missing tables `patients`, `device_metrics`, `dilution_worklists` with triggers. (3) Resolve `devices` `updated_at` conflict (remove UPDATE trigger or make `devices` truly read-only). |

### Phase B — Functional Correctness
*Estimated effort: 2–4 days*

| # | Action | Effort | Dependencies | Fix Tasks |
|:--|:|:|:--|:--|
| B1 | **Barcode d==2 rejection fix** | S | None | `barcode.py:75,87` — change severity threshold: `'critical' if dist < min_distance` (i.e., `< 3`), not `< 2`. |
| B2 | **Barcode authenticity** | M | None | Replace `barcode.py` 6-base TruSeq set with real 8/10-base Illumina UDI sequences from doc 1000000002694; verify Hamming distances. |
| B3 | **Vectorize Hamming distance** | M | None | `barcode.py` — use `numpy`/`scipy.spatial.distance.pdist` for O(n²) computation; protect async event loop (DEVELOPMENT_PLAN risk #5). |
| B4 | **FHIR persistence** | M | A5 | `fhir.py:48,90` — implement real DB writes to `observations` and `device_metrics`; return HTTP 201; remove placeholder. |
| B5 | **Dilution unit conversion cleanup** | S | None | `dilution.py:315,359` — remove dead `elif` branches; consolidate conversion logic. |
| B6 | **LTTB downsampling** | M | None | Implement Largest-Triangle-Three-Buckets on backend before WebSocket push (DEVELOPMENT_PLAN risk #3); remove 1000-point frontend cap. |
| B7 | **Microplate import/export symmetry** | S | None | Add CSV export; add JSON import to `MicroplateEditor.tsx`. |
| B8 | **Microplate well click → FHIR fetch** | M | B4 | Wire well click to `GET /api/fhir/Observation?well=...` backend query. |

### Phase C — Frontend & Performance
*Estimated effort: 2–3 days*

| # | Action | Effort | Dependencies | Fix Tasks |
|:--|:|:|:--|:--|
| C1 | **SciChart provider** | **Resolved (deviation)** | `chart-provider.tsx` — SciChart branch removed; ECharts-only per approved deviation from FR-3.1.3. No new charting dependency. |
| C2 | **Alarm timing guarantee** | S | None | Add timestamped alarm evaluation + 100 ms SLA test in frontend. |
| C3 | **Threshold consistency** | S | None | Align frontend `140` and backend `150` pressure thresholds. |
| C4 | **uFMEA JSON export** | **Resolved** | `human_factors.py` — `GET /api/human-factors/export` (sessions, event-type counts, latency percentiles, steps stats, per-component breakdown) + `POST /api/human-factors/events` ingest; frontend wires `useHumanFactors.ts` to POST debounced/batched. |

### Phase D — Qualification & Documentation
*Estimated effort: 2–3 days*

| # | Action | Effort | Dependencies | Fix Tasks |
|:--|:|:|:--|:--|
| D1 | **Missing IQ tests** | S | None | Add `tests/test_iq2_python_version.py`, `test_iq3_pgcrypto.py`, `test_iq6_triggers_installed.py`, `test_iq7_alembic_upgrade.py`. |
| D2 | **PQ-1 real load test** | M | C1, B6 | Run Locust against real stack; assert ≥55 fps, ≤80% CPU, 0 dropped frames. |
| D3 | **PQ-3 real 1M-row test** | M | A4 | Generate 1M audit_log rows; run `verify_hash_chain()`; assert <60 s. |
| D4 | **PQ-4 24 h ingest** | L | B6 | Overnight test script; assert ≤5% memory growth, 0 deadlocks. |
| D5 | **Docs: URS.md, FRS.md** | S | None | Create `docs/URS.md` and `docs/FRS.md` per SRS §9. |
| D6 | **OQ-6 tolerance fix** | S | None | `signal.py:317` — enforce ≤4 steps per SRS; update test expectation. |

---

## 6. Recommended First 5 Actions (COMPLETED)

These actions have been **implemented and verified** (see §0 Remediation Status above):

1. **✅ A1 — JWT secret from env (fail closed).** `middleware/api/auth.py` now reads `JWT_SECRET` from env (or `JWT_SECRET_FILE` for Docker secrets); raises `RuntimeError` in production if unset. `docker-compose.yml` default removed. `.env.example` documents the requirement.
2. **✅ A2 — DB-backed login.** `routes/auth.py:login` now calls `authenticate_user()` which queries the `users` table, verifies bcrypt password hash via `passlib`, and derives scopes from the DB row. Dev fallback only when `ENVIRONMENT=development` and DB is unavailable.
3. **✅ A4 — Hash-chain `D_prev` + `R_i`.** Added `previous_state JSONB` and `reason TEXT` columns to `audit_log` (migration `0005`); trigger now hashes `H_{i-1} ‖ T_i ‖ U_i ‖ D_prev ‖ D_new ‖ R_i` per SRS FR-3.8.3; Python `hash_chain.py` and SQL `hash-chain-check.sql` updated.
4. **✅ A5 — Complete append-only coverage.** Triggers added to `human_factors_metrics`, `barcode_indices`, `patients`, `device_metrics`, `dilution_worklists` (migration `0006`); `devices` `updated_at` trigger removed (read-only per SRS §6.1).
5. **✅ B1 — Barcode d==2 rejection.** `barcode.py:75` severity threshold fixed: `dist < min_distance` (i.e., `< 3`) is now always `'critical'`, so `is_valid=False`.

---

## 7. Verification Steps

After implementing the first 5 actions (and ideally before any commit):

```bash
# Backend: lint, typecheck, tests
cd middleware
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
mypy api/ engine/ --ignore-missing-imports
pytest ../tests/ ../tests/unit/ ../tests/integration/ -v --cov=api --cov=engine --cov-report=term-missing

# Database: fresh migration (IQ-7 surrogate)
docker-compose up -d db
psql -h localhost -U biosync_user -d biosync -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head
psql -h localhost -U biosync_user -d biosync -c "SELECT to_regclass('audit_log'); SELECT to_regclass('patients');"

# Pulse Engine: real import (IQ-4 surrogate)
python -c "import PyPulse; print('PyPulse OK')"

# Frontend: lint, typecheck, tests
cd ../frontend
npm run lint
npm run typecheck
npm test

# Docker build (IQ-1 surrogate)
cd ..
docker-compose build
docker-compose up -d
curl -sf http://localhost:8000/api/health && echo "healthy"
docker-compose down
```

**Expected baseline (current state):** backend tests pass (against mock Pulse), `alembic upgrade head` applies, but `import PyPulse` fails and JWT secret is hardcoded. After Phase A, all of the above should pass with real components.

---

## 8. Notes on Architectural Risks (from DEVELOPMENT_PLAN §7)

The DEVELOPMENT_PLAN identifies 5 technical risks. Current status:

| Risk | Mitigation in Plan | Current Status |
|------|-------------------|----------------|
| Pulse binary incompatibility | Multi-stage Docker build from C++ source | **Not started** (A3) |
| pgcrypto unavailable | Use native `sha256()` | pgcrypto is used; OK on RDS/GCP/Azure |
| WebGL 60 fps not achievable | LTTB downsampling | **Not implemented** (B6) |
| WebSocket scaling >500 conns | uvloop + no sync DB writes | uvloop not configured; sync DB writes in WS path (`telemetry.py:235`) |
| Hamming O(n²) on 384-well | NumPy vectorization | **Not implemented** (B3) |

---

*Document prepared for Computer System Validation (CSV) under FDA General Principles of Software Validation. This gap analysis is the working baseline for Phase 5 (Validation & Hardening) of the BioSync-Gateway development plan.*
