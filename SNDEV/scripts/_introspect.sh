#!/bin/sh
python - <<'PY'
import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration, SEPatient
print('--- SEPatient methods (Name/Patient related) ---')
print([m for m in dir(SEPatient) if 'ame' in m or 'atient' in m.lower() or 'et' in m][:40])
print('--- SEPatientConfiguration methods ---')
print([m for m in dir(SEPatientConfiguration) if 'atient' in m or 'et' in m or 'tate' in m][:40])
print('--- Engine init-related ---')
print([m for m in dir(Engine) if 'nitial' in m or 'load' in m or 'atient' in m][:40])
PY
