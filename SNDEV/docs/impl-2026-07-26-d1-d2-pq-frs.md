Title: d1-pq1-pq3-pq4-and-d2-urs-frs
Date: 2026-07-26T12:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: D1 (item 8, revised) + D2 (item 9) — Performance Qualification tooling and URS/FRS authoring
Summary: Adopted Grafana k6 for PQ-1 load, added PQ-3 1M-row hash-chain test + PQ-4 soak skeleton, and authored docs/URS.md & docs/FRS.md.

---

## 1. Task Reference

- **D1 (item 8, revised):** Implement PQ-1 / PQ-3 / PQ-4 qualification tooling.
- **D2 (item 9):** Author `docs/URS.md` and `docs/FRS.md` derived from `SRS.md`.

## 2. Specification Summary

### D1 — Performance Qualification (revised plan)
- **Tooling:** Grafana k6 (`grafana/k6`) for distributed load; pytest micro-benchmarks retained for algorithmic engines.
- **PQ-1:** `tests/performance/k6/pq1_websocket.js` — ramp to 50 VUs over ~12 min; SLOs `http_req_failed<0.01`, `http_req_duration p(95)<250ms`, plus WS-specific `ws_connecting p(95)<250ms` (only when a JWT is supplied). Triggered via `workflow_dispatch` + nightly `pq.yml`. The old CI "smoke-only" import micro-benchmarks in `test_pq1_websocket_latency.py` were replaced by a pointer test + docstring directing to k6.
- **PQ-3:** 1,000,000-row `audit_log` insert (`generate_series`, hash computed by the existing `audit_log_hash_chain` trigger inside the DB) → run `database/migrations/hash-chain-check.sql` → assert completion `< 60s` (NFR-P4) and integrity `= 'ok'`. Added `tests/performance/test_pq3_1m_rows.py`, gated behind `BIOSYNC_PQ3_DATABASE_URL` so it only runs against a dedicated/throwaway Postgres (docker-compose or cloud), never the shared CI DB.
- **PQ-4:** Deferred per user direction. Provided `SNDEV/scripts/pq4_24h_ingest.py` skeleton with a `--mode smoke` short burst and a clearly commented/disabled 24h soak section. No CI execution.

### D2 — Specification authoring
- `docs/URS.md`: user classes (SRS §2.2), user-facing functional requirements, clinical/safety thresholds (alarms, d≥3, 0.5µL, immutability), operating environment (§2.3), constraints, and the SciChart deviation note.
- `docs/FRS.md`: FR-3.x → components mapping, §6.1 tables → owning modules, the four math engines (Hamming/EMA/Dilution/Hash-Chain) with formulas and source files, an FR→URS→Component→OQ/PQ traceability matrix, and the SciChart deviation note.

## 3. Implementation Notes

### Files created / modified
- `tests/performance/k6/pq1_websocket.js` (new) — k6 PQ-1 load script (ramping-vus, thresholds, optional WS via `API_TOKEN`).
- `tests/performance/test_pq1_websocket_latency.py` (modified) — replaced micro-benchmarks with a pointer test + migration docstring.
- `tests/performance/test_pq3_1m_rows.py` (new) — 1M-row insert via PL/pgSQL `generate_series` loop + run `hash-chain-check.sql` + assert `<60s` and integrity `ok`; gated by `BIOSYNC_PQ3_DATABASE_URL`.
- `SNDEV/scripts/pq4_24h_ingest.py` (new) — PQ-4 smoke/soak skeleton (soak disabled/commented).
- `.github/workflows/pq.yml` (new) — `workflow_dispatch` (pq choice) + nightly cron; `pq1-k6` (docker-compose + grafana/k6) and `pq3-1m` (dedicated Postgres) jobs.
- `docs/URS.md`, `docs/FRS.md` (new) — D2 specifications.
- `tests/conftest.py` (modified) — registered `pq1`/`pq3`/`pq4` pytest markers.

### Verification performed (local)
- `python -m py_compile` on `test_pq3_1m_rows.py`, `test_pq1_websocket_latency.py`, `pq4_24h_ingest.py` → PASS (no syntax errors).
- `node --check tests/performance/k6/pq1_websocket.js` → PASS.
- `pytest tests/performance/test_pq1_websocket_latency.py tests/performance/test_pq3_1m_rows.py -v` → `test_pq1_k6_asset_present PASSED`, `TestPQ3HashChain1M::test_1m_rows_hash_chain_under_60s SKIPPED` (DB URL unset, as designed).

### Notes / rationale
- The PQ-3 insert uses a PL/pgSQL `FOR i IN SELECT generate_series(1,1e6) LOOP ... INSERT ... END LOOP` rather than a single `INSERT ... SELECT generate_series(...)`. The `audit_log_hash_chain` trigger derives `previous_hash` from the latest committed row; within one multi-row statement the new rows are mutually invisible, which would produce a broken chain. The per-statement loop (within a single transaction) yields a correctly chained, valid 1M-row audit log.
- `TRUNCATE audit_log RESTART IDENTITY` is used so the first row is `id=1`, keeping the genesis-row branch of `hash-chain-check.sql` valid on the dedicated test DB.
- SciChart deviation is documented in both `docs/URS.md` (§9.1) and `docs/FRS.md` (§8.1): SRS FR-3.1.3 lists ECharts + SciChart.js as swappable; only the ECharts backend is implemented, with the `chart-provider` seam retained.

### Not executed (per instructions)
- No `git commit` (none requested).
- PQ-4 soak (deferred) and the heavy `pq.yml` jobs are not run in this environment; they target disposable cloud / docker-compose runners.
