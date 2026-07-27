Title: Phase B/C/D Remaining-Work Implementation
Date: 2026-07-23T00:00:00Z
Author: Seth Nenninger (Poolside/laguna-s-2.1 Agent)
Contribution Type: Implementation
Ticket/Context: Remaining work items 1–9 (Phase B/C/D roadmap)
Summary: Persist FHIR POST endpoints, vectorize barcode Hamming distance, seed authentic Illumina UDI barcodes, add LTTB downsampling, symmetrize microplate import/export, implement uFMEA export endpoint, real PQ-1/PQ-3/PQ-4 tests, and write URS/FRS docs.

---

## 1. Task Reference
Items from REMAINING_WORK.md §0 and the user-approved plan (Phase B/C/D).
SRS refs: FR-3.3.1–3.3.4, FR-3.7.2–3.7.3, FR-3.1.2/3.1.3, FR-3.2.5, FR-3.9.2, PQ-1/PQ-3/PQ-4, NFR-P2/P4.

## 2. Specification Summary
See approved plan. Locked decisions:
- SciChart removed (ECharts-only) — explicit deviation from FR-3.1.3.
- PQ tests via Grafana k6 + Docker Compose; PQ-4 deferred to script-only.
- Barcode authenticity sourced from version-controlled DB seed manifest.

## 3. Implementation Notes

### Phase B (Functional Correctness)
- **B1 FHIR persistence** (`middleware/api/routes/fhir.py`): add `db: Session = Depends(get_db)` to `create_observation` and `create_device_metric`; persist via ORM `Observation`/`DeviceMetric`; return HTTP 201 with `Location` header; remove placeholder.
- **B2 Barcode vectorization** (`middleware/engine/barcode.py`): NumPy integer-encode matrix, vectorized pairwise Hamming; preserve return schema; keep scalar fn for unequal-length ValueError.
- **B3 Barcode authenticity**: new `database/seeds/illumina_udis_v1.0.0.json` (authentic 8/10-base TruSeq/Nextera UDIs); migration seeds `barcode_indices`; `load_barcode_set()` queries DB with in-memory cache.
- **B4 LTTB**: new `engine/lttb.py`; backend history endpoint + WS replay downsampling; frontend removes `.slice(-1000)` cap.
- **B5 Microplate symmetry**: add `handleImportJSON` + `handleExportCSV` to `MicroplateEditor.tsx`.

### Phase C (Frontend & Export)
- **C1 SciChart removal** (`chart-provider.tsx`): delete `scichart` branch; ECharts-only.
- **C2 uFMEA export** (`human_factors.py`): `GET /api/human-factors/export` + `POST /api/human-factors/events`.

### Phase D (Qualification & Docs)
- **D1 PQ tests**: k6 scripts in `tests/performance/k6/`; PQ-3 `generate_series` 1M seed; PQ-4 script skeleton in `SNDEV/scripts/`.
- **D2 Docs**: `docs/URS.md`, `docs/FRS.md`.

## 4. Verification
- Backend: `flake8`, `mypy`, `pytest tests/`
- Frontend: `npm run lint`, `npm run typecheck`, `npm test`
- PQ: `docker compose up -d db`; run k6 scripts / PQ-3 1M test.
- Evidence recorded per-item below as work proceeds.

## 5. Phase B Verification Results
- **flake8** (E9,F63,F7,F82): **0 errors** across all changed Python files.
- **TypeScript typecheck** (`tsc --noEmit`): **clean** (0 errors).
- **Frontend tests** (`vitest`): **80 passed, 1 skipped**.
- **Backend unit + OQ tests**: **146 passed, 7 skipped** (PyPulse), 0 failed.
- **Barcode tests** (OQ-1, OQ-2, PQ-5, authenticity): **23 passed**.
- **LTTB tests**: **10 passed** (including 100k-point <1s performance).
- Pre-existing issues NOT introduced by these changes:
  - `database.py:90` SQLAlchemy 2.0 `declarative_base()` deprecation warning.
  - `frontend/` has no ESLint config file (lint command fails on setup, not code).
  - `tests/integration/test_api_auth.py` requires `JWT_SECRET` env var (Phase A fail-closed security, working as intended).

## 5. Per-Item Evidence

### B1 — FHIR POST persistence (DONE)
- `middleware/api/routes/fhir.py`: added `db: Session = Depends(get_db)` + `DeviceMetric` import to both POST handlers; persist via ORM with try/except → `OperationOutcome` 500 on DB error; return HTTP 201 + `Location` header; implemented GET `/Observation/{id}` + GET `/DeviceMetric/{id}` from DB.
- Existing tests pass: `test_oq10_valid_observation.py`, `test_oq11`, `test_oq12` → **9 passed**.
- Module import OK with `JWT_SECRET` set (guard from Phase A fires correctly without it).
- TODO: add `tests/integration/test_fhir_persist.py` (201 + DB round-trip) — deferred to B1 verification step if DB available.

### B2 — Barcode vectorization (DONE)
- `middleware/engine/barcode.py`: added `_encode_sequences()` (uint8 matrix); rewrote `validate_plate_indices` and `validate_plate_barcodes` to use NumPy broadcast pairwise Hamming `(matrix[:,None,:] != matrix[None,:,:]).sum(-1)` + `np.triu_indices`; preserved scalar `hamming_distance()` for unequal-length `ValueError`; preserved exact violation return schema.
- Updated `tests/performance/test_pq5_barcode_benchmark.py::test_96_index_pairwise_count` to assert vectorized pair count via `np.triu_indices` instead of instrumenting scalar calls.
- Tests: OQ-1, OQ-2, PQ-5 → **15 passed**.
- Benchmark: 384-well plate (73,440 pairs) → **5.6 ms** (was ~8 s pure Python); protects async event loop (DEVELOPMENT_PLAN risk #5).

### B3 — Barcode authenticity (DONE)
- New `database/seeds/illumina_udis_v1.0.0.json`: version-controlled manifest with 24 validated 8-base and 24 validated 10-base sequences each for TruSeq and Nextera sets (min Hamming distance ≥ 3 verified programmatically).
- `middleware/alembic/versions/0003_seed_barcodes.py`: rewritten to load from the JSON manifest into `barcode_indices` (canonical schema: `index_name`, `index_sequence`, `barcode_set`, `kit_type`).
- `database/migrations/004-seed-barcodes.sql`: updated to match manifest with 8/10-base authentic sequences (raw SQL path consistency).
- `middleware/models.py`: added `BarcodeIndex` ORM model for `barcode_indices` table.
- `middleware/engine/barcode.py`: `load_barcode_set()` now queries DB via `BarcodeIndex` model with in-memory cache; built-in `TRUSEQ_BARCODES` updated to 8-base authentic sequences (fallback only); removed fake Nextera built-in sets.
- New `tests/unit/test_barcode_authenticity.py`: 8 tests validating manifest existence, required sets, valid DNA, min Hamming distance, load_barcode_set fallback, and 8-base TruSeq length.
- Tests: **8 passed** (1 pre-existing SQLAlchemy 2.0 deprecation warning, not from these changes).
- Full unit+OQ suite: **136 passed, 7 skipped** (PyPulse), 0 failed.

### B4 — LTTB downsampling (DONE)
- New `middleware/engine/lttb.py`: pure-Python/NumPy LTTB implementation (`lttb()`, `lttb_multichannel()`, `downsample_telemetry()`).
- `middleware/api/routes/telemetry.py`: added `GET /api/telemetry/history` endpoint with LTTB downsampling (query params: channel, from_time, to_time, threshold).
- `frontend/src/utils/lttb.ts`: TypeScript LTTB port (`lttb()`, `downsampleTelemetry()`).
- `frontend/src/pages/TelemetryDashboard.tsx`: removed `.slice(-1000)` hard cap (now 10,000-point buffer); applies frontend LTTB downsampling to 2,000 points before chart update; wired `acknowledgedAlarms` into alarm banner display.
- New `tests/unit/test_lttb.py`: 10 tests (preserves first/last, preserves peaks, edge cases, 100k-point <1s performance).
- Tests: **10 passed**. TypeScript typecheck: clean. Frontend tests: **80 passed, 1 skipped**.

### B5 — Microplate import/export symmetry (DONE)
- `frontend/src/pages/MicroplateEditor.tsx`: added `handleImportJSON` (reads/validates JSON PlateData) and `handleExportCSV` (emits `row,col,state,sampleId,concentration`); added both buttons alongside existing CSV import + JSON export → all four combos (CSV↔JSON in/out).
- TypeScript typecheck: clean. Frontend tests: **80 passed, 1 skipped**.
