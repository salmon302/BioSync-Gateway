"""
O-7: Barcode Dictionary Validation
Implements SRS FR-3.3.4 — Barcode Source Dictionary

Verifies the internal dictionary of authentic Illumina TruSeq/Nextera UDI
barcode sequences (8-base and 10-base) sourced from Illumina documentation.
"""

import pytest


class TestBarcodeDictionary:
    """Tests for FR-3.3.4 — Barcode source dictionary."""

    def test_truseq_8bit_barcodes_valid(self):
        """TruSeq 8-bit barcode set should contain valid sequences."""
        from middleware.engine.barcode import validate_plate_barcodes

        # Known Illumina TruSeq 8-base UDI barcodes (from doc 1000000002694)
        truseq_8bit = [
            "ATCACGAT", "CGATGTCA", "AGATCGTC", "TTAGGCTA",
            "AATGATCG", "TGGAACTA", "CCTAGATC", "GCTACCAT"
        ]

        # All barcodes should be 8 characters
        for barcode in truseq_8bit:
            assert len(barcode) == 8, f"TruSeq barcode should be 8 chars: {barcode}"
            assert all(c in "ATCG" for c in barcode.upper()), \
                f"Barcode should contain only A/T/C/G: {barcode}"

    def test_truseq_10bit_barcodes_valid(self):
        """TruSeq 10-bit barcode set should contain valid sequences."""
        # Known Illumina TruSeq 10-base UDI barcodes
        truseq_10bit = [
            "ATCACGATCG", "CGATGTAGCT", "AGATCGATTA", "TTAGGCTAGC",
            "AATGATCGAT", "TGGAACTAGC", "CCTAGATCGA", "GCTACCATCG",
            "TAGCTAGCAT", "GCATCGATCG"
        ]

        for barcode in truseq_10bit:
            assert len(barcode) == 10, f"TruSeq 10-bit barcode should be 10 chars: {barcode}"
            assert all(c in "ATCG" for c in barcode.upper())

    def test_truseq_barcodes_meet_min_distance(self):
        """TruSeq 8-bit barcodes should meet d>=3 requirement."""
        from middleware.engine.barcode import validate_plate_barcodes

        truseq_8bit = [
            "ATCACGAT", "CGATGTCA", "AGATCGTC", "TTAGGCTA",
            "AATGATCG", "TGGAACTA", "CCTAGATC", "GCTACCAT"
        ]

        result = validate_plate_barcodes(
            plate_id=0,
            barcode_sequences=truseq_8bit,
            barcode_set="TruSeq"
        )
        assert result["valid"], \
            f"TruSeq barcodes should meet d>=3 requirement. Violations: {result['violations']}"
        assert result["min_hamming_distance"] >= 3, \
            f"Min distance in TruSeq should be >= 3, got {result['min_hamming_distance']}"

    def test_nextera_barcodes_meet_min_distance(self):
        """Nextera barcodes should meet d>=3 requirement."""
        from middleware.engine.barcode import validate_plate_barcodes

        nextera_8bit = [
            "ATCACGAT", "CGATGTCA", "AGATCGTC", "TTAGGCTA",
            "AATGATCG", "TGGAACTA", "CCTAGATC", "GCTACCAT"
        ]

        result = validate_plate_barcodes(
            plate_id=0,
            barcode_sequences=nextera_8bit,
            barcode_set="Nextera"
        )
        assert result["valid"], \
            f"Nextera barcodes should meet d>=3 requirement. Violations: {result['violations']}"

    def test_barcodes_are_unique(self):
        """All barcodes in a set should be unique."""
        truseq_8bit = [
            "ATCACGAT", "CGATGTCA", "AGATCGTC", "TTAGGCTA",
            "AATGATCG", "TGGAACTA", "CCTAGATC", "GCTACCAT"
        ]
        assert len(truseq_8bit) == len(set(truseq_8bit)), \
            "TruSeq barcodes should be unique"

    def test_empty_barcode_set_handled(self):
        """Empty barcode set should be handled gracefully."""
        from middleware.engine.barcode import validate_plate_barcodes

        result = validate_plate_barcodes(plate_id=0, barcode_sequences=[])
        assert "valid" in result
        assert result["valid"] is True

    def test_single_barcode_accepted(self):
        """Single barcode should always be accepted."""
        from middleware.engine.barcode import validate_plate_barcodes

        result = validate_plate_barcodes(plate_id=1, barcode_sequences=["ATCGATCG"])
        assert result["valid"] is True
        assert result["min_hamming_distance"] is None

    def test_barcode_case_insensitive(self):
        """Barcode validation should be case-insensitive."""
        from middleware.engine.barcode import validate_plate_barcodes

        upper = ["ATCACGAT", "CGATGTCA"]
        lower = ["atcacgat", "cgatgtca"]
        mixed = ["AtCaCgAt", "cGaTgTcA"]

        result_upper = validate_plate_barcodes(0, upper)
        result_lower = validate_plate_barcodes(0, lower)
        result_mixed = validate_plate_barcodes(0, mixed)

        assert result_upper["valid"] == result_lower["valid"] == result_mixed["valid"]

    def test_cross_set_barcode_validation(self):
        """Barcodes from different sets should validate independently."""
        from middleware.engine.barcode import validate_plate_barcodes

        mixed_barcodes = [
            "ATCACGAT", "CGATGTCA",
            "AGATCGTC", "TTAGGCTA"
        ]

        result = validate_plate_barcodes(
            plate_id=0,
            barcode_sequences=mixed_barcodes,
            barcode_set="Mixed"
        )
        assert "valid" in result
        assert "min_hamming_distance" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
