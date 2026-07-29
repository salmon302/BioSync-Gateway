import sys
sys.path.insert(0, '/pulse/python')
sys.path.insert(0, '/pulse/bin')
sys.path.insert(0, '/tmp/Pulse')

from pulse.cdm.patient import SEPatientConfiguration
from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
import os

print('--- /pulse/bin contents ---')
for f in sorted(os.listdir('/pulse/bin')):
    print('  ', f)

_drm = SEDataRequestManager()
_drm.set_data_requests([SEDataRequest.create_physiology_request('HeartRate')])
from pulse.engine.PulseEngine import PulseEngine
e = PulseEngine(data_root_dir='/pulse/bin')
e.log_to_console(True)
# The bare engine reloads substances from the process CWD during
# Controller::Initialize; chdir into the data root (as the shim now does) and
# use an EXPLICIT patient so the reload path is actually exercised (True).
_bpc = SEPatientConfiguration()
_bpc.set_patient_file('/pulse/bin/patients/StandardMale.json')
_prev = os.getcwd()
try:
    os.chdir('/pulse/bin')
    print('REAL ENGINE INIT:', e.initialize_engine(_bpc, _drm))
finally:
    os.chdir(_prev)

import Pulse
from Pulse.CDM import (
    SEPatientConfiguration as PC2,
    SEDataRequest as DR,
    SEState,
    eSex,
    TimeUnit,
    MassUnit,
    LengthUnit,
)
print('SHIM eSex:', [m.name for m in eSex])
print('SHIM units:', TimeUnit.yr, MassUnit.kg, LengthUnit.cm)

eng = Pulse.Engine(data_root_dir='/pulse/bin')
_sp = PC2()
_sp.set_patient_file('/pulse/bin/patients/StandardMale.json')
print('SHIM ENGINE INIT:', eng.initialize_engine(_sp))
eng.advance_time_s(0.1)
drm = eng.get_data_request_manager()
print('SHIM get_data_request_manager ->', type(drm).__name__)
res = drm.pull_data()
cols = list(res.columns)[:4] if hasattr(res, 'columns') else res
print('SHIM pull_data type:', type(res).__name__, 'cols:', cols)

st = SEState()
eng.get_state(st)
print('SHIM get_state bytes len:', len(st.SerializeToString()))

dr = DR()
dr.set_name('HeartRate')
dr.set_unit('bpm')
print('SHIM SEDataRequest shim ok:', dr._name, dr._unit)

print('ALL CHECKS PASSED')
