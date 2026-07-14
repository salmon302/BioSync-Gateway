Title: frontend-test-suite
Date: 2026-07-13T00:00:00Z
Author: Seth Nenninger (DeepSeek V4 Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc — Priority 7 frontend tests from e2e-test-expansion conception
Summary: Implement all 7 Priority 7 frontend tests (chart provider, telemetry dashboard, microplate editor, audit viewer, admin console, useWebSocket, useHumanFactors).

## Task Reference
See SNDEV/docs/conception-2026-07-13-e2e-test-expansion.md — Priority 7 (Week 7) frontend tests.

## Specification Summary
7 React component and hook tests covering: chart provider abstraction, WebGL rendering, alarm states, CSS Grid plate rendering, well interaction, sortable audit table, hash chain indicators, admin forms, WebSocket reconnection, and passive metrics capture.

## Implementation Notes
- Tools: Vitest + @testing-library/react + jsdom
- Files created: 9 (vitest config, setup, 7 test files)
- Verification: `npx vitest run` — PASS/FAIL TBD
