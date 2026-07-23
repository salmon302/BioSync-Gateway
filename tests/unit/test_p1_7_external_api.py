# SPDX-License-Identifier: MIT
"""
P1-7 - Real external API calls (SRS §3.10.1 / §3.10.2).

Verifies the AccessGUDID/openFDA and NCBI ClinVar clients:
    - make real HTTP requests (no mock-data fallbacks),
    - normalise upstream payloads into stable shapes,
    - cache responses (FR-3.10.3) and degrade to stale cache on failure,
    - raise ExternalAPIError when the upstream fails and nothing is cached,
    - enforce rate limiting (SRS §4.3).

The default suite is hermetic: upstream HTTP is stubbed via ``_get_json``.
Live tests that hit the real APIs are guarded by BIOSYNC_LIVE_TESTS=1.
"""

import asyncio
import os
import time

import pytest

from external.accessgudid import AccessGUDIDClient, seed_devices_from_accessgudid
from external.base import ExternalAPIError, RateLimiter
from external.clinvar import ClinVarClient

pytestmark = pytest.mark.external

LIVE = os.getenv("BIOSYNC_LIVE_TESTS") == "1"
live_only = pytest.mark.skipif(not LIVE, reason="set BIOSYNC_LIVE_TESTS=1 for live API tests")


# ---------------------------------------------------------------------------
# Sample upstream payloads (trimmed from real responses)
# ---------------------------------------------------------------------------

ACCESSGUDID_LOOKUP = {
    "gudid": {
        "device": {
            "publicDeviceRecordKey": "d27ea5ec-590c-4051-8040-63b4cadbd962",
            "identifiers": {
                "identifier": [
                    {"deviceId": "00844588018923", "deviceIdType": "Primary",
                     "deviceIdIssuingAgency": "GS1"}
                ]
            },
            "brandName": "CS2 Acet. Cup Sys. - VitalitE",
            "versionModelNumber": "1107-0-3258",
            "companyName": "CONSENSUS ORTHOPEDICS, INC.",
            "deviceDescription": "Acet. Insert, VitalitE",
            "productCodes": {
                "fdaProductCode": [
                    {"productCode": "OQG", "productCodeName": "Hip Prosthesis"}
                ]
            },
        }
    }
}

OPENFDA_UDI = {
    "meta": {"results": {"total": 5804}},
    "results": [
        {
            "device_description": "SHAVER BUR ABRADER AQUA",
            "public_device_record_key": "3891e617-83d5-4701-9e94-4c1659be80a7",
            "version_or_model_number": "SMI7205324",
            "brand_name": "NA",
            "identifiers": [{"id": "10888551034227", "type": "Primary",
                             "issuing_agency": "GS1"}],
            "company_name": "STERILMED, INC.",
            "product_codes": [{"code": "HRX", "name": "ARTHROSCOPE"}],
        }
    ],
}

CLINVAR_ESEARCH = {
    "header": {"type": "esearch"},
    "esearchresult": {"count": "16041", "idlist": ["4867750", "4867749"]},
}

CLINVAR_ESUMMARY = {
    "header": {"type": "esummary"},
    "result": {
        "uids": ["4867750"],
        "4867750": {
            "uid": "4867750",
            "obj_type": "single nucleotide variant",
            "accession": "VCV004867750",
            "title": "NM_007294.4(BRCA1):c.3909G>C (p.Leu1303Phe)",
            "variation_set": [
                {
                    "canonical_spdi": "NC_000017.11:43091621:C:G",
                    "variation_loc": [
                        {"status": "current", "assembly_name": "GRCh38",
                         "chr": "17", "start": "43091622", "stop": "43091622",
                         "alt": "", "ref": ""},
                        {"status": "previous", "assembly_name": "GRCh37",
                         "chr": "17", "start": "41243639", "stop": "41243639"},
                    ],
                }
            ],
            "germline_classification": {
                "description": "Uncertain significance",
                "last_evaluated": "2026/06/09 00:00",
                "review_status": "criteria provided, single submitter",
            },
            "gene_sort": "BRCA1",
            "molecular_consequence_list": ["missense variant", "intron variant"],
            "protein_change": "L1303F",
        },
    },
}


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------

def _stub_get_json(mapping, counter=None):
    """Return an async stub for CachedClient._get_json keyed by URL substring."""
    async def _fake(url, params=None, headers=None):
        if counter is not None:
            counter["calls"] += 1
        for needle, value in mapping.items():
            if needle in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"unexpected URL: {url}")
    return _fake


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

def test_rate_limiter_enforces_min_interval():
    limiter = RateLimiter(calls_per_second=20.0)  # 50ms interval

    async def _run():
        start = time.monotonic()
        for _ in range(3):
            await limiter.acquire()
        return time.monotonic() - start

    elapsed = asyncio.run(_run())
    # Two enforced gaps of ~50ms after the first immediate call.
    assert elapsed >= 0.09


def test_rate_limiter_disabled_when_non_positive():
    limiter = RateLimiter(calls_per_second=0)

    async def _run():
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        return time.monotonic() - start

    assert asyncio.run(_run()) < 0.05


# ---------------------------------------------------------------------------
# AccessGUDID / openFDA
# ---------------------------------------------------------------------------

def test_get_device_normalizes_accessgudid(tmp_path, monkeypatch):
    client = AccessGUDIDClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json",
                        _stub_get_json({"lookup.json": ACCESSGUDID_LOOKUP}))

    device = asyncio.run(client.get_device("00844588018923"))

    assert device["deviceIdentifier"] == "00844588018923"
    assert device["deviceName"] == "CS2 Acet. Cup Sys. - VitalitE"
    assert device["manufacturer"] == "CONSENSUS ORTHOPEDICS, INC."
    assert device["productCodes"][0]["productCode"] == "OQG"
    assert device["fhirResource"]["resourceType"] == "Device"
    assert device["fhirResource"]["identifier"][0]["value"] == "00844588018923"


def test_get_device_returns_none_on_404(tmp_path, monkeypatch):
    client = AccessGUDIDClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json", _stub_get_json({"lookup.json": None}))
    assert asyncio.run(client.get_device("does-not-exist")) is None


def test_search_devices_normalizes_openfda(tmp_path, monkeypatch):
    client = AccessGUDIDClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json",
                        _stub_get_json({"api.fda.gov": OPENFDA_UDI}))

    devices = asyncio.run(client.search_devices("HRX"))

    assert len(devices) == 1
    assert devices[0]["deviceIdentifier"] == "10888551034227"
    assert devices[0]["productCodes"][0]["productCode"] == "HRX"
    assert devices[0]["source"] == "openfda"


def test_search_devices_empty_on_404(tmp_path, monkeypatch):
    client = AccessGUDIDClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json", _stub_get_json({"api.fda.gov": None}))
    assert asyncio.run(client.search_devices("ZZZ")) == []


def test_device_response_is_cached(tmp_path, monkeypatch):
    counter = {"calls": 0}
    client = AccessGUDIDClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json",
                        _stub_get_json({"lookup.json": ACCESSGUDID_LOOKUP}, counter))

    asyncio.run(client.get_device("00844588018923"))
    asyncio.run(client.get_device("00844588018923"))

    assert counter["calls"] == 1  # second call served from cache


def test_stale_cache_served_on_upstream_failure(tmp_path, monkeypatch):
    client = AccessGUDIDClient(cache_dir=str(tmp_path))

    # Prime the cache with a good response.
    monkeypatch.setattr(client, "_get_json",
                        _stub_get_json({"lookup.json": ACCESSGUDID_LOOKUP}))
    asyncio.run(client.get_device("00844588018923"))

    # Force the cache to look expired, then make upstream fail.
    path = client._cache_path("device_00844588018923")
    os.utime(path, (time.time() - 90000, time.time() - 90000))  # ~25h old
    monkeypatch.setattr(
        client, "_get_json",
        _stub_get_json({"lookup.json": ExternalAPIError("boom")}))

    device = asyncio.run(client.get_device("00844588018923"))
    assert device["deviceName"] == "CS2 Acet. Cup Sys. - VitalitE"  # stale copy


def test_error_raised_when_no_cache_and_failure(tmp_path, monkeypatch):
    client = AccessGUDIDClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(
        client, "_get_json",
        _stub_get_json({"lookup.json": ExternalAPIError("boom")}))

    with pytest.raises(ExternalAPIError):
        asyncio.run(client.get_device("00844588018923"))


def test_seed_devices_shape(tmp_path, monkeypatch):
    # Patch the client class so the helper uses our stub + temp cache.
    from external import accessgudid as ag_module

    orig_init = AccessGUDIDClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["cache_dir"] = str(tmp_path)
        orig_init(self, *args, **kwargs)
        self._get_json = _stub_get_json({"api.fda.gov": OPENFDA_UDI})

    monkeypatch.setattr(AccessGUDIDClient, "__init__", patched_init)

    seeded = asyncio.run(seed_devices_from_accessgudid("HRX"))
    assert seeded[0]["device_identifier"] == "10888551034227"
    assert seeded[0]["device_type"] == "ARTHROSCOPE"
    assert seeded[0]["fhir_resource"]["resourceType"] == "Device"


# ---------------------------------------------------------------------------
# ClinVar
# ---------------------------------------------------------------------------

def test_search_variants_normalizes(tmp_path, monkeypatch):
    client = ClinVarClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json", _stub_get_json({
        "esearch.fcgi": CLINVAR_ESEARCH,
        "esummary.fcgi": CLINVAR_ESUMMARY,
    }))

    variants = asyncio.run(client.search_variants("BRCA1"))

    assert len(variants) == 1
    v = variants[0]
    assert v["clinvarId"] == "4867750"
    assert v["gene"] == "BRCA1"
    assert v["clinicalSignificance"] == "Uncertain significance"
    assert v["proteinChange"] == "L1303F"
    assert v["genomicCoordinates"]["assembly"] == "GRCh38"
    # ref/alt filled from canonical SPDI when the loc entry omits them.
    assert v["genomicCoordinates"]["reference"] == "C"
    assert v["genomicCoordinates"]["alternate"] == "G"


def test_get_variant_by_id(tmp_path, monkeypatch):
    client = ClinVarClient(cache_dir=str(tmp_path))
    monkeypatch.setattr(client, "_get_json",
                        _stub_get_json({"esummary.fcgi": CLINVAR_ESUMMARY}))

    variant = asyncio.run(client.get_variant("4867750"))
    assert variant["accession"] == "VCV004867750"


def test_search_variants_empty_when_no_hits(tmp_path, monkeypatch):
    client = ClinVarClient(cache_dir=str(tmp_path))
    empty = {"esearchresult": {"idlist": []}}
    monkeypatch.setattr(client, "_get_json",
                        _stub_get_json({"esearch.fcgi": empty}))
    assert asyncio.run(client.search_variants("NOSUCHGENE")) == []


def test_clinvar_uses_api_key_rate(tmp_path):
    keyed = ClinVarClient(api_key="abc", cache_dir=str(tmp_path))
    unkeyed = ClinVarClient(cache_dir=str(tmp_path))
    # 10/s with key -> smaller interval than 3/s without.
    assert keyed._rate_limiter._min_interval < unkeyed._rate_limiter._min_interval


# ---------------------------------------------------------------------------
# Live verification (opt-in)
# ---------------------------------------------------------------------------

@live_only
def test_live_clinvar_search():
    async def _run():
        client = ClinVarClient()
        try:
            return await client.search_variants("BRCA1", retmax=3)
        finally:
            await client.aclose()

    variants = asyncio.run(_run())
    assert variants and variants[0]["gene"]
    assert variants[0]["clinvarId"]


@live_only
def test_live_openfda_search_hrx():
    async def _run():
        client = AccessGUDIDClient()
        try:
            return await client.search_devices("HRX", limit=3)
        finally:
            await client.aclose()

    devices = asyncio.run(_run())
    assert devices
    assert any(
        pc["productCode"] == "HRX"
        for d in devices for pc in d["productCodes"]
    )


@live_only
def test_live_accessgudid_lookup():
    async def _run():
        client = AccessGUDIDClient()
        try:
            return await client.get_device("00844588018923")
        finally:
            await client.aclose()

    device = asyncio.run(_run())
    assert device and device["deviceIdentifier"] == "00844588018923"
