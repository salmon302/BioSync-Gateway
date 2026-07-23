Title: srs-remaining-work-roadmap
Date: 2026-07-17T10:35:00Z
Author: Seth Nenninger (Qwen3.5-Flash Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc — Actionable roadmap for SRS gap closure
Summary: Prioritized development roadmap with effort estimates and dependencies for completing remaining SRS requirements.

---

# BioSync-Gateway — Remaining Work Roadmap

**Date:** 2026-07-17 | **Derived From:** impl-2026-07-17-srs-gap-analysis.md  
**Goal:** Close all P0/P1 gaps to achieve SRS v1.0 compliance and CSV readiness  

---

## Quick Reference

| Priority | Items | Total Effort | Target Completion |
|:---------|:-----:|:------------:|:------------------|
| **P0** (Critical) | 6 | 7 days | 2026-07-26 |
| **P1** (Feature Complete) | 4 | 7.5 days | 2026-08-04 |
| **P2** (Enhancements) | 5 | 6 days | 2026-08-15 |
| **Total** | **15** | **20.5 days** | **~4 weeks** |

---

## Phase 4a — Security Hardening (7 days)

### 🔴 P0-1: JWT Lifetime ≤1 Hour + Refresh Tokens
**SRS Reference:** NFR-S3  
**Effort:** 0.5 days  
**Files to Modify:**
- `middleware/api/auth.py`
- `middleware/api/routes/auth.py` (new)

**Implementation Steps:**
1. Change `JWT_EXPIRATION_HOURS = 1` in `auth.py`
2. Add `/api/auth/refresh` endpoint:
   ```python
   @router.post("/refresh")
   async def refresh_token(refresh_token: str = Depends(...)):
       # Validate refresh token
       # Issue new access token
       # Store refresh token in DB for rotation
   ```
3. Add refresh token rotation logic (invalidate old token on use)
4. Add `OQ-13, OQ-14, OQ-15` tests

**Verification:**
- `OQ-13`: Valid token → HTTP 200
- `OQ-14`: Expired token → HTTP 401 + `WWW-Authenticate: Bearer`
- `OQ-15`: No token → HTTP 401

---

### 🔴 P0-2: TLS 1.3 for All Traffic
**SRS Reference:** NFR-S4  
**Effort:** 2 days  
**Files to Modify:**
- `nginx/nginx.conf`
- `docker-compose.yml`
- `frontend/.env`

**Implementation Steps:**
1. Generate self-signed certs (or use Let's Encrypt for production):
   ```bash
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem
   ```
2. Update `nginx/nginx.conf`:
   ```nginx
   server {
       listen 443 ssl;
       ssl_certificate /etc/nginx/ssl/cert.pem;
       ssl_certificate_key /etc/nginx/ssl/key.pem;
       ssl_protocols TLSv1.3;  # Enforce TLS 1.3
       ssl_ciphers HIGH:!aNULL:!MD5;
   }
   ```
3. Update `docker-compose.yml` to expose HTTPS port (443)
4. Update frontend `VITE_API_URL` to `https://localhost`
5. Add nginx container to `docker-compose.yml`

**Verification:**
- `curl -v https://localhost` → TLS 1.3 handshake
- Frontend connects via WSS (not WS)

---

### 🔴 P0-3: Wire EMA Filter into Telemetry Pipeline
**SRS Reference:** FR-3.5.1, FR-3.5.4  
**Effort:** 1 day  
**Files to Modify:**
- `middleware/engine/signal.py`
- `middleware/api/routes/telemetry.py`
- `frontend/src/components/TelemetryDashboard/TelemetryDashboard.tsx`

**Implementation Steps:**
1. Update `MultiChannelEMAFilter` in `signal.py`:
   ```python
   class MultiChannelEMAFilter:
       def __init__(self):
           self.filters = {
               "pressure": EMAFilter(alpha=0.2),  # SRS FR-3.5.2
               "flow": EMAFilter(alpha=0.1),       # SRS FR-3.5.2
               "heart_rate": EMAFilter(alpha=0.3),
               "spo2": EMAFilter(alpha=0.2),
           }
   ```
2. Modify `POST /api/telemetry/ingest`:
   ```python
   @router.post("/ingest")
   async def ingest_telemetry(data: List[TelemetryPoint]):
       # Apply EMA filter
       filtered = ema_filter.filter_batch([d.value for d in data])
       
       # Store both raw and filtered
       for raw, filt in zip(data, filtered):
           await db.execute("""
               INSERT INTO observations (raw_data, filtered_data, ...)
               VALUES ($1, $2, ...)
           """, raw_json, filtered_json)
       
       # Check alarms on filtered data
       for raw, filt in zip(data, filtered):
           if filt.value > THRESHOLD:  # Use filtered, not raw
               trigger_alarm()
   ```
3. Update `TelemetryDashboard` to check filtered values for alarms

**Verification:**
- `OQ-6`: EMA filter convergence test passes
- Alarms trigger only on sustained violations (not jitter)

---

### 🔴 P0-4: Plate Import/Export File Handlers
**SRS Reference:** FR-3.2.5  
**Effort:** 1 day  
**Files to Modify:**
- `frontend/src/components/MicroplateEditor/PlateActions.tsx`
- `frontend/src/utils/fileSaver.ts` (new)
- `frontend/src/utils/csvParser.ts` (new)

**Implementation Steps:**
1. Create `fileSaver.ts`:
   ```typescript
   export function downloadJSON(data: PlateManifest, filename: string) {
       const blob = new Blob([JSON.stringify(data, null, 2)], {
           type: 'application/json'
       });
       const url = URL.createObjectURL(blob);
       const a = document.createElement('a');
       a.href = url;
       a.download = filename;
       a.click();
   }
   ```
2. Create `csvParser.ts`:
   ```typescript
   export function parseCSV(csv: string): PlateManifest {
       const lines = csv.split('\n').filter(l => l.trim());
       const headers = lines[0].split(',');
       return lines.slice(1).map(line => {
           const values = line.split(',');
           return Object.fromEntries(headers.map((h, i) => [h, values[i]]));
       });
   }
   ```
3. Update `PlateActions.tsx`:
   ```typescript
   const handleExportJSON = () => {
       downloadJSON(plateManifest, `${plateId}_manifest.json`);
   };
   
   const handleImportCSV = async (event: ChangeEvent<HTMLInputElement>) => {
       const file = event.target.files?.[0];
       if (!file) return;
       const text = await file.text();
       const parsed = parseCSV(text);
       setPlateManifest(parsed);
   };
   ```

**Verification:**
- Export produces valid JSON matching SRS §3.2.5
- Import validates against plate format (96/384-well)

---

### 🔴 P0-5: FHIR OperationOutcome Response Format
**SRS Reference:** FR-3.7.4  
**Effort:** 0.5 days  
**Files to Modify:**
- `middleware/fhir_validator.py`
- `middleware/api/routes/fhir.py`

**Implementation Steps:**
1. Update `FHIRValidator.to_operation_outcome()`:
   ```python
   def to_operation_outcome(self) -> Dict:
       return {
           "resourceType": "OperationOutcome",
           "id": str(uuid.uuid4()),
           "issue": [
               {
                   "severity": self.severity,
                   "code": self.code,
                   "details": {
                       "text": self.details
                   },
                   "location": self.location
               }
           ]
       }
   ```
2. Update error responses in `fhir.py`:
   ```python
   from fastapi.responses import JSONResponse
   
   @router.post("/Observation")
   async def create_observation(obs: Dict, validator: FHIRValidator = Depends()):
       is_valid, errors = validator.validate_observation(obs)
       if not is_valid:
           outcome = OperationOutcome(
               issue=[e.to_operation_outcome() for e in errors]
           )
           return JSONResponse(
               status_code=422,
               content=outcome.dict(),
               headers={"Content-Type": "application/fhir+json"}
           )
   ```

**Verification:**
- Validation errors return `Content-Type: application/fhir+json`
- Response matches FHIR OperationOutcome schema

---

### 🔴 P0-6: FHIR Bundle Transaction Processing
**SRS Reference:** FR-3.7.5  
**Effort:** 1.5 days  
**Files to Modify:**
- `middleware/api/routes/fhir.py`
- `middleware/database.py`

**Implementation Steps:**
1. Add `POST /api/fhir/Bundle` endpoint:
   ```python
   @router.post("/Bundle")
   async def process_bundle(
       bundle: Bundle,
       db: Session = Depends(get_db),
       validator: FHIRValidator = Depends()
   ):
       # Begin transaction
       try:
           for entry in bundle.entry:
               # Validate each entry
               if entry.resource.resourceType == "Observation":
                   is_valid, errors = validator.validate_observation(entry.resource.dict())
                   if not is_valid:
                       raise HTTPException(status_code=422, detail=errors)
               
               # Insert into DB
               await insert_fhir_resource(db, entry.resource)
           
           # Commit transaction
           db.commit()
           return {"status": "success", "processed": len(bundle.entry)}
       
       except Exception as e:
           # Rollback on any failure
           db.rollback()
           raise e
   ```
2. Add transaction semantics (all-or-nothing)
3. Add Bundle parsing logic

**Verification:**
- Valid Bundle → HTTP 201 with all entries persisted
- Invalid entry → HTTP 422, no entries persisted

---

## Phase 4b — Feature Completion (7.5 days)

### 🟡 P1-7: Real External API Calls
**SRS Reference:** FR-3.10.1, FR-3.10.2  
**Effort:** 2 days  
**Files to Modify:**
- `middleware/external/accessgudid.py`
- `middleware/external/clinvar.py`

**Implementation Steps:**
1. Update `accessgudid.py`:
   ```python
   import httpx
   
   class AccessGUDIDClient:
       BASE_URL = "https://accessgudid.nlm.nih.gov"
       
       async def get_device(self, device_identifier: str) -> Dict:
           async with httpx.AsyncClient(timeout=30.0) as client:
               response = await client.get(
                   f"{self.BASE_URL}/api/v1/devices/{device_identifier}",
                   headers={"Accept": "application/json"}
               )
               response.raise_for_status()
               return response.json()
   ```
2. Update `clinvar.py`:
   ```python
   class ClinVarClient:
       BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
       
       async def search_variants(self, term: str) -> List[str]:
           # Use esearch
           # Use efetch to get details
           pass
   ```
3. Add rate limiting:
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=fastapi.requests.client_ip)
   
   @router.get("/device")
   @limiter.limit("1/second")
   async def get_device(...):
       ...
   ```
4. Add error handling for API downtime (return cached data with warning)

**Verification:**
- Real API calls succeed for valid identifiers
- Rate limiting prevents abuse
- Graceful degradation on API failure

---

### 🟡 P1-8: 8/10-Base Barcode Sequences
**SRS Reference:** FR-3.3.4  
**Effort:** 1 day  
**Files to Modify:**
- `middleware/engine/barcode.py`
- `database/migrations/004-seed-barcodes.sql`

**Implementation Steps:**
1. Update `barcode.py`:
   ```python
   # Illumina TruSeq 8-base and 10-base UDIs from doc 1000000002694
   TRUSEQ_8BASE = [
       "AGATCGGA", "AGATCGGC", "AGATCGGT", "AGATCGGA",  # Example
       # ... add full set from Illumina doc
   ]
   
   TRUSEQ_10BASE = [
       "AGATCGGAAGAG", "AGATCGGAAGAT",  # Example
       # ... add full set from Illumina doc
   ]
   ```
2. Update `004-seed-barcodes.sql`:
   ```sql
   INSERT INTO barcode_indices (sequence, length, set_name, source)
   VALUES 
       ('AGATCGGA', 8, 'TruSeq', 'Illumina 1000000002694'),
       ('AGATCGGAAGAG', 10, 'TruSeq', 'Illumina 1000000002694'),
       ...;
   ```
3. Update validation to accept 8-base and 10-base sequences

**Verification:**
- `OQ-1`: Hamming distance tests pass for 8/10-base sequences
- Plate validation accepts valid 8/10-base sets

---

### 🟡 P1-9: Performance Instrumentation
**SRS Reference:** NFR-P1–P6  
**Effort:** 3 days  
**Files to Modify:**
- `frontend/src/components/TelemetryDashboard/FPSCounter.tsx` (new)
- `middleware/api/middleware/response_time.py` (new)
- `tests/performance/locustfile.py` (new)

**Implementation Steps:**
1. Add FPS counter overlay:
   ```typescript
   function FPSCounter() {
       const [fps, setFps] = useState(0);
       
       useEffect(() => {
           const interval = setInterval(() => {
               const currentFps = chartRef.current?.getFPS() || 0;
               setFps(currentFps);
           }, 1000);
           return () => clearInterval(interval);
       }, []);
       
       return <div style={{position: 'absolute', top: 10, left: 10}}>
           {fps.toFixed(1)} fps
       </div>;
   }
   ```
2. Add response-time middleware:
   ```python
   class ResponseTimeMiddleware:
       async def __call__(self, scope, receive, send):
           start_time = time.time()
           await self.app(scope, receive, send)
           duration = time.time() - start_time
           logger.info(f"Request {scope['path']} took {duration:.3f}s")
   ```
3. Create Locust load test:
   ```python
   from locust import HttpUser, task, between
   
   class TelemetryUser(HttpUser):
       wait_time = between(1, 5)
       
       @task(3)
       def websocket_telemetry(self):
           # Simulate 100k pts/sec
           pass
       
       @task(1)
       def http_crud(self):
           self.client.post("/api/observations", json={...})
   ```

**Verification:**
- NFR-P1: 100k pts/sec ingestion
- NFR-P2: ≥60 fps sustained
- NFR-P3: ≤200 ms API response (95th %)
- NFR-P4: ≤60 sec hash chain verification (1M rows)
- NFR-P5: ≤50 ms Pulse time-step
- NFR-P6: ≥500 concurrent WebSocket connections

---

### 🟡 P1-10: Per-Channel EMA α Defaults
**SRS Reference:** FR-3.5.2  
**Effort:** 0.5 days  
**Files to Modify:**
- `middleware/engine/signal.py`

**Implementation Steps:**
1. Update `MultiChannelEMAFilter`:
   ```python
   class MultiChannelEMAFilter:
       DEFAULT_ALPHAS = {
           "pressure": 0.2,   # SRS FR-3.5.2
           "flow": 0.1,       # SRS FR-3.5.2
           "heart_rate": 0.3,
           "spo2": 0.2,
       }
       
       def __init__(self, channel: str):
           alpha = self.DEFAULT_ALPHAS.get(channel, 0.5)
           self.filter = EMAFilter(alpha=alpha)
   ```
2. Update telemetry ingest to use per-channel filters

**Verification:**
- Pressure channel uses α=0.2
- Flow channel uses α=0.1
- `OQ-6`: Convergence test passes

---

## Phase 4c — Enhancements (6 days)

### 🟢 P2-11: Auditory Alarm Alerts
**SRS Reference:** FR-3.1.5  
**Effort:** 0.5 days  
**Files to Modify:**
- `frontend/src/components/TelemetryDashboard/AlarmAudio.tsx` (new)

**Implementation Steps:**
1. Add Web Audio API beep:
   ```typescript
   export function playAlarmSound() {
       const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
       const osc = ctx.createOscillator();
       const gain = ctx.createGain();
       
       osc.connect(gain);
       gain.connect(ctx.destination);
       
       osc.frequency.value = 800;  // 800 Hz beep
       gain.gain.value = 0.3;
       
       osc.start();
       setTimeout(() => osc.stop(), 200);  // 200ms beep
   }
   ```
2. Call `playAlarmSound()` when alarm triggers

---

### 🟢 P2-12: Batch Coordinate Input
**SRS Reference:** FR-3.2.4  
**Effort:** 0.5 days  
**Files to Modify:**
- `frontend/src/components/MicroplateEditor/BatchSelector.tsx` (new)

**Implementation Steps:**
1. Add text input modal:
   ```typescript
   function BatchSelectorModal({ onClose, onSelect }) {
       const [input, setInput] = useState("");
       
       const parseInput = () => {
           // Parse "Rows A-D, Cols 1-6"
           const rows = input.match(/[A-H]-?[A-H]?/)?.[0];
           const cols = input.match(/[1-12]-?[1-12]?/)?.[0];
           // Return selected well coordinates
       };
       
       return (
           <dialog open>
               <input value={input} onChange={e => setInput(e.target.value)} />
               <button onClick={parseInput}>Select</button>
           </dialog>
       );
   }
   ```
2. Add "Apply Status" button for batch operations

---

### 🟢 P2-13: DB Client Certificate Auth
**SRS Reference:** NFR-S5  
**Effort:** 2 days  
**Files to Modify:**
- `docker-compose.yml`
- `middleware/database.py`
- `nginx/nginx.conf`

**Implementation Steps:**
1. Generate client certs:
   ```bash
   openssl req -new -x509 -days 365 -nodes \
     -out database/client-cert.pem \
     -keyout database/client-key.pem
   ```
2. Update `docker-compose.yml`:
   ```yaml
   services:
     postgres:
       environment:
         POSTGRES_SSL_MODE: verify-full
         POSTGRES_SSL_CERT: /var/lib/postgresql/client-cert.pem
         POSTGRES_SSL_KEY: /var/lib/postgresql/client-key.pem
   ```
3. Update `database.py`:
   ```python
   engine = create_engine(
       DATABASE_URL,
       connect_args={"sslmode": "verify-full", "sslrootcert": "..."}
   )
   ```

---

### 🟢 P2-14: Simulation State Persistence
**SRS Reference:** FR-3.6.3  
**Effort:** 1 day  
**Files to Modify:**
- `middleware/engine/pulse.py`
- `middleware/models.py`

**Implementation Steps:**
1. Add `simulations` table to schema:
   ```sql
   CREATE TABLE simulations (
       id SERIAL PRIMARY KEY,
       patient_id VARCHAR(255) UNIQUE NOT NULL,
       state JSONB NOT NULL,
       state_hash VARCHAR(64) NOT NULL,
       created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
   );
   ```
2. Update `PulseWorker`:
   ```python
   def pause_simulation(self, patient_id: str):
       state = self.serialize_state()
       await db.execute("""
           INSERT INTO simulations (patient_id, state, state_hash)
           VALUES ($1, $2, $3)
           ON CONFLICT (patient_id) DO UPDATE
           SET state = $2, state_hash = $3, updated_at = CURRENT_TIMESTAMP
       """, patient_id, state_json, state_hash)
   ```
3. Add `resume_simulation` endpoint

---

### 🟢 P2-15: WebSocket JWT Auth
**SRS Reference:** NFR-S2  
**Effort:** 0.5 days  
**Files to Modify:**
- `middleware/api/routes/telemetry.py`

**Implementation Steps:**
1. Add JWT validation in `on_connect`:
   ```python
   @router.websocket("/telemetry")
   async def telemetry_stream(websocket: WebSocket):
       token = websocket.query_params.get("token")
       if not token:
           await websocket.close(code=4001, reason="Missing JWT")
           return
       
       try:
           payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
           await websocket.accept()
           
           async for message in websocket.iter_json():
               await handle_telemetry_message(websocket, message, user=payload)
       except JWTError:
           await websocket.close(code=4002, reason="Invalid JWT")
   ```

---

## Dependencies & Blockers

| Item | Depends On | Blocks |
|:-----|:-----------|:-------|
| P0-2 (TLS) | — | P0-1 (JWT over WSS), P2-15 (WS auth) |
| P0-3 (EMA) | P1-10 (α defaults) | None |
| P0-6 (Bundle) | P0-5 (OperationOutcome) | None |
| P1-7 (External APIs) | — | None |
| P2-13 (DB certs) | P0-2 (TLS) | None |

---

## Success Criteria

### Phase 4a — Security Hardening
- [ ] All JWT tokens expire within 1 hour
- [ ] All traffic uses TLS 1.3
- [ ] WebSocket connections require valid JWT
- [ ] Database requires client certificate auth

### Phase 4b — Feature Completion
- [ ] Plate import/export works for CSV/JSON
- [ ] FHIR validation returns proper OperationOutcome
- [ ] FHIR Bundle transaction processing works
- [ ] Real API calls to AccessGUDID/ClinVar
- [ ] 8/10-base barcode sequences seeded

### Phase 4c — Enhancements
- [ ] Performance metrics instrumented
- [ ] Per-channel EMA α defaults applied
- [ ] Auditory alarm alerts functional
- [ ] Batch coordinate input available
- [ ] Simulation states persisted to DB

---

## Sign-Off

**Roadmap Created:** 2026-07-17T10:35:00Z  
**Author:** Seth Nenninger (Qwen3.5-Flash Agent)  
**Next Review:** After Phase 4a completion  

---

*This roadmap provides actionable steps for closing all SRS gaps. Each item includes file-level implementation details and verification criteria for CSV compliance.*
