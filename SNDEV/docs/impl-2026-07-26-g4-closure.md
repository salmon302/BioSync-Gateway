Title: Close G4 — plate/well persistence + frontend auth (FR-3.2.3)
Date: 2026-07-26T00:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: BioSync-Gateway SRS-v1.1 gap remediation (user directive: "close G4 properly by adding plate/well persistence + frontend auth"); follows SNDEV/docs/impl-2026-07-26-srs-remaining-work.md
Summary: Implemented real plate/well persistence (models + create/get + well→Observation endpoints) and frontend authentication (login modal storing JWT), completing FR-3.2.3 end-to-end.

---

## 1. Task Reference
FR-3.2.3 (well-click → FHIR Observation) full closure. Prior session left G4 as "wiring only" because (a) no plate/well persistence existed and (b) no frontend auth/token plumbing existed.

## 2. Specification Summary
- SRS FR-3.2 / FR-3.2.3: plates/wells persisted; clicking a well reveals the associated FHIR `Observation`.
- SRS §6.1: `plates`, `plate_wells` tables required (existed in SQL/migrations but had no ORM models).
- SRS NFR-S2/S7: auth via JWT; frontend must present a token to call protected endpoints.

## 3. Implementation Notes

### 3.1 Backend — plate/well persistence
**Files:** `middleware/models.py`, `middleware/api/routes/plates.py`
- Added `Plate` and `PlateWell` SQLAlchemy models (matching migration `0001` DDL).
  - **Bug fixed during implementation:** initial models used a `metadata` Column, which is a *reserved* name in SQLAlchemy declarative models; renamed to `meta = Column("metadata", JSON)` (mapped to the `metadata` DB column). Re-import validated.
- `POST /api/plates/` now persists a `Plate` + `PlateWell` rows (validates `plate_type`, row/col ranges, computes `well_index`). The well→Observation link is stored in `plate_wells.metadata['observation_uid']` (no schema migration required).
- `GET /api/plates/{id}` returns the plate with wells incl. `observationUid`, `id` (PK), and `metadata`.
- Added `GET /api/plates/{id}/wells/{well_id}/observation` to resolve and return the linked FHIR Observation.
- Endpoints keep `plate_read`/`plate_write` scope requirements.

### 3.2 Frontend — authentication + live plate load
**Files:** `frontend/src/utils/api.ts`, `frontend/src/components/LoginModal.tsx` (new), `frontend/src/components/Navigation.tsx`, `frontend/src/pages/MicroplateEditor.tsx`, `middleware/api/auth.py`
- `LoginModal` posts to `/api/auth/login` and stores the JWT in `localStorage['biosync_jwt']` (already consumed by `api.ts`). `Navigation` shows Sign in / Signed-in / Sign out.
- `MicroplateEditor` now loads a persisted plate from `GET /api/plates/1` on mount (best-effort; falls back to locally generated wells when no backend/plate). Wells carry `observationUid`, enabling the existing well-click → `fetchObservation(uid)` path (FR-3.2.3) to return the real FHIR Observation.
- `auth.py` dev-fallback scopes extended (plate/fhir/simulation/human_factors) so local login can exercise all feature areas; production still uses DB-backed scopes only.

### 3.3 Tests
- `tests/integration/test_api_plates.py` (new, DB-gated): create plate → link Observation → GET returns `observationUid` → dedicated well-observation endpoint returns the FHIR resource; missing plate → 404. Runs in CI (postgres:15 service).
- Frontend `microplate_editor.test.tsx`: **16 passed** (no regression from async backend load + new import).

## 4. Verification
- `JWT_SECRET=test-secret python -c "import api.routes.plates; import models"` → imports OK (after `metadata`→`meta` fix).
- `pytest --collect-only` → 378 tests collected, no import errors.
- `pytest tests/integration/test_api_plates.py` → 3 skipped locally (no DB), will run in CI.
- `npx vitest run tests/microplate_editor.test.tsx` → 16 passed.

## 5. Remaining
G1 final authenticity ingestion (external Illumina doc), G2 (real PyPulse build/verify), G3 (live-path perf hardening), EMA-spec nuance (G8), and the entire v1.1 advanced-analytics/AI scope (FR-3.11–3.16).
