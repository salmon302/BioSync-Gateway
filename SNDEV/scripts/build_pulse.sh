#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# build_pulse.sh - Reproducibly build the BioSync-Gateway middleware image with
# the REAL Kitware Pulse Physiology Engine ("Pulse" Python bindings, PyPulse).
#
# This closes REMAINING_WORK R1 (physiological fidelity). The engine is
# compiled from source inside middleware/Dockerfile.pulse (multi-stage).
#
# Prerequisites:
#   - Linux host with Docker >= 24 (daemon running) and >= 8 GiB RAM
#     (Pulse superbuild compiles Boost/Protobuf/Eigen; 4 GiB is too small).
#   - Network access to gitlab.kitware.com (source clone + dependency download).
#
# Usage:
#   ./build_pulse.sh [TAG]      # TAG defaults to REL_4_3_2
#
# Output image: biosync-pulse:<TAG>
set -euo pipefail

TAG="${1:-REL_4_3_2}"
IMAGE="biosync-pulse"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CTX="${ROOT}/middleware"

echo ">> Building ${IMAGE}:${TAG} from ${CTX} (Dockerfile.pulse)"
docker build \
  --file "${CTX}/Dockerfile.pulse" \
  --build-arg "PULSE_VERSION=${TAG}" \
  --tag "${IMAGE}:${TAG}" \
  "${CTX}"

echo ">> Verifying IQ-4 gate: 'import Pulse' inside the image"
docker run --rm "${IMAGE}:${TAG}" \
  python -c "import Pulse; from Pulse import Engine; print('PyPulse (Pulse) OK:', Pulse.__file__)"

echo ">> Build + IQ-4 gate PASSED for ${IMAGE}:${TAG}"
echo ">> Deploy with: MIDDLEWARE_DOCKERFILE=Dockerfile.pulse docker compose up --build"
