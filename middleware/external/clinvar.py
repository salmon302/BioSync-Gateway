# SPDX-License-Identifier: MIT
"""
NCBI ClinVar API Client
Implements SRS §3.10.2 - NCBI ClinVar Integration

Real external API integration (P1-7) via NCBI E-utilities:
    - search_variants(gene):        esearch -> esummary
    - get_variant(variant_id):      esummary
    - get_variant_by_coordinates(): esearch -> esummary

Caching (FR-3.10.3): 7-day TTL for variant data, with stale-cache fallback on
upstream failure. There are no mock-data fallbacks.

Rate limiting (SRS §4.3): NCBI permits 3 requests/second without an API key and
10/second with one. The client rate-limits accordingly.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, List, Optional

from external.base import CachedClient, ExternalAPIError, default_cache_root

logger = logging.getLogger(__name__)


class ClinVarClient(CachedClient):
    """
    NCBI ClinVar variant data client.

    Implements:
        SRS FR-3.10.2 - ClinVar variant lookup / search
        SRS FR-3.10.3 - 7-day cache TTL
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    CACHE_TTL_HOURS = 168  # 7 days
    # NCBI: 3/s without key, 10/s with key.
    CALLS_PER_SECOND = 3.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        """
        Args:
            api_key: NCBI API key (optional; raises rate limit to 10/s).
            cache_dir: Override cache directory (defaults to shared cache root).
        """
        self.api_key = api_key or os.getenv("CLINVAR_API_KEY") or None
        super().__init__(
            cache_dir=cache_dir or os.path.join(default_cache_root(), "clinvar"),
            calls_per_second=10.0 if self.api_key else 3.0,
        )

    def _eutils_params(self, extra: Dict) -> Dict:
        """Merge common E-utilities params (db, tool, email, api_key)."""
        params = {
            "db": "clinvar",
            "retmode": "json",
            "tool": "biosync-gateway",
        }
        params.update(extra)
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def _esearch(self, term: str, retmax: int = 20) -> List[str]:
        """Run esearch and return the list of matching ClinVar UIDs."""
        result = await self._get_json(
            f"{self.BASE_URL}/esearch.fcgi",
            params=self._eutils_params({"term": term, "retmax": retmax}),
        )
        if not result:
            return []
        return (result.get("esearchresult") or {}).get("idlist", [])

    async def _esummary(self, uids: List[str]) -> List[Dict]:
        """Run esummary for UIDs and return normalised variant dicts."""
        if not uids:
            return []
        result = await self._get_json(
            f"{self.BASE_URL}/esummary.fcgi",
            params=self._eutils_params({"id": ",".join(uids)}),
        )
        if not result:
            return []
        docs = result.get("result") or {}
        variants = []
        for uid in docs.get("uids", []):
            doc = docs.get(uid)
            if doc:
                variants.append(self._normalize_variant(doc))
        return variants

    async def get_variant(self, variant_id: str) -> Optional[Dict]:
        """
        Retrieve a single variant summary by ClinVar UID.

        Args:
            variant_id: ClinVar variation UID.

        Returns:
            Normalised variant dict, or ``None`` if not found.

        Raises:
            ExternalAPIError: on upstream failure with no cached copy.

        Implements:
            SRS FR-3.10.2 - Variant lookup
        """
        cache_key = f"variant_{variant_id}"

        async def fetch():
            variants = await self._esummary([variant_id])
            return variants[0] if variants else None

        return await self._cached_fetch(cache_key, self.CACHE_TTL_HOURS, fetch)

    async def search_variants(
        self,
        gene: str,
        significance: Optional[str] = None,
        retmax: int = 20,
    ) -> List[Dict]:
        """
        Search variants by gene, optionally filtered by clinical significance.

        Args:
            gene: Gene symbol (e.g. "BRCA1").
            significance: Optional clinical significance filter
                          (e.g. "pathogenic").
            retmax: Maximum number of variants to return.

        Returns:
            List of normalised variant dicts (possibly empty).

        Raises:
            ExternalAPIError: on upstream failure with no cached copy.

        Implements:
            SRS FR-3.10.2 - Variant search
        """
        cache_key = f"gene_{gene}_{significance or 'all'}_{retmax}"

        async def fetch():
            term = f"{gene}[gene]"
            if significance:
                term += f' AND "{significance}"[Clinical significance]'
            uids = await self._esearch(term, retmax=retmax)
            return await self._esummary(uids)

        return await self._cached_fetch(
            cache_key, self.CACHE_TTL_HOURS, fetch, empty=[]
        )

    async def get_variant_by_coordinates(
        self, chrom: str, pos: int, ref: str, alt: str, assembly: str = "GRCh38"
    ) -> Optional[Dict]:
        """
        Retrieve a variant by genomic coordinates (VCF-style).

        Args:
            chrom: Chromosome (e.g. "chr17" or "17").
            pos: 1-based genomic position.
            ref: Reference allele.
            alt: Alternate allele.
            assembly: Genome assembly for the position term.

        Returns:
            Normalised variant dict, or ``None`` if not found.

        Raises:
            ExternalAPIError: on upstream failure with no cached copy.
        """
        cache_key = f"coords_{assembly}_{chrom}_{pos}_{ref}_{alt}"
        chrom_num = chrom[3:] if chrom.lower().startswith("chr") else chrom

        async def fetch():
            term = (
                f"{chrom_num}[Chromosome] AND "
                f"{pos}[Base Position for Assembly {assembly}]"
            )
            uids = await self._esearch(term, retmax=5)
            variants = await self._esummary(uids)
            # Prefer an exact ref>alt match when available.
            for variant in variants:
                coords = variant.get("genomicCoordinates") or {}
                if (
                    coords.get("reference") == ref
                    and coords.get("alternate") == alt
                ):
                    return variant
            return variants[0] if variants else None

        return await self._cached_fetch(cache_key, self.CACHE_TTL_HOURS, fetch)

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_variant(doc: Dict) -> Dict:
        """Transform a ClinVar esummary docsum into our variant shape."""
        germline = doc.get("germline_classification") or {}

        # Genomic coordinates: prefer the current variation_loc entry.
        coords: Dict = {}
        canonical_spdi = None
        variation_set = doc.get("variation_set") or []
        if variation_set:
            vset = variation_set[0]
            canonical_spdi = vset.get("canonical_spdi") or None
            for loc in vset.get("variation_loc") or []:
                if loc.get("status") == "current":
                    coords = {
                        "assembly": loc.get("assembly_name"),
                        "chromosome": loc.get("chr"),
                        "start": loc.get("start"),
                        "stop": loc.get("stop"),
                        "reference": loc.get("ref") or None,
                        "alternate": loc.get("alt") or None,
                    }
                    break

        # SPDI encodes NC_...:pos:ref:alt - use it to fill ref/alt when the loc
        # entry omits them (common for the current assembly).
        if canonical_spdi and (not coords.get("reference") or not coords.get("alternate")):
            parts = canonical_spdi.split(":")
            if len(parts) == 4:
                if not coords.get("reference"):
                    coords["reference"] = parts[2] or None
                if not coords.get("alternate"):
                    coords["alternate"] = parts[3] or None

        return {
            "clinvarId": doc.get("uid"),
            "accession": doc.get("accession"),
            "variantName": doc.get("title"),
            "gene": doc.get("gene_sort"),
            "clinicalSignificance": germline.get("description"),
            "reviewStatus": germline.get("review_status"),
            "lastEvaluated": germline.get("last_evaluated"),
            "molecularConsequence": doc.get("molecular_consequence_list") or [],
            "proteinChange": doc.get("protein_change") or None,
            "variantType": doc.get("obj_type"),
            "canonicalSpdi": canonical_spdi,
            "genomicCoordinates": coords or None,
        }


if __name__ == "__main__":
    # Live self-test (requires network access).
    logging.basicConfig(level=logging.INFO)
    print("Testing ClinVar client (live)...")

    async def _main():
        client = ClinVarClient()
        try:
            print("\n1. Search variants for BRCA1:")
            variants = await client.search_variants("BRCA1", retmax=3)
            print(f"   Found {len(variants)} variants")
            for v in variants:
                print(f"   - {v['variantName']} => {v['clinicalSignificance']}")

            if variants:
                vid = variants[0]["clinvarId"]
                print(f"\n2. Get variant by ID ({vid}):")
                variant = await client.get_variant(vid)
                if variant:
                    print(f"   {variant['variantName']}")
                    print(f"   Coordinates: {variant['genomicCoordinates']}")
        finally:
            await client.aclose()

    asyncio.run(_main())
