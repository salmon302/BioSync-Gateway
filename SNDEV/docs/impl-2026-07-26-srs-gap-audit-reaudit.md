Title: SRS-v1.1 → Implementation Gap Audit & Future Development Plan (Re-audit)
Date: 2026-07-26T19:30:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc audit of working tree vs SRS.md v1.1 (2026-07-24)
Summary: Re-verified BioSync-Gateway ground truth; the four v1.1 simulation modules (FR-3.11–3.14) are now backend-implemented and wired, but FR-3.15 (LLM/RAG) and FR-3.16 (Scenario orchestrator + UI) remain schema-only with no code. Documents the shifted remaining-work baseline and a prioritized roadmap.

---

# BioSync-Gateway — Remaining Work Audit (Re-verified 2026-07-26)

## 0. Headline Verdict (what changed since the 2026-07-26 morning audit)

The earlier `impl-2026-07-26-srs-remaining-work.md` stated **all** of FR-3.11–FR-3.16 were entirely missing. A fresh ground-truth inspection of the current tree shows that is **no longer accurate**: four of the six advanced modules have been implemented at the **backend** level since that document was written.

| SRS FR | Status now (ground truth) | Was (morning audit) |
|:--|:--|:--|
| FR-3.11 PK/PD Lab Loop | ✅ Backend implemented + routed + tested | ❌ Missing |
| FR-3.12 Clinical Chemistry | ✅ Backend implemented + routed + tested | ❌ Missing |
| FR-3.13 Digital Twin Cohorts | ✅ Backend implemented + routed + tested | ❌ Missing |
| FR-3.14 MRD / Liquid Biopsy | ✅ Backend implemented + routed + tested | ❌ Missing |
| FR-3.15 LLM/RAG Text Gateway | ⚠️ **Schema-only** — no code, no route, no RAG assets | ❌ Missing |
| FR-3.16 Scenario Framework | ⚠️ **Schema-only** — no orchestrator, no route, no UI | ❌ Missing |

**The dominant remaining work has therefore shifted** from "implement all six v1.1 features" to:
1. **Build FR-3.15 (LLM/RAG gateway)** — the only advanced feature with *zero* implementation.
2. **Build FR-3.16 (Scenario orchestrator + Scenario Designer UI)** — schema exists, orchestrator does not.
3. **Promote the four implemented modules from "backend-only" to "validated + integrated"** (real Pulse integration per G2, frontend visibility, dedicated OQ-17…OQ-20 / PQ-8 qualification).
4. **Close the v1.0 carry-over gaps** (G1, G3, G5, G7, G9 primarily; G2/G4/G6/G8 already resolved/deferred).

---

## 1. Method & Scope

- Measured the working tree (branch `main`) against `SRS.md` **v1.1** (2026-07-24).
- Verification was by **direct source inspection and grep** (file:line evidence below), not by executing the full test suite (most v1.1 tests are DB-gated and run in CI).
- DB schema verified via `middleware/models.py` and `middleware/alembic/versions/0007_v1_1_advanced_analytics.py`.
- API surface verified via `middleware/api/main.py` router registration.

---

## 2. v1.1 Advanced Analytics — Detailed Status

### 2.1 FR-3.11 — In Silico PK/PD Lab Loop  →  ✅ BACKEND DONE
- `middleware/simulation/pkpd.py`: `PkpdSubstance`, `simulate_clearance()`, `derive_target_matrix()`, `build_pkpd_worklist_steps()`, `generate_pkpd_worklist()` — real algorithms.
- `middleware/api/routes/pkpd.py` (prefix `/api/simulation`, registered `main.py:176`): create/get/list worklists; `scenario_run_id` linkage present.
- `middleware/models.py:307` `pkpd_worklists` (with `origin='pk_pd_loop'` check constraint, `models.py:324`).
- Test: `tests/unit/test_pkpd.py` (pure + DB-gated).
- **Caveat (C7 vs FR-3.6):** docstring/implementation synthesizes clearance curves deterministically from a numeric seed rather than registering substances into a *live* Pulse engine state (`pkpd.py` does not import `engine.pulse`). Acceptable for reproducibility (C7) but **not** a true FR-3.11.1 Pulse-state integration until G2 (real PyPulse) is resolved.

### 2.2 FR-3.12 — Closed-Loop Clinical Chemistry  →  ✅ BACKEND DONE
- `middleware/simulation/chemistry.py`: `generate_chemistry_vectors()`, `_observation_resource()`, `_genomics_resource()`, `assemble_multimodal_bundle()`, `send_lims_bundle()` (real `httpx` webhook post), `generate_chemistry_profile()`.
- `middleware/api/routes/chemistry.py` (`main.py:177`); `models.py:286` `chemistry_profiles`.
- Test: `tests/unit/test_chemistry.py` (includes mocked LIMS round-trip).
- **Caveat:** chemistry vectors are synthesized, not extracted from a live Pulse state (`chemistry.py:1` docstring: "given the currently mocked Pulse Engine, synthesizes"). Same G2 dependency as 2.1.

### 2.3 FR-3.13 — Synthetic Digital Twin Cohorts  →  ✅ BACKEND DONE
- `middleware/simulation/digital_twin.py`: `generate_cohort_members()`, `_vital_observation()`, `_genomics_observation()`, `simulate_member_timeseries()`, `assemble_cohort_bundle()`, `generate_synthetic_cohort()`, `export_cohort_bundle()`. Emits FHIR `Observation` resources, `synthetic=true` flag present.
- `middleware/api/routes/digital_twin.py` (`main.py:178`); `models.py:263` `synthetic_cohorts`.
- Test: `tests/unit/test_digital_twin.py`.
- **Caveat:** trends synthesized from seed, not driven by Pulse engine (docstring, `digital_twin.py:1`).

### 2.4 FR-3.14 — MRD / Liquid Biopsy Sandbox  →  ✅ BACKEND DONE
- `middleware/simulation/mrd_sandbox.py`: `apply_stressor()`, `cfdna_shedding()`, `evaluate_lod()`, `build_cfdna_observation()`, `verify_lims_webhook()`, `run_mrd_sandbox()`, `generate_mrd_narrative()`, `generate_cfdna_sandbox_run()`.
- `middleware/api/routes/mrd.py` (`main.py:179`); `models.py:330` `cfdna_sandbox_runs`.
- Test: `tests/unit/test_mrd_sandbox.py` (mocked LIMS post).
- **Dangling dependency (action item):** `mrd_sandbox.py:504` does `from ai.llm_gateway import generate_text` as a lazy import. The `ai` package **does not exist** (see 2.5), so MRD narrative generation would raise `ModuleNotFoundError` if invoked. This is a soft `# pragma: no cover` hook today but must be resolved when FR-3.15 lands.

### 2.5 FR-3.15 — LLM/RAG Clinical Text Gateway  →  ⚠️ SCHEMA-ONLY (NO CODE)
- **Missing entirely:**
  - No `middleware/ai/` directory (no `llm_gateway.py`, no `rag.py`).
  - No `middleware/api/routes/ai.py` (not registered in `main.py`).
  - No OpenAI-compatible client abstraction; no provider swappability (C8).
  - No RAG retrieval / template-merge logic (C9).
  - No `.env`/config for `OPENROUTER_API_KEY` / `OLLAMA_BASE_URL` (verified `middleware/.env` and `.env.example` contain no LLM provider keys).
  - No RAG template asset files anywhere in the repo (`grep "rag|template"` returns only `fhir.resources` library files and `pygments` lexers — no project RAG assets).
- **Schema present but empty:**
  - `models.py:357` `llm_runs` (with `provider` column `openrouter/ollama/vllm`), `models.py:378` `clinical_text_outputs`, `models.py:396` `rag_templates`.
  - `0007_…_advanced_analytics.py` creates these three tables (lines 88, 270) **but inserts NO seed rows into `rag_templates`** — so FR-3.15.3 has a registry table with zero templates.
- **Unmet sub-requirements:** 3.15.1 (provider abstraction), 3.15.2 (async isolation), 3.15.3 (RAG repo), 3.15.4 (Pulse→narrative), 3.15.5 (pathology RAG), 3.15.6 (provenance — table exists, nothing writes it), 3.15.7 (EHR harness). **None implemented.**

### 2.6 FR-3.16 — Integrated Simulation Scenario Framework  →  ⚠️ SCHEMA-ONLY (NO ORCHESTRATOR/UI)
- **Schema present:** `models.py:217` `simulation_scenarios` (FR-3.16.1), `models.py:237` `scenario_runs` (FR-3.16.2/3/4); both created in `0007` (lines 104, 122). All four implemented modules accept `scenario_run_id` to attach outputs to a run (`pkpd.py:272`, `chemistry.py:247`, `digital_twin.py:237`, `mrd_sandbox.py:532`).
- **Missing entirely:**
  - No `middleware/simulation/scenarios.py` orchestrator. Explicitly declared TODO in `middleware/simulation/__init__.py:10` ("scenarios.py (FR-3.16) — to be added").
  - No scenario API route (no `api/routes/scenario*.py`; `api/routes/simulations.py` is **Pulse-engine lifecycle only** — create/step/pause/resume/stop/status/metrics/state/export/diff/purge/list, confirmed by endpoint grep).
  - No downstream validation harness API (FR-3.16.3).
  - **No frontend `ScenarioDesigner/`** and no `/scenario` route in `frontend/src/App.tsx` (frontend pages are only TelemetryDashboard, MicroplateEditor, AuditViewer, AdminConsole). FR-3.16.5 unmet.
- **Unmet sub-requirements:** 3.16.1 (spec API), 3.16.2 (orchestration engine), 3.16.3 (downstream validation harness), 3.16.4 (determinism/replay — tables exist, no logic), 3.16.5 (UI).

---

## 3. v1.0 Carry-Over Gaps — Current State

Re-verified the G-series from the morning audit. Net status:

| # | Gap | Status | Evidence / Note |
|:--|:--|:--|:--|
| G1 | Barcode authenticity (FR-3.3.4) | ⚠️ Partial (guarded) | `illumina_udis_v1.0.0.json` declares `authentic:false`; `test_barcode_authenticity.py` forbids false `authentic:true`. Real Illumina doc 1000000002694 still not ingested (was 404). |
| G2 | Real PyPulse build/verify | ⚠️ Open | `engine/pulse.py:142-153` returns `False` on import failure (no mock — correct). `Dockerfile.pulse` present. CI (`ci.yml`,`pq.yml`) exists but PyPulse build step **not confirmed**. IQ-4 / OQ-16 / PQ-2 / PQ-6 still gated on real engine. |
| G3 | Live ingest perf (NFR-P1/P3/P6) | ⚠️ Open | `api/routes/telemetry.py:235` performs **synchronous `db.commit()`** inside `POST /ingest`. `uvloop` not configured (no refs). LTTB applied only on historical endpoint. |
| G4 | Well-click → FHIR fetch (FR-3.2.3) | ✅ Resolved | Backend `GET /api/plates/{id}/wells/{well_id}/observation`; frontend fetches on click. (Morning audit session 2.) |
| G5 | Alarm 100 ms SLA test (FR-3.1.5) | ⚠️ Open | No timed frontend/backend test asserting ≤100 ms red-trace transition. |
| G6 | Threshold consistency | ✅ Resolved | Frontend `TelemetryDashboard.tsx` aligned to backend `ALARM_THRESHOLDS` (pressure 150, flow ±60, hr 50–120, spo2 90). (Morning audit.) |
| G7 | JWT `scope` vs `scopes` (FR-3.8.5) | ⚠️ Open | Code issues/reads `"scopes"` (`api/auth.py`, `routes/auth.py`); SRS specifies `"scope"`. Minor interop risk. |
| G8 | EMA OQ-6 ≤4 vs ≤5 steps | ⚠️ Deferred (spec issue) | SRS OQ-6 mathematically requires step 5 at α=0.5; current ≤5 is correct. Await spec decision. |
| G9 | FHIR `Bundle` non-Observation persistence (FR-3.7.5) | ⚠️ Open | `api/routes/fhir.py:315` acknowledges non-Observation entries "without storage". |

---

## 4. Qualification (IQ/OQ/PQ) Coverage Gaps

**Present (file exists; many DB-gated/skip locally, run in CI):**
- IQ-1, IQ-5 (`tests/test_iq1_docker_health.py`, `test_iq5_pip_check.py`); IQ-2/3/6/7 added as DB-gated (`test_iq2_python_version.py`, `test_iq3_pgcrypto.py`, `test_iq6_triggers_installed.py`, `test_iq7_alembic_upgrade.py`).
- OQ-1…OQ-16 (`tests/test_oq1…oq16*`, `tests/unit/test_o07…o13*`, plus Pulse async/serialization unit tests).
- Unit tests for the four v1.1 modules: `tests/unit/test_{pkpd,chemistry,digital_twin,mrd_sandbox}.py`, `test_v1_1_schema.py`.

**Missing / incomplete against the SRS matrix:**
| Test | Gap |
|:--|:--|
| **OQ-17** PK/PD loop | No dedicated `test_oq17_*`; coverage exists only inside `test_pkpd.py` (not mapped to OQ-ID). |
| **OQ-18** Chemistry bundle | Inside `test_chemistry.py` (not OQ-named). |
| **OQ-19** Digital twin | Inside `test_digital_twin.py` (not OQ-named). |
| **OQ-20** MRD sandbox | Inside `test_mrd_sandbox.py` (not OQ-named). |
| **OQ-21 / OQ-22** LLM/RAG | **Entirely missing** — depend on unimplemented FR-3.15. |
| **OQ-23** Scenario determinism | **Entirely missing** — depend on unimplemented FR-3.16. |
| **PQ-7** LLM isolation under load | **Missing** (needs FR-3.15). |
| **PQ-8** Integrated multi-feature scenario | **Missing** (needs FR-3.16 + all modules). |
| IQ-4 | Code enforces real PyPulse; no successful-import verification in CI yet (G2). |
| PQ-1 / PQ-3 / PQ-4 | Scripts exist (`tests/performance/*`, `SNDEV/scripts/pq4_24h_ingest.py`); not confirmed as enforced CI gates. |

**Recommendation:** add OQ-named test wrappers (or rename) so the SRS traceability matrix maps 1:1 to test files, and stand up OQ-21…23 / PQ-7 / PQ-8 once FR-3.15/3.16 land.

---

## 5. Prioritized Future Development Roadmap

### Phase 1 — FR-3.15 LLM/RAG Gateway (est. 4–6 days)  [highest remaining value]
1. `middleware/ai/llm_gateway.py`: OpenAI-compatible client with provider abstraction (OpenRouter ↔ Ollama/vLLM) selected from config — satisfies **C8** and **FR-3.15.1**.
2. `middleware/ai/rag.py`: local static RAG retrieval from a `rag/templates/` directory of markdown/JSON (CAP/CLIA, FDA manuals, EHR rubrics) — satisfies **C9** and **FR-3.15.3**.
3. `middleware/api/routes/ai.py`: async endpoints for Pulse→narrative (FR-3.15.4) and ClinVar→pathology report (FR-3.15.5), dispatched via FastAPI background tasks (**C6**, FR-3.15.2).
4. Seed `rag_templates` with at least one CAP/CLIA pathology template + one EHR rubric; add a seed step to migration 0007 or a separate seed script.
5. Persist outputs with provenance to `clinical_text_outputs` + `llm_runs` (FR-3.15.6); add EHR ingestion harness endpoint (FR-3.15.7).
6. Add `.env` LLM provider config (`OPENROUTER_API_KEY`, `OLLAMA_BASE_URL`, `LLM_PROVIDER`) and wire into `main.py`.
7. **Resolves the dangling `from ai.llm_gateway import generate_text` in `mrd_sandbox.py:504`.**
8. Qualification: OQ-21, OQ-22, PQ-7.

### Phase 2 — FR-3.16 Scenario Orchestrator + UI (est. 4–6 days)
1. `middleware/simulation/scenarios.py`: orchestrator sequencing FR-3.11–3.15, sharing seeded patient/state context, writing `scenario_runs` (FR-3.16.2); determinism via stored seeds (FR-3.16.4).
2. `middleware/api/routes/scenarios.py`: create/run/inspect scenario specs + downstream validation harness routing outputs to configurable LIMS/EHR webhooks capturing responses (FR-3.16.1, 3.16.3).
3. Frontend `frontend/src/ScenarioDesigner/` + `/scenario` route in `App.tsx` (FR-3.16.5); satisfy NFR-U4 (assemble+execute in ≤5 interactions).
4. Qualification: OQ-23, PQ-8.

### Phase 3 — Real Pulse Integration (G2) & Module Promotion (est. 3–5 days)
1. Build `PyPulse.so` in CI (`Dockerfile.pulse`); passing IQ-4 / OQ-16 / PQ-2 / PQ-6 against the **real** engine.
2. Refactor the four v1.1 modules to optionally drive the real Pulse engine (FR-3.11.1, 3.12.1, 3.13.2, 3.14.1) while keeping seed-deterministic synthesis as the default/fallback (preserves C7).
3. Add frontend visibility for the four modules' outputs (at minimum read-only result viewers) to support validation/usability.

### Phase 4 — v1.0 Carry-Over Hardening (est. 3–4 days)
- G1: ingest authentic Illumina TruSeq/Nextera UDI sequences from doc 1000000002694; extend authenticity test to assert set membership.
- G3: move `db.commit()` off the event loop (async worker / bulk insert), enable `uvloop`, apply LTTB on the live relay path; verify NFR-P1/P3/P6.
- G5: add a timed alarm ≤100 ms SLA test.
- G7: reconcile JWT `scope` vs `scopes` to SRS (or document deviation).
- G9: persist all supported resource types within a FHIR transaction/batch Bundle, not only `Observation`.

### Phase 5 — CSV Qualification & Release (est. 3–4 days)
- Execute the full IQ/OQ/PQ matrix against a real stack; produce a validation report per FDA General Principles of Software Validation.
- Confirm `alembic upgrade head` from clean DB (IQ-7 surrogate) and the nightly hash-chain verification job (FR-3.8.4).

---

## 6. Evidence Index (files inspected this audit)

- `middleware/api/main.py:18,170-182` — router registration (pkpd/chemistry/digital_twin/mrd present; **no ai, no scenario**).
- `middleware/simulation/{pkpd,chemistry,digital_twin,mrd_sandbox}.py` — backend implementations (real algorithms; deterministic seed synthesis; `mrd_sandbox.py:504` lazy `ai.llm_gateway` import).
- `middleware/simulation/__init__.py:10` — explicit "scenarios.py (FR-3.16) — to be added".
- `middleware/models.py:217,237,263,286,307,330,357,378,396` — all nine v1.1 tables modeled (incl. `llm_runs.provider`, `rag_templates`).
- `middleware/alembic/versions/0007_v1_1_advanced_analytics.py` — creates 9 tables + append-only triggers; **no `rag_templates` seed rows**.
- `middleware/api/routes/{pkpd,chemistry,digital_twin,mrd}.py` — endpoints with `scenario_run_id` linkage.
- `middleware/api/routes/simulations.py` — Pulse lifecycle only (no scenario orchestration).
- `middleware/engine/pulse.py:142-153` — returns `False` on `PyPulse` import failure (no mock).
- `middleware/api/routes/telemetry.py:235` — synchronous `db.commit()` in `POST /ingest` (G3).
- `middleware/api/routes/fhir.py:315` — Bundle non-Observation entries "without storage" (G9).
- `middleware/.env` / `.env.example` — **no** LLM provider keys (FR-3.15.1/C8 config absent).
- `frontend/src/App.tsx`, `frontend/src/pages/*` — pages: Telemetry, Microplate, Audit, Admin, Login, Navigation; **no Scenario Designer, no advanced-analytics UI**.
- `tests/unit/test_{pkpd,chemistry,digital_twin,mrd_sandbox,v1_1_schema}.py`, `tests/test_oq*, test_iq*` — present but OQ-17…23 / PQ-7 / PQ-8 not named/missing.

---

## 7. Progress Note

This re-audit supersedes the "all FR-3.11–3.16 missing" claim in `impl-2026-07-26-srs-remaining-work.md` where it conflicts with the current tree. The four implemented modules represent substantial completed work; the **authoritative remaining-work baseline** is now: finish FR-3.15 (code) and FR-3.16 (orchestrator+UI), then promote/validate all six v1.1 features and close the open v1.0 gaps (G1, G2, G3, G5, G7, G9).

*Prepared for Computer System Validation (CSV) under FDA General Principles of Software Validation.*
