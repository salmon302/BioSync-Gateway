# Software Requirements Specification (SRS)

**Project:** BioSync-Gateway — 2D High-Throughput Medical Telemetry & Laboratory Informatics Middleware  
**Version:** 1.0  
**Date:** 2026-07-13  
**Document Type:** Software Requirements Specification (SRS)

---

## 1. Introduction

### 1.1 Purpose

BioSync-Gateway provides a secure, regulatory-compliant middleware gateway bridging clinical device telemetry and high-throughput laboratory automation. It connects edge hardware instruments to a centralized, append-only PostgreSQL storage tier while enforcing FDA 21 CFR Part 11 data integrity throughout the pipeline.

### 1.2 Scope

The system encompasses six major capability domains:

1. **Real-Time Telemetry Visualization:** 2D rendering of time-series surgical device data (pressure, flow rate) at 60 fps via WebGL/Canvas.
2. **Laboratory Automation:** Microplate configuration management (96-well, 384-well), barcode multiplexing safety validation, and automated dilution worklist generation.
3. **Physiological Simulation:** Integration with Kitware Pulse Physiology Engine for high-fidelity patient baseline generation.
4. **FHIR Interoperability:** HL7 FHIR R4 compliant data exchange using `DeviceMetric` and `Observation` resources.
5. **Regulatory Data Integrity:** Cryptographic hash-chained audit trails enforced at the database level via PL/pgSQL triggers and `pgcrypto`.
6. **Human Factors Instrumentation:** Passive UI metrics capture for uFMEA-based usability validation.

### 1.3 Definitions and Acronyms

| Acronym | Definition |
|:--------|:-----------|
| **21 CFR Part 11** | FDA regulation governing electronic records and electronic signatures |
| **CSV** | Computer System Validation |
| **DOM** | Document Object Model |
| **EMA** | Exponential Moving Average (first-order low-pass filter) |
| **FHIR** | Fast Healthcare Interoperability Resources (HL7 standard) |
| **GPB** | Google Protocol Buffers |
| **IQ/OQ/PQ** | Installation Qualification / Operational Qualification / Performance Qualification |
| **JWT** | JSON Web Token |
| **NGS** | Next-Generation Sequencing |
| **PL/pgSQL** | Procedural Language / PostgreSQL |
| **UDI** | Unique Device Identifier / Unique Dual Index |
| **uFMEA** | Usability Failure Modes and Effects Analysis |
| **WebGL** | Web Graphics Library (GPU-accelerated browser rendering) |

### 1.4 References

- FDA 21 CFR Part 11 — Electronic Records; Electronic Signatures
- FDA General Principles of Software Validation
- HL7 FHIR R4 Specification (`http://hl7.org/fhir/R4/`)
- Kitware Pulse Physiology Engine (`https://pulse.kitware.com/`)
- Illumina Adapter Sequences Document (1000000002694)
- AccessGUDID — FDA Global Unique Device Identification Database
- NCBI ClinVar E-utilities API

---

## 2. Overall Description

### 2.1 Product Perspective

BioSync-Gateway is a **three-tier middleware** positioned between:

- **Upstream (Edge):** Clinical hardware (arthroscopic pumps, ventilators), laboratory workstations, and NCBI/AccessGUDID reference APIs.
- **Downstream (Storage):** An append-only PostgreSQL 15+ database with `pgcrypto` extension enabled.

The architecture resolves the tension between high-frequency real-time execution and strict regulatory auditability by decoupling:

1. **Frontend User Console** (React/TypeScript — WebGL rendering, CSS Grid microplate layout)
2. **Processing Engine Middleware** (FastAPI/Python — signal processing, FHIR mapping, Pulse Engine orchestration)
3. **Compliance Storage Tier** (PostgreSQL — trigger-enforced immutability, hash-chained audit ledger)

### 2.2 User Classes and Characteristics

| User Class | Role | Primary Interactions |
|:-----------|:-----|:---------------------|
| **Clinical Technician** | Monitors live surgical telemetry | 2D time-series dashboards; real-time alarm acknowledgment; device parameter adjustment |
| **Laboratory Operator** | Manages sample processing workflows | Plate configuration (96/384-well); barcode validation; dilution manifest review; worklist generation |
| **Compliance/QA Officer** | Conducts regulatory inspections | Audit trail review; hash chain verification; nightly integrity report review |
| **System Administrator** | Maintains deployment health | Docker container orchestration; PostgreSQL extension management; JWT key rotation |

### 2.3 Operating Environment

- **Server OS:** Linux (Docker containerized; Ubuntu 22.04 LTS target)
- **Runtime:** Python 3.11+, Node.js 20 LTS
- **Database:** PostgreSQL 15+ with `pgcrypto` extension
- **Browser:** Chromium 110+, Firefox 115+, Safari 16+ (WebGL 1.0 required)
- **External Dependencies:** Kitware Pulse Engine C++ shared library (`PyPulse.so`)

### 2.4 Design and Implementation Constraints

- **C1:** The Pulse Physiology Engine is single-threaded per patient simulation; all Pulse interactions must be delegated to async worker pools.
- **C2:** The system shall not store Protected Health Information (PHI) directly; simulated patient data shall use synthetic identifiers.
- **C3:** All database mutations on finalized records must be rejected at the storage tier — application-layer audit guards alone are insufficient.
- **C4:** 3D rendering is deliberately excluded to prevent DOM saturation during high-throughput streams.
- **C5:** Barcode validation must use Illumina TruSeq/Nextera authentic adapter sequences (8-base and 10-base) sourced from public documentation.

### 2.5 Assumptions and Dependencies

- **A1:** The Pulse Engine C++ binary (`PyPulse.so`) is pre-compiled and linkable on the target Linux architecture.
- **A2:** The PostgreSQL instance has `pgcrypto` available for `CREATE EXTENSION`.
- **A3:** External APIs (AccessGUDID, ClinVar E-utilities) are accessible for device parameter and variant lookups.
- **A4:** WebSocket connections between frontend and middleware are persistent and support binary frames.

---

## 3. System Features and Functional Requirements

### 3.1 Telemetry Visualization Engine

**FR-3.1.1 — Canvas/WebGL Rendering:** The system shall render all time-series telemetry (pressure, flow rate, heart rate) using an HTML5 Canvas or WebGL context, bypassing SVG DOM manipulation.

**FR-3.1.2 — Frame Rate:** The visualization shall maintain a minimum of 60 fps during sustained streaming of 100,000+ data points.

**FR-3.1.3 — Chart Library:** The frontend shall support Apache ECharts (open-source path) and SciChart.js (enterprise path) as swappable rendering backends via a chart-provider abstraction interface.

**FR-3.1.4 — Telemetry Channels:** The dashboard shall simultaneously render at minimum:

- Continuous arterial pressure waveform (0–150 mmHg range)
- Respiratory flow rate
- Heart rate (derived)
- Oxygen saturation (SpO₂)

**FR-3.1.5 — Alarm Visualization:** Telemetry traces exceeding configurable safety thresholds (e.g., arthroscopic pump pressure > 150 mmHg) shall trigger a visual alarm state (trace color change to red, optional auditory alert) within 100 ms of threshold violation.

**FR-3.1.6 — Zoom and Pan:** Users shall be able to zoom into time ranges as small as 5 seconds and pan across the full session history without frame drops.

### 3.2 Microplate Layout & Laboratory Automation

**FR-3.2.1 — CSS Grid Plate Rendering:** The frontend shall render 96-well and 384-well microplate configurations using CSS Grid layouts with the following grid dimensions:

| Plate Format | Grid (Rows × Columns) | `grid-template-columns` |
|:-------------|:----------------------|:------------------------|
| 96-Well Standard | 8 × 12 | `repeat(12, 1fr)` |
| 384-Well Standard | 16 × 24 | `repeat(24, 1fr)` |

**FR-3.2.2 — Well State Binding:** Each well's visual state (processed, pending, reagent-error, concentration gradient) shall be bound to a React state manager for instantaneous color-coded re-rendering.

**FR-3.2.3 — Well Interaction:** Individual well clicks shall reveal underlying FHIR data payloads (`Observation` resources) associated with that sample.

**FR-3.2.4 — Batch Operations:** Users shall be able to select multiple wells by coordinate (e.g., "Rows A–D, Columns 1–6") and apply batch status changes.

**FR-3.2.5 — Plate Import/Export:** The system shall accept plate manifests in CSV and JSON formats and export validated worklists in the same formats.

### 3.3 Barcode Multiplexing Safety Engine

**FR-3.3.1 — Hamming Distance Calculation:** Upon plate configuration submission, the middleware shall compute the pairwise Hamming distance between all barcode index sequences across the plate:

$$d(B_1, B_2) = \sum_{j=1}^{n} (B_{1,j} \neq B_{2,j})$$

**FR-3.3.2 — Minimum Distance Enforcement:** The system shall reject any plate configuration where any pairwise Hamming distance $d < 3$, returning the offending barcode pair(s) and their distance to the operator.

**FR-3.3.3 — Error Correction Guarantee:** A minimum distance of $d \ge 3$ ensures single-nucleotide sequencing errors (Illumina error rate ≈ 0.1%) are unambiguously correctable.

**FR-3.3.4 — Barcode Source:** The system shall maintain an internal dictionary of authentic 8-base and 10-base TruSeq/Nextera UDI sequences sourced from Illumina documentation (document 1000000002694).

**FR-3.3.5 — Validation Timing:** The Hamming distance check shall execute before the physical pooling instruction is released to the liquid handler.

### 3.4 Automated Dilution Solver

**FR-3.4.1 — Dilution Calculation:** For each sample in a laboratory manifest, the system shall compute the required sample volume using:

$$V_{\text{sample}} = \frac{C_{\text{target}} \cdot V_{\text{target}}}{C_{\text{initial}}}$$

**FR-3.4.2 — Physical Limit Detection:** When the calculated $V_{\text{sample}} < 0.5\,\mu\text{L}$ (the minimum volumetric pipetting limit of standard liquid-handling robots), the system shall:

1. Flag the transaction with a warning code `DILUTION_BELOW_PIPETTE_LIMIT`.
2. Automatically inject a pre-dilution serial array routine (e.g., 1:10 then 1:100 intermediate steps) into the manifest.

**FR-3.4.3 — Serial Dilution Worklist:** The generated pre-dilution steps shall include intermediate transfer-plate coordinates, target concentrations, and required volumes for each step.

**FR-3.4.4 — Concentration Unit Handling:** The solver shall accept concentration inputs in molar (M, mM, µM) and mass/volume (ng/µL, µg/mL) units with automatic conversion.

### 3.5 Signal Processing — Telemetry Smoothing

**FR-3.5.1 — Low-Pass Filter:** The middleware shall apply an adaptive first-order digital low-pass filter (Exponential Moving Average) to all incoming device telemetry streams:

$$y[n] = \alpha \cdot x[n] + (1 - \alpha) \cdot y[n-1]$$

where $\alpha$ is the configurable smoothing factor ($0 < \alpha \le 1$).

**FR-3.5.2 — Tuning:** The default $\alpha$ value shall be 0.2 for pressure channels and 0.1 for flow-rate channels, both overridable via configuration.

**FR-3.5.3 — Raw Data Preservation:** Both raw ($x[n]$) and filtered ($y[n]$) values shall be stored in the database; the raw stream serves as the source of truth for compliance audits.

**FR-3.5.4 — False Alarm Prevention:** The filtered output shall be used for alarm threshold evaluation to prevent mechanical roller-jitter from triggering false system alarms.

### 3.6 Kitware Pulse Physiology Engine Integration

**FR-3.6.1 — Engine Initialization:** The middleware shall initialize a Pulse Physiology Engine instance via the Python API (`PyPulse`) for each requested patient simulation.

**FR-3.6.2 — Async Delegation:** All Pulse simulation time-step computations shall be delegated to `asyncio` worker threads or `ProcessPoolExecutor` workers to prevent blocking of the FastAPI event loop.

**FR-3.6.3 — State Serialization:** The system shall serialize and deserialize full physiological states using Google Protocol Buffers (Engine_pb2), enabling:

- Pause/resume of simulations across API requests
- JSON-format state persistence to PostgreSQL
- State comparison and diffing for audit purposes

**FR-3.6.4 — Data Extraction:** The middleware shall use the Pulse Data Request Manager to extract specific physiological metrics at configurable intervals, including:

- `MeanAirwayPressure_cmH2O`
- `ArterialOxygenPartialPressure_mmHg`
- `OxygenSaturation`
- `HeartRate`
- `RespirationRate`

**FR-3.6.5 — Multi-Patient Simulation:** The system shall support concurrent simulation of up to 10 patients, each in an isolated worker, for stress-testing ventilator-sharing scenarios.

### 3.7 FHIR Interoperability

**FR-3.7.1 — FHIR R4 Compliance:** All clinical data payloads shall be validated against HL7 FHIR R4 Pydantic schemas via the `fhir.resources` library before database insertion.

**FR-3.7.2 — DeviceMetric Mapping:** Static device capabilities and alarm thresholds shall be mapped to FHIR `DeviceMetric` resources, including:

- `category` (measurement vs. setting)
- `operationalStatus` (on, off, standby)
- `unit` (FHIR UCUM codes)
- `measurementPeriod`

**FR-3.7.3 — Observation Mapping:** Real-time telemetry streams from devices and Pulse Engine simulations shall be structured into discrete, timestamped FHIR `Observation` resources, each containing:

- `effectiveDateTime`
- `valueQuantity` (with UCUM unit)
- `subject` reference (simulated patient)
- `device` reference (source instrument)

**FR-3.7.4 — Validation Failure Response:** Schema validation failures shall return an FHIR `OperationOutcome` resource detailing the specific validation error(s) to the caller.

**FR-3.7.5 — Bundle Support:** The system shall support FHIR `Bundle` resources (type: `transaction` and `batch`) for bulk data submission.

### 3.8 Regulatory Data Integrity — Compliance Tier

**FR-3.8.1 — Append-Only Triggers:** The PostgreSQL database shall employ `BEFORE UPDATE OR DELETE` triggers on all audit-trail tables and finalized clinical-record tables. These triggers shall execute `RAISE EXCEPTION` to reject any mutation attempt, rolling back the entire transaction.

**FR-3.8.2 — Trigger Scope:** The triggers shall intercept all mutation sources — FastAPI backend, scheduled CRON jobs, direct SQL console connections, and admin scripts — with no bypass path.

**FR-3.8.3 — Cryptographic Hash Chaining:** Each audit log insertion shall compute a SHA-256 hash ($H_i$) via the `pgcrypto` `digest()` function:

$$H_i = \text{SHA256}(H_{i-1} \mathbin{\Vert} T_i \mathbin{\Vert} U_i \mathbin{\Vert} D_{\text{prev}} \mathbin{\Vert} D_{\text{new}} \mathbin{\Vert} R_i)$$

where:

| Component | Description |
|:----------|:------------|
| $H_{i-1}$ | Hash of the previous chronological log entry (via `LAG()` window function) |
| $T_i$ | Database-generated timestamp (`occurred_at`) — not client-supplied |
| $U_i$ | Authenticated user/API token identity (`actor_id`) |
| $D_{\text{prev}}$ | Previous row state (JSONB canonical form) |
| $D_{\text{new}}$ | New row state (JSONB canonical form) |
| $R_i$ | Human-readable change reason/justification |

**FR-3.8.4 — Tamper Detection:** A nightly automated verification query shall traverse the audit table, recompute all hashes from raw data, compare against stored hashes, and alert QA personnel to the exact row where any hash chain break is detected.

**FR-3.8.5 — JWT Authentication:** All API interactions shall require a valid, non-expired JWT. JWTs shall include claims for `sub` (user identity), `iat` (issued-at), `exp` (expiration), and `scope` (role-based access).

### 3.9 Human Factors Instrumentation

**FR-3.9.1 — Passive Metrics Collection:** The frontend shall run a passive background tracking script that records:

- **Selection Latency:** Time elapsed (ms) between an alarm triggering on the telemetry display and user acknowledgment.
- **Input Adjustment Steps:** Number of discrete interactions required to modify a device parameter (e.g., pump flow rate).

**FR-3.9.2 — uFMEA Data Export:** Collected human-factors metrics shall be exportable as structured JSON for ingestion into Usability Failure Modes and Effects Analysis (uFMEA) workflows.

**FR-3.9.3 — Privacy:** Metrics collection shall be pseudonymized (no PHI, no direct user identity) and stored separately from clinical data.

### 3.10 External Data Integration

**FR-3.10.1 — AccessGUDID Device Lookup:** The system shall query the FDA AccessGUDID API to retrieve device metadata (manufacturer, model, 510(k) number, performance specifications) for devices under FDA Product Code HRX (Arthroscopes and Accessories).

**FR-3.10.2 — ClinVar Variant Lookup:** The laboratory module shall query NCBI ClinVar E-utilities (`esearch`, `esummary`, `efetch`) to retrieve structured variant data (clinical significance, molecular consequence, protein/DNA coordinates, population frequency) for populating simulated diagnostic output.

**FR-3.10.3 — Caching:** External API responses shall be cached locally (TTL: 24 hours for device data, 7 days for variant data) to reduce dependency on external service availability.

---

## 4. External Interface Requirements

### 4.1 User Interfaces

| Interface | Technology | Description |
|:----------|:-----------|:------------|
| Telemetry Dashboard | React + WebGL Canvas | Multi-channel time-series waveform display with alarm states |
| Microplate Editor | React + CSS Grid | Interactive 96/384-well plate layout with click-to-inspect |
| Audit Viewer | React + Table | Sortable, filterable audit log with hash chain integrity indicators |
| Admin Console | React + Forms | System configuration, Pulse Engine control, JWT key management |

### 4.2 Hardware Interfaces

- **Liquid-Handling Robots:** Worklist instructions delivered via CSV/JSON file export (no direct serial/USB control).
- **Medical Devices:** Telemetry ingested via WebSocket connections from edge IoT gateways (protocol: JSON-framed binary).

### 4.3 Software Interfaces

| External System | Protocol | Data Format | Purpose |
|:----------------|:---------|:------------|:--------|
| PostgreSQL 15+ | TCP/IP (libpq) | SQL / JSONB | Primary data store |
| Kitware Pulse Engine | Native Python API (`PyPulse`) | Protocol Buffers / JSON | Physiology simulation |
| AccessGUDID API | HTTPS REST | JSON | Device metadata retrieval |
| NCBI ClinVar E-utilities | HTTPS REST | JSON / XML | Variant data retrieval |
| Illumina Adapter Sequences | Static file | CSV / JSON | Barcode dictionary |

### 4.4 Communication Interfaces

- **Frontend ↔ Middleware:** WebSocket (WSS) for real-time telemetry streaming; HTTPS REST for CRUD operations.
- **Middleware ↔ Database:** PostgreSQL wire protocol (TLS 1.3).
- **Middleware ↔ Pulse Engine:** In-process Python API calls dispatched to worker threads/processes.

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Metric |
|:---|:------------|:-------|
| **NFR-P1** | Telemetry ingestion throughput | ≥ 100,000 data points/second without main-thread blocking |
| **NFR-P2** | WebGL rendering frame rate | ≥ 60 fps sustained during active telemetry streams |
| **NFR-P3** | API response time (95th percentile) | ≤ 200 ms for CRUD operations; ≤ 50 ms for WebSocket message relay |
| **NFR-P4** | Hash chain verification scan (full table) | ≤ 60 seconds for 1 million audit log rows |
| **NFR-P5** | Pulse Engine time-step computation | ≤ 50 ms per physiological time-step (single patient) |
| **NFR-P6** | Concurrent WebSocket connections | ≥ 500 simultaneous telemetry sessions |

### 5.2 Security and Compliance

| ID | Requirement |
|:---|:------------|
| **NFR-S1** | FDA 21 CFR Part 11 compliance: contemporaneous, time-stamped, tamper-proof electronic audit trails (§ 11.10(e)) |
| **NFR-S2** | All API endpoints require JWT Bearer token authentication |
| **NFR-S3** | JWTs shall have a maximum lifetime of 1 hour; refresh tokens, 24 hours |
| **NFR-S4** | All network communication shall use TLS 1.3 (HTTPS/WSS) |
| **NFR-S5** | Database connection shall require client certificate authentication in addition to password |
| **NFR-S6** | Audit trail rows shall be immutable at the database level (no application-layer bypass) |
| **NFR-S7** | Secrets (database credentials, JWT signing keys) shall be injected via Docker secrets or environment variables — never hard-coded |

### 5.3 Reliability and Availability

| ID | Requirement |
|:---|:------------|
| **NFR-R1** | System uptime target: 99.9% (excluding planned maintenance) |
| **NFR-R2** | Graceful degradation: if Pulse Engine is unavailable, the dashboard shall continue to display live device telemetry |
| **NFR-R3** | Database connection pool shall implement automatic reconnection with exponential backoff |
| **NFR-R4** | WebSocket disconnection shall trigger automatic reconnection with message replay for missed data points |

### 5.4 Maintainability and Portability

| ID | Requirement |
|:---|:------------|
| **NFR-M1** | All components shall be Docker-containerized with a single `docker-compose.yml` for local development |
| **NFR-M2** | Chart rendering backend (ECharts vs. SciChart.js) shall be swappable via a provider abstraction without changing consuming components |
| **NFR-M3** | Database migrations shall be managed via Alembic with forward- and backward-compatible scripts |
| **NFR-M4** | All mathematical algorithms (Hamming distance, dilution solver, EMA filter) shall be implemented in pure Python with no external numeric library dependencies beyond NumPy |

### 5.5 Usability

| ID | Requirement |
|:---|:------------|
| **NFR-U1** | Alarm acknowledgment shall require no more than 2 clicks/gestures from the active dashboard view |
| **NFR-U2** | Microplate layout shall support keyboard navigation (arrow keys to traverse wells) |
| **NFR-U3** | The web application shall be fully responsive and usable on displays from 13" (laptop) to 27" (clinical workstation monitor) |

---

## 6. Data Requirements

### 6.1 Database Schema — Core Tables

| Table | Purpose | Mutability |
|:------|:--------|:-----------|
| `patients` | Simulated patient demographics (synthetic) | Append-only after creation |
| `devices` | Medical device registry (populated from AccessGUDID) | Read-only after insertion |
| `device_metrics` | FHIR `DeviceMetric` resources | Read-only after insertion |
| `observations` | FHIR `Observation` resources (telemetry data points) | Append-only after insertion |
| `plates` | Microplate configuration metadata | Append-only after finalization |
| `plate_wells` | Individual well statuses and associated sample data | Append-only after finalization |
| `barcode_indices` | Multiplexing barcode dictionary (Illumina sequences) | Read-only after bulk load |
| `dilution_worklists` | Automated dilution manifests | Append-only after finalization |
| `audit_log` | Hash-chained audit trail | Immutable (BEFORE UPDATE/DELETE trigger rejection) |
| `simulation_states` | Serialized Pulse Engine states (Protocol Buffer → JSONB) | Append-only |
| `human_factors_metrics` | Pseudonymized UI interaction metrics | Append-only |

### 6.2 Data Integrity Constraints

- **D1:** All `audit_log` rows shall have a non-null `prev_hash` (except the genesis row, where `prev_hash` is the SHA-256 of the empty string).
- **D2:** Timestamps shall be generated by the database server (`DEFAULT now()`), never by the application layer.
- **D3:** `observations.valueQuantity` shall always include a valid UCUM unit code.
- **D4:** `plate_wells.coordinate` shall be validated against the parent plate's `format` (e.g., row A–H, col 1–12 for 96-well).

### 6.3 Data Retention

- Audit logs: Indefinite (regulatory requirement).
- Telemetry observations: 7 years (standard medical device record retention).
- Simulation states: 90 days (non-regulatory, purgeable).
- Human factors metrics: 2 years (or duration of associated validation study).

---

## 7. Validation Protocols

### 7.1 Installation Qualification (IQ)

| ID | Test | Acceptance Criteria |
|:---|:-----|:--------------------|
| **IQ-1** | Docker Compose environment starts all services (FastAPI, PostgreSQL, React dev server) | All containers report `healthy` within 120 seconds |
| **IQ-2** | Python 3.11+ is the active runtime in the middleware container | `python --version` reports ≥ 3.11 |
| **IQ-3** | `pgcrypto` extension is available and enabled | `SELECT crypt('test', gen_salt('bf'));` returns a hash |
| **IQ-4** | Pulse Engine binary (`PyPulse.so`) is present and importable | `import PyPulse` succeeds in the Python environment |
| **IQ-5** | Required Python packages installed | `pip check` returns zero conflicts for `fastapi`, `fhir.resources`, `pydantic`, `asyncpg`, `numpy` |
| **IQ-6** | Audit-log triggers are installed | Query `pg_trigger` confirms `before_update_reject` and `before_delete_reject` on `audit_log` table |
| **IQ-7** | Alembic migrations apply cleanly | `alembic upgrade head` completes without error on a fresh database |

### 7.2 Operational Qualification (OQ)

| ID | Test | Acceptance Criteria |
|:---|:-----|:--------------------|
| **OQ-1** | Hamming distance calculation against known test vectors | All Pytest cases pass with exact expected distances (identical → $d=0$, single mismatch → $d=1$, fully divergent → $d=n$; e.g., `CGCTCAGTTC` vs `CGCTCAGTTA` → $d=2$) |
| **OQ-2** | Hamming distance rejection at $d < 3$ | Plate config with any pair at $d=2$ triggers rejection; config with all pairs at $d \ge 3$ is accepted |
| **OQ-3** | Dilution solver boundary: $V_{\text{sample}} = 0.5\,\mu\text{L}$ | Result accepted without pre-dilution flag; $V_{\text{sample}}$ matches computed value to 4 decimal places |
| **OQ-4** | Dilution solver boundary: $V_{\text{sample}} = 0.49\,\mu\text{L}$ | Result flagged with `DILUTION_BELOW_PIPETTE_LIMIT`; at least one pre-dilution step injected |
| **OQ-5** | Dilution solver unit conversion: mM → ng/µL | Input in mM yields correct ng/µL result after molar-mass conversion within 1% tolerance |
| **OQ-6** | EMA filter: $\alpha = 0.5$, step input ($x[n]=0 \rightarrow 100$) | Output $y[n]$ converges to within 5% of 100 after at most 4 iterations |
| **OQ-7** | Audit trigger rejects `UPDATE` on finalized audit_log row | `RAISE EXCEPTION` returned; transaction rolled back; row unchanged after rollback |
| **OQ-8** | Audit trigger rejects `DELETE` on finalized audit_log row | `RAISE EXCEPTION` returned; transaction rolled back; row still present after rollback |
| **OQ-9** | Hash chain integrity: tampered row detected | After manually altering one `data_new` JSONB field, nightly verification query identifies broken chain at tampered row |
| **OQ-10** | FHIR `Observation` validation — valid payload | Valid payload inserts successfully; status code 201 returned |
| **OQ-11** | FHIR `Observation` validation — missing `valueQuantity` | `OperationOutcome` resource returned with severity=`error` and diagnostic message; HTTP 422 |
| **OQ-12** | FHIR `DeviceMetric` validation — missing `operationalStatus` | `OperationOutcome` returned; HTTP 422 |
| **OQ-13** | JWT authentication — valid token | Request with valid JWT succeeds; HTTP 200 |
| **OQ-14** | JWT authentication — expired token | Request returns HTTP 401 with `WWW-Authenticate: Bearer` header |
| **OQ-15** | JWT authentication — no token | Request returns HTTP 401 |
| **OQ-16** | Pulse Engine initialization | `import PyPulse; engine = PulseEngine()` creates valid instance; initial state serializes to valid JSON without error |

### 7.3 Performance Qualification (PQ)

| ID | Test | Acceptance Criteria |
|:---|:-----|:--------------------|
| **PQ-1** | Locust load test: 500 concurrent WebSocket connections, 100,000 points/sec aggregate | Frontend fps ≥ 55; middleware CPU ≤ 80%; zero dropped WebSocket frames over 5-minute run |
| **PQ-2** | Multi-patient simulation: 10 concurrent Pulse Engine instances | All 10 simulations maintain ≤ 50 ms per time-step; no thread-pool exhaustion or task starvation |
| **PQ-3** | Hash chain verification: 1 million audit_log rows | Recompute-and-compare query completes within 60 seconds |
| **PQ-4** | Sustained 24-hour telemetry ingestion at 100,000 points/sec | Zero database deadlocks; memory growth ≤ 5%; audit log grows linearly without insert degradation |
| **PQ-5** | Barcode validation: 96-index plate (4,560 pairwise comparisons) | All pairwise Hamming distances computed within 500 ms |
| **PQ-6** | Simulated multi-patient ventilator stress event | Dashboard maintains ≥ 55 fps while rendering 10 concurrent pressure waveforms from Pulse Engine output |

---

## 8. Traceability Matrix

| Functional Requirement | URS Reference | FRS Reference | OQ Test |
|:-----------------------|:-------------|:-------------|:--------|
| FR-3.1.1 (Canvas/WebGL) | Telemetry Visualization | Frontend Rendering Engine | — |
| FR-3.1.2 (60 fps) | Real-Time Performance | Frame Rate SLA | PQ-1 |
| FR-3.2.1 (CSS Grid Plate) | Microplate Layout | Plate Grid Component | — |
| FR-3.3.1 (Hamming Distance) | Sample Integrity | Barcode Safety Engine | OQ-1, OQ-2 |
| FR-3.3.2 (d ≥ 3 Rejection) | Cross-Contamination Prevention | Barcode Validation Gate | OQ-2 |
| FR-3.4.1 (Dilution Equation) | Measurement Accuracy | Dilution Solver | OQ-3, OQ-4, OQ-5 |
| FR-3.4.2 (0.5 µL Limit) | Hardware Compatibility | Physical Limit Detector | OQ-4 |
| FR-3.5.1 (EMA Filter) | Signal Quality | Telemetry Smoothing Pipeline | OQ-6 |
| FR-3.6.1 (Pulse Engine) | Simulation Authenticity | Pulse Integration Layer | OQ-16 |
| FR-3.7.1 (FHIR R4) | Interoperability | FHIR Validation Middleware | OQ-10, OQ-11, OQ-12 |
| FR-3.8.1 (Append-Only Triggers) | 21 CFR § 11.10(e) | Compliance Trigger Suite | OQ-7, OQ-8 |
| FR-3.8.3 (Hash Chaining) | Audit Trail Integrity | pgcrypto Hash Pipeline | OQ-9 |
| FR-3.8.5 (JWT) | Access Control | Auth Middleware | OQ-13, OQ-14, OQ-15 |
| FR-3.9.1 (Human Factors) | Usability Validation | Metrics Collector | — |

---

## 9. Repository Structure

```
BioSync-Gateway/
├── README.md
├── SRS.md                               # This document
├── docs/
│   ├── URS.md                           # User Requirements Specification
│   └── FRS.md                           # Functional Requirements Specification
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── TelemetryDashboard/      # WebGL/Canvas chart components
│   │   │   ├── MicroplateEditor/        # CSS Grid plate components
│   │   │   ├── AuditViewer/             # Hash chain inspection UI
│   │   │   └── AdminConsole/            # System configuration UI
│   │   ├── providers/
│   │   │   └── chart-provider.ts        # ECharts/SciChart abstraction
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts          # WSS connection management
│   │   │   └── useHumanFactors.ts       # Passive metrics collection
│   │   └── types/
│   │       └── fhir.ts                  # FHIR resource TypeScript types
│   ├── package.json
│   └── tsconfig.json
├── middleware/
│   ├── src/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── telemetry.py         # WebSocket telemetry endpoints
│   │   │   │   ├── plates.py            # Microplate CRUD
│   │   │   │   ├── fhir.py              # FHIR resource endpoints
│   │   │   │   └── audit.py             # Audit log query endpoints
│   │   │   ├── auth.py                  # JWT middleware
│   │   │   └── dependencies.py          # FastAPI dependency injection
│   │   ├── engine/
│   │   │   ├── pulse.py                 # Pulse Engine worker pool
│   │   │   ├── barcode.py               # Hamming distance engine
│   │   │   ├── dilution.py              # Dilution solver
│   │   │   └── signal.py                # EMA filter
│   │   ├── fhir_validator.py            # fhir.resources Pydantic validation
│   │   ├── external/
│   │   │   ├── accessgudid.py           # FDA AccessGUDID client
│   │   │   └── clinvar.py               # NCBI ClinVar client
│   │   └── db/
│   │       ├── models.py                # SQLAlchemy/Alembic models
│   │       └── migrations/              # Alembic migration scripts
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   ├── init/
│   │   ├── 001-extensions.sql           # pgcrypto enablement
│   │   ├── 002-schema.sql               # Core table DDL
│   │   ├── 003-triggers.sql             # BEFORE UPDATE/DELETE triggers
│   │   └── 004-seed-barcodes.sql        # Illumina barcode dictionary
│   └── verify/
│       └── hash-chain-check.sql         # Nightly integrity verification
├── tests/
│   ├── IQ/                              # Installation Qualification
│   │   ├── test_docker_health.py
│   │   ├── test_extensions.py
│   │   └── test_pulse_import.py
│   ├── OQ/                              # Operational Qualification
│   │   ├── test_hamming_distance.py
│   │   ├── test_dilution_solver.py
│   │   ├── test_ema_filter.py
│   │   ├── test_audit_triggers.py
│   │   ├── test_hash_chain.py
│   │   ├── test_fhir_validation.py
│   │   └── test_jwt_auth.py
│   └── PQ/                              # Performance Qualification
│       ├── locustfile.py
│       ├── test_multi_patient_load.py
│       └── test_hash_scan_perf.py
├── docker-compose.yml
└── .env.example
```

---

*Document prepared for Computer System Validation (CSV) under FDA General Principles of Software Validation. This SRS serves as the foundational traceability anchor linking User Requirements (URS) to Functional Requirements (FRS) to Qualification Tests (IQ/OQ/PQ).*
