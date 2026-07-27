# SPDX-License-Identifier: MIT
"""
G9: FHIR Bundle Persistence of All Supported Resource Types
Implements SRS FR-3.7.5 — Bundle (transaction/batch) support.

Verifies that POST /api/fhir/Bundle durably persists EVERY supported
resource type (Observation AND DeviceMetric), not only Observation.
This is a unit test that exercises the Bundle handler with a mocked
database session, so it runs without a live Postgres.
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
class TestFHIRBundlePersistsAllResourceTypes:
    """G9 — Bundle must persist all supported resource types."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def _make_bundle(self):
        return {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": "Observation"},
                    "resource": {
                        "resourceType": "Observation",
                        "code": {"text": "Heart rate"},
                        "valueQuantity": {"value": 72, "unit": "/min"},
                    },
                },
                {
                    "request": {"method": "POST", "url": "DeviceMetric"},
                    "resource": {
                        "resourceType": "DeviceMetric",
                        "operationalStatus": {"coding": [{"code": "on"}]},
                        "type": {"coding": [{"code": "temperature"}]},
                        "unit": {"coding": [{"code": "Cel"}]},
                    },
                },
            ],
        }

    def test_bundle_persists_observation_and_device_metric(self):
        """Both Observation and DeviceMetric entries are durably persisted."""
        from api.routes.fhir import process_bundle

        mock_db = MagicMock()
        bundle = self._make_bundle()

        response = self._run(
            process_bundle(bundle, db=mock_db, current_user=MagicMock())
        )

        # One db.add() per supported resource type entry (not just Observation).
        assert mock_db.add.call_count == 2, (
            f"Expected both entries persisted, got db.add called "
            f"{mock_db.add.call_count} times"
        )

        body = json.loads(response.body)
        assert body["resourceType"] == "Bundle"
        assert body["type"] == "transaction-response"
        for entry in body["entry"]:
            assert entry["response"]["status"] == "201 Created", (
                "Every supported resource type must be persisted (201 Created), "
                "not merely acknowledged."
            )

    def test_bundle_batch_persists_device_metric(self):
        """Batch bundles also persist DeviceMetric entries."""
        from api.routes.fhir import process_bundle

        mock_db = MagicMock()
        bundle = self._make_bundle()
        bundle["type"] = "batch"

        response = self._run(
            process_bundle(bundle, db=mock_db, current_user=MagicMock())
        )
        body = json.loads(response.body)
        assert body["type"] == "batch-response"
        assert mock_db.add.call_count == 2

    def test_bundle_persists_every_registered_supported_type(self):
        """G9 regression: EVERY type in RESOURCE_PERSISTERS is persisted.

        This is registry-driven, so when a new supported resource type is
        registered it is automatically covered -- the Bundle can never again
        silently drop a supported type (the exact bug G9 closes).
        """
        from api.routes.fhir import process_bundle, RESOURCE_PERSISTERS

        # One valid resource per registered supported type.
        valid_resources = {
            "Observation": {
                "resourceType": "Observation",
                "code": {"text": "Heart rate"},
                "valueQuantity": {"value": 72, "unit": "/min"},
            },
            "DeviceMetric": {
                "resourceType": "DeviceMetric",
                "operationalStatus": {"coding": [{"code": "on"}]},
                "type": {"coding": [{"code": "temperature"}]},
                "unit": {"coding": [{"code": "Cel"}]},
            },
        }
        assert set(RESOURCE_PERSISTERS.keys()) == set(valid_resources.keys()), (
            "Test fixtures must cover every registered supported type"
        )

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": rtype},
                    "resource": resource,
                }
                for rtype, resource in valid_resources.items()
            ],
        }

        mock_db = MagicMock()
        response = self._run(
            process_bundle(bundle, db=mock_db, current_user=MagicMock())
        )
        body = json.loads(response.body)

        # One db.add() per registered supported type -- none skipped.
        assert mock_db.add.call_count == len(RESOURCE_PERSISTERS), (
            f"Every supported resource type must be persisted; got "
            f"{mock_db.add.call_count} adds for "
            f"{len(RESOURCE_PERSISTERS)} registered types"
        )
        for entry in body["entry"]:
            assert entry["response"]["code"] == "created", (
                "Supported resource types must be durably persisted (201 Created)"
            )

    def test_bundle_unsupported_type_not_persisted(self):
        """Unsupported types are acknowledged, not stored (boundary check)."""
        from api.routes.fhir import process_bundle, RESOURCE_PERSISTERS

        unsupported = "OperationOutcome"  # not in RESOURCE_PERSISTERS
        assert unsupported not in RESOURCE_PERSISTERS

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {"method": "POST", "url": unsupported},
                    "resource": {"resourceType": unsupported},
                }
            ],
        }
        mock_db = MagicMock()
        response = self._run(
            process_bundle(bundle, db=mock_db, current_user=MagicMock())
        )
        body = json.loads(response.body)

        # Unsupported type must NOT be persisted.
        assert mock_db.add.call_count == 0
        assert body["entry"][0]["response"]["code"] == "ok"
