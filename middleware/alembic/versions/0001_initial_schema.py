# SPDX-License-Identifier: MIT
"""
Initial schema migration
Implements SRS §6.1 - Database Tables

Reconciled against database/migrations/002-schema.sql to be the single
authoritative source of truth (NFR-M3). Adds CHECK constraints, UUID
defaults, server_default timestamps, and append-only triggers for all
compliance tables.

Revision ID: 0001
Revises: 
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy import func, text

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('operation', sa.String(10), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=True),
        sa.Column('previous_hash', sa.String(64), nullable=True),
        sa.Column('current_hash', sa.String(64), nullable=False),
        sa.Column('data', JSONB(), nullable=False),
        sa.CheckConstraint("operation IN ('INSERT', 'UPDATE', 'DELETE')", name='audit_log_operation_check'),
        sa.CheckConstraint("current_hash ~ '^[a-f0-9]{64}$'", name='audit_log_current_hash_check'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_log_table_record', 'audit_log', ['table_name', 'record_id'])
    op.create_index('idx_audit_log_timestamp', 'audit_log', ['timestamp'])
    op.create_index('idx_audit_log_hash_chain', 'audit_log', ['id', 'previous_hash', 'current_hash'])

    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_identifier', sa.String(255), nullable=False),
        sa.Column('device_name', sa.String(255), nullable=False),
        sa.Column('manufacturer', sa.String(255), nullable=True),
        sa.Column('model_number', sa.String(100), nullable=True),
        sa.Column('device_type', sa.String(100), nullable=True),
        sa.Column('fhir_resource', JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_identifier')
    )
    op.create_index('idx_devices_identifier', 'devices', ['device_identifier'])
    op.create_index('idx_devices_type', 'devices', ['device_type'])

    # Create observations table
    op.create_table(
        'observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('observation_uid', UUID(as_uuid=True), server_default=text("uuid_generate_v4()"), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('patient_id', sa.String(255), nullable=True),
        sa.Column('observation_code', sa.String(100), nullable=False),
        sa.Column('value_quantity', JSONB(), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('timestamp', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('raw_data', JSONB(), nullable=True),
        sa.Column('filtered_data', JSONB(), nullable=True),
        sa.Column('fhir_resource', JSONB(), nullable=False),
        sa.CheckConstraint("value_quantity ? 'value' AND value_quantity ? 'unit'", name='observations_value_check'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('observation_uid')
    )
    op.create_index('idx_observations_device', 'observations', ['device_id'])
    op.create_index('idx_observations_patient', 'observations', ['patient_id'])
    op.create_index('idx_observations_timestamp', 'observations', ['timestamp'])
    op.create_index('idx_observations_code', 'observations', ['observation_code'])

    # Create plates table
    op.create_table(
        'plates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plate_uid', UUID(as_uuid=True), server_default=text("uuid_generate_v4()"), nullable=False),
        sa.Column('plate_name', sa.String(255), nullable=False),
        sa.Column('plate_type', sa.String(50), nullable=True),
        sa.Column('barcode_set', sa.String(100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.CheckConstraint("plate_type IN ('96-well', '384-well')", name='plates_plate_type_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plate_uid')
    )
    op.create_index('idx_plates_uid', 'plates', ['plate_uid'])
    op.create_index('idx_plates_type', 'plates', ['plate_type'])

    # Create plate_wells table
    op.create_table(
        'plate_wells',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plate_id', sa.Integer(), nullable=True),
        sa.Column('well_row', sa.Integer(), nullable=False),
        sa.Column('well_column', sa.Integer(), nullable=False),
        sa.Column('well_index', sa.Integer(), nullable=False),
        sa.Column('sample_id', sa.String(255), nullable=True),
        sa.Column('concentration', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('volume', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('status', sa.String(50), server_default=text("'pending'"), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.CheckConstraint('well_row BETWEEN 0 AND 15', name='plate_wells_well_row_check'),
        sa.CheckConstraint('well_column BETWEEN 0 AND 23', name='plate_wells_well_column_check'),
        sa.ForeignKeyConstraint(['plate_id'], ['plates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plate_id', 'well_row', 'well_column')
    )
    op.create_index('idx_plate_wells_plate', 'plate_wells', ['plate_id'])
    op.create_index('idx_plate_wells_status', 'plate_wells', ['status'])

    # Create barcode_indices table
    op.create_table(
        'barcode_indices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('index_name', sa.String(100), nullable=False),
        sa.Column('index_sequence', sa.String(255), nullable=False),
        sa.Column('barcode_set', sa.String(100), nullable=True),
        sa.Column('kit_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.CheckConstraint("kit_type IN ('TruSeq', 'Nextera', 'Custom')", name='barcode_indices_kit_type_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('index_sequence')
    )
    op.create_index('idx_barcode_indices_set', 'barcode_indices', ['barcode_set'])
    op.create_index('idx_barcode_indices_kit', 'barcode_indices', ['kit_type'])

    # Create simulations table
    op.create_table(
        'simulations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('simulation_uid', UUID(as_uuid=True), server_default=text("uuid_generate_v4()"), nullable=False),
        sa.Column('patient_id', sa.String(255), nullable=False),
        sa.Column('engine_state', JSONB(), nullable=False),
        sa.Column('status', sa.String(50), server_default=text("'active'"), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'paused', 'completed')", name='simulations_status_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('simulation_uid')
    )
    op.create_index('idx_simulations_uid', 'simulations', ['simulation_uid'])
    op.create_index('idx_simulations_status', 'simulations', ['status'])

    # Create telemetry_sessions table
    op.create_table(
        'telemetry_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_uid', UUID(as_uuid=True), server_default=text("uuid_generate_v4()"), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('patient_id', sa.String(255), nullable=True),
        sa.Column('start_time', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('end_time', sa.TIMESTAMPTZ(), nullable=True),
        sa.Column('status', sa.String(50), server_default=text("'active'"), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_uid')
    )
    op.create_index('idx_telemetry_sessions_device', 'telemetry_sessions', ['device_id'])
    op.create_index('idx_telemetry_sessions_patient', 'telemetry_sessions', ['patient_id'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('scopes', ARRAY(sa.Text()), server_default=text("'{}'"), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('last_login', sa.TIMESTAMPTZ(), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'clinician', 'researcher', 'qa_officer')", name='users_role_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])

    # Create human_factors_metrics table
    op.create_table(
        'human_factors_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_timestamp', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('steps_count', sa.Integer(), nullable=True),
        sa.Column('component', sa.String(100), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_hf_metrics_session', 'human_factors_metrics', ['session_id'])
    op.create_index('idx_hf_metrics_event', 'human_factors_metrics', ['event_type'])

    # Create external_cache table
    op.create_table(
        'external_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(255), nullable=False),
        sa.Column('cache_source', sa.String(50), nullable=True),
        sa.Column('response_data', JSONB(), nullable=False),
        sa.Column('cached_at', sa.TIMESTAMPTZ(), server_default=func.now(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMPTZ(), nullable=False),
        sa.CheckConstraint("cache_source IN ('AccessGUDID', 'ClinVar', 'Other')", name='external_cache_source_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key')
    )
    op.create_index('idx_external_cache_key', 'external_cache', ['cache_key'])
    op.create_index('idx_external_cache_expires', 'external_cache', ['expires_at'])

    # Append-only triggers for all compliance tables (SRS FR-3.8.1)
    # Applied in 0002_extensions_triggers.py alongside trigger functions.


def downgrade():
    op.drop_table('external_cache')
    op.drop_table('human_factors_metrics')
    op.drop_table('users')
    op.drop_table('telemetry_sessions')
    op.drop_table('simulations')
    op.drop_table('barcode_indices')
    op.drop_table('plate_wells')
    op.drop_table('plates')
    op.drop_table('observations')
    op.drop_table('devices')
    op.drop_table('audit_log')
