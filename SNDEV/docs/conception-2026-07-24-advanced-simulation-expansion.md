Title: srs-advanced-simulation-expansion
Date: 2026-07-24T17:00:00Z
Author: Seth Nenninger (BioSync Agent)
Contribution Type: Conception
Ticket/Context: ad-hoc / Strategic Pulse + LLM/RAG integration proposal
Summary: Fleshed out four Pulse-driven advanced analytics features plus an LLM/RAG text gateway into formal SRS requirements (FR-3.11–FR-3.16) and a composable simulation scenario framework.

## 1. Problem
The BioSync-Gateway SRS (v1.0) defines a baseline telemetry/laboratory middleware but stops at passive Pulse Engine integration (FR-3.6). A strategic proposal supplied four high-value integrations — In Silico PK/PD Lab Loop, Closed-Loop Clinical Chemistry, Synthetic Digital Twin Cohorts, and a Liquid Biopsy/MRD Sandbox — plus a lightweight LLM/RAG clinical-text simulation gateway. These were provided only as prose summaries and lacked: (a) formal functional requirements, (b) traceability to the existing architecture, (c) a mechanism to exercise them end-to-end, and (d) explicit deferral so they do not disrupt the v1.0 delivery.

## 2. Constraints/Analysis
- **No regressions to v1.0:** The expansion must not alter public APIs, compliance tier, or baseline algorithms; it is explicitly deferred until all v1.0 capabilities are complete (user instruction).
- **Architectural fit:** BioSync is async FastAPI + PostgreSQL + Pulse (`PyPulse`). LLM inference must not block the telemetry event loop (existing constraint C1 / new C6).
- **Compliance continuity:** 21 CFR Part 11 immutability, synthetic-only data (C2), and append-only provenance must extend to all new outputs (scenarios, cohorts, LLM text).
- **Reproducibility:** Downstream LIMS/EHR ingestion validation is only credible if deterministic modules are seed-reproducible; LLM modules are non-deterministic by nature and need provenance capture instead of hash equality.
- **Low overhead:** Avoid heavy vector DB / trained models; use local static RAG templates and OpenAI-compatible SDK routing (C8/C9).

## 3. Proposed Solution
Mapped the prose into six new requirement families:
- **FR-3.11 PK/PD Lab Loop:** registers Pulse substances, simulates clearance curves, derives target matrices, and feeds the existing Dilution Solver (FR-3.4) to emit plate worklists.
- **FR-3.12 Clinical Chemistry:** extracts Pulse blood-gas/electrolyte/metabolic vectors, assembles multi-modal FHIR Bundles with ClinVar data, and stress-tests LIMS webhooks.
- **FR-3.13 Digital Twin Cohorts:** deterministically generates N synthetic FHIR patients with reactive Pulse time-series paired to variant sets, flagged `synthetic=true`.
- **FR-3.14 MRD Sandbox:** injects systemic stressors to perturb plasma volume, applies a cfDNA shedding transfer function, and verifies LOD pass/fail via LIMS webhook.
- **FR-3.15 LLM/RAG Gateway:** OpenAI-compatible provider abstraction (OpenRouter / Ollama / vLLM), async-isolated, local static RAG templates, Pulse-to-narrative and ClinVar-to-pathology-report synthesis with append-only provenance.
- **FR-3.16 Scenario Framework (key synthesis):** composes any subset of FR-3.11–FR-3.15 with seeded parameters into replayable, end-to-end simulated scenarios routed to downstream LIMS/EHR harnesses — directly satisfying the "simulated scenarios exercising each feature" objective.

Supporting updates: scope (6→8 domains), definitions (PK/PD, RAG, cfDNA, MRD, LOD, LIMS, EHR, HIPAA/GDPR, OpenRouter/Ollama/vLLM, CAP/CLIA), constraints C6–C9, assumptions A5–A6, NFRs P7/S8/M5/U4, nine new data tables, OQ-17–OQ-23, PQ-7–PQ-8, traceability rows, and repository modules (`middleware/src/simulation/*`, `middleware/src/ai/*`, `frontend ScenarioDesigner`, DB migrations 005/006, new test files). All captured under a v1.1 revision note with explicit deferral.
