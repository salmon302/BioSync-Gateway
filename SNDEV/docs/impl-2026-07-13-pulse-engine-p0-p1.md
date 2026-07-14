Title: pulse-engine-p0-p1-integration
Date: 2026-07-13T00:00:00Z
Author: Seth Nenninger (DeepSeek V4 Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc — Pulse Engine full integration (P0 + P1 items)
Summary: Implement P0 (ProcessPoolExecutor, GPB serialization, DB persistence, triggers) and P1 (API endpoints, metric names, patients table, init_engines) for Pulse Engine compliance.

## Task Reference
Gap analysis identified 5 P0 critical items and 6 P1 high-priority items remaining for full Pulse Engine integration.

## Specification Summary
Wire async delegation, implement GPB-compatible serialization, add DB persistence, add missing triggers and endpoints, register engine, create patients table.

## Implementation Notes
- Files changed: pulse.py, simulations.py, engine/__init__.py, database schema
- Verification: pytest, import test, API manual check
