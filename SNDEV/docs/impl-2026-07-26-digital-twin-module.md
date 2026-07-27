Title: Digital twin cohort module (FR-3.13)
Date: 2026-07-26T19:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: BioSync-Gateway SRS v1.1 — third advanced-analytics feature module in the PK/PD → chemistry → digital-twin → MRD → scenario chain (continues SNDEV/docs/impl-2026-07-26-chemistry-module.md)
Summary: Implemented deterministic synthetic digital-twin cohort generation (FR-3.13.1), reactive FHIR Observation vital-trend streams per member (FR-3.13.2), FHIR R4 validation of cohort outputs (FR-3.13.3), genomic/variant pairing into an exportable unified Bundle (FR-3.13.4), and `synthetic=true` privacy flagging (FR-3.13.5). Persisted to synthetic_cohorts and exposed via /api/simulation/cohort endpoints.

---

## 1. Task Reference
User instruction: *"digital-twin cohort module"* (FR-3.13 → `synthetic_cohorts`).

## 2. Specification Summary
Implements SRS FR-3.13.1–FR-3.13.5:
- **FR-3.13.1** Cohort definition → deterministic generation of N synthetic patient identities (no PHI, synthetic identifiers per C2).
- **FR-3.13.2** Reactive time-series → per-member physiological trends (HR, SpO2, BP) emitted as FHIR Observations at configurable cadence.
- **FR-3.13.3** FHIR R4 compliance → outputs validate; subject references to synthetic patients + device references to simulated instruments.
- **FR-3.13.4** Variant pairing → each twin's ClinVar variant paired with its trend stream in a unified, exportable FHIR Bundle.
- **FR-3.13.5** Privacy assurance → `is_synthetic = True` flag (no real data).

## 3. Implementation Notes

### Files created / modified
- **Created** `middleware/simulation/digital_twin.py`:
  - `CHEM_VITALS_SPEC` — vital channels (HR, SpO2, systolic/diastolic BP) with UCUM units + LOINC codes.
  - `generate_cohort_members(spec, seed)` — seeded generation of member identities (synthetic_id, demographics, variant, baseline vitals).
  - `simulate_member_timeseries(member, duration_min, cadence_sec, seed)` — deterministic vital-trend Observations per member.
  - `assemble_cohort_bundle(members, timeseries_by_member, validate)` — unified FHIR `transaction` Bundle (member Observations + genomics), validated via `fhir_validator`.
  - `generate_synthetic_cohort(db, spec, ...)` — orchestrates and persists a `SyntheticCohort` row (`is_synthetic=True`).
  - `export_cohort_bundle(cohort_row, ...)` — rebuilds the exportable Bundle from stored members+seed (reproducible, FR-3.16.4).
- **Created** `middleware/api/routes/digital_twin.py` — `POST /api/simulation/cohort` (`simulation_write`), `GET /api/simulation/cohort/{id}` + `/cohorts` (`simulation_read`).
- **Modified** `middleware/api/main.py` — added `digital_twin` route import + `app.include_router(digital_twin.router, prefix="/api/simulation", tags=["simulation-digital-twin"])`.
- **Created** `tests/unit/test_digital_twin.py` — pure tests (determinism, identity/PHI, timeseries, bundle structure/FHIR validation, export reproducibility) + wiring checks (gated on `JWT_SECRET`) + DB-gated persistence/endpoint tests.

### Design decisions
- Pulse Engine is mocked, so vital trends are synthesized deterministically (seeded random walk around baselines). `simulate_member_timeseries` accepts a per-member seed so a real Pulse stream can replace it later behind the same signature.
- Genomics Observation reuses the project-validator-compatible shape (valueQuantity count + variant detail in `note`), consistent with the chemistry module.
- All cohort rows are flagged `is_synthetic=True` to satisfy FR-3.13.5 (HIPAA/GDPR bypass).
- Auth reuses existing `simulation_write`/`simulation_read` scopes.

## 4. Verification Evidence
- **py_compile** (digital_twin.py, digital_twin route, main.py, test): **PASS** (exit 0).
- **pytest tests/unit/test_digital_twin.py** (with `JWT_SECRET`, mirroring CI): **9 passed, 3 skipped** (7 pure: determinism, identity/PHI, timeseries, bundle structure/FHIR validation, export reproducibility + 2 app-wiring). DB-gated persistence/endpoint tests skip without `DATABASE_URL`.
- **Regression:** all three advanced modules together → **29 passed, 9 skipped** (PK/PD +10/3, chemistry +10/3, digital-twin +9/3). `main.py` additions did not break earlier modules.
- **Determinism fix (FR-3.16.4):** the Bundle `timestamp` and genomics `effectiveDateTime` are now seed-derived (not `datetime.now()`), so exports are byte-for-byte reproducible from the stored seed — required for deterministic scenario output hashes.

### Files delivered
- `middleware/simulation/digital_twin.py` (created — cohort members, vital time-series, Bundle assembly, export)
- `middleware/api/routes/digital_twin.py` (created — /api/simulation/cohort endpoints, auth-gated)
- `middleware/api/main.py` (modified — registers digital_twin router)
- `tests/unit/test_digital_twin.py` (created — pure + wiring + DB-gated tests)
- `SNDEV/docs/impl-2026-07-26-digital-twin-module.md` (this log)

### Follow-ups (deferred)
- Real Pulse Engine streams could replace the seeded synthetic vital generator behind `simulate_member_timeseries`.
- Next in the chain: **MRD / cfDNA sandbox** (FR-3.14 → `cfdna_sandbox_runs`).
