Title: Clinical chemistry generation module (FR-3.12)
Date: 2026-07-26T17:30:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: BioSync-Gateway SRS v1.1 — second advanced-analytics feature module in the PK/PD → chemistry → digital-twin → MRD → scenario chain (continues SNDEV/docs/impl-2026-07-26-pkpd-module.md)
Summary: Implemented a deterministic synthetic clinical-chemistry vector generator (blood gas / electrolytes / metabolic), a multi-modal FHIR Bundle assembler (chemistry Observations + ClinVar genomics), and an optional LIMS webhook poster, persisted to the chemistry_profiles table and exposed via /api/simulation/chemistry endpoints (FR-3.12.1–FR-3.12.4).

---

## 1. Task Reference
User instruction: *"proceed straight to the chemistry module"* (FR-3.12 → `chemistry_profiles`). Second module on the v1.1 schema scaffold.

## 2. Specification Summary
Implements SRS FR-3.12.1–FR-3.12.4:
- **FR-3.12.1** Chemistry vector extraction — blood gas (pO₂, pCO₂, pH, HCO₃⁻), electrolytes (Na⁺, K⁺, Cl⁻, Ca²⁺), metabolic (glucose, lactate). Synthetic but deterministic from a seed (Pulse is mocked; analytic/PRNG generation stands in for extraction).
- **FR-3.12.2** Multi-modal Bundle assembly — chemistry Observations + ClinVar genomics-referenced resource in a `transaction` Bundle.
- **FR-3.12.3** LIMS ingestion stress test — Bundle POSTed to a configurable webhook; response (incl. OperationOutcome) captured.
- **FR-3.12.4** Determinism & seedability — same seed → identical vectors/bundle (FR-3.16.4).

## 3. Implementation Notes

### Files created / modified
- **Created** `middleware/simulation/chemistry.py`:
  - `CHEMISTRY_VECTOR_SPEC` — analyte ranges + UCUM units.
  - `generate_chemistry_vectors(seed, simulation_id, patient_id)` — seeded `random.Random` generation (deterministic, no external state).
  - `assemble_multimodal_bundle(...)` — builds FHIR `transaction` Bundle (chemistry Observations + genomics Observation referencing `clinvar_data`); validates via `fhir_validator.FHIRValidator.validate_bundle` (FR-3.7.1) and raises on invalid.
  - `send_lims_bundle(bundle, webhook_url)` — `httpx.post`, captures status/body/OperationOutcome; resilient to HTTP errors.
  - `generate_chemistry_profile(db, ...)` — orchestrates vectors → bundle → optional LIMS post → persists a `ChemistryProfile` row.
- **Created** `middleware/api/routes/chemistry.py` — `POST /api/simulation/chemistry/profile` (`simulation_write`), `GET /api/simulation/chemistry/profile/{id}` and `/profiles` (`simulation_read`); 422 on validation failure (FR-3.7.4).
- **Modified** `middleware/api/main.py` — added `chemistry` to route imports and `app.include_router(chemistry.router, prefix="/api/simulation", tags=["simulation-chemistry"])`.
- **Created** `tests/unit/test_chemistry.py` — pure tests (determinism, ranges, bundle structure, FHIR validation, mocked LIMS post) + router/app wiring checks (gated on `JWT_SECRET`) + DB-gated persistence/endpoint tests.

### Design decisions
- Pulse Engine is mocked in this environment, so chemistry vectors are generated synthetically (seeded). The function signature accepts `simulation_id`/`patient_id` so a real Pulse extraction can replace the generator later without changing callers.
- ClinVar data is passed in as `clinvar_data` (dict) to keep the module offline/deterministic; the existing `external/clinvar.py` client can be used by callers to populate it.
- Reuses `fhir_validator.validate_bundle` (local, no network) to honor FR-3.7.1 before persistence.
- Auth reuses existing `simulation_write`/`simulation_read` scopes.

## 4. Verification Evidence
- **py_compile** (chemistry.py, chemistry route, main.py, test): **PASS** (exit 0).
- **pytest tests/unit/test_chemistry.py** (with `JWT_SECRET` set, mirroring CI): **10 passed, 3 skipped** (8 pure: determinism/ranges/bundle structure/FHIR validation/mocked-LIMS + 2 app-wiring checks). DB-gated persistence/endpoint tests skip without `DATABASE_URL` (run in CI against `postgres:15`).
- **Regression:** both `test_pkpd.py` and `test_chemistry.py` pass together (20 passed, 6 skipped) — `main.py` chemistry import did not break the PK/PD module.
- Noted: the project `fhir_validator` requires `valueQuantity` on every `Observation`, so the genomics entry carries a variant-count quantity with full variant detail in `note` (FR-3.7.1 honored via `validate_bundle`).

### Files delivered
- `middleware/simulation/chemistry.py` (created — vectors, bundle assembly, LIMS poster, profile orchestration)
- `middleware/api/routes/chemistry.py` (created — /api/simulation/chemistry endpoints, auth-gated)
- `middleware/api/main.py` (modified — registers chemistry router)
- `tests/unit/test_chemistry.py` (created — pure + wiring + DB-gated tests)
- `SNDEV/docs/impl-2026-07-26-chemistry-module.md` (this log)

### Follow-ups (deferred)
- Real Pulse Engine extraction could replace the seeded synthetic vector generator behind the same `generate_chemistry_vectors` signature (FR-3.12.1 references Pulse state).
- Next in the chain: **digital twin cohort** (FR-3.13 → `synthetic_cohorts`).
