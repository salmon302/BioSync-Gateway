# SPDX-License-Identifier: MIT
"""
Add previous_state and reason columns to audit_log; update hash chain to
include D_prev and R_i per SRS FR-3.8.3.

SRS FR-3.8.3 formula:
    H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i)

Previously the trigger omitted D_prev (prior row state) and R_i (change
reason). This migration adds the columns and rewrites the trigger.

Revision ID: 0005
Revises: 0003_seed_barcodes
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
revision = '0005_hash_chain_fields'
down_revision = '0003_seed_barcodes'
branch_labels = None
depends_on = None


def upgrade():
    # --- Add columns to audit_log (SRS FR-3.8.3) ---
    # previous_state: JSONB canonical form of the row BEFORE the change (D_prev)
    # reason: human-readable change justification (R_i)
    op.add_column('audit_log',
        sa.Column('previous_state', sa.JSONB(), nullable=True)
    )
    op.add_column('audit_log',
        sa.Column('reason', sa.Text(), nullable=True)
    )

    # --- Rewrite the hash chain trigger to include D_prev and R_i ---
    # Drop the old trigger and function
    op.execute("DROP TRIGGER IF EXISTS audit_log_hash_chain ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS compute_hash_chain();")

    # New trigger function implementing the full SRS FR-3.8.3 formula:
    #   H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i)
    op.execute("""
        CREATE OR REPLACE FUNCTION compute_hash_chain()
        RETURNS TRIGGER AS $$
        DECLARE
            prev_hash VARCHAR(64);
            concat_data TEXT;
            genesis_hash CONSTANT VARCHAR(64) := '0000000000000000000000000000000000000000000000000000000000000000';
        BEGIN
            -- Get the previous hash from the last row in audit_log (SRS FR-3.8.3: H_{i-1})
            SELECT current_hash INTO prev_hash
            FROM audit_log
            ORDER BY id DESC
            LIMIT 1;

            IF prev_hash IS NULL THEN
                prev_hash := genesis_hash;
            END IF;

            -- Concatenate all fields per SRS FR-3.8.3:
            --   H_{i-1} || T_i || U_i || D_prev || D_new || R_i
            concat_data := prev_hash ||
                           COALESCE(NEW.timestamp::TEXT, CURRENT_TIMESTAMP::TEXT) ||
                           COALESCE(NEW.user_id, '') ||
                           COALESCE(NEW.previous_state::TEXT, '{}') ||
                           COALESCE(NEW.data::TEXT, '{}') ||
                           COALESCE(NEW.reason, '');

            NEW.previous_hash := prev_hash;
            NEW.current_hash := encode(digest(concat_data, 'sha256'), 'hex');

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_log_hash_chain
            BEFORE INSERT ON audit_log
            FOR EACH ROW EXECUTE FUNCTION compute_hash_chain();
    """)

    # --- Update insert_audit_log helper to accept D_prev and R_i ---
    op.execute("DROP FUNCTION IF EXISTS insert_audit_log(VARCHAR, VARCHAR, INTEGER, VARCHAR, JSONB);")
    op.execute("""
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
    """)

    # --- Update verify_hash_chain to use the new formula ---
    op.execute("DROP FUNCTION IF EXISTS verify_hash_chain();")
    op.execute("""
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
                SELECT id, table_name, operation, record_id, timestamp, user_id,
                       previous_hash, current_hash, data, previous_state, reason
                FROM audit_log
                ORDER BY id ASC
            LOOP
                -- Check previous_hash linkage (H_{i-1})
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

                IF computed_hash != rec.current_hash THEN
                    integrity_status := 'broken';
                    broken_at_row_id := rec.id;
                    broken_at_table := rec.table_name;
                    RETURN NEXT;
                    RETURN;
                END IF;

                prev_hash := rec.current_hash;
            END LOOP;

            integrity_status := 'ok';
            broken_at_row_id := NULL;
            broken_at_table := NULL;
            RETURN NEXT;
            RETURN;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    # Drop updated trigger and function
    op.execute("DROP TRIGGER IF EXISTS audit_log_hash_chain ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS compute_hash_chain();")
    op.execute("DROP FUNCTION IF EXISTS verify_hash_chain();")
    op.execute("DROP FUNCTION IF EXISTS insert_audit_log(VARCHAR, VARCHAR, INTEGER, VARCHAR, JSONB, JSONB, TEXT);")

    # Recreate original trigger without D_prev/R_i
    op.execute("""
        CREATE OR REPLACE FUNCTION compute_hash_chain()
        RETURNS TRIGGER AS $$
        DECLARE
            prev_hash VARCHAR(64);
            concat_data TEXT;
            genesis_hash CONSTANT VARCHAR(64) := '0000000000000000000000000000000000000000000000000000000000000000';
        BEGIN
            SELECT current_hash INTO prev_hash
            FROM audit_log
            ORDER BY id DESC
            LIMIT 1;

            IF prev_hash IS NULL THEN
                prev_hash := genesis_hash;
            END IF;

            concat_data := prev_hash ||
                           TG_TABLE_NAME ||
                           TG_OP ||
                           NEW.record_id::TEXT ||
                           COALESCE(NEW.timestamp::TEXT, CURRENT_TIMESTAMP::TEXT) ||
                           COALESCE(NEW.user_id, '') ||
                           COALESCE(NEW.data::TEXT, '{}');

            NEW.previous_hash := prev_hash;
            NEW.current_hash := encode(digest(concat_data, 'sha256'), 'hex');

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER audit_log_hash_chain
            BEFORE INSERT ON audit_log
            FOR EACH ROW EXECUTE FUNCTION compute_hash_chain();
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION insert_audit_log(
            p_table_name VARCHAR(255),
            p_operation VARCHAR(10),
            p_record_id INTEGER,
            p_user_id VARCHAR(255),
            p_data JSONB
        ) RETURNS INTEGER AS $$
        DECLARE
            new_id INTEGER;
        BEGIN
            INSERT INTO audit_log (table_name, operation, record_id, user_id, data)
            VALUES (p_table_name, p_operation, p_record_id, p_user_id, p_data)
            RETURNING id INTO new_id;
            RETURN new_id;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Drop the new columns
    op.drop_column('audit_log', 'reason')
    op.drop_column('audit_log', 'previous_state')
