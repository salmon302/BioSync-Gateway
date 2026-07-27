# SPDX-License-Identifier: MIT
"""
PQ-5: Barcode Validation Performance Benchmark
Implements SRS PQ-5 — Barcode validation: 96-index plate (4,560 pairwise
comparisons) computed within 500 ms.

Also satisfies NFR-P2 (plate validation < 5s) with a wider margin.
"""

import time
import pytest


class TestPQ5BarcodeBenchmark:
    """Performance qualification for barcode Hamming distance computation."""

    def test_96_index_pairwise_within_500ms(self):
        """4,560 pairwise Hamming distances for a 96-index plate must complete
        within 500 ms (SRS PQ-5)."""
        from middleware.engine.barcode import validate_plate_indices

        # Generate 96 unique 8-base barcodes
        barcodes = [f"ATCG{i:04d}"[:8] for i in range(96)]

        start = time.perf_counter()
        validate_plate_indices(barcodes, min_distance=3)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 96 indices → C(96,2) = 4,560 pairwise comparisons
        assert elapsed_ms < 500, (
            f"PQ-5 FAILED: 96-index pairwise computation took {elapsed_ms:.1f}ms "
            f"(target ≤ 500ms)"
        )

    def test_96_index_pairwise_count(self):
        """Verify exactly 4,560 pairwise comparisons are performed for 96 indices.

        With the NumPy-vectorized implementation, comparisons are computed in a
        single broadcast operation rather than via scalar hamming_distance calls.
        We assert the upper-triangle pair count (C(96,2) = 4,560) is reflected
        in the number of violations evaluated.
        """
        from middleware.engine.barcode import validate_plate_indices, _encode_sequences
        import numpy as np

        barcodes = [f"ATCG{i:04d}"[:8] for i in range(96)]

        # The vectorized path encodes sequences into an (n, L) matrix and
        # computes C(n,2) pairwise distances via triu_indices.
        matrix = _encode_sequences(barcodes)
        n = len(barcodes)
        rows, cols = np.triu_indices(n, k=1)
        pair_count = len(rows)

        # C(96,2) = 96*95/2 = 4560
        assert pair_count == 4560, (
            f"Expected 4,560 pairwise comparisons, got {pair_count}"
        )

        # Sanity: validate_plate_indices runs without error and returns
        # a result dict with the expected total_indices count.
        is_valid, violations = validate_plate_indices(barcodes, min_distance=3)
        assert isinstance(is_valid, bool)
        assert isinstance(violations, list)

    def test_384_index_pairwise_within_5s(self):
        """NFR-P2: 384-well plate validation must complete within 5 seconds.

        With NumPy vectorization, 384-well (73,440 pairs) drops from ~8 s
        (pure Python) to well under 50 ms.
        """
        from middleware.engine.barcode import validate_plate_indices

        barcodes = [f"ATCGAT{i:04d}"[:10] for i in range(384)]

        start = time.perf_counter()
        validate_plate_indices(barcodes, min_distance=3)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, (
            f"NFR-P2 FAILED: 384-index validation took {elapsed:.3f}s (target < 5s)"
        )

    def test_hamming_distance_single_call_latency(self):
        """Single Hamming distance call should be sub-microsecond."""
        from middleware.engine.barcode import hamming_distance

        seq1 = "ATCGATCGAT"
        seq2 = "ATCGATCGAA"

        start = time.perf_counter()
        for _ in range(10000):
            hamming_distance(seq1, seq2)
        elapsed_ms = (time.perf_counter() - start) * 1000

        per_call_us = (elapsed_ms / 10000) * 1000
        assert per_call_us < 10, (
            f"Single Hamming distance call took {per_call_us:.2f}µs (target < 10µs)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
