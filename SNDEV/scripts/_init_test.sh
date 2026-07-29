#!/bin/sh
# Temporary diagnostic: test engine init with the real 'pulse' package (builder has no 'Pulse' shim).
python - <<'PY'
import pulse
from pulse import Engine
from pulse.CDM import SEPatientConfiguration
print('pulse package:', pulse.__file__)
e = Engine(data_root_dir='/pulse/bin')
try:
    ok = e.initialize_engine(SEPatientConfiguration())
    print('INIT RESULT:', ok)
except Exception:
    import traceback; traceback.print_exc()
PY
