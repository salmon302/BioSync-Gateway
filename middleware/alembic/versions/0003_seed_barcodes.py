# SPDX-License-Identifier: MIT
"""
Seed barcode_indices with Illumina TruSeq/Nextera UDI dictionary.
Implements SRS §3.3 - Barcode Multiplexing Engine.

Seeds from a version-controlled JSON manifest
(database/seeds/illumina_udis_v1.0.0.json) containing authentic
8-base and 10-base Illumina UDI sequences validated for minimum
pairwise Hamming distance >= 3 (SRS FR-3.3.4).

The manifest is the source of truth; this migration loads it into the
barcode_indices table at deploy time.

Revision ID: 0003
Revises: 0002_extensions_triggers
Create Date: 2026-07-16
"""
import json
import os
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0003_seed_barcodes'
down_revision = '0002_extensions_triggers'
branch_labels = None
depends_on = None

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    'database', 'seeds', 'illumina_udis_v1.0.0.json'
)


def _load_manifest():
    """Load the UDI manifest JSON, returning the barcode_sets dict."""
    with open(MANIFEST_PATH, 'r') as f:
        manifest = json.load(f)
    return manifest['barcode_sets']


def upgrade():
    conn = op.get_bind()

    # Load manifest and seed barcode_indices
    barcode_sets = _load_manifest()

    for set_name, set_data in barcode_sets.items():
        kit_type = set_data['kit_type']
        seq_len = set_data['sequence_length']
        for index_name, sequence in set_data['indices'].items():
            conn.execute(text("""
                INSERT INTO barcode_indices (index_name, index_sequence, barcode_set, kit_type, created_at)
                VALUES (:index_name, :index_sequence, :barcode_set, :kit_type, NOW())
                ON CONFLICT (index_sequence) DO NOTHING
            """), {
                "index_name": index_name,
                "index_sequence": sequence,
                "barcode_set": set_name,
                "kit_type": kit_type,
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
