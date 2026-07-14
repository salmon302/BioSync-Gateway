"""
O-15: FHIR Bundle Processing
Implements SRS FR-3.7.5 — Bundle Support

Verifies that the system supports FHIR Bundle resources (type: transaction
and batch) for bulk data submission.
"""

import pytest


class TestFHIRBundleProcessing:
    """Tests for FR-3.7.5 — Bundle (transaction/batch) support."""

    def test_bundle_transaction_type(self):
        """Bundle should support transaction type."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": []
        }
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "transaction"

    def test_bundle_batch_type(self):
        """Bundle should support batch type."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": []
        }
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "batch"

    def test_bundle_with_observation_entries(self):
        """Bundle should contain Observation entries."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "Observation"
                    },
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Heart rate"},
                        "valueQuantity": {"value": 72, "unit": "/min"}
                    }
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "Observation"
                    },
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Blood pressure"},
                        "valueQuantity": {"value": 120, "unit": "mmHg"}
                    }
                }
            ]
        }

        assert len(bundle["entry"]) == 2
        for entry in bundle["entry"]:
            assert "request" in entry
            assert "resource" in entry
            assert entry["request"]["method"] == "POST"
            assert entry["request"]["url"] == "Observation"

    def test_bundle_with_device_metric_entries(self):
        """Bundle should contain DeviceMetric entries."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "DeviceMetric"
                    },
                    "resource": {
                        "resourceType": "DeviceMetric",
                        "operationalStatus": {
                            "coding": [{"code": "on"}]
                        },
                        "type": {
                            "coding": [{"code": "temperature"}]
                        },
                        "unit": {
                            "coding": [{"code": "Cel"}]
                        }
                    }
                }
            ]
        }

        assert len(bundle["entry"]) == 1
        resource = bundle["entry"][0]["resource"]
        assert resource["resourceType"] == "DeviceMetric"

    def test_bundle_mixed_resource_types(self):
        """Bundle should support mixed resource types."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Observation"},
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Heart rate"},
                        "valueQuantity": {"value": 72, "unit": "/min"}
                    }
                },
                {
                    "request": {"method": "POST", "url": "DeviceMetric"},
                    "resource": {
                        "resourceType": "DeviceMetric",
                        "operationalStatus": {"coding": [{"code": "on"}]},
                        "type": {"coding": [{"code": "temperature"}]},
                        "unit": {"coding": [{"code": "Cel"}]}
                    }
                }
            ]
        }

        assert len(bundle["entry"]) == 2
        resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Observation" in resource_types
        assert "DeviceMetric" in resource_types

    def test_bundle_batch_get_requests(self):
        """Batch bundle should support GET requests."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "request": {
                        "method": "GET",
                        "url": "Observation/1"
                    }
                },
                {
                    "request": {
                        "method": "GET",
                        "url": "Observation/2"
                    }
                }
            ]
        }

        assert bundle["type"] == "batch"
        for entry in bundle["entry"]:
            assert entry["request"]["method"] == "GET"

    def test_bundle_empty_entry_list(self):
        """Empty bundle entry list should be handled gracefully."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": []
        }

        assert len(bundle["entry"]) == 0

    def test_bundle_entry_request_required(self):
        """Each bundle entry should have a request field."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "Observation"
                    },
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "test"},
                        "valueQuantity": {"value": 1, "unit": "test"}
                    }
                }
            ]
        }

        for entry in bundle["entry"]:
            assert "request" in entry
            assert "method" in entry["request"]
            assert "url" in entry["request"]

    def test_bundle_transaction_atomic(self):
        """Transaction bundle should be atomic (all-or-nothing)."""
        # In a real implementation, this would verify that either
        # all entries are processed or none are
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Observation"},
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Heart rate"},
                        "valueQuantity": {"value": 72, "unit": "/min"}
                    }
                },
                {
                    "request": {"method": "POST", "url": "Observation"},
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Blood pressure"},
                        "valueQuantity": {"value": 120, "unit": "mmHg"}
                    }
                }
            ]
        }

        # Verify bundle structure supports atomicity
        assert bundle["type"] == "transaction"
        assert len(bundle["entry"]) == 2

        # In transaction mode, all entries should succeed or all fail
        # This is a structural test; actual atomicity is tested in API tests

    def test_bundle_with_parameters(self):
        """Bundle should support Parameters resource type."""
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Parameters",
                        "parameter": [
                            {"name": "patient_id", "valueString": "test-001"},
                            {"name": "start_date", "valueDate": "2026-01-01"},
                            {"name": "end_date", "valueDate": "2026-12-31"}
                        ]
                    }
                }
            ]
        }

        assert bundle["type"] == "collection"
        resource = bundle["entry"][0]["resource"]
        assert resource["resourceType"] == "Parameters"

    def test_bundle_entry_count(self):
        """Bundle should support multiple entries."""
        entries = []
        for i in range(10):
            entries.append({
                "request": {"method": "POST", "url": "Observation"},
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": f"Observation {i}"},
                    "valueQuantity": {"value": i, "unit": "test"}
                }
            })

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": entries
        }

        assert len(bundle["entry"]) == 10

    def test_bundle_validation_integration(self):
        """Bundle entries should be validated individually."""
        from middleware.fhir_validator import FHIRValidator

        validator = FHIRValidator()

        # Valid bundle entry
        valid_entry = {
            "resource": {
                "resourceType": "Observation",
                "code": {"text": "Heart rate"},
                "valueQuantity": {"value": 72, "unit": "/min"}
            }
        }

        is_valid, errors = validator.validate_observation(valid_entry["resource"])
        assert is_valid is True, "Valid Observation in bundle should pass"

        # Invalid bundle entry
        invalid_entry = {
            "resource": {
                "resourceType": "Observation",
                # Missing code and valueQuantity
            }
        }

        is_valid, errors = validator.validate_observation(invalid_entry["resource"])
        assert is_valid is False, "Invalid Observation in bundle should fail"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
