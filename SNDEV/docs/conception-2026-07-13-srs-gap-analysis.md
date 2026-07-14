Title: comprehensive-srs-gap-analysis
Date: 2026-07-13T00:00:00Z
Author: Seth Nenninger (DeepSeek V4 Pro Agent)
Contribution Type: Conception
Ticket/Context: ad-hoc — Full SRS-to-code gap analysis for future development planning
Summary: Comprehensive comparison of all 70 SRS requirements against actual implementation, with prioritized work items.

---

# BioSync-Gateway — SRS Gap Analysis & Roadmap

**Date:** 2026-07-13 | **Analyzed:** 40+ source files across frontend, middleware, database

---

## Overall Status

| Total Requirements | ✅ Implemented | ⚠️ Partial | ❌ Missing |
|:---|:---:|:---:|:---:|
| **70** (FR + NFR) | **38** (54%) | **22** (31%) | **10** (14%) |

### By Section

| Section | % Complete | Key Gaps |
|:---|:---:|:---|
| §3.1 Telemetry Dashboard | 33% | fps counter, alarm thresholds, zoom/pan min span |
| §3.2 Microplate Editor | 60% | CSV import/export handler code |
| §3.3 Barcode Validation | 80% | 8/10-base UDI sequences |
| §3.4 Dilution Solver | **100%** ✅ | — |
| §3.5 Signal Processing | 25% | EMA not wired into telemetry pipeline |
| §3.6 Pulse Engine | **100%** ✅ | — |
| §3.7 FHIR Compliance | 60% | OperationOutcome response format, Bundle processing |
| §3.8 Audit Trail | **100%** ✅ | — |
| §3.9 Human Factors | **100%** ✅ | — |
| §3.10 External Integration | 33% | Real API calls (AccessGUDID/ClinVar are mocks) |
| NFR-P (Performance) | 0% | All 6 perf NFRs unmeasured |
| NFR-S (Security) | 57% | JWT lifetime, TLS, DB certs |
| NFR-R (Reliability) | 75% | 99.9% uptime (no HA) |
| NFR-M (Maintainability) | **100%** ✅ | — |
| NFR-U (Usability) | 33% | Alarm ack UX, responsive layout |

---

## Top 10 Remaining Items (Prioritized)

### 🔴 P0 — Blocks Compliance / Security

| # | Item | Severity | Effort |
|:---|:---|:---|:---:|
| **1** | **JWT lifetime ≤1 hour** — Currently 24h. Add refresh token endpoint. Per FDA 21 CFR Part 11 session controls. Change `JWT_EXPIRATION_HOURS = 1` in `auth.py`. | Critical | 0.5d |
| **2** | **TLS 1.3 + DB client certs** — All traffic plaintext. Required for production and regulatory. Add nginx reverse proxy with Let's Encrypt, DB sslmode=verify-full. | Critical | 2d |
| **3** | **Wire EMA filter into telemetry pipeline** — Raw data used for alarms defeats the purpose. Pipe ingest → EMA → alarm check → store raw+filtered in `observations` table. | High | 1d |
| **4** | **Plate import/export handlers** — `handleImportCSV`/`handleExportJSON` state exists but no file i/o code. Core lab workflow feature. | High | 1d |
| **5** | **FHIR OperationOutcome response format** — Currently returns HTTP 400 plain JSON. Must return `Content-Type: application/fhir+json` with proper OperationOutcome resource. | High | 0.5d |
| **6** | **FHIR Bundle transaction processing** — Route is a placeholder. Must persist entries with transaction semantics. | High | 1.5d |

### 🟡 P1 — Completes Feature Set

| # | Item | Severity | Effort |
|:---|:---|:---|:---:|
| **7** | **Real external API calls** — AccessGUDID and ClinVar clients are 100% mocks. Add `httpx` calls with rate limiting and caching. | Medium | 2d |
| **8** | **8/10-base barcode sequences** — Only 6-base seeded. SRS requires 8-base and 10-base UDI from Illumina doc 1000000002694. Seed data + update `TRUSEQ_BARCODES` dict. | Medium | 1d |
| **9** | **Performance instrumentation** — All 6 NFR-P items unmeasured. Add fps counter in dashboard, response-time middleware, Locust load tests in CI. | Medium | 3d |
| **10** | **Per-channel EMA α defaults** — Single α=0.5 for all. SRS specifies α=0.2 (pressure), α=0.1 (flow). Update `MultiChannelEMAFilter`. | Medium | 0.5d |

---

## Architecture Gaps (Cross-Cutting)

| Gap | Impact | Fix |
|:---|:---|:---|
| **No Admin API routes** — Frontend calls `/api/admin/jwt/rotate`, `/api/admin/signal/ema`, `/api/admin/pulse/restart` but none exist | Admin Console non-functional except health display | Create `api/routes/admin.py` with JWT rotate, EMA config, Pulse restart endpoints |
| **No CI/CD** — `.github/workflows/` missing | No automated testing or deployment | Add lint/typecheck/test/build workflow |
| **Alembic idle** — Raw SQL in `/docker-entrypoint-initdb.d` | Migration versioning not tracked | Convert schema to Alembic-managed migrations |
| **Observations never persisted** — Telemetry ingest broadcasts to WS but never writes to DB | No audit trail for telemetry | Add DB insert + audit log write in `POST /api/telemetry/ingest` |
| **Synthetic generator unconditional** — Background task always generates data | Conflicts with real device ingestion mode | Add config toggle: `TELEMETRY_MODE=synthetic|device` |
| **Simulation states in-memory only** — Server restart loses all simulations | No pause/resume across restarts | Write `SerializedState` to `simulations` table on pause/stop |
| **WebSocket lacks JWT auth** — Any client can connect | Violates NFR-S2; potential data leak | Add query-param token validation in `telemetry_stream()` `on_connect` |

---

## Test Coverage Gap

| Category | Existing | Missing | Targeted |
|:---|:---:|:---:|:---:|
| IQ Tests (7) | 1 | IQ-1,2,3,5,6,7 | Docker health, pgcrypto, PyPulse import, pip check, pg_trigger, Alembic |
| OQ Tests (16) | ~12 | OQ-13,14,15 | JWT auth tests |
| PQ Tests (6) | 5 | PQ-5 | Barcode 500ms benchmark for 96-index plate |
| Frontend Tests | 66 | — | ✅ Good coverage |

---

## Section-by-Section Detailed Status

### §3.1 — Telemetry Dashboard (33%)

| ID | Status | Note |
|:---|:---|:---|
| FR-3.1.1 Canvas/WebGL | ✅ | ECharts via chart-provider |
| FR-3.1.2 ≥60 fps | ⚠️ | No fps counter or measurement |
| FR-3.1.3 Swappable backend | ✅ | ECharts/SciChart abstraction |
| FR-3.1.4 4 channels | ✅ | Pressure, Flow, HR, SpO₂ with LOINC codes |
| FR-3.1.5 Alarm visualization | ⚠️ | Thresholds hardcoded (60/140 vs SRS 150 for arthroscopic pump); no auditory alert |
| FR-3.1.6 Zoom/pan | ⚠️ | ECharts dataZoom present but no explicit 5s min constraint |

### §3.2 — Microplate Editor (60%)

| ID | Status | Note |
|:---|:---|:---|
| FR-3.2.1 CSS Grid | ✅ | 96-well and 384-well layouts |
| FR-3.2.2 Well state binding | ✅ | empty/pending/processed/error states |
| FR-3.2.3 Click-to-inspect | ✅ | FHIR Observation overlay on click |
| FR-3.2.4 Batch selection | ⚠️ | Drag-select works; missing text coordinate input and batch status apply |
| FR-3.2.5 Import/export | ❌ | `handleImportCSV`/`handleExportJSON` declared but no file i/o code |

### §3.5 — Signal Processing (25%)

| ID | Status | Note |
|:---|:---|:---|
| FR-3.5.1 EMA filter | ✅ | `EMAFilter` class with correct formula |
| FR-3.5.2 Per-channel α | ⚠️ | Single α=0.5 default; SRS requires 0.2/0.1 |
| FR-3.5.3 Raw+filtered storage | ⚠️ | Schema columns exist; ingest endpoint doesn't use EMA |
| FR-3.5.4 Filtered alarms | ⚠️ | Dashboard checks raw data, not EMA-filtered |

### §3.7 — FHIR Compliance (60%)

| ID | Status | Note |
|:---|:---|:---|
| FR-3.7.1 FHIR R4 validation | ✅ | `FHIRValidator` with Pydantic/fallback |
| FR-3.7.2 DeviceMetric | ✅ | `validate_device_metric()` |
| FR-3.7.3 Observation | ✅ | `validate_observation()` |
| FR-3.7.4 OperationOutcome | ⚠️ | Returns plain 400 JSON; needs proper FHIR content-type |
| FR-3.7.5 Bundle | ⚠️ | Route is placeholder; no persistence or transaction semantics |

### §3.10 — External Integration (33%)

| ID | Status | Note |
|:---|:---|:---|
| FR-3.10.1 AccessGUDID | ⚠️ | Client class exists; all responses are hardcoded mocks |
| FR-3.10.2 ClinVar | ⚠️ | Client class exists; all responses are hardcoded mocks |
| FR-3.10.3 Caching | ✅ | 24h (GUDID) / 7d (ClinVar) TTL via file cache |

### NFR-S — Security (57%)

| ID | Status | Note |
|:---|:---|:---|
| NFR-S1 21 CFR Part 11 | ✅ | Triggers + hash chain + JWT + audit |
| NFR-S2 JWT all endpoints | ✅ | Most routes use `require_scope()` |
| NFR-S3 JWT ≤1h lifetime | ❌ | 24h configured; no refresh tokens |
| NFR-S4 TLS 1.3 | ❌ | Plain HTTP in docker-compose |
| NFR-S5 DB client certs | ❌ | Password-only auth |
| NFR-S6 Audit immutable | ✅ | DB-level triggers |
| NFR-S7 Secrets via env | ✅ | docker-compose env vars |
