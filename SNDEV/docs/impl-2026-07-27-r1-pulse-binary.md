# Title: R1 - Build & deploy real PyPulse binary (remove synthetic fallback)
# Date: 2026-07-27T17:45:00Z
# Author: Seth Nenninger (tencent/hy3 Agent)
# Contribution Type: Implementation
# Ticket/Context: REMAINING_WORK_v1.1 R1 (SRS FR-3.6.1-3.6.5, FR-3.11-3.14)
# Summary: Compile the real Kitware Pulse engine from the local .pulse source via a multi-stage Dockerfile.pulse, flip runtime default to the real engine (synthetic becomes explicit opt-in), and add a CI/assert gate.
#
# NOTE: This refines the earlier impl-2026-07-27-R1-pypulse-binary.md (same
# author/agent, earlier today). That pass built from the pinned upstream tag
# (REL_4_3_2) via `git clone` and kept the real engine as an opt-in
# (BIOSSYNC_REAL_PULSE=1). This pass (a) switches the default source to the
# locally-vendored `.pulse/` you downloaded (offline/reproducible, VARIANT arg),
# and (b) makes the REAL engine the default at runtime with synthetic as an
# explicit opt-in (BIOSSYNC_SYNTHETIC=1) -- directly closing the R1 "synthetic
# fallback dependence" clause.

## Task Reference
REMAINING_WORK_v1.1.md R1 — "Build & deploy real `PyPulse` binary (multi-stage
`Dockerfile.pulse`); remove synthetic fallback dependence."
Acceptance: `import Pulse` succeeds in the runtime image; IQ-4 / OQ-16 / PQ-2 /
PQ-6 pass against the real engine.

## Specification Summary
- FR-3.6.1-3.6.5 (Pulse Engine integration) require authentic, compiled Pulse
  output instead of deterministic seeded-random synthesis.
- FR-3.11-3.14 (advanced analytics) depend on R1 for physiological fidelity.
- Prior state: `engine/pulse.py` already integrates the real engine
  (`import Pulse`, GPB state serialization, no mock fallback), but
  `engine/pulse_bridge.py` defaulted to SYNTHETIC (real only when
  `BIOSSYNC_REAL_PULSE=1`), and `Dockerfile.pulse` cloned `REL_4_3_2` from
  gitlab instead of using the locally downloaded `.pulse/` source.

## Implementation Notes
Files changed (evidence: file:line):

1. `middleware/Dockerfile.pulse` (rewritten)
   - Two builder stages selected by build arg `VARIANT` (default `local`):
     * `pulse-builder-local` does `COPY .pulse /source` (uses the vendored source
       you downloaded; offline, reproducible).
     * `pulse-builder-git` clones the pinned `PULSE_VERSION` (default `REL_4_3_2`)
       from gitlab (used by CI, because `.pulse/` is gitignored and absent from
       the checkout).
     * `FROM pulse-builder-${VARIANT}` picks the active stage, so the unused
       stage (and its `COPY .pulse`) is never executed -- CI never fails on the
       missing local source.
   - Build context is the repo root so `.pulse/` is reachable; `COPY middleware/requirements.txt`
     + `COPY middleware /app` adjusted accordingly.
   - Keeps the IQ-4 gate: `RUN python -c "import Pulse; from Pulse import Engine; ..."`
     (fails the build if the engine does not import).
   - Sets `ENV BIOSSYNC_SYNTHETIC=0` (real is default).

2. `.dockerignore` (new, repo root) — excludes `.git`, `frontend`, caches,
   venvs, secrets (`.env`); slims `.pulse/bin` and `.pulse/data` (not needed to
   compile); keeps `.pulse` + `middleware`.

3. `middleware/engine/pulse_bridge.py` (real-by-default)
   - Replaced `ENABLE_REAL_PULSE = getenv("BIOSSYNC_REAL_PULSE", "0")=="1"`
     with `SYNTHETIC_ONLY = getenv("BIOSSYNC_SYNTHETIC", "0")=="1"`.
   - `real_pulse_available()` now returns True whenever `import Pulse` succeeds
     (real is the default); returns False only when `BIOSSYNC_SYNTHETIC=1` is set
     or the import fails (with a loud warning). This removes the synthetic
     fallback *dependence*.

4. `middleware/engine/pulse.py` — docstring updated to reflect real-by-default /
   synthetic opt-in semantics.

5. `.github/workflows/pulse-engine.yml` — build context changed from `middleware`
   to `.` (repo root) so `.pulse/` is available; comment updated (no remote
   dependency). The run step already mounts the repo and runs IQ-4/OQ-16/PQ-2/PQ-6;
   those tests use `pytest.importorskip("Pulse")` and construct real workers, so
   they exercise the real engine once importable.

6. `docker-compose.yml` — corrected build/run guidance:
   `MIDDLEWARE_DOCKERFILE=Dockerfile.pulse docker compose` no longer works
   (context mismatch); replaced with the explicit
   `docker build -f middleware/Dockerfile.pulse -t biosync-pulse .`. Env var
   `BIOSSYNC_REAL_PULSE=1` replaced by `BIOSSYNC_SYNTHETIC=0` with a clarifying
   comment.

7. `SNDEV/scripts/build-pulse.sh` (new) — reproducible build + `import Pulse`
   assertion (IQ-4 gate) and a copy-paste command to run the four real-engine
   qualification tests.

## Verification Steps
- The heavy native compile
  (`docker build -f middleware/Dockerfile.pulse -t biosync-pulse .`) is deferred
  to the user environment (per agreed scope); it requires network for the Pulse
  superbuild (Boost/Protobuf/Eigen/abseil) and ~30-90 min.
- Automated gate (run after build): `SNDEV/scripts/build-pulse.sh biosync-pulse:local`
  asserts `import Pulse` in the image (IQ-4).
- Real-engine qualification (once built): the `pulse-engine.yml` workflow runs
  IQ-4 / OQ-16 / PQ-2 / PQ-6. These currently `skip` without PyPulse and run for
  real once it is importable (re-basing R4).
- Static checks performed in-session: Dockerfile/COPY-path consistency (context =
  repo root), `.dockerignore` excludes secrets, `pulse_bridge.real_pulse_available()`
  default flipped, no remaining references to `BIOSSYNC_REAL_PULSE` as a gate.

## Evidence
- `middleware/Dockerfile.pulse:34-51` (COPY .pulse + cmake/make install)
- `middleware/Dockerfile.pulse:86` (IQ-4 import gate)
- `middleware/engine/pulse_bridge.py:26-39` (SYNTHETIC_ONLY + real-by-default)
- `.github/workflows/pulse-engine.yml:25` (repo-root build context)
- `SNDEV/scripts/build-pulse.sh` (reproducible build + gate)

## Remaining (user-run) — not blocking the artifact delivery
- Execute `SNDEV/scripts/build-pulse.sh` and confirm the image imports `Pulse`.
- Run the four qualification tests in the built image and confirm PASS.
- Optional: bump REMAINING_WORK_v1.1.md R1 to CLOSED once the build is verified.
