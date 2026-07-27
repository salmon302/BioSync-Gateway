Title: SRS-v1.1 Remaining-Work Gap Analysis & Future Development Roadmap
Date: 2026-07-26T00:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc audit (supersedes REMAINING_WORK.md dated 2026-07-22)
Summary: Re-verified BioSync-Gateway against SRS v1.1; documents completed remediations, the dominant unimplemented v1.1 advanced-analytics/AI scope, and a prioritized roadmap for future development.

---

# BioSync-Gateway — Remaining Work & Future Development Roadmap
## SRS v1.1 Gap Analysis (Re-verified 2026-07-26)

**Scope of this document:** This is a point-in-time audit of the working tree (branch `main`, 9 commits ahead of `origin/main`, with numerous uncommitted/untracked changes) measured against `SRS.md` **v1.1** (2026-07-24). It supersedes the stale `REMAINING_WORK.md` (2026-07-22), which described the pre-remediation baseline of the v1.0 (domains 1–6) feature set only.

**Method:** Direct source inspection of the actual tree (subagent dispatch was disabled in the local `opencode.json`, so verification was performed by reading real files and grepping for evidence). Every status below cites `file:line` evidence.

---

## 0. Headline Verdict

1. **The five v1.0 compliance/security blockers from the prior audit (B1–B6) are LARGELY REMEDIATED** at the code level — JWT secrets, DB-backed auth, full hash-chain formula, full append-only trigger coverage, and FHIR persistence now exist.
2. **The dominant remaining work is the entire v1.1 advanced-analytics & AI expansion (FR-3.11 → FR-3.16).** As of this audit, **none** of these features are implemented beyond a conception document (`SNDEV/docs/conception-2026-07-24-advanced-simulation-expansion.md`). No simulation modules, no AI/LLM gateway, no RAG, no scenario orchestrator, no Scenario Designer UI, and no supporting database tables exist.
3. **A handful of v1.0 carry-over gaps remain**, most notably: barcode-sequence *authenticity* (sequences are synthetically generated, not sourced from Illumina doc 1000000002694), the real PyPulse binary build/verification, live-path telemetry performance hardening, and the frontend well-click → FHIR fetch.
4. **Qualification (IQ/OQ/PQ) coverage is incomplete**, especially the v1.1 IQ/OQ/PQ tests (OQ-17…23, PQ-7, PQ-8), which cannot exist until the features do.

---

## 1. What Is DONE (verified against current tree)

| Item (prior audit) | Status | Evidence |
|:--|:--|:--|
| A1 — JWT secret from env, fail-closed in prod | ✅ Done | `middleware/api/auth.py:26-63` (`_load_jwt_secret` raises `RuntimeError` if unset and not dev) |
| A2 — DB-backed login (bcrypt, scopes from DB) | ✅ Done | `middleware/api/auth.py:92-133` (`authenticate_user` queries `users`, verifies via `passlib`); `middleware/api/routes/auth.py:45-73` |
| A4 — Hash-chain includes `D_prev` + `R_i` per FR-3.8.3 | ✅ Done | `middleware/engine/hash_chain.py:54-66` (`compute_hash` concatenates `previous_state` + `reason`); `middleware/models.py:110-112` (`AuditLog.previous_state`, `AuditLog.reason`); migration `0005_hash_chain_fields.py` |
| A5 — Full append-only trigger coverage + missing tables | ✅ Done | `middleware/alembic/versions/0006_complete_compliance_tables.py` creates `patients`, `device_metrics`, `dilution_worklists` and adds `prevent_update`/`prevent_delete` triggers to `human_factors_metrics`, `barcode_indices`, `patients`, `device_metrics`, `dilution_worklists`; removes conflicting `devices` update trigger |
| B1 — Barcode `d<3` rejection → `is_valid=False` | ✅ Done | `middleware/engine/barcode.py:158` (`'critical' if dist < min_distance`); `:161` only `critical` violations fail the plate |
| B6 — FHIR POST `/Observation` & `/DeviceMetric` persist (HTTP 201) | ✅ Done | `middleware/api/routes/fhir.py:49-91` (Observation → `observations`, 201); `:148-192` (DeviceMetric → `device_metrics`, 201) |
| M5 (partial) — Barcode now 8/10-base TruSeq & Nextera sets | ⚠️ Partial | `database/seeds/illumina_udis_v1.0.0.json` defines 8- and 10-base sets for TruSeq & Nextera; **but** `provenance_note` states sequences are *synthetically generated* because the Illumina source document 1000000002694 returned 404. Not authentic Illumina data. |
| M7 (partial) — LTTB downsampling engine | ⚠️ Partial | `middleware/engine/lttb.py` (full LTTB + multi-channel + observation adapters); wired into **historical** telemetry endpoint `middleware/api/routes/telemetry.py:309-352`. Live WebSocket-path integration unverified (see §3). |
| M8 — Microplate import/export symmetric (CSV+JSON) | ✅ Done | `frontend/src/pages/MicroplateEditor.tsx:287` (CSV import), `:340` (JSON export), `:356` (JSON import), `:388` (CSV export) |
| M1/M2 — Schema & layout drift | ✅ Resolved | `middleware/models.py:16-160` now models all SRS §6.1 tables; `docs/URS.md` and `docs/FRS.md` now exist (resolves m1) |
| C4 — uFMEA JSON export + human-factors route | ✅ Done | `middleware/api/routes/human_factors.py` (untracked); `frontend/src/hooks/useHumanFactors.ts`, `frontend/src/providers/human-factors-provider.tsx` |
| Base FR-3.6 Pulse integration | ✅ Done (enforced) | `middleware/api/routes/simulations.py` (full lifecycle: create/step/pause/resume/stop/status/metrics/state/export/purge, `max_concurrent=10`); `middleware/engine/pulse.py:137-147` now **raises** if `PyPulse` import fails (mock fallback removed — satisfies A3 intent) |
| Real PyPulse build scaffolding | ⚠️ Present, unverified | `middleware/Dockerfile.pulse` (multi-stage C++ build of Kitware Pulse → `PyPulse.so`) |

---

## 2. DOMINANT REMAINING WORK — v1.1 Advanced Analytics & AI (FR-3.11 → FR-3.16)

**None of FR-3.11 through FR-3.16 are implemented.** Verified by glob/grep: no `middleware/simulation/*.py`, no `middleware/ai/*.py`, no `middleware/api/routes/ai.py`, no `middleware/api/routes/simulation.py` (scenario endpoints), no `frontend/src/ScenarioDesigner/`, and `frontend/src/App.tsx:13-19` exposes only `/telemetry`, `/plates`, `/audit`, `/admin` (no `/scenario`).

| SRS FR | Feature | Implementation Status | Evidence / Missing Artifacts |
|:--|:--|:--|:--|
| FR-3.11 | In Silico PK/PD Lab Loop | ❌ Missing | No `middleware/simulation/pkpd.py`; no `pkpd_worklists` table; no OQ-17 test |
| FR-3.12 | Closed-Loop Clinical Chemistry Generation | ❌ Missing | No `middleware/simulation/chemistry.py`; no `chemistry_profiles` table; no OQ-18 test |
| FR-3.13 | Synthetic Digital Twin Cohorts | ❌ Missing | No `middleware/simulation/digital_twin.py`; no `synthetic_cohorts` table; no OQ-19 test |
| FR-3.14 | Liquid Biopsy / MRD Sandbox | ❌ Missing | No `middleware/simulation/mrd_sandbox.py`; no `cfdna_sandbox_runs` table; no OQ-20 test |
| FR-3.15 | LLM/RAG Clinical Text Gateway | ❌ Missing | No `middleware/ai/llm_gateway.py`, `middleware/ai/rag.py`, or `api/routes/ai.py`; no `clinical_text_outputs`/`llm_runs`/`rag_templates` tables; no OQ-21/22 tests |
| FR-3.16 | Integrated Scenario Framework | ❌ Missing | No `middleware/simulation/scenarios.py`, no scenario orchestrator API, no `simulation_scenarios`/`scenario_runs` tables, no OQ-23 / PQ-8 tests, **and no Scenario Designer UI (FR-3.16.5)** |

> **Note on SRS deferral:** SRS v1.1 §10 records that FR-3.11–3.16 were *deferred* until baseline (v1.0) capabilities completed. That baseline is now substantially met, so these features are the **primary future-development scope**, not optional.

---

## 3. Remaining v1.0 Carry-Over Gaps

| # | Gap | Evidence | Impact / Future Action |
|:--|:--|:--|:--|
| G1 | **Barcode sequences not authentic Illumina data** | `database/seeds/illumina_udis_v1.0.0.json` `provenance_note`: "Sequences below are reference UDI sequences generated to satisfy the SRS FR-3.3.4 minimum Hamming distance constraint … Replace with official Illumina sequences when the source document is available." `tests/unit/test_barcode_authenticity.py` only asserts min Hamming distance ≥ 3, **not** match to real Illumina indices. | FR-3.3.4 (authentic 8/10-base TruSeq/Nextera sourced from public documentation) is **not met**. Replace seed with sequences verified against doc 1000000002694; extend the authenticity test to assert set membership. |
| G2 | **Real PyPulse binary not yet built/verified** | `pulse.py:137-147` raises on import failure; `Dockerfile.pulse` present but CI (`ci.yml`) does not build it. `IQ-4` (PyPulse import) therefore remains unverified; Pulse-dependent tests are gated. | Build `PyPulse.so` in a CI job; add a passing IQ-4 that asserts real engine init + GPB serialization (FR-3.6.3). |
| G3 | **Live telemetry-path performance hardening** | `middleware/api/routes/telemetry.py:176` `ingest_telemetry` performs **synchronous `db.commit()` at `:235`** inside the ingest path; `uvloop` not configured; LTTB is applied only on the **historical** endpoint (`:309-352`), not on the live WebSocket relay. | Affects NFR-P1 (100k pts/s ingest), NFR-P3 (≤50 ms relay), NFR-P6 (500 WS conns), and PQ-1/PQ-6 SLAs. Move DB writes off the event loop (async/worker), enable `uvloop`, and apply LTTB/downsampling on the live relay path. |
| G4 | **Frontend well-click → FHIR fetch (FR-3.2.3)** | `frontend/src/pages/MicroplateEditor.tsx:84` renders `well.observation` **only if preloaded**; no backend `GET /api/fhir/Observation?well=...` is wired. | Implement backend lookup + frontend fetch so clicking a well shows its FHIR `Observation` regardless of preload. |
| G5 | **Alarm 100 ms timing guarantee (FR-3.1.5)** | Backend alarm logic exists (`telemetry.py`); frontend has `checkAlarms` but no explicit ≤100 ms SLA assertion/test. | Add a timed frontend test asserting red-trace transition within 100 ms of threshold violation. |
| G6 | **Threshold inconsistency (m7)** | Backend pump-pressure high = 150 mmHg; verify frontend uses the same value (stale audit flagged 140). | Align constants; add a shared threshold config consumed by both tiers. |
| G7 | **JWT claim naming (m8)** | Code issues/reads `"scopes"` (plural) (`auth.py:203`, `routes/auth.py:61`); SRS FR-3.8.5 specifies `"scope"`. | Minor interop risk; reconcile to SRS or document deviation. |
| G8 | **EMA OQ-6 ≤4-step enforcement (m6)** | Stale audit claimed `signal.py:317` relaxed to ≤5. Re-verify current `middleware/engine/signal.py` enforces ≤4 per SRS. | Confirm/repair tolerance; align OQ-6 expectation. |
| G9 | **FHIR `Bundle` does not persist non-Observation resources** | `fhir.py:314-323` acknowledges `DeviceMetric`/other entries in a Bundle "without storage". | For transaction/batch completeness, persist all supported resource types within a Bundle, not only `Observation`. |

---

## 4. Qualification (IQ/OQ/PQ) Coverage Gaps

**Present & verified-existing:**
- IQ-1 (docker health), IQ-5 (pip check) present.
- OQ-1…OQ-15 present (hamming, dilution, EMA, triggers, tamper, FHIR validation, JWT).
- OQ-16 (Pulse state serialization) present but **runs against mock/gated engine** until G2 resolved.
- PQ-3 (`tests/performance/test_pq3_1m_rows.py`) and PQ-4 (`SNDEV/scripts/pq4_24h_ingest.py`) scripts present but not confirmed as passing CI gates.
- New unit tests added: `test_lttb.py`, `test_barcode_authenticity.py`, `test_p2_append_only_triggers.py`, `test_o13_hash_chain_api.py`, `test_p2_db_persistence_pulse.py`, `test_p2_async_delegation_timing.py`, `test_o11_pulse_async_delegation.py`, `test_o12_pulse_data_extraction.py`, `integration/test_human_factors_export.py`.

**Missing / incomplete:**
| Test | Gap |
|:--|:--|
| IQ-2 (Python ≥3.11 dedicated test), IQ-3 (pgcrypto available), IQ-6 (trigger introspection `pg_trigger`), IQ-7 (`alembic upgrade head` on fresh DB) | Still missing as dedicated tests (prior audit action D1 not confirmed complete). |
| IQ-4 (PyPulse import) | Code enforces real PyPulse, but no successful-import verification exists (gated, see G2). |
| PQ-1 (500 WS conns @ 100k pts/s) | Smoke-only / not executed at real scale (architectural risk G3). |
| PQ-3 / PQ-4 | Scripts exist; not confirmed as enforced CI performance gates. |
| **OQ-17…OQ-23, PQ-7, PQ-8** | **Entirely missing** — depend on the unimplemented v1.1 features (§2). |

---

## 5. Prioritized Future Development Roadmap

### Phase A — Compliance & Correctness Hardening (est. 3–4 days)
1. **G1 Barcode authenticity:** source real Illumina TruSeq/Nextera UDI sequences from doc 1000000002694; replace `database/seeds/illumina_udis_v1.0.0.json`; extend `test_barcode_authenticity.py` to assert set membership, not just min-distance.
2. **G7/G6 JWT claim & threshold consistency:** align `"scope"` vs `"scopes"` and shared alarm thresholds; add config.
3. **G4 Well-click → FHIR fetch:** backend `GET /api/fhir/Observation?well=` + frontend fetch.
4. **G5 Alarm 100 ms SLA test**; **G8 EMA ≤4-step** re-verification.
5. **IQ-2/3/6/7** dedicated tests (close D1).

### Phase B — Performance SLA & Pulse Reality (est. 3–5 days)
1. **G3 Live-path hardening:** move synchronous `db.commit()` off the WebSocket event loop; enable `uvloop`; apply LTTB on the live relay; verify 60 fps @ 100k pts/s.
2. **G2 Real PyPulse:** build `PyPulse.so` in CI (`Dockerfile.pulse`); passing IQ-4 / OQ-16 / PQ-2 / PQ-6 against the **real** engine (remove mock-gating).
3. **PQ-1 / PQ-3 / PQ-4** promoted to enforced CI performance gates.

### Phase C — v1.1 Advanced Analytics & AI (the primary remaining scope; est. 2–3 weeks)
Implement, in dependency order, all of FR-3.11 → FR-3.16:
1. `middleware/simulation/pkpd.py` (FR-3.11) → `pkpd_worklists` table + OQ-17.
2. `middleware/simulation/chemistry.py` (FR-3.12) → `chemistry_profiles` + OQ-18.
3. `middleware/simulation/digital_twin.py` (FR-3.13) → `synthetic_cohorts` + OQ-19.
4. `middleware/simulation/mrd_sandbox.py` (FR-3.14) → `cfdna_sandbox_runs` + OQ-20.
5. `middleware/ai/llm_gateway.py` + `middleware/ai/rag.py` + `api/routes/ai.py` (FR-3.15) → `clinical_text_outputs`, `llm_runs`, `rag_templates` + OQ-21/22.
6. `middleware/simulation/scenarios.py` + scenario orchestrator API (FR-3.16) → `simulation_scenarios`, `scenario_runs` + OQ-23 / PQ-8.
7. **Frontend `ScenarioDesigner`** (FR-3.16.5) + route in `App.tsx`.
8. **PQ-7** (LLM isolation under load).
All modules must honor C6/C7/C8/C9 (async isolation, synthetic-only reproducibility, swappable LLM provider, local static RAG repo).

### Phase D — CSV Qualification & Release (est. 3–4 days)
- Execute the full IQ/OQ/PQ matrix against a real stack; produce a validation report (FDA General Principles of Software Validation).
- Confirm `alembic upgrade head` from clean DB (IQ-7 surrogate) and nightly hash-chain verification job (FR-3.8.4).

---

## 6. Evidence Index (files inspected)

- `middleware/api/auth.py`, `middleware/api/routes/auth.py` — A1/A2
- `middleware/engine/hash_chain.py`, `middleware/models.py`, `middleware/alembic/versions/0005_*`, `0006_*` — A4/A5
- `middleware/api/routes/fhir.py` — B6
- `middleware/engine/barcode.py`, `database/seeds/illumina_udis_v1.0.0.json` — M5/G1
- `middleware/engine/lttb.py`, `middleware/api/routes/telemetry.py` — M7/G3
- `middleware/engine/pulse.py`, `middleware/Dockerfile.pulse`, `middleware/api/routes/simulations.py` — FR-3.6/G2
- `frontend/src/App.tsx`, `frontend/src/providers/chart-provider.tsx`, `frontend/src/pages/MicroplateEditor.tsx` — FR-3.1.3/M8/G4
- `docs/URS.md`, `docs/FRS.md` — m1
- Glob/grep confirmed absence of `middleware/simulation/`, `middleware/ai/`, `api/routes/ai.py`, `frontend/src/ScenarioDesigner/` — §2

---

## 7. Progress Log (2026-07-26 session)

First development slice executed (see `SNDEV/docs/impl-2026-07-26-phase-a-compliance.md`):

- **G6 — RESOLVED:** Frontend `TelemetryDashboard.tsx:41-49` alarm thresholds aligned to the authoritative backend `ALARM_THRESHOLDS` (`telemetry.py:29-34`): pressure high 150, flow {−60,60}, hr {50,120}, spo2 low 90. Client visualization now matches server-side EMA-filtered alarm evaluation (FR-3.5.4).
- **D1 — PARTIALLY RESOLVED:** Added missing IQ qualification tests under `tests/`:
  - `test_iq2_python_version.py` — **passes** locally (Python 3.14.3 ≥ 3.11). Pure, runs in all envs.
  - `test_iq3_pgcrypto.py`, `test_iq6_triggers_installed.py`, `test_iq7_alembic_upgrade.py` — **DB-gated**; skip cleanly without a live PostgreSQL and execute in CI where the `postgres:15` service is provisioned.
- **G8 — DEFERRED (spec issue, not a code bug):** SRS OQ-6 demands "≤4 iterations" but α=0.5 step 0→100 converges within 5% only at step 5 (mathematically). Current `≤5` is correct; left unchanged pending a spec decision (adjust tolerance or α). Flagged, not silently "fixed."

### 2026-07-26 (session 2) — G1 + G4
- **G1 — PARTIALLY RESOLVED (authenticity now explicit + guarded):** `database/seeds/illumina_udis_v1.0.0.json` declares `authentic: false` with `source_document_status` + `ingestion_procedure`; `tests/unit/test_barcode_authenticity.py` adds `test_manifest_authenticity_is_explicit` and guardrail `test_authenticity_not_falsely_claimed` (forbids `authentic: true` without a verified reference). **Remaining:** ingest official Illumina TruSeq/Nextera UDI sequences from doc 1000000002694 (external step; was 404). See `SNDEV/docs/impl-2026-07-26-g1-g4.md`.
- **G4 — RESOLVED (full FR-3.2.3 closure):** Backend added `Plate`/`PlateWell` models + real `POST /api/plates/` and `GET /api/plates/{id}` (persisting wells with the Observation link in `plate_wells.metadata['observation_uid']`), plus `GET /api/plates/{id}/wells/{well_id}/observation`. Frontend added `LoginModal` + `Navigation` auth state (stores JWT in `localStorage['biosync_jwt']`) and the editor now loads persisted plates on mount and fetches the FHIR Observation by UID on well-click. Dev-fallback JWT scopes extended for local use. **Verification:** backend imports OK; `tests/integration/test_api_plates.py` (DB-gated, CI) covers create→get→observation link; frontend `microplate_editor.test.tsx` 16 passed (no regression). See `SNDEV/docs/impl-2026-07-26-g4-closure.md`.

**Still open after this slice:** G1 final authenticity ingestion (external doc), G2 (real PyPulse build/verify), G3 (live-path perf hardening), the EMA-spec nuance (G8), and the entire v1.1 advanced-analytics/AI scope (FR-3.11–3.16).

*Prepared for Computer System Validation (CSV) under FDA General Principles of Software Validation. This document is the authoritative "remaining work" baseline for future development of BioSync-Gateway and supersedes `REMAINING_WORK.md` (2026-07-22).*
