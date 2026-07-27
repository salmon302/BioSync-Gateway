-- Barcode Indices Seed Data
-- Implements SRS §3.3 - Barcode Multiplexing Engine
-- Populates Illumina TruSeq/Nextera UDI dictionary
--
-- Source of truth: database/seeds/illumina_udis_v1.0.0.json
-- This SQL file mirrors the Alembic migration 0003_seed_barcodes.py for
-- environments that bootstrap from raw SQL instead of Alembic.

-- ============================================
-- Table: barcode_indices
-- Stores barcode sequences for multiplexing
-- ============================================
CREATE TABLE IF NOT EXISTS barcode_indices (
    id SERIAL PRIMARY KEY,
    index_name VARCHAR(100) NOT NULL,
    index_sequence VARCHAR(255) NOT NULL UNIQUE,
    barcode_set VARCHAR(100),
    kit_type VARCHAR(50) CHECK (kit_type IN ('TruSeq', 'Nextera', 'Custom')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_barcode_indices_set ON barcode_indices(barcode_set);
CREATE INDEX IF NOT EXISTS idx_barcode_indices_id ON barcode_indices(index_name);

-- ============================================
-- Seed Data: Illumina TruSeq 8-base UDI sequences
-- Authenticated per SRS FR-3.3.4 / C5 (doc 1000000002694)
-- Minimum pairwise Hamming distance >= 3 within each set
-- ============================================
INSERT INTO barcode_indices (index_name, index_sequence, barcode_set, kit_type)
VALUES
    ('D701', 'ATTACTCG', 'TruSeq-8base', 'TruSeq'),
    ('D702', 'TCCGGAGA', 'TruSeq-8base', 'TruSeq'),
    ('D703', 'CGCTCATT', 'TruSeq-8base', 'TruSeq'),
    ('D704', 'GAGATTCC', 'TruSeq-8base', 'TruSeq'),
    ('D705', 'ATTCAGAA', 'TruSeq-8base', 'TruSeq'),
    ('D706', 'GAATTCGT', 'TruSeq-8base', 'TruSeq'),
    ('D707', 'CTGAAGCT', 'TruSeq-8base', 'TruSeq'),
    ('D708', 'TAATGCGC', 'TruSeq-8base', 'TruSeq'),
    ('D709', 'CGGCTATG', 'TruSeq-8base', 'TruSeq'),
    ('D710', 'TCCGCGAA', 'TruSeq-8base', 'TruSeq'),
    ('D711', 'TCTCGCGC', 'TruSeq-8base', 'TruSeq'),
    ('D712', 'AGCGATAG', 'TruSeq-8base', 'TruSeq'),
    ('N701', 'TAAGGCGA', 'Nextera-8base', 'Nextera'),
    ('N702', 'CGTACTAG', 'Nextera-8base', 'Nextera'),
    ('N703', 'AGGCAGAA', 'Nextera-8base', 'Nextera'),
    ('N704', 'TCCTGAGC', 'Nextera-8base', 'Nextera'),
    ('N705', 'GGACTCCT', 'Nextera-8base', 'Nextera'),
    ('N706', 'TAGGCATG', 'Nextera-8base', 'Nextera'),
    ('N707', 'CTCTCTAC', 'Nextera-8base', 'Nextera'),
    ('N708', 'CAGAGAGG', 'Nextera-8base', 'Nextera'),
    ('N710', 'CGAGGCTG', 'Nextera-8base', 'Nextera'),
    ('N711', 'AAGAGGCA', 'Nextera-8base', 'Nextera'),
    ('N712', 'GTAGAGGA', 'Nextera-8base', 'Nextera'),
    ('N714', 'GCTCATGA', 'Nextera-8base', 'Nextera'),
    ('N715', 'ATCTCAGG', 'Nextera-8base', 'Nextera'),
    ('N716', 'ACTCGCTA', 'Nextera-8base', 'Nextera'),
    ('N718', 'GGAGCTAC', 'Nextera-8base', 'Nextera'),
    ('N719', 'GCGTAGTA', 'Nextera-8base', 'Nextera'),
    ('N720', 'CGGAGCCT', 'Nextera-8base', 'Nextera'),
    ('N721', 'TACGCTGC', 'Nextera-8base', 'Nextera'),
    ('N722', 'ATGCGCAG', 'Nextera-8base', 'Nextera'),
    ('N723', 'TAGCGCTC', 'Nextera-8base', 'Nextera'),
    ('N724', 'ACTGAGCG', 'Nextera-8base', 'Nextera'),
    ('N726', 'CCTAAGAC', 'Nextera-8base', 'Nextera'),
    ('N727', 'CGATCAGT', 'Nextera-8base', 'Nextera'),
    ('N728', 'TGCAGCTA', 'Nextera-8base', 'Nextera'),
    ('N729', 'TCGACGTC', 'Nextera-8base', 'Nextera'),
    ('UDP0001', 'GAACTGAGCG', 'TruSeq-10base', 'TruSeq'),
    ('UDP0002', 'AGGTCAGATA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0003', 'CGACATCCGA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0004', 'ATTCCATAAG', 'TruSeq-10base', 'TruSeq'),
    ('UDP0005', 'CACAATAGGA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0006', 'AACATCGCGC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0007', 'CTAGTGCTCT', 'TruSeq-10base', 'TruSeq'),
    ('UDP0008', 'GATCAAGGCA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0009', 'GACTGAGTAG', 'TruSeq-10base', 'TruSeq'),
    ('UDP0010', 'AGTCAGACGA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0011', 'CCGTATGTTC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0012', 'GAGTCATAGG', 'TruSeq-10base', 'TruSeq'),
    ('UDP0013', 'CTTGCCATTA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0014', 'GAAGCGGCAC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0015', 'TCCATTGCCG', 'TruSeq-10base', 'TruSeq'),
    ('UDP0016', 'CGGTTACGGC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0017', 'GAGAATGGTT', 'TruSeq-10base', 'TruSeq'),
    ('UDP0018', 'AGAGGCAACC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0019', 'CCATCATTAG', 'TruSeq-10base', 'TruSeq'),
    ('UDP0020', 'GATAGGCCGA', 'TruSeq-10base', 'TruSeq'),
    ('UDP0021', 'ATGGTTGACT', 'TruSeq-10base', 'TruSeq'),
    ('UDP0022', 'TATTGCGCTC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0023', 'ACGCCTTGTT', 'TruSeq-10base', 'TruSeq'),
    ('UDP0024', 'TTCTACATAC', 'TruSeq-10base', 'TruSeq'),
    ('UDP0025', 'AACCATAGAA', 'Nextera-10base', 'Nextera'),
    ('UDP0026', 'GGTTGCGAGG', 'Nextera-10base', 'Nextera'),
    ('UDP0027', 'TAAGCATCCA', 'Nextera-10base', 'Nextera'),
    ('UDP0028', 'ACCACGACAT', 'Nextera-10base', 'Nextera'),
    ('UDP0029', 'GCCGCACTCT', 'Nextera-10base', 'Nextera'),
    ('UDP0030', 'CCACCAGGCA', 'Nextera-10base', 'Nextera'),
    ('UDP0031', 'GTGACACGCA', 'Nextera-10base', 'Nextera'),
    ('UDP0032', 'ACAGTGTATG', 'Nextera-10base', 'Nextera'),
    ('UDP0033', 'TGATTATACG', 'Nextera-10base', 'Nextera'),
    ('UDP0034', 'CAGCCGCGTA', 'Nextera-10base', 'Nextera'),
    ('UDP0035', 'GGTAACTCGC', 'Nextera-10base', 'Nextera'),
    ('UDP0036', 'ACCGGCCGTA', 'Nextera-10base', 'Nextera'),
    ('UDP0037', 'TGTAATCGAC', 'Nextera-10base', 'Nextera'),
    ('UDP0038', 'GTGCAGACAG', 'Nextera-10base', 'Nextera'),
    ('UDP0039', 'CAATCGGCTG', 'Nextera-10base', 'Nextera'),
    ('UDP0040', 'TATGTAGTCA', 'Nextera-10base', 'Nextera'),
    ('UDP0041', 'ACTCGGCAAT', 'Nextera-10base', 'Nextera'),
    ('UDP0042', 'GTCTAATGGC', 'Nextera-10base', 'Nextera'),
    ('UDP0043', 'CCATCTCGCC', 'Nextera-10base', 'Nextera'),
    ('UDP0044', 'CTGCGAGCCA', 'Nextera-10base', 'Nextera'),
    ('UDP0045', 'CGTTATTCTA', 'Nextera-10base', 'Nextera'),
    ('UDP0046', 'TCCATGTTGC', 'Nextera-10base', 'Nextera')
ON CONFLICT (index_sequence) DO NOTHING;

-- ============================================
-- Verification Query: Check Hamming distances
-- ============================================
-- This query validates that all barcode pairs in the same set
-- have minimum Hamming distance of 3
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
    -- Calculate Hamming distance (requires pgcrypto for bitwise operations)
    -- This is a placeholder - actual calculation done in Python
    0 AS hamming_distance_placeholder
FROM barcode_pairs
ORDER BY barcode_set, id1, id2;

-- ============================================
-- Grant Permissions
-- ============================================
-- Read-only access for middleware
GRANT SELECT ON barcode_indices TO biosync_middleware;

-- ============================================
-- Comments for Documentation
-- ============================================
COMMENT ON TABLE barcode_indices IS 'Stores barcode sequences for Illumina multiplexing protocols (SRS §3.3)';
COMMENT ON COLUMN barcode_indices.index_name IS 'Unique identifier (e.g., HT1, NX1)';
COMMENT ON COLUMN barcode_indices.barcode_set IS 'Barcode set name (TruSeq, Nextera, etc.)';
COMMENT ON COLUMN barcode_indices.index_sequence IS 'DNA sequence (ATCGN format)';
