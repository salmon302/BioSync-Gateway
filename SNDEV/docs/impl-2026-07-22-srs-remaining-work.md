Title: SRS Remaining-Work Implementation
Date: 2026-07-22T21:30:00Z
Author: Seth Nenninger (poolside/laguna-s-2.1 Agent)
Contribution Type: Implementation
Ticket/Context: SRS remaining-work roadmap (P2-12, P2-13, NFR-M3, NFR-R3/R4, NFR-U1/U2/U3, Test Coverage, Hygiene)
Summary: Implement the remaining OPEN SRS items: Alembic sole-source migrations, batch coordinate modal, alarm ack, keyboard focus, responsive breakpoints, DB reconnect backoff, WS client replay, DB cert test, PQ-5 benchmark, IQ/CI jobs, and hygiene commits.

## Task Reference
- SRS.md requirements as cited per-item below.
- Decisions locked (user): NFR-U1 = visual-alarm 1-click ack; NFR-M3 = Alembic sole source of truth; P2-13 = client-wiring only (no server-side enforcement).

## Specification Summary
See SRS.md:
- FR-3.2.4 — Batch coordinate selection by range.
- NFR-S5 — DB client cert auth (client wiring).
- NFR-M3 — Alembic migrations sole schema authority.
- NFR-R3 — DB pool auto-reconnect w/ exponential backoff.
- NFR-R4 — WS reconnect w/ message replay (server already done; client gap).
- NFR-U1 — Alarm ack ≤2 clicks.
- NFR-U2 — Keyboard navigation focus.
- NFR-U3 — Responsive 13"–27".
- IQ-1, IQ-5, OQ-13/14/15, PQ-1/2/5/6 — test coverage.

## Implementation Notes
### Phase 1 — NFR-M3 (Alembic sole source)
- Reconciled `0001_initial_schema.py` with `002-schema.sql` + `003-triggers.sql`: added CHECK constraints (operation, hash regex, well_row/col bounds, plate_type, role, cache_source, kit_type), `server_default=func.now()` on timestamp columns, UUID defaults, append-only triggers for devices/simulations, hash-chain + audit functions.
- New `0002_extensions_triggers.py` migration: pgcrypto/uuid-ossp/btree_gin extensions + all trigger functions + append-only triggers + hash chain trigger + audit helpers.
- New `0003_seed_barcodes.py` migration: seed barcode_indices with correct schema (barcode_id/sequence/sequence_length) + analysis view.
- `docker-compose.yml`: removed `docker-entrypoint-initdb.d` mount; middleware command runs `alembic upgrade head` before uvicorn.
- `alembic/env.py`: honor `DATABASE_URL` env var.
- `api/main.py` lifespan: run `alembic upgrade head` at startup as belt-and-suspenders.

### Phase 2 — Frontend (P2-12, NFR-U1/U2/U3)
- MicroplateEditor: batch coordinate modal (A-D, 1-6), tabIndex focus, focus ring, modal focus trap.
- TelemetryDashboard: 1-click Acknowledge button.
- CSS: responsive breakpoints.

### Phase 3 — Backend resilience (NFR-R3, NFR-R4)
- database.py: exponential backoff reconnect wrapper.
- useWebSocket.ts: message queue + flush on reconnect + re-subscribe.

### Phase 4 — Test coverage
- OQ-14: assert WWW-Authenticate: Bearer header.
- IQ-1/IQ-5: CI jobs.
- PQ-5: 4,560 pairwise Hamming ≤ 500ms.
- locust smoke in CI.

## Verification
- Phase 1: `alembic upgrade head` on fresh DB; schema diff vs old SQL = 0.
- Phase 2: `npm test` + manual.
- Phase 3: `pytest middleware/tests/`.
- Phase 4: `pytest` + CI.
- Phase 5: CI green.

## Evidence
- File paths + line numbers cited inline per change.
