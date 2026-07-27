Title: PK/PD lab loop module (FR-3.11.1–FR-3.11.4)
Date: 2026-07-26T16:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: BioSync-Gateway SRS v1.1 — first advanced-analytics feature module built on the v1.1 schema scaffold (SNDEV/docs/impl-2026-07-26-v1.1-schema-scaffold.md)
Summary: Implemented a deterministic one-compartment PK/PD lab loop (middleware/simulation/pkpd.py) that feeds the existing DilutionSolver to emit pipetting worklists tagged origin=pk_pd_loop, persisted to the pkpd_worklists table, and exposed via /api/simulation/pkpd endpoints.

---

## 1. Task Reference
User instruction: *"start building the first feature module (PK/PD pkpd.py → pkpd_worklists) on top of it."* First module in the PK/PD → chemistry → digital-twin → MRD → scenario chain. Continuation of the v1.1 schema scaffold.

## 2. Specification Summary
Implements SRS FR-3.11.1–FR-3.11.4:
- **FR-3.11.1** Substance registration with PK params (Vd, clearance, half-life, dose) → `PkpdSubstance`.
- **FR-3.11.2** Clearance-cycle simulation → `simulate_clearance()` samples a plasma concentration time-series.
- **FR-3.11.3** Target matrix derivation → `derive_target_matrix()` interpolates targets at requested times.
- **FR-3.11.4** Pipetting manifest generation → `build_pkpd_worklist_steps()` feeds `engine.dilution.DilutionSolver` (C1V1=C2V2, pre-dilution on below-limit) and `generate_pkpd_worklist()` persists a `PkpdWorklist` row tagged `origin=pk_pd_loop`.

FR-3.11.5 (loop-closure re-ingestion as Observation Bundle) is deferred to the scenario framework and noted as a follow-up hook.

## 3. Implementation Notes

### Files created / modified
- **Created** `middleware/simulation/__init__.py` — package marker for the advanced-analytics simulation modules.
- **Created** `middleware/simulation/pkpd.py` — pure, deterministic PK engine:
  - `PkpdSubstance` dataclass (PK params + optional `molar_mass`).
  - `simulate_clearance()` — one-compartment IV-bolus `C(t)=C0·e^(−kt)`, `k=CL/Vd`; no RNG (reproducible per FR-3.16.4).
  - `derive_target_matrix()` — linear interpolation of the curve at requested sample times.
  - `build_pkpd_worklist_steps()` — per-well transfer/pre-dilution via `DilutionSolver`; canonical unit is `mg/L` (or `µM` when `molar_mass` set).
  - `generate_pkpd_worklist(db, ...)` — orchestrates and persists a `PkpdWorklist` row.
- **Created** `middleware/api/routes/pkpd.py` — FastAPI router (prefix `/api/simulation`):
  - `POST /api/simulation/pkpd/worklist` (`simulation_write`) — body dict → persisted worklist JSON.
  - `GET  /api/simulation/pkpd/worklist/{id}` (`simulation_read`).
  - `GET  /api/simulation/pkpd/worklists` (`simulation_read`) — recent list.
- **Modified** `middleware/api/main.py` — added `pkpd` to the route imports and `app.include_router(pkpd.router, prefix="/api/simulation", tags=["simulation-pkpd"])`.
- **Created** `tests/unit/test_pkpd.py` — pure-math unit tests (run anywhere) + router-wiring check (no DB) + DB-gated persistence/endpoint tests.

### Design decisions
- The plasma curve is computed analytically from PK parameters rather than relying on the (currently mocked) Pulse Engine; this keeps the loop deterministic, testable, and independent of `PyPulse` availability, while still honoring "registers substance into the active Pulse simulation state" intent (the substance params are persisted alongside the worklist for later Pulse linkage).
- Reuses `engine.dilution.DilutionSolver` (already validated for FR-3.4 OQ-3/4/5) — no duplicated dilution logic.
- Auth reuses existing `simulation_write`/`simulation_read` scopes; no new scopes introduced.

## 4. Verification Evidence
- **py_compile** (pkpd.py, pkpd route, main.py, test): **PASS** (exit 0).
- **pytest tests/unit/test_pkpd.py** (no DB): **8 passed** (pure PK/PD math + router-object check), **3 skipped** (DB-gated persistence + endpoint tests; `test_router_registered`/`test_app_includes_pkpd_routes` are app-gated on `JWT_SECRET`).
- **With `JWT_SECRET` set** (mirrors CI): **10 passed, 3 skipped** — confirms the router is importable and `main.py` registers `/api/simulation/pkpd/{worklist,worklists,worklist/{id}}`.
- **DB-gated tests** (`test_generate_pkpd_worklist_persists`, `test_pkpd_worklist_endpoint_roundtrip`, `test_pkpd_worklist_requires_auth`): **skipped locally** (no `DATABASE_URL`); execute in CI against `postgres:15` via the existing `authenticated_client` / `SessionLocal` fixtures. These exercise real persistence to `pkpd_worklists` and the auth gate (`simulation_write`).
- The two app-wiring checks require `JWT_SECRET` because `api.auth` fails closed at import when the secret is unset (NFR-S7) — expected suite behavior, not a defect.

### Files delivered
- `middleware/simulation/__init__.py` (created — package marker)
- `middleware/simulation/pkpd.py` (created — PK/PD engine: PkpdSubstance, simulate_clearance, derive_target_matrix, build_pkpd_worklist_steps, generate_pkpd_worklist)
- `middleware/api/routes/pkpd.py` (created — /api/simulation/pkpd endpoints, auth-gated)
- `middleware/api/main.py` (modified — registers pkpd router)
- `tests/unit/test_pkpd.py` (created — pure + wiring + DB-gated tests)
- `SNDEV/docs/impl-2026-07-26-pkpd-module.md` (this log)

### Follow-ups (deferred)
- **FR-3.11.5** loop-closure re-ingestion as an `Observation` Bundle — fold into the scenario orchestrator (FR-3.16) later.
- Next module in the chain: chemistry (FR-3.12) → `chemistry_profiles`.
