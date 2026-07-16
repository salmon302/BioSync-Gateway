Title: SRS Gap Analysis — Phase 1 Security & Phase 2 Core Features
Date: 2026-07-14T00:00:00Z
Author: Seth Nenninger (Qwen3.6 Flash Agent)
Contribution Type: Implementation
Ticket/Context: SRS gap analysis — Top 10 remaining items
Summary: JWT lifetime reduction, refresh tokens, EMA pipeline wiring, FHIR OperationOutcome, barcode expansion, per-channel EMA, plate import/export

---

# BioSync-Gateway — SRS Gap Analysis Implementation

**Date:** 2026-07-14 | **Phases:** 1 (Security) + 2 (Core Features)

---

## Task Reference

Derived from: [conception-2026-07-13-srs-gap-analysis.md](conception-2026-07-13-srs-gap-analysis.md)

## Specification Summary

### Phase 1 — Critical Security (P0)
1. **JWT lifetime ≤1 hour + refresh tokens** — Reduce `JWT_EXPIRATION_HOURS` from 24 to 1; add refresh token endpoint
2. **TLS 1.3 + DB client certs** — Add nginx reverse proxy config; add `sslmode=verify-full` to database connection

### Phase 2 — Core Feature Completion (P0/P1)
3. **Wire EMA filter into telemetry pipeline** — Use `MultiChannelEMAFilter` in ingest endpoint; pipe raw → EMA → alarm check
4. **Plate CSV/JSON import-export handlers** — Implement file I/O for `POST /{plate_id}/import` and `GET /{plate_id}/export`
5. **FHIR OperationOutcome proper response format** — Return `application/fhir+json` with proper OperationOutcome resource
6. **FHIR Bundle transaction processing** — Implement entry-by-entry processing with rollback semantics
8. **8/10-base barcode sequences** — Seed 8-base and 10-base UDI sequences; update `TRUSEQ_BARCODES` dict
10. **Per-channel EMA α defaults** — α=0.2 for pressure, α=0.1 for flow, α=0.3 for HR, α=0.4 for SpO₂

## Implementation Notes

### Files Changed

| File | Change |
|------|--------|
| `middleware/api/auth.py` | JWT_EXPIRATION_HOURS=1, refresh token functions, `/auth/refresh` endpoint |
| `middleware/api/main.py` | Register auth router, register admin router, response-time middleware |
| `middleware/api/routes/auth.py` | **NEW** — Login and refresh token endpoints |
| `middleware/api/routes/admin.py` | **NEW** — JWT rotate, EMA config, Pulse restart |
| `middleware/api/routes/telemetry.py` | EMA filter in ingest, WebSocket JWT auth, DB persistence |
| `middleware/api/routes/fhir.py` | OperationOutcome responses, Bundle transaction processing |
| `middleware/api/routes/plates.py` | CSV import, JSON export endpoints |
| `middleware/engine/signal.py` | Per-channel α defaults in MultiChannelEMAFilter |
| `middleware/engine/barcode.py` | TRUSEQ_BARCODES dict with 8/10-base sequences |
| `database/migrations/004-seed-barcodes.sql` | 8-base and 10-base UDI seed data |
| `docker-compose.yml` | nginx reverse proxy with TLS, DB sslmode |
| `middleware/api/routes/__init__.py` | Import new routers |

### Verification Steps

1. JWT tokens expire in 1 hour (was 24)
2. `/api/auth/refresh` returns new access token + new refresh token
3. Telemetry ingest applies EMA filtering before broadcast
4. Plate import accepts CSV, export returns JSON
5. FHIR validation returns `application/fhir+json` with OperationOutcome
6. Bundle POST processes entries with transaction semantics
7. MultiChannelEMAFilter uses per-channel α defaults
8. Barcode validation supports 8-base and 10-base sequences

### Test Results

| Test | Result |
|------|--------|
| JWT expiration ≤1h | PASS |
| Refresh token endpoint | PASS |
| EMA in telemetry pipeline | PASS |
| Plate import/export | PASS |
| FHIR OperationOutcome format | PASS |
| Bundle transaction processing | PASS |
| Per-channel EMA α | PASS |
| 8/10-base barcodes | PASS |
