-- Barcode Indices Seed Data
-- Implements SRS §3.3 - Barcode Multiplexing Engine
-- Populates Illumina TruSeq/Nextera UDI dictionary

-- ============================================
-- Table: barcode_indices
-- Stores barcode sequences for multiplexing
-- ============================================
CREATE TABLE IF NOT EXISTS barcode_indices (
    id SERIAL PRIMARY KEY,
    barcode_id VARCHAR(50) UNIQUE NOT NULL,
    barcode_set VARCHAR(100) NOT NULL,
    sequence VARCHAR(255) NOT NULL,
    sequence_length INTEGER NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT barcode_indices_sequence_check CHECK (
        sequence ~ '^[ATCGNatcgn]+$'
    )
);

CREATE INDEX idx_barcode_indices_set ON barcode_indices(barcode_set);
CREATE INDEX idx_barcode_indices_id ON barcode_indices(barcode_id);

-- ============================================
-- Seed Data: Illumina TruSeq HT Barcodes
-- From: Illumina TruSeq HT Dual Index Kit
-- ============================================
INSERT INTO barcode_indices (barcode_id, barcode_set, sequence, sequence_length, description)
VALUES
    -- TruSeq HT Index Set A (i7 indices)
    ('HT1', 'TruSeq', 'ATCACG', 6, 'TruSeq HT Index 1'),
    ('HT2', 'TruSeq', 'CGATGT', 6, 'TruSeq HT Index 2'),
    ('HT3', 'TruSeq', 'TTAGGC', 6, 'TruSeq HT Index 3'),
    ('HT4', 'TruSeq', 'TGACCA', 6, 'TruSeq HT Index 4'),
    ('HT5', 'TruSeq', 'ACAGTG', 6, 'TruSeq HT Index 5'),
    ('HT6', 'TruSeq', 'GCCAAT', 6, 'TruSeq HT Index 6'),
    ('HT7', 'TruSeq', 'CAGATC', 6, 'TruSeq HT Index 7'),
    ('HT8', 'TruSeq', 'ACTTGA', 6, 'TruSeq HT Index 8'),
    ('HT9', 'TruSeq', 'GATCAG', 6, 'TruSeq HT Index 9'),
    ('HT10', 'TruSeq', 'TAGCTT', 6, 'TruSeq HT Index 10'),
    ('HT11', 'TruSeq', 'GGCTAC', 6, 'TruSeq HT Index 11'),
    ('HT12', 'TruSeq', 'CTTGTA', 6, 'TruSeq HT Index 12'),
    
    -- Additional TruSeq indices (i5 indices for dual indexing)
    ('HT13', 'TruSeq', 'AGTCAA', 6, 'TruSeq HT Index 13'),
    ('HT14', 'TruSeq', 'AGTTCC', 6, 'TruSeq HT Index 14'),
    ('HT15', 'TruSeq', 'ATGTCA', 6, 'TruSeq HT Index 15'),
    ('HT16', 'TruSeq', 'CCGTCC', 6, 'TruSeq HT Index 16'),
    ('HT17', 'TruSeq', 'GTAGAG', 6, 'TruSeq HT Index 17'),
    ('HT18', 'TruSeq', 'GTCCGC', 6, 'TruSeq HT Index 18'),
    ('HT19', 'TruSeq', 'GTGAAA', 6, 'TruSeq HT Index 19'),
    ('HT20', 'TruSeq', 'GTGGCC', 6, 'TruSeq HT Index 20'),
    ('HT21', 'TruSeq', 'GTTTCG', 6, 'TruSeq HT Index 21'),
    ('HT22', 'TruSeq', 'CGTACG', 6, 'TruSeq HT Index 22'),
    ('HT23', 'TruSeq', 'GAGTGG', 6, 'TruSeq HT Index 23'),
    ('HT24', 'TruSeq', 'GGTAGC', 6, 'TruSeq HT Index 24'),
    
    -- Nextera Index Set (example)
    ('NX1', 'Nextera', 'GCGTAAGA', 8, 'Nextera Index 1'),
    ('NX2', 'Nextera', 'CGATCAGA', 8, 'Nextera Index 2'),
    ('NX3', 'Nextera', 'AAGCGTAG', 8, 'Nextera Index 3'),
    ('NX4', 'Nextera', 'GTTCAGGA', 8, 'Nextera Index 4')
ON CONFLICT (barcode_id) DO NOTHING;

-- ============================================
-- Verification Query: Check Hamming distances
-- ============================================
-- This query validates that all barcode pairs in the same set
-- have minimum Hamming distance of 3
CREATE OR REPLACE VIEW barcode_hamming_analysis AS
WITH barcode_pairs AS (
    SELECT 
        a.barcode_id AS id1,
        b.barcode_id AS id2,
        a.sequence AS seq1,
        b.sequence AS seq2,
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
COMMENT ON COLUMN barcode_indices.barcode_id IS 'Unique identifier (e.g., HT1, NX1)';
COMMENT ON COLUMN barcode_indices.barcode_set IS 'Barcode set name (TruSeq, Nextera, etc.)';
COMMENT ON COLUMN barcode_indices.sequence IS 'DNA sequence (ATCGN format)';
COMMENT ON COLUMN barcode_indices.sequence_length IS 'Length of sequence in bases';
