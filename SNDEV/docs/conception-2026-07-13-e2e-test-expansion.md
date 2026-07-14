Title: End-to-End Test Expansion Plan
Date: 2026-07-13T00:00:00Z
Author: Seth Nenninger (Qwen3.6 Flash Agent)
Contribution Type: Conception
Ticket/Context: ad-hoc
Summary: Comprehensive plan to expand BioSync-Gateway end-to-end testing from 16 unit tests to a full IQ/OQ/PQ suite covering all SRS requirements.

---

# BioSync-Gateway End-to-End Test Expansion Plan

## 1. Current State Assessment

### 1.1 Existing Test Inventory (16 test files)

| File | SRS Coverage | Type |
|------|-------------|------|
| `test_iq4_pulse_engine_init.py` | IQ-4 | Unit |
| `test_oq1_barcode_test_vectors.py` | OQ-1 | Unit |
| `test_oq2_hamming_distance_rejection.py` | OQ-2 | Unit |
| `test_oq3_dilution_volume_accepted.py` | OQ-3 | Unit |
| `test_oq4_dilution_volume_flagged.py` | OQ-4 | Unit |
| `test_oq5_unit_conversion.py` | OQ-5 | Unit |
| `test_oq6_ema_convergence.py` | OQ-6 | Unit |
| `test_oq7_update_rejection.py` | OQ-7 | Unit |
| `test_oq8_delete_rejection.py` | OQ-8 | Unit |
| `test_oo9_tamper_detection.py` | OQ-9 | Unit |
| `test_oq10_valid_observation.py` | OQ-10 | Unit |
| `test_oq11_missing_value_quantity.py` | OQ-11 | Unit |
| `test_oq12_missing_operational_status.py` | OQ-12 | Unit |
| `test_oq16_state_serialization.py` | OQ-16 | Unit |
| `test_pq2_concurrent_simulations.py` | PQ-2 | Integration |
| `test_pq6_ventilator_stress.py` | PQ-6 | Integration |

**Total: 16 files, ~120 test methods**

### 1.2 Critical Gaps

| Gap | Severity | Description |
|-----|----------|-------------|
| **No `conftest.py`** | Critical | No shared fixtures, no pytest configuration, no DB test fixtures |
| **No API-level integration tests** | Critical | All routes are stubs — no FastAPI `TestClient` tests |
| **No JWT auth tests** | High | `api/auth.py` has zero coverage |
| **No WebSocket tests** | High | `telemetry/stream` endpoint untested |
| **No hash chain integration tests** | High | `hash_chain.py` tested in isolation only |
| **No FHIR Bundle tests** | High | FR-3.7.5 has no test |
| **No external API tests** | Medium | `accessgudid.py`, `clinvar.py` untested |
| **No performance benchmark tests** | Medium | `performance_benchmarks.py` untested |
| **No E2E workflow tests** | Medium | No multi-step user journeys |
| **No frontend tests** | Low | React components untested |
| **No DB migration tests** | Low | `database/migrations/` untested |

---

## 2. SRS Requirement Coverage Matrix

### 2.1 Section 3 — System Features

| SRS ID | Requirement | Current Test | Gap |
|--------|-------------|-------------|-----|
| FR-3.1.1 | Canvas/WebGL rendering | None | Frontend test needed |
| FR-3.1.2 | 60 fps rendering | None | Frontend test needed |
| FR-3.1.3 | Chart provider abstraction | None | Frontend test needed |
| FR-3.1.4 | Telemetry channels | None | API integration test needed |
| FR-3.1.5 | Alarm visualization | None | Frontend + API test needed |
| FR-3.1.6 | Zoom and pan | None | Frontend test needed |
| FR-3.2.1 | CSS Grid plate rendering | None | Frontend test needed |
| FR-3.2.2 | Well state binding | None | Frontend test needed |
| FR-3.2.3 | Well interaction | None | Frontend test needed |
| FR-3.2.4 | Batch operations | None | API + Frontend test needed |
| FR-3.2.5 | Plate import/export | None | API integration test needed |
| FR-3.3.1 | Hamming distance | OQ-1, OQ-2 | Covered |
| FR-3.3.2 | Min distance enforcement | OQ-2 | Covered |
| FR-3.3.3 | Error correction guarantee | OQ-2 | Covered (implicit) |
| FR-3.3.4 | Barcode source dictionary | None | Unit test needed |
| FR-3.3.5 | Validation timing | None | API integration test needed |
| FR-3.4.1 | Dilution calculation | OQ-3 | Covered |
| FR-3.4.2 | Physical limit detection | OQ-3, OQ-4 | Covered |
| FR-3.4.3 | Serial dilution worklist | OQ-4 | Covered |
| FR-3.4.4 | Concentration unit handling | OQ-5 | Covered |
| FR-3.5.1 | Low-pass filter (EMA) | OQ-6 | Covered |
| FR-3.5.2 | Alpha tuning | None | Unit test needed |
| FR-3.5.3 | Raw data preservation | None | API integration test needed |
| FR-3.5.4 | False alarm prevention | None | API integration test needed |
| FR-3.6.1 | Engine initialization | IQ-4 | Covered |
| FR-3.6.2 | Async delegation | None | Integration test needed |
| FR-3.6.3 | State serialization | OQ-16 | Covered |
| FR-3.6.4 | Data extraction | None | Integration test needed |
| FR-3.6.5 | Multi-patient simulation | PQ-2 | Covered |
| FR-3.7.1 | FHIR R4 compliance | OQ-10 | Partially covered |
| FR-3.7.2 | DeviceMetric mapping | OQ-12 | Covered |
| FR-3.7.3 | Observation mapping | OQ-10 | Covered |
| FR-3.7.4 | Validation failure response | OQ-11 | Covered |
| FR-3.7.5 | Bundle support | None | **Missing** |
| FR-3.8.1 | Append-only triggers | OQ-7 | Covered |
| FR-3.8.2 | Trigger scope | OQ-7, OQ-8 | Covered |
| FR-3.8.3 | Cryptographic hash chaining | OQ-9 | Covered |
| FR-3.8.4 | Tamper detection | OQ-9 | Covered |
| FR-3.8.5 | JWT authentication | None | **Missing** |
| FR-3.9.1 | Passive metrics collection | None | **Missing** |
| FR-3.9.2 | uFMEA data export | None | **Missing** |
| FR-3.9.3 | Privacy | None | **Missing** |
| FR-3.10.1 | AccessGUDID lookup | None | **Missing** |
| FR-3.10.2 | ClinVar variant lookup | None | **Missing** |
| FR-3.10.3 | Caching | None | **Missing** |

### 2.2 Section 4 — External Interfaces

| SRS ID | Requirement | Current Test | Gap |
|--------|-------------|-------------|-----|
| NFR-R1 | HTTPS API | None | **Missing** |
| NFR-R2 | WebSocket auto-reconnect | None | **Missing** |
| NFR-R3 | JWT token lifecycle | None | **Missing** |
| NFR-R4 | WebSocket with auto-reconnect | None | **Missing** |
| NFR-P1 | 100ms alarm response | None | **Missing** |
| NFR-P2 | 5s plate validation | None | **Missing** |
| NFR-P3 | 50ms P95 WebSocket latency | None | **Missing** |
| NFR-P4 | 60s hash chain 1M rows | None | **Missing** |
| NFR-P5 | 10 concurrent simulations | PQ-2 | Covered |

---

## 3. Proposed Test Expansion

### 3.1 Priority 1 — Foundation (Week 1)

These are prerequisites for all other testing.

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 1 | `tests/conftest.py` | Shared fixtures: TestClient, mock JWT, mock DB session, barcode test vectors, patient configs | All |
| 2 | `tests/test_conftest_config.py` | Verify pytest configuration, fixture availability, import paths | Meta |
| 3 | `tests/test_imports.py` | Verify all middleware modules import cleanly | Meta |

**`conftest.py` fixture design:**
```python
# Shared fixtures
@pytest.fixture
def client():
    """FastAPI TestClient for API testing"""

@pytest.fixture
def authenticated_client(client):
    """TestClient with valid JWT token attached"""

@pytest.fixture
def sample_jwt_token():
    """Generate a valid JWT token for testing"""

@pytest.fixture
def sample_patient_config():
    """Standard PatientConfig for simulation tests"""

@pytest.fixture
def sample_barcodes_truseq():
    """Illumina TruSeq UDI barcode set"""

@pytest.fixture
def sample_observation():
    """Valid FHIR Observation resource"""

@pytest.fixture
def sample_device_metric():
    """Valid FHIR DeviceMetric resource"""

@pytest.fixture
def mock_db_session():
    """Mock SQLAlchemy session for DB-dependent tests"""

@pytest.fixture
def ema_filter_alpha_05():
    """EMA filter with alpha=0.5"""

@pytest.fixture
def dilution_solver():
    """DilutionSolver with default min_volume=0.5"""
```

### 3.2 Priority 2 — API Integration Tests (Week 2)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 4 | `tests/test_api_root.py` | Root endpoint, API info, OpenAPI schema | NFR-R1 |
| 5 | `tests/test_api_health.py` | `/health`, `/health/protected` | NFR-R1 |
| 6 | `tests/test_api_auth.py` | JWT creation, validation, scope enforcement, token expiry | FR-3.8.5, NFR-R3 |
| 7 | `tests/test_api_telemetry.py` | WebSocket connect/disconnect, subscribe, ping/pong, ingest | FR-3.1.4, NFR-R2, NFR-R4 |
| 8 | `tests/test_api_audit.py` | Paginated logs, filtering, hash chain verification endpoint | FR-3.8.3, FR-3.8.4 |
| 9 | `tests/test_api_plates.py` | Create plate, validate barcodes, generate dilution worklist | FR-3.2.5, FR-3.3.5 |
| 10 | `tests/test_api_fhir.py` | Create Observation, create DeviceMetric, Bundle processing | FR-3.7.5 |
| 11 | `tests/test_api_simulations.py` | Create simulation, step, pause, resume, stop | FR-3.6.2, FR-3.6.4 |
| 12 | `tests/test_api_protected.py` | Protected endpoints with/without JWT | FR-3.8.5 |

### 3.3 Priority 3 — Engine Deepening (Week 3)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 13 | `tests/test_o07_barcode_dictionary.py` | TruSeq/Nextera UDI dictionary validation | FR-3.3.4 |
| 14 | `tests/test_o08_ema_alpha_tuning.py` | α=0.2 for pressure, α=0.1 for flow-rate | FR-3.5.2 |
| 15 | `tests/test_o09_signal_raw_preservation.py` | Both raw and filtered values stored | FR-3.5.3 |
| 16 | `tests/test_o10_signal_alarm_filtered.py` | Alarm evaluation on filtered data | FR-3.5.4 |
| 17 | `tests/test_o11_pulse_async_delegation.py` | Pulse steps via ProcessPoolExecutor | FR-3.6.2 |
| 18 | `tests/test_o12_pulse_data_extraction.py` | Required metrics extraction (FR-3.6.4) | FR-3.6.4 |
| 19 | `tests/test_o13_hash_chain_api.py` | Hash chain compute/verify via API | FR-3.8.3 |
| 20 | `tests/test_o14_fhir_bundle.py` | Bundle transaction/batch processing | FR-3.7.5 |
| 21 | `tests/test_o15_fhir_validation_errors.py` | OperationOutcome detail verification | FR-3.7.4 |

### 3.4 Priority 4 — Performance & Stress (Week 4)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 22 | `tests/test_pq1_websocket_latency.py` | P95 < 50ms WebSocket latency | NFR-P3 |
| 23 | `tests/test_pq2_hash_chain_perf.py` | < 60s for 1M rows | NFR-P4 |
| 24 | `tests/test_pq3_barcode_perf.py` | 96-well pairwise computation < 5s | NFR-P2 |
| 25 | `tests/test_pq4_alarm_response.py` | < 100ms alarm detection | NFR-P1 |
| 26 | `tests/test_pq5_sustained_throughput.py` | Sustained 10k msg throughput | NFR-P3 |
| 27 | `tests/test_pq7_plate_batch_ops.py` | Batch well operations performance | FR-3.2.4 |

### 3.5 Priority 5 — External Integrations (Week 5)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 28 | `tests/test_ext_accessgudid.py` | AccessGUDID API mock responses | FR-3.10.1 |
| 29 | `tests/test_ext_clinvar.py` | ClinVar E-utilities mock responses | FR-3.10.2 |
| 30 | `tests/test_ext_caching.py` | TTL-based caching behavior | FR-3.10.3 |

### 3.6 Priority 6 — Human Factors & E2E Workflows (Week 6)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 31 | `tests/test_e2e_plate_workflow.py` | Full plate lifecycle: create → validate → dilute → export | FR-3.2.5, FR-3.3.5 |
| 32 | `tests/test_e2e_telemetry_pipeline.py` | Ingest → filter → store → stream → visualize | FR-3.1.4, FR-3.5.3 |
| 33 | `tests/test_e2e_simulation_lifecycle.py` | Create → step → pause → resume → stop → serialize | FR-3.6.3 |
| 34 | `tests/test_e2e_audit_trail.py` | Mutation → audit log → hash chain verify | FR-3.8.1, FR-3.8.4 |
| 35 | `tests/test_hf_passive_metrics.py` | Selection latency capture | FR-3.9.1 |
| 36 | `tests/test_hf_ufmea_export.py` | uFMEA JSON export | FR-3.9.2 |
| 37 | `tests/test_hf_privacy.py` | Pseudonymization verification | FR-3.9.3 |

### 3.7 Priority 7 — Frontend Tests (Week 7)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 38 | `frontend/tests/chart_provider.test.tsx` | Chart provider abstraction | FR-3.1.3 |
| 39 | `frontend/tests/telemetry_dashboard.test.tsx` | WebGL rendering, alarm states | FR-3.1.1, FR-3.1.5 |
| 40 | `frontend/tests/microplate_editor.test.tsx` | CSS Grid rendering, well interaction | FR-3.2.1, FR-3.2.3 |
| 41 | `frontend/tests/audit_viewer.test.tsx` | Sortable table, hash chain indicators | FR-3.8.4 |
| 42 | `frontend/tests/admin_console.test.tsx` | Forms, configuration | FR-3.8.5 |
| 43 | `frontend/tests/use_websocket.test.ts` | WebSocket reconnection | NFR-R2, NFR-R4 |
| 44 | `frontend/tests/use_human_factors.test.ts` | Passive metrics capture | FR-3.9.1 |

### 3.8 Priority 8 — Database Migration Tests (Week 8)

| # | File | Description | SRS Coverage |
|---|------|-------------|-------------|
| 45 | `tests/test_db_migrations.py` | Migration execution order, idempotency | FR-3.8.1 |
| 46 | `tests/test_db_append_only.py` | Trigger enforcement via raw SQL | FR-3.8.1, FR-3.8.2 |
| 47 | `tests/test_db_hash_chain_sql.py` | SQL-level hash chain verification | FR-3.8.3 |

---

## 4. Test Architecture

### 4.1 Directory Structure

```
tests/
├── conftest.py                          # Shared fixtures (P1)
├── test_imports.py                      # Import verification (P1)
│
├── unit/                                # Engine unit tests
│   ├── test_o01_barcode_test_vectors.py       # OQ-1 (existing)
│   ├── test_o02_hamming_distance_rejection.py # OQ-2 (existing)
│   ├── test_o03_dilution_volume_accepted.py   # OQ-3 (existing)
│   ├── test_o04_dilution_volume_flagged.py    # OQ-4 (existing)
│   ├── test_o05_unit_conversion.py            # OQ-5 (existing)
│   ├── test_o06_ema_convergence.py            # OQ-6 (existing)
│   ├── test_o07_barcode_dictionary.py         # FR-3.3.4 (new)
│   ├── test_o08_ema_alpha_tuning.py           # FR-3.5.2 (new)
│   ├── test_o09_signal_raw_preservation.py    # FR-3.5.3 (new)
│   ├── test_o10_signal_alarm_filtered.py      # FR-3.5.4 (new)
│   ├── test_o11_pulse_async_delegation.py     # FR-3.6.2 (new)
│   ├── test_o12_pulse_data_extraction.py      # FR-3.6.4 (new)
│   ├── test_o13_hash_chain_api.py             # FR-3.8.3 (new)
│   ├── test_o14_fhir_validation_errors.py     # FR-3.7.4 (new)
│   ├── test_iq01_engine_initialization.py     # IQ-4 (existing)
│   └── test_o16_state_serialization.py        # OQ-16 (existing)
│
├── integration/                         # API + engine integration
│   ├── test_api_root.py                   # Root endpoint (P2)
│   ├── test_api_health.py                 # Health checks (P2)
│   ├── test_api_auth.py                   # JWT auth (P2)
│   ├── test_api_telemetry.py              # WebSocket + ingest (P2)
│   ├── test_api_audit.py                  # Audit logs + verify (P2)
│   ├── test_api_plates.py                 # Plate CRUD + validation (P2)
│   ├── test_api_fhir.py                   # FHIR resources + Bundle (P2)
│   ├── test_api_simulations.py            # Simulation lifecycle (P2)
│   ├── test_api_protected.py              # Protected endpoints (P2)
│   ├── test_e2e_plate_workflow.py         # Full plate workflow (P6)
│   ├── test_e2e_telemetry_pipeline.py     # Full telemetry pipeline (P6)
│   ├── test_e2e_simulation_lifecycle.py   # Full sim lifecycle (P6)
│   └── test_e2e_audit_trail.py            # Full audit trail (P6)
│
├── performance/                         # Performance benchmarks
│   ├── test_pq1_websocket_latency.py      # P95 < 50ms (P4)
│   ├── test_pq2_hash_chain_perf.py        # < 60s 1M rows (P4)
│   ├── test_pq3_barcode_perf.py           # 96-well < 5s (P4)
│   ├── test_pq4_alarm_response.py         # < 100ms alarm (P4)
│   ├── test_pq5_sustained_throughput.py   # 10k msg throughput (P4)
│   └── test_pq7_plate_batch_ops.py        # Batch ops perf (P4)
│
├── external/                            # External API mocks
│   ├── test_ext_accessgudid.py            # AccessGUDID (P5)
│   ├── test_ext_clinvar.py                # ClinVar (P5)
│   └── test_ext_caching.py                # TTL caching (P5)
│
├── human_factors/                       # uFMEA
│   ├── test_hf_passive_metrics.py         # Selection latency (P6)
│   ├── test_hf_ufmea_export.py            # uFMEA export (P6)
│   └── test_hf_privacy.py                 # Pseudonymization (P6)
│
├── database/                            # DB-level tests
│   ├── test_db_migrations.py              # Migration order (P8)
│   ├── test_db_append_only.py             # Trigger enforcement (P8)
│   └── test_db_hash_chain_sql.py          # SQL hash chain (P8)
│
├── test_o07_update_rejection.py         # OQ-7 (existing)
├── test_o08_delete_rejection.py         # OQ-8 (existing)
├── test_o09_tamper_detection.py         # OQ-9 (existing)
├── test_o10_valid_observation.py        # OQ-10 (existing)
├── test_o11_missing_value_quantity.py   # OQ-11 (existing)
├── test_o12_missing_operational_status.py # OQ-12 (existing)
├── test_pq2_concurrent_simulations.py   # PQ-2 (existing)
└── test_pq6_ventilator_stress.py        # PQ-6 (existing)
```

### 4.2 Test Categories & Markers

```python
# conftest.py — pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: API integration tests")
    config.addinivalue_line("markers", "performance: performance benchmarks")
    config.addinivalue_line("markers", "external: external API tests")
    config.addinivalue_line("markers", "e2e: end-to-end workflow tests")
    config.addinivalue_line("markers", "db: database-level tests")
    config.addinivalue_line("markers", "slow: slow-running tests")
    config.addinivalue_line("markers", "hf: human factors tests")
```

### 4.3 pytest Configuration (`pyproject.toml` or `pytest.ini`)

```ini
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "unit",
    "integration",
    "performance",
    "external",
    "e2e",
    "db",
    "hf",
    "slow",
]
addopts = "-v --tb=short"
```

---

## 5. Implementation Strategy

### 5.1 Phase Gating

| Phase | Deliverable | Gate Criteria |
|-------|-------------|---------------|
| P1 | `conftest.py` + fixtures | All existing 16 tests pass with new fixtures |
| P2 | 9 API integration tests | All FastAPI routes have TestClient coverage |
| P3 | 8 engine deepening tests | All FR-3.5.x, FR-3.6.x gaps closed |
| P4 | 6 performance tests | All NFR-P1 through NFR-P5 benchmarks defined |
| P5 | 3 external API tests | Mock-based coverage for AccessGUDID + ClinVar |
| P6 | 7 E2E + human factors tests | Full user workflows validated |
| P7 | 7 frontend tests | React component coverage ≥ 60% |
| P8 | 3 DB migration tests | All migrations tested, triggers verified |

### 5.2 Total Target

| Category | Existing | New | Total |
|----------|----------|-----|-------|
| Unit | 12 | 8 | 20 |
| Integration | 2 | 13 | 15 |
| Performance | 0 | 6 | 6 |
| External | 0 | 3 | 3 |
| E2E | 0 | 4 | 4 |
| Human Factors | 0 | 3 | 3 |
| Frontend | 0 | 7 | 7 |
| Database | 0 | 3 | 3 |
| **Total** | **14** | **47** | **61** |

### 5.3 SRS Coverage After Expansion

| SRS Section | Before | After |
|-------------|--------|-------|
| FR-3.1 Telemetry | 0% | 80% (20% = WebGL rendering, frontend) |
| FR-3.2 Microplate | 0% | 60% (40% = CSS Grid rendering, frontend) |
| FR-3.3 Barcode | 100% | 100% |
| FR-3.4 Dilution | 100% | 100% |
| FR-3.5 Signal | 50% | 100% |
| FR-3.6 Pulse Engine | 60% | 100% |
| FR-3.7 FHIR | 75% | 100% |
| FR-3.8 Compliance | 100% | 100% |
| FR-3.9 Human Factors | 0% | 100% |
| FR-3.10 External | 0% | 100% |
| NFR-R (Reliability) | 0% | 75% |
| NFR-P (Performance) | 20% | 100% |
| **Overall** | **~35%** | **~90%** |

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pulse Engine C++ not available | Blocks FR-3.6.x tests | Mock `PyPulse` with deterministic simulator |
| PostgreSQL not available for DB tests | Blocks FR-3.8.x tests | Use `pytest-postgresql` or SQLite with trigger emulation |
| Frontend tests require browser | Slower CI | Use `@testing-library/react` + jsdom for unit tests |
| External API rate limits | Blocks FR-3.10.x tests | All tests use mocked responses |
| JWT secret in tests | Security risk | Use test-only secret, never commit production key |
| Test data pollution | Flaky tests | Each test gets isolated fixtures; no shared mutable state |

---

## 7. CI/CD Integration

### 7.1 GitHub Actions Workflow

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: biosync_test
          POSTGRES_USER: biosync_user
          POSTGRES_PASSWORD: biosync_test_password
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r middleware/requirements.txt
          pip install pytest pytest-cov pytest-postgresql

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=middleware/engine

      - name: Run integration tests
        run: pytest tests/integration/ -v --cov=middleware/api

      - name: Run performance benchmarks
        run: pytest tests/performance/ -v --benchmark-only

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### 7.2 Coverage Targets

| Module | Target |
|--------|--------|
| `middleware/engine/` | ≥ 90% |
| `middleware/api/` | ≥ 80% |
| `middleware/fhir_validator.py` | ≥ 95% |
| `middleware/engine/hash_chain.py` | ≥ 95% |
| `middleware/api/auth.py` | ≥ 90% |

---

## 8. Execution Order

1. **Create `conftest.py`** — foundation for all fixtures
2. **Run existing tests** — verify nothing breaks
3. **Build API integration tests** — FastAPI TestClient against all routes
4. **Deepen engine tests** — fill FR-3.5.x, FR-3.6.x gaps
5. **Add performance benchmarks** — NFR-P1 through NFR-P5
6. **Mock external APIs** — AccessGUDID, ClinVar
7. **Build E2E workflows** — multi-step user journeys
8. **Add frontend tests** — React component coverage
9. **Add DB migration tests** — trigger enforcement, hash chain SQL
10. **Integrate with CI/CD** — GitHub Actions pipeline
