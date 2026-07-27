Title: R1 - Build & deploy real PyPulse (Pulse) binary via multi-stage Dockerfile.pulse
Date: 2026-07-27T18:30:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: R1 from REMAINING_WORK_v1.1.md (SRS FR-3.6.1-3.6.5, FR-3.11-3.14; Blocker fidelity)
Summary: Corrected Dockerfile.pulse (real tag, Python ABI match, Pulse_PYTHON_API) and rewrote engine/pulse.py against the real Pulse (PyPulse) `Pulse` binding API so the deployed image runs authentic physiology.

---

## 1. Task Reference
REMAINING_WORK_v1.1.md R1: "Build & deploy real `PyPulse` binary (multi-stage `Dockerfile.pulse`); remove synthetic fallback dependence." Acceptance: `import PyPulse` succeeds in the runtime image; IQ-4 / OQ-16 / PQ-2 / PQ-6 pass against the real engine.

## 2. Specification Summary
SRS §3.6 requires the Kitware Pulse Physiology Engine for high-fidelity simulation. The prior code used an *imagined* PyPulse API (`engine.initialize(age=...)`, `engine.step()`, `engine.serialize_to_gpb()`, `import PyPulse`) that would never work against the real compiled engine, and Dockerfile.pulse was unbuildable (wrong tag, Python ABI mismatch, wrong CMake flag, wrong Boost package names).

## 3. Implementation Notes

### 3.1 Root-cause findings (verified against Kitware source, tag REL_4_3_2)
- Real module name is **`Pulse`** (Kitware's official image sets `PYTHONPATH /pulse/bin:/pulse/python`; the wrapper package is `Pulse`). The repo's `import PyPulse` was wrong.
- CMake flag is **`Pulse_PYTHON_API=ON`** (default on); there is no `PULSE_PYTHON_BINDINGS`. Java/C# APIs can be disabled to cut build time.
- Builder/runtime Python **ABI must match** or the compiled `.so` cannot import. Original used Ubuntu Py3.10 builder vs Py3.11 runtime.
- Latest stable tag is **`REL_4_3_2`** (the old `v3.0.0` does not exist).
- Pulse's `DataRequestManager.pull_data()` returns a **pandas DataFrame** => `pandas` is now a runtime dependency.

### 3.2 Files changed
- `middleware/Dockerfile.pulse` (rewritten): multi-stage; builder `python:3.11-bullseye` compiling `REL_4_3_2` with `Pulse_PYTHON_API=ON`, `-DPulse_JAVA_API=OFF -DPulse_CSHARP_API=OFF`; runtime `python:3.11-slim` copying `/pulse`, setting `PYTHONPATH`/`LD_LIBRARY_PATH`, `ENV BIOSSYNC_REAL_PULSE=1`, and an IQ-4 build gate (`import Pulse; from Pulse import Engine`).
- `middleware/engine/pulse.py` (rewritten engine layer): real API — `Pulse.Engine()`, `initialize_engine(SEPatientConfiguration)` with CDM `SEPatient` (age/weight/height/sex via `TimeUnit`/`MassUnit`/`LengthUnit`/`eSex`), `advance_time_s(TIME_STEP)`, `get_data_request_manager()` + `SEDataRequest` registration + `pull_data()` DataFrame extraction, and `get_state(SEState)` -> GPB `SerializeToString()` for FR-3.6.3. Still fails *closed* (no mock) when the engine is absent (SRS C1). SimulationManager/DB persistence preserved.
- `middleware/engine/pulse_bridge.py`: `import PyPulse` -> `import Pulse`; graceful degradation to seed-synthesis unchanged (C7).
- `middleware/requirements.txt`: added `pandas==2.2.2` (Pulse `pull_data()`).
- `docker-compose.yml`: added `BIOSSYNC_REAL_PULSE=1` to the middleware service (already supports `MIDDLEWARE_DOCKERFILE=Dockerfile.pulse`).
- 8 test modules: `pytest.importorskip("PyPulse")` -> `importorskip("Pulse")` so IQ-4/OQ-16/PQ-2/PQ-6 actually *run* against the engine instead of skipping.

### 3.3 Verification performed here (daemon-down environment)
- `python -m py_compile` on `engine/pulse.py` and `engine/pulse_bridge.py`: PASS (syntax/import-structure valid).
- grep confirms zero functional `import PyPulse` / `PyPulse.Engine()` references remain (one docstring updated).
- Docker daemon is NOT running in this environment (`docker info` -> daemon not running), so the image could **not** be compiled here. The build was authored to be reproducible in a provisioned Linux CI runner (>=8 GiB RAM) via the new `SNDEV/scripts/build_pulse.sh`, which also re-runs the IQ-4 gate.

### 3.4 Outstanding / follow-up (not blockers for R1 artifact)
- Final functional qualification (IQ-4, OQ-16, PQ-2, PQ-6) must be executed in a runner that builds the image (R4 in REMAINING_WORK). Acceptance proven once `import Pulse` succeeds and those tests pass in-image.
- `SimulationManager.step_simulation` currently degrades to a direct (sync) call because the native engine object is not picklable for `ProcessPoolExecutor`; a production hardening is to pin each engine to a long-lived worker process/thread (separate task; does not affect R1 fidelity).

## 4. Evidence links
- Kitware tags: `REL_4_3_2` (gitlab.kitware.com/physiology/engine).
- Authoritative build recipe used: Kitware repo `Dockerfile` at `REL_4_3_2` (superbuild, `Pulse_PYTHON_API`).
- Companion: REMAINING_WORK_v1.1.md R1.
