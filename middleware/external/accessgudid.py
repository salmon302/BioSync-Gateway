# SPDX-License-Identifier: MIT
"""
FDA Device Data Client
Implements SRS §3.10.1 - AccessGUDID Device Integration

Real external API integration (P1-7):
    - get_device(di):  FDA AccessGUDID Device Lookup API (canonical device record)
    - search_devices(product_code):  openFDA Device UDI API (parametric search)

Why two upstreams?
    AccessGUDID exposes a *lookup-by-identifier* JSON API only - it has no
    public parametric/product-code search endpoint. The openFDA Device UDI
    database (also an FDA service) mirrors the same GUDID data and supports
    ``search=product_codes.code:HRX`` queries required by FR-3.10.1
    (Product Code HRX = Arthroscopes and Accessories). We therefore use
    openFDA for discovery and AccessGUDID for canonical per-device detail.

Caching (FR-3.10.3): 24-hour TTL for device data, with stale-cache fallback on
upstream failure. There are no mock-data fallbacks.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, List, Optional

from external.base import CachedClient, ExternalAPIError, default_cache_root

logger = logging.getLogger(__name__)


class AccessGUDIDClient(CachedClient):
    """
    FDA device metadata client.

    Implements:
        SRS FR-3.10.1 - AccessGUDID device lookup / product-code search
        SRS FR-3.10.3 - 24-hour cache TTL
    """

    # AccessGUDID canonical lookup (by device identifier).
    ACCESSGUDID_LOOKUP_URL = "https://accessgudid.nlm.nih.gov/api/v3/devices/lookup.json"
    # openFDA UDI parametric search (by product code, etc.).
    OPENFDA_UDI_URL = "https://api.fda.gov/device/udi.json"

    CACHE_TTL_HOURS = 24
    # AccessGUDID has no published hard limit; openFDA allows 240/min without a
    # key. 2 req/s is a safe sustained rate for both.
    CALLS_PER_SECOND = 2.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        openfda_api_key: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        """
        Args:
            api_key: Reserved for AccessGUDID (public API needs none today).
            openfda_api_key: openFDA API key (raises daily quota; optional).
            cache_dir: Override cache directory (defaults to shared cache root).
        """
        super().__init__(
            cache_dir=cache_dir or os.path.join(default_cache_root(), "accessgudid"),
        )
        self.api_key = api_key or os.getenv("ACCESSGUDID_API_KEY") or None
        self.openfda_api_key = openfda_api_key or os.getenv("OPENFDA_API_KEY") or None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_device(self, device_identifier: str) -> Optional[Dict]:
        """
        Retrieve a canonical device record by Device Identifier (DI).

        Args:
            device_identifier: GUDID primary device identifier (DI).

        Returns:
            Normalised device dict, or ``None`` if the DI is unknown.

        Raises:
            ExternalAPIError: on upstream failure with no cached copy.

        Implements:
            SRS FR-3.10.1 - Device lookup
        """
        cache_key = f"device_{device_identifier}"

        async def fetch():
            raw = await self._get_json(
                self.ACCESSGUDID_LOOKUP_URL, params={"di": device_identifier}
            )
            if raw is None:
                return None
            return self._normalize_accessgudid(raw)

        return await self._cached_fetch(cache_key, self.CACHE_TTL_HOURS, fetch)

    async def search_devices(
        self, product_code: str, limit: int = 20
    ) -> List[Dict]:
        """
        Search devices by FDA product code via openFDA.

        Args:
            product_code: FDA product code (e.g. "HRX" for arthroscopes).
            limit: Maximum records to return (openFDA max 1000).

        Returns:
            List of normalised device dicts (possibly empty).

        Raises:
            ExternalAPIError: on upstream failure with no cached copy.

        Implements:
            SRS FR-3.10.1 - Device search by product code
        """
        cache_key = f"product_code_{product_code}_{limit}"

        async def fetch():
            params = {
                "search": f"product_codes.code:{product_code}",
                "limit": max(1, min(limit, 1000)),
            }
            if self.openfda_api_key:
                params["api_key"] = self.openfda_api_key
            raw = await self._get_json(self.OPENFDA_UDI_URL, params=params)
            # openFDA returns 404 when zero records match the query.
            if raw is None:
                return []
            results = raw.get("results", [])
            return [self._normalize_openfda(r) for r in results]

        return await self._cached_fetch(
            cache_key, self.CACHE_TTL_HOURS, fetch, empty=[]
        )

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _primary_di(identifiers: List[Dict]) -> Optional[str]:
        """Pick the primary device identifier from an identifier list."""
        for ident in identifiers or []:
            if ident.get("deviceIdType") == "Primary" or ident.get("type") == "Primary":
                return ident.get("deviceId") or ident.get("id")
        if identifiers:
            first = identifiers[0]
            return first.get("deviceId") or first.get("id")
        return None

    def _normalize_accessgudid(self, raw: Dict) -> Dict:
        """Transform an AccessGUDID lookup payload into our device shape."""
        device = (raw.get("gudid") or {}).get("device") or {}
        identifiers = (device.get("identifiers") or {}).get("identifier") or []
        di = self._primary_di(identifiers)

        product_codes = [
            {
                "productCode": pc.get("productCode"),
                "productCodeName": pc.get("productCodeName"),
            }
            for pc in (device.get("productCodes") or {}).get("fdaProductCode") or []
        ]

        return {
            "deviceIdentifier": di,
            "deviceName": device.get("brandName"),
            "manufacturer": device.get("companyName"),
            "modelNumber": device.get("versionModelNumber")
            or device.get("catalogNumber"),
            "deviceDescription": device.get("deviceDescription"),
            "productCodes": product_codes,
            "source": "accessgudid",
            "recordKey": device.get("publicDeviceRecordKey"),
            "fhirResource": self._to_fhir_device(
                di,
                device.get("brandName"),
                device.get("companyName"),
                device.get("versionModelNumber"),
                product_codes,
            ),
        }

    def _normalize_openfda(self, raw: Dict) -> Dict:
        """Transform an openFDA UDI record into our device shape."""
        identifiers = raw.get("identifiers") or []
        di = self._primary_di(identifiers)

        product_codes = [
            {
                "productCode": pc.get("code"),
                "productCodeName": pc.get("name"),
            }
            for pc in raw.get("product_codes") or []
        ]

        return {
            "deviceIdentifier": di,
            "deviceName": raw.get("brand_name"),
            "manufacturer": raw.get("company_name"),
            "modelNumber": raw.get("version_or_model_number")
            or raw.get("catalog_number"),
            "deviceDescription": raw.get("device_description"),
            "productCodes": product_codes,
            "source": "openfda",
            "recordKey": raw.get("public_device_record_key"),
            "fhirResource": self._to_fhir_device(
                di,
                raw.get("brand_name"),
                raw.get("company_name"),
                raw.get("version_or_model_number"),
                product_codes,
            ),
        }

    @staticmethod
    def _to_fhir_device(
        di: Optional[str],
        brand_name: Optional[str],
        manufacturer: Optional[str],
        model_number: Optional[str],
        product_codes: List[Dict],
    ) -> Dict:
        """Build a minimal FHIR Device resource (SRS §3.7 alignment)."""
        resource: Dict = {
            "resourceType": "Device",
            "identifier": [
                {
                    "system": "http://hl7.org/fhir/NamingSystem/gs1-di",
                    "value": di,
                }
            ]
            if di
            else [],
        }
        if manufacturer:
            resource["manufacturer"] = manufacturer
        if model_number:
            resource["modelNumber"] = model_number
        if brand_name:
            resource["deviceName"] = [
                {"name": brand_name, "type": "user-friendly-name"}
            ]
        if product_codes:
            resource["type"] = {
                "coding": [
                    {
                        "system": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPCD/classification.cfm",
                        "code": pc["productCode"],
                        "display": pc.get("productCodeName"),
                    }
                    for pc in product_codes
                    if pc.get("productCode")
                ]
            }
        return resource


async def seed_devices_from_accessgudid(
    product_code: str = "HRX", limit: int = 20
) -> List[Dict]:
    """
    Seed the device registry from FDA data for a product code.

    Args:
        product_code: FDA product code to seed (default HRX = arthroscopes).
        limit: Maximum number of devices to fetch.

    Returns:
        List of DB-shaped device records.

    Implements:
        SRS FR-3.10.1 - Device registry seeding
    """
    client = AccessGUDIDClient()
    try:
        devices = await client.search_devices(product_code, limit=limit)
    finally:
        await client.aclose()

    db_devices = []
    for device in devices:
        db_devices.append(
            {
                "device_identifier": device.get("deviceIdentifier"),
                "device_name": device.get("deviceName"),
                "manufacturer": device.get("manufacturer"),
                "model_number": device.get("modelNumber"),
                "device_type": (device.get("productCodes") or [{}])[0].get(
                    "productCodeName"
                ),
                "fhir_resource": device.get("fhirResource"),
            }
        )
    return db_devices


if __name__ == "__main__":
    # Live self-test (requires network access).
    logging.basicConfig(level=logging.INFO)
    print("Testing AccessGUDID / openFDA client (live)...")

    async def _main():
        client = AccessGUDIDClient()
        try:
            print("\n1. Search devices by product code HRX (openFDA):")
            devices = await client.search_devices("HRX", limit=3)
            print(f"   Found {len(devices)} devices")
            for d in devices:
                print(f"   - {d['deviceName']} ({d['deviceIdentifier']}) "
                      f"by {d['manufacturer']}")

            print("\n2. Lookup device by DI (AccessGUDID):")
            device = await client.get_device("00844588018923")
            if device:
                print(f"   {device['deviceName']} - {device['manufacturer']}")
                print(f"   Product codes: {device['productCodes']}")
            else:
                print("   Not found")
        finally:
            await client.aclose()

    asyncio.run(_main())
