import sys
sys.path.insert(0, '/pulse/python')
sys.path.insert(0, '/pulse/bin')
sys.path.insert(0, '/tmp/Pulse')

import Pulse
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
print('PyPulse (Pulse) OK:', Pulse.__file__)
e = Engine(data_root_dir='/pulse/bin')
assert e.initialize_engine(SEPatientConfiguration()), 'Engine failed to initialize'
print('ENGINE INIT OK')
e.advance_time_s(0.1)
res = e.get_data_request_manager().pull_data()
print('pull_data rows:', len(res) if hasattr(res, '__len__') else 'n/a')
# exercise state serialization (OQ-16 path)
from Pulse.CDM import SEState
st = SEState()
e.get_state(st)
print('get_state bytes:', len(st.SerializeToString()))
print('ALL CHECKS PASSED')
