# BioSync-Gateway Development Plan

**Version:** 1.0  
**Date:** 2026-07-13  
**Derived From:** SRS.md v1.0  

---

## 1. Overview

### 1.1 Project Summary

BioSync-Gateway is a three-tier medical telemetry and laboratory informatics middleware bridging clinical edge hardware to an append-only PostgreSQL storage tier, enforcing FDA 21 CFR Part 11 data integrity.

### 1.2 Guiding Principles

1. **Database-First Compliance:** Immutability and audit trails are enforced at the PostgreSQL tier, not the application layer.
2. **Vertical Slice Delivery:** Each phase produces a demonstrable, testable increment — no "integration big bang."
3. **CSV-Aligned Testing:** IQ, OQ, and PQ tests are written alongside feature code, not after.
4. **Docker Everywhere:** All components containerized from day one; `docker-compose up` is the only setup command.
5. **Algorithmic Determinism:** All mathematical engines (Hamming, dilution, EMA) are pure Python with no external numeric dependencies beyond NumPy.

---

## 2. Technology Stack

| Layer | Technology | Version Constraint |
|:------|:-----------|:-------------------|
| **Frontend** | React 18, TypeScript 5 | Node.js 20 LTS |
| **Charting** | Apache ECharts 5 (open-source), SciChart.js (enterprise swap) | — |
| **Middleware** | FastAPI, Python | Python 3.11+ |
| **Async** | asyncio, `ProcessPoolExecutor` | — |
| **FHIR** | `fhir.resources` 7.x (Pydantic v2) | — |
| **Database** | PostgreSQL 15+ | `pgcrypto` extension |
| **Migrations** | Alembic | — |
| **Auth** | PyJWT, `python-jose` | — |
| **Container** | Docker, Docker Compose | — |
| **Testing** | Pytest (unit/integration), Locust (load) | — |
| **CI** | GitHub Actions | — |
| **Simulation** | Kitware Pulse Engine C++ (`PyPulse.so`) | — |

---

## 3. Architecture Summary

```
┌──────────────────────────────────────────────────────┐
│                  FRONTEND (React/TS)                  │
│  ┌─────────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Telemetry Dash  │  │ Microplate  │  │  Audit    │  │
│  │ (WebGL Canvas)  │  │ (CSS Grid)  │  │  Viewer   │  │
│  └────────┬────────┘  └─────┬──────┘  └─────┬─────┘  │
│           └─────────────────┼───────────────┘        │
│                    WSS / HTTPS                        │
└──────────────────────────┬───────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────┐
│               MIDDLEWARE (FastAPI/Python)              │
│  ┌──────────┐ ┌───────────┐ ┌────────┐ ┌──────────┐ │
│  │ Pulse    │ │ Barcode   │ │ Dilut. │ │ Signal   │ │
│  │ Worker   │ │ Engine    │ │ Solver │ │ Filter   │ │
│  │ Pool     │ │ (Hamming) │ │        │ │ (EMA)    │ │
│  └────┬─────┘ └─────┬─────┘ └───┬────┘ └────┬─────┘ │
│       └──────────────┼───────────┼───────────┘       │
│                 ┌────┴────┐ ┌───┴─────┐              │
│                 │  FHIR   │ │  JWT    │              │
│                 │ Valid.  │ │  Auth   │              │
│                 └────┬────┘ └───┬─────┘              │
└──────────────────────┼──────────┼────────────────────┘
                       │          │
              PostgreSQL Wire Protocol (TLS 1.3)
                       │          │
┌──────────────────────┴──────────┴────────────────────┐
│           COMPLIANCE TIER (PostgreSQL 15+)             │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ BEFORE UPDATE/    │  │ pgcrypto Hash Chain      │  │
│  │ DELETE Triggers   │  │ SHA-256 Audit Ledger     │  │
│  └──────────────────┘  └──────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐ │
│  │            JSONB Append-Only Tables               │ │
│  └──────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

### 3.1 Key Design Decisions

| Decision | Rationale |
|:---------|:----------|
| **Trigger-level audit, not app-level** | Prevents admin script / raw SQL bypass (SRS C3) |
| **Worker pools for Pulse, not async-inline** | Pulse C++ core is single-threaded per patient (SRS C1) |
| **Both raw and filtered telemetry stored** | Raw = compliance source of truth; filtered = alarm evaluation (FR-3.5.3) |
| **Chart provider abstraction** | Swappable ECharts ↔ SciChart without component rewrites (FR-3.1.3) |
| **DB-generated timestamps only** | Prevents client clock spoofing for audit integrity (SRS D2) |

---

## 4. Phased Development Plan

### Phase 0: Foundation (Week 1–2)

**Goal:** Establish repository, CI/CD pipelines, Docker environment, and project scaffolding.

#### 0.1 — Repository Initialization

| Task | Output | Est. |
|:-----|:-------|:-----|
| Initialize monorepo with `frontend/`, `middleware/`, `database/`, `tests/` | Directory tree per SRS §9 | 0.5d |
| Create `docker-compose.yml` with PostgreSQL + FastAPI + React services | Single-command dev environment | 1d |
| Configure GitHub Actions: lint, typecheck, test on PR | `.github/workflows/ci.yml` | 1d |
| Create `.env.example`, `.gitignore` | — | 0.5d |

#### 0.2 — Database Bootstrapping

| Task | Output | Est. |
|:-----|:-------|:-----|
| Write `001-extensions.sql` (pgcrypto enable) | Extension available at container init | 0.5d |
| Write `002-schema.sql` (all 11 core tables) | Schema matches SRS §6.1 | 1.5d |
| Configure Alembic, run initial migration | `alembic upgrade head` succeeds (IQ-7) | 0.5d |

#### 0.3 — Middleware Skeleton

| Task | Output | Est. |
|:-----|:-------|:-----|
| Initialize FastAPI project with router structure | `api/routes/` stubs | 0.5d |
| Add JWT auth middleware (`api/auth.py`) | Endpoints reject unauthenticated requests (OQ-13/14/15) | 1d |
| Add `requirements.txt` and Dockerfile | Middleware container builds and health-checks | 0.5d |

#### 0.4 — Frontend Skeleton

| Task | Output | Est. |
|:-----|:-------|:-----|
| Initialize React+TypeScript project (Vite) | `frontend/` with dev server | 0.5d |
| Add stub components: TelemetryDashboard, MicroplateEditor, AuditViewer, AdminConsole | Placeholder views | 1d |
| Add chart provider abstraction (`providers/chart-provider.ts`) | Interface defined; ECharts wired as default | 0.5d |

**Phase 0 Exit Criteria:**
- `docker-compose up` starts PostgreSQL (healthy), FastAPI (healthy), React dev server (running)
- GitHub Actions CI passes: lint + typecheck on both services
- Alembic `upgrade head` applies cleanly → empty schema with all tables present
- `curl localhost:8000/health` returns 200

---

### Phase 1: Compliance Tier (Week 3–4)

**Goal:** Deliver the cryptographic audit infrastructure. This phase alone satisfies SRS §3.8 and OQ-7/8/9.

#### 1.1 — Append-Only Triggers

| Task | Output | Est. |
|:-----|:-------|:-----|
| Write `003-triggers.sql`: `before_update_reject()` / `before_delete_reject()` functions | SRS FR-3.8.1 | 1d |
| Apply triggers to `audit_log`, `observations`, `plates`, `plate_wells` | Mutation from any source rolls back | 0.5d |
| Write OQ-7 (UPDATE rejection) pytest | Direct SQL UPDATE → `RAISE EXCEPTION`, row unchanged | 0.5d |
| Write OQ-8 (DELETE rejection) pytest | Direct SQL DELETE → `RAISE EXCEPTION`, row intact | 0.5d |

#### 1.2 — Hash Chain Engine

| Task | Output | Est. |
|:-----|:-------|:-----|
| Write `hash_chain.py` middleware module: `compute_hash()`, `verify_chain()` | SRS FR-3.8.3 | 1d |
| Implement `BEFORE INSERT` trigger calling `pgcrypto digest()` with full concatenated input | Hash computed server-side on insert | 0.5d |
| Write `hash-chain-check.sql` nightly verification query | Detects exact row of chain break | 1d |
| Write OQ-9 (tamper detection) pytest | Alter JSONB → verification reports broken row | 1d |

#### 1.3 — Audit API Endpoints

| Task | Output | Est. |
|:-----|:-------|:-----|
| `GET /api/audit` — paginated, filterable audit log query | Returns `audit_log` rows with hash chain status | 0.5d |
| `GET /api/audit/verify` — trigger on-demand chain verification | Returns `{ integrity: "ok" | "broken", broken_at_row_id }` | 0.5d |
| Add `scope: audit_read` JWT claim requirement | QA Officer role gate | 0.5d |

**Phase 1 Exit Criteria:**
- OQ-7, OQ-8, OQ-9 pass: triggers reject UPDATE/DELETE; tamper detection works
- `GET /api/audit/verify` returns `"ok"` on clean ledger
- Nightly check query executes in sub-second time on <10k rows
- All hash chain math verified against known test vectors

---

### Phase 2: Algorithmic Engines & FHIR (Week 5–8)

**Goal:** Implement all deterministic mathematical models and FHIR interoperability.

#### 2.1 — Barcode Multiplexing Engine

| Task | Output | Est. |
|:-----|:-------|:-----|
| Write `004-seed-barcodes.sql` — populate Illumina UDI dictionary | `barcode_indices` table with authentic TruSeq/Nextera sequences | 0.5d |
| Implement `engine/barcode.py`: `hamming_distance()`, `validate_plate_indices()` | SRS FR-3.3.1, FR-3.3.2 | 1d |
| Implement `POST /api/plates/{id}/validate-barcodes` endpoint | Returns `{ valid, violations }` | 0.5d |
| Write OQ-1 (test vectors) + OQ-2 (d ≥ 3 rejection) | Both pass; PQ-5 benchmark < 500 ms for 96-index plate | 1d |

#### 2.2 — Dilution Solver

| Task | Output | Est. |
|:-----|:-------|:-----|
| Implement `engine/dilution.py`: `compute_volume()`, `detect_below_limit()`, `generate_pre_dilution()` | SRS FR-3.4.1, FR-3.4.2, FR-3.4.3 | 1.5d |
| Implement unit conversion (M ↔ ng/µL via molar mass) | SRS FR-3.4.4 | 0.5d |
| Implement `POST /api/plates/{id}/dilution-worklist` endpoint | Returns worklist with pre-dilution steps if needed | 0.5d |
| Write OQ-3 (0.5 µL — accepted), OQ-4 (0.49 µL — flagged), OQ-5 (unit conv) | All three boundary tests pass | 1d |

#### 2.3 — Signal Processing (EMA Filter)

| Task | Output | Est. |
|:-----|:-------|:-----|
| Implement `engine/signal.py`: `ema_filter()`, `ema_stream()` generator | SRS FR-3.5.1 | 0.5d |
| Wire filter into telemetry ingest pipeline: raw → filtered → alarm evaluation | SRS FR-3.5.3, FR-3.5.4 | 0.5d |
| Write OQ-6 (step input convergence) | α=0.5, step 0→100 converges within 5% after ≤ 4 iterations | 0.5d |

#### 2.4 — FHIR Validation Layer

| Task | Output | Est. |
|:-----|:-------|:-----|
| Implement `fhir_validator.py` using `fhir.resources` Pydantic models | SRS FR-3.7.1 | 1d |
| Implement DeviceMetric CRUD endpoints with validation | SRS FR-3.7.2 | 1d |
| Implement Observation CRUD endpoints with validation | SRS FR-3.7.3 | 1d |
| Implement `OperationOutcome` error responses | SRS FR-3.7.4 | 0.5d |
| Implement Bundle (transaction/batch) support | SRS FR-3.7.5 | 1d |
| Write OQ-10 (valid Observation), OQ-11 (missing valueQuantity), OQ-12 (missing operationalStatus) | All three return correct status codes and error details | 1d |

#### 2.5 — External Data Clients

| Task | Output | Est. |
|:-----|:-------|:-----|
| Implement `external/accessgudid.py` — FDA API client + local cache | SRS FR-3.10.1 | 1d |
| Implement `external/clinvar.py` — NCBI E-utilities client + local cache | SRS FR-3.10.2 | 1d |
| Seed `devices` table from AccessGUDID Product Code HRX | Pre-populated device registry | 0.5d |
| Implement cache TTL (24h devices, 7d variants) | SRS FR-3.10.3 | 0.5d |

**Phase 2 Exit Criteria:**
- OQ-1 through OQ-6, OQ-10 through OQ-12 all pass
- Barcode validation rejects a plate with d=2 pair; accepts d≥3 plate
- Dilution solver correctly flags 0.49 µL and generates pre-dilution chain
- EMA filter converges on step input as predicted
- FHIR endpoints accept valid resources, reject malformed ones with proper `OperationOutcome`
- External API clients return cached data when upstream is unavailable

---

### Phase 3: Frontend Delivery (Week 7–10)

**Goal:** Build all four UI surfaces with real data flowing from middleware.

*Note: Phase 3 overlaps with Phase 2 (frontend can begin consuming middleware endpoints as they become available).*

#### 3.1 — WebSocket Telemetry Infrastructure

| Task | Output | Est. |
|:-----|:-------|:-----|
| Implement `hooks/useWebSocket.ts` — WSS connection with auto-reconnect + message replay | SRS NFR-R4 | 1d |
| Implement `POST /api/telemetry/stream` (WebSocket endpoint) on middleware | Binary-framed JSON telemetry relay | 1d |
| Implement telemetry ingest route: device → middleware → DB + broadcast to subscribers | End-to-end data flow | 1d |

#### 3.2 — Telemetry Dashboard

| Task | Output | Est. |
|:-----|:-------|:-----|
| Build `TelemetryDashboard` component with ECharts canvas rendering | SRS FR-3.1.1, FR-3.1.4 | 2d |
| Implement real-time multi-channel rendering (pressure, flow, HR, SpO₂) | Four-channel synchronized display | 1d |
| Implement zoom (5s minimum) and pan across session history | SRS FR-3.1.6 | 1d |
| Implement alarm visualization (threshold trace → red within 100 ms) | SRS FR-3.1.5 | 1d |
| Verify 60 fps rendering under Locust load (PQ-1) | Frame counter ≥ 60 during sustained stream | 1d |

#### 3.3 — Microplate Editor

| Task | Output | Est. |
|:-----|:-------|:-----|
| Build `MicroplateEditor` with CSS Grid layout | SRS FR-3.2.1 | 2d |
| Implement well state binding (color-coded: processed/pending/error/gradient) | SRS FR-3.2.2 | 1d |
| Implement click-to-inspect → FHIR `Observation` overlay | SRS FR-3.2.3 | 1d |
| Implement batch selection (drag-select by coordinate range) | SRS FR-3.2.4 | 1d |
| Implement import/export (CSV, JSON manifests) | SRS FR-3.2.5 | 0.5d |
| Implement keyboard navigation (arrow keys) | SRS NFR-U2 | 0.5d |

#### 3.4 — Audit Viewer

| Task | Output | Est. |
|:-----|:-------|:-----|
| Build `AuditViewer` with sortable/filterable table | Paginated audit log display | 1d |
| Add hash chain integrity indicator (green check / red broken per row) | Visual chain verification | 0.5d |
| Add "Verify Chain" button → calls `GET /api/audit/verify` | On-demand integrity check | 0.5d |

#### 3.5 — Admin Console

| Task | Output | Est. |
|:-----|:-------|:-----|
| Build `AdminConsole` — system configuration forms | JWT key rotation, α parameter tuning, Pulse Engine controls | 1d |

#### 3.6 — Human Factors Instrumentation

| Task | Output | Est. |
|:-----|:-------|:-----|
| Implement `hooks/useHumanFactors.ts` — passive metrics collector | SRS FR-3.9.1 | 1d |
| Wire selection latency tracking to alarm acknowledgment events | Time-to-acknowledge (ms) recorded | 0.5d |
| Wire input adjustment step counter to parameter change flows | Steps-per-adjustment recorded | 0.5d |
| Implement JSON export endpoint for uFMEA ingestion | SRS FR-3.9.2 | 0.5d |

**Phase 3 Exit Criteria:**
- Telemetry dashboard renders 4 channels at 60 fps with 100k points/sec stream
- WebSocket auto-reconnects on disconnect with message replay
- Microplate editor supports 96 and 384-well modes with batch select + FHIR inspection
- Audit viewer shows hash chain integrity per row; verify button returns correct status
- Human factors metrics silently collected and exportable

---

### Phase 4: Pulse Engine Integration (Week 9–10)

**Goal:** Integrate Kitware Pulse Physiology Engine for high-fidelity simulation.

#### 4.1 — Core Integration

| Task | Output | Est. |
|:-----|:-------|:-----|
| Verify `PyPulse.so` import in Docker container (IQ-4) | Import succeeds; engine initializes | 0.5d |
| Implement `engine/pulse.py` — `PulseWorker` class with `ProcessPoolExecutor` | SRS FR-3.6.1, FR-3.6.2 | 2d |
| Implement state serialization/deserialization via GPB → JSONB | SRS FR-3.6.3 | 1d |
| Implement data request manager: extract 5 required metrics at configurable intervals | SRS FR-3.6.4 | 1d |
| Implement multi-patient simulation (up to 10 concurrent) | SRS FR-3.6.5 | 1.5d |

#### 4.2 — API & Testing

| Task | Output | Est. |
|:-----|:-------|:-----|
| `POST /api/simulations` — create new patient simulation | Returns simulation ID, initial state | 0.5d |
| `POST /api/simulations/{id}/step` — advance simulation by N time-steps | Returns serialized state + extracted metrics | 0.5d |
| `POST /api/simulations/{id}/pause` / `.../resume` | State persisted to DB, resumable | 0.5d |
| Write IQ-4 + OQ-16 (engine init + state serialization) | Pytest confirms engine lifecycle | 0.5d |
| Write PQ-2 (10 concurrent simulations) + PQ-6 (multi-patient ventilator stress) | Load test with 10 patients; dashboard fps ≥ 55 | 1d |

**Phase 4 Exit Criteria:**
- `import PyPulse` succeeds in Docker; engine initializes and produces valid JSON state
- Single patient simulation yields physiological telemetry matching expected ranges
- 10 concurrent patients maintain ≤ 50 ms per time-step each
- Dashboard renders 10-patient ventilator stress event at ≥ 55 fps

---

### Phase 5: Validation & Hardening (Week 11–12)

**Goal:** Execute full IQ/OQ/PQ suite; performance tuning; documentation finalization.

#### 5.1 — Full Test Suite Execution

| Task | Output | Est. |
|:-----|:-------|:-----|
| Run full IQ suite (IQ-1 through IQ-7) in clean Docker environment | All 7 pass | 0.5d |
| Run full OQ suite (OQ-1 through OQ-16) | All 16 pass | 0.5d |
| Run full PQ suite (PQ-1 through PQ-6) | All 6 pass with metrics recorded | 1d |

#### 5.2 — Performance Tuning

| Task | Output | Est. |
|:-----|:-------|:-----|
| Profile WebSocket message relay path; optimize serialization | < 50 ms P95 latency (NFR-P3) | 1d |
| Profile hash chain verification on 1M rows; add index if needed | < 60 seconds (NFR-P4) | 0.5d |
| Profile barcode pairwise computation; optimize if needed | < 500 ms for 96-index plate (PQ-5) | 0.5d |
| Memory leak check: 24-hour sustained ingest | Growth ≤ 5% (PQ-4) | 1d (run overnight) |

#### 5.3 — Documentation

| Task | Output | Est. |
|:-----|:-------|:-----|
| Write `/docs/URS.md` — User Requirements Specification | Derived from SRS; clinical & safety thresholds | 1d |
| Write `/docs/FRS.md` — Functional Requirements Specification | Maps schemas & math engines to URS | 1d |
| Write developer onboarding guide (`CONTRIBUTING.md`) | Setup, conventions, PR process | 0.5d |
| Finalize README.md with architecture diagram + quickstart | — | 0.5d |

#### 5.4 — Security Review

| Task | Output | Est. |
|:-----|:-------|:-----|
| Audit JWT implementation: expiration, refresh, scope claims | No bypass paths | 0.5d |
| Verify TLS 1.3 on all connections (WSS, HTTPS, PostgreSQL) | Confirmed via `sslyze` or equivalent | 0.5d |
| Verify no secrets in codebase (Docker secrets / env vars only) | `git leak` scan clean | 0.5d |
| Confirm trigger coverage: all append-only tables have BEFORE UPDATE/DELETE | Every table in SRS §6.1 covered | 0.5d |

**Phase 5 Exit Criteria:**
- All 7 IQ, 16 OQ, 6 PQ tests pass
- All performance NFRs met (P1–P6)
- URS.md and FRS.md written and cross-referenced
- Security review clean: no secrets exposed, all TLS enforced, trigger coverage 100%

---

## 5. Dependency Graph

```
Phase 0 (Foundation)
  │
  ├─► Phase 1 (Compliance Tier)
  │     │
  │     └─► Phase 3 (Frontend) ──► Phase 5 (Validation)
  │           ▲                        ▲
  │           │                        │
  ├─► Phase 2 (Algorithms + FHIR) ────┘
  │     │
  │     └─► Phase 4 (Pulse Engine) ───┘
  │
  └─► (All phases depend on Phase 0 Docker + CI)
```

**Critical Path:** Phase 0 → Phase 2 → Phase 3 → Phase 5

**Parallel Opportunities:**
- Phase 1 and Phase 2 can run concurrently (different teams/files)
- Phase 3 frontend can consume Phase 2 endpoints as they're built (overlap weeks 7–8)
- Phase 4 (Pulse) is independent of Phase 3 frontend — can run in parallel weeks 9–10

---

## 6. Milestones & Timeline

| Milestone | Week | Deliverables | Exit Criteria |
|:----------|:-----|:-------------|:--------------|
| **M0: Foundation** | 2 | Docker env, CI/CD, Alembic schema, project scaffolding | `docker-compose up` healthy; CI green |
| **M1: Compliance Tier** | 4 | Append-only triggers, hash chain, audit API | OQ-7/8/9 pass; chain verification works |
| **M2: Algorithms + FHIR** | 8 | Barcode engine, dilution solver, EMA filter, FHIR validation, external data clients | OQ-1 through OQ-6, OQ-10 through OQ-12 pass |
| **M3: Frontend** | 10 | Telemetry dashboard, microplate editor, audit viewer, admin console, human factors | All UI surfaces functional; 60 fps rendering; WSS reconnect works |
| **M4: Pulse Integration** | 10 | Pulse Engine worker pool, multi-patient simulation | OQ-16 passes; PQ-2/PQ-6 passed at load |
| **M5: Validation** | 12 | Full IQ/OQ/PQ suite, URS/FRS docs, security review | All 29 qualification tests pass; docs complete; security clean |

### Timeline (Calendar)

```
Week:  1  2  3  4  5  6  7  8  9  10 11 12
       ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
Phase 0 ████████
Phase 1       ████████
Phase 2             ████████████████████
Phase 3                     ████████████████
Phase 4                             ████████
Phase 5                                     ████████
```

Total: **12 weeks** (single developer / small team). With 2+ developers working in parallel, the critical path compresses to ~10 weeks.

---

## 7. Risk Assessment

### 7.1 Technical Risks

1. Pulse Engine Binary Incompatibility
Original Mitigation: Fallback to synthetic data generator.

The Flaw: You explicitly rejected this, and rightly so. Falling back to synthetic data defeats the purpose of the simulation tier and downgrades the project from an advanced physiological engine to a basic random number generator.

The Hardened Solution (Guaranteed Full Integration): Control the compilation environment. Do not rely on pre-compiled PyPulse.so binaries matching the host Linux machine. Instead, utilize a Multi-Stage Docker Build.

Stage 1 (Builder): Pull a base Ubuntu image, install cmake and gcc, clone the Kitware Pulse repository, and compile the engine natively from C++ source code during the Docker image build.

Stage 2 (Production): Copy only the compiled PyPulse.so and Python bindings into a lightweight Python 3.11 runtime image. This completely eliminates target OS incompatibility while keeping your final container small and secure.

2. PostgreSQL pgcrypto Unavailable
Original Mitigation: Application-level hashing (accepting reduced security posture).

The Flaw: In an FDA 21 CFR Part 11 environment, you cannot accept a reduced security posture. Shifting the hash chaining from the database layer to the Python application layer means anyone with direct SQL access can alter records without breaking the chain. It destroys the core value proposition of the BioSync-Gateway.

The Hardened Solution: First, recognize that pgcrypto is universally supported on AWS RDS, Google Cloud SQL, and Azure Database for PostgreSQL; the risk is artificially inflated. However, if you are forced onto a highly restricted server, do not use Python. Use PostgreSQL’s native sha256(bytea) function, which is built into the core engine (PostgreSQL 11+) and does not require the pgcrypto extension. You can still enforce the cryptographic chain entirely within PL/pgSQL triggers.

3. WebGL 60 FPS Not Achievable
Original Mitigation: Reduce channel count or decimate data (lower fps).

The Flaw: Simply dropping frames or arbitrarily "decimating" (skipping) data points in a medical telemetry stream is dangerous. You might skip over a transient pressure spike (e.g., a micro-occlusion in an arthroscopic pump) that the user needs to see.

The Hardened Solution: Implement Largest Triangle Three Buckets (LTTB) downsampling on the FastAPI backend before pushing to WebSockets. LTTB is an algorithm specifically designed for time-series data that reduces the number of data points while perfectly preserving visual peaks and troughs (anomalies). This reduces the browser's WebGL rendering load without destroying clinical signal integrity.

4. WebSocket Scaling Beyond 500 Connections
Original Mitigation: Horizontal scaling via Redis pub/sub.

The Flaw: While Redis pub/sub is the correct architectural choice for horizontal scaling, it ignores the immediate vertical bottleneck: Python's asynchronous event loop.

The Hardened Solution: Before scaling horizontally, replace FastAPI's default asyncio event loop with uvloop (a Cython drop-in replacement used by Node.js). Additionally, ensure absolutely zero database writes (like the Pulse state saves) are executed synchronously inside the WebSocket route, as a single blocking database call will freeze all 500 active telemetry streams on that worker.

5. Hamming Distance O(n²) Explosion on 384-Well Plates
Original Mitigation: Accept an 8-second calculation delay as "acceptable for a pre-submit validation gate."

The Flaw: This is a severe architectural blind spot. Because FastAPI runs on a single-threaded asynchronous event loop, running a nested for loop in pure Python for 8 seconds will block the entire server. Every active medical WebSocket telemetry stream will freeze for 8 seconds while the server calculates barcodes for the lab team.

The Hardened Solution: Vectorize the math. Do not use pure Python loops. Pass the barcode arrays into NumPy or use SciPy's pdist(matrix, metric='hamming'). By pushing the O(n²) calculation down to the optimized C-backend of NumPy, a 384-well plate comparison (73,440 pairs) will drop from 8 seconds to under 50 milliseconds, completely protecting the async event loop.

### 7.2 Project Risks

| Risk | Likelihood | Impact | Mitigation |
|:-----|:-----------|:-------|:-----------|
| **Scope creep from "nice-to-have" features** | Medium | Medium | Strict phase gates; new features require SRS amendment and phase re-planning |
| **Single developer bottleneck** | Medium | High | Phases 1/2 and 3/4 designed for parallel execution; clear interface contracts between middleware and frontend |
| **Insufficient test coverage for regulatory submission** | Low | High | IQ/OQ/PQ tests written alongside feature code; traceability matrix (SRS §8) maintained throughout |

---

## 8. Resource Requirements

### 8.1 Skill Matrix

| Role | Skills Required | Phases |
|:-----|:----------------|:-------|
| **Backend Developer** | Python, FastAPI, asyncio, PostgreSQL, PL/pgSQL, FHIR | 0, 1, 2, 4, 5 |
| **Frontend Developer** | React, TypeScript, WebGL/Canvas, CSS Grid, WebSocket | 0, 3, 5 |
| **DevOps** | Docker, GitHub Actions, TLS configuration | 0, 5 |
| **QA/Validation** | Pytest, Locust, test vector design, CSV methodology | 1, 2, 4, 5 |

### 8.2 Infrastructure

| Resource | Purpose | Est. Cost |
|:---------|:--------|:----------|
| GitHub repository | Source control, CI/CD | Free (public) |
| Docker Hub | Container image hosting | Free (public) |
| Local development machine | 16 GB RAM, SSD, Docker Desktop | Existing |
| Load test environment | Temporary cloud VM (for PQ-1, PQ-4) | ~$50–100 (spot instance) |

---

## 9. Phase Exit Checklist Template

Each phase must satisfy ALL criteria before proceeding:

```
[ ] All specified tests pass (IQ/OQ/PQ as applicable)
[ ] Code reviewed (if team > 1)
[ ] CI pipeline green on main branch
[ ] docker-compose up succeeds from clean clone
[ ] Phase-specific exit criteria met (see §4)
[ ] No regressions in prior phase tests
[ ] Documentation updated (README, API docs if endpoints added)
```

---

*This development plan is a living document. It should be updated at each milestone to reflect actual progress, discovered risks, and scope adjustments. All changes must be traceable to SRS amendments.*
