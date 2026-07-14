"""
OQ-10: Valid Observation Accepted
Implements SRS OQ-10 - Valid FHIR Observation is accepted
"""

import pytest
from middleware.fhir_validator import validate_resource, ValidationError


class TestOQ10ValidObservationAccepted:
    """Test suite for OQ-10"""
    
    def test_valid_observation_accepted(self):
        """Valid Observation should pass validation"""
        valid_observation = {
            "resourceType": "Observation",
            "id": "example-obs",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8310-5",
                    "display": "Body temperature"
                }]
            },
            "valueQuantity": {
                "value": 36.5,
                "unit": "Celsius",
                "system": "http://unitsofmeasure.org",
                "code": "Cel"
            }
        }
        
        is_valid, outcome = validate_resource(valid_observation)
        assert is_valid, f"Valid Observation should be accepted, got: {outcome}"
        assert outcome is None, "No OperationOutcome for valid resource"
    
    def test_minimal_valid_observation(self):
        """Minimal valid Observation (only required fields)"""
        minimal_observation = {
            "resourceType": "Observation",
            "code": {
                "text": "Body temperature"
            },
            "valueQuantity": {
                "value": 98.6,
                "unit": "Fahrenheit"
            }
        }
        
        is_valid, outcome = validate_resource(minimal_observation)
        assert is_valid, f"Minimal Observation should be accepted, got: {outcome}"
    
    def test_observation_with_components(self):
        """Observation with component array"""
        observation_with_components = {
            "resourceType": "Observation",
            "code": {
                "text": "Blood pressure"
            },
            "valueQuantity": {
                "value": 120,
                "unit": "mmHg"
            },
            "component": [
                {
                    "code": {"text": "Systolic"},
                    "valueQuantity": {"value": 120, "unit": "mmHg"}
                },
                {
                    "code": {"text": "Diastolic"},
                    "valueQuantity": {"value": 80, "unit": "mmHg"}
                }
            ]
        }
        
        is_valid, outcome = validate_resource(observation_with_components)
        assert is_valid, f"Observation with components should be accepted, got: {outcome}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
