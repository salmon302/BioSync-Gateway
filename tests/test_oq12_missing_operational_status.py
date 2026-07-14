"""
OQ-12: Missing operationalStatus Rejected
Implements SRS OQ-12 - DeviceMetric without operationalStatus is rejected
"""

import pytest
from middleware.fhir_validator import validate_resource, ValidationError


class TestOQ12MissingOperationalStatusRejected:
    """Test suite for OQ-12"""
    
    def test_missing_operationalStatus_rejected(self):
        """DeviceMetric without operationalStatus should be rejected"""
        invalid_device_metric = {
            "resourceType": "DeviceMetric",
            "id": "example-dm-no-status",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/metric-type",
                    "code": "temperature"
                }]
            },
            "unit": {
                "coding": [{
                    "system": "http://unitsofmeasure.org",
                    "code": "Cel"
                }]
            }
            # Missing operationalStatus
        }
        
        is_valid, outcome = validate_resource(invalid_device_metric)
        assert not is_valid, "DeviceMetric without operationalStatus should be rejected"
        assert outcome is not None, "Should return OperationOutcome"
        
        # Check that error mentions operationalStatus
        issues = outcome.get("issue", [])
        status_errors = [
            issue for issue in issues
            if any("operationalStatus" in loc for loc in issue.get("location", []))
        ]
        assert len(status_errors) > 0, "Should have error for operationalStatus"
    
    def test_missing_type_rejected(self):
        """DeviceMetric without type should be rejected"""
        invalid_device_metric = {
            "resourceType": "DeviceMetric",
            "id": "example-dm-no-type",
            "operationalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/metric-operational-status",
                    "code": "on"
                }]
            },
            "unit": {
                "coding": [{
                    "system": "http://unitsofmeasure.org",
                    "code": "Cel"
                }]
            }
            # Missing type
        }
        
        is_valid, outcome = validate_resource(invalid_device_metric)
        assert not is_valid, "DeviceMetric without type should be rejected"
    
    def test_valid_device_metric_accepted(self):
        """Valid DeviceMetric should pass validation"""
        valid_device_metric = {
            "resourceType": "DeviceMetric",
            "id": "example-dm-valid",
            "operationalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/metric-operational-status",
                    "code": "on"
                }]
            },
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/metric-type",
                    "code": "temperature"
                }]
            },
            "unit": {
                "coding": [{
                    "system": "http://unitsofmeasure.org",
                    "code": "Cel"
                }]
            }
        }
        
        is_valid, outcome = validate_resource(valid_device_metric)
        assert is_valid, f"Valid DeviceMetric should be accepted, got: {outcome}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
