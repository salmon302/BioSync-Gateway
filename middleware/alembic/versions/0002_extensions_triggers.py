# SPDX-License-Identifier: MIT
"""
Extensions, append-only triggers, and hash chain functions.
Implements SRS FR-3.8.1 (trigger-level audit) and FR-3.8.3 (hash chain).

Reconciled against database/migrations/001-extensions.sql and
database/migrations/003-triggers.sql to be the Alembic single source of truth.

Revision ID: 0002
Revises: 0001_initial
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0002_extensions_triggers'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # --- Extensions (001-extensions.sql) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin;")

    # --- Append-only trigger functions (003-triggers.sql) ---
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_update()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is append-only. UPDATE operations are not permitted. Use INSERT for new records.', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Table % is append-only. DELETE operations are not permitted. Records cannot be removed.', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # --- Apply append-only triggers to all compliance tables ---
    # audit_log
    op.execute("DROP TRIGGER IF EXISTS audit_log_prevent_update ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_prevent_delete ON audit_log;")
    op.execute("""
        CREATE TRIGGER audit_log_prevent_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER audit_log_prevent_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # observations
    op.execute("DROP TRIGGER IF EXISTS observations_prevent_update ON observations;")
    op.execute("DROP TRIGGER IF EXISTS observations_prevent_delete ON observations;")
    op.execute("""
        CREATE TRIGGER observations_prevent_update
            BEFORE UPDATE ON observations
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER observations_prevent_delete
            BEFORE DELETE ON observations
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # plates
    op.execute("DROP TRIGGER IF EXISTS plates_prevent_update ON plates;")
    op.execute("DROP TRIGGER IF EXISTS plates_prevent_delete ON plates;")
    op.execute("""
        CREATE TRIGGER plates_prevent_update
            BEFORE UPDATE ON plates
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER plates_prevent_delete
            BEFORE DELETE ON plates
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # plate_wells
    op.execute("DROP TRIGGER IF EXISTS plate_wells_prevent_update ON plate_wells;")
    op.execute("DROP TRIGGER IF EXISTS plate_wells_prevent_delete ON plate_wells;")
    op.execute("""
        CREATE TRIGGER plate_wells_prevent_update
            BEFORE UPDATE ON plate_wells
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER plate_wells_prevent_delete
            BEFORE DELETE ON plate_wells
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # devices
    op.execute("DROP TRIGGER IF EXISTS devices_prevent_update ON devices;")
    op.execute("DROP TRIGGER IF EXISTS devices_prevent_delete ON devices;")
    op.execute("""
        CREATE TRIGGER devices_prevent_update
            BEFORE UPDATE ON devices
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER devices_prevent_delete
            BEFORE DELETE ON devices
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # simulations
    op.execute("DROP TRIGGER IF EXISTS simulations_prevent_update ON simulations;")
    op.execute("DROP TRIGGER IF EXISTS simulations_prevent_delete ON simulations;")
    op.execute("""
        CREATE TRIGGER simulations_prevent_update
            BEFORE UPDATE ON simulations
            FOR EACH ROW EXECUTE FUNCTION prevent_update();
    """)
    op.execute("""
        CREATE TRIGGER simulations_prevent_delete
            BEFORE DELETE ON simulations
            FOR EACH ROW EXECUTE FUNCTION prevent_delete();
    """)

    # --- Hash chain trigger function (003-triggers.sql) ---
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
    op.execute("DROP TRIGGER IF EXISTS audit_log_hash_chain ON audit_log;")
    op.execute("""
        CREATE TRIGGER audit_log_hash_chain
            BEFORE INSERT ON audit_log
            FOR EACH ROW EXECUTE FUNCTION compute_hash_chain();
    """)

    # --- Audit insert helper function ---
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

    # --- Hash chain verification function ---
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
                SELECT id, table_name, operation, record_id, timestamp, user_id, previous_hash, current_hash, data
                FROM audit_log
                ORDER BY id ASC
            LOOP
                IF rec.previous_hash != prev_hash THEN
                    integrity_status := 'broken';
                    broken_at_row_id := rec.id;
                    broken_at_table := rec.table_name;
                    RETURN NEXT;
                    RETURN;
                END IF;

                concat_data := rec.previous_hash ||
                              rec.table_name ||
                              rec.operation ||
                              rec.record_id::TEXT ||
                              rec.timestamp::TEXT ||
                              COALESCE(rec.user_id, '') ||
                              rec.data::TEXT;

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

    # --- Updated-at trigger function for devices/simulations ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS update_devices_updated_at ON devices;")
    op.execute("""
        CREATE TRIGGER update_devices_updated_at
            BEFORE UPDATE ON devices
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("DROP TRIGGER IF EXISTS update_simulations_updated_at ON simulations;")
    op.execute("""
        CREATE TRIGGER update_simulations_updated_at
            BEFORE UPDATE ON simulations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS update_simulations_updated_at ON simulations;")
    op.execute("DROP TRIGGER IF EXISTS update_devices_updated_at ON devices;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    op.execute("DROP FUNCTION IF EXISTS verify_hash_chain();")
    op.execute("DROP FUNCTION IF EXISTS insert_audit_log(VARCHAR, VARCHAR, INTEGER, VARCHAR, JSONB);")
    op.execute("DROP FUNCTION IF EXISTS compute_hash_chain();")
    op.execute("DROP TRIGGER IF EXISTS audit_log_hash_chain ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_delete();")
    op.execute("DROP FUNCTION IF EXISTS prevent_update();")
    op.execute("DROP EXTENSION IF EXISTS btree_gin;")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp";')
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
