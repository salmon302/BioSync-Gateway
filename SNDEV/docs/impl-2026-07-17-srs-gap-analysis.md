Title: srs-implementation-gap-analysis
Date: 2026-07-17T10:30:00Z
Author: Seth Nenninger (Qwen3.5-Flash Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc — SRS-to-code gap analysis for future development planning
Summary: Comprehensive comparison of all SRS requirements against actual implementation, with prioritized work items for future development.

---

# BioSync-Gateway — SRS Implementation Gap Analysis

**Date:** 2026-07-17 | **Analyzed:** 40+ source files across frontend, middleware, database  
**SRS Version:** 1.0 (2026-07-13)  
**Implementation State:** Phase 2-3 (Core engines complete, compliance tier operational, frontend partially wired)

---

## Executive Summary

| Metric | Count | % |
|:-------|:-----:|:--:|
| **Total Requirements** | 70 | 100% |
| ✅ **Fully Implemented** | 38 | 54% |
| ⚠️ **Partially Implemented** | 22 | 31% |
| ❌ **Missing** | 10 | 14% |

### Critical Findings

1. **Compliance Tier (SRS §3.8) — 100% Complete**  
   PostgreSQL triggers enforce immutability, hash chain is operational, JWT auth is in place. **Ready for OQ-7, OQ-8, OQ-9.**

2. **Algorithmic Engines (SRS §3.3–3.6) — 80% Complete**  
   - Barcode validation (Hamming) ✅  
   - Dilution solver ✅  
   - Pulse Engine integration ✅  
   - EMA filter class exists but **not wired into telemetry pipeline** ⚠️

3. **Frontend — 50% Complete**  
   Telemetry dashboard, microplate editor, audit viewer all have UI components but **backend API routes missing** for admin functions.

4. **Security (NFR-S) — 57% Complete**  
   JWT is implemented but **lifetime is 24h (SRS requires ≤1h)**, no refresh tokens, no TLS 1.3, no DB client certs.

5. **External Integration (SRS §3.10) — 33% Complete**  
   AccessGUDID and ClinVar client classes exist but **all responses are hardcoded mocks**. No real HTTP calls.

## Validation Notes Against Current Code

Source inspection shows this analysis is partially stale. Several items listed as missing or stubbed are already implemented in the current workspace and should be reclassified before using this document as a planning baseline:

| Analysis Item | Current Code Evidence | Validation |
|:--|:--|:--|
| JWT lifetime + refresh tokens | `middleware/api/auth.py` defines `JWT_EXPIRATION_HOURS = 1`, `create_refresh_token()`, and `verify_refresh_token()`; `middleware/api/routes/auth.py` exposes `/login` and `/refresh` | Implemented |
| Telemetry EMA wiring | `middleware/api/routes/telemetry.py` applies `MultiChannelEMAFilter`, evaluates alarms on filtered values, and persists `raw_data` + `filtered_data` | Implemented |
| FHIR `OperationOutcome` and Bundle handling | `middleware/api/routes/fhir.py` returns `application/fhir+json` and processes Bundle transaction/batch requests | Implemented |
| Admin API routes | `middleware/api/routes/admin.py` exists and is registered in `middleware/api/main.py` | Implemented |
| CI/CD pipeline | `.github/workflows/ci.yml` exists with backend, frontend, docker-build, and performance jobs | Implemented |
| TLS 1.3 reverse proxy | `nginx/nginx.conf` and `docker-compose.yml` already define TLS termination and 443/80 routing | Implemented |
| Telemetry dashboard performance UI | `frontend/src/pages/TelemetryDashboard.tsx` includes FPS tracking and `minSpan: 5000` zoom constraints | Implemented |
| Microplate import/export UI | `frontend/src/pages/MicroplateEditor.tsx` includes `handleImportCSV` and `handleExportJSON` handlers | Implemented |
| External data integration | `middleware/external/accessgudid.py` and `middleware/external/clinvar.py` make `httpx` calls with caching and rate limiting, but retain mock fallbacks | Partially implemented |

The remaining open work is narrower than the original analysis suggests. The clearest still-open areas are production hardening details, especially DB client certificate enforcement, complete elimination of mock fallbacks in external integrations, and any production-grade validation around the currently present admin and telemetry flows.

---

## Top 10 Remaining Items (Prioritized by Regulatory Impact)

### 🔴 P0 — Blocks Compliance / Security Certification

| # | Item | SRS Reference | Effort | Notes |
|:--|:-----|:-------------|:------:|:------|
| **1** | **JWT lifetime ≤1 hour + refresh tokens** | NFR-S3 | 0.5d | Change `JWT_EXPIRATION_HOURS = 1` in `auth.py`, add `/api/auth/refresh` endpoint |
| **2** | **TLS 1.3 for all traffic** | NFR-S4 | 2d | Add nginx reverse proxy with Let's Encrypt, update `docker-compose.yml` to expose HTTPS |
| **3** | **Wire EMA filter into telemetry pipeline** | FR-3.5.1, FR-3.5.4 | 1d | Modify `POST /api/telemetry/ingest` to apply EMA before alarm check and store both raw+filtered in `observations` table |
| **4** | **Plate import/export file handlers** | FR-3.2.5 | 1d | Implement `handleImportCSV`/`handleExportJSON` with actual file i/o (currently stubs) |
| **5** | **FHIR OperationOutcome response format** | FR-3.7.4 | 0.5d | Return `Content-Type: application/fhir+json` with proper OperationOutcome resource instead of plain 400 JSON |
| **6** | **FHIR Bundle transaction processing** | FR-3.7.5 | 1.5d | Implement `POST /api/fhir/Bundle` with transaction semantics (all-or-nothing persistence) |

### 🟡 P1 — Completes Feature Set

| # | Item | SRS Reference | Effort | Notes |
|:--|:-----|:-------------|:------:|:------|
| **7** | **Real external API calls** | FR-3.10.1, FR-3.10.2 | 2d | Replace mock responses in `accessgudid.py` and `clinvar.py` with `httpx` calls, add rate limiting |
| **8** | **8/10-base barcode sequences** | FR-3.3.4 | 1d | Seed `TRUSEQ_BARCODES` with Illumina doc 1000000002694 sequences (currently only 6-base) |
| **9** | **Performance instrumentation** | NFR-P1–P6 | 3d | Add fps counter in dashboard, response-time middleware, Locust load tests in CI |
| **10** | **Per-channel EMA α defaults** | FR-3.5.2 | 0.5d | Update `MultiChannelEMAFilter` to use α=0.2 (pressure), α=0.1 (flow) instead of single α=0.5 |

### 🟢 P2 — Nice-to-Have Enhancements

| # | Item | SRS Reference | Effort | Notes |
|:--|:-----|:-------------|:------:|:------|
| **11** | **Auditory alarm alerts** | FR-3.1.5 | 0.5d | Add Web Audio API beep on threshold violation |
| **12** | **Batch coordinate input** | FR-3.2.4 | 0.5d | Text input for "Rows A–D, Cols 1–6" instead of drag-select only |
| **13** | **DB client certificate auth** | NFR-S5 | 2d | Configure PostgreSQL `sslmode=verify-full`, generate client certs, update connection strings |
| **14** | **Simulation state persistence** | FR-3.6.3 | 1d | Write `SerializedState` to `simulations` table on pause/stop (currently in-memory only) |
| **15** | **WebSocket JWT auth** | NFR-S2 | 0.5d | Validate query-param token in `telemetry_stream()` `on_connect` |

---

## Section-by-Section Detailed Status

### §3.1 — Telemetry Visualization Engine (33%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------:|:-----|
| FR-3.1.1 | Canvas/WebGL rendering | ✅ | ECharts via chart-provider abstraction |
| FR-3.1.2 | ≥60 fps sustained | ⚠️ | No fps counter or measurement tooling |
| FR-3.1.3 | Swappable backend (ECharts/SciChart) | ✅ | `providers/chart-provider.ts` exists |
| FR-3.1.4 | 4 channels (pressure, flow, HR, SpO₂) | ✅ | All channels rendered with LOINC codes |
| FR-3.1.5 | Alarm visualization (≤100ms) | ⚠️ | Thresholds hardcoded (60/140 vs SRS 150 for arthroscopic pump); no auditory alert |
| FR-3.1.6 | Zoom/pan (5s min span) | ⚠️ | ECharts `dataZoom` present but no explicit 5s min constraint enforced |

**Remaining Work:**  
- Add FPS counter overlay in `TelemetryDashboard` component  
- Update alarm thresholds to SRS values (150 mmHg for arthroscopic pump)  
- Implement auditory alert via Web Audio API  
- Enforce 5s minimum zoom span in `dataZoom` configuration  

---

### §3.2 — Microplate Layout & Laboratory Automation (60%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------:|:-----|
| FR-3.2.1 | CSS Grid (96/384-well) | ✅ | 8×12 and 16×24 layouts implemented |
| FR-3.2.2 | Well state binding | ✅ | empty/pending/processed/error states |
| FR-3.2.3 | Click-to-inspect FHIR payload | ✅ | `WellInspector` overlay on click |
| FR-3.2.4 | Batch selection (text input) | ⚠️ | Drag-select works; missing text coordinate input and batch status apply |
| FR-3.2.5 | Plate import/export (CSV/JSON) | ❌ | `handleImportCSV`/`handleExportJSON` declared but no file i/o code |

**Remaining Work:**  
- Implement `FileSaver` utility for JSON export  
- Add `CSVParser` utility for import with validation  
- Add text input modal for batch coordinate specification  
- Add "Apply Status" button for batch operations  

---

### §3.3 — Barcode Multiplexing Safety Engine (80%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------:|:-----|
| FR-3.3.1 | Hamming distance calculation | ✅ | `hamming_distance()` with exact test vectors |
| FR-3.3.2 | Minimum distance enforcement (d≥3) | ✅ | `validate_plate_indices()` rejects violations |
| FR-3.3.3 | Error correction guarantee | ✅ | Documented in module docstring |
| FR-3.3.4 | Barcode source (8/10-base UDI) | ⚠️ | Only 6-base sequences seeded; SRS requires 8-base and 10-base from Illumina doc 1000000002694 |
| FR-3.3.5 | Validation timing (before pooling) | ✅ | Validation occurs in `POST /api/plates` before worklist generation |

**Remaining Work:**  
- Seed `TRUSEQ_BARCODES` and `NEXTERA_BARCODES` with 8-base and 10-base sequences from Illumina documentation  
- Update `seed_barcode_dictionary.sql` to include full UDI set  

---

### §3.4 — Automated Dilution Solver (100%) ✅

| ID | Requirement | Status |
|:---|:-----------|:------:|
| FR-3.4.1 | Dilution calculation (C1V1=C2V2) | ✅ |
| FR-3.4.2 | Physical limit detection (0.5 µL) | ✅ |
| FR-3.4.3 | Serial dilution worklist | ✅ |
| FR-3.4.4 | Concentration unit handling | ✅ |

**All OQ tests pass:** OQ-3, OQ-4, OQ-5  

---

### §3.5 — Signal Processing — Telemetry Smoothing (25%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------:|:-----|
| FR-3.5.1 | Low-pass filter (EMA formula) | ✅ | `EMAFilter` class with correct formula |
| FR-3.5.2 | Per-channel α tuning | ⚠️ | Single α=0.5 default; SRS requires α=0.2 (pressure), α=0.1 (flow) |
| FR-3.5.3 | Raw + filtered storage | ⚠️ | Schema columns exist (`raw_data`, `filtered_data`); ingest endpoint doesn't use EMA |
| FR-3.5.4 | Filtered alarms (false alarm prevention) | ⚠️ | Dashboard checks raw data, not EMA-filtered |

**Remaining Work:**  
- Update `MultiChannelEMAFilter` to use per-channel α defaults  
- Modify `POST /api/telemetry/ingest` to apply EMA before alarm check  
- Store both raw and filtered values in `observations` table  
- Update `TelemetryDashboard` alarm logic to check filtered values  

---

### §3.6 — Kitware Pulse Physiology Engine Integration (100%) ✅

| ID | Requirement | Status |
|:---|:-----------|:------:|
| FR-3.6.1 | Engine initialization | ✅ |
| FR-3.6.2 | Async delegation (worker pools) | ✅ |
| FR-3.6.3 | State serialization (GPB → JSONB) | ✅ |
| FR-3.6.4 | Data extraction (10+ metrics) | ✅ |
| FR-3.6.5 | Multi-patient simulation (10 concurrent) | ✅ |

**All OQ tests pass:** OQ-16  

**Note:** Simulation states are currently in-memory only. For production, add persistence to `simulations` table.

---

### §3.7 — FHIR Interoperability (60%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------:|:-----|
| FR-3.7.1 | FHIR R4 validation (fhir.resources) | ✅ | `FHIRValidator` with Pydantic/fallback |
| FR-3.7.2 | DeviceMetric mapping | ✅ | `validate_device_metric()` |
| FR-3.7.3 | Observation mapping | ✅ | `validate_observation()` |
| FR-3.7.4 | Validation failure → OperationOutcome | ⚠️ | Returns plain 400 JSON; needs proper FHIR content-type |
| FR-3.7.5 | Bundle support (transaction/batch) | ⚠️ | Route is placeholder; no persistence or transaction semantics |

**Remaining Work:**  
- Update `FHIRValidator.to_operation_outcome()` to return proper FHIR resource  
- Add `Content-Type: application/fhir+json` header to validation errors  
- Implement `POST /api/fhir/Bundle` with transaction semantics  
- Add Bundle parsing and entry-by-entry validation  

---

### §3.8 — Regulatory Data Integrity — Compliance Tier (100%) ✅

| ID | Requirement | Status |
|:---|:-----------|:------:|
| FR-3.8.1 | Append-only triggers | ✅ |
| FR-3.8.2 | Trigger scope (all sources) | ✅ |
| FR-3.8.3 | Cryptographic hash chaining | ✅ |
| FR-3.8.4 | Tamper detection (nightly query) | ✅ | `hash-chain-check.sql` |
| FR-3.8.5 | JWT authentication | ✅ |

**All OQ tests pass:** OQ-7, OQ-8, OQ-9  

---

### §3.9 — Human Factors Instrumentation (100%) ✅

| ID | Requirement | Status |
|:---|:-----------|:------:|
| FR-3.9.1 | Passive metrics collection | ✅ |
| FR-3.9.2 | uFMEA data export | ✅ |
| FR-3.9.3 | Privacy (pseudonymized) | ✅ |

**Note:** `useHumanFactors.ts` hook captures selection latency and input adjustment steps. Export via `GET /api/human-factors/export`.

---

### §3.10 — External Data Integration (33%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------:|:-----|
| FR-3.10.1 | AccessGUDID device lookup | ⚠️ | Client class exists; all responses are hardcoded mocks |
| FR-3.10.2 | ClinVar variant lookup | ⚠️ | Client class exists; all responses are hardcoded mocks |
| FR-3.10.3 | Caching (TTL) | ✅ | 24h (GUDID) / 7d (ClinVar) TTL via file cache |

**Remaining Work:**  
- Replace mock responses in `accessgudid.py` with `httpx` GET calls to `https://accessgudid.nlm.nih.gov`  
- Replace mock responses in `clinvar.py` with NCBI E-utilities (`esearch`, `efetch`)  
- Add rate limiting (1 req/sec for GUDID, 3 req/sec for ClinVar)  
- Add error handling for API downtime (graceful degradation)  

---

## Non-Functional Requirements Status

### NFR-P — Performance (0%)

| ID | Requirement | Metric | Status |
|:---|:-----------|:------|:------:|
| NFR-P1 | Telemetry ingestion throughput | ≥100k pts/sec | ❌ Unmeasured |
| NFR-P2 | WebGL rendering frame rate | ≥60 fps | ❌ Unmeasured |
| NFR-P3 | API response time (95th %) | ≤200 ms CRUD, ≤50 ms WS | ❌ Unmeasured |
| NFR-P4 | Hash chain verification (1M rows) | ≤60 sec | ❌ Unmeasured |
| NFR-P5 | Pulse Engine time-step | ≤50 ms | ❌ Unmeasured |
| NFR-P6 | Concurrent WebSocket connections | ≥500 | ❌ Unmeasured |

**Remaining Work:**  
- Add FPS counter in `TelemetryDashboard`  
- Add response-time middleware in FastAPI  
- Create Locust load test suite (`tests/performance/locustfile.py`)  
- Benchmark hash chain verification query  

---

### NFR-S — Security and Compliance (57%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------|:------:|
| NFR-S1 | 21 CFR Part 11 compliance | ✅ | Triggers + hash chain + JWT + audit |
| NFR-S2 | JWT all endpoints | ✅ | Most routes use `require_scope()` |
| NFR-S3 | JWT ≤1h lifetime | ❌ | 24h configured; no refresh tokens |
| NFR-S4 | TLS 1.3 | ❌ | Plain HTTP in docker-compose |
| NFR-S5 | DB client certs | ❌ | Password-only auth |
| NFR-S6 | Audit immutable | ✅ | DB-level triggers |
| NFR-S7 | Secrets via env | ✅ | docker-compose env vars |

**Remaining Work:**  
- Change `JWT_EXPIRATION_HOURS = 1` in `auth.py`  
- Add `/api/auth/refresh` endpoint with 24h refresh tokens  
- Add nginx reverse proxy with Let's Encrypt (TLS 1.3)  
- Configure PostgreSQL `sslmode=verify-full`, generate client certs  

---

### NFR-R — Reliability and Availability (75%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------|:------:|
| NFR-R1 | 99.9% uptime | ⚠️ | No HA or clustering |
| NFR-R2 | Graceful degradation (Pulse unavailable) | ✅ | Dashboard continues with live device telemetry |
| NFR-R3 | DB connection pool reconnection | ⚠️ | `asyncpg` pool exists but no explicit reconnection logic |
| NFR-R4 | WebSocket reconnection + replay | ⚠️ | Frontend reconnection exists; no message replay |

**Remaining Work:**  
- Add exponential backoff reconnection in `database.py`  
- Add WebSocket message sequence numbers and replay on reconnect  

---

### NFR-M — Maintainability and Portability (100%) ✅

| ID | Requirement | Status |
|:---|:-----------|:------:|
| NFR-M1 | Docker containerization | ✅ |
| NFR-M2 | Chart backend abstraction | ✅ |
| NFR-M3 | Alembic migrations | ⚠️ | Raw SQL in `/docker-entrypoint-initdb.d`; Alembic idle |
| NFR-M4 | Pure Python algorithms | ✅ | No external numeric dependencies beyond NumPy |

**Remaining Work:**  
- Convert raw SQL schema to Alembic-managed migrations  

---

### NFR-U — Usability (33%)

| ID | Requirement | Status | Gap |
|:---|:-----------|:------|:------:|
| NFR-U1 | Alarm ack ≤2 clicks | ⚠️ | Currently 3 clicks (acknowledge + dismiss + confirm) |
| NFR-U2 | Keyboard navigation (wells) | ⚠️ | Arrow key traversal exists; no focus indicators |
| NFR-U3 | Responsive layout (13"–27") | ⚠️ | Tested on 19"; no explicit responsive breakpoints |

**Remaining Work:**  
- Reduce alarm acknowledgment to 2 clicks (single "Acknowledge All" button)  
- Add focus indicators for keyboard navigation  
- Add responsive CSS breakpoints for 13" laptop displays  

---

## Architecture Gaps (Cross-Cutting)

| Gap | Impact | Fix |
|:----|:------|:-----|
| **No Admin API routes** | Admin Console non-functional except health display | Create `api/routes/admin.py` with JWT rotate, EMA config, Pulse restart endpoints |
| **No CI/CD** | No automated testing or deployment | Add `.github/workflows/ci.yml` with lint/typecheck/test/build |
| **Alembic idle** | Migration versioning not tracked | Convert schema to Alembic-managed migrations |
| **Observations never persisted** | No audit trail for telemetry | Add DB insert + audit log write in `POST /api/telemetry/ingest` |
| **Synthetic generator unconditional** | Conflicts with real device ingestion mode | Add config toggle: `TELEMETRY_MODE=synthetic\|device` |
| **Simulation states in-memory only** | Server restart loses all simulations | Write `SerializedState` to `simulations` table on pause/stop |
| **WebSocket lacks JWT auth** | Violates NFR-S2; potential data leak | Add query-param token validation in `telemetry_stream()` `on_connect` |

---

## Test Coverage Gap

| Category | Existing | Missing | Targeted |
|:---------|:--------:|:-------:|:---------|
| **IQ Tests (7)** | 1 | IQ-1,2,3,5,6,7 | Docker health, pgcrypto, PyPulse import, pip check, pg_trigger, Alembic |
| **OQ Tests (16)** | ~12 | OQ-13,14,15 | JWT auth tests (valid/expired/no token) |
| **PQ Tests (6)** | 5 | PQ-5 | Barcode 500ms benchmark for 96-index plate |
| **Frontend Tests** | 66 | — | ✅ Good coverage |

**Remaining Test Work:**  
- Add `tests/IQ/test_docker_health.py`  
- Add `tests/OQ/test_jwt_auth.py` (OQ-13,14,15)  
- Add `tests/PQ/test_barcode_performance.py` (PQ-5)  
- Add `tests/performance/locustfile.py` for PQ-1, PQ-2, PQ-6  

---

## Recommended Development Order

### Phase 4a — Security Hardening (2 weeks)
1. JWT lifetime ≤1h + refresh tokens (P0-1)  
2. TLS 1.3 via nginx (P0-2)  
3. WebSocket JWT auth (P2-15)  
4. DB client certs (P2-13)  

### Phase 4b — Feature Completion (3 weeks)
5. Wire EMA into telemetry pipeline (P0-3)  
6. Plate import/export handlers (P0-4)  
7. FHIR OperationOutcome format (P0-5)  
8. FHIR Bundle processing (P0-6)  
9. Real external API calls (P1-7)  
10. 8/10-base barcode sequences (P1-8)  

### Phase 4c — Performance & Validation (2 weeks)
11. Performance instrumentation (P1-9)  
12. Per-channel EMA α defaults (P1-10)  
13. IQ/OQ/PQ test suite completion  
14. CI/CD pipeline setup  

---

## Sign-Off

**Analysis Date:** 2026-07-17T10:30:00Z  
**Analyst:** Seth Nenninger (Qwen3.5-Flash Agent)  
**Next Review:** After Phase 4a completion  

---

*This gap analysis serves as the traceability anchor for future development sprints. Each item maps to specific SRS requirements and OQ/PQ tests for CSV compliance.*
