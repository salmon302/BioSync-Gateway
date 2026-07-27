-- Phase 1: Enhanced Append-Only Triggers and Hash Chain
-- Implements SRS FR-3.8.1 and FR-3.8.3
-- Date: 2026-07-13

-- ============================================
-- Drop existing triggers if they exist (for idempotency)
-- ============================================

DROP TRIGGER IF EXISTS audit_log_prevent_update ON audit_log;
DROP TRIGGER IF EXISTS audit_log_prevent_delete ON audit_log;
DROP TRIGGER IF EXISTS observations_prevent_update ON observations;
DROP TRIGGER IF EXISTS observations_prevent_delete ON observations;
DROP TRIGGER IF EXISTS plates_prevent_update ON plates;
DROP TRIGGER IF EXISTS plates_prevent_delete ON plates;
DROP TRIGGER IF EXISTS plate_wells_prevent_update ON plate_wells;
DROP TRIGGER IF EXISTS plate_wells_prevent_delete ON plate_wells;

-- ============================================
-- Enhanced Append-Only Trigger Functions
-- SRS FR-3.8.1: Trigger-level audit, not app-level
-- ============================================

-- Function to prevent UPDATE on append-only tables
CREATE OR REPLACE FUNCTION prevent_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. UPDATE operations are not permitted. Use INSERT for new records.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- Function to prevent DELETE on append-only tables
CREATE OR REPLACE FUNCTION prevent_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. DELETE operations are not permitted. Records cannot be removed.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Apply Append-Only Triggers to All Compliance Tables
-- ============================================

-- audit_log table (core compliance table)
CREATE TRIGGER audit_log_prevent_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER audit_log_prevent_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- observations table (telemetry data - SRS FR-3.8.1)
CREATE TRIGGER observations_prevent_update
    BEFORE UPDATE ON observations
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER observations_prevent_delete
    BEFORE DELETE ON observations
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- plates table (plate definitions)
CREATE TRIGGER plates_prevent_update
    BEFORE UPDATE ON plates
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER plates_prevent_delete
    BEFORE DELETE ON plates
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- plate_wells table (well data)
CREATE TRIGGER plate_wells_prevent_update
    BEFORE UPDATE ON plate_wells
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER plate_wells_prevent_delete
    BEFORE DELETE ON plate_wells
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- devices table (device registry - append-only for audit)
CREATE TRIGGER devices_prevent_update
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER devices_prevent_delete
    BEFORE DELETE ON devices
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- simulations table (Pulse Engine sessions)
CREATE TRIGGER simulations_prevent_update
    BEFORE UPDATE ON simulations
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER simulations_prevent_delete
    BEFORE DELETE ON simulations
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- human_factors_metrics table (uFMEA data - append-only)
CREATE TRIGGER human_factors_metrics_prevent_update
    BEFORE UPDATE ON human_factors_metrics
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER human_factors_metrics_prevent_delete
    BEFORE DELETE ON human_factors_metrics
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- barcode_indices table (Illumina dictionary - read-only after bulk load)
CREATE TRIGGER barcode_indices_prevent_update
    BEFORE UPDATE ON barcode_indices
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER barcode_indices_prevent_delete
    BEFORE DELETE ON barcode_indices
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- patients table (simulated demographics - append-only after creation)
CREATE TRIGGER patients_prevent_update
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER patients_prevent_delete
    BEFORE DELETE ON patients
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- device_metrics table (FHIR DeviceMetric - read-only after insertion)
CREATE TRIGGER device_metrics_prevent_update
    BEFORE UPDATE ON device_metrics
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER device_metrics_prevent_delete
    BEFORE DELETE ON device_metrics
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- dilution_worklists table (dilution manifests - append-only after finalization)
CREATE TRIGGER dilution_worklists_prevent_update
    BEFORE UPDATE ON dilution_worklists
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER dilution_worklists_prevent_delete
    BEFORE DELETE ON dilution_worklists
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- ============================================
-- Hash Chain Trigger Function
-- SRS FR-3.8.3: Cryptographic hash chain
-- Formula: H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i)
-- ============================================

CREATE OR REPLACE FUNCTION compute_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash VARCHAR(64);
    concat_data TEXT;
    genesis_hash CONSTANT VARCHAR(64) := '0000000000000000000000000000000000000000000000000000000000000000';
BEGIN
    -- Get the previous hash from the last row in audit_log (H_{i-1})
    SELECT current_hash INTO prev_hash
    FROM audit_log
    ORDER BY id DESC
    LIMIT 1;
    
    -- If no previous hash, start with genesis block
    IF prev_hash IS NULL THEN
        prev_hash := genesis_hash;
    END IF;
    
    -- Concatenate data for hashing per SRS FR-3.8.3:
    --   H_{i-1} || T_i || U_i || D_prev || D_new || R_i
    concat_data := prev_hash || 
                   COALESCE(NEW.timestamp::TEXT, CURRENT_TIMESTAMP::TEXT) ||
                   COALESCE(NEW.user_id, '') ||
                   COALESCE(NEW.previous_state::TEXT, '{}') ||
                   COALESCE(NEW.data::TEXT, '{}') ||
                   COALESCE(NEW.reason, '');
    
    -- Compute SHA-256 hash using pgcrypto
    NEW.previous_hash := prev_hash;
    NEW.current_hash := encode(digest(concat_data, 'sha256'), 'hex');
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply hash chain trigger to audit_log
DROP TRIGGER IF EXISTS audit_log_hash_chain ON audit_log;
CREATE TRIGGER audit_log_hash_chain
    BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION compute_hash_chain();

-- ============================================
-- Audit Log Insert Function
-- Helper function to insert audit entries from application
-- SRS FR-3.8.3: accepts D_prev (previous_state) and R_i (reason)
-- ============================================

CREATE OR REPLACE FUNCTION insert_audit_log(
    p_table_name VARCHAR(255),
    p_operation VARCHAR(10),
    p_record_id INTEGER,
    p_user_id VARCHAR(255),
    p_data JSONB,
    p_previous_state JSONB DEFAULT NULL,
    p_reason TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    new_id INTEGER;
BEGIN
    INSERT INTO audit_log (table_name, operation, record_id, user_id, data, previous_state, reason)
    VALUES (p_table_name, p_operation, p_record_id, p_user_id, p_data, p_previous_state, p_reason)
    RETURNING id INTO new_id;
    
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Hash Chain Verification Function
-- Returns broken row ID if chain is compromised
-- ============================================

CREATE OR REPLACE FUNCTION verify_hash_chain()
RETURNS TABLE (
    integrity_status VARCHAR(10),
    broken_at_row_id INTEGER,
    broken_at_table VARCHAR(255)
) AS $$
DECLARE
    prev_hash VARCHAR(64);
    genesis_hash CONSTANT VARCHAR(64) := '0000000000000000000000000000000000000000000000000000000000000000';
    rec RECORD;
    computed_hash VARCHAR(64);
    concat_data TEXT;
BEGIN
    prev_hash := genesis_hash;
    
    FOR rec IN 
        SELECT id, table_name, operation, record_id, timestamp, user_id, previous_hash, current_hash, data, previous_state, reason
        FROM audit_log
        ORDER BY id ASC
    LOOP
        -- Check if previous_hash matches expected (H_{i-1} linkage)
        IF rec.previous_hash != prev_hash THEN
            integrity_status := 'broken';
            broken_at_row_id := rec.id;
            broken_at_table := rec.table_name;
            RETURN NEXT;
            RETURN;
        END IF;
        
        -- Recompute hash with full SRS FR-3.8.3 formula:
        --   H_{i-1} || T_i || U_i || D_prev || D_new || R_i
        concat_data := rec.previous_hash || 
                      COALESCE(rec.timestamp::TEXT, CURRENT_TIMESTAMP::TEXT) ||
                      COALESCE(rec.user_id, '') ||
                      COALESCE(rec.previous_state::TEXT, '{}') ||
                      COALESCE(rec.data::TEXT, '{}') ||
                      COALESCE(rec.reason, '');
        
        computed_hash := encode(digest(concat_data, 'sha256'), 'hex');
        
        -- Check if computed hash matches stored hash
        IF computed_hash != rec.current_hash THEN
            integrity_status := 'broken';
            broken_at_row_id := rec.id;
            broken_at_table := rec.table_name;
            RETURN NEXT;
            RETURN;
        END IF;
        
        prev_hash := rec.current_hash;
    END LOOP;
    
    -- Chain is valid
    integrity_status := 'ok';
    broken_at_row_id := NULL;
    broken_at_table := NULL;
    RETURN NEXT;
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON FUNCTION prevent_update() IS 'Prevents UPDATE on append-only tables (SRS FR-3.8.1)';
COMMENT ON FUNCTION prevent_delete() IS 'Prevents DELETE on append-only tables (SRS FR-3.8.1)';
COMMENT ON FUNCTION compute_hash_chain() IS 'Computes cryptographic hash chain for audit_log (SRS FR-3.8.3)';
COMMENT ON FUNCTION verify_hash_chain() IS 'Verifies integrity of hash chain, returns broken row if compromised';
COMMENT ON FUNCTION insert_audit_log(VARCHAR, VARCHAR, INTEGER, VARCHAR, JSONB) IS 'Helper to insert audit entries with automatic hash chain';
