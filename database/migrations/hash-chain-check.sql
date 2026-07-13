-- Nightly Hash Chain Verification Query
-- Implements SRS FR-3.8.3 - Automated integrity checking
-- Designed for scheduled execution (e.g., cron job, pgAgent)
-- Date: 2026-07-13

-- ============================================
-- Configuration
-- ============================================

-- Set search path
SET search_path TO public;

-- ============================================
-- Hash Chain Verification Query
-- Returns detailed report of chain integrity
-- ============================================

WITH chain_verification AS (
    SELECT 
        id,
        table_name,
        operation,
        record_id,
        timestamp,
        previous_hash,
        current_hash,
        -- Compute expected hash
        encode(
            digest(
                COALESCE(previous_hash, '') ||
                table_name ||
                operation ||
                record_id::TEXT ||
                timestamp::TEXT ||
                COALESCE(user_id, '') ||
                COALESCE(data::TEXT, '{}')
            , 'sha256')
        , 'hex') AS computed_hash,
        -- Check if previous_hash matches expected
        CASE 
            WHEN id = 1 THEN 
                CASE WHEN previous_hash = '0000000000000000000000000000000000000000000000000000000000000000' 
                THEN TRUE ELSE FALSE END
            ELSE 
                previous_hash = LAG(current_hash) OVER (ORDER BY id)
        END AS prev_hash_valid,
        -- Check if current_hash matches computed
        current_hash = encode(
            digest(
                COALESCE(previous_hash, '') ||
                table_name ||
                operation ||
                record_id::TEXT ||
                timestamp::TEXT ||
                COALESCE(user_id, '') ||
                COALESCE(data::TEXT, '{}')
            , 'sha256')
        , 'hex') AS current_hash_valid
    FROM audit_log
    ORDER BY id ASC
)
SELECT 
    'Hash Chain Verification Report' AS report_title,
    NOW() AS verification_timestamp,
    COUNT(*) AS total_entries,
    SUM(CASE WHEN prev_hash_valid AND current_hash_valid THEN 1 ELSE 0 END) AS valid_entries,
    SUM(CASE WHEN NOT prev_hash_valid OR NOT current_hash_valid THEN 1 ELSE 0 END) AS broken_entries,
    CASE 
        WHEN SUM(CASE WHEN NOT prev_hash_valid OR NOT current_hash_valid THEN 1 ELSE 0 END) = 0 
        THEN 'OK' 
        ELSE 'BROKEN' 
    END AS integrity_status,
    -- Find first broken entry
    MIN(CASE WHEN NOT prev_hash_valid OR NOT current_hash_valid THEN id END) AS first_broken_id,
    -- Detailed broken entries
    jsonb_agg(
        jsonb_build_object(
            'id', id,
            'table_name', table_name,
            'operation', operation,
            'record_id', record_id,
            'timestamp', timestamp,
            'prev_hash_valid', prev_hash_valid,
            'current_hash_valid', current_hash_valid,
            'stored_hash', current_hash,
            'computed_hash', computed_hash
        )
    ) FILTER (WHERE NOT prev_hash_valid OR NOT current_hash_valid) AS broken_entries_detail
FROM chain_verification;

-- ============================================
-- Performance Metrics
-- ============================================

-- Query execution time (for NFR-P4: < 60 seconds on 1M rows)
SELECT 
    'Performance Metrics' AS metric_type,
    COUNT(*) AS rows_checked,
    NOW() AS query_end_time
FROM audit_log;

-- ============================================
-- Summary Statistics
-- ============================================

-- Entries by table
SELECT 
    table_name,
    COUNT(*) AS entry_count,
    MIN(timestamp) AS first_entry,
    MAX(timestamp) AS last_entry
FROM audit_log
GROUP BY table_name
ORDER BY table_name;

-- ============================================
-- Recommended Actions
-- ============================================

-- If integrity_status = 'BROKEN', recommend:
-- 1. Identify point of tampering (first_broken_id)
-- 2. Review audit logs around that timestamp
-- 3. Check for unauthorized database access
-- 4. Restore from backup if necessary
-- 5. Recompute hash chain from last known good entry

-- ============================================
-- Automation Example (pgAgent or cron)
-- ============================================

/*
-- Example cron job (runs daily at 2 AM):
0 2 * * * psql -U biosync_user -d biosync -f /path/to/hash-chain-check.sql | mail -s "BioSync Hash Chain Verification" admin@biosync.local

-- Or as a PostgreSQL function for pgAgent:
CREATE OR REPLACE FUNCTION run_nightly_hash_check()
RETURNS void AS $$
BEGIN
    -- Execute verification query
    -- Log results to a monitoring table
    INSERT INTO monitoring_log (check_type, result, timestamp)
    SELECT 
        'hash_chain',
        CASE WHEN COUNT(CASE WHEN NOT prev_hash_valid OR NOT current_hash_valid THEN 1 END) = 0 
        THEN 'OK' ELSE 'BROKEN' END,
        NOW()
    FROM (
        -- Same verification logic as above
        SELECT ...
    ) AS verification;
END;
$$ LANGUAGE plpgsql;
*/

-- ============================================
-- Comments
-- ============================================
COMMENT ON TABLE audit_log IS 'Append-only audit trail - run hash-chain-check.sql nightly for integrity verification';
