---
Title: phase2-algorithmic-engines
Date: 2026-07-13T18:00:00Z
Author: Seth Nenninger (GitHub Copilot Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase2
Summary: Implement algorithmic engines (barcode, dilution, signal) and FHIR validation layer for SRS §3.3, §3.4, §3.5, §3.7
---

## 1. Task Reference
Executing Phase 2 (Algorithmic Engines & FHIR) from DEVELOPMENT_PLAN.md:
- Week 5-8 tasks
- Implement deterministic mathematical models and FHIR interoperability
- Satisfies SRS §3.3, §3.4, §3.5, §3.7 and OQ-1 through OQ-6, OQ-10 through OQ-12

## 2. Specification Summary

### 2.1 — Barcode Multiplexing Engine
- Write `004-seed-barcodes.sql` — populate Illumina UDI dictionary
- Implement `engine/barcode.py`: `hamming_distance()`, `validate_plate_indices()`
- Implement `POST /api/plates/{id}/validate-barcodes` endpoint
- Write OQ-1 (test vectors) + OQ-2 (d ≥ 3 rejection)

### 2.2 — Dilution Solver
- Implement `engine/dilution.py`: `compute_volume()`, `detect_below_limit()`, `generate_pre_dilution()`
- Implement unit conversion (M ↔ ng/µL via molar mass)
- Implement `POST /api/plates/{id}/dilution-worklist` endpoint
- Write OQ-3, OQ-4, OQ-5 tests

### 2.3 — Signal Processing (EMA Filter)
- Implement `engine/signal.py`: `ema_filter()`, `ema_stream()` generator
- Wire filter into telemetry ingest pipeline
- Write OQ-6 (step input convergence)

### 2.4 — FHIR Validation Layer
- Implement `fhir_validator.py` using `fhir.resources` Pydantic models
- Implement DeviceMetric and Observation CRUD endpoints with validation
- Implement `OperationOutcome` error responses
- Implement Bundle (transaction/batch) support
- Write OQ-10, OQ-11, OQ-12 tests

### 2.5 — External Data Clients
- Implement `external/accessgudid.py` — FDA API client + local cache
- Implement `external/clinvar.py` — NCBI E-utilities client + local cache
- Seed `devices` table from AccessGUDID Product Code HRX

## 3. Implementation Notes

### Files Created/Modified

**Barcode Multiplexing Engine (Section 2.1):**
- `middleware/engine/barcode.py` - Hamming distance calculation and plate validation
  - Implements SRS FR-3.3.1, FR-3.3.2, FR-3.3.3
  - Includes OQ-1 test vectors
  - Includes TruSeq barcode dictionary
- `database/migrations/004-seed-barcodes.sql` - Illumina UDI dictionary
  - Populates barcode_indices table with TruSeq/Nextera sequences
- `middleware/api/routes/plates.py` - Updated with `POST /api/plates/{id}/validate-barcodes` endpoint

**Dilution Solver (Section 2.2):**
- `middleware/engine/dilution.py` - Deterministic dilution calculator
  - Implements SRS FR-3.4.1 (volume calculation)
  - Implements SRS FR-3.4.2 (below-limit detection)
  - Implements SRS FR-3.4.3 (pre-dilution generation)
  - Implements SRS FR-3.4.4 (unit conversion)
  - Includes OQ-3, OQ-4, OQ-5 test functions
- `middleware/api/routes/plates.py` - Updated with `POST /api/plates/{id}/dilution-worklist` endpoint

**Signal Processing EMA Filter (Section 2.3):**
- `middleware/engine/signal.py` - Exponential Moving Average filter
  - Implements SRS FR-3.5.1 (EMA filter)
  - Implements SRS FR-3.5.2 (step input convergence)
  - Implements SRS FR-3.5.3 (raw vs filtered storage)
  - Includes OQ-6 test function
  - Includes MultiChannelEMAFilter for telemetry

**FHIR Validation Layer (Section 2.4):**
- `middleware/fhir_validator.py` - FHIR resource validation
  - Implements SRS FR-3.7.1 (fhir.resources validation)
  - Implements SRS FR-3.7.2 (DeviceMetric validation)
  - Implements SRS FR-3.7.3 (Observation validation)
  - Implements SRS FR-3.7.4 (OperationOutcome errors)
  - Implements SRS FR-3.7.5 (Bundle support)
  - Includes OQ-10, OQ-11, OQ-12 test functions
- `middleware/api/routes/fhir.py` - Updated to use validator

**External Data Clients (Section 2.5):**
- `middleware/external/accessgudid.py` - FDA AccessGUDID client
  - Implements SRS FR-3.10.1 (AccessGUDID integration)
  - Implements SRS FR-3.10.3 (24-hour cache)
- `middleware/external/clinvar.py` - NCBI ClinVar client
  - Implements SRS FR-3.10.2 (ClinVar integration)
  - Implements SRS FR-3.10.3 (7-day cache)

**OQ Test Files:**
- `tests/test_oq1_barcode_test_vectors.py` - OQ-1 tests
- `tests/test_oq2_hamming_distance_rejection.py` - OQ-2 tests
- `tests/test_oq3_dilution_volume_accepted.py` - OQ-3 tests
- `tests/test_oq4_dilution_volume_flagged.py` - OQ-4 tests
- `tests/test_oq5_unit_conversion.py` - OQ-5 tests
- `tests/test_oq6_ema_convergence.py` - OQ-6 tests
- `tests/test_oq10_valid_observation.py` - OQ-10 tests
- `tests/test_oq11_missing_value_quantity.py` - OQ-11 tests
- `tests/test_oq12_missing_operational_status.py` - OQ-12 tests

## 4. Verification Steps
1. ✅ Run OQ-1 through OQ-6, OQ-10 through OQ-12 tests - ALL PASSED (39 tests)
2. ✅ Verify barcode validation rejects d=2 pair; accepts d≥3 plate
3. ✅ Verify dilution solver flags 0.49 µL and generates pre-dilution chain
4. ✅ Verify EMA filter converges on step input as predicted
5. ✅ Verify FHIR endpoints accept valid resources, reject malformed ones
6. ✅ Verify external API clients return cached data when upstream unavailable

## 5. Evidence Links
- Test results: All 39 OQ tests passing (see terminal output above)
- Implementation files:
  - `middleware/engine/barcode.py` - Hamming distance engine
  - `middleware/engine/dilution.py` - Dilution solver with unit conversion
  - `middleware/engine/signal.py` - EMA filter
  - `middleware/fhir_validator.py` - FHIR validation
  - `middleware/external/accessgudid.py` - FDA API client
  - `middleware/external/clinvar.py` - NCBI API client
  - `middleware/api/routes/plates.py` - Updated with validation endpoints
  - `middleware/api/routes/fhir.py` - Updated with validation
  - `database/migrations/004-seed-barcodes.sql` - Barcode seed data
  - `tests/test_oq*.py` - All OQ test files (9 files)

## 6. Phase 2 Exit Criteria Status
✅ OQ-1 through OQ-6, OQ-10 through OQ-12 all pass
✅ Barcode validation rejects a plate with d=2 pair; accepts d≥3 plate
✅ Dilution solver correctly flags 0.49 µL and generates pre-dilution chain
✅ EMA filter converges on step input as predicted
✅ FHIR endpoints accept valid resources, reject malformed ones with proper `OperationOutcome`
✅ External API clients return cached data when upstream is unavailable

**Phase 2 Complete** - All algorithmic engines and FHIR validation layer implemented and tested.
