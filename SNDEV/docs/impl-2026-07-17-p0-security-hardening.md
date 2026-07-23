Title: p0-security-hardening-implementation
Date: 2026-07-17T15:00:00Z
Author: Seth Nenninger (Qwen3.5-Flash Agent)
Contribution Type: Implementation
Ticket/Context: P0 — Blocks Compliance / Security Certification
Summary: Implementing 6 critical security and compliance items to achieve regulatory certification readiness.

---

# P0 Security Hardening — Implementation Plan

## Overview
This implementation addresses all 6 P0 items identified in the SRS gap analysis to achieve regulatory compliance and security certification readiness.

## Items to Implement

### 1. JWT Lifetime ≤1 Hour + Refresh Tokens (P0-1)
- **Files:** `middleware/auth.py`, `api/routes/auth.py`
- **Changes:**
  - Reduce `JWT_EXPIRATION_HOURS` from 24 to 1
  - Add `/api/auth/refresh` endpoint
  - Implement refresh token storage and validation
  - Add refresh token rotation

### 2. TLS 1.3 for All Traffic (P0-2)
- **Files:** `nginx/nginx.conf`, `docker-compose.yml`, `nginx/README.md`
- **Changes:**
  - Configure nginx as reverse proxy with Let's Encrypt
  - Enable TLS 1.3 only (disable TLS 1.2)
  - Add HSTS headers
  - Update docker-compose service dependencies

### 3. Wire EMA Filter into Telemetry Pipeline (P0-3)
- **Files:** `middleware/database.py`, `api/routes/telemetry.py`, `engine/pulse.py`
- **Changes:**
  - Modify `POST /api/telemetry/ingest` to apply EMA before alarm check
  - Store both raw and filtered values in `observations` table
  - Update `MultiChannelEMAFilter` to use per-channel α defaults (α=0.2 pressure, α=0.1 flow)
  - Update alarm logic to check filtered values

### 4. Plate Import/Export File Handlers (P0-4)
- **Files:** `frontend/src/utils/fileHandler.ts`, `frontend/src/components/MicroplateEditor.tsx`
- **Changes:**
  - Implement `handleImportCSV` with CSV parsing and validation
  - Implement `handleExportJSON` with FileSaver utility
  - Add batch coordinate input modal
  - Add "Apply Status" button for batch operations

### 5. FHIR OperationOutcome Response Format (P0-5)
- **Files:** `middleware/fhir_validator.py`, `api/routes/fhir.py`
- **Changes:**
  - Return `Content-Type: application/fhir+json` for validation errors
  - Return proper FHIR OperationOutcome resource structure
  - Update error response schema

### 6. FHIR Bundle Transaction Processing (P0-6)
- **Files:** `api/routes/fhir.py`, `middleware/database.py`
- **Changes:**
  - Implement `POST /api/fhir/Bundle` endpoint
  - Add transaction semantics (all-or-nothing persistence)
  - Add Bundle parsing and entry-by-entry validation
  - Add rollback on failure

## Verification Plan

### Unit Tests
- `tests/OQ/test_jwt_auth.py` — OQ-13, OQ-14, OQ-15 (JWT lifetime, refresh, rotation)
- `tests/integration/test_ema_pipeline.py` — EMA filtering and alarm logic
- `tests/integration/test_plate_import_export.py` — CSV import, JSON export
- `tests/integration/test_fhir_bundle.py` — Bundle transaction semantics

### Integration Tests
- Verify JWT expires after 1 hour
- Verify refresh token rotation works
- Verify TLS 1.3 only (test with openssl s_client)
- Verify EMA-filtered alarms trigger correctly
- Verify import/export round-trip preserves data
- Verify FHIR Bundle transaction rollback on error

### Security Validation
- Run `nmap --script ssl-enum-ciphers -p 443 <host>` to confirm TLS 1.3
- Verify JWT payload shows `exp` ≤ 1 hour from `iat`
- Verify refresh tokens are single-use (rotation)
- Verify audit log captures all auth events

## Dependencies
- **Python:** `cryptography` (for refresh token encryption), `httpx` (for FHIR calls)
- **Node:** `papaparse` (CSV parsing), `file-saver` (already installed)
- **Docker:** nginx:alpine with TLS 1.3 support

## Timeline
- **Day 1:** JWT lifetime + refresh tokens (P0-1)
- **Day 2:** TLS 1.3 configuration (P0-2)
- **Day 3:** EMA pipeline wiring (P0-3)
- **Day 4:** Plate import/export (P0-4)
- **Day 5:** FHIR OperationOutcome + Bundle (P0-5, P0-6)
- **Day 6:** Testing and validation

---

*Implementation begins immediately. All changes will be committed with DCO sign-off and linked to this log.*
