#!/bin/sh
python - <<'PY'
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
e = Engine(data_root_dir='/pulse/bin')
cfg = SEPatientConfiguration()
cfg.set_patient_file("/pulse/bin/patients/StandardMale.json")
print('INIT (set_patient_file):', e.initialize_engine(cfg))
PY
