# Functional Requirements Specification (FRS)

**Project:** BioSync-Gateway — 2D High-Throughput Medical Telemetry & Laboratory Informatics Middleware
**Version:** 1.0 (derived from SRS v1.1)
**Date:** 2026-07-26
**Parent documents:** `SRS.md` (normative), `docs/URS.md` (user requirements)
**Companion:** `database/migrations/*`, `middleware/engine/*`, `frontend/src/*`

---

## 1. Purpose and Scope

This FRS decomposes the SRS functional requirements (FR-3.x), the §6.1 data
schema, and the core **mathematical engines** (Hamming distance, EMA filter,
dilution solver, hash-chain) into concrete components, modules, and files. It
provides the **FR → URS → Component → OQ/PQ** traceability matrix (§7).

Tooling note (D1): load testing adopts **Grafana k6** (`grafana/k6`) for
distributed load (PQ-1), while **pytest micro-benchmarks** remain for the
algorithmic engines. See `docs/URS.md` §8 for cross-references.

---

## 2. Component Architecture Overview

Three-tier middleware (SRS §2.1):

| Tier | Technology | Key Components |
|:–|:–|:–|
| Frontend Console | React + TypeScript (WebGL/Canvas, CSS Grid) | `frontend/src/components/*`, `frontend/src/providers/chart-provider.*`, `frontend/src/hooks/useWebSocket.ts`, `useHumanFactors.ts` |
| Processing Engine | FastAPI / Python | `middleware/api/*`, `middleware/engine/*`, `middleware/simulation/*`, `middleware/ai/*` |
| Compliance Storage | PostgreSQL 15+ (`pgcrypto`) | `database/migrations/002-schema.sql`, `003-triggers.sql`, `hash-chain-check.sql`, `004-seed-barcodes.sql` |

---

## 3. Functional Requirement → Component Mapping

| FR-ID | Responsibility | Implementing Component(s) / File(s) | URS Ref |
|:–|:–|:–|:–|
| FR-3.1.1–3.1.6 | 2D/WebGL telemetry rendering, 60 fps, alarm viz, zoom/pan | `frontend/src/components/TelemetryDashboard/`, `providers/chart-provider.*`, `hooks/useWebSocket.ts` | URS-FR-3.1–3.4 |
| FR-3.2.1–3.2.5 | Microplate CSS-Grid layout, well binding, batch ops, import/export | `frontend/src/components/MicroplateEditor/`, `middleware/api/routes/plates.py` | URS-FR-3.5–3.7 |
| FR-3.3.1–3.3.5 | Hamming distance, d≥3 enforcement, Illumina dictionary | `middleware/engine/barcode.py` (`hamming_distance`, `validate_plate_indices`, `validate_plate_barcodes`); `database/migrations/004-seed-barcodes.sql` | URS-FR-3.8 |
| FR-3.4.1–3.4.4 | Dilution volume solve, 0.5 µL limit, serial pre-dilution, unit handling | `middleware/engine/dilution.py` (`DilutionSolver`, `DilutionWorklist`, `DilutionStep`) | URS-FR-3.9 |
| FR-3.5.1–3.5.4 | EMA low-pass filter, alpha tuning, raw preservation, filtered alarms | `middleware/engine/signal.py` (`MultiChannelEMAFilter`, `EMAFilter`); `middleware/api/routes/telemetry.py` (alarm eval) | URS-SAF-4,5 |
| FR-3.6.1–3.6.5 | Pulse Engine init, async delegation, state serialization, metrics, multi-patient | `middleware/engine/pulse.py` (`PulseWorker`, `SimulationManager`); `middleware/simulation/*` | URS-FR-3.14 |
| FR-3.7.1–3.7.5 | FHIR R4 validation, DeviceMetric/Observation mapping, OperationOutcome, Bundles | `middleware/fhir_validator.py`, `middleware/api/routes/fhir.py` | URS-FR-3.13 |
| FR-3.8.1–3.8.2 | Append-only triggers (no UPDATE/DELETE) on all compliance tables | `database/migrations/002-schema.sql`, `003-triggers.sql` (`prevent_update`, `prevent_delete`) | URS-FR-3.10 |
| FR-3.8.3–3.8.4 | Cryptographic hash chaining + nightly verification | `database/migrations/003-triggers.sql` (`compute_hash_chain`, `verify_hash_chain`); `hash-chain-check.sql`; `middleware/engine/hash_chain.py` | URS-FR-3.11 |
| FR-3.8.5 | JWT auth (sub/iat/exp/scope) | `middleware/api/auth.py` | URS-FR-3.12 |
| FR-3.9.1–3.9.3 | Passive human-factors metrics, uFMEA export, pseudonymization | `frontend/src/hooks/useHumanFactors.ts`, `providers/human-factors-provider.tsx`, `middleware/api/routes/human_factors.py` | URS-FR-3.4 (NFR-U1) |
| FR-3.10.1–3.10.5 | AccessGUDID, ClinVar, caching, LLM routing, RAG repo | `middleware/external/accessgudid.py`, `middleware/ai/llm_gateway.py`, `middleware/ai/rag.py` | URS-FR-3.16 |
| FR-3.11.1–3.11.5 | In-silico PK/PD loop → dilution worklist | `middleware/simulation/pkpd.py` + `engine/dilution.py` | URS-FR-3.15 |
| FR-3.12.1–3.12.4 | Closed-loop clinical chemistry bundle | `middleware/simulation/chemistry.py` | URS-FR-3.15 |
| FR-3.13.1–3.13.5 | Synthetic digital-twin cohorts | `middleware/simulation/digital_twin.py` | URS-FR-3.15 |
| FR-3.14.1–3.14.4 | MRD / liquid-biopsy sandbox | `middleware/simulation/mrd_sandbox.py` | URS-FR-3.15 |
| FR-3.15.1–3.15.7 | LLM/RAG clinical text gateway, provenance | `middleware/ai/llm_gateway.py`, `middleware/ai/rag.py` | URS-FR-3.16 |
| FR-3.16.1–3.16.5 | Integrated scenario orchestrator + UI | `middleware/simulation/scenarios.py`, `frontend/src/ScenarioDesigner/` | URS-FR-3.17 |

---

## 4. Data Schema → Component Mapping (SRS §6.1)

| Table (§6.1) | Owning Module / Component | Mutability Guard |
|:–|:–|:–|
| `audit_log` | `database/migrations/002-schema.sql`, `003-triggers.sql` (`audit_log_hash_chain`, `prevent_update/delete`) | Immutable (trigger reject) |
| `patients`, `devices`, `device_metrics` | `middleware/api/routes/*`, seed/accessgudid | Append-only / read-only |
| `observations` | `middleware/api/routes/telemetry.py`, `engine/signal.py` (raw+filtered) | Append-only |
| `plates`, `plate_wells` | `middleware/api/routes/plates.py`, `engine/barcode.py` | Append-only after finalization |
| `barcode_indices` | `database/migrations/004-seed-barcodes.sql` | Read-only |
| `dilution_worklists` | `engine/dilution.py` | Append-only after finalization |
| `simulation_states` | `engine/pulse.py` (Engine_pb2 ↔ JSONB) | Append-only |
| `human_factors_metrics` | `api/routes/human_factors.py`, `hooks/useHumanFactors.ts` | Append-only (pseudonymized) |
| `simulation_scenarios`, `scenario_runs` | `simulation/scenarios.py` | Append-only |
| `synthetic_cohorts`, `chemistry_profiles`, `pkpd_worklists`, `cfdna_sandbox_runs` | `simulation/*` | Append-only |
| `clinical_text_outputs`, `llm_runs`, `rag_templates` | `ai/llm_gateway.py`, `ai/rag.py` | Append-only / read-only |

Data-integrity constraints (SRS §6.2): `prev_hash` non-null except genesis (D1);
server-generated timestamps (D2); `valueQuantity` UCUM unit (D3); well-coordinate
validation vs plate format (D4) — enforced by `002-schema.sql` CHECKs and
`api/routes/plates.py`.

---

## 5. Mathematical Engine Specifications

The four engines called out in the D2 task (Hamming / EMA / Dilution / Hash-Chain).

### 5.1 Hamming Distance Engine — FR-3.3.1–3.3.5
- **Module:** `middleware/engine/barcode.py`
- **Functions:** `hamming_distance(a, b)`, `validate_plate_indices(sequences, min_distance=3)`, `validate_plate_barcodes(plate_id, barcode_sequences, barcode_set)`
- **Formula:** `d(B₁, B₂) = Σ (B₁,ⱼ ≠ B₂,ⱼ)`
- **Enforcement:** reject any pair with `d < 3`; return offending pair(s) + distance.
- **Data:** authentic 8-base / 10-base Illumina TruSeq/Nextera UDI sequences in `barcode_indices` (seeded by `004-seed-barcodes.sql`).
- **URS:** URS-FR-3.8, URS-SAF-7.

### 5.2 EMA (Low-Pass) Filter — FR-3.5.1–3.5.4
- **Module:** `middleware/engine/signal.py`
- **Classes:** `EMAFilter(alpha)`, `MultiChannelEMAFilter` (per-channel alpha: 0.2 pressure / 0.1 flow default).
- **Formula:** `y[n] = α·x[n] + (1−α)·y[n−1]`, `0 < α ≤ 1`.
- **Behavior:** both raw `x[n]` and filtered `y[n]` persisted (`observations.raw_data` / `filtered_data`); alarms evaluated on **filtered** value to prevent false alarms (URS-SAF-4/5).
- **URS:** URS-FR-3.1, URS-SAF-4/5.

### 5.3 Dilution Solver — FR-3.4.1–3.4.4
- **Module:** `middleware/engine/dilution.py`
- **Classes:** `DilutionSolver(min_volume=0.5)`, `DilutionWorklist`, `DilutionStep`.
- **Formula:** `V_sample = (C_target · V_target) / C_initial`.
- **Behavior:** when `V_sample < 0.5 µL` → flag `DILUTION_BELOW_PIPETTE_LIMIT` + inject serial pre-dilution steps (e.g., 1:10 / 1:100). Accepts molar and mass/volume units with auto-conversion.
- **URS:** URS-FR-3.9, URS-SAF-8.

### 5.4 Hash-Chain Engine — FR-3.8.3 / 3.8.4
- **Database trigger:** `compute_hash_chain()` in `database/migrations/003-triggers.sql` (BEFORE INSERT on `audit_log`); reads previous row's `current_hash`, computes SHA-256 via `pgcrypto.digest`.
- **Formula:** `Hᵢ = SHA256( Hᵢ₋₁ ‖ Tᵢ ‖ Uᵢ ‖ D_prev ‖ D_new ‖ Rᵢ )`
  - `Hᵢ₋₁`: previous `current_hash` (genesis = 64 zeros).
  - `Tᵢ`: DB-generated `occurred_at` (not client).
  - `Uᵢ`: `actor_id` (`user_id`); `D_prev`/`D_new`: canonical JSONB; `Rᵢ`: reason.
- **Verification:** `verify_hash_chain()` SQL function + `hash-chain-check.sql` (nightly recompute-and-compare; reports first broken row). Python mirror: `middleware/engine/hash_chain.py` (`compute_hash`, `verify_chain`, `GENESIS_HASH`).
- **Performance gate:** NFR-P4 — full-table verify **≤ 60 s for 1M rows** (see PQ-3, `tests/performance/test_pq3_1m_rows.py`).
- **URS:** URS-FR-3.10/3.11, URS-SAF-9/10.

---

## 6. Non-Functional Mapping (selected)

| NFR | Enforced By | Ref |
|:–|:–|:–|
| NFR-P1 (≥100k pts/s ingest) | `api/routes/telemetry.py` + `engine/signal.py`; PQ-4 soak (`SNDEV/scripts/pq4_24h_ingest.py`, deferred) | URS-FR-3.1 |
| NFR-P2 (≥60 fps) | `TelemetryDashboard` + `chart-provider` (ECharts path) | URS-FR-3.1 |
| NFR-P3 (P95 ≤200 ms CRUD / ≤50 ms WS) | FastAPI routes; **k6 PQ-1** enforces P95<250 ms SLO | URS-FR-3.1 |
| NFR-P4 (1M hash verify ≤60 s) | `hash-chain-check.sql` + PQ-3 | URS-FR-3.11 |
| NFR-P6 (≥500 WS) | `api/routes/telemetry.py` ConnectionManager | URS-FR-3.1 |
| NFR-S1..S8 | triggers, JWT, TLS, secrets injection | URS-FR-3.10/3.12 |
| NFR-M2/M4 | `chart-provider` abstraction; pure-Python engines (NumPy only) | URS §6 |
| NFR-U1..U4 | dashboard UX, keyboard nav, Scenario Designer | URS-FR-3.4/3.17 |

---

## 7. Traceability Matrix (FR → URS → Component → OQ/PQ)

| FR | URS | Component | OQ / PQ |
|:–|:–|:–|:–|
| FR-3.1.1 (Canvas/WebGL) | URS-FR-3.1 | TelemetryDashboard / chart-provider | — |
| FR-3.1.2 (60 fps) | URS-FR-3.1 | chart-provider (ECharts) | PQ-1 (k6), PQ-6 |
| FR-3.1.5 (alarm ≤100 ms) | URS-SAF-1..6 | telemetry.py alarm eval | — |
| FR-3.2.1 (CSS Grid) | URS-FR-3.5 | MicroplateEditor | — |
| FR-3.3.1 (Hamming) | URS-FR-3.8 | engine/barcode.py | OQ-1, OQ-2 |
| FR-3.3.2 (d≥3 reject) | URS-SAF-7 | engine/barcode.py | OQ-2 |
| FR-3.4.1 (dilution eq) | URS-FR-3.9 | engine/dilution.py | OQ-3, OQ-5 |
| FR-3.4.2 (0.5 µL limit) | URS-SAF-8 | engine/dilution.py | OQ-4 |
| FR-3.5.1 (EMA) | URS-SAF-5 | engine/signal.py | OQ-6 |
| FR-3.6.1 (Pulse) | URS-FR-3.14 | engine/pulse.py | OQ-16, PQ-2 |
| FR-3.7.1 (FHIR R4) | URS-FR-3.13 | fhir_validator.py | OQ-10..12 |
| FR-3.8.1 (append-only) | URS-FR-3.10 | 003-triggers.sql | OQ-7, OQ-8 |
| FR-3.8.3 (hash chain) | URS-FR-3.11 | 003-triggers.sql / hash_chain.py | OQ-9, **PQ-3** |
| FR-3.8.5 (JWT) | URS-FR-3.12 | api/auth.py | OQ-13..15 |
| FR-3.9.1 (human factors) | URS-FR-3.4 | useHumanFactors.ts | — |
| FR-3.11 (PK/PD) | URS-FR-3.15 | simulation/pkpd.py | OQ-17 |
| FR-3.12 (chemistry) | URS-FR-3.15 | simulation/chemistry.py | OQ-18 |
| FR-3.13 (digital twin) | URS-FR-3.15 | simulation/digital_twin.py | OQ-19 |
| FR-3.14 (MRD) | URS-FR-3.15 | simulation/mrd_sandbox.py | OQ-20 |
| FR-3.15 (LLM/RAG) | URS-FR-3.16 | ai/llm_gateway.py, ai/rag.py | OQ-21, OQ-22 |
| FR-3.16 (scenarios) | URS-FR-3.17 | simulation/scenarios.py | OQ-23 |

---

## 8. Documented Deviations

### 8.1 SciChart Rendering Backend (SRS FR-3.1.3)
SRS §3.1.3 specifies **two** swappable chart backends behind the
`chart-provider` abstraction: **Apache ECharts** (open-source, **implemented**)
and **SciChart.js** (enterprise, **not integrated — deviation**). The seam in
`frontend/src/providers/chart-provider.*` allows the SciChart.js backend to be
enabled once an enterprise license is procured. Until then only ECharts is built
and shipped; NFR-P2 (≥60 fps) is met by that path. (See also `docs/URS.md`
§9.1.)

*All other SRS FRs are implemented as specified. Performance qualification
status: PQ-1 → k6 (`tests/performance/k6/pq1_websocket.js`); PQ-3 →
`tests/performance/test_pq3_1m_rows.py`; PQ-4 → deferred
(`SNDEV/scripts/pq4_24h_ingest.py` skeleton).*
