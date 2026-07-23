# SPDX-License-Identifier: MIT
"""
External Data Integration clients.
Implements SRS §3.10 - External Data Integration (AccessGUDID, NCBI ClinVar).
"""

from external.accessgudid import AccessGUDIDClient, seed_devices_from_accessgudid
from external.base import CachedClient, ExternalAPIError, RateLimiter
from external.clinvar import ClinVarClient

__all__ = [
    "AccessGUDIDClient",
    "ClinVarClient",
    "CachedClient",
    "ExternalAPIError",
    "RateLimiter",
    "seed_devices_from_accessgudid",
]
