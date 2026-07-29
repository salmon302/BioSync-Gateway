#!/usr/bin/env bash
#=============================================================================
# Title: build-pulse.sh
# Date: 2026-07-27T17:45:00Z
# Author: Seth Nenninger (tencent/hy3 Agent)
# Contribution Type: Implementation
# Ticket/Context: REMAINING_WORK_v1.1 R1 - Build & deploy real PyPulse binary
# Summary: Reproducibly build the BioSync-Gateway Pulse image from the local
#          .pulse source and assert `import Pulse` (IQ-4 build gate).
#=============================================================================
#
# Usage:
#   SNDEV/scripts/build-pulse.sh [IMAGE_TAG]
#
# The build context is the repository root so the vendored `.pulse/` engine
# source is reachable by middleware/Dockerfile.pulse. Requires Docker with
# network access for the Pulse superbuild (Boost/Protobuf/Eigen/abseil) when
# VARIANT=git (the default VARIANT=local only needs the local .pulse source).
#
# Env:
#   PULSE_VARIANT  local (default) = COPY the vendored .pulse/ source (offline)
#                  git            = clone the pinned upstream tag (CI)
set -euo pipefail

# Resolve script directory and log paths relative to SNDEV/scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${LOG_DIR}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/build-pulse_${TIMESTAMP}.log"

# Define failure trap handler
on_failure() {
    local exit_code=$?
    local line_no=$1
    echo ""
    echo "========================================================================"
    echo ">> [ERROR] Script execution failed at line ${line_no} with code ${exit_code}."
    echo ">> [LOGS]  Failure log saved to: ${LOG_FILE}"
    echo "========================================================================"
    echo ""
    read -rp "Press [ENTER] to exit..."
    exit "${exit_code}"
}

trap 'on_failure $LINENO' ERR

# Tee all script output (stdout + stderr) to both the terminal and log file
exec > >(tee -a "${LOG_FILE}") 2>&1

IMAGE_TAG="${1:-biosync-pulse:local}"
PULSE_VARIANT="${PULSE_VARIANT:-local}"
# Resolve the repository root relative to this script (SNDEV/scripts -> root).
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo ">> Log session started at $(date)"
echo ">> [R1] Building Pulse image (source variant: ${PULSE_VARIANT})"
echo "   context = ${REPO_ROOT}"
echo "   tag     = ${IMAGE_TAG}"
echo "   log     = ${LOG_FILE}"

docker build -f middleware/Dockerfile.pulse --build-arg "VARIANT=${PULSE_VARIANT}" -t "${IMAGE_TAG}" "${REPO_ROOT}"

echo ">> [IQ-4 build gate] asserting 'import Pulse' in the runtime image"
docker run --rm "${IMAGE_TAG}" python -c \
  "import Pulse; from Pulse import Engine; print('PyPulse (Pulse) OK:', Pulse.__file__)"

cat <<'EOF'

>> [Next step] Run the real-engine qualification suite (IQ-4 / OQ-16 / PQ-2 / PQ-6).
   These tests `pytest.importorskip("Pulse")`, so they skip without PyPulse and
   run for real once it is importable:

docker run --rm \
  -v "${REPO_ROOT}":/repo \
  -w /repo/middleware \
  -e PYTHONPATH=/repo/middleware:/repo \
  "${IMAGE_TAG}" pytest \
    /repo/tests/test_iq4_pulse_engine_init.py \
    /repo/tests/test_oq16_state_serialization.py \
    /repo/tests/test_pq2_concurrent_simulations.py \
    /repo/tests/test_pq6_ventilator_stress.py -v

EOF