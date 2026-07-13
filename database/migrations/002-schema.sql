-- BioSync-Gateway Core Schema
-- Implements SRS §6.1 - Database Tables
-- Version: 1.0
-- Date: 2026-07-13

-- ============================================
-- Table 1: audit_log
-- Append-only audit trail with hash chain
-- ============================================
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    record_id INTEGER NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_id VARCHAR(255),
    previous_hash VARCHAR(64),
    current_hash VARCHAR(64) NOT NULL,
    data JSONB NOT NULL,
    CONSTRAINT audit_log_current_hash_check CHECK (current_hash ~ '^[a-f0-9]{64}$')
);

-- Index for efficient audit queries
CREATE INDEX idx_audit_log_table_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_hash_chain ON audit_log(id, previous_hash, current_hash);

-- ============================================
-- Table 2: devices
-- Medical device registry (AccessGUDID integration)
-- ============================================
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_identifier VARCHAR(255) UNIQUE NOT NULL,
    device_name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255),
    model_number VARCHAR(100),
    device_type VARCHAR(100),
    fhir_resource JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_devices_identifier ON devices(device_identifier);
CREATE INDEX idx_devices_type ON devices(device_type);

-- ============================================
-- Table 3: observations
-- FHIR Observation resources (telemetry data)
-- ============================================
CREATE TABLE IF NOT EXISTS observations (
    id SERIAL PRIMARY KEY,
    observation_uid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    device_id INTEGER REFERENCES devices(id),
    patient_id VARCHAR(255),
    observation_code VARCHAR(100) NOT NULL,
    value_quantity JSONB NOT NULL,
    unit VARCHAR(50),
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    raw_data JSONB,
    filtered_data JSONB,
    fhir_resource JSONB NOT NULL,
    CONSTRAINT observations_value_check CHECK (value_quantity ? 'value' AND value_quantity ? 'unit')
);

CREATE INDEX idx_observations_device ON observations(device_id);
CREATE INDEX idx_observations_patient ON observations(patient_id);
CREATE INDEX idx_observations_timestamp ON observations(timestamp DESC);
CREATE INDEX idx_observations_code ON observations(observation_code);

-- ============================================
-- Table 4: plates
-- Microplate definitions and metadata
-- ============================================
CREATE TABLE IF NOT EXISTS plates (
    id SERIAL PRIMARY KEY,
    plate_uid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    plate_name VARCHAR(255) NOT NULL,
    plate_type VARCHAR(50) CHECK (plate_type IN ('96-well', '384-well')),
    barcode_set VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by VARCHAR(255),
    metadata JSONB
);

CREATE INDEX idx_plates_uid ON plates(plate_uid);
CREATE INDEX idx_plates_type ON plates(plate_type);

-- ============================================
-- Table 5: plate_wells
-- Individual well data for microplates
-- ============================================
CREATE TABLE IF NOT EXISTS plate_wells (
    id SERIAL PRIMARY KEY,
    plate_id INTEGER REFERENCES plates(id) ON DELETE CASCADE,
    well_row INTEGER NOT NULL CHECK (well_row BETWEEN 0 AND 15),
    well_column INTEGER NOT NULL CHECK (well_column BETWEEN 0 AND 23),
    well_index INTEGER NOT NULL,
    sample_id VARCHAR(255),
    concentration DECIMAL(10, 4),
    volume DECIMAL(10, 4),
    status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB,
    UNIQUE(plate_id, well_row, well_column)
);

CREATE INDEX idx_plate_wells_plate ON plate_wells(plate_id);
CREATE INDEX idx_plate_wells_status ON plate_wells(status);

-- ============================================
-- Table 6: barcode_indices
-- Illumina UDI barcode dictionary
-- ============================================
CREATE TABLE IF NOT EXISTS barcode_indices (
    id SERIAL PRIMARY KEY,
    index_name VARCHAR(100) NOT NULL,
    index_sequence VARCHAR(255) NOT NULL UNIQUE,
    barcode_set VARCHAR(100),
    kit_type VARCHAR(50) CHECK (kit_type IN ('TruSeq', 'Nextera', 'Custom')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_barcode_indices_set ON barcode_indices(barcode_set);
CREATE INDEX idx_barcode_indices_kit ON barcode_indices(kit_type);

-- ============================================
-- Table 7: simulations
-- Pulse Engine simulation sessions
-- ============================================
CREATE TABLE IF NOT EXISTS simulations (
    id SERIAL PRIMARY KEY,
    simulation_uid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    patient_id VARCHAR(255) NOT NULL,
    engine_state JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    metadata JSONB
);

CREATE INDEX idx_simulations_uid ON simulations(simulation_uid);
CREATE INDEX idx_simulations_status ON simulations(status);

-- ============================================
-- Table 8: telemetry_sessions
-- WebSocket telemetry streaming sessions
-- ============================================
CREATE TABLE IF NOT EXISTS telemetry_sessions (
    id SERIAL PRIMARY KEY,
    session_uid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    device_id INTEGER REFERENCES devices(id),
    patient_id VARCHAR(255),
    start_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    end_time TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB
);

CREATE INDEX idx_telemetry_sessions_device ON telemetry_sessions(device_id);
CREATE INDEX idx_telemetry_sessions_patient ON telemetry_sessions(patient_id);

-- ============================================
-- Table 9: users
-- User accounts for JWT authentication
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'clinician', 'researcher', 'qa_officer')),
    scopes TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- ============================================
-- Table 10: human_factors_metrics
-- uFMEA data collection (SRS FR-3.9)
-- ============================================
CREATE TABLE IF NOT EXISTS human_factors_metrics (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    latency_ms INTEGER,
    steps_count INTEGER,
    component VARCHAR(100),
    metadata JSONB
);

CREATE INDEX idx_hf_metrics_session ON human_factors_metrics(session_id);
CREATE INDEX idx_hf_metrics_event ON human_factors_metrics(event_type);

-- ============================================
-- Table 11: external_cache
-- Cached external API responses
-- ============================================
CREATE TABLE IF NOT EXISTS external_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    cache_source VARCHAR(50) CHECK (cache_source IN ('AccessGUDID', 'ClinVar', 'Other')),
    response_data JSONB NOT NULL,
    cached_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_external_cache_key ON external_cache(cache_key);
CREATE INDEX idx_external_cache_expires ON external_cache(expires_at);

-- ============================================
-- Trigger Functions for Append-Only Enforcement
-- ============================================

-- Function to prevent UPDATE on append-only tables
CREATE OR REPLACE FUNCTION prevent_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. UPDATE operations are not permitted.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- Function to prevent DELETE on append-only tables
CREATE OR REPLACE FUNCTION prevent_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. DELETE operations are not permitted.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Apply Append-Only Triggers
-- SRS FR-3.8.1: Trigger-level audit, not app-level
-- ============================================

-- Apply to audit_log (core compliance table)
CREATE TRIGGER audit_log_prevent_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER audit_log_prevent_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- Apply to observations (telemetry data)
CREATE TRIGGER observations_prevent_update
    BEFORE UPDATE ON observations
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER observations_prevent_delete
    BEFORE DELETE ON observations
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- Apply to plates (plate definitions)
CREATE TRIGGER plates_prevent_update
    BEFORE UPDATE ON plates
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER plates_prevent_delete
    BEFORE DELETE ON plates
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- Apply to plate_wells (well data)
CREATE TRIGGER plate_wells_prevent_update
    BEFORE UPDATE ON plate_wells
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

CREATE TRIGGER plate_wells_prevent_delete
    BEFORE DELETE ON plate_wells
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- ============================================
-- Hash Chain Function
-- SRS FR-3.8.3: Cryptographic hash chain
-- ============================================

CREATE OR REPLACE FUNCTION compute_hash_chain()
RETURNS TRIGGER AS $$
DECLARE
    prev_hash VARCHAR(64);
    concat_data TEXT;
BEGIN
    -- Get the previous hash from the last row in audit_log
    SELECT current_hash INTO prev_hash
    FROM audit_log
    ORDER BY id DESC
    LIMIT 1;
    
    -- If no previous hash, start with genesis block
    IF prev_hash IS NULL THEN
        prev_hash := '0000000000000000000000000000000000000000000000000000000000000000';
    END IF;
    
    -- Concatenate data for hashing
    concat_data := prev_hash || 
                   NEW.table_name || 
                   NEW.operation || 
                   NEW.record_id::TEXT || 
                   NEW.timestamp::TEXT || 
                   COALESCE(NEW.user_id, '') || 
                   NEW.data::TEXT;
    
    -- Compute SHA-256 hash
    NEW.previous_hash := prev_hash;
    NEW.current_hash := encode(digest(concat_data, 'sha256'), 'hex');
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply hash chain trigger to audit_log
CREATE TRIGGER audit_log_hash_chain
    BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION compute_hash_chain();

-- ============================================
-- Updated timestamp trigger function
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at column
CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_simulations_updated_at
    BEFORE UPDATE ON simulations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Comments for documentation
-- ============================================
COMMENT ON TABLE audit_log IS 'Append-only audit trail with cryptographic hash chain (SRS §3.8)';
COMMENT ON TABLE devices IS 'Medical device registry with FHIR Device resources';
COMMENT ON TABLE observations IS 'FHIR Observation resources storing telemetry data';
COMMENT ON TABLE plates IS 'Microplate definitions for laboratory workflows';
COMMENT ON TABLE plate_wells IS 'Individual well data within microplates';
COMMENT ON TABLE barcode_indices IS 'Illumina UDI barcode dictionary for multiplexing';
COMMENT ON TABLE simulations IS 'Pulse Engine simulation sessions';
COMMENT ON TABLE telemetry_sessions IS 'WebSocket telemetry streaming sessions';
COMMENT ON TABLE users IS 'User accounts for JWT authentication';
COMMENT ON TABLE human_factors_metrics IS 'uFMEA data collection for human factors analysis';
COMMENT ON TABLE external_cache IS 'Cached external API responses (AccessGUDID, ClinVar)';
