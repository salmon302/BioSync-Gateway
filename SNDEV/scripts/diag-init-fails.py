import sys, os
sys.path.insert(0, '/middleware')
sys.path.insert(0, '/pulse/python')
sys.path.insert(0, '/pulse/bin')
from Pulse import Engine
from Pulse.CDM import SEPatientConfiguration
from pulse.cdm.scalars import TimeUnit, MassUnit, LengthUnit
from pulse.cdm.engine import SEDataRequest, SEDataRequestManager, eSerializationFormat

def make_config(pid, age, weight, height, sex):
    pc = SEPatientConfiguration()
    patient = pc.get_patient()
    patient.set_name(pid)
    patient.get_age().set_value(age, TimeUnit.yr)
    patient.get_weight().set_value(weight, MassUnit.kg)
    patient.get_height().set_value(height, LengthUnit.cm)
    if sex == "female":
        patient.set_sex(__import__('pulse.cdm.patient', fromlist=['eSex']).eSex.Female)
    else:
        patient.set_sex(__import__('pulse.cdm.patient', fromlist=['eSex']).eSex.Male)
    return pc

reqs = SEDataRequestManager()
reqs.set_data_requests([SEDataRequest.create_physiology_request(n) for n in
    ["HeartRate","SystolicArterialPressure","DiastolicArterialPressure","RespirationRate","OxygenSaturation"]])

configs = [
    ("vent-patient-7", 66, 79, 179, "female"),
    ("range-patient-4", 70, 80, 180, "male"),
    ("vent-patient-0", 45, 65, 165, "male"),
    ("vent-patient-6", 63, 77, 177, "male"),
]

for pid, age, w, h, sex in configs:
    e = Engine(data_root_dir='/pulse/bin')
    try:
        e.log_to_console(True)
    except Exception:
        pass
    pc = make_config(pid, age, w, h, sex)
    try:
        ok = e.initialize_engine(pc, reqs)
        print(f"INIT {pid}: {ok}", flush=True)
    except Exception as ex:
        print(f"INIT {pid}: EXC {ex!r}", flush=True)
