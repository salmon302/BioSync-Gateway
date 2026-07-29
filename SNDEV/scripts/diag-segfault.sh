#!/bin/sh
#=============================================================================
# Title: diag-segfault.sh
# Date: 2026-07-28T22:00:00Z
# Author: Seth Nenninger (tencent/hy3 Agent)
# Contribution Type: Implementation (diagnostic scaffolding)
# Ticket/Context: Pulse engine initialize_engine SIGSEGV (REMAINING_WORK R1)
# Summary: Comprehensive diagnostic harness executing diag-plan Steps 0,1,2,3
#          inside the pulse-builder-local image. Logs to /tmp/logs (mounted
#          from SNDEV/logs). Does NOT overwrite the canonical repro.
#
# Run:
#   docker run --rm \
#     -v "$PWD/SNDEV/scripts:/tmp/scripts" \
#     -v "$PWD/middleware/Pulse:/pulse/python/Pulse" \
#     -v "$PWD/SNDEV/logs:/tmp/logs" \
#     pulse-builder-local sh /tmp/scripts/diag-segfault.sh
#=============================================================================
set -u
LOG=/tmp/logs
mkdir -p "$LOG"

echo "==================== STEP 0: faulthandler backtrace (explicit patient) ===================="
python - <<'PY' 2>&1 | tee "$LOG/step0-faulthandler.txt"
import faulthandler, sys
faulthandler.enable()
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
print('PyPulse (Pulse) OK:', Pulse.__file__)
e = Engine(data_root_dir='/pulse/bin')
cfg = SEPatientConfiguration()
cfg.set_patient_file('/pulse/bin/patients/StandardMale.json')
try:
    ok = e.initialize_engine(cfg)
    sys.stdout.write('INITIALIZE_ENGINE_RESULT=' + str(ok) + '\n')
except Exception:
    import traceback; traceback.print_exc()
PY
echo "EXIT=$?"

echo "==================== STEP 1: substance data completeness ===================="
python - <<'PY' 2>&1 | tee "$LOG/step1-data-completeness.txt"
import json, glob, os
d='/pulse/bin/substances'
if not os.path.isdir(d):
    print('NO SUBSTANCE DIR at', d); raise SystemExit
names=sorted(os.path.basename(p) for p in glob.glob(d+'/*.json'))
print('count', len(names))
print('has Oxygen.json', 'Oxygen.json' in names)
print('has CarbonDioxide.json', 'CarbonDioxide.json' in names)
print('has Nitrogen.json', 'Nitrogen.json' in names)
bad=[n for n in names if os.path.getsize(os.path.join(d,n))<2]
print('empty/suspicious(<2 bytes):', bad[:20])
# show first few names to gauge the set
print('sample names:', names[:10])
PY

echo "==================== STEP 2: engine console log (log_to_console) ===================="
python - <<'PY' 2>&1 | tee "$LOG/step2-console.txt"
import sys
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
e = Engine(data_root_dir='/pulse/bin')
try:
    e.log_to_console(True)
except Exception as ex:
    print('log_to_console not available:', ex)
cfg = SEPatientConfiguration()
cfg.set_patient_file('/pulse/bin/patients/StandardMale.json')
try:
    ok = e.initialize_engine(cfg)
    sys.stdout.write('INITIALIZE_ENGINE_RESULT=' + str(ok) + '\n')
except Exception:
    import traceback; traceback.print_exc()
PY
echo "EXIT=$?"

echo "==================== STEP 3: shim bypass (bare pulse.engine.PulseEngine) ===================="
python - <<'PY' 2>&1 | tee "$LOG/step3-shim-bypass.txt"
import faulthandler, sys
faulthandler.enable()
from pulse.engine.PulseEngine import PulseEngine
from pulse.cdm.patient import SEPatientConfiguration
from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
names=["HeartRate","SystolicArterialPressure","DiastolicArterialPressure",
       "RespirationRate","OxygenSaturation","MeanAirwayPressure",
       "ArterialOxygenPartialPressure"]
drm=SEDataRequestManager()
drm.set_data_requests([SEDataRequest.create_physiology_request(n) for n in names])
e=PulseEngine(data_root_dir='/pulse/bin')
cfg=SEPatientConfiguration()
cfg.set_patient_file('/pulse/bin/patients/StandardMale.json')
try:
    ok=e.initialize_engine(cfg, drm)
    sys.stdout.write('BARE_ENGINE_INIT=' + str(ok) + '\n')
except Exception:
    import traceback; traceback.print_exc()
PY
echo "EXIT=$?"
echo "==================== DONE ===================="
