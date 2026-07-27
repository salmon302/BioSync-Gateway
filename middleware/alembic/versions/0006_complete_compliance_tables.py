# SPDX-License-Identifier: MIT
"""
Add missing SRS §6.1 tables and complete append-only trigger coverage.

Creates:
  - patients (append-only after creation)
  - device_metrics (read-only after insertion)
  - dilution_worklists (append-only after finalization)

Adds append-only triggers to:
  - human_factors_metrics
  - barcode_indices

Also fixes the devices table: removes the conflicting BEFORE UPDATE trigger
(update_updated_at_column) so devices is truly read-only after insertion
(SRS §6.1: "Read-only after insertion").

Revision ID: 0006_complete_compliance_tables
Revises: 0005_hash_chain_fields
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB

# SQLAlchemy 2.0 compatibility shim (see 0001_initial_schema.py).
class _TIMESTAMPTZ(TIMESTAMP):
    def __init__(self, timezone=True, precision=None, **kw):
        super().__init__(timezone=timezone, precision=precision, **kw)
sa.TIMESTAMPTZ = _TIMESTAMPTZ
sa.JSONB = JSONB

# revision identifiers, used by Alembic.
revision = '0006_complete_compliance_tables'
down_revision = '0005_hash_chain_fields'
branch_labels = None
depends_on = None


def upgrade():
    # --- Create missing SRS §6.1 tables ---

    # patients table (append-only after creation)
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_uid', sa.String(36), nullable=False),
        sa.Column('synthetic_id', sa.String(255), nullable=False),
        sa.Column('demographics', sa.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patient_uid'),
        sa.UniqueConstraint('synthetic_id'),
    )
    op.create_index('idx_patients_uid', 'patients', ['patient_uid'])
    op.create_index('idx_patients_synthetic', 'patients', ['synthetic_id'])

    # device_metrics table (read-only after insertion)
    op.create_table(
        'device_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('metric_name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('operational_status', sa.String(50), nullable=True),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('measurement_period', sa.Float(), nullable=True),
        sa.Column('fhir_resource', sa.JSONB(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    )
    op.create_index('idx_device_metrics_device', 'device_metrics', ['device_id'])
    op.create_index('idx_device_metrics_name', 'device_metrics', ['metric_name'])

    # dilution_worklists table (append-only after finalization)
    op.create_table(
        'dilution_worklists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plate_id', sa.Integer(), nullable=True),
        sa.Column('sample_id', sa.String(255), nullable=False),
        sa.Column('initial_concentration', sa.Float(), nullable=False),
        sa.Column('initial_unit', sa.String(50), nullable=False),
        sa.Column('target_concentration', sa.Float(), nullable=False),
        sa.Column('target_unit', sa.String(50), nullable=False),
        sa.Column('steps', sa.JSONB(), nullable=False),
        sa.Column('total_volume_needed', sa.Float(), nullable=True),
        sa.Column('molar_mass', sa.Float(), nullable=True),
        sa.Column('warning_code', sa.String(100), nullable=True),
        sa.Column('is_finalized', sa.Boolean(), server_default=text("false"), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['plate_id'], ['plates.id'], ),
    )
    op.create_index('idx_dilution_worklists_plate', 'dilution_worklists', ['plate_id'])
    op.create_index('idx_dilution_worklists_sample', 'dilution_worklists', ['sample_id'])

    # --- Complete append-only trigger coverage (SRS FR-3.8.1) ---

    # human_factors_metrics (SRS §6.1: append-only)
    op.execute("DROP TRIGGER IF EXISTS human_factors_metrics_prevent_update ON human_factors_metrics;")
    op.execute("DROP TRIGGER IF EXISTS human_factors_metrics_prevent_delete ON human_factors_metrics;")
    op.execute("""
        CREATE TRIGGER human_factors_metrics_prevent_update
            BEFORE UPDATE ON human_factors_metrics
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER human_factors_metrics_prevent_delete
            BEFORE DELETE ON human_factors_metrics
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # barcode_indices (SRS §6.1: read-only after bulk load)
    op.execute("DROP TRIGGER IF EXISTS barcode_indices_prevent_update ON barcode_indices;")
    op.execute("DROP TRIGGER IF EXISTS barcode_indices_prevent_delete ON barcode_indices;")
    op.execute("""
        CREATE TRIGGER barcode_indices_prevent_update
            BEFORE UPDATE ON barcode_indices
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER barcode_indices_prevent_delete
            BEFORE DELETE ON barcode_indices
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # patients (SRS §6.1: append-only after creation)
    op.execute("DROP TRIGGER IF EXISTS patients_prevent_update ON patients;")
    op.execute("DROP TRIGGER IF EXISTS patients_prevent_delete ON patients;")
    op.execute("""
        CREATE TRIGGER patients_prevent_update
            BEFORE UPDATE ON patients
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER patients_prevent_delete
            BEFORE DELETE ON patients
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # device_metrics (SRS §6.1: read-only after insertion)
    op.execute("DROP TRIGGER IF EXISTS device_metrics_prevent_update ON device_metrics;")
    op.execute("DROP TRIGGER IF EXISTS device_metrics_prevent_delete ON device_metrics;")
    op.execute("""
        CREATE TRIGGER device_metrics_prevent_update
            BEFORE UPDATE ON device_metrics
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER device_metrics_prevent_delete
            BEFORE DELETE ON device_metrics
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # dilution_worklists (SRS §6.1: append-only after finalization)
    op.execute("DROP TRIGGER IF EXISTS dilution_worklists_prevent_update ON dilution_worklists;")
    op.execute("DROP TRIGGER IF EXISTS dilution_worklists_prevent_delete ON dilution_worklists;")
    op.execute("""
        CREATE TRIGGER dilution_worklists_prevent_update
            BEFORE UPDATE ON dilution_worklists
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER dilution_worklists_prevent_delete
            BEFORE DELETE ON dilution_worklists
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # --- Fix devices table: remove conflicting update_updated_at trigger ---
    # SRS §6.1 says devices is "Read-only after insertion", so the
    # update_updated_at_column trigger (which fires on UPDATE) is contradictory.
    # The append-only prevent_update trigger on devices already rejects all
    # UPDATEs, so the updated_at trigger is dead code that should be removed.
    op.execute("DROP TRIGGER IF EXISTS update_devices_updated_at ON devices;")


def downgrade():
    # Restore the devices updated_at trigger
    op.execute("""
        CREATE TRIGGER update_devices_updated_at
            BEFORE UPDATE ON devices
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # Drop new triggers
    for table in ['dilution_worklists', 'device_metrics', 'patients',
                  'barcode_indices', 'human_factors_metrics']:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_prevent_update ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_prevent_delete ON {table};")

    # Drop new tables
    op.drop_table('dilution_worklists')
    op.drop_table('device_metrics')
    op.drop_table('patients')
