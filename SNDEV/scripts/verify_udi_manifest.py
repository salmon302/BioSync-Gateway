import json, sys
sys.path.insert(0, 'middleware')
from engine.barcode import validate_plate_indices, _encode_sequences
import numpy as np

with open('database/seeds/illumina_udis_v1.0.0.json') as f:
    manifest = json.load(f)

for set_name, set_data in manifest['barcode_sets'].items():
    indices = list(set_data['indices'].values())
    is_valid, violations = validate_plate_indices(indices, min_distance=3)
    min_dist = None
    if is_valid and len(indices) > 1:
        matrix = _encode_sequences(indices)
        dist_matrix = (matrix[:, np.newaxis, :] != matrix[np.newaxis, :, :]).sum(axis=-1)
        n = len(indices)
        rows, cols = np.triu_indices(n, k=1)
        min_dist = int(dist_matrix[rows, cols].min())
    status = 'OK' if is_valid else 'FAIL'
    print(f'{set_name}: {len(indices)} indices, valid={is_valid}, min_dist={min_dist}, violations={len(violations)} [{status}]')
    if violations:
        for v in violations[:3]:
            print(f'  VIOLATION: {v["index1"]} vs {v["index2"]} dist={v["hamming_distance"]}')
