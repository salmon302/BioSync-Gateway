"""
PQ-3: Barcode Computation Performance
Implements SRS NFR-P2 — Plate Validation < 5s

Benchmarks barcode pairwise Hamming distance computation performance.
"""

import pytest
import time


class TestBarcodePerformance:
    """Tests for NFR-P2 — Plate validation < 5s."""

    def test_96_well_barcode_computation(self):
        """96-well plate barcode validation should complete within 5 seconds."""
        from middleware.engine.barcode import validate_plate_barcodes

        # Generate 96 unique barcodes (8-base)
        barcodes = []
        for i in range(96):
            # Create unique 8-base barcodes
            barcode = f"ATCG{'{:04d}'.format(i)}"[:8]
            barcodes.append(barcode)

        start = time.perf_counter()
        result = validate_plate_barcodes(
            plate_id=1,
            barcode_sequences=barcodes,
            barcode_set="TruSeq"
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"96-well validation took {elapsed:.3f}s (target < 5s)"
        assert "valid" in result
        assert "min_hamming_distance" in result

    def test_384_well_barcode_computation(self):
        """384-well plate barcode validation should complete within 30 seconds."""
        from middleware.engine.barcode import validate_plate_barcodes

        # Generate 384 unique barcodes (10-base)
        barcodes = []
        for i in range(384):
            barcode = f"ATCGAT{'{:04d}'.format(i)}"[:10]
            barcodes.append(barcode)

        start = time.perf_counter()
        result = validate_plate_barcodes(
            plate_id=2,
            barcode_sequences=barcodes,
            barcode_set="Nextera"
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 30.0, f"384-well validation took {elapsed:.3f}s (target < 30s)"

    def test_hamming_distance_1000_sequences(self):
        """Hamming distance on 1000 sequences should complete quickly."""
        from middleware.engine.barcode import validate_plate_indices

        # Generate 1000 barcodes
        barcodes = [f"ATCG{'{:06d}'.format(i)}"[:8] for i in range(1000)]

        start = time.perf_counter()
        is_valid, violations = validate_plate_indices(barcodes, min_distance=3)
        elapsed = time.perf_counter() - start

        assert elapsed < 30.0, f"1000-sequence validation took {elapsed:.3f}s"

    def test_valid_plate_fast(self):
        """Valid plate (d>=3) should validate quickly."""
        from middleware.engine.barcode import validate_plate_barcodes

        # Known valid TruSeq barcodes
        barcodes = [
            "ATCACGAT", "CGATGTCA", "AGATCGTC", "TTAGGCTA",
            "AATGATCG", "TGGAACTA", "CCTAGATC", "GCTACCAT"
        ]

        start = time.perf_counter()
        result = validate_plate_barcodes(0, barcodes)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"Valid plate validation took {elapsed:.3f}s"
        assert result["valid"] is True

    def test_invalid_plate_detection_speed(self):
        """Invalid plate (d<3) should be detected quickly."""
        from middleware.engine.barcode import validate_plate_barcodes

        # Invalid barcodes with d=1
        barcodes = ["ATCGATCG", "ATCGATCC", "ATCGATCA"]

        start = time.perf_counter()
        result = validate_plate_barcodes(0, barcodes)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"Invalid plate detection took {elapsed:.3f}s"
        assert result["valid"] is False
        assert len(result["violations"]) > 0

    def test_single_barcode_instant(self):
        """Single barcode validation should be instant."""
        from middleware.engine.barcode import validate_plate_barcodes

        start = time.perf_counter()
        result = validate_plate_barcodes(0, ["ATCGATCG"])
        elapsed = time.perf_counter() - start

        assert elapsed < 0.01, f"Single barcode took {elapsed*1000:.3f}ms"
        assert result["valid"] is True

    def test_empty_plate_instant(self):
        """Empty plate validation should be instant."""
        from middleware.engine.barcode import validate_plate_barcodes

        start = time.perf_counter()
        result = validate_plate_barcodes(0, [])
        elapsed = time.perf_counter() - start

        assert elapsed < 0.01, f"Empty plate took {elapsed*1000:.3f}ms"
        assert result["valid"] is True

    def test_barcode_validation_scalability(self):
        """Validation time should scale reasonably with plate size."""
        from middleware.engine.barcode import validate_plate_indices

        sizes = [16, 32, 64, 96]
        times = []

        for size in sizes:
            barcodes = [f"ATCG{'{:06d}'.format(i)}"[:8] for i in range(size)]

            start = time.perf_counter()
            validate_plate_indices(barcodes, min_distance=3)
            elapsed = time.perf_counter() - start

            times.append(elapsed)

        # Time should increase but not exponentially
        # O(n^2) pairwise comparison is expected
        assert times[-1] > times[0], "Larger plates should take longer"
        # Allow up to 100x scaling for O(n^2) behavior
        assert times[-1] < times[0] * 100, \
            f"Time scaling {times[-1]/times[0]:.1f}x is too high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
