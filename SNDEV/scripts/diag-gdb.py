#!/usr/bin/env python3
# Standalone repro for gdb (no heredoc) -- explicit patient init that SIGSEGVs.
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
e = Engine(data_root_dir='/pulse/bin')
cfg = SEPatientConfiguration()
cfg.set_patient_file('/pulse/bin/patients/StandardMale.json')
print('calling initialize_engine ...', flush=True)
ok = e.initialize_engine(cfg)
print('INITIALIZE_ENGINE_RESULT=', ok)
