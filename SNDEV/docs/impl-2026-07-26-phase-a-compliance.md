Title: Phase A compliance quick-wins (alarm threshold consistency + missing IQ tests)
Date: 2026-07-26T00:00:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: BioSync-Gateway SRS-v1.1 gap remediation; follows SNDEV/docs/impl-2026-07-26-srs-remaining-work.md (gap analysis)
Summary: Fixed frontend/backend alarm-threshold divergence (gap G6) and added the missing IQ-2/3/6/7 qualification tests (gap D1), verifying IQ-2 passes locally and DB-gated tests skip cleanly.

---

## 1. Task Reference
Remediation of gaps enumerated in `SNDEV/docs/impl-2026-07-26-srs-remaining-work.md`:
- **G6** — Alarm threshold inconsistency between frontend and backend.
- **D1** — Missing IQ-2 / IQ-3 / IQ-6 / IQ-7 qualification tests (SRS §7.1).

## 2. Specification Summary
- SRS FR-3.1.5 / FR-3.5.4: alarm evaluation must be consistent; backend evaluates alarms on the EMA-filtered value (`middleware/api/routes/telemetry.py:29-34`, `ALARM_THRESHOLDS`).
- SRS §7.1 IQ-2..IQ-7: installation-qualification gates for Python version, pgcrypto, trigger introspection, and clean Alembic upgrade.

## 3. Implementation Notes

### 3.1 G6 — Frontend/backend alarm threshold alignment
**File:** `frontend/src/pages/TelemetryDashboard.tsx:39-49`
- Backend `ALARM_THRESHOLDS` (authoritative, server-side per FR-3.5.4) uses:
  `pressure {high:150}`, `flow {low:-60, high:60}`, `hr {low:50, high:120}`, `spo2 {low:90}`.
- Frontend `alarmThresholds` ref previously diverged: `pressure high:140`, `flow {low:1, high:80}`, `hr {low:40, high:160}`, `spo2 {low:88}`.
- Updated the frontend constants to exactly mirror the backend values, with a comment requiring the two sources stay in lock-step. This makes the client visualization agree with server-side alarm state.

### 3.2 D1 — Missing IQ qualification tests
Added four tests under `tests/`:
- `tests/test_iq2_python_version.py` — pure, asserts `sys.version_info >= (3,11)`; **runs everywhere** (verified PASS locally on Python 3.14.3).
- `tests/test_iq3_pgcrypto.py` — asserts `crypt('test', gen_salt('bf'))` returns a hash; **DB-gated**, skips when `DATABASE_URL` unset.
- `tests/test_iq6_triggers_installed.py` — introspects `pg_trigger` for `audit_log_prevent_update` + `audit_log_prevent_delete`; **DB-gated**.
- `tests/test_iq7_alembic_upgrade.py` — drives `alembic upgrade head` against `DATABASE_URL`; **DB-gated**.
All three DB-gated tests skip cleanly without a live PostgreSQL (verified) and will execute in CI where the `postgres:15` service is provisioned.

## 4. Verification
- `python -m pytest tests/test_iq2_python_version.py tests/test_iq3_*.py tests/test_iq6_*.py tests/test_iq7_*.py -v` from repo root → **1 passed, 3 skipped**.
- EMA OQ-6 regression still green: `tests/test_oq6_ema_convergence.py` → 5 passed.
- Frontend edit is a constant-literal change (no logic); not separately unit-run here (requires `npm test`/vitest).

## 5. Out-of-scope / deferred (documented, not fixed this session)
- **G8 (EMA OQ-6 ≤4 vs ≤5):** SRS OQ-6 demands convergence "within 5% after ≤4 iterations" but with α=0.5 the step 0→100 reaches 5% only at step 5 (50→75→87.5→93.75→96.875). The current `≤5` is mathematically correct; tightening to `≤4` would be wrong. This is a **genuine SRS internal inconsistency**, not a code defect — requires a spec decision (adjust tolerance or α), so left unchanged and flagged.
- **G1** (barcode authenticity — real Illumina sequences), **G2** (real PyPulse build), **G3** (live-path perf hardening), **G4** (well-click → FHIR fetch), and the entire **v1.1 advanced-analytics/AI scope (FR-3.11–3.16)** remain unimplemented — see the gap-analysis doc.
