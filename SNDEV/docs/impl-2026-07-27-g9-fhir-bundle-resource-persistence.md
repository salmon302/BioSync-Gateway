Title: G9 — FHIR Bundle persists all supported resource types
Date: 2026-07-27T13:33:27Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: Phase 4 — v1.0 Carry-Over Hardening (est. 3–4 days); gap G9 from impl-2026-07-26-srs-gap-audit-reaudit.md (lines 107, 164).
Summary: Hardened POST /api/fhir/Bundle (FR-3.7.5) so it durably persists EVERY supported FHIR resource type, not only Observation, via a single-source-of-truth persister registry shared with the standalone POST endpoints.

---

# 1. Task Reference

- Parent: **Phase 4 — v1.0 Carry-Over Hardening** (BioSync-Gateway remaining-work roadmap).
- Gap: **G9 — FHIR `Bundle` non-Observation persistence (FR-3.7.5)**, recorded as ⚠️ Open in `SNDEV/docs/impl-2026-07-26-srs-gap-audit-reaudit.md`:
  - Line 107: "`api/routes/fhir.py:315` acknowledges non-Observation entries 'without storage'."
  - Line 164 (Phase 4): "G9: persist all supported resource types within a FHIR transaction/batch Bundle, not only `Observation`."
- Spec: **SRS FR-3.7.5** — "The system shall support FHIR `Bundle` resources (type: `transaction` and `batch`) for bulk data submission."

# 2. Specification Summary

The FHIR interface exposes two persistable write endpoints — `POST /Observation` (FR-3.7.3) and `POST /DeviceMetric` (FR-3.7.2) — each backed by a durable table (`observations`, `device_metrics`). The `Bundle` transaction/batch handler must store every one of these supported resource types when submitted in bulk, rather than persisting only `Observation` and silently acknowledging the rest "without storage."

# 3. Implementation Notes

### 3.1 Root cause of the original gap
The prior `process_bundle` handler used a hand-maintained `if res_type == "Observation" … elif res_type == "DeviceMetric" … else: acknowledge without storage` chain. This is the exact anti-pattern G9 targets: adding a new supported resource type required remembering to extend the branch, and any omission produced a *silent* "accepted but not stored" result — dangerous for audit-grade data.

### 3.2 Fix — registry-driven persisters (single source of truth)
File: `middleware/api/routes/fhir.py`

- Extracted two module-level helpers that construct, `add()`, and `flush()` the ORM row (no commit) and return `(orm_object, canonical_id)`:
  - `_persist_observation(resource, db)` → `(Observation, observation_uid)`
  - `_persist_device_metric(resource, db)` → `(DeviceMetric, str(id))`
- Introduced `RESOURCE_PERSISTERS = {"Observation": …, "DeviceMetric": …}`, the canonical list of resource types the FHIR API can durably store.
- The **Bundle handler (`process_bundle`)** now dispatches via `RESOURCE_PERSISTERS.get(res_type)`:
  - If a persister exists and the method is `POST`/`PUT`, the entry is persisted (201 Created with a `Location` built from the canonical id).
  - Otherwise (genuinely unsupported type, or non-write method such as `GET`/`DELETE`) the entry is acknowledged without storage.
- The **standalone** `POST /Observation` and `POST /DeviceMetric` endpoints now call the *same* persisters, eliminating duplicated column-mapping logic and guaranteeing the Bundle path and the single-resource path store identical columns.

### 3.3 Behavior preserved (no regressions)
- Transaction bundles still roll back the entire batch on any validation **or** persistence (SQLAlchemy) error.
- Batch bundles still persist valid entries and report invalid entries (400) without aborting the batch.
- Response shapes unchanged: `201 Created` / `transaction-response` / `batch-response` with per-entry `response` objects.
- Unsupported resource types continue to be acknowledged (not stored), which is correct (e.g. an `OperationOutcome` or `GET` entry in a bundle).

### 3.4 Files changed
| File | Change |
|------|--------|
| `middleware/api/routes/fhir.py` | Added `_persist_observation`, `_persist_device_metric`, `RESOURCE_PERSISTERS`; rewired both standalone endpoints and `process_bundle` to use them. (Amended prior uncommitted DeviceMetric-in-Bundle branch into the registry design.) |
| `tests/unit/test_fhir_bundle_persistence.py` | Strengthened G9 unit test: added a registry-driven regression test (`test_bundle_persists_every_registered_supported_type`) and an unsupported-type boundary test (`test_bundle_unsupported_type_not_persisted`); fixed `_run` helper to use `asyncio.run` (Python 3.14 `get_event_loop()` raises when no loop is present). |

# 4. Verification

- **Command:** `python -m pytest tests/unit/test_fhir_bundle_persistence.py tests/unit/test_o15_fhir_bundle.py -v` (with `JWT_SECRET` set for module import).
- **Result:** **16 passed** (4 G9 bundle-persistence tests + 12 OQ-15 bundle structural/validation tests). **PASS.**
- Evidence that "all supported types" are persisted:
  - `test_bundle_persists_observation_and_device_metric`: 2 supported entries → `db.add` called 2×, both `201 Created`.
  - `test_bundle_persists_every_registered_supported_type`: builds one valid resource per key of `RESOURCE_PERSISTERS` and asserts `db.add.call_count == len(RESOURCE_PERSISTERS)` — this test fails automatically if a type is ever registered but not persisted (the G9 regression guard).
  - `test_bundle_unsupported_type_not_persisted`: an `OperationOutcome` entry → `db.add` called 0×, response `code == "ok"`.

# 5. Notes / Recommendations (out of scope for G9)

- **Integration-test drift — RESOLVED (follow-up, same date):** Updated `tests/integration/test_api_fhir.py` so the OQ-13/14/15 qualification evidence asserts the real FHIR-compliant contract (see §6). These tests are DB-gated (require a live Postgres per the audit's CI note) and were not executed locally; the assertions are now structurally aligned with `middleware/api/routes/fhir.py`.
- **Future supported types:** Adding e.g. a `Patient` FHIR write endpoint is now a one-line registration (`RESOURCE_PERSISTERS["Patient"] = _persist_patient`) plus the persister — no Bundle handler edit required.

# 6. Follow-up — Integration-Test Assertion Correction (same date)

The integration tests in `tests/integration/test_api_fhir.py` asserted a response contract the implementation does not (and should not) produce, undermining the OQ-13/14/15 qualification evidence. Corrected to the actual FHIR-compliant responses:

| Test | Before (drift) | After (correct) |
|------|----------------|-----------------|
| `test_create_valid_observation_accepted` | `status_code == 200`; `data["status"] == "created"` | `status_code == 201`; `data["resourceType"] == "Observation"`; `"id" in data` |
| `test_create_minimal_observation_accepted` | `status_code == 200` | `status_code == 201` |
| `test_create_valid_device_metric_accepted` | `status_code == 200`; `data["status"] == "created"` | `status_code == 201`; `data["resourceType"] == "DeviceMetric"`; `"id" in data` |
| `test_process_valid_transaction_bundle` | `data["status"] == "processed"` | `data["resourceType"] == "Bundle"`; `data["type"] == "transaction-response"`; per-entry `response.status == "201 Created"` |

Source of truth confirmed against `middleware/api/routes/fhir.py`:
- Single-resource `POST /Observation` and `POST /DeviceMetric` return `JSONResponse(..., status_code=201)` with `{"resourceType", "id", "resource"}` (no top-level `status`).
- `POST /Bundle` returns a `Bundle` of type `transaction-response`/`batch-response` whose `entry[].response.status` is `"201 Created"` for persisted resources.

These integration tests remain DB-gated (default `DATABASE_URL` = `postgresql://…@localhost:5432/biosync`); they run in CI against a live Postgres, not in this local environment. Verification here was by code review + `py_compile` (passed).
