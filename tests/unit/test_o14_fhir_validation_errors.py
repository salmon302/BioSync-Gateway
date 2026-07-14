"""
O-14: FHIR Validation Error Details
Implements SRS FR-3.7.4 — Validation Failure Response

Verifies that schema validation failures return FHIR OperationOutcome
resources with specific error details.
"""

import pytest


class TestFHIRValidationErrors:
    """Tests for FR-3.7.4 — OperationOutcome error responses."""

    def test_missing_valueQuantity_error_detail(self):
        """Missing valueQuantity should return specific error detail."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()
        is_valid, errors = validator.validate_observation({
            "resourceType": "Observation",
            "status": "final",
            "code": {"text": "test"}
            # Missing valueQuantity
        })

        assert is_valid is False
        assert len(errors) > 0

        # Should have valueQuantity error
        value_qty_errors = [e for e in errors
                          if "valueQuantity" in e.details.lower()
                          or "valueQuantity" in str(e.location)]
        assert len(value_qty_errors) > 0, \
            "Should have error mentioning valueQuantity"

    def test_missing_code_error_detail(self):
        """Missing code should return specific error detail."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()
        is_valid, errors = validator.validate_observation({
            "resourceType": "Observation",
            "status": "final",
            "valueQuantity": {"value": 1, "unit": "test"}
            # Missing code
        })

        assert is_valid is False
        assert len(errors) > 0

        # Should have code error
        code_errors = [e for e in errors
                      if "code" in e.details.lower()
                      or "code" in str(e.location)]
        assert len(code_errors) > 0, "Should have error mentioning code"

    def test_wrong_resource_type_error(self):
        """Wrong resource type should return structure error."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()
        is_valid, errors = validator.validate_observation({
            "resourceType": "Patient",  # Wrong type
            "name": "John Doe"
        })

        assert is_valid is False
        assert len(errors) > 0

        # Should have structure error
        structure_errors = [e for e in errors
                          if e.code == "structure"
                          or "Observation" in e.details]
        assert len(structure_errors) > 0, \
            "Should have structure error for wrong resource type"

    def test_empty_valueQuantity_error(self):
        """Empty valueQuantity should return required field error."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()
        is_valid, errors = validator.validate_observation({
            "resourceType": "Observation",
            "code": {"text": "test"},
            "valueQuantity": {}  # Empty object
        })

        assert is_valid is False
        assert len(errors) > 0

        # Should have value error
        value_errors = [e for e in errors
                       if "value" in e.details.lower()
                       or "required" in e.code]
        assert len(value_errors) > 0, \
            "Should have error for missing value in valueQuantity"

    def test_valid_observation_no_errors(self):
        """Valid Observation should return no errors."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()
        is_valid, errors = validator.validate_observation({
            "resourceType": "Observation",
            "code": {"text": "Body temperature"},
            "valueQuantity": {"value": 98.6, "unit": "Fahrenheit"}
        })

        assert is_valid is True
        assert len(errors) == 0

    def test_operation_outcome_format(self):
        """ValidationError should produce valid OperationOutcome format."""
        from middleware.fhir_validator import ValidationError

        error = ValidationError(
            severity="error",
            code="required",
            details="valueQuantity is required",
            location=["Observation", "valueQuantity"]
        )

        outcome = error.to_operation_outcome()

        assert "severity" in outcome
        assert outcome["severity"] == "error"
        assert "code" in outcome
        assert outcome["code"] == "required"
        assert "details" in outcome
        assert "text" in outcome["details"]
        assert "location" in outcome

    def test_error_severity_levels(self):
        """Errors should support different severity levels."""
        from middleware.fhir_validator import ValidationError

        # Fatal error
        fatal = ValidationError(
            severity="fatal",
            code="structure",
            details="Invalid resource type"
        )
        assert fatal.severity == "fatal"

        # Error
        error = ValidationError(
            severity="error",
            code="required",
            details="Missing required field"
        )
        assert error.severity == "error"

        # Warning
        warning = ValidationError(
            severity="warning",
            code="value",
            details="Unusual value"
        )
        assert warning.severity == "warning"

    def test_multiple_errors_returned(self):
        """Multiple validation errors should all be returned."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()
        is_valid, errors = validator.validate_observation({
            "resourceType": "Observation",
            # Missing both code and valueQuantity
        })

        assert is_valid is False
        assert len(errors) >= 2, \
            "Should return errors for both missing code and valueQuantity"

    def test_device_metric_missing_operational_status(self):
        """DeviceMetric without operationalStatus should return error."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()

        # Check if validate_device_metric exists
        if hasattr(validator, 'validate_device_metric'):
            is_valid, errors = validator.validate_device_metric({
                "resourceType": "DeviceMetric",
                "type": {"coding": [{"code": "temperature"}]},
                "unit": {"coding": [{"code": "Cel"}]}
                # Missing operationalStatus
            })

            assert is_valid is False
            assert len(errors) > 0

            status_errors = [e for e in errors
                           if "operationalStatus" in e.details.lower()
                           or "operationalStatus" in str(e.location)]
            assert len(status_errors) > 0, \
                "Should have error mentioning operationalStatus"

    def test_error_location_path(self):
        """Errors should include FHIRPath location."""
        from middleware.fhir_validator import ValidationError

        error = ValidationError(
            severity="error",
            code="required",
            details="valueQuantity is required",
            location=["Observation", "valueQuantity", "value"]
        )

        assert len(error.location) == 3
        assert error.location[0] == "Observation"
        assert error.location[1] == "valueQuantity"
        assert error.location[2] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
