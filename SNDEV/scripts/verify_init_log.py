import sys
sys.path.insert(0, '/pulse/python')
sys.path.insert(0, '/pulse/bin')
sys.path.insert(0, '/tmp/Pulse')

from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
e = Engine(data_root_dir='/pulse/bin')
e.log_to_console(True)
print('INIT:', e.initialize_engine(SEPatientConfiguration()))
