# SPDX-License-Identifier: MIT
"""
v1.1 Advanced Analytics Schema — SRS FR-3.11–FR-3.16.

Creates the nine storage tables required to build out the advanced
Pulse-driven analytics and LLM/RAG features introduced in SRS v1.1, and
attaches append-only (BEFORE UPDATE/DELETE rejection) triggers to each so
they inherit the 21 CFR Part 11 immutability posture of the v1.0 tables
(SRS FR-3.8.1).

The nine tables and their SRS mapping:
  - simulation_scenarios   (FR-3.16 scenario specification/seeds)
  - scenario_runs          (FR-3.16 executed run + aggregated outputs)
  - synthetic_cohorts      (FR-3.13 digital-twin cohort definitions)
  - chemistry_profiles     (FR-3.12 clinical chemistry vectors)
  - pkpd_worklists         (FR-3.11 in silico PK/PD pipetting manifests)
  - cfdna_sandbox_runs     (FR-3.14 MRD / cfDNA sandbox + LOD results)
  - clinical_text_outputs  (FR-3.15 LLM/RAG narratives with provenance)
  - llm_runs               (FR-3.15 LLM invocation metadata)
  - rag_templates          (FR-3.15 static RAG template registry)

A foreign-key chain materializes the build-out order:
  simulation_scenarios -> scenario_runs ->
    {synthetic_cohorts, chemistry_profiles, pkpd_worklists,
     cfdna_sandbox_runs, llm_runs, clinical_text_outputs}

Audit logging is intentionally NOT a per-table trigger here: it stays an
application-layer concern via the existing ``insert_audit_log()`` helper
(consistent with v1.0). This migration only enforces storage immutability.

Revision ID: 0007_v1_1_advanced_analytics
Revises: 0006_complete_compliance_tables
Create Date: 2026-07-26
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
revision = '0007_v1_1_advanced_analytics'
down_revision = '0006_complete_compliance_tables'
branch_labels = None
depends_on = None

# Tables in FK-dependency (creation) order.
NEW_TABLES = [
    'rag_templates',
    'simulation_scenarios',
    'scenario_runs',
    'synthetic_cohorts',
    'chemistry_profiles',
    'pkpd_worklists',
    'cfdna_sandbox_runs',
    'llm_runs',
    'clinical_text_outputs',
]


def upgrade():
    # --- Defensive (idempotent) trigger functions ---
    # These are created by 0002_extensions_triggers in the chain; re-defining
    # them here with OR REPLACE keeps this migration self-contained.
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

    # --- 1. rag_templates (FR-3.15.3, C9) — read-only after bulk load ---
    op.create_table(
        'rag_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(255), nullable=False),
        sa.Column('template_name', sa.String(255), nullable=False),
        sa.Column('template_type', sa.String(100), nullable=True),
        sa.Column('source_path', sa.String(512), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id'),
    )
    op.create_index('idx_rag_templates_id', 'rag_templates', ['template_id'])
    op.create_index('idx_rag_templates_type', 'rag_templates', ['template_type'])

    # --- 2. simulation_scenarios (FR-3.16.1) — append-only after finalization ---
    op.create_table(
        'simulation_scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_uid', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_modules', sa.JSONB(), nullable=False),
        sa.Column('seed', sa.JSONB(), nullable=False),
        sa.Column('config', sa.JSONB(), nullable=True),
        sa.Column('is_finalized', sa.Boolean(), server_default=text("false"), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scenario_uid'),
    )
    op.create_index('idx_simulation_scenarios_uid', 'simulation_scenarios', ['scenario_uid'])

    # --- 3. scenario_runs (FR-3.16.2/3.16.3/3.16.4) — append-only ---
    op.create_table(
        'scenario_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_uid', sa.String(36), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=True),
        sa.Column('seed', sa.JSONB(), nullable=True),
        sa.Column('status', sa.String(50), server_default=text("'queued'"), nullable=False),
        sa.Column('started_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMPTZ(), nullable=True),
        sa.Column('aggregated_outputs', sa.JSONB(), nullable=True),
        sa.Column('output_hashes', sa.JSONB(), nullable=True),
        sa.Column('downstream_results', sa.JSONB(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_uid'),
        sa.ForeignKeyConstraint(['scenario_id'], ['simulation_scenarios.id'], ),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name='scenario_runs_status_check'),
    )
    op.create_index('idx_scenario_runs_uid', 'scenario_runs', ['run_uid'])
    op.create_index('idx_scenario_runs_scenario', 'scenario_runs', ['scenario_id'])
    op.create_index('idx_scenario_runs_status', 'scenario_runs', ['status'])

    # --- 4. synthetic_cohorts (FR-3.13) — append-only ---
    op.create_table(
        'synthetic_cohorts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cohort_uid', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('demographic_distribution', sa.JSONB(), nullable=True),
        sa.Column('clinvar_variant_set', sa.JSONB(), nullable=True),
        sa.Column('physiological_baseline_ranges', sa.JSONB(), nullable=True),
        sa.Column('members', sa.JSONB(), nullable=True),
        sa.Column('is_synthetic', sa.Boolean(), server_default=text("true"), nullable=False),
        sa.Column('seed', sa.JSONB(), nullable=True),
        sa.Column('scenario_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cohort_uid'),
        sa.ForeignKeyConstraint(['scenario_run_id'], ['scenario_runs.id'], ),
    )
    op.create_index('idx_synthetic_cohorts_uid', 'synthetic_cohorts', ['cohort_uid'])
    op.create_index('idx_synthetic_cohorts_run', 'synthetic_cohorts', ['scenario_run_id'])

    # --- 5. chemistry_profiles (FR-3.12) — append-only ---
    op.create_table(
        'chemistry_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_uid', sa.String(36), nullable=False),
        sa.Column('simulation_id', sa.Integer(), nullable=True),
        sa.Column('patient_id', sa.String(255), nullable=True),
        sa.Column('chemistry_vectors', sa.JSONB(), nullable=False),
        sa.Column('clinvar_data', sa.JSONB(), nullable=True),
        sa.Column('fhir_bundle', sa.JSONB(), nullable=True),
        sa.Column('lims_response', sa.JSONB(), nullable=True),
        sa.Column('seed', sa.JSONB(), nullable=True),
        sa.Column('scenario_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_uid'),
        sa.ForeignKeyConstraint(['simulation_id'], ['simulations.id'], ),
        sa.ForeignKeyConstraint(['scenario_run_id'], ['scenario_runs.id'], ),
    )
    op.create_index('idx_chemistry_profiles_uid', 'chemistry_profiles', ['profile_uid'])
    op.create_index('idx_chemistry_profiles_sim', 'chemistry_profiles', ['simulation_id'])
    op.create_index('idx_chemistry_profiles_run', 'chemistry_profiles', ['scenario_run_id'])

    # --- 6. pkpd_worklists (FR-3.11) — append-only after finalization ---
    op.create_table(
        'pkpd_worklists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('worklist_uid', sa.String(36), nullable=False),
        sa.Column('plate_id', sa.Integer(), nullable=True),
        sa.Column('substance_name', sa.String(255), nullable=True),
        sa.Column('pk_parameters', sa.JSONB(), nullable=True),
        sa.Column('plasma_concentration_series', sa.JSONB(), nullable=True),
        sa.Column('target_matrix', sa.JSONB(), nullable=True),
        sa.Column('steps', sa.JSONB(), nullable=False),
        sa.Column('origin', sa.String(50), server_default=text("'pk_pd_loop'"), nullable=False),
        sa.Column('is_finalized', sa.Boolean(), server_default=text("false"), nullable=False),
        sa.Column('scenario_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('worklist_uid'),
        sa.ForeignKeyConstraint(['plate_id'], ['plates.id'], ),
        sa.ForeignKeyConstraint(['scenario_run_id'], ['scenario_runs.id'], ),
        sa.CheckConstraint("origin = 'pk_pd_loop'", name='pkpd_worklists_origin_check'),
    )
    op.create_index('idx_pkpd_worklists_uid', 'pkpd_worklists', ['worklist_uid'])
    op.create_index('idx_pkpd_worklists_plate', 'pkpd_worklists', ['plate_id'])
    op.create_index('idx_pkpd_worklists_run', 'pkpd_worklists', ['scenario_run_id'])

    # --- 7. cfdna_sandbox_runs (FR-3.14) — append-only ---
    op.create_table(
        'cfdna_sandbox_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_uid', sa.String(36), nullable=False),
        sa.Column('simulation_id', sa.Integer(), nullable=True),
        sa.Column('cohort_id', sa.Integer(), nullable=True),
        sa.Column('stressor', sa.JSONB(), nullable=False),
        sa.Column('plasma_volume', sa.JSONB(), nullable=True),
        sa.Column('cfdna_concentration', sa.JSONB(), nullable=True),
        sa.Column('shedding_params', sa.JSONB(), nullable=True),
        sa.Column('lod_threshold', sa.JSONB(), nullable=True),
        sa.Column('detection_result', sa.String(50), nullable=True),
        sa.Column('lims_response', sa.JSONB(), nullable=True),
        sa.Column('scenario_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_uid'),
        sa.ForeignKeyConstraint(['simulation_id'], ['simulations.id'], ),
        sa.ForeignKeyConstraint(['cohort_id'], ['synthetic_cohorts.id'], ),
        sa.ForeignKeyConstraint(['scenario_run_id'], ['scenario_runs.id'], ),
        sa.CheckConstraint(
            "detection_result IS NULL OR detection_result IN ('pass', 'fail', 'pending')",
            name='cfdna_sandbox_runs_detection_result_check',
        ),
    )
    op.create_index('idx_cfdna_sandbox_runs_uid', 'cfdna_sandbox_runs', ['run_uid'])
    op.create_index('idx_cfdna_sandbox_runs_sim', 'cfdna_sandbox_runs', ['simulation_id'])
    op.create_index('idx_cfdna_sandbox_runs_cohort', 'cfdna_sandbox_runs', ['cohort_id'])
    op.create_index('idx_cfdna_sandbox_runs_run', 'cfdna_sandbox_runs', ['scenario_run_id'])

    # --- 8. llm_runs (FR-3.15) — append-only ---
    op.create_table(
        'llm_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_uid', sa.String(36), nullable=False),
        sa.Column('provider', sa.String(100), nullable=False),
        sa.Column('model_id', sa.String(255), nullable=True),
        sa.Column('prompt_hash', sa.String(64), nullable=True),
        sa.Column('template_id', sa.String(255), nullable=True),
        sa.Column('source_data_hash', sa.String(64), nullable=True),
        sa.Column('request_payload', sa.JSONB(), nullable=True),
        sa.Column('response_metadata', sa.JSONB(), nullable=True),
        sa.Column('scenario_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_uid'),
        sa.ForeignKeyConstraint(['scenario_run_id'], ['scenario_runs.id'], ),
    )
    op.create_index('idx_llm_runs_uid', 'llm_runs', ['run_uid'])
    op.create_index('idx_llm_runs_provider', 'llm_runs', ['provider'])
    op.create_index('idx_llm_runs_run', 'llm_runs', ['scenario_run_id'])

    # --- 9. clinical_text_outputs (FR-3.15.6) — append-only ---
    op.create_table(
        'clinical_text_outputs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('output_uid', sa.String(36), nullable=False),
        sa.Column('scenario_run_id', sa.Integer(), nullable=True),
        sa.Column('llm_run_id', sa.Integer(), nullable=True),
        sa.Column('text_type', sa.String(100), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('provenance', sa.JSONB(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('output_uid'),
        sa.ForeignKeyConstraint(['scenario_run_id'], ['scenario_runs.id'], ),
        sa.ForeignKeyConstraint(['llm_run_id'], ['llm_runs.id'], ),
    )
    op.create_index('idx_clinical_text_outputs_uid', 'clinical_text_outputs', ['output_uid'])
    op.create_index('idx_clinical_text_outputs_run', 'clinical_text_outputs', ['scenario_run_id'])
    op.create_index('idx_clinical_text_outputs_llm', 'clinical_text_outputs', ['llm_run_id'])

    # --- Append-only triggers (SRS FR-3.8.1) on all nine v1.1 tables ---
    for table in NEW_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_prevent_update ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_prevent_delete ON {table};")
        op.execute(f"""
            CREATE TRIGGER {table}_prevent_update
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION prevent_update();
        """)
        op.execute(f"""
            CREATE TRIGGER {table}_prevent_delete
                BEFORE DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION prevent_delete();
        """)


def downgrade():
    # Drop append-only triggers for all nine tables.
    for table in NEW_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_prevent_update ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_prevent_delete ON {table};")

    # Drop tables in reverse FK-dependency order.
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
