import sys
sys.path.insert(0, '/pulse/python')
sys.path.insert(0, '/pulse/bin')
sys.path.insert(0, '/tmp/Pulse')

from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration, SEPatient, TimeUnit, MassUnit, LengthUnit

e = Engine(data_root_dir='/pulse/bin')
e.log_to_console(True)

pc = SEPatientConfiguration()
patient = SEPatient()
patient.set_name('test')
patient.get_age().set_value(45, TimeUnit.yr)
patient.get_weight().set_value(70.0, MassUnit.kg)
patient.get_height().set_value(175.0, LengthUnit.cm)
pc.set_patient(patient)

print('INIT:', e.initialize_engine(pc))
if e.initialize_engine(pc):
    e.advance_time_s(0.1)
    print('pull_data ok')
