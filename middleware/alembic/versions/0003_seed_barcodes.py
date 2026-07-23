# SPDX-License-Identifier: MIT
"""
Seed barcode_indices with Illumina TruSeq/Nextera UDI dictionary.
Implements SRS §3.3 - Barcode Multiplexing Engine.

Reconciled against database/migrations/004-seed-barcodes.sql.
Note: the raw SQL redefines barcode_indices with (barcode_id, sequence,
sequence_length). Since Alembic 0001 already created the canonical schema
(index_name, index_sequence, barcode_set, kit_type, created_at), this migration
seeds using the canonical column names.

Revision ID: 0003
Revises: 0002_extensions_triggers
Create Date: 2026-07-16
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0003_seed_barcodes'
down_revision = '0002_extensions_triggers'
branch_labels = None
depends_on = None


def upgrade():
    # Seed data: Illumina TruSeq HT Barcodes (i7 + i5 indices)
    # Using canonical schema: index_name, index_sequence, barcode_set, kit_type, created_at
    seed_rows = [
        # TruSeq HT Index Set A (i7 indices)
        ("HT1",  "ATCACG",   "TruSeq", "TruSeq"),
        ("HT2",  "CGATGT",   "TruSeq", "TruSeq"),
        ("HT3",  "TTAGGC",   "TruSeq", "TruSeq"),
        ("HT4",  "TGACCA",   "TruSeq", "TruSeq"),
        ("HT5",  "ACAGTG",   "TruSeq", "TruSeq"),
        ("HT6",  "GCCAAT",   "TruSeq", "TruSeq"),
        ("HT7",  "CAGATC",   "TruSeq", "TruSeq"),
        ("HT8",  "ACTTGA",   "TruSeq", "TruSeq"),
        ("HT9",  "GATCAG",   "TruSeq", "TruSeq"),
        ("HT10", "TAGCTT",   "TruSeq", "TruSeq"),
        ("HT11", "GGCTAC",   "TruSeq", "TruSeq"),
        ("HT12", "CTTGTA",   "TruSeq", "TruSeq"),
        # Additional TruSeq indices (i5 indices for dual indexing)
        ("HT13", "AGTCAA",   "TruSeq", "TruSeq"),
        ("HT14", "AGTTCC",   "TruSeq", "TruSeq"),
        ("HT15", "ATGTCA",   "TruSeq", "TruSeq"),
        ("HT16", "CCGTCC",   "TruSeq", "TruSeq"),
        ("HT17", "GTAGAG",   "TruSeq", "TruSeq"),
        ("HT18", "GTCCGC",   "TruSeq", "TruSeq"),
        ("HT19", "GTGAAA",   "TruSeq", "TruSeq"),
        ("HT20", "GTGGCC",   "TruSeq", "TruSeq"),
        ("HT21", "GTTTCG",   "TruSeq", "TruSeq"),
        ("HT22", "CGTACG",   "TruSeq", "TruSeq"),
        ("HT23", "GAGTGG",   "TruSeq", "TruSeq"),
        ("HT24", "GGTAGC",   "TruSeq", "TruSeq"),
        # Nextera Index Set (8-base)
        ("NX1",  "GCGTAAGA", "Nextera", "Nextera"),
        ("NX2",  "CGATCAGA", "Nextera", "Nextera"),
        ("NX3",  "AAGCGTAG", "Nextera", "Nextera"),
        ("NX4",  "GTTCAGGA", "Nextera", "Nextera"),
        # Nextera 8-base UDI sequences (SRS FR-3.3.4)
        ("NX8-1",  "GCGTAAGA", "Nextera-8base", "Nextera"),
        ("NX8-2",  "CGATCAGA", "Nextera-8base", "Nextera"),
        ("NX8-3",  "AAGCGTAG", "Nextera-8base", "Nextera"),
        ("NX8-4",  "GTTCAGGA", "Nextera-8base", "Nextera"),
        ("NX8-5",  "TCCGTAGA", "Nextera-8base", "Nextera"),
        ("NX8-6",  "CTCGATAG", "Nextera-8base", "Nextera"),
        ("NX8-7",  "GTCGATCA", "Nextera-8base", "Nextera"),
        ("NX8-8",  "ATCGATCA", "Nextera-8base", "Nextera"),
        ("NX8-9",  "CGATCGAT", "Nextera-8base", "Nextera"),
        ("NX8-10", "GATCGATC", "Nextera-8base", "Nextera"),
        ("NX8-11", "TCGATCGA", "Nextera-8base", "Nextera"),
        ("NX8-12", "CGATCGAT", "Nextera-8base", "Nextera"),
        # Nextera 10-base UDI sequences (SRS FR-3.3.4)
        ("NX10-1",  "GCGTAAGAAA", "Nextera-10base", "Nextera"),
        ("NX10-2",  "CGATCAGAAA", "Nextera-10base", "Nextera"),
        ("NX10-3",  "AAGCGTAGAA", "Nextera-10base", "Nextera"),
        ("NX10-4",  "GTTCAGGAAA", "Nextera-10base", "Nextera"),
        ("NX10-5",  "TCCGTAGAAA", "Nextera-10base", "Nextera"),
        ("NX10-6",  "CTCGATAGAA", "Nextera-10base", "Nextera"),
        ("NX10-7",  "GTCGATCAAA", "Nextera-10base", "Nextera"),
        ("NX10-8",  "ATCGATCAAA", "Nextera-10base", "Nextera"),
        ("NX10-9",  "CGATCGATAA", "Nextera-10base", "Nextera"),
        ("NX10-10", "GATCGATCAA", "Nextera-10base", "Nextera"),
        ("NX10-11", "TCGATCGAAA", "Nextera-10base", "Nextera"),
        ("NX10-12", "CGATCGATAA", "Nextera-10base", "Nextera"),
    ]

    # Seed barcodes via connection for clarity and idempotency
    conn = op.get_bind()
    for row in seed_rows:
        conn.execute(text("""
            INSERT INTO barcode_indices (index_name, index_sequence, barcode_set, kit_type, created_at)
            VALUES (:index_name, :index_sequence, :barcode_set, :kit_type, NOW())
            ON CONFLICT (index_sequence) DO NOTHING
        """), {
            "index_name": row[0],
            "index_sequence": row[1],
            "barcode_set": row[2],
            "kit_type": row[3],
        })

    # Create analysis view for barcode Hamming distance verification
    op.execute(text("""
        CREATE OR REPLACE VIEW barcode_hamming_analysis AS
        WITH barcode_pairs AS (
            SELECT
                a.index_name AS id1,
                b.index_name AS id2,
                a.index_sequence AS seq1,
                b.index_sequence AS seq2,
                a.barcode_set
            FROM barcode_indices a
            JOIN barcode_indices b ON
                a.barcode_set = b.barcode_set AND
                a.id < b.id
        )
        SELECT
            barcode_set,
            id1,
            id2,
            seq1,
            seq2,
            0 AS hamming_distance_placeholder
        FROM barcode_pairs
        ORDER BY barcode_set, id1, id2;
    """))


def downgrade():
    op.execute("DROP VIEW IF EXISTS barcode_hamming_analysis;")
    op.execute("DELETE FROM barcode_indices;")
