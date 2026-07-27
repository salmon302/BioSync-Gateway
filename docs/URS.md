# User Requirements Specification (URS)

**Project:** BioSync-Gateway — 2D High-Throughput Medical Telemetry & Laboratory Informatics Middleware
**Version:** 1.0 (derived from SRS v1.1)
**Date:** 2026-07-26
**Parent document:** `SRS.md` (Software Requirements Specification, §1–3)
**Companion document:** `docs/FRS.md` (Functional Requirements Specification)

---

## 1. Introduction

### 1.1 Purpose
This User Requirements Specification (URS) captures the **user-facing** needs for BioSync-Gateway: who uses the system, what they must be able to accomplish, the clinical and safety thresholds they depend on, and the environment in which they operate. It is derived directly from `SRS.md` §1 (Introduction), §2 (Overall Description), and §3 (System Features) and serves as the parent requirement baseline for `docs/FRS.md`.

### 1.2 Scope
The URS covers the eight capability domains enumerated in SRS §1.2 from the **user's** perspective:
real-time telemetry visualization, laboratory automation, physiological simulation, FHIR interoperability, regulatory data integrity, human-factors instrumentation, advanced simulation analytics, and AI-generated clinical text simulation.

### 1.3 Relationship to SRS and FRS
- **SRS.md** is the normative source. Where this URS and the SRS disagree, the SRS governs.
- **FRS.md** decomposes each user requirement below into components, modules, data tables, and mathematical engines, and provides the FR→URS traceability matrix.

---

## 2. User Classes and Characteristics

Derived from SRS §2.2. Each class implies a distinct set of user requirements (§3).

| User Class | Role | Primary Interactions |
|:–|:–|:–|
| **Clinical Technician** | Monitors live surgical telemetry | 2D time-series dashboards; real-time alarm acknowledgment; device parameter adjustment |
| **Laboratory Operator** | Manages sample processing workflows | Plate configuration (96/384-well); barcode validation; dilution manifest review; worklist generation |
| **Compliance/QA Officer** | Conducts regulatory inspections | Audit trail review; hash-chain verification; nightly integrity report review |
| **System Administrator** | Maintains deployment health | Docker container orchestration; PostgreSQL extension management; JWT key rotation |

---

## 3. User-Facing Functional Requirements

Written from the user's viewpoint. The `Source FR` column cites the SRS functional requirement; the `FRS` column cites the implementing component in `docs/FRS.md`.

### 3.1 Telemetry Visualization (Clinical Technician)
| URS-ID | User Requirement | Source FR | FRS |
|:–|:–|:–|:–|
| URS-FR-3.1 | View continuous time-series telemetry (pressure, flow, heart rate, SpO₂) in a responsive 2D dashboard that sustains smooth motion during high-throughput streams. | FR-3.1.1–FR-3.1.4 | FRS §3, §5 |
| URS-FR-3.2 | Receive an unmistakable visual (and optional auditory) alarm within ~100 ms when a safety threshold is violated (e.g., arthroscopic pump pressure > 150 mmHg). | FR-3.1.5 | FRS §3, §4 (Safety) |
| URS-FR-3.3 | Zoom into time ranges as small as 5 seconds and pan full session history without frame drops. | FR-3.1.6 | FRS §3 |
| URS-FR-3.4 | Acknowledge an alarm with no more than 2 clicks/gestures from the active dashboard. | (NFR-U1) | FRS §6 |

### 3.2 Laboratory Automation (Laboratory Operator)
| URS-ID | User Requirement | Source FR | FRS |
|:–|:–|:–|:–|
| URS-FR-3.5 | Configure and visually inspect 96-well and 384-well microplate layouts with instantaneous, color-coded well-state rendering. | FR-3.2.1–FR-3.2.3 | FRS §3, §5 |
| URS-FR-3.6 | Select multiple wells by coordinate and apply batch status changes. | FR-3.2.4 | FRS §3 |
| URS-FR-3.7 | Import plate manifests (CSV/JSON) and export validated worklists in the same formats. | FR-3.2.5 | FRS §3, §5 |
| URS-FR-3.8 | Be prevented from releasing a pooling instruction when any pair of multiplexing barcodes is too similar (minimum Hamming distance not met), with the offending pair(s) identified. | FR-3.3.1–FR-3.3.5 | FRS §5 (Hamming) |
| URS-FR-3.9 | Obtain a correct per-sample dilution volume, and be warned (with an auto-generated serial pre-dilution routine) when the computed volume falls below the liquid handler's physical pipetting limit. | FR-3.4.1–FR-3.4.4 | FRS §5 (Dilution) |

### 3.3 Regulatory Data Integrity (Compliance/QA Officer)
| URS-ID | User Requirement | Source FR | FRS |
|:–|:–|:–|:–|
| URS-FR-3.10 | Trust that audit records are immutable — no application, script, or direct SQL console can alter or delete a finalized audit entry. | FR-3.8.1, FR-3.8.2 | FRS §3, §5 (Hash Chain) |
| URS-FR-3.11 | Verify, on demand and nightly, that the cryptographic hash chain across the full audit log is intact and be told the exact row where any break occurs. | FR-3.8.3, FR-3.8.4 | FRS §3, §5 (Hash Chain) |
| URS-FR-3.12 | Access the system only with a valid, expiring JWT; have role/permission-scoped access enforced. | FR-3.8.5 | FRS §3 (Auth) |

### 3.4 Interoperability & Simulation (all classes)
| URS-ID | User Requirement | Source FR | FRS |
|:–|:–|:–|:–|
| URS-FR-3.13 | Exchange clinical data as HL7 FHIR R4 `DeviceMetric`/`Observation`/`Bundle` resources that validate before storage. | FR-3.7.1–FR-3.7.5 | FRS §3, §5 |
| URS-FR-3.14 | Run high-fidelity, reproducible patient simulations (Kitware Pulse) for training, stress-testing, and analytics without blocking live telemetry. | FR-3.6.1–FR-3.6.5 | FRS §3, §5 |
| URS-FR-3.15 | Generate synthetic digital-twin cohorts, in-silico PK/PD worklists, clinical-chemistry bundles, and MRD/Liquid-Biopsy sandbox outputs for downstream LIMS/EHR validation. | FR-3.11–FR-3.14 | FRS §3 |
| URS-FR-3.16 | Synthesize unstructured clinical/narrative text from structured telemetry via a swappable LLM provider, with provenance captured for every artifact. | FR-3.15.1–FR-3.15.7 | FRS §3 |
| URS-FR-3.17 | Assemble, configure, execute, and inspect integrated multi-feature simulation scenarios and their downstream validation results. | FR-3.16.1–FR-3.16.5 | FRS §3 |

---

## 4. Clinical and Safety Thresholds

These are the thresholds the user implicitly relies on for patient safety and regulatory defensibility (SRS §3.1.5, §3.5.4, §5).

| URS-ID | Threshold | Value | Source | User Impact |
|:–|:–|:–|:–|:–|
| URS-SAF-1 | Arthroscopic pump pressure alarm | > 150 mmHg (high) | FR-3.1.5 | Prevents tissue over-pressure injury |
| URS-SAF-2 | Heart-rate alarm band | > 120 bpm (high) / < 50 bpm (low) | FR-3.1.5 | Detects instability |
| URS-SAF-3 | SpO₂ alarm | < 90 % (low) | FR-3.1.5 | Detects desaturation |
| URS-SAF-4 | Flow-rate alarm band | > 60 / < −60 L/min | FR-3.1.5 | Detects perfusion anomalies |
| URS-SAF-5 | Alarm evaluation basis | On **EMA-filtered** signal, not raw samples | FR-3.5.4 | Prevents false alarms from mechanical jitter |
| URS-SAF-6 | Alarm visual latency | ≤ 100 ms from threshold violation | FR-3.1.5 | Clinician reaction time |
| URS-SAF-7 | Barcode cross-contamination guard | Minimum Hamming distance **d ≥ 3** between any pair | FR-3.3.2–FR-3.3.3 | Correctable single-nucleotide sequencing error |
| URS-SAF-8 | Pipetting physical limit | Minimum sample volume 0.5 µL | FR-3.4.2 | Prevents invalid transfers |
| URS-SAF-9 | Audit immutability | No UPDATE/DELETE on finalized records at DB tier | FR-3.8.1 | 21 CFR Part 11 §11.10(e) |
| URS-SAF-10 | Audit contemporaneity | Timestamps generated by the database server | (D2, SRS §6.2) | Trustworthy event ordering |

---

## 5. Operating Environment

Derived from SRS §2.3.

| Aspect | Requirement |
|:–|:–|
| Server OS | Linux, Docker-containerized (Ubuntu 22.04 LTS target) |
| Runtime | Python 3.11+, Node.js 20 LTS |
| Database | PostgreSQL 15+ with `pgcrypto` extension |
| Browser | Chromium 110+, Firefox 115+, Safari 16+ (WebGL 1.0 required) |
| External dependency | Kitware Pulse Physiology Engine C++ shared library (`PyPulse.so`) |

---

## 6. User-Relevant Constraints

Summarized from SRS §2.4 (impact on the user experience):

- **C1 / C6 (Non-blocking):** Simulations and AI text generation must never degrade or block live telemetry (user always sees data).
- **C2 / C7 (Non-PHI):** All patient/sample data is synthetic; no real PHI is processed.
- **C3 (Enforced immutability):** Users cannot "edit" finalized records; corrections are new append-only entries.
- **C4 (No 3D):** UI is intentionally 2D to protect rendering performance.
- **C5 (Authentic barcodes):** Only Illumina TruSeq/Nextera authentic sequences are accepted.
- **C8 / C9 (Swappable providers, local RAG):** LLM backend and retrieval source are configuration-driven, with no code changes.

---

## 7. Assumptions and Dependencies

From SRS §2.5: the Pulse binary is pre-compiled and linkable (A1); `pgcrypto` is available (A2); external APIs (AccessGUDID, ClinVar) are reachable (A3); WebSocket transport is persistent with binary frames (A4); an LLM endpoint is reachable (A5); static RAG templates are present locally (A6).

---

## 8. Traceability and Cross-References

- **SRS.md** — normative source (§1–3 used here; §4–8 for interface, data, validation, and traceability detail).
- **docs/FRS.md** — decomposes every `URS-FR-*` / `URS-SAF-*` above into components, data tables, and math engines, with a full FR→URS matrix.
- **Validation:** User requirements are verified through the OQ/PQ protocols in SRS §7 (e.g., URS-SAF-7 → OQ-1/OQ-2; URS-FR-3.10 → OQ-7/OQ-8; URS-FR-3.11 → OQ-9 / PQ-3).

---

## 9. Documented Deviations

### 9.1 SciChart Rendering Backend (SRS FR-3.1.3)
SRS §3.1.3 specifies **two** swappable chart backends behind a provider abstraction:
1. **Apache ECharts** (open-source path) — **implemented**, and
2. **SciChart.js** (enterprise path) — **not integrated (deviation)**.

The `chart-provider` abstraction (`frontend/src/providers/chart-provider.*`) retains the seam so the SciChart.js backend can be enabled later once an enterprise license is procured. Until then, only the ECharts backend is built and shipped. This deviation does not affect the functional or performance requirements (NFR-P2: ≥ 60 fps) which are met by the ECharts path.

*All other SRS requirements are implemented as specified unless called out in `docs/FRS.md`.*
