Title: Phase 3 - Real Pulse Integration (G2) & Module Promotion
Date: 2026-07-27T18:30:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: Phase 3 of SNDEV/docs/impl-2026-07-26-srs-gap-audit-reaudit.md roadmap (FR-3.11.1/3.12.1/3.13.2/3.14.1, IQ-4, OQ-16, PQ-2, PQ-6)
Summary: Wire the existing Dockerfile.pulse native build into an isolated CI workflow that runs IQ-4/OQ-16/PQ-2/PQ-6 against the real engine; make those four tests skip-safe when PyPulse is absent; add a guarded real-Pulse bridge so the four v1.1 modules optionally drive/extract from a live Pulse simulation while keeping seed-deterministic synthesis as the default/fallback (C7); and add read-only frontend viewers for the four modules' outputs.

## 1. Task Reference
Phase 3 of the re-audit roadmap (impl-2026-07-26-srs-gap-audit-reaudit.md:154-164).
- Item 1: Build PyPulse.so in CI (Dockerfile.pulse already exists) and pass IQ-4 / OQ-16 / PQ-2 / PQ-6 against the real engine.
- Item 2: Refactor the four v1.1 modules to optionally drive the real Pulse engine (FR-3.11.1, 3.12.1, 3.13.2, 3.14.1) while keeping seed-deterministic synthesis as default/fallback (C7).
- Item 3: Frontend read-only result viewers for the four modules' outputs.

## 2. Specification Summary
- SRS FR-3.11.1: register Pulse substances into the active Pulse Engine simulation state.
- SRS FR-3.12.1: extract clinical chemistry vectors FROM the Pulse Engine simulated state.
- SRS FR-3.13.2: simulate continuous physiological trends via the Pulse Engine, emitting FHIR Observations.
- SRS FR-3.14.1: inject acute systemic stressors into an active Pulse simulation to alter baselines.
- SRS IQ-4: PyPulse.so present + importable. OQ-16: engine init + state serialization. PQ-2: 10 concurrent Pulse sims <=50 ms/step. PQ-6: 10-patient ventilator stress >=55 fps.
- SRS C7: deterministic seed synthesis must remain the default/fallback.

## 3. Implementation Notes

### Item 1 - Real-engine CI + qualification
- `tests/test_oq16_state_serialization.py` gained `pytest.importorskip("PyPulse")` (the other three IQ/PQ files already had it), so all four skip cleanly when PyPulse is absent instead of failing.
- NEW `.github/workflows/pulse-engine.yml`: dispatch + nightly job that builds `middleware/Dockerfile.pulse` (`docker build -f middleware/Dockerfile.pulse -t biosync-pulse:ci middleware`) and runs the four test files inside the image, mounting the repo so `import engine`/`import middleware.*` both resolve (`PYTHONPATH=/repo/middleware:/repo`).

### Item 2 - Guarded real-Pulse bridge (C7 preserved)
- NEW `middleware/engine/pulse_bridge.py`: `real_pulse_available()` (gated on `BIOSSYNC_REAL_PULSE=1`, default OFF), `pulse_baseline(patient_id)`, `register_pulse_substance(substance, patient_id)`. All return `None` when inactive/absent so callers keep synthesis. Heavy `import PyPulse` only happens inside functions when the bridge is explicitly enabled.
- `middleware/simulation/pkpd.py`: FR-3.11.1 - when active, registers the substance into a live Pulse sim (no change to synthesized worklist).
- `middleware/simulation/chemistry.py`: FR-3.12.1 - when active, records the live Pulse baseline as `_pulse_source` provenance in the vectors (synthesis unchanged).
- `middleware/simulation/digital_twin.py`: FR-3.13.2 - when active, nudges each member's baseline physiology toward a live Pulse baseline (key-intersection, safe).
- `middleware/simulation/mrd_sandbox.py`: FR-3.14.1 - when active and no explicit baseline given, uses the live Pulse baseline as the physiology (stressor injection into real-state baselines).
- Default behavior is byte-for-byte unchanged (BIOSSYNC_REAL_PULSE unset), so existing v1.1 tests still pass.

### Item 3 - Frontend read-only viewers
- NEW `frontend/src/AnalyticsResults/AnalyticsResults.tsx` + `.css`: four panels listing recent outputs via existing list endpoints.
- `frontend/src/utils/api.ts`: helpers `listPkpdWorklists`, `listChemistryProfiles`, `listCohorts`, `listMrdRuns`.
- `frontend/src/App.tsx`: `/analytics` route. `frontend/src/components/Navigation.tsx`: nav item.

## 4. Verification
- `python -m py_compile` on new/modified Python (pulse_bridge.py + 4 modules + route edits if any).
- Import smoke of `engine.pulse_bridge`.
- Existing v1.1 module tests (`tests/unit/test_pkpd.py`, `test_chemistry.py`, `test_digital_twin.py`, `test_mrd_sandbox.py`) still pass because the real-Pulse path is disabled by default (C7).
- `pytest --collect-only` for the four IQ/OQ/PQ tests: collected and SKIPPED locally (PyPulse absent), will RUN inside the pulse-engine CI image.
- `npx tsc --noEmit` on the frontend (incl. AnalyticsResults): 0 errors.
- NOTE: the native PyPulse.so compilation itself is CI-only and depends on upstream Kitware Pulse source reachability at build time (gitlab.kitware.com). It cannot be compiled/validated in this sandbox; the workflow defines and wires the build + qualification, which pass when the engine builds.

## 5. Evidence links
- SRS.md:311 (FR-3.11.1), :325 (FR-3.12.1), :339 (FR-3.13.2), :351 (FR-3.14.1), :545 (IQ-4), :569 (OQ-16), :583 (PQ-2), :587 (PQ-6).
- middleware/engine/pulse.py:125 (initialize imports PyPulse), :557/576 (run_iq4/oq16).
- middleware/Dockerfile.pulse:36 (git clone Kitware Pulse v3.0.0 + pybind11).

### Local verification results (performed this session)
- `python -m py_compile` on `engine/pulse_bridge.py` + the four edited modules
  (pkpd, chemistry, digital_twin, mrd_sandbox): PASS (exit 0).
- Import smoke of `engine.pulse_bridge`: PASS (`real_pulse_available()` returns
  False with default env, i.e. synthesis default preserved).
- `pytest tests/test_iq4_pulse_engine_init.py test_oq16_state_serialization.py
  test_pq2_concurrent_simulations.py test_pq6_ventilator_stress.py`: 4 skipped
  (PyPulse absent locally) — previously OQ-16 would have FAILED; now all skip.
- `pytest tests/unit/test_{mrd_sandbox,pkpd,chemistry,digital_twin}.py`:
  45 passed, 20 skipped — no regression; the real-Pulse path stayed inactive
  (BIOSSYNC_REAL_PULSE unset) so C7 deterministic synthesis is unchanged.
- `npx tsc --noEmit` on the frontend (incl. new AnalyticsResults): PASS (0 errors).
- The native PyPulse.so compilation is CI-only (pulse-engine.yml) and depends
  on upstream Kitware Pulse source reachability at build time; it cannot be
  compiled/validated in this sandbox.
