#!/bin/sh
# Patch the reversed isinstance bug in the installed binding (container-only, for diagnosis)
sed -i 's/if not isinstance(SEPatient, patient):/if not isinstance(patient, SEPatient):/' /pulse/python/pulse/cdm/patient.py
python - <<'PY'
import Pulse, traceback
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
from Pulse.CDM import SEPatient
e = Engine(data_root_dir='/pulse/bin')
print('== set_name + set_patient ==')
try:
    cfg = SEPatientConfiguration()
    p = SEPatient()
    p.set_name("StandardMale")
    cfg.set_patient(p)
    print('INIT name:', e.initialize_engine(cfg))
except Exception:
    traceback.print_exc()
print('== set_patient_file ==')
try:
    cfg2 = SEPatientConfiguration()
    cfg2.set_patient_file("/pulse/bin/patients/StandardMale.json")
    print('INIT file:', e.initialize_engine(cfg2))
except Exception:
    traceback.print_exc()
PY
