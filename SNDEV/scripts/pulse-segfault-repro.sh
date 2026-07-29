#!/usr/bin/env bash
#=============================================================================
# Title: pulse-segfault-repro.sh
# Date: 2026-07-28T19:30:00Z
# Author: Seth Nenninger (tencent/hy3 Agent)
# Contribution Type: Implementation (diagnostic scaffolding)
# Ticket/Context: Pulse engine initialize_engine SIGSEGV (REMAINING_WORK R1)
# Summary: Quick, rebuild-free reproduction of the engine segfault during
#          initialize_engine, so any planned patch can be validated fast.
#
# Usage (engine + generated data are already in the builder image):
#   docker run --rm \
#     -v "$PWD/SNDEV/scripts/pulse-segfault-repro.sh:/tmp/r.sh" \
#     -v "$PWD/middleware/Pulse:/pulse/python/Pulse" \
#     pulse-builder-local sh /tmp/r.sh
#
# Output: prints INITIALIZE_ENGINE_RESULT=<bool> and EXIT=<code>.
#   EXIT=139 (SIGSEGV) => engine crashes during init (the bug).
#   INITIALIZE_ENGINE_RESULT=True => engine initializes OK.
#=============================================================================
set -u
python - <<'PY'
import sys, traceback
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
e = Engine(data_root_dir='/pulse/bin')
cfg = SEPatientConfiguration()
cfg.set_patient_file('/pulse/bin/patients/StandardMale.json')
try:
    ok = e.initialize_engine(cfg)
    sys.stdout.write('INITIALIZE_ENGINE_RESULT=' + str(ok) + '\n')
except Exception:
    traceback.print_exc()
PY
echo "EXIT=$?"
