Title: pulse-engine-p2-completion
Date: 2026-07-13T00:00:00Z
Author: Seth Nenninger (DeepSeek V4 Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc — Pulse Engine P2 (medium priority) completion
Summary: Metrics export endpoint, 90-day retention purge, state diffing, DB persistence tests, async delegation timing test, append-only + hash chain tests.

## Task Reference
Gap analysis identified 8 P2 items remaining for full Pulse Engine integration.

## Specification Summary
Add export/purge/diff endpoints, write verification tests for DB persistence, async delegation, triggers, and hash chain.

## Implementation Notes
- Files changed: simulations.py (export/purge/diff endpoints), pulse.py (diffing logic), new test files
- Verification: pytest
