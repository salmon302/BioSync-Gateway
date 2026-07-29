#!/bin/sh
# Diagnostic scaffolding: establish reference (healthy) engine init behavior.
# Run with: docker run --rm -v <this>:/tmp/t.sh pulse-builder-local sh /tmp/t.sh
python - <<'PY'
import sys, traceback
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
e = Engine(data_root_dir='/pulse/bin')

print('--- EMPTY SEPatientConfiguration() ---')
try:
    ok = e.initialize_engine(SEPatientConfiguration())
    print('EMPTY_CONFIG:', ok)
except Exception:
    print('EMPTY_CONFIG EXC:'); traceback.print_exc()

print('--- EXPLICIT set_patient_file(StandardMale) ---')
try:
    cfg = SEPatientConfiguration()
    cfg.set_patient_file('/pulse/bin/patients/StandardMale.json')
    ok = e.initialize_engine(cfg)
    print('FILE_CONFIG:', ok)
except Exception:
    print('FILE_CONFIG EXC:'); traceback.print_exc()
PY
echo "EXIT=$?"
