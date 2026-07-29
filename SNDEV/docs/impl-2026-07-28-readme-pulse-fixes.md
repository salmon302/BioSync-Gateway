Title: README Pulse fixes documentation update
Date: 2026-07-28T23:30:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: REMAINING_WORK_v1.1 R1 — document Pulse SIGSEGV fix + secondary defects in README
Summary: Reflect the v1.1 R1 Pulse reliability fixes in README (status table, trade-off #6, new subsection).

# 1. Task Reference
User request: "Update the readme, with description of the pulse fixes."
Source logs: `SNDEV/docs/impl-2026-07-28-pulse-segfault-fix.md`,
`SNDEV/docs/impl-2026-07-28-pulse-segfault-diag-plan.md`.

# 2. Specification Summary
Document the resolved Pulse engine defects and the 19/19 qualification result in the
project README so external readers understand the engine now runs and is qualified.

# 3. Implementation Notes
Files changed (tracked, no secrets):
- `README.md`
  - Status table: Pulse Engine integration row now reads "Real `PyPulse` built, runs, and
    qualified (19/19 IQ/OQ/PQ)" (was "build pending CI (gated)").
  - Engineering Trade-off #6 cost note: removed the "gated on building PyPulse.so" clause;
    notes the live binary is now built/qualified.
  - New subsection "Pulse Engine Reliability Fixes (v1.1 R1)" describing R-FIX-E (CWD/chdir
    shim fix for the SIGSEGV) and the six secondary production defects (A–F) plus the
    19/19 validation result, with references to the two source logs.

No code, config, or API changes. Verification: README rendered and reviewed manually.

(No secrets/tokens recorded.)
