Plan: SRS Remaining-Work Analysis & Documentation
Finding (current state vs. SRS)
The July 17–22 docs are stale. The HEAD commit (7dbd812) plus the uncommitted working tree already closed most of the original 15-item roadmap. Evidence gathered:

Effectively DONE (incl. uncommitted, per your choice):

P0-1 JWT ≤1h + refresh (auth.py, routes/auth.py; uncommitted adds iat/jti)
P0-2 TLS 1.3 (nginx/nginx.conf:36,65; nginx/generate-certs.sh untracked)
P0-3 EMA pipeline wiring (uncommitted telemetry.py + signal.py — raw+filtered persisted, alarms on filtered)
P0-4 Plate import/export (routes/plates.py, MicroplateEditor.tsx)
P0-5 FHIR OperationOutcome (fhir.py, fhir_validator.py)
P0-6 FHIR Bundle transaction (uncommitted fhir.py all-or-nothing)
P1-8 8/10-base barcodes (barcode.py:172-251, 004-seed-barcodes.sql)
P1-10 Per-channel EMA α (signal.py DEFAULT_ALPHAS/LOINC_TO_CHANNEL)
P2-14 Simulation state persistence (pulse.py:505 _persist_state, models.Simulation)
P2-15 WebSocket JWT auth (telemetry.py, useWebSocket.ts)
Still OPEN:

Item	SRS	Status
P1-9 Performance instrumentation	NFR-P1–P6	NOT DONE — no FPS counter, no response-time middleware, no locustfile.py (greps returned nothing)
P2-11 Auditory alarm	FR-3.1.5	NOT DONE — no Web Audio beep
P2-12 Batch coordinate input	FR-3.2.4	NOT DONE — drag-select only, no text-input modal
P2-13 DB client cert auth	NFR-S5	PARTIAL — DB_SSLMODE=verify-full in compose, but no client-cert generation/verification path confirmed
NFR-M3 Alembic	NFR-M3	PARTIAL — 0001_initial_schema.py exists, but docker-compose.yml:17 still mounts raw SQL to docker-entrypoint-initdb.d (divergence risk)
NFR-R3/R4	NFR-R3/4	PARTIAL — pool exists, no reconnect backoff; WS reconnect lacks message replay
NFR-U1/U2/U3	NFR-U	PARTIAL — 3-click ack (SRS ≤2); keyboard nav lacks focus; no responsive breakpoints
Test coverage	IQ/OQ/PQ	OQ-13/14/15 partially in uncommitted test_api_auth.py; IQ-1/IQ-5 untracked; PQ-5 benchmark + locustfile (PQ-1/2/6) NOT DONE
Hygiene	—	Uncommitted P0-3/P0-6/external-API changes need commit + CI run (test_p0_compliance.py needs PostgreSQL biosync_test)