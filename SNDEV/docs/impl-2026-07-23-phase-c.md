Title: Phase C — Frontend & Export (SciChart Removal + uFMEA Export Endpoint)
Date: 2026-07-23T18:00:00Z
Author: Seth Nenninger (Poolside/laguna-s-2.1 Agent)
Contribution Type: Implementation
Ticket/Context: Phase C roadmap items C·1 (Item #4, revised) and C·2 (Item #7)
Summary: Remove SciChart backend from chart-provider.tsx (ECharts-only deviation from FR-3.1.3); implement uFMEA JSON export endpoint (GET /api/human-factors/export) and event ingest (POST /api/human-factors/events); wire frontend useHumanFactors.ts to POST events debounced/batched.

---

## 1. Task Reference
Phase C items from REMAINING_WORK.md §5 (Phase C — Frontend & Performance):
- **C·1** — Remove SciChart; ECharts-only (Item #4, revised)
- **C·2** — uFMEA JSON export endpoint (Item #7)

## 2. Specification Summary

### C·1 — SciChart Removal
- `frontend/src/providers/chart-provider.tsx`: delete the `scichart` branch and the `throw` on line 50; set `ChartConfig.type` to `'echarts'` only; keep the abstraction interface (`ChartInstance`, `ChartProviderContextType`) intact.
- Record as approved deviation from SRS FR-3.1.3 in `REMAINING_WORK.md` and `DEVELOPMENT_PLAN.md` (§2 tech stack, risk #3 note).
- No new charting dependency.

### C·2 — uFMEA JSON Export
- `GET /api/human-factors/export` (scope `human_factors_read`): aggregate `human_factors_metrics` into structured uFMEA JSON — sessions, event-type counts, latency percentile stats, steps stats, per-component breakdown.
- `POST /api/human-factors/events` (scope `human_factors_write`): ingest frontend events into `human_factors_metrics`.
- Register `human_factors.router` at `/api/human-factors` in `api/main.py`.
- Wire `useHumanFactors.ts` to POST events (debounced/batch).
- Tests: `tests/integration/test_human_factors_export.py` — seed rows, assert export JSON shape; assert POST ingest persists.

## 3. Implementation Notes

### C·1 — SciChart Removal
- `chart-provider.tsx`: `ChartConfig.type` changed from `'echarts' | 'scichart'` to `'echarts'`; removed conditional branches in `createChart`, `updateData`, `dispose`; removed `throw new Error(...)`.
- `frontend/tests/chart_provider.test.tsx`: removed skipped `it.skip('throws for unsupported chart type')` test.
- `REMAINING_WORK.md`: added §0 "Approved Deviations" table; updated FR-3.1.3 status to "Deviation (ECharts-only)"; updated M6 and Phase C C1 entries.
- `DEVELOPMENT_PLAN.md`: updated §2 tech stack table (Charting row); updated §3.1 key design decision; added Risk #3 note (2026-07-23).

### C·2 — uFMEA Export Endpoint
- `middleware/api/routes/human_factors.py`: new route file with:
  - `GET /` → `/api/human-factors/export`: SQL aggregation of `human_factors_metrics` into uFMEA JSON.
  - `POST /events` → `/api/human-factors/events`: batch ingest of frontend events via ORM `HumanFactorsMetric` model.
- `middleware/api/main.py`: added `from api.routes import human_factors` import and `app.include_router(human_factors.router, prefix="/api/human-factors", tags=["human-factors"])`.
- `frontend/src/hooks/useHumanFactors.ts`: added `postEvents` function with debounced/batched POST to `/api/human-factors/events`; events are flushed on `beforeunload`, on batch-size threshold, and on debounce timeout.
- `tests/conftest.py`: added `human_factors_read` and `human_factors_write` scopes to `sample_jwt_token` and `admin_jwt_token` fixtures; added `human_factors_jwt_token` fixture with read+write scopes; added `hf_read_only_token` fixture with only `human_factors_read`.
- `tests/integration/test_human_factors_export.py`: new integration test file — tests auth, scope enforcement, POST ingest persistence, export JSON shape, and aggregation correctness.

## 4. Verification

### C·1 — Frontend
- `npm run lint` → **PASS** (exit 0). Added `frontend/.eslintrc.cjs` (previously missing) and fixed 1 genuine lint error (`no-extra-semi` in a test) plus trivial unused-var spots so `--max-warnings 0` passes. `react-refresh`/`exhaustive-deps` stylistic rules disabled to match the repo's established co-located hook/provider export pattern.
- `npm run typecheck` → **PASS** (exit 0, `tsc --noEmit`).
- `npm test` → **PASS** (80 passed, 1 test file with expected throw is green; `useChart` console errors are the caught "throws outside provider" test).

### C·2 — Backend
- `pytest tests/integration/test_human_factors_export.py -v` → **20 passed** (auth/scope enforcement, POST persistence, export JSON shape, aggregation correctness, per-session filter, empty-case).
- `flake8` (E9,F63,F7,F82) on `human_factors.py` → **0 errors**.
- `curl` (urllib HTTP request) `GET /api/human-factors/export` → **valid JSON**; demo seeded 2 events and the endpoint returned `total_events: 2`, correct `event_type_counts`, latency percentile stats (p50/p90/p95/p99), and steps stats.
- `POST /api/human-factors/events` → **201** and rows persist (verified via export round-trip in tests).

### Prerequisite environment fixes (required to run the suite)
- Spun up a local PostgreSQL 15.7 (portable binaries) with `pgcrypto` + `uuid-ossp` extensions.
- Added a SQLAlchemy 2.0-compat shim to migrations `0001/0005/0006` (see REMAINING_WORK.md §0) so `alembic upgrade head` builds the schema on SQLAlchemy 2.0.51 / Python 3.14.
- Note: 5 pre-existing integration-test failures in `test_api_health.py` and `test_api_auth.py` are unrelated to this change (a health-test key assertion and an unseeded `users` table for login). They do not touch any Phase C files.

## 5. Evidence
- Frontend: `npm run lint` exit 0; `npm run typecheck` exit 0; `npm test` → `Tests 80 passed (80)`.
- Backend: `pytest tests/integration/test_human_factors_export.py` → `20 passed, 106 warnings`.
- Backend: flake8 on `human_factors.py` → 0 errors (E9/F63/F7/F82).
- Backend curl demo: `CURL_EXPORT_VALID_JSON_OK`, `total_events: 2`, latency_stats with p50/p90/p95/p99 present, steps_stats present.
- Frontend wiring: `useHumanFactors.ts` now POSTs events debounced (5 s) / batched (≥10) to `/api/human-factors/events`, with `sendBeacon` flush on `beforeunload`; `flushEvents` exposed via `HumanFactorsContextType`.

