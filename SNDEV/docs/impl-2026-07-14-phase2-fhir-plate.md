Title: Phase 2 FHIR Bundle and Plate Import/Export Implementation
Date: 2026-07-14T10:00:00Z
Author: Seth Nenninger (Poolside: Laguna XS 2.1 Agent)
Contribution Type: Implementation
Ticket/Context: Phase 2 Development Plan - Items 4, 5, 6
Summary: Implemented plate CSV/JSON import-export and FHIR OperationOutcome/Bundle transaction support

## Task Reference
Phase 2 Development Plan items 4, 5, 6:
- Item 4: Plate CSV/JSON import-export (80 lines)
- Item 5: FHIR OperationOutcome proper response (40 lines)
- Item 6: FHIR Bundle transaction (60 lines)

## Specification Summary

### Phase 2 Item 4 - Plate CSV/JSON Import-Export
- POST /{plate_id}/import: Accept CSV or JSON file upload, parse plate layout
- GET /{plate_id}/export: Return plate layout as CSV or JSON stream
- Support well positions (A1-H12 format) with sample_id, barcode, concentration fields

### Phase 2 Item 5 - FHIR OperationOutcome Response
- Return application/fhir+json content type for all FHIR responses
- Proper OperationOutcome structure with severity, code, details, location
- Used for validation errors in Observation, DeviceMetric, and Bundle endpoints

### Phase 2 Item 6 - FHIR Bundle Transaction
- POST /Bundle: Process transaction bundles with entry-by-entry processing
- Implement transaction semantics with rollback on error
- Return transaction-response bundle with status codes

## Implementation Notes

### Files Changed

1. **middleware/api/routes/plates.py**
   - Added imports: csv, io, json, UploadFile, File, StreamingResponse
   - Added POST /{plate_id}/import endpoint (~50 lines)
   - Added GET /{plate_id}/export endpoint (~50 lines)
   - Supports both CSV and JSON formats for import/export

2. **middleware/fhir_validator.py**
   - Added to_operation_outcome() helper function (~20 lines)
   - Returns proper FHIR OperationOutcome structure

3. **middleware/api/routes/fhir.py**
   - Added imports: Response, JSONResponse
   - Updated create_observation() to return JSONResponse with application/fhir+json
   - Updated create_device_metric() to return JSONResponse with application/fhir+json
   - Implemented POST /Bundle with transaction semantics (~80 lines)
   - Entry-by-entry validation and processing
   - Rollback on error with combined OperationOutcome

## Verification Steps

1. **Plate Import/Export**
   - Import CSV: curl -X POST -F "file=@plate.csv" http://localhost:8000/plates/1/import
   - Export JSON: curl -X GET http://localhost:8000/plates/1/export?format=json
   - Export CSV: curl -X GET http://localhost:8000/plates/1/export?format=csv

2. **FHIR OperationOutcome**
   - Invalid Observation: Returns 400 with OperationOutcome in application/fhir+json
   - Invalid DeviceMetric: Returns 400 with OperationOutcome in application/fhir+json

3. **FHIR Bundle Transaction**
   - POST valid bundle: Returns transaction-response bundle
   - POST bundle with errors: Returns OperationOutcome with error details

## Evidence Links
- Code changes applied via replace_string_in_file tool
- All edits returned "successfully edited" status

## Phase 2 Item 7 - External API Calls (Additional)

### Files Changed

4. **middleware/external/accessgudid.py**
   - Added rate_limit decorator for API throttling
   - Added async _get_session() method for HTTP client management
   - Added async _make_request() method with httpx support
   - Updated get_device() to use real API calls with fallback to mock data
   - Updated search_devices() to use real API calls with fallback to mock data
   - Added httpx AsyncClient with connection pooling

5. **middleware/external/clinvar.py**
   - Added rate_limit decorator (3 calls/second for NCBI)
   - Added async _get_session() method for HTTP client management
   - Added async _make_request() method with httpx support
   - Updated get_variant() to use NCBI E-utilities efefch.fcgi API
   - Updated search_variants() to use NCBI E-utilities esearch.fcgi API
   - Updated get_variant_by_coordinates() to use genomic coordinate search
   - Added proper API key support for increased rate limits

### Verification Steps

1. **AccessGUDID Client**
   - get_device("HRX-001"): Returns device data from API or mock fallback
   - search_devices("HRX"): Returns device list from API or mock fallback

2. **ClinVar Client**
   - get_variant("12345"): Returns variant data from ClinVar API
   - search_variants("BRCA1"): Returns variant list from ClinVar API
   - get_variant_by_coordinates("chr1", 12345, "A", "T"): Returns variant by coordinates

### Evidence Links
- All edits returned "successfully edited" status

## Phase 2 Item 9 - Performance Instrumentation

### Files Changed

6. **middleware/api/main.py**
   - Added PerformanceMiddleware class for response time tracking
   - Added X-Response-Time-ms header to all responses
   - Logs slow requests (>100ms) for performance monitoring
   - Added to FastAPI middleware stack

7. **frontend/src/pages/TelemetryDashboard.tsx**
   - Added FPS counter state and refs for performance tracking
   - Added FPS tracking via requestAnimationFrame loop
   - Displays FPS in connection status area when streaming
   - Tracks frame count and updates every second

8. **.github/workflows/ci.yml**
   - Added response time check in Docker Compose test step
   - Added new performance-tests job with benchmark script
   - Benchmarks EMA filter (10k iterations)
   - Benchmarks Hamming distance (10k iterations)
   - Timeout: 5 minutes

### Verification Steps

1. **Response Time Header**
   - All API responses include X-Response-Time-ms header
   - Slow requests (>100ms) logged with warning

2. **FPS Counter**
   - TelemetryDashboard shows FPS when streaming active
   - Uses requestAnimationFrame for accurate frame timing

3. **CI Performance Tests**
   - Benchmarks run on every push/PR
   - Reports EMA filter and Hamming distance performance

### Evidence Links
- All edits returned "successfully edited" status
- Python syntax validation passed for all modified files