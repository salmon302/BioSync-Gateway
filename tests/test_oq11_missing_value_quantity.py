"""
OQ-11: Missing valueQuantity Rejected
Implements SRS OQ-11 - Observation without valueQuantity is rejected
"""

import pytest
from middleware.fhir_validator import validate_resource, ValidationError


class TestOQ11MissingValueQuantityRejected:
    """Test suite for OQ-11"""
    
    def test_missing_valueQuantity_rejected(self):
        """Observation without valueQuantity should be rejected"""
        invalid_observation = {
            "resourceType": "Observation",
            "id": "example-obs-no-value",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8310-5"
                }]
            }
            # Missing valueQuantity
        }
        
        is_valid, outcome = validate_resource(invalid_observation)
        assert not is_valid, "Observation without valueQuantity should be rejected"
        assert outcome is not None, "Should return OperationOutcome"
        
        # Check that error mentions valueQuantity
        issues = outcome.get("issue", [])
        value_quantity_errors = [
            issue for issue in issues
            if any("valueQuantity" in loc for loc in issue.get("location", []))
        ]
        assert len(value_quantity_errors) > 0, "Should have error for valueQuantity"
    
    def test_missing_code_rejected(self):
        """Observation without code should be rejected"""
        invalid_observation = {
            "resourceType": "Observation",
            "id": "example-obs-no-code",
            "status": "final",
            "valueQuantity": {
                "value": 36.5,
                "unit": "Celsius"
            }
            # Missing code
        }
        
        is_valid, outcome = validate_resource(invalid_observation)
        assert not is_valid, "Observation without code should be rejected"
    
    def test_empty_valueQuantity_rejected(self):
        """Observation with empty valueQuantity should be rejected"""
        invalid_observation = {
            "resourceType": "Observation",
            "code": {"text": "test"},
            "valueQuantity": {}  # Empty object
        }
        
        is_valid, outcome = validate_resource(invalid_observation)
        assert not is_valid, "Observation with empty valueQuantity should be rejected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
