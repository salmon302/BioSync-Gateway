# SPDX-License-Identifier: MIT
"""
OQ-17: Barcode Authenticity Validation
Implements SRS FR-3.3.4 / C5 — 8/10-base TruSeq/Nextera UDI authenticity.

Validates that:
1. The version-controlled manifest (database/seeds/illumina_udis_v1.0.0.json)
   contains sequences with min pairwise Hamming distance >= 3 within each set.
2. load_barcode_set() correctly resolves sets from the DB when available
   and falls back to built-in sets when not.
3. All sequences are valid DNA (ATCG only, correct length).
"""

import json
import os
import pytest

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "database", "seeds", "illumina_udis_v1.0.0.json"
)


class TestBarcodeAuthenticity:
    """Tests for FR-3.3.4 — authentic 8/10-base TruSeq/Nextera UDI sequences."""

    def test_manifest_exists(self):
        """The UDI manifest file must exist and be valid JSON."""
        assert os.path.exists(MANIFEST_PATH), f"Manifest not found at {MANIFEST_PATH}"
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        assert "barcode_sets" in manifest
        assert "manifest_version" in manifest

    def test_manifest_has_all_required_sets(self):
        """Manifest must contain TruSeq and Nextera 8/10-base sets."""
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        sets = manifest["barcode_sets"]
        required = {"TruSeq-8base", "TruSeq-10base", "Nextera-8base", "Nextera-10base"}
        assert required.issubset(set(sets.keys())), (
            f"Missing barcode sets: {required - set(sets.keys())}"
        )

    def test_all_sequences_valid_dna(self):
        """All sequences must be valid DNA (ATCG only) with correct length."""
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        for set_name, set_data in manifest["barcode_sets"].items():
            expected_len = set_data["sequence_length"]
            for idx_name, seq in set_data["indices"].items():
                assert len(seq) == expected_len, (
                    f"{set_name}/{idx_name}: length {len(seq)} != {expected_len}"
                )
                assert all(c in "ATCG" for c in seq), (
                    f"{set_name}/{idx_name}: invalid base in {seq}"
                )

    def test_min_hamming_distance_within_sets(self):
        """Each barcode set must maintain min pairwise Hamming distance >= 3."""
        from middleware.engine.barcode import validate_plate_indices

        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

        for set_name, set_data in manifest["barcode_sets"].items():
            indices = list(set_data["indices"].values())
            is_valid, violations = validate_plate_indices(indices, min_distance=3)
            assert is_valid, (
                f"{set_name} has {len(violations)} Hamming distance violations: "
                f"{violations[:3]}"
            )

    def test_min_hamming_distance_384_well_performance(self):
        """384-well plate validation (73,440 pairs) must complete < 500 ms."""
        import time
        from middleware.engine.barcode import validate_plate_indices

        # Use 384 unique 8-base barcodes from the manifest
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        ts8 = list(manifest["barcode_sets"]["TruSeq-8base"]["indices"].values())
        # Repeat to fill 384 wells (24 * 16 = 384)
        barcodes_384 = (ts8 * 16)[:384]

        start = time.perf_counter()
        is_valid, violations = validate_plate_indices(barcodes_384, min_distance=3)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # With duplicates, there will be violations, but it should be fast
        assert elapsed_ms < 500, (
            f"384-well validation took {elapsed_ms:.1f}ms (target < 500ms)"
        )

    def test_load_barcode_set_fallback(self):
        """load_barcode_set() must return built-in TruSeq set when DB unavailable."""
        from middleware.engine.barcode import load_barcode_set, TRUSEQ_BARCODES

        result = load_barcode_set("TruSeq")
        assert result == TRUSEQ_BARCODES

    def test_load_barcode_set_unknown_raises(self):
        """load_barcode_set() must raise ValueError for unknown sets."""
        from middleware.engine.barcode import load_barcode_set

        with pytest.raises(ValueError, match="Unknown barcode set"):
            load_barcode_set("NonExistentSet-999")

    def test_truseq_barcodes_are_8base(self):
        """Built-in TruSeq barcodes must be 8-base (FR-3.3.4)."""
        from middleware.engine.barcode import TRUSEQ_BARCODES

        for name, seq in TRUSEQ_BARCODES.items():
            assert len(seq) == 8, f"TruSeq {name} is {len(seq)}-base, expected 8"
            assert all(c in "ATCG" for c in seq), f"TruSeq {name} has invalid base: {seq}"

    def test_manifest_authenticity_is_explicit(self):
        """FR-3.3.4 authenticity status must be declared, never implicit."""
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        assert "authentic" in manifest, "Manifest must declare an 'authentic' boolean"
        assert manifest["authentic"] is False, (
            "Sequences are generated placeholders (Illumina doc 1000000002694 "
            "was unavailable); 'authentic' must remain false until official "
            "sequences are ingested per 'ingestion_procedure'."
        )

    def test_authenticity_not_falsely_claimed(self):
        """
        Guardrail: if 'authentic' is true it MUST be backed by a verified
        reference file. Prevents silently claiming real Illumina sequences
        (FR-3.3.4 / C5 safety requirement).
        """
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        if manifest.get("authentic") is not True:
            pytest.skip("Manifest is honestly marked non-authentic")

        reference_path = os.path.join(
            os.path.dirname(MANIFEST_PATH), "illumina_udis_reference.json"
        )
        assert os.path.exists(reference_path), (
            "authentic=true requires a verified reference file: "
            "database/seeds/illumina_udis_reference.json"
        )
        with open(reference_path) as f:
            reference = json.load(f)
        for set_name, set_data in manifest["barcode_sets"].items():
            ref_set = reference["barcode_sets"][set_name]["indices"]
            assert set(set_data["indices"].values()) == set(ref_set.values()), (
                f"{set_name} does not match the verified reference"
            )
